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
  一律由调用方传进来，**本模块不读插件配置**：代理 / 裁切锚点 / 开关全部经
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
import random
import re
import subprocess
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote, urlencode, urlparse

from app.sdk.logging import logger

from . import emby
from . import number_classify
from . import ratelimit
from . import scrape_graph

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
SRC_LLM = "llm"
SRC_EMBY_WRITE = "emby_write"
SRC_IMAGE = "javdb_assets"

# javtxt 主站与备用镜像（契约 §4.2：内容同源，`javtxt.me` 会 429，不要加）
JAVTXT_HOSTS: Tuple[str, ...] = ("https://javtxt.com", "https://javtxt.net", "https://javtxt.org")
# 单站点请求间隔（契约 §4.2 硬要求 ≥2s）。搜索要试多个变体，不节流会打爆站点。
JAVTXT_MIN_INTERVAL = 2.0
# javtxt 的重试次数（0.8.0 加）：只对 `RETRYABLE_STATUS` + 超时/连接类异常生效，
# 403（被拦）/ 404（地址没了）**不重试**。退避 2±1 秒起，不比 `JAVTXT_MIN_INTERVAL` 更密。
JAVTXT_RETRIES = 2

# 退避序列（契约 §5.3 / v4.1 §5.3）：6h → 24h → 72h → 7d → 14d
BACKOFF_HOURS: Tuple[int, ...] = (6, 24, 72, 168, 336)
# Tier1 只处理「缺简介」；`missing_core` 不算退避（等下次手动/定时）。
TIER1_COMPLETENESS = "missing_plot"

# `meta.raw_json` 总体积上限（v4.1 §5.2：剔掉磁力数组与评论，控制体积 ≤5KB）
RAW_JSON_LIMIT = 5120
# 单帧原始 javdb 详情在 raw_json 里的上限（给 javtxt 留出余量）
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
    "javtxt_hosts": JAVTXT_HOSTS,
    "crop_anchor": "auto",           # auto / left / center / right / raw
    "write_images": True,            # 封面 + 剧照
    "write_samples": True,
    "translate": True,               # 允许调 translator（模块缺失时自动降级）
    "allow_machine": False,          # 「允许机翻兜底」开关（默认关，契约 D6）
    "plot_sources": ("javtxt",),
    "force": False,                  # True = 无视已有 raw_json['javdb']，重抓骨架
    "javdb_assets": True,            # 是否调 `assets list/download`
    "log_sources": True,             # 是否把数据源结果写 scrape_log（film_view 不涉及）
    "fetch_cache": None,             # S11 抓取缓存（dict 或 coverage.json 路径）；命中则 0 站点请求
    "cache_only": False,             # True = 缓存的"没有"也是权威结论（dry-run 用，绝不回落真站点）
    "min_plot_zh": MIN_PLOT_ZH,      # 中文简介短于它就当站点占位符（同时有日文时才判无效）
    "javtxt_interval": JAVTXT_MIN_INTERVAL,
    "http_timeout": 30,
    "javdb_timeout": 60,
    "now": "",                       # 便于单测固定时间戳（ISO 字符串）
}

# 写入矩阵里要参与 diff 的字段（`preview_one` 的 `fields[]` 顺序即此）
MATRIX_FIELDS: Tuple[str, ...] = (
    "Name", "OriginalTitle", "Overview", "PremiereDate", "ProductionYear",
    "Studios", "SeriesName", "GenreItems", "CommunityRating", "People", "ProviderIds",
)


def _now(opts: Optional[Dict[str, Any]] = None) -> str:
    """当前时间（UTC 秒级，**与 `store._now()` 逐字同形**：空格分隔、不带时区）；`opts['now']` 可覆盖（单测用）。

    为什么必须是空格分隔：`store.meta_due()` 拿库里的时间戳跟这个串做**字典序比较**，而
    `'T'(0x54) > ' '(0x20)` —— 写成 `2026-10-21T03:00:00` 会让同一天到点的行被判成
    「还没到」，Tier1 退避要等日期翻页才生效（0.8.x 的真 bug，0.9.0 修）。
    """
    fixed = str((opts or {}).get("now") or "").strip()
    if fixed:
        return fixed
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


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
    # 入参两种写法都吃：库里的存量行可能是老的 `T` 分隔（v3 迁移会统一改写），
    # 而 `fromisoformat` 在 3.11 以前只认 `T` —— 先归一成空格再解析，两头都不挑。
    stamp = stamp.replace("T", " ")
    try:
        base = datetime.fromisoformat(stamp)
    except ValueError:                                          # pragma: no cover - 防御
        base = datetime.now(timezone.utc).replace(tzinfo=None)
    due = base + timedelta(hours=BACKOFF_HOURS[count - 1])
    # 输出**空格分隔**：`store.meta_due()` 拿它跟 `"%Y-%m-%d %H:%M:%S"` 做字典序比较，
    # 写成 `T` 分隔会让同一天到点的行永远「还没到」（见 `_now()` 的说明）。
    return count, due.strftime("%Y-%m-%d %H:%M:%S")


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


def launch_number(resolved: Optional[Dict[str, Any]] = None, key: str = "",
                  store: Any = None, library: Any = None,
                  fallback: Any = "") -> str:
    """**抓取侧拿去查站点的番号**（R10）：Emby 条目名派生的补零形态优先。

    这条链的终点是 `cli.detail(number)` —— javdb 的番号**错一位就是整条片子查不到**
    （去零形态 `CAWB-40` / `IPOK-25` 站点回「找不到番号」，补零形态 `CAWB-040` /
    `IPOK-025` 返回完整详情，2026-10-14 真机实测）。

    优先级（**从"库里的真相"往"从键反推"退**）：

    1. `emby.shown_number(key, library.index()[key]['name'])` —— Emby 条目 `Name` 开头那段
       原始番号（MetaTube 刮削写进去的，**最权威**，也是 `/library` 卡片上那个写法的来源）。
       零网络：读的是 `EmbyLibrary.index()` 那份内存缓存（`locate_instances()` 定位实例时
       本来就会建它）；
    2. `store.meta_get(key)['display_number']` —— `tasks._seed_library_meta()` 播种时写的
       就是 `emby.shown_number(键, Emby 条目 Name)`，**同一份真相的耐久副本**（Emby 索引
       不可用时靠它）。排在 Name 之后：条目名是新鲜的，meta 行可能是旧口径留下的
       （`CAWB-40` —— 正是 R10 要修掉的那个形态）；
    3. 调用方给的 `fallback`（通常是 `resolve_key()['display_number']`，即
       `site_number()` 的 parse 优先产物）；
    4. `emby.display_number(key)` 旧口径兜底（例如 `MIRD277C` → `MIRD-277`）。

    1/2 两级都只认**归一化后与 `key` 相等、且不等于键本身**的写法（与 `shown_number()`
    同一条纪律：对不上宁可按老规则，否则会把 B 片的号写到 A 片上）。第 4 级是最后的
    形态兜底 —— 键本来就推不出展示番号（`SNOS192C`）时，至少保持旧行为不变。

    为什么需要它（R10 的分歧点）：`resolve_key()` 只能从**键**反推，
    `site_number()` 认不出番号时会落到 `emby.display_number()` —— 那是旧口径
    （`^([A-Z]{2,6})(\\d{2,7})$` 直接拼、**不补三位零**），于是 `CAWB040` → `CAWB-40`。
    库里的展示番号（`/library` 的 `number`）一直是对的（`library_rows()` 走 `shown_number()`），
    分歧只发生在"展示番号 → 查询番号"这一段。这里把库里的真相接回来。

    `store` / `library` 不可用（未配置 Emby、索引还没建）时逐级回退，**绝不抛异常**：
    取数链不能因为查不到展示番号就整条停摆。
    """
    resolved = resolved if isinstance(resolved, dict) else {}
    key_text = str(key or resolved.get("key") or "").strip()

    def usable(candidate: Any, allow_identity: bool = False) -> str:
        """这一级能不能用：非空 + 归一化后与 `key` 相等（+ 默认**不等于键本身**）。

        `allow_identity=False` 是为了识别"Name 没给出番号"：`emby.shown_number()` 在认不出
        时会**原样回传键**（`MIRD277C`）——那不是 Emby 的权威写法，不能因为它挡住后面的
        meta 行。第 3 级（parse 产物，旧行为就是拿它）允许原样回传，见下。
        """
        text = _clean_text(candidate)
        if not text:
            return ""
        if key_text:
            if emby.norm_key(text) != key_text:
                return ""
            if not allow_identity and text.upper() == key_text.upper():
                return ""
        return text

    if key_text and library is not None:
        index = None
        getter = getattr(library, "index", None)
        if callable(getter):
            try:
                index = getter() or {}
            except Exception as error:                          # noqa: BLE001 - 读侧兜底
                logger.warning(f"AVHelper 读 Emby 索引失败（展示番号按旧口径）：{error}")
                index = {}
        entry = index.get(key_text) if isinstance(index, dict) else None
        if isinstance(entry, dict):
            picked = usable(emby.shown_number(key_text, entry.get("name")))
            if picked:
                return picked
    row = _meta_of(store, key_text)
    if isinstance(row, dict):
        picked = usable(row.get("display_number"))
        if picked:
            return picked
    # 第 3 级 = `resolve_key()` 的产物（`site_number()` 的 parse 优先口径）。旧行为就是
    # 拿它去查站点，所以这里允许"原样回传键"（`SNOS192C` 这种推不出展示番号的键）。
    picked = usable(resolved.get("display_number"), True) or usable(resolved.get("number"), True)
    if picked:
        return picked
    if fallback:
        picked = usable(fallback) or _clean_text(fallback)
        if picked:
            return picked
    return emby.display_number(key_text) or str(fallback or "")


def _fallback_number(resolved: Dict[str, Any], options: Dict[str, Any],
                     found: Sequence[Dict[str, Any]], dto: Any) -> str:
    """`launch_number()` 的第三级兜底：键反推不出来时，从缓存行 / 盘上路径 / 输入原样取。

    ★ `cache_only` 的那条路要用**缓存行的 `display`**（S11 的 `coverage.json` 是"当时站点
    认得的写法"），所以它必须排在 `number_from_dto()` **之前**（旧行为如此，别调换）。
    """
    row = cache_row(options.get("fetch_cache"), resolved.get("key") or "")
    if _clean_text(row.get("display")):
        return _clean_text(row.get("display"))
    number = number_from_dto(dto)
    for entry in found:
        if number:
            break
        number = str(entry.get("number") or "")
    return number or str(resolved.get("input") or "")


# ---------------------------------------------------------------------------
# 失败原因（封闭枚举）与拦截判定
#
# 分工：`status` 说"成没成"，`reason` 说"为什么"。只靠 status 分不清「站点没收录这部片」
# 与「被 CF / 年龄墙拦了」，而这两件事的处置**相反** —— 前者换源，后者冷却 + 换 UA。
# 枚举照 amane `net/errors.py:37-63` 裁剪到我们真正会产出的取值；**只加不改**。
# ---------------------------------------------------------------------------

REASON_NOT_FOUND = "not_found"                  # HTTP 404：地址没了 / 番号不存在
REASON_RATE_LIMITED = "rate_limited"            # 429
REASON_SERVER_ERROR = "server_error"            # 5xx
REASON_HTTP_ERROR = "http_error"                # 其余 4xx
REASON_TIMEOUT = "timeout"                      # 连上了但没在超时内回话
REASON_NETWORK = "network"                      # 连不上 / DNS / TLS / 代理
REASON_EMPTY = "empty_response"                 # 200 但正文是空的
REASON_LOGIN_REQUIRED = "login_required"        # 站点要求登录 / 登录态过期（0.8.1）
REASON_CF_CHALLENGE = "cloudflare_challenge"    # "Just a moment" 挑战页
REASON_CF_BLOCKED = "cloudflare_blocked"        # Ray ID 拦截页（无挑战）
REASON_IP_BANNED = "ip_banned"
REASON_GEO = "geo_restricted"
REASON_AGE = "age_verification"                 # 年龄墙
REASON_NO_USABLE = "no_usable_metadata"         # 请求成功、页面干净，但没有可用内容
REASON_PARSE = "parse_error"                    # 响应与我们的读模型不符 = 站点可能改版
REASON_UNEXPECTED = "unexpected"

#: 全部合法取值（`scrape_log.reason` 的取值域；界面按它分组）
REASONS = frozenset({
    REASON_NOT_FOUND, REASON_RATE_LIMITED, REASON_SERVER_ERROR, REASON_HTTP_ERROR,
    REASON_TIMEOUT, REASON_NETWORK, REASON_EMPTY, REASON_CF_CHALLENGE, REASON_CF_BLOCKED,
    REASON_IP_BANNED, REASON_GEO, REASON_AGE, REASON_NO_USABLE, REASON_PARSE,
    REASON_LOGIN_REQUIRED, REASON_UNEXPECTED,
})

#: 强特征：**HTTP 200 也认** —— 挑战页/封锁页本来就是 200 回来的，
#: 而正常页里不会出现这些串。
_BLOCK_STRONG: Tuple[Tuple[str, str], ...] = (
    ("not available in your region", REASON_GEO),
    ("お住まいの地域からはご利用になれません", REASON_GEO),
    ("banned your access", REASON_IP_BANNED),
    # `_cf_chl_opt` 只在挑战页出现；`challenge-platform` 在正常页也加载，**不能**当判据。
    ("_cf_chl_opt", REASON_CF_CHALLENGE),
)
#: 弱特征：**只在失败响应上认**。实测踩过：维基演员页的引用里带「年齢認証」，
#: 拿它判 200 会把正常页误判成年龄墙。
_BLOCK_WEAK: Tuple[Tuple[str, str], ...] = (
    ("driver-verify", REASON_AGE),
    ("年齢認証", REASON_AGE),
    ("age verification", REASON_AGE),
)


def classify_block(text: Any = "", status: Optional[int] = None) -> str:
    """这次失败/拦截到底是什么 —— 回 `REASON_*` 之一，**没发现问题时空串**。

    顺序（照 amane `net/errors.py:120-156`，是精华，别重排）：

    1. 正文强特征：地域封锁 / IP 封禁 / CF 挑战页；
    2. CF 封禁页（`ray-id` + `cf-`）—— **必须在挑战页之后判**：挑战页同样带 ray-id；
    3. 正文弱特征（年龄墙）—— 只在 `status` 缺失或 ≥400 时认（见 `_BLOCK_WEAK`）；
    4. 状态码兜底：429 / 5xx / 404 / 其余 4xx；
    5. 正文为空 → `empty_response`。
    """
    lower = str(text or "").lower()
    if lower:
        for marker, reason in _BLOCK_STRONG:
            if marker in lower:
                return reason
        if "just a moment" in lower and "cloudflare" in lower:
            return REASON_CF_CHALLENGE
        if "ray-id" in lower and "cf-" in lower:
            return REASON_CF_BLOCKED
        if status is None or _to_int(status) >= 400:
            for marker, reason in _BLOCK_WEAK:
                if marker in lower:
                    return reason
    code = _to_int(status)
    if code == 404:
        return REASON_NOT_FOUND
    if code == 429:
        return REASON_RATE_LIMITED
    if 500 <= code < 600:
        return REASON_SERVER_ERROR
    if 400 <= code < 500:
        return REASON_HTTP_ERROR
    if not lower:
        return REASON_EMPTY
    return ""


def reason_from_text(text: Any, default: str = "") -> str:
    """从**自由文本**里猜一个机器原因（兜底用）。

    只在拿不到结构化信号的地方用（javdb 走子进程，只有一句中文说明）。猜不出给 `default`。
    规则按"先具体后笼统"排；**别加宽泛的关键词**（`error` / `fail` 这类），
    否则"站点收录缺口"又会被猜成"请求失败"。
    """
    low = str(text or "").lower()
    if not low:
        return default
    if "timeout" in low or "timed out" in low or "超时" in low:
        return REASON_TIMEOUT
    if "频繁" in low or "too many" in low or "rate limit" in low:
        return REASON_RATE_LIMITED
    if "冷却" in low or "cool" in low:
        return REASON_RATE_LIMITED
    found = re.search(r"\b([45]\d{2})\b", low)
    if found:
        return classify_block("", _to_int(found.group(1))) or default
    # 登录态问题要单独成一类：javdb 走子进程、只有一句中文说明，以前会被兜成
    # `unexpected`（界面显示"未知错误"），用户根本看不出该去更新 cookie。
    if ("未登录" in low or "需要登录" in low or "请先登录" in low or "登录已过期" in low
            or "login required" in low or "not logged in" in low or "sign in" in low):
        return REASON_LOGIN_REQUIRED
    if "未找到" in low or "不存在" in low or "not found" in low:
        return REASON_NOT_FOUND
    return default


# ---------------------------------------------------------------------------
# HTTP（javtxt）：一律走调用方给的代理，失败不抛异常
# ---------------------------------------------------------------------------

#: 出站 UA。**全插件唯一一份**（0.8.0 之前 scraper / sitesearch / imgproxy 各写一份，
#: 同一个进程对外有三个身份）。版本号只是装饰，发版时一并改即可。
UA_DEFAULT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AVHelper/0.7"
UA_HEADERS: Dict[str, str] = {
    "User-Agent": UA_DEFAULT,
    "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
}

#: 失败正文只留 64 KB：拦截页（CF 挑战 / 年龄墙）**只有正文能认出来**，
#: 而完整正文动辄几百 KB，没必要为了判定留全份。
FAILURE_BODY_LIMIT = 65536
#: 常规取数的重试次数（总尝试 = 1 + 本值）
HTTP_RETRIES = 2
#: 可重试的状态码：只有这四条（+超时/连接类异常）。
#: **403 / 404 不重试** —— 403 是"被拦"（重试只会更冷）、404 是"没有"（重试是白等）。
RETRYABLE_STATUS = frozenset({408, 429, 503, 504})
#: `time.sleep` 的间接引用：**所有等待都走它**（重试退避 + 站点节流）。
#: 单测把它换成不睡的假函数 —— 否则"失败 + 重试"的用例要真等 2±1、5±1 秒，
#: 一轮全量测试会被拖到几分钟（实测 40 秒 → 4 分钟）。
_SLEEP = time.sleep


def urlparse_host(url: Any) -> str:
    """从 URL 里取 host（被拦后的冷却按 host 记，轮换域名也绕不过）；解析不出来回空串。"""
    try:
        return str(urlparse(str(url or "")).hostname or "")
    except Exception:                                          # pragma: no cover - 防御
        return ""


def _proxy_opener(proxy: str) -> Any:
    """按代理串建一个 urllib opener（空串 = 直连，不设任何 handler）。"""
    import urllib.request

    text = str(proxy or "").strip()
    if text:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": text, "https": text})
        )
    return urllib.request.build_opener()


@dataclass
class FetchResult:
    """一次出站请求的结构化结果。`body is None` 即失败，`reason` 说明为什么。

    `kind` 是传输层分类（`http_status` / `timeout` / `network`），`reason` 是业务分类
    （`REASON_*`，含拦截判定）—— 两者分开，是为了让"要不要重试"（看 kind 与 status）
    与"要不要冷却/换源"（看 reason）各用各的判据。
    """

    url: str = ""
    status: Optional[int] = None
    body: Optional[bytes] = None
    error: str = ""
    kind: str = ""
    reason: str = ""
    attempts: int = 1

    @property
    def ok(self) -> bool:
        return self.body is not None


def _backoff_wait(retry_index: int) -> float:
    """第 `retry_index` 次重试前的等待秒数（**从 0 数**）：`retry_index*3 + 2 ± 1`（2±1、5±1）。

    带 jitter 是**必须的**：多源同时失败时，固定退避会让它们在同一秒一起重发。
    """
    return max(0.0, float(retry_index) * 3 + 2 + random.uniform(-1, 1))


def _classify_transport(error: BaseException) -> str:
    """异常 → `REASON_TIMEOUT` / `REASON_NETWORK`（超时与"连不上"分开：前者值得重试与放宽
    超时，后者多半是代理/DNS 问题）。"""
    text = f"{type(error).__name__}: {error}".lower()
    if isinstance(error, TimeoutError) or "timed out" in text or "timeout" in text:
        return REASON_TIMEOUT
    return REASON_NETWORK


def _http_once(url: str, *, proxy: str = "", timeout: int = 30,
               headers: Optional[Dict[str, str]] = None,
               body_limit: int = FAILURE_BODY_LIMIT, attempts: int = 1) -> FetchResult:
    """发一次请求，**任何异常都吞掉**（失败回结构化结果）。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={**UA_HEADERS, **(headers or {})})
    try:
        with _proxy_opener(proxy).open(req, timeout=max(1, _to_int(timeout) or 30)) as res:
            blob = res.read()
            code = _to_int(getattr(res, "status", 200)) or 200
            reason = classify_block(blob[:body_limit].decode("utf-8", "replace"), code)
            return FetchResult(url=url, status=code, body=blob, kind="http_status",
                               reason=reason, attempts=attempts)
    except urllib.error.HTTPError as error:
        # ★ 失败正文必须留档：`HTTPError.read()` 能拿到拦截页正文，
        #   老实现直接丢掉，于是"被 CF 拦"与"404"只能靠状态码猜。
        blob = b""
        try:
            blob = error.read(body_limit) or b""
        except Exception:                                       # pragma: no cover - 防御
            blob = b""
        code = _to_int(error.code)
        reason = classify_block(blob.decode("utf-8", "replace"), code)
        return FetchResult(url=url, status=code, body=None, error=f"HTTP {code}",
                           kind="http_status", reason=reason, attempts=attempts)
    except Exception as error:                                  # noqa: BLE001 - 故意的
        reason = _classify_transport(error)
        return FetchResult(url=url, status=None, body=None,
                           error=f"{type(error).__name__}: {error}",
                           kind=reason, reason=reason, attempts=attempts)


def http_fetch(url: str, *, proxy: str = "", timeout: int = 30,
               headers: Optional[Dict[str, str]] = None, retries: int = HTTP_RETRIES,
               body_limit: int = FAILURE_BODY_LIMIT, sleeper: Any = None) -> FetchResult:
    """**唯一出站函数**：一次 GET（含重试），失败回结构化结果，**不抛异常**。

    - 重试只针对 `RETRYABLE_STATUS` + 超时 + 连接类异常；退避 `attempt*3+2±1`。
    - 重试之间**不绕过站点节流**：退避最小 1 秒、`javtxt_interval` 默认 2 秒，
      同一 host 的重试不会比正常请求更密（`scraper.throttle()` 仍在每次尝试前调用）。
    - `sleeper` 可注入（单测传 `lambda _s: None`，不真睡）。
    """
    tries = max(1, _to_int(retries) + 1)
    sleep = sleeper or _SLEEP
    last = FetchResult(url=url, kind=REASON_NETWORK, reason=REASON_NETWORK)
    for index in range(tries):
        if index:
            sleep(_backoff_wait(index - 1))
        last = _http_once(url, proxy=proxy, timeout=timeout, headers=headers,
                          body_limit=body_limit, attempts=index + 1)
        if last.ok:
            return last
        retryable = (last.status in RETRYABLE_STATUS
                     or last.kind in (REASON_TIMEOUT, REASON_NETWORK))
        if not retryable or index == tries - 1:
            return last
    return last


def http_get(url: str, *, proxy: str = "", timeout: int = 30,
             headers: Optional[Dict[str, str]] = None, retries: int = 0,
             sleeper: Any = None) -> Tuple[Optional[bytes], str, int]:
    """`http_fetch` 的**兼容外壳**：旧的三元组返回，默认**不重试**（retries=0）。

    保留它是因为调用点与单测都按 `(body, error, status)` 写；新代码一律用 `http_fetch()`
    （要多一份 `kind` / `reason` / `attempts`，并且要重试）。
    """
    got = http_fetch(url, proxy=proxy, timeout=timeout, headers=headers,
                     retries=retries, sleeper=sleeper)
    return got.body, got.error, got.status


# 站点节流（同一站点两次请求之间的最小间隔；跨线程也要守住）
#
# P1-2（0.8.0）：**执行点搬到 `ratelimit.RateLimiter.wait_host()`** —— 元数据取数与 PT 站点搜索
# 共用同一个限流器实例（插件 `init_plugin` 时 `set_limiter()` 注入），
# 这里只留一个薄封装，签名不变（调用点与老单测都按 `throttle(host, interval)` 写）。
_LIMITER: Any = None


def set_limiter(limiter: Any) -> None:
    """注入限流器（插件 `init_plugin` 调用；不注入时用一个不带 store 的默认实例）。

    不注入也能跑：默认实例是**进程内内存态**（单测、启动早期、独立脚本都要能用）。
    """
    global _LIMITER
    _LIMITER = limiter


def limiter() -> ratelimit.RateLimiter:
    """取当前限流器（没有就现造一个内存态的）。

    ⚠️ 默认实例的 `sleep` 走 `_SLEEP`（而不是直接 `time.sleep`）：单测把它换成空实现，
    否则每一个"调 javtxt"的用例都要真等 2 秒（`ratelimit` 自己的默认睡在它模块内，
    这里必须显式接上注入点）。
    """
    global _LIMITER
    if _LIMITER is None:
        _LIMITER = ratelimit.RateLimiter(None, sleep=_sleep_now)
    return _LIMITER


def _sleep_now(seconds: float) -> None:
    """`_SLEEP` 的**延迟读取**包装：单测改了 `scraper._SLEEP` 之后，已经建好的限流器也跟着变。"""
    _SLEEP(seconds)


def throttle(host: str, interval: float) -> float:
    """把「对 `host` 的下一次请求」推迟到距上次 ≥`interval` 秒；返回实际等待秒数。

    等待走 `_SLEEP`（在限流器里注入），单测里被换成空实现。
    """
    return limiter().wait_host(host, interval=interval)


def host_cooling(host: str) -> float:
    """该 host 还剩多少秒冷却（被拦后 `ratelimit.BLOCK_COOLDOWN_HOURS` 小时）。"""
    return limiter().cooling(host)


#: 视为"被拦"的原因（命中后按 host 冷却，下次不再打这个镜像）
BLOCK_REASONS: FrozenSet[str] = frozenset({
    REASON_CF_CHALLENGE, REASON_CF_BLOCKED, REASON_AGE, REASON_IP_BANNED,
    REASON_GEO, REASON_RATE_LIMITED,
})


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
    那是站点收录缺口，试完所有变体仍为空就**如实返回空**，不许猜条。
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
                  key: str = "", run_id: str = "") -> Dict[str, Any]:
    """Javtxt 一键取数：搜索（多变体 + 强校验）→ 详情页解析。

    返回 `{ok, status, vid, url, title_zh, title_jp, plot_zh, plot_jp, zh_is_machine, actors,
    latency_ms, error, reason, http_status, tried[]}`；`status` ∈ `ok` / `miss` / `error`。

    **`miss` 与 `error` 的边界（0.8.0 修的那个最贵的 bug）**：
    `miss` 只表示"我们真的读到了一张干净页面，站点就是没收录这个番号"；
    只要没有任何一次尝试拿到干净页面（全是 429/5xx/超时/拦截页），就落 `error` +
    `reason`（`REASON_*`）。老实现把两者都写成 `miss`，于是**被 CF 拦会被记成"站点收录缺口"**，
    重试与换源策略全部做错。

    请求一律走 `opts['proxy']`，**每个站点请求之间 ≥`opts['javtxt_interval']`（默认 2s）**，
    `http_fetch` 的重试退避（2±1 秒起）也不比它密；失败不抛异常（只回 error 文案并写 `scrape_log`）。
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
        "reason": "", "http_status": 0, "latency_ms": 0,
    }
    target = emby.parse_av_number(number)
    target_norm = target.norm_key if target.matched else emby.canon_key(number)
    # 被拦过（CF/年龄墙/429）的镜像先别打 —— 冷却按 **host** 记，轮换域名也绕不过
    lim = limiter()
    cooled = [h for h in hosts if lim.cooling(h) > 0]
    if hosts and len(cooled) == len(hosts):
        wait_min = int(max(lim.cooling(h) for h in cooled) / 60) + 1
        result.update({"status": "skipped", "reason": "", "latency_ms": 0,
                       "error": f"镜像都在冷却中（约 {wait_min} 分钟后重试）"})
        _log_source(store, SRC_JAVTXT, "skipped", key or number, 0, result["error"],
                    reason=lim.blocked_reason(cooled[0]), run_id=run_id)
        return result
    if cooled:
        hosts = [h for h in hosts if h not in cooled]
    # 只要有任何一次拿到"干净页面"（HTTP 成功且不是拦截页），"没有结果"就是真·收录缺口
    clean_seen = False
    detail_failed = False

    for variant in javtxt_variants(number):
        for host in hosts:
            throttle(host, interval)
            url = f"{host}/search?{urlencode({'type': 'id', 'q': variant})}"
            got = http_fetch(url, proxy=proxy, timeout=timeout, retries=JAVTXT_RETRIES)
            result["tried"].append({"variant": variant, "host": host, "error": got.error})
            if not got.ok:
                result["error"] = got.error or "搜索结果为空"
                _remember_failure(result, got)
                if got.reason in BLOCK_REASONS:          # 被拦 → 这个镜像歇一会儿
                    lim.note_blocked(host, reason=got.reason)
                continue
            text = got.body.decode("utf-8", "replace")
            blocked = classify_block(text[:FAILURE_BODY_LIMIT], got.status)
            if blocked:
                # 200 也可能是拦截页（CF 挑战就是 200）：正文强特征已经认出来了
                result["error"] = f"命中拦截页（{blocked}）"
                result["reason"] = blocked
                result["http_status"] = _to_int(got.status)
                lim.note_blocked(host, reason=blocked)
                continue
            clean_seen = True
            cards = parse_javtxt_search(text)
            hit = pick_javtxt_hit(cards, target_norm)
            if not hit:
                continue
            throttle(host, interval)
            detail = http_fetch(f"{host}{hit['url']}", proxy=proxy, timeout=timeout,
                                retries=JAVTXT_RETRIES)
            if not detail.ok:
                result["error"] = detail.error or "详情页拉取失败"
                _remember_failure(result, detail)
                if detail.reason in BLOCK_REASONS:
                    lim.note_blocked(host, reason=detail.reason)
                detail_failed = True
                continue
            detail_text = detail.body.decode("utf-8", "replace")
            blocked = classify_block(detail_text[:FAILURE_BODY_LIMIT], detail.status)
            if blocked:
                result["error"] = f"详情页命中拦截页（{blocked}）"
                _remember_failure(result, detail)
                lim.note_blocked(host, reason=blocked)
                detail_failed = True
                continue
            parsed = parse_javtxt_detail(detail_text)
            result.update(parsed)
            result.update({
                "ok": True, "status": "ok", "vid": hit.get("id", ""),
                "url": f"{host}{hit['url']}", "host": host, "error": "",
                "reason": "", "http_status": _to_int(detail.status),
            })
            result["latency_ms"] = int((time.time() - started) * 1000)
            _log_source(store, SRC_JAVTXT, "ok", key or number,
                        result["latency_ms"], "", run_id=run_id)
            return result

    result["latency_ms"] = int((time.time() - started) * 1000)
    if detail_failed:
        # 站点上**有**这个番号（搜索页干净且命中），但详情页取不回来 → 是请求失败，不是收录缺口
        result["status"] = "error"
        if not result["error"]:
            result["error"] = f"详情页取不到内容（{result['reason'] or '未知原因'}）"
    elif clean_seen:
        # 读到过干净页面 → 真·收录缺口：reason 清空（别让界面把它显示成"被拦"）
        result["status"] = "miss"
        result["reason"] = ""
        result["error"] = ""
    elif result["reason"]:
        result["status"] = "error"
        if not result["error"]:
            result["error"] = f"请求失败（{result['reason']}）"
    _log_source(store, SRC_JAVTXT, result["status"], key or number,
                result["latency_ms"], result["error"], reason=result["reason"],
                http_status=_to_int(result.get("http_status")), run_id=run_id)
    return result


def _remember_failure(result: Dict[str, Any], got: FetchResult) -> None:
    """把一次失败的 `reason`/`http_status` 收进结果（**首个原因优先**）。

    只记第一个：多变体 × 多主机的循环里，最后一个失败通常是"另一个镜像也连不上"，
    信息量不如第一个（真正的始作俑者）。
    """
    if not result.get("reason") and got.reason:
        result["reason"] = got.reason
        result["http_status"] = _to_int(got.status)
    elif not result.get("http_status") and got.status:
        result["http_status"] = _to_int(got.status)


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


# ---------------------------------------------------------------------------
# 逐站快照（0.8.0 / P0-3）：只重算不重抓
#
# 与 `meta.raw_json` 的分工：那边是**摘要**（URL/vid/长度，受 5KB 上限），这里是**可复用结果**
# （`javtxt_lookup()` 的返回形状，落 `store.site_snapshot`）。
# 于是"换字段聚合策略时只重算不重抓"能在**单个源**的粒度上成立。
# ---------------------------------------------------------------------------

#: 快照载荷保留的键（结果 + 排障线索；`tried`/`latency_ms` 这类过程信息不入库）。
#: `raw` 是 javdb 那条的**原始 DTO**（P0-4 离线回放要用它重算骨架；它比 `meta.raw_json`
#: 里那份受 5KB 上限的摘要完整）。
_SNAPSHOT_KEYS: Tuple[str, ...] = (
    "ok", "status", "vid", "url", "host", "title_jp", "title_zh", "plot_jp", "plot_zh",
    "zh_is_machine", "actors", "release_date", "studio", "director", "number_written",
    "error", "reason", "http_status", "provider", "id", "candidates", "mismatch", "movie",
    "raw",
)


def snapshot_use(options: Dict[str, Any]) -> Set[str]:
    """允许复用哪些源的快照：`opts['use_cache']`。

    接受集合（`("javdb","javtxt")`）或 `"all"`。**默认空** —— 复用是"只重算不重抓"
    的显式选择，不是默认行为：站点后来补了简介、改了标题，只有重抓才看得到。
    （`javdb` 那条既有路径不受它管：`meta.raw_json['javdb']` 存在时本来就跳过调用。）
    """
    raw = _opt(options, "use_cache")
    if isinstance(raw, str):
        return set(scrape_graph.SOURCES) if raw.strip().lower() in ("all", "1", "true") else set()
    if isinstance(raw, (list, tuple, set, frozenset)):
        return {str(item) for item in raw}
    return set()


def snapshot_payload(got: Any) -> Dict[str, Any]:
    """把一次源调用的结果收成快照载荷（只留 `_SNAPSHOT_KEYS`，空值不留）。"""
    data = got if isinstance(got, dict) else {}
    return {name: data.get(name) for name in _SNAPSHOT_KEYS
            if data.get(name) not in (None, "", [], {})}


def write_snapshot(store: Any, key: str, site: str, got: Any, *, run_id: str = "") -> None:
    """落一份逐站快照。`store` 缺失/不支持/写失败都**静默跳过**（快照只是加速器）。

    调用方传 `store=logs`（与 `scrape_log` 同一条闸门）：`log_sources=False` 的只读调用方
    （`preview_one`）不落盘 —— "preview 一行不写"这条纪律不能因为快照破掉。
    """
    if store is None or not hasattr(store, "snapshot_put"):
        return
    try:
        store.snapshot_put(key, site, snapshot_payload(got),
                           status=str((got or {}).get("status") or ""), run_id=run_id)
    except Exception as error:                                  # pragma: no cover - 防御
        logger.warning(f"AVHelper 写站点快照失败（{site}）：{error}")


def javtxt_from_snapshot(row: Any) -> Optional[Dict[str, Any]]:
    """快照 → `javtxt_lookup()` 的返回形状（`from_cache=True`）；不能复用回 `None`。

    **失败快照不复用**：被 CF 拦 / 超时那次的记录只说明"当时不行"，下次要真重试；
    只有 `ok` 与 `miss`（真·收录缺口）才值得复用。
    """
    data = dict((row or {}).get("payload") or {}) if isinstance(row, dict) else {}
    if not data:
        return None
    status = str(data.get("status") or "miss")
    ok = bool(data.get("ok"))
    if not ok and status != "miss":
        return None
    return {
        "ok": ok, "status": status, "from_cache": True,
        "vid": str(data.get("vid") or ""), "url": str(data.get("url") or ""),
        "host": str(data.get("host") or ""),
        "title_jp": _clean_text(data.get("title_jp")),
        "title_zh": _clean_text(data.get("title_zh")),
        "plot_jp": _clean_text(data.get("plot_jp")),
        "plot_zh": _clean_text(data.get("plot_zh")),
        "zh_is_machine": bool(data.get("zh_is_machine")),
        "actors": [a for a in (data.get("actors") or []) if isinstance(a, dict)],
        "tried": [], "error": str(data.get("error") or ""),
        "reason": str(data.get("reason") or ""),
        "http_status": _to_int(data.get("http_status")), "latency_ms": 0,
    }


def replay_run(key: str, store: Any, *, number: str = "", opts: Optional[Dict[str, Any]] = None,
               existing: Any = None) -> Dict[str, Any]:
    """**离线回放**（P0-4）：只用逐站快照重算一遍聚合，**一个站点请求都不发**。

    治的就是"某源静默返回空"这类排查：现场数据（javdb 原始 DTO / javtxt 结果）
    已经在 `site_snapshot` 里，改聚合规则（字段优先级、黑名单、启用源、链顺序）之后可以
    **反复重算**看结果怎么变，不必为每次试验再抓一遍站点。

    返回 `{ok, key, target, sources, field_sources, warnings, snapshots, missing}`：

    - `target` 是这次重算出的字段值（与 `gather()` 的产出同一形状）；
    - `sources` 每个源的 `status`/`from_cache`（回放时统统是 `cache`）；
    - `missing` 是"快照里没有的源"（回放结果对它的字段不可信）。

    ⚠️ **不写库**：`log_sources=False`（与 `preview_one()` 同一条纪律），也不碰 Emby。
    """
    name = str(key or "").strip()
    if not name or store is None or not hasattr(store, "snapshot_map"):
        return {"ok": False, "error": "缺少 key 或 store 不支持快照", "target": {}}
    snapshots = store.snapshot_map(name) or {}
    if not snapshots:
        return {"ok": False, "target": {}, "snapshots": [],
                "error": "库里没有这部片的站点快照（先刮一次再来回放）"}
    raw = ((snapshots.get(SRC_JAVDB) or {}).get("payload") or {}).get("raw") or {}
    options = dict(opts or {})
    options["log_sources"] = False                     # 回放绝不写 scrape_log / 快照
    options["use_cache"] = tuple(scrape_graph.SOURCES)  # 所有源都走快照
    options["force"] = False
    display = str(number or "").strip() or name
    target = gather(None, store, name, display, existing=existing,
                    javdb_raw=raw if isinstance(raw, dict) and raw else None, opts=options)
    target_fields = {field: target.get(field) for field in scrape_graph.FIELDS
                     if target.get(field) not in (None, "", [], {})}
    return {
        "ok": bool(target_fields) or bool(target.get("sources")),
        "key": name, "number": str(target.get("number") or display),
        "target": target_fields,
        "sources": target.get("sources") or {},
        "field_sources": target.get("field_sources") or {},
        "warnings": target.get("warnings") or [],
        "snapshots": {site: str((row or {}).get("fetched_at") or "")
                      for site, row in snapshots.items()},
        "missing": [site for site in scrape_graph.SOURCES if site not in snapshots],
        "error": "",
    }


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
# scrape_log 记录（一行封装，所有数据源调用共用）
# ---------------------------------------------------------------------------

def _log_source(store: Any, source: str, status: str, key: str = "",
                latency_ms: int = 0, error: str = "", *, reason: str = "",
                http_status: int = 0, run_id: str = "") -> None:
    """往 `scrape_log` 记一条；`store` 缺失/不可用时静默跳过（读侧不该因为日志挂掉）。

    `reason`（机器可读，`REASON_*`）与 `http_status` 是 0.8.0 加的：`status` 只能回答
    "成没成"，排障要回答"为什么" —— 两者都要落在库里，才能按原因分组看趋势
    （`parse_error` 连续上涨 = 站点改版；`cloudflare_challenge` 上涨 = 被拦）。
    `run_id` 把同一次刮削的各源记录串成一组（`store.scrape_log_run()` 取回）。
    """
    if store is None or not hasattr(store, "scrape_log_add"):
        return
    try:
        store.scrape_log_add(source, status, key=key, latency_ms=_to_int(latency_ms),
                             error_summary=str(error or "")[:500], reason=str(reason or ""),
                             http_status=_to_int(http_status), run_id=str(run_id or ""))
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
                   store: Any = None, key: str = "", raw: Any = None,
                   run_id: str = "") -> Dict[str, Any]:
    """取 javdb 骨架（标题/发行日/时长/片商/系列/导演/评分/演员/标签/封面）。

    `raw` 非空时**直接用它还原骨架、不调 javdb**（契约 §5.3「只补缺不重抓」：
    Tier1 重试时 `meta.raw_json['javdb']` 已存在就跳过这次调用）。
    调用走 `cli.detail(number)`（`client.JavdbClient._run()` 的既有失败留痕/冷却都在里面）。

    javdb 走**子进程**，拿不到 HTTP 状态码 → 机器原因只能从失败文案反推
    （`reason_from_text()`）；反推不出来给 `unexpected`，**绝不猜成"站点没收录"**。
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
                        int((time.time() - started) * 1000), f"{type(error).__name__}: {error}",
                        reason=reason_from_text(error, REASON_UNEXPECTED), run_id=run_id)
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
        _log_source(store, SRC_JAVDB, "error", key or number, latency, reason,
                    reason=reason_from_text(reason, REASON_UNEXPECTED), run_id=run_id)
        return {
            "ok": False, "error": reason, "latency_ms": latency, "display_number": number,
            "reason": reason_from_text(reason, REASON_UNEXPECTED),
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
    _log_source(store, SRC_JAVDB, "ok", key or number, latency, "", run_id=run_id)
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


def pack_raw_json(javdb_raw: Any, javtxt: Any = None,
                  extra: Any = None, limit: int = RAW_JSON_LIMIT) -> Dict[str, Any]:
    """组装 `meta.raw_json` 并保证总体积 ≤`limit`（默认 5KB）。

    javtxt 只存**摘要元数据**（URL / vid / 有没有中文），不存正文 ——
    正文有自己的列（`plot_zh`/`plot_jp`），再塞进 raw_json 就是重复占体积。
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
    if isinstance(extra, dict):
        out["extra"] = extra
    if len(_json_dumps(out)) <= limit:
        return out
    javdb = out.get("javdb")
    if isinstance(javdb, dict):
        out["javdb"] = trim_javdb_raw(javdb, max(256, limit // 2))
    if len(_json_dumps(out)) <= limit:
        return out
    for drop in ("extra", "javtxt"):
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
                 store: Any = None, key: str = "", run_id: str = "") -> List[Dict[str, Any]]:
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
        detail = f"assets list 退出码 {code}：{err.decode('utf-8', 'replace')[:200]}"
        _log_source(store, SRC_IMAGE, "error", key or number, latency, detail,
                    reason=reason_from_text(detail, REASON_UNEXPECTED), run_id=run_id)
        return []
    try:
        payload = json.loads(out.decode("utf-8", "replace") or "[]")
    except ValueError:
        _log_source(store, SRC_IMAGE, "error", key or number, latency, "assets list 输出不是 JSON",
                    reason=REASON_PARSE, run_id=run_id)
        return []
    assets = parse_assets_list(payload)
    _log_source(store, SRC_IMAGE, "ok" if assets else "miss", key or number, latency,
                "" if assets else "assets list 为空",
                reason="" if assets else REASON_NO_USABLE, run_id=run_id)
    return assets


def javdb_assets_download(cli: Any, number: str, assets: Sequence[Dict[str, Any]],
                          *, opts: Optional[Dict[str, Any]] = None, store: Any = None,
                          key: str = "", run_id: str = "") -> Dict[str, bytes]:
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
                    "资产缺少 1-based 位置（assets list --json 未给出），跳过下载",
                    reason=REASON_PARSE, run_id=run_id)
        return {}
    timeout = _to_int(_opt(opts, "javdb_timeout")) or 60
    started = time.time()
    code, out, err = _run_cli(
        cli, ["assets", "list", str(number), "--type", kind, ",".join(selectors)],
        timeout=timeout)
    if code != 0:
        detail = f"assets list(pipe) 退出码 {code}：{err.decode('utf-8', 'replace')[:200]}"
        _log_source(store, SRC_IMAGE, "error", key or number,
                    int((time.time() - started) * 1000), detail,
                    reason=reason_from_text(detail, REASON_UNEXPECTED), run_id=run_id)
        return {}
    lines = [ln for ln in out.decode("utf-8", "replace").splitlines() if _ASSET_LINE.match(ln)]
    if len(lines) != len(selectors):
        detail = f"管道记录数 {len(lines)} ≠ 选择器数 {len(selectors)}，放弃这一批下载"
        _log_source(store, SRC_IMAGE, "error", key or number,
                    int((time.time() - started) * 1000), detail,
                    reason=REASON_PARSE, run_id=run_id)
        return {}
    tmp = tempfile.mkdtemp(prefix=_TMP_PREFIX)
    try:
        code, dl_out, dl_err = _run_cli(
            cli, ["assets", "download", "-d", tmp], timeout=timeout,
            stdin_data=out or b"")
        paths = [ln.strip() for ln in dl_out.decode("utf-8", "replace").splitlines()
                 if ln.strip()]
        result: Dict[str, bytes] = {}
        # 行数与下载条数**允许不等**（CLI 只打印下成功的），所以显式 strict=False：
        # 不是「长度必须先对齐」的不变量，缺的图会在这里静默跳过。
        for asset, path in zip(rows, paths, strict=False):
            try:
                with open(path, "rb") as handle:
                    blob = handle.read()
            except OSError:
                continue
            if blob:
                result[str(asset.get("url"))] = blob
        latency = int((time.time() - started) * 1000)
        detail = "" if result else (
            f"下载了 0 张（退出码 {code}）：{dl_err.decode('utf-8', 'replace')[:200]}")
        _log_source(store, SRC_IMAGE, "ok" if result else "error", key or number, latency,
                    detail, reason="" if result else reason_from_text(detail, REASON_UNEXPECTED),
                    run_id=run_id)
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

    每行固定给全这八个键，下游（`film_view()` / `sync_actor_avatars()`）不再各自兼容：

    | 键 | 来源 | 用途 |
    | --- | --- | --- |
    | `name` | `namemap.actor_display()` 的 `name`（**简中名**；无映射时原名） | 界面展示、`names` 过滤 |
    | `person` | `person_name()` = D13 规范名 `中文（日文）` | Emby `People[].Name`（**必须与写入值逐字一致**，D15） |
    | `zh` / `jp` | 映射表 / 原名 | 展示、`person` 的构件 |
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
            # Emby `People[].Name` 的取值：与写侧 `build_people()` **同一个函数**（D15 的
            # 「逐字一致」要求）。0.7.2 真机误报 `person_missing` 就是这里缺了这一格，
            # 下游只能退而拿只有简中名的 `name` 去 `find_person()`。
            "person": person_name(display),
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


def person_from_actor(actor: Any, mod: Any = None) -> str:
    """一行 actor → Emby `People[].Name`（**唯一取值链**：三语名 → D13 规范名）。

    写侧（`build_people()`）与头像侧（`_avatar_index()` → `find_person()`）**必须都走
    这一个函数**，否则两边会算出不同的名字。兼容两种输入：

    - javdb 原始形状 `{id,name,avatar_url,gender}`（`name` 是站点给的原名）或裸字符串
      → 走 `actor_display()` 查映射表，再 `person_name()` 拼 `中文（日文）`；
    - `actor_rows()` 产出的行（自带 `zh`/`jp`）→ **直接用行里的三语名复算** `person_name()`，
      不再查一次表：那正是写 Emby 那一刻映射出来的值（映射表被用户覆盖/换版、或名字本身
      是歧义键时，再查一次可能给出另一个答案）。

    ⚠️ **0.7.2 真机 bug 的根因**：头像侧原来拿的是 `actor_rows()['name']`，那是
    `namemap.actor_display()` 的 `name` 字段 = **只有简中名**（`松本一香`），而 Emby 里的
    Person 实体叫 `松本一香（松本いちか）`（写侧 `person_name()` 的结果）→ `find_person()`
    精确匹配失败 → 误报 `person_missing`、头像永远传不上去（见 §`sync_actor_avatars`）。

    **只做精确相等匹配**：本函数只负责"算出那一个名字"，Emby 侧绝不拿别名/子串去猜
    （D15：Person 实体按 `Name` 精确建，模糊匹配会挂到别人的实体上）。
    """
    if isinstance(actor, dict):
        if _clean_text(actor.get("jp")) or _clean_text(actor.get("zh")):
            return person_name(actor)
        raw: Any = actor.get("name")
    else:
        raw = actor
    if mod is None:
        # 走模块级 `actor_display()`（不是 `_display_with()`）：那是既有的注入点，
        # 单测与调用方靠 monkeypatch 它来顶掉映射层。
        return person_name(actor_display(raw))
    return person_name(_display_with(mod, raw))


def build_people(original: Any, actors: Any, director: Any) -> List[Dict[str, Any]]:
    """按契约 §3.6.1 重写 `People[]`（D13/D14）。

    - 演员一条 `{"Name": 规范名, "Type": "Actor"}`，**不写 `Id`**（实测填 Id 与置空行为完全一样，
      写了只会误导后来人以为能"回填 PersonId"）；
    - **只写女演员**：javdb 口径 `gender` 0=女 / 1=男，`1` 一律跳过；`gender` 缺失（旧行 `None`）
      或取值无法判定时**保守保留**（宁可多写一条，也不误删女优）；
    - **不再写导演**（`director` 参数保留只为兼容调用方，本函数不再使用）；
    - **保留原 DTO 里 `Type` 既非 Actor 也非 Director 的元素**（工作室人员/客串等），
      否则一次刮削就把 MetaTube 或用户手工加的其它人员抹掉了。

    `Name` 由 `person_from_actor()` 算 —— 与头像侧 `_avatar_index()` **同一个函数**，
    两边逐字一致是 D15 的硬要求（0.7.2 的 `person_missing` 误报就是两边走了不同的链）。
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
        name = person_from_actor(actor)
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
                     store: Any = None, key: str = "", run_id: str = "") -> Dict[str, Any]:
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
                    int((time.time() - started) * 1000), f"{type(error).__name__}: {error}",
                    reason=REASON_UNEXPECTED, run_id=run_id)
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
                int((time.time() - started) * 1000), out["error"],
                reason="" if status == "done" else REASON_UNEXPECTED, run_id=run_id)
    return out


# ---------------------------------------------------------------------------
# 取数层总装：三源合并成一份「目标」（写侧与 preview 共用同一份，保证 diff 不会说谎）
# ---------------------------------------------------------------------------

#: `build_overrides()` 的 **Emby 字段 → 取数图字段**（预览里那行"这条是谁给的"）。
#: 候选**按取值顺序**给（与 `build_overrides()` 里的 `a or b` 一致），取第一个有来源的。
#: 未登记的覆盖键回空串 —— **不猜**（将来新增字段时要同步这张表，另有一条单测盯着）。
_OVERRIDE_SOURCES: Dict[str, Tuple[str, ...]] = {
    "Name": ("title_zh", "title_jp"),
    "OriginalTitle": ("title_jp", "origin_title"),
    "Overview": ("plot_zh", "plot_jp"),
    "PremiereDate": ("release_date",),
    "ProductionYear": ("release_date",),
    "Studios": ("studio",),
    "SeriesName": ("series",),
    "GenreItems": ("tags",),
    "CommunityRating": ("score",),
    "People": ("actors",),
    "ProviderIds": ("javdb_id",),
}


def gather(cli: Any, store: Any, key: str, display_number: str, *,
           opts: Optional[Dict[str, Any]] = None, existing: Optional[Dict[str, Any]] = None,
           version_tags: Optional[Dict[str, Any]] = None,
           javdb_raw: Any = None) -> Dict[str, Any]:
    """两源取数 → 目标字段 + 来源状态 + 警告（**不碰 Emby**）。

    顺位严格照契约：骨架 javdb → 简介 Javtxt（中文直出）→ 缺中文才走翻译（LLM）；
    标签 `namemap.clean_tags`；演员/导演来自 javdb。

    `existing`（`store.meta_get(key)`）里已有 `raw_json['javdb']` 且 `opts['force']` 不为真时
    **跳过 javdb 调用**（契约 §5.3：只补缺不重抓）。
    """
    options = dict(opts or {})
    # `log_sources=False` 时整条取数链一行日志都不写（preview 的纯只读调用方用得上）
    logs = store if bool(_opt(options, "log_sources", True)) else None
    # 一次刮削 = 一个 run：本次各源的 `scrape_log` 记录都带同一个 `run_id`，
    # 排障时用 `store.scrape_log_run(run_id)` 一次取回"当时每个源各发生了什么"。
    # `opts['run_id']` 可注入（单测/工装要固定它）。
    run_id = str(_opt(options, "run_id") or "") or uuid.uuid4().hex[:12]
    # 取数图（0.8.0 / P0-1）：内容类型 → 站点链 → **每字段一条链**。
    # 今天三个源、所有类型共用一条链；`field_priority` / `field_blacklist` 是稀疏旋钮
    # （设置台存 camelCase，由 `__init__.scrape_opts()` 映射成下划线）。
    shape = number_classify.classify(display_number, version_tags=version_tags)
    # ⚠️ 走 `_opt()` 而不是 `options.get()`：调用方没给时要能回落到 `DEFAULT_OPTS`
    #   （`plot_sources` 的默认值就在那儿；直接读 options 会让默认链路整条失效）
    enabled = scrape_graph.enabled_sources({"sources": _opt(options, "sources"),
                                            "plot_sources": _opt(options, "plot_sources")})
    chains = scrape_graph.compile_chain(
        shape["content_type"],
        field_priority=_opt(options, "field_priority"),
        field_blacklist=_opt(options, "field_blacklist"),
        enabled=enabled,
    )
    # 「这个字段最后是谁给的」——**在填值的那一刻打标**（事后按链反推会撒谎：
    # javtxt 的占位简介要丢弃、LLM 会覆盖它）。
    field_sources: Dict[str, str] = {}

    def may_fill(field: str, site: str) -> bool:
        """**链的裁决口**（P0-1 收口）：`site` 现在能不能给 `field` 赋值。

        两条判据（都在 `scrape_graph.compile_chain()` 产出的链上）：

        1. `site` 不在该字段的链里 → **不给**（这就是 `field_blacklist` 与"源被关掉"的执行力：
           以前链算完就放着，填值时一点不看，配置写了等于没写）；
        2. 链上排在 `site` **前面**、但执行顺序上还在它**后面**的源 → 说明"这个字段要优先问它"，
           于是现在先别填，留给那个源（执行顺序是 javdb → javtxt，见 `EXEC_ORDER`）。

        默认链（三种顺序一致）下两条恒真 → 行为与引入取数图之前**逐字一致**。
        """
        chain = chains.get(field)
        if not chain:
            return True
        if site not in chain:
            return False
        here = scrape_graph.EXEC_ORDER.index(site) if site in scrape_graph.EXEC_ORDER else -1
        for earlier in chain[:chain.index(site)]:
            where = (scrape_graph.EXEC_ORDER.index(earlier)
                     if earlier in scrape_graph.EXEC_ORDER else -1)
            if where > here:
                return False                    # 留给执行顺序更晚的那个优先源
        return True
    # 逐站快照的复用名单（P0-3）：`force` 时不复用（"强制重抓"要真的重抓）
    use_snapshots = set() if bool(_opt(options, "force")) else snapshot_use(options)

    def mark(name: str, source: str) -> None:
        field_sources[name] = source
    warnings: List[str] = []
    sources: Dict[str, Any] = {
        SRC_JAVDB: {"status": "skipped"}, SRC_JAVTXT: {"status": "skipped"},
        SRC_LLM: {"status": "skipped"},
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
                                  raw=cached_javdb if cached_javdb else None, run_id=run_id)
        # P0-4：把**真抓到的** javdb 原始 DTO 也存成逐站快照 —— 它比 `meta.raw_json` 里那份
        # 摘要完整（那份受 5KB 上限、还会被后续写入覆盖），离线回放要靠它重算骨架。
        if skeleton.get("ok") and isinstance(skeleton.get("raw"), dict):
            write_snapshot(logs, key, SRC_JAVDB,
                           {"ok": True, "status": "ok", "raw": skeleton["raw"]}, run_id=run_id)
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
            sources[SRC_JAVDB] = {"status": "error", "error": skeleton.get("error", ""),
                                  "reason": skeleton.get("reason", REASON_UNEXPECTED)}
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
    # javdb 的字段先全部打上"javdb"的标（有值才算），后面谁覆盖就改谁的标
    # P0-1 收口：链上说这个字段不要 javdb（或要优先问后面的源）时，这里就不打标、值也清掉。
    for name in scrape_graph.SOURCES["javdb"].provides:
        if name == "plot_jp":
            value = plot_jp
        elif name == "title_jp":
            value = title_jp
        elif name == "origin_title":
            value = origin_jp
        else:
            value = skeleton.get(name if name != "studio" else "maker")
        if value and not may_fill(name, "javdb"):
            if name in ("plot_jp", "title_jp", "origin_title"):
                if name == "plot_jp":
                    plot_jp = ""
                elif name == "title_jp":
                    title_jp = ""
                else:
                    origin_jp = ""
            else:
                skeleton[name if name != "studio" else "maker"] = ""
            continue
        if value:
            mark(name, "javdb")

    javtxt_meta: Dict[str, Any] = {}
    # 逐站快照（P0-3）：`use_cache` 点名的源可以**不发请求**直接复用上次的结果
    snapshots: Dict[str, Any] = {}
    if use_snapshots and store is not None and hasattr(store, "snapshot_map"):
        try:
            snapshots = store.snapshot_map(key) or {}
        except Exception as error:                              # pragma: no cover - 防御
            logger.warning(f"AVHelper 读站点快照失败（{key}）：{error}")
            snapshots = {}
    # 启停来自取数图（`opts['sources']`，回落旧的 `plot_sources`）—— 别再自己拼条件
    if "javtxt" in enabled:
        javtxt = javtxt_from_snapshot(snapshots.get("javtxt")) if "javtxt" in use_snapshots \
            else None
        if javtxt is None:
            # S11 抓取缓存（工装 `coverage.json`）：命中就一次站点请求都不发
            javtxt = _javtxt_from_cache(row.get("javtxt")) if row else None
        if javtxt is None:
            if cache_only:
                # 缓存的"没命中"同样是权威结论（S11：8 条站点收录缺口，重试也没用）
                javtxt = {"ok": False, "status": "miss", "from_cache": True, "error": "",
                          "title_jp": "", "title_zh": "", "plot_jp": "", "plot_zh": "",
                          "zh_is_machine": False, "actors": [], "vid": "", "url": "",
                          "tried": [], "latency_ms": 0}
            else:
                javtxt = javtxt_lookup(options, display_number, store=logs, key=key,
                                       run_id=run_id)
                # 快照与 `scrape_log` 同一条闸门（`store=logs`）：preview 只读、不落盘
                write_snapshot(logs, key, SRC_JAVTXT, javtxt, run_id=run_id)
        javtxt_meta = javtxt
        sources[SRC_JAVTXT] = {
            "status": javtxt.get("status", "miss"), "latency_ms": javtxt.get("latency_ms", 0),
            "url": javtxt.get("url", ""), "error": javtxt.get("error", ""),
        }
        if javtxt.get("reason"):
            sources[SRC_JAVTXT]["reason"] = javtxt.get("reason")
        if javtxt.get("http_status"):
            sources[SRC_JAVTXT]["http_status"] = _to_int(javtxt.get("http_status"))
        if javtxt.get("from_cache"):
            sources[SRC_JAVTXT]["from_cache"] = True
        if javtxt.get("ok"):
            # P0-1 收口：链是**用来裁决的**，不是算完就放着 —— 该字段被排除（黑名单）或
            # 链上还有更靠前、但执行顺序上更晚的源时，这里就先别填，留给它。
            title_zh = _clean_text(javtxt.get("title_zh")) if may_fill("title_zh", "javtxt") else ""
            plot_zh = _clean_text(javtxt.get("plot_zh")) if may_fill("plot_zh", "javtxt") else ""
            javtxt_jp = (_clean_text(javtxt.get("plot_jp")) if may_fill("plot_jp", "javtxt")
                         else "")
            plot_jp = javtxt_jp or plot_jp
            if title_zh:
                mark("title_zh", "javtxt")
            if javtxt_jp:
                mark("plot_jp", "javtxt")
            if plot_zh:
                mark("plot_zh", "javtxt")
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
                field_sources.pop("plot_zh", None)          # 溯源也要跟着撤，别留下假来源
        elif javtxt.get("status") == "skipped":
            # P1-2：这个源在冷却里（被拦过），本次一个请求都没发 —— 与"站点没收录"分开说
            warnings.append(f"Javtxt 已跳过：{javtxt.get('error', '') or '冷却中'}")
        elif javtxt.get("status") == "error":
            # 被拦与"站点挂了/改版了"处置不同：前者要冷却 + 换 UA，后者要修解析器
            if str(javtxt.get("reason") or "") in (REASON_CF_CHALLENGE, REASON_CF_BLOCKED,
                                                  REASON_AGE, REASON_IP_BANNED, REASON_GEO):
                warnings.append(f"Javtxt 被站点拦截（{javtxt.get('reason')}）："
                                f"{javtxt.get('error', '')} —— 稍后重试")
            else:
                warnings.append(f"Javtxt 请求失败：{javtxt.get('error', '')}")
        else:
            warnings.append("Javtxt 无同号结果（站点收录缺口，本次没有中文简介）")

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
            actors=skeleton.get("actors"), opts=options, store=logs, key=key, run_id=run_id)
        if tr.get("title_zh"):
            title_zh = tr["title_zh"]
            mark("title_zh", scrape_graph.DERIVED_SOURCE)
        if tr.get("plot_zh"):
            plot_zh = tr["plot_zh"]
            plot_source = plot_source or "llm"
            mark("plot_zh", scrape_graph.DERIVED_SOURCE)
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
    result = {
        "key": key,
        "cli": cli,
        "run_id": run_id,
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
        # P0-0 的分类（路由的键）
        "content_type": shape["content_type"],
        "mosaic": shape["mosaic"],
    }
    # P0-1 的溯源：**只在最终真有值时才留来源**（被丢弃/清空的字段不留假来源）
    result["field_sources"] = {name: source for name, source in field_sources.items()
                               if result_value(result, name) not in ("", None, [], {})}
    return result


def result_value(result: Dict[str, Any], name: str) -> Any:
    """取最终值的**同一口径**（`field_sources` 过滤用）：字段可能被写成 int 0（duration），
    也可能是列表（actors/tags）—— 这里只看"空不空"。"""
    value = result.get(name)
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if value else ""
    return value


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


def _write_field_set(opts: Dict[str, Any]) -> Optional[Set[str]]:
    """`opts['write_fields']` → 「这次允许写的字段名」集合；没给这个键时回 `None` = 不过滤。

    ⚠️ **空表与"没给"必须分开**：`[]`（用户一个字段都没勾）要回**空集合** —— 那意味着
    "一项都不写"；回 `None` 会退化成"整份写"，正好把用户的意思做反。
    `None`（键不存在）才是不过滤，批量刮削与定时刮削走的都是这条路。

    图片槽位用两个伪字段名：`Primary`（封面）/ `Backdrop`（剧照），与 `_upload_images()`
    共用同一份闸门。
    """
    src = opts or {}
    if "write_fields" not in src or src.get("write_fields") is None:
        return None
    only = src.get("write_fields")
    if not isinstance(only, (list, tuple, set)):
        return None
    return {str(item).strip() for item in only if str(item).strip()}


def _pick_fields(overrides: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
    """按 `opts['write_fields']` 裁覆盖表（手动刮削的"只写勾中的那几项"）。

    只裁**字段**；图片走 `_upload_images()` 里同一份闸门（`Primary` / `Backdrop` 这两个
    伪字段名），两边共用 `_write_field_set()`，不会一边写一边不写。
    """
    allowed = _write_field_set(opts)
    if allowed is None:
        return overrides
    return {key: value for key, value in overrides.items() if str(key) in allowed}


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


def field_diff(dto: Optional[Dict[str, Any]], overrides: Dict[str, Any],
               field_sources: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """生成 `fields:[{name,current,target,changed,source}]`（`preview_one` 的字段级 diff）。

    顺序固定走 `MATRIX_FIELDS`，**每个矩阵字段都出一行**（哪怕这次跳过它）：
    `target=None` 就是"拿不到、跳过该字段"的可见证据，比只列改动过的字段有用得多。

    `changed` 的判据是「**最终会写进去 且 与现值不同**」（`effective_overrides()` + 值比对），
    不是"`target` 非空"—— 后者会把压根不会发的字段也算成改动（0.7.0 试点真机反例：
    `FC2PPV4828968` 只写 `ProviderIds`，却报了 8 个"改动"）。

    `source`（0.8.0 / P0-1）来自 `gather()` 的逐字段溯源：**这个值是谁给的**。
    查 `_OVERRIDE_SOURCES` 拿候选字段，取第一个有来源的；未登记的字段回空串（不猜）。
    """
    current = dto if isinstance(dto, dict) else {}
    will_write = effective_overrides(overrides)
    sources = field_sources or {}

    def source_of(name: str) -> str:
        for key in _OVERRIDE_SOURCES.get(name, ()):
            if overrides.get(name) is None:
                break
            if sources.get(key):
                return str(sources[key])
        return ""

    out: List[Dict[str, Any]] = []
    for name in MATRIX_FIELDS:
        out.append({
            "name": name,
            "current": current.get(name, None),
            "target": overrides.get(name, None),
            "changed": name in will_write and _differs(current.get(name, None),
                                                       overrides.get(name)),
            "source": source_of(name),
        })
    for name in sorted(set(overrides) - set(MATRIX_FIELDS)):
        out.append({"name": name, "current": current.get(name),
                    "target": overrides[name],
                    "changed": name in will_write and _differs(current.get(name), overrides[name]),
                    "source": source_of(name)})
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
    got = http_fetch(text, proxy=str(_opt(opts, "proxy") or ""),
                     timeout=_to_int(_opt(opts, "http_timeout")) or 30, retries=1)
    if not got.ok:
        return b"", f"取图失败（{got.reason or got.kind}）：{got.error}"
    if not is_image_bytes(got.body):
        return b"", "拿到的不是图片（缺 imgproxy 时无法解 XOR/Referer，已丢弃）"
    return got.body, ""


def _upload_images(emby_client: Any, store: Any, emby_id: str, target: Dict[str, Any],
                   assets: Sequence[Dict[str, Any]], opts: Dict[str, Any],
                   key: str, cli: Any = None) -> Dict[str, Any]:
    """封面 → `Primary`、横版剧照 → `Backdrop/0..2` + `Thumb`（**同一张图只下一次**）。

    **封面取数的两级兜底**（缺陷 5，试点批真机）：

    1. javdb `assets list` 挑出来的 cover（优先）；
    2. 拿不到就退回**取数层给的 `cover_url`**（javdb 详情的封面 / 剧照），
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
    # 手动刮削可以在界面上取消勾选「封面 / 剧照」：与字段走同一份闸门（`Primary` / `Backdrop`
    # 是这两个图片槽位的伪字段名）。`None` = 不过滤（批量与自动刮削照旧全写）。
    only = _write_field_set(opts)
    cover_wanted = only is None or "Primary" in only
    samples_wanted = only is None or "Backdrop" in only
    picked = pick_assets(assets, cover_url=str(target.get("cover_url") or ""))
    cover = picked.get("cover") if cover_wanted else None
    samples = list(picked.get("samples") or [])
    if not bool(_opt(opts, "write_samples", True)) or not samples_wanted:
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
    # ⚠️ 兜底分支**必须也受 `cover_wanted` 管**（真机实测抓到过）：用户取消勾选「封面」时
    # `cover` 被置空 → `raw` 为空 → 老写法会顺着 `cover_url` 兜底把封面照样传上去，
    # 于是"我只勾了一个字段"变成"封面也被换了"。字段闸门要覆盖**所有**上传出口。
    if not raw and fallback_url and cover_wanted:
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
        if ok:
            # C2（0.9.5）：换了封面就把 `/img?emby=` 的本地缓存删掉，否则界面还是旧图
            _forget_emby_image(emby_id, "Primary")
        else:
            report["errors"].append(f"封面上传失败：{detail}")
    else:
        # 两级都拿不到：**不报错**，只留说明（javdb 图集空 + 没有 cover_url / 取不到）
        if not cover_wanted:
            # 用户手动取消了「封面」勾选：这不是取数失败，不许留"没拿到封面"的说明
            report["cover"] = "skipped_manual"
        else:
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
        if ok:
            _forget_emby_image(emby_id, f"Backdrop/{index}")
        if index == 0:
            ok2, detail2 = _call(emby_client, "upload_image", emby_id, "Thumb", raw_sample)
            if not ok2:
                report["errors"].append(f"Thumb 上传失败：{detail2}")
            else:
                _forget_emby_image(emby_id, "Thumb")
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


def _forget_emby_image(emby_id: Any, img_type: str = "Primary") -> None:
    """写图成功之后删掉 `/img?emby=` 的本地缓存（0.9.5 C2）。

    不删的话：换完封面 / 剧照 / 头像，界面还是旧图，直到每晚清缓存 —— `/img?emby=` 命中
    磁盘就直接回旧字节，而那条缓存**没有 TTL**。缓存只是加速，删失败不影响写入结果。
    """
    try:
        if imgproxy is not None:
            imgproxy.forget_emby(str(emby_id or ""), img_type)
    except Exception as error:                              # noqa: BLE001 - 缓存失效不许影响主流程
        logger.warning(f"AVHelper 清理 Emby 图片缓存失败（{emby_id}/{img_type}）：{error}")


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
    overrides = _pick_fields(build_overrides(local, dto), options)
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
        target.get("javdb_raw"), target.get("javtxt_meta"),
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
        # P0-1 溯源落库（`{"plot_zh": "javtxt", "title_jp": "javdb", ...}`）：
        # 界面要回答"这条简介是谁给的"，排障要回答"这个源到底贡献了什么"
        "field_sources_json": dict(target.get("field_sources") or {}),
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
        parts = str(path).replace("\\", "/").rsplit("/", 2)
        base = parts[-1]
        parent = parts[-2] if len(parts) >= 2 else ""       # P1-6：分集兜底看直接父目录
        parsed = emby.parse_av_number(base, parent=parent)
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
    sources:{javdb,javtxt,llm}, warnings:[], images:{…}, completeness}`。

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
    # ★ R10：查站点的番号 = `launch_number()`（Emby 条目名派生的补零形态优先）。
    # 键反推只能给到 `site_number()` 的旧口径兜底（`CAWB040` → `CAWB-40`），
    # 而库里真正的真相是 Emby Name / meta 行里的 `CAWB-040`（1/2/3/4 级依次回退）。
    number = launch_number(resolved, key=resolved.get("key") or "", store=store,
                           library=options.get("library"),
                           fallback=(str(options.get("display_number") or "").strip()
                                     or _fallback_number(resolved, options, found, dto)))
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
        "fields": field_diff(dto, overrides, target.get("field_sources")),
        # P0-1：逐字段溯源（`{"plot_zh": "javtxt", …}`）—— 与 `fields[].source` 是同一份数据的
        # 两种颗粒度：前者按我们的字段名，后者按 Emby 字段名
        "field_sources": dict(target.get("field_sources") or {}),
        # 0.7.4：手动刮削对话框要**如实列出将写入的演员**（0.7.1 起只写女演员，导演不写），
        # 用户能一眼看出"这次会写这几个人"，而不是只看到一个 People 字段名。
        "people": [str(entry.get("Name") or "") for entry in (overrides.get("People") or [])
                   if str(entry.get("Name") or "")],
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
    # ★ R10：查站点的番号 = `launch_number()`（Emby 条目名派生的补零形态优先，见它的说明）。
    # 输入是 `emby:<id>` 时键反推不出来，才由 `_fallback_number()` 从缓存行 / 盘上路径反推
    # （S11：**绝不用 Name 当番号源**，Name 只经 `shown_number()` 取开头那一段原始写法）。
    dto, _dto_error = _read_dto(emby_client, emby_id)
    number = launch_number(resolved, key=resolved.get("key") or "", store=store,
                           library=options.get("library"),
                           fallback=(str(options.get("display_number") or "").strip()
                                     or _fallback_number(resolved, options, found, dto)))
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
            # ★ 传给头像同步的必须是**写进 Emby 的那个名字**（`person`，与 `build_people()`
            #   同链）：拿 `name`（简中名）会让单片路径必然 `person_missing`（0.7.2 真机 bug）。
            names = [str(row.get("person") or person_from_actor(row))
                     for row in actor_rows(target.get("actors"))]
            names = [name for name in names if name]
            if names:
                avatar_sync = sync_actor_avatars(
                    store, emby_client, names=names, dry_run=False, opts=options)
                failed = [str(err) for err in (avatar_sync.get("errors") or []) if str(err)]
                if failed:
                    report["warnings"].append("头像同步：" + "；".join(failed))
        except Exception as error:                              # noqa: BLE001 - 头像同步不阻断刮削
            logger.warning(f"AVHelper 头像同步失败（不影响刮削）：{type(error).__name__}: {error}")
            report["warnings"].append(f"头像同步失败：{type(error).__name__}: {error}")
    # 女演员入 actor 队列（0.9.0 方案 §4「自动入队」）：这里**只登记、不立刻请求**，由定时 tick
    # 批量消费（每轮 ≤20 位、两车间隔 ≥2s）。整段必须自己兜住：入队失败绝不能让刮削失败。
    # 只登记女演员：拿得到 gender 才过滤 gender == 1；拿不到就全登记（**不猜**，与 0.8.1 的
    # existing 口径一致 —— 缺失 ≠ 男）。store 还没有这套 API（S1 未落地）时静默跳过，不记 warning。
    if wrote:
        try:
            queued: List[str] = []
            for row in actor_rows(target.get("actors")):
                gender = row.get("gender")
                try:
                    gender = None if gender in (None, "") else int(gender)
                except (TypeError, ValueError):
                    gender = None
                if gender == 1:
                    continue
                person = str(row.get("person") or person_from_actor(row) or "")
                if person and person not in queued:
                    queued.append(person)
            pusher = getattr(store, "actor_queue_push", None)
            if queued and callable(pusher):
                pusher(queued)
        except Exception as error:                              # noqa: BLE001 - 入队不阻断刮削
            logger.warning(f"AVHelper 演员入队失败（不影响刮削）：{type(error).__name__}: {error}")
            report["warnings"].append(f"演员入队失败：{type(error).__name__}: {error}")
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


def _skip_row(source: str, why: str, stamp: str) -> Dict[str, Any]:
    """**未探测**的一行：不给耗时、不算失败（P1-3）。

    没探测就没有耗时 —— 界面显示「无法探测 + 0 ms」是自相矛盾的；`error` 也留空，
    真正的说明放 `detail.why`（那是"没配置/没启用"，不是"站点不可达"）。
    """
    return {"source": source, "status": "skipped", "latency_ms": 0, "error": "",
            "reason": "", "checked_at": stamp, "detail": {"why": why}}


def sources_selfcheck(store: Any, cli: Any, opts: Optional[Dict[str, Any]] = None
                      ) -> List[Dict[str, Any]]:
    """**当前会真正请求的**来源各打一次轻量探针，写 `scrape_log` 并返回逐源结果。

    返回 `[{source, status, latency_ms, error, reason, http_status, checked_at, detail}]`
    （`status` ∈ `ok` / `miss` / `error` / `skipped`）。探针一律走**轻量调用**：

    - javdb：`cli.detail('SNOS-380')`（真实存在的老片，1 次子进程）；
    - javtxt：搜索 + 详情（受 2s 站点间隔约束，约 3–5 s）；
    - llm：`translator.selfcheck()`（派生源，不在取数图里，**总是探**）。

    **探测范围 = 取数图里启用的来源**（P1-3，照 amane 的"探测范围与刮削范围一致"）：
    用户在设置台关掉的源不必探 —— 否则结果里永远挂着一个"从不参与"的红行。
    `skipped` 与"不可达"分开：未配置 / 未启用 / 模块缺失都是 `skipped`（零耗时、不算失败）。
    """
    options = dict(opts or {})
    ensure_namemap(store, options)
    stamp = _now(options)
    out: List[Dict[str, Any]] = []
    # 自检也是一次 run：这一组探针记录带同一个 id，便于"按一次自检"回溯
    run_id = str(_opt(options, "run_id") or "") or uuid.uuid4().hex[:12]
    # 探测范围：当前**会真正请求**的来源（用户关掉的源不探）
    enabled = scrape_graph.enabled_sources({"sources": _opt(options, "sources"),
                                            "plot_sources": _opt(options, "plot_sources")})
    route = scrape_graph.route_for(number_classify.classify(SELFCHECK_NUMBER)["content_type"])
    wanted = [site for site in route if site in enabled]

    if "javdb" in wanted:
        out.append(_probe_javdb(cli, stamp))
    if "javtxt" in wanted:
        out.append(_probe_javtxt(options, store, stamp))
    for site in wanted:                                   # 图上将来新增的源：没有探针就如实说
        if site not in (SRC_JAVDB, SRC_JAVTXT):
            out.append(_skip_row(site, "该来源还没有自检探针", stamp))

    started = time.time()
    llm: Dict[str, Any]
    if translator is None or not hasattr(translator, "selfcheck"):
        llm = _skip_row(SRC_LLM, "translator 模块缺失（翻译链不可用，不影响取数）", stamp)
    else:
        llm = {"source": SRC_LLM, "status": "skipped", "latency_ms": 0, "error": "",
               "reason": "", "checked_at": stamp, "detail": {}}
        try:
            result = translator.selfcheck()
            ok = bool((result or {}).get("ok"))
            llm.update({
                "status": "ok" if ok else "error",
                "latency_ms": _to_int((result or {}).get("latency_ms")) or
                int((time.time() - started) * 1000),
                "error": str((result or {}).get("error") or ""),
                "reason": "" if ok else REASON_UNEXPECTED,
                "detail": {"model": (result or {}).get("model", "")},
            })
        except Exception as error:                              # noqa: BLE001 - 故意的
            llm.update({"status": "error",
                        "latency_ms": int((time.time() - started) * 1000),
                        "error": f"{type(error).__name__}: {error}",
                        "reason": REASON_UNEXPECTED})
    out.append(llm)

    for row in out:
        _log_source(store, row["source"], row["status"], SELFCHECK_NUMBER,
                    row.get("latency_ms", 0), row.get("error", ""),
                    reason=str(row.get("reason") or ""),
                    http_status=_to_int(row.get("http_status")), run_id=run_id)
    return out


def _probe_javdb(cli: Any, stamp: str) -> Dict[str, Any]:
    """javdb 探针：`cli.detail(SNOS-380)` 一次子进程（真实存在的老片）。"""
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
        return {"source": SRC_JAVDB, "status": "ok", "latency_ms": latency, "error": "",
                "reason": "", "checked_at": stamp,
                "detail": {"number": detail.get("number"), "title": bool(detail.get("title"))}}
    # 失败原因优先用 client 记下的真话（`JavdbClient.last_error` 里有子进程的 stderr 摘要：
    # 二进制不存在 / 代理不可达 / 超时 …），拿不到才退回一句笼统的说明。
    reporter = getattr(cli, "last_error", None) if cli is not None else None
    if callable(reporter) and not reason:
        try:
            reason = str(reporter(f"detail:{SELFCHECK_NUMBER}") or "")
        except Exception:                                       # pragma: no cover - 防御
            reason = ""
    return {"source": SRC_JAVDB, "status": "error", "latency_ms": latency,
            "error": reason or f"javdb 没有 {SELFCHECK_NUMBER} 的详情"
                               f"（番号下架 / 站点改版 / 被风控）",
            "reason": reason_from_text(reason, REASON_UNEXPECTED),
            "checked_at": stamp, "detail": {}}


def _probe_javtxt(opts: Dict[str, Any], store: Any, stamp: str) -> Dict[str, Any]:
    """javtxt 探针：真的搜一次 + 真的抓一次详情（否则"能连上"毫无意义）。"""
    result = javtxt_lookup(opts, SELFCHECK_NUMBER, store=None)
    ok = bool(result.get("ok"))
    return {
        "source": SRC_JAVTXT,
        "status": "ok" if ok else str(result.get("status") or "miss"),
        "latency_ms": result.get("latency_ms", 0),
        "error": result.get("error", ""),
        # 0.8.0：自检也要能回答"miss 还是被拦" —— 老版把两者都显示成 miss
        "reason": str(result.get("reason") or ""),
        "http_status": _to_int(result.get("http_status")),
        "checked_at": stamp,
        "detail": {"url": result.get("url", ""), "vid": result.get("vid", ""),
                   "title_zh": bool(result.get("title_zh")),
                   "plot_zh_len": len(result.get("plot_zh") or "")},
    }


# ---------------------------------------------------------------------------
# 公开接口 6：sync_actor_avatars（P0-② 落地版：演员头像写进 Person 实体）
# ---------------------------------------------------------------------------

AVATAR_SOURCE = "emby_avatar"


def _avatar_index(store: Any, mod: Any) -> Dict[str, Dict[str, Any]]:
    """汇总「规范名 → {avatar, javdb_actor_id, numbers[]}」（`meta.actors_json` 是唯一来源）。

    **槽键就是 `find_person()` 的入参**：一律由 `person_from_actor()` 算（与写 Emby 的
    `build_people()` 同一条链，D15）。行的 `name`（简中名）只留在 `display` 里给 `names`
    过滤与界面用 —— 0.7.2 真机误报 `person_missing` 就是拿它去匹配实体导致的
    （实体叫 `松本一香（松本いちか）`，简中名 `松本一香` 精确匹配必然落空）。

    同一演员出现在多部片里时合并；**头像取第一条非空的**（0.8.1 起头像只有 javdb 一个源）。
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
            name = person_from_actor(actor, mod)
            if not name:
                continue
            slot = index.setdefault(name, {"name": name, "display": actor["name"],
                                           "zh": actor["zh"], "jp": actor["jp"],
                                           "avatar": "", "javdb_actor_id": "",
                                           "gender": actor.get("gender"), "numbers": []})
            if not slot["avatar"] and actor["avatar"]:
                slot["avatar"] = actor["avatar"]
            if not slot["javdb_actor_id"] and actor["javdb_actor_id"]:
                slot["javdb_actor_id"] = actor["javdb_actor_id"]
            if slot.get("gender") is None and actor.get("gender") is not None:
                slot["gender"] = actor.get("gender")
            if not slot.get("jp") and actor.get("jp"):
                slot["jp"] = actor["jp"]
            number = str(row.get("display_number") or row.get("key") or "")
            if number and number not in slot["numbers"]:
                slot["numbers"].append(number)
    return index


def _wanted_slot(slot: Dict[str, Any], wanted: set) -> bool:
    """这一索引槽是否被 `names` 点名（规范名 / 展示名 / 中文名 / 日文原名**任一相等**即算）。

    放宽的**只是「挑哪几行」**：调用方（界面、单片路径）手里的名字可能是短名或日文原名。
    真正交给 `find_person()` 的永远只有 `slot['name']` 这一个**精确**值 —— Emby 的 Person
    实体按 `Name` 精确建（D15），拿别名/子串去搜等于把头像挂到别人的实体上，绝不这么做。
    """
    for key in ("name", "display", "zh", "jp"):
        text = _clean_text(slot.get(key))
        if text and text in wanted:
            return True
    return False


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
        # ★ 重试一次（0.7.4 真机实测，0.8.1 保留）：图床/代理偶发**传到一半就断**
        # （urllib 抛 `IncompleteRead`）→ `imgproxy.fetch()` 回 None。本库批跑 113 张里
        # 有 2 张这样：一张重试即成功、另一张 2.1 MB 每次都断（属图床/代理的传输问题，
        # 不是插件逻辑）—— 所以重试一次、仍失败才如实报错。
        last = "imgproxy.fetch 返回空"
        for _ in range(2):
            try:
                blob = imgproxy.fetch(url, proxy=str(_opt(opts, "proxy") or ""))
            except Exception as error:                          # noqa: BLE001 - 故意的
                last = f"imgproxy.fetch 异常：{type(error).__name__}: {error}"
                continue
            if blob:
                return bytes(blob), ""
        return b"", last
    got = http_fetch(url, proxy=str(_opt(opts, "proxy") or ""),
                     timeout=_to_int(_opt(opts, "http_timeout")) or 30, retries=1)
    if not got.ok:
        return b"", f"取头像失败（{got.reason or got.kind}）：{got.error}"
    body = got.body
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


def sync_actor_avatars(store: Any, emby_client: Any, *, limit: int = 0, dry_run: bool = True,
                       namemap_mod: Any = None, opts: Optional[Dict[str, Any]] = None,
                       names: Optional[List[str]] = None
                       ) -> Dict[str, Any]:
    """把演员头像同步到 Emby 的 **Person 实体**（P0-② / v4.1 §6.2 的落地版）。

    流程与依据（每一条都对应 `_tmp/p0/REPORT-2.md` 的实测）：

    1. 从 `store.meta_list()` 的 `actors_json` 汇总「规范名 → 头像 / javdb_actor_id」；
    2. 规范名 = 契约 D13 的 `中文（日文）`，**由 `person_from_actor()` 算出 —— 与写 Emby 的
       `build_people()` 同一个函数**（只有一边时用那一边，映射表没有的演员只写日文原名，
       绝不音译）。⚠️ 两边必须同链，否则就是这个函数的真机事故现场：
       0.7.2 头像侧拿的是 `actor_rows()['name']`（简中名 `松本一香`），而 Emby 里写的是
       `松本一香（松本いちか）` → 精确匹配落空 → 误报 `person_missing`、头像传不上去；
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
       `None`（本库还有 12 位缺字段）**保守保留**并单独计入 `gender_unknown`（**不混进
       `missing_person`**，也不静默丢掉 —— 0.7.4 改：老代码在这里 `continue`，那 12 位
       ——看名字多数是女演员——一个头像都同步不到）。只有 `gender == 1` 是硬性排除。
    9. **头像源只剩 javdb**（0.8.1）：MetaTube 整体下线后，原先经由它转发的 Gfriends
        `/v1/actors/search` 一并去掉。javdb 的 `avatars/**.jpg` 是 100×100 ~ 400×400 的
       **列表缩略图**（比 Gfriends 整图小），这是本次下线必须接受的画质代价；javdb 没给头像
       → `action='skip'` + `reason='no_avatar'`，如实跳过，不拿别的站点猜图、也绝不挂错人。
    10. `names` 给了就**只处理这些名字**（单片刮完只同步本片演员；自动路径绝不走全表）：
        规范名 / 展示名 / 中英日任一写法相等即算点名（`_wanted_slot()`；**只影响挑哪几行**，
        交给 `find_person()` 的仍只有规范名一个精确值）；`None` = 现有的全量行为。

    返回 `{ok, dry_run, actors, planned:[{name, person_id, action, reason, url?, source?}],
    applied:[…], errors:[…], missing_person, gender_unknown}`；`actors` 是**过滤后真正进流程**的
    条数（性别 + `names` 过滤在前，`limit` 在后）。

    实现已迁到 `actor_sync.py`（0.9.0 演员线）：本函数只剩转调，`opts`/`names`/`limit` 的
    口径不变；新入口是 `actor_sync.run_actor_scrape()`（actor 表、退避、gFriends 源）。
    """
    from . import actor_sync          # ⚠️ 必须函数体内 lazy import：actor_sync 模块级 import 本模块
    return actor_sync.sync_actor_avatars(
        store, emby_client, limit=limit, dry_run=dry_run, namemap_mod=namemap_mod,
        opts=opts, names=names)


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


def _dirs_of(path: Any, depth: int = 3) -> List[str]:
    """文件路径里**最近 `depth` 层目录名**（给内容类型 / 马赛克判定用）。

    只看最近几层：够认「欧美 / 里番 / CD2」这类用户自己建的目录，又不会被更外层的
    库根（`/media/9kg/avi`）带偏。路径为空回空列表（判定退回番号形态）。
    """
    parts = [p for p in re.split(r"[\\/]+", str(path or "").strip()) if p and p not in (".", "/")]
    return parts[:-1][-depth:] if len(parts) > 1 else []


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
    # 番号形态分类（0.8.0 / P0-0）：内容类型 + 马赛克标记。**只读、零网络**，
    # 是 P0-1 的路由键，也让界面现在就能显示"这部片属于哪条链"。
    shape = number_classify.classify(number, dirs=_dirs_of((picked or {}).get("file_path")),
                                     version_tags=version_tags)

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
        # P0-0 的分类结论（路由的键；`mosaic` 为空串表示判不出来，见 number_classify 的口径）
        "content_type": shape["content_type"],
        "mosaic": shape["mosaic"],
        # P0-1 逐字段溯源：界面要回答"这条简介/这张封面是谁给的"
        "field_sources": dict((meta or {}).get("field_sources") or {}),
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
