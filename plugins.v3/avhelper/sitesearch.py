"""站点搜索适配层：把 AV 番号真正送进 PT 站点索引（插件自有索引路径）。

MP 原生站点搜索为什么搜不到 AV（2026-10-11 在真机逐条实测）：

- **馒头**：宿主 `MTorrentSpider` 搜索只带电影/剧集/音乐分类，且**不发 `mode` 参数**，
  成人区永远进不了结果集（实测 normal 模式 `keyword=SSIS-001` → 0 条；
  `mode=adult` + 同关键词 → 3 条，分类 410/429 等）。成人区必须显式 `"mode": "adult"`。
- **肉丝（Rousi）**：宿主 `RousiSpider` 会按媒体类型追加 `category` 过滤
  （实测 `category=movie` + `keyword=MIDV` → 0 条；**不带 category** → 6 条，含 9kg 区）。
  肉丝的搜索本身就同时包含成人与正常内容，所以「不带分类」才是正确用法——
  这就是要参考的肉丝逻辑：番号搜索**不要带媒体类型过滤**。
- **其它站点**：仍交给 MP 原生索引器（`chain.search_site_torrents`），但同样不带 `mtype`，
  避免站点索引器按分类把成人内容排除在外。

下载内容解析也收在这里：插件的 `self.chain` 只有 `download()`，拿不到 MP
DownloadChain 的 `download_torrent()`，因此 `[base64]{url}` 两段式 enclosure
必须由插件自己换票、取回种子字节，再交给下载链（换票协议与 MP 内部完全一致）。

模块顶只用标准库，宿主 HTTP 工具在使用处延迟导入——这样纯函数（参数构造、结果映射、
enclosure 编解码）可以在无宿主环境下单测。
"""

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

# 站点适配器
ADAPTER_MTEAM = "mteam"
ADAPTER_ROUSI = "rousi"
ADAPTER_MP = "mp"

# 站点域名特征（命中即用对应适配器；域名可能带端口/子域，用包含判断）
MTEAM_DOMAINS = ("m-team.cc", "mteam.cc", "m-team.io")
ROUSI_DOMAINS = ("rousi.pro", "rousi.cc", "rousi.org")

ADAPTER_LABELS = {
    ADAPTER_MTEAM: "馒头成人区（mode=adult）",
    ADAPTER_ROUSI: "肉丝全站（不带分类过滤）",
    ADAPTER_MP: "MoviePilot 原生索引器（不带媒体类型）",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PAGE_SIZE = 50
TIMEOUT = 20
# `[base64 换票参数]{换票地址}`，与 MP 的 enclosure 协议一致
RECIPE_RE = re.compile(r"^\[(.*)\](.*)$", re.S)

# M-Team 促销系数（与宿主 MTorrentSpider 保持一致）
_MT_DOWNLOAD_FACTOR = {
    "FREE": 0.0, "PERCENT_50": 0.5, "PERCENT_70": 0.3,
    "_2X_FREE": 0.0, "_2X_PERCENT_50": 0.5,
}
_MT_UPLOAD_FACTOR = {"_2X": 2.0, "_2X_FREE": 2.0, "_2X_PERCENT_50": 2.0}

# 馒头自带的元数据字段映射（2026-10-11 用 240 条成人区样本交叉统计得出：
# 名字含 1080p 的 65 条全部 standard=1、含 720p 的 59 条全为 3、含 2160p/4K 的 64 条全为 6；
# 名字含 H265/x265 的样本 videoCodec=16，其余为 1）。只映射有证据的值，未验证的留空走标题正则。
MTEAM_STANDARD = {"1": "1080p", "3": "720p", "6": "2160p"}
MTEAM_VIDEO_CODEC = {"1": "H264", "16": "H265"}
_UNCENSORED_MARKERS = ("无码", "無碼", "破解", "流出", "uncensored", "leak")


def _warn(message: str) -> None:
    """写宿主日志（延迟导入，保持本模块在无宿主环境下可单测）。"""
    try:
        from app.sdk.logging import logger

        logger.warning(f"AVHelper {message}")
    except Exception:
        pass


def mteam_hints(row: Dict[str, Any]) -> Dict[str, Any]:
    """从馒头自带元数据生成打分提示（比只看种名可靠）。

    馒头成人区每条结果都带 `standard`（分辨率）、`videoCodec`、`hasChineseSubtitle`
    （中文字幕标记）与 `smallDescr`（含「[无码破解]」这类前缀），这些比种名正则准得多。
    """
    status_text = f"{row.get('name') or ''} {row.get('smallDescr') or ''}".lower()
    return {
        "res_hint": MTEAM_STANDARD.get(str(row.get("standard") or ""), ""),
        "codec_hint": MTEAM_VIDEO_CODEC.get(str(row.get("videoCodec") or ""), ""),
        "cnsub_hint": bool(row.get("hasChineseSubtitle")),
        "uncensored_hint": any(mark in status_text for mark in _UNCENSORED_MARKERS),
    }


def text_of(row: Any, key: str, default: Any = "") -> Any:
    """同时兼容 dict 与宿主对象（TorrentInfo）的取字段写法。"""
    if isinstance(row, dict):
        value = row.get(key)
    else:
        value = getattr(row, key, None)
    return default if value is None else value


def int_of(value: Any, default: int = 0) -> int:
    """把接口里的数字字段安全转成整数（可能是字符串）。"""
    try:
        return default if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return default


def detect_adapter(site: Dict[str, Any]) -> str:
    """按域名判断站点该走哪个适配器。"""
    raw = f"{site.get('domain') or ''} {site.get('url') or ''}".lower()
    if any(domain in raw for domain in MTEAM_DOMAINS):
        return ADAPTER_MTEAM
    if any(domain in raw for domain in ROUSI_DOMAINS):
        return ADAPTER_ROUSI
    return ADAPTER_MP


def adapter_label(site: Dict[str, Any]) -> str:
    """给界面看的适配器说明。"""
    return ADAPTER_LABELS.get(detect_adapter(site), ADAPTER_LABELS[ADAPTER_MP])


def registered_domain(host: str) -> str:
    """按 MoviePilot 的站点规则取注册域名（≤3 段取末两段，>3 段原样）。

    宿主给插件的索引器配置里 `domain` 可能是入口子域（实测馒头是 `kp.m-team.cc`），
    直接拼 `api.` 会得到不存在的 `api.kp.m-team.cc`。
    """
    labels = [part for part in str(host or "").split(".") if part]
    if not labels:
        return ""
    if len(labels) <= 3:
        return ".".join(labels[-2:]) if len(labels) >= 2 else labels[0]
    return ".".join(labels)


def mteam_api_host(site: Dict[str, Any]) -> str:
    """解析 M-Team API 主机：优先站点配置，其次 `api.<注册域>`。"""
    for key in ("api_domain", "api_host"):
        value = str(site.get(key) or "").strip()
        if value:
            host = value.split("://")[-1].split("/")[0]
            if host:
                return host
    raw = str(site.get("domain") or site.get("url") or "")
    host = raw.split("://")[-1].split("/")[0]
    if host.startswith("api."):
        return host
    base = registered_domain(host)
    return f"api.{base}" if base else "api.m-team.cc"


def mteam_search_payload(keyword: str, mode: Optional[str] = "adult",
                         page: int = 0) -> Dict[str, Any]:
    """构造馒头搜索请求体：成人区必须显式带 mode=adult，且不带分类过滤。"""
    payload: Dict[str, Any] = {
        "keyword": keyword or "",
        "categories": [],
        "pageNumber": int(page or 0) + 1,
        "pageSize": PAGE_SIZE,
        "visible": 1,
    }
    if mode:
        payload["mode"] = mode
    return payload


def mteam_discount(status: Dict[str, Any]) -> Tuple[float, float, Optional[str]]:
    """从馒头 status 里取（下载系数, 上传系数, 免费截止时间）。"""
    discount = str((status or {}).get("discount") or "")
    dvf = _MT_DOWNLOAD_FACTOR.get(discount, 1.0)
    uvf = _MT_UPLOAD_FACTOR.get(discount, 1.0)
    freedate = (status or {}).get("discountEndTime") or None
    rule = (status or {}).get("promotionRule") or {}
    if rule:
        dvf = _MT_DOWNLOAD_FACTOR.get(str(rule.get("discount") or ""), dvf)
        uvf = _MT_UPLOAD_FACTOR.get(str(rule.get("discount") or ""), uvf)
        freedate = rule.get("endTime") or freedate
    single_free = (status or {}).get("mallSingleFree") or {}
    if str(single_free.get("status") or "") == "ONGOING":
        dvf = 0.0
        freedate = single_free.get("endDate") or freedate
    return dvf, uvf, freedate


def mteam_recipe(api_host: str, apikey: str, torrent_id: Any,
                 use_proxy: bool = False, ua: str = UA) -> str:
    """馒头下载换票 enclosure：[base64 参数]https://api.../api/torrent/genDlToken。"""
    recipe = {
        "method": "post",
        "cookie": False,
        "params": {"id": str(torrent_id)},
        "header": {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "x-api-key": apikey,
        },
        "proxy": bool(use_proxy),
        "result": "data",
    }
    return f"[{_encode_recipe(recipe)}]https://{api_host}/api/torrent/genDlToken"


def rousi_recipe(api_host: str, apikey: str, torrent_id: Any,
                 use_proxy: bool = False, ua: str = UA) -> str:
    """肉丝下载换票 enclosure：详情接口返回短时 download_url。"""
    recipe = {
        "method": "get",
        "cookie": False,
        "header": {
            "Authorization": f"Bearer {apikey}",
            "Accept": "application/json",
            "User-Agent": ua,
        },
        "proxy": bool(use_proxy),
        "result": "data.download_url",
    }
    return f"[{_encode_recipe(recipe)}]https://{api_host}/api/v1/torrents/{torrent_id}"


def _encode_recipe(recipe: Dict[str, Any]) -> str:
    """把换票参数编码成 base64（与 MP 的 enclosure 协议一致）。"""
    raw = json.dumps(recipe, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def parse_recipe(enclosure: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """解析 `[base64]{url}`：返回（换票参数, 换票地址）；不是该格式返回 None。"""
    match = RECIPE_RE.match(str(enclosure or ""))
    if not match:
        return None
    encoded, url = match.groups()
    if not encoded or not url:
        return None
    try:
        recipe = json.loads(base64.b64decode(encoded.encode("utf-8")).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(recipe, dict):
        return None
    return recipe, url


def pick_result(payload: Any, path: str) -> Any:
    """按 `a.b.c` 取响应里的值（与 MP 的 result 语义一致）。"""
    data = payload
    for key in str(path or "").split("."):
        if not key:
            continue
        if not isinstance(data, dict):
            return None
        data = data.get(key)
        if data is None:
            return None
    return data


def mteam_rows(site: Dict[str, Any], payload: Any, apikey: str,
               use_proxy: bool = False) -> List[Dict[str, Any]]:
    """把馒头搜索响应映射成本插件的种子结构（纯函数，便于单测）。"""
    rows = ((payload or {}).get("data") or {}).get("data") or []
    if not isinstance(rows, list):
        return []
    api_host = mteam_api_host(site)
    site_url = str(site.get("url") or "").rstrip("/")
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        status = row.get("status") or {}
        dvf, uvf, freedate = mteam_discount(status)
        labels = row.get("labelsNew") or []
        if not isinstance(labels, list):
            labels = []
        hints = mteam_hints(row)
        entry = {
            "site": site.get("id"),
            "site_name": site.get("name") or "",
            "site_cookie": "",
            "site_ua": site.get("ua") or UA,
            "title": str(row.get("name") or ""),
            "description": str(row.get("smallDescr") or ""),
            "enclosure": mteam_recipe(api_host, apikey, row.get("id"), use_proxy,
                                      str(site.get("ua") or UA)),
            "page_url": f"{site_url}/detail/{row.get('id')}",
            "size": int_of(row.get("size")),
            "seeders": int_of(status.get("seeders")),
            "peers": int_of(status.get("leechers")),
            "grabs": int_of(status.get("timesCompleted")),
            "pubdate": str(status.get("createdDate") or ""),
            "freedate": freedate,
            "downloadvolumefactor": dvf,
            "uploadvolumefactor": uvf,
            "category": "电影",
            "labels": labels,
            "adapter": ADAPTER_MTEAM,
        }
        entry.update(hints)
        out.append(entry)
    return out


def rousi_rows(site: Dict[str, Any], payload: Any, apikey: str,
               use_proxy: bool = False) -> List[Dict[str, Any]]:
    """把肉丝搜索响应映射成本插件的种子结构（纯函数）。"""
    rows = ((payload or {}).get("data") or {}).get("torrents") or []
    if not isinstance(rows, list):
        return []
    host = registered_domain(str(site.get("domain") or site.get("url") or ""))
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        promotion = row.get("promotion") or {}
        dvf, uvf, freedate = 1.0, 1.0, None
        if promotion.get("is_active"):
            try:
                dvf = float(promotion.get("down_multiplier", 1.0))
                uvf = float(promotion.get("up_multiplier", 1.0))
            except (TypeError, ValueError):
                dvf, uvf = 1.0, 1.0
            freedate = promotion.get("until") or None
        raw_cat = row.get("category")
        if isinstance(raw_cat, dict):
            raw_cat = raw_cat.get("slug") or raw_cat.get("name")
        out.append({
            "site": site.get("id"),
            "site_name": site.get("name") or "",
            "site_cookie": str(site.get("cookie") or ""),
            "site_ua": site.get("ua") or UA,
            "title": str(row.get("title") or ""),
            "description": str(row.get("subtitle") or ""),
            "enclosure": rousi_recipe(host, apikey, row.get("id"), use_proxy,
                                      str(site.get("ua") or UA)),
            "page_url": f"https://{host}/torrents/{row.get('id')}",
            "size": int_of(row.get("size")),
            "seeders": int_of(row.get("seeders")),
            "peers": int_of(row.get("leechers")),
            "grabs": int_of(row.get("downloads")),
            "pubdate": str(row.get("created_at") or ""),
            "freedate": freedate,
            "downloadvolumefactor": dvf,
            "uploadvolumefactor": uvf,
            "category": "电影",
            "labels": [str(raw_cat)] if raw_cat else [],
            "adapter": ADAPTER_ROUSI,
        })
    return out


class SiteSearcher:
    """按站点策略搜索种子并解析下载内容。"""

    def __init__(self, chain: Any = None, proxy: str = ""):
        self.chain = chain
        self.proxy = proxy or ""

    # ---------- 站点策略 ----------

    def describe(self, site: Dict[str, Any]) -> Dict[str, Any]:
        """给界面用的站点能力描述。"""
        adapter = detect_adapter(site)
        return {
            "id": site.get("id"),
            "name": site.get("name") or "",
            "adapter": adapter,
            "adapterLabel": ADAPTER_LABELS.get(adapter, ""),
        }

    def _proxies(self, site: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """站点开了代理时才走插件代理（与宿主索引器行为一致）。"""
        if site.get("proxy") and self.proxy:
            return {"http": self.proxy, "https": self.proxy}
        return None

    # ---------- 搜索 ----------

    def search(self, site: Dict[str, Any], keyword: str) -> Tuple[List[Dict[str, Any]], str]:
        """搜索一个站点，返回（种子列表, 过程说明）。单站失败不抛异常。"""
        adapter = detect_adapter(site)
        try:
            if adapter == ADAPTER_MTEAM:
                return self._search_mteam(site, keyword)
            if adapter == ADAPTER_ROUSI:
                return self._search_rousi(site, keyword)
            return self._search_mp(site, keyword)
        except Exception as error:  # 站点异常不该打断整轮搜索
            _warn(f"{site.get('name')} 搜索异常：{error}")
            return [], f"{site.get('name')} 搜索异常：{str(error)[:120]}"

    def _search_mteam(self, site: Dict[str, Any], keyword: str) -> Tuple[List[Dict[str, Any]], str]:
        """馒头：先搜成人区，成人区没有再看常规区（常规区不带分类过滤）。"""
        name = site.get("name") or ""
        apikey = str(site.get("apikey") or "")
        if not apikey:
            return [], f"{name} 未配置 API Key，无法搜索"
        host = mteam_api_host(site)
        url = f"https://{host}/api/torrent/search"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": str(site.get("ua") or UA),
            "x-api-key": apikey,
        }
        client = self._http(headers=headers, site=site)
        response, error = self._call(client, "post", url,
                                     json=mteam_search_payload(keyword, "adult"))
        if response is None:
            return [], f"{name} 成人区搜索失败：{error or '无响应'}"
        payload = self._json(response)
        if payload is None:
            return [], f"{name} 成人区搜索失败（HTTP {getattr(response, 'status_code', '—')}）"
        rows = mteam_rows(site, payload, apikey, bool(site.get("proxy")))
        if rows:
            return rows, f"{name} 成人区命中 {len(rows)} 条"
        # 成人区没有 → 常规区兜底（同样不带分类，避免漏掉放在常规区的 AV）
        response, error = self._call(client, "post", url,
                                     json=mteam_search_payload(keyword, None))
        payload = self._json(response) if response is not None else None
        rows = mteam_rows(site, payload, apikey, bool(site.get("proxy"))) if payload else []
        if rows:
            return rows, f"{name} 常规区命中 {len(rows)} 条（成人区无结果）"
        return [], f"{name} 未命中（成人区 + 常规区都为空）{('：' + error) if error else ''}"

    def _search_rousi(self, site: Dict[str, Any], keyword: str) -> Tuple[List[Dict[str, Any]], str]:
        """肉丝：不带 category 搜索（带上分类会把 9kg 区过滤掉）。"""
        name = site.get("name") or ""
        apikey = str(site.get("apikey") or "")
        if not apikey:
            return [], f"{name} 未配置 API Key，无法搜索"
        host = str(site.get("domain") or "").split("://")[-1].split("/")[0]
        headers = {
            "Authorization": f"Bearer {apikey}",
            "Accept": "application/json",
            "User-Agent": str(site.get("ua") or UA),
        }
        client = self._http(headers=headers, site=site)
        response, error = self._call(client, "get", f"https://{host}/api/v1/torrents",
                                     params={"keyword": keyword, "page": 1,
                                             "page_size": PAGE_SIZE})
        if response is None:
            return [], f"{name} 搜索失败：{error or '无响应'}"
        payload = self._json(response)
        if payload is None:
            return [], f"{name} 搜索失败（HTTP {getattr(response, 'status_code', '—')}）"
        rows = rousi_rows(site, payload, apikey, bool(site.get("proxy")))
        if rows:
            return rows, f"{name} 命中 {len(rows)} 条"
        return [], f"{name} 未命中"

    def _search_mp(self, site: Dict[str, Any], keyword: str) -> Tuple[List[Dict[str, Any]], str]:
        """其它站点：走 MP 原生索引器，但不带媒体类型（等价肉丝的“不带分类”逻辑）。"""
        name = site.get("name") or ""
        if self.chain is None:
            return [], f"{name} 缺少宿主搜索链"
        results = self.chain.search_site_torrents(site=site, keyword=keyword, mtype=None) or []
        rows = []
        for item in results:
            row = {key: text_of(item, key, None) for key in (
                "site", "site_name", "site_cookie", "site_ua", "title", "description",
                "enclosure", "page_url", "size", "seeders", "peers", "grabs", "pubdate",
                "freedate", "downloadvolumefactor", "uploadvolumefactor", "category", "labels",
            )}
            row["site"] = site.get("id")
            row["site_name"] = site.get("name") or row.get("site_name") or ""
            row["adapter"] = ADAPTER_MP
            if row.get("title"):
                rows.append(row)
        if rows:
            return rows, f"{name} 原生索引器命中 {len(rows)} 条"
        return [], f"{name} 未命中"

    # ---------- 下载内容 ----------

    def resolve(self, enclosure: str, site: Optional[Dict[str, Any]] = None
                ) -> Tuple[Optional[Any], str]:
        """把 enclosure 变成下载器能吃的内容：种子字节 / 磁力 / 直链。

        返回（内容, 失败原因）；内容为 None 表示彻底失败。
        """
        content = str(enclosure or "")
        if not content:
            return None, "候选缺少下载地址"
        if content.startswith("magnet:"):
            return content, ""
        parsed = parse_recipe(content)
        if parsed is None:
            blob = self._fetch_bytes(content, site)
            if blob:
                return blob, ""
            # 取不回字节就把直链交给下载器（由下载器带 Cookie 去取）
            return content, ""
        recipe, request_url = parsed
        real_url = self._redeem(recipe, request_url, site)
        if not real_url:
            return None, "站点换票失败，无法取得种子下载地址"
        blob = self._fetch_bytes(real_url, site, recipe=recipe)
        if blob:
            return blob, ""
        return None, "种子文件下载失败"

    def _redeem(self, recipe: Dict[str, Any], request_url: str,
                site: Optional[Dict[str, Any]]) -> Optional[str]:
        """执行换票请求并取出真实下载地址。"""
        headers = recipe.get("header") if isinstance(recipe.get("header"), dict) else None
        params = recipe.get("params") if isinstance(recipe.get("params"), dict) else None
        cookies = (site or {}).get("cookie") if recipe.get("cookie") else None
        client = self._http(headers=headers, site=site or {}, cookies=cookies)
        method = "get" if str(recipe.get("method") or "get").lower() == "get" else "post"
        response, _ = self._call(client, method, request_url, params=params)
        payload = self._json(response)
        if payload is None:
            return None
        value = pick_result(payload, str(recipe.get("result") or ""))
        return str(value) if isinstance(value, str) and value else None

    def _fetch_bytes(self, url: str, site: Optional[Dict[str, Any]] = None,
                     recipe: Optional[Dict[str, Any]] = None) -> Optional[bytes]:
        """取回种子文件字节（换过票的地址不再带站点 Cookie，与 MP 行为一致）。"""
        headers = {"User-Agent": str((site or {}).get("ua") or UA),
                   "Accept": "application/x-bittorrent, application/octet-stream, */*"}
        cookies = None if recipe else (site or {}).get("cookie")
        try:
            client = self._http(headers=headers, site=site or {}, cookies=cookies)
            response, _ = self._call(client, "get", url)
            if response is None or response.status_code != 200:
                return None
            blob = response.content or b""
            return blob if len(blob) > 100 else None
        except Exception:
            return None

    # ---------- 基础设施 ----------

    def _http(self, headers: Optional[Dict[str, Any]] = None,
              site: Optional[Dict[str, Any]] = None, cookies: Any = None) -> Any:
        """构造宿主 HTTP 工具（延迟导入，便于无宿主环境下单测纯函数）。"""
        from app.sdk.network import RequestUtils

        return RequestUtils(headers=headers, cookies=cookies, proxies=self._proxies(site or {}),
                            timeout=TIMEOUT, verify=False)

    @staticmethod
    def _call(client: Any, method: str, url: str, **kwargs: Any) -> Tuple[Any, str]:
        """发一次请求；失败时把异常类型与文本带回来（不抛给上层，便于写进任务说明）。"""
        try:
            if str(method).lower() == "post":
                return client.post_res(url=url, raise_exception=True, **kwargs), ""
            return client.get_res(url=url, raise_exception=True, **kwargs), ""
        except Exception as error:
            return None, f"{type(error).__name__}: {str(error)[:160]}"

    @staticmethod
    def _json(response: Any) -> Optional[Dict[str, Any]]:
        """安全解析 JSON 响应，失败返回 None。"""
        if response is None or getattr(response, "status_code", 0) != 200:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None
