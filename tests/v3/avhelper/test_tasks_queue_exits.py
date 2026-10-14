"""下载页那一行的三个出口（取消 / 换资源 / 不要了）+ `canceled` 冻结口径的单测。

起因是用户 2026-10-15 的要求：
「当前缺少取消下载按钮，需增加该功能；取消下载后条目不要立即消失，应保留在原位置；
提供『返回任务』操作……如果用户真的不想下载了，想完全取消而不返回，该怎么处理」。

设计口径（`docs/AVHelper-显示统一与下载界面方案.md` §5）：
- **取消** = 删下载器里的种子（含已下载的部分文件）→ 队列行改 `canceled` 且**留在原位**；
- **换资源** = 摘掉这一行 + 对应任务从 `pushed` 置回 `await`（候选原样保留，去任务页重挑）；
- **不要了** = 摘行 + 台账墓碑 + 任务 `canceled` +（默认）取消该番号的订阅 + 写 known；
- **移除** = 只把已经 `canceled` 的灰行从列表去掉。

本文件钉住的正是这几条最容易悄悄坏掉的纪律：

1. **冻结**：`canceled` 的条目不许被下载器读数翻回 `down`/`done`，也不许被 `_flush_gone`
   摘掉或改写成「已下载」——否则用户点完取消，几秒后它自己又变回「下载中」；
2. **先删种子、成功了才改状态**：删失败就什么都不改（不能一边写"已取消"一边还在下）；
3. **已完成的不许取消**（可能已入库，删文件是破坏性动作）；
4. 三个出口的**副作用范围**各自正确（换资源不动台账与订阅；不要了才动订阅）。
"""


class _Torrent:
    """宿主 `DownloaderTorrent` 的最小替身。"""

    def __init__(self, hash, progress=0.0, state="downloading", downloader="qb"):
        self.hash = hash
        self.progress = progress
        self.state = state
        self.downloader = downloader


class _Chain:
    """下载链替身：`remove_calls` 记录每一次删种子请求（含 `delete_file`）。"""

    def __init__(self, remove_result=True, remove_boom=None):
        self.torrents = []
        self.calls = []
        self.remove_calls = []
        self.remove_result = remove_result
        self.remove_boom = remove_boom

    def list_torrents(self, hashs=None, **kwargs):
        self.calls.append((list(hashs or []), bool(kwargs.get("include_all_tags"))))
        return list(self.torrents)

    def remove_torrents(self, hashs=None, delete_file=False, **kwargs):
        if self.remove_boom:
            raise self.remove_boom
        self.remove_calls.append((list(hashs or []), bool(delete_file)))
        return self.remove_result


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
        return False

    def emby(self):
        return self._emby


class _Notifier:
    def __init__(self):
        self.notices = []

    def info(self, title, body):
        self.notices.append((title, body))
        return {"title": title, "body": body}


class _InlineThread:
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


def queue_rows(store):
    """当前队列快照。"""
    return store.kv_get("queue", []) or []


# ---------- 取消：删种子 + 留在原位 ----------


class TestCancelEntry:
    """`cancel_entry()`：删种子（含文件）→ 行改 canceled 留在原位 → 台账打墓碑。"""

    def test_cancel_removes_torrent_with_files_and_keeps_row(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, notifier = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        result = engine.cancel_entry("q0001")
        assert result["ok"] is True
        # 删种子用的是 delete_file=True（取消的是**还没下完**的任务，半截文件该清掉）
        assert chain.remove_calls == [(["h" * 40], True)]
        # 行留在原位，状态改成 canceled
        rows = queue_rows(store)
        assert len(rows) == 1
        assert rows[0]["state"] == "canceled"
        assert rows[0]["number"] == "IPZZ-961"
        assert rows[0]["canceled_at"]
        assert notifier.notices and "取消" in notifier.notices[0][0]

    def test_cancel_is_idempotent(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled"))
        result = engine.cancel_entry("q0001")
        assert result["ok"] is True
        assert chain.remove_calls == []          # 已经取消过就不再麻烦下载器

    def test_cancel_refuses_done_entry(self, tasks_mod, store_mod, tmp_path):
        """已完成的不许取消：那可能已经入库，删文件是破坏性动作。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="done"))
        result = engine.cancel_entry("q0001")
        assert result["ok"] is False
        assert "已经下载完成" in result["message"]
        assert chain.remove_calls == []
        assert queue_rows(store)[0]["state"] == "done"

    def test_cancel_leaves_state_untouched_when_torrent_removal_fails(self, tasks_mod, store_mod,
                                                                     tmp_path):
        """删种子失败（下载器失联/拒绝）→ 什么都不改，绝不假称已取消。"""
        chain = _Chain(remove_result=False)
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path, chain=chain)
        seed(store, make_entry())
        # 复查也查不到它 → `_remove_torrents` 会把「本来就没有」算成功；这里让它**查得到**，
        # 模拟"下载器拒了删除请求、种子还在跑"
        chain.torrents = [_Torrent("h" * 40)]
        result = engine.cancel_entry("q0001")
        assert result["ok"] is False
        assert queue_rows(store)[0]["state"] == "down"

    def test_cancel_writes_ledger_tombstone(self, tasks_mod, store_mod, tmp_path):
        """台账那条「提交下载时写的 downloading」要打墓碑（这次下载没发生）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40)
        seed(store, make_entry())
        engine.cancel_entry("q0001")
        assert all(row["key"] != "IPZZ961" for row in store.download_list())

    def test_cancel_without_hash_still_marks_row(self, tasks_mod, store_mod, tmp_path):
        """老数据没有 hash：不麻烦下载器，但仍要把这一行标成 canceled（并如实说明）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(hash=""))
        result = engine.cancel_entry("q0001")
        assert result["ok"] is True
        assert chain.remove_calls == []
        assert queue_rows(store)[0]["state"] == "canceled"


# ---------- 冻结口径：取消之后条目不许自己变回去 ----------


class TestCanceledIsFrozen:
    """`canceled` 的条目必须对下载器读数免疫（否则取消几秒后就"复活"）。"""

    def test_merge_queue_skips_canceled(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled"))
        chain.torrents = [_Torrent("h" * 40, progress=88.0, state="downloading")]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["state"] == "canceled"
        assert rows[0]["progress"] == 0          # 进度也不该被改写

    def test_merge_queue_skips_canceled_even_when_completed(self, tasks_mod, store_mod, tmp_path):
        """下载器报 completed 也不许把 canceled 翻成 done。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled"))
        chain.torrents = [_Torrent("h" * 40, progress=100.0, state="completed")]
        fresh, _ = engine._query_torrents(["h" * 40])
        rows = store.kv_update("queue", lambda cur: engine._merge_queue(cur, fresh, {}))
        assert rows[0]["state"] == "canceled"

    def test_flush_gone_keeps_canceled_row(self, tasks_mod, store_mod, tmp_path):
        """`_flush_gone` 不许摘掉 canceled 行（用户还要在原位点换资源/不要了）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled", miss=5))
        rows = engine._flush_gone(queue_rows(store))
        assert len(rows) == 1
        assert rows[0]["state"] == "canceled"

    def test_flush_gone_does_not_mark_canceled_as_downloaded(self, tasks_mod, store_mod, tmp_path):
        """关键回归：Emby 库里恰好有这个番号时，也不许把取消的记录改写成「已下载」。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path, library=("IPZZ961",))
        seed(store, make_entry(state="canceled", miss=5))
        engine._flush_gone(queue_rows(store))
        assert store.download_list() == []       # 台账里没有凭空多出一条"已下载"

    def test_queue_buckets_exclude_canceled(self, tasks_mod, store_mod, tmp_path):
        """轮询不该再去问一个已经删掉的 hash（否则每 5 秒白打一次下载器）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled"), make_entry(id="q0002", hash="g" * 40))
        engine.queue(fresh=True)
        flat = [h for group, _ in chain.calls for h in group]
        assert "h" * 40 not in flat
        assert "g" * 40 in flat


# ---------- 换资源：摘行 + 任务回待确认 ----------


class TestReturnEntry:
    """`return_entry()`：摘掉这一行 + 把 `pushed` 的任务置回 `await`。"""

    def test_return_removes_row_and_reopens_task(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, notifier = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        store.task_add({"id": "t1", "number": "IPZZ-961", "state": "pushed", "cands": []})
        result = engine.return_entry("q0001")
        assert result["ok"] is True
        assert queue_rows(store) == []
        assert store.task_get("t1")["state"] == "await"
        assert "任务" in result["message"]
        assert notifier.notices

    def test_return_keeps_candidates_and_does_not_touch_ledger(self, tasks_mod, store_mod, tmp_path):
        """候选与规则原样保留（不必重搜）；台账与订阅一概不动。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        cands = [{"site": "馒头", "title": "x", "pass": True}]
        seed(store, make_entry())
        store.task_add({"id": "t1", "number": "IPZZ-961", "state": "pushed", "cands": cands})
        store.download_upsert("IPZZ-961", state="downloading")
        store.sub_add("number", "IPZZ-961", {})
        engine.return_entry("q0001")
        task = store.task_get("t1")
        assert task["cands"] == cands
        assert [row["key"] for row in store.download_list()] == ["IPZZ961"]
        assert len(store.sub_list()) == 1

    def test_return_matches_task_by_number_when_id_differs(self, tasks_mod, store_mod, tmp_path):
        """队列行 id 与任务 id 不同源：按番号（归一后）也能对上。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(number="ipzz-00961"))
        store.task_add({"id": "t9", "number": "IPZZ961", "state": "pushed", "cands": []})
        engine.return_entry("q0001")
        assert store.task_get("t9")["state"] == "await"

    def test_return_without_task_still_removes_row(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        result = engine.return_entry("q0001")
        assert result["ok"] is True
        assert queue_rows(store) == []
        assert "重新搜" in result["message"]      # 如实告诉用户要自己搜

    def test_return_unknown_id_fails(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        result = engine.return_entry("nope")
        assert result["ok"] is False


# ---------- 不要了：彻底取消 ----------


class TestDiscardEntry:
    """`discard_entry()`：摘行 + 台账墓碑 + 任务 canceled +（默认）删订阅 + 写 known。"""

    def test_discard_removes_row_and_cleans_up(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, notifier = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        store.download_upsert("IPZZ-961", state="downloading")
        store.sub_add("number", "IPZZ-961", {})
        store.task_add({"id": "t1", "number": "IPZZ-961", "state": "pushed", "cands": []})
        result = engine.discard_entry("q0001", unsubscribe=True)
        assert result["ok"] is True
        assert queue_rows(store) == []
        assert store.download_list() == []                    # 台账墓碑
        assert store.sub_list() == []                         # 订阅一并取消
        assert store.task_get("t1")["state"] == "canceled"    # 任务不再回任务页
        assert "IPZZ-961" in store.known_all()                # 写进忽略表
        assert notifier.notices

    def test_discard_without_unsubscribe_keeps_sub(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        store.sub_add("number", "IPZZ-961", {})
        engine.discard_entry("q0001", unsubscribe=False)
        assert len(store.sub_list()) == 1

    def test_discard_removes_torrent_without_files(self, tasks_mod, store_mod, tmp_path):
        """「不要了」只摘任务**不删文件**：已经下好的正片可能在媒体库里。

        （种子那一步由 `cancel_all()` 走，`delete_file=False`；这条同时看着"只删一次"。）
        """
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        engine.discard_entry("q0001")
        assert chain.remove_calls == [(["h" * 40], False)]

    def test_discard_already_canceled_row_skips_torrent(self, tasks_mod, store_mod, tmp_path):
        """先点过「取消」再点「不要了」：种子那一次删不必重复发（仍在队列里的 hash 会被复查成
        "本来就不在"，不会报错），而这一行必须消失。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled", hash=""))
        result = engine.discard_entry("q0001", unsubscribe=False)
        assert result["ok"] is True
        assert chain.remove_calls == []          # 没有 hash 就不打下载器
        assert queue_rows(store) == []


# ---------- 移除灰行 ----------


class TestDropEntry:
    """`drop_entry()`：只把已经 canceled 的灰行从列表去掉。"""

    def test_drop_removes_canceled_row_only(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(state="canceled"), make_entry(id="q0002", hash="g" * 40))
        result = engine.drop_entry("q0001")
        assert result["ok"] is True
        rows = queue_rows(store)
        assert [row["id"] for row in rows] == ["q0002"]
        assert chain.remove_calls == []          # 不动下载器

    def test_drop_refuses_active_row(self, tasks_mod, store_mod, tmp_path):
        """还在下载的行不许直接移除（否则用户以为取消了，种子还在跑）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        result = engine.drop_entry("q0001")
        assert result["ok"] is False
        assert "取消下载" in result["message"]
        assert len(queue_rows(store)) == 1

    def test_drop_unknown_id_fails(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        assert engine.drop_entry("nope")["ok"] is False


# ---------- 辅助判据 ----------


class TestHelpers:
    """`_find_queue_entry` / `_same_queue_row` / `_is_frozen` 的兜底口径。"""

    def test_find_by_id_then_hash(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry(hash="a" * 40))
        assert engine._find_queue_entry("q0001")["id"] == "q0001"
        assert engine._find_queue_entry("a" * 40)["id"] == "q0001"
        assert engine._find_queue_entry("") is None
        assert engine._find_queue_entry("nope") is None

    def test_is_frozen_only_for_canceled(self, tasks_mod):
        assert tasks_mod._is_frozen({"state": "canceled"}) is True
        for state in ("down", "done", "failed", "", None):
            assert tasks_mod._is_frozen({"state": state}) is False
        assert tasks_mod._is_frozen(None) is False

