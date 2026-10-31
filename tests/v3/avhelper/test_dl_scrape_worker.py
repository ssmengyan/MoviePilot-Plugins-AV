"""「下载完成即刮」的后台 worker：停机 / 重载边界与队列持久化（0.9.5 C1）。

对应用户报过的一类问题（通用版 §11）：队列只在内存里，进程一重载就丢；worker 的启停又没有
回归测试，只能靠"看起来没事"。这里钉住四条：

1. **待办落库**：入队同时写 `kv:dl_scrape_pending`，刮过才删 —— reload 不再丢；
2. **恢复**：新实例 `_dl_scrape_resume()` 把上次没刮完的放回队列并重新起线程；
3. **停机**：队列空时 `stop_service()` 能把 worker 收掉，不留活线程；
4. **重启/单实例**：stop 之后再入队会起新线程；重复 `_dl_scrape_start()` 不会有两个 worker。
"""
import threading
import time

from test_api_scrape import _load_entry

PENDING = "dl_scrape_pending"


class _BlockingScrape:
    """刮削模块替身：每个 key 都会卡在 `gate` 上，方便观察"在队 / 在刮"两态。"""

    def __init__(self, gate=None):
        self.gate = gate or threading.Event()
        self.calls = []

    def scrape_batch(self, keys, **kwargs):
        self.calls.append(list(keys))
        self.gate.wait(5)
        self.gate.set()                 # 只放行一次：后续条目秒过，避免测试拖时间
        return [{"ok": True, "status": "ok"}]


class _InstantScrape(_BlockingScrape):
    """立刻返回的替身（用来验"刮过就删待办"）。"""

    def __init__(self):
        super().__init__(gate=threading.Event())
        self.gate.set()


def _plugin(tmp_path, store_mod, scrape=None):
    api_mod = _load_entry()
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    plugin = api_mod.AVHelper()
    plugin._enabled = True
    plugin._proxy = ""
    plugin._store = store
    fake = scrape or _InstantScrape()
    plugin.scrape_module = lambda: fake
    plugin.scrape_deps = lambda: {}
    return plugin, store, fake


def _wait(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def _reset_worker(plugin):
    """模拟「进程重载」：把内存态清掉（store 留着），像新实例一样。"""
    plugin.stop_service()
    plugin._dl_scrape_queue = None
    plugin._dl_scrape_thread = None
    plugin._dl_scrape_wake = None
    plugin._dl_scrape_stop = None


def test_pending_survives_and_is_cleared_after_attempt(tmp_path, store_mod):
    gate = threading.Event()
    plugin, store, fake = _plugin(tmp_path, store_mod, _BlockingScrape(gate))
    try:
        assert plugin.on_download_done(["IPZZ961"]) == 1
        assert store.kv_get(PENDING) == ["IPZZ961"]        # 入队即落库
        assert _wait(lambda: fake.calls)                    # worker 已经拿到它了
        # 还在刮（gate 没放）：待办**不能**提前删，否则崩在这就丢了
        assert store.kv_get(PENDING) == ["IPZZ961"]
        gate.set()
        assert _wait(lambda: store.kv_get(PENDING) == [])   # 刮过才删
    finally:
        gate.set()
        plugin.stop_service()


def test_resume_puts_pending_back_after_reload(tmp_path, store_mod):
    plugin, store, _ = _plugin(tmp_path, store_mod)
    store.kv_set(PENDING, ["CAWB040", "IPZZ961"])
    _reset_worker(plugin)
    fake = _InstantScrape()
    plugin.scrape_module = lambda: fake

    assert plugin._dl_scrape_resume() == 2
    assert _wait(lambda: sorted(fake.calls[0]) == ["CAWB040", "IPZZ961"]
                 or len(fake.calls) >= 1)
    assert _wait(lambda: store.kv_get(PENDING) == [])
    plugin.stop_service()


def test_resume_without_pending_is_noop(tmp_path, store_mod):
    plugin, store, _ = _plugin(tmp_path, store_mod)
    assert plugin._dl_scrape_resume() == 0
    assert plugin._dl_scrape_thread is None


def test_stop_service_joins_worker_when_queue_empty(tmp_path, store_mod):
    plugin, store, _ = _plugin(tmp_path, store_mod)
    plugin._dl_scrape_ready()
    plugin._dl_scrape_start()
    thread = plugin._dl_scrape_thread
    assert thread is not None and thread.is_alive()
    plugin.stop_service()
    assert not thread.is_alive()
    assert plugin._dl_scrape_thread is None


def test_enqueue_after_stop_starts_a_new_worker(tmp_path, store_mod):
    plugin, store, fake = _plugin(tmp_path, store_mod)
    plugin._dl_scrape_ready()
    plugin._dl_scrape_start()
    first = plugin._dl_scrape_thread
    plugin.stop_service()
    assert not first.is_alive()

    plugin.on_download_done(["IPZZ961"])
    second = plugin._dl_scrape_thread
    assert second is not None and second is not first
    assert _wait(lambda: fake.calls)
    plugin.stop_service()


def test_only_one_worker_thread(tmp_path, store_mod):
    plugin, store, _ = _plugin(tmp_path, store_mod)
    plugin._dl_scrape_ready()
    for _ in range(3):
        plugin._dl_scrape_start()
    alive = [t for t in threading.enumerate() if t.name == "avhelper-download-scrape"]
    assert len(alive) == 1
    plugin.stop_service()
