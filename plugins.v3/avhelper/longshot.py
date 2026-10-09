"""长缩略图（长条剧情图）解析：projectjav 渠道，只解析 URL 不下载图片（执行方案 §7.2）。

解析链路：搜索页 `?searchTerm={番号}` → 按番号归一化过滤 `/movie/...` 详情链接 → 详情页取
`a[data-featherlight="image"]` 的 href。实测该图 1224×5817、无防盗链，但域名需走代理，
因此图片本身交给浏览器直连加载，后端只负责解析并把 URL 缓存 7 天。

javstore 的 "CLICK HERE" 规则已失效，不实现。
"""

import html
import re
import urllib.parse
from typing import Callable, Optional

PJ_SEARCH = "https://projectjav.com/?searchTerm=%s"
PJ_REFERER = "https://projectjav.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_MOVIE_LINK_RE = re.compile(r'<a[^>]+href=["\'](/movie/[^"\']+)["\'][^>]*>(.*?)</a>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
# 属性顺序与引号风格都可能变，两种顺序各配一套、单双引号都接受
_FEATHER_RE = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*data-featherlight=["\']image["\']'
)
_FEATHER_RE2 = re.compile(
    r'<a[^>]+data-featherlight=["\']image["\'][^>]*href=["\']([^"\']+)["\']'
)


def norm_number(text: str) -> str:
    """番号归一化：只保留字母数字并转小写，用于宽松匹配。"""
    return re.sub(r"[^A-Za-z0-9]", "", str(text or "")).lower()


def resolve_long(number: str, fetcher: Callable[[str, str], Optional[str]]) -> Optional[str]:
    """解析一个番号的长图 URL。

    :param number: 番号，如 IPZZ-961
    :param fetcher: (url, referer) -> 页面 HTML 或 None；由调用方注入带代理的抓取实现
    :return: 长图 URL；找不到或异常时返回 None
    """
    if not number:
        return None
    try:
        search_url = PJ_SEARCH % urllib.parse.quote(str(number))
        page = fetcher(search_url, PJ_REFERER)
        if not page:
            return None
        want = norm_number(number)
        links = _MOVIE_LINK_RE.findall(page)
        candidates = [
            href for href, text in links
            if want and want in norm_number(_TAG_RE.sub("", text))
        ]
        for href in candidates[:2]:
            detail = fetcher("https://projectjav.com" + href, PJ_REFERER)
            if not detail:
                continue
            match = _FEATHER_RE.search(detail) or _FEATHER_RE2.search(detail)
            if match:
                return html.unescape(match.group(1))
        return None
    except Exception:  # 外部站点改版属于常态，失败即降级为“未找到长图”
        return None
