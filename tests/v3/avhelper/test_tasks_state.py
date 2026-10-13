"""`tasks.py` 的状态判定单测（v4 · S6）。

对应 v4.1 §9.2 里属于 `tasks.py` 的四条 + 一条挂点，每条都钉一个"改回去就会红"的断言：

1. **下载失败被误标为 `downloaded`**：判据是**种子状态**，不是「队列里找不到它了」
   也不是「完成时间非空」。qB 的 `error` / `missingFiles` / `unknown` 必须落到台账
   `state='failed'` + `failed_reason`，且**不许**被后面几轮轮询翻成 `downloaded`；
2. **番号订阅重复下单**：下单前查三处（Emby 库 / 下载台账 / 待确认任务），命中即跳过并补写
   `known`；用户手动洗版（`source='manual'`）不受这条闸门约束；
3. **下载器失联**：`downloader_state()` 连接异常必须 `online=False`，并把上一轮进度快照作废；
4. **「不要了」三出口联动**：`cancel_all()` 的四个步骤都被执行（用真 Store + 假下载链验）；
5. **Tier 1/Tier 2 重刮挂点**：`_scrape_tick()` 取得到待办、且不在 `scraper.py` 缺位时炸掉。

关于 qB 状态的一个**实测前提**（2026-10-14 读容器里 MP v3.1.5 的源码）：
`app/modules/qbittorrent/__init__.py:370-379` 的 `__normalize_torrent_state()` 只认「下载中」
与「暂停」两组原始状态，**其余一律回 `'completed'`** —— 也就是说 `error` / `missingFiles` /
`unknown` 到插件这儿已经变成 `'completed'` 了，`DownloaderTorrent` 上也没有原始状态的字段。
所以「宿主把失败归一成 completed」这一条（`completed` + 进度不到 100）是**真机上唯一能走通**
的判据，本文件里按这条造案子（`TestHostLossyNormalization`）。
"""

import pytest


class _Torrent:
    """宿主 `DownloaderTorrent` 的最小替身（进度合并碰到的字段 + 可选原始状态）。"""

    def __init__(self, hash, progress=0.0, state="downloading", downloader="qb", **extra):
        self.hash = hash
        self.progress = progress
        self.state = state
        self.downloader = downloader
        for key, value in extra.items():        # raw_state=... / raw={...} 这类透传字段
            setattr(self, key, value)


class _Chain:
    """宿主下载链替身：`torrents` 是下一次 `list_torrents` 的回包，`remove_result` 是删种结果。"""

    def __init__(self):
        self.torrents = []
        self.boom = None
        self.remove_result = True
        self.remove_boom = None
        self.removed = []

    def list_torrents(self, hashs=None, **kwargs):
        if self.boom:
            raise self.boom
        return list(self.torrents)

    def remove_torrents(self, hashs=None, delete_file=True, downloader=None):
        if self.remove_boom:
            raise self.remove_boom
        self.removed.append((list(hashs or []), delete_file))
        return self.remove_result


class _Emby:
    """`EmbyLibrary` 替身：`index()` 的键就是归一化番号（与真实现同口径）。"""

    def __init__(self, keys=()):
        self.keys = set(keys)

    def index(self):
        return {key: {"id": key, "name": key} for key in self.keys}


class _Plugin:
    def __init__(self, chain=None, library=(), movies=None):
        self.chain = chain or _Chain()
        self._emby = _Emby(library)
        self._movies = list(movies or [])

    def fill_thumbs(self, rows):
        return False

    def thumbs_of(self, numbers):
        return {}

    def remember_thumbs(self, mapping):
        return None

    def magnets_cached(self, number):
        return []

    def magnets_failed_recently(self, number):
        return False

    def emby(self):
        return self._emby

    def image_url(self, url):
        return str(url or "")

    def cli(self):
        return self

    def actor(self, name, page=1, limit=50):
        return {"movies": self._movies if page == 1 else []}


class _Notifier:
    def __init__(self):
        self.notices = []

    def info(self, title, body):
        self.notices.append((title, body))
        return {"title": title, "body": body}

    def sub_hit_number(self, number, push=True):
        self.notices.append(("订阅命中", number))
        return {"title": "订阅命中", "body": number}

    def sub_new_actor(self, actor, number, push=True):
        self.notices.append(("演员订阅命中", number))
        return {"title": "演员订阅命中", "body": number}

    def candidate_ready(self, number, count, push=True):
        self.notices.append(("候选待确认", number))
        return {"title": "候选待确认", "body": number}

    def download_start(self, number, cand, image=""):
        self.notices.append(("开始下载", number))
        return {"title": "开始下载", "body": number}

    def limited(self, reason):
        self.notices.append(("限流", reason))
        return {"title": "限流", "body": reason}


class _Limiter:
    """限流替身：一律放行（本文件不测限流，那条政策由 `test_tasks_acquire.py` 钉着）。"""

    def site_available(self, name):
        return True, ""

    def throttle(self):
        return None

    def note_site_search(self, name):
        return None

    def site_gap(self):
        return None

    def site_cooldown(self, name):
        return None

    def check_allowed(self, max_per_day, min_interval):
        return True, ""

    def note_check(self):
        return None


def make_engine(tasks_mod, store_mod, tmp_path, library=(), chain=None, movies=None):
    """真 Store + 假插件/下载链/通知器/限流器。"""
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    chain = chain or _Chain()
    notifier = _Notifier()
    engine = tasks_mod.TaskEngine(_Plugin(chain, library, movies), store, _Limiter(), notifier)
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
    store.kv_set("queue", list(entries))


def ledger_row(store, key="IPZZ961"):
    return (store.download_map() or {}).get(key)


# ---------- 判据本身（纯函数） ----------


class TestFailureReason:
    """`_failure_reason()`：失败态与"真下完"的分界。"""

    def test_error_state_is_failure(self, tasks_mod):
        assert "error" in tasks_mod._failure_reason(_Torrent("h" * 40, state="error"), 0.0)

    def test_missing_files_state_is_failure(self, tasks_mod):
        reason = tasks_mod._failure_reason(_Torrent("h" * 40, state="missingFiles"), 0.0)
        assert "missingfiles" in reason.lower()

    def test_unknown_state_is_failure(self, tasks_mod):
        assert "unknown" in tasks_mod._failure_reason(_Torrent("h" * 40, state="unknown"), 0.0)

    def test_raw_state_in_nested_dict_is_failure(self, tasks_mod):
        """原始状态挂在别的字段/字典里也要认出来（别的宿主版本会这么透传）。"""
        torrent = _Torrent("h" * 40, state="completed", raw={"state": "missingFiles"})
        assert "missingfiles" in tasks_mod._failure_reason(torrent, 100.0).lower()

    def test_completed_with_short_progress_is_failure(self, tasks_mod):
        """**真机唯一能走通的那条**：宿主把 error/missingFiles/unknown 归一成 completed。"""
        reason = tasks_mod._failure_reason(_Torrent("h" * 40, state="completed"), 40.0)
        assert reason and "40%" in reason

    def test_completed_at_full_progress_is_not_failure(self, tasks_mod):
        assert tasks_mod._failure_reason(_Torrent("h" * 40, state="completed"), 100.0) == ""

    def test_uploading_is_not_failure(self, tasks_mod):
        assert tasks_mod._failure_reason(_Torrent("h" * 40, state="uploading"), 100.0) == ""

    def test_downloading_is_not_failure(self, tasks_mod):
        assert tasks_mod._failure_reason(_Torrent("h" * 40, state="downloading"), 42.0) == ""

    def test_transmission_fraction_at_complete_is_not_failure(self, tasks_mod):
        """transmission 完成给 1.0（小数口径），换算后就是 100%，不能当失败。"""
        assert tasks_mod._failure_reason(
            _Torrent("h" * 40, state="completed", downloader="tr"), 100.0) == ""


# ---------- 失败态 → 台账 ----------


class TestFailureLedger:
    """`queue()` 端到端：失败态进台账，且不会被后面的轮次翻成已下载。"""

    def test_raw_error_state_marks_ledger_failed(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, notifier = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=12.0, state="error")]
        rows = engine.queue(fresh=True)
        assert rows[0]["state"] == "failed"
        row = ledger_row(store)
        assert row["state"] == "failed"
        assert "error" in row["failed_reason"]
        assert any("下载失败" in title for title, _ in notifier.notices)

    def test_host_lossy_completed_marks_ledger_failed(self, tasks_mod, store_mod, tmp_path):
        """真机现场的案子：状态被宿主写成 `completed`，进度只有 12% —— 那就是失败。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=12.0, state="completed")]
        engine.queue(fresh=True)
        row = ledger_row(store)
        assert row["state"] == "failed"
        assert "12%" in row["failed_reason"]

    def test_failed_is_not_flipped_back_to_downloaded(self, tasks_mod, store_mod, tmp_path):
        """失败之后连问三轮，台账与队列都不许变成"已下载"。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=12.0, state="completed")]
        for _ in range(3):
            rows = engine.queue(fresh=True)
        # 条目**留在队列里**（S8/S9 要能把它画成一行"失败：<原因>"，不是悄悄消失）
        assert rows[0]["state"] == "failed"
        assert rows[0]["failed_reason"]
        assert rows[0]["failed_ledger"] is True
        assert ledger_row(store)["state"] == "failed"
        assert store.download_list()[0]["completed_at"] == ""

    def test_raw_failure_state_at_full_progress_stays_failed(self, tasks_mod, store_mod, tmp_path):
        """种子自己报失败态时，进度哪怕是 100% 也不算下完（判据是状态，不是进度）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=100.0, state="missingFiles")]
        rows = engine.queue(fresh=True)
        assert rows[0]["state"] == "failed"
        assert ledger_row(store)["state"] == "failed"

    def test_failed_round_is_registered_once(self, tasks_mod, store_mod, tmp_path):
        """台账只在首次判失败那一轮写一次（不是每 12 秒重写一遍）。"""
        engine, store, chain, notifier = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=12.0, state="completed")]
        engine.queue(fresh=True)
        first = len([n for n in notifier.notices if "下载失败" in n[0]])
        engine.queue(fresh=True)
        engine.queue(fresh=True)
        assert first == 1
        assert len([n for n in notifier.notices if "下载失败" in n[0]]) == 1

    def test_real_completion_after_failure_is_downloaded(self, tasks_mod, store_mod, tmp_path):
        """「除非 qB 真的报完成」：进度到 100 才允许翻回 done → 台账 downloaded。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=12.0, state="completed")]
        engine.queue(fresh=True)
        assert ledger_row(store)["state"] == "failed"
        chain.torrents = [_Torrent("h" * 40, progress=100.0, state="completed")]
        rows = engine.queue(fresh=True)
        assert rows == []                      # done → 登记进台账后从队列摘走
        assert ledger_row(store)["state"] == "downloaded"

    def test_missing_after_failure_keeps_failed(self, tasks_mod, store_mod, tmp_path):
        """失败条目在下载器里被删掉、而 Emby 库里恰好有这个番号 → **仍算失败**。

        这条正是「队列里找不到它了就当成功」的反例：库里的同号可能是上一次下的，
        失败是这一颗种子自己报出来的硬证据。
        """
        engine, store, chain, _ = make_engine(
            tasks_mod, store_mod, tmp_path, library={"IPZZ961"})
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=12.0, state="error")]
        engine.queue(fresh=True)               # 第一轮判失败（miss=0）
        chain.torrents = []                    # 用户在下载器里把它删了
        engine.queue(fresh=True)               # miss=1
        assert engine.queue(fresh=True) == []  # miss=2 → 摘队列
        row = ledger_row(store)
        assert row["state"] == "failed"
        assert "error" in row["failed_reason"]

    def test_downloaded_entry_still_flushes_normally(self, tasks_mod, store_mod, tmp_path):
        """回归：正常下完那条路一字不改（done → downloaded + 完成时间）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=100.0, state="completed")]
        assert engine.queue(fresh=True) == []
        row = ledger_row(store)
        assert row["state"] == "downloaded" and row["completed_at"]


# ---------- 下载器失联 ----------


class TestDownloaderState:
    """`downloader_state()`：S8 拿它给 `/downloads` 顶层加 `downloader_offline`。"""

    def test_connection_error_is_offline(self, tasks_mod, store_mod, tmp_path):
        engine, _, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.boom = RuntimeError("下载器连不上")
        state = engine.downloader_state()
        assert state["online"] is False
        assert "下载器连不上" in state["error"]
        assert len(state["checked_at"]) == 19        # 'YYYY-MM-DD HH:MM:SS'

    def test_offline_invalidates_progress_snapshot(self, tasks_mod, store_mod, tmp_path):
        """失联时上一轮快照必须作废 —— 不许沿用上一轮读到的进度。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        chain.torrents = [_Torrent("h" * 40, progress=42.0)]
        engine.queue(fresh=True)
        assert engine._queue_at["active"] > 0
        chain.boom = TimeoutError("read timeout")
        engine.downloader_state()
        assert engine._queue_at == {"active": 0.0, "done": 0.0}

    def test_none_result_is_offline(self, tasks_mod, store_mod, tmp_path):
        engine, _, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.torrents = None
        assert engine.downloader_state()["online"] is False

    def test_empty_list_is_online(self, tasks_mod, store_mod, tmp_path):
        """「下载器活着但一个种子都没有」是正常状态，不能当离线。"""
        engine, _, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.torrents = []
        state = engine.downloader_state()
        assert state == {"online": True, "error": "", "checked_at": state["checked_at"]}

    def test_online_clears_previous_error(self, tasks_mod, store_mod, tmp_path):
        engine, _, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        chain.boom = RuntimeError("下载器连不上")
        engine.downloader_state()
        chain.boom = None
        chain.torrents = [_Torrent("h" * 40)]
        assert engine.downloader_state()["online"] is True
        assert engine._downloader_error == ""


# ---------- 订阅去重 ----------


class TestDuplicateReason:
    """`duplicate_reason()` / `build_task()` 的查重闸门。"""

    def test_library_hit_skips_order(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, notifier = make_engine(
            tasks_mod, store_mod, tmp_path, library={"IPZZ961"})
        task = engine.build_task("IPZZ-961", "", None, False, source="sub")
        assert task["state"] == "skipped"
        assert "Emby" in task["duplicate"]
        assert store.task_list() == []                       # 一单都没建
        assert "IPZZ-961" in store.known_all()               # known 补写了
        notices = engine._after_task(task, {}, tasks_mod.merge_rule(None))
        assert "跳过" in notices[0]["title"]

    def test_ledger_downloading_hit_skips_order(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        task = engine.build_task("IPZZ-961", "", None, False, source="sub")
        assert task["state"] == "skipped"
        assert "台账" in task["duplicate"] and "downloading" in task["duplicate"]
        assert store.task_list() == []

    def test_ledger_downloaded_hit_skips_order(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloaded", hash="h" * 40, source="plugin")
        task = engine.build_task("IPZZ-961", "", None, False, source="sub")
        assert task["state"] == "skipped"
        assert "downloaded" in task["duplicate"]

    def test_pending_task_hit_skips_order(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.task_add({"id": "t1", "number": "IPZZ-961", "state": "await", "source": "manual"})
        task = engine.build_task("IPZZ-961", "", None, False, source="sub")
        assert task["state"] == "skipped"
        assert "待确认" in task["duplicate"]

    def test_failed_ledger_row_does_not_block(self, tasks_mod, store_mod, tmp_path):
        """`failed` 不算占住：失败了本来就该允许重下一次。"""
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="failed", failed_reason="种子状态 error",
                              hash="h" * 40, source="plugin")
        task = engine.build_task("IPZZ-961", "", None, False, source="sub")
        assert task["state"] != "skipped"
        assert task["number"] == "IPZZ-961"

    def test_manual_source_bypasses_the_gate(self, tasks_mod, store_mod, tmp_path):
        """手动洗版（详情页「下载该影片」/ 站点搜索）不受闸门约束。"""
        engine, store, _, _ = make_engine(
            tasks_mod, store_mod, tmp_path, library={"IPZZ961"})
        assert engine.duplicate_reason("IPZZ-961", "manual") == ""
        task = engine.build_task("IPZZ-961", "", None, False, source="manual")
        assert task["state"] != "skipped"
        assert task["source"] == "manual"
        assert len(store.task_list()) == 1

    def test_ledger_key_is_matched_verbatim(self, tasks_mod, store_mod, tmp_path):
        """台账主键是旧口径（保留后缀）：`IPZZ-912-UC` 与写回来的同一个写法要能对上。"""
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-912-UC", state="downloaded", hash="h" * 40, source="plugin")
        assert engine.duplicate_reason("IPZZ-912-UC", "sub")

    def test_canon_key_bridges_suffix_variants(self, tasks_mod, store_mod, tmp_path, emby_mod):
        """规范号要能跨过后缀写法：台账存 `IPZZ-912-UC`，订阅拿 `IPZZ-912` 来查也得命中。

        `emby.canon_key()`（契约 D1）已落地（2026-10-14）→ 这条现在是**真断言**。
        保留 skipif 只是因为并行施工期别的会话可能把它改回去：那时候它变成一条 skip
        并写明原因，而不是静默通过或假红。
        """
        if not callable(getattr(emby_mod, "canon_key", None)):
            pytest.skip("S2 的 emby.canon_key() 尚未落地（_canon() 现在退回 norm_key）")
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-912-UC", state="downloaded", hash="h" * 40, source="plugin")
        assert engine.duplicate_reason("IPZZ-912", "sub")

    def test_check_skips_number_sub_order(self, tasks_mod, store_mod, tmp_path):
        """端到端：订阅巡检里番号订阅已在库 → 不下单（任务表为空）。"""
        engine, store, _, _ = make_engine(
            tasks_mod, store_mod, tmp_path, library={"IPZZ961"})
        store.sub_add("number", "IPZZ-961", {})
        result = engine.check()
        assert result["limited"] is False
        assert store.task_list() == []
        assert "IPZZ-961" in store.known_all()

    def test_check_actor_skips_downloaded_number(self, tasks_mod, store_mod, tmp_path):
        """端到端：演员订阅命中新片、但那片子已经下过 → 只记 known，不下单。"""
        engine, store, _, _ = make_engine(
            tasks_mod, store_mod, tmp_path,
            movies=[{"number": "IPZZ-961", "cover_url": "http://img/1.jpg"}])
        store.download_upsert("IPZZ-961", state="downloaded", hash="h" * 40, source="plugin")
        store.sub_add("actor", "某演员", {})
        engine.check()
        assert store.task_list() == []
        assert "IPZZ-961" in store.known_all()


# ---------- 「不要了」三出口 ----------


class TestCancelAll:
    """`cancel_all()`：四个步骤都要真的被执行。"""

    def test_four_steps_all_run(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40,
                              actor="某演员", source="plugin")
        seed(store, make_entry())
        sid = store.sub_add("number", "IPZZ-961", {})
        store.sub_add("actor", "某演员", {})
        result = engine.cancel_all("IPZZ-961")
        assert result["ok"] is True and result["error"] == ""
        assert set(result["steps"]) == {"torrent", "ledger", "sub", "known"}
        assert all(step["ok"] for step in result["steps"].values())
        # ① 下载器种子（不动磁盘文件）
        assert chain.removed == [(["h" * 40], False)]
        # ② 台账打墓碑
        assert ledger_row(store) is None
        assert store.download_list(sources=["plugin"]) == []
        # ③ 订阅（番号 + 演员两条）
        assert [s["name"] for s in store.sub_list()] == []
        assert sid                      # 番号订阅确实建过（不然上面那条断言是空转）
        # ④ known
        assert "IPZZ-961" in store.known_all()

    def test_cancel_sub_false_keeps_subscriptions(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        seed(store, make_entry())
        store.sub_add("number", "IPZZ-961", {})
        result = engine.cancel_all("IPZZ-961", cancel_sub=False)
        assert result["steps"]["sub"]["ok"] is True
        assert "跳过" in result["steps"]["sub"]["detail"]
        assert [s["name"] for s in store.sub_list()] == ["IPZZ-961"]

    def test_missing_number_is_reported(self, tasks_mod, store_mod, tmp_path):
        engine, _, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        result = engine.cancel_all("   ")
        assert result["ok"] is False and result["error"]

    def test_steps_are_independent(self, tasks_mod, store_mod, tmp_path):
        """删种子失败不该拦住台账与订阅的清理（用户点了「不要了」，最要紧的是别回来）。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        store.sub_add("number", "IPZZ-961", {})
        chain.remove_boom = RuntimeError("下载器 500")
        result = engine.cancel_all("IPZZ-961")
        assert result["ok"] is False
        assert result["steps"]["torrent"]["ok"] is False
        assert "下载器 500" in result["error"]
        assert result["steps"]["ledger"]["ok"] is True
        assert result["steps"]["sub"]["ok"] is True
        assert result["steps"]["known"]["ok"] is True
        assert store.sub_list() == [] and "IPZZ-961" in store.known_all()

    def test_hash_already_gone_counts_as_done(self, tasks_mod, store_mod, tmp_path):
        """qB 对不存在的 id 回 False：复查发现"下载器里已经没有它了"就算达成目标。"""
        engine, store, chain, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", hash="h" * 40, source="plugin")
        chain.remove_result = False
        chain.torrents = []
        result = engine.cancel_all("IPZZ-961")
        assert result["steps"]["torrent"]["ok"] is True
        assert "已经没有" in result["steps"]["torrent"]["detail"]


# ---------- Tier 1 / Tier 2 挂点 ----------


class TestScrapeTick:
    """`_scrape_tick()`：只取不刮，`scraper.py` 缺位时不许炸。"""

    def test_empty_queue_is_noop(self, tasks_mod, store_mod, tmp_path):
        engine, _, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        assert engine._scrape_tick() == {"tier1": 0, "tier2": 0, "scraper": False, "error": ""}

    def test_due_tier1_is_picked_without_scraper(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.meta_upsert("IPZZ961", display_number="IPZZ-961",
                          next_retry_at="2020-01-01 00:00:00")
        result = engine._scrape_tick()
        assert result["tier1"] == 1
        assert result["scraper"] is False            # scraper.py 还没落地
        assert result["error"] == "scraper 未落地"    # 延迟导入被 ImportError 兜住了

    def test_tier2_picks_never_scraped(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        store.meta_upsert("IPZZ961", display_number="IPZZ-961")
        assert engine._scrape_tick()["tier2"] == 1

    def test_check_calls_the_tick_even_without_subs(self, tasks_mod, store_mod, tmp_path):
        """挂点必须在 `check()` 最前面：没有订阅时定时任务也要照跑。"""
        engine, _, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        calls = []
        engine._scrape_tick = lambda: calls.append(1) or {}
        result = engine.check()
        assert result["message"] == "没有可检查的订阅"
        assert calls == [1]

    def test_missing_meta_due_is_survivable(self, tasks_mod, store_mod, tmp_path, monkeypatch):
        """S1 的 `meta_due()` 万一没落地，定时任务只能记日志，不能抛。"""
        engine, store, _, _ = make_engine(tasks_mod, store_mod, tmp_path)
        monkeypatch.setattr(store_mod.Store, "meta_due", None, raising=False)
        assert engine._scrape_tick()["error"] == ""
        assert engine._meta_due(1) == []


# ---------- 限流政策（不能被这次改动放宽） ----------


class TestPolicyUntouched:
    """v4.1 的改动不许把用户点名要的限流参数放宽（AGENTS.md §5）。"""

    def test_rule_still_clamped(self, tasks_mod):
        rule = tasks_mod.merge_rule({"maxPerDay": 100, "minIntervalMin": 1})
        assert rule["maxPerDay"] <= tasks_mod.POLICY_MAX_PER_DAY
        assert rule["minIntervalMin"] >= tasks_mod.POLICY_MIN_INTERVAL_MIN

    def test_manual_rule_accepts_tightening(self, tasks_mod):
        rule = tasks_mod.merge_rule({"maxPerDay": 2, "minIntervalMin": 480})
        assert rule["maxPerDay"] == 2 and rule["minIntervalMin"] == 480
