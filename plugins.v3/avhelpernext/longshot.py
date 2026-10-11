"""长缩略图（长条剧情图）解析：projectjav 主源 + javfree 备源，只解析 URL 不下载图片（执行方案 §7.2）。

渠道照抄油猴脚本 JHS-enhance/src/plugins/screenshot.js 的 Thumbnail 类：
  1) projectjav：`?searchTerm={番号}` 的列表卡片自带 `a[data-featherlight="image"]`，
     实测与详情页取到的是同一张（1224×5817），所以先按卡片取；卡片里没有才进详情页。
  2) javfree：`/search/{番号}` → `.entry-title > a` 命中的详情页 → `p > img` 里优先 `-1080p`，
     其次 `-demosaic`，再次 `_1`（实测 1200×6858，比 projectjav 还长，且不校验 Referer）。
  javstore 的 "CLICK HERE" 规则对现行页面已失效（油猴脚本里也只剩兜底），不实现。

⚠️ 防盗链（2026-10-11 实测）：images.projectjav.com 会校验 Referer —— 空 Referer 或
projectjav 自己域名放行，带 MoviePilot 页面地址（或 https://javdb.com/）一律 403。
所以前端 <img> 必须带 referrerpolicy="no-referrer"，否则图片一定加载失败。
图片本身始终由浏览器直连加载，后端只负责解析 URL 并缓存 7 天。
"""

import html
import re
import urllib.parse
from typing import Callable, List, Optional

PJ_HOST = "https://projectjav.com"
PJ_SEARCH = PJ_HOST + "/?searchTerm=%s"
JF_HOST = "https://javfree.me"
JF_SEARCH = JF_HOST + "/search/%s"
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
# javfree（WordPress）：搜索结果标题链 + 详情页正文图
_JF_LINK_RE = re.compile(
    r'<h[1-6][^>]*class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>\s*'
    r'<a[^>]+href=["\']([^"\']+)["\']', re.I)
_JF_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
# 油猴脚本的优先级：1080p 长图 → 去马赛克版 → 单张预览
_JF_PREFER = ("-1080p.", "-demosaic.", "_1.")


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


def _detail_hrefs(page: str, want: str) -> List[str]:
    """列表页里命中该番号的详情页链接（去重、保序）。"""
    hrefs = [
        href for href, text in _MOVIE_LINK_RE.findall(page)
        if want in norm_number(_TAG_RE.sub("", text))
    ]
    return list(dict.fromkeys(hrefs))


def from_projectjav(number: str, fetcher: Callable[[str, str], Optional[str]]) -> Optional[str]:
    """projectjav：列表卡片 → 详情页（同款选择器）。"""
    search_url = PJ_SEARCH % urllib.parse.quote(str(number))
    page = fetcher(search_url, PJ_HOST + "/")
    if not page:
        return None
    want = norm_number(number)
    found = _long_from_cards(page, want)
    if found:
        return found
    for href in _detail_hrefs(page, want)[:2]:
        detail = fetcher(PJ_HOST + href, search_url)
        if not detail:
            continue
        found = _long_url_in(detail)
        if found:
            return found
    return None


def from_javfree(number: str, fetcher: Callable[[str, str], Optional[str]]) -> Optional[str]:
    """javfree：搜索页 → 番号命中的详情页 → 正文图里按优先级挑长图。"""
    want = norm_number(number)
    if not want:
        return None
    search_url = JF_SEARCH % urllib.parse.quote(str(number))
    page = fetcher(search_url, JF_HOST + "/")
    if not page:
        return None
    link = next(
        (href for href in _JF_LINK_RE.findall(page) if want in norm_number(href)),
        None,
    )
    if not link:
        return None
    if link.startswith("//"):
        link = "https:" + link
    detail = fetcher(link, search_url)
    if not detail:
        return None
    urls = [html.unescape(u) for u in _JF_IMG_RE.findall(detail) if want in norm_number(u)]
    for key in _JF_PREFER:
        hit = next((u for u in urls if key in u.lower()), None)
        if hit:
            return hit
    return None


def resolve_long(number: str, fetcher: Callable[[str, str], Optional[str]]) -> Optional[str]:
    """按油猴脚本的源顺序解析一个番号的长图 URL。

    :param number: 番号，如 IPZZ-961
    :param fetcher: (url, referer) -> 页面 HTML 或 None；由调用方注入带代理的抓取实现
    :return: 长图 URL；所有源都没找到或异常时返回 None
    """
    if not number:
        return None
    want = norm_number(number)
    if not want:
        return None
    for source in (from_projectjav, from_javfree):
        try:
            url = source(number, fetcher)
        except Exception:  # 外部站点改版属于常态，单源失败不影响下一个源
            url = None
        if url:
            return url
    return None
