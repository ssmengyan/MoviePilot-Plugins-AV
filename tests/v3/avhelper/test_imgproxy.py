"""`imgproxy.py` 单测：白名单/SSRF、XOR 解包、Emby 原图直取、封面智能裁切。

本文件只碰 `imgproxy`（契约 §3.5），全部走假 HTTP 层 —— **不真连图床、不真连 Emby**。
`imgproxy` 的磁盘缓存被 monkeypatch 到 `tmp_path`（`paths._DATA_ROOT`），不污染线上缓存。
"""

import importlib.util
import io
import os
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
# 与 conftest 用同一个合成包名：避免同一份模块被加载出两个互不相干的副本
PKG_NAME = "avhelper_under_test"


def _load(name: str):
    """按 conftest 的口径加载插件目录下的单个模块（本文件不改 conftest，故自带一份）。"""
    if PKG_NAME not in sys.modules:
        pkg = types.ModuleType(PKG_NAME)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PKG_NAME] = pkg
    key = f"{PKG_NAME}.{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def imgproxy():
    """imgproxy 模块（延迟导入 Pillow，本机有没有都能加载）。"""
    return _load("imgproxy")


@pytest.fixture
def cache_root(imgproxy, monkeypatch, tmp_path):
    """把数据根指到 tmp_path —— 图片缓存落 tmp，不碰线上 `/avhelper/cache`。"""
    paths_mod = _load("paths")
    monkeypatch.setattr(paths_mod, "_DATA_ROOT", tmp_path)
    return tmp_path


class _FakeResp:
    """`urllib` 响应对象的最小替身（支持 `with` 与 `read()`）。"""

    def __init__(self, body: bytes):
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeHTTP:
    """假 HTTP 层：记录每次调用，按预设脚本回响应或抛异常。"""

    def __init__(self, *results):
        self.calls = []
        self._results = list(results)

    def __call__(self, req, proxy="", timeout=45, direct=False):
        self.calls.append({"url": getattr(req, "full_url", str(req)),
                           "headers": dict(getattr(req, "headers", {}) or {}),
                           "proxy": proxy, "timeout": timeout, "direct": direct})
        if not self._results:
            raise AssertionError("假 HTTP 层没有更多预设响应了（第 %d 次调用）" % len(self.calls))
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResp(item)

    @property
    def urls(self):
        return [c["url"] for c in self.calls]


def _bands(width=1400, height=1000):
    """左红 / 中绿 / 右蓝的三段色带图：用来验证到底裁了哪一侧。"""
    Image = pytest.importorskip("PIL.Image")
    img = Image.new("RGB", (width, height), (255, 0, 0))
    third = width // 3
    img.paste((0, 255, 0), (third, 0, 2 * third, height))
    img.paste((0, 0, 255), (2 * third, 0, width, height))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), img


# ---------------------------------------------------------------------------
# 一、白名单与 SSRF 边界
# ---------------------------------------------------------------------------

ALLOWED_EXACT = [
    "https://tp.spfcas.com/rhe951l4q/covers/96/96GB0p.jpg",
    "https://images.projectjav.com/data/screenshots/snos-380.jpg?v=1791538589",
    "https://cf.javfree.me/HLIC/GVH-883-1080p.jpeg",
    "https://img.j-cdn.com/avatar/60390.jpg",
    "https://pic.duga.jp/unsecure/firststar/1968/noauth/jacket.jpg",
    "https://raw.githubusercontent.com/gfriends/gfriends/master/Content/1-Diaz/Rio.jpg",
]

ALLOWED_SUFFIX = [
    "https://c0.jdbstatic.com/covers/96/96GB0p.jpg",
    "https://c1.jdbstatic.com/avatars/yp/YPKz.jpg",
    "https://images.jdbstatic.com/x.png",
    "https://pics.dmm.co.jp/digital/video/snos00380/snos00380pl.jpg",
    "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/snos00380/snos00380pl.jpg",
]

REJECTED = [
    # 后缀域的反例：不许"以白名单串结尾"就算数
    "https://evil-jdbstatic.com/covers/96/96GB0p.jpg",
    "https://evil-dmm.co.jp/x.jpg",
    "https://jdbstatic.com/x.jpg",                  # 域本身不在白名单（只认子域）
    "https://dmm.co.jp/x.jpg",
    "https://nottp.spfcas.com/x.jpg",               # 精确域不认子域
    "https://tp.spfcas.com.evil.com/x.jpg",
    "https://raw.githubusercontent.com.evil.com/x.jpg",
    # scheme
    "http://tp.spfcas.com/x.jpg",
    "http://pics.dmm.co.jp/digital/video/x/x.jpg",
    "ftp://tp.spfcas.com/x.jpg",
    "//tp.spfcas.com/x.jpg",
    # IP 字面量（含局域网 Emby 本身：它有自己的入口 `emby_image()`，不走 /img）
    # 地址一律用 RFC 5737 TEST-NET（`192.0.2.0/24`）：既保住"IP 字面量"这条语义，
    # 又不泄露任何真实内网坐标（`tests/` 会随公开仓库发布）。
    "https://127.0.0.1/x.jpg",
    "http://192.0.2.50:8096/emby/Items/1/Images/Primary",
    "https://[::1]/x.jpg",
    "https://2130706433/x.jpg",
    # `@` 混淆（userinfo）
    "https://tp.spfcas.com@evil.com/x.jpg",
    "https://evil.com@tp.spfcas.com/x.jpg",
    "https://user:pw@tp.spfcas.com/x.jpg",
    # 非标端口
    "https://tp.spfcas.com:8080/x.jpg",
    "https://tp.spfcas.com:abc/x.jpg",
    # 空 / 畸形
    "",
    None,
    "tp.spfcas.com/x.jpg",
    "https://",
    "https:///x.jpg",
    "https://localhost/x.jpg",
]


@pytest.mark.parametrize("url", ALLOWED_EXACT)
def test_is_allowed_exact_hosts(imgproxy, url):
    assert imgproxy.is_allowed(url) is True


@pytest.mark.parametrize("url", ALLOWED_SUFFIX)
def test_is_allowed_suffix_hosts(imgproxy, url):
    assert imgproxy.is_allowed(url) is True


@pytest.mark.parametrize("url", REJECTED)
def test_is_allowed_rejects(imgproxy, url):
    assert imgproxy.is_allowed(url) is False


def test_suffix_rule_is_dot_bound(imgproxy, monkeypatch):
    """后缀必须带点：`evil-jdbstatic.com` / 裸域 一律不通过（验收硬用例）。"""
    assert imgproxy.host_allowed("c0.jdbstatic.com") is True
    assert imgproxy.host_allowed("evil-jdbstatic.com") is False
    assert imgproxy.host_allowed("jdbstatic.com") is False
    assert imgproxy.host_allowed("pics.dmm.co.jp") is True
    assert imgproxy.host_allowed("evil-dmm.co.jp") is False
    assert imgproxy.host_allowed("127.0.0.1") is False
    assert imgproxy.host_allowed("") is False
    # 白名单里漏写前导点也必须仍然安全（自动补点，不靠配的人记得）
    monkeypatch.setattr(imgproxy, "ALLOWED_SUFFIXES", ("jdbstatic.com",))
    assert imgproxy.host_allowed("c0.jdbstatic.com") is True
    assert imgproxy.host_allowed("evil-jdbstatic.com") is False


def test_upgrade_scheme_only_for_whitelisted(imgproxy):
    """MetaTube/javtxt 给的 DMM 图是 http → 只给白名单域升级，别的原样退回。"""
    assert imgproxy.upgrade_scheme("http://pics.dmm.co.jp/a/b.jpg") == \
        "https://pics.dmm.co.jp/a/b.jpg"
    assert imgproxy.upgrade_scheme("http://tp.spfcas.com/x.jpg") == \
        "https://tp.spfcas.com/x.jpg"
    assert imgproxy.upgrade_scheme("http://evil-jdbstatic.com/x.jpg") == \
        "http://evil-jdbstatic.com/x.jpg"
    assert imgproxy.upgrade_scheme("https://tp.spfcas.com/x.jpg") == \
        "https://tp.spfcas.com/x.jpg"
    assert imgproxy.upgrade_scheme("http://192.0.2.50/x.jpg") == \
        "http://192.0.2.50/x.jpg"


# ---------------------------------------------------------------------------
# 二、Referer 策略
# ---------------------------------------------------------------------------

def test_referer_policy(imgproxy):
    """每个 host 的 Referer 按实测定；未知 host 走历史默认值。"""
    assert imgproxy.referer_for("tp.spfcas.com") == "https://javdb.com/"
    assert imgproxy.referer_for("images.projectjav.com") == "https://projectjav.com/"
    assert imgproxy.referer_for("cf.javfree.me") == ""
    assert imgproxy.referer_for("img.j-cdn.com") == "https://javtxt.net/"   # 严格：只有它放行
    assert imgproxy.referer_for("pic.duga.jp") == ""
    assert imgproxy.referer_for("raw.githubusercontent.com") == ""
    assert imgproxy.referer_for("c0.jdbstatic.com") == ""                   # 后缀域
    assert imgproxy.referer_for("pics.dmm.co.jp") == ""
    assert imgproxy.referer_for("unknown.example.com") == imgproxy.DEFAULT_REFERER


def test_fetch_sends_referer_per_host(imgproxy, cache_root, monkeypatch):
    jpeg = b"\xff\xd8\xff\xdb" + b"\x00" * 64
    http = _FakeHTTP(jpeg, jpeg)
    monkeypatch.setattr(imgproxy, "_open", http)
    imgproxy.fetch("https://images.projectjav.com/a.jpg")
    imgproxy.fetch("https://img.j-cdn.com/avatar/1.jpg")
    assert http.calls[0]["headers"]["Referer"] == "https://projectjav.com/"
    assert http.calls[1]["headers"]["Referer"] == "https://javtxt.net/"


# ---------------------------------------------------------------------------
# 三、XOR 解包 / 魔数（向后兼容）
# ---------------------------------------------------------------------------

def test_unwrap_passes_plain_images(imgproxy):
    """WebP/PNG/JPEG/GIF 直传（长图是 WebP，必须原样透传）。"""
    webp = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x01" * 16
    png = b"\x89PNG\r\n\x1a\n" + b"\x02" * 20
    jpeg = b"\xff\xd8\xff\xe0" + b"\x03" * 20
    gif = b"GIF89a" + b"\x04" * 20
    for blob in (webp, png, jpeg, gif):
        assert imgproxy.unwrap(blob) == blob
        assert imgproxy.is_plain_image(blob) is True


def test_unwrap_rejects_non_webp_riff(imgproxy):
    """裸 `RIFF` 不等于图片：WAV/AVI 不该被当成"已是图片"放行（本次收紧的点）。"""
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x05" * 16
    assert imgproxy.is_plain_image(wav) is False
    assert imgproxy.unwrap(wav) != wav
    # 但 WebP 仍然直传
    assert imgproxy.is_plain_image(b"RIFF\x24\x00\x00\x00WEBPVP8 ") is True


def test_unwrap_xor_wrapped_jpeg(imgproxy):
    """JavDB 图床的 XOR 包装：首字节为 key，其余逐字节异或。"""
    jpeg = b"\xff\xd8\xff\xdb" + bytes(range(30))
    key = 0x5A
    wrapped = bytes([key]) + bytes(b ^ key for b in jpeg[:-1])
    assert imgproxy.unwrap(wrapped + bytes([jpeg[-1] ^ key])) == jpeg
    assert imgproxy.unwrap(b"\x01\x02") == b"\x01\x02"      # 太短 → 原样返回


def test_media_type_by_magic(imgproxy):
    assert imgproxy.media_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert imgproxy.media_type(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert imgproxy.media_type(b"GIF89a") == "image/gif"
    assert imgproxy.media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert imgproxy.media_type(b"RIFF\x00\x00\x00\x00WAVE") == "application/octet-stream"
    assert imgproxy.media_type(b"<html>") == "application/octet-stream"


# ---------------------------------------------------------------------------
# 四、fetch()：缓存、解包、白名单闸门（签名与行为向后兼容）
# ---------------------------------------------------------------------------

def test_fetch_unwraps_and_caches(imgproxy, cache_root, monkeypatch):
    jpeg = b"\xff\xd8\xff\xdb" + bytes(range(256)) * 2
    key = 0x33
    wrapped = bytes([key]) + bytes(b ^ key for b in jpeg)
    http = _FakeHTTP(wrapped)
    monkeypatch.setattr(imgproxy, "_open", http)

    url = "https://tp.spfcas.com/rhe951l4q/covers/96/96GB0p.jpg"
    assert imgproxy.cached(url) is False
    assert imgproxy.fetch(url) == jpeg
    assert len(http.calls) == 1
    assert imgproxy.cached(url) is True
    # 命中缓存不再发请求
    assert imgproxy.fetch(url) == jpeg
    assert len(http.calls) == 1
    # 缓存文件就在 images 目录下，且不是 emby- 前缀
    files = [p.name for p in (cache_root / "images").glob("*")]
    assert len(files) == 1 and not files[0].startswith("emby-")


def test_fetch_webp_passthrough(imgproxy, cache_root, monkeypatch):
    webp = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x0a" * 32
    monkeypatch.setattr(imgproxy, "_open", _FakeHTTP(webp))
    got = imgproxy.fetch("https://images.projectjav.com/data/screenshots/x.jpg")
    assert got == webp
    assert imgproxy.media_type(got) == "image/webp"


def test_fetch_blocks_before_network(imgproxy, cache_root, monkeypatch):
    """非白名单 / IP / `@` 混淆：一次网络都不发。

    （白名单域的 `http://` 是**故意**升级成 https 后放行的，见 `test_fetch_upgrades_dmm_http`；
    它们在 `is_allowed()` 层面仍然是 False，由 `test_is_allowed_rejects` 覆盖。）
    """
    http = _FakeHTTP()
    monkeypatch.setattr(imgproxy, "_open", http)
    for url in REJECTED:
        if isinstance(url, str) and imgproxy.is_allowed(imgproxy.upgrade_scheme(url)):
            continue
        assert imgproxy.fetch(url) is None
    assert http.calls == []


def test_fetch_upgrades_dmm_http(imgproxy, cache_root, monkeypatch):
    """MetaTube(JAV321) 给的 `http://pics.dmm.co.jp/…` 要能取到，且真的走 https。"""
    jpeg = b"\xff\xd8\xff\xdb" + b"\x0b" * 32
    http = _FakeHTTP(jpeg)
    monkeypatch.setattr(imgproxy, "_open", http)
    got = imgproxy.fetch("http://pics.dmm.co.jp/digital/video/ssis00001/ssis00001ps.jpg")
    assert got == jpeg
    assert http.urls == ["https://pics.dmm.co.jp/digital/video/ssis00001/ssis00001ps.jpg"]
    # 升级后的 URL 与直接传 https 命中同一份缓存
    assert imgproxy.cached("https://pics.dmm.co.jp/digital/video/ssis00001/ssis00001ps.jpg")
    assert imgproxy.fetch("https://pics.dmm.co.jp/digital/video/ssis00001/ssis00001ps.jpg") == jpeg
    assert len(http.calls) == 1


def test_fetch_rejects_non_image_and_http_errors(imgproxy, cache_root, monkeypatch):
    html = b"<!DOCTYPE html><html>403</html>"
    monkeypatch.setattr(imgproxy, "_open", _FakeHTTP(html))
    assert imgproxy.fetch("https://tp.spfcas.com/x.jpg") is None
    monkeypatch.setattr(imgproxy, "_open", _FakeHTTP(OSError("boom")))
    assert imgproxy.fetch("https://tp.spfcas.com/y.jpg") is None


def test_fetch_passes_proxy(imgproxy, cache_root, monkeypatch):
    http = _FakeHTTP(b"\xff\xd8\xff\xdb" + b"\x0c" * 16)
    monkeypatch.setattr(imgproxy, "_open", http)
    imgproxy.fetch("https://tp.spfcas.com/p.jpg", proxy="http://proxy.invalid:7890")
    assert http.calls[0]["proxy"] == "http://proxy.invalid:7890"
    assert http.calls[0]["direct"] is False


# ---------------------------------------------------------------------------
# 五、emby_image()：拼 URL、缓存键、失败降级
# ---------------------------------------------------------------------------

EMBY = "http://192.0.2.50:8096"   # RFC 5737 TEST-NET：假的局域网地址，不泄露真实坐标
# 假密钥：这里**只**用于拼 URL 与缓存键的断言，绝不是真凭据。
# ⚠️ 2026-10-14 修：这个常量原先被写成了本机线上 Emby 的真实 API Key，而 `tests/` 会随
# 公开仓库（`MoviePilot-Plugins-AV/` 子树）一起发布 —— 等于把密钥公开。任何测试都不得内置真凭据。
KEY = "fake-emby-api-key-for-tests"
JPEG = b"\xff\xd8\xff\xe0" + b"\x0d" * 128


def test_emby_image_builds_url_and_uses_direct_connection(imgproxy, cache_root, monkeypatch):
    http = _FakeHTTP(JPEG)
    monkeypatch.setattr(imgproxy, "_open", http)

    assert imgproxy.emby_image(EMBY, KEY, "12598") == JPEG
    assert http.urls == [
        "%s/emby/Items/12598/Images/Primary?api_key=%s" % (EMBY, KEY)]
    # 局域网直连：不走代理
    assert http.calls[0]["direct"] is True
    assert http.calls[0]["proxy"] == ""
    assert http.calls[0]["headers"]["Accept"] == "image/*"


def test_emby_image_host_normalization(imgproxy, cache_root, monkeypatch):
    """`host` 带尾斜杠 / 带 `/emby` / 不带 scheme 都要拼成同一个 URL。"""
    seen = []
    for idx, host in enumerate(("http://192.0.2.50:8096/",
                                "http://192.0.2.50:8096/emby",
                                "192.0.2.50:8096")):
        item = "1259%d" % idx                       # 换 id，免得第二次就命中缓存不发请求
        http = _FakeHTTP(JPEG)
        monkeypatch.setattr(imgproxy, "_open", http)
        imgproxy.emby_image(host, KEY, item)
        seen.append(http.urls[0])
    assert seen == ["%s/emby/Items/1259%d/Images/Primary?api_key=%s" % (EMBY, i, KEY)
                    for i in range(3)]
    assert imgproxy.emby_base("http://192.0.2.50:8096/emby/") == EMBY
    assert imgproxy.emby_base("192.0.2.50:8096") == EMBY
    assert imgproxy.emby_base("") == ""


def test_emby_image_img_type_and_person(imgproxy, cache_root, monkeypatch):
    """`Backdrop/0` 与 `?emby_person=`（就是另一个 item id）都要支持。"""
    http = _FakeHTTP(JPEG, JPEG)
    monkeypatch.setattr(imgproxy, "_open", http)
    imgproxy.emby_image(EMBY, KEY, "12598", "Backdrop/0")
    imgproxy.emby_image(EMBY, KEY, "fake-person-id-0001")   # Person Id
    assert http.urls[0].endswith("/Images/Backdrop/0?api_key=" + KEY)
    assert http.urls[1] == "%s/emby/Items/fake-person-id-0001/Images/Primary?api_key=%s" % (EMBY, KEY)


def test_emby_cache_key_is_separate_from_url_cache(imgproxy, cache_root, monkeypatch):
    """emby 图与普通 URL 图、不同 img_type、不同 item 的缓存键必须互不相同。"""
    http = _FakeHTTP(JPEG, JPEG, JPEG, JPEG)
    monkeypatch.setattr(imgproxy, "_open", http)
    url = "https://tp.spfcas.com/rhe951l4q/covers/96/96GB0p.jpg"
    imgproxy.fetch(url)
    imgproxy.emby_image(EMBY, KEY, "12598")
    imgproxy.emby_image(EMBY, KEY, "12598", "Thumb")
    imgproxy.emby_image(EMBY, KEY, "12599")
    names = sorted(p.name for p in (cache_root / "images").glob("*"))
    assert len(names) == 4, names
    emby_files = [n for n in names if n.startswith("emby-")]
    assert len(emby_files) == 3
    url_file = [n for n in names if not n.startswith("emby-")][0]
    # 缓存键是 sha1("emby:<id>:<type>")，绝不可能撞上 sha1(URL)
    emby_name = os.path.basename(imgproxy.emby_cache_path("12598"))
    assert emby_name in names and emby_name.startswith("emby-") and emby_name != url_file
    assert imgproxy.emby_cache_path("12598") == imgproxy.emby_cache_path("12598", "Primary")
    assert imgproxy.emby_cache_path("12598") != imgproxy.emby_cache_path("12598", "Thumb")
    assert imgproxy.emby_cache_path("12598") != imgproxy.emby_cache_path("12599")
    # 与 URL 图的缓存路径不可能同一条（前缀 + 摘要口径都不同）
    assert imgproxy.emby_cache_path("12598") != imgproxy._cache_path(url)
    # 二次调用命中磁盘缓存：不再发请求
    assert imgproxy.emby_image(EMBY, KEY, "12598") == JPEG
    assert len(http.calls) == 4
    assert imgproxy.cached_emby("12598") is True
    assert imgproxy.cached_emby("12598", "Thumb") is True
    assert imgproxy.cached_emby("nope") is False


def test_emby_image_failure_paths(imgproxy, cache_root, monkeypatch):
    # 1. 非图片响应（Emby 的 404 HTML）→ None，且不落缓存
    monkeypatch.setattr(imgproxy, "_open", _FakeHTTP(b"<html>not found</html>"))
    assert imgproxy.emby_image(EMBY, KEY, "404") is None
    assert imgproxy.cached_emby("404") is False
    # 2. 网络异常 → None（不抛）
    monkeypatch.setattr(imgproxy, "_open", _FakeHTTP(OSError("connection refused")))
    assert imgproxy.emby_image(EMBY, KEY, "12598") is None
    # 3. 空响应 → None
    monkeypatch.setattr(imgproxy, "_open", _FakeHTTP(b""))
    assert imgproxy.emby_image(EMBY, KEY, "12598") is None
    # 4. 缺参不发请求
    http = _FakeHTTP()
    monkeypatch.setattr(imgproxy, "_open", http)
    assert imgproxy.emby_image("", KEY, "12598") is None
    assert imgproxy.emby_image(EMBY, "", "12598") is None
    assert imgproxy.emby_image(EMBY, KEY, "") is None
    assert http.calls == []


def test_emby_image_quotes_weird_ids(imgproxy, cache_root, monkeypatch):
    """item_id 里的怪字符要被百分号编码，别让它改变路径结构。"""
    http = _FakeHTTP(JPEG)
    monkeypatch.setattr(imgproxy, "_open", http)
    imgproxy.emby_image(EMBY, KEY, "12/../34?x=1")
    assert http.urls[0].startswith("%s/emby/Items/12%%2F..%%2F34%%3Fx%%3D1/Images/Primary" % EMBY)


# ---------------------------------------------------------------------------
# 六、crop_poster()：四种 anchor + 竖图直传 + 降级
# ---------------------------------------------------------------------------

def _dominant(blob: bytes, x: int, y: int):
    Image = pytest.importorskip("PIL.Image")
    with Image.open(io.BytesIO(blob)) as img:
        return img.convert("RGB").getpixel((x, y))


def _decoded_size(blob: bytes):
    Image = pytest.importorskip("PIL.Image")
    with Image.open(io.BytesIO(blob)) as img:
        return img.size


def test_crop_poster_portrait_passthrough(imgproxy):
    """原生竖图（ratio <= 0.80）原图直传，一个字节都不改。"""
    Image = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    Image.new("RGB", (534, 800), (10, 20, 30)).save(buf, "JPEG")
    raw = buf.getvalue()
    out, meta = imgproxy.crop_poster(raw)
    assert out is raw or out == raw
    assert meta["mode"] == "raw" and meta["reason"] == "portrait"
    assert meta["source_size"] == [534, 800] and meta["size"] == [534, 800]
    # 边界：ratio 正好 0.80 也算竖图
    buf2 = io.BytesIO()
    Image.new("RGB", (800, 1000), (0, 0, 0)).save(buf2, "JPEG")
    _, meta2 = imgproxy.crop_poster(buf2.getvalue())
    assert meta2["reason"] == "portrait"


@pytest.mark.parametrize("anchor,expect", [("right", "right"), ("center", "center"),
                                           ("left", "left")])
def test_crop_poster_anchors_crop_the_right_side(imgproxy, anchor, expect):
    """四种 anchor：裁出来的图必须可解码、比例接近 377/538、且真的裁在对应那一侧。"""
    raw, _ = _bands()
    out, meta = imgproxy.crop_poster(raw, anchor=anchor)
    assert meta["mode"] == "cropped" and meta["anchor"] == expect
    assert meta["source_size"] == [1400, 1000]
    width, height = meta["size"]
    assert [width, height] == list(_decoded_size(out))
    assert abs(width / height - 377 / 538) < 0.01
    assert abs(width - round(1000 * 377 / 538)) <= 1
    r, g, b = _dominant(out, width // 2, height // 2)
    order = {"left": r, "center": g, "right": b}
    # 命中色带的通道必须是主通道
    assert order[expect] == max(r, g, b), (anchor, (r, g, b))


def test_crop_poster_raw_anchor_keeps_bytes(imgproxy):
    raw, _ = _bands()
    out, meta = imgproxy.crop_poster(raw, anchor="raw")
    assert out == raw
    assert meta["mode"] == "raw" and meta["reason"] == "anchor_raw"
    assert meta["source_size"] == [1400, 1000] and meta["size"] == [1400, 1000]


@pytest.mark.parametrize("kwargs,expect", [
    ({}, "right"),
    ({"is_fc2": True}, "center"),
    ({"is_vr": True}, "center"),
    ({"is_amateur": True}, "center"),
])
def test_crop_poster_auto_anchor(imgproxy, kwargs, expect):
    """`auto` → FC2 / VR / 素人走 center，其余走 right。"""
    raw, _ = _bands()
    out, meta = imgproxy.crop_poster(raw, anchor="auto", **kwargs)
    assert meta["anchor"] == expect
    width, height = meta["size"]
    r, g, b = _dominant(out, width // 2, height // 2)
    assert (g if expect == "center" else b) == max(r, g, b)


def test_crop_poster_unknown_anchor_falls_back_to_auto(imgproxy):
    """认不出的 anchor 与 `auto` 完全同效（meta 里记的是**实际生效**的那一侧）。"""
    raw, _ = _bands()
    _, unknown = imgproxy.crop_poster(raw, anchor="bottom-ish")
    _, auto = imgproxy.crop_poster(raw, anchor="auto")
    assert unknown == auto
    assert unknown["anchor"] == "right"
    _, unknown_vr = imgproxy.crop_poster(raw, anchor="bottom-ish", is_vr=True)
    _, auto_vr = imgproxy.crop_poster(raw, anchor="auto", is_vr=True)
    assert unknown_vr == auto_vr and unknown_vr["anchor"] == "center"
    # 大小写/空白也不该改变判定
    assert imgproxy.crop_poster(raw, anchor=" RIGHT ")[1]["anchor"] == "right"


def test_crop_poster_target_wider_than_source_is_not_cropped(imgproxy):
    """目标比原图还宽时无处可裁 → 原图返回（别把图裁成 1px）。"""
    raw, _ = _bands(1000, 1000)          # ratio 1.0，target_ratio 给到 1.2
    out, meta = imgproxy.crop_poster(raw, target_ratio=1.2)
    assert out == raw and meta["reason"] == "no_crop_needed"


def test_crop_poster_decode_error_returns_raw(imgproxy):
    """不是图片的字节 → 原图返回 + `decode_error`，绝不抛异常。"""
    junk = b"\x00\x01\x02not-an-image" * 4
    out, meta = imgproxy.crop_poster(junk)
    assert out == junk
    assert meta["mode"] == "raw" and meta["reason"] == "decode_error"
    assert meta["size"] is None
    assert imgproxy.crop_poster(b"")[1]["reason"] == "decode_error"


def test_crop_poster_without_pillow(imgproxy, monkeypatch):
    """无 Pillow 降级：monkeypatch 顶掉 import（`sys.modules["PIL"] = None`）。"""
    raw = b"\xff\xd8\xff\xdb" + b"\x0e" * 32
    monkeypatch.setitem(sys.modules, "PIL", None)        # 让 `from PIL import Image` 报错
    monkeypatch.setattr(imgproxy, "_PIL_TRIED", False)
    monkeypatch.setattr(imgproxy, "_PIL_IMAGE", None)
    out, meta = imgproxy.crop_poster(raw, anchor="right")
    assert out == raw                                     # 原图直传
    assert meta["mode"] == "raw" and meta["reason"] == "no_pillow"
    assert meta["anchor"] == "right"
    assert imgproxy._pillow_image() is None               # 结果被记住，不再反复重试


def test_crop_poster_output_is_decodable_at_real_poster_ratio(imgproxy):
    """真实尺寸样例（javdb 封面 800×538）走一遍，输出必须是可解码的 JPEG。"""
    Image = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    Image.new("RGB", (800, 538), (200, 30, 30)).save(buf, "JPEG")
    out, meta = imgproxy.crop_poster(buf.getvalue(), anchor="right")
    assert meta["mode"] == "cropped"
    assert meta["source_size"] == [800, 538]
    assert _decoded_size(out) == tuple(meta["size"])
    assert out[:2] == b"\xff\xd8"
