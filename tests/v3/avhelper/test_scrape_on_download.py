"""S6：下载完成即刮（`_flush_done` 钩子 + `on_download_done()` 后台 worker）单测。

两段被测代码，两套夹具：

1. **`tasks.TaskEngine._flush_done()` 的钩子**（A 段）：台账写成功、条目从队列摘掉之后，
   才 duck-typing 探 `plugin.on_download_done`，把这一批真下完的番号交出去。三条纪律：
   ① 只对**这次入账成功**的条目触发（写台账失败的那条留在队列里下轮重试，不触发）；
   ② 钩子抛异常不影响入账与摘除（台账是真值，刮削只是附加动作）；
   ③ 插件没有这个属性时照常工作（`tasks.py` 不 import 刮削）。
2. **插件侧的 `on_download_done()` 与 worker**（B 段）：`scrapeMode='off'` /
   `scrapeOnDownload=False` 都不排队；番号归一化复用 `scraper.resolve_key()`（meta 表主键）
   并去重；**入队后立即返回**，真正刮削在守护线程里逐条做；单条异常只记 `scrape_log`
   绝不让线程死掉；`stop_service()` 能让 worker 退出。

B 段要 `__init__.py`（宿主 `app.sdk.*` + fastapi），所以按文件路径独立加载入口，
合成包名与 `conftest.py` / `test_api_scrape.py` 保持一致。归一化用**真 `scraper`
模块**的 `resolve_key()`（测试里不另写一套），只有网络动作被替身接管。
"""

import importlib.util
import sys
import threading
import time
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
    if "app.sdk.plugin" not in sys.modules:
        plugin = types.ModuleType("app.sdk.plugin")

        class _PluginBase:
            """宿主插件基类的空壳：只要求 `get_data_path()` 存在。"""

            @staticmethod
            def get_data_path():
                return Path(".")

        plugin._PluginBase = _PluginBase
        sys.modules["app.sdk.plugin"] = plugin
    if "app.sdk.scheduler" not in sys.modules:
        sched = types.ModuleType("app.sdk.scheduler")
        sched.add_plugin_once_job = lambda *a, **k: None
        sched.remove_plugin_once_job = lambda *a, **k: None
        sys.modules["app.sdk.scheduler"] = sched
    if "app.schemas.types" not in sys.modules:
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
    key = PKG_NAME + ".__init__"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def api_mod():
    """插件入口模块（`__init__.py`）。"""
    return _load_entry()


def _wait_for(predicate, timeout=5.0, interval=0.01):
    """轮询等后台线程做完手上的事（这条路没有别的同步点可用）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


# ---------------------------------------------------------------------------
# A. `_flush_done` 的下载完成钩子
# ---------------------------------------------------------------------------


class _Emby:
    """`emby()` 的最小替身（`_flush_done` 这条路不查库，只为别的方法属性齐全）。"""

    def index(self):
        return {}


class _Notifier:
    def __init__(self):
        self.notices = []

    def info(self, title, body):
        self.notices.append((title, body))
        return {"title": title, "body": body}


class _PlainPlugin:
    """**没有** `on_download_done` 的插件：钩子是 duck-typing 的可选项。"""

    def __init__(self):
        self._emby = _Emby()

    def fill_thumbs(self, rows):
        return False

    def emby(self):
        return self._emby


class _HookPlugin(_PlainPlugin):
    """记录钩子入参；`boom=True` 时入账后抛异常（钩子炸了不许影响台账）。"""

    def __init__(self, boom=False):
        super().__init__()
        self.calls = []
        self.boom = boom

    def on_download_done(self, numbers):
        self.calls.append(list(numbers))
        if self.boom:
            raise RuntimeError("钩子炸了")
        return len(numbers)


def _engine(tasks_mod, store_mod, tmp_path, plugin):
    """真 Store + 假插件的引擎（与 `test_tasks_queue.make_engine` 同一套）。"""
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    engine = tasks_mod.TaskEngine(plugin, store, None, _Notifier())
    return engine, store


def _done_entry(number, hash="h" * 40, **kwargs):
    """一条 `state='done'` 的队列条目（`_merge_queue` 判完成后写回的形状）。"""
    entry = {
        "id": "q0001", "number": number, "thumb": "", "site": "馒头", "spec": "1080p",
        "size": "1.2 GB", "hash": hash, "downloader": "qb", "category": "avi",
        "savePath": "/media/9kg/avi", "state": "done", "progress": 100,
        "added": "2026-10-21 10:00:00",
    }
    entry.update(kwargs)
    return entry


class TestFlushDoneHook:
    """`_flush_done()`：入账成功才触发钩子，钩子的异常不许影响台账与摘除。"""

    def test_success_calls_hook_once_with_downloaded_numbers(self, tasks_mod, store_mod,
                                                             tmp_path):
        plugin = _HookPlugin()
        engine, store = _engine(tasks_mod, store_mod, tmp_path, plugin)
        store.kv_set("queue", [_done_entry("IPZZ-961"),
                               _done_entry("SNOS-380", hash="s" * 40)])
        remaining = engine._flush_done(store.kv_get("queue"))
        # 两条都入账并摘掉，钩子收到的是**这一批**番号（顺序按队列）
        assert remaining == []
        assert store.kv_get("queue") == []
        assert plugin.calls == [["IPZZ-961", "SNOS-380"]]
        ledger = store.download_map()
        assert ledger["IPZZ961"]["state"] == "downloaded"
        assert ledger["SNOS380"]["state"] == "downloaded"

    def test_ledger_write_failure_calls_hook_zero_times(self, tasks_mod, store_mod, tmp_path,
                                                        monkeypatch):
        """台账写失败 → 条目留在队列里下轮重试，**一次钩子都不许调**。"""
        plugin = _HookPlugin()
        engine, store = _engine(tasks_mod, store_mod, tmp_path, plugin)

        def boom(*args, **kwargs):
            raise RuntimeError("台账库被锁了")

        monkeypatch.setattr(store, "download_upsert", boom)
        store.kv_set("queue", [_done_entry("IPZZ-961")])
        remaining = engine._flush_done(store.kv_get("queue"))
        assert plugin.calls == []
        assert [row["number"] for row in remaining] == ["IPZZ-961"]      # 没有被摘掉
        assert [row["number"] for row in store.kv_get("queue")] == ["IPZZ-961"]

    def test_hook_exception_keeps_ledger_and_removal(self, tasks_mod, store_mod, tmp_path):
        """钩子抛异常：`_flush_done` 照常返回、条目照样被摘除、台账照样写进去。"""
        plugin = _HookPlugin(boom=True)
        engine, store = _engine(tasks_mod, store_mod, tmp_path, plugin)
        store.kv_set("queue", [_done_entry("IPZZ-961")])
        remaining = engine._flush_done(store.kv_get("queue"))
        assert plugin.calls == [["IPZZ-961"]]        # 抛之前确实调到了
        assert remaining == []
        assert store.kv_get("queue") == []
        assert store.download_map()["IPZZ961"]["state"] == "downloaded"

    def test_plugin_without_hook_still_flushes(self, tasks_mod, store_mod, tmp_path):
        """插件没有 `on_download_done`（老宿主 / 没装钩子）：照常入账摘除，不报错。"""
        engine, store = _engine(tasks_mod, store_mod, tmp_path, _PlainPlugin())
        store.kv_set("queue", [_done_entry("IPZZ-961")])
        assert engine._flush_done(store.kv_get("queue")) == []
        assert store.download_map()["IPZZ961"]["state"] == "downloaded"

    def test_numberless_entry_stays_and_hook_not_called(self, tasks_mod, store_mod, tmp_path):
        """没番号的条目归一不出键：留在队列里当「已完成」显示，不算"这次真下完"。"""
        plugin = _HookPlugin()
        engine, store = _engine(tasks_mod, store_mod, tmp_path, plugin)
        store.kv_set("queue", [_done_entry("")])
        remaining = engine._flush_done(store.kv_get("queue"))
        assert plugin.calls == []
        assert [row["number"] for row in remaining] == [""]


# ---------------------------------------------------------------------------
# B. 插件侧：`on_download_done()` 与后台 worker
# ---------------------------------------------------------------------------

#: 假 `scrape_deps()` 的返回值：断言 worker 走的是 `scrape_batch([key], **deps)` 这条路
FAKE_DEPS = {"store": "STORE", "cli": "CLI", "emby_client": "EMBY",
             "opts": {"sources": ("javdb",)}}


class FakeScraper:
    """`scraper` 模块替身：归一化**转调真模块的 `resolve_key()`**，刮削动作只记账。"""

    def __init__(self, scraper_module, boom_keys=()):
        self._real = scraper_module
        self.calls = []
        self.sleeps = []
        self.boom_keys = set(boom_keys)

    def resolve_key(self, number_or_key, item_key=""):
        return self._real.resolve_key(number_or_key, item_key)

    def scrape_batch(self, keys, **kwargs):
        keys = list(keys)
        self.calls.append((keys, dict(kwargs)))
        key = str(keys[0] if keys else "")
        if key in self.boom_keys:
            raise RuntimeError("站点 502（" + key + "）")
        return [{"ok": True, "status": "ok", "key": key, "changed": []}]

    def _SLEEP(self, seconds):
        """节流注入点：真模块里是 `time.sleep`，这里只记一笔（conftest 也把它换成空实现）。"""
        self.sleeps.append(seconds)


@pytest.fixture
def store(store_mod, tmp_path):
    """真 Store（临时库）：`scrape_conf()` 读的就是它的 kv `global_rule`。"""
    instance = store_mod.Store(db_path=tmp_path / "avhelper.db")
    instance.init()
    return instance


@pytest.fixture
def fake_scraper(api_mod, scraper_mod, monkeypatch):
    """换上假 scraper + 固定依赖包（不连站点、不建 Emby 客户端）。"""
    fake = FakeScraper(scraper_mod)
    monkeypatch.setattr(api_mod.AVHelper, "scrape_module", lambda self: fake)
    monkeypatch.setattr(api_mod.AVHelper, "scrape_deps", lambda self: dict(FAKE_DEPS))
    return fake


@pytest.fixture
def plugin(api_mod, store):
    """不跑 `init_plugin()` 的插件实例：store 直接注入，用完一定收线程。"""
    instance = api_mod.AVHelper()
    instance._enabled = True
    instance._proxy = ""
    instance._store = store
    try:
        yield instance
    finally:
        instance.stop_service()


class TestOnDownloadDoneGates:
    """三道闸门：`scrapeMode='off'` / `scrapeOnDownload=False` / 空与重复番号。"""

    def test_scrape_mode_off_enqueues_nothing(self, plugin, store, fake_scraper):
        store.kv_set("global_rule", {"scrapeMode": "off", "scrapeOnDownload": True})
        assert plugin.on_download_done(["IPZZ-961"]) == 0
        assert fake_scraper.calls == []
        assert plugin._dl_scrape_queue is None          # 连队列/线程都没建
        assert plugin._dl_scrape_thread is None

    def test_scrape_on_download_false_enqueues_nothing(self, plugin, store, fake_scraper):
        store.kv_set("global_rule", {"scrapeMode": "fill", "scrapeOnDownload": False})
        assert plugin.on_download_done(["IPZZ-961"]) == 0
        assert fake_scraper.calls == []
        assert plugin._dl_scrape_thread is None

    def test_empty_and_duplicate_numbers_collapse_to_one_key(self, plugin, store, fake_scraper):
        """空串丢弃；`IPZZ-961` / `ipzz00961` / `IPZZ-961-UC` 是同一个 meta 键，只排一条。"""
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        # 返回值就是**去重后**真正入队的条数
        assert plugin.on_download_done(["IPZZ-961", "ipzz00961", "IPZZ-961-UC", "", None]) == 1
        assert _wait_for(lambda: len(fake_scraper.calls) == 1)
        # 只刮一条，且键是 meta 表主键（去重失败这里会变成 3 条）
        assert [call[0] for call in fake_scraper.calls] == [["IPZZ961"]]

    def test_non_number_inputs_are_not_queued(self, plugin, store, fake_scraper):
        """`resolve_key()` 认不出是番号的输入（裸数字 = Emby id、`emby:` 实例键）不排队：
        排进去只会去刮另一部片。"""
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        assert plugin.on_download_done(["12598", "emby:12598"]) == 0
        assert fake_scraper.calls == []
        assert plugin._dl_scrape_thread is None

    def test_scraper_not_ready_returns_without_queueing(self, plugin, store, api_mod,
                                                        monkeypatch):
        monkeypatch.setattr(api_mod.AVHelper, "scrape_module", lambda self: None)
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        assert plugin.on_download_done(["IPZZ-961"]) == 0
        assert plugin._dl_scrape_thread is None


class TestOnDownloadDoneReturnsImmediately:
    """**绝不能在调用方线程里刮**：入队后立刻返回，worker 才去调 `scrape_batch`。"""

    def test_returns_before_worker_calls_scrape_batch(self, plugin, store, fake_scraper,
                                                      api_mod, monkeypatch):
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        gate = threading.Event()
        real_take = api_mod.AVHelper._dl_scrape_take

        def gated_take(self):
            # worker 卡在「取任务」这一步：保证断言时 scrape_batch 一定还没被调
            gate.wait(5.0)
            return real_take(self)

        monkeypatch.setattr(api_mod.AVHelper, "_dl_scrape_take", gated_take)
        try:
            assert plugin.on_download_done(["IPZZ-961"]) == 1
            assert fake_scraper.calls == []             # 返回时一次都没刮
            assert list(plugin._dl_scrape_queue) == ["IPZZ961"]
        finally:
            gate.set()
        assert _wait_for(lambda: len(fake_scraper.calls) == 1)
        assert fake_scraper.calls[0][0] == ["IPZZ961"]


class TestDownloadScrapeWorker:
    """worker：逐条 `scrape_batch([key], **deps)`、异常不杀线程、失败写 `scrape_log`。"""

    def test_calls_scrape_batch_per_key_with_deps(self, plugin, store, fake_scraper):
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        assert plugin.on_download_done(["IPZZ-961", "SNOS-380"]) == 2
        assert _wait_for(lambda: len(fake_scraper.calls) == 2)
        assert fake_scraper.calls[0] == (["IPZZ961"], dict(FAKE_DEPS))
        assert fake_scraper.calls[1] == (["SNOS380"], dict(FAKE_DEPS))
        # 两条之间歇一下：走 `scraper._SLEEP`，默认 2 秒、夹在 1–3 秒
        assert fake_scraper.sleeps and all(1.0 <= value <= 3.0 for value in fake_scraper.sleeps)
        rows = store.scrape_log_recent(limit=10, source_name="download_scrape")
        assert sorted(row["key"] for row in rows) == ["IPZZ961", "SNOS380"]
        assert {row["status"] for row in rows} == {"ok"}

    def test_exception_on_one_key_does_not_kill_thread(self, plugin, store, fake_scraper):
        """第一条抛异常：只记 `scrape_log` 的 error，线程活着，第二条照常被处理。"""
        fake_scraper.boom_keys = {"IPZZ961"}
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        assert plugin.on_download_done(["IPZZ-961", "SNOS-380"]) == 2
        assert _wait_for(lambda: len(fake_scraper.calls) == 2)
        assert fake_scraper.calls[0][0] == ["IPZZ961"]
        assert fake_scraper.calls[1][0] == ["SNOS380"]
        thread = plugin._dl_scrape_thread
        assert thread is not None and thread.is_alive()     # 线程没死
        rows = store.scrape_log_recent(limit=10, source_name="download_scrape")
        statuses = {row["key"]: row["status"] for row in rows}
        assert statuses == {"IPZZ961": "error", "SNOS380": "ok"}
        error_row = next(row for row in rows if row["key"] == "IPZZ961")
        assert "502" in error_row["error_summary"]

    def test_stop_service_stops_worker(self, plugin, store, fake_scraper):
        store.kv_set("global_rule", {"scrapeMode": "fill"})
        assert plugin.on_download_done(["IPZZ-961"]) == 1
        assert _wait_for(lambda: len(fake_scraper.calls) == 1)
        thread = plugin._dl_scrape_thread
        assert thread is not None and thread.is_alive()
        plugin.stop_service()
        assert plugin._dl_scrape_stop.is_set()
        assert _wait_for(lambda: not thread.is_alive(), timeout=3.0)
        assert thread.is_alive() is False
