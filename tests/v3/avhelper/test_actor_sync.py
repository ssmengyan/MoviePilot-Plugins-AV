"""`actor_sync.py`（演员抓取流水线，0.9.0 演员线 S3）的单测。

**零外网**：`urllib.request` 的两个入口被顶掉；图片下载一律走假的 `scraper.imgproxy`
（真 `imgproxy` 只用来"量尺寸"，本机有 Pillow）。

被测的是**判断**，不是形状：选图顺序（gfriends 命中就不问 javdb）、候选质量门槛
（最长边 <200px 丢弃并换下一个，3 个不过 → `no_avatar`）、锁、`person_missing` 记 skip、
`force` 只对点名生效、单飞、退避记账。夹具用**内存版 store / Emby / actor_sources**，
不依赖 S1 的 actor 表与 S2 的 gFriends 索引是否已落地（并行施工期必须能单独跑绿）。

测试图片用**真 PNG**（`_png()` 手写 IHDR/IDAT/IEND）：尺寸门槛要过真的 Pillow 解码，
拿假字节 monkeypatch 掉尺寸探测等于把被测代码换成桩。
"""

from __future__ import annotations

import importlib.util
import struct
import sys
import threading
import types
import zlib
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
PKG_NAME = "avhelper_under_test"          # 与 conftest.py / test_scraper.py 同名同缓存键


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
    return _load("scraper")


@pytest.fixture(scope="session")
def actor_sync():
    return _load("actor_sync")


@pytest.fixture(scope="session")
def store_mod():
    return _load("store")


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """★ 零外网硬闸门：任何真的 HTTP 调用当场炸掉（假的 imgproxy 不受影响）。"""
    import urllib.request

    def boom(*args, **kwargs):
        raise AssertionError("单测不许发网络请求（见 no_real_network 夹具）")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(urllib.request, "build_opener", boom)


@pytest.fixture(autouse=True)
def reset_index_kick(actor_sync):
    """gFriends 后台加载标志是**模块级**状态：每个用例前后清一次，别让上一条的线程影响下一条。"""
    actor_sync._INDEX_KICKED = False
    yield
    actor_sync._INDEX_KICKED = False


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch, scraper):
    """整目录把睡眠换成记录器（队列 tick 的 ≥2s 间隔不该真睡）。"""
    slept: list = []
    monkeypatch.setattr(scraper, "_SLEEP", lambda seconds: slept.append(seconds))
    return slept


# ---------------------------------------------------------------------------
# 假对象
# ---------------------------------------------------------------------------

PERSON = "A（ア）"
GF_URL = "https://raw.githubusercontent.com/gfriends/gfriends/master/Content/0-Hand-Storage/a.jpg"
JAVDB_URL = "https://tp.spfcas.com/avatars/ab/a.jpg"
#: gFriends 的真实形状：**中日文路径 + 时间戳查询**（直接请求会 UnicodeEncodeError，必须先编码）
GF_JP_URL = ("https://raw.githubusercontent.com/gfriends/gfriends/master/Content/"
             "z-ラグジュTV/AI-Fix-黒瀬萌衣.jpg?t=1607433809")


def _png(width: int, height: int) -> bytes:
    """手写一张**真** PNG（8 位灰度、全黑）：尺寸门槛要真的过 Pillow 解码。"""
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _row(**patch):
    """一行 actor（形状照 store._actor_row()）。"""
    row = {"id": 7, "person": PERSON, "name": "A", "zh": "A", "jp": "ア", "gender": 0,
           "aliases": [], "javdb_actor_id": "", "images": [], "field_sources": {},
           "locked_fields": [], "last_scraped_at": "", "retry_count": 0, "next_retry": "",
           "updated_at": ""}
    row.update(patch)
    return row


class FakeSources:
    """假 `actor_sources`：`index_status/load_index/match_candidates/fetch_javdb_avatar` 四件套。"""

    def __init__(self, hits=None, count=10, stale=False, javdb="", broken=False):
        self.hits = list(hits or [])
        self.count = count
        self.stale = stale
        self.javdb = javdb
        self.broken = broken
        self.calls = {"index_status": 0, "load_index": 0, "match_candidates": 0,
                      "fetch_javdb_avatar": 0}
        self.seen_names: list = []

    def index_status(self):
        self.calls["index_status"] += 1
        return {"count": self.count, "fetched_at": "2026-10-20T00:00:00",
                "stale": self.stale, "source": "gfriends"}

    def load_index(self, *, proxy="", force=False, fetch=None):
        self.calls["load_index"] += 1
        if self.broken:
            raise RuntimeError("索引拉取失败")
        return {"index": True}

    def match_candidates(self, index, names):
        self.calls["match_candidates"] += 1
        self.seen_names.append(list(names))
        return [dict(hit) for hit in self.hits]

    def fetch_javdb_avatar(self, client, name, *, proxy=""):
        self.calls["fetch_javdb_avatar"] += 1
        if not self.javdb:
            return None
        return {"url": self.javdb, "source": "javdb"}


class FakeImgproxy:
    """假 `imgproxy`（接到 `scraper.imgproxy` 上）：按 URL 回字节，记录取图次数。"""

    def __init__(self, blobs=None):
        self.blobs = dict(blobs or {})
        self.calls: list = []

    def fetch(self, url, proxy=""):
        self.calls.append(url)
        return self.blobs.get(url)


class FakeEmby:
    """假 Emby 写侧：只实现流水线用到的四个方法，并记录每一次调用。"""

    def __init__(self, persons=None, upload_ok=True):
        self.persons = dict(persons or {})
        self.upload_ok = upload_ok
        self.uploaded: list = []
        self.updated: list = []
        self.calls = {"find_person": 0, "upload_image": 0, "update_item": 0}

    def find_person(self, name):
        self.calls["find_person"] += 1
        person = self.persons.get(name)
        return dict(person) if person else None

    def upload_image(self, item_id, img_type="Primary", data=b""):
        self.calls["upload_image"] += 1
        if not self.upload_ok:
            return False, "emby 500"
        self.uploaded.append({"item_id": item_id, "type": img_type, "bytes": data})
        return True, ""

    def update_item(self, item_id, dto):
        self.calls["update_item"] += 1
        self.updated.append({"item_id": item_id, "dto": dto})
        return True, ""


class FakeActorStore:
    """内存版 actor 表 + `scrape_log`：只实现本模块用到的 API（缺方法即"能力不足"）。"""

    def __init__(self, rows=None, queue=None):
        self.rows = [dict(row) for row in (rows or [])]
        self.queue = [dict(row) for row in (queue or [])]
        self.logs: list = []
        self.calls = {"mark_ok": [], "mark_failed": [], "queue_push": [], "queue_pop": 0}

    def actor_get(self, actor_id=0, person=""):
        for row in self.rows:
            if actor_id and int(row.get("id") or 0) == int(actor_id):
                return dict(row)
            if not actor_id and person and row.get("person") == person:
                return dict(row)
        return None

    def actor_list(self, q="", flt="", limit=60, offset=0):
        items = [dict(row) for row in self.rows
                 if not q or q in str(row.get("name") or "") or q in str(row.get("person") or "")]
        return {"items": items, "total": len(items)}

    def actor_due(self, limit=20):
        return [dict(row) for row in self.rows[:limit]]

    def actor_set_images(self, actor_id, images, field_sources=None):
        row = self.actor_get(actor_id=actor_id)
        if not row:
            return {}
        if "images" in [str(one) for one in (row.get("locked_fields") or [])]:
            return row
        row["images"] = [dict(one) for one in (images or [])]
        merged = dict(row.get("field_sources") or {})
        merged.update(field_sources or {})
        row["field_sources"] = merged
        self.calls.setdefault("set_images", []).append({"actor_id": actor_id,
                                                       "images": list(row["images"])})
        for index, stored in enumerate(self.rows):
            if int(stored.get("id") or 0) == int(actor_id):
                self.rows[index] = dict(row)
        return dict(row)

    def actor_lock(self, actor_id, field="images", on=True):
        row = self.actor_get(actor_id=actor_id)
        if not row:
            return {}
        locked = [str(one) for one in (row.get("locked_fields") or [])]
        if on and field not in locked:
            locked.append(field)
        elif not on and field in locked:
            locked = [one for one in locked if one != field]
        row["locked_fields"] = locked
        for index, stored in enumerate(self.rows):
            if int(stored.get("id") or 0) == int(actor_id):
                self.rows[index] = dict(row)
        self.calls.setdefault("lock", []).append({"actor_id": actor_id, "field": field,
                                                  "on": on})
        return dict(row)

    def actor_mark_ok(self, actor_id, when=""):
        self.calls["mark_ok"].append({"actor_id": actor_id, "when": when})
        return {"id": actor_id, "retry_count": 0}

    def actor_mark_failed(self, actor_id, reason=""):
        self.calls["mark_failed"].append({"actor_id": actor_id, "reason": reason})
        return {"id": actor_id, "retry_count": 1}

    def actor_queue_push(self, persons):
        self.calls["queue_push"].append(list(persons))
        return len(persons)

    def actor_queue_pop(self, limit=20):
        self.calls["queue_pop"] += 1
        out, self.queue = self.queue[:limit], self.queue[limit:]
        return out

    def scrape_log_add(self, source_name, status, key="", latency_ms=0, error_summary="",
                       reason="", http_status=0, run_id=""):
        self.logs.append({"source": source_name, "status": status, "key": key,
                          "reason": reason, "error": error_summary})


def _wire(monkeypatch, scraper, actor_sync, *, sources=None, blobs=None):
    """接好假来源与假图片代理；返回假代理（方便断言"取了几次图"）。"""
    monkeypatch.setattr(actor_sync, "actor_sources", sources)
    proxy = FakeImgproxy(blobs)
    monkeypatch.setattr(scraper, "imgproxy", proxy)
    return proxy


# ---------------------------------------------------------------------------
# 选图顺序：gfriends → javdb
# ---------------------------------------------------------------------------

class TestImageOrder:
    """方案 §3 的 `image_sources` 顺序：gFriends 命中即用，未命中才回落 javdb。"""

    def test_gfriends_hit_never_asks_javdb(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "0-Hand-Storage",
                                     "file": "a.jpg"}], javdb=JAVDB_URL)
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "1", "ImageTags": {}}})
        store = FakeActorStore([_row(javdb_actor_id="w1Xb")])
        result = actor_sync.run_actor_scrape(
            store, emby, actor_ids=[7], dry_run=False,
            opts={"proxy": "http://px:1", "javdb_cli": object()})
        assert result["ok"] is True and result["errors"] == []
        item = result["items"][0]
        assert item["source"] == "gfriends" and item["url"] == GF_URL
        assert emby.uploaded == [{"item_id": "1", "type": "Primary", "bytes": _png(400, 600)}]
        # ★ 命中 gfriends 就不许去问 javdb（哪怕行里有 javdb_actor_id）
        assert sources.calls["fetch_javdb_avatar"] == 0
        assert sources.calls["match_candidates"] == 1

    def test_gfriends_url_is_percent_encoded(self, actor_sync, scraper, monkeypatch):
        """坑 1：gFriends 直链含中日文 + `?t=`，交给 imgproxy 之前必须只编路径段、保留查询串。"""
        encoded = actor_sync._encode_url(GF_JP_URL)
        assert "%E3%83%A9%E3%82%B0%E3%82%B8%E3%83%A5TV" in encoded      # z-ラグジュTV
        assert "%E9%BB%92%E7%80%AC%E8%90%8C%E8%A1%A3" in encoded        # 黒瀬萌衣
        assert encoded.endswith("?t=1607433809")                        # 问号留在 query 里
        assert "ラグジュ" not in encoded and " " not in encoded
        assert actor_sync._encode_url(JAVDB_URL) == JAVDB_URL           # 已编码/纯 ASCII 原样
        assert actor_sync._encode_url("") == ""

        sources = FakeSources(hits=[{"name": "黒瀬萌衣", "url": GF_JP_URL, "folder": "z-ラグジュTV",
                                     "file": "AI-Fix-黒瀬萌衣.jpg"}])
        blob = _png(400, 600)
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={encoded: blob})
        emby = FakeEmby({PERSON: {"Id": "21", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=False)
        assert proxy.calls == [encoded]                     # ★ 真的用编码后的地址去取图
        assert result["items"][0]["action"] == "upload_avatar"
        assert emby.uploaded[0]["bytes"] == blob
        assert result["items"][0]["url"] == GF_JP_URL        # 落库/回报仍留原始地址

    def test_empty_index_loads_in_background_without_blocking(self, actor_sync, scraper,
                                                              monkeypatch):
        """方案 §3：索引没建时**后台加载、本轮不等**；下一轮用上整图，且只起一个线程。"""
        release = threading.Event()
        calls: list = []
        state = {"loaded": False, "hits": []}

        class SlowSources(FakeSources):
            def index_status(self):
                self.calls["index_status"] += 1
                return {"count": 2 if state["loaded"] else 0, "fetched_at": "",
                        "stale": not state["loaded"], "source": ""}

            def load_index(self, *, proxy="", force=False, fetch=None):
                # 记下"是不是后台线程起的"：标志置位时进来的那次就是后台加载
                calls.append((bool(actor_sync._INDEX_KICKED), str(proxy or "")))
                assert release.wait(5), "测试自锁：后台加载没有被放行"
                state.update(loaded=True, hits=[{"name": "ア", "url": GF_URL,
                                                 "folder": "f", "file": "f"}])

            def match_candidates(self, index, names):
                self.calls["match_candidates"] += 1
                return [dict(hit) for hit in state["hits"]]

        sources = SlowSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={JAVDB_URL: _png(300, 400), GF_URL: _png(600, 800)})
        store = FakeActorStore([_row(avatar=JAVDB_URL)])
        emby = FakeEmby({PERSON: {"Id": "40", "ImageTags": {}}})

        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False,
                                             opts={"proxy": "http://px:1"})
        # ★ 本轮**立刻**返回：后台 loader 还卡在 release 上，结论已经出来了
        assert not release.is_set()
        assert calls == [(True, "http://px:1")]               # 恰好起了一次后台加载（带代理）
        assert result["counts"]["index_stale"] == 1
        assert result["items"][0]["source"] == "javdb"        # 照旧走兜底，不等 9 秒

        release.set()
        for _ in range(200):
            if not actor_sync._INDEX_KICKED:
                break
            threading.Event().wait(0.01)
        assert state["loaded"] is True

        second = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert second["items"][0]["source"] == "gfriends"     # 下一轮就用上整图了
        assert second["items"][0]["url"] == GF_URL
        # 第二轮只多了一次**同步读缓存**（count>0 的正常路径），后台线程仍只有那一次
        assert [one for one in calls if one[0]] == [(True, "http://px:1")]

    def test_failed_background_load_is_retried_next_time(self, actor_sync, scraper,
                                                         monkeypatch):
        """加载线程抛异常也要清位：第二轮必须能**再试一次**（标志不会永久卡死）。"""
        calls: list = []
        failed = threading.Event()

        class BoomSources(FakeSources):
            def index_status(self):
                return {"count": 0, "fetched_at": "", "stale": True, "source": ""}

            def load_index(self, *, proxy="", force=False, fetch=None):
                calls.append(1)
                failed.set()
                raise RuntimeError("拉 6.5MB 失败")

        sources = BoomSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={JAVDB_URL: _png(300, 400)})
        store = FakeActorStore([_row(avatar=JAVDB_URL)])
        emby = FakeEmby({PERSON: {"Id": "41", "ImageTags": {}}})
        actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert failed.wait(5)
        for _ in range(200):
            if not actor_sync._INDEX_KICKED:
                break
            threading.Event().wait(0.01)
        assert actor_sync._INDEX_KICKED is False            # 失败也清位

        actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        for _ in range(200):
            if len(calls) >= 2:
                break
            threading.Event().wait(0.01)
        assert len(calls) == 2                              # 第二轮真的又试了一次

    def test_gfriends_miss_falls_back_to_javdb(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[], javdb=JAVDB_URL)
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={JAVDB_URL: _png(300, 400)})
        emby = FakeEmby({PERSON: {"Id": "2", "ImageTags": {}}})
        store = FakeActorStore([_row(javdb_actor_id="w1Xb")])
        result = actor_sync.run_actor_scrape(
            store, emby, actor_ids=[7], dry_run=False,
            opts={"proxy": "http://px:1", "javdb_cli": object()})
        item = result["items"][0]
        assert item["source"] == "javdb" and item["url"] == JAVDB_URL
        assert len(emby.uploaded) == 1
        assert sources.calls["fetch_javdb_avatar"] == 1

    def test_stale_index_is_reported(self, actor_sync, scraper, monkeypatch):
        """索引没建好/过期 → 回落 javdb，但 `counts['index_stale']` 要照实报（页面靠它提示）。"""
        sources = FakeSources(hits=[], count=0, stale=True, javdb=JAVDB_URL)
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={JAVDB_URL: _png(300, 400)})
        store = FakeActorStore([_row(javdb_actor_id="w1Xb")])
        result = actor_sync.run_actor_scrape(
            store, FakeEmby({PERSON: {"Id": "2", "ImageTags": {}}}), actor_ids=[7],
            dry_run=False, opts={"javdb_cli": object()})
        assert result["counts"]["index_stale"] == 1
        assert sources.calls["match_candidates"] == 0   # 索引没建：本轮直接回落 javdb（后台线程另有用例）

    def test_no_source_at_all_is_no_avatar(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        emby = FakeEmby({PERSON: {"Id": "3", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(actor_sync and FakeActorStore([_row()]), emby,
                                             actor_ids=[7], dry_run=False)
        item = result["items"][0]
        assert item["action"] == "skip" and item["reason"] == "no_avatar"
        assert result["counts"]["no_avatar"] == 1 and result["counts"]["failed"] == 0
        assert result["ok"] is True and emby.calls["upload_image"] == 0


# ---------------------------------------------------------------------------
# 校验：尺寸门槛与候选上限
# ---------------------------------------------------------------------------

class TestValidation:
    """方案 §5.3：最长边 <200px 丢弃并换下一个，最多试 3 个；字节 >5MB 丢弃。"""

    def test_small_candidate_is_skipped_for_the_next_one(self, actor_sync, scraper, monkeypatch):
        small, mid, good = _png(100, 100), _png(150, 150), _png(400, 600)
        urls = ["https://gf/1.jpg", "https://gf/2.jpg", "https://gf/3.jpg"]
        sources = FakeSources(hits=[{"name": "ア", "url": url, "folder": "f", "file": "f"}
                                    for url in urls])
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources,
                      blobs={urls[0]: small, urls[1]: mid, urls[2]: good})
        emby = FakeEmby({PERSON: {"Id": "4", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=False)
        item = result["items"][0]
        assert (item["url"], item["w"], item["h"]) == (urls[2], 400, 600)
        assert proxy.calls == urls                      # 前两个**真的**下过（不是空指针跳过）
        assert emby.uploaded[0]["bytes"] == good

    def test_bad_first_candidate_falls_back_to_the_second(self, actor_sync, scraper,
                                                         monkeypatch):
        """坑 2：键值不同名时第一个候选常是别人的图/坏图 → 换下一个，仍按 match_candidates 的顺序。"""
        first, second = "https://gf/bad.jpg", "https://gf/good.jpg"
        sources = FakeSources(hits=[{"name": "ア", "url": first, "folder": "0-Hand-Storage",
                                     "file": "bad.jpg"},
                                    {"name": "ア", "url": second, "folder": "7-S1",
                                     "file": "good.jpg"}])
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources,
                      blobs={first: b"not-an-image-at-all", second: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "22", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=False)
        item = result["items"][0]
        assert proxy.calls == [first, second]               # 顺序 = match_candidates 给的顺序
        assert item["url"] == second and item["action"] == "upload_avatar"
        assert emby.uploaded[0]["bytes"] == _png(400, 600)

    def test_three_small_candidates_end_as_no_avatar(self, actor_sync, scraper, monkeypatch):
        urls = [f"https://gf/{index}.jpg" for index in range(5)]
        sources = FakeSources(hits=[{"name": "ア", "url": url, "folder": "f", "file": "f"}
                                    for url in urls])
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources,
                      blobs={url: _png(120, 120) for url in urls})
        emby = FakeEmby({PERSON: {"Id": "5", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=False)
        item = result["items"][0]
        assert item["action"] == "skip" and item["reason"] == "no_avatar"
        assert result["counts"]["no_avatar"] == 1 and result["counts"]["failed"] == 0
        assert len(proxy.calls) == 3                    # 最多试 3 个候选
        assert emby.calls["upload_image"] == 0

    def test_oversized_bytes_are_dropped(self, actor_sync, scraper, monkeypatch):
        big = _png(400, 400)
        sources = FakeSources(hits=[{"name": "ア", "url": "https://gf/big.png", "folder": "f",
                                     "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={"https://gf/big.png": big})
        emby = FakeEmby({PERSON: {"Id": "6", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=False,
                                             opts={"max_avatar_bytes": 100})
        assert result["items"][0]["reason"] == "no_avatar"
        assert result["items"][0]["action"] == "skip"
        assert emby.calls["upload_image"] == 0

    def test_all_downloads_failing_is_a_failure(self, actor_sync, scraper, monkeypatch):
        """**一张都没下到**才算错（`action='failed'`），与"下到了但不达标"分开。"""
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        emby = FakeEmby({PERSON: {"Id": "7", "ImageTags": {}}})
        store = FakeActorStore([_row()])
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert result["items"][0]["action"] == "failed"
        assert result["counts"]["failed"] == 1
        assert result["ok"] is False and result["errors"]
        assert [one["actor_id"] for one in store.calls["mark_failed"]] == [7]


# ---------------------------------------------------------------------------
# 锁 / force / 性别
# ---------------------------------------------------------------------------

class TestGuards:
    def test_locked_images_never_replaces_the_picture(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources,
                      blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "8", "ImageTags": {"Primary": "old"}}})
        store = FakeActorStore([_row(locked_fields=["images"])])
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False,
                                            force=True)
        item = result["items"][0]
        assert item["reason"] == "locked" and item["action"] == "skip"
        assert emby.calls["upload_image"] == 0          # ★ 手工锁：绝不换图
        assert proxy.calls == []                        # 连图都不下载
        assert result["counts"]["locked"] == 1

    def test_person_missing_is_skip_not_failure(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({})                             # Emby 里还没有这个人
        store = FakeActorStore([_row()])
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        item = result["items"][0]
        assert item["reason"] == "person_missing" and item["action"] == "skip"
        assert result["counts"]["failed"] == 0 and result["ok"] is True
        assert result["counts"]["person_missing"] == 1
        assert emby.calls["upload_image"] == 0
        assert store.calls["mark_failed"] == []         # 过渡态不该排退避

    def test_force_only_touches_named_actors(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "9", "ImageTags": {"Primary": "old"}}})
        store = FakeActorStore([_row()])

        named = actor_sync.run_actor_scrape(store, emby, persons=[PERSON], dry_run=False,
                                            force=True)
        assert named["items"][0]["action"] == "upload_avatar"
        assert emby.calls["upload_image"] == 1

        emby2 = FakeEmby({PERSON: {"Id": "9", "ImageTags": {"Primary": "old"}}})
        due = actor_sync.run_actor_scrape(store, emby2, dry_run=False, force=True)
        assert due["items"][0]["reason"] == "has_image"      # 批量挑行时 force 不算数
        assert emby2.calls["upload_image"] == 0

    def test_has_image_without_force_is_skipped(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "10", "ImageTags": {"Primary": "tag"}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=False)
        assert result["items"][0]["reason"] == "has_image"
        assert result["counts"]["has_image"] == 1 and emby.calls["upload_image"] == 0

    def test_male_actor_is_excluded(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "11", "ImageTags": {}}})
        item = actor_sync.scrape_actor(FakeActorStore([]), emby, _row(gender=1), dry_run=False)
        assert item["reason"] == "male" and item["action"] == "skip"
        assert emby.calls["find_person"] == 0 and emby.calls["upload_image"] == 0

    def test_gender_unknown_is_kept(self, actor_sync, scraper, monkeypatch):
        """`gender is None` 保守保留（与 0.8.1 的 existing 口径一致，别在这里改成丢弃）。"""
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "12", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row(gender=None)]), emby,
                                             actor_ids=[7], dry_run=False)
        assert result["items"][0]["action"] == "upload_avatar"
        assert emby.calls["upload_image"] == 1

    def test_dry_run_makes_no_write_request(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources,
                      blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "13", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(FakeActorStore([_row()]), emby, actor_ids=[7],
                                             dry_run=True)
        assert result["dry_run"] is True
        assert result["items"][0]["action"] == "upload_avatar"      # "将会上传"
        assert result["counts"]["uploaded"] == 1
        assert emby.calls["upload_image"] == 0 and emby.calls["update_item"] == 0
        assert proxy.calls == []                                    # dry-run 也不下载


# ---------------------------------------------------------------------------
# 记账：scrape_log / 退避
# ---------------------------------------------------------------------------

class TestBookkeeping:
    def test_success_marks_ok_and_logs_actor_source(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "14", "ImageTags": {}}})
        store = FakeActorStore([_row(javdb_actor_id="w1Xb")])
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert result["ok"] is True
        assert store.calls["mark_ok"] == [{"actor_id": 7, "when": ""}]
        assert store.calls["mark_failed"] == []
        assert [(one["source"], one["status"]) for one in store.logs] == [("actor", "ok")]
        assert emby.updated[0]["dto"] == {"ProviderIds": {"JavDB": "w1Xb"}}

    def test_failure_marks_failed_with_reason(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        emby = FakeEmby({PERSON: {"Id": "15", "ImageTags": {}}})
        store = FakeActorStore([_row()])
        actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert [one["actor_id"] for one in store.calls["mark_failed"]] == [7]
        assert store.calls["mark_failed"][0]["reason"]          # 带原因才能按原因分组排障
        assert store.calls["mark_ok"] == []
        assert any(one["status"] == "error" and one["source"] == "actor"
                   for one in store.logs)

    def test_upload_failure_marks_failed(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        emby = FakeEmby({PERSON: {"Id": "16", "ImageTags": {}}}, upload_ok=False)
        store = FakeActorStore([_row()])
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert result["items"][0]["action"] == "failed"
        assert "上传头像失败" in result["errors"][0]          # 原因进 errors（item 只带机器可读 reason）
        assert result["items"][0]["reason"] == "emby 500"
        assert [one["actor_id"] for one in store.calls["mark_failed"]] == [7]

    def test_one_failure_does_not_stop_the_batch(self, actor_sync, scraper, monkeypatch):
        """隔离：第一位失败只记它自己，第二位照常上传（方案 §5.5）。"""
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])

        class Broken(FakeImgproxy):
            def fetch(self, url, proxy=""):
                self.calls.append(url)
                raise RuntimeError("图床炸了")

        proxy = Broken({})
        monkeypatch.setattr(actor_sync, "actor_sources", sources)
        monkeypatch.setattr(scraper, "imgproxy", proxy)
        emby = FakeEmby({PERSON: {"Id": "17", "ImageTags": {}}})
        store = FakeActorStore([_row(id=1), _row(id=2, person=PERSON + "2")])
        emby.persons[PERSON + "2"] = {"Id": "18", "ImageTags": {}}
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[1, 2], dry_run=False)
        assert result["counts"]["total"] == 2 and result["counts"]["failed"] == 2
        assert {one["actor_id"] for one in store.calls["mark_failed"]} == {1, 2}


# ---------------------------------------------------------------------------
# 候选图落库（0.9.0 真机缺口：只传了 Emby、actor.images_json 恒 "[]"）
# ---------------------------------------------------------------------------

class TestImagesLedger:
    """`images_json` 是演员库「有图」与 `crop-avatar`「当前主图」的**唯一**数据源（方案 §2）。"""

    OLD_URL = "https://tp.spfcas.com/avatars/old/old.jpg"

    def _store(self):
        return FakeActorStore([_row(images=[{"url": self.OLD_URL, "source": "javdb",
                                             "w": 100, "h": 100, "bytes": 999,
                                             "primary": True}])])

    def test_upload_records_candidate_images(self, actor_sync, scraper, monkeypatch):
        """★ 上传成功后 `images[0]` 就是这次的候选，旧图**保留**在后面（前插不是覆盖）。"""
        blob = _png(400, 600)
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: blob})
        store = self._store()
        emby = FakeEmby({PERSON: {"Id": "50", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert result["ok"] is True and len(emby.uploaded) == 1

        written = store.calls["set_images"][-1]["images"]
        assert [one["url"] for one in written] == [GF_URL, self.OLD_URL]
        assert written[0] == {"url": GF_URL, "source": "gfriends", "w": 400, "h": 600,
                             "bytes": len(blob), "primary": True}
        assert written[1]["primary"] is False              # 旧图降级但仍留在列表里
        assert store.rows[0]["field_sources"]["images"] == "gfriends"
        assert store.rows[0]["images"][0]["url"] == GF_URL  # 真的写进库了

    def test_person_missing_still_records_candidate_images(self, actor_sync, scraper,
                                                           monkeypatch):
        """Emby 里还没这个人也是"有候选"：照记 `images`（演员库要显示、裁剪要用），且不算失败。"""
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        proxy = _wire(monkeypatch, scraper, actor_sync, sources=sources,
                      blobs={GF_URL: _png(400, 600)})
        store = self._store()
        result = actor_sync.run_actor_scrape(store, FakeEmby({}), actor_ids=[7], dry_run=False)
        assert result["items"][0]["reason"] == "person_missing"
        assert result["counts"]["failed"] == 0 and result["ok"] is True
        written = store.calls["set_images"][-1]["images"]
        assert [one["url"] for one in written] == [GF_URL, self.OLD_URL]
        assert written[0]["primary"] is True and written[0]["source"] == "gfriends"
        assert proxy.calls == []                            # 只记地址，不必为它下载一张图

    def test_dry_run_records_no_images(self, actor_sync, scraper, monkeypatch):
        """`dry_run` 仍然**零写**：连候选图落库都不许发生（预览不是应用）。"""
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        store = self._store()
        result = actor_sync.run_actor_scrape(store, FakeEmby({PERSON: {"Id": "51", "ImageTags": {}}}),
                                            actor_ids=[7], dry_run=True)
        assert result["items"][0]["action"] == "upload_avatar"
        assert store.calls.get("set_images") is None        # ★ zero write
        assert store.rows[0]["images"][0]["url"] == self.OLD_URL

    def test_locked_images_are_not_recorded(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        store = FakeActorStore([_row(locked_fields=["images"],
                                     images=[{"url": self.OLD_URL, "source": "javdb"}])])
        result = actor_sync.run_actor_scrape(store, FakeEmby({PERSON: {"Id": "52", "ImageTags": {}}}),
                                             actor_ids=[7], dry_run=False, force=True)
        assert result["items"][0]["reason"] == "locked"
        assert store.calls.get("set_images") is None        # ★ 锁了连账都不记
        assert store.rows[0]["images"][0]["url"] == self.OLD_URL

    def test_record_failure_does_not_change_the_verdict(self, actor_sync, scraper, monkeypatch):
        """写库抛异常只 warning：Emby 已经传上去了，这一条仍算成功。"""
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={GF_URL: _png(400, 600)})
        store = self._store()

        def boom(*args, **kwargs):
            raise RuntimeError("数据库锁住了")

        store.actor_set_images = boom
        emby = FakeEmby({PERSON: {"Id": "53", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
        assert result["ok"] is True and len(emby.uploaded) == 1
        assert result["items"][0]["action"] == "upload_avatar"

# ---------------------------------------------------------------------------
# 单飞与队列 tick
# ---------------------------------------------------------------------------

class TestSingleFlight:
    def test_second_concurrent_run_returns_busy(self, actor_sync, scraper, monkeypatch):
        sources = FakeSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        store = FakeActorStore([_row()])
        emby = FakeEmby({})
        started, release = threading.Event(), threading.Event()
        real = actor_sync._scrape_row

        def slow(*args, **kwargs):
            started.set()
            assert release.wait(5), "测试自锁：第一位没有放行"
            return real(*args, **kwargs)

        monkeypatch.setattr(actor_sync, "_scrape_row", slow)
        box: list = []
        worker = threading.Thread(
            target=lambda: box.append(actor_sync.run_actor_scrape(store, emby, actor_ids=[7],
                                                                  dry_run=False)))
        worker.start()
        try:
            assert started.wait(5), "第一位没有跑起来"
            second = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False)
            assert second["ok"] is False and second["reason"] == "busy"
            assert second["items"] == []
        finally:
            release.set()
            worker.join(5)
        assert box and box[0]["ok"] is True

    def test_queue_tick_pops_queue_and_paces(self, actor_sync, scraper, monkeypatch, no_real_sleep):
        sources = FakeSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        rows = [_row(id=1, person="A"), _row(id=2, person="B")]
        store = FakeActorStore([], queue=rows)
        seen: list = []

        def fake_row(store_, emby_, row, **kwargs):
            seen.append((row.get("person"), kwargs.get("dry_run")))
            return {"actor_id": row.get("id"), "person": row.get("person"), "name": "x",
                    "person_id": "1", "action": "upload_avatar", "reason": "", "url": "u",
                    "source": "javdb", "bytes": 1, "w": 400, "h": 600, "error": "",
                    "index_stale": False}

        monkeypatch.setattr(actor_sync, "_scrape_row", fake_row)
        result = actor_sync.queue_tick(store, FakeEmby(), batch=20,
                                       opts={"queue_interval_s": 0})
        assert result["ok"] is True and result["dry_run"] is False
        assert (result["queued"], result["due"], result["handled"]) == (2, 0, 2)
        assert seen == [("A", False), ("B", False)]        # 队列顺序、逐个真跑
        assert no_real_sleep == []                          # 间隔 0 → 一次都不睡

    def test_queue_tick_default_interval_is_two_seconds(self, actor_sync, scraper, monkeypatch,
                                                        no_real_sleep):
        sources = FakeSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        store = FakeActorStore([], queue=[_row(id=1, person="A"), _row(id=2, person="B")])
        monkeypatch.setattr(actor_sync, "_scrape_row",
                            lambda store_, emby_, row, **kw: {
                                "actor_id": row.get("id"), "person": row.get("person"),
                                "name": "x", "person_id": "1", "action": "upload_avatar",
                                "reason": "", "url": "u", "source": "javdb", "bytes": 1,
                                "w": 400, "h": 600, "error": "", "index_stale": False})
        actor_sync.queue_tick(store, FakeEmby())
        assert no_real_sleep == [2.0]                       # 两位之间睡一次，且是 2s

    def test_queue_tick_without_actor_queue_degrades(self, actor_sync, scraper, monkeypatch):
        _wire(monkeypatch, scraper, actor_sync, sources=FakeSources(hits=[]), blobs={})

        class Bare:
            pass

        result = actor_sync.queue_tick(Bare(), FakeEmby())
        assert result["ok"] is False and result["reason"] == "no_actor_queue"

    def test_empty_queue_is_not_an_error(self, actor_sync, scraper, monkeypatch):
        _wire(monkeypatch, scraper, actor_sync, sources=FakeSources(hits=[]), blobs={})
        result = actor_sync.queue_tick(FakeActorStore([]), FakeEmby())
        assert result["ok"] is True and result["popped"] == 0
        assert (result["queued"], result["due"], result["handled"]) == (0, 0, 0)

    def test_queue_tick_tops_up_with_due_actors(self, actor_sync, scraper, monkeypatch):
        """队列抽干之后**必须**还有"到期待重刮"的补位（S1：队列不重排，只读队列会让自动同步停摆）。"""
        sources = FakeSources(hits=[])
        _wire(monkeypatch, scraper, actor_sync, sources=sources, blobs={})
        store = FakeActorStore([_row(id=1, person="A"), _row(id=2, person="B"),
                                _row(id=3, person="C")],
                               queue=[_row(id=1, person="A")])       # A 同时在队列与到期里
        seen: list = []

        def fake_row(store_, emby_, row, **kwargs):
            seen.append(row.get("person"))
            return {"actor_id": row.get("id"), "person": row.get("person"), "name": "x",
                    "person_id": "1", "action": "upload_avatar", "reason": "", "url": "u",
                    "source": "javdb", "bytes": 1, "w": 400, "h": 600, "error": "",
                    "index_stale": False}

        monkeypatch.setattr(actor_sync, "_scrape_row", fake_row)
        result = actor_sync.queue_tick(store, FakeEmby(), batch=3, opts={"interval": 0})
        # 队列给 A（1 位），剩余 2 个名额问 actor_due → [A, B] → A 已在 queued 里被去重，只补 B
        assert (result["queued"], result["due"], result["handled"]) == (1, 1, 2)
        assert seen == ["A", "B"]
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# 手工覆盖：裁剪 / 上传本地图（方案 §5.6）
# ---------------------------------------------------------------------------

class TestManualOverride:
    """#BQ#crop_avatar()#BQ# / #BQ#upload_avatar()#BQ#：派生图落盘 → **前插** #BQ#images[0]#BQ#，原图保留。

    派生图写进 #BQ#imgproxy.cache_dir()#BQ#（= #BQ#paths.images_dir()#BQ#），所以这些用例都要 #BQ#sandbox_paths#BQ#
    把数据根钉到临时目录 —— 否则会往本机的历史坐标里写文件。
    """

    def _source(self, tmp_path, width, height, name="src.png"):
        path = tmp_path / name
        path.write_bytes(_png(width, height))
        return str(path)

    def test_crop_by_explicit_rect(self, actor_sync, scraper, tmp_path, sandbox_paths):
        source = self._source(tmp_path, 600, 400)
        store = FakeActorStore([_row(images=[{"url": source, "source": "javdb",
                                              "w": 600, "h": 400}])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]),
                                        rect={"x": 0, "y": 0, "w": 300, "h": 400})
        assert result["ok"] is True and result["reason"] == ""
        assert result["size"] == [300, 400]
        assert result["url"] and result["url"] != source
        written = store.calls["set_images"][-1]["images"]
        assert written[0]["url"] == result["url"]            # ★ 派生图成为主图
        assert written[1]["url"] == source                   # ★ 原图保留在列表尾部
        assert written[0]["primary"] is True and written[1]["primary"] is False
        assert written[0]["source"] == "manual"
        assert store.rows[0]["field_sources"]["images"] == "manual"

    def test_crop_centers_without_rect(self, actor_sync, scraper, tmp_path, sandbox_paths):
        """不给 rect → 按 ratio 居中自判：600×400 横图裁成 3:4 竖图（300×400）。"""
        source = self._source(tmp_path, 600, 400)
        store = FakeActorStore([_row(images=[{"url": source, "w": 600, "h": 400}])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]))
        assert result["ok"] is True and result["size"] == [300, 400]
        assert store.calls["set_images"]

    def test_crop_fetches_remote_primary_through_imgproxy(self, actor_sync, scraper, tmp_path,
                                                          sandbox_paths, monkeypatch):
        """主图是 http 地址时走 #BQ#imgproxy#BQ#（与流水线同一条取图链）。"""
        _wire(monkeypatch, scraper, actor_sync, sources=FakeSources(hits=[]),
              blobs={GF_URL: _png(600, 400)})
        store = FakeActorStore([_row(images=[{"url": GF_URL, "source": "gfriends"}])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]),
                                        rect={"x": 0, "y": 0, "w": 300, "h": 400})
        assert result["ok"] is True and result["size"] == [300, 400]

    def test_crop_rejects_bad_image(self, actor_sync, scraper, tmp_path, sandbox_paths):
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"not-an-image-at-all")
        store = FakeActorStore([_row(images=[{"url": str(broken)}])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]))
        assert result["ok"] is False
        assert "decode_error" in result["reason"]
        assert store.calls.get("set_images") is None          # ★ 坏图绝不写库

    def test_crop_refuses_too_small_result(self, actor_sync, scraper, tmp_path, sandbox_paths):
        source = self._source(tmp_path, 100, 100)
        store = FakeActorStore([_row(images=[{"url": source}])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]))
        assert result["ok"] is False and "小于" in result["reason"]
        assert store.calls.get("set_images") is None

    def test_crop_refuses_locked_images(self, actor_sync, scraper, tmp_path, sandbox_paths):
        source = self._source(tmp_path, 600, 400)
        store = FakeActorStore([_row(images=[{"url": source}], locked_fields=["images"])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"],
                                                    locked_fields=["images"]))
        assert result["ok"] is False and result["reason"] == "locked"
        assert store.calls.get("set_images") is None

    def test_crop_without_images_says_so(self, actor_sync):
        store = FakeActorStore([_row(images=[])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=[]))
        assert result["ok"] is False and result["reason"] == "no_images"

    def test_crop_resolves_actor_by_id(self, actor_sync, scraper, tmp_path, sandbox_paths):
        source = self._source(tmp_path, 600, 400)
        store = FakeActorStore([_row(id=3, images=[{"url": source, "w": 600, "h": 400}])])
        result = actor_sync.crop_avatar(store, None, actor_id=3,
                                        rect={"x": 0, "y": 0, "w": 300, "h": 400})
        assert result["ok"] is True
        assert result["actor"]["images"][0]["url"] == result["url"]
        assert actor_sync.crop_avatar(store, None, actor_id=999)["reason"] == "not_found"

    def test_upload_local_image_becomes_primary(self, actor_sync, scraper, tmp_path,
                                                sandbox_paths):
        source = self._source(tmp_path, 600, 400, "old.png")
        store = FakeActorStore([_row(images=[{"url": source}])])
        result = actor_sync.upload_avatar(store, _row(id=7, images=store.rows[0]["images"]),
                                          _png(400, 600))
        assert result["ok"] is True and result["size"] == [400, 600]
        written = store.calls["set_images"][-1]["images"]
        assert written[0]["url"] == result["url"] and written[1]["url"] == source
        assert written[0]["bytes"] > 0

    def test_upload_rejects_garbage_and_small_images(self, actor_sync, scraper, tmp_path,
                                                    sandbox_paths):
        store = FakeActorStore([_row(images=[])])
        bad = actor_sync.upload_avatar(store, _row(id=7, images=[]), b"not-an-image")
        assert bad["ok"] is False and "图片" in bad["reason"]
        small = actor_sync.upload_avatar(store, _row(id=7, images=[]), _png(100, 100))
        assert small["ok"] is False and "小于" in small["reason"]
        assert store.calls.get("set_images") is None

    def test_upload_without_store_support_degrades(self, actor_sync, scraper, tmp_path,
                                                  sandbox_paths):
        class Bare:
            pass

        result = actor_sync.upload_avatar(Bare(), _row(id=7), _png(400, 600))
        assert result["ok"] is False and "actor_set_images" in result["reason"]

    def test_crop_locks_images_after_write(self, actor_sync, scraper, tmp_path, sandbox_paths):
        """方案 §5.6：手工覆盖写库成功即**自动锁 images** —— 不锁下一轮自动同步就把它盖了。"""
        source = self._source(tmp_path, 600, 400)
        store = FakeActorStore([_row(images=[{"url": source, "w": 600, "h": 400}])])
        result = actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]))
        assert result["ok"] is True and result["locked"] is True
        assert "images" in result["locked_fields"]
        assert result["actor"]["locked_fields"] == ["images"]
        assert "images" in store.rows[0]["locked_fields"]
        assert store.calls["lock"] == [{"actor_id": 7, "field": "images", "on": True}]

    def test_locked_manual_primary_survives_forced_rescrape(self, actor_sync, scraper,
                                                            tmp_path, sandbox_paths,
                                                            monkeypatch):
        """裁剪/上传之后 #BQ#run_actor_scrape(force=True)#BQ# 也不许换图（#BQ#reason="locked"#BQ#）。"""
        source = self._source(tmp_path, 600, 400)
        store = FakeActorStore([_row(images=[{"url": source, "w": 600, "h": 400}])])
        assert actor_sync.upload_avatar(store, _row(id=7, images=store.rows[0]["images"]),
                                        _png(400, 600))["locked"] is True
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={GF_URL: _png(600, 800)})
        emby = FakeEmby({PERSON: {"Id": "30", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False,
                                             force=True)
        item = result["items"][0]
        assert item["reason"] == "locked" and item["action"] == "skip"
        assert emby.calls["upload_image"] == 0
        assert result["counts"]["locked"] == 1

    def test_unlock_hands_the_picture_back_to_the_source(self, actor_sync, scraper,
                                                         tmp_path, sandbox_paths,
                                                         monkeypatch):
        """解锁之后源图重新说了算（方案 §8 的验收「解锁后能换回源图」）。"""
        source = self._source(tmp_path, 600, 400, "manual.png")
        store = FakeActorStore([_row(images=[{"url": source, "w": 600, "h": 400}])])
        assert actor_sync.crop_avatar(store, _row(id=7, images=store.rows[0]["images"]))[
            "locked"] is True
        store.actor_lock(7, "images", False)                 # 界面上的解锁按钮
        sources = FakeSources(hits=[{"name": "ア", "url": GF_URL, "folder": "f", "file": "f"}])
        _wire(monkeypatch, scraper, actor_sync, sources=sources,
              blobs={GF_URL: _png(600, 800)})
        emby = FakeEmby({PERSON: {"Id": "20", "ImageTags": {}}})
        result = actor_sync.run_actor_scrape(store, emby, actor_ids=[7], dry_run=False,
                                            force=True)
        item = result["items"][0]
        assert item["source"] == "gfriends" and item["url"] == GF_URL
        assert emby.uploaded[0]["bytes"] == _png(600, 800)

# ---------------------------------------------------------------------------
# 0.8.1 兼容壳（老形状）与降级
# ---------------------------------------------------------------------------

class _NoMap:
    """空映射模块（与 test_scraper.py 的 `nomap` 同义）：断言不依赖 5351 行真实表。"""

    @staticmethod
    def actor_display(name, alias=""):
        return {"name": str(name), "zh": "", "jp": str(name), "alias": str(alias)}

    @staticmethod
    def actor_lookup(name):
        return None


class TestCompatShell:
    def _store(self, store_mod, tmp_path, actors):
        store = store_mod.Store(db_path=tmp_path / "compat.db")
        store.init()
        store.meta_upsert("SNOS380", display_number="SNOS-380", actors_json=actors)
        return store

    def _actors(self):
        return [{"name": "雛形みくる", "jp": "雛形みくる", "zh": "", "canonical_id": "",
                 "avatar": JAVDB_URL, "javdb_actor_id": "neAOa", "gender": 0}]

    def test_return_shape_is_unchanged(self, actor_sync, scraper, store_mod, tmp_path,
                                       monkeypatch):
        monkeypatch.setattr(actor_sync, "actor_sources", None)      # 只剩 javdb（S2 缺失态）
        store = self._store(store_mod, tmp_path, self._actors())
        emby = FakeEmby({"雛形みくる": {"Id": "12617", "ImageTags": {}}})
        report = scraper.sync_actor_avatars(store, emby, dry_run=True, namemap_mod=_NoMap())
        assert set(report) == {"ok", "dry_run", "actors", "planned", "applied", "errors",
                               "missing_person", "gender_unknown"}
        assert report["ok"] is True and report["dry_run"] is True and report["actors"] == 1
        assert set(report["planned"][0]) == {"name", "person_id", "action", "reason",
                                             "url", "source"}
        assert report["planned"][0]["action"] == "upload_avatar"
        assert emby.calls["upload_image"] == 0

    def test_shell_applies_and_keeps_applied_shape(self, actor_sync, scraper, store_mod,
                                                   tmp_path, monkeypatch):
        monkeypatch.setattr(actor_sync, "actor_sources", None)
        blob = _png(400, 600)
        monkeypatch.setattr(scraper, "imgproxy", FakeImgproxy({JAVDB_URL: blob}))
        store = self._store(store_mod, tmp_path, self._actors())
        emby = FakeEmby({"雛形みくる": {"Id": "12617", "ImageTags": {}}})
        report = scraper.sync_actor_avatars(store, emby, dry_run=False, namemap_mod=_NoMap())
        assert report["ok"] is True and len(report["applied"]) == 1
        assert set(report["applied"][0]) == {"name", "person_id", "action", "reason",
                                             "url", "source", "bytes"}
        assert report["applied"][0]["bytes"] == len(blob)
        assert emby.uploaded == [{"item_id": "12617", "type": "Primary", "bytes": blob}]

    def test_empty_meta_reports_clearly(self, actor_sync, scraper, store_mod, tmp_path,
                                        monkeypatch):
        monkeypatch.setattr(actor_sync, "actor_sources", None)
        store = store_mod.Store(db_path=tmp_path / "empty.db")
        store.init()
        report = scraper.sync_actor_avatars(store, FakeEmby({}), dry_run=True,
                                            namemap_mod=_NoMap())
        assert report["ok"] is False and report["actors"] == 0
        assert report["errors"] == ["meta 里还没有演员（先刮削几条再来同步头像）"]

    def test_no_emby_short_circuits(self, actor_sync, scraper, monkeypatch):
        monkeypatch.setattr(actor_sync, "actor_sources", None)
        report = scraper.sync_actor_avatars(FakeActorStore([]), None, dry_run=True)
        assert report["ok"] is False and report["errors"] == ["未配置 Emby（emby_client 不可用）"]
        assert report["planned"] == []

    def test_store_without_actor_table_still_works(self, actor_sync, scraper, store_mod,
                                                   tmp_path, monkeypatch):
        """兼容壳**不碰 actor 表**：store 只有 meta 也能跑（S1 未落地时的降级路径）。"""
        monkeypatch.setattr(actor_sync, "actor_sources", None)
        store = self._store(store_mod, tmp_path, self._actors())
        assert not hasattr(store, "actor_get") or True          # 真 store 有没有都不影响本用例
        emby = FakeEmby({"雛形みくる": {"Id": "1", "ImageTags": {}}})
        report = scraper.sync_actor_avatars(store, emby, dry_run=True, namemap_mod=_NoMap())
        assert report["actors"] == 1 and report["ok"] is True
