"""下载队列的进度合并与「下载器里已经没有它了」的收尾单测。

起因是 2026-10-12 用户报的问题：在下载器里手动取消下载之后，插件「下载中」列表里那条记录
不消失，点「刷新进度」也没任何变化，一直挂着 0% 的进度条。根因是 `_merge_queue` 只认
「查到的 hash」——查不到就什么都不改，那条于是永远停在最后一次读到的进度上。

这里把三条纪律钉住：

1. **查不到 → 累计轮数 → 够 `QUEUE_MISS_LIMIT` 摘掉**，并且摘队列时只在 Emby 已有该番号时
   才补记「已下载」，其余情况**绝不**动台账；
2. **查询失败（异常）绝不算「查不到」**——下载器连不上时不能把队列当成「全被删了」清空；
3. 进度数字只用来画进度条，**「下完了」看宿主归一后的状态**（`completed`），
   所以 qB 上真实的 1%（原生读数 1.0）不会被算成 100%。
"""


class _Torrent:
    """宿主 `DownloaderTorrent` 的最小替身（只用到进度合并碰的那几个字段）。"""

    def __init__(self, hash, progress=0.0, state="downloading", downloader="qb"):
        self.hash = hash
        self.progress = progress
        self.state = state
        self.downloader = downloader


class _Chain:
    """宿主下载链替身：`torrents` 就是下一次 `list_torrents` 的回包。"""

    def __init__(self):
        self.torrents = []
        self.calls = []
        self.boom = None
        self.kwargs_error = False

    def list_torrents(self, hashs=None, **kwargs):
        # 老宿主的真实症状：形参表里没有 include_all_tags，传了就 TypeError
        if self.kwargs_error and "include_all_tags" in kwargs:
            raise TypeError("list_torrents() got an unexpected keyword argument 'include_all_tags'")
        self.calls.append((list(hashs or []), bool(kwargs.get("include_all_tags"))))
        if self.boom:
            raise self.boom
        return list(self.torrents)


class _Emby:
    def __init__(self, keys=()):
        self.keys = set(keys)

    def index(self):
        return {key: {"id": key, "name": key} for key in self.keys}


class _Plugin:
    def __init__(self, chain, library=()):
        self.chain = chain
        self._emby = _Emby(library)

    def fill_thumbs(self, rows):
        return False        # 单测不需要补封面

    def emby(self):
        return self._emby


class _Notifier:
    def __init__(self):
        self.notices = []

    def info(self, title, body):
        self.notices.append((title, body))
        return {"title": title, "body": body}


class _InlineThread:
    """守护线程替身：`start()` 直接就地把目标跑完，测试里没有真线程。"""

    def __init__(self, target=None, name="", daemon=False):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def make_engine(tasks_mod, store_mod, tmp_path, library=(), chain=None):
    """建一个跑在临时库上的引擎：真 Store + 假插件/下载链/通知器。"""
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    chain = chain or _Chain()
    notifier = _Notifier()
    engine = tasks_mod.TaskEngine(_Plugin(chain, library), store, None, notifier)
    return engine, store, chain, notifier


def make_entry(hash="h" * 40, number="IPZZ-961", **kwargs):
    """一条下载队列条目（字段与 `download()` 插进去的那份一致）。"""
    entry = {
        "id": "q0001", "number": number, "thumb": "", "site": "馒头", "spec": "1080p",
        "size": "1.2 GB", "hash": hash, "downloader": "qb", "category": "avi",
        "savePath": "/media/9kg/avi", "state": "down", "progress": 0,
        "added": "2026-10-12 10:00:00",
    }
    entry.update(kwargs)
    return entry


def seed(store, *entries):
    """把条目写进队列 KV（`queue()` 读的就是它）。"""
    store.kv_set("queue", list(entries))


# ---------- 进度合并 ----------


class TestProgressMerge:
    """`_merge_queue`：进度换算、完成判据、缺失计数。"""

    def test_downloading_torrent_updates_progress(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=42.6, state="downloading")]
        fresh, ok = engine._query_torrents(["h" * 40])
        assert ok is True
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["progress"] == 43
        assert rows[0]["state"] == "down"
        assert rows[0]["miss"] == 0

    def test_completed_state_is_done(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=100.0, state="completed")]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["state"] == "done"

    def test_fraction_state_completed_counts_as_done(self, tasks_mod, store_mod, tmp_path):
        """transmission 口径（0-1 小数）完成时给 1.0，也得算下完。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(downloader="tr"))
        chain.torrents = [_Torrent("h" * 40, progress=1.0, state="completed", downloader="tr")]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["state"] == "done"

    def test_one_percent_on_qb_is_not_done(self, tasks_mod, store_mod, tmp_path):
        """回归：qB 的 `progress` 已经是百分比，原生 1.0 就是 1%，不能算成 100%。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        # 先给一条 >1 的读数，让引擎记住「这台下载器是百分比口径」
        chain.torrents = [_Torrent("h" * 40, progress=37.0)]
        fresh, _ = engine._query_torrents(["h" * 40])
        store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        # 再回到 1%（重新校验/换种都会掉回来）
        chain.torrents = [_Torrent("h" * 40, progress=1.0, state="downloading")]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["progress"] == 1
        assert rows[0]["state"] == "down"

    def test_fraction_scale_is_multiplied(self, tasks_mod, store_mod, tmp_path):
        """transmission 口径没变：0.42 就是 42%。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(downloader="tr"))
        chain.torrents = [_Torrent("h" * 40, progress=0.42, downloader="tr")]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["progress"] == 42

    def test_missing_hash_counts_a_round(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = []                     # 下载器里已经没有这个 hash
        fresh, ok = engine._query_torrents(["h" * 40])
        assert ok is True and fresh == {}
        missing = {"h" * 40}
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}, missing))
        assert rows[0]["miss"] == 1             # 只累计，还没摘
        assert len(rows) == 1

    def test_found_again_resets_counter(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(miss=1))
        chain.torrents = [_Torrent("h" * 40, progress=5.0)]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}, set()))
        assert rows[0]["miss"] == 0

    def test_done_entry_is_not_counted_as_missing(self, tasks_mod, store_mod, tmp_path):
        """已完成的条目被清理掉是正常的，不该再记一笔「不见了」。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="done"))
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, {}, {}, {"h" * 40}))
        assert rows[0].get("miss") in (None, 0)

    def test_unknown_round_never_counts(self, tasks_mod, store_mod, tmp_path):
        """`missing=None`（本轮没问成）一个都不算缺失。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(miss=1))
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, {}, {}, None))
        assert rows[0]["miss"] == 1


# ---------- 查询口径 ----------


class TestQueryTorrents:
    """`_query_torrents`：失败要能被调用方看出来，且不吞异常。"""

    def test_success_reports_reliable(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.torrents = [_Torrent("a" * 40)]
        by_hash, ok = engine._query_torrents(["a" * 40])
        assert ok is True and set(by_hash) == {"a" * 40}

    def test_failure_reports_unreliable(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.boom = RuntimeError("下载器连不上")
        by_hash, ok = engine._query_torrents(["a" * 40])
        assert ok is False and by_hash == {}

    def test_empty_hash_list_is_not_a_round(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        assert engine._query_torrents([]) == ({}, False)

    def test_asks_without_tag_filter(self, tasks_mod, store_mod, tmp_path):
        """`include_all_tags=True`：种子被摘掉宿主标签后不能再被当成「已移除」。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.torrents = [_Torrent("a" * 40)]
        engine._query_torrents(["a" * 40])
        assert chain.calls == [(["a" * 40], True)]

    def test_falls_back_when_host_lacks_kwarg(self, tasks_mod, store_mod, tmp_path):
        """老宿主没有这个形参时退回不带它的调用（TypeError 不等于下载器坏了）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.torrents = [_Torrent("a" * 40)]
        chain.kwargs_error = True
        by_hash, ok = engine._query_torrents(["a" * 40])
        assert ok is True and set(by_hash) == {"a" * 40}


# ---------- 队列收尾（用户报的那条） ----------


class TestFlushGone:
    """`queue()` 端到端：取消下载之后那条记录必须消失。"""

    def test_cancelled_download_leaves_the_queue(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, notifier = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = []
        first = engine.queue(fresh=True)
        assert len(first) == 1 and first[0]["miss"] == 1     # 第一轮只记账
        second = engine.queue(fresh=True)
        assert second == []                                   # 第二轮摘掉
        assert store.kv_get("queue", []) == []
        assert notifier.notices and "IPZZ-961" in notifier.notices[0][1]

    def test_downloader_failure_never_clears_the_queue(self, tasks_mod, store_mod, tmp_path):
        """下载器连不上时连问十轮，队列也必须原样留着。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.boom = RuntimeError("下载器连不上")
        for _ in range(10):
            rows = engine.queue(fresh=True)
        assert len(rows) == 1 and rows[0]["hash"] == "h" * 40
        assert int(rows[0].get("miss") or 0) == 0

    def test_ledger_row_is_kept_when_not_in_library(self, tasks_mod, store_mod, tmp_path):
        """没下成 → 台账那条原样留着（不进徽标、不触发重复下载提示），绝不抹记录。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40,
                              source="plugin", title="某片")
        seed(store, make_entry())
        chain.torrents = []
        engine.queue(fresh=True)
        engine.queue(fresh=True)
        row = store.download_map().get("IPZZ961")
        assert row is not None and row["state"] == "downloading"

    def test_ledger_row_upgraded_when_already_in_library(self, tasks_mod, store_mod, tmp_path):
        """下完了才把种子清理掉（Emby 已有）→ 按已完成补记，别把它当没下成。"""
        engine, store, chain, notifier = make_engine(
            tasks_mod, store_mod, tmp_path, library={"IPZZ961"})
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40,
                              source="plugin", title="某片")
        seed(store, make_entry())
        chain.torrents = []
        engine.queue(fresh=True)
        engine.queue(fresh=True)
        row = store.download_map().get("IPZZ961")
        assert row is not None and row["state"] == "downloaded"
        assert row["completed_at"]
        assert any("已完成" in title for title, _ in notifier.notices)

    def test_mixed_queue_keeps_live_downloads(self, tasks_mod, store_mod, tmp_path):
        """一条被取消、一条还在下：只摘被取消的那条。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(hash="a" * 40, number="AAA-001"),
             make_entry(hash="b" * 40, number="BBB-002", id="q0002"))
        chain.torrents = [_Torrent("b" * 40, progress=18.0)]
        engine.queue(fresh=True)
        chain.torrents = [_Torrent("b" * 40, progress=22.0)]
        rows = engine.queue(fresh=True)
        assert [row["number"] for row in rows] == ["BBB-002"]
        assert rows[0]["progress"] == 22

    def test_new_entry_inserted_midway_is_not_dropped(self, tasks_mod, store_mod, tmp_path):
        """摘除按指纹就地做：期间「提交下载」插进来的新条目不能被整份写回冲掉。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = []
        engine.queue(fresh=True)                 # 第一轮：miss=1
        # 模拟「提交下载」在摘除之前插入了一条
        store.kv_update("queue", lambda cur: [make_entry(hash="c" * 40, number="CCC-003",
                                                         id="q0003")] + (cur or []))
        rows = engine.queue(fresh=True)
        assert [row["number"] for row in rows] == ["CCC-003"]

    def test_background_refresh_counts_too(self, tasks_mod, store_mod, tmp_path, monkeypatch):
        """`/bootstrap` 那条后台刷新路也要能把「查不到」记上（两条路共用同一套算法）。

        后台路比同步路多一轮才摘：它拿的是**刷新前**的快照（`fresh=False` 的契约就是
        「立刻回本地快照，刷新丢给守护线程」），所以计数由这次线程写进库里、下一轮才判。
        """
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = []
        monkeypatch.setattr(tasks_mod.threading, "Thread", _InlineThread)
        engine.queue(fresh=False)                # 后台刷一轮：miss=1
        assert store.kv_get("queue")[0]["miss"] == 1
        engine._queue_at["active"] = 0.0         # 假装过了 12 秒（否则这一轮被年龄闸挡住）
        engine.queue(fresh=False)                # 再刷一轮：miss=2
        assert store.kv_get("queue")[0]["miss"] == 2
        assert engine.queue(fresh=False) == []   # 下一轮按快照里的 miss=2 摘掉
        assert store.kv_get("queue") == []
