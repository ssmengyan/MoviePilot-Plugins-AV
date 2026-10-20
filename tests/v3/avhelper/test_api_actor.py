"""`__init__.py` 的演员子系统对外面单测（0.9.0 · S4）。

覆盖任务书 S4 的七条验收：

1. **路由表**：7 条新端点都在 `get_api()` 里、全部 `auth:"bear"`，且**下标都排在
   `/actor` / `/actors` 之前**；路径里没有 `{}` 路径参数 —— 宿主的 `/actor` 会把
   `/actor/xxx` 前缀吃掉，所以 `/actor/list` 与 `/actor` 必须**精确相等**地各占一条；
2. **`/actor/scrape` 的 `dry_run` 缺省 True**（与 `/scrape/avatars` 同一口径）；
3. **`actor_opts()`**：6 个键的默认值 + 越界夹取（batch 999→200、interval -1→0），
   并且**只读不写**（调用它不会往 kv 里落任何东西）；
4. **`get_service()`** 里有 `actorsync` 条目，`trigger/kwargs/func` 形状正确；
5. **`job_actor_sync()`**：`actorAutoSync=False` → 返回 0 且**不**调 `queue_tick`；
   依赖模块缺失、`queue_tick` 抛异常都不外抛（定时任务不能把宿主 scheduler 带停）；
6. **端点异常路径**一律 `{success:false}`（不 500、不抛）；依赖缺失回「演员子系统未就绪」；
7. **`/scrape/avatars` 原样保留**（路径与处理函数都还在）。

依赖全部是假对象：`store` 用 `FakeStore`（只实现 kv + `actor_*` 四件套），
`actor_sync` / `actor_sources` 用带记录的假模块注入 —— **不联网、不碰真库**。
"""

import asyncio
import importlib.util
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
    """FastAPI `Request` 的最小替身：处理器只用到 method/query_params/json。"""

    def __init__(self, body=None, method="POST"):
        self.method = method
        self._body = body
        self.query_params: dict = {}
        self.headers: dict = {}

    async def json(self):
        if self._body is None:
            raise ValueError("没有请求体")
        return self._body


class FakeStore:
    """演员子系统用到的那几个方法的假 store（**不碰 SQLite**）。"""

    def __init__(self, rule=None, rows=None, person_row=None, boom=(), meta=None, logs=None):
        self.rule = dict(rule or {})
        self.rows = list(rows if rows is not None else [
            {"id": 7, "person": "河北彩花", "name": "河北彩花", "locked_fields": [],
             "images": [{"url": "http://img.invalid/a.jpg", "source": "gfriends"},
                        {"url": "http://img.invalid/b.jpg", "source": "javdb"}]},
            {"id": 8, "person": "深田えいみ", "name": "深田えいみ", "images": [],
             "locked_fields": []},
        ])
        self.person_row = person_row if person_row is not None else {
            "id": 7, "person": "河北彩花", "name": "河北彩花", "zh": "河北彩花", "jp": "",
            "images": [{"url": "http://img.invalid/a.jpg", "source": "gfriends"},
                       {"url": "http://img.invalid/b.jpg", "source": "javdb"}],
            "locked_fields": [], "last_scraped_at": "2026-10-20 03:00:00", "retry_count": 0,
        }
        # `meta` 只给 actors（`_meta_row` 的解析副本）与番号两列，够 `actor_numbers()` 用
        self.meta = list(meta if meta is not None else [
            {"key": "SSIS001", "display_number": "SSIS-001", "title_zh": "第一部",
             "actors": [{"name": "河北彩花"}]},
            {"key": "SSIS002", "display_number": "SSIS-002", "title_zh": "第二部",
             "actors": [{"name": "深田えいみ"}]},
            {"key": "SSIS003", "display_number": "", "title_zh": "",
             "actors": [{"name": "河北彩花"}]},
        ])
        self.logs = list(logs if logs is not None else [
            {"key": "河北彩花", "status": "ok", "reason": "",
             "created_at": "2026-10-20 03:00:00", "error_summary": ""},
            {"key": "深田えいみ", "status": "skipped", "reason": "no_avatar",
             "created_at": "2026-10-20 03:01:00", "error_summary": ""},
            {"key": "河北彩花", "status": "skipped", "reason": "has_image",
             "created_at": "2026-10-20 03:02:00", "error_summary": ""},
        ])
        self.boom = set(boom)
        self.calls = []
        self.kv_writes = []
        self.init_calls = 0
        self.backfill_calls = []
        self.backfill_result = {"created": 3, "updated": 1, "total": 4, "skipped": False}

    def init(self):
        """启动路径会调 `store.init()`（迁移）；假 store 只记次数。"""
        self.init_calls += 1

    def cache_all(self, limit=0):
        return []

    # --- kv（`global_rule`）---
    def kv_get(self, key, default=None):
        return dict(self.rule) if key == "global_rule" else default

    def kv_set(self, key, val, ttl=0):
        self.kv_writes.append((key, dict(val or {}) if isinstance(val, dict) else val))
        if key == "global_rule":
            self.rule = dict(val or {})

    # --- S1 的 actor_* 四件套 ---
    def actor_list(self, q="", flt="", limit=60, offset=0):
        if "actor_list" in self.boom:
            raise RuntimeError("库挂了")
        self.calls.append(("actor_list", q, flt, limit, offset))
        return {"items": self.rows[offset:offset + limit], "total": len(self.rows)}

    def actor_get(self, actor_id=0, person=""):
        if "actor_get" in self.boom:
            raise RuntimeError("库挂了")
        self.calls.append(("actor_get", actor_id, person))
        return dict(self.person_row) if int(actor_id or 0) == int(self.person_row["id"]) else None

    def actor_stats(self):
        if "actor_stats" in self.boom:
            raise RuntimeError("库挂了")
        return {"total": len(self.rows), "missing_avatar": 0, "locked": 0}

    def actor_lock(self, actor_id, field="images", on=True):
        if "actor_lock" in self.boom:
            raise RuntimeError("库挂了")
        self.calls.append(("actor_lock", actor_id, field, on))
        if int(actor_id or 0) != int(self.person_row["id"]):
            return {}
        row = dict(self.person_row)
        row["locked_fields"] = [field] if on else []
        return row

    # --- 存量回填（启动路径）---
    def actor_backfill(self, actors=None, namemap_mod=None):
        self.backfill_calls.append({"actors": actors, "namemap_mod": namemap_mod})
        if "actor_backfill" in self.boom:
            raise RuntimeError("回填炸了")
        return dict(self.backfill_result)

    # --- 作品史与日志（`/actor/detail` 用）---
    def meta_list(self, limit=0, offset=0, **filters):
        if "meta_list" in self.boom:
            raise RuntimeError("库挂了")
        return [dict(row) for row in self.meta]

    def scrape_log_recent(self, limit=50, source_name=""):
        if "scrape_log_recent" in self.boom:
            raise RuntimeError("库挂了")
        self.calls.append(("scrape_log_recent", limit, source_name))
        return [dict(row) for row in self.logs][:int(limit or 50)]


class FakeActorSync:
    """S3 `actor_sync` 的假模块：记录调用参数，结果可控，能按需抛异常。"""

    def __init__(self, scrape=None, tick=None, crop=None, boom=False):
        self.scrape = scrape if scrape is not None else {
            "ok": True, "dry_run": True,
            "counts": {"total": 1, "uploaded": 0, "skipped": 1, "failed": 0, "no_avatar": 0,
                       "person_missing": 0, "has_image": 1, "locked": 0, "index_stale": 0},
            "items": [{"actor_id": 7, "person": "河北彩花", "name": "河北彩花",
                       "action": "skip", "reason": "has_image", "url": "", "source": "gfriends",
                       "bytes": 0, "w": 0, "h": 0}],
            "errors": [],
        }
        # S3 `queue_tick()` 落地的形状：`popped` + `counts['total']`，没有 processed/count
        self.tick = tick if tick is not None else {"ok": True, "popped": 3,
                                                   "counts": {"total": 3}}
        self.crop = crop if crop is not None else {"ok": True, "actor": {"id": 7}}
        self.boom = boom
        self.scrape_calls = []
        self.tick_calls = []
        self.crop_calls = []

    def run_actor_scrape(self, store, emby_client=None, **kwargs):
        self.scrape_calls.append((store, emby_client, kwargs))
        if self.boom:
            raise RuntimeError("流水线炸了")
        return dict(self.scrape)

    def queue_tick(self, store, emby_client=None, **kwargs):
        self.tick_calls.append((store, emby_client, kwargs))
        if self.boom:
            raise RuntimeError("流水线炸了")
        return dict(self.tick)

    def crop_avatar(self, store, emby_client=None, **kwargs):
        self.crop_calls.append((store, emby_client, kwargs))
        if self.boom:
            raise RuntimeError("裁切炸了")
        return dict(self.crop)


class FakePeople:
    """只给 `person_from_actor()` 的假 `scraper`（作品史比对走的就是这一条取值链）。"""

    def __init__(self, mapping=None):
        self.mapping = dict(mapping if mapping is not None else {
            "河北彩花": "河北彩花", "深田えいみ": "深田えいみ"})
        self.calls = []

    def person_from_actor(self, actor):
        self.calls.append(actor)
        name = str((actor or {}).get("name") if isinstance(actor, dict) else actor or "")
        return self.mapping.get(name, "")


class FakeActorSources:
    """S2 `actor_sources` 的假模块：索引状态与刷新都是可控的同步函数。"""

    def __init__(self, status=None, refresh=None, boom=False):
        self.status = status if status is not None else {
            "count": 12873, "fetched_at": "2026-10-19 08:00:00", "stale": False,
            "source": "raw.githubusercontent.com"}
        self.refresh = refresh if refresh is not None else {
            "ok": True, "count": 12873, "fetched_at": "2026-10-20 06:00:00", "stale": False}
        self.boom = boom
        self.status_calls = 0
        self.refresh_calls = []

    def index_status(self):
        self.status_calls += 1
        if self.boom:
            raise RuntimeError("索引读不出来")
        return dict(self.status)

    def refresh_index(self, *, proxy="", fetch=None):
        self.refresh_calls.append({"proxy": proxy, "fetch": fetch})
        if self.boom:
            raise RuntimeError("拉取失败")
        return dict(self.refresh)


@pytest.fixture(scope="session")
def api_mod():
    """插件入口模块（`__init__.py`）。"""
    return _load_entry()


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def plugin(api_mod, store):
    """不跑 `init_plugin()` 的插件实例：store 注入假对象，Emby 一律未配置。"""
    instance = api_mod.AVHelper()
    instance._enabled = True
    instance._proxy = "http://proxy.invalid:7890"
    instance._store = store
    instance._emby_host = ""
    instance._emby_apikey = ""
    instance._emby_lib = None
    instance._emby_sig = None
    instance._emby_client = None
    instance._emby_client_sig = None
    instance._client = None
    return instance


def call(coro):
    """跑一个 async 处理器（不引入 pytest-asyncio 依赖）。"""
    return asyncio.run(coro)


def with_actor_sync(api_mod, monkeypatch, fake):
    """换上假 `actor_sync` 模块。"""
    monkeypatch.setattr(api_mod.AVHelper, "actor_sync_module", lambda self: fake)
    return fake


def no_actor_sync(api_mod, monkeypatch):
    """把 `actor_sync` 摘掉（模拟 S3 还没落盘 / 导入失败）。"""
    monkeypatch.setattr(api_mod.AVHelper, "actor_sync_module", lambda self: None)


def with_people(api_mod, monkeypatch, fake=None):
    """换上假 `scraper`（`/actor/detail` 的规范名比对要用 `person_from_actor()`）。"""
    fake = fake if fake is not None else FakePeople()
    monkeypatch.setattr(api_mod.AVHelper, "scrape_module", lambda self: fake)
    return fake


def with_actor_sources(api_mod, monkeypatch, fake):
    monkeypatch.setattr(api_mod.AVHelper, "actor_sources_module", lambda self: fake)
    return fake


def no_actor_sources(api_mod, monkeypatch):
    monkeypatch.setattr(api_mod.AVHelper, "actor_sources_module", lambda self: None)


NEW_ACTOR_PATHS = ["/actor/list", "/actor/detail", "/actor/sources", "/actor/scrape",
                   "/actor/crop-avatar", "/actor/lock", "/actor/gfriends/refresh"]


def stub_startup(api_mod, monkeypatch, store, namemap=None):
    """把 `init_plugin()` 里的重活（限流/引擎/客户端/后台预热）全换成假对象。

    只留真正要验的两步：`store.init()`（迁移）与 `store.actor_backfill()`（存量回填）。
    """
    namemap = namemap if namemap is not None else types.SimpleNamespace()
    monkeypatch.setattr(api_mod, "Store", lambda *args, **kwargs: store)
    monkeypatch.setattr(api_mod, "RateLimiter", lambda *args, **kwargs: types.SimpleNamespace())
    monkeypatch.setattr(api_mod, "Notifier", lambda *args, **kwargs: types.SimpleNamespace())
    monkeypatch.setattr(api_mod, "TaskEngine", lambda *args, **kwargs: types.SimpleNamespace())
    monkeypatch.setattr(api_mod, "JavdbClient", lambda *args, **kwargs: types.SimpleNamespace())
    monkeypatch.setattr(api_mod, "reset_javdb_state", lambda: None)
    monkeypatch.setattr(api_mod.paths, "configure", lambda **kwargs: None)
    monkeypatch.setattr(api_mod.AVHelper, "_wire_limiter", lambda self: None)
    monkeypatch.setattr(api_mod.AVHelper, "start_javdb_bootstrap", lambda self: None)
    monkeypatch.setattr(api_mod.AVHelper, "start_warm_up", lambda self: None)
    monkeypatch.setattr(api_mod.AVHelper, "namemap_module", lambda self: namemap)
    return namemap


# ---------------------------------------------------------------------------
# 0. 启动路径：存量演员回填（0.9.0 真机缺口 —— 不回填则 actor 表永远 0 行）
# ---------------------------------------------------------------------------


class TestStartupBackfill:
    def test_startup_backfills_once_with_namemap(self, api_mod, monkeypatch):
        store = FakeStore()
        namemap = stub_startup(api_mod, monkeypatch, store)
        plugin = api_mod.AVHelper()
        assert plugin.init_plugin() is None
        assert store.init_calls == 1                       # 迁移先做完
        assert store.backfill_calls == [{"actors": None, "namemap_mod": namemap}]

    def test_startup_survives_backfill_failure(self, api_mod, monkeypatch):
        """回填抛异常只 warning：插件必须照常起来（否则一次聚合失败就打不开界面）。"""
        store = FakeStore(boom={"actor_backfill"})
        stub_startup(api_mod, monkeypatch, store)
        plugin = api_mod.AVHelper()
        plugin.init_plugin()                               # 不抛就是通过
        assert len(store.backfill_calls) == 1              # 确实调了，异常被吞
        assert plugin._store is store
        assert plugin.actor_opts()["actorBatchSize"] == 20 # 起来之后照样能干活

    def test_startup_without_backfill_api(self, api_mod, monkeypatch):
        """store 还没这套 API（半截升级）时同样不许把启动打挂。"""
        store = FakeStore()
        monkeypatch.delattr(store.__class__, "actor_backfill", raising=False)
        stub_startup(api_mod, monkeypatch, store)
        plugin = api_mod.AVHelper()
        plugin.init_plugin()
        assert plugin._store is store


# ---------------------------------------------------------------------------
# A. 路由表：7 条都在，且都排在 `/actor` / `/actors` 之前
# ---------------------------------------------------------------------------


class TestRouteTable:
    def test_seven_actor_paths_registered(self, plugin):
        paths = [route["path"] for route in plugin.get_api()]
        missing = [path for path in NEW_ACTOR_PATHS if path not in paths]
        assert missing == []
        assert len(set(NEW_ACTOR_PATHS)) == 7

    def test_new_paths_are_bear_authed(self, plugin):
        routes = {route["path"]: route for route in plugin.get_api()}
        for path in NEW_ACTOR_PATHS:
            assert routes[path].get("auth") == "bear", path
            assert str(routes[path].get("summary") or "").strip(), path

    def test_new_paths_all_before_actor_prefix(self, plugin):
        """下标断言：宿主按注册顺序匹配，新条目必须排在 `/actor` 与 `/actors` 之前。"""
        paths = [route["path"] for route in plugin.get_api()]
        actor_at = paths.index("/actor")
        actors_at = paths.index("/actors")
        for path in NEW_ACTOR_PATHS:
            assert paths.index(path) < actor_at, path
            assert paths.index(path) < actors_at, path

    def test_actor_list_would_be_shadowed_by_actor_prefix(self, plugin):
        """`/actor/list` 的防护：**路径精确相等**（不是前缀包含），且下标在 `/actor` 之前。

        `/actor/list`.startswith(`/actor`) 为真 —— 所以顺序一旦反了，前缀匹配会把这条吃掉，
        `GET /actor?name=`（javdb 演员页）与 `GET /actor/list` 就只有一条能活。
        """
        paths = [route["path"] for route in plugin.get_api()]
        assert "/actor/list".startswith("/actor")            # 撞前缀是真的
        assert paths.count("/actor/list") == 1               # 精确相等的那一条
        assert paths.count("/actor") == 1                    # 老端点也还在
        assert paths.index("/actor/list") < paths.index("/actor")
        assert "/actor/list" != "/actor"

    def test_new_paths_have_no_path_parameters(self, plugin):
        """一律不用路径参数：有 `{id}` 之类的写法就会被 `/actor` 前缀抢先匹配。"""
        paths = [route["path"] for route in plugin.get_api()]
        for path in NEW_ACTOR_PATHS:
            assert "{" not in path and "}" not in path, path
            assert paths.count(path) == 1, path

    def test_old_actor_endpoints_kept(self, plugin):
        routes = {route["path"]: route for route in plugin.get_api()}
        assert routes["/actor"]["methods"] == ["GET"]
        assert routes["/actors"]["methods"] == ["GET"]

    def test_scrape_avatars_compat_route_kept(self, plugin):
        """`POST /scrape/avatars` 原样保留（内部转调是 S7 的事，这里只锁注册形状）。"""
        routes = {route["path"]: route for route in plugin.get_api()}
        assert routes["/scrape/avatars"]["methods"] == ["POST"]
        assert routes["/scrape/avatars"]["auth"] == "bear"
        assert routes["/scrape/avatars"]["endpoint"] == plugin.api_scrape_avatars

    def test_no_duplicate_path_and_method(self, plugin):
        seen = set()
        for route in plugin.get_api():
            for method in route.get("methods") or []:
                pair = (str(route.get("path")), str(method).upper())
                assert pair not in seen, pair
                seen.add(pair)


# ---------------------------------------------------------------------------
# B. actor_opts()：6 个键的默认值与夹取
# ---------------------------------------------------------------------------


class TestActorOpts:
    def test_defaults(self, plugin, store):
        assert plugin.actor_opts() == {
            "actorEnabled": True, "actorGfriends": True, "actorJavdbFallback": True,
            "actorAutoSync": True, "actorBatchSize": 20, "actorInterval": 2,
        }
        assert store.kv_writes == []          # 只读不写

    def test_clamps_out_of_range(self, plugin, store):
        store.rule = {"actorBatchSize": 999, "actorInterval": -1}
        opts = plugin.actor_opts()
        assert opts["actorBatchSize"] == 200
        assert opts["actorInterval"] == 0

    def test_clamps_low_bound_of_batch(self, plugin, store):
        store.rule = {"actorBatchSize": 0, "actorInterval": 999}
        opts = plugin.actor_opts()
        assert opts["actorBatchSize"] == 1
        assert opts["actorInterval"] == 60

    def test_tolerates_string_values(self, plugin, store):
        """设置台写进来的可能是字符串（`/rule` POST 的 JSON 不保证类型）。"""
        store.rule = {"actorBatchSize": "35", "actorInterval": "0", "actorAutoSync": "false"}
        opts = plugin.actor_opts()
        assert opts["actorBatchSize"] == 35
        assert opts["actorInterval"] == 0
        assert opts["actorAutoSync"] is False

    def test_unknown_keys_are_ignored(self, plugin, store):
        store.rule = {"actorSomethingNew": 1, "scrapeMode": "hybrid"}
        opts = plugin.actor_opts()
        assert "actorSomethingNew" not in opts
        assert set(opts) == {"actorEnabled", "actorGfriends", "actorJavdbFallback",
                             "actorAutoSync", "actorBatchSize", "actorInterval"}

    def test_store_failure_falls_back_to_defaults(self, plugin, monkeypatch):
        def boom_rule(self):
            raise RuntimeError("kv 读不出来")

        monkeypatch.setattr(plugin.__class__, "global_rule", boom_rule)
        assert plugin.actor_opts() == {"actorEnabled": True, "actorGfriends": True,
                                       "actorJavdbFallback": True, "actorAutoSync": True,
                                       "actorBatchSize": 20, "actorInterval": 2}


# ---------------------------------------------------------------------------
# C. get_service()：actorsync 条目
# ---------------------------------------------------------------------------


class TestService:
    def test_actorsync_entry_shape(self, plugin):
        services = {item["id"]: item for item in plugin.get_service()}
        assert "actorsync" in services
        entry = services["actorsync"]
        assert entry["name"] == "AV 演员头像同步"
        assert entry["trigger"] == "cron"
        assert entry["kwargs"] == {"minute": "5,20,35,50"}

    def test_actorsync_func_is_bound_handler(self, plugin):
        services = {item["id"]: item for item in plugin.get_service()}
        assert services["actorsync"]["func"] == plugin.job_actor_sync
        assert callable(services["actorsync"]["func"])

    def test_old_services_kept(self, plugin):
        services = {item["id"]: item for item in plugin.get_service()}
        assert set(services) >= {"subcheck", "cacheclean"}


# ---------------------------------------------------------------------------
# D. job_actor_sync()：门禁、异常与返回值
# ---------------------------------------------------------------------------


class TestJobActorSync:
    def test_disabled_auto_sync_returns_zero_without_tick(self, plugin, store, api_mod,
                                                         monkeypatch):
        store.rule = {"actorAutoSync": False}
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        assert plugin.job_actor_sync() == 0
        assert fake.tick_calls == []

    def test_disabled_actor_returns_zero_without_tick(self, plugin, store, api_mod, monkeypatch):
        store.rule = {"actorEnabled": False}
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        assert plugin.job_actor_sync() == 0
        assert fake.tick_calls == []

    def test_missing_module_returns_zero(self, plugin, api_mod, monkeypatch):
        no_actor_sync(api_mod, monkeypatch)
        assert plugin.job_actor_sync() == 0

    def test_queue_tick_exception_is_swallowed(self, plugin, api_mod, monkeypatch):
        with_actor_sync(api_mod, monkeypatch, FakeActorSync(boom=True))
        assert plugin.job_actor_sync() == 0

    def test_tick_receives_batch_proxy_and_opts(self, plugin, store, api_mod, monkeypatch):
        store.rule = {"actorBatchSize": 999, "actorInterval": 3}
        fake = with_actor_sync(api_mod, monkeypatch,
                               FakeActorSync(tick={"ok": True, "popped": 2,
                                                   "counts": {"total": 3}}))
        assert plugin.job_actor_sync() == 3          # counts['total'] 优先于 popped
        assert len(fake.tick_calls) == 1
        called_store, emby_client, kwargs = fake.tick_calls[0]
        assert called_store is store
        assert emby_client is None                 # 没配 Emby
        assert kwargs["batch"] == 200              # 夹取后的值
        assert kwargs["proxy"] == "http://proxy.invalid:7890"
        assert kwargs["opts"]["actorInterval"] == 3

    def test_handled_wins_over_popped(self, plugin, api_mod, monkeypatch):
        """S3 现在给 `handled`（真进流水线的条数，含 due 补位）：它比 `popped` 准。"""
        with_actor_sync(api_mod, monkeypatch,
                        FakeActorSync(tick={"ok": True, "handled": 3, "queued": 1, "popped": 1}))
        assert plugin.job_actor_sync() == 3

    def test_tick_result_without_count_returns_zero(self, plugin, api_mod, monkeypatch):
        with_actor_sync(api_mod, monkeypatch, FakeActorSync(tick={"ok": True}))
        assert plugin.job_actor_sync() == 0


# ---------------------------------------------------------------------------
# E. /actor/scrape：dry_run 缺省 True
# ---------------------------------------------------------------------------


class TestActorScrapeEndpoint:
    def test_dry_run_defaults_true(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        result = call(plugin.api_actor_scrape(FakeRequest(body={})))
        assert fake.scrape_calls[0][2]["dry_run"] is True
        assert result["success"] is True
        assert result["dry_run"] is True

    def test_dry_run_false_passthrough(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        call(plugin.api_actor_scrape(FakeRequest(body={"dry_run": False, "id": 7})))
        kwargs = fake.scrape_calls[0][2]
        assert kwargs["dry_run"] is False
        assert kwargs["actor_ids"] == [7]

    def test_ids_persons_names_parsed(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        call(plugin.api_actor_scrape(FakeRequest(body={
            "ids": [7, 8, "x"], "persons": ["河北彩花", " "], "names": ["深田えいみ"],
            "force": True, "limit": 5})))
        kwargs = fake.scrape_calls[0][2]
        assert kwargs["actor_ids"] == [7, 8]          # "x" 转不出正整数，被丢掉
        assert kwargs["persons"] == ["河北彩花"]      # 空串被丢掉
        assert kwargs["names"] == ["深田えいみ"]
        assert kwargs["force"] is True
        assert kwargs["limit"] == 5

    def test_ids_filtered_to_positive(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        call(plugin.api_actor_scrape(FakeRequest(body={"ids": [7, 0, -2, "9"]})))
        assert fake.scrape_calls[0][2]["actor_ids"] == [7, 9]

    def test_empty_body_passes_none(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        call(plugin.api_actor_scrape(FakeRequest(body={})))
        kwargs = fake.scrape_calls[0][2]
        assert kwargs["actor_ids"] is None and kwargs["persons"] is None
        assert kwargs["names"] is None and kwargs["limit"] == 0

    def test_missing_module_returns_not_ready(self, plugin, api_mod, monkeypatch):
        no_actor_sync(api_mod, monkeypatch)
        result = call(plugin.api_actor_scrape(FakeRequest(body={})))
        assert result["success"] is False
        assert result["message"] == "演员子系统未就绪"
        assert result["dry_run"] is True

    def test_exception_becomes_success_false(self, plugin, api_mod, monkeypatch):
        with_actor_sync(api_mod, monkeypatch, FakeActorSync(boom=True))
        result = call(plugin.api_actor_scrape(FakeRequest(body={})))
        assert result["success"] is False
        assert result["ok"] is False
        assert "流水线炸了" in result["message"]
        assert result["errors"] == ["流水线炸了"]

    def test_broken_body_is_tolerated(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        call(plugin.api_actor_scrape(FakeRequest(body=None)))     # request.json() 抛
        assert fake.scrape_calls[0][2]["dry_run"] is True


# ---------------------------------------------------------------------------
# F. /actor/list 与 /actor/detail
# ---------------------------------------------------------------------------


class TestActorListEndpoint:
    def test_list_paginates(self, plugin, store):
        result = plugin.api_actor_list(q="河北", filter="missing_avatar", page=1, limit=1)
        assert result["success"] is True
        assert result["total"] == 2 and len(result["items"]) == 1
        assert result["page"] == 1 and result["limit"] == 1
        assert store.calls[-1] == ("actor_list", "河北", "missing_avatar", 1, 0)

    def test_list_marks_primary_image(self, plugin, store):
        items = plugin.api_actor_list(page=1, limit=2)["items"]
        assert [item["primary"] for item in items[0]["images"]] == [True, False]
        assert items[1]["images"] == []
        # 序列化是"现场算"：库里存的那份 JSON 不许被塞进 primary
        assert "primary" not in store.rows[0]["images"][0]

    def test_list_offset_follows_page(self, plugin, store):
        plugin.api_actor_list(page=3, limit=10)
        assert store.calls[-1][-1] == 20

    def test_list_clamps_limit(self, plugin, store):
        plugin.api_actor_list(limit=9999)
        assert store.calls[-1][3] == 200
        plugin.api_actor_list(limit=-5)
        assert store.calls[-1][3] == 1

    def test_list_missing_store_method(self, plugin, monkeypatch):
        monkeypatch.delattr(plugin._store.__class__, "actor_list", raising=False)
        result = plugin.api_actor_list()
        assert result["success"] is False
        assert result["message"] == "演员子系统未就绪"
        assert result["items"] == [] and result["total"] == 0

    def test_list_exception_is_envelope(self, plugin, store):
        store.boom = {"actor_list"}
        result = plugin.api_actor_list()
        assert result["success"] is False
        assert "库挂了" in result["message"]
        assert result["items"] == []


class TestActorDetailEndpoint:
    def test_detail_ok(self, plugin, store, api_mod, monkeypatch):
        with_people(api_mod, monkeypatch)
        result = plugin.api_actor_detail(id="7")
        assert result["success"] is True
        assert result["actor"]["person"] == "河北彩花"
        assert ("actor_get", 7, "") in store.calls

    def test_detail_marks_primary_image(self, plugin, api_mod, monkeypatch):
        with_people(api_mod, monkeypatch)
        images = plugin.api_actor_detail(id="7")["actor"]["images"]
        assert [item["primary"] for item in images] == [True, False]

    def test_detail_numbers_come_from_meta(self, plugin, api_mod, monkeypatch):
        """`numbers` 按规范名精确比对：只收河北彩花那两条，无 display_number 的回落 key。"""
        fake = with_people(api_mod, monkeypatch)
        numbers = plugin.api_actor_detail(id="7")["numbers"]
        assert [item["number"] for item in numbers] == ["SSIS-001", "SSIS003"]
        assert numbers[0]["title"] == "第一部"
        assert fake.calls                      # 比拼走的是 person_from_actor()

    def test_detail_history_filters_by_name(self, plugin, store, api_mod, monkeypatch):
        with_people(api_mod, monkeypatch)
        history = plugin.api_actor_detail(id="7")["history"]
        assert [item["action"] for item in history] == ["ok", "skipped"]
        assert history[1]["reason"] == "has_image"
        assert history[0]["at"] == "2026-10-20 03:00:00"
        assert ("scrape_log_recent", 200, "actor") in store.calls

    def test_detail_survives_meta_and_log_failure(self, plugin, store, api_mod, monkeypatch):
        """作品史/日志读不出来只留空数组，详情照常成功（不 500）。"""
        with_people(api_mod, monkeypatch)
        store.boom = {"meta_list", "scrape_log_recent"}
        result = plugin.api_actor_detail(id="7")
        assert result["success"] is True
        assert result["numbers"] == [] and result["history"] == []

    def test_detail_without_scraper_module(self, plugin, api_mod, monkeypatch):
        monkeypatch.setattr(api_mod.AVHelper, "scrape_module", lambda self: None)
        result = plugin.api_actor_detail(id="7")
        assert result["success"] is True and result["numbers"] == []

    def test_detail_missing_id(self, plugin):
        result = plugin.api_actor_detail(id="")
        assert result["success"] is False
        assert result["actor"] is None
        assert result["numbers"] == [] and result["history"] == []

    def test_detail_not_found(self, plugin):
        result = plugin.api_actor_detail(id="424242")
        assert result["success"] is False
        assert "没有这位演员" in result["message"]

    def test_detail_missing_store_method(self, plugin, monkeypatch):
        monkeypatch.delattr(plugin._store.__class__, "actor_get", raising=False)
        assert plugin.api_actor_detail(id="7")["message"] == "演员子系统未就绪"

    def test_detail_exception_is_envelope(self, plugin, store):
        store.boom = {"actor_get"}
        result = plugin.api_actor_detail(id="7")
        assert result["success"] is False
        assert "库挂了" in result["message"]


# ---------------------------------------------------------------------------
# G. /actor/sources 与 /actor/gfriends/refresh
# ---------------------------------------------------------------------------


class TestActorSourcesEndpoint:
    def test_sources_reports_index_status(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sources(api_mod, monkeypatch, FakeActorSources())
        result = call(plugin.api_actor_sources())
        assert result["success"] is True
        assert result["index"] == {"count": 12873, "fetched_at": "2026-10-19 08:00:00",
                                   "stale": False, "source": "raw.githubusercontent.com"}
        assert fake.status_calls == 1
        image_ids = [s["id"] for s in result["sources"] if s["role"] == "image"]
        assert image_ids == ["gfriends", "javdb"]     # 顺序即回落优先级

    def test_sources_entries_carry_note(self, plugin, api_mod, monkeypatch):
        """`sources[]` 每条都有 `note`（前端直接当 title，不在前端拼文案）。"""
        with_actor_sources(api_mod, monkeypatch, FakeActorSources())
        sources = call(plugin.api_actor_sources())["sources"]
        assert len(sources) == 4
        assert all(str(item.get("note") or "").strip() for item in sources)
        assert all({"role", "id", "name", "enabled"} <= set(item) for item in sources)

    def test_sources_switches_follow_kv(self, plugin, store, api_mod, monkeypatch):
        store.rule = {"actorGfriends": False, "actorJavdbFallback": False}
        with_actor_sources(api_mod, monkeypatch, FakeActorSources())
        result = call(plugin.api_actor_sources())
        assert all(not s["enabled"] for s in result["sources"] if s["role"] == "image")

    def test_sources_missing_module(self, plugin, api_mod, monkeypatch):
        no_actor_sources(api_mod, monkeypatch)
        result = call(plugin.api_actor_sources())
        assert result["success"] is False
        assert result["message"] == "演员子系统未就绪"
        assert result["index"]["stale"] is True

    def test_sources_exception_is_envelope(self, plugin, api_mod, monkeypatch):
        with_actor_sources(api_mod, monkeypatch, FakeActorSources(boom=True))
        result = call(plugin.api_actor_sources())
        assert result["success"] is False
        assert "索引读不出来" in result["message"]


class TestActorRefreshEndpoint:
    def test_refresh_passes_plugin_proxy(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sources(api_mod, monkeypatch, FakeActorSources())
        result = call(plugin.api_actor_gfriends_refresh())
        assert set(result) == {"success", "index"}       # 信封与 /actor/sources 同一套
        assert result["success"] is True
        assert fake.refresh_calls == [{"proxy": "http://proxy.invalid:7890", "fetch": None}]
        assert result["index"]["count"] == 12873
        assert result["index"]["stale"] is False

    def test_refresh_missing_module(self, plugin, api_mod, monkeypatch):
        no_actor_sources(api_mod, monkeypatch)
        result = call(plugin.api_actor_gfriends_refresh())
        assert result["message"] == "演员子系统未就绪"
        assert result["success"] is False
        assert result["index"] == {"count": 0, "fetched_at": "", "stale": True, "source": ""}

    def test_refresh_stale_index_reports_false(self, plugin, api_mod, monkeypatch):
        """拉取失败时 S2 保留旧缓存、只把 `stale` 置真 —— 端点据它回 `success:false`。"""
        with_actor_sources(api_mod, monkeypatch, FakeActorSources(
            refresh={"count": 12000, "fetched_at": "2026-10-01 00:00:00", "stale": True,
                     "source": "cdn.jsdelivr.net"}))
        result = call(plugin.api_actor_gfriends_refresh())
        assert result["success"] is False
        assert result["index"]["stale"] is True
        assert result["index"]["count"] == 12000

    def test_refresh_exception_is_envelope(self, plugin, api_mod, monkeypatch):
        with_actor_sources(api_mod, monkeypatch, FakeActorSources(boom=True))
        result = call(plugin.api_actor_gfriends_refresh())
        assert result["success"] is False
        assert "拉取失败" in result["message"]


# ---------------------------------------------------------------------------
# G2. `/img` 的本地派生图分支（裁剪/上传落盘的绝对路径）
# ---------------------------------------------------------------------------


def img_req(if_none_match: str = "") -> FakeRequest:
    """`/img` 的替身请求：处理器只用到 `headers`（ETag 条件请求）。"""
    request = FakeRequest(method="GET")
    request.headers = {"if-none-match": if_none_match} if if_none_match else {}
    return request


JPEG = b"\xff\xd8\xff\xe0" + b"local-derived-crop" * 4


@pytest.fixture
def cache_dir(tmp_path, api_mod, monkeypatch):
    """把 `imgproxy.cache_dir()` 钉到临时目录（本地派生图分支唯一允许的根）。"""
    root = tmp_path / "images"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(api_mod.imgproxy, "cache_dir", lambda: str(root))
    return root


@pytest.fixture
def fetch_recorder(api_mod, monkeypatch):
    """记录白名单取图分支有没有被调用（默认一律回 None → 404）。"""
    calls = []

    def fake_fetch(url, proxy=""):
        calls.append({"url": url, "proxy": proxy})
        return None

    monkeypatch.setattr(api_mod.imgproxy, "fetch", fake_fetch)
    return calls


class TestImgLocalDerived:
    def test_local_cache_image_is_served(self, plugin, cache_dir, fetch_recorder):
        """裁剪/上传落盘的绝对路径要能被 `/img?url=` 直接读出来（否则用户看到的是裂图）。"""
        path = cache_dir / "crop-actor-7.jpg"
        path.write_bytes(JPEG)
        response = plugin.api_img(img_req(), url=str(path))
        assert response.status_code == 200
        assert response.body == JPEG
        assert response.headers.get("content-type", "").startswith("image/jpeg")
        assert response.headers.get("cache-control") == "public, no-cache"
        assert fetch_recorder == []                 # 本地命中就不该再走白名单取图

    def test_local_image_etag_revalidates(self, plugin, cache_dir, fetch_recorder):
        path = cache_dir / "crop-actor-7.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"png")
        first = plugin.api_img(img_req(), url=str(path))
        assert first.status_code == 200
        assert first.headers.get("content-type", "").startswith("image/png")
        etag = str(first.headers.get("etag") or "")
        assert etag
        again = plugin.api_img(img_req(if_none_match=etag), url=str(path))
        assert again.status_code == 304 and again.body in (b"", None)

    def test_traversal_path_is_404(self, plugin, cache_dir, fetch_recorder):
        """`../` 穿越必须被挡住：真实路径不在缓存目录内 → 落回白名单分支 → 404。"""
        secret = cache_dir.parent / "secret.jpg"
        secret.write_bytes(JPEG)
        escape = str(cache_dir / ".." / "secret.jpg")
        response = plugin.api_img(img_req(), url=escape)
        assert response.status_code == 404
        assert fetch_recorder                      # 确实落回了原分支（不是读到了文件）

    def test_file_outside_cache_is_404(self, plugin, cache_dir, fetch_recorder, tmp_path):
        other = tmp_path / "elsewhere"
        other.mkdir()
        path = other / "x.jpg"
        path.write_bytes(JPEG)
        response = plugin.api_img(img_req(), url=str(path))
        assert response.status_code == 404
        assert fetch_recorder

    def test_non_image_extension_is_404(self, plugin, cache_dir, fetch_recorder):
        """缓存目录内的非图片文件不许读（`.db` / `.json` 就在同一棵树里）。"""
        path = cache_dir / "avhelper.db"
        path.write_bytes(b"SQLite format 3\x00")
        response = plugin.api_img(img_req(), url=str(path))
        assert response.status_code == 404
        assert fetch_recorder

    def test_missing_path_falls_back_to_url_branch(self, plugin, cache_dir, fetch_recorder):
        """不存在的路径 → 原逻辑照旧：白名单取图回 None → 404。"""
        response = plugin.api_img(img_req(), url=str(cache_dir / "nope.jpg"))
        assert response.status_code == 404
        assert fetch_recorder == [{"url": str(cache_dir / "nope.jpg"),
                                   "proxy": plugin._proxy}]


# ---------------------------------------------------------------------------
# H. /actor/lock 与 /actor/crop-avatar
# ---------------------------------------------------------------------------


WRITE_ENVELOPE_KEYS = {"success", "ok", "actor", "reason"}


class TestActorLockEndpoint:
    def test_lock_defaults(self, plugin, store):
        result = call(plugin.api_actor_lock(FakeRequest(body={"id": 7})))
        assert set(result) == WRITE_ENVELOPE_KEYS      # 摊平的行收回 actor，success/ok/reason 并列
        assert result["success"] is True and result["ok"] is True
        assert result["reason"] == ""
        assert result["actor"]["locked_fields"] == ["images"]
        assert result["actor"]["images"][0]["primary"] is True
        assert store.calls[-1] == ("actor_lock", 7, "images", True)

    def test_unlock_passes_on_false(self, plugin, store):
        result = call(plugin.api_actor_lock(
            FakeRequest(body={"id": 7, "field": "images", "on": False})))
        assert store.calls[-1] == ("actor_lock", 7, "images", False)
        assert result["actor"]["locked_fields"] == []
        assert set(result) == WRITE_ENVELOPE_KEYS

    def test_lock_missing_row_reports_reason(self, plugin):
        """store 回 `{}`（没有这位演员）时 success/ok 同假，并把原因说清楚。"""
        result = call(plugin.api_actor_lock(FakeRequest(body={"id": 999})))
        assert set(result) == WRITE_ENVELOPE_KEYS
        assert result["success"] is False and result["ok"] is False
        assert result["actor"] is None
        assert result["reason"] == "没有这位演员（id=999）"

    def test_lock_missing_id(self, plugin):
        result = call(plugin.api_actor_lock(FakeRequest(body={})))
        assert result["success"] is False and result["ok"] is False
        assert result["reason"] == "缺少演员 id"

    def test_lock_missing_store_method(self, plugin, monkeypatch):
        monkeypatch.delattr(plugin._store.__class__, "actor_lock", raising=False)
        result = call(plugin.api_actor_lock(FakeRequest(body={"id": 7})))
        assert result["message"] == "演员子系统未就绪"
        assert result["reason"] == "演员子系统未就绪"     # api_error 分支也带 reason
        assert result["success"] is False and result["ok"] is False

    def test_lock_exception_is_envelope(self, plugin, store):
        store.boom = {"actor_lock"}
        result = call(plugin.api_actor_lock(FakeRequest(body={"id": 7})))
        assert result["success"] is False and result["ok"] is False
        assert "库挂了" in result["message"]
        assert result["reason"] == result["message"]


class TestActorCropEndpoint:
    def test_crop_delegates_to_pipeline(self, plugin, store, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        result = call(plugin.api_actor_crop_avatar(
            FakeRequest(body={"id": 7, "rect": {"x": 0, "y": 0, "w": 300, "h": 400}})))
        assert set(result) == WRITE_ENVELOPE_KEYS      # {success, ok, actor, reason}
        assert result["success"] is True and result["ok"] is True
        assert result["reason"] == ""
        assert result["actor"] == {"id": 7, "images": []}
        _, _, kwargs = fake.crop_calls[0]
        assert kwargs["actor_id"] == 7
        assert kwargs["rect"] == {"x": 0, "y": 0, "w": 300, "h": 400}

    def test_crop_failure_keeps_reason(self, plugin, api_mod, monkeypatch):
        """流水线回 `ok:false + reason`：原因必须透传到信封（真机就是看不到这句话）。"""
        with_actor_sync(api_mod, monkeypatch, FakeActorSync(
            crop={"ok": False, "actor": None, "reason": "actor.images 为空"}))
        result = call(plugin.api_actor_crop_avatar(FakeRequest(body={"id": 7})))
        assert set(result) == WRITE_ENVELOPE_KEYS
        assert result["success"] is False and result["ok"] is False
        assert result["actor"] is None
        assert result["reason"] == "actor.images 为空"

    def test_crop_without_rect(self, plugin, api_mod, monkeypatch):
        fake = with_actor_sync(api_mod, monkeypatch, FakeActorSync())
        call(plugin.api_actor_crop_avatar(FakeRequest(body={"id": 7})))
        assert fake.crop_calls[0][2]["rect"] is None     # 交给流水线按 3:4 自判

    def test_crop_missing_id(self, plugin):
        result = call(plugin.api_actor_crop_avatar(FakeRequest(body={})))
        assert result["success"] is False and result["ok"] is False
        assert result["message"] == "缺少演员 id"
        assert result["reason"] == "缺少演员 id"
        assert result["actor"] is None

    def test_crop_missing_module(self, plugin, api_mod, monkeypatch):
        no_actor_sync(api_mod, monkeypatch)
        result = call(plugin.api_actor_crop_avatar(FakeRequest(body={"id": 7})))
        assert result["message"] == "演员子系统未就绪"
        assert result["reason"] == "演员子系统未就绪"     # actor_not_ready 分支也带 reason
        assert result["ok"] is False

    def test_crop_module_without_handler(self, plugin, api_mod, monkeypatch):
        """S3 还没写 `crop_avatar()` 时也只回未就绪，不 500。"""
        with_actor_sync(api_mod, monkeypatch, types.SimpleNamespace())
        result = call(plugin.api_actor_crop_avatar(FakeRequest(body={"id": 7})))
        assert result["message"] == "演员子系统未就绪"

    def test_crop_exception_is_envelope(self, plugin, api_mod, monkeypatch):
        with_actor_sync(api_mod, monkeypatch, FakeActorSync(boom=True))
        result = call(plugin.api_actor_crop_avatar(FakeRequest(body={"id": 7})))
        assert result["success"] is False and result["ok"] is False
        assert "裁切炸了" in result["message"]
        assert result["reason"] == result["message"]
