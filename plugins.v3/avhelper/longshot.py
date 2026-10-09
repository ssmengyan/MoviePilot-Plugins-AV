"""长缩略图（长条剧情图）解析：projectjav 渠道，只解析 URL 不下载图片（执行方案 §7.2）。

解析链路：搜索页 `?searchTerm={番号}` → 在该番号的结果卡片里取
`a[data-featherlight="image"]` 的 href（实测列表页的卡片本身就带这个链接，1224×5817，
与详情页取到的是同一张）；卡片里没有时才退回进详情页取。实测该图无防盗链，但域名需走代理，
因此图片本身交给浏览器直连加载，后端只负责解析并把 URL 缓存 7 天。

javstore 的 "CLICK HERE" 规则已失效，不实现。
"""

import html
import re
import urllib.parse
from typing import Callable, List, Optional

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
# 列表页的结果卡片边界：每张卡片一个 video-item 块，长图链接必须按卡片取，不能跨卡片拿
_CARD_SPLIT_RE = re.compile(r'<div[^>]+class=["\'][^"\']*\bvideo-item\b[^"\']*["\']', re.I)


def norm_number(text: str) -> str:
    """番号归一化：只保留字母数字并转小写，用于宽松匹配。"""
    return re.sub(r"[^A-Za-z0-9]", "", str(text or "")).lower()


def _long_url_in(fragment: str) -> Optional[str]:
    """取一段 HTML 里第一个 featherlight 图片链接。"""
    match = _FEATHER_RE.search(fragment) or _FEATHER_RE2.search(fragment)
    return html.unescape(match.group(1)) if match else None


def _card_chunks(page: str) -> List[str]:
    """按结果卡片切分列表页；页面上没有卡片结构时返回空列表（调用方走回退）。"""
    parts = _CARD_SPLIT_RE.split(page)
    return parts[1:] if len(parts) > 1 else []


def _long_from_cards(page: str, want: str) -> Optional[str]:
    """在列表页的结果卡片里定位该番号的长图链接。

    卡片级作用域是硬要求：整页第一个 featherlight 很可能属于别的影片。
    """
    for card in _card_chunks(page):
        matched = any(
            want in norm_number(_TAG_RE.sub("", text))
            for _href, text in _MOVIE_LINK_RE.findall(card)
        )
        if not matched:
            continue
        url = _long_url_in(card)
        if url:
            return url
    return None


def resolve_long(number: str, fetcher: Callable[[str, str], Optional[str]]) -> Optional[str]:
    """解析一个番号的长图 URL。

    :param number: 番号，如 IPZZ-961
    :param fetcher: (url, referer) -> 页面 HTML 或 None；由调用方注入带代理的抓取实现
    :return: 长图 URL；找不到或异常时返回 None
    """
    if not number:
        return None
    want = norm_number(number)
    if not want:
        return None
    try:
        search_url = PJ_SEARCH % urllib.parse.quote(str(number))
        page = fetcher(search_url, PJ_REFERER)
        if not page:
            return None
        # 列表页卡片里通常已经带长图链接：命中就省掉一次详情页抓取（实测省一半时间）
        found = _long_from_cards(page, want)
        if found:
            return found
        # 回退：进详情页取（页面结构变化时的兜底路径）
        candidates = [
            href for href, text in _MOVIE_LINK_RE.findall(page)
            if want in norm_number(_TAG_RE.sub("", text))
        ]
        for href in candidates[:2]:
            detail = fetcher("https://projectjav.com" + href, PJ_REFERER)
            if not detail:
                continue
            found = _long_url_in(detail)
            if found:
                return found
        return None
    except Exception:  # 外部站点改版属于常态，失败即降级为“未找到长图”
        return None
