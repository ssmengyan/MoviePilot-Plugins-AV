"""订阅命中自动下载的单测（0.9.1，2026-10-27 用户反馈）。

用户原话：「订阅规则中已开启『命中后自动下载』，但搜索到资源后并未自动执行下载，存在逻辑问题」。

根因（`tasks._after_task()`）：「有没有得下」的判据与 `download()` 真会挑哪一条不一致 ——

- `_after_task()` 旧写法：`best = 第一条 pass 的候选`；
- `download()` 不传站点时：`picked` 优先，其次"第一条 pass 的候选"。

PT 命中时 `scoring.rank_candidates()` 会给最高分那条打 `picked`，两边一致；
但 **PT 全被淘汰、只剩 BT 兜底行** 时，BT 行带 `pass=true` 却**不会**有 `picked`
（`picked` 只在 PT 段里选）。于是 `_after_task()` 认为"有得下"、进去 `download()`，
`download()` 回「该任务没有可下载的候选」，自动下载落空、任务停在「待确认」。

这里钉住五件事：

1. 自动下载真的会下单（PT 命中 / 只有 BT 兜底两条路）；
2. `picked` 不是第一条 pass 候选时，挑的是 `picked` 那条（与 `download()` 一致）；
3. 一条合格候选都没有时**不**调 `download()`，只发「发现候选，等你确认」；
4. `trigger=notify` 时一个字都不下（老行为不许被"顺手统一"改掉）；
5. `build_task()` 的 `auto` 参数默认按规则自己判（任务卡上那句话要准）。
"""


class _Chain:
    def __init__(self):
        self.calls = []

    def download(self, **kwargs):
        self.calls.append(kwargs)
        return ("qb", "f" * 40, "", "添加下载成功")


class _Plugin:
    def __init__(self):
        self.chain = _Chain()
        self._cli = _CLI()

    def cli(self):
        """`_check_actor()` 里写的是 `self.plugin.cli().actor(...)`（方法，不是属性）。"""
        return self._cli

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

    def image_url(self, url):
        return str(url or "")


class _CLI:
    """javdb-cli 替身：只实现 `_check_actor()` 会调的 `actor()`。"""

    def __init__(self):
        self.movies = [{"number": "IPZZ-961", "cover_url": ""}]

    def actor(self, name, page=1, limit=50):
        return {"movies": list(self.movies) if page == 1 else []}


class _Notifier:
    def __init__(self):
        self.notices = []

    def _push(self, title, body=""):
        notice = {"title": title, "body": body}
        self.notices.append(notice)
        return notice

    def info(self, title, body=""):
        return self._push(title, body)

    def download_start(self, number, cand, image=""):
        return self._push("开始下载", number)

    def candidate_ready(self, number, count):
        return self._push("发现候选，等你确认", f"{number} · {count} 个结果")

    def sub_hit_number(self, number):
        return self._push("订阅命中，开始搜索", f"番号 {number}")

    def sub_new_actor(self, actor, number):
        return self._push("订阅命中新片", f"{actor} 新作 {number}")

    def limited(self, reason):
        return self._push("检查被限流", reason)


class _Searcher:
    def resolve(self, content, site):
        return str(content or ""), ""


class _Limiter:
    """限流器替身：永远放行、只记次数（`check()` 会问它两件事）。"""

    def __init__(self):
        self.checks = 0

    def check_allowed(self, max_per_day, min_interval):
        return True, ""

    def note_check(self):
        self.checks += 1


def _engine(tasks_mod, store_mod, tmp_path):
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    plugin = _Plugin()
    notifier = _Notifier()
    limiter = _Limiter()
    engine = tasks_mod.TaskEngine(plugin, store, limiter, notifier)
    engine.searcher = _Searcher()
    return engine, store, plugin.chain, notifier


def _cand(site="馒头", src="PT", pas=True, picked=True, score=80):
    return {
        "src": src, "site": site, "spec": "1080p / H264", "res": "1080p", "cnsub": True,
        "uncensored": False, "size": "1.2 GB", "seeders": 20, "free": False,
        "pref": site == "馒头", "group": "", "title": "XXX-001", "score": score,
        "pass": pas, "picked": picked, "breakdown": "",
        "_enclosure": "http://site/download/1" if src == "PT" else "",
        "_site_name": site, "_page_url": "", "adapter": "",
        **({"hash": "a" * 40} if src == "BT" else {}),
    }


def _rule(**overrides):
    base = {
        "res": "1080p", "mustCnsub": False, "preferUncensored": True, "allow4k": True,
        "minSeeders": 3, "sites": [], "prefSites": [], "btFallback": True,
        "trigger": "auto", "maxPerDay": 6, "minIntervalMin": 240,
        "savePath": "", "category": "avi", "downloader": "",
    }
    base.update(overrides)
    return base


def _stub(engine, cands):
    engine.search_candidates = lambda keyword, rule, only_sites=None: (list(cands), [])


# ---------- 1. 自动下载真的会下单 ----------


class TestAutoDownload:
    def test_pt_hit_downloads(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        task = engine.build_task("IPZZ-961", rule=_rule(), source="sub")
        engine._after_task(task, {}, _rule())
        assert len(chain.calls) == 1
        assert store.task_get(task["id"])["state"] == "pushed"

    def test_only_bt_fallback_still_downloads(self, tasks_mod, store_mod, tmp_path):
        """报到的那条：PT 全淘汰、只剩 BT 兜底行 → 旧写法会落空（"该任务没有可下载的候选"）。"""
        engine, store, chain, notifier = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand(site="馒头", pas=False, picked=False),
                       _cand(site="BT 公网", src="BT", pas=True, picked=False)])
        task = engine.build_task("IPZZ-961", rule=_rule(), source="sub")
        notices = engine._after_task(task, {}, _rule())
        assert len(chain.calls) == 1
        assert "magnet:?xt=urn:btih:" in str(chain.calls[0]["content"])
        assert store.task_get(task["id"])["state"] == "pushed"
        assert [n["title"] for n in notices] == ["开始下载"]

    def test_picks_the_picked_candidate_not_the_first_pass(self, tasks_mod, store_mod, tmp_path):
        """与 `download()` 同一判据：`picked` 在第二条时也挑它，不是"第一条 pass"。"""
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        first = _cand(site="Rousi", picked=False, score=70)
        first["_enclosure"] = "http://rousi/download/2"
        pick = _cand(site="馒头", picked=True, score=90)
        _stub(engine, [first, pick])
        task = engine.build_task("IPZZ-961", rule=_rule(), source="sub")
        engine._after_task(task, {}, _rule())
        assert len(chain.calls) == 1
        assert "download/1" in str(chain.calls[0]["content"])


# ---------- 2. 没得下时不瞎调 download ----------


class TestNoCandidate:
    def test_no_pass_candidate_does_not_call_download(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand(pas=False, picked=False)])
        task = engine.build_task("IPZZ-961", rule=_rule(), source="sub")
        notices = engine._after_task(task, {}, _rule())
        assert chain.calls == []
        assert store.task_get(task["id"])["state"] == "await"
        assert [n["title"] for n in notices] == ["发现候选，等你确认"]

    def test_empty_cands_does_not_call_download(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [])
        task = engine.build_task("IPZZ-961", rule=_rule(), source="sub")
        engine._after_task(task, {}, _rule())
        assert chain.calls == []

    def test_notify_rule_never_downloads(self, tasks_mod, store_mod, tmp_path):
        """「仅通知」不许被"顺手统一"成自动下载。"""
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        rule = _rule(trigger="notify")
        task = engine.build_task("IPZZ-961", rule=rule, source="sub")
        notices = engine._after_task(task, {}, rule)
        assert chain.calls == []
        assert store.task_get(task["id"])["state"] == "await"
        assert [n["title"] for n in notices] == ["发现候选，等你确认"]


# ---------- 3. build_task 的 auto 归一 ----------


class TestBuildTaskAuto:
    def test_auto_defaults_to_rule_trigger(self, tasks_mod, store_mod, tmp_path):
        engine, store, _, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        auto_task = engine.build_task("IPZZ-961", rule=_rule(trigger="auto"), source="sub")
        notice_task = engine.build_task("IPZZ-962", rule=_rule(trigger="notify"), source="sub")
        assert auto_task["auto"] is True
        assert notice_task["auto"] is False

    def test_manual_search_keeps_auto_false_by_default(self, tasks_mod, store_mod, tmp_path):
        """站点搜索 / 手动检索不显式给 auto → 任务卡上不画"订阅为自动下载"那句。"""
        engine, store, _, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        task = engine.build_task("IPZZ-961", rule=_rule(trigger="auto"), source="manual")
        assert task["auto"] is True      # 按规则（trigger=auto）；站点搜索页仍可读它做提示


# ---------- 4. 端到端：订阅检查这条真路 ----------


class TestCheckEndToEnd:
    """走 `engine.check()`（不是直接调 `_after_task`），确认订阅这条路真的会下单。

    这条是用户报的原始场景：「订阅规则里已开启『命中后自动下载』，但搜索到资源后并未自动
    执行下载」。直接调 `_after_task` 的用例挡不住"调用方传错了规则"这类回归，所以这里
    从 `store.sub_add()` 建订阅、再 `check()`，全链路只经过真实代码。
    """

    def test_number_sub_with_auto_rule_downloads(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        store.sub_add("number", "IPZZ-961", _rule(trigger="auto"))
        result = engine.check()
        assert result["limited"] is False
        assert len(chain.calls) == 1
        pushed = [t for t in store.task_list() if t.get("state") == "pushed"]
        assert len(pushed) == 1

    def test_number_sub_with_notify_rule_waits(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        store.sub_add("number", "IPZZ-961", _rule(trigger="notify"))
        engine.check()
        assert chain.calls == []
        assert [t.get("state") for t in store.task_list()] == ["await"]

    def test_actor_sub_with_auto_rule_downloads(self, tasks_mod, store_mod, tmp_path):
        """演员订阅那条路（`_check_actor`）同样要自动下载。"""
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        store.sub_add("actor", "某演员", _rule(trigger="auto"))
        engine.check()
        assert len(chain.calls) == 1

    def test_rule_snapshot_is_what_check_reads(self, tasks_mod, store_mod, tmp_path):
        """订阅存的是**创建那一刻的规则快照**：这就是"设置台改了自动下载、旧订阅不生效"的机制。

        钉住它是为了让"界面新建订阅时必须显式传当前规则"这条纪律有据可依
        （`usePluginStore.subscribeAndSearch()` 的 ⚠️ 注释）—— 不是让人去改快照语义。
        """
        engine, store, chain, _ = _engine(tasks_mod, store_mod, tmp_path)
        _stub(engine, [_cand()])
        store.sub_add("number", "IPZZ-961", _rule(trigger="notify"))
        engine.check()
        assert chain.calls == []                     # 快照是 notify
        # 把同一条订阅的规则改成 auto（等价于"重新订阅一次、带上此刻的规则"）。
        # 上一次检查落了一条 await 任务，查重会拦下这一单 —— 先把它清掉。
        for task in store.task_list():
            store.task_set_state(str(task.get("id") or ""), "canceled")
        store.sub_add("number", "IPZZ-961", _rule(trigger="auto"))
        engine.check()
        assert len(chain.calls) == 1
