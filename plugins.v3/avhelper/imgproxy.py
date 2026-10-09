"""图片代理：JavDB 图床 XOR 解包（§7.1）。

实测：tp.spfcas.com 返回 application/octet-stream，且字节为 XOR 包装：
首字节为 key，其余逐字节异或后才是 JPEG。解包后校验 FF D8 魔数再缓存。
"""

import hashlib
import os
import urllib.parse
import urllib.request
from typing import Optional

# 防 SSRF：只代理白名单域名（§7.1）
ALLOWED_HOSTS = {"tp.spfcas.com", "images.projectjav.com"}
PROXY = "http://192.0.2.11:7890"
CACHE_DIR = "/avhelper/cache/images"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def unwrap(raw: bytes) -> bytes:
    """还原 JavDB 图床的 XOR 包装：首字节为 key，其余异或。已是 JPEG 则原样返回。"""
    if len(raw) >= 2 and raw[0] == 0xFF and raw[1] == 0xD8:
        return raw
    if len(raw) < 3:
        return raw
    key = raw[0]
    return bytes(b ^ key for b in raw[1:])


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
    return os.path.join(CACHE_DIR, digest + ".jpg")


def fetch(url: str, proxy: str = PROXY) -> Optional[bytes]:
    """取图并返回解包后的 JPEG 字节；命中缓存直接读文件。失败返回 None。"""
    if not is_allowed(url):
        return None
    path = _cache_path(url)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Referer": "https://javdb.com/"})
        with opener.open(req, timeout=30) as resp:
            raw = resp.read()
    except Exception:
        return None
    data = unwrap(raw)
    if not (len(data) >= 2 and data[0] == 0xFF and data[1] == 0xD8):
        return None
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return data
