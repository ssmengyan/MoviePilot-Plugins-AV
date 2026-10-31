"""下载提交的原子认领（0.9.2 A1）与队列裁剪（A2）。

**A1 的用户症状**：同一张待确认卡片点两次「下载」就会下两次 —— `download()` 读完任务从不看
`state`，成功后才写 `pushed`；换个站点就是另一个 hash，下载器自己没法去重，`canceled` 的任务
再发一次请求也照样下单。现在进来先做**条件写**认领（`await` → `submitting`），认领不到一律
拒绝；任何失败出口都把状态放回 `await`，所以「下载器抽风之后还能重试」不会被认领机制吃掉。

**A2 的用户症状**：队列三处 `[:50]` 硬截断，第 51 条进来切掉的是**最旧的活动项**（完成项早被
`_flush_done()` 摘进台账了），那条之后既不入账、也接不上下载完成即刮。现在只裁灰行。

替身与夹具沿用 `test_tasks_autodownload.py`（那边的 `_engine()` 已经把 searcher / 下载链 /
通知器全换成假的了）。
"""

import threading

from test_tasks_autodownload import _cand, _engine, _rule


# ---------------------------------------------------------------- 夹具

def _task(store, number="IPZZ-961", cands=None, thumb="http://img/1.jpg"):
    """落一条待确认任务（`thumb` 非空：省掉 `thumbs_of()` 那次查索引）。"""
    task = {
        "id": "t" + number.replace("-", ""),
        "number": number,
        "actor": "",
        "cands": [_cand()] if cands is None else cands,
        "reason": "",
        "state": "await",
        "thumb": thumb,
        "auto": False,
        "rule": _rule(trigger="notify"),
        "source": "manual",
        "pending": "",
    }
    store.task_add(task)
    return task["id"]


def _state(store, tid):
    return str((store.task_get(tid) or {}).get("state") or "")


# ---------------------------------------------------------------- A1：一单只下一次

class TestAtomicClaim:
    def test_second_click_is_refused_and_downloader_called_once(self, tasks_mod, store_mod,
                                                                tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store)

        first = engine.download(tid)
        assert first["ok"] is True
        assert _state(store, tid) == "pushed"
        assert len(chain.calls) == 1

        second = engine.download(tid)
        assert second["ok"] is False
        assert "已经提交过下载" in second["message"]
        assert second["number"] == "IPZZ-961"
        assert len(chain.calls) == 1          # ★ 下载器只收到一次

    def test_canceled_task_is_refused(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store)
        assert store.task_set_state(tid, "canceled", only_from=("await",)) is True

        result = engine.download(tid)
        assert result["ok"] is False
        assert "已取消" in result["message"]
        assert chain.calls == []
        assert _state(store, tid) == "canceled"

    def test_claim_is_atomic_under_threads(self, tasks_mod, store_mod, tmp_path):
        """4 条线程同时点同一张卡：只有一次能认领成功，下载器只收到一次。"""
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store)
        results = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            results.append(engine.download(tid))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for item in threads:
            item.start()
        for item in threads:
            item.join(10)
        assert len(results) == 4
        assert sum(1 for r in results if r["ok"]) == 1
        assert len(chain.calls) == 1
        assert _state(store, tid) == "pushed"

    def test_downloader_rejection_restores_await_and_retry_works(self, tasks_mod, store_mod,
                                                                 tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store)
        original = chain.download
        chain.download = lambda **kwargs: None          # 下载器拒收

        failed = engine.download(tid)
        assert failed["ok"] is False
        assert "没有接受" in failed["message"]
        assert _state(store, tid) == "await"            # ★ 能直接再点一次

        chain.download = original
        retried = engine.download(tid)
        assert retried["ok"] is True
        assert _state(store, tid) == "pushed"

    def test_exception_restores_await(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store)

        def boom(**kwargs):
            raise RuntimeError("下载器炸了")

        chain.download = boom
        result = engine.download(tid)
        assert result["ok"] is False
        assert "下载器炸了" in result["message"]
        assert _state(store, tid) == "await"

    def test_no_candidate_restores_await(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store, cands=[_cand(pas=False, picked=False)])

        result = engine.download(tid)
        assert result["ok"] is False
        assert _state(store, tid) == "await"
        assert chain.calls == []

    def test_other_tasks_are_not_affected(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        first = _task(store, "IPZZ-961")
        second = _task(store, "CAWB-040")

        assert engine.download(first)["ok"] is True
        assert engine.download(second)["ok"] is True
        assert len(chain.calls) == 2
        assert _state(store, first) == "pushed"
        assert _state(store, second) == "pushed"


# ------------------------------------------------- A1 收尾：卡在 submitting 的任务

class TestStaleSubmittingRecovery:
    def test_only_stale_rows_come_back(self, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        tid = _task(store)
        assert store.task_set_state(tid, "submitting", only_from=("await",)) is True

        # `before` 早于这一行：说明它「刚认领不久」，不该动
        assert store.task_recover_submitting(before="2000-01-01 00:00:00") == []
        assert _state(store, tid) == "submitting"

        # `before` 晚于这一行：按超时恢复
        rows = store.task_recover_submitting(before="2999-01-01 00:00:00")
        assert [row["id"] for row in rows] == [tid]
        assert [row["number"] for row in rows] == ["IPZZ-961"]
        assert _state(store, tid) == "await"
        # 幂等：再恢复一次什么都不做
        assert store.task_recover_submitting(before="2999-01-01 00:00:00") == []

    def test_recovered_task_can_be_downloaded_again(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        tid = _task(store)
        store.task_set_state(tid, "submitting", only_from=("await",))
        store.task_recover_submitting(before="2999-01-01 00:00:00")

        assert engine.download(tid)["ok"] is True
        assert len(chain.calls) == 1


# ---------------------------------------------------------------- A2：只裁灰行

def _entry(state="down", index=0):
    return {"id": f"q{index:04d}", "number": f"IPZZ-{index:03d}", "hash": f"{index:040d}",
            "state": state, "progress": 0, "site": "馒头", "spec": "", "size": "",
            "downloader": "qb", "category": "avi", "savePath": "", "thumb": "",
            "added": "2026-11-01 10:00:00"}


class TestTrimQueue:
    def test_under_limit_is_untouched(self, tasks_mod):
        rows = [_entry(index=i) for i in range(10)]
        assert tasks_mod._trim_queue(rows) == rows

    def test_all_active_rows_survive(self, tasks_mod):
        """60 条活动项：一条都不能因为队列长度被丢掉（老写法会切掉最旧 10 条）。"""
        rows = [_entry(index=i) for i in range(60)]
        trimmed = tasks_mod._trim_queue(rows)
        assert len(trimmed) == 60
        assert trimmed == rows

    def test_only_gray_rows_are_trimmed(self, tasks_mod):
        active = [_entry("down", i) for i in range(48)]
        gray = [_entry("canceled", 100 + i) for i in range(12)]
        trimmed = tasks_mod._trim_queue(active + gray)
        assert len(trimmed) == 50
        assert [row for row in trimmed if row["state"] == "down"] == active
        # 从队尾（最旧）裁灰行：留下的正好是最早插入的那两条
        assert [row["id"] for row in trimmed if row["state"] == "canceled"] == ["q0100", "q0101"]

    def test_failed_rows_count_as_gray(self, tasks_mod):
        rows = [_entry("down", i) for i in range(50)] + [_entry("failed", 100)]
        trimmed = tasks_mod._trim_queue(rows)
        assert len(trimmed) == 50
        assert trimmed == rows[:50]

    def test_active_rows_win_over_the_limit(self, tasks_mod):
        rows = [_entry("down", i) for i in range(55)] + [_entry("canceled", 100)]
        trimmed = tasks_mod._trim_queue(rows)
        assert len(trimmed) == 55
        assert all(row["state"] == "down" for row in trimmed)
