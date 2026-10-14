"""`__init__.py` 的 REST 端点与读侧接线单测（v4 刮削线 · S8）。

覆盖（任务书 A/B/C + 主统筹 2026-10-14 的两条口径更正）：

1. **路由表**：9 个新路径都在、全部 `auth:"bear"`、无重复路径、`/img` 仍匿名；
2. **`/img`**：`?emby=` / `?emby_person=` 服务端回源（Emby 主机名与 API Key **不进 URL/响应**），
   `?url=` 老分支一字不动；
3. **依赖模块缺失即降级**：`scraper.py` / `translator.py` 不在时回
   `{success:false, "刮削模块未就绪"}`，插件本身照常起得来；
4. **`/scrape/run` 的闸门**：`all=true` 必须带 `confirm=true`；单飞；Emby 未配置时明确报错；
5. **`/scrape/status` 的 `items[]`**：字段名与主统筹跟前端定死的那份逐字一致，
   `has_backup` 取 `item_list()` 的布尔位（不是 `emby_backup_json` 本体），
   `version_tags` 取 **media_item 行的 dict**；
6. **`/namemap/*`**：真 Store（走 S1 的 `name_map` 表）；
7. **读侧只加不改**：`/library`、`/downloads`、`/tasks`、`/detail` 的追加字段，
   以及 `/bootstrap` **不带** `downloader_offline`（它只挂 `/downloads`）。

宿主依赖（`app.sdk.*` / `app.schemas.types`）在本文件里装空壳；插件入口按文件路径独立加载，
合成包名与 `conftest.py` 保持一致，所以 `store` / `emby` 这些模块与其它单测共用同一份。
"""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
PKG_NAME = "avhelper_under_test"          # 与 conftest.py 同一个合成包名


# ---------------------------------------------------------------------------
# 加载插件入口（宿主空壳 + 合成包）
# ---------------------------------------------------------------------------


def _install_host_stubs() -> None:
    """补齐 `__init__.py` 需要的宿主符号（conftest 只装了 logging/network/config）。"""
    for name in ("app", "app.sdk", "app.schemas"):
        sys.modules.setdefault(name, types.ModuleType(name))
    if "app.sdk.logging" not in sys.modules:
        log = types.ModuleType("app.sdk.logging")

        class _Logger:
            def info(self, *args, **kwargs):
                pass

            error = warning = debug = info
        log.logger = _Logger()
        sys.modules["app.sdk.logging"] = log
    if "app.sdk.network" not in sys.modules:
        net = types.ModuleType("app.sdk.network")

        class _RequestUtils:
            def __init__(self, *args, **kwargs):
                pass

            @staticmethod
            def get(*args, **kwargs):
                return None

        net.RequestUtils = _RequestUtils
        net.SitesHelper = _RequestUtils
        sys.modules["app.sdk.network"] = net
    if "app.sdk.config" not in sys.modules:
        cfg = types.ModuleType("app.sdk.config")
        cfg.settings = types.SimpleNamespace(MP_DOMAIN=lambda url="": "")
        sys.modules["app.sdk.config"] = cfg
    plugin = types.ModuleType("app.sdk.plugin")
    class _PluginBase:
        """宿主插件基类的空壳：只要求 `get_data_path()` 存在。"""

        @staticmethod
        def get_data_path():
            return Path(".")

    plugin._PluginBase = _PluginBase
    sys.modules["app.sdk.plugin"] = plugin
    sched = types.ModuleType("app.sdk.scheduler")
    sched.add_plugin_once_job = lambda *a, **k: None
    sched.remove_plugin_once_job = lambda *a, **k: None
    sys.modules["app.sdk.scheduler"] = sched
    types_mod = types.ModuleType("app.schemas.types")

    class _MessageType:
        pass

    types_mod.MessageType = _MessageType
    sys.modules["app.schemas.types"] = types_mod


def _load_entry():
    """按文件路径加载插件入口 `__init__.py`（同名模块复用 `sys.modules` 里那一份）。"""
    _install_host_stubs()
    if PKG_NAME not in sys.modules:
        pkg = types.ModuleType(PKG_NAME)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PKG_NAME] = pkg
    key = f"{PKG_NAME}.__init__"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 夹具与替身
# ---------------------------------------------------------------------------


class FakeRequest:
    """FastAPI `Request` 的最小替身：处理器只用到 method/query_params/json/base_url。"""

    def __init__(self, body=None, method="POST", query=None, base_url="http://127.0.0.1:3001/"):
        self.method = method
        self._body = body
        self.query_params = dict(query or {})
        self.base_url = base_url

    async def json(self):
        if self._body is None:
            raise ValueError("没有请求体")
        return self._body


class FakeEngine:
    """`TaskEngine` 替身：只给读接口与「不要了」用到的那几个方法。"""

    def __init__(self, online=True, error="", boom=False, tasks=None, queue=None,
                 cancel_ok=True, cancel_boom=False):
        self.online = online
        self.error = error
        self.boom = boom
        self.tasks = list(tasks or [])
        self.queue_rows = list(queue or [])
        self.probed = 0
        self.cancel_ok = cancel_ok
        self.cancel_boom = cancel_boom
        self.cancel_calls = []
        self.task_cancel_calls = []

    def downloader_state(self):
        self.probed += 1
        if self.boom:
            raise RuntimeError("下载器探测炸了")
        return {"online": self.online, "error": "" if self.online else self.error,
                "checked_at": "2026-10-14 06:00:00"}

    def migrate_queue_to_ledger(self):
        return 0

    def site_options(self):
        return []

    def task_list(self, limit=50):
        return list(self.tasks)

    def queue(self, fresh=False):
        return list(self.queue_rows)

    def cancel_all(self, number_or_key, cancel_sub=True):
        if self.cancel_boom:
            raise RuntimeError("取消炸了")
        self.cancel_calls.append((number_or_key, cancel_sub))
        return {
            "ok": self.cancel_ok,
            "steps": {"torrent": {"ok": True, "detail": "已删种子"},
                      "ledger": {"ok": self.cancel_ok, "detail": "已从下载历史移除（hidden=1）"},
                      "sub": {"ok": True, "detail": "已删订阅" if cancel_sub else "按参数跳过"},
                      "known": {"ok": True, "detail": "已写入忽略表"}},
            "error": "" if self.cancel_ok else "ledger：没找到记录",
        }

    def cancel_task(self, tid):
        self.task_cancel_calls.append(tid)
        return {"ok": True, "message": f"已取消待确认任务 {tid}"}


class FakeEmbyLib:
    """`EmbyLibrary` 替身：`index()` 的键是归一化番号（与真实现同口径）。"""

    def __init__(self, index=None):
        self._index = dict(index or {})

    def ready(self):
        return bool(self._index)

    def index(self):
        return dict(self._index)

    def lookup(self, number):
        for key in (number, str(number or "").upper()):
            if key in self._index:
                return self._index[key]
        return None

    def invalidate(self):
        return None


class FakeClient:
    """javdb 客户端替身（本文件不碰子进程）。"""

    def last_error(self, key=""):
        return ""

    def cooldown_left(self, key=""):
        return 0


class FakeScraper:
    """`scraper` 模块替身：记录调用参数，返回可控结果。"""

    def __init__(self, preview=None, batch=None, rollback=None, view=None, sources=None):
        self.preview = preview if preview is not None else {
            "key": "SNOS380", "number": "SNOS-380",
            "fields": [{"name": "Overview", "current": "", "target": "中文简介", "changed": True}],
            "sources": {"javdb": "ok"}, "warnings": []}
        self.batch_rows = batch if batch is not None else [
            {"key": "SNOS380", "status": "ok", "changed": ["Overview"], "error": ""}]
        self.rollback = rollback if rollback is not None else {
            "ok": True, "item_key": "emby:12598", "restored": ["Overview"], "images": {}, "error": ""}
        self.view = view
        self.sources = sources if sources is not None else [
            {"source": "javdb", "status": "ok", "latency_ms": 1200, "error": ""}]
        self.calls = {"preview": [], "batch": [], "rollback": [], "view": [], "sources": 0}

    def preview_one(self, key, **kwargs):
        self.calls["preview"].append((key, kwargs))
        return dict(self.preview)

    def scrape_batch(self, keys, **kwargs):
        self.calls["batch"].append((list(keys), kwargs))
        return [dict(row) for row in self.batch_rows if isinstance(row, dict)]

    def rollback_item(self, item_key, **kwargs):
        self.calls["rollback"].append((item_key, kwargs))
        return dict(self.rollback)

    def film_view(self, key_or_number, item_key=None, store=None, library=None):
        self.calls["view"].append((key_or_number, item_key, store, library))
        if self.view is None:
            return {}
        return dict(self.view)

    def sources_selfcheck(self, store, cli, opts=None):
        self.calls["sources"] += 1
        return [dict(row) for row in self.sources]


class FakeTranslator:
    def __init__(self, ok=True, error="", latency=42, model=""):
        self.ok = ok
        self.error = error
        self.latency = latency
        self.model = model
        self.calls = []

    def selfcheck(self, model=""):
        self.calls.append(model)
        return {"ok": self.ok, "model": self.model or model, "latency_ms": self.latency,
                "error": self.error}


@pytest.fixture(scope="session")
def api_mod():
    """插件入口模块（`__init__.py`）。"""
    return _load_entry()


@pytest.fixture
def store(store_mod, tmp_path):
    """真 Store（临时库），v4 的五张表与迁移都在。"""
    instance = store_mod.Store(db_path=tmp_path / "avhelper.db")
    instance.init()
    return instance


@pytest.fixture
def plugin(api_mod, store):
    """一个不跑 `init_plugin()` 的插件实例：store/engine/Emby 全部直接注入。"""
    instance = api_mod.AVHelper()
    instance._enabled = True
    instance._proxy = ""
    instance._store = store
    instance._engine = FakeEngine()
    instance._emby_host = ""
    instance._emby_apikey = ""
    instance._emby_lib = FakeEmbyLib()
    instance._emby_sig = ("", "")
    instance._client = FakeClient()
    instance._view_cache = {}
    instance._film_cache = (0.0, {})
    instance._sources_cache = (0.0, [])
    return instance


def call(coro):
    """跑一个 async 处理器（不引入 pytest-asyncio 依赖）。"""
    return asyncio.run(coro)


def no_scraper(api_mod, monkeypatch):
    """把 `scraper` 摘掉（模拟 S7 还没落盘 / 导入失败）。"""
    monkeypatch.setattr(api_mod.AVHelper, "scrape_module", lambda self: None)


def with_scraper(api_mod, monkeypatch, fake):
    """换上假 scraper。"""
    monkeypatch.setattr(api_mod.AVHelper, "scrape_module", lambda self: fake)
    return fake


def no_translator(api_mod, monkeypatch):
    monkeypatch.setattr(api_mod.AVHelper, "translator_module", lambda self: None)


def with_translator(api_mod, monkeypatch, fake):
    monkeypatch.setattr(api_mod.AVHelper, "translator_module", lambda self: fake)
    return fake


def no_emby(api_mod, monkeypatch, plugin):
    """把 Emby 连接信息清空（`_emby_conn()` 两条路都取不到）。"""
    plugin._emby_host = ""
    plugin._emby_apikey = ""
    monkeypatch.setattr(api_mod.emby, "mp_emby_conf", lambda: ("", ""))
    return plugin


def use_emby(plugin, host="http://emby.invalid:8096", apikey="fake-apikey"):
    plugin._emby_host = host
    plugin._emby_apikey = apikey
    plugin._emby_client = None
    plugin._emby_client_sig = None
    return plugin


# ---------------------------------------------------------------------------
# A. 路由表
# ---------------------------------------------------------------------------

NEW_PATHS = ["/scrape/status", "/scrape/preview", "/scrape/run", "/scrape/rollback",
             "/scrape/log", "/scrape/selfcheck", "/namemap/actors", "/namemap/set",
             "/namemap/tags"]


class TestRouteTable:
    def test_nine_new_paths_are_registered(self, plugin):
        routes = {route["path"]: route for route in plugin.get_api()}
        missing = [path for path in NEW_PATHS if path not in routes]
        assert missing == []

    def test_new_paths_are_bear_authed(self, plugin):
        routes = {route["path"]: route for route in plugin.get_api()}
        for path in NEW_PATHS:
            assert routes[path].get("auth") == "bear", path

    def test_new_paths_have_summary_and_description(self, plugin):
        routes = {route["path"]: route for route in plugin.get_api()}
        for path in NEW_PATHS:
            assert str(routes[path].get("summary") or "").strip(), path

    def test_no_duplicate_path_and_method(self, plugin):
        seen = set()
        for route in plugin.get_api():
            for method in route.get("methods") or []:
                pair = (str(route.get("path")), str(method).upper())
                assert pair not in seen, pair
                seen.add(pair)

    def test_endpoints_are_callable(self, plugin):
        for route in plugin.get_api():
            assert callable(route.get("endpoint")), route.get("path")

    def test_img_stays_anonymous(self, plugin):
        routes = {route["path"]: route for route in plugin.get_api()}
        assert routes["/img"].get("allow_anonymous") is True
        assert routes["/img"].get("auth") in (None, "")

    def test_existing_read_paths_still_registered(self, plugin):
        routes = {route["path"] for route in plugin.get_api()}
        for path in ("/bootstrap", "/library", "/downloads", "/tasks", "/detail", "/img"):
            assert path in routes, path


# ---------------------------------------------------------------------------
# B. `/img`：老分支不动，新分支服务端回源
# ---------------------------------------------------------------------------


class TestImageProxy:
    def test_url_branch_unchanged(self, plugin, api_mod, monkeypatch):
        seen = {}

        def fake_fetch(url, proxy=""):
            seen["url"] = url
            seen["proxy"] = proxy
            return b"\xff\xd8\xff\xe0jpeg"

        monkeypatch.setattr(api_mod.imgproxy, "fetch", fake_fetch)
        response = plugin.api_img(url="https://tp.spfcas.com/x.jpg")
        assert response.status_code == 200
        assert response.body == b"\xff\xd8\xff\xe0jpeg"
        assert seen["url"] == "https://tp.spfcas.com/x.jpg"

    def test_emby_branch_uses_server_side_image(self, plugin, api_mod, monkeypatch):
        use_emby(plugin)
        seen = {}

        def fake_emby_image(host, apikey, item_id, img_type="Primary"):
            seen.update(host=host, apikey=apikey, item_id=item_id, img_type=img_type)
            return b"\xff\xd8\xff\xe0emby"

        monkeypatch.setattr(api_mod.imgproxy, "emby_image", fake_emby_image)
        response = plugin.api_img(emby="12598", type="Primary")
        assert response.status_code == 200
        assert response.body == b"\xff\xd8\xff\xe0emby"
        assert seen["item_id"] == "12598" and seen["img_type"] == "Primary"
        # 夹具里是假坐标（`tests/` 会随公开仓库发布，不写线上凭据）
        assert seen["host"] == "http://emby.invalid:8096" and seen["apikey"] == "fake-apikey"

    def test_emby_person_branch(self, plugin, api_mod, monkeypatch):
        use_emby(plugin)
        seen = {}
        monkeypatch.setattr(api_mod.imgproxy, "emby_image",
                            lambda host, apikey, item_id, img_type="Primary":
                            seen.update(item_id=item_id, img_type=img_type) or b"\xff\xd8\xff\xe0p")
        response = plugin.api_img(emby_person="10775")
        assert response.status_code == 200
        assert seen == {"item_id": "10775", "img_type": "Primary"}

    def test_emby_key_never_leaks_into_response(self, plugin, api_mod, monkeypatch):
        secret = "super-secret-apikey"
        use_emby(plugin, apikey=secret)
        monkeypatch.setattr(api_mod.imgproxy, "emby_image",
                            lambda host, apikey, item_id, img_type="Primary": b"\xff\xd8\xff\xe0x")
        response = plugin.api_img(emby="12598")
        assert secret not in str(dict(response.headers))
        assert secret.encode() not in response.body

    def test_emby_branch_without_config_is_404(self, plugin, api_mod, monkeypatch):
        no_emby(api_mod, monkeypatch, plugin)
        called = []
        monkeypatch.setattr(api_mod.imgproxy, "emby_image",
                            lambda *a, **k: called.append(a) or b"\xff\xd8\xff\xe0x")
        response = plugin.api_img(emby="12598")
        assert response.status_code == 404
        assert called == []

    def test_emby_image_url_helper_shape(self, plugin):
        assert plugin.emby_image_url("12598") == "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"
        assert plugin.emby_image_url("") == ""


# ---------------------------------------------------------------------------
# C. 依赖模块缺失即降级（绝不 import 期崩）
# ---------------------------------------------------------------------------


class TestScrapeNotReady:
    def test_preview_degrades(self, plugin, api_mod, monkeypatch):
        no_scraper(api_mod, monkeypatch)
        result = plugin.api_scrape_preview(key="SNOS-380")
        assert result["success"] is False
        assert result["message"] == "刮削模块未就绪"

    def test_run_degrades(self, plugin, api_mod, monkeypatch):
        no_scraper(api_mod, monkeypatch)
        result = call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"]})))
        assert result["success"] is False and result["ok"] is False
        assert result["message"] == "刮削模块未就绪"
        assert result["results"] == []

    def test_rollback_degrades(self, plugin, api_mod, monkeypatch):
        no_scraper(api_mod, monkeypatch)
        result = call(plugin.api_scrape_rollback(FakeRequest({"item_key": "emby:12598"})))
        assert result["success"] is False and result["ok"] is False
        assert result["error"] == "刮削模块未就绪"

    def test_selfcheck_degrades(self, plugin, api_mod, monkeypatch):
        no_translator(api_mod, monkeypatch)
        result = call(plugin.api_scrape_selfcheck(FakeRequest({})))
        assert result["success"] is False and result["ok"] is False
        assert result["error"] == "刮削模块未就绪"

    def test_status_and_log_still_work_without_scraper(self, plugin, api_mod, monkeypatch, store):
        """刮削模块缺位时，状态与日志端点照样出数（读的是本地表）。"""
        no_scraper(api_mod, monkeypatch)
        store.scrape_log_add("javdb", "ok", "SNOS380", 1200, "")
        assert plugin.api_scrape_status()["success"] is True
        assert plugin.api_scrape_log()["success"] is True


# ---------------------------------------------------------------------------
# D. `/scrape/run` 的闸门与 `/scrape/preview`
# ---------------------------------------------------------------------------


class TestScrapeRunGates:
    def test_all_without_confirm_is_refused(self, plugin, api_mod, monkeypatch, store):
        store.meta_upsert("SNOS380", display_number="SNOS-380")
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"all": True})))
        assert result["ok"] is False
        assert "confirm" in result["message"]
        assert fake.calls["batch"] == []            # 一个字节都没写

    def test_all_with_confirm_runs_every_meta_key(self, plugin, api_mod, monkeypatch, store):
        store.meta_upsert("SNOS380", display_number="SNOS-380")
        store.meta_upsert("IPZZ912", display_number="IPZZ-912")
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"all": True, "confirm": True})))
        assert result["ok"] is True
        keys = fake.calls["batch"][0][0]
        assert sorted(keys) == ["IPZZ912", "SNOS380"]

    def test_explicit_keys_are_used_as_is(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS-380", " ", "IPZZ912"]})))
        assert result["ok"] is True
        assert fake.calls["batch"][0][0] == ["SNOS-380", "IPZZ912"]

    def test_force_and_anchor_go_into_opts(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"], "force": True,
                                                "anchor": "center"})))
        opts = fake.calls["batch"][0][1]["opts"]
        assert opts["force"] is True and opts["anchor"] == "center"

    def test_results_are_normalized_to_contract_shape(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch,
                            FakeScraper(batch=[{"key": "", "extra": 1}, "垃圾"]))
        use_emby(plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"]})))
        assert result["results"] == [{"key": "", "extra": 1, "status": "", "changed": [],
                                      "error": ""}]

    def test_single_flight_guard(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        busy = api_mod.AVHelper._scrape_busy
        assert busy.acquire(blocking=False)
        try:
            result = call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"]})))
        finally:
            busy.release()
        assert result["ok"] is False and "进行中" in result["message"]
        assert fake.calls["batch"] == []

    def test_emby_not_configured_is_reported(self, plugin, api_mod, monkeypatch):
        with_scraper(api_mod, monkeypatch, FakeScraper())
        no_emby(api_mod, monkeypatch, plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"]})))
        assert result["ok"] is False and result["message"] == "Emby 未配置"

    def test_empty_keys_reports_nothing_to_do(self, plugin, api_mod, monkeypatch):
        with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"keys": []})))
        assert result["ok"] is True and result["results"] == []

    def test_run_invalidates_film_cache(self, plugin, api_mod, monkeypatch):
        with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        plugin._film_cache = (123456.0, {"meta": {"X": {}}})
        plugin._view_cache = {"X": (123456.0, {"key": "X"})}
        call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"]})))
        assert plugin._film_cache[1] == {} and plugin._view_cache == {}

    def test_batch_exception_is_reported_not_raised(self, plugin, api_mod, monkeypatch):
        fake = FakeScraper()

        def boom(keys, **kwargs):
            raise RuntimeError("站点全挂了")

        fake.scrape_batch = boom
        with_scraper(api_mod, monkeypatch, fake)
        use_emby(plugin)
        result = call(plugin.api_scrape_run(FakeRequest({"keys": ["SNOS380"]})))
        assert result["ok"] is False and "站点全挂了" in result["message"]


class TestScrapePreview:
    def test_preview_passes_dependency_bundle(self, plugin, api_mod, monkeypatch, store):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        result = plugin.api_scrape_preview(key="SNOS-380")
        assert result["success"] is True
        assert result["fields"][0]["name"] == "Overview"
        kwargs = fake.calls["preview"][0][1]
        assert set(kwargs) == {"store", "cli", "emby_client", "opts"}
        assert kwargs["emby_client"] is not None

    def test_preview_requires_key(self, plugin):
        assert plugin.api_scrape_preview(key="")["success"] is False

    def test_preview_without_emby_is_reported(self, plugin, api_mod, monkeypatch):
        with_scraper(api_mod, monkeypatch, FakeScraper())
        no_emby(api_mod, monkeypatch, plugin)
        result = plugin.api_scrape_preview(key="SNOS-380")
        assert result["success"] is False and result["message"] == "Emby 未配置"

    def test_preview_exception_is_swallowed(self, plugin, api_mod, monkeypatch):
        fake = FakeScraper()

        def boom(key, **kwargs):
            raise ValueError("取数炸了")

        fake.preview_one = boom
        with_scraper(api_mod, monkeypatch, fake)
        use_emby(plugin)
        result = plugin.api_scrape_preview(key="SNOS-380")
        assert result["success"] is False and "取数炸了" in result["message"]


class TestScrapeRollbackAndSelfcheck:
    def test_rollback_returns_restored(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        result = call(plugin.api_scrape_rollback(FakeRequest({"item_key": "emby:12598"})))
        assert result["ok"] is True and result["restored"] == ["Overview"]
        assert fake.calls["rollback"][0][0] == "emby:12598"

    def test_rollback_accepts_key_alias(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        call(plugin.api_scrape_rollback(FakeRequest({"key": "emby:1"})))
        assert fake.calls["rollback"][0][0] == "emby:1"

    def test_rollback_work_key_resolves_to_item_key(self, plugin, api_mod, monkeypatch, store):
        """工作台列表给的是**作品键**：回滚要先解析成 `emby:{id}` 实例键。"""
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("SNOS380", display_number="SNOS-380")
        store.item_upsert("emby:12598", "SNOS380", emby_id="12598", library_state="in_library")
        assert plugin._resolve_item_key("SNOS380") == "emby:12598"
        assert plugin._resolve_item_key("SNOS-380") == "emby:12598"
        assert plugin._resolve_item_key("emby:999") == "emby:999"
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        use_emby(plugin)
        call(plugin.api_scrape_rollback(FakeRequest({"key": "SNOS380"})))
        assert fake.calls["rollback"][0][0] == "emby:12598"

    def test_rollback_requires_item_key(self, plugin):
        result = call(plugin.api_scrape_rollback(FakeRequest({})))
        assert result["ok"] is False and "item_key" in result["error"]

    def test_selfcheck_uses_configured_model(self, plugin, api_mod, monkeypatch, store):
        fake = with_translator(api_mod, monkeypatch, FakeTranslator())
        result = call(plugin.api_scrape_selfcheck(FakeRequest({})))
        assert result["ok"] is True and result["latency_ms"] == 42
        assert fake.calls == ["hy3"]           # 默认模型（不读 LLM_MODEL）

    def test_selfcheck_model_override_from_global_rule(self, plugin, api_mod, monkeypatch, store):
        store.kv_set("global_rule", {"translateModel": "deepseek-v4.1-flash"})
        fake = with_translator(api_mod, monkeypatch, FakeTranslator())
        call(plugin.api_scrape_selfcheck(FakeRequest({})))
        assert fake.calls == ["deepseek-v4.1-flash"]

    def test_selfcheck_sources_branch_runs_deep_probe(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        result = call(plugin.api_scrape_selfcheck(FakeRequest({"sources": True})))
        assert fake.calls["sources"] == 1
        assert result["ok"] is True and result["sources"][0]["source"] == "javdb"

    def test_selfcheck_without_sources_never_probes_sites(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        with_translator(api_mod, monkeypatch, FakeTranslator())
        call(plugin.api_scrape_selfcheck(FakeRequest({})))
        assert fake.calls["sources"] == 0


# ---------------------------------------------------------------------------
# E. `/scrape/status`（含主统筹补充的 items[]）
# ---------------------------------------------------------------------------

ITEM_KEYS = {"key", "number", "title", "emby_id", "completeness", "scrape_state",
             "has_backup", "crop_anchor", "version_tags", "updated_at"}


class TestScrapeStatus:
    def test_stats_shape(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("SNOS380", display_number="SNOS-380", completeness="missing_plot")
        store.meta_upsert("IPZZ912", display_number="IPZZ-912", completeness="full")
        stats = plugin.api_scrape_status()["stats"]
        assert set(stats) == {"full", "missing_plot", "missing_core", "unscraped", "total"}
        assert stats["full"] == 1 and stats["missing_plot"] == 1
        assert stats["total"] == stats["full"] + stats["missing_plot"] + stats["missing_core"] \
            + stats["unscraped"]

    def test_items_fields_are_exactly_the_agreed_set(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("SNOS380", display_number="SNOS-380", title_zh="标题",
                          completeness="full")
        store.item_upsert("emby:12598", "SNOS380", emby_id="12598", library_state="in_library",
                          scrape_state="scraped_full", crop_anchor="right",
                          version_tags_json={"is_zh_sub": True, "is_uncensored_leak": True})
        items = plugin.api_scrape_status()["items"]
        assert len(items) == 1
        assert set(items[0]) == ITEM_KEYS
        assert items[0]["key"] == "SNOS380" and items[0]["emby_id"] == "12598"
        assert items[0]["version_tags"] == ["中字", "流出"]      # media_item 的 dict
        assert items[0]["scrape_state"] == "scraped_full"
        assert items[0]["crop_anchor"] == "right"

    def test_has_backup_is_the_boolean_gate(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("SNOS380", display_number="SNOS-380")
        store.item_upsert("emby:12598", "SNOS380", emby_id="12598", library_state="in_library")
        assert plugin.api_scrape_status()["items"][0]["has_backup"] is False
        assert store.item_backup_save("emby:12598", '{"Name": "原"}') is True
        plugin.film_cache_forget()
        assert plugin.api_scrape_status()["items"][0]["has_backup"] is True

    def test_filter_limit_offset(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("A1", display_number="A-1", completeness="full")
        store.meta_upsert("B1", display_number="B-1", completeness="missing_plot")
        store.meta_upsert("C1", display_number="C-1", completeness="missing_plot")
        assert len(plugin.api_scrape_status(filter="missing_plot")["items"]) == 2
        assert len(plugin.api_scrape_status(limit=2)["items"]) == 2
        assert len(plugin.api_scrape_status(limit=2, offset=2)["items"]) == 1

    def test_instance_without_meta_row_still_listed(self, plugin, api_mod, monkeypatch, store):
        """只有 media_item、没有 meta 行的条目也算一条（按 `missing_core` 计）。"""
        no_scraper(api_mod, monkeypatch)
        store.item_upsert("emby:1", "ORPHAN1", emby_id="1", display_number="ORPHAN-1")
        items = plugin.api_scrape_status()["items"]
        assert len(items) == 1
        assert items[0]["key"] == "ORPHAN1" and items[0]["completeness"] == "missing_core"
        assert items[0]["number"] == "ORPHAN-1"

    def test_queue_counts_due_items(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("SNOS380", display_number="SNOS-380",
                          next_retry_at="2020-01-01 00:00:00")
        queue = plugin.api_scrape_status()["queue"]
        assert queue["tier1"] == 1 and queue["tier2"] == 1

    def test_last_run_comes_from_scrape_log(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.scrape_log_add("javdb", "ok", "SNOS380", 1000, "")
        assert plugin.api_scrape_status()["last_run"]

    def test_sources_is_cheap_by_default(self, plugin, api_mod, monkeypatch):
        """`/scrape/status` 绝不能打站点：S7 的真探针只在 selfcheck 的 sources 分支跑。"""
        fake = with_scraper(api_mod, monkeypatch, FakeScraper())
        plugin.api_scrape_status()
        assert fake.calls["sources"] == 0

    def test_sources_falls_back_to_log_summary(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        store.scrape_log_add("javtxt", "timeout", "SNOS380", 30000, "读超时")
        sources = plugin.api_scrape_status()["sources"]
        assert sources and sources[0]["source"] == "javtxt"

    def test_summary_rows_carry_the_names_the_frontend_reads(self, plugin, api_mod,
                                                             monkeypatch, store):
        """S9 的 `ScrapeView.vue` 按 `status`/`latency_ms`/`error`/`checked_at` 读行。"""
        no_scraper(api_mod, monkeypatch)
        store.scrape_log_add("javtxt", "timeout", "SNOS380", 30000, "读超时")
        row = plugin.api_scrape_status()["sources"][0]
        for key in ("source", "status", "latency_ms", "error", "checked_at"):
            assert key in row, key
        assert row["status"] == "timeout" and row["error"] == "读超时"
        assert row["latency_ms"] == 30000 and row["checked_at"]
        # 原始汇总列名一个不删（诊断还用得上）
        assert {"total", "ok", "fail", "avg_latency_ms", "last_status", "last_error"} <= set(row)


class TestScrapeLog:
    def test_items_use_contract_keys(self, plugin, store):
        store.scrape_log_add("javdb", "ok", "SNOS380", 1200, "")
        result = plugin.api_scrape_log(limit=5)
        assert set(result["items"][0]) == {"source", "status", "key", "latency_ms", "error",
                                           "created_at"}
        assert result["items"][0]["source"] == "javdb"
        assert result["items"][0]["latency_ms"] == 1200
        assert "summary" in result

    def test_limit_is_clamped(self, plugin, store):
        for index in range(3):
            store.scrape_log_add("javdb", "ok", f"K{index}", 1, "")
        assert len(plugin.api_scrape_log(limit=2)["items"]) == 2


# ---------------------------------------------------------------------------
# F. `/namemap/*`
# ---------------------------------------------------------------------------


class TestNameMap:
    def test_set_then_list_actor(self, plugin, store):
        result = call(plugin.api_namemap_set(FakeRequest({"name": "三上悠亜", "zh": "三上悠亚"})))
        assert result["ok"] is True and result["canonical_id"]
        items = plugin.api_namemap_actors(q="三上")["items"]
        # 内置映射此时也已进库（见 TestNameMapReady），所以不能断言"只有 1 条"；
        # 用户写入的那条必须**存在**，且因为 source='user_custom' 排在前面。
        user = [row for row in items if row["source"] == "user_custom"]
        assert user and user[0]["zh"] == "三上悠亚"
        assert user[0] is items[0]
        assert set(items[0]) == {"canonical_id", "zh", "jp", "tw", "avatar", "aliases", "source"}

    def test_set_requires_name_and_zh(self, plugin):
        assert call(plugin.api_namemap_set(FakeRequest({"zh": "x"})))["ok"] is False
        assert call(plugin.api_namemap_set(FakeRequest({"name": "x"})))["ok"] is False

    def test_set_tag_entity_type(self, plugin, store):
        result = call(plugin.api_namemap_set(FakeRequest({"name": "中出", "zh": "内射",
                                                          "entity_type": "tag"})))
        assert result["ok"] is True
        items = plugin.api_namemap_tags(q="中出")["items"]
        assert set(items[0]) == {"canonical_id", "zh", "jp", "is_delete_rule"}
        assert any(row["zh"] == "内射" for row in items)

    def test_actors_and_tags_are_separated(self, plugin, store):
        call(plugin.api_namemap_set(FakeRequest({"name": "中出", "zh": "内射",
                                                 "entity_type": "tag"})))
        assert plugin.api_namemap_actors(q="中出")["items"] == []

    def test_store_failure_is_swallowed(self, plugin, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("库炸了")
        monkeypatch.setattr(plugin.store, "namemap_list", boom)
        assert plugin.api_namemap_actors()["items"] == []
        assert plugin.api_namemap_actors()["success"] is True


class TestNameMapReady:
    """S10 验收缺口：`namemap.load()` 必须在首次访问映射表时就跑过，且只跑一次。

    未 load 的症状是**静默**的：`ready()=False`、繁简转换原样返回、标签清洗不过滤删除规则、
    `/namemap/*` 只有 `actor_alias` 搬来的那几行、`/detail` 的演员中文名恒空。
    """

    def test_first_access_loads_and_syncs_then_stops(self, plugin, api_mod, monkeypatch, store):
        monkeypatch.setattr(api_mod, "_NAMEMAP_TRIED", False)
        nm = importlib.import_module(f"{PKG_NAME}.namemap")
        calls = []
        original = nm.load

        def counted(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(nm, "load", counted)
        items = plugin.api_namemap_actors(q="三上")["items"]
        assert items, "内置映射没进库 → /namemap/actors 会是空的"
        assert nm.ready() is True
        first = len(calls)
        # 首次访问会 load 一次（S3 的 `sync_store()` 内部也会 `load()` 一次，都是幂等的 0ms），
        # 关键是**之后不再 load**：这才是"别每次请求都 load"的判据。
        assert 1 <= first <= 2, f"首次访问 load 了 {first} 次"
        plugin.api_namemap_actors(q="三上")          # 第二次访问
        assert len(calls) == first                  # 不再 load
        assert len(store.namemap_list(entity_type="actor", limit=10)) == 10

    def test_ready_namemap_makes_detail_actors_chinese(self, plugin, api_mod, monkeypatch):
        monkeypatch.setattr(api_mod, "_NAMEMAP_TRIED", False)
        assert plugin.actor_zh("三上悠亜") == "三上悠亚"

    def test_tags_endpoint_prepares_names_too(self, plugin, api_mod, monkeypatch):
        monkeypatch.setattr(api_mod, "_NAMEMAP_TRIED", False)
        items = plugin.api_namemap_tags(q="中出")["items"]
        assert items, "内置标签映射没进库 → /namemap/tags 会是空的"

    def test_prepare_failure_only_warns_and_logs(self, plugin, store):
        class Boom:
            @staticmethod
            def load():
                raise RuntimeError("资源文件坏了")

            @staticmethod
            def sync_store(store):
                raise RuntimeError("灌库失败")

        assert plugin.prepare_namemap(Boom()) is False
        logged = store.scrape_log_recent(limit=5)
        assert any(str(row.get("source") or "") == "namemap" for row in logged)


# ---------------------------------------------------------------------------
# G. 读侧只加不改
# ---------------------------------------------------------------------------


def _lib_index():
    entry = {"id": "12598", "name": "SNOS-380 タイトル",
             "path": "/media/9kg/avi/SNOS-380.mp4", "url": "",
             "created": "2026-10-05T04:34:56.0000000Z"}
    # 真实现里同一部片在索引里有好几个键（归一化键 / 展示番号 / Name 里的写法）
    return {"SNOS380": entry, "SNOS-380": entry}


class TestLibraryReadSide:
    def test_rows_gain_film_fields_and_keep_old_ones(self, plugin, api_mod, monkeypatch):
        plugin._emby_lib = FakeEmbyLib(_lib_index())
        no_scraper(api_mod, monkeypatch)          # 走本地批量投影（S7 未就绪时的降级实现）
        result = plugin.api_library()
        row = result["items"][0]
        # 原有字段一个不少、语义不变
        for key in ("number", "title", "thumb", "lib", "actor", "addedAt"):
            assert key in row, key
        # 追加字段
        for key in ("key", "original_title", "actors", "cover", "version_tags", "states"):
            assert key in row, key
        assert row["cover"] == "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"
        assert row["states"]["library"] == "in_library"
        assert row["lib"]["id"] == "12598"

    def test_local_projection_uses_meta(self, plugin, api_mod, monkeypatch, store):
        plugin._emby_lib = FakeEmbyLib(_lib_index())
        no_scraper(api_mod, monkeypatch)
        store.meta_upsert("SNOS380", display_number="SNOS-380", title_zh="中文标题",
                          title_jp="日本語タイトル", plot_zh="简介",
                          actors_json=[{"zh": "上原", "jp": "上原亜衣", "avatar": "https://a/x.jpg"}],
                          completeness="full")
        row = plugin.api_library()["items"][0]
        assert row["key"] == "SNOS380"
        assert row["original_title"] == "日本語タイトル"
        assert row["actors"][0]["name"] == "上原" and row["actors"][0]["jp"] == "上原亜衣"
        assert row["version_tags"] == []
        assert row["states"]["scrape"] == "scraped_full"

    def test_film_view_scraper_path_is_used_when_available(self, plugin, api_mod, monkeypatch):
        plugin._emby_lib = FakeEmbyLib(_lib_index())
        view = {"key": "SNOS380", "number": "SNOS-380", "original_title": "JP",
                "actors": [{"name": "上原", "jp": "上原亜衣", "avatar": ""}],
                "cover": "/api/v1/plugin/AVHelper/img?url=x",
                "version_tags": ["中字"], "states": {"download": "none",
                                                     "library": "in_library",
                                                     "scrape": "scraped_full"}}
        fake = with_scraper(api_mod, monkeypatch, FakeScraper(view=view))
        row = plugin.api_library()["items"][0]
        assert fake.calls["view"], "应当走 scraper.film_view"
        assert row["version_tags"] == ["中字"]
        assert row["cover"] == "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"

    def test_film_views_are_cached_for_the_poll_window(self, plugin, api_mod, monkeypatch):
        fake = with_scraper(api_mod, monkeypatch, FakeScraper(view={"key": "A", "number": "A"}))
        plugin.film_views(["A", "A", "B"])
        first = len(fake.calls["view"])
        plugin.film_views(["A", "B"])
        assert first == 2
        assert len(fake.calls["view"]) == first        # 30 秒 TTL 内不再重算


class TestDownloadsReadSide:
    def _seed(self, store):
        store.download_upsert("SNOS-380", state="downloaded",
                              title="标题", actor="上原", size=1024, source="plugin",
                              thumb="https://tp.spfcas.com/a.jpg",
                              version_tags={"is_zh_sub": True})

    def test_rows_and_top_level_fields(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        self._seed(store)
        plugin._engine = FakeEngine(online=False, error="下载器连接失败")
        plugin._emby_lib = FakeEmbyLib(_lib_index())
        result = plugin.api_downloads(FakeRequest(method="GET"))
        row = result["items"][0]
        for key in ("display_number", "version_tags", "states", "key", "original_title",
                    "actors", "cover"):
            assert key in row, key
        assert row["display_number"] == "SNOS-380"
        assert row["version_tags"] == ["中字"]          # downloads 行那份是 JSON 串
        assert row["states"]["download"] == "completed"
        assert result["downloader_offline"] is True
        assert result["downloader_error"] == "下载器连接失败"

    def test_downloader_probe_failure_does_not_break_page(self, plugin, api_mod, monkeypatch,
                                                          store):
        no_scraper(api_mod, monkeypatch)
        self._seed(store)
        plugin._engine = FakeEngine(boom=True)
        result = plugin.api_downloads(FakeRequest(method="GET"))
        assert result["success"] is True and result["items"]
        assert result["downloader_offline"] is False

    def test_bootstrap_has_no_downloader_field(self, plugin, api_mod, monkeypatch, store):
        """`downloader_offline` 只挂 `/downloads`，不许挂 15 秒轮询的 `/bootstrap`。"""
        no_scraper(api_mod, monkeypatch)
        payload = plugin.api_bootstrap()
        assert "downloader_offline" not in payload
        assert "downloader_error" not in payload


class TestCancelLinkage:
    """「不要了」三出口联动（任务书 C）：`/tasks/cancel` 与 `DELETE /downloads`。

    口径（主统筹 2026-10-14 裁决）：`cancel_sub` **默认 false** —— 不带参数时**绝不**调
    `cancel_all()`，老按钮（「取消任务」「移除记录」）的语义一字不改；只有显式传
    `cancel_sub=true` 才走三出口联动并返回 `steps`。
    """

    def test_tasks_cancel_default_does_not_call_cancel_all(self, plugin):
        """带番号但不带 `cancel_sub` → 老行为：不联动（`cancel_all` 调用次数 0）。"""
        plugin._engine = FakeEngine()
        result = call(plugin.api_task_cancel(FakeRequest({"number": "SNOS-380"})))
        assert plugin._engine.cancel_calls == []
        assert plugin._engine.task_cancel_calls == []
        assert result["success"] is False and "cancel_sub=true" in result["message"]

    def test_tasks_cancel_by_number_with_cancel_sub_true(self, plugin):
        plugin._engine = FakeEngine()
        result = call(plugin.api_task_cancel(FakeRequest({"number": "SNOS-380",
                                                          "cancel_sub": True})))
        assert plugin._engine.cancel_calls == [("SNOS-380", True)]
        assert plugin._engine.task_cancel_calls == []
        assert result["success"] is True
        assert result["steps"]["ledger"]["detail"].startswith("已从下载历史移除")

    def test_tasks_cancel_accepts_key_alias(self, plugin):
        plugin._engine = FakeEngine()
        call(plugin.api_task_cancel(FakeRequest({"key": "SNOS380", "cancel_sub": True})))
        assert plugin._engine.cancel_calls == [("SNOS380", True)]

    def test_tasks_cancel_number_plus_id_keeps_old_path_by_default(self, plugin):
        """老界面同时带 id 与 number 也不许联动（默认 false），只按 id 取消待确认任务。"""
        plugin._engine = FakeEngine()
        result = call(plugin.api_task_cancel(FakeRequest({"id": "t1", "number": "SNOS-380"})))
        assert plugin._engine.cancel_calls == []
        assert plugin._engine.task_cancel_calls == ["t1"]
        assert set(result) == {"success", "message", "tasks", "queue"}

    def test_tasks_cancel_cancel_sub_false_from_body(self, plugin):
        plugin._engine = FakeEngine()
        call(plugin.api_task_cancel(FakeRequest({"number": "SNOS-380", "cancel_sub": False})))
        assert plugin._engine.cancel_calls == []

    def test_tasks_cancel_cancel_sub_true_from_query_string(self, plugin):
        plugin._engine = FakeEngine()
        call(plugin.api_task_cancel(FakeRequest({"number": "SNOS-380"},
                                                query={"cancel_sub": "true"})))
        assert plugin._engine.cancel_calls == [("SNOS-380", True)]

    def test_tasks_cancel_body_beats_query_string(self, plugin):
        plugin._engine = FakeEngine()
        call(plugin.api_task_cancel(FakeRequest({"number": "SNOS-380", "cancel_sub": False},
                                                query={"cancel_sub": "true"})))
        assert plugin._engine.cancel_calls == []

    def test_tasks_cancel_by_id_keeps_old_behaviour(self, plugin):
        """老界面只发 `{id}`：走 `cancel_task()`，不碰下载器与订阅、返回形状不变。"""
        plugin._engine = FakeEngine()
        result = call(plugin.api_task_cancel(FakeRequest({"id": "t1"})))
        assert plugin._engine.task_cancel_calls == ["t1"]
        assert plugin._engine.cancel_calls == []
        assert result["success"] is True and "steps" not in result
        assert set(result) == {"success", "message", "tasks", "queue"}

    def test_tasks_cancel_without_target_is_refused(self, plugin):
        plugin._engine = FakeEngine()
        result = call(plugin.api_task_cancel(FakeRequest({})))
        assert result["success"] is False and "缺少" in result["message"]

    def test_tasks_cancel_failure_is_reported_per_step(self, plugin):
        plugin._engine = FakeEngine(cancel_ok=False)
        result = call(plugin.api_task_cancel(FakeRequest({"number": "SNOS-380",
                                                          "cancel_sub": True})))
        assert result["success"] is False and "未完成" in result["message"]
        assert result["steps"]["ledger"]["ok"] is False

    def test_downloads_delete_default_only_tombstones(self, plugin, api_mod, monkeypatch, store):
        """不带 `cancel_sub` = 老行为：只打台账墓碑，不碰种子/订阅/known。"""
        no_scraper(api_mod, monkeypatch)
        store.download_upsert("SNOS-380", state="downloaded", source="plugin")
        plugin._engine = FakeEngine()
        result = plugin.api_downloads(FakeRequest(method="DELETE", query={"key": "SNOS-380"}))
        assert plugin._engine.cancel_calls == []
        assert result["success"] is True and result["message"] == "已移除记录"
        assert result["steps"] == {}
        assert "SNOS380" not in (store.download_map() or {})

    def test_downloads_delete_with_cancel_sub_true_delegates(self, plugin, api_mod, monkeypatch,
                                                             store):
        no_scraper(api_mod, monkeypatch)
        store.download_upsert("SNOS-380", state="downloaded", source="plugin")
        plugin._engine = FakeEngine()
        result = plugin.api_downloads(FakeRequest(method="DELETE",
                                                  query={"key": "SNOS-380", "cancel_sub": "true"}))
        assert plugin._engine.cancel_calls == [("SNOS-380", True)]
        assert set(result["steps"]) == {"torrent", "ledger", "sub", "known"}
        assert {"success", "items", "counts", "message"} <= set(result)

    def test_downloads_delete_cancel_sub_false(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        plugin._engine = FakeEngine()
        plugin.api_downloads(FakeRequest(method="DELETE",
                                         query={"key": "SNOS-380", "cancel_sub": "false"}))
        assert plugin._engine.cancel_calls == []

    def test_downloads_delete_without_key_keeps_old_shape(self, plugin, api_mod, monkeypatch):
        no_scraper(api_mod, monkeypatch)
        plugin._engine = FakeEngine()
        result = plugin.api_downloads(FakeRequest(method="DELETE"))
        assert result["success"] is False and result["message"] == "缺少 key"

    def test_downloads_delete_falls_back_when_engine_is_broken(self, plugin, api_mod,
                                                               monkeypatch, store):
        """联动那一步炸了也要保住老行为：接口不挂、记录照样移除。"""
        no_scraper(api_mod, monkeypatch)
        store.download_upsert("SNOS-380", state="downloaded", source="plugin")
        plugin._engine = FakeEngine(cancel_boom=True)
        assert "SNOS380" in (store.download_map() or {})
        result = plugin.api_downloads(FakeRequest(method="DELETE",
                                                  query={"key": "SNOS-380", "cancel_sub": "true"}))
        assert result["success"] is True
        assert result["steps"] == {}
        assert result["message"] == "已移除记录（清种子/订阅失败）"
        assert "SNOS380" not in (store.download_map() or {})      # 墓碑生效，行不再可见


class TestTasksAndDetail:
    def test_tasks_rows_gain_poster(self, plugin, api_mod, monkeypatch, store):
        no_scraper(api_mod, monkeypatch)
        plugin._emby_lib = FakeEmbyLib(_lib_index())
        plugin._engine = FakeEngine(
            tasks=[{"id": "t1", "number": "SNOS-380", "thumb": "/old-thumb"}],
            queue=[{"number": "OTHER-1", "thumb": "/queue-thumb"}],
        )
        store.meta_upsert("SNOS380", display_number="SNOS-380", completeness="full")
        store.item_upsert("emby:12598", "SNOS380", emby_id="12598", library_state="in_library")
        result = plugin.api_tasks()
        task = result["tasks"][0]
        assert task["poster"] == "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"
        assert task["thumb"] == "/old-thumb"          # 原字段不动
        assert result["queue"][0]["poster"] == "/queue-thumb"

    def test_detail_appends_emby_fields(self, plugin, api_mod, monkeypatch):
        plugin._emby_lib = FakeEmbyLib(_lib_index())
        monkeypatch.setattr(api_mod.AVHelper, "_detail_pair",
                            lambda self, number, mid="": ({"number": number, "title": "日文",
                                                           "cover_url": "https://c/x.jpg",
                                                           "actors": [{"name": "上原亜衣"}]}, None))
        plugin.actor_zh = lambda name: "上原"       # 不依赖映射表资源
        result = plugin.api_detail("SNOS-380")
        assert result["success"] is True
        assert result["emby_id"] == "12598"
        assert result["cover"] == "/api/v1/plugin/AVHelper/img?emby=12598&type=Primary"
        assert result["actors"][0]["zh"] == "上原"
        # 原有字段语义不变
        assert result["movie"]["cover"].startswith("/api/v1/plugin/AVHelper/img?url=")
        assert result["movie"]["number"] == "SNOS-380"

    def test_detail_without_library_keeps_shape(self, plugin, api_mod, monkeypatch):
        plugin._emby_lib = FakeEmbyLib()
        monkeypatch.setattr(api_mod.AVHelper, "_detail_pair",
                            lambda self, number, mid="": ({"number": number, "title": "日文"}, None))
        result = plugin.api_detail("SNOS-380")
        assert result["success"] is True
        assert "emby_id" not in result and "cover" not in result


# ---------------------------------------------------------------------------
# H. 配置口径（存 kv 的 global_rule，不落宿主配置）
# ---------------------------------------------------------------------------


class TestScrapeConf:
    def test_defaults_when_rule_is_empty(self, plugin, store):
        conf = plugin.scrape_conf()
        assert conf == {
            "scrapeMode": "fill", "plotJavtxt": True, "plotMetatube": True,
            "translateModel": "hy3", "translateModelFallback": "deepseek-v4.1-flash",
            "cropAnchor": "auto", "trailerMode": "off",
            "autoScrapeTier1": True, "autoScrapeTier2": True,
            "cleanSuffixes": [], "nameTemplate": "{number}{badge} {title}",
        }

    def test_camel_case_keys_are_read(self, plugin, store):
        store.kv_set("global_rule", {"scrapeMode": "hybrid", "plotJavtxt": False,
                                     "cropAnchor": "right", "trailerMode": "local",
                                     "translateModel": "hy3-pro", "cleanSuffixes": ["-UC", " "],
                                     "nameTemplate": "{number}"})
        conf = plugin.scrape_conf()
        assert conf["scrapeMode"] == "hybrid" and conf["plotJavtxt"] is False
        assert conf["cropAnchor"] == "right" and conf["trailerMode"] == "local"
        assert conf["translateModel"] == "hy3-pro"
        assert conf["cleanSuffixes"] == ["-UC"]

    def test_bad_values_fall_back_without_raising(self, plugin, store):
        store.kv_set("global_rule", {"scrapeMode": "随便", "cropAnchor": 7, "trailerMode": None,
                                     "plotMetatube": "false", "cleanSuffixes": "不是数组"})
        conf = plugin.scrape_conf()
        assert conf["scrapeMode"] == "fill" and conf["cropAnchor"] == "auto"
        assert conf["trailerMode"] == "off"
        assert conf["plotMetatube"] is False
        assert conf["cleanSuffixes"] == []

    def test_scrape_opts_carries_proxy(self, plugin):
        # 假坐标：`tests/` 会随公开仓库发布，不写真实内网地址
        plugin._proxy = "http://proxy.invalid:7890"
        assert plugin.scrape_opts()["proxy"] == "http://proxy.invalid:7890"

    def test_scrape_deps_keywords(self, plugin, api_mod, monkeypatch):
        use_emby(plugin)
        deps = plugin.scrape_deps()
        assert set(deps) == {"store", "cli", "emby_client", "opts"}

    def test_emby_client_is_none_without_config(self, plugin, api_mod, monkeypatch):
        no_emby(api_mod, monkeypatch, plugin)
        assert plugin.emby_client() is None
        assert plugin.scrape_deps()["emby_client"] is None

    def test_emby_client_is_cached_until_connection_changes(self, plugin, api_mod):
        use_emby(plugin)
        first = plugin.emby_client()
        assert first is not None
        assert plugin.emby_client() is first
        use_emby(plugin, host="http://other:8096")
        assert plugin.emby_client() is not first


class _FakeEmbyWrite:
    """`EmbyClient`（写侧）的最小替身：preview 只用到读方法。"""

    def __init__(self, dto=None):
        self.dto = dict(dto or {})
        self.reads = []
        self.writes = []

    def ready(self):
        return True

    def get_item(self, item_id, user_id=""):
        self.reads.append(str(item_id))
        return dict(self.dto)


class TestPreviewLocateByNumber:
    """S10 试点批抓到的**阻塞级**缺口：`meta`/`media_item` 都空时，按番号也要能定位到 Emby 条目。

    根因是 `AVHelper.scrape_opts()` 从来没给过 `opts['library']`，于是
    `scraper.locate_items()` 的第四条兜底（Emby 内存索引 `lookup()`）在 REST 路径上是死代码：
    `/scrape/preview?key=SNOS380` 回 `items: []`、`/scrape/run` 十条全 `找不到该番号对应的 Emby 条目`。
    """

    @staticmethod
    def _wire_library(plugin):
        """把假 Emby 索引挂成"已配置 Emby"的样子（`_emby_sig` 必须与 `_emby_conn()` 一致）。"""
        use_emby(plugin)
        fake = FakeEmbyLib(_lib_index())
        plugin._emby_lib = fake
        plugin._emby_sig = ("http://emby.invalid:8096", "fake-apikey")
        return fake

    def test_scrape_opts_carries_the_emby_library(self, plugin):
        fake = self._wire_library(plugin)
        assert plugin.scrape_opts()["library"] is fake
        assert plugin.scrape_deps()["opts"]["library"] is fake

    def test_library_is_none_without_emby(self, plugin, api_mod, monkeypatch):
        no_emby(api_mod, monkeypatch, plugin)
        opts = plugin.scrape_opts()
        assert "library" in opts and opts["library"] is None
        assert plugin.scrape_deps()["opts"]["library"] is None

    def test_number_lookup_falls_back_to_emby_index(self, plugin, store):
        """`meta`/`media_item` 全空 → 靠 `opts['library']` 的 `lookup()` 定位。"""
        scraper = importlib.import_module(f"{PKG_NAME}.scraper")
        self._wire_library(plugin)
        assert store.meta_list() == [] and store.item_list() == []
        opts = plugin.scrape_opts()
        assert scraper.locate_items(store, "SNOS380", "SNOS-380", opts, "") == \
            [("emby:12598", "12598")]
        assert scraper.locate_item(store, "SNOS380", "SNOS-380", opts, "") == ("emby:12598", "12598")

    def test_library_none_degrades_without_raising(self, plugin, store):
        scraper = importlib.import_module(f"{PKG_NAME}.scraper")
        assert scraper.locate_items(store, "SNOS380", "SNOS-380", {"library": None}, "") == []
        assert scraper.locate_items(store, "SNOS380", "SNOS-380", {}, "") == []

    def test_preview_yields_items_and_current_by_number(self, plugin, store, monkeypatch):
        """端到端：真 `scraper.preview_one()` + 假 Emby，**零网络**（`fetch_cache` + `cache_only`）。"""
        scraper = importlib.import_module(f"{PKG_NAME}.scraper")
        self._wire_library(plugin)
        cache = {"numbers": {"SNOS380": {
            "display": "SNOS-380",
            "javdb": {"ok": True, "detail": {
                "id": "96GB0p", "number": "SNOS-380", "title": "日文原标题",
                "origin_title": "日文原标题", "release_date": "2026-09-01", "duration": 120,
                "score": "4.33", "maker_name": "S1 NO.1 STYLE",
                "actors": [{"id": "1", "name": "演员甲"}],
                "tags": [{"id": "t1", "name": "中出"}],
                "cover_url": "https://c0.jdbstatic.com/covers/96/96GB0p.jpg"}},
            "javtxt": {"hit": True, "title_zh": "中文标题", "title_jp": "日文原标题",
                       "plot_zh": "中文简介", "plot_jp": "", "zh_is_machine": True,
                       "actors": []},
        }}}
        opts = dict(plugin.scrape_opts())
        # `fetch_cache` 要的是**已展开的 dict**（`scraper.cache_row()` 直接按 key 查），
        # 不是文件路径；配上 `cache_only=True` 就是"零网络"的 dry-run 语义。
        opts.update({"fetch_cache": cache, "cache_only": True, "translate": False,
                     "log_sources": False})

        def no_network(*args, **kwargs):
            raise AssertionError("preview 不该联网")

        def no_subprocess(*args, **kwargs):
            raise AssertionError("preview 不该起子进程")

        monkeypatch.setattr(scraper, "http_get", no_network)
        monkeypatch.setattr(scraper, "_run_cli", no_subprocess)
        emby_client = _FakeEmbyWrite({"Id": "12598", "Name": "SNOS-380",
                                      "Path": "/media/9kg/avi/SNOS-380.mp4",
                                      "ProviderIds": {"MetaTube": "JavBus:SNOS-380"}})
        result = scraper.preview_one("SNOS380", store=store, cli=FakeClient(),
                                     emby_client=emby_client, opts=opts)
        assert result["items"] == [{"item_key": "emby:12598", "emby_id": "12598"}]
        assert result["item_key"] == "emby:12598" and result["emby_id"] == "12598"
        assert not any("没有找到对应的 Emby 条目" in str(w) for w in result["warnings"])
        assert result["sources"]["javdb"]["status"] == "cache"      # 骨架来自缓存，没打站点
        assert emby_client.reads == ["12598"]          # 真的拿 DTO 去比对了 current
        fields = {row["name"]: row for row in result["fields"]}
        assert fields["Name"]["current"] == "SNOS-380"
        assert str(fields["Name"]["target"]).startswith("SNOS-380")
        assert fields["Name"]["changed"] is True


# ---------------------------------------------------------------------------
# I. `tasks._scrape_tick()` 的接线（S8 只改方法体）
# ---------------------------------------------------------------------------


class _TickPlugin:
    """`_scrape_tick` 需要的插件替身（配置 + 依赖 + 模块加载器）。"""

    def __init__(self, conf=None, scraper=None, deps=None, boom=None):
        self._conf = conf if conf is not None else {}
        self._scraper = scraper
        self._deps = deps if deps is not None else {"store": None, "cli": None,
                                                    "emby_client": None, "opts": {}}
        self.boom = boom
        self.calls = []

    def scrape_conf(self):
        conf = {"scrapeMode": "fill", "autoScrapeTier1": True, "autoScrapeTier2": True}
        conf.update(self._conf)
        return conf

    def scrape_module(self):
        return self._scraper

    def scrape_deps(self):
        return dict(self._deps)


class _TickScraper:
    def __init__(self):
        self.calls = []

    def scrape_batch(self, keys, **kwargs):
        self.calls.append((list(keys), kwargs))
        return [{"key": keys[0], "status": "ok", "changed": [], "error": ""}]


class TestScrapeTick:
    def test_scrape_mode_off_skips_everything(self, tasks_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        store.meta_upsert("SNOS380", display_number="SNOS-380", next_retry_at="2020-01-01 00:00:00")
        engine = tasks_mod.TaskEngine(
            _TickPlugin(conf={"scrapeMode": "off"}, scraper=_TickScraper()), store, None, None)
        result = engine._scrape_tick()
        assert result == {"tier1": 0, "tier2": 0, "scraper": False, "error": ""}

    def test_tier_limits_are_five_and_three(self, tasks_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        # K0..K4：Tier1 到点（Tier1 取 5 条）；K5..K7：没到点但最久没刮（Tier2 取 3 条）
        for index in range(5):
            store.meta_upsert(f"K{index}", display_number=f"K-{index:03d}",
                              next_retry_at=f"2020-01-01 00:00:0{index}",
                              last_scraped_at="2026-01-01 00:00:00")
        for index in range(5, 8):
            store.meta_upsert(f"K{index}", display_number=f"K-{index:03d}",
                              next_retry_at="", last_scraped_at="")
        scraper = _TickScraper()
        engine = tasks_mod.TaskEngine(_TickPlugin(scraper=scraper), store, None, None)
        result = engine._scrape_tick()
        assert result["scraper"] is True
        assert result["tier1"] == 5 and result["tier2"] == 3
        assert len(scraper.calls) == 8                      # 8 条互不重复，逐条独立调用
        assert scraper.calls[0][0] == ["K0"]

    def test_dependency_bundle_is_passed_through(self, tasks_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        store.meta_upsert("SNOS380", display_number="SNOS-380", next_retry_at="2020-01-01 00:00:00")
        scflags = {"store": store, "cli": "C", "emby_client": "E", "opts": {"a": 1}}
        scraper = _TickScraper()
        engine = tasks_mod.TaskEngine(_TickPlugin(scraper=scraper, deps=scflags), store, None, None)
        engine._scrape_tick()
        assert scraper.calls[0][1] == scflags

    def test_single_failure_is_logged_and_never_raised(self, tasks_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        store.meta_upsert("SNOS380", display_number="SNOS-380", next_retry_at="2020-01-01 00:00:00")

        class Boom:
            def scrape_batch(self, keys, **kwargs):
                raise RuntimeError("单条炸了")

        engine = tasks_mod.TaskEngine(_TickPlugin(scraper=Boom()), store, None, None)
        result = engine._scrape_tick()
        assert result["scraper"] is True and "失败" in result["error"]
        logged = store.scrape_log_recent(limit=5)
        assert any(row.get("source") == "scrape_tick" for row in logged)

    def test_scraper_missing_keeps_old_shape(self, tasks_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        store.meta_upsert("SNOS380", display_number="SNOS-380", next_retry_at="2020-01-01 00:00:00")
        engine = tasks_mod.TaskEngine(_TickPlugin(scraper=None), store, None, None)
        result = engine._scrape_tick()
        assert result["scraper"] is False and result["error"] == "scraper 未落地"
        assert result["tier1"] == 1

    def test_tier_switches_are_honoured(self, tasks_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        store.meta_upsert("SNOS380", display_number="SNOS-380", next_retry_at="2020-01-01 00:00:00")
        engine = tasks_mod.TaskEngine(
            _TickPlugin(conf={"autoScrapeTier1": False}, scraper=_TickScraper()), store, None, None)
        result = engine._scrape_tick()
        assert result["tier1"] == 0
        assert result["tier2"] == 1        # Tier2 仍然跑
