"""图片代理：JavDB 图床 XOR 解包（§7.1）+ projectjav/javfree 长图兜底。

实测：tp.spfcas.com 返回 application/octet-stream，且字节为 XOR 包装：
首字节为 key，其余逐字节异或后才是 JPEG。解包后校验 FF D8 魔数再缓存。

长缩略图默认由浏览器直连（快、不占 NAS 带宽），只有浏览器取不到时才退回这里；
projectjav 图床是 WebP 且**校验 Referer**（带 MP 页面地址一律 403），所以按 host 发对应的 Referer。
"""

import hashlib
import os
import urllib.parse
import urllib.request
from typing import Dict, Optional

# 防 SSRF：只代理白名单域名（§7.1）
ALLOWED_HOSTS = {"tp.spfcas.com", "images.projectjav.com", "cf.javfree.me"}
# 各图床要带的 Referer：projectjav 图床带 MP 域名会被 403，带自己域名最稳；javfree 不需要
REFERERS: Dict[str, str] = {
    "tp.spfcas.com": "https://javdb.com/",
    "images.projectjav.com": "https://projectjav.com/",
    "cf.javfree.me": "",
}
PROXY = "http://192.0.2.11:7890"
# 图片缓存根：与 CACHE_ROOT 同卷（容量淘汰也在这个目录里跑）
CACHE_ROOT = "/avhelper/cache"
CACHE_DIR = f"{CACHE_ROOT}/images"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 已经是完整图片的魔数：WebP(RIFF) / PNG / JPEG / GIF，命中就原样返回，不做 XOR
PLAIN_MAGIC = (b"\xff\xd8", b"RIFF", b"\x89PNG\r\n\x1a\n", b"GIF8")


def unwrap(raw: bytes) -> bytes:
    """还原 JavDB 图床的 XOR 包装：首字节为 key，其余异或。已是完整图片则原样返回。"""
    if any(raw.startswith(magic) for magic in PLAIN_MAGIC):
        return raw
    if len(raw) < 3:
        return raw
    key = raw[0]
    return bytes(b ^ key for b in raw[1:])


def media_type(data: bytes) -> str:
    """按魔数给 Content-Type（长图是 WebP，不能一律报 image/jpeg）。"""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return "application/octet-stream"


def is_allowed(url: str) -> bool:
    """URL 是否在白名单内（仅 https，host 严格匹配）。"""
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return u.scheme == "https" and (u.hostname or "") in ALLOWED_HOSTS


def _cache_path(url: str) -> str:
    """按 URL 的 sha1 生成缓存文件路径。"""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    # 扩展名只影响磁盘文件名（内容由魔数判定），沿用 .jpg 以免丢掉已有缓存
    return os.path.join(CACHE_DIR, digest + ".jpg")


def _headers(url: str) -> Dict[str, str]:
    """按 host 组装请求头（主要是 Referer：projectjav 图床认这个）。"""
    host = urllib.parse.urlparse(url).hostname or ""
    headers = {"User-Agent": UA}
    referer = REFERERS.get(host, "https://javdb.com/")
    if referer:
        headers["Referer"] = referer
    return headers


def fetch(url: str, proxy: str = PROXY) -> Optional[bytes]:
    """取图并返回解包后的图片字节；命中缓存直接读文件。失败返回 None。"""
    if not is_allowed(url):
        return None
    path = _cache_path(url)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
        req = urllib.request.Request(url, headers=_headers(url))
        with opener.open(req, timeout=45) as resp:
            raw = resp.read()
    except Exception:
        return None
    data = unwrap(raw)
    if len(data) < 2 or not any(data.startswith(magic) for magic in PLAIN_MAGIC):
        return None
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return data
