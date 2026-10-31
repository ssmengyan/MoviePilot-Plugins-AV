"""演员来源层：gFriends 头像索引 + javdb 演员页头像兜底（**只产出候选 URL**）。

本模块是演员刮削子系统的第一环（docs/AVHelper-演员刮削子系统方案.md §3），只负责
"拿到候选地址"：**不下载图片、不写库、不上传 Emby** —— 下载/校验/写侧都在下一环。

三块职责
--------
1. **gFriends 索引**（头像源顺序 `gfriends → javdb` 的第一顺位）：直连 GitHub 的
   `Filetree.json`（实测 6.5 MB / 51 个文件夹 / 107,678 条），解析成
   `{艺名: [{url, folder, file}, …]}`；落 `paths.meta_dir()/gfriends.json`（紧凑 + 原子写），
   7 天过期；进程内缓存 + 模块级单飞锁（并发调用只真拉一次）。
2. **匹配**：`jp` 精确 → 别名逐个 → 剥 `(無碼)/(无码)/(Uncensored)` 后缀再试。
   **绝不做模糊/子串匹配**（挂错人比没头像糟得多）。
3. **javdb 兜底**：沿用 javdb-cli 演员页的口径（`actor` 命令 JSON 里的 `entity.avatar_url`，
   即站点 `div.actor-avatar span.avatar` 的 background-image），丢弃 `actor_unknow` 占位；
   未登录判 `login_required` 并返回 `None`（**不抛**）。

实测依据（2026-10-21，走 NAS 软路由那条代理；坐标见 AGENTS.md §2）
------------------------------------------------------------
- **6.5 MB 正文几乎每次都被中途掐断**：`resp.read()` 一次性读，实测 3/3 全抛
  `http.client.IncompleteRead`（已读 6.20~6.46 MB / 6,503,467）。因此 `_http_fetch()`
  带 **Range 续传**：raw 支持 206（实测从 6,400,000 起精确取回余下 103,467 字节），
  jsdelivr 不支持（416，此时丢掉偏移整拉重来）。**完整性最终由 `parse_filetree()` 判定** ——
  截断的 JSON 解析不出条目，于是自动换下一个源。
- 值（实际文件名）**全部**带 `?t=时间戳`，约 53% 带 `AI-Fix-` 前缀，且**必须原样拼接**：
  路径里还有中日文（如 `z-ラグジュTV/黒瀬萌衣.jpg`），二次编码会把 `?t=` 编成 `%3Ft%3D`。
- 文件夹名形如 `0-Hand-Storage` / `7-S1` / `z-DMM(步)`；`z-*` 是低质/AI-Fix 源，排最后。
- 同一艺名在多个文件夹出现是常态（34,100 个艺名里 16,770 个有多候选），所以**全部保留**，
  由下一环按顺序试。
"""

from __future__ import annotations

import datetime
import http.client
import json
import os
import re
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import paths

# ---------------------------------------------------------------------------
# 契约常量（下一环按这些值对接，不要改）
# ---------------------------------------------------------------------------

#: 主源：GitHub raw（实测支持 Range 续传）。
GFRIENDS_URL = "https://raw.githubusercontent.com/gfriends/gfriends/master/Filetree.json"
#: 镜像：jsdelivr（实测约 8 秒整拉完，但**不支持 Range**）。
GFRIENDS_MIRROR = "https://cdn.jsdelivr.net/gh/gfriends/gfriends@master/Filetree.json"
#: 索引保质期（天）：过期后下一次 load_index() 会重新拉。
GFRIENDS_TTL_DAYS = 7
#: 落盘缓存文件名（在 paths.meta_dir() 下）。
CACHE_NAME = "gfriends.json"

#: 直链前缀：base/folder/file，folder 与 file 分别来自 Filetree 的层级与值。
GFRIENDS_RAW_BASE = "https://raw.githubusercontent.com/gfriends/gfriends/master/Content"

#: 认的图片扩展名（Filetree 里实测只有这两个：jpg 107,368 / png 310）。
IMAGE_EXTS = (".jpg", ".png")

UA = "AVHelper"
#: 单次拉取的超时（6.5 MB 走代理实测 8~14 秒，给足余量）。
DOWNLOAD_TIMEOUT = 120
#: 每个 URL 的尝试次数（含一次 Range 续传）。
DOWNLOAD_ATTEMPTS = 3

#: javdb 兜底：只要 entity 那一格，作品列表取最小页（省带宽；page/limit 同时决定失败日志键）。
JAVDB_PAGE = 1
JAVDB_LIMIT = 1

#: 站点占位头像的特征串（javdb 的"未知演员"占位图）。
_PLACEHOLDER = "actor_unknow"

#: 登录态判定的 marker：与 scraper.reason_from_text() **同一份口径**（那边是子进程
#: 只有一句中文说明时用的兜底判据）。这里不 import scraper：来源层要能独立加载。
_LOGIN_MARKERS = ("未登录", "需要登录", "请先登录", "登录已过期",
                  "login required", "not logged in", "sign in")

#: 名字尾部的"无码"标注：三种写法 + 半角/全角括号，可能叠用（X(無碼)(Uncensored)）。
_SUFFIX_RE = re.compile(r"\s*[（(]\s*(?:無碼|无码|uncensored)\s*[)）]\s*$", re.I)

# ---------------------------------------------------------------------------
# 进程内状态（单飞 + 缓存）
# ---------------------------------------------------------------------------

#: 单飞锁：load_index() 的**整个**加载/刷新都在锁内，并发调用只有第一个真去拉。
_LOCK = threading.RLock()
#: 进程内索引；None = 还没加载过（空索引用 {} 表示，两者不能混）。
_INDEX: Optional[Dict[str, List[Dict[str, Any]]]] = None
#: 当前索引的生成时间（ISO 串，与落盘缓存同一个值）。
_FETCHED_AT = ""
#: 当前索引的真实来源 URL（"" = 继承自进程内/落盘）。
_SOURCE = ""
#: 上一次刷新是否失败（失败仍保留旧缓存，index_status() 的 stale 靠它）。
_REFRESH_FAILED = False
#: "发生过一次采纳/刷新"的单调计数：等锁的线程靠它判断"别人已经刷过了，直接复用"。
_EPOCH = 0
#: 最近一次失败原因（键 = 请求名 / "index"）；last_error() 读它。
_LAST_ERROR: Dict[str, str] = {}
_LAST_ERROR_KEY = ""


def _clean_text(value: Any) -> str:
    """把任意值归一成去掉首尾空白的字符串（None / 空 → ""）。"""
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value: Any) -> int:
    """尽量转 int，转不了给 0（HTTP 头里的 Content-Length 可能是空）。"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _cache_path():
    """落盘缓存路径：paths.meta_dir() / CACHE_NAME。"""
    return paths.meta_dir() / CACHE_NAME


# ---------------------------------------------------------------------------
# 解析：Filetree.json → {艺名: [候选, …]}
# ---------------------------------------------------------------------------

def _as_json(payload: Any) -> Any:
    """把 bytes/str/已解析对象统一成 Python 对象；解析不了给 {}（**不抛**）。"""
    if isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload).decode("utf-8", "replace")
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (ValueError, TypeError):
            return {}
    return payload if isinstance(payload, (dict, list)) else {}


def _split_ext(name: Any) -> Tuple[str, str]:
    """三上悠亚.png → ("三上悠亚", ".png")；没有扩展名时扩展名给空串。"""
    text = _clean_text(name)
    base, dot, ext = text.rpartition(".")
    if not dot:
        return text, ""
    return base.strip(), ("." + ext.strip().lower()) if ext.strip() else ""


def _folder_key(folder: Any) -> Tuple[bool, str]:
    """文件夹排序键：z-*（低质 / AI-Fix 源）**排最后**，其余按名字不区分大小写排。"""
    text = _clean_text(folder).lower()
    return (text.startswith("z-"), text)


def parse_filetree(payload: Any) -> Dict[str, List[Dict[str, Any]]]:
    """解析 Filetree.json，返回 {艺名: [{"url","folder","file"}, …]}。

    :param payload: 原始 bytes / str（也容忍已解析的 dict）

    四条口径（都是实测数据驱动的）：

    1. **同一艺名保留全部候选**：16,770/34,100 个艺名出现在多个文件夹里（amane 只留第一个，
       我们保留候选列表，运行时逐个试）；
    2. **候选按文件夹名排序，z-* 排最后**：z-* 是低质 / AI-Fix 源（实测 29,252 条）；
    3. **扩展名只认 .jpg/.png（不分大小写）**：键和值都要过（值带 ?t= 时先剥查询串）；
    4. **URL 原样拼接** base/folder/file，file 里的 ?t= 与 AI-Fix- 前缀、以及中日文
       一律不编码（二次编码会让 raw 404）。

    截断 / 损坏的正文返回空字典（调用方据此换源），**绝不抛异常**。
    """
    data = _as_json(payload)
    root: Any = None
    if isinstance(data, dict):
        # 正常形状是 {"Content": {...}, "Information": {...}}；没有 Content 壳时
        # 把顶层当 folder→files（结构探测，而不是猜版本）。
        root = data.get("Content") if isinstance(data.get("Content"), dict) else data
    if not isinstance(root, dict):
        return {}

    index: Dict[str, List[Dict[str, Any]]] = {}
    for folder in sorted(root.keys(), key=_folder_key):
        files = root.get(folder)
        if not isinstance(files, dict):
            continue
        for key, value in files.items():
            name, ext = _split_ext(key)
            if not name or ext not in IMAGE_EXTS:
                continue
            filename = _clean_text(value)
            if not filename:
                continue
            # 值里的扩展名也要过一遍（先剥 ?t= 查询串再判）
            if _split_ext(filename.split("?", 1)[0])[1] not in IMAGE_EXTS:
                continue
            item = {
                "url": "%s/%s/%s" % (GFRIENDS_RAW_BASE, _clean_text(folder), filename),
                "folder": _clean_text(folder),
                "file": filename,
            }
            bucket = index.setdefault(name, [])
            if not any(old["folder"] == item["folder"] and old["file"] == item["file"]
                       for old in bucket):
                bucket.append(item)
    return index


# ---------------------------------------------------------------------------
# 匹配
# ---------------------------------------------------------------------------

def _strip_suffix(name: Any) -> str:
    """剥名字尾部的 (無碼) / (无码) / (Uncensored)（半角全角都认，可叠用）。"""
    text = _clean_text(name)
    previous = None
    while text and text != previous:
        previous = text
        text = _SUFFIX_RE.sub("", text).strip()
    return text


def match_candidates(index: Dict[str, List[Dict[str, Any]]],
                     names: Iterable[Any]) -> List[Dict[str, Any]]:
    """按 jp → 别名 的顺序做**精确**匹配，返回第一个命中的候选列表。

    :param index: parse_filetree() 的产物（或 load_index() 的返回值）
    :param names: 待试名字，**有序**（调用方把 jp 放第一个，其后是别名）
    :return: [{"name","url","folder","file"}, …]，没命中给空列表

    - name 是**命中的索引键**（靠剥后缀命中时就是剥过的那写法），调用方据此知道靠哪个写法命中；
    - 两轮：① 全部名字精确试一遍 ② 剩下的再剥后缀试 —— 精确命中永远优先于剥后缀命中；
    - **只做相等比较**：不做模糊、不做子串、不做归一化（挂错人比没头像糟得多）。
    """
    wanted: List[str] = []
    for raw in names or []:
        text = _clean_text(raw)
        if text and text not in wanted:
            wanted.append(text)
    if not wanted or not isinstance(index, dict):
        return []

    for strip in (False, True):
        for name in wanted:
            key = _strip_suffix(name) if strip else name
            if not key or (strip and key == name):
                continue                      # 剥不掉就别重复问一次
            rows = index.get(key)
            if rows:
                return [{"name": key, "url": _clean_text(row.get("url")),
                         "folder": _clean_text(row.get("folder")),
                         "file": _clean_text(row.get("file"))}
                        for row in rows if isinstance(row, dict)]
    return []


# ---------------------------------------------------------------------------
# 落盘缓存（紧凑 + 原子写，口径同 imgproxy._store）
# ---------------------------------------------------------------------------

def _write_cache(items: Dict[str, List[Dict[str, Any]]], fetched_at: str, source: str) -> None:
    """写 {fetched_at, source, items} 紧凑 JSON；**先写 .tmp 再 os.replace**。

    失败不影响本次返回（缓存只是加速与"重启后不用重拉"，不是正确性的一部分）。
    """
    path = _cache_path()
    payload = json.dumps({"fetched_at": fetched_at, "source": source, "items": items},
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp = "%s.%d.%d.tmp" % (str(path), os.getpid(), threading.get_ident())
    try:
        os.makedirs(os.path.dirname(str(path)), exist_ok=True)
        with open(tmp, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, str(path))
    except (OSError, ValueError):
        try:
            os.remove(tmp)
        except OSError:
            pass


def _read_cache() -> Tuple[Dict[str, List[Dict[str, Any]]], str, str]:
    """读落盘缓存 → (items, fetched_at, source)；没有 / 损坏 / 形状不对都给空。"""
    try:
        with open(str(_cache_path()), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}, "", ""
    if not isinstance(data, dict):
        return {}, "", ""
    items = data.get("items")
    if not isinstance(items, dict) or not items:
        return {}, "", ""
    clean: Dict[str, List[Dict[str, Any]]] = {}
    for name, rows in items.items():
        if isinstance(rows, list) and rows:
            clean[_clean_text(name)] = [row for row in rows if isinstance(row, dict)]
    if not clean:
        return {}, "", ""
    return clean, _clean_text(data.get("fetched_at")), _clean_text(data.get("source"))


# ---------------------------------------------------------------------------
# 时间 / 状态
# ---------------------------------------------------------------------------

def _iso(timestamp: float) -> str:
    """时间戳 → ISO 串（UTC，秒级；与 datetime.fromisoformat 对称）。"""
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat(
        timespec="seconds")


def _stamp(text: str) -> float:
    """ISO 串 → 时间戳；解析不了给 0.0（= 很旧）。"""
    try:
        return datetime.datetime.fromisoformat(_clean_text(text)).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _expired(fetched_at: str) -> bool:
    """缓存是否已过期（没有时间戳也算过期 → 需要拉取）。"""
    stamp = _stamp(fetched_at)
    if stamp <= 0:
        return True
    age = datetime.datetime.now(datetime.timezone.utc).timestamp() - stamp
    return age > GFRIENDS_TTL_DAYS * 86400


def _adopt(items: Dict[str, List[Dict[str, Any]]], fetched_at: str, source: str,
           failed: bool) -> None:
    """把一份索引装进进程内状态并推进 _EPOCH（等锁的线程据此直接复用）。"""
    global _INDEX, _FETCHED_AT, _SOURCE, _REFRESH_FAILED, _EPOCH
    _INDEX = items
    _FETCHED_AT = fetched_at
    _SOURCE = source
    _REFRESH_FAILED = bool(failed)
    _EPOCH += 1


def _note_error(key: str, reason: str) -> None:
    """记一条失败原因（条目有上限，last_error() 读它）。"""
    global _LAST_ERROR_KEY
    if len(_LAST_ERROR) > 200:
        _LAST_ERROR.clear()
    _LAST_ERROR[key] = _clean_text(reason)
    _LAST_ERROR_KEY = key


def last_error(name: Any = "") -> str:
    """最近一次失败原因（空串 = 没失败）。

    契约里 fetch_javdb_avatar() 失败只返回 None（不抛），登录态过期这类信息需要一个出口
    —— 就是这里。name 留空取最近一次；索引刷新失败记在 "index" 上。
    javdb 侧取值：login_required / no_avatar / unexpected；索引侧是中文说明。
    """
    key = _clean_text(name)
    if key:
        return _LAST_ERROR.get(key, "")
    return _LAST_ERROR.get(_LAST_ERROR_KEY, "") if _LAST_ERROR_KEY else ""


def index_status() -> Dict[str, Any]:
    """索引状态：{"count", "fetched_at", "stale", "source"}。

    - count：艺名条目数（不是候选总数）；
    - fetched_at：索引生成时间（ISO/UTC 串；没有索引时空串）；
    - stale：**刷新失败**或**已过期**（> GFRIENDS_TTL_DAYS 天）→ True；
    - source：这份索引的真实来源 URL（GFRIENDS_URL / GFRIENDS_MIRROR；从落盘缓存继承的也算）。

    进程内还没有索引时读一次落盘缓存（**不联网**），所以页面能在 load_index() 之前就显示。
    """
    global _INDEX, _FETCHED_AT, _SOURCE
    with _LOCK:
        if _INDEX is None:
            items, fetched_at, source = _read_cache()
            if items:
                _INDEX, _FETCHED_AT, _SOURCE = items, fetched_at, source
        count = len(_INDEX or {})
        return {
            "count": count,
            "fetched_at": _FETCHED_AT,
            "stale": bool(_REFRESH_FAILED) or _expired(_FETCHED_AT),
            "source": _SOURCE,
        }


# ---------------------------------------------------------------------------
# 拉取（主源 → 镜像，Range 续传）
# ---------------------------------------------------------------------------

def _open(url: str, headers: Dict[str, str], proxy: str, timeout: int):
    """按代理设置打开一个 URL（proxy 留空 = 直连，不套一层空代理）。"""
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    return opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)


def _http_fetch(url: str, proxy: str = "", timeout: int = DOWNLOAD_TIMEOUT,
                attempts: int = DOWNLOAD_ATTEMPTS) -> bytes:
    """拉一个 URL 的字节；正文被中途掐断时用 Range 续传接上。**不抛异常**。

    为什么必须续传：raw 的 6.5 MB 正文经代理实测几乎每次都被掐（IncompleteRead，
    已读 6.20~6.46 MB / 6,503,467）。raw 支持 206 续传（实测一次补齐余下 103,467 字节），
    jsdelivr 不支持（416 → 丢掉偏移整拉重来）。

    :return: 拿到的字节（可能不完整）；一个字节都没拿到时空 bytes。**完整性由调用方用
        parse_filetree() 判**（截断的 JSON 解析不出条目）。
    """
    blob = b""
    for _attempt in range(max(1, _to_int(attempts) or 1)):
        headers = {"User-Agent": UA}
        if blob:
            headers["Range"] = "bytes=%d-" % len(blob)
        try:
            with _open(url, headers, proxy, timeout) as resp:
                status = _to_int(getattr(resp, "status", 200)) or 200
                length = _to_int(resp.headers.get("Content-Length"))
                if status == 206 and blob:
                    want = len(blob) + length if length else 0
                else:
                    blob, want = b"", length
                broken = False
                try:
                    chunk = resp.read()
                except http.client.IncompleteRead as partial:
                    chunk, broken = (partial.partial or b""), True
                blob += chunk or b""
                if not broken or (want and len(blob) >= want):
                    return blob
        except urllib.error.HTTPError as error:
            if error.code == 416:          # 服务器不认续传（实测 jsdelivr）→ 整拉重来
                blob = b""
            continue
        except Exception:                  # 超时 / 代理不可达 / TLS：下一轮
            continue
    return blob


def _source_host(url: str) -> str:
    """URL → host（只给日志/失败原因用）。"""
    try:
        return str(urllib.parse.urlparse(url).hostname or url)
    except Exception:                                              # pragma: no cover - 防御
        return str(url)


def _acquire(proxy: str, fetch: Any) -> Tuple[Dict[str, List[Dict[str, Any]]], str, str]:
    """按「主源 → 镜像」拉一次并解析，返回 (索引, 实际来源, 失败原因)。

    fetch 可注入（形如 fetch(url, proxy="") -> bytes），单测靠它顶掉网络。
    "拉到了但解析不出条目"（截断）与"抛异常"同样算这一次失败，继续试下一个源。
    """
    problems: List[str] = []
    for url in (GFRIENDS_URL, GFRIENDS_MIRROR):
        try:
            blob = fetch(url, proxy=proxy) if callable(fetch) else _http_fetch(url, proxy)
        except Exception as error:
            problems.append("%s：%s" % (_source_host(url), type(error).__name__))
            continue
        items = parse_filetree(blob)
        if items:
            return items, url, ""
        problems.append("%s：正文解析不出条目（可能被截断）" % _source_host(url))
    return {}, "", "；".join(problems) or "拉取失败"


# ---------------------------------------------------------------------------
# 公开接口：加载 / 刷新
# ---------------------------------------------------------------------------

def load_index(*, proxy: str = "", force: bool = False,
               fetch: Any = None) -> Dict[str, List[Dict[str, Any]]]:
    """拿 gFriends 索引（进程内缓存 → 落盘缓存 → 真实拉取），**失败也返回可用索引**。

    :param proxy: 拉取走的代理（插件配置里那份；留空 = 直连）
    :param force: 跳过 7 天 TTL 强制刷新（失败仍保留旧索引）
    :param fetch: 注入的抓取函数（fetch(url, proxy="") -> bytes）；单测用，默认走 _http_fetch
    :return: {艺名: [{"url","folder","file"}, …]}；一次都没拉到过时是 {}（**不抛异常**）

    单飞：整个加载/刷新在模块级锁内，并发调用只有第一个真去拉 6.5 MB，其余等它拉完直接复用；
    force=True 也一样（等锁期间别人刷过了就不再刷第二遍）。
    """
    seen = _EPOCH
    with _LOCK:
        if _INDEX is not None and _EPOCH != seen:
            return _INDEX                      # 等锁期间别人刚刷完 → 直接复用
        if _INDEX is not None and not force and not _expired(_FETCHED_AT):
            return _INDEX
        return _load_locked(proxy, force, fetch)


def _load_locked(proxy: str, force: bool, fetch: Any) -> Dict[str, List[Dict[str, Any]]]:
    """load_index() 的锁内主体：定基线（内存 → 落盘）→ 必要时拉取 → 采纳/保旧。"""
    items: Optional[Dict[str, List[Dict[str, Any]]]] = _INDEX
    fetched_at, source = _FETCHED_AT, _SOURCE
    if items is None:
        disk_items, disk_at, disk_source = _read_cache()
        if disk_items:
            items, fetched_at, source = disk_items, disk_at, disk_source
    if items is not None and not force and not _expired(fetched_at):
        _adopt(items, fetched_at, source, failed=False)
        return _INDEX

    fresh, used, problem = _acquire(proxy, fetch)
    if fresh:
        stamp = _iso(datetime.datetime.now(datetime.timezone.utc).timestamp())
        _adopt(fresh, stamp, used, failed=False)
        _write_cache(fresh, stamp, used)
        return _INDEX

    # 失败：**保留旧缓存继续可用**，只把 stale 标上（拉取失败绝不能让调用方吃异常）
    _note_error("index", problem)
    _adopt(items or {}, fetched_at, source, failed=True)
    return _INDEX


def refresh_index(*, proxy: str = "", fetch: Any = None) -> Dict[str, Any]:
    """强制刷新索引，返回刷新后的 index_status()（失败时 stale=True 且索引仍是旧的）。"""
    load_index(proxy=proxy, force=True, fetch=fetch)
    return index_status()


def reset_cache() -> None:
    """测试用：清掉进程内索引与"刷新过"的标记（_EPOCH 保持单调，不复位）。

    _EPOCH 不复位：它只是"发生过一次采纳"的计数器，复位会让正在等锁的线程误判成
    "没人刷过"从而重复拉一次。落盘缓存不在这里删（那是数据，不是进程状态）。
    """
    global _INDEX, _FETCHED_AT, _SOURCE, _REFRESH_FAILED, _LAST_ERROR_KEY
    with _LOCK:
        _INDEX = None
        _FETCHED_AT = ""
        _SOURCE = ""
        _REFRESH_FAILED = False
        _LAST_ERROR.clear()
        _LAST_ERROR_KEY = ""


# ---------------------------------------------------------------------------
# javdb 演员页兜底
# ---------------------------------------------------------------------------

def _is_placeholder(url: str) -> bool:
    """是不是站点的占位头像（actor_unknow）—— 占位图一律当"没有头像"。"""
    return _PLACEHOLDER in _clean_text(url).lower()


def _login_required(text: Any) -> bool:
    """失败说明是不是登录态问题（口径同 scraper.reason_from_text()）。"""
    low = _clean_text(text).lower()
    return bool(low) and any(marker in low for marker in _LOGIN_MARKERS)


def _client_error(client: Any, key: str) -> str:
    """问 javdb client 要这次调用的失败说明（拿不到给空串）。"""
    getter = getattr(client, "last_error", None)
    if not callable(getter):
        return ""
    try:
        return _clean_text(getter(key))
    except Exception:                                              # pragma: no cover - 防御
        return ""


def fetch_javdb_avatar(client: Any, name: Any,
                       *, proxy: str = "") -> Optional[Dict[str, Any]]:
    """javdb 演员页兜底：返回 {"name","url","source","javdb_actor_id"} 或 None。

    :param client: client.JavdbClient（有 actor(name, page, limit) 与 last_error(key)）；
        也接受只实现 actor(name) 的替身
    :param name: 演员名（javdb 站点写法，例如 葵つかさ）
    :param proxy: 源层统一的代理参数；javdb 的代理由 JavdbClient 自己持有（client.proxy），
        这里不重复设置 —— 留这个参数只为让上游按同一形状调用各个源
    :return: 有可用头像时给候选；调不通 / 没有头像 / 占位图 / 未登录一律 None（**不抛**）

    解析口径沿用现有链：javdb-cli 的 actor 命令已经把 div.actor-avatar span.avatar 的
    background-image 解析成 entity.avatar_url，这里只做取值 + 占位图过滤。
    """
    text = _clean_text(name)
    if not text or client is None:
        return None
    fetcher = getattr(client, "actor", None)
    if not callable(fetcher):
        return None

    limit = JAVDB_LIMIT
    try:
        data = fetcher(text, page=JAVDB_PAGE, limit=limit)
    except TypeError:                     # 只收一个位置参数的替身（单测/老实现）
        limit = 30
        try:
            data = fetcher(text)
        except Exception:
            _note_error(text, "unexpected")
            return None
    except Exception:
        _note_error(text, "unexpected")
        return None

    entity: Any = data.get("entity") if isinstance(data, dict) else None
    if not isinstance(entity, dict):
        entity = data if isinstance(data, dict) else {}
    url = _clean_text(entity.get("avatar_url") or entity.get("avatar"))
    if url and not _is_placeholder(url):
        _LAST_ERROR.pop(text, None)
        return {"name": text, "url": url, "source": "javdb",
                "javdb_actor_id": _clean_text(entity.get("id"))}

    # 没有可用头像：区分"未登录"（要让用户去更新 cookie）与"站点就是没有头像"
    error_text = _client_error(client, "actor:%s:p%d:l%d" % (text, JAVDB_PAGE, limit))
    _note_error(text, "login_required" if _login_required(error_text) else "no_avatar")
    return None
