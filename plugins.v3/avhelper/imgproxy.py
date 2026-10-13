"""图片代理：图床白名单直出（浏览器 `<img src="/img?url=…">`）+ Emby 原图直取 + 封面智能裁切。

**本模块的三条职责（v4 刮削线，契约 §3.5 / 裁决 D5、D8）**

1. `fetch()` —— 浏览器直出的图床原图。带 host 白名单（防 SSRF）与按 host 的 Referer 策略。
   JavDB 图床 `tp.spfcas.com` 返回 `application/octet-stream` 且字节为 XOR 包装：
   首字节为 key，其余逐字节异或后才是 JPEG（`unwrap()` 解包，解包后校验魔数再缓存）。
2. `emby_image()` —— 局域网 Emby 原图直取（`?emby=<item_id>` / `?emby_person=<person_id>`）。
   封面写进 Emby 之后前端一律走这条，host/apikey 由调用方（`__init__.py`）传，本模块不读配置。
3. `crop_poster()` —— 横版大图裁成 377/538 竖版海报（v4.1 §8.2）。Pillow **延迟导入**：
   容器里是 12.3.0，本机/别的宿主可能没有 —— 缺 Pillow 时原样返回，绝不抛异常。

**白名单是按实测定的（2026-10-14，见 `_tmp/s5/REPORT-S5.md`）**，不是猜的：
精确域 6 个 + 后缀域 2 个；每个 host 的 Referer 取值也都有实测依据（见 `REFERERS` 注释）。
`is_allowed()` 的 SSRF 约束：只认 `https`、host 必须等于白名单域或以 `.`+后缀域结尾
（`evil-jdbstatic.com` 不通过）、`netloc` 不许带 userinfo（`@` 混淆）与端口、IP 字面量一律拒绝。

⚠️ 前端 `<img>` 直连图床时必须带 `referrerpolicy="no-referrer"`（AGENTS.md §5 的坑：
站点的 Referer 会被 projectjav 图床 403；直连失败才回落本模块的 `/img`）。
"""

import hashlib
import io
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from . import paths

# ---------------------------------------------------------------------------
# 白名单（2026-10-14 实测出现域；见 _tmp/s5/hosts.json 与 REPORT-S5.md）
# ---------------------------------------------------------------------------

#: 精确匹配的图床域。
ALLOWED_HOSTS = {
    # JavDB App API 图床（封面/小图/演员头像/剧照）——线上库实测出现 6866 次，绝对主力
    "tp.spfcas.com",
    # 长缩略图主源（projectjav 的剧照长图，WebP，校验 Referer）
    "images.projectjav.com",
    # 长缩略图备源（javfree 的剧照长图，WebP，不校验 Referer）
    "cf.javfree.me",
    # Javtxt 的演员头像（v4.1 §5.2 简介源；契约 §3.6.1 注明）。**严格校验 Referer**
    "img.j-cdn.com",
    # MetaTube Server 返回的 DUGA 图（契约 §0 的 MetaTube 坐标；实测每查必有）
    "pic.duga.jp",
    # Gfriends 演员头像（v4.1 §5.2 第二顺位头像源；raw.githubusercontent.com 直出）
    "raw.githubusercontent.com",
}

#: 后缀匹配的图床域（**必须以 `.` 开头**，只匹配子域，不匹配域本身）。
#: 用后缀是因为这些 CDN 会在 `c0/c1/c2`、`pics/awsimgsrc` 之间轮换子域，
#: 精确匹配正是这次要修的病（新增子域 → 全线 403）；带点的后缀挡住了 `evil-jdbstatic.com`。
ALLOWED_SUFFIXES = (
    # JavDB 网页版静态图床：实测 javdb.com 的影片页/演员页引用 c0.jdbstatic.com
    # 54/43 次（封面/头像/剧照），真实 JPEG、任意 Referer 放行；c1/c2 本机 TLS 不通（未启用）
    ".jdbstatic.com",
    # DMM 图片 CDN：MetaTube 的 JAV321 provider 实测直接返回
    # `http://pics.dmm.co.jp/digital/video/ssis00001/ssis00001ps.jpg`；javtxt 详情页也引用
    # `http://pics.dmm.co.jp/mono/actjpgs/…`。pics/awsimgsrc 均实测 200（见 _REFERER 说明）
    ".dmm.co.jp",
)

#: 各图床要带的 Referer（实测矩阵见 REPORT-S5.md「Referer 策略」）。
#: 空串 = 不带 Referer 头。
REFERERS: Dict[str, str] = {
    # 实测 4 种 Referer（空/自身/javdb/MP 页面）全 200；沿用 javdb 域名（保守、与 0.6.x 行为一致）
    "tp.spfcas.com": "https://javdb.com/",
    # 实测：空 Referer 200、`https://projectjav.com/` 200；`https://javdb.com/` 与 MP 页面一律 403。
    # 注意空 Referer 只是"这次放行"，站方随时可能收紧 → 固定发自己域名最稳。
    "images.projectjav.com": "https://projectjav.com/",
    # 实测 5 种 Referer 全 200（不校验），索性不发
    "cf.javfree.me": "",
    # **严格**：只有 `https://javtxt.net/` 放行（200 image/jpeg），空 Referer / javdb / MP 一律 403
    "img.j-cdn.com": "https://javtxt.net/",
    # 实测 5 种 Referer 全 200（DMM 系图床都不校验 Referer）
    "pic.duga.jp": "",
    # 实测空 Referer 200（GitHub raw 是公共 CDN，不校验）
    "raw.githubusercontent.com": "",
    "pics.dmm.co.jp": "",
    "awsimgsrc.dmm.co.jp": "",
}

#: 后缀域 → Referer（键同样以 `.` 开头）。
REFERER_SUFFIXES: Dict[str, str] = {
    ".jdbstatic.com": "",   # 实测 5 种 Referer 全 200
    ".dmm.co.jp": "",       # 实测 5 种 Referer 全 200
}

#: 白名单里没有的 host 的兜底 Referer（历史行为，保持向后兼容）。
DEFAULT_REFERER = "https://javdb.com/"

# 默认不内置代理：留空即直连（内地用户在插件设置里填自己的代理）
PROXY = ""
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

#: 已经是完整图片的魔数：WebP(RIFF) / PNG / JPEG / GIF，命中就原样返回，不做 XOR。
#: **保持原值不动**（外部可能引用）；判定请用 `is_plain_image()`，它额外要求 RIFF 后面是 WEBP。
PLAIN_MAGIC = (b"\xff\xd8", b"RIFF", b"\x89PNG\r\n\x1a\n", b"GIF8")

#: Emby 原图直取的超时与文件名前缀（缓存键要能和 URL 图的 sha1 区分开）。
EMBY_TIMEOUT = 20
EMBY_CACHE_PREFIX = "emby-"

#: host 允许的字符集（字母数字、点、连字符）——挡住 IPv6 字面量、空白、下划线等怪 host。
_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.\-]*[a-z0-9])?$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def cache_dir() -> str:
    """图片缓存目录（与 SQLite/JSON 同根，由 `paths` 在初始化时锁定）。"""
    return str(paths.images_dir())


# ---------------------------------------------------------------------------
# SSRF 边界
# ---------------------------------------------------------------------------

def _split(url: str) -> Optional[Tuple[str, str, bool]]:
    """容错解析：返回 `(scheme, host, netloc_ok)`；解析不出来返回 None。

    `netloc_ok` 要求 netloc **就是** host（可带 `:443`）—— 这一条同时挡住三类混淆：
    `https://tp.spfcas.com@evil.com/`（userinfo）、`https://tp.spfcas.com\\@evil.com/`（反斜杠）、
    `https://[::1]/`（IPv6 字面量，hostname 与 netloc 不等）。
    """
    if not url or not isinstance(url, str):
        return None
    text = url.strip()
    if not text:
        return None
    try:
        u = urllib.parse.urlparse(text)
        host = (u.hostname or "").lower()
        u.port                             # 端口非法（`https://h:abc/`）时这里抛 ValueError
    except ValueError:
        return None
    if not host:
        return None
    netloc = (u.netloc or "").lower()
    # netloc 必须就是 host（或显式 `:443`）：一行挡住 userinfo(`@` 混淆)、IPv6 方括号、
    # 反斜杠、以及指向白名单域非标端口的写法（`https://tp.spfcas.com:8080/`）。
    return (u.scheme or "").lower(), host, netloc in (host, host + ":443")


def host_allowed(host: str) -> bool:
    """host（不含 scheme）是否在白名单内：精确域相等，或后缀域（带点）匹配子域。"""
    name = (host or "").lower().rstrip(".")
    if not name or _IPV4_RE.match(name) or ":" in name:
        return False                      # IP 字面量一律不放行（防 SSRF）
    if not _HOSTNAME_RE.match(name):
        return False
    if name in ALLOWED_HOSTS:
        return True
    # `.jdbstatic.com` 只认子域：`c0.jdbstatic.com` ✔ / `evil-jdbstatic.com` ✘ / `jdbstatic.com` ✘
    # 后缀写法漏了点也自动补上（少了它 `evil-jdbstatic.com` 就会通过，不能指望配的人记得）
    for suffix in ALLOWED_SUFFIXES:
        tail = suffix if suffix.startswith(".") else "." + suffix
        if name.endswith(tail) and len(name) > len(tail):
            return True
    return False


def is_allowed(url: str) -> bool:
    """URL 能否经 `/img` 代理（仅 https + 白名单域 + 无 userinfo/端口/IP 混淆）。"""
    info = _split(url)
    if info is None:
        return False
    scheme, host, netloc_ok = info
    if scheme != "https" or not netloc_ok:
        return False
    return host_allowed(host)


def upgrade_scheme(url: str) -> str:
    """把白名单域的 `http://` 升级成 `https://`（其余原样返回）。

    依据：MetaTube 的 JAV321 provider 与 javtxt 详情页给的 DMM 图都是 `http://pics.dmm.co.jp/…`，
    而该域名实测 https 可用（同一张图 200/147237 字节）。`is_allowed()` 仍然**只认 https**，
    这里只是让 `fetch()` 不必让调用方自己拼 scheme。
    """
    info = _split(url)
    if info is None:
        return url
    scheme, host, netloc_ok = info
    if scheme != "http" or not netloc_ok or not host_allowed(host):
        return url
    parsed = urllib.parse.urlparse(url.strip())
    return urllib.parse.urlunparse(parsed._replace(scheme="https"))


def _normalize(url: str) -> str:
    """进缓存/发请求前统一口径（http→https），保证 `cached()` 与 `fetch()` 命中同一份。"""
    return upgrade_scheme(url) if isinstance(url, str) else url


# ---------------------------------------------------------------------------
# 图片字节处理
# ---------------------------------------------------------------------------

def is_plain_image(data: bytes) -> bool:
    """是否已经是完整图片。

    `PLAIN_MAGIC` 里的裸 `RIFF` 会把 WAV/AVI 也当成"已是图片"放行，所以这里收紧：
    RIFF 之后必须是 `WEBP`。WebP/PNG/JPEG/GIF 之外的一律按"需要 XOR 解包"处理。
    """
    if not data:
        return False
    if data[:4] == b"RIFF":
        return data[8:12] == b"WEBP"
    return any(data.startswith(magic) for magic in PLAIN_MAGIC)


def unwrap(raw: bytes) -> bytes:
    """还原 JavDB 图床的 XOR 包装：首字节为 key，其余异或。已是完整图片则原样返回。"""
    if is_plain_image(raw):
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


# ---------------------------------------------------------------------------
# 磁盘缓存（TTL/淘汰由 __init__.py 的 cache_idx 与容量淘汰管，本模块只管读写）
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> str:
    """按 URL 的 sha1 生成缓存文件路径。"""
    digest = hashlib.sha1(str(_normalize(url) or "").encode("utf-8")).hexdigest()
    # 扩展名只影响磁盘文件名（内容由魔数判定），沿用 .jpg 以免丢掉已有缓存
    return os.path.join(cache_dir(), digest + ".jpg")


def emby_cache_path(item_id: str, img_type: str = "Primary") -> str:
    """Emby 原图的缓存路径。

    **与 URL 图分开**：文件名带 `emby-` 前缀、摘要算的是 `emby:{id}:{type}` 而不是 URL，
    所以既不会与 `sha1(url)` 撞车，也能和主统筹的容量淘汰/排查肉眼对上号。
    `item_id` 在这里与拼 URL 时用同一套百分号编码，保证 `cached_emby()` 与 `emby_image()` 口径一致。
    """
    item = urllib.parse.quote(str(item_id or "").strip(), safe="")
    kind = str(img_type or "Primary").strip() or "Primary"
    key = "emby:%s:%s" % (item, kind)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(cache_dir(), EMBY_CACHE_PREFIX + digest + ".jpg")


def cached(url: str) -> bool:
    """这张图是否已经在本地缓存里（预热时用来跳过已缓存的那部分，不读文件内容）。"""
    return bool(url) and os.path.exists(_cache_path(url))


def cached_emby(item_id: str, img_type: str = "Primary") -> bool:
    """这张 Emby 原图是否已在本地缓存里。"""
    return bool(item_id) and os.path.exists(emby_cache_path(item_id, img_type))


def _store(path: str, data: bytes) -> None:
    """写缓存；失败不影响本次返回（缓存只是加速，不是正确性的一部分）。"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _open(req: urllib.request.Request, proxy: str = "", timeout: int = 45,
          direct: bool = False):
    """统一的打开入口（单测 monkeypatch 这里，不真连网）。

    :param proxy: 代理地址，留空按历史行为走系统默认（可能没有代理）
    :param direct: 显式不走代理（Emby 在局域网，绝不能被 http_proxy 环境变量带到外网去）
    """
    handlers = []
    if direct:
        handlers.append(urllib.request.ProxyHandler({}))
    elif proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    opener = urllib.request.build_opener(*handlers)
    return opener.open(req, timeout=timeout)


def referer_for(host: str) -> str:
    """按 host（含后缀域）取 Referer；白名单外的 host 走历史默认值。"""
    name = (host or "").lower().rstrip(".")
    if name in REFERERS:
        return REFERERS[name]
    for suffix, referer in REFERER_SUFFIXES.items():
        if name.endswith(suffix):
            return referer
    return DEFAULT_REFERER


def _headers(url: str) -> Dict[str, str]:
    """按 host 组装请求头（主要是 Referer：projectjav / javtxt 图床认这个）。"""
    host = urllib.parse.urlparse(url).hostname or ""
    headers = {"User-Agent": UA}
    referer = referer_for(host)
    if referer:
        headers["Referer"] = referer
    return headers


def fetch(url: str, proxy: str = PROXY) -> Optional[bytes]:
    """取图并返回解包后的图片字节；命中缓存直接读文件。失败返回 None。

    `proxy` 留空即直连（不再套一层空代理，否则 urllib 会拿空串当代理地址报错）。
    白名单域的 `http://` 会先升级成 `https://`（MetaTube/javtxt 给的 DMM 图是 http）。
    """
    url = _normalize(url)
    if not is_allowed(url):
        return None
    path = _cache_path(url)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            pass                          # 缓存读失败就当没缓存，往下走网络
    try:
        req = urllib.request.Request(url, headers=_headers(url))
        with _open(req, proxy=proxy, timeout=45) as resp:
            raw = resp.read()
    except Exception:
        return None
    data = unwrap(raw)
    if len(data) < 2 or not is_plain_image(data):
        return None
    _store(path, data)
    return data


# ---------------------------------------------------------------------------
# Emby 局域网原图直取（契约 §3.5；v4.1 §3 imgproxy 行）
# ---------------------------------------------------------------------------

def emby_base(host: str) -> str:
    """把调用方给的 Emby 地址归一成根地址：去尾斜杠、去掉多余的 `/emby` 后缀、补 scheme。"""
    text = str(host or "").strip().rstrip("/")
    if text.lower().endswith("/emby"):
        text = text[: -len("/emby")].rstrip("/")
    if text and "://" not in text:
        text = "http://" + text
    return text


def emby_image(host: str, apikey: str, item_id: str, img_type: str = "Primary"
               ) -> Optional[bytes]:
    """取 Emby 原图（局域网直连，不走代理）：`GET {host}/emby/Items/{id}/Images/{type}`。

    `?emby=<item_id>` 与 `?emby_person=<person_id>` 是同一个端点（Person 也是 Item），
    差别只在调用方传进来的 id；返回值落磁盘缓存（与 URL 图分开，见 `emby_cache_path`）。

    :param host: Emby 根地址（`http://192.0.2.50:8096`；带 `/emby` 也认）
    :param apikey: Emby API Key（由 `__init__.py` 从配置里读，本模块不读配置）
    :param item_id: 影片 / Person 的 Emby Id
    :param img_type: `Primary` / `Backdrop/0` / `Thumb` …
    :return: 图片字节；任何失败（含非图片响应）一律返回 None，不抛异常
    """
    base = emby_base(host)
    item = urllib.parse.quote(str(item_id or "").strip(), safe="")
    kind = str(img_type or "Primary").strip() or "Primary"
    if not base or not item or not str(apikey or "").strip():
        return None
    path = emby_cache_path(item_id, kind)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                blob = f.read()
            if blob:
                return blob
        except Exception:
            pass
    url = "%s/emby/Items/%s/Images/%s?api_key=%s" % (
        base, item, urllib.parse.quote(kind, safe="/"),
        urllib.parse.quote(str(apikey).strip(), safe=""))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
        with _open(req, timeout=EMBY_TIMEOUT, direct=True) as resp:
            data = resp.read()
    except Exception:
        return None
    if not data or media_type(data) == "application/octet-stream":
        return None                       # 404 页面 / 空响应：别把 HTML 当图缓存下来
    _store(path, data)
    return data


# ---------------------------------------------------------------------------
# 封面智能裁切（v4.1 §8.2）
# ---------------------------------------------------------------------------

#: `ratio <= 该值` 视为原生竖图，原图直传。
CROP_PORTRAIT_MAX = 0.80
#: 目标海报宽高比（Emby 海报框 377×538）。
POSTER_RATIO = 377 / 538
#: 认得的 anchor 取值；`auto` 由 is_fc2/is_vr/is_amateur 决定。
ANCHORS = ("auto", "left", "center", "right", "raw")

_PIL_IMAGE: Any = None
_PIL_TRIED = False


def _pillow_image():
    """延迟导入 Pillow 的 Image；导不进来返回 None（本机/别的宿主可能没有 Pillow）。"""
    global _PIL_IMAGE, _PIL_TRIED
    if not _PIL_TRIED:
        _PIL_TRIED = True
        try:
            from PIL import Image            # noqa: WPS433（故意的延迟导入）
            _PIL_IMAGE = Image
        except Exception:
            _PIL_IMAGE = None
    return _PIL_IMAGE


def crop_poster(raw: bytes, anchor: str = "auto", target_ratio: float = POSTER_RATIO,
                is_fc2: bool = False, is_vr: bool = False, is_amateur: bool = False
                ) -> Tuple[bytes, Dict[str, Any]]:
    """把横版大图裁成竖版海报，返回 `(jpeg_bytes, meta)`。**任何情况都不抛异常。**

    - `ratio = 宽/高 <= 0.80`（原生竖图）→ 原图直传，`mode='raw'`、`reason='portrait'`；
    - `ratio > 0.80`（横版大图）→ 按 `anchor` 裁右侧/居中/左侧，`mode='cropped'`；
    - `anchor='raw'` → 不裁；`anchor='auto'` → FC2 / VR / 素人走 `center`，其余走 `right`；
    - 缺 Pillow → 原图 + `reason='no_pillow'`；解码失败 → 原图 + `reason='decode_error'`。

    `meta` 固定含 `mode` / `anchor` / `source_size` / `size`（后两者是 `[w, h]` 或 None）。

    :param raw: 图床原图字节（javdb-cli 的 `assets download` 给的已是纯 JPEG/PNG）
    :param anchor: `auto` / `left` / `center` / `right` / `raw`（认不出的一律按 `auto`）
    :param target_ratio: 目标宽高比，默认 `377/538 ≈ 0.7007`
    :param is_fc2: FC2 作品（构图居中，走 center）
    :param is_vr: VR 作品（构图居中，走 center）
    :param is_amateur: 素人作品（同 FC2/VR；调用方按番号前缀判定后传进来）
    """
    data = bytes(raw) if isinstance(raw, (bytes, bytearray)) else b""
    key = str(anchor or "auto").strip().lower()
    if key not in ANCHORS:
        key = "auto"
    meta: Dict[str, Any] = {"mode": "raw", "anchor": key, "source_size": None, "size": None}

    Image = _pillow_image()
    if Image is None:
        meta["reason"] = "no_pillow"
        return data, meta
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = int(img.size[0]), int(img.size[1])
            if width <= 0 or height <= 0:
                meta["reason"] = "empty"
                return data, meta
            meta["source_size"] = [width, height]
            meta["size"] = [width, height]
            if width / height <= CROP_PORTRAIT_MAX:
                meta["reason"] = "portrait"
                return data, meta
            if key == "raw":
                meta["reason"] = "anchor_raw"
                return data, meta
            resolved = key if key != "auto" else (
                "center" if (is_fc2 or is_vr or is_amateur) else "right")
            target_w = int(round(height * float(target_ratio)))
            target_w = max(1, min(width, target_w))
            if target_w >= width:
                meta["reason"] = "no_crop_needed"
                return data, meta
            if resolved == "left":
                box = (0, 0, target_w, height)
            elif resolved == "center":
                left = (width - target_w) // 2
                box = (left, 0, left + target_w, height)
            else:
                box = (width - target_w, 0, width, height)
            shot = img.crop(box)
            if shot.mode not in ("RGB", "L"):
                shot = shot.convert("RGB")
            buf = io.BytesIO()
            shot.save(buf, "JPEG", quality=90, optimize=True)
            blob = buf.getvalue()
        # 自检：裁出来的图必须能被重新解码，且尺寸与预期一致
        with Image.open(io.BytesIO(blob)) as check:
            got = (int(check.size[0]), int(check.size[1]))
        if got != (box[2] - box[0], box[3] - box[1]):
            meta["reason"] = "verify_failed"
            return data, meta
        meta.update({"mode": "cropped", "anchor": resolved, "size": [got[0], got[1]],
                     "reason": ""})
        return blob, meta
    except Exception as error:                # 解码失败/半张图/OOM 一律降级成原图
        meta["reason"] = "decode_error"
        meta["error"] = "%s: %s" % (type(error).__name__, error)
        meta["size"] = None
        return data, meta
