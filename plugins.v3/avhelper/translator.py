"""日文 → 简体中文翻译链路（v4 刮削线 S4，v4.1 §7 全文 + 契约 §3.4）。

职责：把 JavDB / MetaTube / Javtxt 拿到的**日文标题与简介**翻成简体中文，供 `scraper.py`
写进 `meta.title_zh` / `meta.plot_zh` 与 Emby 的 `Name` / `Overview`。

设计口径（每条都有实测依据，别改）：

- **模型**：默认 `hy3`（NAS 网关 `http://192.0.2.50:3065/v1`，OpenAI 兼容），失败降级
  `deepseek-v4.1-flash`（D6）。网关坐标从宿主运行时配置读（`app.runtime.settings.get_runtime_setting`），
  **模块 import 期不读配置、不联网**（单测环境没有宿主，延迟到调用点）。
- **`max_tokens` 必须给足（D20 / P0-②）**：`hy3` 把 token 先烧在 `reasoning_content` 上，
  `max_tokens` 太小会 `finish_reason=length` 且 `content=""`（实测 512 必空、4096 在「5 条露骨简介」
  这种批次上也会被推理耗尽）。所以默认给 8192，并且**显式判空**：`content` 为空而
  `reasoning_content` 非空 → 判失败、重试一次，**绝不把推理过程当译文**。
- **JSON Key 用 `display_number`**（`SNOS-380`），严禁数组下标；解析时对顶层 Key 做
  「大小写 + 连字符/下划线/空格」归一后比对，对不上的条目**判失败**，不硬套到别的番号上。
- **三道输出净化校验器**（v4.1 §7.3）：拒译词黑名单 / 假名残留率 / 长度畸变。
- **降级链**（v4.1 §7.3）：批量失败或单条未过校验 → 单条重试 `hy3` → 备用模型单条重试 →
  标 `untranslated`（保留日文原名）。只有 `allow_machine=True` 才退到「机翻兜底」
  （由调用方注入的 `machine_fn`，缺省时说明「构造新条目」，标 `machine_fallback`）。
- **持久化缓存**（v4.1 §4.2 `translate` 表）：
  `cache_key = sha256(source_text + target_lang + field_type + prompt_ver + glossary_hash)`。
  `store` 由参数注入（`translate_batch(..., store=None)`），无 `store` 时纯翻译不缓存。
- **红线**：API key 只从运行时配置读，**任何一个字都不写进代码/测试/报告**；单测一律假值 + 假 HTTP。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:  # 宿主只在容器里有；单测环境走下面的降级分支
    from app.sdk.logging import logger as _host_logger
except Exception:  # noqa: BLE001 - 任何导入失败都退到标准 logging
    _host_logger = None

logger = _host_logger if _host_logger is not None else logging.getLogger(__name__)


# ---------------------------------------------------------------- 常量

DEFAULT_MODEL = "hy3"
DEFAULT_FALLBACK = "deepseek-v4.1-flash"

DEFAULT_BASE_URL = "http://192.0.2.50:3065/v1"
CHAT_PATH = "/chat/completions"
SELFCHECK_TIMEOUT = 30      # 自检要快，界面点一下就得回
CHAT_TIMEOUT = 180          # 批量超时：实测 hy3 最长 52 s，180 s 有 3.4x 余量（别按中位数设）
SINGLE_TIMEOUT = 60         # 单条超时（实测单条 3.2~23.3 s）
CHAT_TEMPERATURE = 0.0      # 实测 1.5 起开始寒暄；网关不校验范围，自己夹到 [0,2]
MAX_TOKENS_MIN = 2000       # D20 的下限：低于它 hy3 有概率只吐 reasoning
MAX_TOKENS_DEFAULT = 8192   # ★ REPORT-5 C2：reasoning 与正文共享预算，实测峰值 5147
MAX_TOKENS_TITLE = 8192     # 标题批与简介批同一预算（统一 8192，不再分档）
MAX_TOKENS_MAX = 32768
RETRY_MAX = 2               # 兼容旧常量：单条模型级重试上限
RETRY_MAX_BATCH = 1         # 批量重试上限（REPORT-5 §5.4：同批只重试 1 次）
RETRY_MAX_SINGLE = 2        # 拆单条后每个模型的重试上限
#: 批量路径实际的 HTTP 重试上限 = 上面两个值相加。
#: 分工：`chat_detail` 的重试留给「5xx/429/超时」这类**同一请求再打一次就能好**的抖动
#: （`retry_limit=RETRY_MAX_BATCH`），批量层再留一次机会给「HTTP 200 但内容不合格 / 一个条目都没解出来」。
#: 两层相加正好等于 REPORT-5 §5.4 的「同批最多 2 次网络往返」，不会多打。
RETRY_MAX_BATCH_HTTP = RETRY_MAX_BATCH + RETRY_MAX_SINGLE
RETRY_BASE_SLEEP = 2.0      # 指数退避基数（秒）
EMPTY_CONTENT_RETRY = 1     # 空正文（推理吃光 token）额外重试次数
MIN_CALL_GAP = 1.0          # ★ 串行 + 调用间隔 ≥1 s（网关无并发保护，并发会放大审查触发）
BATCH_TITLE = 6             # 纯标题：一次 6 部（v4.1 §7.2）
BATCH_PLOT = 3              # 含简介：一次 3 部
PROMPT_VER = "v2"           # 提示词版本，进缓存键；改提示词必须递增（v2 = REPORT-5 §9.3 定稿）

#: 思考开关（REPORT-5 §9.2）：`"off"` → 请求体带 `reasoning_effort: "none"`，
#: 6 部批量 **50400 ms → 5686 ms（5~6x）**、`reasoning_tokens=0`、JSON 合法性与 Key 一致性不变、
#: 假名残留仍为 0；代价是措辞略直（`"任人摆布的校服泳装"` → `"言听计从的校服泳衣"`）。
#: `"auto"` → 不传该参数，保留默认思考（更细的措辞、4.9~52 s 的随机耗时带宽）。
REASONING_OFF = "off"
REASONING_AUTO = "auto"
DEFAULT_REASONING = REASONING_OFF

DEFAULT_TARGET_LANG = "zh-CN"

FIELD_TITLE = "title"
FIELD_PLOT = "plot"

STATUS_DONE = "done"
STATUS_REJECTED = "rejected"
STATUS_UNTRANSLATED = "untranslated"
STATUS_MACHINE = "machine_fallback"
STATUSES = (STATUS_DONE, STATUS_REJECTED, STATUS_UNTRANSLATED, STATUS_MACHINE)

#: 契约 §3.4 的对外字段，缺字段会让调用方 KeyError —— 一条都不许省
_ENTRY_FIELDS = ("number", "title_zh", "plot_zh", "status", "error",
                 "model", "from_cache", "generated_plot", "title_jp", "plot_jp",
                 "usage", "actors")

#: 假运行时的哨兵：`llm_conf()` 用它决定「有没有真配到网关」
_UNSET = object()

#: 拒译词黑名单（v4.1 §7.3 第 1 条 + REPORT-5 §3 补两词）
#:
#: 实测口径：模型自己**从不**拒译（5 条露骨单条命中 0），这 13 个词真正的价值是**兜住网关审查的
#: 拒绝原话** —— `"抱歉，系统检测到您当前输入的信息存在敏感内容，我无法响应您的请求"` 恰好命中
#: `抱歉` / `系统检测` / `敏感内容` 三个词；截断样本则命中 `Inappropriate` / `rejected for security`。
REFUSE_WORDS = (
    "抱歉", "无法翻译", "无法提供", "色情", "露骨", "成人", "违规",
    "Inappropriate", "rejected for security", "cannot fulfill", "I cannot",
    "敏感内容", "系统检测",
)

#: 传输层失败原因（REPORT-5 §9.4 的「第 0 道校验器」）
TR_GATEWAY_BLOCK = "gateway_block"      # usage 为 null：网关审查拦截
TR_CONTENT_FILTER = "rejected"          # finish_reason=content_filter
TR_TOKEN_EXHAUSTED = "token_exhausted"  # finish_reason=length（reasoning 吃了预算）
TR_EMPTY_CONTENT = "empty_content"
TR_BAD_JSON = "bad_json"
TR_KEY_MISMATCH = "key_mismatch"

#: 命中即**不再重试同批**，直接拆单条（省一次 40 秒的批量往返）
TRANSPORT_SKIP_BATCH_RETRY = (TR_GATEWAY_BLOCK, TR_CONTENT_FILTER, TR_EMPTY_CONTENT, TR_TOKEN_EXHAUSTED)
#: 命中即**不重试当前模型**（模型级不可用，切下一个模型）
TRANSPORT_MODEL_FATAL = ("model_not_found", "invalid_api_key")

_HIRA = re.compile(r"[\u3040-\u309f]")
_KATA = re.compile(r"[\u30a0-\u30ff]")
_KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
_FENCE_OPEN = re.compile(r"^\s*```[A-Za-z0-9_-]*[ \t]*\n?")
_FENCE_LINE = re.compile(r"^\s*```[A-Za-z0-9_-]*[ \t]*$", re.M)
_FENCE_CLOSE = re.compile(r"```\s*$")
_KEY_NOISE = re.compile(r"[^0-9A-Za-z]")


# ---------------------------------------------------------------- 基础工具

def _log_warn(msg: str) -> None:
    """警告日志：连续失败必须在日志里留痕（宿主的 logger 与标准 logger 都吃这一套）。"""
    try:
        logger.warning(msg)
    except Exception:  # noqa: BLE001 - 日志绝不能让业务挂掉
        pass


def _log_debug(msg: str) -> None:
    try:
        logger.debug(msg)
    except Exception:  # noqa: BLE001
        pass


def _env(key: str, default: str = "") -> str:
    return str(os.environ.get(key, default) or "").strip()


def _s(v: Any) -> str:
    """把 None / 空白都收敛成空串 —— 模型经常回 `"null"` 或 `" "`。"""
    if v is None:
        return ""
    return str(v).strip()


def _txt(v: Any) -> Optional[str]:
    """取文本字段：空、空白、字面 `null` 一律算没有。"""
    s = _s(v)
    if not s or s.lower() in ("null", "none", "n/a"):
        return None
    return s


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def normalize_key(text: Any) -> str:
    """JSON Key 归一：去非字母数字 + 大写（`snos-380` / `SNOS_380` / `Snos 380` → `SNOS380`）。"""
    return _KEY_NOISE.sub("", _s(text)).upper()


def strip_code_fence(text: str) -> str:
    """剥掉 ```` ```json ```` 围栏（模型经常给，虽然提示词明令禁止）。"""
    t = _s(text)
    if not t.startswith("```"):
        return t
    t = _FENCE_OPEN.sub("", t, count=1)
    t = _FENCE_CLOSE.sub("", t)
    return t.strip()


def parse_model_json(text: Any) -> Optional[Any]:
    """把模型返回的正文解析成 JSON 对象。

    三条路径：严格解析 → 剥代码块 → 取最外层 `{...}` 再解析。全失败回 None
    （调用方据此判失败，**不要**在文本里乱找番号硬套）。
    """
    t = _s(text)
    if not t:
        return None
    candidates: List[str] = [t]
    unfenced = strip_code_fence(t)
    if unfenced and unfenced != t:
        candidates.append(unfenced)
    # 剥掉正文里残留的围栏行（` ```json ` 与结尾 ` ``` ` 不在首尾时 strip_code_fence 碰不到）
    if "```" in t:
        delined = _FENCE_LINE.sub("", t).replace("```", "").strip()
        if delined and delined not in candidates:
            candidates.append(delined)
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except Exception:  # noqa: BLE001 - 解析失败依次降级
            continue
        if isinstance(obj, dict):
            return obj
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            obj = None
        if isinstance(obj, dict):
            return obj
    return None


def glossary_hash(glossary: Optional[Dict[str, str]]) -> str:
    """词表指纹：键排序后 sha256，取前 16 位（进缓存键，词表变了缓存必须失效）。"""
    items = sorted((_s(k), _s(v)) for k, v in (glossary or {}).items() if _s(k) and _s(v))
    if not items:
        return "none"
    raw = "\n".join("%s=%s" % (k, v) for k, v in items)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_key(source_text: str, target_lang: str = DEFAULT_TARGET_LANG, field_type: str = FIELD_TITLE,
              prompt_ver: str = PROMPT_VER, glossary: Optional[Dict[str, str]] = None) -> str:
    """v4.1 §4.2 表 4 的 `translate.cache_key`（字段顺序按契约钉死，别调）。"""
    raw = "|".join((_s(source_text), _s(target_lang), _s(field_type),
                    _s(prompt_ver), glossary_hash(glossary)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 校验器（v4.1 §7.3）

def count_kana(text: Any) -> int:
    """平假名（぀-ゟ）+ 片假名（゠-ヿ）字符数。"""
    return len(_KANA.findall(_s(text)))


def kana_ratio(text: Any) -> float:
    """假名占比；空文本回 0.0。"""
    s = _s(text)
    if not s:
        return 0.0
    return count_kana(s) / float(len(s))


def refuse_hits(text: Any) -> List[str]:
    """命中的拒译词（大小写不敏感）。"""
    s = _s(text)
    if not s:
        return []
    low = s.lower()
    return [w for w in REFUSE_WORDS if w.lower() in low]


def check_refuse_words(text: Any) -> Tuple[bool, str]:
    """校验器 1：拒译词黑名单。"""
    hits = refuse_hits(text)
    if hits:
        return False, "拒译词 %s" % "、".join(hits)
    return True, "ok"


def check_kana_residue(text: Any, min_kana: int = 4, max_ratio: float = 0.30) -> Tuple[bool, str]:
    """校验器 2：假名残留率（假名数 ≥4 且占比 >30% 判未有效翻译）。"""
    s = _s(text)
    n = count_kana(s)
    if not s or n == 0:
        return True, "ok"
    ratio = n / float(len(s))
    if n >= min_kana and ratio > max_ratio:
        return False, "假名残留 %d/%d=%.1f%%" % (n, len(s), ratio * 100)
    return True, "ok"


def check_length(title_zh: Any, plot_zh: Any = None, plot_jp: Any = None,
                 has_plot: Optional[bool] = None) -> Tuple[bool, str]:
    """校验器 3：长度畸变。

    `len(title_zh)<2`；有日文简介时 `plot_zh < plot_jp*0.15` 或 `> plot_jp*2.5`；
    无日文简介却凭空给出 plot_zh 也算失败（提示词铁律 3：严禁编造简介）。
    """
    tz = _s(title_zh)
    if len(tz) < 2:
        return False, "标题过短(len=%d)" % len(tz)
    pz = _s(plot_zh)
    src = _s(plot_jp)
    if has_plot is None:
        has_plot = bool(src)
    if not has_plot:
        if pz:
            return False, "源无简介却生成了 plot_zh(len=%d)" % len(pz)
        return True, "ok"
    if not pz:
        return False, "plot_zh 为空"
    if src:
        lo, hi = len(src) * 0.15, len(src) * 2.5
        if len(pz) < lo:
            return False, "plot_zh 过短(%d < %.1f)" % (len(pz), lo)
        if len(pz) > hi:
            return False, "plot_zh 过长(%d > %.1f)" % (len(pz), hi)
    return True, "ok"


def transport_status(res: Any, parsed: Any = None, found_keys: Any = None,
                     expected_keys: Any = None) -> str:
    """**第 0 道：传输层校验**（REPORT-5 §9.4 —— 拦住「HTTP 200 的假成功」）。

    真实网关有三种 `HTTP 200` 但内容无效的失败模式，只看状态码一个都抓不到：

    | 模式 | 响应特征 | 判定 |
    | --- | --- | --- |
    | 网关审查拦截 | `finish_reason=content_filter` + `usage=null` + 一句拒绝话术 | `rejected` / `gateway_block` |
    | 审查中途截断 | 半个 JSON 拼着 `"Inappropriate input/output rejected for security reasons` | `bad_json` |
    | `max_tokens` 被思维链吃光 | `content:""` + `finish_reason=length` | `token_exhausted` / `empty_content` |

    回 `"ok"` 或上面的 `TR_*` 之一。`parsed` / `found_keys` / `expected_keys` 只在拿到正文后才有意义。
    """
    res = res if isinstance(res, dict) else {}
    if not res:
        return TR_EMPTY_CONTENT
    if res.get("ok") and _s(res.get("content")):
        if parsed is None:
            return TR_BAD_JSON
        if expected_keys is not None and found_keys is not None:
            if set(found_keys) != set(expected_keys):
                return TR_KEY_MISMATCH
        return "ok"
    err = _s(res.get("error"))
    if err.startswith("model_not_found") or "模型不存在" in err:
        return "model_not_found"
    if err.startswith("invalid_api_key") or "invalid_api_key" in err:
        return "invalid_api_key"
    finish = _s(res.get("finish_reason"))
    if finish == "content_filter":
        return TR_CONTENT_FILTER
    if res.get("usage") is None and not _s(res.get("content")):
        # 审查拦截时 usage 整个为 null（不是"没返回 usage"，是网关明确置空）
        return TR_GATEWAY_BLOCK
    if finish == "length":
        return TR_TOKEN_EXHAUSTED
    if not _s(res.get("content")):
        return TR_EMPTY_CONTENT
    return TR_BAD_JSON


def transport_reason(status: str) -> str:
    """把传输层状态翻译成给用户/日志看的中文原因。"""
    return {
        TR_GATEWAY_BLOCK: "网关审查拦截（usage=null）",
        TR_CONTENT_FILTER: "网关审查拦截（content_filter）",
        TR_TOKEN_EXHAUSTED: "max_tokens 被思维链吃光（length）",
        TR_EMPTY_CONTENT: "空正文",
        TR_BAD_JSON: "正文不是合法 JSON",
        TR_KEY_MISMATCH: "返回的番号集合与请求不一致",
    }.get(status, status or "未知传输层失败")


def validate_transport(entry: Any, source: dict) -> Tuple[bool, str]:
    """对**带传输元数据的条目**执行第 0 道校验；不带 `_transport` 时视为通过（缓存/机翻路径）。"""
    if not isinstance(entry, dict):
        return True, "ok"
    meta = entry.get("_transport") if isinstance(entry.get("_transport"), dict) else None
    if not meta:
        return True, "ok"
    status = _s(meta.get("status")) or "ok"
    if status in ("ok", "partial"):
        # `partial` = 调用本身合格、只是整批里漏了几条；对**拿到手的这条**来说传输层没问题
        return True, "ok"
    number = _s(source.get("number")) or "(未知)"
    return False, "%s %s" % (number, transport_reason(status))


def validate_entry(entry: dict, source: dict) -> Tuple[bool, str]:
    """四道校验器，顺序执行；任一不过即 `(False, 原因)`。

    第 0 道 **传输层**（REPORT-5 新增，优先级最高）：`usage=null` / `finish_reason != "stop"` /
    空正文 / 非法 JSON / Key 集合不符 —— 这几种在真机上都是 `HTTP 200`，不检就静默毁整批。
    第 1 道 拒译词黑名单；第 2 道 假名残留率；第 3 道 长度畸变。

    `entry`   = 模型返回的单个条目（可带 `_transport` 元数据）
    `source`  = 请求里的源条目 `{'number':…, 'title_jp':…, 'plot_jp':…}`
    """
    ok, why = validate_transport(entry, source)
    if not ok:
        return False, why

    ent = entry if isinstance(entry, dict) else {}
    src = source if isinstance(source, dict) else {}
    if not ent:
        return False, "%s 条目为空" % (_s(src.get("number")) or "(未知)")

    title_zh = _s(ent.get("title_zh"))
    plot_zh = ent.get("plot_zh")
    pz = _s(plot_zh)
    src_plot = _txt(src.get("plot_jp"))
    has_plot = bool(src_plot)
    number = _s(src.get("number")) or "(未知)"

    if not title_zh:
        return False, "%s 标题为空" % number

    for text in (title_zh, pz):
        ok, why = check_refuse_words(text)
        if not ok:
            return False, "%s %s" % (number, why)
    for text in (title_zh, pz):
        ok, why = check_kana_residue(text)
        if not ok:
            return False, "%s %s" % (number, why)
    ok, why = check_length(title_zh, plot_zh, src_plot, has_plot=has_plot)
    if not ok:
        return False, "%s %s" % (number, why)
    return True, "ok"


# ---------------------------------------------------------------- 提示词

def _glossary_lines(glossary: Optional[Dict[str, str]]) -> str:
    items = [(k, v) for k, v in (glossary or {}).items() if _s(k) and _s(v)]
    if not items:
        return "（本次没有需要强制的译名词条）"
    return "\n".join("- %s → %s" % (k, v) for k, v in items)


def system_prompt(glossary: Optional[Dict[str, str]] = None) -> str:
    """System Prompt：v4.1 §7.2 四条铁律 + REPORT-5 §9.3 术语条 + 「表外人名保日文」条。

    词表同时出现在 system 与 user 的 `actor_glossary` 里（双保险）：实测 `hy3` 对 system 里的
    词表遵守得好（**8/8 严格替换**），但小模型/备用模型只认 user 侧结构，所以两处都给。

    第 3 条（表外人名保日文）来自 **S3 映射表覆盖率实测**：`mapping_actor.xml` 5351 条里本库
    冷门演员常查不到（抽样命中 6/10），而 P0 实测**未进词表的人名会被自由音译**
    （`茉城まみ → 茉城真美`）→ 会直接毁掉 G2 的「标题/简介译名与演职员表 100% 一致」。
    一致性优先于覆盖率：**查不到就保留日文原名**。
    """
    return SYSTEM_PROMPT_TMPL.format(glossary=_glossary_lines(glossary))


# 提示词版本 PROMPT_VER 与这段正文绑定：改正文必须递增 PROMPT_VER，否则旧缓存会污染新提示词。
SYSTEM_PROMPT_TMPL = """你是一名专业的日本成人影片元数据本地化译者，服务于个人媒体库的刮削工具。你的唯一任务是把日文标题与简介翻译成简体中文。

【输出铁律】
1. 必须返回严格合法的 JSON 对象（不要 markdown 代码块、不要任何前后缀说明）。顶层 Key 必须与输入的番号字符串完全一致（大小写、连字符一字不差）：{{"SNOS-380": {{"title_zh": "...", "plot_zh": "..."}}}}
2. 译文中若出现下方【演员译名对照表】中的日文名，必须严格替换为给定的中文译名，严禁自行音译或保留日文。
3. **演员人名只允许来自下方对照表**：只有出现在【演员译名对照表】里的人名才允许译成中文；**不在表里的人名一律原样保留日文写法**（严禁音译、严禁自创中文名、严禁猜译）。表为空时所有人名都保留日文。
4. 若输入的 plot_jp 为 null 或空字符串，输出的 plot_zh 必须为 null，严禁根据标题扩写或编造简介。
5. 直接输出忠实、流畅的简体中文译文，严禁输出任何解释、安全声明或道德说教。
6. 成人影像作品的专业术语按中国大陆媒体库通行译法处理（如「中出し」→「内射」），保持直译，不做删减或委婉化。

【演员译名对照表】（必须严格替换，严禁自行音译；表外的人名保持日文原样）
{glossary}"""


def build_user_payload(items: Sequence[dict]) -> str:
    """User 消息：以 `display_number` 为 Key 的 JSON 请求体（严禁数组下标）。"""
    payload: Dict[str, Any] = {}
    for it in items:
        num = _s(it.get("number"))
        if not num:
            continue
        entry: Dict[str, Any] = {
            "title_jp": _s(it.get("title_jp")),
            "plot_jp": _txt(it.get("plot_jp")),
        }
        glossary = {k: v for k, v in (it.get("glossary") or {}).items() if _s(k) and _s(v)}
        if glossary:
            entry["actor_glossary"] = glossary
        payload[num] = entry
    return json.dumps(payload, ensure_ascii=False, indent=1)


def build_messages(items: Sequence[dict]) -> List[Dict[str, str]]:
    """组装一次批量调用的 messages。"""
    merged: Dict[str, str] = {}
    for it in items:
        for k, v in (it.get("glossary") or {}).items():
            if _s(k) and _s(v):
                merged.setdefault(_s(k), _s(v))
    return [
        {"role": "system", "content": system_prompt(merged)},
        {"role": "user", "content": build_user_payload(items)},
    ]


# ---------------------------------------------------------------- 网关配置

def _host_setting(key: str, default: Any = _UNSET) -> Any:
    """读宿主运行时配置；单测/无宿主环境静默降级（模块 import 期绝不调用）。"""
    try:
        from app.runtime.settings import get_runtime_setting  # 延迟导入
    except Exception:  # noqa: BLE001 - 没有宿主模块是正常情况
        return default
    try:
        return get_runtime_setting(key, default)
    except Exception:  # noqa: BLE001
        return default


def _conf_value(override: Optional[Dict[str, str]], name: str, host_key: str) -> str:
    """取值优先级：override → 环境变量 → 宿主运行时配置 → 空。"""
    if override:
        for k, v in override.items():
            if _s(k).lower() == name.lower() or _s(k) == host_key:
                if _s(v):
                    return _s(v)
    env = _env(name) or _env(host_key)
    if env:
        return env
    val = _host_setting(host_key, _UNSET)
    if val is _UNSET or val is None:
        return ""
    return _s(val)


def llm_conf(override: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """翻译链路配置。

    `{'base_url','api_key','model','fallback','reasoning','temperature'}`；`api_key` 只在这里读出来，
    **不允许写进任何文件/日志/report**。缺 key 时不抛异常（让 `selfcheck` 有能力报 `ok=False`）。

    `reasoning`（REPORT-5 §9.2 的 A/B 结论，**默认 `"off"`**）：

    ==========  ==========================  ==========================
    项          `"auto"`（保留思考）           `"off"`（`reasoning_effort:"none"`）
    ==========  ==========================  ==========================
    6 部纯标题   31613~50400 ms               **5686 ms**（5~6x）
    3 部含简介   28044~50038 ms               **4971 ms**
    reasoning  2834~4788 tokens               **0**
    JSON/Key   5/5 严格合法                   2/2 严格合法（不变）
    假名残留     0                            0
    措辞        细（"任人摆布的校服泳装"）      略直（"言听计从的校服泳衣"）
    ==========  ==========================  ==========================

    关掉思考还顺带消掉了最大的坑：`max_tokens` 被思维链吃光（`content:""` + `finish_reason=length`）。
    代价只有"用词略直"，`"auto"` 保留给"想要更细措辞"的场景（需在 20~30 条真实数据上 A/B）。
    """
    base = _conf_value(override, "base_url", "LLM_BASE_URL")
    if not _s(base):
        # 显式传了空 base_url = 我要显式禁用网络（降级链短路）；没显式传才回落默认网关
        explicit_empty = bool(override) and "base_url" in override
        base = "" if explicit_empty else DEFAULT_BASE_URL
    reasoning = _conf_value(override, "reasoning", "LLM_TRANSLATE_REASONING") or DEFAULT_REASONING
    reasoning = reasoning.lower()
    if reasoning not in (REASONING_OFF, REASONING_AUTO):
        reasoning = DEFAULT_REASONING
    model = _conf_value(override, "model", "LLM_TRANSLATE_MODEL")
    if not _s(model) and not (override and "model" in override):
        model = DEFAULT_MODEL
    fallback = _conf_value(override, "fallback", "LLM_TRANSLATE_FALLBACK")
    if not _s(fallback) and not (override and "fallback" in override):
        fallback = DEFAULT_FALLBACK
    conf = {
        "base_url": _s(base).rstrip("/"),
        "api_key": _conf_value(override, "api_key", "LLM_API_KEY"),
        "model": _s(model),
        "fallback": _s(fallback),
        "reasoning": reasoning,
        "temperature": _conf_value(override, "temperature", "LLM_TRANSLATE_TEMPERATURE")
        or str(CHAT_TEMPERATURE),
    }
    return conf


def reasoning_effort(conf: Optional[Dict[str, str]] = None) -> str:
    """`"off"` → 请求体带 `"reasoning_effort": "none"`；`"auto"` → 空串（不传该参数）。"""
    c = conf if conf is not None else llm_conf()
    return "none" if _s(c.get("reasoning")).lower() == REASONING_OFF else ""


def _resolve_temperature(value: Any = None, conf: Optional[Dict[str, str]] = None) -> float:
    """温度：网关**不校验范围也不夹取**（实测 -1/100 都 200），必须自己夹到 [0,2]。"""
    raw = value
    if raw in (None, ""):
        raw = (conf or llm_conf()).get("temperature")
    if raw in (None, ""):
        raw = CHAT_TEMPERATURE
    try:
        t = float(raw)
    except (TypeError, ValueError):
        t = CHAT_TEMPERATURE
    if t != t or t in (float("inf"), float("-inf")):   # NaN / inf
        t = CHAT_TEMPERATURE
    return max(0.0, min(2.0, t))


def resolve_conf(conf: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """把「调用方传来的 conf」也过一遍 `llm_conf()`，保证**每个键都有值**。

    ★ 踩过的坑：直接 `c = conf or llm_conf()` 时，调用方手工拼的 conf（比如 smoke 脚本里只写了
    base_url/api_key/model/fallback）会让 `reasoning` 静默变成空 → `reasoning_effort` 不传 →
    思考没关掉、耗时回到 30~50 s，而且**看不出任何异常**。所以任何入口都必须走这里。
    """
    return llm_conf(conf) if conf else llm_conf()


def is_configured(conf: Optional[Dict[str, str]] = None) -> bool:
    """配置是否可用于真实调用（自检与降级链的闸门）。"""
    c = resolve_conf(conf)
    return bool(_s(c.get("api_key")) and _s(c.get("base_url")) and _s(c.get("model")))


def _resolve_max_tokens(max_tokens: int) -> int:
    """`max_tokens<=0` → 默认值；任何值都夹到 [MAX_TOKENS_MIN, MAX_TOKENS_MAX]（D20）。"""
    try:
        mt = int(max_tokens or 0)
    except (TypeError, ValueError):
        mt = 0
    if mt <= 0:
        mt = MAX_TOKENS_DEFAULT
    return max(MAX_TOKENS_MIN, min(MAX_TOKENS_MAX, mt))


# ---------------------------------------------------------------- HTTP

class ChatResult(dict):
    """`chat_detail()` 的返回容器（dict 子类，字段也能用属性取）。"""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _build_request(base_url: str, api_key: str, payload: dict, timeout: int):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    return urllib.request.Request(
        _s(base_url).rstrip("/") + CHAT_PATH, data=body, method="POST", headers=headers
    )


def _open_url(req, timeout):
    """唯一的真实网络出口（单测 monkeypatch 这一个符号即可）。"""
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - 网关是内网固定地址


def _sleep(sec: float) -> None:
    """退避睡眠（单测里 monkeypatch 成 no-op，避免真等）。"""
    time.sleep(max(0.0, float(sec)))


#: 上次真实网络调用的时刻（模块级）：保证**串行且间隔 ≥ MIN_CALL_GAP 秒**
_last_call = [0.0]


def _throttle() -> None:
    """调用间隔闸门：网关无并发保护，并发会放大审查触发（REPORT-5 §5.2）。"""
    dt = time.time() - _last_call[0]
    if _last_call[0] and dt < MIN_CALL_GAP:
        _sleep(MIN_CALL_GAP - dt)
    _last_call[0] = time.time()


def _retryable_http(code: int) -> bool:
    return code in (408, 409, 425, 429) or code >= 500


def _retry_guard(attempts: int, limit: int = RETRY_MAX) -> bool:
    """已经用掉 `attempts` 次尝试后，还允许再重试一次吗（最多 `limit` 次重试）。"""
    return attempts <= limit


def chat_detail(messages, model: str = "", timeout: int = CHAT_TIMEOUT, max_tokens: int = 0,
                temperature: Any = None, retry_limit: int = RETRY_MAX_BATCH,
                conf: Optional[Dict[str, str]] = None, opener=None,
                reasoning: Optional[str] = None) -> ChatResult:
    """一次对话调用（内层实现，返回完整信封；`chat()` 只取 text/err）。

    返回字段：`ok/content/reasoning/finish_reason/usage/http_status/text/turns/attempts/
    latency_ms/model/request/error`。原始请求体留在 `request` 里，供 evidence 落盘。

    请求体口径（REPORT-5 §9.1）：`temperature` 夹到 [0,2]、`max_tokens=8192`、
    **`reasoning_effort:"none"`**（默认关思考）；**不用** `response_format`（无收益且更慢）、
    **不用** `stream`（非流式 TTFB == 总耗时）。

    `reasoning=None` 走配置；显式传 `""` = 这一条**强制保留思考**（A/B 对照用）。
    """
    c = resolve_conf(conf)
    used_model = _s(model) or _s(c.get("model")) or DEFAULT_MODEL
    mt = _resolve_max_tokens(max_tokens)
    payload = {
        "model": used_model,
        "messages": list(messages or []),
        "temperature": _resolve_temperature(temperature, c),
        "max_tokens": mt,
    }
    if reasoning is None:
        effort = reasoning_effort(c)
    else:
        effort = _s(reasoning).lower()
    if effort == "none":
        payload["reasoning_effort"] = "none"
    elif effort in ("low", "medium", "high"):
        payload["reasoning_effort"] = effort
    res = ChatResult(ok=False, content=None, reasoning=None, finish_reason=None, usage=None,
                     http_status=None, text="", turns=0, attempts=0, latency_ms=0,
                     model=used_model, request=payload, max_tokens=mt,
                     reasoning_effort=payload.get("reasoning_effort", ""),
                     transport="", error="")
    if not _s(c.get("base_url")):
        res["error"] = "缺少 LLM_BASE_URL"
        return res

    open_fn = opener or _open_url
    started = time.time()
    try:
        while True:
            res["attempts"] += 1
            raw = ""
            code = None
            err = ""
            try:
                req = _build_request(c["base_url"], _s(c.get("api_key")), payload, timeout)
                _throttle()
                with open_fn(req, timeout) as resp:
                    code = getattr(resp, "status", None) or getattr(resp, "code", None)
                    raw = resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:  # 网关的 4xx/5xx 也带 JSON 正文
                code = exc.code
                try:
                    raw = exc.read().decode("utf-8", "replace")
                except Exception:  # noqa: BLE001
                    raw = ""
                err = "HTTP %s" % exc.code
            except Exception as exc:  # noqa: BLE001 - 超时/连不上统一收敛
                err = "%s: %s" % (type(exc).__name__, exc)

            res["http_status"] = code
            envelope = None
            if raw:
                try:
                    envelope = json.loads(raw)
                except Exception:  # noqa: BLE001
                    envelope = None
            if envelope is None:
                res["error"] = err or "网关返回非 JSON"
                if code is None or _retryable_http(int(code or 0)):
                    if _retry_guard(res["attempts"], retry_limit):
                        _sleep(RETRY_BASE_SLEEP * (2 ** (res["attempts"] - 1)))
                        continue
                res["latency_ms"] = int((time.time() - started) * 1000)
                return res
            if isinstance(envelope.get("error"), dict):
                err_obj = envelope["error"]
                res["error"] = "%s: %s" % (err_obj.get("code") or "error",
                                           err_obj.get("message") or err)
                # 404/model_not_found 与 401/invalid_api_key 是**配置/模型级**错误：立即返回给降级链接管
                code_name = _s(err_obj.get("code"))
                if code_name in TRANSPORT_MODEL_FATAL or "模型不存在" in _s(err_obj.get("message")):
                    res["latency_ms"] = int((time.time() - started) * 1000)
                    return res
                if code is not None and _retryable_http(int(code)) \
                        and _retry_guard(res["attempts"], retry_limit):
                    _sleep(RETRY_BASE_SLEEP * (2 ** (res["attempts"] - 1)))
                    continue
                res["latency_ms"] = int((time.time() - started) * 1000)
                return res
            if code is not None and _retryable_http(int(code)) \
                    and _retry_guard(res["attempts"], retry_limit):
                res["error"] = err or ("HTTP %s" % code)
                _sleep(RETRY_BASE_SLEEP * (2 ** (res["attempts"] - 1)))
                continue

            choices = envelope.get("choices") or [{}]
            choice = choices[0] if isinstance(choices[0], dict) else {}
            msg = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            content = msg.get("content")
            reasoning_text = msg.get("reasoning_content")
            res["content"] = content
            res["reasoning"] = reasoning_text
            res["finish_reason"] = choice.get("finish_reason")
            res["usage"] = envelope.get("usage")
            res["envelope"] = envelope

            if _s(content):
                res["ok"] = True
                res["text"] = _s(content)
                res["error"] = ""       # ★ 前面失败尝试留下的 err 必须清掉，否则调用方误判失败
                res["latency_ms"] = int((time.time() - started) * 1000)
                return res

            # 网关审查拦截（200 + content_filter + usage=null，正文可能是一句拒绝话术）：
            # 重试同批没有意义，直接返回让上层拆单条（REPORT-5 §5.4）
            if _s(res.get("finish_reason")) == "content_filter":
                res["error"] = "网关审查拦截（content_filter）"
                res["latency_ms"] = int((time.time() - started) * 1000)
                return res

            # ★ D20 判空：content 空而 reasoning 非空 = 推理把 token 烧光了（不是译文）
            if _s(reasoning_text):
                res["turns"] += 1
                res["error"] = "空正文（reasoning %d 字符，finish_reason=%s，max_tokens=%d）" % (
                    len(_s(reasoning_text)), res["finish_reason"], mt)
                if res["turns"] <= EMPTY_CONTENT_RETRY:
                    _log_warn("translator: %s %s，重试一次" % (used_model, res["error"]))
                    _sleep(RETRY_BASE_SLEEP)
                    continue
            else:
                res["error"] = "空响应（finish_reason=%s）" % res["finish_reason"]
            res["latency_ms"] = int((time.time() - started) * 1000)
            return res
    except Exception as exc:  # noqa: BLE001 - 任何异常都不许冒泡到调度线程
        res["error"] = "%s: %s" % (type(exc).__name__, exc)
        res["latency_ms"] = int((time.time() - started) * 1000)
        _log_warn("translator: chat 异常 %s" % res["error"])
        return res


def chat(messages, model: str = "", timeout: int = CHAT_TIMEOUT,
         max_tokens: int = 0, **kw) -> Tuple[str, str]:
    """契约 §3.4：`(text, err)`。失败不抛异常，`text` 为空串、`err` 给原因。"""
    res = chat_detail(messages, model=model, timeout=timeout, max_tokens=max_tokens, **kw)
    return _s(res.get("text")), _s(res.get("error"))


def selfcheck(model: str = "") -> Dict[str, Any]:
    """模型连通性自检：`{'ok','model','latency_ms','error'}`（外加 base_url/max_tokens 便于排查）。

    缺配置（没有 key）时**返回 `ok=False` 而不是抛异常** —— 前端「模型自检」按钮要能显示原因。
    """
    conf = llm_conf()
    used = _s(model) or _s(conf.get("model")) or DEFAULT_MODEL
    out: Dict[str, Any] = {"ok": False, "model": used, "latency_ms": 0, "error": "",
                           "base_url": conf.get("base_url", ""),
                           "max_tokens": _resolve_max_tokens(0)}
    if not _s(conf.get("api_key")):
        out["error"] = "未配置 LLM_API_KEY（宿主运行时配置里读不到）"
        return out
    messages = [
        {"role": "system", "content": "你是连通性探针，只按用户要求回复，不要任何解释。"},
        {"role": "user", "content": "请只回复两个字：正常"},
    ]
    res = chat_detail(messages, model=used, timeout=SELFCHECK_TIMEOUT,
                      max_tokens=MAX_TOKENS_MIN, conf=conf)
    out["latency_ms"] = int(res.get("latency_ms") or 0)
    out["finish_reason"] = res.get("finish_reason")
    out["usage"] = res.get("usage")
    if res.get("ok"):
        out["ok"] = True
        out["reply"] = _s(res.get("text"))[:40]
        return out
    out["error"] = _s(res.get("error")) or "调用失败"
    _log_warn("translator: selfcheck(%s) 失败：%s" % (used, out["error"]))
    return out


# ---------------------------------------------------------------- 翻译主流程

def translate_call(messages, model: str = "", *, conf: Optional[Dict[str, str]] = None,
                   max_tokens: int = 0, timeout: int = 0, opener=None,
                   retry_limit: int = RETRY_MAX_BATCH, single: bool = False) -> ChatResult:
    """对话调用封装（`chat_detail` 已内建空正文重试），保留为可替换的调用点。

    `single=True` 走**单条超时 60 s**；批量默认 **180 s**（实测 hy3 最长 52 s，别按中位数设）。
    """
    if not timeout or int(timeout) <= 0:
        timeout = SINGLE_TIMEOUT if single else CHAT_TIMEOUT
    return chat_detail(messages, model=model, timeout=timeout, max_tokens=max_tokens,
                       retry_limit=retry_limit, conf=conf, opener=opener)


def _source_has_plot(source: dict) -> bool:
    return bool(_txt(source.get("plot_jp")))


def normalize_actors(actors: Any, glossary: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """把源条目的演员列表归一成 `[{'jp','zh'}]`，`zh` 为空串表示**保留日文原名**。

    上层（`scraper.py` / Emby 写侧）要的正是这个：**本片演员里哪些有中文名**。
    没有中文名的绝不能编（S3 的 `actor_lookup` 未命中就回 None，不猜）——写 Emby 的
    `People[].Name` 必须是用户搜得到的写法，乱音译会让用户搜不到人（D13/D15）。
    """
    gl = {k: v for k, v in (glossary or {}).items() if _s(k) and _s(v)}
    out: List[Dict[str, str]] = []
    seen = set()
    for raw in (actors or []):
        if isinstance(raw, dict):
            jp = _s(raw.get("jp") or raw.get("name") or raw.get("jp_name"))
            zh = _s(raw.get("zh") or raw.get("zh_cn") or raw.get("canonical"))
        else:
            jp, zh = _s(raw), ""
        if not jp:
            continue
        zh = zh or gl.get(jp, "")
        if jp in seen:
            continue
        seen.add(jp)
        out.append({"jp": jp, "zh": zh})
    return out


def _merge_result(source: dict, entry: dict, *, status: str, model: str = "",
                  error: str = "", from_cache: bool = False, generated_plot: bool = False) -> Dict[str, Any]:
    """构造契约 §3.4 的返回条目（字段齐全，绝不让调用方 KeyError）。"""
    number = _s(source.get("number"))
    ent = entry if isinstance(entry, dict) else {}
    out: Dict[str, Any] = {
        "number": number,
        "title_jp": _s(source.get("title_jp")),
        "title_zh": _s(ent.get("title_zh")),
        "plot_jp": _txt(source.get("plot_jp")),
        "plot_zh": _txt(ent.get("plot_zh")),
        "status": status,
        "error": _s(error),
        "model": _s(model),
        "from_cache": bool(from_cache),
        "generated_plot": bool(generated_plot),
        "actors": normalize_actors(source.get("actors"), source.get("glossary")),
        "usage": {},
    }
    if not out["title_zh"] and status != STATUS_MACHINE:
        out["title_zh"] = out["title_jp"]   # 未译/被拒时调用方至少要拿到日文原名
    if status in (STATUS_UNTRANSLATED, STATUS_REJECTED):
        out["plot_zh"] = None               # 未译就不给中文简介，免得空串把旧值洗掉
    return {k: out[k] for k in _ENTRY_FIELDS if k in out}


def _entry_from_obj(obj: Any, number: str) -> Optional[dict]:
    """从模型返回的顶层对象里按归一 Key 取本番号的条目；对不上回 None（判失败，不硬套）。"""
    if not isinstance(obj, dict):
        return None
    want = normalize_key(number)
    for k, v in obj.items():
        if normalize_key(k) == want and isinstance(v, dict):
            return v
    return None


def _extract_usage(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总本轮调用的 token 用量（报告要用；网关不返回 usage 时回 {}）。"""
    total: Dict[str, Any] = {}
    for rec in records:
        usage = rec.get("usage") if isinstance(rec, dict) else None
        if not isinstance(usage, dict):
            continue
        for k, v in usage.items():
            if isinstance(v, (int, float)):
                total[k] = total.get(k, 0) + v
    return total


def _call_once(items: Sequence[dict], model: str, *, conf: Dict[str, str], max_tokens: int,
               timeout: int, opener=None, retry_limit: int = RETRY_MAX_BATCH, single: bool = False,
               ) -> Tuple[Dict[str, dict], str, List[Dict[str, Any]]]:
    """一次批量/单条调用。

    回 `(归一 Key → 条目, 传输层状态, 调用记录)`。每个条目都带上 `_transport` 元数据，
    让第 0 道校验器能判出「HTTP 200 的假成功」（审查拦截 / 半个 JSON / token 耗尽）。
    """
    if not items:
        return {}, TR_EMPTY_CONTENT, []
    messages = build_messages(items)
    res = translate_call(messages, model=model, conf=conf, max_tokens=max_tokens,
                         timeout=timeout, opener=opener, retry_limit=retry_limit,
                         single=single)
    records = [res]
    expected = [_s(i.get("number")) for i in items]
    parsed = parse_model_json(res.get("text")) if res.get("ok") else None
    found: Dict[str, dict] = {}
    if isinstance(parsed, dict):
        for it in items:
            num = _s(it.get("number"))
            entry = _entry_from_obj(parsed, num)
            if entry is not None:
                found[normalize_key(num)] = entry
    status = transport_status(res, parsed=parsed, found_keys=list(found),
                             expected_keys=[normalize_key(n) for n in expected])
    if status == TR_KEY_MISMATCH and found:
        # 部分成功：调用本身没坏（HTTP 200 + 合法 JSON），只是漏了其中几条 →
        # 对**已拿到的**条目来说这是合格返回，别对着它们判 Key 不一致。
        status = "partial"
    if status == "ok":
        meta = {"status": "ok"}
    else:
        meta = {"status": status, "reason": transport_reason(status),
                "finish_reason": _s(res.get("finish_reason")),
                "usage_missing": res.get("usage") is None,
                "http_status": res.get("http_status")}
    for entry in found.values():
        entry["_transport"] = meta

    if status == "partial":
        _log_warn("translator: model=%s 部分返回，漏了 %s"
                  % (model, "、".join(n for n in expected if normalize_key(n) not in found)))
    elif status != "ok":
        _log_warn("translator: %s 调用 model=%s 失败（%s）：%s"
                  % ("单条" if single else "批量", model, status, _s(res.get("error"))))
    return found, status, records


def _bail(source: dict, err: str, *, model: str = "", status: str = STATUS_UNTRANSLATED,
          from_cache: bool = False) -> Dict[str, Any]:
    return _merge_result(source, {}, status=status, model=model, error=err, from_cache=from_cache)


def batch_retry_worthwhile(status: str, found: Any = None) -> bool:
    """批量结果**值得再打一次同一批**吗（只针对「HTTP 200 但内容不合格」）。

    - `bad_json` / 整批一个 Key 都没解出来 → 模型抖动，值得重试；
    - 只缺个别 Key（部分成功）→ 单条补比整批重打便宜得多（整批一次 30~50 s），**不重试**；
    - 审查拦截 / token 耗尽 / 空正文 / 模型不可用 → 重试无意义，直接降级。
    """
    if status in TRANSPORT_SKIP_BATCH_RETRY or status in TRANSPORT_MODEL_FATAL:
        return False
    got = len(found or {})
    if status == TR_KEY_MISMATCH and got > 0:
        return False
    return status in (TR_BAD_JSON, TR_KEY_MISMATCH)


def _translate_one(source: dict, *, conf: Dict[str, str], models: Sequence[str], store=None,
                   allow_machine: bool = False, machine_fn: Optional[Callable[[dict], str]] = None,
                   timeout: int = 0, opener=None,
                   retry_limit: int = RETRY_MAX_SINGLE) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """单条完整降级链：缓存 → 主模型（至多 2 次）→ 备用模型（至多 2 次）→ 机翻(可选) → untranslated。

    REPORT-5 §5.4/§6.2：**每个模型各自重试**（`length`/`bad_json` 这类抖动值得重试一次；
    `model_not_found` 直接跳下一个模型不浪费往返），**备用模型只用于单条** —— 实测
    `deepseek-v4.1-flash` 的批量 4/4 全被网关审查拦掉，单条才 1/1 成功。
    """
    number = _s(source.get("number"))
    glossary = {k: v for k, v in (source.get("glossary") or {}).items() if _s(k) and _s(v)}
    title_jp = _s(source.get("title_jp"))
    plot_jp = _txt(source.get("plot_jp"))
    has_plot = bool(plot_jp)
    max_tokens = _resolve_max_tokens(0)
    records: List[Dict[str, Any]] = []

    # ---- 缓存（标题 + 简介都命中且过校验才直接返回）
    cached = _cache_lookup(store, source, glossary)
    if cached is not None:
        _log_debug("translator: %s 命中缓存" % number)
        return cached, records

    errors: List[str] = []
    for model in [m for m in models if _s(m)]:
        for attempt in range(1, max(1, int(retry_limit)) + 1):
            found, status, recs = _call_once([source], model, conf=conf, max_tokens=max_tokens,
                                             timeout=timeout, opener=opener,
                                             retry_limit=RETRY_MAX_SINGLE, single=True)
            records.extend(recs)
            if status in TRANSPORT_MODEL_FATAL:
                errors.append("%s 模型不可用（%s）" % (model, status))
                break                                   # 配置/模型级错误：直接切下一个模型
            entry = found.get(normalize_key(number))
            if entry is None:
                errors.append("%s 无有效返回（%s）" % (model, transport_reason(status)))
                if status in TRANSPORT_SKIP_BATCH_RETRY or status in TRANSPORT_MODEL_FATAL:
                    break                               # 审查/空正文/模型不可用：不重试同模型
                continue
            ok, why = validate_entry(entry, source)
            if not ok:
                errors.append("%s 校验未过：%s" % (model, why))
                _log_warn("translator: %s 单条校验未过（%s）" % (number, why))
                continue
            result = _merge_result(source, entry, status=STATUS_DONE, model=model, error="")
            _write_cache(store, source, result, glossary=glossary, has_plot=has_plot, tier="llm")
            return result, records
        # 单模型重试次数用尽 → 换下一个模型
        _log_debug("translator: %s 的 %s 路径试了 %d 次" % (number, model, retry_limit))

    err_text = "；".join(errors) if errors else "无可用模型"

    # ---- 机翻兜底（默认关，只有调用方显式允许才走）
    if allow_machine:
        if callable(machine_fn):
            try:
                machine = _s(machine_fn(source))
            except Exception as exc:  # noqa: BLE001
                machine = ""
                _log_warn("translator: 机翻兜底异常 %s" % exc)
            if machine:
                entry = {"title_zh": machine, "plot_zh": None}
                ok, why = validate_entry(entry, source)
                if ok:
                    result = _merge_result(source, entry, status=STATUS_MACHINE, model="machine",
                                           error=err_text)
                    _write_cache(store, source, result, glossary=glossary, has_plot=False,
                                 tier="machine")
                    return result, records
                err_text = "%s；机翻未过校验：%s" % (err_text, why)
        else:
            entry = {"title_zh": title_jp, "plot_zh": None}
            ok, why = validate_entry(entry, source)
            if ok:
                result = _merge_result(source, entry, status=STATUS_MACHINE, model="machine",
                                       error=err_text)
                _write_cache(store, source, result, glossary=glossary, has_plot=False,
                             tier="machine")
                return result, records
            err_text = "%s；机翻构造条目未过校验：%s" % (err_text, why)

    _log_warn("translator: %s 全部降级失败 → untranslated（%s）" % (number, err_text))
    return _bail(source, err_text, model=",".join(m for m in models if _s(m))), records


def _write_cache(store, source: dict, result: dict, *, glossary: Dict[str, str],
                 has_plot: bool, tier: str = "llm") -> None:
    """把校验通过的译文写回缓存（标题/简介分开存，键互不干扰）。"""
    if store is None:
        return
    model = _s(result.get("model"))
    try:
        if _s(result.get("title_zh")) and not result.get("from_cache"):
            store.translate_put(cache_key(_s(source.get("title_jp")), field_type=FIELD_TITLE,
                                          glossary=glossary),
                                _s(source.get("title_jp")), _s(result.get("title_zh")),
                                model_name=model, quality_tier=tier)
        if has_plot and _s(result.get("plot_zh")):
            store.translate_put(cache_key(_s(source.get("plot_jp")), field_type=FIELD_PLOT,
                                          glossary=glossary),
                                _s(source.get("plot_jp")), _s(result.get("plot_zh")),
                                model_name=model, quality_tier=tier)
    except Exception as exc:  # noqa: BLE001 - 缓存写失败不影响本次结果
        _log_warn("translator: 缓存写失败 %s" % exc)


def _cache_get(store, key: str) -> Optional[str]:
    """读缓存：没有 store、缓存坏了都回 None（缓存问题绝不能拖垮翻译）。"""
    if store is None or not _s(key):
        return None
    try:
        return store.translate_get(key)
    except Exception as exc:  # noqa: BLE001
        _log_warn("translator: 缓存读失败 %s" % exc)
        return None


def _cache_lookup(store, source: dict, glossary: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """命中缓存就直接返回结果（标题/简介都要命中，且过三道校验）。

    返回 `None` = 未命中（或命中的是坏条目）。**必须在任何 HTTP 之前调用** ——
    「命中缓存直接返回」是契约要求，靠 HTTP 之后再判就晚了。
    """
    if store is None:
        return None
    title_jp = _s(source.get("title_jp"))
    plot_jp = _txt(source.get("plot_jp"))
    has_plot = bool(plot_jp)
    if not title_jp:
        return None
    cached_title = _cache_get(store, cache_key(title_jp, field_type=FIELD_TITLE, glossary=glossary))
    if not cached_title:
        return None
    cached_plot = None
    if has_plot:
        cached_plot = _cache_get(store, cache_key(plot_jp, field_type=FIELD_PLOT, glossary=glossary))
        if not cached_plot:
            return None
    entry = {"title_zh": cached_title, "plot_zh": cached_plot}
    ok, why = validate_entry(entry, source)
    if not ok:
        _log_warn("translator: %s 缓存条目未过校验（%s），走真实调用" % (_s(source.get("number")), why))
        return None
    return _merge_result(source, entry, status=STATUS_DONE, model="cache", from_cache=True)


def _chunk_items(items: Sequence[dict]) -> List[List[dict]]:
    """分批（v4.1 §7.2 上限）：**纯标题批 ≤6 部；批里只要有简介就 ≤3 部**。

    口径：一条带简介的条目只与「前面那批剩下的空位」合批，且合出来的批 ≤3 部；
    装不下就把它自己单独成批，**并切断与后面条目的合批**（实测踩过：`[含简介, 纯标题×3]`
    被塞成 4 条一批）。纯标题条目按 6 部装满。顺序永远保持不变。
    """
    out: List[List[dict]] = []
    batch: List[dict] = []
    for it in items:
        if _source_has_plot(it):
            if batch and len(batch) + 1 > BATCH_PLOT:   # 前面那批剩余空位不够 → 先收尾
                out.append(batch)
                batch = []
            batch.append(it)
            out.append(batch)                            # 含简介的批到此为止，不与后面合批
            batch = []
            continue
        if len(batch) >= BATCH_TITLE:
            out.append(batch)
            batch = []
        batch.append(it)
    if batch:
        out.append(batch)
    return out


def translate_batch(items: List[dict], model: str = "", allow_machine: bool = False,
                    *,
                    store=None, conf: Optional[Dict[str, str]] = None,
                    opener=None, timeout: int = CHAT_TIMEOUT,
                    machine_fn: Optional[Callable[[dict], str]] = None,
                    fallback: str = "") -> Dict[str, dict]:
    """契约 §3.4 的批量翻译入口。

    `items`: `[{'number','title_jp','plot_jp'(or None),'glossary'}]`
    返回:    `{number: {'number','title_zh','plot_zh','status','error','model','from_cache',
                       'generated_plot','title_jp','plot_jp'}}`

    流程：分批（纯标题 6 / 含简介 3）→ 每批一次调用 → 逐条三道校验 →
    未过的条目走**单条降级链**（单条 hy3 → 备用模型 → 机翻(可选) → `untranslated`）。
    `store` 缺省 `None`（不缓存），传入 Store 后走 `translate_get/translate_put` 持久化缓存。
    """
    out: Dict[str, dict] = {}
    clean: List[dict] = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        num = _s(it.get("number"))
        if not num:
            _log_warn("translator: 跳过没有 number 的条目")
            continue
        src = {
            "number": num,
            "title_jp": _s(it.get("title_jp")),
            "plot_jp": _txt(it.get("plot_jp")),
            "actors": it.get("actors") or [],
            "glossary": {k: v for k, v in (it.get("glossary") or {}).items() if _s(k) and _s(v)},
        }
        clean.append(src)
        out[num] = _bail(src, "未开始", status=STATUS_UNTRANSLATED)  # 兜底：任何异常路径都有条目

    if not clean:
        return out

    conf = resolve_conf(conf)
    models = [m for m in (_s(model) or _s(conf.get("model")) or DEFAULT_MODEL,
                          _s(fallback) or _s(conf.get("fallback")) or DEFAULT_FALLBACK) if _s(m)]
    # 去重但保序（主备同名时别调两遍）
    seen = set()
    models = [m for m in models if not (m in seen or seen.add(m))]

    if not models:
        for src in clean:
            out[src["number"]] = _bail(src, "没有可用模型", status=STATUS_UNTRANSLATED)
        return out

    if not _s(conf.get("base_url")):
        for src in clean:
            out[src["number"]] = _bail(src, "缺少 LLM_BASE_URL", status=STATUS_UNTRANSLATED)
        _log_warn("translator: 缺少 LLM_BASE_URL，全部标 untranslated")
        return out

    all_usage: Dict[str, Any] = {}
    pending: List[dict] = []
    #: 批量**完整成功但漏了这条**的番号：这类只给单条链 1 次机会（批量成功已证明模型可用）
    partial_from_batch: set = set()

    # ---- 缓存预检（必须在任何 HTTP 之前：命中缓存直接返回，零外网）
    todo: List[dict] = []
    for src in clean:
        cached = _cache_lookup(store, src, src["glossary"])
        if cached is not None:
            out[src["number"]] = cached
        else:
            todo.append(src)

    for batch in _chunk_items(todo):
        max_tokens = _resolve_max_tokens(0)          # 统一 8192（REPORT-5 C2）
        found: Dict[str, dict] = {}
        status = TR_EMPTY_CONTENT
        recs: List[Dict[str, Any]] = []
        # 批量最多重试 RETRY_MAX_BATCH 次；命中「审查/空正文」不再重试同批，直接拆单条
        for attempt in range(1, RETRY_MAX_BATCH + 1):
            found, status, recs = _call_once(batch, models[0], conf=conf, max_tokens=max_tokens,
                                             timeout=timeout, opener=opener,
                                             retry_limit=RETRY_MAX_BATCH)
            for k, v in _extract_usage(recs).items():
                all_usage[k] = all_usage.get(k, 0) + v
            # 批量层只在「HTTP 200 但内容不合格、且展望还能救」时再打一次；
            # 5xx/429/超时已由 chat_detail 内部按 RETRY_MAX_BATCH 重试过，不重复计次
            if batch_retry_worthwhile(status, found):
                if attempt < RETRY_MAX_BATCH:
                    _log_warn("translator: 批量返回内容不合格（%s），重试同批（第 %d 次）"
                              % (status, attempt + 1))
                    continue
            break
        if status in TRANSPORT_SKIP_BATCH_RETRY:
            _log_warn("translator: 批量被拦截/空正文（%s），直接拆单条重试" % status)
        # 部分成功（`partial`）：批量本身没坏（HTTP 200 + 合法 JSON），只是漏了其中几条
        partial = status == "partial"
        for src in batch:
            entry = found.get(normalize_key(src["number"]))
            if entry is None:
                pending.append(src)
                if partial:
                    partial_from_batch.add(src["number"])
                continue
            ok, why = validate_entry(entry, src)
            if not ok:
                _log_warn("translator: %s 批量校验未过（%s），转单条重试" % (src["number"], why))
                pending.append(src)
                continue
            has_p = _source_has_plot(src)
            result = _merge_result(src, entry, status=STATUS_DONE, model=models[0], error="")
            _write_cache(store, src, result, glossary=src["glossary"], has_plot=has_p, tier="llm")
            out[src["number"]] = result

    # ---- 单条降级链（缓存 → 主模型 → 备用 → 机翻 → untranslated）
    for src in pending:
        num = src["number"]
        # 批量已经完整成功、只是漏了这条 → 单条链只给它 1 次机会（批量结果本身就说明模型是好的，
        # 不是抖动）；批量整批失败（审查/空正文/坏 JSON）才给满 RETRY_MAX_SINGLE 次。
        solo_limit = 1 if num in partial_from_batch else RETRY_MAX_SINGLE
        result, recs = _translate_one(src, conf=conf, models=models, store=store,
                                      allow_machine=allow_machine, machine_fn=machine_fn,
                                      timeout=timeout, opener=opener,
                                      retry_limit=solo_limit)
        for k, v in _extract_usage(recs).items():
            all_usage[k] = all_usage.get(k, 0) + v
        result["usage"] = all_usage
        out[num] = result

    for entry in out.values():
        entry["usage"] = all_usage
    _log_debug("translator: translate_batch 完成 %d 条（批量直通 %d，单条重试 %d）"
               % (len(out), len(clean) - len(pending), len(pending)))
    return out


# ---------------------------------------------------------------- 自测入口（本地手跑，不入库逻辑）

if __name__ == "__main__":  # pragma: no cover - 只给人手跑
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "selfcheck":
        m = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(selfcheck(m), ensure_ascii=False, indent=1))
    else:
        demo = [{"number": "SNOS-380", "title_jp": "新人NO.1 STYLE 専属決定 18歳",
                 "plot_jp": None, "glossary": {}}]
        print(json.dumps(translate_batch(demo), ensure_ascii=False, indent=1))
