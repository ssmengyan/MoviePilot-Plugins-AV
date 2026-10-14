"""AVHelper v4 刮削线的**编排核心**（S7）：取数 → 写 Emby → 读侧统一投影。

本模块是整条刮削线的集成点，也是唯一的「三源取数 + Emby 写入 + 读投影」落点。
契约：`docs/AVHelper-刮削v4-模块契约.md` §3.6 / §3.6.1 / §3.6.2 / §4 / §4.2；
方案：`docs/AVHelper-最终方案-v4.1.md` §5 / §7 / §9；实测依据 `_tmp/p0/REPORT-{1,2,3,4}.md`。

公开接口（契约 §3.6）
----------------------

```python
resolve_key(number_or_key, item_key="") -> dict
film_view(key_or_number, item_key=None, store=None, library=None) -> dict   # 零外网
preview_one(key, *, store, cli, emby_client=None, opts=None) -> dict       # 不写
scrape_one(key, *, store, cli, emby_client, opts=None) -> dict
scrape_batch(keys, *, store, cli, emby_client, opts=None) -> list
rollback_item(item_key, *, store, emby_client) -> dict
sources_selfcheck(store, cli, opts=None) -> list
sync_actor_avatars(store, emby_client, *, limit=0, dry_run=True, namemap_mod=None, opts=None,
                   names=None) -> dict
ensure_namemap(store, opts=None) -> bool
```

依赖注入与纪律
--------------

- `store`（`store.Store`）、`cli`（`client.JavdbClient`）、`emby_client`（`emby.EmbyClient`）
  一律由调用方传进来，**本模块不读插件配置**：代理 / MetaTube 地址 / 裁切锚点 / 开关全部经
  `opts` 传入（见 `DEFAULT_OPTS`），这样单测能零外网、零配置跑。
- 只有 `scrape_one` / `scrape_batch` / `rollback_item` 会发写请求，且**写 Emby 前必须过
  `store.item_backup_save()` 闸门**（裁决 D7）；`preview_one` 与 `film_view()` 一行不写。

**延迟导入 + 缺失即降级**（`namemap` / `translator` 由 S3 / S4 交付，本线开工时可能还不存在）：

- `namemap` 缺失 → 演员名/标签不做映射（原名直出、标签仅去重），`translation_status` 照常。
- `translator` 缺失 → **只用原文**，不编造中文，`translation_status='untranslated'`。
- `imgproxy.crop_poster` 缺失 / 本机无 Pillow → 封面**直传原图**（P0-① 实测原图直传是合法写入）。

javdb-cli 的两条调用链（与契约 D8 一致）
--------------------------------------

1. **骨架**：`cli.detail(number)` —— 复用 `client.JavdbClient._run()`（私有方法，S7 说明：
   它同时给了失败留痕、连续 2 次失败冷却、`stdin=DEVNULL` 三条既有保证，另起一套只会漂）。
2. **图片**：`assets list --json` 拿 `type/url/width/height` 元数据定"要哪几张"，
   再用 `assets list --type image <1-based 位置>` 的 **`TYPE<TAB>URL` 管道格式**喂给
   `assets download`。⚠️ **`assets download` 只认管道格式，喂 JSON 会
   `invalid input at line 1 … (want TYPE<TAB>URL)`** —— 所以这两步必须自己起子进程
   （`_run()` 会给所有命令追加 `--json` 且按 JSON 解析 stdout，用它拿不到管道文本）。
   实测（2026-10-14，容器内）：`assets list SNOS-380 --type image 2` → 封面 800×538，
   `assets download -o` 落盘 147 237 B、Pillow 读到 `(800, 538) JPEG` —— **javdb-cli 已把
   XOR/Referer 那层处理掉**，落盘就是纯 JPEG（契约 D8）。
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlencode

from app.sdk.logging import logger

from . import emby

# 延迟导入：S3 / S4 交付前本模块必须照常工作（降级见模块 docstring）。
#
# ⚠️ 这里捕的是 **`Exception` 而不是 `ImportError`**：并行施工期兄弟模块随时可能处于
# 「文件已存在但正在写」的半成品状态（实测：某次跑测试时 `translator.py` 正被写到一半，
# `exec_module` 抛的是 `SyntaxError`）。`SyntaxError` 不是 `ImportError` 的子类，
# 只捕 ImportError 会让**整个 scraper 模块 import 失败**，把"某个可选能力缺失"放大成
# "刮削线整体挂掉"。可选依赖的降级必须对"缺失"和"坏掉"一视同仁。
try:                                    # pragma: no cover - 取决于并行施工进度
    from . import namemap
except Exception as _error:             # noqa: BLE001 - 故意的（见上）
    logger.warning(f"AVHelper scraper：namemap 不可用，演员/标签映射降级：{_error}")
    namemap = None                      # type: ignore[assignment]

try:                                    # pragma: no cover
    from . import translator
except Exception as _error:             # noqa: BLE001 - 故意的（见上）
    logger.warning(f"AVHelper scraper：translator 不可用，翻译降级为只用原文：{_error}")
    translator = None                   # type: ignore[assignment]

try:                                    # pragma: no cover
    from . import imgproxy
except Exception as _error:             # noqa: BLE001 - 故意的（见上）
    logger.warning(f"AVHelper scraper：imgproxy 不可用，封面直传原图：{_error}")
    imgproxy = None                     # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 常量：坐标、档位、上限（全部来自契约与 P0 实测，不在这里重新发明）
# ---------------------------------------------------------------------------

PLUGIN_ID = "AVHelper"
IMG_PROXY = f"/api/v1/plugin/{PLUGIN_ID}/img"

# 数据源名（写进 `scrape_log.source_name`，自检页与排障按它分组）
SRC_JAVDB = "javdb"
SRC_JAVTXT = "javtxt"
SRC_METATUBE = "metatube"
SRC_LLM = "llm"
SRC_EMBY_WRITE = "emby_write"
SRC_IMAGE = "javdb_assets"

# javtxt 主站与备用镜像（契约 §4.2：内容同源，`javtxt.me` 会 429，不要加）
JAVTXT_HOSTS: Tuple[str, ...] = ("https://javtxt.com", "https://javtxt.net", "https://javtxt.org")
# 单站点请求间隔（契约 §4.2 硬要求 ≥2s）。搜索要试多个变体，不节流会打爆站点。
JAVTXT_MIN_INTERVAL = 2.0

# MetaTube Server 地址：**代码里不留坐标**（同 `DEFAULT_PROXY` 的公开分发口径，0.7.0 起），
# 只从插件设置「刮削」栏的 `metatubeBase` 来；留空 = 混合模式不做 MetaTube 兜底，
# `metatube_lookup()` 会给出「未配置 MetaTube 地址」的显式 error，不炸、不编造。
METATUBE_BASE = ""
# MetaTube 单次 search 的 HTTP 超时：**必须 ≥25 秒**（S0b：服务端对 30 个源有硬 10 秒截止，
# 30 次实测全落在 [10000, 10047] ms；给 10 秒会把"它还在正常等上游"误判成超时）
METATUBE_TIMEOUT = 30

# 退避序列（契约 §5.3 / v4.1 §5.3）：6h → 24h → 72h → 7d → 14d
BACKOFF_HOURS: Tuple[int, ...] = (6, 24, 72, 168, 336)
# Tier1 只处理「缺简介」；`missing_core` 不算退避（等下次手动/定时）。
TIER1_COMPLETENESS = "missing_plot"

# `meta.raw_json` 总体积上限（v4.1 §5.2：剔掉磁力数组与评论，控制体积 ≤5KB）
RAW_JSON_LIMIT = 5120
# 单帧原始 javdb 详情在 raw_json 里的上限（给 javtxt/metatube 留出余量）
JAVDB_RAW_LIMIT = 4096

# 中文简介的"占位符"下限：短于这个长度且**同时有日文简介**时，判为不可用并转翻译链。
# 依据 S11 全库实测：`AKDL-332` 的 Javtxt 中文简介只有 9 字（站点占位），
# 而同类片子 `SSNI-378`/`SSNI-497` 是"有日文 177/163 字、中文没出来"→ 两者都该交 S4 翻译。
MIN_PLOT_ZH = 30

# 剧照上限（横版前 3 张，契约 §3.6.1 / D8）
SAMPLE_COUNT = 3
# 流派上限（契约写入矩阵：去重、剔删除规则词、上限 10 个）
GENRE_LIMIT = 10

# 版本角标文案（契约 §3.6.1 的 `badge`）
LEAK_BOTH = "中字流出"
ZH_SUB = "中字"
LEAK = "流出"

# 下载台账来源：只认插件自己下的（`library` 那批是"本来就在库里"的补种行，不算下载）
DOWNLOAD_SOURCES: Tuple[str, ...] = ("plugin", "queue")

# 图片下载用的临时目录前缀（`tempfile` 管生命周期，绝不留痕在数据根里）
_TMP_PREFIX = "avhelper-scrape-"

DEFAULT_OPTS: Dict[str, Any] = {
    "proxy": "",                     # javtxt / javdb 代理；**只从调用方传进来**
    "metatube_base": METATUBE_BASE,  # 只从设置台 `metatubeBase` 来（见 `scrape_opts()` 的映射）
    "javtxt_hosts": JAVTXT_HOSTS,
    "crop_anchor": "auto",           # auto / left / center / right / raw
    "write_images": True,            # 封面 + 剧照
    "write_samples": True,
    "translate": True,               # 允许调 translator（模块缺失时自动降级）
    "allow_machine": False,          # 「允许机翻兜底」开关（默认关，契约 D6）
    "plot_sources": ("javtxt", "metatube"),
    "force": False,                  # True = 无视已有 raw_json['javdb']，重抓骨架
    "javdb_assets": True,            # 是否调 `assets list/download`
    "log_sources": True,             # 是否把数据源结果写 scrape_log（film_view 不涉及）
    "fetch_cache": None,             # S11 抓取缓存（dict 或 coverage.json 路径）；命中则 0 站点请求
    "cache_only": False,             # True = 缓存的"没有"也是权威结论（dry-run 用，绝不回落真站点）
    "min_plot_zh": MIN_PLOT_ZH,      # 中文简介短于它就当站点占位符（同时有日文时才判无效）
    "javtxt_interval": JAVTXT_MIN_INTERVAL,
    "http_timeout": 30,
    "metatube_timeout": METATUBE_TIMEOUT,   # ≥25s，见 METATUBE_TIMEOUT 的说明
    "javdb_timeout": 60,
    "now": "",                       # 便于单测固定时间戳（ISO 字符串）
}

# 写入矩阵里要参与 diff 的字段（`preview_one` 的 `fields[]` 顺序即此）
MATRIX_FIELDS: Tuple[str, ...] = (
    "Name", "OriginalTitle", "Overview", "PremiereDate", "ProductionYear",
    "Studios", "SeriesName", "GenreItems", "CommunityRating", "People", "ProviderIds",
)


def _now(opts: Optional[Dict[str, Any]] = None) -> str:
    """当前时间（ISO 秒级、UTC，与 `store._now()` 同形）；`opts['now']` 可覆盖（单测用）。"""
    fixed = str((opts or {}).get("now") or "").strip()
    if fixed:
        return fixed
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _opt(opts: Optional[Dict[str, Any]], name: str, default: Any = None) -> Any:
    """取一个选项：调用方给的 → `DEFAULT_OPTS` → 调用点给的 `default`。

    `None` 一律当"没给"（调用方用 `opts={"crop_anchor": None}` 表达不了"要 None"，
    但本模块所有选项都有非 None 的合法值，所以这条简化是安全的）。
    """
    src = opts or {}
    if name in src and src[name] is not None:
        return src[name]
    if name in DEFAULT_OPTS:
        return DEFAULT_OPTS[name]
    return default


# ---------------------------------------------------------------------------
# 小工具（纯函数，全部可离线单测）
# ---------------------------------------------------------------------------

_WS = re.compile(r"[ \t\r\f\v]+")


def _clean_text(value: Any) -> str:
    """压平空白、去掉零宽字符与首尾空白（javtxt 的换行会原样进 Emby 的 Overview）。"""
    text = _html.unescape(str(value if value is not None else ""))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = _WS.sub(" ", text.replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(line.strip() for line in text.split("\n") if line.strip()).strip()


def _nfkc(text: Any) -> str:
    """NFKC 归一（契约 §6.1 的归一化第一步；`＠`/全角数字会在这里被收掉）。"""
    return unicodedata.normalize("NFKC", str(text or ""))


def _first(match: Optional[Any], group: int = 1) -> str:
    """正则结果里取一组文本（没有就空串）——省掉满屏的 `if m else ""`。"""
    if not match:
        return ""
    try:
        return str(match.group(group) or "")
    except (IndexError, AttributeError):                        # pragma: no cover - 防御
        return ""


def _to_float(value: Any) -> float:
    """宽松转 float（javdb 的 `score` 是字符串 `"4.33"`，也可能是空串/None）。"""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    """宽松转 int。"""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# 版本角标（`parse_av_number().version_tags` → 展示标签 / Emby Name 的 badge）
# ---------------------------------------------------------------------------

def version_labels(tags: Any) -> List[str]:
    """`version_tags` 字典 → 展示标签列表（`film_view.version_tags` 用它）。

    顺序固定（中字/流出 → 分辨率 → 碟号 → 版本字母），保证同一部片每次渲染都一样；
    `中字 + 流出` 合成一个 `中字流出`（与契约 §3.6.1 的 badge 口径一致，不拆成两行）。
    """
    data = tags if isinstance(tags, dict) else {}
    out: List[str] = []
    zh = bool(data.get("is_zh_sub"))
    leak = bool(data.get("is_uncensored_leak"))
    if zh and leak:
        out.append(LEAK_BOTH)
    elif zh:
        out.append(ZH_SUB)
    elif leak:
        out.append(LEAK)
    resolution = str(data.get("resolution") or "").strip()
    if resolution:
        out.append(resolution.upper() if resolution.isascii() else resolution)
    part = data.get("part_no")
    if part:
        out.append(f"CD{_to_int(part)}" if _to_int(part) else str(part))
    edition = str(data.get("edition") or "").strip()
    if edition:
        out.append(edition.upper() if len(edition) <= 2 else edition)
    if data.get("is_iso"):
        out.append("ISO")
    if data.get("is_vr"):
        out.append("VR")
    seen: List[str] = []
    for item in out:
        if item and item not in seen:
            seen.append(item)
    return seen


def version_badge(tags: Any) -> str:
    """`version_tags` → Emby `Name` 里的角标文本（无标签时空串）。

    契约 §3.6.1：`f"{display_number}{badge} {title}"`，`badge` 形如 ` [中字流出]`；
    多个标签用 `/` 连（`[中字/4K]`）。
    """
    labels = version_labels(tags)
    return f" [{'/'.join(labels)}]" if labels else ""


def apply_backoff(completeness: str, retry_count: Any, now: str = "") -> Tuple[int, str]:
    """按 `completeness` 决定下一次重试（返回 `(retry_count, next_retry_at)`）。

    契约 §5.3（Tier1 指数退避）：

    - `missing_plot` → `retry_count` 递增并排下一档 `6h → 24h → 72h → 7d → 14d`；
      跑完 5 档就**不再排**（`next_retry_at=''`），交给 Tier2 冷数据滚动；
    - `missing_core` → **不进退避**（`retry_count` 与 `next_retry_at` 原样返回）；
    - `full` → 清零（`0` / `''`）。
    """
    count = _to_int(retry_count)
    if str(completeness or "") != TIER1_COMPLETENESS:
        if str(completeness or "") == "full":
            return 0, ""
        return max(count, 0), ""
    count += 1
    if count > len(BACKOFF_HOURS):
        return count, ""
    stamp = str(now or "").strip() or _now()
    try:
        base = datetime.fromisoformat(stamp)
    except ValueError:                                          # pragma: no cover - 防御
        base = datetime.now(timezone.utc).replace(tzinfo=None)
    due = base + timedelta(hours=BACKOFF_HOURS[count - 1])
    return count, due.strftime("%Y-%m-%dT%H:%M:%S")


def completeness_of(title_zh: str, title_jp: str, plot_zh: str) -> str:
    """分档（契约 §5.3 的三档 + `store.meta_stats()` 的计数口径）。

    - 标题（中/日任一）都拿不到 → `missing_core`（骨架都没刮到，等下次手动/定时）；
    - 有标题没中文简介 → `missing_plot`（Tier1 退避，新片饥饿就靠它兜）；
    - 都有 → `full`。
    """
    if not (str(title_zh or "").strip() or str(title_jp or "").strip()):
        return "missing_core"
    if not str(plot_zh or "").strip():
        return "missing_plot"
    return "full"


def scrape_state_of(completeness: str) -> str:
    """`completeness` → `media_item.scrape_state`（读侧 `states.scrape` 直接透出）。"""
    if completeness == "full":
        return "scraped_full"
    if completeness == "missing_core":
        return "unscraped"
    return "scraped_partial"


# ---------------------------------------------------------------------------
# 键解析（番号 / 归一化 key / `emby:<id>` 实例键）
# ---------------------------------------------------------------------------

_ITEM_KEY = re.compile(r"^(?P<kind>[a-z]+):(?P<tail>.+)$", re.I)
_DIGITS_ONLY = re.compile(r"^\d{2,12}$")


def resolve_key(number_or_key: str, item_key: str = "") -> Dict[str, Any]:
    """把三种输入收敛成一套坐标（`{key, number, item_key, emby_id, ...}`）。

    认这三种（外加一个便利分支）：

    1. **展示番号**：`SNOS-380`、`ipzz00961` → `display_number` 归一成 `SNOS-380`/`IPZZ-961`；
    2. **归一化键**：`SNOS380`、`IPZZ912`（前端与老台账传的就是这个）→ 反推展示番号；
    3. **实例键**：`emby:12598` / `dl:<hash>` → 拆出 `kind` 与 `emby_id`；
    4. 纯数字（`12598`）→ 当 Emby id 用（`parse_av_number` 解析不出番号时才会走到这里）。

    返回里 `matched` 表示"这是个能解析的番号"，`key` **绝不返回空串**（调用方拿它当查询键，
    空串会让整条链悄悄查不到东西）——解析不出时退回 `canon_key()` 的旧口径。
    """
    raw = _nfkc(str(number_or_key or "")).strip()
    given_item = str(item_key or "").strip()

    # ① 实例键优先：`emby:12598` / `dl:<hash>`（显式参数优先于位置参数）
    for candidate in (given_item, raw):
        match = _ITEM_KEY.match(candidate)
        if match and match.group("kind").lower() in ("emby", "dl"):
            kind = match.group("kind").lower()
            tail = match.group("tail").strip()
            return {
                "input": raw, "item_key": candidate, "kind": kind,
                "number": "", "display_number": "", "key": "", "norm_key": "",
                "emby_id": tail if kind == "emby" else "",
                "version_tags": {}, "matched": False, "reason": "item_key",
            }

    # ② 纯数字**必须在 parse 之前判**：Emby 实例 id 就是裸数字（P0 试点 `12598`），
    #    而 `parse_av_number("12598")` 会把裸数字解析成 `125-098`（matched=True）——
    #    先 parse 就会把 id 当番号，进而去 javdb 查一个根本不存在的 `125-098`。
    if _DIGITS_ONLY.match(raw):
        return {
            "input": raw, "item_key": given_item or f"emby:{raw}", "kind": "emby",
            "number": "", "display_number": "", "key": "", "norm_key": "",
            "emby_id": raw, "version_tags": {}, "matched": False, "reason": "emby_id",
        }

    parsed = emby.parse_av_number(raw)
    number = parsed.display_number if parsed.matched else ""
    if not number:
        # 归一化键（`SNOS380`）反推展示番号；推不出来就原样用（宁可显示怪一点也不猜别的片）。
        # ⚠️ 这是**旧口径兜底**，只在 `parse_av_number()` 认不出番号时才走到 ——
        #    能认出时一律用 parse 的 `display_number`（见 `site_number()`：`CAWB-040` 不能被
        #    旧口径抹成 `CAWB-40`，前导零是有意义的）。
        number = emby.display_number(raw) or raw
    key = parsed.norm_key if (parsed.matched and parsed.norm_key) else emby.canon_key(number)
    return {
        "input": raw,
        "item_key": given_item,
        "kind": "number",
        "number": number,
        "display_number": site_number(raw, parsed, key),
        "key": key,
        "norm_key": key,
        "emby_id": "",
        "version_tags": dict(parsed.version_tags or {}) if parsed.matched else {},
        "matched": bool(parsed.matched),
        "reason": "",
    }


def site_number(raw_or_number: Any, parsed: Any = None, key: str = "") -> str:
    """**给站点 / 给 Emby 用**的展示番号：`parse_av_number()` 优先，解析不出才退回旧口径。

    历史（**别把顺序改回去**，两端都踩过）：

    - 2026-10-14 早先：S2 的 `parse_av_number("ipzz00961").display_number` 会保留**多余**的零
      （`IPZZ-00961`），而番号错一位就是整条片子查不到（javdb 404）→ 这里加了一层
      `emby.display_number(canon_key(...))` 兜底（得到 `IPZZ-961`），当时是对的；
    - 但那个 bug 已由 S2 修好（复核：`ipzz00586_1_4K.mp4` → `IPZZ-586`、
      `CAWB-040.mp4` → `CAWB-040`、`IPOK-025L.iso` → `IPOK-025`），于是这层兜底**反而有害**：
      `emby.display_number()` 是**旧口径**（`^([A-Z]{2,6})(\\d{2,7})$` 直接拼、**不补三位零**），
      会把**有意义的前导零**抹掉 —— 真机缺陷 4：`CAWB-040` 写成 `CAWB-40`、`IPOK-025` → `IPOK-25`
      （AGENTS.md §5：本库 109 条里 **31 条**是这个"数字段不足三位"的形态）。
    - 结论：**parse 优先**（它同时管住"零太多"与"不足三位"两个方向），
      只有 parse 认不出时才退回旧口径兜底。

    `norm_key` / `canon_key` **一律不动**（它们是台账主键，改一个字就全库错位）。
    """
    text = _nfkc(str(raw_or_number or "")).strip()
    if not text:
        return ""
    info = parsed if parsed is not None else emby.parse_av_number(text)
    display = str(getattr(info, "display_number", "") or "")
    if getattr(info, "matched", False) and display:
        return display                                   # ① parse 优先（权威口径）
    clean = emby.canon_key(text) or str(key or "")        # ② 旧口径兜底（认不出番号时）
    if clean:
        fixed = emby.display_number(clean)
        if fixed:
            return fixed
    return emby.display_number(text) or text              # ③ 最后的原样退回


# ---------------------------------------------------------------------------
# HTTP（javtxt / MetaTube）：一律走调用方给的代理，失败不抛异常
# ---------------------------------------------------------------------------

def _proxy_opener(proxy: str) -> Any:
    """按代理串建一个 urllib opener（空串 = 直连，不设任何 handler）。"""
    import urllib.request

    text = str(proxy or "").strip()
    if text:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": text, "https": text})
        )
    return urllib.request.build_opener()


def http_get(url: str, *, proxy: str = "", timeout: int = 30,
             headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[bytes], str, int]:
    """GET 一个 URL，返回 `(body, error, status)`。**任何异常都吞掉**（失败只回错误文案）。

    `error` 里带异常类型与原文（截断），调用方把它写进 `scrape_log.error_summary` /
    `preview.warnings` —— 静默失败在刮削线里是最贵的 bug（分不清站点挂了还是解析器坏了）。
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AVHelper/0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
        **(headers or {}),
    })
    try:
        with _proxy_opener(proxy).open(req, timeout=max(1, _to_int(timeout) or 30)) as res:
            return res.read(), "", int(getattr(res, "status", 200) or 200)
    except urllib.error.HTTPError as error:
        return None, f"HTTP {error.code}", int(error.code or 0)
    except Exception as error:                                  # noqa: BLE001 - 故意的
        return None, f"{type(error).__name__}: {error}", 0


# 站点节流（同一站点两次请求之间的最小间隔；跨线程也要守住）
_SITE_LAST: Dict[str, float] = {}
_SITE_LOCK = threading.Lock()


def throttle(host: str, interval: float) -> float:
    """把「对 `host` 的下一次请求」推迟到距上次 ≥`interval` 秒；返回实际等待秒数。"""
    wait = 0.0
    with _SITE_LOCK:
        now = time.monotonic()
        last = _SITE_LAST.get(host, 0.0)
        wait = max(0.0, float(interval or 0) - (now - last))
        if wait > 0:
            time.sleep(wait)
        _SITE_LAST[host] = time.monotonic()
    return wait


# ---------------------------------------------------------------------------
# Javtxt（契约 §4.2：选择器、三个坑、搜索非 100% 命中）
# ---------------------------------------------------------------------------

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")
_DIV_EDGE = re.compile(r"<div\b[^>]*>|</div>", re.I)
_JAVTXT_CARD = re.compile(r'<a[^>]*class="[^"]*\bwork\b[^"]*"[^>]*href="/v/(\d+)"[^>]*>(.*?)</a>',
                          re.S | re.I)
_JAVTXT_WORK_ID = re.compile(r'<h4 class="work-id"[^>]*>(.*?)</h4>', re.S | re.I)
_JAVTXT_WORK_TITLE = re.compile(r'<h4 class="work-title"[^>]*>(.*?)</h4>', re.S | re.I)
_JAVTXT_H1_JP = re.compile(r'<h1[^>]*class="[^"]*\btext-jp\b[^"]*"[^>]*>(.*?)</h1>', re.S | re.I)
_JAVTXT_H2_ZH = re.compile(r'<h2[^>]*class="[^"]*\btext-zh\b[^"]*"[^>]*>(.*?)</h2>', re.S | re.I)
_JAVTXT_P_JP = re.compile(r'<p[^>]*class="[^"]*\btext-jp\b[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
_JAVTXT_ACTRESS = re.compile(
    r'<a[^>]*class="[^"]*\bactress\b[^"]*"[^>]*href="/actress/(\d+)"[^>]*>(.*?)</a>', re.S | re.I)
_JAVTXT_AVATAR = re.compile(r'<img[^>]*class="[^"]*\bavatar\b[^"]*"[^>]*src="([^"]+)"', re.I)
_JAVTXT_DL_ACTRESS = re.compile(r'<dl[^>]*class="[^"]*\bdl-actress\b[^"]*"[^>]*>(.*?)</dl>', re.S | re.I)
_JAVTXT_BREADCRUMB = re.compile(r'<nav[^>]*class="[^"]*\bbreadcrumb\b[^"]*"[^>]*>(.*?)</nav>', re.S | re.I)
_JAVTXT_STUDIO = re.compile(r'<li[^>]*>\s*<a[^>]*href="/studio/\d+"[^>]*>(.*?)</a>', re.S | re.I)
_JAVTXT_ACTIVE = re.compile(r'<li[^>]*class="[^"]*\bis-active\b[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>', re.S | re.I)


def _javtxt_dd(label: str) -> "re.Pattern[str]":
    """`<dd>…发行时间…</dd><dt>值</dt>` 的成对匹配（`attributes` 块里的键值对）。"""
    return re.compile(r'<dd[^>]*>[^<]*' + re.escape(label) + r'[^<]*</dd>\s*<dt[^>]*>(.*?)</dt>',
                      re.S | re.I)


def strip_comments(text: str) -> str:
    """剥掉 HTML 注释（契约 §4.2 坑 1）。

    **必须先剥**：javtxt 详情页把"别的演员"塞在 `<!-- …辻あずき… -->` 里（实测 4 条），
    不剥就会把无关演员写进 Emby 的 `People`，从而凭空造出 Person 实体。
    """
    return _COMMENT.sub("", str(text or ""))


def _div_block(text: str, opener: str) -> str:
    """从 `opener`（形如 `<div class="intro">`）开始，取到配平的 `</div>`（含内层）。"""
    start = text.find(opener)
    if start < 0:
        return ""
    depth = 0
    pos = start
    while True:
        edge = _DIV_EDGE.search(text, pos)
        if not edge:
            return text[start:]
        if edge.group(0).lower().startswith("</"):
            depth -= 1
            if depth <= 0:
                return text[start:edge.end()]
        else:
            depth += 1
        pos = edge.end()


def _class_block(text: str, class_name: str) -> str:
    """按 class 名取一个 `<div>` 块（**精确匹配 `class="x"`**，不会误吃 `x-header`）。"""
    return _div_block(text, f'<div class="{class_name}">')


def parse_javtxt_search(body: str) -> List[Dict[str, str]]:
    """解析 javtxt 搜索页 → `[{id, url, number, title}]`（按出现顺序）。

    契约 §4.2：结果是 `<a class="work" href="/v/<数字id>">` 的卡片，卡片里
    `<h4 class="work-id">` 才是番号写法 —— **别去正则整段 `<a>…</a>` 的文本**（markup 很长，会失配）。
    """
    clean = strip_comments(body)
    out: List[Dict[str, str]] = []
    for match in _JAVTXT_CARD.finditer(clean):
        vid = match.group(1)
        card = match.group(2)
        out.append({
            "id": vid,
            "url": f"/v/{vid}",
            "number": _clean_text(_first(_JAVTXT_WORK_ID.search(card))),
            "title": _clean_text(_first(_JAVTXT_WORK_TITLE.search(card))),
        })
    return out


def pick_javtxt_hit(cards: Sequence[Dict[str, str]], target_norm: str) -> Optional[Dict[str, str]]:
    """在搜索结果里**强校验**挑出与目标同号的那张卡（拿不到就 `None`）。

    判据只有一条：`parse_av_number(card['number']).norm_key == target_norm`。
    契约 §4.2 要求"不许猜条"：javtxt 的搜索是模糊匹配，命中列表里可能出现完全无关的番号，
    取第一条等于把别人的标题/简介写进这部片。
    """
    want = str(target_norm or "").strip().upper()
    if not want:
        return None
    for card in cards or []:
        got = emby.parse_av_number(card.get("number"))
        if got.matched and str(got.norm_key or "").upper() == want:
            return dict(card)
    return None


def parse_javtxt_detail(body: str) -> Dict[str, Any]:
    """解析 javtxt 详情页（选择器全部来自契约 §4.2 的实测表）。

    返回 `{vid?, title_jp, title_zh, plot_jp, plot_zh, zh_is_machine, actors[], studio,
    number_written, director, release_date, tags[]}`；抽不到的字段是空串/空列表。

    三个坑都按契约处理：① 先剥注释；② 演员只在 `<dl class="dl-actress">` 里抽
    （页面右侧/底部的排行榜会混进无关演员名）；③ 中文简介取 `<div class="text-zh">` 里的
    `<p>` 序列并跳过 `.zh-tip`（那是"来自机翻，不准确请谅解"的提示，不是正文）。
    """
    clean = strip_comments(body)
    intro = _class_block(clean, "intro")
    info = _class_block(clean, "info")
    scope = intro or info or clean

    plot_jp = _clean_text(_first(_JAVTXT_P_JP.search(scope)))
    zh_block = _class_block(scope, "text-zh") or ""
    zh_parts = [p for p in re.findall(r"<p[^>]*>(.*?)</p>", zh_block, re.S | re.I)]
    plot_zh = _clean_text("\n".join(_clean_text(p) for p in zh_parts if _clean_text(p)))
    zh_is_machine = "机翻" in zh_block

    actors: List[Dict[str, str]] = []
    dl = _JAVTXT_DL_ACTRESS.search(scope)
    if dl:
        for match in _JAVTXT_ACTRESS.finditer(dl.group(1)):
            inner = match.group(2)
            name = _clean_text(_TAG.sub(" ", inner))
            avatar = _first(_JAVTXT_AVATAR.search(inner))
            if name:
                actors.append({"id": match.group(1), "name": name, "avatar_url": avatar})

    crumb = _first(_JAVTXT_BREADCRUMB.search(clean))
    studio = _clean_text(_first(_JAVTXT_STUDIO.search(crumb))) if crumb else ""
    number_written = _clean_text(_first(_JAVTXT_ACTIVE.search(crumb))) if crumb else ""
    attrs = info or clean
    director = _clean_text(_TAG.sub(" ", _first(_javtxt_dd("导演").search(attrs))))
    release = _clean_text(_TAG.sub(" ", _first(_javtxt_dd("发行时间").search(attrs))))
    tags = [_clean_text(_TAG.sub(" ", t)) for t in re.findall(
        r'<a[^>]*class="[^"]*\btag\b[^"]*"[^>]*href="/genre/\d+"[^>]*>(.*?)</a>',
        attrs, re.S | re.I)]
    return {
        "title_jp": _clean_text(_first(_JAVTXT_H1_JP.search(clean))),
        "title_zh": _clean_text(_first(_JAVTXT_H2_ZH.search(clean))),
        "plot_jp": plot_jp,
        "plot_zh": plot_zh,
        "zh_is_machine": bool(zh_is_machine),
        "actors": actors,
        "studio": studio,
        "number_written": number_written,
        "director": director,
        "release_date": release,
        "tags": [t for t in tags if t],
    }


def javtxt_variants(display_number: str) -> List[str]:
    """搜索变体（契约 §4.2：① 原写法 ② 连字符/大小写变体 ③ 纯数字段）。

    实测：`SNOS-380`/`IPOK-025`/`MIDV-946` 有结果，`IPZZ-912`/`CAWB-040` **0 命中** ——
    那是站点收录缺口，试完所有变体仍为空就**如实返回空**，交给 MetaTube 兜底，不许猜条。
    """
    text = str(display_number or "").strip()
    if not text:
        return []
    compact = re.sub(r"[^0-9A-Za-z]", "", text)
    digits = re.sub(r"\D", "", text)
    prefix = re.sub(r"\d+$", "", compact).lstrip("0")
    out: List[str] = [text, text.upper(), text.lower()]
    if compact:
        out += [compact, compact.upper(), compact.lower()]
    if prefix and digits:
        out += [f"{prefix}-{digits}", f"{prefix.lower()}-{digits}", digits]
    seen: List[str] = []
    for item in out:
        if item and item not in seen:
            seen.append(item)
    return seen


def javtxt_lookup(opts: Dict[str, Any], number: str, *, store: Any = None,
                  key: str = "") -> Dict[str, Any]:
    """Javtxt 一键取数：搜索（多变体 + 强校验）→ 详情页解析。

    返回 `{ok, status, vid, url, title_zh, title_jp, plot_zh, plot_jp, zh_is_machine, actors,
    latency_ms, error, tried[]}`；`status` ∈ `ok` / `miss` / `error`。

    请求一律走 `opts['proxy']`，**每个站点请求之间 ≥`opts['javtxt_interval']`（默认 2s）**，
    失败不抛异常（只回 error 文案并由调用方写 `scrape_log`）。
    """
    hosts = [str(h).rstrip("/") for h in (javtxt_lookup_hosts(opts))]
    proxy = str(_opt(opts, "proxy") or "")
    timeout = _to_int(_opt(opts, "http_timeout")) or 30
    interval = float(_opt(opts, "javtxt_interval") or JAVTXT_MIN_INTERVAL)
    started = time.time()
    result: Dict[str, Any] = {
        "ok": False, "status": "miss", "vid": "", "url": "", "host": "",
        "title_zh": "", "title_jp": "", "plot_zh": "", "plot_jp": "",
        "zh_is_machine": False, "actors": [], "tried": [], "error": "",
        "latency_ms": 0,
    }
    target = emby.parse_av_number(number)
    target_norm = target.norm_key if target.matched else emby.canon_key(number)

    for variant in javtxt_variants(number):
        for host in hosts:
            throttle(host, interval)
            url = f"{host}/search?{urlencode({'type': 'id', 'q': variant})}"
            body, error, _status = http_get(url, proxy=proxy, timeout=timeout)
            result["tried"].append({"variant": variant, "host": host, "error": error})
            if body is None:
                result["error"] = error or "搜索结果为空"
                continue
            cards = parse_javtxt_search(body.decode("utf-8", "replace"))
            hit = pick_javtxt_hit(cards, target_norm)
            if not hit:
                continue
            throttle(host, interval)
            detail_body, detail_error, _st = http_get(
                f"{host}{hit['url']}", proxy=proxy, timeout=timeout)
            if detail_body is None:
                result["error"] = detail_error or "详情页拉取失败"
                continue
            detail = parse_javtxt_detail(detail_body.decode("utf-8", "replace"))
            result.update(detail)
            result.update({
                "ok": True, "status": "ok", "vid": hit.get("id", ""),
                "url": f"{host}{hit['url']}", "host": host, "error": "",
            })
            result["latency_ms"] = int((time.time() - started) * 1000)
            _log_source(store, SRC_JAVTXT, "ok", key or number,
                        result["latency_ms"], "")
            return result

    result["latency_ms"] = int((time.time() - started) * 1000)
    if not result["error"]:
        result["error"] = ""                    # 命中不到不是错误：站点收录缺口，交 MetaTube
    _log_source(store, SRC_JAVTXT, result["status"], key or number,
                result["latency_ms"], result["error"])
    return result


def javtxt_lookup_hosts(opts: Dict[str, Any]) -> Tuple[str, ...]:
    """javtxt 主机列表（`opts` 可覆盖，便于单测指向假站点）。"""
    raw = _opt(opts, "javtxt_hosts") or JAVTXT_HOSTS
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(h) for h in raw if str(h).strip())


def _javtxt_from_cache(row: Any) -> Optional[Dict[str, Any]]:
    """把 S11 `coverage.json` 的一行 `javtxt` 还原成 `javtxt_lookup()` 的形状。

    S11 的抓取缓存（`_tmp/s11/coverage.json`，108 部真机）里 `javtxt` 是**已解析结果**
    （`hit`/`title_jp`/`title_zh`/`plot_jp`/`plot_zh`/`actors`/`tags`/`vid`/`url`），
    用它就能在**一次站点请求都不发**的前提下跑完全库 dry-run。
    """
    data = row if isinstance(row, dict) else {}
    if not data.get("hit"):
        return None
    return {
        "ok": True, "status": "ok", "from_cache": True,
        "vid": str(data.get("vid") or ""), "url": str(data.get("url") or ""),
        "host": str(data.get("host") or ""),
        "title_jp": _clean_text(data.get("title_jp")),
        "title_zh": _clean_text(data.get("title_zh")),
        "plot_jp": _clean_text(data.get("plot_jp")),
        "plot_zh": _clean_text(data.get("plot_zh")),
        "zh_is_machine": bool(data.get("zh_is_machine", True)),
        "actors": [a for a in (data.get("actors") or []) if isinstance(a, dict)],
        "tried": [], "error": "", "latency_ms": 0,
    }


def load_fetch_cache(source: Any) -> Dict[str, Dict[str, Any]]:
    """载入抓取缓存（S11 `coverage.json` 形状），返回 `{norm_key: row}`。

    `source` 可以是：`None`/空（无缓存）、已经载入的 dict（含 `numbers`）、或**文件路径**。
    解析不出来一律回空字典 —— 缓存是加速器，坏了只该"变慢"，不该让刮削失败。
    """
    data: Any = source
    if isinstance(source, (str, bytes)):
        path = str(source)
        if not path or not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            logger.warning(f"AVHelper 抓取缓存读取失败（忽略）：{error}")
            return {}
    if not isinstance(data, dict):
        return {}
    rows = data.get("numbers")
    if not isinstance(rows, dict):
        rows = data if all(isinstance(v, dict) for v in data.values()) else {}
    return {str(k): v for k, v in rows.items() if isinstance(v, dict)}


def cache_row(cache: Any, key: str) -> Dict[str, Any]:
    """在缓存里按 `norm_key` 取一行（兼容 `cache['numbers']` 与已展开的两种形状）。"""
    rows = cache.get("numbers") if isinstance(cache, dict) and "numbers" in cache else cache
    if not isinstance(rows, dict) or not key:
        return {}
    row = rows.get(key) or rows.get(str(key).upper())
    return row if isinstance(row, dict) else {}


# 缓存行里 `javdb` 是 `{ok, number, cross_number, fields, detail, fetched_at}`；
# `detail` 才是 `javdb detail --json` 的原样输出（骨架与 raw_json 都从它来）。
def _javdb_from_cache(row: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """缓存行 → `(javdb detail dict 或 None, 说明)`。"""
    data = row if isinstance(row, dict) else {}
    if not data:
        return None, ""
    if data.get("ok") is False or not data.get("detail"):
        return None, str(data.get("error") or "缓存里没有 javdb 详情")
    detail = data.get("detail")
    if isinstance(detail, dict) and detail:
        return detail, "cache"
    if isinstance(data.get("title"), str):          # 直接就是 detail 形状的缓存
        return data, "cache"
    return None, ""


def _short_plot_zh(plot_zh: str, plot_jp: str, opts: Optional[Dict[str, Any]]) -> bool:
    """中文简介是不是"站点占位符"（短且**同时有日文**才判不可用）。

    只有日文也没有时才不判 —— 那时短的也比空的好，交回上游按 `missing_plot` 退避。
    """
    text = str(plot_zh or "").strip()
    if not text:
        return False
    floor = _to_int(_opt(opts, "min_plot_zh")) or MIN_PLOT_ZH
    return len(text) < floor and bool(str(plot_jp or "").strip())


# ---------------------------------------------------------------------------
# MetaTube（概述兜底；**必须强校验番号**，否则会把随机 DUGA 结果写进你的库）
# ---------------------------------------------------------------------------

def pick_metatube_hit(items: Any, target_norm: str) -> Tuple[Optional[Dict[str, Any]], int, bool]:
    """在 MetaTube 返回列表里挑同号条目，返回 `(命中项, 候选数, 是否串号)`。

    实测（2026-10-14，`/v1/movies/search?q=SNOS-380`）返回的是 **DUGA 的 FSDSS 系列**：
    查 `ZZZZ-999` 也能返回 `FSDSS-666` —— 站点查不到时返回随机结果，**同一条查询三次三个答案**。
    所以这里**遍历整个列表逐个校验** `parse_av_number(item['number']).norm_key == target_norm`，
    取第一条命中的；一个都不命中就判 `mismatch`（`mismatch=True`），**绝不退回 `items[0]`**。
    """
    want = str(target_norm or "").strip().upper()
    rows = [it for it in (items if isinstance(items, list) else []) if isinstance(it, dict)]
    if not want:
        return None, len(rows), False
    for item in rows:
        got = emby.parse_av_number(item.get("number"))
        if got.matched and str(got.norm_key or "").upper() == want:
            return item, len(rows), False
    return None, len(rows), bool(rows)


def metatube_movie(item: Any) -> Dict[str, Any]:
    """把一条 MetaTube 影片记录映射成**骨架字段**（字段真名见下，与 javdb 不同名！）。

    S0b 真机 130 次探测（`_tmp/s0b/REPORT-S0b.md`）给的映射表 —— **别按 javdb 的名字去读它**：

    | 我们的字段 | MetaTube 真名 | 备注 |
    | --- | --- | --- |
    | 片商 | `maker` | 不是 `studio` |
    | 时长（分钟） | `runtime` | 整数；不是 `duration` |
    | 标签 | `genres` | 字符串数组；不是 `tags` |
    | 预告片 | `preview_video_url`（+`preview_video_hls_url`） | — |
    | 简介 | `summary` | **真正命中的条目上 100% 是空串**（7/7）；有值的只有乱返的 DUGA 条目 |
    | 剧照 | `preview_images` | 是 `[]string`，**不是** `{large_url,thumb_url}` 对象数组 |
    | 发行日 | `release_date` | `"2024-11-29T00:00:00Z"` 这种 ISO 串（要切掉时间部分） |
    | 演员 | `actors` | `[]string` 纯名字（**没有头像**） |
    | 导演 | `director` | — |
    """
    data = item if isinstance(item, dict) else {}
    release = str(data.get("release_date") or "")
    return {
        "number": _clean_text(data.get("number")),
        "title": _clean_text(data.get("title")),
        "summary": _clean_text(data.get("summary")),
        "maker": _clean_text(data.get("maker")),
        "runtime": _to_int(data.get("runtime")),
        "genres": [_clean_text(g) for g in (data.get("genres") or []) if _clean_text(g)],
        "director": _clean_text(data.get("director")),
        "preview_video_url": str(data.get("preview_video_url") or ""),
        "preview_images": [str(u) for u in (data.get("preview_images") or []) if str(u or "")],
        "release_date": release[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", release) else "",
        "cover_url": str(data.get("big_cover_url") or data.get("cover_url") or ""),
        "thumb_url": str(data.get("big_thumb_url") or data.get("thumb_url") or ""),
        "actors": [_clean_text(a) for a in (data.get("actors") or []) if _clean_text(a)],
        "provider": str(data.get("provider") or ""),
        "id": str(data.get("id") or ""),
    }


def _metatube_fetch(opts: Dict[str, Any], url: str, timeout: int) -> Tuple[Optional[bytes], str, int]:
    """打一次 MetaTube search，**带 S0b 定的重试口径**，返回 `(body, error, status)`。

    S0b 实测的三条硬约束（别"优化"掉）：

    1. **`404` 是业务空值，不是错误，绝不重试** —— 它表示"30 个源都没收录这个番号"，
       重试只会再白等 10 秒；实测并发 5 次搜索还会 **5/5 全 404**。
    2. **只有 5xx / 超时才退避重试，≤2 次，间隔 1s → 3s**。
    3. **必须串行**：服务端对 30 源有硬 10 秒截止，并发只会一起失败；而且响应**完全不缓存**
       （31 个 200 里有 12 个不同 sha）。本模块所有 MetaTube 调用都是同步串行的一次调用。

    `timeout` 必须 **≥25 秒**（默认 30）—— 服务端自己在等上游，给 10 秒会把"它还在正常等待"
    误判成超时。
    """
    body, error, status = http_get(url, proxy=str(_opt(opts, "proxy") or ""), timeout=timeout)
    if body is not None or status == 404:
        return body, error, status
    for wait in (1.0, 3.0):
        if status and 400 <= status < 500:                      # 其它 4xx：同样是业务结论
            break
        time.sleep(wait)
        body, error, status = http_get(url, proxy=str(_opt(opts, "proxy") or ""),
                                       timeout=timeout)
        if body is not None or status == 404:
            break
    return body, error, status


def metatube_lookup(opts: Dict[str, Any], number: str, *, store: Any = None,
                    key: str = "") -> Dict[str, Any]:
    """MetaTube 取数：搜索 → **强校验** → 提取（概述兜底 + javdb 挂掉时的骨架兜底）。

    只打 `/v1/movies/search?q=`：**永远用默认 `lazy=true`**（`lazy=false` 对 7 个命中 7/7 全 500）、
    **永远不用 `provider=` 参数**（`MGS` 403 / `FANZA` 500 / JavBus 查不到时 404）——S0b 实测。

    ⚠️ **别指望它的简介**：真机 7 个命中条目的 `summary` **全是空串**，返回日文简介的只有乱返的
    DUGA 条目（别人的片子）。所以 `ok=True` 是"拿到了可用字段"而不是"拿到了简介"；
    `plot_jp` 的正源是 Javtxt 详情页的 `<p class="text-jp">`。

    ⚠️ **成本**：search 恒定 ~10.0 秒（30 次实测全落在 [10000, 10047] ms），全库 108 条就是
    18 分钟纯等待 —— 调用方（`gather()`）只在「Javtxt 落空」或「javdb 挂了」时才调它。

    整源不可用（全 404 / 连不上）时**返回空 + 记 `scrape_log(status='error')`，不抛异常**：
    S0b 提醒 JAV321 上游 main 已删目录，将来容器换版本会让这条源突然掉一半命中。

    返回 `{ok, status, movie{…}, plot_jp, title_jp, candidates, mismatch, latency_ms, error}`；
    `status` ∈ `ok` / `miss` / `mismatch` / `error` / `empty`（404 = 业务空值）。
    """
    base = str(_opt(opts, "metatube_base") or "").rstrip("/")
    timeout = _to_int(_opt(opts, "metatube_timeout")) or METATUBE_TIMEOUT
    started = time.time()
    out: Dict[str, Any] = {
        "ok": False, "status": "miss", "plot_jp": "", "title_jp": "", "movie": {},
        "provider": "", "id": "", "candidates": 0, "mismatch": False,
        "latency_ms": 0, "error": "",
    }
    if not base:
        out["status"] = "error"
        out["error"] = "未配置 MetaTube 地址"
        return out
    target = emby.parse_av_number(number)
    target_norm = target.norm_key if target.matched else emby.canon_key(number)
    url = f"{base}/v1/movies/search?{urlencode({'q': number})}"      # 只带 q；不要 provider=
    body, error, status = _metatube_fetch(opts, url, timeout)
    if body is None:
        # 404 = 业务空值（30 个源都没收录），记 miss 而不是 error，也不进退避重试
        out.update({
            "status": "empty" if status == 404 else "error",
            "error": "" if status == 404 else (error or "请求失败"),
            "latency_ms": int((time.time() - started) * 1000),
        })
        _log_source(store, SRC_METATUBE, out["status"], key or number, out["latency_ms"],
                    out["error"])
        return out
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        out.update({"status": "error", "error": "返回不是合法 JSON",
                    "latency_ms": int((time.time() - started) * 1000)})
        _log_source(store, SRC_METATUBE, "error", key or number, out["latency_ms"], out["error"])
        return out
    items = payload.get("data") if isinstance(payload, dict) else payload
    hit, count, mismatch = pick_metatube_hit(items, target_norm)
    out["candidates"] = count
    out["mismatch"] = mismatch
    if hit is None:
        out["status"] = "mismatch" if mismatch else "miss"
        out["error"] = (f"返回 {count} 条候选全不同号（MetaTube 查不到时会返回随机结果，已拦截）"
                        if mismatch else "")
        out["latency_ms"] = int((time.time() - started) * 1000)
        _log_source(store, SRC_METATUBE, out["status"], key or number, out["latency_ms"],
                    out["error"])
        return out
    movie = metatube_movie(hit)
    out["movie"] = movie
    out["plot_jp"] = movie["summary"]
    out["title_jp"] = movie["title"]
    out["provider"] = movie["provider"]
    out["id"] = movie["id"]
    usable = bool(movie["title"] or movie["maker"] or movie["cover_url"] or movie["summary"])
    out["ok"] = usable
    out["status"] = "ok" if usable else "miss"
    out["latency_ms"] = int((time.time() - started) * 1000)
    _log_source(store, SRC_METATUBE, out["status"], key or number, out["latency_ms"],
                "" if usable else "命中同号条目但所有可用字段都为空")
    return out


def metatube_fill(skeleton: Dict[str, Any], movie: Dict[str, Any]) -> List[str]:
    """javdb 挂掉时用 MetaTube 的字段**补空**（只补空，绝不覆盖 javdb 已给的值）。

    契约 §5.2：核心骨架字段第一顺位是 javdb，MetaTube **仅在 javdb 404 时启用**。
    返回被补上的字段名清单（写进 `warnings`/报告，让"这条数据是谁给的"可追）。
    """
    filled: List[str] = []
    pairs = (
        ("title_jp", movie.get("title")), ("summary_jp", movie.get("summary")),
        ("maker", movie.get("maker")), ("director", movie.get("director")),
        ("release_date", movie.get("release_date")), ("cover_url", movie.get("cover_url")),
        ("thumb_url", movie.get("thumb_url")),
        ("preview_video_url", movie.get("preview_video_url")),
        ("javdb_id", movie.get("id")),
    )
    for name, value in pairs:
        if not _clean_text(skeleton.get(name)) and _clean_text(value):
            skeleton[name] = _clean_text(value) if name != "javdb_id" else value
            filled.append(name)
    if not _to_int(skeleton.get("duration")) and _to_int(movie.get("runtime")):
        skeleton["duration"] = _to_int(movie["runtime"])
        filled.append("duration")
    if not (skeleton.get("actors") or []) and movie.get("actors"):
        # MetaTube 的 actors 是**纯名字**（没有头像/id），只当"人名兜底"用
        skeleton["actors"] = [{"name": n} for n in movie["actors"] if n]
        filled.append("actors")
    if not (skeleton.get("tags") or []) and movie.get("genres"):
        skeleton["tags"] = [{"id": "", "name": g} for g in movie["genres"] if g]
        filled.append("tags")
    return filled


# ---------------------------------------------------------------------------
# scrape_log 记录（一行封装，所有数据源调用共用）
# ---------------------------------------------------------------------------

def _log_source(store: Any, source: str, status: str, key: str = "",
                latency_ms: int = 0, error: str = "") -> None:
    """往 `scrape_log` 记一条；`store` 缺失/不可用时静默跳过（读侧不该因为日志挂掉）。"""
    if store is None or not hasattr(store, "scrape_log_add"):
        return
    try:
        store.scrape_log_add(source, status, key=key, latency_ms=_to_int(latency_ms),
                             error_summary=str(error or "")[:500])
    except Exception as error_obj:                              # pragma: no cover - 防御
        logger.warning(f"AVHelper 写 scrape_log 失败（{source}/{status}）：{error_obj}")


# ---------------------------------------------------------------------------
# javdb 骨架 + 图片资产
# ---------------------------------------------------------------------------

# `meta.raw_json['javdb']` 保留的键（够在不重抓 javdb 的前提下重建写入载荷）
_JAVDB_KEEP = (
    "id", "number", "title", "origin_title", "summary", "release_date", "duration", "score",
    "maker_name", "publisher_name", "series_name", "director_name", "cover_url", "thumb_url",
    "preview_video_url", "has_cnsub", "type",
)
# 图片文件名特征（javdb 的封面/剧照靠 URL 路径区分，而不是靠位置）
_COVER_HINT = re.compile(r"/covers?/", re.I)
_SAMPLE_HINT = re.compile(r"/(samples?|preview)/", re.I)
_ASSET_LINE = re.compile(r"^(?P<kind>[a-z]+)\t(?P<url>\S+)\s*$", re.I)


def _skeleton_from_raw(raw: Any) -> Dict[str, Any]:
    """把 `raw_json['javdb']` 还原成骨架 dict（Tier1「只补简介」路径用，**不打 javdb**）。"""
    data = raw if isinstance(raw, dict) else {}
    return {
        "ok": True,
        "javdb_id": str(data.get("id") or ""),
        "display_number": str(data.get("number") or ""),
        "title_jp": _clean_text(data.get("title") or ""),
        "origin_title": _clean_text(data.get("origin_title") or ""),
        "summary_jp": _clean_text(data.get("summary") or ""),
        "release_date": str(data.get("release_date") or ""),
        "duration": _to_int(data.get("duration")),
        "score": str(data.get("score") or ""),
        "maker": _clean_text(data.get("maker_name") or ""),
        "publisher": _clean_text(data.get("publisher_name") or ""),
        "series": _clean_text(data.get("series_name") or ""),
        "director": _clean_text(data.get("director_name") or ""),
        "actors": [a for a in (data.get("actors") or []) if isinstance(a, dict)],
        "tags": [t for t in (data.get("tags") or []) if isinstance(t, dict)],
        "cover_url": str(data.get("cover_url") or ""),
        "thumb_url": str(data.get("thumb_url") or ""),
        "preview_video_url": str(data.get("preview_video_url") or ""),
        "has_cnsub": bool(data.get("has_cnsub")),
        "preview_images": [s for s in (data.get("samples") or []) if isinstance(s, dict)],
        "from_cache": True,
    }


def javdb_skeleton(cli: Any, number: str, *, opts: Optional[Dict[str, Any]] = None,
                   store: Any = None, key: str = "", raw: Any = None) -> Dict[str, Any]:
    """取 javdb 骨架（标题/发行日/时长/片商/系列/导演/评分/演员/标签/封面）。

    `raw` 非空时**直接用它还原骨架、不调 javdb**（契约 §5.3「只补缺不重抓」：
    Tier1 重试时 `meta.raw_json['javdb']` 已存在就跳过这次调用）。
    调用走 `cli.detail(number)`（`client.JavdbClient._run()` 的既有失败留痕/冷却都在里面）。
    """
    options = opts or {}
    if raw:
        skeleton = _skeleton_from_raw(raw)
        if skeleton.get("title_jp") or skeleton.get("cover_url"):
            return skeleton
    started = time.time()
    detail = None
    getter = getattr(cli, "detail", None) if cli is not None else None
    if callable(getter):
        try:
            detail = getter(number)
        except Exception as error:                              # noqa: BLE001 - 门面之外不抛
            _log_source(store, SRC_JAVDB, "error", key or number,
                        int((time.time() - started) * 1000), f"{type(error).__name__}: {error}")
            detail = None
    latency = int((time.time() - started) * 1000)
    if not isinstance(detail, dict) or not detail:
        reason = ""
        reporter = getattr(cli, "last_error", None) if cli is not None else None
        if callable(reporter):
            try:
                reason = str(reporter(f"detail:{number}") or "")
            except Exception:                                   # pragma: no cover - 防御
                reason = ""
        reason = reason or (options.get("javdb_error") or "javdb 未返回详情")
        _log_source(store, SRC_JAVDB, "error", key or number, latency, reason)
        return {
            "ok": False, "error": reason, "latency_ms": latency, "display_number": number,
        }
    skeleton = _skeleton_from_raw(detail)
    skeleton.update({"ok": True, "error": "", "latency_ms": latency, "from_cache": False})
    skeleton["display_number"] = skeleton.get("display_number") or number
    skeleton["preview_images"] = [s for s in (detail.get("preview_images") or [])
                                  if isinstance(s, dict)]
    # 原始 DTO 一并带上：`trim_javdb_raw()` 认的是 javdb 的**原始键名**（`title`/`maker_name`…），
    # 而骨架用的是本模块的键名（`title_jp`/`maker`…）。少了这一步，`raw_json['javdb']`
    # 会存成一份没有标题的空壳，Tier1「只补简介不重抓」就会把整条片子退化成 `missing_core`。
    skeleton["raw"] = detail
    _log_source(store, SRC_JAVDB, "ok", key or number, latency, "")
    return skeleton


def trim_javdb_raw(skeleton: Dict[str, Any], limit: int = JAVDB_RAW_LIMIT) -> Dict[str, Any]:
    """把骨架压成 `raw_json['javdb']`（契约 §5.2：剔掉 `magnets` 与评论，体积 ≤5KB）。

    磁力数组与评论是体积大头（几百 KB），且**刮削线一个字段都不用它**；
    演员/标签/剧照按上限截断；实在还超就逐级丢字段，最后退到"只剩标识与标题"。

    入参可以是 **javdb 的原始 detail dict**，也可以是 `javdb_skeleton()` 的产出
    （后者带 `raw`，本函数优先用 `raw` —— 否则拿骨架的键名去读 javdb 的键名会全部落空）。
    """
    src = skeleton if isinstance(skeleton, dict) else {}
    inner = src.get("raw")
    if isinstance(inner, dict) and inner:
        src = inner
    actors = [{"id": str(a.get("id") or ""), "name": _clean_text(a.get("name") or ""),
               "avatar_url": str(a.get("avatar_url") or ""),
               "gender": a.get("gender")}
              for a in (src.get("actors") or []) if isinstance(a, dict)]
    tags = [{"id": str(t.get("id") or ""), "name": _clean_text(t.get("name") or "")}
            for t in (src.get("tags") or []) if isinstance(t, dict)]
    samples = []
    for item in (src.get("preview_images") or [])[:6]:
        if not isinstance(item, dict):
            continue
        samples.append({"large_url": str(item.get("large_url") or ""),
                        "thumb_url": str(item.get("thumb_url") or "")})
    out: Dict[str, Any] = {k: _clean_text(src.get(k)) if isinstance(src.get(k), str)
                           else src.get(k) for k in _JAVDB_KEEP if src.get(k) not in (None, "")}
    out["actors"] = actors[:12]
    out["tags"] = tags[:24]
    out["samples"] = samples
    if len(_json_dumps(out)) <= limit:
        return out
    out["actors"] = actors[:6]                                  # 逐级瘦身
    out.pop("samples", None)
    if len(_json_dumps(out)) <= limit:
        return out
    out["tags"] = tags[:12]
    out.pop("actors", None)
    if len(_json_dumps(out)) <= limit:
        return out
    minimal = {k: out[k] for k in ("id", "number", "title", "release_date", "cover_url")
               if k in out}
    return minimal


def _json_dumps(value: Any) -> str:
    """紧凑 JSON（`ensure_ascii=False`：中文原样存，别把体积翻三倍）。"""
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):                             # pragma: no cover - 防御
        return "{}"


def pack_raw_json(javdb_raw: Any, javtxt: Any = None, metatube: Any = None,
                  extra: Any = None, limit: int = RAW_JSON_LIMIT) -> Dict[str, Any]:
    """组装 `meta.raw_json` 并保证总体积 ≤`limit`（默认 5KB）。

    javtxt / metatube 只存**摘要元数据**（URL / vid / 有没有中文 / 候选数），不存正文 ——
    正文各有自己的列（`plot_zh`/`plot_jp`），再塞进 raw_json 就是重复占体积。
    """
    out: Dict[str, Any] = {}
    if isinstance(javdb_raw, dict) and javdb_raw:
        out["javdb"] = javdb_raw
    if isinstance(javtxt, dict):
        out["javtxt"] = {
            k: javtxt.get(k) for k in
            ("url", "vid", "status", "zh_is_machine", "title_zh", "number_written")
            if javtxt.get(k) not in (None, "")
        }
        out["javtxt"]["plot_zh_len"] = len(str(javtxt.get("plot_zh") or ""))
        out["javtxt"]["plot_jp_len"] = len(str(javtxt.get("plot_jp") or ""))
    if isinstance(metatube, dict):
        out["metatube"] = {
            k: metatube.get(k) for k in
            ("provider", "id", "status", "candidates", "mismatch")
            if metatube.get(k) not in (None, "")
        }
    if isinstance(extra, dict):
        out["extra"] = extra
    if len(_json_dumps(out)) <= limit:
        return out
    javdb = out.get("javdb")
    if isinstance(javdb, dict):
        out["javdb"] = trim_javdb_raw(javdb, max(256, limit // 2))
    if len(_json_dumps(out)) <= limit:
        return out
    for drop in ("extra", "metatube", "javtxt"):
        out.pop(drop, None)
        if len(_json_dumps(out)) <= limit:
            return out
    if isinstance(out.get("javdb"), dict):
        out["javdb"] = trim_javdb_raw(out["javdb"], max(256, limit - 64))
    return out


def parse_assets_list(payload: Any) -> List[Dict[str, Any]]:
    """解析 `javdb assets list --json` → `[{type, url, width, height, duration, idx}]`。

    `idx` 是**该类型内的 1-based 位置** —— `assets download` 的选择器认的就是这个位置
    （实测 `assets list SNOS-380 --type image 2` 给的就是全量列表里第 2 张图）。
    """
    rows = payload if isinstance(payload, list) else []
    out: List[Dict[str, Any]] = []
    counters: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "image").strip().lower()
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        counters[kind] = counters.get(kind, 0) + 1
        out.append({
            "type": kind, "url": url, "idx": counters[kind],
            "width": _to_int(row.get("width")), "height": _to_int(row.get("height")),
            "duration": _to_int(row.get("duration")),
        })
    return out


def pick_assets(assets: Sequence[Dict[str, Any]], cover_url: str = "",
                sample_count: int = SAMPLE_COUNT) -> Dict[str, Any]:
    """按几何与 URL 特征挑封面与剧照（返回 `{cover, samples}`，元素是 assets 里的条目）。

    规则（契约 D8 + 浏览器侧既有口径）：

    - **封面**：优先与 `detail.cover_url` 完全同 URL 的那张（最权威）；
      否则取 URL 命中 `/covers?/` 且面积最大的；再否则取面积最大的竖版；
      最后退回面积最大的一张。
    - **剧照**：URL 命中 `/(samples?|preview)/` 且**横版**（`w > h`）的前 3 张；
      没有 samples 路径特征时退回"除封面外面积最大的横版"。
    - 剧照与封面**不会是同一张**；几何未知（宽高都是 0）的条目不进剧照（宁可少传也不传竖图）。
    """
    rows = [a for a in (assets or []) if isinstance(a, dict) and a.get("url")
            and str(a.get("type") or "image").lower() != "video"]
    wanted = str(cover_url or "").strip()
    cover: Optional[Dict[str, Any]] = None
    for row in rows:
        if wanted and row.get("url") == wanted:
            cover = row
            break
    if cover is None:
        candidates = [r for r in rows if _COVER_HINT.search(str(r.get("url") or ""))]
        if not candidates:
            candidates = [r for r in rows
                          if r.get("height") and r.get("width")
                          and _to_int(r.get("height")) > _to_int(r.get("width"))]
        if not candidates:
            candidates = rows
        cover = max(candidates, key=lambda r: _to_int(r.get("width")) * _to_int(r.get("height")),
                    default=None)

    samples: List[Dict[str, Any]] = []
    for row in rows:
        if cover is not None and row.get("url") == cover.get("url"):
            continue
        width, height = _to_int(row.get("width")), _to_int(row.get("height"))
        if not width or not height or width <= height:           # 只要横版
            continue
        if _SAMPLE_HINT.search(str(row.get("url") or "")):
            samples.append(row)
    if not samples:
        samples = [r for r in rows
                   if (cover is None or r.get("url") != cover.get("url"))
                   and _to_int(r.get("width")) > _to_int(r.get("height")) > 0]
        samples.sort(key=lambda r: _to_int(r.get("width")) * _to_int(r.get("height")),
                     reverse=True)
    out: List[Dict[str, Any]] = []
    for row in samples:
        if len(out) >= max(0, _to_int(sample_count)):
            break
        out.append(row)
    return {"cover": cover, "samples": out}


def _javdb_cmd(cli: Any, args: Sequence[str]) -> List[str]:
    """拼一条 javdb-cli 命令行（复用注入 client 的二进制路径与代理，不读插件配置）。"""
    binary = str(getattr(cli, "bin_path", "") or "").strip() or "javdb"
    proxy = str(getattr(cli, "proxy", "") or "").strip()
    return [binary] + (["--proxy", proxy] if proxy else []) + list(args)


def _run_cli(cli: Any, args: Sequence[str], *, timeout: int = 60,
             stdin_data: Optional[bytes] = None) -> Tuple[int, bytes, bytes]:
    """起一次 javdb-cli 子进程，返回 `(returncode, stdout, stderr)`；**失败也回码不抛**。

    `stdin` 必须显式给出（AGENTS.md §5 的坑）：MP 的 uvicorn 继承的 stdin 是打开的管道，
    不设 `DEVNULL` 会阻塞到超时（`docker exec` 下手跑不复现，所以这里照 `client._run()` 的写法抄）。
    """
    cmd = _javdb_cmd(cli, args)
    try:
        proc = subprocess.run(
            cmd, input=stdin_data,
            stdin=subprocess.DEVNULL if stdin_data is None else None,
            capture_output=True, timeout=max(5, _to_int(timeout) or 60),
        )
    except FileNotFoundError:
        return 127, b"", f"javdb 二进制不存在或不可执行：{cmd[0]}".encode()
    except subprocess.TimeoutExpired:
        return 124, b"", f"调用超时 {timeout}s（网络不通 / 代理不可达）".encode()
    except Exception as error:                                  # noqa: BLE001 - 故意的
        return 1, b"", f"{type(error).__name__}: {error}".encode()
    return proc.returncode, proc.stdout or b"", proc.stderr or b""


def javdb_assets(cli: Any, number: str, *, opts: Optional[Dict[str, Any]] = None,
                 store: Any = None, key: str = "") -> List[Dict[str, Any]]:
    """`javdb assets list <number> --json` → 资产元数据列表（失败回空列表 + 留痕）。

    这一步**只用元数据**（type/url/width/height），真正下载走 `javdb_assets_download()`。
    """
    if not bool(_opt(opts, "javdb_assets", True)) or cli is None:
        return []
    timeout = _to_int(_opt(opts, "javdb_timeout")) or 60
    started = time.time()
    code, out, err = _run_cli(cli, ["assets", "list", str(number), "--json"], timeout=timeout)
    latency = int((time.time() - started) * 1000)
    if code != 0:
        _log_source(store, SRC_IMAGE, "error", key or number, latency,
                    f"assets list 退出码 {code}：{err.decode('utf-8', 'replace')[:200]}")
        return []
    try:
        payload = json.loads(out.decode("utf-8", "replace") or "[]")
    except ValueError:
        _log_source(store, SRC_IMAGE, "error", key or number, latency, "assets list 输出不是 JSON")
        return []
    assets = parse_assets_list(payload)
    _log_source(store, SRC_IMAGE, "ok" if assets else "miss", key or number, latency,
                "" if assets else "assets list 为空")
    return assets


def javdb_assets_download(cli: Any, number: str, assets: Sequence[Dict[str, Any]],
                          *, opts: Optional[Dict[str, Any]] = None, store: Any = None,
                          key: str = "") -> Dict[str, bytes]:
    """下载指定的图片资产，返回 `{url: 字节}`。

    ★ **`assets download` 只认 `TYPE<TAB>URL` 管道格式**（实测：喂 JSON 直接
    `invalid input at line 1 … (want TYPE<TAB>URL)`），所以这里分两步起子进程：
    `assets list <number> --type image <1-based 位置,逗号分隔>` → 管道 → `assets download -d <临时目录>`。
    `-d` 会按顺序自动命名（`image-001.jpg`…）并**逐行打印最终落盘路径**，于是
    「第 i 行输出 ↔ 第 i 个选择器」就是我们的映射；行数对不上就按缺失处理（不瞎猜）。

    下载一律落在 `tempfile` 建的一次性目录里，**不碰数据根**；"已有文件不覆盖"这条
    javdb-cli 语义也因此天然满足（每次都是新目录）。
    """
    rows = [a for a in (assets or []) if isinstance(a, dict) and a.get("url")]
    if not rows or cli is None:
        return {}
    kind = str(rows[0].get("type") or "image").lower()
    selectors = [str(_to_int(a.get("idx"))) for a in rows if _to_int(a.get("idx")) > 0]
    if len(selectors) != len(rows):                             # 拿不到位置就不下载，绝不猜顺序
        _log_source(store, SRC_IMAGE, "error", key or number, 0,
                    "资产缺少 1-based 位置（assets list --json 未给出），跳过下载")
        return {}
    timeout = _to_int(_opt(opts, "javdb_timeout")) or 60
    started = time.time()
    code, out, err = _run_cli(
        cli, ["assets", "list", str(number), "--type", kind, ",".join(selectors)],
        timeout=timeout)
    if code != 0:
        _log_source(store, SRC_IMAGE, "error", key or number,
                    int((time.time() - started) * 1000),
                    f"assets list(pipe) 退出码 {code}：{err.decode('utf-8', 'replace')[:200]}")
        return {}
    lines = [ln for ln in out.decode("utf-8", "replace").splitlines() if _ASSET_LINE.match(ln)]
    if len(lines) != len(selectors):
        _log_source(store, SRC_IMAGE, "error", key or number,
                    int((time.time() - started) * 1000),
                    f"管道记录数 {len(lines)} ≠ 选择器数 {len(selectors)}，放弃这一批下载")
        return {}
    tmp = tempfile.mkdtemp(prefix=_TMP_PREFIX)
    try:
        code, dl_out, dl_err = _run_cli(
            cli, ["assets", "download", "-d", tmp], timeout=timeout,
            stdin_data=out or b"")
        paths = [ln.strip() for ln in dl_out.decode("utf-8", "replace").splitlines()
                 if ln.strip()]
        result: Dict[str, bytes] = {}
        for asset, path in zip(rows, paths):
            try:
                with open(path, "rb") as handle:
                    blob = handle.read()
            except OSError:
                continue
            if blob:
                result[str(asset.get("url"))] = blob
        latency = int((time.time() - started) * 1000)
        _log_source(store, SRC_IMAGE, "ok" if result else "error", key or number, latency,
                    "" if result else
                    f"下载了 0 张（退出码 {code}）：{dl_err.decode('utf-8', 'replace')[:200]}")
        return result
    finally:
        _shutil_rmtree(tmp)


def _shutil_rmtree(path: str) -> None:
    """删掉临时目录（删不掉也不抛：临时目录残留比刮削失败轻得多）。"""
    import shutil

    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:                                           # pragma: no cover - 防御
        pass


# ---------------------------------------------------------------------------
# 标签 / 演员名（`namemap` 缺失即降级）
# ---------------------------------------------------------------------------

def clean_tags(tags: Any, limit: int = 0) -> List[str]:
    """标签净化：`namemap.clean_tags()` 优先，模块缺失时**原样去重 + 限长**。

    写 Emby 的 `GenreItems` 时**必须显式传 `limit=10`**（S3 口径：`limit=0` 是"不限"，
    只给读用途）；`namemap.clean_tags` 内部走 `tag_lookup()` 的简繁双索引，
    所以这里**不要**改用 `store.namemap_find()` —— 那是原文整词匹配，
    繁体 `獨占配信` 查不到（那条记录的 keyword 是简体）。

    降级版**不做**删除规则过滤（`mapping_info.xml` 的删除关键词只有 S3 知道），
    所以降级时宁可保留噪音词，也不假装净化过。
    """
    raw = [t for t in (tags or []) if isinstance(t, (str, dict))]
    cap = _to_int(limit) or GENRE_LIMIT
    if namemap is not None and hasattr(namemap, "clean_tags"):
        try:
            mapped = namemap.clean_tags(raw, limit=cap)
            if isinstance(mapped, (list, tuple)):
                return [str(x) for x in mapped if str(x or "").strip()][:cap]
        except TypeError:                                       # 老签名（无 limit）
            try:
                mapped = namemap.clean_tags(raw)
                if isinstance(mapped, (list, tuple)):
                    return [str(x) for x in mapped if str(x or "").strip()][:cap]
            except Exception as error:                          # pragma: no cover - 防御
                logger.warning(f"AVHelper namemap.clean_tags 失败，退回原样去重：{error}")
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper namemap.clean_tags 失败，退回原样去重：{error}")
    out: List[str] = []
    for item in raw:
        name = _clean_text(item.get("name") if isinstance(item, dict) else item)
        if name and name not in out:
            out.append(name)
    return out[:cap]


def to_simplified(text: Any) -> str:
    """简繁转换（`namemap.to_simplified`；缺失时原样返回）。

    ⚠️ **只对中文用**：实测（REPORT-4 §0.10）把日文标题丢进转换器会被改字
    （`間→间`、`頭→头`），而 javdb 的 `title` 基本是日文原名 —— 所以日文字段一律不过这里。
    """
    value = str(text or "")
    if not value:
        return ""
    if namemap is not None and hasattr(namemap, "to_simplified"):
        try:
            return str(namemap.to_simplified(value) or value)
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper namemap.to_simplified 失败：{error}")
    return value


_NAMEMAP_SYNCED = False


def ensure_namemap(store: Any, opts: Optional[Dict[str, Any]] = None) -> bool:
    """首次刮削前把映射表灌进 `name_map`（`namemap.sync_store()`，幂等）。

    S3 口径：5698 行（5351 演员 + 347 info），**幂等**，失败**不阻塞刮削** ——
    只往 `scrape_log` 记一条 `namemap/error`，让自检页能看见"映射没灌进来"。
    模块级 `_NAMEMAP_SYNCED` 只防同进程重复调用；`opts['force_namemap']=True` 可强制重灌。
    """
    global _NAMEMAP_SYNCED
    options = opts or {}
    if namemap is None or not hasattr(namemap, "sync_store") or store is None:
        return False
    if _NAMEMAP_SYNCED and not bool(_opt(options, "force_namemap")):
        return True
    started = time.time()
    try:
        written = namemap.sync_store(store, force=bool(_opt(options, "force_namemap")))
    except Exception as error:                                  # noqa: BLE001 - 故意的
        _log_source(store, "namemap", "error", "", int((time.time() - started) * 1000),
                    f"{type(error).__name__}: {error}")
        logger.warning(f"AVHelper namemap.sync_store 失败（不阻塞刮削）：{error}")
        return False
    _NAMEMAP_SYNCED = True
    _log_source(store, "namemap", "ok", "", int((time.time() - started) * 1000),
                f"写入 {written} 行")
    return True


def _display_with(mod: Any, name: Any, alias: str = "") -> Dict[str, str]:
    """`namemap.actor_display` 的带模块版本（`sync_actor_avatars` 可注入别的模块）。"""
    raw = _clean_text(name)
    if not raw:
        return {"name": "", "jp": "", "zh": "", "alias": ""}
    if mod is not None and hasattr(mod, "actor_display"):
        try:
            data = mod.actor_display(raw, alias or "")
            if isinstance(data, dict):
                out = {k: _clean_text(data.get(k)) for k in ("name", "jp", "zh", "alias")}
                out["name"] = out["name"] or raw
                return out
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper namemap.actor_display 失败，退回原名：{error}")
    return {"name": raw, "jp": raw, "zh": "", "alias": _clean_text(alias)}


def actor_display(name: Any, alias: str = "") -> Dict[str, str]:
    """演员展示名（`namemap.actor_display`；缺失时降级成 `{name: 原名}`）。

    返回固定形状 `{'name','jp','zh','alias'}`，`name` 是 Emby `People[].Name` 要用的那个
    （契约 D13：`中文（日文）`；只有一边时用那一边）。
    """
    return _display_with(namemap, name, alias)


def _canonical_id_of(mod: Any, name: Any) -> str:
    """`namemap.actor_lookup().canonical_id`（模块缺失/查不到回空串）。"""
    if mod is None or not hasattr(mod, "actor_lookup"):
        return ""
    try:
        row = mod.actor_lookup(name)
    except Exception as error:                                  # pragma: no cover - 防御
        logger.warning(f"AVHelper namemap.actor_lookup 失败：{error}")
        return ""
    return str((row or {}).get("canonical_id") or "") if isinstance(row, dict) else ""


def actor_rows(actors: Any, mod: Any = None) -> List[Dict[str, Any]]:
    """javdb `actors[]` → `meta.actors_json` 的**规范形状**（S7 追加口径，为头像治理服务）。

    每行固定给全这七个键，下游（`film_view()` / `sync_actor_avatars()`）不再各自兼容：

    | 键 | 来源 | 用途 |
    | --- | --- | --- |
    | `name` | D13 规范名 `中文（日文）` | Emby `People[].Name`（**必须与写入值逐字一致**，D15） |
    | `zh` / `jp` | 映射表 / 原名 | 展示、`name` 的构件 |
    | `avatar` | javdb `actors[].avatar_url` | 头像同步（P0-②：javdb 头像是第一顺位） |
    | `javdb_actor_id` | javdb `actors[].id` | 之后可写进 Person 的 `ProviderIds.JavDB`（可选） |
    | `canonical_id` | `namemap.actor_lookup()` | 映射表主键，缺映射时是空串 |
    | `gender` | javdb `actors[].gender`（**0=女 / 1=男**） | 女演员专属写入与头像过滤（P8/R3）；旧行缺失即 `None`，调用方须保守处理 |

    **兼容**：入参既可以是 javdb 原样的 `{id,name,avatar_url,gender}`，也可以是本函数已经
    产出过的行（含 `avatar`/`javdb_actor_id`），重复归一不会丢字段。
    """
    source = mod if mod is not None else namemap
    out: List[Dict[str, Any]] = []
    seen: List[str] = []
    for item in (actors if isinstance(actors, list) else []):
        gender: Any = None
        if isinstance(item, dict):
            raw = item.get("name")
            avatar = item.get("avatar") or item.get("avatar_url") or ""
            actor_id = item.get("javdb_actor_id") or item.get("id") or ""
            gender = item.get("gender")
        else:
            raw, avatar, actor_id = item, "", ""
        display = _display_with(source, raw)
        name = display.get("name") or _clean_text(raw)
        if not name or name in seen:
            continue
        seen.append(name)
        out.append({
            "name": name,
            "zh": display.get("zh") or "",
            "jp": display.get("jp") or _clean_text(raw),
            "avatar": str(avatar or ""),
            "javdb_actor_id": str(actor_id or ""),
            "canonical_id": _canonical_id_of(source, raw),
            "gender": gender,
        })
    return out


def _actor_avatar(actor: Any) -> str:
    """从一行 actor 里取头像地址（两种历史形状都认）。"""
    if not isinstance(actor, dict):
        return ""
    return str(actor.get("avatar") or actor.get("avatar_url") or "")


def _actor_stored_name(actor: Any) -> str:
    """从一行 actor 里取规范名（`name` 优先，其次 `zh`/`jp`）。"""
    if not isinstance(actor, dict):
        return _clean_text(actor)
    return (_clean_text(actor.get("name")) or _clean_text(actor.get("zh"))
            or _clean_text(actor.get("jp")))


def person_name(display: Dict[str, str], fallback: str = "") -> str:
    """`People[].Name` 的规范写法（契约 D13/D14）：`中文（日文）`。

    - 中英都有且不同 → `f"{zh}（{jp}）"`（**全角括号**，实测 Emby 把 `（）` 当词分隔符，
      于是 `皆川千遥`、`みながわ千遥`、`みながわ` 三种搜法全部命中）；
    - 只有一边 → 用那一边；
    - 都没有 → 空串（调用方据此**不写这条 People**）。
    """
    zh = _clean_text((display or {}).get("zh"))
    jp = _clean_text((display or {}).get("jp"))
    name = _clean_text((display or {}).get("name")) or _clean_text(fallback)
    if zh and jp and zh != jp:
        return f"{zh}（{jp}）"
    return zh or jp or name


def build_people(original: Any, actors: Any, director: Any) -> List[Dict[str, Any]]:
    """按契约 §3.6.1 重写 `People[]`（D13/D14）。

    - 演员一条 `{"Name": 规范名, "Type": "Actor"}`，**不写 `Id`**（实测填 Id 与置空行为完全一样，
      写了只会误导后来人以为能"回填 PersonId"）；
    - **只写女演员**：javdb 口径 `gender` 0=女 / 1=男，`1` 一律跳过；`gender` 缺失（旧行 `None`）
      或取值无法判定时**保守保留**（宁可多写一条，也不误删女优）；
    - **不再写导演**（`director` 参数保留只为兼容调用方，本函数不再使用）；
    - **保留原 DTO 里 `Type` 既非 Actor 也非 Director 的元素**（工作室人员/客串等），
      否则一次刮削就把 MetaTube 或用户手工加的其它人员抹掉了。
    """
    kept: List[Dict[str, Any]] = []
    for item in (original if isinstance(original, list) else []):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("Type") or "").strip().lower()
        if kind in ("actor", "director"):
            continue
        kept.append(item)
    out: List[Dict[str, Any]] = list(kept)
    seen: List[str] = []
    for actor in (actors if isinstance(actors, list) else []):
        gender = actor.get("gender") if isinstance(actor, dict) else None
        if gender is not None:
            try:
                if int(gender) == 1:      # javdb 1=男 → 不写进 People
                    continue
            except (TypeError, ValueError):
                pass                      # 脏值判不了男女 → 保守保留
        raw = actor.get("name") if isinstance(actor, dict) else actor
        name = person_name(actor_display(raw))
        if not name or name in seen:
            continue
        seen.append(name)
        out.append({"Name": name, "Type": "Actor", "Role": ""})
    return out


# ---------------------------------------------------------------------------
# 翻译（`translator` 缺失即降级为只用原文）
# ---------------------------------------------------------------------------

def translate_fields(*, display_number: str, title_jp: str, plot_jp: str,
                     actors: Any, opts: Optional[Dict[str, Any]],
                     store: Any = None, key: str = "") -> Dict[str, Any]:
    """把日文标题/简介翻成中文（只有**确实拿到日文**才调 LLM）。

    契约 §3.4 / v4.1 §7：`items=[{'number','title_jp','plot_jp','glossary'}]`，
    返回 `{number: {'title_zh','plot_zh','status','error'}}`。

    降级：`translator` 模块不存在 / `opts['translate']=False` / 没有日文输入 → 一次 LLM 都不调，
    返回 `status='untranslated'`（**绝不编造中文**）。异常也走同一条降级路径。
    """
    blank = {"title_zh": "", "plot_zh": "", "status": "untranslated", "error": "",
             "called": False}
    if not bool(_opt(opts, "translate", True)):
        blank["error"] = "翻译开关关闭"
        return blank
    if not (_clean_text(title_jp) or _clean_text(plot_jp)):
        return blank
    if translator is None or not hasattr(translator, "translate_batch"):
        blank["error"] = "translator 模块缺失（降级：只用原文）"
        return blank
    glossary: Dict[str, str] = {}
    if namemap is not None and hasattr(namemap, "actor_glossary"):
        try:
            names = [(a.get("name") if isinstance(a, dict) else a) for a in (actors or [])]
            glossary = dict(namemap.actor_glossary([n for n in names if n]) or {})
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper namemap.actor_glossary 失败：{error}")
    started = time.time()
    item = {"number": display_number, "title_jp": _clean_text(title_jp),
            "plot_jp": _clean_text(plot_jp) or None, "glossary": glossary}
    kwargs: Dict[str, Any] = {"allow_machine": bool(_opt(opts, "allow_machine"))}
    if store is not None and _accepts(translator.translate_batch, "store"):
        # S4 的 `translate_batch(..., store=…)` 会把结果落进 `translate` 表（二次刮削直接命中缓存，
        # 省一次 LLM 往返）。签名不支持就不传 —— 宁可少一份缓存，也不要 TypeError 把翻译整条打挂。
        kwargs["store"] = store
    try:
        result = translator.translate_batch([item], **kwargs)
    except Exception as error:                                  # noqa: BLE001 - 故意的
        _log_source(store, SRC_LLM, "error", key or display_number,
                    int((time.time() - started) * 1000), f"{type(error).__name__}: {error}")
        blank["error"] = f"{type(error).__name__}: {error}"
        return blank
    entry = {}
    if isinstance(result, dict):
        entry = result.get(display_number) or {}
        if not entry:                                           # 键写法不一致时退到第一条
            for value in result.values():
                if isinstance(value, dict):
                    entry = value
                    break
    status = str((entry or {}).get("status") or "untranslated")
    out = {
        "title_zh": _clean_text((entry or {}).get("title_zh")),
        "plot_zh": _clean_text((entry or {}).get("plot_zh")),
        "status": status, "error": str((entry or {}).get("error") or ""), "called": True,
    }
    _log_source(store, SRC_LLM, "ok" if status == "done" else status, key or display_number,
                int((time.time() - started) * 1000), out["error"])
    return out


# ---------------------------------------------------------------------------
# 取数层总装：三源合并成一份「目标」（写侧与 preview 共用同一份，保证 diff 不会说谎）
# ---------------------------------------------------------------------------

def gather(cli: Any, store: Any, key: str, display_number: str, *,
           opts: Optional[Dict[str, Any]] = None, existing: Optional[Dict[str, Any]] = None,
           version_tags: Optional[Dict[str, Any]] = None,
           javdb_raw: Any = None) -> Dict[str, Any]:
    """三源取数 → 目标字段 + 来源状态 + 警告（**不碰 Emby**）。

    顺位严格照契约：骨架 javdb → 简介 Javtxt（中文直出）→ MetaTube（日文 + 翻译）；
    标签 `namemap.clean_tags`；演员/导演来自 javdb。

    `existing`（`store.meta_get(key)`）里已有 `raw_json['javdb']` 且 `opts['force']` 不为真时
    **跳过 javdb 调用**（契约 §5.3：只补缺不重抓）。
    """
    options = dict(opts or {})
    # `log_sources=False` 时整条取数链一行日志都不写（preview 的纯只读调用方用得上）
    logs = store if bool(_opt(options, "log_sources", True)) else None
    warnings: List[str] = []
    sources: Dict[str, Any] = {
        SRC_JAVDB: {"status": "skipped"}, SRC_JAVTXT: {"status": "skipped"},
        SRC_METATUBE: {"status": "skipped"}, SRC_LLM: {"status": "skipped"},
    }
    prev_raw = (existing or {}).get("raw") or {}
    cached_javdb = javdb_raw if javdb_raw is not None else prev_raw.get("javdb")
    if cached_javdb and not bool(_opt(options, "force")):
        cached_javdb = dict(cached_javdb)
    else:
        cached_javdb = None

    # S11 抓取缓存（`opts['fetch_cache']`，`_tmp/s11/coverage.json`）：命中就**一次站点请求都不发**。
    # 存在的意义是让全库 dry-run 从 17 分钟降到秒级；缓存只是加速器，没命中就照常走真链路。
    row = cache_row(options.get("fetch_cache"), key)
    cache_hit = bool(row)
    cache_only = bool(_opt(options, "cache_only")) and cache_hit
    if cache_hit and not bool(_opt(options, "force")):
        if not cached_javdb:
            detail, why = _javdb_from_cache(row.get("javdb"))
            if isinstance(detail, dict) and detail:
                cached_javdb = detail
                sources[SRC_JAVDB] = {"status": "cache", "why": why,
                                      "fetched_at": (row.get("javdb") or {}).get("fetched_at", "")}
        if _clean_text(row.get("display")):
            display_number = _clean_text(row.get("display")) or display_number
    if cached_javdb and sources[SRC_JAVDB].get("status") == "skipped":
        sources[SRC_JAVDB] = {"status": "cache"}

    if cache_only and not cached_javdb:
        # `cache_only`：缓存的"没有"也是权威结论 —— 不许回落到真站点（否则全库 dry-run
        # 会为 3 条 javdb 失败样本各打一次真实调用，0 请求的保证就没了）。
        skeleton = {"ok": False, "error": (row.get("javdb") or {}).get("error", "")
                    or "缓存里没有 javdb 详情", "display_number": display_number,
                    "title_jp": "", "cover_url": "", "actors": [], "tags": [],
                    "preview_images": [], "from_cache": True}
        sources[SRC_JAVDB] = {"status": "cache_miss",
                              "error": skeleton["error"],
                              "fetched_at": (row.get("javdb") or {}).get("fetched_at", "")}
    else:
        skeleton = javdb_skeleton(cli, display_number, opts=options, store=logs, key=key,
                                  raw=cached_javdb if cached_javdb else None)
    if not skeleton.get("ok"):
        skeleton = dict(skeleton)
        skeleton.setdefault("display_number", display_number)
        skeleton.setdefault("title_jp", "")
        skeleton.setdefault("cover_url", "")
        skeleton.setdefault("actors", [])
        skeleton.setdefault("tags", [])
        skeleton.setdefault("preview_images", [])
        if cached_javdb:
            sources[SRC_JAVDB] = {"status": "cache"}
        elif str(sources.get(SRC_JAVDB, {}).get("status")) == "cache_miss":
            warnings.append(f"缓存里没有 javdb 详情（{skeleton.get('error', '')}）")
        else:
            sources[SRC_JAVDB] = {"status": "error", "error": skeleton.get("error", "")}
            warnings.append(f"javdb 取数失败：{skeleton.get('error', '')}")
    elif not cached_javdb:
        sources[SRC_JAVDB] = {"status": "ok", "latency_ms": skeleton.get("latency_ms", 0)}

    title_jp = _clean_text(skeleton.get("title_jp") or skeleton.get("origin_title") or "")
    origin_jp = _clean_text(skeleton.get("origin_title") or skeleton.get("title_jp") or "")
    plot_jp = _clean_text(skeleton.get("summary_jp") or "")
    title_zh = ""
    plot_zh = ""
    translation_status = "untranslated"
    plot_source = ""

    javtxt_meta: Dict[str, Any] = {}
    metatube_meta: Dict[str, Any] = {}
    plot_sources = [str(s) for s in (_opt(options, "plot_sources") or ())]
    if "javtxt" in plot_sources:
        javtxt = _javtxt_from_cache(row.get("javtxt")) if row else None
        if javtxt is None:
            if cache_only:
                # 缓存的"没命中"同样是权威结论（S11：8 条站点收录缺口，重试也没用）
                javtxt = {"ok": False, "status": "miss", "from_cache": True, "error": "",
                          "title_jp": "", "title_zh": "", "plot_jp": "", "plot_zh": "",
                          "zh_is_machine": False, "actors": [], "vid": "", "url": "",
                          "tried": [], "latency_ms": 0}
            else:
                javtxt = javtxt_lookup(options, display_number, store=logs, key=key)
        javtxt_meta = javtxt
        sources[SRC_JAVTXT] = {
            "status": javtxt.get("status", "miss"), "latency_ms": javtxt.get("latency_ms", 0),
            "url": javtxt.get("url", ""), "error": javtxt.get("error", ""),
        }
        if javtxt.get("from_cache"):
            sources[SRC_JAVTXT]["from_cache"] = True
        if javtxt.get("ok"):
            title_zh = _clean_text(javtxt.get("title_zh"))
            plot_zh = _clean_text(javtxt.get("plot_zh"))
            plot_jp = _clean_text(javtxt.get("plot_jp")) or plot_jp
            if title_zh or plot_zh:
                # 契约 §4.2 坑 3：Javtxt 的中文是**站点机翻**，状态由「允许机翻兜底」开关决定
                translation_status = "machine_fallback" if javtxt.get("zh_is_machine") else "done"
                if javtxt.get("zh_is_machine") and bool(_opt(options, "allow_machine")):
                    translation_status = "done"
            plot_source = "javtxt"
            # 把中文过一遍简繁转换（只对中文用；日文字段绝不过，见 REPORT-4 §0.10）
            title_zh = to_simplified(title_zh)
            plot_zh = to_simplified(plot_zh)
            if not title_zh:
                warnings.append("Javtxt 命中但没取到中文标题")
            if not plot_zh:
                warnings.append("Javtxt 命中但没取到中文简介")
            elif _short_plot_zh(plot_zh, plot_jp, options):
                # S11：`AKDL-332` 的中文简介只有 9 字（站点占位）→ 不能当"已刮全"，
                # 丢弃它让日文走翻译链（`plot_jp` 为空时上面那条判断不成立，短的也留着）
                warnings.append(f"Javtxt 中文简介只有 {len(plot_zh)} 字，按站点占位符丢弃，"
                                f"改走翻译链")
                plot_zh = ""
                plot_source = ""
        elif javtxt.get("status") == "error":
            warnings.append(f"Javtxt 请求失败：{javtxt.get('error', '')}")
        else:
            warnings.append("Javtxt 无同号结果（站点收录缺口，交 MetaTube 兜底）")

    # ★ S0b 的性能纪律：MetaTube search **恒定 ~10 秒**（服务端内部 10s 截止），
    #   所以「Javtxt 已经拿到简介」时**绝不再打它**。只有两种情况值得这 10 秒：
    #   ① 还没有中文简介（契约的概述第二顺位）；② javdb 挂了（契约 §5.2：MetaTube 是
    #   核心骨架字段的第二顺位，仅在 javdb 404 时启用）。
    need_core = str(sources.get(SRC_JAVDB, {}).get("status") or "") == "error"
    if cache_only:
        # dry-run 不打 MetaTube：它恒定 ~10 秒且**不缓存**，108 条就是 18 分钟纯等待
        sources[SRC_METATUBE] = {"status": "skipped", "why": "cache_only dry-run"}
    elif (not plot_zh or need_core) and "metatube" in plot_sources:
        mt = metatube_lookup(options, display_number, store=logs, key=key)
        metatube_meta = mt
        sources[SRC_METATUBE] = {
            "status": mt.get("status", "miss"), "latency_ms": mt.get("latency_ms", 0),
            "provider": mt.get("provider", ""), "id": mt.get("id", ""),
            "candidates": mt.get("candidates", 0), "error": mt.get("error", ""),
        }
        if mt.get("movie"):
            plot_before = plot_jp
            filled = metatube_fill(skeleton, mt["movie"])
            if filled:
                sources[SRC_METATUBE]["filled"] = filled
                warnings.append(f"MetaTube 补上了 javdb 没给的字段：{'/'.join(filled)}")
                title_jp = _clean_text(skeleton.get("title_jp") or title_jp)
                origin_jp = origin_jp or title_jp
                # 「只补空」：javtxt 已经给的简介不许被 MetaTube 顶掉
                if not plot_before:
                    plot_jp = _clean_text(skeleton.get("summary_jp")) or plot_jp
        if mt.get("plot_jp"):
            plot_jp = mt["plot_jp"]
            plot_source = plot_source or "metatube"
        if mt.get("title_jp") and not title_jp:
            title_jp = mt["title_jp"]
        if mt.get("mismatch"):
            warnings.append(f"MetaTube 串号拦截：返回 {mt.get('candidates')} 条候选无一与 "
                            f"{display_number} 同号（该站点查不到时会返回随机结果）")
        elif not mt.get("ok") and mt.get("status") == "miss":
            warnings.append("MetaTube 命中同号条目但没有可用字段（实测命中条目的 summary 恒空）")

    # 翻译：只有确实缺中文、且拿到了日文，才值得花一次 LLM
    need_title = bool(title_jp) and not title_zh
    need_plot = bool(plot_jp) and not plot_zh
    if cache_only:
        # `cache_only` = **不发任何网络请求**（含 LLM）—— dry-run 的语义就是"只读缓存"，
        # 所以这一档一律不翻译；`translation_status` 保持 `untranslated`（如实反映"还没译"）。
        sources[SRC_LLM] = {"status": "skipped", "why": "cache_only dry-run"}
    elif need_title or need_plot:
        tr = translate_fields(
            display_number=display_number,
            title_jp=title_jp if need_title else "",
            plot_jp=plot_jp if need_plot else "",
            actors=skeleton.get("actors"), opts=options, store=logs, key=key)
        if tr.get("title_zh"):
            title_zh = tr["title_zh"]
        if tr.get("plot_zh"):
            plot_zh = tr["plot_zh"]
            plot_source = plot_source or "llm"
        if tr.get("called"):
            translation_status = str(tr.get("status") or "untranslated")
            sources[SRC_LLM] = {"status": tr.get("status", ""), "error": tr.get("error", "")}
            if tr.get("status") not in ("done",):
                warnings.append(f"翻译未完成（{tr.get('status')}）：{tr.get('error', '') or '无中文'}")
        else:
            sources[SRC_LLM] = {"status": "untranslated", "error": tr.get("error", "")}
    elif title_zh or plot_zh:
        sources[SRC_LLM] = {"status": "skipped", "error": "已有中文直出，未调 LLM"}
    if not plot_zh:
        translation_status = "untranslated" if not (title_zh or plot_zh) else translation_status
        plot_source = plot_source or ""

    tags = clean_tags(skeleton.get("tags"), limit=GENRE_LIMIT)
    if not tags and skeleton.get("tags"):
        warnings.append("标签全部被清洗规则滤掉")
    completeness = completeness_of(title_zh, title_jp, plot_zh)
    # 展示番号以**调用方给的那个**为准（它来自 `resolve_key`/`site_number`/缓存行的 `display`）：
    # javdb 的 `number` 只用来补空，**不许反过来覆盖请求番号** —— 万一站点把我们的请求
    # 解析成了别的条目，覆盖 `display_number` 就会把 B 片的号写到 A 片上（写 `Name` 时尤其危险）。
    display = _clean_text(display_number) or _clean_text(skeleton.get("display_number"))
    return {
        "key": key,
        "cli": cli,
        "display_number": display,
        "javdb_id": str(skeleton.get("javdb_id") or ""),
        "title_jp": title_jp,
        "origin_title": origin_jp,
        "title_zh": title_zh,
        "plot_jp": plot_jp,
        "plot_zh": plot_zh,
        "plot_source": plot_source,
        "translation_status": translation_status,
        "actors": [a for a in (skeleton.get("actors") or []) if isinstance(a, dict)],
        "tags": tags,
        "raw_tags": [t for t in (skeleton.get("tags") or []) if isinstance(t, dict)],
        "studio": _clean_text(skeleton.get("maker") or ""),
        "series": _clean_text(skeleton.get("series") or ""),
        "director": _clean_text(skeleton.get("director") or ""),
        "release_date": str(skeleton.get("release_date") or ""),
        "duration": _to_int(skeleton.get("duration")),
        "score": str(skeleton.get("score") or ""),
        "cover_url": str(skeleton.get("cover_url") or ""),
        "thumb_url": str(skeleton.get("thumb_url") or ""),
        "preview_video_url": str(skeleton.get("preview_video_url") or ""),
        "has_cnsub": bool(skeleton.get("has_cnsub")),
        "preview_images": [s for s in (skeleton.get("preview_images") or [])
                           if isinstance(s, dict)],
        "version_tags": dict(version_tags or {}),
        "completeness": completeness,
        "sources": sources,
        "warnings": warnings,
        "javdb_raw": cached_javdb or trim_javdb_raw(skeleton),
        "javtxt_meta": javtxt_meta,
        "metatube_meta": metatube_meta if isinstance(metatube_meta, dict) else {},
    }


# ---------------------------------------------------------------------------
# 写入矩阵（契约 §3.6.1 + §3.6.2）：目标 → Emby 覆盖表
# ---------------------------------------------------------------------------

def build_overrides(target: Dict[str, Any], dto: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """把取数层的结果翻成 `update_item()` 的**字段覆盖表**（契约 §3.6.1 逐行）。

    通用铁律 ①：**只对"拿到的值"动手，拿不到就跳过该字段** —— 所以这里只往 dict 里塞
    有值的键；被跳过的字段根本不会出现在覆盖表里（单测就是断言"请求体里没有这个键"）。

    明确**不写**的键（契约 §3.6.2 实测，写了要么无效要么有害）：
    `RunTimeTicks` / `RemoteTrailers` / `SortName` / `ForcedSortName` / `LockedFields` /
    `Taglines` / `OfficialRating`。`Genres` 字符串数组由 S2 从 `GenreItems` 派生。
    """
    out: Dict[str, Any] = {}
    display = _clean_text(target.get("display_number"))
    title_zh = _clean_text(target.get("title_zh"))
    title_jp = _clean_text(target.get("title_jp"))
    title = title_zh or title_jp

    # Name：display_number + 版本角标 + 标题；标题取不到时**不写 Name**（保留原值）
    if display and title:
        out["Name"] = f"{display}{version_badge(target.get('version_tags'))} {title}"

    original_title = title_jp or _clean_text(target.get("origin_title"))
    if original_title:
        out["OriginalTitle"] = original_title

    plot_zh = _clean_text(target.get("plot_zh"))
    plot_jp = _clean_text(target.get("plot_jp"))
    if plot_zh:
        out["Overview"] = plot_zh
    elif plot_jp:
        # 有日文没中文：写空串**清掉旧的错误机翻**（矩阵明确要求的唯一"写空"例外）
        out["Overview"] = ""

    release = _clean_text(target.get("release_date"))
    stamp = _release_stamp(release)
    if stamp:
        out["PremiereDate"] = stamp
        out["ProductionYear"] = _to_int(release[:4])

    studio = to_simplified(_clean_text(target.get("studio")))
    if studio:
        out["Studios"] = [{"Name": studio}]

    series = _clean_text(target.get("series"))
    if series:
        out["SeriesName"] = series

    tags = [t for t in (target.get("tags") or []) if _clean_text(t)]
    if tags:
        genres = [{"Name": to_simplified(t)} for t in tags][:GENRE_LIMIT]
        out["GenreItems"] = genres

    rating = _to_float(target.get("score"))
    if rating > 0:
        out["CommunityRating"] = rating

    people = build_people((dto or {}).get("People"), target.get("actors"),
                          target.get("director"))
    if people:
        out["People"] = people

    provider_ids: Dict[str, str] = {}
    if display:
        provider_ids["AVHelper"] = display
    if _clean_text(target.get("javdb_id")):
        provider_ids["JavDB"] = _clean_text(target.get("javdb_id"))
    if provider_ids:
        # S2 的 `update_item()` 默认 **合并**（`merge_provider_ids(base, overrides)`），
        # 所以这里只给增量，MetaTube 等原有键由它保住（P0-① 铁律：整份覆盖会抹掉别人的键）。
        out["ProviderIds"] = provider_ids
    return out


_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _release_stamp(value: Any) -> str:
    """`YYYY-MM-DD` → Emby 要的 `YYYY-MM-DDT00:00:00.0000000Z`（格式不合就不写）。"""
    match = _DATE.match(str(value or "").strip())
    if not match:
        return ""
    return f"{match.group(0)}T00:00:00.0000000Z"


def effective_overrides(overrides: Any) -> Dict[str, Any]:
    """覆盖表里**最终真的会写进去**的那部分（与 S2 `writable_overrides()` 对齐）。

    过滤规则（顺序即 S2 的顺序）：

    1. `None` 值丢掉（`build_overrides()` 正常不会产生 None，这里是防御）；
    2. 不在 `emby.WRITABLE_KEYS` 白名单里的丢掉 —— 例如 `SeriesName`（S2 目前的白名单没有它，
       传了会被"忽略不在白名单里的键"丢掉，**不该报成"有改动"**）；
    3. 其余保留（`Overview: ""` 是矩阵明确要求的"清空旧机翻"，**必须算作要写**）。

    存在的意义只有一个：**`changed[]` 不许高估**。真机反例（0.7.0 试点）：
    `FC2PPV4828968` 的 javdb/javtxt 双源全挂，实际只会写 `ProviderIds` 一个字段，
    却因为"每个矩阵字段都出一行"报了 8 个改动。
    """
    src = overrides if isinstance(overrides, dict) else {}
    writable = getattr(emby, "WRITABLE_KEYS", None)
    out: Dict[str, Any] = {}
    for key, value in src.items():
        name = str(key)
        if name.startswith("_") or value is None:
            continue
        if isinstance(writable, (set, frozenset, tuple, list)) and name not in writable:
            continue
        out[name] = value
    return out


def field_diff(dto: Optional[Dict[str, Any]], overrides: Dict[str, Any]) -> List[Dict[str, Any]]:
    """生成 `fields:[{name,current,target,changed}]`（`preview_one` 的字段级 diff）。

    顺序固定走 `MATRIX_FIELDS`，**每个矩阵字段都出一行**（哪怕这次跳过它）：
    `target=None` 就是"拿不到、跳过该字段"的可见证据，比只列改动过的字段有用得多。

    `changed` 的判据是「**最终会写进去 且 与现值不同**」（`effective_overrides()` + 值比对），
    不是"`target` 非空"—— 后者会把压根不会发的字段也算成改动（0.7.0 试点真机反例：
    `FC2PPV4828968` 只写 `ProviderIds`，却报了 8 个"改动"）。
    """
    current = dto if isinstance(dto, dict) else {}
    will_write = effective_overrides(overrides)
    out: List[Dict[str, Any]] = []
    for name in MATRIX_FIELDS:
        out.append({
            "name": name,
            "current": current.get(name, None),
            "target": overrides.get(name, None),
            "changed": name in will_write and _differs(current.get(name, None),
                                                       overrides.get(name)),
        })
    for name in sorted(set(overrides) - set(MATRIX_FIELDS)):
        out.append({"name": name, "current": current.get(name),
                    "target": overrides[name],
                    "changed": name in will_write and _differs(current.get(name), overrides[name])})
    return out


# 集合类字段的"实质"投影：只比 (Name, Type)，忽略 Id/Role/ImageTags 这些**我们不写**的键。
# 为什么需要它：Emby 读回时 `GenreItems`/`Studios` 带 `Id`、`People` 带 `Id`/`ImageTags`，
# 而我们只写 `Name`（+`Type`）。不比投影的话，这三个字段**每次刮削都会报"有改动"**，
# 界面上的"改动"永远消不掉 —— 那是另一种形式的高估。
_COLLECTION_FIELDS = ("GenreItems", "Genres", "Studios", "People")


def _collection_key(value: Any) -> Any:
    """集合字段的比较键：`sorted([(Name, Type), …])`；不是这类形状就回 `None`（退回全量比对）。"""
    if not isinstance(value, list):
        return None
    out: List[Any] = []
    for item in value:
        if isinstance(item, dict):
            name = _clean_text(item.get("Name") or item.get("name"))
            if not name:
                return None
            out.append((name, str(item.get("Type") or "")))
        elif isinstance(item, str):
            out.append((_clean_text(item), ""))
        else:
            return None
    return sorted(out)


def _differs(left: Any, right: Any) -> bool:
    """两个 DTO 值是否不同（集合类按键排序后比，避免顺序造成的假改动）。"""
    if left == right:
        return False
    if left is None and right is None:
        return False
    left_key, right_key = _collection_key(left), _collection_key(right)
    if left_key is not None and right_key is not None:
        return left_key != right_key
    return _canon(left) != _canon(right)


def _canon(value: Any) -> Any:
    """比较用的规范化（dict 去 None 值、list 按 `json` 排序）。"""
    if isinstance(value, dict):
        return {k: _canon(v) for k, v in sorted(value.items()) if v is not None}
    if isinstance(value, list):
        return sorted((_json_dumps(_canon(v)) for v in value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 4)
    return value


# ---------------------------------------------------------------------------
# Emby 写侧编排：备份闸门 → update_item → 图片 → 台账
# ---------------------------------------------------------------------------

def _emby_write_ok(emby_client: Any) -> bool:
    """`emby_client` 是否可用（缺了就整体降级：只更新本地台账，不发写请求）。"""
    if emby_client is None:
        return False
    ready = getattr(emby_client, "ready", None)
    if callable(ready):
        try:
            return bool(ready())
        except Exception:                                       # pragma: no cover - 防御
            return False
    return True


def _backup_gate(store: Any, item_key: str, dto: Optional[Dict[str, Any]],
                 emby_id: str) -> Tuple[bool, str]:
    """备份闸门（裁决 D7）：**没有非空备份就不许写**。

    正确用法是「先存再查」（`store.item_backup_save()` 的 docstring 写明了原因）：
    它的返回值 False 有两种含义（已有备份 / 这次给的备份是空的），只看返回值会把
    "早就备份过"误判成"没备份成"而永远不敢写；所以存完必须用 `item_backup_get()` 复核。
    """
    if dto is None:
        return False, "读不到条目的完整 DTO（read-modify-write 的第一半失败，未发写请求）"
    if store is None or not hasattr(store, "item_backup_save"):
        return False, "未注入 store，无法落写前备份（拒绝写入）"
    try:
        store.item_backup_save(item_key, _json_dumps(dto))
    except Exception as error:                                  # noqa: BLE001 - 故意的
        return False, f"写前备份落库异常：{type(error).__name__}: {error}"
    try:
        saved = str(store.item_backup_get(item_key) or "")
    except Exception as error:                                  # noqa: BLE001
        return False, f"写前备份复核异常：{type(error).__name__}: {error}"
    if not saved:
        return False, "写前备份为空（拿不到 DTO 就不该写 Emby）"
    return True, ""


def _fetch_cover_bytes(url: Any, opts: Dict[str, Any]) -> Tuple[bytes, str]:
    """按 `cover_url` 取封面字节：**优先 `imgproxy.fetch()`**（它负责白名单、Referer、
    `http→https` 升级与 XOR 解包），缺它时退回裸 `http_get` + **图片魔数校验**。

    `imgproxy.fetch()` 返回的已经是可用图片字节（S5 实测 `pics.dmm.co.jp`/`awsimgsrc.dmm.co.jp`
    都在白名单里，DMM 系不校验 Referer）；裸取那条路必须校验魔数 —— javdb 图床的字节是 XOR
    包装的，把垃圾喂给 Emby 会 500（P0-① 实测）。
    """
    text = str(url or "").strip()
    if not text:
        return b"", "没有 cover_url"
    if imgproxy is not None and hasattr(imgproxy, "fetch"):
        try:
            blob = imgproxy.fetch(text, proxy=str(_opt(opts, "proxy") or ""))
        except Exception as error:                              # noqa: BLE001 - 故意的
            return b"", f"imgproxy.fetch 异常：{type(error).__name__}: {error}"
        if blob:
            return bytes(blob), ""
        return b"", "imgproxy.fetch 返回空（不在白名单 / 站点 4xx / 代理不通）"
    body, error, _status = http_get(text, proxy=str(_opt(opts, "proxy") or ""),
                                    timeout=_to_int(_opt(opts, "http_timeout")) or 30)
    if body is None:
        return b"", f"http_get 失败：{error}"
    if not is_image_bytes(body):
        return b"", "拿到的不是图片（缺 imgproxy 时无法解 XOR/Referer，已丢弃）"
    return body, ""


def _upload_images(emby_client: Any, store: Any, emby_id: str, target: Dict[str, Any],
                   assets: Sequence[Dict[str, Any]], opts: Dict[str, Any],
                   key: str, cli: Any = None) -> Dict[str, Any]:
    """封面 → `Primary`、横版剧照 → `Backdrop/0..2` + `Thumb`（**同一张图只下一次**）。

    **封面取数的两级兜底**（缺陷 5，试点批真机）：

    1. javdb `assets list` 挑出来的 cover（优先）；
    2. 拿不到就退回**取数层给的 `cover_url`**（MetaTube 的 dmm 系封面 / javdb 详情的封面），
       走 `imgproxy.fetch(url, proxy)`。真机现象：`12593`(IPOK-025L.iso)/`12596`(CAWB-040.mp4)
       的 javdb 图集是空的（番号查不到 / 该片图集为空），写完 `/img?emby=<id>&type=Primary`
       仍 404 —— 而这两条的 `cover_url` 在 target 里**本来是有的**。
    3. 两级都空/都取不到 → 记 `scrape_log` 与 `report['notes']` 的说明，**不报错**
       （不写 `errors`：封面缺失不该让整条刮削记成失败）。
    裁剪：`imgproxy.crop_poster(raw, anchor=…)` —— **竖图直传、横图按 anchor 裁**（契约 §8.2），
    没有尺寸信息（解码失败/无 Pillow）也一律直传原图，不会崩。

    ⚠️ `Thumb` **只传第一张剧照**：契约 §3.6.1 说"同一张图上传多个 type 时别重复下载"，
    不是"每张剧照都传 Thumb" —— Thumb 是条目列表里那张小图，多传只会互相覆盖。
    """
    report: Dict[str, Any] = {"cover": "skipped", "samples": [], "crop": {}, "errors": [],
                              "notes": []}
    if not bool(_opt(opts, "write_images", True)) or not _emby_write_ok(emby_client):
        report["cover"] = "skipped"
        return report
    picked = pick_assets(assets, cover_url=str(target.get("cover_url") or ""))
    cover = picked.get("cover")
    samples = list(picked.get("samples") or [])
    if not bool(_opt(opts, "write_samples", True)):
        samples = []

    cli = cli if cli is not None else _cli_of(target)
    wanted: List[Dict[str, Any]] = [a for a in ([cover] if cover else []) + samples if a]
    blobs = (javdb_assets_download(cli, str(target.get("display_number") or ""), wanted,
                                   opts=opts, store=store, key=key)
             if (cli is not None and wanted) else {})

    raw: Optional[bytes] = None
    source = ""
    if cover:
        raw = blobs.get(str(cover.get("url")))
        source = "javdb_assets"
    fallback_url = str(target.get("cover_url") or "")
    if not raw and fallback_url:
        raw, why = _fetch_cover_bytes(fallback_url, opts)
        if raw:
            source = "cover_url"
            report["notes"].append(f"javdb 图集没有封面，已用 cover_url 兜底：{fallback_url}")
            _log_source(store, SRC_IMAGE, "ok", key, 0,
                        f"封面走 cover_url 兜底（{len(raw)} B）：{fallback_url}")
        else:
            report["notes"].append(f"cover_url 兜底也失败（{why}）：{fallback_url}")
            _log_source(store, SRC_IMAGE, "error", key, 0, f"cover_url 兜底失败：{why}")
    if raw:
        anchor = str(_opt(opts, "crop_anchor") or "auto")
        jpeg, meta = _crop(raw, anchor, target)
        meta = dict(meta or {})
        meta["source"] = source
        report["crop"] = meta
        ok, detail = _call(emby_client, "upload_image", emby_id, "Primary", jpeg)
        report["cover"] = "ok" if ok else f"error: {detail}"
        if not ok:
            report["errors"].append(f"封面上传失败：{detail}")
    else:
        # 两级都拿不到：**不报错**，只留说明（javdb 图集空 + 没有 cover_url / 取不到）
        report["cover"] = "no_cover"
        if not cover and not fallback_url:
            report["notes"].append("javdb 图集与 cover_url 都没有封面，跳过 Primary")
        elif cover and not fallback_url:
            report["notes"].append(f"javdb 图集的封面下载失败且没有 cover_url 可兜底："
                                   f"{cover.get('url')}")
        _log_source(store, SRC_IMAGE, "miss", key, 0,
                    "封面两级兜底都没拿到字节（javdb 图集 + cover_url），跳过 Primary")
    for index, asset in enumerate(samples[:SAMPLE_COUNT]):
        raw_sample = blobs.get(str(asset.get("url")))
        if not raw_sample:
            report["samples"].append({"url": asset.get("url"), "status": "download_failed"})
            continue
        ok, detail = _call(emby_client, "upload_image", emby_id, f"Backdrop/{index}", raw_sample)
        report["samples"].append({
            "url": asset.get("url"), "type": f"Backdrop/{index}",
            "status": "ok" if ok else f"error: {detail}",
        })
        if index == 0:
            ok2, detail2 = _call(emby_client, "upload_image", emby_id, "Thumb", raw_sample)
            if not ok2:
                report["errors"].append(f"Thumb 上传失败：{detail2}")
    return report


def _crop(raw: bytes, anchor: str, target: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    """`imgproxy.crop_poster()` 的降级包装：没有它就直传原图（并在 meta 里说明）。"""
    if imgproxy is None or not hasattr(imgproxy, "crop_poster"):
        return raw, {"mode": "raw", "anchor": anchor, "reason": "no_imgproxy"}
    version = target.get("version_tags") or {}
    prefix = str(target.get("display_number") or "").upper()
    try:
        return imgproxy.crop_poster(
            raw, anchor=anchor,
            is_fc2=prefix.startswith("FC2"),
            is_vr=bool(version.get("is_vr")),
        )
    except Exception as error:                                  # noqa: BLE001 - 故意的
        logger.warning(f"AVHelper crop_poster 失败，直传原图：{error}")
        return raw, {"mode": "raw", "anchor": anchor, "reason": f"error: {error}"}


def _cli_of(target: Dict[str, Any]) -> Any:
    """取数层带回来的 `cli` 引用（图片下载要它；`target['cli']` 由 `gather` 注入）。"""
    return target.get("cli")


def _accepts(func: Any, name: str) -> bool:
    """目标函数是否接受某个**关键字参数**（用来安全地传可选能力，如 `store=`）。

    并行施工期各模块的签名会各自演进；`_accepts` 让"多一个可选依赖"退化成"少一项优化"，
    而不是 `TypeError` 把整条链打挂。
    """
    try:
        import inspect

        params = inspect.signature(func).parameters
    except (TypeError, ValueError):                             # pragma: no cover - 防御
        return False
    if name in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _call(holder: Any, name: str, *args: Any) -> Tuple[bool, str]:
    """调一个返回 `(ok, detail)` 的方法；异常/缺失一律折成 `(False, 原因)`。"""
    func = getattr(holder, name, None) if holder is not None else None
    if not callable(func):
        return False, f"{name} 不可用"
    try:
        result = func(*args)
    except Exception as error:                                  # noqa: BLE001 - 故意的
        return False, f"{type(error).__name__}: {error}"
    if isinstance(result, tuple):
        ok = bool(result[0]) if result else False
        detail = str(result[1]) if len(result) > 1 else ""
        return ok, detail
    return bool(result), ""


def write_item(store: Any, emby_client: Any, target: Dict[str, Any], *, item_key: str,
               key: str, emby_id: str, opts: Optional[Dict[str, Any]] = None,
               library: Any = None, assets: Optional[Sequence[Dict[str, Any]]] = None,
               cli: Any = None, dry: bool = False) -> Dict[str, Any]:
    """把「目标」写进 Emby + 更新本地台账（**写侧唯一入口**）。

    顺序（顺序本身就是安全设计，别调换）：

    1. `emby_client.get_item(emby_id)` 读完整 DTO（本机唯一可用的读法）；
    2. `store.item_backup_save()` + `item_backup_get()` **闸门**：没有非空备份就**直接拒绝写入**；
    3. `build_overrides()` 出覆盖表 → `emby_client.update_item()`（S2 内部 get/合并/剔只读/POST）；
    4. 图片（封面 `Primary` + 横版剧照 `Backdrop/0..2`/`Thumb`）；
    5. 成功后才写 `meta` / `media_item` / `scrape_log`（写失败**不留"已刮"的假状态**）。

    `dry=True` 时只做第 1 步与覆盖表（**不发任何写请求、不落任何库**）—— 给"只想看会写什么"
    的调用方用；`preview_one` 走的是自己那条更轻的路径（它连备份与台账都不碰），不走这里。
    """
    options = dict(opts or {})
    # 每个实例一份**带自己角标**的视图（缺陷 1）：`locate_instances()` 已经用盘上路径派生过一次，
    # 下面读到 DTO 后再用条目自己的 `Path` 补正一次（DTO 才是权威，且**不额外增加请求**）。
    local = dict(target)
    result: Dict[str, Any] = {
        "ok": False, "status": "skipped", "changed": [], "images": {}, "error": "",
        "emby_id": emby_id, "item_key": item_key, "key": key,
        "completeness": target.get("completeness", "missing_core"),
        "version_tags": version_labels(local.get("version_tags")),
    }
    if not _emby_write_ok(emby_client):
        result["error"] = "未配置 Emby（emby_client 不可用），仅更新本地台账"
        result["status"] = "no_emby"
        _persist(store, local, item_key=item_key, key=key, emby_id=emby_id, opts=options,
                 library=library, assets=assets, wrote=False,
                 completeness=result["completeness"], error=result["error"])
        return result

    dto = None
    getter = getattr(emby_client, "get_item", None)
    if callable(getter):
        try:
            dto = getter(emby_id)
        except Exception as error:                              # noqa: BLE001 - 故意的
            result["error"] = f"读 Emby DTO 异常：{type(error).__name__}: {error}"
    if not isinstance(dto, dict):
        result["status"] = "error"
        result["error"] = result["error"] or "读不到 Emby 完整 DTO"
        _log_source(store, SRC_EMBY_WRITE, "error", key, 0, result["error"])
        return result

    local["version_tags"] = item_version_tags(dto, target.get("version_tags"))
    result["version_tags"] = version_labels(local["version_tags"])
    result["version_tags_raw"] = dict(local["version_tags"])
    overrides = build_overrides(local, dto)
    result["fields"] = field_diff(dto, overrides)
    result["changed"] = [f["name"] for f in result["fields"] if f["changed"]]
    if dry:
        result.update({"status": "preview", "ok": True})
        return result
    if not overrides:
        result["status"] = "nothing"
        result["error"] = "没有可写字段（取数层什么都没拿到）"
        _log_source(store, SRC_EMBY_WRITE, "skip", key, 0, result["error"])
        return result

    allowed, reason = _backup_gate(store, item_key, dto, emby_id)
    if not allowed:
        result["status"] = "blocked"
        result["error"] = reason
        _log_source(store, SRC_EMBY_WRITE, "blocked", key, 0, reason)
        return result

    started = time.time()
    ok, detail = _call(emby_client, "update_item", emby_id, overrides)
    if not ok:
        result["status"] = "error"
        result["error"] = f"Emby 写入失败：{detail}"
        _log_source(store, SRC_EMBY_WRITE, "error", key,
                    int((time.time() - started) * 1000), result["error"])
        return result

    images = _upload_images(emby_client, store, emby_id, local, assets or [],
                            options, key, cli=cli)
    result["images"] = images
    result["notes"] = list(images.get("notes") or [])
    if images.get("errors"):
        result["error"] = "；".join(images["errors"])
    _log_source(store, SRC_EMBY_WRITE, "ok", key,
                int((time.time() - started) * 1000), result["error"])
    result["ok"] = True
    result["status"] = "ok"
    _persist(store, local, item_key=item_key, key=key, emby_id=emby_id, opts=options,
             library=library, assets=assets, wrote=True,
             completeness=result["completeness"], error=result["error"])
    return result


def _persist(store: Any, target: Dict[str, Any], *, item_key: str, key: str, emby_id: str,
             opts: Dict[str, Any], library: Any = None, assets: Any = None,
             wrote: bool, completeness: str, error: str = "") -> None:
    """写成功后更新本地台账（`meta` + `media_item`）并让 Emby 内存索引失效。

    `wrote=False`（没写 Emby，例如未配置）时**仍然写 meta**（取数结果本身有价值，
    读侧要靠它渲染标题/简介），但 `media_item.scrape_state` 保持 `unscraped`
    —— 不能因为"我们抓到了数据"就显示"已刮进库"。
    """
    now = _now(opts)
    existing = None
    if store is not None and hasattr(store, "meta_get"):
        try:
            existing = store.meta_get(key)
        except Exception:                                       # pragma: no cover - 防御
            existing = None
    version_tags = dict(target.get("version_tags") or {})
    state = scrape_state_of(completeness) if wrote else "unscraped"
    retry_count, next_retry = apply_backoff(
        completeness if wrote else "", (existing or {}).get("retry_count"), now)
    raw = pack_raw_json(
        target.get("javdb_raw"), target.get("javtxt_meta"), target.get("metatube_meta"),
        extra={"version_tags": version_tags, "plot_source": target.get("plot_source", ""),
               "sources": {k: str((v or {}).get("status") or "")
                           for k, v in (target.get("sources") or {}).items()}},
    )
    meta_fields = {
        "display_number": target.get("display_number") or key,
        "javdb_id": target.get("javdb_id") or "",
        "title_jp": target.get("title_jp") or "",
        "title_zh": target.get("title_zh") or "",
        "plot_jp": target.get("plot_jp") or "",
        "plot_zh": target.get("plot_zh") or "",
        "translation_status": target.get("translation_status") or "untranslated",
        "actors_json": actor_rows(target.get("actors")),
        "tags_json": target.get("tags") or [],
        "studio": target.get("studio") or "",
        "series": target.get("series") or "",
        "director": target.get("director") or "",
        "release_date": target.get("release_date") or "",
        "runtime_min": _to_int(target.get("duration")),
        "rating": _to_float(target.get("score")),
        "cover_raw_url": target.get("cover_url") or "",
        "samples_json": [s.get("large_url") for s in (target.get("preview_images") or [])
                         if isinstance(s, dict) and s.get("large_url")][:SAMPLE_COUNT],
        "trailer_url": target.get("preview_video_url") or "",
        "raw_json": raw,
        "completeness": completeness if wrote else "missing_core",
        "retry_count": retry_count,
        "next_retry_at": next_retry if wrote else "",
        "last_scraped_at": now,
    }
    if store is None:
        return
    try:
        if hasattr(store, "meta_upsert"):
            store.meta_upsert(key, **meta_fields)
        if hasattr(store, "item_upsert"):
            store.item_upsert(
                item_key, key,
                display_number=target.get("display_number") or key,
                emby_id=emby_id,
                version_tags_json=version_tags,
                crop_anchor=str(_opt(opts, "crop_anchor") or "auto"),
                library_state="in_library" if wrote else "not_in_library",
                scrape_state=state,
                last_synced_at=now,
            )
    except Exception as error_obj:                              # noqa: BLE001 - 故意的
        logger.error(f"AVHelper 更新刮削台账失败（{item_key}）：{error_obj}")
    if wrote and library is not None and hasattr(library, "invalidate"):
        try:
            library.invalidate()
        except Exception as error_obj:                          # pragma: no cover - 防御
            logger.warning(f"AVHelper library.invalidate 失败：{error_obj}")


# ---------------------------------------------------------------------------
# 实例定位：key → (item_key, emby_id)
# ---------------------------------------------------------------------------

def locate_instances(store: Any, key: str, display_number: str,
                     opts: Optional[Dict[str, Any]] = None,
                     item_key: str = "") -> List[Dict[str, Any]]:
    """定位该作品下的**全部**实例 —— 一个番号可能对应多个 Emby 条目（含各自的角标）。

    返回 `[{item_key, emby_id, path, number, version_tags}, …]`。

    ★ S11 全库实测（`_tmp/s11/REPORT-S11.md`，事实：设计缺口）：
    **同一个 `norm_key` 可能挂多个 Emby 条目** —— `IPZZ586` ×2、`MIRD277` ×4（`-A/-B/-C/-D`）。
    只写第一条的后果不是"少刮一点"，而是**另外 4 条永远没有元数据**（用户看到 4 张空卡片）。
    `media_item` 本身是一行一个 `emby_id`，表结构天然支持多实例，所以这里必须全列出来。

    ★ 每个实例**自带 `version_tags`**（0.7.0 试点缺陷 1）：能拿到盘上路径时
    （`media_item.file_path` → S11 缓存行 `emby[].path`）就地用**该条目的文件名**解析一次；
    拿不到就先留 `{}`，由 `write_item()` 在读到 DTO 后用它自己的 `Path` 补正
    （`item_version_tags()`）—— **同一组多实例各用各的文件名**，`-UC` 的那条有角标、
    普通版没有，正好是 v4.1 §9.2 第 6 条要的版本角标。

    顺序：显式实例键 → `media_item` 全部行 → `opts['emby_id']` → Emby 内存索引（只补一条）。
    同 `emby_id` 去重；`item_key` 一律规范化成 `emby:<id>`（避免同一实例两种写法各写一遍）。
    抓取缓存只用来**补路径/角标**，**不会凭空造实例**（台账里没有就是没有）。
    """
    options = opts or {}
    out: List[Dict[str, Any]] = []
    seen: List[str] = []

    def add(item: Any, emby_id: Any, path: Any = "") -> None:
        ident = str(emby_id or "").strip()
        if not ident or ident in seen:
            return
        seen.append(ident)
        text = str(item or "").strip()
        info = item_number({"Path": path}) if path else {}
        out.append({
            "item_key": text if text.startswith("emby:") else f"emby:{ident}",
            "emby_id": ident,
            "path": str(path or ""),
            "number": str((info or {}).get("number") or ""),
            "version_tags": dict((info or {}).get("version_tags") or {}),
        })

    text = str(item_key or "").strip()
    match = _ITEM_KEY.match(text)
    if match and match.group("kind").lower() == "emby":
        add(text, match.group("tail").strip())
        return out
    if store is not None and hasattr(store, "item_list") and key:
        try:
            for row in store.item_list(key=key) or []:
                if isinstance(row, dict):
                    add(row.get("item_key"), row.get("emby_id"), row.get("file_path"))
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper item_list({key}) 失败：{error}")
    forced = str(options.get("emby_id") or "").strip()
    if forced:
        add(f"emby:{forced}", forced)
    if out:
        # 台账里没有 file_path 时，用 S11 抓取缓存里的 emby[].path 补（本地、零请求）
        cached = (cache_row(options.get("fetch_cache"), key).get("emby") or [])
        paths = {str(e.get("id") or ""): str(e.get("path") or "") for e in cached
                 if isinstance(e, dict)}
        for entry in out:
            if not entry["path"] and paths.get(entry["emby_id"]):
                info = item_number({"Path": paths[entry["emby_id"]]})
                entry["path"] = paths[entry["emby_id"]]
                entry["number"] = entry["number"] or str(info.get("number") or "")
                entry["version_tags"] = dict(info.get("version_tags") or {})
        return out
    library = options.get("library")
    finder = getattr(library, "lookup", None) if library is not None else None
    if callable(finder):
        try:
            hit = finder(display_number)
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper EmbyLibrary.lookup 失败：{error}")
            hit = None
        if isinstance(hit, dict):
            add(f"emby:{hit.get('id')}", hit.get("id"), hit.get("path"))
    return out


def locate_items(store: Any, key: str, display_number: str, opts: Optional[Dict[str, Any]] = None,
                 item_key: str = "") -> List[Tuple[str, str]]:
    """`locate_instances()` 的**实例键对**视图：`[(item_key, emby_id), …]`。

    保留这个形状是因为它是**已经上线的对外形状**（S8 的 `__init__.py` 与它的用例都按
    `[("emby:12598", "12598")]` 断言）。角标等逐实例信息在 `locate_instances()` 里，
    要那几项的调用方直接用它 —— 别为了少写一行去改别人的用例。
    """
    return [(entry["item_key"], entry["emby_id"])
            for entry in locate_instances(store, key, display_number, opts, item_key)]


def locate_item(store: Any, key: str, display_number: str, opts: Optional[Dict[str, Any]] = None,
                item_key: str = "") -> Tuple[str, str]:
    """`locate_items()` 的第一个（代表实例），没有就回 `("", "")`。

    `library`（`emby.EmbyLibrary`）只在**台账里一条都没有**时才问一次 —— 它是"刮削到哪一条"的
    最后兜底，不是主路径（它的 `lookup()` 会按需建一次全库索引）。
    """
    found = locate_items(store, key, display_number, opts, item_key)
    return found[0] if found else ("", "")


# 从文件名里认番号的顺序（**只用路径，绝不用 Name**，见 `number_from_dto`）
def number_from_dto(dto: Any) -> str:
    """从 Emby DTO 反推展示番号（`emby:12598` 这种"只有 id"的输入必须有这一步）。

    顺序：`Path` → `FileName` → `MediaSources[0].Path`，一律取 basename 再 `parse_av_number()`。

    ★ **绝不用 `Name`**（S11 全库 108 部实测，`_tmp/s11/REPORT-S11.md`）：

    - `parse_av_number(Name)` 只有 **6/112 = 5.4%** 命中 —— `Name` 是 MetaTube 写进去的
      中文翻译标题（`ADN-801 ど田舎の… 女教师…`），整串锚定认不出番号；
    - 而 `parse_av_number(Path)` 是 **102/112**，剩下 10 条交给 `EmbyLibrary._item_keys()` 的兜底；
    - `Path` 与 `Name` 双侧都解析成功的 96 条里，**键不同 = 0** → 只用 Path 是安全且更准的。

    拿 `Name` 当番号源的后果不是"少刮一条"，而是**可能刮成另一部片**（Name 里的中文标题偶尔
    会带别的番号形态），所以这里连"兜底"都不做：认不出就回空串，让调用方走 Emby 索引兜底。
    """
    data = dto if isinstance(dto, dict) else {}
    info = item_number(data)
    return info["number"]


def item_number(dto: Any) -> Dict[str, Any]:
    """从**条目自己的文件名**派生 `{number, version_tags, path, matched}`。

    与 `number_from_dto()` 是同一套解析，但把 `version_tags` 一起带出来 ——
    **写侧拿不到角标是 0.7.0 试点抓到的真机缺陷**：

    | 请求的 key | 旧行为 `version_tags` | `Name` 目标 |
    | --- | --- | --- |
    | `IPZZ-912-UC` | `["中字流出"]` | `IPZZ-912 [中字流出] 标题` ✅ |
    | `IPZZ912`（工作台给的是干净键） | `[]` | `IPZZ-912 标题` ❌ 角标没了 |
    | `emby:12595` | `[]` | 同上 ❌ |

    而 `IPZZ-912-UC` 与 `IPZZ912` 是**同一部片**（`norm_key` 都是 `IPZZ912`），
    主路径给的就是干净键 → 盘上文件名里的「中字流出」信息就再也出不来。
    所以角标必须以**该条目自己的文件名**为准：文件在盘上是什么，就是什么。

    `number` 仍是干净号（`IPZZ-912`）—— 角标只进 `Name` 的 `{badge}` 与
    `media_item.version_tags_json`，不参与番号匹配（契约 D1）。
    """
    data = dto if isinstance(dto, dict) else {}
    paths: List[str] = []
    for key in ("Path", "FileName"):
        if data.get(key):
            paths.append(str(data[key]))
    for source in (data.get("MediaSources") or []):
        if isinstance(source, dict) and source.get("Path"):
            paths.append(str(source["Path"]))
    out: Dict[str, Any] = {"number": "", "version_tags": {}, "path": "", "matched": False}
    for path in paths:
        base = str(path).replace("\\", "/").rsplit("/", 1)[-1]
        parsed = emby.parse_av_number(base)
        if parsed.matched and parsed.display_number:
            return {
                "number": str(parsed.display_number),
                "version_tags": dict(parsed.version_tags or {}),
                "path": str(path), "matched": True,
            }
    return out


def item_version_tags(dto: Any, fallback: Any = None) -> Dict[str, Any]:
    """该条目的 `version_tags`：**条目文件名优先**，解析不出文件名才退回请求键的角标。

    「优先」是**整体替换而不是逐键合并**：`IPZZ-912.mp4`（普通版）解出来的角标是 `{}`，
    那就该是 `{}` —— 请求键里的 `-UC` 属于另一个实例，逐键合并会把它的「中字流出」
    错安到普通版头上（同组多实例时尤其明显：`MIRD-277-A/B/C/D` 各有各的角标）。
    """
    info = item_number(dto)
    if info.get("matched"):
        return dict(info.get("version_tags") or {})
    return dict(fallback or {})


def _read_dto(emby_client: Any, emby_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """只读一份完整 DTO（`get_item` 是**读**操作，preview 也允许）；返回 `(dto, 错误)`。"""
    if not emby_id or not _emby_write_ok(emby_client):
        return None, "" if not emby_id else "emby_client 不可用"
    getter = getattr(emby_client, "get_item", None)
    if not callable(getter):
        return None, "emby_client 没有 get_item"
    try:
        dto = getter(emby_id)
    except Exception as error:                                  # noqa: BLE001 - 故意的
        return None, f"{type(error).__name__}: {error}"
    return (dto if isinstance(dto, dict) else None), ("" if isinstance(dto, dict)
                                                      else "读不到 Emby 完整 DTO")


# ---------------------------------------------------------------------------
# 公开接口 1：preview_one（**零写请求**）
# ---------------------------------------------------------------------------

def preview_one(key: Any, *, store: Any, cli: Any, emby_client: Any = None,
                opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """字段级 diff 预览（REST `/scrape/preview`）：**不发任何写请求**。

    产出 `{key, number, item_key, emby_id, fields:[{name,current,target,changed}],
    sources:{javdb,javtxt,metatube,llm}, warnings:[], images:{…}, completeness}`。

    `current` 来自 Emby DTO（`get_item` 是**读**，允许）；`target` 来自取数层。
    本函数**不调** `update_item` / `upload_image` / `delete_image`，**不写** meta/media_item
    （单测就是断言假 `emby_client` 的写方法与假 `store` 的写方法调用次数都是 0）。
    数据源结果仍会进 `scrape_log`（那是审计日志；`opts['log_sources']=False` 可关）。
    """
    options = dict(opts or {})
    resolved = resolve_key(key)
    found = locate_instances(store, resolved.get("key") or "",
                             resolved.get("display_number") or "", options,
                             resolved.get("item_key") or "")
    first = found[0] if found else {"item_key": "", "emby_id": "", "path": "",
                                    "version_tags": {}, "number": ""}
    item_key, emby_id = first["item_key"], first["emby_id"]
    # `emby:12598` 这种输入本身不带番号：先从条目 DTO 的**路径**反推（S11：绝不用 Name）。
    dto, dto_error = _read_dto(emby_client, emby_id)
    number = (str(options.get("display_number") or "").strip()
              or resolved.get("display_number") or resolved.get("number")
              or number_from_dto(dto) or first.get("number")
              or resolved.get("input") or "")
    key_text = resolved.get("key") or emby.canon_key(number) or number
    # ★ 缺陷 1：角标以**该实例自己的文件名**为准（DTO 优先 → 定位时用盘上路径派生的 → 请求键）
    instance_tags = item_version_tags(dto, first.get("version_tags")
                                      or resolved.get("version_tags"))
    existing = _meta_of(store, key_text)
    target = gather(cli, store, key_text, number, opts=options, existing=existing,
                    version_tags=instance_tags)
    target["cli"] = cli
    result_tags = version_labels(target.get("version_tags"))

    warnings = list(target.get("warnings") or [])
    if not emby_id:
        warnings.append("没有找到对应的 Emby 条目（只在取数层预览，current 全为空）")
    elif not isinstance(dto, dict):
        warnings.append(f"没读到 Emby 完整 DTO（current 全为空）：{dto_error or '未知原因'}")
    if len(found) > 1:
        warnings.append(f"该番号下有 {len(found)} 个 Emby 条目，这里预览的是代表实例 "
                        f"{item_key}；scrape_one 会把它们全部写一遍")

    overrides = build_overrides(target, dto)
    # `assets list` 是一次 javdb-cli **子进程**（也是真实网络调用）→ `cache_only` 下必须跳过，
    # 否则"0 请求 dry-run"会为每条片子起一次进程。跳过时用 meta 里的原图地址兜底出图集计划。
    if bool(_opt(options, "cache_only")) and cache_row(options.get("fetch_cache"), key_text):
        assets = []
    else:
        assets = (javdb_assets(cli, number, opts=options, store=store, key=key_text)
                  if (number and bool(_opt(options, "javdb_assets", True))) else [])
    picked = pick_assets(assets, cover_url=str(target.get("cover_url") or ""))
    samples = [(s or {}).get("url") for s in (picked.get("samples") or [])]
    if not assets:
        # 没有几何信息（缓存模式）：直接用 javdb 详情的剧照地址，**不按横竖过滤**，
        # 并在 `source` 里标明这一档是元数据推算而不是实测挑选。
        samples = [str(s.get("large_url") or "") for s in (target.get("preview_images") or [])
                   if isinstance(s, dict) and s.get("large_url")][:SAMPLE_COUNT]
    images = {
        "cover": (picked.get("cover") or {}).get("url") or target.get("cover_url") or "",
        "samples": samples,
        "anchor": str(_opt(options, "crop_anchor") or "auto"),
        "assets": len(assets),
        "source": "assets" if assets else "meta",
        # 真实封面链路的**预览**：javdb 图集空时，写侧会退回 `cover_url`（缺陷 5）
        "plan": ("javdb_assets" if (picked.get("cover") and assets)
                 else ("cover_url" if target.get("cover_url") else "none")),
    }
    return {
        "key": key_text,
        "number": number,
        "display_number": target.get("display_number") or number,
        "item_key": item_key,
        "emby_id": emby_id,
        # `items[]` 保持**已上线的形状**（`[{item_key, emby_id}]`，S8 的用例按它断言）；
        # 逐实例的角标等新增信息放 `instances[]`（只加不改）。
        "items": [{"item_key": entry["item_key"], "emby_id": entry["emby_id"]}
                  for entry in found],
        "instances": [{"item_key": entry["item_key"], "emby_id": entry["emby_id"],
                       "path": entry.get("path") or "",
                       "number": entry.get("number") or "",
                       "version_tags": version_labels(entry.get("version_tags"))}
                      for entry in found],
        "fields": field_diff(dto, overrides),
        "sources": target.get("sources") or {},
        "warnings": warnings,
        "images": images,
        "completeness": target.get("completeness"),
        "title_zh": target.get("title_zh"), "title_jp": target.get("title_jp"),
        "title": target.get("title_zh") or target.get("title_jp") or "",
        "plot_zh_len": len(target.get("plot_zh") or ""),
        "plot_jp_len": len(target.get("plot_jp") or ""),
        "translation_status": target.get("translation_status"),
        "version_tags": result_tags,
        "version_tags_raw": dict(target.get("version_tags") or {}),
    }


# ---------------------------------------------------------------------------
# 公开接口 2：scrape_one / scrape_batch
# ---------------------------------------------------------------------------

def scrape_one(key: Any, *, store: Any, cli: Any, emby_client: Any,
               opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """刮削一条：取数（**一次**）→ 写 Emby（**该番号下的全部实例，逐个写**）→ 更新台账。

    两处关键设计：

    1. **一个番号可能挂多个 Emby 条目**（S11 实测 `IPZZ586`×2、`MIRD277`×4）→ 取数只做一次
       （三源调用最贵），但 `write_item()` 对每个 `emby:<id>` 各跑一遍（各自读 DTO、各自备份、
       各自写 `media_item`）。只写第一条会让其余实例永远缺元数据。
    2. Tier1 的「只补缺不重抓」：`meta.raw_json['javdb']`（或 `opts['fetch_cache']` 的缓存行）
       已存在且 `opts['force']` 不为真时**跳过 javdb 调用**，只补简介（契约 §5.3）。

    返回（**向后兼容单实例的形状**，多出来的 `items[]` 是每个实例的明细）：

    `{ok, status, key, number, item_key, emby_id, changed[], images{}, sources{}, warnings[],
    completeness, translation_status, retry:{retry_count,next_retry_at}, error,
    items:[{item_key, emby_id, ok, status, changed[], images{}, error}], written, total}`
    `status` ∈ `ok` / `partial` / `nothing` / `blocked` / `no_emby` / `error`。
    """
    options = dict(opts or {})
    ensure_namemap(store, options)
    resolved = resolve_key(key)
    found = locate_instances(store, resolved.get("key") or "",
                             resolved.get("display_number") or "", options,
                             resolved.get("item_key") or "")
    if not found:
        return {
            "ok": False, "status": "error", "key": resolved.get("key") or str(key or ""),
            "number": resolved.get("display_number") or str(key or ""), "item_key": "",
            "emby_id": "", "changed": [], "images": {}, "sources": {}, "warnings": [],
            "completeness": "missing_core", "retry": {}, "items": [], "written": 0, "total": 0,
            "error": "找不到该番号对应的 Emby 条目（先用 /library 或 item_upsert 登记）",
        }
    first = found[0]
    item_key, emby_id = first["item_key"], first["emby_id"]
    number = (str(options.get("display_number") or "").strip()
              or resolved.get("display_number") or resolved.get("number") or "")
    if not number:
        # 输入是 `emby:<id>` 时番号只能从**路径**反推（S11：绝不用 Name）；缓存行里也有一份
        row = cache_row(options.get("fetch_cache"), resolved.get("key") or "")
        number = _clean_text(row.get("display"))
        for entry in found:
            if number:
                break
            dto, _err = _read_dto(emby_client, entry["emby_id"])
            number = number_from_dto(dto)
        number = number or resolved.get("input") or ""
    key_text = resolved.get("key") or emby.canon_key(number) or number
    existing = _meta_of(store, key_text)
    # 取数**只做一次**（三源调用最贵）；角标由每个实例在 `write_item()` 里用自己的文件名定。
    # 这里传代表实例的角标只作兜底（比如条目读不到 DTO 时 `_persist` 仍要有个值）。
    target = gather(cli, store, key_text, number, opts=options, existing=existing,
                    version_tags=first.get("version_tags")
                    or resolved.get("version_tags"))
    target["cli"] = cli
    assets: List[Dict[str, Any]] = []
    if number and bool(_opt(options, "write_images", True)) \
            and bool(_opt(options, "javdb_assets", True)):
        assets = javdb_assets(cli, number, opts=options, store=store, key=key_text)

    results: List[Dict[str, Any]] = []
    for entry in found:
        one = write_item(
            store, emby_client, target, item_key=entry["item_key"], key=key_text,
            emby_id=entry["emby_id"], opts=options, library=options.get("library"),
            assets=assets, cli=cli)
        one.pop("fields", None)
        results.append({
            "item_key": entry["item_key"], "emby_id": entry["emby_id"],
            "ok": bool(one.get("ok")), "status": one.get("status"),
            "changed": one.get("changed") or [], "images": one.get("images") or {},
            "error": one.get("error") or "",
            "notes": one.get("notes") or [],
            "version_tags": one.get("version_tags") or version_labels(entry.get("version_tags")),
        })
    changed: List[str] = []
    for one in results:
        for name in one["changed"]:
            if name not in changed:
                changed.append(name)
    wrote = [one for one in results if one["ok"]]
    ok_all = len(wrote) == len(results)
    notes: List[str] = []
    for one in results:
        for note in one.get("notes") or []:
            if note not in notes:
                notes.append(note)
    report: Dict[str, Any] = {
        "ok": bool(wrote) and ok_all,
        "status": "ok" if ok_all and wrote else ("partial" if wrote else results[0]["status"]),
        "key": key_text, "number": number,
        "item_key": item_key, "emby_id": emby_id,
        "changed": changed, "images": results[0]["images"],
        "sources": target.get("sources") or {},
        # 图片兜底之类的"说明"折进 warnings：**不是错误**，但用户该看见
        "warnings": list(target.get("warnings") or []) + notes,
        "notes": notes,
        "completeness": target.get("completeness"),
        "translation_status": target.get("translation_status"),
        "error": "；".join(one["error"] for one in results if one["error"]),
        "items": results, "written": len(wrote), "total": len(results),
        "version_tags": results[0]["version_tags"],
    }
    # 本片女演员头像同步（R3/P0-②）：元数据写入成功后才做，**失败绝不能让刮削本身失败**
    if wrote:
        try:
            names = [row["name"] for row in actor_rows(target.get("actors")) if row.get("name")]
            if names:
                avatar_sync = sync_actor_avatars(
                    store, emby_client, names=names, dry_run=False, opts=options)
                failed = [str(err) for err in (avatar_sync.get("errors") or []) if str(err)]
                if failed:
                    report["warnings"].append("头像同步：" + "；".join(failed))
        except Exception as error:                              # noqa: BLE001 - 头像同步不阻断刮削
            logger.warning(f"AVHelper 头像同步失败（不影响刮削）：{type(error).__name__}: {error}")
            report["warnings"].append(f"头像同步失败：{type(error).__name__}: {error}")
    meta = _meta_of(store, key_text)
    report["retry"] = {
        "retry_count": _to_int((meta or {}).get("retry_count")),
        "next_retry_at": str((meta or {}).get("next_retry_at") or ""),
    }
    return report


def scrape_batch(keys: Any, *, store: Any, cli: Any, emby_client: Any,
                 opts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """批量刮削：逐条独立（**一条失败不影响其它条**），返回与入参同序的结果列表。

    只做"逐条 try/except + 汇总"，不做并发：本环境是**单节点美区出口**，
    并发打 javdb/javtxt 只会更快触发站点限流与 `javdb-cli` 的 1 小时冷却
    （契约 §8.2 的冷却机制就是为串行调用设计的）。要吞吐请由调用方按批切分。
    """
    rows = keys if isinstance(keys, (list, tuple, set)) else [keys]
    out: List[Dict[str, Any]] = []
    for raw in rows:
        try:
            out.append(scrape_one(raw, store=store, cli=cli, emby_client=emby_client, opts=opts))
        except Exception as error:                              # noqa: BLE001 - 故意的
            logger.error(f"AVHelper 刮削 {raw!r} 异常：{type(error).__name__}: {error}")
            out.append({
                "ok": False, "status": "error", "key": str(raw), "number": str(raw),
                "changed": [], "images": {}, "sources": {}, "warnings": [],
                "completeness": "missing_core", "retry": {},
                "error": f"{type(error).__name__}: {error}",
            })
    return out


# ---------------------------------------------------------------------------
# 公开接口 3：rollback_item
# ---------------------------------------------------------------------------

def rollback_item(item_key: Any, *, store: Any, emby_client: Any) -> Dict[str, Any]:
    """回滚一条：把 `store.item_backup_get()` 的完整 DTO 回灌成**基线状态**（只认 204）。

    ⚠️ **S2 的 `update_item()` 是「合并覆盖」语义**（GET → 剔只读键 → 盖上覆盖表 → POST），
    所以"整份还原"要靠覆盖表**显式表达清空**，不能只把备份里有的键塞进去：

    1. 覆盖表走 `_restore_payload()` → `emby.restore_overrides(backup)`（S2 交付）。
       它解决的正是**回滚链断掉**的那个真机缺陷：Emby 对"没有值的可选字段"会整个省略该键
       （12598 写前备份 45 键里**没有 `Overview`**），而"备份里没有的键 = 不动" →
       备份原样回灌**回滚不掉 `Overview`**。`restore_overrides()` 对基线缺席但可清空的标量
       显式写 `None`（S2 落成 `""`）、缺席集合键写 `[]`、`ProviderIds` 整份还原
       （`provider_ids_replace=True` 已包含）。
    2. ⚠️ **`PremiereDate`/`ProductionYear` 的清空未实测**（S2 交底），所以它们**保持"不动"**
       —— 宁可留旧值，也不要拿空串去赌 400。
    3. **正常写入路径不共用这套**：`scrape_one()` 该跳过的字段仍要跳过（"拿不到就不写"），
       回滚是"整份还原"，两者语义不同，所以分成两个函数。

    只读键（`Path`/`MediaSources`/`RunTimeTicks`/`ImageTags`…）由 S2 从**当前** DTO 重新取，
    这是对的：它们是服务端/探针维护的，本来就不该被备份覆盖。

    `Etag` 不可复现（P0-① 实测：内容改回原样也回不到原值），任何比对都要排除它 ——
    所以 `restored` 是"可写键里已经等于备份值"的清单，不含 `Etag`。

    图片另说（D16）：每次上传都会重算 `PrimaryImageTag`，**回滚不能照搬备份里的 `ImageTags`**。
    本函数按"备份里原本没有封面 → 删掉现在这张"处理，并在 `images` 里如实回报；
    备份里**原本有封面**的情形本函数**无法还原**（原始字节没落盘），会在返回里标出来。
    """
    name = str(item_key or "").strip()
    out: Dict[str, Any] = {"ok": False, "item_key": name, "emby_id": "", "restored": [],
                           "images": {}, "error": ""}
    if not name:
        out["error"] = "item_key 为空"
        return out
    raw = ""
    if store is not None and hasattr(store, "item_backup_get"):
        try:
            raw = str(store.item_backup_get(name) or "")
        except Exception as error:                              # noqa: BLE001 - 故意的
            out["error"] = f"读备份异常：{type(error).__name__}: {error}"
            return out
    if not raw:
        out["error"] = "没有写前备份，无法回滚（从未刮削过，或备份被清空）"
        return out
    try:
        backup = json.loads(raw)
    except ValueError:
        out["error"] = "备份不是合法 JSON（拒绝用坏数据回灌 Emby）"
        return out
    if not isinstance(backup, dict) or not backup:
        out["error"] = "备份为空对象（拒绝回灌）"
        return out
    emby_id = str(backup.get("Id") or "").strip()
    if not emby_id:
        _prefix, _, tail = name.partition(":")
        emby_id = tail.strip()
    out["emby_id"] = emby_id
    if not _emby_write_ok(emby_client):
        out["error"] = "未配置 Emby（emby_client 不可用）"
        return out

    before = None
    getter = getattr(emby_client, "get_item", None)
    if callable(getter):
        try:
            before = getter(emby_id)
        except Exception:                                       # pragma: no cover - 防御
            before = None

    overrides = _restore_payload(backup)
    started = time.time()
    ok, detail = _call(emby_client, "update_item", emby_id, overrides)
    if not ok:
        out["error"] = f"回灌失败：{detail}"
        _log_source(store, SRC_EMBY_WRITE, "error", name,
                    int((time.time() - started) * 1000), out["error"])
        return out
    _log_source(store, SRC_EMBY_WRITE, "ok", name, int((time.time() - started) * 1000), "rollback")

    after = None
    if callable(getter):
        try:
            after = getter(emby_id)
        except Exception:                                       # pragma: no cover - 防御
            after = None
    out["restored"] = _restored_fields(backup, before, after)

    images: Dict[str, Any] = {}
    if isinstance(after, dict):
        had_cover = bool((backup.get("ImageTags") or {}).get("Primary"))
        now_cover = bool((after.get("ImageTags") or {}).get("Primary"))
        if not had_cover and now_cover:
            ok_img, detail_img = _call(emby_client, "delete_image", emby_id, "Primary")
            images["cover"] = "deleted" if ok_img else f"error: {detail_img}"
        elif had_cover and now_cover:
            images["cover"] = ("unrestorable: 备份里原有封面，原始字节未落盘，"
                               "无法还原（D16）")
        else:
            images["cover"] = "unchanged"
    out["images"] = images
    if store is not None and hasattr(store, "item_set"):
        try:
            store.item_set(name, scrape_state="unscraped", library_state="not_in_library",
                           last_synced_at=_now())
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper 回滚后更新 media_item 失败：{error}")
    out["ok"] = True
    return out


def _restore_payload(backup: Dict[str, Any]) -> Dict[str, Any]:
    """备份 DTO → **能真正还原**的覆盖表（回滚专用，与正常写入的语义**不同**）。

    首选 `emby.restore_overrides(backup)`（S2 交付，2026-10-14）。为什么非它不可 ——
    S2 的真机 E2E 抓到的缺陷：

    - Emby 对"没有值的可选字段"**会整个省略该键**：12598 写前的 DTO 与备份里**根本没有
      `Overview`**（45 键），写一次之后才出现（46 键）；
    - 而 `update_item()` 是「以当前 DTO 为底、覆盖表改哪算哪」→ **备份里没有的键 = 不动**，
      不是清空 → 「备份原样回灌」**回滚不掉 `Overview`**，条目停在验证态、与备份 sha 不一致。
    - `restore_overrides()` 补上了这一层：基线缺席但可清空的标量显式写 `None`
      （`writable_overrides()` 会落成 `""`）、缺席的集合键写 `[]`、`ProviderIds` 整份还原
      （`provider_ids_replace=True` 已包在里面）。

    ⚠️ **未验证项（S2 明确交底，别赌）**：`NULL_CLEARABLE_KEYS` 只覆盖**字符串类**字段
    （`Name`/`OriginalTitle`/`Overview`/`SeriesName`/`OfficialRating`/`CommunityRating`/
    `Taglines`）；`PremiereDate`/`ProductionYear` 是日期/数值型，**清空写法未实测**，
    所以它们**故意不在表里** → 回滚时**保持"不动"**（宁可留旧值，也不要拿空串去赌 400）。
    等真机探明"清空写不服 400"再由 S2 放进那张表，本函数不用改。

    降级：`emby.py` 里没有 `restore_overrides`（旧版/正在改）时退回老写法
    （剔只读键 + `provider_ids_replace=True`）—— 它至少能还原**备份里有的**字段。
    """
    src = backup if isinstance(backup, dict) else {}
    # 先把只读键剔掉再交给 S2：`restore_overrides()` 是**整份复制**备份的，
    # 只读键（`Path`/`MediaSources`/`Etag`/`Id`… 实测 32 个）留着不会写错，
    # 但会让 `writable_overrides()` 为每一个键记一条"忽略只读键"的 warning（一次回滚 30 条噪音），
    # 而且只读键本来就不在 `WRITABLE_KEYS` 里 → 剔掉**不影响**它的"缺席即清空"判定。
    cleaned = {k: v for k, v in src.items() if k not in emby.READONLY_KEYS}
    builder = getattr(emby, "restore_overrides", None)
    if callable(builder):
        try:
            out = builder(cleaned)
            if isinstance(out, dict) and out:
                return out
        except Exception as error:                              # noqa: BLE001 - 故意的
            logger.warning(f"AVHelper emby.restore_overrides 失败，退回老写法：{error}")
    overrides = dict(cleaned)
    overrides["provider_ids_replace"] = True
    overrides["ProviderIds"] = dict(src.get("ProviderIds") or {})
    return overrides


def _restored_fields(backup: Dict[str, Any], before: Any, after: Any) -> List[str]:
    """回滚后「确实已经等于备份值」的可写键清单（`Etag` 之类的只读键天然不在里面）。"""
    if not isinstance(after, dict):
        return []
    out: List[str] = []
    for name in MATRIX_FIELDS:
        if name not in backup:
            continue
        want = _canon(backup.get(name))
        got = _canon(after.get(name))
        if want != got:
            continue
        if isinstance(before, dict) and _canon(before.get(name)) == want:
            continue                                            # 本来就没变，不算"恢复"
        out.append(name)
    for name, value in backup.items():
        if name in MATRIX_FIELDS or name in emby.READONLY_KEYS:
            continue
        if _canon(value) == _canon(after.get(name)):
            if not (isinstance(before, dict) and _canon(before.get(name)) == _canon(value)):
                out.append(name)
    return out


# ---------------------------------------------------------------------------
# 公开接口 4：sources_selfcheck（四个源各打一次探针）
# ---------------------------------------------------------------------------

SELFCHECK_NUMBER = "SNOS-380"


def sources_selfcheck(store: Any, cli: Any, opts: Optional[Dict[str, Any]] = None
                      ) -> List[Dict[str, Any]]:
    """四个源各打一次轻量探针，写 `scrape_log` 并返回逐源结果。

    返回 `[{source, status, latency_ms, error, checked_at, detail}]`（`status` ∈
    `ok` / `miss` / `error` / `skipped`）。探针一律走**轻量调用**：

    - javdb：`cli.detail('SNOS-380')`（真实存在的老片，1 次子进程）；
    - javtxt：搜索 + 详情（受 2s 站点间隔约束，约 3–5 s）；
    - metatube：`/v1/movies/search`（本地服务器，毫秒级）；
    - llm：`translator.selfcheck()`（模块缺失时 `skipped`，不假装成功）。
    """
    options = dict(opts or {})
    ensure_namemap(store, options)
    stamp = _now(options)
    out: List[Dict[str, Any]] = []

    started = time.time()
    detail = None
    reason = ""                      # ★ 必须先初始化：`detail()` 正常返回 None 时不会进 except
    getter = getattr(cli, "detail", None) if cli is not None else None
    if callable(getter):
        try:
            detail = getter(SELFCHECK_NUMBER)
        except Exception as error:                              # noqa: BLE001 - 故意的
            detail = None
            reason = f"{type(error).__name__}: {error}"
    else:
        reason = "未注入 javdb client"
    latency = int((time.time() - started) * 1000)
    if isinstance(detail, dict) and detail:
        out.append({"source": SRC_JAVDB, "status": "ok", "latency_ms": latency, "error": "",
                    "checked_at": stamp,
                    "detail": {"number": detail.get("number"), "title": bool(detail.get("title"))}})
    else:
        # 失败原因优先用 client 记下的真话（`JavdbClient.last_error` 里有子进程的 stderr 摘要：
        # 二进制不存在 / 代理不可达 / 超时 …），拿不到才退回一句笼统的说明。
        reporter = getattr(cli, "last_error", None) if cli is not None else None
        if callable(reporter) and not reason:
            try:
                reason = str(reporter(f"detail:{SELFCHECK_NUMBER}") or "")
            except Exception:                                   # pragma: no cover - 防御
                reason = ""
        out.append({"source": SRC_JAVDB, "status": "error", "latency_ms": latency,
                    "error": reason or f"javdb 没有 {SELFCHECK_NUMBER} 的详情"
                                       f"（番号下架 / 站点改版 / 被风控）",
                    "checked_at": stamp, "detail": {}})

    for source, probe in ((SRC_JAVTXT, _probe_javtxt), (SRC_METATUBE, _probe_metatube)):
        out.append(probe(options, store, stamp))

    started = time.time()
    llm: Dict[str, Any] = {"source": SRC_LLM, "status": "skipped", "latency_ms": 0,
                           "error": "", "checked_at": stamp, "detail": {}}
    if translator is not None and hasattr(translator, "selfcheck"):
        try:
            result = translator.selfcheck()
            ok = bool((result or {}).get("ok"))
            llm.update({
                "status": "ok" if ok else "error",
                "latency_ms": _to_int((result or {}).get("latency_ms")) or
                int((time.time() - started) * 1000),
                "error": str((result or {}).get("error") or ""),
                "detail": {"model": (result or {}).get("model", "")},
            })
        except Exception as error:                              # noqa: BLE001 - 故意的
            llm.update({"status": "error",
                        "latency_ms": int((time.time() - started) * 1000),
                        "error": f"{type(error).__name__}: {error}"})
    else:
        llm["error"] = "translator 模块缺失（翻译链不可用，不影响取数）"
    out.append(llm)

    for row in out:
        _log_source(store, row["source"], row["status"], SELFCHECK_NUMBER,
                    row.get("latency_ms", 0), row.get("error", ""))
    return out


def _probe_javtxt(opts: Dict[str, Any], store: Any, stamp: str) -> Dict[str, Any]:
    """javtxt 探针：真的搜一次 + 真的抓一次详情（否则"能连上"毫无意义）。"""
    result = javtxt_lookup(opts, SELFCHECK_NUMBER, store=None)
    ok = bool(result.get("ok"))
    return {
        "source": SRC_JAVTXT,
        "status": "ok" if ok else str(result.get("status") or "miss"),
        "latency_ms": result.get("latency_ms", 0),
        "error": result.get("error", ""),
        "checked_at": stamp,
        "detail": {"url": result.get("url", ""), "vid": result.get("vid", ""),
                   "title_zh": bool(result.get("title_zh")),
                   "plot_zh_len": len(result.get("plot_zh") or "")},
    }


def _probe_metatube(opts: Dict[str, Any], store: Any, stamp: str) -> Dict[str, Any]:
    """MetaTube 探针：走一次搜索并**如实回报串号拦截**（这正是它最需要被盯住的行为）。"""
    result = metatube_lookup(opts, SELFCHECK_NUMBER, store=None)
    return {
        "source": SRC_METATUBE,
        "status": str(result.get("status") or "miss"),
        "latency_ms": result.get("latency_ms", 0),
        "error": result.get("error", ""),
        "checked_at": stamp,
        "detail": {"candidates": result.get("candidates", 0),
                   "mismatch": result.get("mismatch", False),
                   "provider": result.get("provider", "")},
    }


# ---------------------------------------------------------------------------
# 公开接口 6：sync_actor_avatars（P0-② 落地版：演员头像写进 Person 实体）
# ---------------------------------------------------------------------------

AVATAR_SOURCE = "emby_avatar"


def _avatar_index(store: Any, mod: Any) -> Dict[str, Dict[str, Any]]:
    """汇总「规范名 → {avatar, javdb_actor_id, numbers[]}」（`meta.actors_json` 是唯一来源）。

    同一演员出现在多部片里时合并；**头像取第一条非空的**（javdb 的演员头像是第一顺位，
    S0b：MetaTube 的 `actors` 只有名字、没有头像）。
    """
    index: Dict[str, Dict[str, Any]] = {}
    if store is None or not hasattr(store, "meta_list"):
        return index
    try:
        rows = store.meta_list() or []
    except Exception as error:                                  # noqa: BLE001 - 故意的
        logger.warning(f"AVHelper meta_list 失败（头像同步跳过）：{error}")
        return index
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_actors = row.get("actors")
        if not isinstance(raw_actors, list):
            raw_actors = _json_load_list(row.get("actors_json"))
        for actor in actor_rows(raw_actors, mod):
            name = actor["name"]
            if not name:
                continue
            slot = index.setdefault(name, {"name": name, "zh": actor["zh"], "jp": actor["jp"],
                                           "avatar": "", "javdb_actor_id": "",
                                           "gender": actor.get("gender"), "numbers": []})
            if not slot["avatar"] and actor["avatar"]:
                slot["avatar"] = actor["avatar"]
            if not slot["javdb_actor_id"] and actor["javdb_actor_id"]:
                slot["javdb_actor_id"] = actor["javdb_actor_id"]
            if slot.get("gender") is None and actor.get("gender") is not None:
                slot["gender"] = actor.get("gender")
            number = str(row.get("display_number") or row.get("key") or "")
            if number and number not in slot["numbers"]:
                slot["numbers"].append(number)
    return index


def _json_load_list(text: Any) -> List[Any]:
    """把 `actors_json` 这类 JSON 列文本解析成列表（解析不出回空列表）。"""
    if isinstance(text, list):
        return text
    try:
        data = json.loads(str(text or "[]"))
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _image_bytes(url: str, opts: Dict[str, Any]) -> Tuple[bytes, str]:
    """取头像字节：**优先 `imgproxy.fetch()`**（它负责 Referer 与 XOR 解包）。

    `imgproxy` 缺失时退回裸 `http_get` —— 但 javdb 图床（`tp.spfcas.com`）的字节是 XOR 包装的，
    裸取会拿到非图片数据，所以这里**必须校验图片魔数**，不合格就报错而不是把垃圾传给 Emby
    （P0-① 实测：非 base64 / 非图片的 body 会让 Emby 回 500）。
    """
    if not url:
        return b"", "没有头像地址"
    if imgproxy is not None and hasattr(imgproxy, "fetch"):
        try:
            blob = imgproxy.fetch(url, proxy=str(_opt(opts, "proxy") or ""))
        except Exception as error:                              # noqa: BLE001 - 故意的
            return b"", f"imgproxy.fetch 异常：{type(error).__name__}: {error}"
        if blob:
            return bytes(blob), ""
        return b"", "imgproxy.fetch 返回空"
    body, error, _status = http_get(url, proxy=str(_opt(opts, "proxy") or ""),
                                     timeout=_to_int(_opt(opts, "http_timeout")) or 30)
    if body is None:
        return b"", f"http_get 失败：{error}"
    if not is_image_bytes(body):
        return b"", "拿到的不是图片（缺 imgproxy 时无法解 XOR/Referer，已丢弃）"
    return body, ""


def is_image_bytes(blob: Any) -> bool:
    """图片魔数校验（JPEG/PNG/GIF/WEBP）—— 挡住 XOR 包装与非图片响应。"""
    data = bytes(blob or b"")
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


# Gfriends 兜底的 provider 名（MetaTube `/v1/actors/search` 返回的 `provider` 字段）
GFRIENDS_PROVIDER = "Gfriends"


def _gfriends_avatar(opts: Dict[str, Any], jp: Any,
                     timeout: int = 0) -> Tuple[str, str, str]:
    """Gfriends 兜底：javdb 没头像时，按**日文原名**去 MetaTube 的 `/v1/actors/search` 找一张。

    返回 `(url, error, reason)`：

    - 命中 → `("https://raw.githubusercontent.com/…", "", "")`（取 `data[].images[0]`）；
    - **HTTP 404 / 没有 Gfriends 条目 = "该演员不在 Gfriends" = 没有头像**（`reason='not_found'`），
      **绝不是错误**，调用方不许把它记进 `errors`；
    - 未配置 `metatube_base` → `reason='unconfigured'`；演员行没有 `jp` → `reason='no_jp_name'`；
    - 只有真异常（连不上 / 非 JSON）才把文案放进 `error`。

    ⚠️ 地址**只从 `_opt(opts, "metatube_base")` 取，绝不写死**；查询用演员行的 `jp`
    （日文原名），**不是规范名** `中文（日文）`（实测规范名带全角括号与中文，查不到）。
    """
    base = str(_opt(opts, "metatube_base") or "").rstrip("/")
    if not base:
        return "", "", "unconfigured"
    query = _clean_text(jp)
    if not query:
        return "", "", "no_jp_name"
    url = f"{base}/v1/actors/search?{urlencode({'q': query})}"
    body, error, status = _metatube_fetch(opts, url,
                                          _to_int(_opt(opts, "metatube_timeout")) or METATUBE_TIMEOUT)
    if body is None:
        if status == 404:                       # 业务空值：该演员不在 Gfriends，不重试也不记错误
            return "", "", "not_found"
        return "", error or "请求失败", ""
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return "", "返回不是合法 JSON", ""
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return "", "", "not_found"
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("provider") or "").lower() != GFRIENDS_PROVIDER.lower():
            continue
        images = item.get("images")
        if not isinstance(images, list):
            continue
        for image in images:
            text = str(image or "").strip()
            if text:
                return text, "", ""
    return "", "", "not_found"


def sync_actor_avatars(store: Any, emby_client: Any, *, limit: int = 0, dry_run: bool = True,
                       namemap_mod: Any = None, opts: Optional[Dict[str, Any]] = None,
                       names: Optional[List[str]] = None
                       ) -> Dict[str, Any]:
    """把演员头像同步到 Emby 的 **Person 实体**（P0-② / v4.1 §6.2 的落地版）。

    流程与依据（每一条都对应 `_tmp/p0/REPORT-2.md` 的实测）：

    1. 从 `store.meta_list()` 的 `actors_json` 汇总「规范名 → 头像 / javdb_actor_id」；
    2. 规范名 = 契约 D13 的 `中文（日文）`（`person_name()`；只有一边时用那一边，
       **映射表没有的演员只写日文原名，绝不音译**）；
    3. `emby_client.find_person(规范名)` —— Emby 的 Person **以 `Name` 为唯一键、精确匹配**
       （D15：`SortName`/`ProviderIds` 一概不参与匹配，`People[].Id` 会被彻底忽略）；
    4. Person 存在且 `ImageTags.Primary` 为空 → 下头像 → `upload_image(pid, "Primary", raw)`；
    5. 可选写 `ProviderIds["JavDB"]`（`provider_ids_replace=False`，即**合并**；
       S2 的 `merge_provider_ids()` 是通用实现，对 Person 同样适用 —— 实测 `JavDB` 与
       `MetaTube` 两个键可以并存）；
    6. **`dry_run=True` 时零写请求**：只 `find_person`（读）+ 产出动作清单，一个字节都不上传；
    7. 找不到 Person（该演员的影片还没刮过 / 名字还没统一）→ `reason='person_missing'`，
       **不算错误**（这正是"先把影片 People 写对，Emby 自己收敛实体"的必然过渡态）。
    8. **只写女演员**（R3，`_avatar_index()` 的行里已有 `gender`）：`1`（男）直接跳过；
       `None`（旧数据缺字段）**保守跳过**并单独计入 `gender_unknown`（**不混进 `missing_person`**）；
       只有 `0`（女）进上传流程。
    9. **javdb 没有头像（行里 `avatar` 为空）时走 Gfriends 兜底**（R5）：按演员行的 `jp`
       （**日文原名**）打 `{metatube_base}/v1/actors/search?q=`，命中取 `data[].images[0]`；
       **404 = 该演员不在 Gfriends = 没有头像，不是错误**；两源都没有 → `action='skip'` +
       `reason='no_avatar'`（另带 `gfriends` 原因码）。
    10. `names` 给了就**只处理这些规范名**（单片刮完只同步本片演员；自动路径绝不走全表）；
       `None` = 现有的全量行为。

    返回 `{ok, dry_run, actors, planned:[{name, person_id, action, reason, url?, source?}],
    applied:[…], errors:[…], missing_person, gender_unknown}`；`actors` 是**过滤后真正进流程**的
    条数（性别 + `names` 过滤在前，`limit` 在后）。
    """
    options = dict(opts or {})
    mod = namemap_mod if namemap_mod is not None else namemap
    planned: List[Dict[str, Any]] = []
    applied: List[Dict[str, Any]] = []
    errors: List[str] = []
    out: Dict[str, Any] = {
        "ok": False, "dry_run": bool(dry_run), "actors": 0, "planned": planned,
        "applied": applied, "errors": errors, "missing_person": 0, "gender_unknown": 0,
    }
    if emby_client is None or not _emby_write_ok(emby_client):
        errors.append("未配置 Emby（emby_client 不可用）")
        return out
    index = _avatar_index(store, mod)
    rows = sorted(index.values(), key=lambda row: row["name"])
    if names is not None:                       # R5：单片路径只处理这一片的演员
        wanted = {_clean_text(item) for item in names}
        wanted.discard("")
        rows = [row for row in rows if row["name"] in wanted]
        if not rows:
            out["ok"] = True                    # 这些名字还不在 meta 索引里 = 无事可做，不是错误
            return out
    if not rows:
        errors.append("meta 里还没有演员（先刮削几条再来同步头像）")
        return out
    # gender 过滤（R3，保守口径）：1=男 直接跳过；None=旧数据 保守跳过并单独计数；只有 0=女 进流程
    female: List[Dict[str, Any]] = []
    for row in rows:
        gender = row.get("gender")
        if gender in (None, ""):
            gender = None
        else:
            try:
                gender = int(gender)
            except (TypeError, ValueError):
                gender = None
        if gender == 1:
            continue
        if gender is None:
            out["gender_unknown"] += 1
            continue
        female.append(row)
    rows = female
    size = _to_int(limit)
    if size > 0:
        rows = rows[:size]
    out["actors"] = len(rows)
    if not rows:
        out["ok"] = not errors                  # 全被 gender 过滤掉：没有可同步的，不是错误
        return out

    writer = bool(_opt(options, "person_provider_ids", True))
    for row in rows:
        name = row["name"]
        entry: Dict[str, Any] = {"name": name, "person_id": "", "action": "skip", "reason": ""}
        finder = getattr(emby_client, "find_person", None)
        person = None
        if callable(finder):
            try:
                person = finder(name)
            except Exception as error:                          # noqa: BLE001 - 故意的
                errors.append(f"{name}：find_person 异常 {type(error).__name__}: {error}")
                entry["reason"] = "find_failed"
                planned.append(entry)
                continue
        if not isinstance(person, dict) or not str(person.get("Id") or ""):
            out["missing_person"] += 1
            entry["reason"] = "person_missing"
            planned.append(entry)
            continue
        entry["person_id"] = str(person.get("Id"))
        has_image = bool((person.get("ImageTags") or {}).get("Primary"))
        if has_image and not bool(_opt(options, "avatar_force", False)):
            entry["reason"] = "has_image"
            planned.append(entry)
            continue
        # 取图：javdb 头像是第一顺位；它没有时才按**日文原名**去 Gfriends 兜底（R5）
        avatar_url = str(row.get("avatar") or "")
        source = "javdb" if avatar_url else ""
        if not avatar_url:
            avatar_url, gfriends_error, gfriends_reason = _gfriends_avatar(options, row.get("jp"))
            if gfriends_error:
                entry["action"] = "failed"
                entry["reason"] = f"Gfriends 兜底失败：{gfriends_error}"
                errors.append(f"{name}：Gfriends 兜底失败 {gfriends_error}")
                planned.append(entry)
                continue
            if avatar_url:
                source = "gfriends"
        if not avatar_url:
            entry["reason"] = "no_avatar"        # 两源都没有：如实跳过（javdb 空 + Gfriends 无）
            entry["gfriends"] = gfriends_reason
            planned.append(entry)
            continue
        entry.update({"action": "upload_avatar", "url": avatar_url, "source": source})
        planned.append(entry)
        if dry_run:
            continue
        raw, error = _image_bytes(avatar_url, options)
        if not raw:
            entry["action"] = "failed"
            entry["reason"] = error
            errors.append(f"{name}：{error}")
            continue
        ok, detail = _call(emby_client, "upload_image", entry["person_id"], "Primary", raw)
        if not ok:
            entry["action"] = "failed"
            entry["reason"] = detail
            errors.append(f"{name}：上传头像失败 {detail}")
            continue
        applied.append(dict(entry, bytes=len(raw)))
        _log_source(store, AVATAR_SOURCE, "ok", name, 0, "")
        if writer and row.get("javdb_actor_id"):
            ok2, detail2 = _call(emby_client, "update_item", entry["person_id"],
                                 {"ProviderIds": {"JavDB": row["javdb_actor_id"]}})
            if not ok2:
                # 不致命：头像已经上去了，provider 写失败只记日志（S3/S2 的口径）
                errors.append(f"{name}：写 ProviderIds.JavDB 失败 {detail2}")
                _log_source(store, AVATAR_SOURCE, "error", name, 0, detail2)
    out["ok"] = not errors
    return out


# ---------------------------------------------------------------------------
# 公开接口 5：film_view（**零抓取、零外网**）
# ---------------------------------------------------------------------------

COVER_URL = f"{IMG_PROXY}?url={{url}}"


def img_url(url: Any) -> str:
    """图床地址 → 插件图片代理地址（外网图必须经代理，AGENTS.md 铁律 3）。"""
    text = str(url or "").strip()
    return COVER_URL.format(url=quote(text, safe="")) if text else ""


def emby_img_url(emby_id: Any, img_type: str = "Primary") -> str:
    """`/img?emby=<id>` —— **局域网原图直取**分支（S5 实现），走它就没有图床防盗链问题。"""
    text = str(emby_id or "").strip()
    if not text:
        return ""
    return f"{IMG_PROXY}?emby={quote(text, safe='')}&type={quote(img_type, safe='')}"


def _meta_of(store: Any, key: str) -> Optional[Dict[str, Any]]:
    """读一行 meta（store 不可用/抛异常一律回 None，读侧不许把界面带崩）。"""
    if store is None or not key:
        return None
    getter = getattr(store, "meta_get", None)
    if not callable(getter):
        return None
    try:
        row = getter(key)
    except Exception as error:                                  # pragma: no cover - 防御
        logger.warning(f"AVHelper meta_get({key}) 失败：{error}")
        return None
    return row if isinstance(row, dict) else None


def _items_of(store: Any, key: str) -> List[Dict[str, Any]]:
    """读该作品的全部媒体实例（`media_item` 行）。"""
    if store is None or not key:
        return []
    lister = getattr(store, "item_list", None)
    if not callable(lister):
        return []
    try:
        rows = lister(key=key) or []
    except TypeError:                                           # pragma: no cover - 兼容
        rows = []
    except Exception as error:                                  # pragma: no cover - 防御
        logger.warning(f"AVHelper item_list({key}) 失败：{error}")
        return []
    return [row for row in rows if isinstance(row, dict)]


# 下载台账主键是**旧口径**（`norm_key()` 保留版本后缀：`IPZZ-912-UC` → `IPZZ912UC`），
# 而 v4 新层用干净号（`canon_key()` → `IPZZ912`）。同一部片因此可能对不上，需要一个
# 「干净号 + 版本后缀」的兜底匹配；后缀形态限定成字母开头（`UC`/`C`/`L`/`4K`…），
# **不允许纯数字尾巴** —— 否则 `IPZZ9` 会误吃 `IPZZ91`（两部不同的片）。
_DL_SUFFIX_TAIL = re.compile(r"^[A-Z]{1,4}\d{0,3}$")


def download_row(rows: Any, key: str) -> Optional[Dict[str, Any]]:
    """在下载台账里找这部片的行（旧口径键 + 版本后缀歧义都能对上）。

    依次试：① 干净号精确命中；② 旧口径 `norm_key(key)`；③ 台账里 `key` + 版本后缀的行
    （`IPZZ912UC` 对 `IPZZ912`）。都不中就回 `None` —— 宁可显示"没下载过"，
    也不要把别的片子的下载状态张冠李戴。
    """
    if not isinstance(rows, dict) or not key:
        return None
    for candidate in dict.fromkeys([key, emby.norm_key(key)]):
        row = rows.get(candidate)
        if isinstance(row, dict):
            return row
    prefix = str(key or "").upper()
    for row_key, row in rows.items():
        text = str(row_key or "").upper()
        if text.startswith(prefix) and _DL_SUFFIX_TAIL.match(text[len(prefix):]):
            return row if isinstance(row, dict) else None
    return None


def _download_state(store: Any, key: str) -> str:
    """下载状态：只认**插件自己下的**（`plugin`/`queue`），`library` 那批补种行不算。"""
    if store is None or not key:
        return "none"
    mapper = getattr(store, "download_map", None)
    if not callable(mapper):
        return "none"
    try:
        rows = mapper(list(DOWNLOAD_SOURCES)) or {}
    except Exception as error:                                  # pragma: no cover - 防御
        logger.warning(f"AVHelper download_map 失败：{error}")
        return "none"
    row = download_row(rows, key)
    return str((row or {}).get("state") or "none")


def _pick_representative(items: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """多实例时挑「代表实例」（契约 §4：优先 `emby:*` 且 `library_state=in_library`，
    其次 `scraped_full`）。"""
    rows = [row for row in items if isinstance(row, dict)]
    if not rows:
        return None
    def rank(row: Dict[str, Any]) -> Tuple[int, int, str]:
        emby = 1 if str(row.get("item_key") or "").startswith("emby:") else 0
        lib = 1 if str(row.get("library_state") or "") == "in_library" else 0
        full = 1 if str(row.get("scrape_state") or "") == "scraped_full" else 0
        return (-(emby and lib), -full, str(row.get("item_key") or ""))
    return sorted(rows, key=rank)[0]


def _item_view(row: Optional[Dict[str, Any]], library: Any, key: str) -> Dict[str, Any]:
    """一条 `media_item` → `{item_key, emby_id, library_state, scrape_state, download_state}`。"""
    data = row if isinstance(row, dict) else {}
    emby_id = str(data.get("emby_id") or "").strip()
    library_state = str(data.get("library_state") or "")
    if not library_state or library_state == "not_in_library":
        if emby_id:
            library_state = "in_library"
        elif library is not None and hasattr(library, "lookup"):
            try:
                hit = library.lookup(key)
            except Exception:                                   # pragma: no cover - 防御
                hit = None
            if isinstance(hit, dict) and str(hit.get("id") or ""):
                library_state = "in_library"
                emby_id = emby_id or str(hit.get("id") or "")
    return {
        "item_key": str(data.get("item_key") or (f"emby:{emby_id}" if emby_id else "")),
        "emby_id": emby_id,
        "library_state": library_state or "not_in_library",
        "scrape_state": str(data.get("scrape_state") or "unscraped"),
        "download_state": str(data.get("download_state") or "none"),
        "crop_anchor": str(data.get("crop_anchor") or ""),
        "file_path": str(data.get("file_path") or ""),
        "last_synced_at": str(data.get("last_synced_at") or ""),
    }


def film_view(key_or_number: Any, item_key: Any = None, store: Any = None,
              library: Any = None) -> Dict[str, Any]:
    """**唯一读投影**（契约 §4）：`meta` + `media_item` + 下载台账 + `name_map` → 界面形状。

    **零抓取**：全程只读本地 SQLite 与调用方给的内存索引（`library` 已建好就直接用；
    没给就不碰它 —— 读接口绝不主动触发一次全库抓取）。

    签名说明：契约 §3.6 写的是 `film_view(key_or_number, item_key=None)`，但那个形状**没有
    拿数据的地方**；本实现按 S7 任务书给的
    `film_view(key_or_number, item_key=None, store=None, library=None)`（多出的两个是关键字参数，
    位置调用 `film_view(key)` 的行为不变）。缺 `store` 时降级成"只有键与番号"的最小视图。
    """
    resolved = resolve_key(key_or_number, str(item_key or ""))
    key = resolved.get("key") or ""
    number = resolved.get("display_number") or resolved.get("number") or resolved.get("input") or ""
    if not key and number:
        key = emby.canon_key(number)
    meta = _meta_of(store, key)
    items = _items_of(store, key)
    views = [_item_view(row, library, key) for row in items]
    picked = _pick_representative(items)
    picked_view = _item_view(picked, library, key) if picked else _item_view(
        {"item_key": str(item_key or resolved.get("item_key") or "")}, library, key)

    title_zh = str((meta or {}).get("title_zh") or "")
    title_jp = str((meta or {}).get("title_jp") or "")
    raw = (meta or {}).get("raw") if isinstance((meta or {}).get("raw"), dict) else {}
    version_tags = dict((raw.get("extra") or {}).get("version_tags") or {}) if raw else {}
    if not version_tags:
        version_tags = dict(resolved.get("version_tags") or {})
    if not version_tags and picked_view.get("item_key"):
        for row in items:
            if str(row.get("item_key")) == picked_view["item_key"]:
                tags = row.get("version_tags")
                if isinstance(tags, dict):
                    version_tags = dict(tags)
    labels = version_labels(version_tags)

    actors: List[Dict[str, Any]] = []
    for actor in ((meta or {}).get("actors") or []):
        if not isinstance(actor, dict):
            continue
        raw_name = _clean_text(actor.get("jp")) or _clean_text(actor.get("name"))
        stored_name = _actor_stored_name(actor)
        display = actor_display(raw_name or stored_name)
        avatar = _actor_avatar(actor)
        actors.append({
            # `name` 用**存进 meta 的那个规范名**（与 Emby `People[].Name` 逐字一致），
            # `namemap` 在线时再补 zh/jp；没映射时 `display` 只会把原名回传。
            "name": stored_name or display.get("name") or raw_name,
            "jp": display.get("jp") or raw_name,
            "zh": display.get("zh") or _clean_text(actor.get("zh")),
            "alias": display.get("alias") or "",
            "id": str(actor.get("javdb_actor_id") or actor.get("id") or ""),
            "avatar": img_url(avatar),
            "avatar_raw": avatar,
        })

    cover_raw = str((meta or {}).get("cover_raw_url") or "")
    emby_id = picked_view.get("emby_id") or resolved.get("emby_id") or ""
    cover = emby_img_url(emby_id) if emby_id else img_url(cover_raw)
    samples = [img_url(u) for u in ((meta or {}).get("samples") or []) if str(u or "").strip()]
    download_state = _download_state(store, key) if key else "none"
    if download_state == "none" and picked_view.get("download_state") not in ("", "none"):
        download_state = str(picked_view["download_state"])

    return {
        "key": key,
        "number": number or str((meta or {}).get("display_number") or ""),
        "title": title_zh or title_jp,
        "original_title": title_jp or str((meta or {}).get("display_number") or ""),
        "plot": str((meta or {}).get("plot_zh") or ""),
        "plot_jp": str((meta or {}).get("plot_jp") or ""),
        "plot_source": str((raw.get("extra") or {}).get("plot_source") or "") if raw else "",
        "actors": actors,
        "cover": cover,
        "cover_raw": cover_raw,
        "samples": samples,
        "crop_anchor": str((meta or {}).get("crop_anchor") or picked_view.get("crop_anchor")
                           or "auto"),
        "version_tags": labels,
        "badge": "/".join(labels),
        "states": {
            "download": download_state,
            "library": picked_view.get("library_state") or "not_in_library",
            "scrape": picked_view.get("scrape_state") or "unscraped",
        },
        "emby_id": emby_id,
        "item_key": picked_view.get("item_key") or "",
        "updated_at": str((meta or {}).get("updated_at") or ""),
        "last_scraped_at": str((meta or {}).get("last_scraped_at") or ""),
        "next_retry_at": str((meta or {}).get("next_retry_at") or ""),
        "completeness": str((meta or {}).get("completeness") or "unscraped"),
        "translation_status": str((meta or {}).get("translation_status") or "untranslated"),
        "display_number": str((meta or {}).get("display_number") or number),
        "tags": list((meta or {}).get("tags") or []),
        "studio": str((meta or {}).get("studio") or ""),
        "series": str((meta or {}).get("series") or ""),
        "director": str((meta or {}).get("director") or ""),
        "release_date": str((meta or {}).get("release_date") or ""),
        "runtime_min": _to_int((meta or {}).get("runtime_min")),
        "rating": _to_float((meta or {}).get("rating")),
        "items": [dict(v, states={"library": v.get("library_state") or "not_in_library",
                                  "scrape": v.get("scrape_state") or "unscraped",
                                  "download": v.get("download_state") or "none"})
                  for v in views],
        "scraped": bool(meta and str(meta.get("last_scraped_at") or "")),
    }


# 兼容别名：老调用方（以及 S8 早期草稿）用过 `film_view_of` 这个名字
film_view_of = film_view
