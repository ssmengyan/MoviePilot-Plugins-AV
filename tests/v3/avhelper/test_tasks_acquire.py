"""「下载该影片」的判定、文案与编排单测（0.6.0）。

起因（2026-10-13 用户报）：规则里「命中之后」选的是**自动下载**，但详情页那颗
「🔎 搜索 PT 站」点下去，候选只出现在「任务」页的待确认里，必须手动挑一条再点「下载」。
根因是接口层恒传 `auto=False`，规则里的 `trigger` 对手动这条路从来没生效过。

这里钉住四件事：

1. **判定矩阵**（`rule_verdict`）：PT 中没中、BT 兜底试没试/中没中、卡片该打什么标记；
2. **提示文案**（`acquire_feedback`）：「PT 站未找到资源」「该资源在所有源中均未找到」
   两句逐字不变 —— 它们是用户点名要的文案；
3. **编排**（`TaskEngine.acquire`）：`trigger=auto` 时当场下单、`notify` 时只落待确认，
   自动下载失败也要有明确提示（不能静默把任务留在待确认里）；
4. **限流政策**（`merge_rule` / `RateLimiter.check_allowed`）：规则里那两个字段用户可写，
   但每天 ≤6 次、间隔 ≥240 分钟这两条不许被界面上的数字绕过。
"""

import pytest


class _Chain:
    """宿主下载链替身：`download()` 回一个四元组，第 2 位是种子 Hash。"""

    def __init__(self, result=("qb", "f" * 40, "", "添加下载成功"), boom=None):
        self.result = result
        self.boom = boom
        self.calls = []

    def download(self, **kwargs):
        self.calls.append(kwargs)
        if self.boom:
            raise self.boom
        return self.result


class _Plugin:
    """插件替身：只实现 `tasks.py` 走到的那几个方法。"""

    def __init__(self, chain=None):
        self.chain = chain or _Chain()

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


class _Notifier:
    def __init__(self):
        self.notices = []

    def info(self, title, body=""):
        self.notices.append((title, body))
        return {"title": title, "body": body}

    def download_start(self, number, cand, image=""):
        notice = {"title": "开始下载", "body": number}
        self.notices.append((notice["title"], number))
        return notice


class _Searcher:
    """站点检索替身：`resolve()` 原样放行（单测不碰两段式换票）。"""

    def resolve(self, content, site):
        return str(content or ""), ""


def make_engine(tasks_mod, store_mod, tmp_path, chain=None):
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    chain = chain or _Chain()
    engine = tasks_mod.TaskEngine(_Plugin(chain), store, None, _Notifier())
    engine.searcher = _Searcher()
    return engine, store, chain


def cand(site="馒头", src="PT", res="1080p", cnsub=True, seeders=20, pas=True, score=80):
    """一条候选：字段名照抄 `scoring.candidate_from_torrent()` 的产物。"""
    return {
        "src": src, "site": site, "spec": f"{res} / H264", "res": res, "cnsub": cnsub,
        "uncensored": False, "size": "1.2 GB", "seeders": seeders, "free": False,
        "pref": site == "馒头", "group": "", "title": f"XXX-001 {res}", "score": score,
        "pass": pas, "breakdown": "", "picked": pas,
        "_enclosure": "http://site/download/1" if src == "PT" else "",
        "_site_name": site, "_page_url": "", "adapter": "",
    }


def bt_cand(pas=True):
    """BT 兜底候选：没有 `_enclosure`，只有 40 位磁力 Hash（`download()` 自己拼 magnet）。"""
    out = cand(site="BT 公网", src="BT", res="1080p", cnsub=True, seeders=0, pas=pas)
    out["hash"] = "a" * 40
    out["group"] = "BT 匿名发布"
    return out


def rule(**overrides):
    base = {
        "res": "1080p", "mustCnsub": False, "preferUncensored": True, "allow4k": True,
        "minSeeders": 3, "sites": [], "prefSites": [], "btFallback": True,
        "trigger": "notify", "maxPerDay": 6, "minIntervalMin": 240,
        "savePath": "", "category": "avi", "downloader": "",
    }
    base.update(overrides)
    return base


def stub_search(engine, cands, notes=None):
    """把引擎的搜种换成固定结果（`acquire()` 只管判定与编排，站点检索另有单测）。"""
    engine.search_candidates = lambda keyword, rule, only_sites=None: (list(cands), list(notes or []))


# ---------- 1. 判定矩阵 ----------


class TestRuleVerdict:
    def test_pt_hit_skips_bt(self, tasks_mod):
        v = tasks_mod.rule_verdict([cand()], rule())
        assert (v["pt"], v["bt"], v["pending"]) == ("hit", "skipped", "")

    def test_pt_miss_with_fallback_off_is_pt_only(self, tasks_mod):
        v = tasks_mod.rule_verdict([cand(pas=False, seeders=0)], rule(btFallback=False))
        assert (v["pt"], v["bt"], v["pending"]) == ("miss", "off", "pt-only")

    def test_pt_miss_and_bt_hit_has_no_mark(self, tasks_mod):
        v = tasks_mod.rule_verdict([bt_cand()], rule())
        assert (v["pt"], v["bt"], v["pending"]) == ("miss", "hit", "")

    def test_pt_miss_and_bt_miss_is_nothing_found(self, tasks_mod):
        v = tasks_mod.rule_verdict([], rule())
        assert (v["pt"], v["bt"], v["pending"]) == ("miss", "miss", "none")

    def test_bt_fallback_on_without_magnets_is_miss(self, tasks_mod):
        """兜底开着但 javdb 上没有磁力（候选里一条 BT 都没有）也算 miss。"""
        v = tasks_mod.rule_verdict([cand(pas=False, seeders=0)], rule(btFallback=True))
        assert (v["pt"], v["bt"], v["pending"]) == ("miss", "miss", "none")

    def test_pt_all_rejected_still_counts_as_miss(self, tasks_mod):
        """PT 搜到了但全被规则淘汰：仍算没找到（提示里会补一句"不满足规则"）。"""
        v = tasks_mod.rule_verdict([cand(pas=False, seeders=1)], rule(btFallback=False))
        assert v["pt"] == "miss"
        assert (v["pt_total"], v["pt_pass"]) == (1, 0)


# ---------- 2. 提示文案 ----------


class TestAcquireFeedback:
    @staticmethod
    def texts(toasts):
        return [t["text"] for t in toasts]

    def test_nothing_found_keeps_both_wording(self, tasks_mod):
        """用户点名要的两句文案，逐字不变，且顺序是「PT → 所有源」。"""
        task = {"cands": [], "number": "IPZZ-961"}
        toasts = tasks_mod.acquire_feedback(task, {"pt": "miss", "bt": "miss", "pending": "none"})
        assert self.texts(toasts)[:2] == ["PT 站未找到资源", "该资源在所有源中均未找到"]
        assert toasts[0]["level"] == "warning" and toasts[1]["level"] == "warning"
        assert "订阅该影片" in self.texts(toasts)[2]

    def test_fallback_off_says_pt_only(self, tasks_mod):
        toasts = tasks_mod.acquire_feedback({"cands": []}, {"pt": "miss", "bt": "off", "pending": "pt-only"})
        assert self.texts(toasts)[0] == "PT 站未找到资源"
        assert "PT/BT" not in self.texts(toasts)[0]      # 标记在卡片上，文案不重复
        assert "已放进「任务」页" in self.texts(toasts)[1]

    def test_rejected_candidates_get_a_second_line(self, tasks_mod):
        task = {"cands": [cand(site="馒头", pas=False), cand(site="Rousi", pas=False)]}
        toasts = tasks_mod.acquire_feedback(task, {"pt": "miss", "bt": "miss", "pending": "none"})
        assert "馒头、Rousi" in self.texts(toasts)[1]
        assert "2 条候选但不满足规则" in self.texts(toasts)[1]

    def test_downloaded_pt_reports_site_and_spec(self, tasks_mod):
        task = {"cands": [cand()]}
        result = {"ok": True, "site": "馒头", "spec": "1080p / H264"}
        toasts = tasks_mod.acquire_feedback(task, {"pt": "hit", "bt": "skipped", "pending": ""}, result)
        assert self.texts(toasts) == ["已提交下载", "馒头 · 1080p / H264 · 进度见「下载」页"]

    def test_downloaded_by_bt_says_so(self, tasks_mod):
        task = {"cands": [bt_cand()]}
        toasts = tasks_mod.acquire_feedback(task, {"pt": "miss", "bt": "hit", "pending": ""},
                                            {"ok": True, "site": "BT 公网", "spec": "1080p / H264"})
        assert self.texts(toasts) == ["PT 站未找到资源", "已用 BT 磁力兜底提交下载", "进度见「下载」页"]

    def test_pending_pt_hit_points_to_tasks_page(self, tasks_mod):
        toasts = tasks_mod.acquire_feedback({"cands": [cand(), cand()]},
                                            {"pt": "hit", "bt": "skipped", "pending": "", "pt_pass": 2})
        assert "已找到 2 个候选" in self.texts(toasts)[0]


# ---------- 3. 编排 ----------


class TestAcquire:
    def test_auto_downloads_best_candidate(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain = make_engine(tasks_mod, store_mod, tmp_path)
        stub_search(engine, [cand(score=90), cand(site="Rousi", score=70)])
        out = engine.acquire("IPZZ-961", rule=rule(trigger="auto"))
        assert out["outcome"] == "downloaded"
        assert len(chain.calls) == 1
        assert store.task_get(out["task"]["id"])["state"] == "pushed"
        assert out["hash"] == "f" * 40

    def test_notify_only_leaves_it_waiting(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain = make_engine(tasks_mod, store_mod, tmp_path)
        stub_search(engine, [cand()])
        out = engine.acquire("IPZZ-961", rule=rule(trigger="notify"))
        assert out["outcome"] == "pending"
        assert chain.calls == []
        assert store.task_get(out["task"]["id"])["state"] == "await"
        assert store.task_get(out["task"]["id"])["pending"] == ""

    def test_pt_miss_without_fallback_waits_marked_pt_only(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain = make_engine(tasks_mod, store_mod, tmp_path)
        stub_search(engine, [])
        out = engine.acquire("IPZZ-961", rule=rule(trigger="auto", btFallback=False))
        assert (out["outcome"], out["pt"], out["bt"], out["pending"]) == ("pending", "miss", "off", "pt-only")
        assert chain.calls == []
        assert store.task_get(out["task"]["id"])["pending"] == "pt-only"
        assert out["toasts"][0]["text"] == "PT 站未找到资源"

    def test_pt_miss_with_bt_hit_downloads_magnet(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain = make_engine(tasks_mod, store_mod, tmp_path)
        stub_search(engine, [bt_cand()])
        out = engine.acquire("IPZZ-961", rule=rule(trigger="auto", btFallback=True))
        assert out["outcome"] == "downloaded"
        assert out["bt"] == "hit"
        assert "magnet:?xt=urn:btih:" in str(chain.calls[0]["content"])

    def test_bt_miss_waits_marked_none(self, tasks_mod, store_mod, tmp_path):
        engine, store, chain = make_engine(tasks_mod, store_mod, tmp_path)
        stub_search(engine, [])
        out = engine.acquire("IPZZ-961", rule=rule(trigger="auto", btFallback=True))
        assert out["pending"] == "none"
        assert [t["text"] for t in out["toasts"]][:2] == ["PT 站未找到资源", "该资源在所有源中均未找到"]

    def test_download_failure_is_not_silent(self, tasks_mod, store_mod, tmp_path):
        """自动下载失败 → 任务照旧留在待确认，但必须有一条写明原因的提示。"""
        chain = _Chain(result=("qb", None, "", "下载器没接"))
        engine, store, _ = make_engine(tasks_mod, store_mod, tmp_path, chain)
        stub_search(engine, [cand()])
        out = engine.acquire("IPZZ-961", rule=rule(trigger="auto"))
        assert out["outcome"] == "pending"
        assert store.task_get(out["task"]["id"])["state"] == "await"
        assert any("自动下载失败" in t["text"] for t in out["toasts"])

    def test_task_carries_pending_mark_for_ui(self, tasks_mod, store_mod, tmp_path):
        """`build_task()` 落库的 pending 字段就是任务卡上那个标记（前端只读它）。"""
        engine, store, _ = make_engine(tasks_mod, store_mod, tmp_path)
        stub_search(engine, [])
        task = engine.build_task("IPZZ-961", rule=rule(btFallback=False))
        assert task["pending"] == "pt-only"
        assert store.task_get(task["id"])["pending"] == "pt-only"


# ---------- 4. 限流政策不许被规则绕过 ----------


class TestPolicyLimits:
    def test_merge_rule_clamps_to_policy(self, tasks_mod):
        merged = tasks_mod.merge_rule({"maxPerDay": 100, "minIntervalMin": 10})
        assert merged["maxPerDay"] == 6
        assert merged["minIntervalMin"] == 240

    def test_merge_rule_allows_tightening(self, tasks_mod):
        """只抬不降：想把间隔调更长（更保守）是允许的。"""
        assert tasks_mod.merge_rule({"minIntervalMin": 480})["minIntervalMin"] == 480

    def test_merge_rule_survives_junk(self, tasks_mod):
        merged = tasks_mod.merge_rule({"maxPerDay": "abc", "minIntervalMin": None})
        assert merged["maxPerDay"] == 6 and merged["minIntervalMin"] == 240

    def test_check_allowed_clamps_max_per_day(self, ratelimit_mod, store_mod, tmp_path):
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        limiter = ratelimit_mod.RateLimiter(store)
        store.kv_set("subcheck:count:" + __import__("time").strftime("%Y-%m-%d"), 6)
        allowed, why = limiter.check_allowed(100, 1)
        assert allowed is False
        assert "6 次/天" in why

    def test_check_allowed_clamps_min_interval(self, ratelimit_mod, store_mod, tmp_path):
        import time
        store = store_mod.Store(db_path=tmp_path / "avhelper.db")
        store.init()
        limiter = ratelimit_mod.RateLimiter(store)
        store.kv_set("subcheck:last", time.time() - 60)      # 一分钟前检查过
        allowed, why = limiter.check_allowed(6, 1)           # 规则里想放宽到 1 分钟
        assert allowed is False
        assert "≥240 分钟" in why


# ---------- 5. 分辨率策略真正生效（0.6.0 顺带修） ----------


class TestResolutionStrategy:
    def test_4k_first_puts_4k_ahead(self, scoring_mod):
        four_k = {"src": "PT", "site": "站", "res": "2160p", "cnsub": True, "pref": False,
                  "seeders": 20, "free": False}
        hd = {"src": "PT", "site": "站", "res": "1080p", "cnsub": True, "pref": False,
              "seeders": 20, "free": False}
        scoring_mod.score_candidate(four_k, rule(res="2160p"))
        scoring_mod.score_candidate(hd, rule(res="2160p"))
        assert four_k["score"] > hd["score"]
        assert "4K +30" in four_k["breakdown"]

    def test_only_4k_rejects_1080p(self, scoring_mod):
        hd = {"src": "PT", "site": "站", "res": "1080p", "cnsub": True, "pref": False,
              "seeders": 20, "free": False}
        scoring_mod.score_candidate(hd, rule(res="only4k"))
        assert hd["pass"] is False
        assert "仅 4K" in hd["breakdown"]

    def test_only_4k_keeps_4k(self, scoring_mod):
        four_k = {"src": "PT", "site": "站", "res": "2160p", "cnsub": True, "pref": False,
                  "seeders": 20, "free": False}
        scoring_mod.score_candidate(four_k, rule(res="only4k"))
        assert four_k["pass"] is True

    def test_default_strategy_unchanged(self, scoring_mod):
        """回归：默认「1080P 优先」的打分与老口径一字不差（+30 / 4K 择优 +16）。"""
        hd = {"src": "PT", "site": "站", "res": "1080p", "cnsub": True, "pref": False,
              "seeders": 20, "free": False}
        scoring_mod.score_candidate(hd, rule(res="1080p"))
        assert "1080P +30" in hd["breakdown"]
        four_k = {"src": "PT", "site": "站", "res": "2160p", "cnsub": True, "pref": False,
                  "seeders": 20, "free": False}
        scoring_mod.score_candidate(four_k, rule(res="1080p", allow4k=True))
        assert "4K 择优 +16" in four_k["breakdown"]
