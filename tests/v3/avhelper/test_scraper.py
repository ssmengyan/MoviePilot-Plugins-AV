"""`scraper.py`（S7 刮削编排核心）的单测。

**零外网**：javdb-cli（子进程）、Javtxt HTTP、MetaTube HTTP、Emby HTTP、LLM 全部被顶掉 ——
- javdb-cli：`subprocess.run` 被 monkeypatch 成脚本化的假进程；
- 两个 HTTP 源：`scraper.http_get` 被 monkeypatch 成按 URL 分派的假响应；
- Emby：`FakeEmby` 假对象（同时**计数写方法调用**，用来验证"预览零写请求"与备份闸门）；
- LLM：本机 `translator.py` 尚未落地 → 天然走降级；另有一条用例显式注入假 translator。

覆盖的硬性验收点（任务书 §硬性验收 2）：
`resolve_key` 三种输入 / `film_view` 形状与无 meta 行降级 / Javtxt 搜索强校验（串号必须判不命中）/
MetaTube 串号拦截 / 写入矩阵"拿不到就跳过该字段" / 备份闸门 / Tier1 退避序列 /
`preview_one` 零写请求。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
PKG_NAME = "avhelper_under_test"          # 与 conftest.py 同名同缓存键：模块只加载一次


# ---------------------------------------------------------------------------
# 模块加载（自足：不依赖 conftest 的 fixture，但共用同一份模块缓存）
# ---------------------------------------------------------------------------

def _install_stubs() -> None:
    """宿主 `app.sdk.*` 空壳（conftest 已经装过就跳过）。"""
    if "app.sdk.logging" in sys.modules:
        return
    for name in ("app", "app.sdk"):
        sys.modules.setdefault(name, types.ModuleType(name))
    log = types.ModuleType("app.sdk.logging")

    class _Logger:
        def __getattr__(self, _name):
            return lambda *a, **k: None

    log.logger = _Logger()
    sys.modules["app.sdk.logging"] = log
    net = types.ModuleType("app.sdk.network")

    class _RequestUtils:
        def __init__(self, *a, **k):
            pass

    net.RequestUtils = _RequestUtils
    sys.modules["app.sdk.network"] = net


def _load(name: str):
    """按文件路径加载插件模块（与 conftest 的合成包共用缓存键）。"""
    _install_stubs()
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
def scraper():
    """`scraper` 模块。"""
    return _load("scraper")


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """★ **零外网硬闸门**：任何真的 HTTP 调用都当场炸掉，而不是悄悄连出去。

    顶掉的是 `urllib.request` 的两个入口（`scraper.http_get` 与 `imgproxy.fetch` 都走它）；
    用例自己 monkeypatch `scraper.http_get` 时，这个闸门对它自然失效（那正是我们要的假响应）。
    """
    import urllib.request

    def boom(*args, **kwargs):
        raise AssertionError("单测不许发网络请求（见 no_real_network 夹具）")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(urllib.request, "build_opener", boom)


@pytest.fixture(autouse=True)
def no_real_translator(monkeypatch, scraper):
    """★ 默认摘掉 `translator`：S4 落地后 `translate_batch()` 会走真 LLM 网关。

    本模块的"零外网"是硬要求，所以默认降级；要验翻译链的用例自己 `monkeypatch.setattr`
    一个假 translator（夹具先跑、用例后设，后者生效）。
    """
    monkeypatch.setattr(scraper, "translator", None)


@pytest.fixture(scope="session")
def emby_mod():
    return _load("emby")


@pytest.fixture(scope="session")
def store_mod():
    return _load("store")


def make_store(store_mod, tmp_path, name="avhelper.db"):
    store = store_mod.Store(db_path=tmp_path / name)
    store.init()
    return store


# ---------------------------------------------------------------------------
# 假对象
# ---------------------------------------------------------------------------

class FakeStore:
    """记录每一次写入的假 `Store`（`preview_one` 的"零写"断言靠它）。"""

    def __init__(self, meta=None, items=None, downloads=None, backup=""):
        self.meta = dict(meta or {})
        self.items = list(items or [])
        self.downloads = dict(downloads or {})
        self.backup = backup
        self.logs = []
        self.calls = {"meta_get": 0, "meta_upsert": 0, "item_list": 0, "item_upsert": 0,
                      "item_set": 0, "item_backup_save": 0, "item_backup_get": 0,
                      "download_map": 0, "scrape_log_add": 0}
        self.writes = {"meta_upsert": 0, "item_upsert": 0, "item_set": 0, "item_backup_save": 0}

    # --- 读 ---
    def meta_get(self, key):
        self.calls["meta_get"] += 1
        return dict(self.meta) if self.meta else None

    def item_list(self, key="", **filters):
        self.calls["item_list"] += 1
        return [dict(r) for r in self.items if not key or r.get("key") == key]

    def download_map(self, sources=None):
        self.calls["download_map"] += 1
        return dict(self.downloads)

    def item_backup_get(self, item_key):
        self.calls["item_backup_get"] += 1
        return self.backup

    # --- 写（preview 必须全部为 0）---
    def meta_upsert(self, key, **fields):
        self.calls["meta_upsert"] += 1
        self.writes["meta_upsert"] += 1
        self.meta.update(fields)

    def item_upsert(self, item_key, key, **fields):
        self.calls["item_upsert"] += 1
        self.writes["item_upsert"] += 1

    def item_set(self, item_key, **fields):
        self.calls["item_set"] += 1
        self.writes["item_set"] += 1
        return True

    def item_backup_save(self, item_key, dto_json):
        self.calls["item_backup_save"] += 1
        self.writes["item_backup_save"] += 1
        if self.backup:
            return False
        self.backup = str(dto_json or "")
        return bool(self.backup)

    def scrape_log_add(self, source_name, status, key="", latency_ms=0, error_summary=""):
        self.calls["scrape_log_add"] += 1
        self.logs.append({"source": source_name, "status": status, "key": key,
                          "error": error_summary})


WRITE_METHODS = ("update_item", "upload_image", "delete_image")


class FakeEmby:
    """假 `EmbyClient`：读走 `dto`，写全部计数（默认成功）。"""

    def __init__(self, dto=None, ready=True, update_ok=True, get_raises=False):
        self.dto = dict(dto or {})
        self._ready = ready
        self.update_ok = update_ok
        self.get_raises = get_raises
        self.calls = {"ready": 0, "get_item": 0, "update_item": 0, "upload_image": 0,
                      "delete_image": 0}
        self.updated = []
        self.uploaded = []
        self.deleted = []

    def ready(self):
        self.calls["ready"] += 1
        return self._ready

    def get_item(self, item_id, user_id=""):
        self.calls["get_item"] += 1
        if self.get_raises:
            raise RuntimeError("Emby 抽风")
        return dict(self.dto) if self.dto else None

    def update_item(self, item_id, dto):
        self.calls["update_item"] += 1
        self.updated.append({"item_id": item_id, "dto": dict(dto)})
        return (self.update_ok, "" if self.update_ok else "HTTP 500")

    def upload_image(self, item_id, img_type, raw):
        self.calls["upload_image"] += 1
        self.uploaded.append({"item_id": item_id, "type": img_type, "bytes": bytes(raw)})
        return (True, "")

    def delete_image(self, item_id, img_type):
        self.calls["delete_image"] += 1
        self.deleted.append({"item_id": item_id, "type": img_type})
        return (True, "")

    def writes(self):
        return {name: self.calls[name] for name in WRITE_METHODS}


class FakeCli:
    """假 `JavdbClient`：`detail` 走脚本，`bin_path`/`proxy` 供图片下载拼命令行。"""

    def __init__(self, detail=None, error="", bin_path="/fake/javdb", proxy="http://px:1"):
        self._detail = detail
        self._error = error
        self.bin_path = bin_path
        self.proxy = proxy
        self.calls = {"detail": 0}

    def detail(self, number, mid="", with_magnets=False):
        self.calls["detail"] += 1
        return dict(self._detail) if isinstance(self._detail, dict) else None

    def last_error(self, key):
        return self._error


class FakeLibrary:
    """假 `EmbyLibrary`：记录 `lookup`/`index`/`invalidate` 的调用次数。"""

    def __init__(self, hit=None):
        self.hit = hit
        self.calls = {"lookup": 0, "index": 0, "invalidate": 0}

    def lookup(self, number):
        self.calls["lookup"] += 1
        return dict(self.hit) if self.hit else None

    def index(self):
        self.calls["index"] += 1
        return {}

    def invalidate(self):
        self.calls["invalidate"] += 1


# ---------------------------------------------------------------------------
# 真实样本（照 `_tmp/s0a/evidence/` 的实测 HTML 抄写，规则与站点一致）
# ---------------------------------------------------------------------------

EMPTY_DTO = {
    "Id": "12598", "Name": "SNOS-380", "Path": "/Media/9kg/avi/SNOS-380.mp4",
    "Etag": "abc123", "Overview": "", "ProviderIds": {}, "People": [], "Studios": [],
    "Genres": [], "GenreItems": [], "MediaSources": [{"Path": "/Media/9kg/avi/SNOS-380.mp4"}],
    "RunTimeTicks": 99493394000, "ImageTags": {}, "Panic": "should-be-dropped",
}

JAVDB_DETAIL = {
    "id": "96GB0p",
    "number": "SNOS-380",
    "title": "地味OLが中年キモ上司にバレた隠れエロボディ… 雛形みくる",
    "origin_title": "地味OLが中年キモ上司にバレた隠れエロボディ… 雛形みくる",
    "summary": None,
    "release_date": "2026-10-14",
    "duration": 170,
    "score": "4.33",
    "maker_name": "S1 NO.1 STYLE",
    "publisher_name": None,
    "series_name": None,
    "director_name": "肉尊",
    "cover_url": "https://tp.spfcas.com/rhe951l4q/covers/96/96GB0p.jpg",
    "thumb_url": "https://tp.spfcas.com/rhe951l4q/small_covers/96/96GB0p.jpg",
    "preview_video_url": "https://jdforrepam.com/x.m3u8",
    "has_cnsub": False,
    "magnets_count": 7,
    "magnets": [{"magnet": "magnet:?xt=urn:btih:" + "a" * 40, "title": "x" * 400}] * 40,
    "comments": [{"text": "c" * 500}] * 20,
    "actors": [{"id": "YPKz", "name": "トニー大木", "avatar_url": "https://a/1.jpg", "gender": 1},
               {"id": "neAOa", "name": "雛形みくる", "avatar_url": "https://a/2.jpg", "gender": 0}],
    "tags": [{"id": "114", "name": "OL"}, {"id": "17", "name": "巨乳"}],
    "preview_images": [
        {"large_url": "https://tp.spfcas.com/rhe951l4q/samples/96/96GB0p_l_0.jpg",
         "thumb_url": "https://tp.spfcas.com/rhe951l4q/samples/96/96GB0p_s_0.jpg"},
        {"large_url": "https://tp.spfcas.com/rhe951l4q/samples/96/96GB0p_l_7.jpg",
         "thumb_url": "https://tp.spfcas.com/rhe951l4q/samples/96/96GB0p_s_7.jpg"},
    ],
}

# `javdb assets list SNOS-380 --json` 的真实形状（截自容器内实测输出）
ASSETS_JSON = [
    {"type": "image", "url": "https://tp.spfcas.com/x/small_covers/96/96GB0p.jpg",
     "width": 147, "height": 200},
    {"type": "image", "url": "https://tp.spfcas.com/rhe951l4q/covers/96/96GB0p.jpg",
     "width": 800, "height": 538},
    {"type": "image", "url": "https://tp.spfcas.com/x/samples/96/96GB0p_l_0.jpg",
     "width": 147, "height": 200},
    {"type": "image", "url": "https://tp.spfcas.com/x/samples/96/96GB0p_l_1.jpg",
     "width": 800, "height": 534},
    {"type": "image", "url": "https://tp.spfcas.com/x/samples/96/96GB0p_l_2.jpg",
     "width": 800, "height": 534},
    {"type": "image", "url": "https://tp.spfcas.com/x/samples/96/96GB0p_l_3.jpg",
     "width": 534, "height": 800},
    {"type": "image", "url": "https://tp.spfcas.com/x/samples/96/96GB0p_l_4.jpg",
     "width": 800, "height": 450},
    {"type": "video",
     "url": "https://jdforrepam.com/api/v1/movies/ttm3u8/preview/1/0/720p.m3u8",
     "width": 768, "height": 432, "duration": 104},
]

JAVTXT_SEARCH_HTML = """<!doctype html><html><body>
<div class="main">
    <h1 class="title is-4">搜索: SNOS-380</h1>
    <div class="works">
        <a class="work" href="/v/558149">
            <h4 class="work-id">SNOS-380</h4>
            <h4 class="work-title">平凡OL的隐藏色气身材被中年猥琐上司撞破</h4>
            <div class="work-meta">
                <span class="work-meta-studio">🎥 S1 NO.1 STYLE</span>
                <span>📅 2026-10-09</span>
            </div>
            <div class="work-actresses">
                <span class="work-actress"><img class="avatar" src="https://img.j-cdn.com/avatar/60390.jpg">
                    雛形みくる</span>
            </div>
        </a>
    </div>
</div></body></html>"""

# 串号搜索结果：卡片上的番号与目标不同（javtxt 是模糊匹配，必须判不命中）
JAVTXT_SEARCH_WRONG = """<div class="works">
    <a class="work" href="/v/490714">
        <h4 class="work-id">MIDV-946</h4>
        <h4 class="work-title">别人的标题</h4>
    </a>
    <a class="work" href="/v/546431">
        <h4 class="work-id">IPOK-025</h4>
        <h4 class="work-title">也是别人的标题</h4>
    </a>
</div>"""

JAVTXT_SEARCH_EMPTY = """<div class="main"><h1 class="title is-4">搜索: CAWB-040</h1>
    <div class="works"></div></div>"""

JAVTXT_DETAIL_HTML = """<!doctype html><html><head><title>SNOS-380 …</title></head><body>
<nav class="navbar"><a class="navbar-item" href="/top-videos">🔥热门</a></nav>
<div class="main">
    <nav class="breadcrumb has-succeeds-separator" aria-label="breadcrumbs">
        <ul>
            <li><a href="/studio/763">エスワン ナンバーワンスタイル</a></li>
            <li><a href="/label/1035">SNOS</a></li>
            <li class="is-active"><a href="#" aria-current="page">snos-380</a></li>
        </ul>
    </nav>
    <h1 class="title is-4 text-jp">地味OLが中年キモ上司にバレた隠れエロボディ… 雛形みくる</h1>
    <h2 class="title is-4 text-zh">平凡OL的隐藏色气身材被中年猥琐上司撞破</h2>
    <div class="info">
        <div class="intro">
            <dl class="dl-actress subtitle">
                <dd>出演女优</dd>
                <dt>
                    <a class="actress" href="/actress/60390"><img class="avatar"
                        src="https://img.j-cdn.com/avatar/60390.jpg"> 雛形みくる</a>
                    <!-- <a class="actress"><img class="avatar"
                        src="http://pics.dmm.co.jp/mono/actjpgs/tuzi_azuki.jpg"> 辻あずき</a>
                    <a class="actress"><img class="avatar"
                        src="http://pics.dmm.co.jp/mono/actjpgs/tuzi_azuki.jpg"> 辻あずき</a> -->
                </dt>
            </dl>
            <div class="intro-header">
                <h5 class="subtitle is-5">剧情介绍</h5>
                <div class="tabs is-toggle is-small"><ul class="btns-lang">
                    <li><a><span>日文</span></a></li>
                    <li class="is-active btn-lang-zh"><a><span>中文</span></a></li>
                </ul></div>
            </div>
            <p class="text-jp">役所で事務作業を行う後輩社員の雛形はどこにでもいる口数が少なく
黙々と真面目に働く地味な女子社員。</p>
            <div class="text-zh">
                <p>在政府部门从事事务性工作的后辈雏形，是一个随处可见、沉默寡言且工作勤恳的平凡女职员。</p>
                <p>从今天起，你就是我的女人了，呵呵。</p>
                <div class="zh-tip">中文简介来自机翻，不准确请谅解</div>
            </div>
        </div>
        <div class="attributes">
            <dl>
                <dd>🆔 番号</dd><dt>snos-380 (snos00380)</dt>
                <dd>📅 发行时间</dd><dt>2026-10-09</dt>
                <dd>🎥 片商</dd><dt><a href="/studio/763">S1 NO.1 STYLE</a></dt>
                <dd>👨‍🏫 导演</dd><dt><a href="/producer/3251">肉尊</a></dt>
                <dd>🏷️ 类别</dd>
                <dt><a class="tag is-white" href="/genre/213">苗条</a>
                    <a class="tag is-white" href="/genre/382">性高潮</a></dt>
            </dl>
        </div>
    </div>
</div>
<footer><div class="rank"><a class="actress">排行榜里的无关演员</a></div></footer>
</body></html>"""

# MetaTube 的真实"串号"响应形状（查 SNOS-380 返回 DUGA 的 FSDSS 系列）
METATUBE_MISMATCH = {"data": [
    {"id": "faleno-0771", "number": "FSDSS-732", "title": "别人的标题", "provider": "DUGA",
     "summary": "别人的简介"},
    {"id": "faleno-0747", "number": "FSDSS-715", "title": "别人的标题2", "provider": "DUGA",
     "summary": "别人的简介2"},
]}


def targets(sources, **patch):
    """构造一个 `target`（`gather()` 的产出形状），供写入矩阵用例逐字段拆解。"""
    base = {
        "key": "SNOS380", "display_number": "SNOS-380", "javdb_id": "96GB0p",
        "title_jp": "日文标题", "origin_title": "日文原标题", "title_zh": "中文标题",
        "plot_jp": "日文简介", "plot_zh": "中文简介", "plot_source": "javtxt",
        "translation_status": "done", "actors": [{"id": "a", "name": "雛形みくる"}],
        "tags": ["OL", "巨乳"], "raw_tags": [], "studio": "S1 NO.1 STYLE", "series": "",
        "director": "肉尊", "release_date": "2026-10-14", "duration": 170, "score": "4.33",
        "cover_url": "https://tp.spfcas.com/covers/x.jpg", "thumb_url": "",
        "preview_video_url": "", "has_cnsub": False, "preview_images": [],
        "version_tags": {}, "completeness": "full", "sources": sources, "warnings": [],
    }
    base.update(patch)
    return base


# ---------------------------------------------------------------------------
# 1. resolve_key
# ---------------------------------------------------------------------------

class TestResolveKey:
    """三种输入（展示番号 / 归一化键 / 实例键）都要收敛到同一套坐标。"""

    def test_display_number(self, scraper):
        got = scraper.resolve_key("SNOS-380")
        assert got["key"] == "SNOS380"
        assert got["number"] == "SNOS-380" and got["display_number"] == "SNOS-380"
        assert got["kind"] == "number" and got["matched"] is True
        assert got["emby_id"] == ""

    def test_normalized_key(self, scraper):
        """归一化键要能反推展示番号（`SNOS380` → `SNOS-380`）。"""
        got = scraper.resolve_key("SNOS380")
        assert got["key"] == "SNOS380"
        assert got["display_number"] == "SNOS-380"

    def test_lowercase_and_zero_padded(self, scraper):
        """零填充写法归一到同一个 `norm_key`。

        ⚠️ `display_number` 这里**故意用容差断言**：S2 的 `parse_av_number("ipzz00961")`
        目前回 `IPZZ-00961`（保留原填充），而 v4.1 §5.1 写的是 `f"{prefix}-{int(digits):03d}"`
        → `IPZZ-961`；`test_parse_number.py` 只锁了 `norm_key`、没锁这一项。
        这是 **S2 侧的口径缺口，已回报主统筹**，S7 不在这里改别人的输出。
        """
        got = scraper.resolve_key("ipzz00961")
        assert got["key"] == "IPZZ961"
        assert got["display_number"] in ("IPZZ-961", "IPZZ-00961")

    def test_version_suffix_kept_out_of_key(self, scraper):
        """D1：新层用干净号（`IPZZ912`），同时把版本标签带出来。"""
        got = scraper.resolve_key("IPZZ-912-UC.mp4")
        assert got["key"] == "IPZZ912"
        assert got["version_tags"].get("is_zh_sub") and got["version_tags"].get("is_uncensored_leak")

    def test_item_key(self, scraper):
        got = scraper.resolve_key("emby:12598")
        assert got["kind"] == "emby" and got["emby_id"] == "12598"
        assert got["item_key"] == "emby:12598"

    def test_item_key_argument_wins(self, scraper):
        got = scraper.resolve_key("SNOS-380", "emby:12598")
        assert got["emby_id"] == "12598" and got["number"] == ""     # 实例键优先
        assert got["item_key"] == "emby:12598"

    def test_pure_digits_is_emby_id(self, scraper):
        """纯数字 = Emby 实例 id（P0 试点就是 `12598` 这种写法）。

        ⚠️ 这条**必须在 `parse_av_number` 之前判**：实测 `parse_av_number("12598")`
        会把裸数字解析成 `125-098`（`matched=True`），任何"先 parse 再兜底"的写法都会
        把 Emby id 当成番号，进而去 javdb 查一个不存在的 `125-098`。
        这条已连同 `parse_av_number` 的裸数字行为一起回报主统筹。
        """
        got = scraper.resolve_key("12598")
        assert got["emby_id"] == "12598" and got["key"] == "" and got["number"] == ""
        assert got["item_key"] == "emby:12598"

    def test_fullwidth_is_normalized(self, scraper):
        """NFKC：全角写法（ＳＮＯＳ－３８０）也要认得出来。"""
        got = scraper.resolve_key("ＳＮＯＳ－３８０")
        assert got["key"] == "SNOS380"


# ---------------------------------------------------------------------------
# 2. 版本角标 / 退避序列 / 分档
# ---------------------------------------------------------------------------

class TestVersionAndBackoff:

    def test_labels_order_and_merge(self, scraper):
        labels = scraper.version_labels({"is_zh_sub": True, "is_uncensored_leak": True,
                                         "resolution": "4K", "edition": "l"})
        assert labels == ["中字流出", "4K", "L"]

    def test_badge_text(self, scraper):
        assert scraper.version_badge({"is_zh_sub": True}) == " [中字]"
        assert scraper.version_badge({}) == ""

    def test_backoff_sequence(self, scraper):
        """6h → 24h → 72h → 7d → 14d，跑完 5 档不再排。"""
        now = "2026-10-14T00:00:00"
        want = ["2026-10-14T06:00:00", "2026-10-15T00:00:00", "2026-10-17T00:00:00",
                "2026-10-21T00:00:00", "2026-10-28T00:00:00"]
        count = 0
        for step, due in enumerate(want, start=1):
            count, stamp = scraper.apply_backoff("missing_plot", count, now)
            assert count == step and stamp == due
        count, stamp = scraper.apply_backoff("missing_plot", count, now)
        assert count == 6 and stamp == ""                # 跑完 5 档就不再排

    def test_missing_core_never_schedules(self, scraper):
        assert scraper.apply_backoff("missing_core", 0, "2026-10-14T00:00:00") == (0, "")
        assert scraper.apply_backoff("missing_core", 3, "2026-10-14T00:00:00") == (3, "")

    def test_full_resets(self, scraper):
        assert scraper.apply_backoff("full", 4, "2026-10-14T00:00:00") == (0, "")

    def test_completeness_and_state(self, scraper):
        assert scraper.completeness_of("", "", "") == "missing_core"
        assert scraper.completeness_of("", "日文", "") == "missing_plot"
        assert scraper.completeness_of("中文", "日文", "简介") == "full"
        assert scraper.scrape_state_of("full") == "scraped_full"
        assert scraper.scrape_state_of("missing_plot") == "scraped_partial"
        assert scraper.scrape_state_of("missing_core") == "unscraped"


# ---------------------------------------------------------------------------
# 3. Javtxt 解析与强校验
# ---------------------------------------------------------------------------

class TestJavtxt:

    def test_parse_search(self, scraper):
        cards = scraper.parse_javtxt_search(JAVTXT_SEARCH_HTML)
        assert cards == [{"id": "558149", "url": "/v/558149", "number": "SNOS-380",
                          "title": "平凡OL的隐藏色气身材被中年猥琐上司撞破"}]

    def test_search_strong_validation_rejects_wrong_number(self, scraper):
        """★ 硬性验收：构造一个串号返回 → 必须判**不命中**，不许猜条。"""
        cards = scraper.parse_javtxt_search(JAVTXT_SEARCH_WRONG)
        assert [c["number"] for c in cards] == ["MIDV-946", "IPOK-025"]
        assert scraper.pick_javtxt_hit(cards, "SNOS380") is None
        assert scraper.pick_javtxt_hit(cards, "MIDV946") == cards[0]   # 同号那条才认

    def test_parse_detail_selectors(self, scraper):
        got = scraper.parse_javtxt_detail(JAVTXT_DETAIL_HTML)
        assert got["title_jp"] == "地味OLが中年キモ上司にバレた隠れエロボディ… 雛形みくる"
        assert got["title_zh"] == "平凡OL的隐藏色气身材被中年猥琐上司撞破"
        assert got["plot_jp"].startswith("役所で事務作業を行う後輩社員")
        assert "从今天起，你就是我的女人了" in got["plot_zh"]
        assert "机翻" not in got["plot_zh"]                      # `.zh-tip` 不算正文
        assert got["zh_is_machine"] is True
        assert got["studio"] == "エスワン ナンバーワンスタイル"
        assert got["number_written"] == "snos-380"
        assert got["director"] == "肉尊"
        assert got["release_date"] == "2026-10-09"
        assert got["tags"] == ["苗条", "性高潮"]

    def test_comments_stripped_from_actors(self, scraper):
        """坑 1：注释里塞的是别的演员（辻あずき），不剥注释就会写进 Emby 的 People。"""
        got = scraper.parse_javtxt_detail(JAVTXT_DETAIL_HTML)
        assert [a["name"] for a in got["actors"]] == ["雛形みくる"]
        assert got["actors"][0]["avatar_url"] == "https://img.j-cdn.com/avatar/60390.jpg"
        assert "辻あずき" not in json.dumps(got, ensure_ascii=False)

    def test_no_sidebar_actors(self, scraper):
        """坑 2：页面底部的排行榜不在 `dl-actress` 里，不许被抽进来。"""
        got = scraper.parse_javtxt_detail(JAVTXT_DETAIL_HTML)
        assert "排行榜里的无关演员" not in [a["name"] for a in got["actors"]]

    def test_variants(self, scraper):
        variants = scraper.javtxt_variants("IPZZ-912")
        assert variants[0] == "IPZZ-912"
        assert "IPZZ912" in variants and "912" in variants
        assert scraper.javtxt_variants("") == []

    def test_prefers_first_matching_variant(self, scraper, monkeypatch):
        """搜索要按变体顺位试；第一枪就命中就不要再打第二枪（站点间隔很贵）。"""
        seen = []

        def fake_get(url, **kwargs):
            seen.append(url)
            if "/v/" in url:
                return JAVTXT_DETAIL_HTML.encode(), "", 200
            body = JAVTXT_SEARCH_HTML if "q=SNOS-380" in url else JAVTXT_SEARCH_EMPTY
            return body.encode(), "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        got = scraper.javtxt_lookup({"javtxt_interval": 0}, "SNOS-380")
        assert got["ok"] and got["status"] == "ok"
        assert got["title_zh"] and got["plot_zh"]
        assert len(seen) == 2                       # 1 次搜索 + 1 次详情
        assert "/v/558149" in seen[1]

    def test_zero_hit_returns_empty_not_guessed(self, scraper, monkeypatch):
        """实测 `IPZZ-912`/`CAWB-040` 0 命中：如实回空，交给 MetaTube 兜底。"""
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (JAVTXT_SEARCH_EMPTY.encode(), "", 200))
        got = scraper.javtxt_lookup({"javtxt_interval": 0, "javtxt_hosts": ("https://j.test",)},
                                    "CAWB-040")
        assert got["ok"] is False and got["status"] == "miss"
        assert got["title_zh"] == "" and got["plot_zh"] == ""

    def test_wrong_number_search_is_miss(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (JAVTXT_SEARCH_WRONG.encode(), "", 200))
        got = scraper.javtxt_lookup({"javtxt_interval": 0, "javtxt_hosts": ("https://j.test",)},
                                    "SNOS-380")
        assert got["ok"] is False and got["status"] == "miss"

    def test_http_error_is_logged_not_raised(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (None, "HTTP 429", 429))
        store = FakeStore()
        got = scraper.javtxt_lookup({"javtxt_interval": 0, "javtxt_hosts": ("https://j.test",)},
                                    "SNOS-380", store=store, key="SNOS380")
        assert got["ok"] is False and got["status"] == "miss"
        assert "429" in got["error"]
        assert [row["status"] for row in store.logs] == ["miss"]
        assert store.logs[0]["source"] == "javtxt"

    def test_real_saved_html_if_present(self, scraper):
        """仓库里若留着 S0a 的真实取证 HTML，就顺手在真实页面上验一遍选择器。"""
        base = PLUGIN_DIR.parents[2] / "_tmp" / "s0a" / "evidence"
        detail = base / "v_558149.html"
        search = base / "search_SNOS-380.html"
        if not detail.exists() or not search.exists():
            pytest.skip("_tmp/s0a/evidence 不在（临时目录不入库）")
        cards = scraper.parse_javtxt_search(search.read_text(encoding="utf-8", errors="replace"))
        hit = scraper.pick_javtxt_hit(cards, "SNOS380")
        assert hit and hit["id"] == "558149"
        got = scraper.parse_javtxt_detail(detail.read_text(encoding="utf-8", errors="replace"))
        assert got["title_zh"] and got["plot_zh"] and got["title_jp"]
        assert [a["name"] for a in got["actors"]] == ["雛形みくる"]


# ---------------------------------------------------------------------------
# 4. MetaTube 串号拦截
# ---------------------------------------------------------------------------

class TestMetaTube:

    def test_pick_rejects_all_mismatch(self, scraper):
        hit, count, mismatch = scraper.pick_metatube_hit(METATUBE_MISMATCH["data"], "SNOS380")
        assert hit is None and count == 2 and mismatch is True

    def test_pick_never_takes_first(self, scraper):
        """★ 硬性验收：命中项在第 2 位时也必须取命中的那条，绝不退回 `items[0]`。"""
        items = [{"number": "FSDSS-732", "summary": "别人的"},
                 {"number": "SNOS-380", "summary": "对的"}]
        hit, count, mismatch = scraper.pick_metatube_hit(items, "SNOS380")
        assert hit is not None and hit["summary"] == "对的"
        assert count == 2 and mismatch is False

    def test_lookup_reports_mismatch(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (json.dumps(METATUBE_MISMATCH).encode(), "", 200))
        store = FakeStore()
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380",
                                      store=store, key="SNOS380")
        assert got["status"] == "mismatch" and got["mismatch"] is True
        assert got["plot_jp"] == ""                       # 绝不采纳别人的简介
        assert got["candidates"] == 2
        assert store.logs[0]["status"] == "mismatch"

    def test_lookup_ok(self, scraper, monkeypatch):
        payload = {"data": [{"number": "SNOS-380", "provider": "JAV321", "id": "snos00380",
                             "summary": "日文简介", "title": "日文标题"}]}
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (json.dumps(payload).encode(), "", 200))
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380")
        assert got["ok"] and got["plot_jp"] == "日文简介" and got["provider"] == "JAV321"

    def test_empty_result_is_miss_not_error(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (b'{"data":[]}', "", 200))
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380")
        assert got["status"] == "miss" and got["mismatch"] is False

    def test_404_is_business_empty_no_retry(self, scraper, monkeypatch):
        """★ S0b：`404` 是业务空值（30 个源都没收录），**不许重试**（重试只会再等 10 秒）。"""
        calls = []
        sleeps = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return None, "HTTP 404", 404

        monkeypatch.setattr(scraper, "http_get", fake_get)
        monkeypatch.setattr(scraper.time, "sleep", lambda s: sleeps.append(s))
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380")
        assert got["status"] == "empty" and got["error"] == ""
        assert len(calls) == 1 and sleeps == []              # 一次就是一次

    def test_5xx_retries_with_backoff(self, scraper, monkeypatch):
        """只有 5xx/超时才退避重试，≤2 次，间隔 1s → 3s。"""
        calls = []
        sleeps = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if len(calls) < 3:
                return None, "HTTP 503", 503
            return b'{"data":[]}', "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        monkeypatch.setattr(scraper.time, "sleep", lambda s: sleeps.append(s))
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380")
        assert len(calls) == 3 and sleeps == [1.0, 3.0]
        assert got["status"] == "miss"

    def test_timeout_gives_up_after_two_retries(self, scraper, monkeypatch):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return None, "TimeoutError: timed out", 0

        monkeypatch.setattr(scraper, "http_get", fake_get)
        monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380")
        assert got["status"] == "error" and len(calls) == 3
        assert "TimeoutError" in got["error"]

    def test_default_timeout_is_at_least_25s(self, scraper):
        """S0b：search 恒定 ~10s，HTTP 超时给 10 秒会把正常等待误判成超时。"""
        assert scraper.METATUBE_TIMEOUT >= 25
        assert scraper.DEFAULT_OPTS["metatube_timeout"] >= 25

    def test_whole_source_down_is_tolerated(self, scraper, monkeypatch):
        """S0b：JAV321 上游已删目录，将来整源不可用要能容忍（空 + 记日志，不抛）。"""
        store = FakeStore()
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (None, "HTTP 404", 404))
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "SNOS-380",
                                      store=store, key="SNOS380")
        assert got["ok"] is False and got["movie"] == {}
        assert store.logs[0]["status"] == "empty"

    def test_missing_actors_key_is_tolerated(self, scraper):
        """S0b：`actors` 只有 8/40 条响应才有（omitempty）→ 读的时候必须 `or []`。"""
        movie = scraper.metatube_movie({"number": "MIDV-946", "title": "x"})
        assert movie["actors"] == [] and movie["genres"] == [] and movie["preview_images"] == []


# ---------------------------------------------------------------------------
# 5. javdb 骨架 / 资产 / raw_json 瘦身
# ---------------------------------------------------------------------------

class TestJavdb:

    def test_skeleton_from_detail(self, scraper):
        cli = FakeCli(detail=JAVDB_DETAIL)
        sk = scraper.javdb_skeleton(cli, "SNOS-380")
        assert sk["ok"] and sk["title_jp"].startswith("地味OL")
        assert sk["javdb_id"] == "96GB0p" and sk["release_date"] == "2026-10-14"
        assert sk["duration"] == 170 and sk["score"] == "4.33"
        assert sk["maker"] == "S1 NO.1 STYLE" and sk["director"] == "肉尊"
        assert len(sk["actors"]) == 2 and sk["has_cnsub"] is False

    def test_skeleton_uses_cache_without_calling_javdb(self, scraper):
        """契约 §5.3「只补缺不重抓」：有 raw_json['javdb'] 时一次 javdb 都不打。"""
        cli = FakeCli(detail=JAVDB_DETAIL)
        raw = scraper.trim_javdb_raw(scraper.javdb_skeleton(cli, "SNOS-380"))
        before = cli.calls["detail"]
        sk = scraper.javdb_skeleton(cli, "SNOS-380", raw=raw)
        assert cli.calls["detail"] == before          # 没再调
        assert sk["ok"] and sk["title_jp"] and sk["cover_url"]
        assert sk["from_cache"] is True

    def test_skeleton_error_leaves_trace(self, scraper):
        store = FakeStore()
        sk = scraper.javdb_skeleton(FakeCli(detail=None, error="站点超时"), "SNOS-380",
                                    store=store, key="SNOS380")
        assert sk["ok"] is False and "站点超时" in sk["error"]
        assert store.logs[0]["source"] == "javdb" and store.logs[0]["status"] == "error"

    def test_trim_drops_magnets_and_comments(self, scraper):
        raw = scraper.trim_javdb_raw(JAVDB_DETAIL)
        text = json.dumps(raw, ensure_ascii=False)
        assert "magnets" not in text and "comments" not in text
        assert len(text) <= scraper.JAVDB_RAW_LIMIT
        assert raw["id"] == "96GB0p" and raw["cover_url"]

    def test_pack_raw_json_budget(self, scraper):
        """`raw_json` 总体积 ≤5KB，且塞满时优先砍 samples/actors 而不是丢标识字段。"""
        fat = dict(JAVDB_DETAIL)
        fat["actors"] = [{"id": f"a{i}", "name": f"演员{i}" * 6} for i in range(60)]
        fat["tags"] = [{"id": str(i), "name": f"标签{i}" * 6} for i in range(120)]
        raw = scraper.pack_raw_json(scraper.trim_javdb_raw(fat, limit=10 ** 6),
                                    {"url": "u", "plot_zh": "x" * 900},
                                    {"provider": "DUGA", "candidates": 3})
        text = json.dumps(raw, ensure_ascii=False)
        assert len(text) <= scraper.RAW_JSON_LIMIT
        assert raw["javdb"]["id"] == "96GB0p"
        assert raw["javdb"]["cover_url"]

    def test_parse_assets_positions(self, scraper):
        assets = scraper.parse_assets_list(ASSETS_JSON)
        images = [a for a in assets if a["type"] == "image"]
        assert len(images) == 7
        assert [a["idx"] for a in images] == [1, 2, 3, 4, 5, 6, 7]
        video = [a for a in assets if a["type"] == "video"]
        assert video and video[0]["idx"] == 1 and video[0]["duration"] == 104

    def test_pick_assets_cover_and_landscape_samples(self, scraper):
        assets = scraper.parse_assets_list(ASSETS_JSON)
        picked = scraper.pick_assets(assets, cover_url=JAVDB_DETAIL["cover_url"])
        assert picked["cover"]["url"].endswith("/covers/96/96GB0p.jpg")
        assert len(picked["samples"]) == 3
        for row in picked["samples"]:
            assert row["width"] > row["height"]          # 只要横版
            assert row["url"] != picked["cover"]["url"]

    def test_pick_assets_falls_back_to_largest(self, scraper):
        assets = scraper.parse_assets_list(ASSETS_JSON)
        picked = scraper.pick_assets(assets, cover_url="")   # 没有 cover_url 提示
        assert picked["cover"]["url"].endswith("/covers/96/96GB0p.jpg")

    def test_pick_assets_no_geometry_no_samples(self, scraper):
        assets = scraper.parse_assets_list([
            {"type": "video", "url": "https://x/v.m3u8", "width": 768, "height": 432}])
        picked = scraper.pick_assets(assets, cover_url="")
        assert picked["cover"] is None and picked["samples"] == []


# ---------------------------------------------------------------------------
# 6. javdb-cli 图片管道（`assets download` 只认 TYPE<TAB>URL）
# ---------------------------------------------------------------------------

class _FakeProc:
    def __init__(self, code, out=b"", err=b""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


class TestAssetsPipeline:
    """`assets download` 的管道语义：喂 JSON 会被拒（实测），所以列表必须走管道格式。"""

    def test_download_uses_pipe_format(self, scraper, monkeypatch, tmp_path):
        seen = []
        assets = [a for a in scraper.parse_assets_list(ASSETS_JSON) if a["type"] == "image"][:2]
        urls = [a["url"] for a in assets]

        def fake_run(cmd, **kwargs):
            seen.append({"cmd": list(cmd), "stdin": kwargs.get("input")})
            if "list" in cmd:
                if "--json" in cmd:
                    return _FakeProc(0, json.dumps(ASSETS_JSON).encode())
                # `assets list <n> --type image 1,2` 的管道格式：TYPE<TAB>URL
                return _FakeProc(0, "".join(f"image\t{u}\n" for u in urls).encode())
            # download：把两个文件写进 -d 指定的目录，并逐行回路径
            out_dir = cmd[cmd.index("-d") + 1]
            lines = []
            for index in (1, 2):
                path = Path(out_dir) / f"image-{index:03d}.jpg"
                path.write_bytes(b"\xff\xd8\xff" + bytes([index]))
                lines.append(str(path))
            return _FakeProc(0, ("\n".join(lines) + "\n").encode())

        monkeypatch.setattr(scraper.subprocess, "run", fake_run)
        blobs = scraper.javdb_assets_download(FakeCli(), "SNOS-380", assets,
                                             opts={"javdb_timeout": 5})
        assert set(blobs) == set(urls)                       # 第 i 行输出 ↔ 第 i 个选择器
        assert blobs[urls[0]] == b"\xff\xd8\xff\x01"
        list_call, download_call = seen[0], seen[1]
        assert "--type" in list_call["cmd"] and "1,2" in list_call["cmd"]
        assert "--json" not in list_call["cmd"]              # 管道步不能带 --json
        assert download_call["cmd"][-2] == "-d"
        assert download_call["stdin"] == "".join(f"image\t{u}\n" for u in urls).encode()
        # 临时目录必须被清掉
        assert not Path(download_call["cmd"][-1]).exists()

    def test_download_skips_when_selector_count_mismatch(self, scraper, monkeypatch):
        def fake_run(cmd, **kwargs):
            if "list" in cmd:
                return _FakeProc(0, b"image\thttps://a/1.jpg\n")     # 只回 1 条，却要 2 张
            raise AssertionError("记录数对不上时不该发起下载")

        monkeypatch.setattr(scraper.subprocess, "run", fake_run)
        assets = [a for a in scraper.parse_assets_list(ASSETS_JSON) if a["type"] == "image"][:2]
        assert scraper.javdb_assets_download(FakeCli(), "SNOS-380", assets, opts={}) == {}

    def test_download_needs_position(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper.subprocess, "run",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不该起进程")))
        assert scraper.javdb_assets_download(FakeCli(), "SNOS-380",
                                            [{"type": "image", "url": "u"}], opts={}) == {}

    def test_assets_list_failure_returns_empty(self, scraper, monkeypatch):
        store = FakeStore()
        monkeypatch.setattr(scraper.subprocess, "run",
                            lambda *a, **k: _FakeProc(1, b"", b"proxy unreachable"))
        assert scraper.javdb_assets(FakeCli(), "SNOS-380", store=store) == []
        assert store.logs[0]["status"] == "error"

    def test_assets_list_ok(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper.subprocess, "run",
                            lambda *a, **k: _FakeProc(0, json.dumps(ASSETS_JSON).encode()))
        got = scraper.javdb_assets(FakeCli(), "SNOS-380")
        assert len(got) == 8


# ---------------------------------------------------------------------------
# 7. 写入矩阵：拿不到就跳过该字段
# ---------------------------------------------------------------------------

class TestWriteMatrix:
    """★ 硬性验收：构造各种半残 target → 覆盖表里**没有**该键。"""

    def test_full_target_fields(self, scraper):
        out = scraper.build_overrides(targets({}), EMPTY_DTO)
        assert out["Name"] == "SNOS-380 中文标题"
        assert out["OriginalTitle"] == "日文标题"
        assert out["Overview"] == "中文简介"
        assert out["PremiereDate"] == "2026-10-14T00:00:00.0000000Z"
        assert out["ProductionYear"] == 2026
        assert out["Studios"] == [{"Name": "S1 NO.1 STYLE"}]
        assert out["GenreItems"] == [{"Name": "OL"}, {"Name": "巨乳"}]
        assert out["CommunityRating"] == 4.33
        assert out["ProviderIds"] == {"AVHelper": "SNOS-380", "JavDB": "96GB0p"}
        assert [p["Type"] for p in out["People"] if p["Type"] == "Director"] == ["Director"]

    def test_name_needs_title(self, scraper):
        out = scraper.build_overrides(targets({}, title_zh="", title_jp=""), EMPTY_DTO)
        assert "Name" not in out
        # 契约：`OriginalTitle` 取 `title_jp`，为空时退 `origin_title`，仍为空才不动
        assert out["OriginalTitle"] == "日文原标题"
        out = scraper.build_overrides(
            targets({}, title_zh="", title_jp="", origin_title=""), EMPTY_DTO)
        assert "Name" not in out and "OriginalTitle" not in out

    def test_name_badge(self, scraper):
        out = scraper.build_overrides(
            targets({}, version_tags={"is_zh_sub": True, "is_uncensored_leak": True}),
            EMPTY_DTO)
        assert out["Name"] == "SNOS-380 [中字流出] 中文标题"

    def test_missing_release_date_skips_both(self, scraper):
        out = scraper.build_overrides(targets({}, release_date=""), EMPTY_DTO)
        assert "PremiereDate" not in out and "ProductionYear" not in out

    def test_bad_release_date_format_skips(self, scraper):
        out = scraper.build_overrides(targets({}, release_date="2026/10"), EMPTY_DTO)
        assert "PremiereDate" not in out and "ProductionYear" not in out

    def test_missing_studio_and_series(self, scraper):
        out = scraper.build_overrides(targets({}, studio="", series=""), EMPTY_DTO)
        assert "Studios" not in out and "SeriesName" not in out

    def test_series_is_passed_when_present(self, scraper):
        """契约 §3.6.1 要求写 `SeriesName`；S2 的白名单目前没有它（已回报主统筹）。"""
        out = scraper.build_overrides(targets({}, series="雛形みくる全集"), EMPTY_DTO)
        assert out["SeriesName"] == "雛形みくる全集"

    def test_missing_tags_skips_genre_items(self, scraper):
        out = scraper.build_overrides(targets({}, tags=[]), EMPTY_DTO)
        assert "GenreItems" not in out and "Genres" not in out

    def test_genre_limit_and_dedupe(self, scraper):
        out = scraper.build_overrides(targets({}, tags=[f"t{i}" for i in range(30)]), EMPTY_DTO)
        assert len(out["GenreItems"]) == 10

    def test_bad_score_skips_rating(self, scraper):
        for value in ("", None, "N/A", 0, "0"):
            out = scraper.build_overrides(targets({}, score=value), EMPTY_DTO)
            assert "CommunityRating" not in out, value

    def test_plot_zh_empty_with_plot_jp_clears_overview(self, scraper):
        """矩阵明确要求的唯一"写空"例外：清掉旧的错误机翻。"""
        out = scraper.build_overrides(targets({}, plot_zh="", plot_jp="日文简介"), EMPTY_DTO)
        assert out["Overview"] == ""

    def test_both_plots_empty_skips_overview(self, scraper):
        out = scraper.build_overrides(targets({}, plot_zh="", plot_jp=""), EMPTY_DTO)
        assert "Overview" not in out

    def test_never_writes_forbidden_fields(self, scraper):
        """§3.6.2 实测：这几个字段写了要么无效要么有害，永远不许出现在覆盖表里。"""
        out = scraper.build_overrides(targets({}), EMPTY_DTO)
        for name in ("RunTimeTicks", "RemoteTrailers", "SortName", "ForcedSortName",
                     "LockedFields", "Taglines", "OfficialRating", "Genres"):
            assert name not in out, name

    def test_provider_ids_are_incremental(self, scraper):
        """P0-① 铁律：只给增量，S2 内部合并（整份覆盖会抹掉 MetaTube 的键）。"""
        out = scraper.build_overrides(targets({}), EMPTY_DTO)
        assert "provider_ids_replace" not in out

    def test_people_name_format_and_no_id(self, scraper, monkeypatch):
        """D13/D14：`中文（日文）`、**不写 Id**、保留非 Actor/Director 元素。"""
        monkeypatch.setattr(scraper, "actor_display",
                            lambda name, alias="": {"name": str(name), "jp": str(name),
                                                    "zh": {"雛形みくる": "雏形实久"}.get(str(name), ""),
                                                    "alias": ""})
        original = {"People": [{"Name": "監督", "Type": "Producer", "Id": "9"},
                               {"Name": "老演员", "Type": "Actor", "Id": "1"}]}
        out = scraper.build_overrides(targets({}), original)
        people = out["People"]
        names = [p["Name"] for p in people]
        assert "雛形みくる" not in names
        assert "雏形实久（雛形みくる）" in names
        assert "肉尊" in names
        for person in people:
            if person["Type"] in ("Actor", "Director"):
                assert "Id" not in person                  # D14：写 Id 会被彻底忽略
        assert people[0] == {"Name": "監督", "Type": "Producer", "Id": "9"}   # 原样保留
        assert {p["Type"] for p in people} == {"Producer", "Actor", "Director"}

    def test_person_name_single_side(self, scraper):
        assert scraper.person_name({"name": "x", "zh": "雏形实久", "jp": ""}) == "雏形实久"
        assert scraper.person_name({"name": "x", "zh": "", "jp": "雛形みくる"}) == "雛形みくる"
        assert scraper.person_name({"name": "x", "zh": "同名", "jp": "同名"}) == "同名"
        assert scraper.person_name({"name": "", "zh": "", "jp": ""}) == ""

    def test_field_diff_covers_whole_matrix(self, scraper):
        out = scraper.build_overrides(targets({}), EMPTY_DTO)
        diff = scraper.field_diff(EMPTY_DTO, out)
        names = [row["name"] for row in diff]
        for name in scraper.MATRIX_FIELDS:
            assert name in names
        assert all(set(row) == {"name", "current", "target", "changed"} for row in diff)
        assert next(r for r in diff if r["name"] == "Name")["changed"] is True
        assert next(r for r in diff if r["name"] == "Overview")["changed"] is True

    def test_field_diff_marks_unchanged(self, scraper):
        dto = dict(EMPTY_DTO, Name="SNOS-380 中文标题")
        out = scraper.build_overrides(targets({}), dto)
        row = next(r for r in scraper.field_diff(dto, out) if r["name"] == "Name")
        assert row["changed"] is False


# ---------------------------------------------------------------------------
# 8. 备份闸门 + 写路径（假 Emby）
# ---------------------------------------------------------------------------

class TestWriteGate:

    def _write(self, scraper, store, emby, target=None, **kwargs):
        return scraper.write_item(
            store, emby, target or targets({}), item_key="emby:12598", key="SNOS380",
            emby_id="12598", opts={"now": "2026-10-14T00:00:00", "write_images": False},
            **kwargs)

    def test_backup_gate_blocks_write(self, scraper):
        """★ 硬性验收：没有非空备份就不许写（`item_backup_save` 落空 + `get` 回空）。"""
        store = FakeStore()
        store.item_backup_save = lambda item_key, dto_json: False       # 备份落不进去
        emby = FakeEmby(dto=EMPTY_DTO)
        report = self._write(scraper, store, emby)
        assert report["status"] == "blocked" and report["ok"] is False
        assert emby.writes() == {"update_item": 0, "upload_image": 0, "delete_image": 0}
        assert "备份" in report["error"]

    def test_backup_gate_blocks_when_dto_unreadable(self, scraper):
        store = FakeStore(backup="{}")
        emby = FakeEmby(dto=None)
        report = self._write(scraper, store, emby)
        assert report["status"] == "error"
        assert emby.calls["update_item"] == 0

    def test_write_ok_after_backup(self, scraper):
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        report = self._write(scraper, store, emby)
        assert report["ok"] and report["status"] == "ok"
        assert emby.calls["update_item"] == 1
        assert store.writes["item_backup_save"] == 1
        assert store.writes["meta_upsert"] == 1 and store.writes["item_upsert"] == 1
        sent = emby.updated[0]["dto"]
        assert sent["Name"] == "SNOS-380 中文标题"
        assert "Panic" not in sent                      # 只发覆盖表，不整份回灌
        assert report["completeness"] == "full"

    def test_existing_backup_is_not_overwritten(self, scraper):
        store = FakeStore(backup=json.dumps(EMPTY_DTO, ensure_ascii=False))
        emby = FakeEmby(dto=EMPTY_DTO)
        report = self._write(scraper, store, emby)
        assert report["ok"] and store.calls["item_backup_save"] == 1
        assert emby.calls["update_item"] == 1

    def test_nothing_to_write(self, scraper):
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        target = targets({}, display_number="", title_zh="", title_jp="", origin_title="",
                         plot_zh="", plot_jp="", release_date="", studio="", series="",
                         tags=[], score="", javdb_id="", actors=[], director="")
        report = self._write(scraper, store, emby, target=target)
        assert report["status"] == "nothing" and emby.calls["update_item"] == 0
        assert store.writes["item_backup_save"] == 0        # 没东西可写就别去动备份

    def test_update_failure_keeps_state_clean(self, scraper):
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO, update_ok=False)
        report = self._write(scraper, store, emby)
        assert report["ok"] is False and "HTTP 500" in report["error"]
        assert store.writes["meta_upsert"] == 0         # 写失败不留"已刮"的假状态

    def test_no_emby_client_degrades(self, scraper):
        store = FakeStore()
        report = self._write(scraper, store, None)
        assert report["status"] == "no_emby"
        assert store.writes["meta_upsert"] == 1         # 取数结果仍然落 meta
        assert store.writes["item_upsert"] == 1

    def test_library_invalidate_called(self, scraper):
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        library = FakeLibrary()
        report = self._write(scraper, store, emby, library=library)
        assert report["ok"] and library.calls["invalidate"] == 1

    def test_images_uploaded_once_and_cropped(self, scraper, monkeypatch):
        """同一张图只下一次：封面 → Primary、剧照 → Backdrop/0..2 + Thumb（复用字节）。"""
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        assets = scraper.parse_assets_list(ASSETS_JSON)
        monkeypatch.setattr(scraper, "javdb_assets_download",
                            lambda *a, **k: {a["url"] if isinstance(a, dict) else "": b""
                                             for a in []} | {
                                "https://tp.spfcas.com/rhe951l4q/covers/96/96GB0p.jpg":
                                    b"\xff\xd8\xff-covers",
                                "https://tp.spfcas.com/x/samples/96/96GB0p_l_1.jpg":
                                    b"\xff\xd8\xff-s1",
                                "https://tp.spfcas.com/x/samples/96/96GB0p_l_2.jpg":
                                    b"\xff\xd8\xff-s2",
                                "https://tp.spfcas.com/x/samples/96/96GB0p_l_4.jpg":
                                    b"\xff\xd8\xff-s3",
                            })
        monkeypatch.setattr(scraper, "_crop", lambda raw, anchor, t: (raw, {"mode": "raw"}))
        report = scraper.write_item(
            store, emby, targets({}), item_key="emby:12598", key="SNOS380", emby_id="12598",
            opts={"now": "2026-10-14T00:00:00", "write_images": True}, assets=assets,
            cli=FakeCli())
        assert report["ok"]
        types = [row["type"] for row in emby.uploaded]
        assert types == ["Primary", "Backdrop/0", "Thumb", "Backdrop/1", "Backdrop/2"]
        assert emby.uploaded[0]["bytes"] == b"\xff\xd8\xff-covers"
        assert emby.uploaded[1]["bytes"] == emby.uploaded[2]["bytes"]

    def test_crop_poster_missing_degrades_to_raw(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "imgproxy", None)
        raw, meta = scraper._crop(b"jpeg", "right", {})
        assert raw == b"jpeg" and meta["reason"] == "no_imgproxy"

    def test_crop_poster_failure_degrades(self, scraper, monkeypatch):
        class Boom:
            @staticmethod
            def crop_poster(*a, **k):
                raise ValueError("坏了")

        monkeypatch.setattr(scraper, "imgproxy", Boom)
        raw, meta = scraper._crop(b"jpeg", "right", {})
        assert raw == b"jpeg" and meta["mode"] == "raw" and "error" in meta["reason"]


# ---------------------------------------------------------------------------
# 9. preview_one：零写请求
# ---------------------------------------------------------------------------

class TestPreview:
    """★ 硬性验收：`preview_one` 的写方法调用次数必须是 0。"""

    def _opts(self, **patch):
        base = {"now": "2026-10-14T00:00:00", "javtxt_interval": 0,
                "javtxt_hosts": ("https://j.test",), "metatube_base": "http://mt:8080",
                "http_timeout": 5}
        base.update(patch)
        return base

    def _patch_http(self, scraper, monkeypatch):
        """假 HTTP：**按 URL 形状分派，而不是按主机名**（测试里 javtxt 用的是 `j.test`）。"""
        def fake_get(url, **kwargs):
            if "/search" in url:
                return JAVTXT_SEARCH_HTML.encode(), "", 200
            if "/v/" in url:
                return JAVTXT_DETAIL_HTML.encode(), "", 200
            if "/v1/movies/search" in url:
                return json.dumps({"data": []}).encode(), "", 200
            raise AssertionError(f"不该请求 {url}")

        monkeypatch.setattr(scraper, "http_get", fake_get)

    def test_preview_makes_zero_write_calls(self, scraper, monkeypatch):
        self._patch_http(scraper, monkeypatch)
        # `assets list` 是 javdb-cli 子进程，单测里换成夹具（它仍然是**只读**调用）
        monkeypatch.setattr(scraper, "javdb_assets",
                            lambda *a, **k: scraper.parse_assets_list(ASSETS_JSON))
        store = FakeStore(meta={"actors": [], "raw": {}})
        emby = FakeEmby(dto=EMPTY_DTO)
        report = scraper.preview_one("emby:12598", store=store, cli=FakeCli(detail=JAVDB_DETAIL),
                                     emby_client=emby, opts=self._opts(emby_id="12598"))
        assert emby.writes() == {"update_item": 0, "upload_image": 0, "delete_image": 0}
        assert store.writes == {"meta_upsert": 0, "item_upsert": 0, "item_set": 0,
                                "item_backup_save": 0}
        assert report["emby_id"] == "12598"
        assert report["number"] == "SNOS-380"          # 从 DTO 的 Path 反推
        assert report["images"]["cover"].endswith("/covers/96/96GB0p.jpg")
        assert len(report["images"]["samples"]) == 3
        assert report["completeness"] == "full"
        names = [row["name"] for row in report["fields"]]
        assert "Name" in names and "ProviderIds" in names
        name_row = next(r for r in report["fields"] if r["name"] == "Name")
        assert name_row["current"] == "SNOS-380"
        assert name_row["target"] == "SNOS-380 平凡OL的隐藏色气身材被中年猥琐上司撞破"
        assert name_row["changed"] is True

    def test_preview_no_emby_still_works(self, scraper, monkeypatch):
        self._patch_http(scraper, monkeypatch)
        monkeypatch.setattr(scraper, "javdb_assets",
                            lambda *a, **k: scraper.parse_assets_list(ASSETS_JSON))
        report = scraper.preview_one("SNOS-380", store=FakeStore(),
                                     cli=FakeCli(detail=JAVDB_DETAIL), emby_client=None,
                                     opts=self._opts())
        assert report["fields"]
        assert report["emby_id"] == ""
        assert any("Emby 条目" in w for w in report["warnings"])

    def test_preview_warns_on_metatube_mismatch(self, scraper, monkeypatch):
        def fake_get(url, **kwargs):
            if "/v1/movies/search" in url:
                return json.dumps(METATUBE_MISMATCH).encode(), "", 200
            if "/search" in url:
                return JAVTXT_SEARCH_EMPTY.encode(), "", 200        # javtxt 0 命中
            raise AssertionError("0 命中时不该抓 Javtxt 详情")

        monkeypatch.setattr(scraper, "http_get", fake_get)
        monkeypatch.setattr(scraper, "javdb_assets", lambda *a, **k: [])
        report = scraper.preview_one("SNOS-380", store=FakeStore(),
                                     cli=FakeCli(detail=dict(JAVDB_DETAIL, title="日文标题")),
                                     emby_client=None, opts=self._opts())
        assert any("串号拦截" in w for w in report["warnings"])
        assert report["sources"]["metatube"]["status"] == "mismatch"
        assert report["sources"]["metatube"]["candidates"] == 2
        assert report["completeness"] == "missing_plot"      # 有标题没中文简介

    def test_preview_degrades_without_translator(self, scraper, monkeypatch):
        """`translator.py` 未落地 → 只用原文，`untranslated`，且不编造中文。"""
        monkeypatch.setattr(scraper, "translator", None)
        monkeypatch.setattr(scraper, "javdb_assets", lambda *a, **k: [])

        def fake_get(url, **kwargs):
            if "/v1/movies/search" in url:
                return json.dumps({"data": []}).encode(), "", 200
            return JAVTXT_SEARCH_EMPTY.encode(), "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        report = scraper.preview_one("SNOS-380", store=FakeStore(),
                                     cli=FakeCli(detail=dict(JAVDB_DETAIL, title="日文标题")),
                                     emby_client=None,
                                     opts=self._opts(plot_sources=("javtxt", "metatube")))
        assert report["translation_status"] == "untranslated"
        assert report["title_zh"] == ""
        assert next(r for r in report["fields"] if r["name"] == "Name")["target"] == \
            "SNOS-380 日文标题"


# ---------------------------------------------------------------------------
# 10. scrape_one / Tier1 退避 / 真实 Store 落库
# ---------------------------------------------------------------------------

class TestScrapeOne:

    def _opts(self, **patch):
        base = {"now": "2026-10-14T00:00:00", "javtxt_interval": 0,
                "javtxt_hosts": ("https://j.test",), "metatube_base": "http://mt:8080",
                "write_images": False, "javdb_assets": False, "http_timeout": 5}
        base.update(patch)
        return base

    def test_scrape_one_writes_and_schedules_retry(self, scraper, store_mod, tmp_path,
                                                  monkeypatch):
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_HTML.encode() if "/search" in url else JAVTXT_DETAIL_HTML.encode(),
            "", 200))
        emby = FakeEmby(dto=EMPTY_DTO)
        report = scraper.scrape_one("SNOS-380", store=store, cli=FakeCli(detail=JAVDB_DETAIL),
                                    emby_client=emby, opts=self._opts())
        assert report["ok"] and report["status"] == "ok"
        assert emby.calls["update_item"] == 1
        assert store.item_backup_get("emby:12598")
        meta = store.meta_get("SNOS380")
        assert meta["title_zh"].startswith("平凡OL")
        assert meta["plot_zh"] and meta["completeness"] == "full"
        assert meta["retry_count"] == 0 and meta["next_retry_at"] == ""
        item = store.item_get("emby:12598")
        assert item["scrape_state"] == "scraped_full"
        assert item["library_state"] == "in_library"
        assert json.dumps(meta["raw"], ensure_ascii=False).__len__() <= scraper.RAW_JSON_LIMIT
        assert store.scrape_log_summary()

    def test_missing_plot_schedules_6h(self, scraper, store_mod, tmp_path, monkeypatch):
        """★ 硬性验收：`missing_plot` → retry_count=1、next_retry_at=now+6h。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_EMPTY.encode(), "", 200))
        emby = FakeEmby(dto=EMPTY_DTO)
        report = scraper.scrape_one(
            "SNOS-380", store=store, cli=FakeCli(detail=dict(JAVDB_DETAIL, title="日文标题")),
            emby_client=emby, opts=self._opts())
        assert report["completeness"] == "missing_plot"
        assert report["retry"] == {"retry_count": 1, "next_retry_at": "2026-10-14T06:00:00"}

    def test_retry_backoff_full_sequence(self, scraper, store_mod, tmp_path, monkeypatch):
        """连续 5 轮 `missing_plot` → 6h/24h/72h/7d/14d，第 6 轮不再排。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_EMPTY.encode(), "", 200))
        want = ["2026-10-14T06:00:00", "2026-10-15T00:00:00", "2026-10-17T00:00:00",
                "2026-10-21T00:00:00", "2026-10-28T00:00:00"]
        for index, due in enumerate(want, start=1):
            scraper.scrape_one(
                "SNOS-380", store=store,
                cli=FakeCli(detail=dict(JAVDB_DETAIL, title="日文标题")),
                emby_client=FakeEmby(dto=EMPTY_DTO),
                opts=self._opts(force=True))
            meta = store.meta_get("SNOS380")
            assert meta["retry_count"] == index, index
            assert meta["next_retry_at"] == due, index
        scraper.scrape_one("SNOS-380", store=store,
                           cli=FakeCli(detail=dict(JAVDB_DETAIL, title="日文标题")),
                           emby_client=FakeEmby(dto=EMPTY_DTO), opts=self._opts(force=True))
        assert store.meta_get("SNOS380")["next_retry_at"] == ""

    def test_tier1_retry_skips_javdb(self, scraper, store_mod, tmp_path, monkeypatch):
        """★ 契约 §5.3「只补缺不重抓」：raw_json['javdb'] 在 → 一次 javdb 都不打。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        cli = FakeCli(detail=JAVDB_DETAIL)
        raw = scraper.trim_javdb_raw(scraper.javdb_skeleton(cli, "SNOS-380"))
        store.meta_upsert("SNOS380", display_number="SNOS-380", raw_json={"javdb": raw},
                          completeness="missing_plot")
        before = cli.calls["detail"]
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_HTML.encode() if "/search" in url else JAVTXT_DETAIL_HTML.encode(),
            "", 200))
        report = scraper.scrape_one("SNOS-380", store=store, cli=cli,
                                    emby_client=FakeEmby(dto=EMPTY_DTO), opts=self._opts())
        assert cli.calls["detail"] == before                # 没重抓骨架
        assert report["sources"]["javdb"]["status"] == "cache"
        assert store.meta_get("SNOS380")["plot_zh"]         # 但简介补上了
        assert report["completeness"] == "full"

    def test_scrape_one_without_item_key(self, scraper, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        report = scraper.scrape_one("SNOS-380", store=store, cli=FakeCli(detail=JAVDB_DETAIL),
                                    emby_client=FakeEmby(dto=EMPTY_DTO), opts=self._opts())
        assert report["status"] == "error" and "Emby 条目" in report["error"]

    def test_scrape_batch_isolation(self, scraper, store_mod, tmp_path, monkeypatch):
        """一条炸掉不影响其它条（返回与入参同序）。"""
        store = make_store(store_mod, tmp_path)
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_EMPTY.encode(), "", 200))

        def boom(key, **kwargs):
            if str(key) == "BAD-001":
                raise RuntimeError("炸了")
            return {"ok": True, "key": str(key), "status": "ok"}

        monkeypatch.setattr(scraper, "scrape_one", boom)
        rows = scraper.scrape_batch(["SNOS-380", "BAD-001", "MIDV-946"], store=store,
                                    cli=FakeCli(), emby_client=FakeEmby())
        assert [r["key"] for r in rows] == ["SNOS-380", "BAD-001", "MIDV-946"]
        assert rows[1]["status"] == "error" and "炸了" in rows[1]["error"]

    def test_locate_item_prefers_item_key(self, scraper):
        store = FakeStore(items=[{"key": "SNOS380", "item_key": "emby:1", "emby_id": "1"}])
        assert scraper.locate_item(store, "SNOS380", "SNOS-380") == ("emby:1", "1")
        assert scraper.locate_item(store, "SNOS380", "SNOS-380", item_key="emby:9") == \
            ("emby:9", "9")

    def test_locate_item_library_fallback(self, scraper):
        library = FakeLibrary(hit={"id": "12598"})
        assert scraper.locate_item(FakeStore(), "SNOS380", "SNOS-380",
                                   {"library": library}) == ("emby:12598", "12598")
        assert library.calls["lookup"] == 1

    def test_number_from_dto(self, scraper):
        """事实 1：只认路径；`Name` 连兜底都不做（5.4% 命中率 + 可能认成别的片）。"""
        assert scraper.number_from_dto(EMPTY_DTO) == "SNOS-380"
        assert scraper.number_from_dto({"Name": "SNOS-380 标题"}) == ""
        assert scraper.number_from_dto({"FileName": "IPZZ-912-UC.mp4"}) == "IPZZ-912"
        assert scraper.number_from_dto({"Path": "/x/无番号的文件.mp4"}) == ""
        assert scraper.number_from_dto(None) == ""


# ---------------------------------------------------------------------------
# 11. rollback_item
# ---------------------------------------------------------------------------

class TestRollback:

    def test_rollback_replays_backup_with_provider_replace(self, scraper):
        backup = dict(EMPTY_DTO, Name="SNOS-380", Overview="", ProviderIds={"MetaTube": "x"})
        store = FakeStore(backup=json.dumps(backup, ensure_ascii=False))
        emby = FakeEmby(dto=dict(EMPTY_DTO, Name="SNOS-380 刮过的标题",
                                 ProviderIds={"AVHelper": "SNOS-380"}))
        report = scraper.rollback_item("emby:12598", store=store, emby_client=emby)
        assert report["ok"] and report["emby_id"] == "12598"
        assert emby.calls["update_item"] == 1
        sent = emby.updated[0]["dto"]
        assert sent["Name"] == "SNOS-380"
        assert sent["provider_ids_replace"] is True          # 整份替换（合并会残留增量键）
        assert sent["ProviderIds"] == {"MetaTube": "x"}
        assert "Etag" not in sent                            # 只读键交给 S2 从当前 DTO 取
        assert "MediaSources" not in sent

    def test_rollback_without_backup_is_refused(self, scraper):
        emby = FakeEmby(dto=EMPTY_DTO)
        report = scraper.rollback_item("emby:12598", store=FakeStore(), emby_client=emby)
        assert report["ok"] is False and "没有写前备份" in report["error"]
        assert emby.calls["update_item"] == 0

    def test_rollback_bad_json_is_refused(self, scraper):
        emby = FakeEmby(dto=EMPTY_DTO)
        report = scraper.rollback_item("emby:12598", store=FakeStore(backup="{不是 JSON"),
                                       emby_client=emby)
        assert report["ok"] is False and emby.calls["update_item"] == 0

    def test_rollback_deletes_cover_added_by_scrape(self, scraper):
        store = FakeStore(backup=json.dumps(EMPTY_DTO, ensure_ascii=False))
        emby = FakeEmby(dto=EMPTY_DTO)
        emby.dto = dict(EMPTY_DTO, ImageTags={"Primary": "newtag"})
        report = scraper.rollback_item("emby:12598", store=store, emby_client=emby)
        assert report["ok"] and report["images"]["cover"] == "deleted"
        assert emby.calls["delete_image"] == 1


class TestRollbackRestoresAbsentKeys:
    """S2 真机 E2E 抓到的回滚链缺陷：Emby 会**整个省略**"没有值"的可选字段。

    12598 写前备份是 **45 键、根本没有 `Overview`**；写一次之后它才出现（46 键）。
    而 `update_item` 是「以当前 DTO 为底、覆盖表改哪算哪」→ **备份里没的键 = 不动**，
    于是"备份原样回灌"回滚不掉 `Overview`，条目停在验证态、与备份 sha 不一致。
    修法：覆盖表走 `emby.restore_overrides(backup)`（基线缺席的可清空标量显式清空）。
    """

    # 模拟 Emby 的省略行为：没有 Overview / ProductionYear，集合键也不在，ImageTags 空
    BASELINE_WITHOUT_OVERVIEW = {
        "Id": "12598", "Name": "SNOS-380", "SortName": "SNOS-380",
        "Path": "/Media/9kg/avi/SNOS-380.mp4", "Etag": "abc",
        "ProviderIds": {}, "MediaSources": [{"Path": "/Media/9kg/avi/SNOS-380.mp4"}],
        "RunTimeTicks": 99493394000, "ImageTags": {},
    }

    def _rollback(self, scraper, backup, current):
        store = FakeStore(backup=json.dumps(backup, ensure_ascii=False))
        emby = FakeEmby(dto=current)
        report = scraper.rollback_item("emby:12598", store=store, emby_client=emby)
        return report, emby, (emby.updated[0]["dto"] if emby.updated else {})

    def test_absent_overview_is_explicitly_cleared(self, scraper):
        """★ 硬性验收：备份里**缺 `Overview`** → 覆盖表里必须**显式带清空**。"""
        current = dict(self.BASELINE_WITHOUT_OVERVIEW,
                       Overview="S2-CT-OK 真机写路径验证", Genres=["4K"],
                       People=[{"Name": "x", "Type": "Actor"}],
                       ProviderIds={"AVHelper": "SNOS-380"})
        report, emby, sent = self._rollback(scraper, self.BASELINE_WITHOUT_OVERVIEW, current)
        assert report["ok"] is True
        assert "Overview" in sent, "缺席键必须显式清空，否则回滚链断在这里"
        assert sent["Overview"] is None                    # S2 把它落成 ""
        assert sent["provider_ids_replace"] is True         # ProviderIds 整份还原
        assert sent["ProviderIds"] == {}
        assert sent["People"] == []                         # 缺席集合键 → []（null 会 400）
        # 端到端口径：S2 的 writable_overrides() 必须把 None 变成 ""（真机能清空 Overview）
        effective, _notes = scraper.emby.writable_overrides(sent)
        assert effective["Overview"] == ""
        assert "MediaSources" not in sent and "Etag" not in sent and "Path" not in sent

    def test_untested_date_clears_are_not_guessed(self, scraper):
        """`PremiereDate`/`ProductionYear` 的清空未实测 → **保持"不动"**，不许拿空串赌 400。"""
        current = dict(self.BASELINE_WITHOUT_OVERVIEW, PremiereDate="2026-10-14T00:00:00.0000000Z",
                       ProductionYear=2026)
        report, emby, sent = self._rollback(scraper, self.BASELINE_WITHOUT_OVERVIEW, current)
        assert report["ok"] is True
        assert "PremiereDate" not in sent                   # S2 明确交底：未验证，故意不放进表
        assert "ProductionYear" not in sent
        assert scraper.emby.NULL_CLEARABLE_KEYS and \
            "PremiereDate" not in scraper.emby.NULL_CLEARABLE_KEYS

    def test_backup_values_are_replayed_verbatim(self, scraper):
        """备份里**有**的字段照原值回灌（含空串 —— 那本身就是基线的值）。"""
        backup = dict(self.BASELINE_WITHOUT_OVERVIEW, Overview="", CommunityRating=None,
                      Studios=[{"Name": "旧片商"}])
        report, emby, sent = self._rollback(scraper, backup, dict(EMPTY_DTO, Overview="新简介"))
        assert report["ok"] is True
        assert sent["Overview"] == "" and sent["Studios"] == [{"Name": "旧片商"}]
        assert "Path" not in sent and "RunTimeTicks" not in sent

    def test_restore_payload_falls_back_when_helper_missing(self, scraper, monkeypatch):
        """`emby.restore_overrides` 不在（旧版/正在改）时退回老写法，至少还原备份里有的键。"""
        monkeypatch.setattr(scraper.emby, "restore_overrides", None, raising=False)
        got = scraper._restore_payload({"Id": "1", "Name": "x", "Path": "/p",
                                        "ProviderIds": {"MetaTube": "y"}})
        assert got["Name"] == "x" and "Path" not in got
        assert got["ProviderIds"] == {"MetaTube": "y"}
        assert got["provider_ids_replace"] is True

    def test_normal_write_path_still_skips(self, scraper):
        """回滚的"整份还原"不许污染正常写入：拿不到的值仍然跳过。"""
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        target = targets({}, plot_zh="", plot_jp="")
        report = scraper.write_item(store, emby, target, item_key="emby:1", key="SNOS380",
                                    emby_id="1", opts={"now": "2026-10-14T00:00:00",
                                                       "write_images": False})
        sent = emby.updated[0]["dto"]
        assert "Overview" not in sent                        # 两者都空 → 不动（回滚才会清）
        assert set(sent) <= set(scraper.MATRIX_FIELDS)


# ---------------------------------------------------------------------------
# 12. film_view（零抓取）
# ---------------------------------------------------------------------------

class TestFilmView:

    def _seed(self, store_mod, tmp_path, **meta_patch):
        store = make_store(store_mod, tmp_path)
        store.meta_upsert(
            "SNOS380", display_number="SNOS-380", title_jp="日文原标题", title_zh="中文标题",
            plot_zh="中文简介", plot_jp="日文简介", translation_status="done",
            actors_json=[{"id": "neAOa", "name": "雛形みくる",
                          "avatar_url": "https://tp.spfcas.com/avatars/ne/neAOa.jpg"}],
            tags_json=["OL", "巨乳"], studio="S1 NO.1 STYLE", release_date="2026-10-14",
            runtime_min=170, rating=4.33, cover_raw_url="https://tp.spfcas.com/covers/x.jpg",
            samples_json=["https://tp.spfcas.com/s1.jpg"], trailer_url="https://x/t.m3u8",
            raw_json={"javdb": {"id": "96GB0p"},
                      "extra": {"version_tags": {"is_zh_sub": True, "resolution": "4K"}}},
            completeness="full", **meta_patch)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598",
                          version_tags_json={"is_zh_sub": True}, library_state="in_library",
                          scrape_state="scraped_full", crop_anchor="right",
                          last_synced_at="2026-10-14T00:00:00")
        return store

    def test_shape(self, scraper, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path)
        store.download_upsert("SNOS-380", state="downloaded", source="plugin")
        view = scraper.film_view("SNOS-380", store=store)
        assert view["key"] == "SNOS380" and view["number"] == "SNOS-380"
        assert view["title"] == "中文标题" and view["original_title"] == "日文原标题"
        assert view["plot"] == "中文简介" and view["plot_jp"] == "日文简介"
        assert view["cover"] == "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"
        assert view["cover_raw"] == "https://tp.spfcas.com/covers/x.jpg"
        assert view["crop_anchor"] == "right"
        assert view["version_tags"] == ["中字", "4K"]
        assert view["badge"] == "中字/4K"
        assert view["states"] == {"download": "downloaded", "library": "in_library",
                                  "scrape": "scraped_full"}
        assert view["emby_id"] == "12598" and view["item_key"] == "emby:12598"
        assert view["updated_at"]
        assert view["actors"][0]["name"] == "雛形みくる"
        assert view["actors"][0]["avatar"].startswith("/api/v1/plugin/AVHelper/img?url=")
        assert view["items"][0]["item_key"] == "emby:12598"
        assert view["completeness"] == "full"

    def test_missing_meta_row_degrades(self, scraper, store_mod, tmp_path):
        """没有 meta 行时也要给出可渲染的骨架，而不是抛异常或空 dict。"""
        store = make_store(store_mod, tmp_path)
        view = scraper.film_view("IPZZ-912", store=store)
        assert view["key"] == "IPZZ912" and view["number"] == "IPZZ-912"
        assert view["title"] == "" and view["plot"] == "" and view["actors"] == []
        assert view["cover"] == "" and view["emby_id"] == ""
        assert view["states"] == {"download": "none", "library": "not_in_library",
                                  "scrape": "unscraped"}
        assert view["completeness"] == "unscraped"
        assert view["items"] == []

    def test_no_store_at_all(self, scraper):
        view = scraper.film_view("SNOS-380")
        assert view["key"] == "SNOS380" and view["states"]["scrape"] == "unscraped"

    def test_cover_falls_back_to_raw_url(self, scraper, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("IPZZ912", display_number="IPZZ-912", title_jp="日文",
                          cover_raw_url="https://tp.spfcas.com/c.jpg")
        view = scraper.film_view("IPZZ-912", store=store)
        assert view["cover"].startswith("/api/v1/plugin/AVHelper/img?url=https%3A%2F%2F")
        assert view["cover"].endswith("%2Fc.jpg")           # 原址整条被 quote 进参数
        assert view["cover_raw"] == "https://tp.spfcas.com/c.jpg"

    def test_ledger_source_filter(self, scraper, store_mod, tmp_path):
        """`source='library'` 是"本来就在库里"的补种行，不算"下载过"。"""
        store = make_store(store_mod, tmp_path)
        store.download_upsert("SNOS-380", state="downloaded", source="library")
        view = scraper.film_view("SNOS-380", store=store)
        assert view["states"]["download"] == "none"

    def test_download_state_uses_old_norm_key(self, scraper, store_mod, tmp_path):
        """台账主键是旧口径（`IPZZ912UC`），film_view 的两套键都要能对上。"""
        store = make_store(store_mod, tmp_path)
        store.download_upsert("IPZZ-912-UC", state="downloading", source="queue")
        assert store.download_map(["queue"])           # 台账确实写了
        view = scraper.film_view("IPZZ-912", store=store)
        assert view["states"]["download"] == "downloading"

    def test_download_row_matching_rules(self, scraper):
        """干净号 ↔ 旧口径键的匹配规则（含"不许误吃另一部片"的反例）。"""
        rows = {"IPZZ912UC": {"state": "downloaded"}, "IPZZ912": {"state": "downloading"},
                "IPZZ91": {"state": "failed"}, "MIDV946": {"state": "downloaded"}}
        assert scraper.download_row(rows, "IPZZ912")["state"] == "downloading"   # 精确优先
        assert scraper.download_row({"IPZZ912UC": {"state": "downloaded"}}, "IPZZ912")[
            "state"] == "downloaded"                                            # 版本后缀
        assert scraper.download_row(rows, "IPZZ9") is None    # 纯数字尾巴不算版本后缀
        assert scraper.download_row(rows, "SSIS129") is None
        assert scraper.download_row({}, "IPZZ912") is None
        assert scraper.download_row(None, "IPZZ912") is None
        assert scraper.download_row(rows, "") is None

    def test_library_state_from_memory_index(self, scraper, store_mod, tmp_path):
        """`media_item` 没有 emby_id 时退回调用方给的内存索引（已建好就直接用）。"""
        store = make_store(store_mod, tmp_path)
        library = FakeLibrary(hit={"id": "12595"})
        view = scraper.film_view("IPZZ-912", store=store, library=library)
        assert view["states"]["library"] == "in_library"
        assert view["emby_id"] == "12595"
        assert library.calls["index"] == 0                  # 绝不主动触发全库抓取

    def test_film_view_is_offline(self, scraper, store_mod, tmp_path, monkeypatch):
        """★ 零外网：任何 HTTP 调用都算失败。"""
        import urllib.request

        def boom(*args, **kwargs):
            raise AssertionError("film_view 不许发网络请求")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        store = self._seed(store_mod, tmp_path)
        library = FakeLibrary()
        view = scraper.film_view("SNOS-380", store=store, library=library)
        assert view["title"] == "中文标题"

    def test_multi_instance_representative(self, scraper, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.item_upsert("dl:abc", "SNOS380", display_number="SNOS-380",
                          library_state="not_in_library", scrape_state="scraped_partial")
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598",
                          library_state="in_library", scrape_state="scraped_full")
        view = scraper.film_view("SNOS-380", store=store)
        assert view["item_key"] == "emby:12598" and view["states"]["library"] == "in_library"
        assert len(view["items"]) == 2

    def test_normalizes_input_variants(self, scraper, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path)
        for text in ("SNOS-380", "SNOS380", "snos00380"):
            assert scraper.film_view(text, store=store)["title"] == "中文标题"


# ---------------------------------------------------------------------------
# 13. sources_selfcheck
# ---------------------------------------------------------------------------

class TestSelfcheck:

    def test_four_sources(self, scraper, store_mod, tmp_path, monkeypatch):
        store = make_store(store_mod, tmp_path)

        def fake_get(url, **kwargs):
            if "/v1/movies/search" in url:
                return b'{"data": []}', "", 200
            if "/search" in url:
                return JAVTXT_SEARCH_HTML.encode(), "", 200
            if "/v/" in url:
                return JAVTXT_DETAIL_HTML.encode(), "", 200
            raise AssertionError(f"不该请求 {url}")

        monkeypatch.setattr(scraper, "http_get", fake_get)
        rows = scraper.sources_selfcheck(store, FakeCli(detail=JAVDB_DETAIL),
                                        {"javtxt_interval": 0,
                                         "javtxt_hosts": ("https://j.test",),
                                         "metatube_base": "http://mt:8080"})
        assert [row["source"] for row in rows] == ["javdb", "javtxt", "metatube", "llm"]
        for row in rows:
            assert set(row) >= {"source", "status", "latency_ms", "error", "checked_at"}
        assert rows[0]["status"] == "ok" and rows[0]["latency_ms"] >= 0
        assert rows[1]["status"] == "ok" and rows[1]["detail"]["plot_zh_len"] > 0
        assert rows[2]["status"] == "miss"
        assert rows[3]["status"] in ("skipped", "ok", "error")     # translator 未落地=skipped
        summary = {row["source"]: row for row in store.scrape_log_summary()}
        assert {"javdb", "javtxt", "metatube", "llm"} <= set(summary)

    def test_javdb_probe_failure_reports_reason(self, scraper, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        rows = scraper.sources_selfcheck(
            store, FakeCli(detail=None, error="代理不可达"),
            {"javtxt_interval": 0, "javtxt_hosts": ("https://j.test",),
             "metatube_base": "http://mt:8080", "http_timeout": 1})
        assert rows[0]["status"] == "error" and "代理不可达" in rows[0]["error"]


# ---------------------------------------------------------------------------
# 15. namemap 接线（S3 口径） + 演员头像治理（追加 1）
# ---------------------------------------------------------------------------

class TestNamemapWiring:
    """S3 的三条口径：`clean_tags(limit=10)`、写侧上限、映射表首灌。"""

    def test_clean_tags_passes_limit_ten(self, scraper, monkeypatch):
        seen = {}

        class Map:
            @staticmethod
            def clean_tags(tags, limit=0):
                seen["limit"] = limit
                return ["a", "b"]

        monkeypatch.setattr(scraper, "namemap", Map)
        assert scraper.clean_tags([{"name": "x"}], limit=scraper.GENRE_LIMIT) == ["a", "b"]
        assert seen["limit"] == 10

    def test_gather_uses_write_side_limit(self, scraper, monkeypatch):
        """取数层落 `tags` 时就要按写侧上限截断（默认 10）。"""
        monkeypatch.setattr(scraper, "clean_tags",
                            lambda tags, limit=0: [f"t{i}" for i in range(limit or 0)])
        target = scraper.gather(FakeCli(detail=dict(JAVDB_DETAIL, tags=[{"name": "x"}])),
                                FakeStore(), "SNOS380", "SNOS-380",
                                opts={"plot_sources": (), "write_images": False})
        assert target["tags"] == [f"t{i}" for i in range(10)]

    def test_clean_tags_tolerates_old_signature(self, scraper, monkeypatch):
        class Old:
            @staticmethod
            def clean_tags(tags):
                return ["旧签名"]

        monkeypatch.setattr(scraper, "namemap", Old)
        assert scraper.clean_tags(["x"], limit=10) == ["旧签名"]

    def test_ensure_namemap_syncs_once(self, scraper, monkeypatch):
        calls = []

        class Map:
            @staticmethod
            def sync_store(store, force=False):
                calls.append(force)
                return 5698

        monkeypatch.setattr(scraper, "namemap", Map)
        monkeypatch.setattr(scraper, "_NAMEMAP_SYNCED", False)
        store = FakeStore()
        assert scraper.ensure_namemap(store, {}) is True
        assert scraper.ensure_namemap(store, {}) is True
        assert calls == [False]                        # 幂等：同进程只灌一次
        assert scraper.ensure_namemap(store, {"force_namemap": True}) is True
        assert calls == [False, True]
        assert [row["source"] for row in store.logs] == ["namemap", "namemap"]

    def test_ensure_namemap_failure_does_not_block(self, scraper, monkeypatch):
        class Boom:
            @staticmethod
            def sync_store(store, force=False):
                raise RuntimeError("表坏了")

        monkeypatch.setattr(scraper, "namemap", Boom)
        monkeypatch.setattr(scraper, "_NAMEMAP_SYNCED", False)
        store = FakeStore()
        assert scraper.ensure_namemap(store, {}) is False
        assert store.logs[0]["status"] == "error" and "表坏了" in store.logs[0]["error"]

    def test_actor_rows_shape(self, scraper, monkeypatch):
        """`meta.actors_json` 必须同时带 avatar 与 javdb_actor_id（追加 2）。"""
        monkeypatch.setattr(scraper, "namemap", None)
        rows = scraper.actor_rows([{"id": "neAOa", "name": "雛形みくる",
                                    "avatar_url": "https://a/2.jpg", "gender": 0}])
        assert rows == [{"name": "雛形みくる", "zh": "", "jp": "雛形みくる",
                         "avatar": "https://a/2.jpg", "javdb_actor_id": "neAOa",
                         "canonical_id": ""}]

    def test_actor_rows_is_idempotent(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "namemap", None)
        once = scraper.actor_rows([{"id": "x", "name": "A", "avatar_url": "u"}])
        twice = scraper.actor_rows(once)
        assert once == twice

    def test_actor_rows_never_invents_chinese(self, scraper, monkeypatch):
        """S3 口径 3：映射表未命中时只留日文原名，**绝不音译**。"""
        monkeypatch.setattr(scraper, "namemap", None)
        rows = scraper.actor_rows(["誰かさん"])
        assert rows[0]["zh"] == "" and rows[0]["name"] == "誰かさん"

    def test_scrape_one_stores_avatar_and_actor_id(self, scraper, store_mod, tmp_path,
                                                  monkeypatch):
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_EMPTY.encode(), "", 200))
        monkeypatch.setattr(scraper, "namemap", None)
        scraper.scrape_one("SNOS-380", store=store, cli=FakeCli(detail=JAVDB_DETAIL),
                           emby_client=FakeEmby(dto=EMPTY_DTO),
                           opts={"now": "2026-10-14T00:00:00", "write_images": False,
                                 "javdb_assets": False, "javtxt_interval": 0,
                                 "javtxt_hosts": ("https://j.test",),
                                 "metatube_base": "http://mt:8080"})
        actors = store.meta_get("SNOS380")["actors"]
        assert [a["javdb_actor_id"] for a in actors] == ["YPKz", "neAOa"]
        assert all(a["avatar"] for a in actors)


class TestSyncActorAvatars:
    """"追加 1"：演员头像写进 Person 实体；`dry_run` 必须零写请求。"""

    def _seed_store(self, store_mod, tmp_path, actors):
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("SNOS380", display_number="SNOS-380", actors_json=actors)
        return store

    def _persons(self, mapping):
        class Client(FakeEmby):
            def find_person(self, name):
                self.calls.setdefault("find_person", 0)
                self.calls["find_person"] += 1
                return dict(mapping[name]) if name in mapping else None

        return Client()

    def test_dry_run_makes_zero_write_calls(self, scraper, store_mod, tmp_path, monkeypatch, nomap):
        store = self._seed_store(store_mod, tmp_path, [
            {"name": "雛形みくる", "jp": "雛形みくる", "zh": "", "canonical_id": "",
             "avatar": "https://tp.spfcas.com/a.jpg", "javdb_actor_id": "neAOa"}])
        emby = self._persons({"雛形みくる": {"Id": "12617", "Name": "雛形みくる",
                                            "ImageTags": {}}})
        report = scraper.sync_actor_avatars(store, emby, dry_run=True, namemap_mod=nomap,
                                           opts={"proxy": "http://px:1"})
        assert emby.writes() == {"update_item": 0, "upload_image": 0, "delete_image": 0}
        assert report["dry_run"] is True and report["ok"] is True
        assert report["applied"] == []
        assert report["planned"][0]["action"] == "upload_avatar"
        assert report["planned"][0]["person_id"] == "12617"

    def test_apply_uploads_avatar_and_provider_id(self, scraper, store_mod, tmp_path,
                                                 monkeypatch, nomap):
        store = self._seed_store(store_mod, tmp_path, [
            {"name": "雛形みくる", "jp": "雛形みくる", "zh": "", "canonical_id": "",
             "avatar": "https://tp.spfcas.com/a.jpg", "javdb_actor_id": "neAOa"}])
        emby = self._persons({"雛形みくる": {"Id": "12617", "Name": "雛形みくる",
                                            "ImageTags": {}}})

        class Proxy:
            @staticmethod
            def fetch(url, proxy=""):
                return b"\xff\xd8\xffjpeg"

        monkeypatch.setattr(scraper, "imgproxy", Proxy)
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=nomap,
                                           opts={"proxy": "http://px:1"})
        assert report["ok"] is True and len(report["applied"]) == 1
        assert emby.uploaded == [{"item_id": "12617", "type": "Primary",
                                  "bytes": b"\xff\xd8\xffjpeg"}]
        assert emby.updated[0]["dto"] == {"ProviderIds": {"JavDB": "neAOa"}}
        assert "provider_ids_replace" not in emby.updated[0]["dto"]    # 合并，不整份覆盖

    def test_missing_person_is_not_an_error(self, scraper, store_mod, tmp_path, nomap):
        store = self._seed_store(store_mod, tmp_path, [
            {"name": "还没刮过的演员", "avatar": "https://a.jpg", "javdb_actor_id": "x"}])
        emby = self._persons({})
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=nomap)
        assert report["ok"] is True and report["errors"] == []
        assert report["missing_person"] == 1
        assert report["planned"][0]["reason"] == "person_missing"
        assert emby.calls["upload_image"] == 0

    def test_skips_when_person_already_has_image(self, scraper, store_mod, tmp_path, nomap):
        store = self._seed_store(store_mod, tmp_path, [
            {"name": "A（ア）", "avatar": "https://a.jpg"}])
        emby = self._persons({"A（ア）": {"Id": "9", "ImageTags": {"Primary": "tag"}}})
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=nomap)
        assert report["planned"][0]["reason"] == "has_image"
        assert emby.calls["upload_image"] == 0

    def test_no_avatar_is_skipped(self, scraper, store_mod, tmp_path, nomap):
        store = self._seed_store(store_mod, tmp_path, [{"name": "A", "avatar": ""}])
        emby = self._persons({"A": {"Id": "9", "ImageTags": {}}})
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=nomap)
        assert report["planned"][0]["reason"] == "no_avatar"
        assert emby.calls["upload_image"] == 0

    def test_fetch_failure_recorded(self, scraper, store_mod, tmp_path, monkeypatch, nomap):
        store = self._seed_store(store_mod, tmp_path, [
            {"name": "A", "avatar": "https://a.jpg", "javdb_actor_id": "x"}])
        emby = self._persons({"A": {"Id": "9", "ImageTags": {}}})

        class Broken:
            @staticmethod
            def fetch(url, proxy=""):
                return None

        monkeypatch.setattr(scraper, "imgproxy", Broken)
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=nomap)
        assert report["ok"] is False and emby.calls["upload_image"] == 0
        assert report["planned"][0]["reason"] == "imgproxy.fetch 返回空"

    def test_rejects_non_image_bytes_without_imgproxy(self, scraper, store_mod, tmp_path,
                                                     monkeypatch, nomap):
        """缺 imgproxy 时裸取会拿到 XOR 包装数据 —— 必须靠魔数挡住，不能喂给 Emby。"""
        store = self._seed_store(store_mod, tmp_path, [
            {"name": "A", "avatar": "https://a.jpg"}])
        emby = self._persons({"A": {"Id": "9", "ImageTags": {}}})
        monkeypatch.setattr(scraper, "imgproxy", None)
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (b"not-an-image-at-all", "", 200))
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=nomap)
        assert emby.calls["upload_image"] == 0
        assert "不是图片" in report["planned"][0]["reason"]

    def test_accepts_xor_unwrapped_jpeg(self, scraper):
        assert scraper.is_image_bytes(b"\xff\xd8\xff\xe0" + b"x" * 20)
        assert scraper.is_image_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 8)
        assert not scraper.is_image_bytes(b"RIFFxxxxNOPE")
        assert not scraper.is_image_bytes(b"short")

    def test_limit_truncates(self, scraper, store_mod, tmp_path, nomap):
        store = self._seed_store(store_mod, tmp_path, [
            {"name": f"演员{i}", "avatar": "https://a.jpg"} for i in range(5)])
        report = scraper.sync_actor_avatars(store, self._persons({}), limit=2, dry_run=True,
                                           namemap_mod=nomap)
        assert report["actors"] == 2

    def test_empty_meta_reports_clearly(self, scraper, store_mod, tmp_path, nomap):
        store = make_store(store_mod, tmp_path)
        report = scraper.sync_actor_avatars(store, self._persons({}), dry_run=True,
                                           namemap_mod=nomap)
        assert report["ok"] is False and report["actors"] == 0


# ---------------------------------------------------------------------------
# 16. MetaTube 只读提取器（S0b 字段真名）
# ---------------------------------------------------------------------------

class TestMetatubeMapping:
    """S0b 130 次真机探测给的字段真名表 —— 别按 javdb 的名字读 MetaTube。"""

    ITEM = {
        "id": "midv00946", "number": "MIDV-946", "provider": "JAV321",
        "title": "日文标题", "summary": "",          # 实测：真正命中的条目 summary 恒为空串
        "maker": "MOODYZ", "runtime": 118, "genres": ["巨乳", "単体作品"],
        "director": "監督さん", "preview_video_url": "https://x/t.m3u8",
        "preview_images": ["https://x/1.jpg", "https://x/2.jpg"],
        "release_date": "2024-11-29T00:00:00Z",
        "cover_url": "https://x/c.jpg", "thumb_url": "https://x/t.jpg",
        "actors": ["石川澪"],
    }

    def test_field_names(self, scraper):
        movie = scraper.metatube_movie(self.ITEM)
        assert movie["maker"] == "MOODYZ"                    # 不是 studio
        assert movie["runtime"] == 118                       # 不是 duration
        assert movie["genres"] == ["巨乳", "単体作品"]        # 不是 tags
        assert movie["preview_images"] == ["https://x/1.jpg", "https://x/2.jpg"]   # []string
        assert movie["release_date"] == "2024-11-29"          # ISO 串切成日期
        assert movie["actors"] == ["石川澪"]                  # 纯名字，没有头像
        assert movie["summary"] == ""

    def test_empty_summary_still_usable(self, scraper, monkeypatch):
        """`summary` 空不代表这次调用白费：标题/片商/时长/封面都是可用的。"""
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (json.dumps({"data": [self.ITEM]}).encode(),
                                              "", 200))
        got = scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "MIDV-946")
        assert got["status"] == "ok" and got["plot_jp"] == ""
        assert got["movie"]["maker"] == "MOODYZ"

    def test_fill_only_fills_empties(self, scraper):
        skeleton = {"title_jp": "javdb 的标题", "maker": "", "duration": 0,
                    "actors": [{"id": "a", "name": "javdb 演员"}],
                    "tags": [], "cover_url": ""}
        filled = scraper.metatube_fill(skeleton, scraper.metatube_movie(self.ITEM))
        assert skeleton["title_jp"] == "javdb 的标题"          # 绝不覆盖
        assert skeleton["maker"] == "MOODYZ" and skeleton["duration"] == 118
        assert skeleton["cover_url"] == "https://x/c.jpg"
        assert skeleton["actors"] == [{"id": "a", "name": "javdb 演员"}]
        assert "title_jp" not in filled and "maker" in filled and "duration" in filled

    def test_search_only_uses_q_param(self, scraper, monkeypatch):
        """永远用默认 lazy=true、永远不带 provider 参数（S0b：lazy=false 7/7 全 500）。"""
        seen = {}

        def fake_get(url, **kwargs):
            seen["url"] = url
            return json.dumps({"data": [self.ITEM]}).encode(), "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        scraper.metatube_lookup({"metatube_base": "http://mt:8080"}, "MIDV-946")
        assert seen["url"] == "http://mt:8080/v1/movies/search?q=MIDV-946"
        assert "lazy" not in seen["url"] and "provider" not in seen["url"]


class TestGatherOrder:
    """S0b 的性能纪律：Javtxt 拿到简介时**不再打 MetaTube**（每次省 10 秒）。"""

    def _count(self, scraper, monkeypatch, javtxt_hits=True):
        """假 HTTP + MetaTube 调用计数；`javtxt_hits=False` 时 javtxt 落空。"""
        hits = {"metatube": 0}

        def fake_get(url, **kwargs):
            if "/v1/movies/search" in url:
                hits["metatube"] += 1
                return json.dumps({"data": []}).encode(), "", 200
            if "/search" in url:
                return (JAVTXT_SEARCH_HTML if javtxt_hits
                        else JAVTXT_SEARCH_EMPTY).encode(), "", 200
            return JAVTXT_DETAIL_HTML.encode(), "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        return hits

    def test_javtxt_hit_skips_metatube(self, scraper, monkeypatch):
        """★ S0b 性能纪律：Javtxt 命中就绝不打 MetaTube（每次省 10 秒）。"""
        hits = self._count(scraper, monkeypatch, javtxt_hits=True)
        target = scraper.gather(FakeCli(detail=JAVDB_DETAIL), FakeStore(), "SNOS380",
                                "SNOS-380",
                                opts={"javtxt_interval": 0, "javtxt_hosts": ("https://j.test",),
                                      "metatube_base": "http://mt:8080", "write_images": False})
        assert target["plot_zh"] and target["plot_jp"]        # 中日简介都来自 Javtxt 详情页
        assert target["sources"]["javtxt"]["status"] == "ok"
        assert hits["metatube"] == 0
        assert target["sources"]["metatube"]["status"] == "skipped"

    def test_metatube_called_when_plot_missing(self, scraper, monkeypatch):
        hits = self._count(scraper, monkeypatch, javtxt_hits=False)
        target = scraper.gather(FakeCli(detail=dict(JAVDB_DETAIL, title="日文标题")), FakeStore(),
                                "SNOS380", "SNOS-380",
                                opts={"javtxt_interval": 0, "javtxt_hosts": ("https://j.test",),
                                      "metatube_base": "http://mt:8080", "write_images": False})
        assert hits["metatube"] == 1
        assert target["sources"]["metatube"]["status"] == "miss"
        assert target["completeness"] == "missing_plot"

    def test_javdb_failure_still_triggers_metatube_core_fallback(self, scraper, monkeypatch):
        """契约 §5.2：核心骨架第二顺位是 MetaTube，**仅在 javdb 失败时启用**。"""
        item = json.loads(json.dumps(TestMetatubeMapping.ITEM))
        item["number"] = "SNOS-380"

        def fake_get(url, **kwargs):
            if "/v1/movies/search" in url:
                return json.dumps({"data": [item]}).encode(), "", 200
            if "/search" in url:
                return JAVTXT_SEARCH_HTML.encode(), "", 200
            return JAVTXT_DETAIL_HTML.encode(), "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        target = scraper.gather(FakeCli(detail=None, error="javdb 挂了"), FakeStore(),
                                "SNOS380", "SNOS-380",
                                opts={"javtxt_interval": 0,
                                      "javtxt_hosts": ("https://j.test",),
                                      "metatube_base": "http://mt:8080",
                                      "write_images": False})
        assert target["sources"]["javdb"]["status"] == "error"
        assert target["studio"] == "MOODYZ"                 # 从 MetaTube 的 maker 补上
        assert target["duration"] == 118
        assert "MetaTube 补上了" in " ".join(target["warnings"])


# ---------------------------------------------------------------------------
# 17. S11 全库实测落进 scraper 的四条（事实 1/2/3 + 设计缺口）
# ---------------------------------------------------------------------------

def s11_cache(key="SNOS380", display="SNOS-380", **patch):
    """S11 `coverage.json` 的一行（结构照 `_tmp/s11/coverage.json` 抄）。"""
    row = {
        "display": display,
        "emby": [{"id": "12598", "name": display, "path": f"/Media/9kg/avi/{display}.mp4"}],
        "javdb": {"ok": True, "number": display, "fetched_at": "2026-10-14T06:00:00+08:00",
                  "detail": dict(JAVDB_DETAIL, number=display, title="javdb 的日文标题")},
        "javtxt": {"hit": True, "url": "https://javtxt.com/v/558149", "vid": "558149",
                   "title_jp": "日文标题", "title_zh": "中文标题",
                   "plot_jp": "日文简介" * 20, "plot_zh": "中文简介" * 20},
    }
    row.update(patch)
    return {"numbers": {key: row}}


@pytest.fixture
def nomap():
    """一个**空映射模块**（注入 `namemap_mod`）：让用例不依赖 5351 行真实映射表。

    为什么需要它：真实表里存在只由单个片假名/单字母构成的 keyword，用例里随手编的
    `A（ア）` 这种"假名"会**真的命中**某条记录（实测 `actor_display("A（ア）")` 返回
    `{'name': 'A', 'jp': 'ア'}`），于是断言随映射表内容漂移。头像治理这类用例只关心
    "名字怎么来的"，就该把映射层换成空壳。
    """
    return types.SimpleNamespace()


class TestNumberSource:
    """事实 1：番号只能从 `Path` 解析 —— `Name` 只有 5.4% 命中，且可能认成别的片。"""

    def test_path_only_never_reads_name(self, scraper):
        assert scraper.number_from_dto(EMPTY_DTO) == "SNOS-380"
        # Name 是 MetaTube 写的中文翻译标题：整串锚定认不出；**也不许拿开头一段去猜**
        assert scraper.number_from_dto(
            {"Name": "SNOS-380 平凡OL的隐藏色气身材", "Path": ""}) == ""
        assert scraper.number_from_dto({"Name": "ADN-801 ど田舎の…女教师"}) == ""
        assert scraper.number_from_dto({"Path": "/x/无番号的文件.mp4",
                                        "Name": "SNOS-380 标题"}) == ""

    def test_media_sources_path_used(self, scraper):
        assert scraper.number_from_dto(
            {"MediaSources": [{"Path": "/Media/9kg/avi/MIRD-277-D.mp4"}]}) == "MIRD-277"

    def test_file_name_used_last(self, scraper):
        assert scraper.number_from_dto({"FileName": "IPZZ-912-UC.mp4"}) == "IPZZ-912"


class TestSiteNumber:
    """事实 2：查站点的番号用 `display_number(canon_key(...))` 兜一层（S2 修好前是刚需）。"""

    def test_zero_padding_stripped(self, scraper):
        """`IPZZ-00586` 查 javdb 直接 404 —— 规范形态必须是 `IPZZ-586`。"""
        assert scraper.site_number("IPZZ-00586") == "IPZZ-586"
        assert scraper.site_number("ipzz00586") == "IPZZ-586"
        assert scraper.site_number("IPZZ-586") == "IPZZ-586"

    def test_resolve_key_uses_site_number(self, scraper):
        got = scraper.resolve_key("ipzz00961")
        assert got["key"] == "IPZZ961" and got["display_number"] == "IPZZ-961"

    def test_version_suffix_trimmed(self, scraper):
        assert scraper.site_number("IPZZ-912-UC") == "IPZZ-912"
        assert scraper.site_number("CAWD-989_4K") == "CAWD-989"

    def test_fc2(self, scraper):
        assert scraper.site_number("FC2PPV4828968") == "FC2-PPV-4828968"
        assert scraper.site_number("FC2-PPV-4828968") == "FC2-PPV-4828968"

    def test_odd_forms_fall_back_to_parse(self, scraper):
        """切不出规范形态（前置数字/一位数字段）时退回 parse 的结果，别丢信息。"""
        assert scraper.site_number("1PONDO-123")
        assert scraper.site_number("") == ""
        assert scraper.site_number("SNOS-380") == "SNOS-380"


class TestFetchCache:
    """事实 3：优先读 S11 抓取缓存（命中则**一次站点请求都不发**）。"""

    def test_cache_hit_makes_zero_requests(self, scraper, monkeypatch):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            raise AssertionError("命中缓存时不该发请求")

        monkeypatch.setattr(scraper, "http_get", fake_get)
        cli = FakeCli(detail=JAVDB_DETAIL)
        target = scraper.gather(cli, FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": s11_cache(), "write_images": False,
                                      "metatube_base": "http://mt:8080"})
        assert calls == [] and cli.calls["detail"] == 0
        assert target["title_zh"] == "中文标题"
        assert target["plot_zh"].startswith("中文简介")
        assert target["plot_jp"].startswith("日文简介")
        assert target["sources"]["javdb"]["status"] == "cache"
        assert target["sources"]["javtxt"]["from_cache"] is True
        assert target["completeness"] == "full"

    def test_cache_miss_falls_through(self, scraper, monkeypatch):
        hits = []
        midv_search = JAVTXT_SEARCH_HTML.replace("SNOS-380", "MIDV-946").replace(
            "/v/558149", "/v/490714")

        def fake_get(url, **kwargs):
            hits.append(url)
            if "/search" in url:
                return midv_search.encode(), "", 200
            return JAVTXT_DETAIL_HTML.encode(), "", 200

        monkeypatch.setattr(scraper, "http_get", fake_get)
        cli = FakeCli(detail=JAVDB_DETAIL)
        target = scraper.gather(cli, FakeStore(), "MIDV946", "MIDV-946",
                                opts={"fetch_cache": s11_cache(), "javtxt_interval": 0,
                                      "javtxt_hosts": ("https://j.test",),
                                      "metatube_base": "", "write_images": False})
        assert cli.calls["detail"] == 1 and hits          # 缓存没这号 → 照常真抓
        assert target["title_zh"] and target["plot_zh"]

    def test_cache_row_without_javdb_uses_javtxt_only(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "http_get",
                            lambda url, **k: (_ for _ in ()).throw(
                                AssertionError("javtxt 命中缓存时不该发请求")))
        cache = s11_cache()
        cache["numbers"]["SNOS380"]["javdb"] = {"ok": False, "error": "找不到番号"}
        target = scraper.gather(FakeCli(detail=None, error="不该被调"),
                                FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": cache, "write_images": False,
                                      "metatube_base": ""})
        assert target["plot_zh"] and target["sources"]["javdb"]["status"] == "error"

    def test_force_ignores_cache(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            JAVTXT_SEARCH_HTML.encode() if "/search" in url
            else JAVTXT_DETAIL_HTML.encode(), "", 200))
        cli = FakeCli(detail=JAVDB_DETAIL)
        scraper.gather(cli, FakeStore(), "SNOS380", "SNOS-380",
                       opts={"fetch_cache": s11_cache(), "force": True,
                             "javtxt_interval": 0, "javtxt_hosts": ("https://j.test",),
                             "write_images": False})
        assert cli.calls["detail"] == 1

    def test_cache_file_path_and_broken_file(self, scraper, tmp_path):
        path = tmp_path / "coverage.json"
        path.write_text(json.dumps(s11_cache(), ensure_ascii=False), encoding="utf-8")
        assert scraper.cache_row(scraper.load_fetch_cache(str(path)), "SNOS380")["display"] \
            == "SNOS-380"
        assert scraper.load_fetch_cache(str(tmp_path / "nope.json")) == {}
        bad = tmp_path / "bad.json"
        bad.write_text("{不是 JSON", encoding="utf-8")
        assert scraper.load_fetch_cache(str(bad)) == {}
        assert scraper.load_fetch_cache(None) == {}
        assert scraper.cache_row({}, "SNOS380") == {}

    def test_empty_plot_in_cache_is_hit_but_no_plot(self, scraper):
        cache = s11_cache()
        cache["numbers"]["SNOS380"]["javtxt"]["plot_zh"] = ""
        target = scraper.gather(FakeCli(detail=None), FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": cache, "write_images": False,
                                      "plot_sources": ("javtxt",)})
        assert target["title_zh"] and target["completeness"] == "missing_plot"


class TestShortPlotGuard:
    """事实 3 补充：`AKDL-332` 的 9 字中文简介是站点占位符，不能当"已刮全"。"""

    def test_short_plot_dropped_when_jp_exists(self, scraper, monkeypatch):
        cache = s11_cache()
        row = cache["numbers"]["SNOS380"]["javtxt"]
        row["plot_zh"] = "短简介"                      # 3 字占位
        row["plot_jp"] = "日本語の長いあらすじ" * 10
        target = scraper.gather(FakeCli(detail=None), FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": cache, "write_images": False,
                                      "plot_sources": ("javtxt",)})
        assert target["plot_zh"] == ""                  # 丢弃 → 交翻译链
        assert target["completeness"] == "missing_plot"
        assert any("占位符" in w for w in target["warnings"])

    def test_short_plot_kept_when_no_jp(self, scraper):
        cache = s11_cache()
        row = cache["numbers"]["SNOS380"]["javtxt"]
        row["plot_zh"] = "短简介"
        row["plot_jp"] = ""
        target = scraper.gather(FakeCli(detail=None), FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": cache, "write_images": False,
                                      "plot_sources": ("javtxt",)})
        assert target["plot_zh"] == "短简介"            # 没有日文时短的也比空的好

    def test_threshold_is_configurable(self, scraper):
        assert scraper._short_plot_zh("x" * 29, "日文", {}) is True
        assert scraper._short_plot_zh("x" * 30, "日文", {}) is False
        assert scraper._short_plot_zh("x" * 5, "日文", {"min_plot_zh": 2}) is False
        assert scraper._short_plot_zh("", "日文", {}) is False


class TestMultiInstance:
    """设计缺口：一个 `norm_key` 可能挂多个 Emby 条目，必须**逐个写**。"""

    def _opts(self, **patch):
        base = {"now": "2026-10-14T00:00:00", "write_images": False, "javdb_assets": False,
                "plot_sources": ("javtxt",), "fetch_cache": s11_cache(key="MIRD277",
                                                                     display="MIRD-277"),
                "metatube_base": ""}
        base.update(patch)
        return base

    def _seed(self, store_mod, tmp_path, ids):
        store = make_store(store_mod, tmp_path)
        for index, ident in enumerate(ids):
            store.item_upsert(f"emby:{ident}", "MIRD277", display_number="MIRD-277",
                              emby_id=ident,
                              version_tags_json={"edition": chr(65 + index)})
        return store

    def test_locates_all_instances(self, scraper, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path, ["1", "2", "3", "4"])
        found = scraper.locate_instances(store, "MIRD277", "MIRD-277")
        assert [entry["emby_id"] for entry in found] == ["1", "2", "3", "4"]
        assert all(entry["item_key"] == f"emby:{entry['emby_id']}" for entry in found)
        # 兼容形状（已上线）：键对
        assert scraper.locate_items(store, "MIRD277", "MIRD-277") == [
            ("emby:1", "1"), ("emby:2", "2"), ("emby:3", "3"), ("emby:4", "4")]
        assert scraper.locate_item(store, "MIRD277", "MIRD-277") == ("emby:1", "1")

    def test_scrape_one_writes_every_instance(self, scraper, store_mod, tmp_path, monkeypatch):
        """★ 只写第一条会让另外 3 条永远没有元数据（S11 实测 MIRD277×4）。"""
        store = self._seed(store_mod, tmp_path, ["11", "12", "13", "14"])
        emby = FakeEmby()
        # 4 个条目各自有一份 DTO（Path 指向同一个番号）
        dtos = {ident: dict(EMPTY_DTO, Id=ident, Path=f"/Media/9kg/avi/MIRD-277-{ident}.mp4",
                            Name="MIRD-277")
                for ident in ("11", "12", "13", "14")}
        emby.get_item = lambda item_id, user_id="": dict(dtos[str(item_id)])
        report = scraper.scrape_one("MIRD-277", store=store, cli=FakeCli(detail=None),
                                    emby_client=emby, opts=self._opts())
        assert report["total"] == 4 and report["written"] == 4 and report["ok"] is True
        assert emby.calls["update_item"] == 4
        assert [one["emby_id"] for one in report["items"]] == ["11", "12", "13", "14"]
        for ident in ("11", "12", "13", "14"):
            item = store.item_get(f"emby:{ident}")
            assert item["scrape_state"] == "scraped_full"      # 4 条都写到了
            assert store.item_backup_get(f"emby:{ident}")      # 各自都有写前备份
        assert len(store.item_list(key="MIRD277")) == 4

    def test_partial_failure_reported(self, scraper, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path, ["21", "22"])
        emby = FakeEmby()
        emby.get_item = lambda item_id, user_id="": (
            dict(EMPTY_DTO, Id=str(item_id), Path="/Media/9kg/avi/MIRD-277-A.mp4")
            if str(item_id) == "21" else None)                  # 22 读不到 DTO
        report = scraper.scrape_one("MIRD-277", store=store, cli=FakeCli(detail=None),
                                    emby_client=emby, opts=self._opts())
        assert report["status"] == "partial" and report["written"] == 1
        assert report["ok"] is False                            # 有一条没写成
        assert report["total"] == 2
        assert report["items"][1]["status"] == "error"

    def test_single_instance_shape_unchanged(self, scraper, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path, ["31"])
        store.item_upsert("emby:31", "MIRD277", display_number="MIRD-277", emby_id="31")
        emby = FakeEmby(dto=dict(EMPTY_DTO, Id="31"))
        report = scraper.scrape_one("MIRD-277", store=store, cli=FakeCli(detail=None),
                                    emby_client=emby, opts=self._opts())
        assert report["status"] == "ok" and report["total"] == 1
        assert report["item_key"] == "emby:31" and report["emby_id"] == "31"
        assert report["changed"]                                  # 老字段还在

    def test_preview_warns_about_extra_instances(self, scraper, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path, ["41", "42"])
        emby = FakeEmby(dto=dict(EMPTY_DTO, Id="41"))
        report = scraper.preview_one("MIRD-277", store=store, cli=FakeCli(detail=None),
                                     emby_client=emby, opts=self._opts())
        assert len(report["items"]) == 2
        assert any("2 个 Emby 条目" in w for w in report["warnings"])
        assert emby.writes() == {"update_item": 0, "upload_image": 0, "delete_image": 0}


class TestCacheOnly:
    """`cache_only`：缓存的"没有"也是权威结论 —— dry-run 必须**一个请求都不发**。"""

    def _boom(self, scraper, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("cache_only 不许发任何请求")

        monkeypatch.setattr(scraper, "http_get", boom)
        monkeypatch.setattr(scraper, "javdb_assets", boom)
        monkeypatch.setattr(scraper.subprocess, "run", boom)
        cli = FakeCli(detail=JAVDB_DETAIL)
        cli.detail = boom
        return cli

    def test_cached_miss_is_not_retried(self, scraper, monkeypatch):
        """S11：8 条站点收录缺口重试也没用 → 缓存说没有就是没有，别回落真站点。"""
        cache = s11_cache()
        cache["numbers"]["SNOS380"]["javtxt"] = {"hit": False}
        cache["numbers"]["SNOS380"]["javdb"] = {"ok": False, "error": "找不到番号"}
        cli = self._boom(scraper, monkeypatch)
        target = scraper.gather(cli, FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": cache, "cache_only": True,
                                      "metatube_base": "http://mt:8080",
                                      "write_images": False})
        assert target["sources"]["javdb"]["status"] == "cache_miss"
        assert target["sources"]["javtxt"]["status"] == "miss"
        assert target["sources"]["metatube"]["status"] == "skipped"
        assert target["sources"]["llm"]["status"] == "skipped"
        assert target["completeness"] == "missing_core"

    def test_cache_only_skips_llm(self, scraper, monkeypatch):
        cache = s11_cache()
        cache["numbers"]["SNOS380"]["javtxt"]["plot_zh"] = ""   # 有日文没中文
        calls = []

        class T:
            @staticmethod
            def translate_batch(items, **kwargs):
                calls.append(items)
                return {}

        monkeypatch.setattr(scraper, "translator", T)
        target = scraper.gather(FakeCli(detail=None), FakeStore(), "SNOS380", "SNOS-380",
                                opts={"fetch_cache": cache, "cache_only": True,
                                      "write_images": False, "plot_sources": ("javtxt",)})
        assert calls == [] and target["sources"]["llm"]["why"] == "cache_only dry-run"
        assert target["completeness"] == "missing_plot"

    def test_preview_cache_only_zero_requests_and_zero_writes(self, scraper, monkeypatch):
        cli = self._boom(scraper, monkeypatch)
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        report = scraper.preview_one("SNOS-380", store=store, cli=cli, emby_client=emby,
                                     opts={"fetch_cache": s11_cache(), "cache_only": True,
                                           "emby_id": "12598"})
        assert emby.writes() == {"update_item": 0, "upload_image": 0, "delete_image": 0}
        assert store.writes == {"meta_upsert": 0, "item_upsert": 0, "item_set": 0,
                                "item_backup_save": 0}
        assert report["images"]["assets"] == 0 and report["images"]["source"] == "meta"
        assert report["images"]["cover"].endswith("/covers/96/96GB0p.jpg")
        assert report["completeness"] == "full"

    def test_cache_only_without_cache_row_is_normal_path(self, scraper, monkeypatch):
        """缓存里没这条时，`cache_only` 不该把它变成"什么都刮不到"——照常走真链路。"""
        midv_search = JAVTXT_SEARCH_HTML.replace("SNOS-380", "MIDV-946").replace(
            "/v/558149", "/v/490714")
        monkeypatch.setattr(scraper, "http_get", lambda url, **k: (
            midv_search.encode() if "/search" in url else JAVTXT_DETAIL_HTML.encode(),
            "", 200))
        cli = FakeCli(detail=JAVDB_DETAIL)
        target = scraper.gather(cli, FakeStore(), "MIDV946", "MIDV-946",
                                opts={"fetch_cache": s11_cache(), "cache_only": True,
                                      "javtxt_interval": 0, "javtxt_hosts": ("https://j.test",),
                                      "metatube_base": "", "write_images": False})
        assert cli.calls["detail"] == 1                     # 没缓存 → 该抓还得抓
        assert target["title_zh"] and target["plot_zh"]


# ---------------------------------------------------------------------------
# 18. 0.7.0 真机试点抓到的两个缺陷（S7 修正）
# ---------------------------------------------------------------------------

class TestInstanceVersionTags:
    """缺陷 1：写侧拿不到 `version_tags` → 中字/流出/4K 角标丢失。

    真机现象（0.7.0 试点，`/scrape/preview`）：

    | 请求的 key | 旧 `version_tags` | `Name` 目标 |
    | --- | --- | --- |
    | `IPZZ-912-UC` | `["中字流出"]` | `IPZZ-912 [中字流出] 标题` ✅ |
    | `IPZZ912`（工作台给的就是干净键） | `[]` | `IPZZ-912 标题` ❌ |
    | `emby:12595` | `[]` | 同上 ❌ |

    而 `IPZZ-912-UC` 与 `IPZZ912` 是同一部片（`norm_key` 都是 `IPZZ912`），主路径给的就是
    干净键 → 盘上文件名里的「中字流出」再也出不来。修法：**角标以该条目自己的文件名为准**。
    """

    def test_item_number_carries_tags(self, scraper):
        info = scraper.item_number({"Path": "/Media/9kg/avi/IPZZ-912-UC.mp4"})
        assert info["matched"] is True
        assert info["number"] == "IPZZ-912"
        assert info["version_tags"]["is_zh_sub"] and info["version_tags"]["is_uncensored_leak"]
        assert info["path"].endswith("IPZZ-912-UC.mp4")
        plain = scraper.item_number({"Path": "/Media/9kg/avi/IPZZ-912.mp4"})
        assert plain["number"] == "IPZZ-912" and plain["version_tags"] == {}
        assert scraper.item_number({})["matched"] is False

    def test_item_version_tags_item_wins(self, scraper):
        """条目文件名优先；解不出文件名才退回请求键的角标。"""
        key_tags = {"is_zh_sub": True, "is_uncensored_leak": True}
        dto = {"Path": "/Media/9kg/avi/IPZZ-912.mp4"}           # 盘上是普通版
        assert scraper.item_version_tags(dto, key_tags) == {}    # 普通版不许带「中字流出」
        dto_uc = {"Path": "/Media/9kg/avi/IPZZ-912-UC.mp4"}
        assert scraper.item_version_tags(dto_uc)["is_zh_sub"] is True
        assert scraper.item_version_tags({}, key_tags) == key_tags    # 无路径 → 退回
        assert scraper.item_version_tags({"Path": "/x/无番号.mp4"}, key_tags) == key_tags

    def test_locate_items_derives_from_store_path(self, scraper, store_mod, tmp_path):
        """台账里有 `file_path` 时，定位阶段就能拿到角标（零请求）。

        `locate_items()` 保持已上线的**键对形状**（S8 的用例按 `[("emby:1","1")]` 断言），
        逐实例的角标在 `locate_instances()` 里 —— 两个都验，免得哪天把兼容层删了。
        """
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:1", "IPZZ912", display_number="IPZZ-912", emby_id="1",
                          file_path="/Media/9kg/avi/IPZZ-912-UC.mp4")
        store.item_upsert("emby:2", "IPZZ912", display_number="IPZZ-912", emby_id="2",
                          file_path="/Media/9kg/avi/IPZZ-912.mp4")
        found = scraper.locate_instances(store, "IPZZ912", "IPZZ-912")
        assert [e["emby_id"] for e in found] == ["1", "2"]
        assert scraper.version_labels(found[0]["version_tags"]) == ["中字流出"]
        assert scraper.version_labels(found[1]["version_tags"]) == []
        assert scraper.locate_items(store, "IPZZ912", "IPZZ-912") == [("emby:1", "1"),
                                                                     ("emby:2", "2")]
        # 台账没存 `file_path` 时，用 S11 缓存行里的 `emby[].path` 补（本地、零请求）
        store2 = make_store(store_mod, tmp_path / "b")
        store2.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        cache = s11_cache()
        cache["numbers"]["SNOS380"]["emby"][0]["path"] = "/Media/9kg/avi/SNOS-380-UC.mp4"
        found2 = scraper.locate_instances(store2, "SNOS380", "SNOS-380", {"fetch_cache": cache})
        assert found2 and found2[0]["item_key"] == "emby:12598"
        assert scraper.version_labels(found2[0]["version_tags"]) == ["中字流出"]
        # 缓存只是"补路径"，**不会凭空造实例**（台账里没有就是没有）
        assert scraper.locate_instances(FakeStore(), "SNOS380", "SNOS-380",
                                        {"fetch_cache": cache}) == []

    def test_same_key_two_instances_get_own_badge(self, scraper, store_mod, tmp_path):
        """★ 硬性验收 ①：同 key 两个实例、一个 `-UC` 一个普通 → 两条各自正确。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:101", "IPZZ912", display_number="IPZZ-912", emby_id="101")
        store.item_upsert("emby:102", "IPZZ912", display_number="IPZZ-912", emby_id="102")
        dtos = {
            "101": dict(EMPTY_DTO, Id="101", Name="IPZZ-912-UC",
                        Path="/Media/9kg/avi/IPZZ-912-UC.mp4"),
            "102": dict(EMPTY_DTO, Id="102", Name="IPZZ-912",
                        Path="/Media/9kg/avi/IPZZ-912.mp4"),
        }
        emby = FakeEmby()
        emby.get_item = lambda item_id, user_id="": dict(dtos[str(item_id)])
        cache = s11_cache(key="IPZZ912", display="IPZZ-912")
        report = scraper.scrape_one("IPZZ912", store=store, cli=FakeCli(detail=None),
                                    emby_client=emby,
                                    opts={"now": "2026-10-14T00:00:00", "write_images": False,
                                          "javdb_assets": False, "plot_sources": ("javtxt",),
                                          "fetch_cache": cache, "metatube_base": ""})
        assert report["total"] == 2 and report["written"] == 2
        by_id = {one["emby_id"]: one for one in report["items"]}
        assert by_id["101"]["version_tags"] == ["中字流出"]
        assert by_id["102"]["version_tags"] == []
        sent = {call["item_id"]: call["dto"] for call in emby.updated}
        assert sent["101"]["Name"].startswith("IPZZ-912 [中字流出] ")
        assert sent["102"]["Name"] == "IPZZ-912 中文标题"         # 普通版没有角标
        # 台账也各自落对了
        assert store.item_get("emby:101")["version_tags"]["is_zh_sub"] is True
        assert store.item_get("emby:102")["version_tags"] == {}

    def test_emby_id_key_gets_badge(self, scraper, store_mod, tmp_path):
        """★ 硬性验收 ②：`emby:<id>` 键也要拿到角标（走 DTO 的 Path）。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12595", "IPZZ912", display_number="IPZZ-912", emby_id="12595")
        emby = FakeEmby(dto=dict(EMPTY_DTO, Id="12595", Name="IPZZ-912-UC",
                                 Path="/Media/9kg/avi/IPZZ-912-UC.mp4"))
        report = scraper.preview_one("emby:12595", store=store, cli=FakeCli(detail=None),
                                     emby_client=emby,
                                     opts={"fetch_cache": s11_cache(key="IPZZ912",
                                                                    display="IPZZ-912"),
                                           "cache_only": True})
        assert report["version_tags"] == ["中字流出"]
        assert report["number"] == "IPZZ-912"                    # 番号仍是干净号
        name_row = next(r for r in report["fields"] if r["name"] == "Name")
        assert name_row["target"].startswith("IPZZ-912 [中字流出] ")

    def test_clean_key_preview_gets_badge(self, scraper, store_mod, tmp_path):
        """主路径（工作台给干净键）也能出角标 —— 这正是缺陷 1 的真机症状。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:101", "IPZZ912", display_number="IPZZ-912", emby_id="101",
                          file_path="/Media/9kg/avi/IPZZ-912-UC.mp4")
        emby = FakeEmby(dto=dict(EMPTY_DTO, Id="101", Path="/Media/9kg/avi/IPZZ-912-UC.mp4"))
        report = scraper.preview_one("IPZZ912", store=store, cli=FakeCli(detail=None),
                                     emby_client=emby,
                                     opts={"fetch_cache": s11_cache(key="IPZZ912",
                                                                    display="IPZZ-912"),
                                           "cache_only": True})
        assert report["version_tags"] == ["中字流出"]
        # `items[]` 保持已上线形状；逐实例角标在 `instances[]`
        assert report["items"] == [{"item_key": "emby:101", "emby_id": "101"}]
        assert report["instances"][0]["version_tags"] == ["中字流出"]
    def test_no_path_falls_back_to_key_tags(self, scraper):
        """条目没有 Path 时退回请求键解析出的角标（别把角标弄丢）。"""
        resolved = scraper.resolve_key("IPZZ-912-UC")
        assert resolved["version_tags"]["is_zh_sub"] is True
        got = scraper.item_version_tags({}, resolved["version_tags"])
        assert scraper.version_labels(got) == ["中字流出"]


class TestChangedAccuracy:
    """缺陷 2：`changed[]` 高估 —— `target=None`（会被跳过）的字段不算改动。"""

    def test_none_targets_are_not_changed(self, scraper):
        """真机反例：`FC2PPV4828968` 只会写 `ProviderIds`，旧实现报了 8 个改动。"""
        target = targets({}, display_number="FC2-PPV-4828968", title_zh="", title_jp="",
                         origin_title="", plot_zh="", plot_jp="", release_date="",
                         studio="", series="", tags=[], score="", javdb_id="",
                         actors=[], director="")
        overrides = scraper.build_overrides(target, EMPTY_DTO)
        assert overrides == {"ProviderIds": {"AVHelper": "FC2-PPV-4828968"}}
        fields = scraper.field_diff(EMPTY_DTO, overrides)
        assert [f["name"] for f in fields if f["changed"]] == ["ProviderIds"]
        # `target=None` 的行仍然**列出来**（供人看"没取到"），只是不算改动
        overview = next(f for f in fields if f["name"] == "Overview")
        assert overview["target"] is None and overview["changed"] is False

    def test_unwritable_key_is_not_changed(self, scraper):
        """不在 S2 `WRITABLE_KEYS` 里的键传了也会被丢掉，**不该报成改动**。

        ⚠️ 2026-10-14 复核：S2 已把 `SeriesName` 加进白名单（11 个矩阵字段现在**全部可写**），
        所以这里改用合成键验证过滤逻辑本身 —— 过滤仍然必要（防的是"以后又有矩阵字段落在
        白名单外"以及误传探针字段），只是今天它不再拦下任何矩阵字段。
        """
        assert set(scraper.MATRIX_FIELDS) <= set(scraper.emby.WRITABLE_KEYS)   # 现状：全可写
        assert "SeriesName" in scraper.emby.WRITABLE_KEYS
        out = scraper.build_overrides(targets({}, series="系列名"), EMPTY_DTO)
        row = next(f for f in scraper.field_diff(EMPTY_DTO, out) if f["name"] == "SeriesName")
        assert row["target"] == "系列名" and row["changed"] is True
        # 白名单外的键（探针字段）进不了覆盖表，也就不算改动
        assert scraper.effective_overrides({"RunTimeTicks": 1, "SeriesName": "x"}) == \
            {"SeriesName": "x"}

    def test_same_value_is_not_changed(self, scraper):
        dto = dict(EMPTY_DTO, Name="SNOS-380 中文标题", CommunityRating=4.33)
        out = scraper.build_overrides(targets({}), dto)
        fields = scraper.field_diff(dto, out)
        assert next(f for f in fields if f["name"] == "Name")["changed"] is False
        assert next(f for f in fields if f["name"] == "CommunityRating")["changed"] is False

    def test_collection_projection_ignores_ids(self, scraper):
        """Emby 读回的 `GenreItems`/`People` 带 `Id`，我们只写 `Name`(+`Type`)：
        不比投影的话这三个字段**每次刮削都会报"有改动"**（另一种高估）。"""
        dto = dict(EMPTY_DTO,
                   GenreItems=[{"Name": "OL", "Id": "114"}, {"Name": "巨乳", "Id": "17"}],
                   Studios=[{"Name": "S1 NO.1 STYLE", "Id": "5"}],
                   People=[{"Name": "雛形みくる", "Type": "Actor", "Id": "12617",
                            "ImageTags": {"Primary": "x"}}])
        out = scraper.build_overrides(targets({}, director=""), dto)
        fields = {f["name"]: f for f in scraper.field_diff(dto, out)}
        assert fields["GenreItems"]["changed"] is False
        assert fields["Studios"]["changed"] is False
        assert fields["People"]["changed"] is False
        # 真变了就得报（换流派）
        out2 = scraper.build_overrides(targets({}, tags=["新标签"], director=""), dto)
        assert next(f for f in scraper.field_diff(dto, out2)
                    if f["name"] == "GenreItems")["changed"] is True

    def test_overview_empty_is_a_real_change(self, scraper):
        """矩阵要求"清掉旧机翻"的 `Overview: ""` **必须**算改动（别被"空值=跳过"误伤）。"""
        dto = dict(EMPTY_DTO, Overview="旧的错误机翻")
        out = scraper.build_overrides(targets({}, plot_zh="", plot_jp="日文简介"), dto)
        assert out["Overview"] == ""
        assert next(f for f in scraper.field_diff(dto, out)
                    if f["name"] == "Overview")["changed"] is True

    def test_write_item_changed_matches_real_payload(self, scraper):
        """`write_item().changed[]` 与真正发出去的载荷一致。"""
        store = FakeStore()
        emby = FakeEmby(dto=EMPTY_DTO)
        target = targets({}, display_number="FC2-PPV-4828968", title_zh="", title_jp="",
                         origin_title="", plot_zh="", plot_jp="", release_date="",
                         studio="", series="", tags=[], score="", javdb_id="",
                         actors=[], director="")
        report = scraper.write_item(store, emby, target, item_key="emby:9", key="FC2PPV4828968",
                                    emby_id="9", opts={"now": "2026-10-14T00:00:00",
                                                       "write_images": False})
        assert report["changed"] == ["ProviderIds"]
        assert set(emby.updated[0]["dto"]) == {"ProviderIds"}

    def test_effective_overrides_filters(self, scraper):
        got = scraper.effective_overrides({"Name": "x", "SeriesName": "y", "Overview": None,
                                           "_mode": "z", "ProviderIds": {"A": "1"},
                                           "RunTimeTicks": 1, "MediaSources": []})
        assert got == {"Name": "x", "SeriesName": "y", "ProviderIds": {"A": "1"}}


# ---------------------------------------------------------------------------
# 14. 其他纯函数（图片代理地址 / 降级路径）
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_img_url_quotes(self, scraper):
        out = scraper.img_url("https://a/b c.jpg?x=1&y=2")
        assert out.startswith("/api/v1/plugin/AVHelper/img?url=")
        assert " " not in out and "&y=2" not in out.split("url=")[1][:40]
        assert scraper.img_url("") == ""

    def test_emby_img_url(self, scraper):
        assert scraper.emby_img_url("12598") == \
            "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"
        assert scraper.emby_img_url("") == ""

    def test_clean_tags_without_namemap(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "namemap", None)
        assert scraper.clean_tags([{"name": "OL"}, {"name": "OL"}, {"name": ""}, "巨乳"]) == \
            ["OL", "巨乳"]

    def test_clean_tags_uses_namemap(self, scraper, monkeypatch):
        class Map:
            @staticmethod
            def clean_tags(tags):
                return ["净化后"]

        monkeypatch.setattr(scraper, "namemap", Map)
        assert scraper.clean_tags([{"name": "X"}]) == ["净化后"]

    def test_clean_tags_namemap_failure_degrades(self, scraper, monkeypatch):
        class Boom:
            @staticmethod
            def clean_tags(tags):
                raise RuntimeError("坏了")

        monkeypatch.setattr(scraper, "namemap", Boom)
        assert scraper.clean_tags(["OL"]) == ["OL"]

    def test_to_simplified_degrades(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "namemap", None)
        assert scraper.to_simplified("雛形みくる") == "雛形みくる"

    def test_actor_display_degrades(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "namemap", None)
        got = scraper.actor_display("雛形みくる")
        assert got["name"] == "雛形みくる" and got["zh"] == ""

    def test_translate_without_module(self, scraper, monkeypatch):
        monkeypatch.setattr(scraper, "translator", None)
        got = scraper.translate_fields(display_number="SNOS-380", title_jp="日文", plot_jp="",
                                       actors=[], opts={})
        assert got["called"] is False and got["status"] == "untranslated"

    def test_translate_switch_off(self, scraper, monkeypatch):
        class T:
            @staticmethod
            def translate_batch(items, model="", allow_machine=False):
                raise AssertionError("开关关掉就不该调 LLM")

        monkeypatch.setattr(scraper, "translator", T)
        got = scraper.translate_fields(display_number="SNOS-380", title_jp="日文", plot_jp="",
                                       actors=[], opts={"translate": False})
        assert got["called"] is False

    def test_translate_ok(self, scraper, monkeypatch):
        class T:
            @staticmethod
            def translate_batch(items, model="", allow_machine=False):
                assert items[0]["number"] == "SNOS-380"
                return {"SNOS-380": {"title_zh": "中文标题", "plot_zh": "中文简介",
                                     "status": "done"}}

        monkeypatch.setattr(scraper, "translator", T)
        got = scraper.translate_fields(display_number="SNOS-380", title_jp="日文", plot_jp="日简介",
                                       actors=[], opts={})
        assert got["called"] and got["title_zh"] == "中文标题" and got["status"] == "done"

    def test_translate_passes_store_when_supported(self, scraper, monkeypatch):
        """S4 的签名带 `store=`（落 `translate` 表缓存）时要传进去；不带就静默不传。"""
        seen = {}

        class WithStore:
            @staticmethod
            def translate_batch(items, model="", allow_machine=False, *, store=None):
                seen["store"] = store
                return {"SNOS-380": {"title_zh": "t", "plot_zh": "", "status": "done"}}

        monkeypatch.setattr(scraper, "translator", WithStore)
        store = FakeStore()
        scraper.translate_fields(display_number="SNOS-380", title_jp="日文", plot_jp="",
                                 actors=[], opts={}, store=store, key="SNOS380")
        assert seen["store"] is store

        class WithoutStore:
            @staticmethod
            def translate_batch(items, model="", allow_machine=False):
                seen["bare"] = True
                return {"SNOS-380": {"title_zh": "t", "plot_zh": "", "status": "done"}}

        monkeypatch.setattr(scraper, "translator", WithoutStore)
        got = scraper.translate_fields(display_number="SNOS-380", title_jp="日文", plot_jp="",
                                       actors=[], opts={}, store=store, key="SNOS380")
        assert seen.get("bare") and got["called"]

    def test_accepts_probe(self, scraper):
        def bare(a, b=1):
            return None

        def kw(a, **rest):
            return None

        assert scraper._accepts(bare, "b") is True
        assert scraper._accepts(bare, "c") is False
        assert scraper._accepts(kw, "anything") is True

    def test_translate_failure_degrades(self, scraper, monkeypatch):
        class T:
            @staticmethod
            def translate_batch(items, model="", allow_machine=False):
                raise RuntimeError("网关 500")

        monkeypatch.setattr(scraper, "translator", T)
        store = FakeStore()
        got = scraper.translate_fields(display_number="SNOS-380", title_jp="日文", plot_jp="",
                                       actors=[], opts={}, store=store, key="SNOS380")
        assert got["called"] is False and "网关 500" in got["error"]
        assert store.logs[0]["source"] == "llm" and store.logs[0]["status"] == "error"

    def test_strip_comments_and_div_block(self, scraper):
        html = '<div class="info"><div class="intro">A<div class="x">B</div>C</div>D</div>'
        assert "B" in scraper._div_block(html, '<div class="intro">')
        assert "D" not in scraper._div_block(html, '<div class="intro">')
        assert scraper._class_block('<div class="intro-header">H</div>', "intro") == ""
        assert scraper.strip_comments("a<!-- b -->c") == "ac"

    def test_module_imports_without_namemap_translator(self, scraper):
        """`namemap`/`translator` 尚未落地时模块必须能正常工作（延迟导入 + 降级）。"""
        assert hasattr(scraper, "namemap")
        assert hasattr(scraper, "translator")
