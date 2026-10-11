"""Emby 媒体库查询：判断番号是否已在库，供界面打「已入库」标记。

连接信息优先取插件配置；没配就复用 MoviePilot「设置 → 媒体服务器」里已启用的 Emby
（官方 SDK `app.sdk.services.MediaServerHelper`），不额外维护一份密钥。

实现要点：
- 一次 HTTP 取回整个 JAV 库的条目（本环境 93 条），按归一化番号建索引，之后是字典命中；
- 索引在内存里缓存 5 分钟，失败负缓存 2 分钟；媒体库不通只是没有标记，不影响插件其它功能；
- 番号来源按可靠性排序：`ProviderIds.MetaTube`（MetaTube 刮削写入，最准）→ 文件名开头 → 标题开头；
- 任何异常都静默降级成空索引（界面就当没有这个功能，用户要求「没有就什么都不显示」）。
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger
from app.sdk.network import RequestUtils

TTL_OK = 300          # 索引缓存 5 分钟
TTL_FAIL = 120        # 失败负缓存 2 分钟（媒体库重启期间不反复打）
TIMEOUT = 6           # 单次请求超时，媒体库不通时不能拖住界面
PAGE = 500            # 分页大小
MAX_ITEMS = 20000     # 单库索引上限，防异常大库吃内存

# 认库依据：库名或路径里出现 jav / 9kg / avi（本环境 JAV 库路径是 /Media/9kg/avi）
_JAV_HINT = re.compile(r"(?:^|[^a-z0-9])(?:jav|9kg|avi)(?:[^a-z0-9]|$)", re.I)
_FC2 = re.compile(r"FC2[-_ ]*PPV[-_ ]*(\d{3,8})", re.I)
_LEAD = re.compile(r"^([A-Za-z]{2,6}\d?[-_ ]?\d{2,7})")


def norm_key(text: Any) -> str:
    """番号归一化：去掉非字母数字、统一大写，并抹掉数字段的前导零。

    `MIDV-946` / `midv00946` / `MIDV-946-UC` → `MIDV946UC`；`FC2-PPV-1234567` → `FC2PPV1234567`。
    javdb 的番号与 Emby 里的文件名、MetaTube 刮削 id 写法各不相同，必须先归一化再比。

    ⚠️ 后**缀**（`-UC` 这种）不会被丢掉 —— 只抹数字段的前导零（原 docstring 写成 `MIDV946` 是错的，
    2026-10-11 由前端那条线实测指出；台账主键、`_download_keys()` 与前端 `downloadHistory.normKey()`
    都按这个"保留后缀"的口径对齐）。
    """
    raw = re.sub(r"[^0-9A-Za-z]", "", str(text or "")).upper()
    if not raw:
        return ""
    return re.sub(r"0*(\d+)", lambda m: str(int(m.group(1))), raw)


def mp_emby_conf() -> Tuple[str, str]:
    """从 MoviePilot 媒体服务器配置里取第一个已启用的 Emby（host, apikey）。

    取不到返回两个空串，调用方按「没有媒体库」处理。
    """
    try:
        from app.sdk.services import MediaServerHelper

        for conf in (MediaServerHelper().get_configs() or {}).values():
            if str(getattr(conf, "type", "") or "").lower() != "emby":
                continue
            cfg = getattr(conf, "config", None) or {}
            host = str(cfg.get("host") or "").strip()
            apikey = str(cfg.get("apikey") or "").strip()
            if host and apikey:
                return host, apikey
    except Exception as error:
        logger.error(f"AVHelper 读取 MoviePilot 媒体服务器配置失败：{error}")
    return "", ""


def pick_libraries(folders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """挑要索引的媒体库：优先 JAV 类库（名字或路径命中），没有才退回全部「电影」库。"""
    jav = [f for f in folders if _looks_jav(f)]
    if jav:
        return jav
    return [f for f in folders if str(f.get("CollectionType") or "") == "movies"]


def _looks_jav(folder: Dict[str, Any]) -> bool:
    """库名或库路径是否像 JAV 库。"""
    text = " ".join([str(folder.get("Name") or "")]
                    + [str(x) for x in (folder.get("Locations") or [])])
    return bool(_JAV_HINT.search(text))


def _file_stem(path: str) -> str:
    """取文件名的去扩展名部分（路径可能是 Windows 反斜杠写法）。"""
    stem = str(path or "").replace("\\", "/").rsplit("/", 1)[-1]
    dot = stem.rfind(".")
    return stem[:dot] if dot > 0 else stem


def _text_keys(text: str) -> List[str]:
    """从一段文本（文件名 / 标题）里抽出可能的番号键。"""
    if not text:
        return []
    keys: List[str] = []
    fc2 = _FC2.search(text)
    if fc2:
        keys.append(norm_key("FC2PPV" + fc2.group(1)))
    lead = _LEAD.match(text)
    if lead:
        keys.append(norm_key(lead.group(1)))
    if len(text) <= 16:            # 短名整体也当候选（如「SSIS001」「ipx-001」）
        keys.append(norm_key(text))
    return keys


def _item_keys(item: Dict[str, Any]) -> List[str]:
    """一条 Emby 条目的全部候选番号键（去重保序）。"""
    keys: List[str] = []
    provider = str((item.get("ProviderIds") or {}).get("MetaTube") or "")
    if provider:                   # "JavBus:IPZZ-802" / "JAV321:midv00946"
        keys.append(norm_key(provider.split(":")[-1]))
    keys.extend(_text_keys(_file_stem(str(item.get("Path") or ""))))
    keys.extend(_text_keys(str(item.get("Name") or "")))
    return [k for k in dict.fromkeys(keys) if k]


class EmbyLibrary:
    """按番号查 Emby 媒体库；索引按需构建并缓存，线程安全。"""

    def __init__(self, host: str = "", apikey: str = "") -> None:
        self._host = str(host or "").strip().rstrip("/")
        self._apikey = str(apikey or "").strip()
        self._lock = threading.Lock()
        self._index: Optional[Dict[str, Dict[str, Any]]] = None
        self._built_at = 0.0
        self._failed_at = 0.0
        self._server_id = ""
        self._items_base = ""

    def ready(self) -> bool:
        """连接信息是否齐备。"""
        return bool(self._host and self._apikey)

    def lookup(self, number: str) -> Optional[Dict[str, Any]]:
        """番号 → {id, name, path, url}；不在库、未配置或查询失败一律返回 None。"""
        key = norm_key(number)
        if not key or not self.ready():
            return None
        return (self._ensure_index() or {}).get(key)

    def index(self) -> Dict[str, Dict[str, Any]]:
        """整个库的 `归一化番号 → {id, name, path, url}`；未配置或查询失败返回空字典。

        与 `lookup()` 是同一份内存索引（同样的 5 分钟缓存与失败负缓存），只是不做单点查询：
        「从库里补种台账」「历史页显示在库状态」要的是一次拿到全部命中，一次 HTTP 抓完就够
        （本环境 93 条），逐个番号调 `lookup()` 会把已经建好的索引白白查一遍。
        """
        return self._ensure_index() or {}

    # ---------- 内部 ----------

    def _ensure_index(self) -> Dict[str, Dict[str, Any]]:
        """取索引：命中缓存直接返回，失败走负缓存，绝不抛异常。"""
        now = time.time()
        if self._index is not None and now - self._built_at <= TTL_OK:
            return self._index
        if now - self._failed_at <= TTL_FAIL:
            return self._index or {}
        with self._lock:
            now = time.time()
            if self._index is not None and now - self._built_at <= TTL_OK:
                return self._index
            if now - self._failed_at <= TTL_FAIL:
                return self._index or {}
            try:
                index = self._build()
            except Exception as error:
                logger.error(f"AVHelper 读取 Emby 媒体库失败：{error}")
                index = None
            if index is None:
                self._failed_at = time.time()
                return self._index or {}
            self._index = index
            self._built_at = time.time()
            self._failed_at = 0.0
            return index

    def _build(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """抓媒体库列表 → 索引目标库的全部条目。失败返回 None（记负缓存）。"""
        folders = self._api("/emby/Library/VirtualFolders")
        if not isinstance(folders, list):
            return None
        targets = pick_libraries([f for f in folders if isinstance(f, dict)])
        if not targets:
            logger.info("AVHelper 未在 Emby 找到 JAV 类媒体库，「已入库」标记跳过")
            return {}
        info = self._api("/emby/System/Info")
        if isinstance(info, dict):
            self._server_id = str(info.get("Id") or "")
        index: Dict[str, Dict[str, Any]] = {}
        total = 0
        for folder in targets:
            items = self._items(str(folder.get("ItemId") or ""))
            total += len(items)
            for item in items:
                entry = {
                    "id": str(item.get("Id") or ""),
                    "name": str(item.get("Name") or ""),
                    "path": str(item.get("Path") or ""),
                    "url": self._web_url(str(item.get("Id") or "")),
                    # 入库时间（Emby 的 UTC ISO）：下载台账拿它当「完成时间」——
                    # 片子是被整理入库那一刻进的库，比「插件第一次看到它」真实得多。
                    "created": str(item.get("DateCreated") or ""),
                }
                for key in _item_keys(item):
                    index.setdefault(key, entry)
        logger.info(f"AVHelper Emby 索引就绪：{len(index)} 个番号键 / {total} 条条目"
                    f"（库 {[f.get('Name') for f in targets]}）")
        return index

    def _items(self, parent: str) -> List[Dict[str, Any]]:
        """取某个媒体库的全部影片条目（带分页）。"""
        if not parent:
            return []
        out: List[Dict[str, Any]] = []
        start = 0
        while len(out) < MAX_ITEMS:
            data = self._api(self._items_base or "/emby/Items", ParentId=parent, Recursive="true",
                             IncludeItemTypes="Movie", Fields="Path,ProviderIds,Name,DateCreated",
                             StartIndex=start, Limit=PAGE, EnableTotalRecordCount="false",
                             SortBy="DateCreated", SortOrder="Descending")
            if not isinstance(data, dict) and not self._items_base:
                # 管理员直查不被接受时退回用户维度（Emby 各版本行为不一）
                self._items_base = self._user_items_base()
                data = self._api(self._items_base, ParentId=parent, Recursive="true",
                                 IncludeItemTypes="Movie", Fields="Path,ProviderIds,Name,DateCreated",
                                 StartIndex=start, Limit=PAGE, EnableTotalRecordCount="false")
            if not isinstance(data, dict):
                break
            items = [x for x in (data.get("Items") or []) if isinstance(x, dict)]
            out.extend(items)
            if len(items) < PAGE:
                break
            start += PAGE
        return out

    def _user_items_base(self) -> str:
        """退回用某个用户维度查条目（Emby 部分版本要求带 userId）。"""
        users = self._api("/emby/Users")
        if isinstance(users, list):
            admin = [u for u in users if isinstance(u, dict)
                     and (u.get("Policy") or {}).get("IsAdministrator")]
            pick = (admin or [u for u in users if isinstance(u, dict)] or [{}])[0]
            if pick.get("Id"):
                return f"/emby/Users/{pick['Id']}/Items"
        return "/emby/Items"

    def _web_url(self, item_id: str) -> str:
        """Emby 网页里该条目的地址（新标签页打开用）。"""
        if not item_id:
            return ""
        return (f"{self._host}/web/index.html#!/item?id={item_id}"
                + (f"&serverId={self._server_id}" if self._server_id else ""))

    def _api(self, path: str, **params: Any) -> Any:
        """带 api_key 的 GET，返回 JSON（失败返回 None）。"""
        if not self.ready():
            return None
        params["api_key"] = self._apikey
        res = RequestUtils(timeout=TIMEOUT).get_res(f"{self._host}{path}", params=params)
        if not res or res.status_code != 200:
            return None
        try:
            return res.json()
        except Exception:
            return None
