"""AVHelper 演员刮削流水线（0.9.0 演员线 S3）：选图 → 下载 → 校验 → 上传 Emby Person。

依据：`docs/AVHelper-演员刮削子系统方案.md` §4（任务与状态）、§5（头像流水线与写侧）。

公开接口
--------

```python
sync_actor_avatars(store, emby_client, *, limit=0, dry_run=True, namemap_mod=None,
                   opts=None, names=None, force=False) -> dict   # 0.8.1 兼容壳（老形状）
run_actor_scrape(store, emby_client=None, *, actor_ids=None, persons=None, names=None,
                 dry_run=True, force=False, limit=0, proxy="", opts=None) -> dict
scrape_actor(store, emby_client, actor, *, force=False, dry_run=False, proxy="",
             opts=None) -> dict
queue_tick(store, emby_client=None, *, batch=20, proxy="", opts=None) -> dict
crop_avatar(store, actor=None, *, actor_id=None, rect=None, ratio=(3, 4), opts=None,
            emby_client=None) -> dict
upload_avatar(store, actor, raw, *, source="manual", opts=None, emby_client=None) -> dict
```

纪律（每条都对应方案里的一句话，别在调用点上重新发明）
------------------------------------------------------

1. **选图顺序** `gfriends` → `javdb`（§3 的 `image_sources`）。gFriends 命中就不问
   javdb；两边都没有 → `action='skip'` + `reason='no_avatar'`，**不是错误**（§5.1）。
2. **下载** 走 `scraper._image_bytes()`：优先 `imgproxy.fetch()`（Referer 与 XOR 解包都在
   它那里），失败**重试一次**；`imgproxy` 缺失时退回裸取，并对裸取结果过
   `is_image_bytes()` 魔数门（0.8.1 原口径：XOR 包装与非图片响应绝不能喂给 Emby）。
   ⚠️ gFriends 的直链是"中日文路径 + `?t=` 时间戳"的形状，`urllib` 遇到非 ASCII URL 直接
   `UnicodeEncodeError`，所以**交给 imgproxy 之前**先过 `_encode_url()`（只编路径段、查询串保留）。
3. **校验** 取真实尺寸（复用 `imgproxy` 里已装好的 Pillow，不引新依赖）后**最长边 < 200px
   丢弃并试下一个候选，最多试 3 个**；字节 > 5MB 丢弃。⚠️ 尺寸取不到（本机无 Pillow /
   解码失败）时**放行**：imgproxy 已经验过它是一张图，"量不出尺寸"不该成为丢掉头像的理由。
   **下载全失败才算 failed**；只是候选不达标 → 仍是 `no_avatar`（skip）。
4. **落库 + 上传** 选中合规字节即 `store.actor_set_images()` **前插成 `images[0]`**
   —— 演员库的「有图」与 `crop-avatar` 的"当前主图"都只读这一格（0.9.0 真机缺口：只传了
   Emby、库里恒 `[]`）；`person_missing` 也记候选，只是不传 Emby。然后
   `find_person(person)` → 无 `ImageTags.Primary`（或 force 点名）→
   `upload_image(person_id, "Primary", raw)`；可选合并写 `ProviderIds.JavDB`
   （沿用 `person_provider_ids` 开关）。找不到 Person → `person_missing`，
   **记 skip 不计失败**（影片还没刮过是必然过渡态）。
5. **锁** `locked_fields` 含 `"images"` → 只补资料、绝不换图（本模块只管头像，
   所以直接 `reason='locked'`）。
6. **记账** `scrape_log.source_name='actor'`，`status ∈ ok/skipped/error`（复用
   `scraper._log_source()`；source 与 reason 一起落库才能按原因分组）。
7. **单飞** 模块级 `threading.Lock`：`run_actor_scrape()` / `queue_tick()` 并发时第二个
   直接回 `{"ok": False, "reason": "busy", ...}`。
8. **隔离** 单个演员失败只记该行，不影响整批；上传在 store 事务外做。
9. **性别** 只处理女演员：`gender == 1` 硬排除；`gender is None` **保守保留**
   （与 0.8.1 的 existing 口径一致 —— 本库还有一批存量行没有 gender，丢了就是
   "女优头像设置还是不行"）。

并行施工期的两个兄弟模块（按契约对接，缺失即降级）
--------------------------------------------------

`actor_sources`（S2）与 `store` 的 `actor_*`（S1）本模块**一律函数体内取用 + 兜住
异常**：

- `actor_sources` 缺失/半成品 → **只剩 javdb 一个源**，流水线照常跑（不会 ImportError）；
- `store` 没有 `actor_*` → 不记账到演员行（`scrape_log` 照记）；兼容壳那条路径
  用的是 `meta.actors_json` 聚合，**根本不碰 actor 表**；
- gFriends 索引还没建时**不阻塞本轮**，而是起一个**守护线程**去 `actor_sources.load_index()`
  （方案 §3：「启动不阻塞，首次使用时在后台线程加载，单飞」）：本轮照旧记 `index_stale` 并回落
  javdb，下一轮就能用上整图。线程由模块级标志串行化（起来置位、结束/失败一律清位），S2 的
  `load_index()` 自身还有单飞锁与 7 天 TTL，重复起不会重复拉。要**同步**等它拉完就传
  `opts={"gfriends_refresh": True}`。

`force` 的两套口径（别混）
--------------------------------

- `opts['avatar_force']`：0.8.1 的**全量**覆盖（`/scrape/avatars` 端点就按它传，老行为不变）；
- `force=` 形参：**只对点名**的演员生效（`actor_ids` / `persons` / `names`），批量挑行
  时忽略 —— 方案 P1 验收「`force` 只覆盖点名演员」。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

from app.sdk.logging import logger

from . import scraper

# 可选依赖：S2 的 `actor_sources` 可能还没落地 / 正在被写（半成品抛的可能是 SyntaxError，
# 所以照 scraper 的口径捕 `Exception`，别把"某个可选能力缺失"放大成"整条线 import 失败"）。
try:                                    # pragma: no cover - 取决于并行施工进度
    from . import actor_sources
except Exception as _error:             # noqa: BLE001 - 故意的
    logger.warning(f"AVHelper actor_sync：actor_sources 不可用，头像只剩 javdb 源：{_error}")
    actor_sources = None                # type: ignore[assignment]

# 尺寸探测要**真**的 imgproxy（Pillow 的延迟导入装在那里）：不能用 `scraper.imgproxy` —— 那是
# 单测的注入点（`monkeypatch.setattr(scraper, "imgproxy", FakeProxy)`），拿它探尺寸会炸。
try:                                    # pragma: no cover
    from . import imgproxy
except Exception as _error:             # noqa: BLE001 - 故意的
    logger.warning(f"AVHelper actor_sync：imgproxy 不可用，头像不做尺寸校验：{_error}")
    imgproxy = None                     # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: `scrape_log.source_name`（排障与自检页按它分组）
SCRAPE_LOG_SOURCE = "actor"

#: 单个演员最多试几个候选（方案 §5.3：最长边不够就换下一个，最多 3 个）
DEFAULT_MAX_CANDIDATES = 3
#: 候选图最长边下限（px）：不够就丢（javdb 缩略图 100×100 会被这条挡住）
DEFAULT_MIN_EDGE = 200
#: 候选图字节上限（5 MB）
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
#: `actor_due()` 不给 limit 时的默认批量
DEFAULT_DUE_LIMIT = 20
#: `queue_tick()` 两位演员之间的间隔（秒）：方案 §4 的"间隔 ≥2s"
DEFAULT_QUEUE_INTERVAL = 2.0

#: 公开 item 的键（契约形状）
ITEM_KEYS = ("actor_id", "person", "name", "action", "reason", "url", "source",
             "bytes", "w", "h")

#: 单飞锁（`run_actor_scrape()` / `queue_tick()` 共用；**不可重入**：`queue_tick()` 走内部
#: `_run()` 而不是再调 `run_actor_scrape()`，否则自己会把自己挡在外面）
_LOCK = threading.Lock()

#: gFriends 索引"后台加载中"的标志（方案 §3：首次使用时后台加载、启动不阻塞）。
#: 线程起来置位、结束/失败**一律清位** —— 清位是为了"这次拉失败"之后下一轮还能再试，不能永久卡死。
_INDEX_LOCK = threading.Lock()
_INDEX_KICKED = False

#: `(無碼)` / `(无码)` / `(Uncensored)` 后缀（方案 §3：匹配前先剥离再试一次）
_UNCENSORED = re.compile(r"\s*[（(]\s*(?:無碼|无码|無修正|uncensored)\s*[)）]\s*$", re.I)


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _opt(options: Optional[Dict[str, Any]], name: str, default: Any = None) -> Any:
    """取选项：走 `scraper._opt()`（同一条"调用方 → DEFAULT_OPTS → default"口径）。"""
    return scraper._opt(options, name, default)


def _as_list(value: Any) -> List[Any]:
    """JSON 列 / 列表 / 元组 → 列表（store 的解析副本与原始串两种输入都认）。"""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    text = str(value or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _strip_uncensored(text: Any) -> str:
    """剥掉 `(無碼)/(无码)/(Uncensored)` 后缀（只影响 gFriends 文件名匹配）。"""
    return _UNCENSORED.sub("", str(text or "")).strip()


def _person_of(row: Dict[str, Any]) -> str:
    """一行演员 → Emby Person 精确名（`person` 优先；兼容壳的行里 `name` 就是规范名）。"""
    return (scraper._clean_text((row or {}).get("person"))
            or scraper._clean_text((row or {}).get("name")))


def _display_of(row: Dict[str, Any]) -> str:
    """展示名（界面/日志用；没有就退化到规范名）。"""
    return (scraper._clean_text((row or {}).get("name"))
            or scraper._clean_text((row or {}).get("display"))
            or _person_of(row))


def _gender_of(row: Dict[str, Any]) -> Optional[int]:
    """`gender` 归一：0 女 / 1 男 / None 未知（缺字段与脏值都归 None —— 不猜）。"""
    gender = (row or {}).get("gender")
    if gender in (None, ""):
        return None
    try:
        return int(gender)
    except (TypeError, ValueError):
        return None


def _image_size(raw: bytes) -> Tuple[int, int]:
    """取图片真实尺寸（宽, 高）；取不到回 `(0, 0)`（**不抛异常**）。

    复用 `imgproxy` 里已装好的 Pillow（`_pillow_image()` 就是那个延迟导入 + 缓存的入口）：
    本模块不引新依赖，也不为"量个尺寸"再写一套图片头解析。
    """
    module = imgproxy
    loader = getattr(module, "_pillow_image", None) if module is not None else None
    if not callable(loader):
        return 0, 0
    Image = loader()
    if Image is None:                   # 本机没有 Pillow → 尺寸未知
        return 0, 0
    try:
        with Image.open(io.BytesIO(bytes(raw or b""))) as img:
            return int(img.size[0]), int(img.size[1])
    except Exception:                   # noqa: BLE001 - 半张图/坏图/不认识的格式
        return 0, 0


def _log(store: Any, status: str, key: str, reason: str = "", error: str = "") -> None:
    """往 `scrape_log` 记一条演员行（`status ∈ ok/skipped/error`；store 不可用时静默）。"""
    scraper._log_source(store, SCRAPE_LOG_SOURCE, status, key, 0,
                        str(error or "")[:500], reason=str(reason or ""))


def _mark(store: Any, actor_id: Any, ok: bool, reason: str = "") -> None:
    """把这一次的结果记到演员行上（成功重置退避 / 失败排下一档）；store 没这套 API 就跳过。

    `actor_id <= 0`（兼容壳的行来自 `meta.actors_json`，没有 actor 主键）一律不动 ——
    那条路径不需要 actor 表也能工作，这是并行施工期最关键的降级点。
    """
    key = scraper._to_int(actor_id)
    if key <= 0:
        return
    name = "actor_mark_ok" if ok else "actor_mark_failed"
    func = getattr(store, name, None)
    if not callable(func):
        return
    try:
        if ok:
            func(key)
        else:
            func(key, reason=str(reason or "failed")[:200])
    except Exception as error:          # noqa: BLE001 - 记账失败不能连累这一位演员的结论
        logger.warning(f"AVHelper {name}({key}) 失败：{type(error).__name__}: {error}")


# ---------------------------------------------------------------------------
# 选图（gfriends → javdb）
# ---------------------------------------------------------------------------

def _match_names(row: Dict[str, Any]) -> List[str]:
    """给 gFriends 精确匹配用的候选名（`jp` 优先，再展示名/中文名/规范名/别名）。

    每个名字再给一份"剥掉 `(無碼)` 后缀"的变体（方案 §3）。**只做整串相等**，不做模糊/
    子串 —— 挂错人比没有头像糟得多。
    """
    out: List[str] = []
    for key in ("jp", "name", "zh", "person", "display"):
        text = scraper._clean_text((row or {}).get(key))
        for one in (text, _strip_uncensored(text)):
            if one and one not in out:
                out.append(one)
    for alias in _as_list((row or {}).get("aliases")):
        text = scraper._clean_text(alias)
        for one in (text, _strip_uncensored(text)):
            if one and one not in out:
                out.append(one)
    return out


def _kick_index_load(module: Any, proxy: Any) -> bool:
    """索引没建好时**起一个守护线程**去拉 gFriends 索引，**本轮不等待**（方案 §3）。

    为什么不能同步拉：6.5 MB 走 GitHub 实测 9 秒起，阻塞式预加载会把第一次 tick / 第一次手动
    刮削直接卡住。为什么要个标志：`queue_tick()` 每 15 分钟一轮、手动批量一次几十位演员，
    没有标志就是几十个线程同时去拉同一个文件。`load_index()` 自己也有单飞锁与 7 天 TTL，所以
    最坏情况只是白起一个立即返回的线程。

    标志**在线程结束时（成功或失败）清位**：这次拉失败不该让索引永久卡在"没人会再拉"的状态。
    """
    global _INDEX_KICKED
    loader = getattr(module, "load_index", None)
    if not callable(loader):
        return False
    with _INDEX_LOCK:
        if _INDEX_KICKED:
            return False
        _INDEX_KICKED = True

    def worker() -> None:
        global _INDEX_KICKED
        try:
            loader(proxy=str(proxy or ""))
        except Exception as error:      # noqa: BLE001 - 6.5 MB 拉失败绝不能把 tick 打挂
            logger.warning(f"AVHelper gfriends 索引后台加载失败（下一轮再试）："
                           f"{type(error).__name__}: {error}")
        finally:
            with _INDEX_LOCK:
                _INDEX_KICKED = False

    thread = threading.Thread(target=worker, name="avhelper-gfriends-index", daemon=True)
    try:
        thread.start()
    except Exception as error:          # pragma: no cover - 起不了线程（资源耗尽）
        logger.warning(f"AVHelper gfriends 索引后台线程起不来：{type(error).__name__}: {error}")
        with _INDEX_LOCK:
            _INDEX_KICKED = False
        return False
    return True


def _gfriends_candidates(row: Dict[str, Any], proxy: str,
                         options: Dict[str, Any]) -> Tuple[List[Dict[str, str]], bool]:
    """gFriends 候选（按文件夹排序、同名多候选都在）+ 索引是否"陈旧/不可用"。"""
    module = actor_sources
    if module is None or not bool(_opt(options, "gfriends", True)):
        return [], False
    names = _match_names(row)
    if not names:
        return [], False
    try:
        status = module.index_status() or {}
    except Exception as error:          # noqa: BLE001 - 索引状态读不到不该拦住头像
        logger.warning(f"AVHelper gfriends 索引状态读取失败：{type(error).__name__}: {error}")
        _kick_index_load(module, proxy)
        return [], True
    status = status if isinstance(status, dict) else {}
    count = scraper._to_int(status.get("count"))
    if count <= 0 and not bool(_opt(options, "gfriends_refresh", False)):
        # 索引还没建：**后台线程拉，本轮不等待**（方案 §3「启动不阻塞」），照旧标 index_stale
        # 并回落 javdb —— 下一轮 tick 就能用上整图。
        _kick_index_load(module, proxy)
        return [], True
    try:
        index = module.load_index(proxy=str(proxy or "")) or {}
        hits = module.match_candidates(index, names) or []
    except Exception as error:          # noqa: BLE001 - 拉索引失败保留旧缓存 / 回落 javdb
        logger.warning(f"AVHelper gfriends 索引不可用，回落 javdb：{type(error).__name__}: {error}")
        return [], True
    out: List[Dict[str, str]] = []
    for hit in hits:
        url = str((hit or {}).get("url") or "").strip()
        if url and all(url != one["url"] for one in out):
            out.append({"url": url, "source": "gfriends"})
    stale = bool(status.get("stale")) or count <= 0
    return out, stale


def _javdb_candidates(row: Dict[str, Any], proxy: str,
                      options: Dict[str, Any]) -> List[Dict[str, str]]:
    """javdb 候选：行自带的 `avatar`（存量 `meta.actors_json`）/ `images` 里的 javdb 源 /
    有 `javdb_actor_id` 且注入了 javdb 客户端时现抓（`actor_sources.fetch_javdb_avatar()`）。"""
    if not bool(_opt(options, "javdb_avatar", True)):
        return []
    out: List[Dict[str, str]] = []

    def add(url: Any) -> None:
        text = str(url or "").strip()
        if text and all(text != one["url"] for one in out):
            out.append({"url": text, "source": "javdb"})

    add((row or {}).get("avatar"))
    add((row or {}).get("avatar_url"))
    for image in _as_list((row or {}).get("images")):
        if not isinstance(image, dict):
            continue
        source = str(image.get("source") or "")
        if source and source != "javdb":
            continue
        add(image.get("url"))
    if out or not str((row or {}).get("javdb_actor_id") or ""):
        return out
    module = actor_sources
    fetcher = getattr(module, "fetch_javdb_avatar", None) if module is not None else None
    client = options.get("javdb_cli") or options.get("cli")
    names = _match_names(row)
    if not callable(fetcher) or client is None or not names:
        return out
    try:
        hit = fetcher(client, names[0], proxy=str(proxy or ""))
    except Exception as error:          # noqa: BLE001 - javdb 兜底失败不算错误
        logger.warning(f"AVHelper javdb 头像抓取失败（{names[0]}）：{type(error).__name__}: {error}")
        return out
    if isinstance(hit, dict):
        add(hit.get("url"))
    return out


def _candidates_for(row: Dict[str, Any], proxy: str,
                    options: Dict[str, Any]) -> Tuple[List[Dict[str, str]], bool]:
    """按 `image_sources` 顺序给出候选与 `index_stale` 标志。

    **gFriends 命中就直接返回**（方案 §3：命中即用；javdb 只是兜底）——所以命中时连
    `fetch_javdb_avatar()` 都不会调，不会为了一位演员白跑一趟演员页。
    """
    gfriends, stale = _gfriends_candidates(row, proxy, options)
    if gfriends:
        return gfriends, stale
    return _javdb_candidates(row, proxy, options), stale


# ---------------------------------------------------------------------------
# 单个演员：选图 → 下载 → 校验 → 上传
# ---------------------------------------------------------------------------

def _record_images(store: Any, row: Dict[str, Any], cand: Dict[str, str],
                   raw: bytes = b"", width: int = 0, height: int = 0) -> bool:
    """把**选中的这张图**记进演员行（`images[0]` 是主图；原图去重后保留在后面）。

    为什么流水线必须自己写这一格：`images_json` 是演员库与"裁剪当前主图"唯一的数据来源
    （方案 §2）。只传 Emby 不落库的话，Emby 侧明明有图，而 `/actor/list` 的「有图」恒为 0、
    `crop-avatar` 报"没有当前主图"—— 0.9.0 真机就是这样（199 奥田咲上传成功但库里是 `[]`）。

    条目形状与 `_apply_master()`（手工裁剪/上传）保持一致；同一 url 不重复追加，旧条目
    `primary` 一律置 False。写库失败只 warning：**不能**因为记不上账就否定这一条的结论。
    """
    actor_id = scraper._to_int((row or {}).get("id"))
    if actor_id <= 0:                       # 兼容壳的行来自 meta.actors_json，没有 actor 主键
        return False
    setter = getattr(store, "actor_set_images", None)
    if not callable(setter):
        return False                        # store 还没有 actor 表（S1 未落地时就是这条路）
    if "images" in _as_list((row or {}).get("locked_fields")):
        return False                        # 双保险：锁了就不写（调用点前面也拦过）
    url = str((cand or {}).get("url") or "").strip()
    if not url:
        return False
    entry = {"url": url, "source": str((cand or {}).get("source") or "manual"),
             "w": int(width or 0), "h": int(height or 0), "bytes": len(bytes(raw or b"")),
             "primary": True}
    images = [entry]
    for old in _as_list((row or {}).get("images")):
        if not isinstance(old, dict):
            continue
        keep = dict(old)
        if not str(keep.get("url") or "").strip() or str(keep.get("url")) == url:
            continue
        keep["primary"] = False
        images.append(keep)
    try:
        setter(actor_id, images, field_sources={"images": entry["source"]})
    except Exception as error:              # noqa: BLE001 - 记账失败不影响这一条的 ok/failed
        logger.warning(f"AVHelper 写演员候选图失败（{actor_id}）：{type(error).__name__}: {error}")
        return False
    return True


def _scrape_row(store: Any, emby_client: Any, row: Dict[str, Any], *, force: bool = False,
                dry_run: bool = True, proxy: str = "",
                opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一位演员走完整条流水线，返回**内部**明细（比公开 item 多 `person_id` / `error`）。

    任何一步失败都**只改这一条的结局**并返回，绝不把异常抛给批量调用方（方案 §5.5 隔离）。
    """
    options = dict(opts or {})
    if proxy:
        options["proxy"] = str(proxy)
    person = _person_of(row)
    name = _display_of(row)
    actor_id = scraper._to_int((row or {}).get("id"))
    item: Dict[str, Any] = {
        "actor_id": actor_id, "person": person, "name": name, "person_id": "",
        "action": "skip", "reason": "", "url": "", "source": "", "bytes": 0,
        "w": 0, "h": 0, "error": "", "index_stale": False,
    }
    if not person:
        item["reason"] = "no_person"
        _log(store, "skipped", name, "no_person")
        return item
    if _gender_of(row) == 1:            # 1=男：硬排除（缺失 ≠ 男，None 会走到下面）
        item["reason"] = "male"
        _log(store, "skipped", person, "male")
        return item
    if "images" in _as_list((row or {}).get("locked_fields")):
        # 手工锁：**绝不换图**（方案 §5.6）。本模块只管头像，所以到此为止。
        item["reason"] = "locked"
        _log(store, "skipped", person, "locked")
        _mark(store, actor_id, True)
        return item

    finder = getattr(emby_client, "find_person", None) if emby_client is not None else None
    if not callable(finder):
        item.update(action="failed", reason="no_emby",
                    error=f"{person}：emby_client 没有 find_person")
        _log(store, "error", person, "no_emby", item["error"])
        _mark(store, actor_id, False, "no_emby")
        return item
    try:
        found = finder(person)          # 只认规范名的**精确**匹配（D15：Person 按 Name 建人）
    except Exception as error:          # noqa: BLE001 - 单条的 find 异常不连累整批
        item.update(action="failed", reason="find_failed",
                    error=f"{person}：find_person 异常 {type(error).__name__}: {error}")
        _log(store, "error", person, "find_failed", item["error"])
        _mark(store, actor_id, False, "find_failed")
        return item
    person_id = str((found or {}).get("Id") or "") if isinstance(found, dict) else ""
    if not person_id:
        item["reason"] = "person_missing"        # skip，不是失败（影片还没刮过）
        _log(store, "skipped", person, "person_missing")
        # Emby 里还没这个人 ≠ 没图：候选照样记进演员库（演员库要显示、crop-avatar 要用），
        # 只是这一步不下载（不需要字节就能入库），也绝不因此把这一条算成失败。
        if not dry_run:
            missing_candidates, missing_stale = _candidates_for(
                row, str(options.get("proxy") or ""), options)
            item["index_stale"] = bool(missing_stale)
            if missing_candidates:
                _record_images(store, row, missing_candidates[0])
        return item
    item["person_id"] = person_id
    has_image = bool(((found or {}).get("ImageTags") or {}).get("Primary"))
    if has_image and not force:
        item["reason"] = "has_image"
        _log(store, "skipped", person, "has_image")
        _mark(store, actor_id, True)
        return item

    candidates, stale = _candidates_for(row, str(options.get("proxy") or ""), options)
    item["index_stale"] = bool(stale)
    if not candidates:
        item["reason"] = "no_avatar"             # 两个源都没有 → 如实跳过
        _log(store, "skipped", person, "no_avatar")
        return item
    if dry_run:                         # dry_run 零写请求，**也不下载**（0.8.1 老口径）：只出候选清单
        first = candidates[0]
        item.update({"url": first["url"], "source": first["source"],
                     "action": "upload_avatar", "reason": ""})
        return item

    cap = max(1, scraper._to_int(_opt(options, "max_avatar_candidates", DEFAULT_MAX_CANDIDATES)))
    min_edge = max(0, scraper._to_int(_opt(options, "min_avatar_edge", DEFAULT_MIN_EDGE)))
    max_bytes = max(0, scraper._to_int(_opt(options, "max_avatar_bytes", DEFAULT_MAX_BYTES)))
    chosen: Optional[Tuple[Dict[str, str], bytes, int, int]] = None
    rejected: List[str] = []
    rejected_bytes = 0                       # 真的下到了字节、但没过校验的候选数
    last_error = ""
    for cand in candidates[:cap]:
        raw, error = _source_bytes(cand["url"], options)   # 本地派生图读盘，其余走 imgproxy + 重试一次
        if not raw:
            last_error = str(error or "取图失败")
            rejected.append(f"{cand['source']}：{last_error}")
            continue
        if max_bytes and len(raw) > max_bytes:
            rejected_bytes += 1
            last_error = f"图片超过 {max_bytes} 字节（{len(raw)}）"
            rejected.append(f"{cand['source']}：{last_error}")
            continue
        width, height = _image_size(raw)
        if not (width and height) and len(raw) >= 12 and not scraper.is_image_bytes(raw):
            # 魔数与解码**都不**通过 → 这一张不是图，换下一个候选（gFriends 的键值不同名时很常见）
            rejected_bytes += 1
            last_error = "拿到的不是图片（魔数/解码都不通过）"
            rejected.append(f"{cand['source']}：{last_error}")
            continue
        if min_edge and width and height and max(width, height) < min_edge:
            rejected_bytes += 1
            last_error = f"最长边 {max(width, height)}px 小于 {min_edge}px"
            rejected.append(f"{cand['source']}：{last_error}")
            continue
        chosen = (cand, bytes(raw), width, height)
        break
    if chosen is None:
        if rejected_bytes:
            # 下到了但都不达标（最长边 <200px / 超 5MB）→ skip + no_avatar（方案 §5.3），不是错误
            item["reason"] = "no_avatar"
            _log(store, "skipped", person, "no_avatar", "；".join(rejected))
            return item
        item.update(action="failed", reason=last_error or "取图失败",
                    error=f"{person}：{last_error or '取图失败'}")
        _log(store, "error", person, "fetch_failed", item["error"])
        _mark(store, actor_id, False, last_error or "fetch_failed")
        return item

    cand, raw, width, height = chosen
    item.update({"url": cand["url"], "source": cand["source"], "bytes": len(raw),
                 "w": width, "h": height, "action": "upload_avatar", "reason": ""})
    if dry_run:                         # dry_run 零写请求（与 0.8.1 的既有口径一致）
        return item
    # ★ 只要选到合规字节就落库（上传成败另说）：演员库的「有图」与「裁剪当前主图」都读这一格。
    _record_images(store, row, cand, raw, width, height)
    ok, detail = scraper._call(emby_client, "upload_image", person_id, "Primary", raw)
    if not ok:
        item.update(action="failed", reason=str(detail or "upload_failed"),
                    error=f"{person}：上传头像失败 {detail}")
        _log(store, "error", person, "upload_failed", item["error"])
        _mark(store, actor_id, False, str(detail or "upload_failed"))
        return item
    # C2（0.9.5）：头像换了，`/img?emby_person=` 的本地缓存也得跟着失效
    scraper._forget_emby_image(person_id, "Primary")
    _log(store, "ok", person)
    _mark(store, actor_id, True)
    javdb_id = str((row or {}).get("javdb_actor_id") or "")
    if javdb_id and bool(_opt(options, "person_provider_ids", True)):
        ok2, detail2 = scraper._call(emby_client, "update_item", person_id,
                                     {"ProviderIds": {"JavDB": javdb_id}})
        if not ok2:
            # 不致命：头像已经上去了，provider 写失败只记日志与 errors（S2/S3 的既有口径）
            item["error"] = f"{person}：写 ProviderIds.JavDB 失败 {detail2}"
            _log(store, "error", person, "provider_ids", item["error"])
    return item


# ---------------------------------------------------------------------------
# 挑行（actor_ids > persons > names > actor_due）
# ---------------------------------------------------------------------------

def _find_by_name(store: Any, text: str) -> Optional[Dict[str, Any]]:
    """按名字找一位演员：先 `actor_get(person=)`（精确键），再在 `actor_list(q=)` 的结果里
    对 `person/name/zh/jp` 做**整串相等**（放宽的只是"挑哪一行"，不碰 Emby 匹配口径）。"""
    getter = getattr(store, "actor_get", None)
    if callable(getter):
        try:
            row = getter(person=text)
        except Exception:               # noqa: BLE001 - 选择阶段失败按"没找到"处理
            row = None
        if isinstance(row, dict):
            return row
    lister = getattr(store, "actor_list", None)
    if not callable(lister):
        return None
    try:
        page = lister(q=text) or {}
    except Exception:                   # noqa: BLE001
        return None
    for item in (page.get("items") or []) if isinstance(page, dict) else []:
        if not isinstance(item, dict):
            continue
        for key in ("person", "name", "zh", "jp"):
            if scraper._clean_text(item.get(key)) == text:
                return item
    return None


def _select_rows(store: Any, actor_ids: Any, persons: Any, names: Any,
                 limit: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """挑出这一轮要处理的演员行；`actor_ids` > `persons` > `names` > `actor_due(limit)`。"""
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    size = max(0, scraper._to_int(limit))
    getter = getattr(store, "actor_get", None)
    if actor_ids:
        for raw in list(actor_ids):
            key = scraper._to_int(raw)
            row = None
            if callable(getter):
                try:
                    row = getter(actor_id=key)
                except Exception:       # noqa: BLE001
                    row = None
            if isinstance(row, dict):
                rows.append(row)
            else:
                errors.append(f"actor_id={key}：演员不存在")
    elif persons or names:
        # `persons` 是 Emby 规范名（队列/端点给的就是它）；`names` 放宽到展示名/中文名/日文名。
        for raw in list(persons or names):
            text = scraper._clean_text(raw)
            if not text:
                continue
            row = _find_by_name(store, text) if (names and not persons) else None
            if row is None and callable(getter):
                try:
                    row = getter(person=text)
                except Exception:       # noqa: BLE001
                    row = None
            rows.append(row if isinstance(row, dict) else {"id": 0, "person": text,
                                                           "name": text})
    else:
        due = getattr(store, "actor_due", None)
        if not callable(due):
            errors.append("store 没有 actor 表（演员线依赖 S1 的 store.actor_*）")
        else:
            try:
                found = due(limit=size or DEFAULT_DUE_LIMIT) or []
            except Exception as error:  # noqa: BLE001
                errors.append(f"actor_due 异常：{type(error).__name__}: {error}")
                found = []
            rows = [row for row in found if isinstance(row, dict)]
    if size > 0:
        rows = rows[:size]
    return rows, errors


# ---------------------------------------------------------------------------
# 批量入口
# ---------------------------------------------------------------------------

def _empty_counts() -> Dict[str, int]:
    """`run_actor_scrape()` 的计数表（键是契约，别省）。"""
    return {"total": 0, "uploaded": 0, "skipped": 0, "failed": 0, "no_avatar": 0,
            "person_missing": 0, "has_image": 0, "locked": 0, "index_stale": 0}


def _bump(counts: Dict[str, int], item: Dict[str, Any]) -> None:
    """一条结果 → 计数（no_avatar/person_missing/has_image/locked 是 skip 的子计数）。"""
    counts["total"] += 1
    action = str(item.get("action") or "")
    if action == "upload_avatar":
        counts["uploaded"] += 1
    elif action == "failed":
        counts["failed"] += 1
    else:
        counts["skipped"] += 1
    reason = str(item.get("reason") or "")
    if reason in ("no_avatar", "person_missing", "has_image", "locked"):
        counts[reason] += 1
    if item.get("index_stale"):
        counts["index_stale"] += 1


def _item_of(result: Dict[str, Any]) -> Dict[str, Any]:
    """内部明细 → 公开 item（契约形状）。"""
    return {key: result.get(key) for key in ITEM_KEYS}


def _run(store: Any, emby_client: Any, *, actor_ids: Any = None, persons: Any = None,
         names: Any = None, dry_run: bool = True, force: bool = False, limit: Any = 0,
         proxy: str = "", opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`run_actor_scrape()` 的主体（**调用方必须已持 `_LOCK`**）。"""
    options = dict(opts or {})
    counts = _empty_counts()
    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    out: Dict[str, Any] = {"ok": False, "dry_run": bool(dry_run), "counts": counts,
                           "items": items, "errors": errors, "reason": ""}
    if emby_client is None or not scraper._emby_write_ok(emby_client):
        errors.append("未配置 Emby（emby_client 不可用）")
        return out
    rows, select_errors = _select_rows(store, actor_ids, persons, names, limit)
    errors.extend(select_errors)
    # named = 点名（actor_ids/persons/names）→ 才让 `force` 生效；actor_due 的批量挑行忽略它。
    named = bool(actor_ids or persons or names)
    # 位与位之间的间隔（`queue_tick()` 会把它设成 ≥2s；直接调本函数默认不睡）
    interval = max(0.0, scraper._to_float(_opt(options, "actor_interval_s", 0)))
    for index, row in enumerate(rows):
        if index and interval > 0:
            scraper._SLEEP(interval)     # 走 scraper 的睡眠注入点：单测里是空实现
        try:
            result = _scrape_row(store, emby_client, row, force=bool(force and named),
                                 dry_run=bool(dry_run), proxy=proxy, opts=options)
        except Exception as error:       # noqa: BLE001 - 黑盒：一条炸了也不许带崩整批
            person = _person_of(row)
            result = {"actor_id": scraper._to_int((row or {}).get("id")), "person": person,
                      "name": _display_of(row), "person_id": "", "action": "failed",
                      "reason": f"{type(error).__name__}", "url": "", "source": "",
                      "bytes": 0, "w": 0, "h": 0,
                      "error": f"{person or '?'}：{type(error).__name__}: {error}",
                      "index_stale": False}
            logger.warning(f"AVHelper 演员刮削 {person!r} 异常：{type(error).__name__}: {error}")
        items.append(_item_of(result))
        _bump(counts, result)
        if result.get("error"):
            errors.append(str(result["error"]))
    out["ok"] = not errors
    return out


def run_actor_scrape(store: Any, emby_client: Any = None, *, actor_ids: Any = None,
                     persons: Any = None, names: Any = None, dry_run: bool = True,
                     force: bool = False, limit: Any = 0, proxy: str = "",
                     opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """主体入口：按 `actor_ids` > `persons` > `names` > `actor_due(limit)` 挑行并逐位跑流水线。

    返回 `{ok, dry_run, counts:{total, uploaded, skipped, failed, no_avatar, person_missing,
    has_image, locked, index_stale}, items:[{actor_id, person, name, action, reason, url,
    source, bytes, w, h}], errors:[str], reason}`。

    - `dry_run=True`（默认）**零写请求**：只 `find_person`（读）+ 出清单；`counts['uploaded']`
      表示"将会上传"的条数，与 apply 一致，只是没发写请求 —— P0 的批量预览吃的就是这个口径；
    - `force=True` 只对**点名**的演员生效（`actor_ids`/`persons`/`names`），批量挑行时忽略；
    - 单飞：并发第二个调用直接回 `{"ok": False, "reason": "busy", ...}`；
    - 只处理女演员：`gender == 1` 在流水线里再排一次；`gender is None` 保守保留。
    """
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "dry_run": bool(dry_run), "counts": _empty_counts(), "items": [],
                "errors": ["busy：已有演员任务在跑"], "reason": "busy"}
    try:
        return _run(store, emby_client, actor_ids=actor_ids, persons=persons, names=names,
                    dry_run=dry_run, force=force, limit=limit, proxy=proxy, opts=opts)
    finally:
        _LOCK.release()


def scrape_actor(store: Any, emby_client: Any, actor: Any, *, force: bool = False,
                 dry_run: bool = False, proxy: str = "",
                 opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """单个演员（`actor` 可以是 actor 行 dict、`actor.id`、或 Emby 规范名）。

    返回 `run_actor_scrape()['items']` 里的那种元素；找不到这一位时回一条 `failed`
    的明细（`reason='not_found'`），不抛异常。
    """
    row: Optional[Dict[str, Any]] = None
    if isinstance(actor, dict):
        row = dict(actor)
    elif isinstance(actor, (int, str)) and str(actor).strip():
        text = str(actor).strip()
        row = _find_by_name(store, text) if not text.isdigit() else None
        if row is None:
            getter = getattr(store, "actor_get", None)
            if callable(getter):
                try:
                    row = getter(actor_id=scraper._to_int(text)) if text.isdigit() \
                        else getter(person=text)
                except Exception:       # noqa: BLE001
                    row = None
        if not isinstance(row, dict):
            row = {"id": 0, "person": text, "name": text}
    if not isinstance(row, dict) or not _person_of(row):
        return {"actor_id": 0, "person": "", "name": "", "action": "failed",
                "reason": "not_found", "url": "", "source": "", "bytes": 0, "w": 0, "h": 0}
    return _item_of(_scrape_row(store, emby_client, row, force=bool(force),
                                dry_run=bool(dry_run), proxy=proxy, opts=opts))


def _tick_envelope(ok: bool, reason: str = "", errors: Any = None,
                   counts: Any = None) -> Dict[str, Any]:
    """`queue_tick()` 的返回骨架：`{ok, queued, due, handled, counts}`（+ 明细键）。"""
    return {"ok": bool(ok), "dry_run": False, "reason": str(reason or ""),
            "queued": 0, "due": 0, "handled": 0, "popped": 0,
            "counts": counts if isinstance(counts, dict) else _empty_counts(),
            "items": [], "errors": [str(one) for one in (errors or [])]}


def queue_tick(store: Any, emby_client: Any = None, *, batch: Any = 20, proxy: str = "",
               opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """定时 tick：**队列 + 到期**一起消费，逐位 `dry_run=False` 跑，两位之间 ≥2s（单飞）。

    为什么不是"只读队列"：`actor_queue_push()` 对已在队列里的行（含 `taken`）不重排，
    所以"同一部片再刮一次"不会把已经消费过的演员重新排队 —— 只读队列的话，第一轮把队列抽干
    之后就**再没有人被自动重刮**，自动同步形同停摆（S1 交付时的口径说明）。因此：

    1. `actor_queue_pop(batch)` 取排队那批（优先）；
    2. 剩余名额用 `actor_due(batch - len(queued))` 补"到期待重刮"那批（按 `person` 去重）；
    3. 两批合并成**一次** `_run(persons=…, dry_run=False)`。

    返回 `{ok, queued, due, handled, counts, dry_run, items, errors, reason, popped}`：
    `queued` 本轮从队列取走几位、`due` 补了几位到期的、`handled` 真进流水线的条数。

    间隔默认 2s，可用 `opts['interval']`（或 `queue_interval_s` / `actor_interval_s`）
    覆盖 —— 测试传 0 就不睡。
    """
    if not _LOCK.acquire(blocking=False):
        return _tick_envelope(False, "busy", ["busy：已有演员任务在跑"])
    try:
        options = dict(opts or {})
        if options.get("actor_interval_s") is None:
            seconds = options.get("interval")
            if seconds is None:
                seconds = options.get("queue_interval_s")
            options["actor_interval_s"] = (
                DEFAULT_QUEUE_INTERVAL if seconds is None
                else scraper._to_float(seconds))
        popper = getattr(store, "actor_queue_pop", None)
        if not callable(popper):
            return _tick_envelope(False, "no_actor_queue",
                                  ["store 没有 actor_queue（演员线依赖 S1 的 store.actor_*）"])
        size = scraper._to_int(batch) or DEFAULT_DUE_LIMIT
        try:
            rows = popper(size) or []
        except Exception as error:      # noqa: BLE001 - 队列读失败不该把定时任务打挂
            return _tick_envelope(False, "queue_error",
                                  [f"actor_queue_pop 异常：{type(error).__name__}: {error}"])
        persons: List[str] = []
        for row in rows:
            person = _person_of(row if isinstance(row, dict) else {})
            if person and person not in persons:
                persons.append(person)
        queued = len(persons)
        due = 0
        remaining = max(0, size - queued)
        due_fn = getattr(store, "actor_due", None)
        if remaining and callable(due_fn):
            try:
                due_rows = due_fn(limit=remaining) or []
            except Exception as error:  # noqa: BLE001 - 补到期失败只影响这一轮的补位
                logger.warning(f"AVHelper 读到期演员失败（本轮只跑队列）：{error}")
                due_rows = []
            for row in due_rows:
                person = _person_of(row if isinstance(row, dict) else {})
                if person and person not in persons:
                    persons.append(person)
                    due += 1
        if not persons:                 # 队列空 + 没有到期 = 无事可做，不是错误
            out = _tick_envelope(True)
            return out
        result = _run(store, emby_client, persons=persons, dry_run=False, force=False,
                      limit=0, proxy=proxy, opts=options)
        result.update({"queued": queued, "due": due, "handled": len(persons),
                       "popped": queued})
        return result
    finally:
        _LOCK.release()


# ---------------------------------------------------------------------------
# 手工覆盖（方案 §5.6）：裁剪 / 上传本地图 → 前插为主图
# ---------------------------------------------------------------------------

def _encode_url(url: Any) -> str:
    """把 URL 的**路径段** percent-encode，查询串原样保留（`?t=…` 不能被编成 `%3F`）。

    gFriends 的直链是"中日文路径 + 时间戳查询"的真实形状：

        `https://raw.githubusercontent.com/gfriends/gfriends/master/Content/z-ラグジュTV/AI-Fix-黒瀬萌衣.jpg?t=1607433809`

    `urllib` / `http.client` 对非 ASCII 的 URL 会直接 `UnicodeEncodeError`（不是 404、是抛异常），
    所以**在交给 imgproxy 之前**必须编码。较保守的 `safe` 集合（`/ : @ % +`）是故意的：路径里的 `%XX`
    已经编码过，再编一次会变成 `%25XX`（S2 实测过的坑）。
    """
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:                          # pragma: no cover - 防御
        return text
    if not parts.scheme or not parts.netloc:    # 本地路径/相对路径：原样返回
        return text
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/:@%+"),
                       parts.query, parts.fragment))


def _source_bytes(url: str, options: Dict[str, Any]) -> Tuple[bytes, str]:
    """取一张候选图的字节：**本地派生图直接读盘**，其余走 `scraper._image_bytes()`。

    为什么要支持本地路径：手工裁剪/上传的派生图落在图片缓存目录里，它的 `images[].url`
    就是这个绝对路径（没有 http 地址可抓）—— 重刮时它必须还能被当成一张候选图正常处理。
    """
    text = str(url or "").strip()
    if text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", text):
        try:
            with open(text, "rb") as handle:
                return handle.read(), ""
        except OSError as error:
            return b"", f"读本地图片失败：{error}"
    return scraper._image_bytes(_encode_url(text), options)


def _store_image(actor_id: Any, blob: bytes, ext: str = "jpg") -> str:
    """把派生图写进 **imgproxy 的图片缓存目录**（原子写用它的 `_store()`），返回绝对路径。

    文件名带内容哈希：同一份字节重裁不产生新文件，不同结果互不覆盖（原图永远还在）。
    """
    module = imgproxy
    folder = getattr(module, "cache_dir", None) if module is not None else None
    if not callable(folder):
        return ""
    try:
        base = str(folder())
        os.makedirs(base, exist_ok=True)
        name = f"manual-{scraper._to_int(actor_id)}-{hashlib.sha1(blob).hexdigest()[:12]}.{ext}"
        path = os.path.join(base, name)
        writer = getattr(module, "_store", None)
        if callable(writer):
            writer(path, blob)
        else:                                   # pragma: no cover - 防御
            with open(path, "wb") as handle:
                handle.write(blob)
        return path
    except Exception as error:                  # noqa: BLE001 - 落盘失败只影响这一次手工操作
        logger.warning(f"AVHelper 派生头像落盘失败：{type(error).__name__}: {error}")
        return ""


def _rect_box(rect: Any, width: int, height: int,
              ratio: Any) -> Optional[Tuple[int, int, int, int]]:
    """算裁切框：给了 `rect` 就按它（像素，越界自动收进图内），否则按 `ratio` 居中自判。"""
    if isinstance(rect, dict):
        try:
            left = int(round(float(rect.get("x") or 0)))
            top = int(round(float(rect.get("y") or 0)))
            box_w = int(round(float(rect.get("w") or 0)))
            box_h = int(round(float(rect.get("h") or 0)))
        except (TypeError, ValueError):
            return None
        left = max(0, min(width - 1, left))
        top = max(0, min(height - 1, top))
        box_w = min(box_w, width - left)
        box_h = min(box_h, height - top)
        if box_w < 1 or box_h < 1:
            return None
        return left, top, left + box_w, top + box_h
    try:
        target = float(ratio[0]) / float(ratio[1])
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return None
    if target <= 0:
        return None
    if width / height > target:                 # 原图偏宽 → 裁两侧
        box_w = max(1, min(width, int(round(height * target))))
        left = max(0, (width - box_w) // 2)
        return left, 0, left + box_w, height
    box_h = max(1, min(height, int(round(width / target))))   # 原图偏高 → 裁上下
    top = max(0, (height - box_h) // 2)
    return 0, top, width, top + box_h


def _crop_bytes(raw: bytes, rect: Any, ratio: Any) -> Tuple[bytes, int, int, str]:
    """裁成 `ratio` 比例的 JPEG；返回 `(字节, 宽, 高, 失败原因)`（原因空串即成功）。"""
    module = imgproxy
    loader = getattr(module, "_pillow_image", None) if module is not None else None
    if not callable(loader) or loader() is None:
        return b"", 0, 0, "no_pillow"
    Image = loader()
    try:
        with Image.open(io.BytesIO(bytes(raw or b""))) as img:
            img.load()
            width, height = int(img.size[0]), int(img.size[1])
            box = _rect_box(rect, width, height, ratio)
            if box is None:
                return b"", 0, 0, "bad_rect"
            shot = img.crop(box)
            if shot.mode not in ("RGB", "L"):
                shot = shot.convert("RGB")
            buf = io.BytesIO()
            shot.save(buf, "JPEG", quality=90, optimize=True)
            blob = buf.getvalue()
    except Exception as error:                  # noqa: BLE001 - 坏图/半张图一律如实拒绝
        return b"", 0, 0, f"decode_error：{type(error).__name__}: {error}"
    got_w, got_h = _image_size(blob)
    return blob, got_w, got_h, ""


def _resolve_actor_row(store: Any, actor: Any, actor_id: Any = None) -> Optional[Dict[str, Any]]:
    """手工入口的 `actor` 入参归一：行 dict / id / Emby 规范名 / 展示名都能进来。"""
    if isinstance(actor, dict):
        return dict(actor)
    key = scraper._to_int(actor_id)
    getter = getattr(store, "actor_get", None)
    if key > 0 and callable(getter):
        try:
            row = getter(actor_id=key)
        except Exception:                       # noqa: BLE001
            row = None
        if isinstance(row, dict):
            return row
    if isinstance(actor, (int, str)) and str(actor).strip():
        text = str(actor).strip()
        if text.isdigit():
            if callable(getter):
                try:
                    row = getter(actor_id=scraper._to_int(text))
                except Exception:               # noqa: BLE001
                    row = None
                if isinstance(row, dict):
                    return row
        else:
            row = _find_by_name(store, text)
            if isinstance(row, dict):
                return row
    return None


def _apply_master(store: Any, row: Dict[str, Any], blob: bytes, width: int, height: int,
                  source: str, options: Dict[str, Any], via: str = "crop",
                  emby_client: Any = None) -> Dict[str, Any]:
    """派生图落盘 → **前插**为 `images[0]` → 写库（原图保留）→ 尽力同步 Emby。"""
    out: Dict[str, Any] = {"ok": False, "actor": row, "reason": "", "url": "",
                           "size": [0, 0], "uploaded": False, "locked": False,
                           "locked_fields": []}
    actor_id = scraper._to_int((row or {}).get("id"))
    if "images" in _as_list((row or {}).get("locked_fields")):
        out["reason"] = "locked"                # 锁了 images：手工入口也不许改（要改先解锁）
        return out
    setter = getattr(store, "actor_set_images", None)
    if not callable(setter):
        out["reason"] = "store 没有 actor_set_images（演员线依赖 S1 的 store.actor_*）"
        return out
    path = _store_image(actor_id, blob)
    if not path:
        out["reason"] = "派生图落盘失败（imgproxy 缓存目录不可用）"
        return out
    entry = {"url": path, "source": str(source or "manual"), "w": int(width),
             "h": int(height), "bytes": len(blob), "primary": True}
    images = [entry]
    for old in _as_list((row or {}).get("images")):
        if not isinstance(old, dict) or not str(old.get("url") or "").strip():
            continue
        keep = dict(old)
        keep["primary"] = False                 # 主图只有一个：旧的降级但仍留在列表里
        images.append(keep)
    try:
        written = setter(actor_id, images, field_sources={"images": entry["source"]})
    except Exception as error:                  # noqa: BLE001 - 写库失败只影响这一次手工操作
        logger.warning(f"AVHelper 写演员主图失败（{actor_id}）：{type(error).__name__}: {error}")
        out["reason"] = f"写库失败：{type(error).__name__}: {error}"
        return out
    after = written if isinstance(written, dict) and written else row
    # 写库成功后**立刻锁 images**（方案 §5.6）：手工覆盖的全部意义就是"这就是我要的那张图"，
    # 不锁的话下一轮 queue_tick 就会拿源图把它盖掉（15 分钟一次），用户的手工成果活不过一刻钟。
    # 解锁仍只有 /actor/lock {on:false} 一条路，不新增入口。
    locked = False
    locker = getattr(store, "actor_lock", None)
    if callable(locker):
        try:
            locked_row = locker(actor_id, "images", True)
        except Exception as error:              # noqa: BLE001 - 加锁失败不推翻这次手工结果
            logger.warning(f"AVHelper 锁演员主图失败（{actor_id}）："
                           f"{type(error).__name__}: {error}")
            locked_row = {}
        if isinstance(locked_row, dict) and locked_row:
            after = locked_row
        locked = "images" in _as_list((after or {}).get("locked_fields"))
    out.update({"ok": True, "url": path, "size": [int(width), int(height)],
                "actor": after, "locked": bool(locked),
                "locked_fields": _as_list((after or {}).get("locked_fields"))})
    person = _person_of(row)
    _log(store, "ok", person, "manual_" + str(via or "crop"))
    if emby_client is not None and person:
        finder = getattr(emby_client, "find_person", None)
        person_id = ""
        if callable(finder):
            try:
                found = finder(person)
            except Exception as error:          # noqa: BLE001
                found = None
                logger.warning(f"AVHelper 手工头像 find_person 异常：{error}")
            if isinstance(found, dict):
                person_id = str(found.get("Id") or "")
        if person_id:
            ok, detail = scraper._call(emby_client, "upload_image", person_id, "Primary", blob)
            out["uploaded"] = bool(ok)
            if not ok:
                out["reason"] = f"Emby 上传失败 {detail}"
                _log(store, "error", person, "manual_upload_failed", detail)
            else:
                # C2：手工上传也要让 `/img?emby_person=` 的缓存失效
                scraper._forget_emby_image(person_id, "Primary")
    return out


def crop_avatar(store: Any, actor: Any = None, *, actor_id: Any = None, rect: Any = None,
                ratio: Any = (3, 4), opts: Optional[Dict[str, Any]] = None,
                emby_client: Any = None) -> Dict[str, Any]:
    """按 `ratio`（默认 3:4 竖图）裁**当前主图**，派生图前插为新的 `images[0]`，原图保留。

    返回 `{ok, actor, reason, url, size, uploaded}`。

    :param actor: actor 行 dict / `actor.id` / Emby 规范名。
        ⚠️ 端点 `/actor/crop-avatar` 把 `emby_client` 放在第二个位置传（`crop_avatar(store,
        emby_client, actor_id=…)`）—— 这里按类型自判：第二参数不是 dict/id/名字就当成 Emby 客户端。
    :param actor_id: 也可以显式给 `actor.id`（端点就是这么传的）。
    :param rect: `{x, y, w, h}`（像素，基于主图原始尺寸）；不给就居中自判。
    :param ratio: 目标宽高比，默认 `(3, 4)`（Emby 演员框是竖图）。

    只做三件事：取当前主图 → 裁 → 前插并写库；**写库成功即自动锁 `images`**（方案 §5.6：
    手工覆盖就是"这就是我要的那张图"，不锁就会被下一轮自动同步盖掉；解锁只走 `/actor/lock`）。
    给了 `emby_client` 时尽力把派生图传成 Person 主图（失败只记 `uploaded=False` + `reason`）。
    派生图最长边 < 200px 时**不写库**（`ok=False` + `reason`）。
    """
    options = dict(opts or {})
    client = emby_client
    if client is None and actor is not None and not isinstance(actor, (dict, int, str)):
        client, actor = actor, None             # 端点把 emby_client 放在第二位
    row = _resolve_actor_row(store, actor, actor_id)
    out: Dict[str, Any] = {"ok": False, "actor": row, "reason": "", "url": "",
                           "size": [0, 0], "uploaded": False, "locked": False,
                           "locked_fields": []}
    if not isinstance(row, dict):
        out["reason"] = "not_found"
        return out
    if _gender_of(row) == 1:                    # 与刮削口径一致：只处理女演员
        out["reason"] = "male"
        return out
    images = [one for one in _as_list(row.get("images")) if isinstance(one, dict)]
    primary = images[0] if images else {}
    url = str(primary.get("url") or "").strip()
    if not url:
        out["reason"] = "no_images"             # 还没有任何候选图：先刮一次再来裁
        return out
    raw, error = _source_bytes(url, options)
    if not raw:
        out["reason"] = f"取不到主图：{error or '空响应'}"
        return out
    blob, width, height, failure = _crop_bytes(raw, rect, ratio)
    if failure:
        out["reason"] = failure
        return out
    min_edge = max(0, scraper._to_int(_opt(options, "min_avatar_edge", DEFAULT_MIN_EDGE)))
    if min_edge and max(width, height) < min_edge:
        out["reason"] = f"裁出来的图只有 {width}×{height}（最长边小于 {min_edge}px）"
        return out
    max_bytes = max(0, scraper._to_int(_opt(options, "max_avatar_bytes", DEFAULT_MAX_BYTES)))
    if max_bytes and len(blob) > max_bytes:
        out["reason"] = f"裁出来的图超过 {max_bytes} 字节（{len(blob)}）"
        return out
    return _apply_master(store, row, blob, width, height, "manual", options, "crop", client)


def upload_avatar(store: Any, actor: Any, raw: Any, *, source: str = "manual",
                  opts: Optional[Dict[str, Any]] = None,
                  emby_client: Any = None) -> Dict[str, Any]:
    """手工上传本地图（方案 §5.6 的另一半）：校验魔数/尺寸 → 前插为 `images[0]`，原图保留。

    校验口径与流水线一致（魔数 + 最长边 ≥200px + 字节 ≤5MB），但**更严一点**：必须能解出真实
    尺寸才收（手工图没有"先把候选跑起来再说"的余地，量不出尺寸的条目下游一定失败）。
    返回 `{ok, actor, reason, url, size, uploaded, locked, locked_fields}`；写库成功后
    **自动锁 `images`**（方案 §5.6），解锁走 `/actor/lock {on:false}`。
    """
    options = dict(opts or {})
    row = _resolve_actor_row(store, actor, None)
    out: Dict[str, Any] = {"ok": False, "actor": row, "reason": "", "url": "",
                           "size": [0, 0], "uploaded": False, "locked": False,
                           "locked_fields": []}
    if not isinstance(row, dict):
        out["reason"] = "not_found"
        return out
    if _gender_of(row) == 1:
        out["reason"] = "male"
        return out
    blob = bytes(raw) if isinstance(raw, (bytes, bytearray)) else b""
    if not blob:
        out["reason"] = "空文件"
        return out
    max_bytes = max(0, scraper._to_int(_opt(options, "max_avatar_bytes", DEFAULT_MAX_BYTES)))
    if max_bytes and len(blob) > max_bytes:
        out["reason"] = f"图片超过 {max_bytes} 字节（{len(blob)}）"
        return out
    width, height = _image_size(blob)
    if not (width and height):
        out["reason"] = "拿到的不是图片（魔数/解码都不通过）"
        return out
    min_edge = max(0, scraper._to_int(_opt(options, "min_avatar_edge", DEFAULT_MIN_EDGE)))
    if min_edge and max(width, height) < min_edge:
        out["reason"] = f"最长边 {max(width, height)}px 小于 {min_edge}px"
        return out
    return _apply_master(store, row, blob, width, height, str(source or "manual"),
                         options, "upload", emby_client)

# ---------------------------------------------------------------------------
# 0.8.1 兼容壳：`scraper.sync_actor_avatars()` 的实现在这里
# ---------------------------------------------------------------------------

def _legacy_action(result: Dict[str, Any]) -> str:
    """内部 action → 0.8.1 老形状（`find_person` 异常那一条在老口径里仍记 `skip`）。"""
    action = str(result.get("action") or "skip")
    if action == "failed" and str(result.get("reason") or "") == "find_failed":
        return "skip"
    return action


def sync_actor_avatars(store: Any, emby_client: Any, *, limit: Any = 0, dry_run: bool = True,
                       namemap_mod: Any = None, opts: Optional[Dict[str, Any]] = None,
                       names: Any = None, force: bool = False) -> Dict[str, Any]:
    """把演员头像同步进 Emby 的 **Person 实体**（0.8.1 `/scrape/avatars` 的老形状，内部新实现）。

    返回键与 0.8.1 **逐字一致**：
    `{ok, dry_run, actors, planned:[{name, person_id, action, reason, url?, source?}], applied,
    errors, missing_person, gender_unknown}`。

    行来源仍是 `scraper._avatar_index(store, namemap_mod)`（`meta.actors_json` 聚合）——
    这条路径**不依赖 actor 表**（S1 还没落地 / 老库没有 actor 行时它就是唯一可用路径），
    `names` 过滤、`limit`、`gender_unknown` 的口径也照 0.8.1 原样。

    `force`：`opts['avatar_force']` 是 0.8.1 的全量覆盖；`force=` 形参只对 `names` **点名**
    的那些演员生效（方案 P1「force 只覆盖点名演员」）。
    """
    options = dict(opts or {})
    planned: List[Dict[str, Any]] = []
    applied: List[Dict[str, Any]] = []
    errors: List[str] = []
    out: Dict[str, Any] = {
        "ok": False, "dry_run": bool(dry_run), "actors": 0, "planned": planned,
        "applied": applied, "errors": errors, "missing_person": 0, "gender_unknown": 0,
    }
    if emby_client is None or not scraper._emby_write_ok(emby_client):
        errors.append("未配置 Emby（emby_client 不可用）")
        return out
    mod = namemap_mod if namemap_mod is not None else getattr(scraper, "namemap", None)
    index = scraper._avatar_index(store, mod)
    rows = sorted(index.values(), key=lambda row: row["name"])
    if names is not None:                       # 单片路径只处理这一片的演员
        wanted = {scraper._clean_text(item) for item in names}
        wanted.discard("")
        rows = [row for row in rows if scraper._wanted_slot(row, wanted)]
        if not rows:
            out["ok"] = True                    # 这些名字还不在 meta 索引里 = 无事可做，不是错误
            return out
    if not rows:
        errors.append("meta 里还没有演员（先刮削几条再来同步头像）")
        return out
    female: List[Dict[str, Any]] = []
    for row in rows:
        gender = _gender_of(row)
        if gender == 1:
            continue
        if gender is None:
            out["gender_unknown"] += 1          # 缺失 ≠ 男：照实报数，但**保留**
        female.append(row)
    rows = female
    size = scraper._to_int(limit)
    if size > 0:
        rows = rows[:size]
    out["actors"] = len(rows)
    if not rows:
        out["ok"] = not errors                  # 全被 gender 过滤掉：没有可同步的，不是错误
        return out
    force_all = bool(_opt(options, "avatar_force", False))
    force_named = bool(force) and names is not None
    for row in rows:
        result = _scrape_row(store, emby_client, row, force=bool(force_all or force_named),
                             dry_run=bool(dry_run), opts=options)
        action = _legacy_action(result)
        entry: Dict[str, Any] = {"name": result["person"], "person_id": result["person_id"],
                                 "action": action, "reason": result["reason"]}
        if action == "upload_avatar":           # 老形状：只有真要上传的那一条才带 url/source
            entry.update({"url": result["url"], "source": result["source"]})
        planned.append(entry)
        if result["reason"] == "person_missing":
            out["missing_person"] += 1
        if result["error"]:
            errors.append(result["error"])
        if action == "upload_avatar" and not dry_run:
            applied.append(dict(entry, bytes=result["bytes"]))
    out["ok"] = not errors
    return out
