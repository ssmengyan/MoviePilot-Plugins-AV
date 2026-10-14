"""限流（0.8.0 / P1-2）：每 host 平滑漏桶 + 单一执行点 + 被拦后的 host 冷却。

节奏类断言用**假钟 + 假睡**（真实 `time.monotonic` / `sleep` 得不出确定结论）：
`RateLimiter(now=…, sleep=…)` 两个都能注入，这是它唯一的测试口子。
"""

from __future__ import annotations

import pytest


class FakeClock:
    """可推进的假钟 + 假睡：`sleep(x)` 就是把钟往前拨 x。"""

    def __init__(self) -> None:
        self.t = 1000.0
        self.slept: list = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(round(float(seconds), 3))
        self.t += max(0.0, float(seconds))


def make_limiter(mod, **kwargs):
    clock = FakeClock()
    limiter = mod.RateLimiter(kwargs.pop("store", None), now=clock.now, sleep=clock.sleep,
                              **kwargs)
    return limiter, clock


# --- 每 host 平滑漏桶 -------------------------------------------------------

def test_wait_host_paces_each_host(ratelimit_mod):
    """容量 1 的平滑桶：同一 host 相邻两次至少隔一个间隔，**不同 host 互不影响**。"""
    limiter, clock = make_limiter(ratelimit_mod)
    assert limiter.wait_host("a.test") == 0.0            # 第一次不等
    wait = limiter.wait_host("a.test")                   # 立刻再来一次 → 等满一个间隔
    assert wait == pytest.approx(limiter.default_rate_limit, abs=0.01)
    assert clock.slept == [pytest.approx(limiter.default_rate_limit, abs=0.01)]
    assert limiter.wait_host("b.test") == 0.0            # 另一个 host 不受影响


def test_wait_host_no_burst(ratelimit_mod):
    """连续 5 次请求：每次都被推到上个请求之后 ≥间隔（没有突发窗口）。"""
    limiter, clock = make_limiter(ratelimit_mod, default_rate_limit=1.0)
    for _ in range(5):
        limiter.wait_host("a.test")
    assert clock.t == pytest.approx(1000.0 + 4 * 1.0, abs=0.01)


def test_explicit_interval_wins(ratelimit_mod):
    """调用方显式给的间隔优先（javtxt 的 `2.0` 就是这么传的）。"""
    limiter, _clock = make_limiter(ratelimit_mod, default_rate_limit=10.0)
    limiter.wait_host("a.test", interval=0.5)
    assert limiter.wait_host("a.test", interval=0.5) == pytest.approx(0.5, abs=0.01)


def test_interval_priority_host_then_site_then_default(ratelimit_mod):
    limiter, _clock = make_limiter(ratelimit_mod, default_rate_limit=2.0,
                                   rate_limits={"a.test": 5, "javtxt": 9})
    assert limiter.interval_for("a.test", "javtxt") == 5      # host 更精确，压过站点
    assert limiter.interval_for("b.test", "javtxt") == 9      # 没有 host 配置 → 用站点
    assert limiter.interval_for("b.test", "other") == 2.0     # 都没有 → 默认


def test_reconfigure_is_hot(ratelimit_mod):
    """配置热更新：**间隔归零/非法一律不当成"更快"**（关掉限流是政策不允许的）。"""
    limiter, _clock = make_limiter(ratelimit_mod, default_rate_limit=2.0)
    limiter.reconfigure(default_rate_limit=6, rate_limits={"a.test": 3, "bad": 0})
    assert limiter.default_rate_limit == 6
    assert limiter.rate_limits == {"a.test": 3}
    limiter.reconfigure(default_rate_limit=0, rate_limits={"a.test": "abc"})
    assert limiter.default_rate_limit == 6                   # 0 被拒，保持原值
    assert limiter.rate_limits == {}


def test_interval_from_string_values(ratelimit_mod):
    """设置台存的是字符串（`"4"`），间隔要能吃字符串。"""
    limiter, _clock = make_limiter(ratelimit_mod, default_rate_limit="3", rate_limits={"a": "4"})
    assert limiter.interval_for("a") == 4
    assert limiter.interval_for("b") == 3


# --- 被拦 → 按 host 冷却 ---------------------------------------------------

def test_cooling_round_trip(ratelimit_mod):
    limiter, _clock = make_limiter(ratelimit_mod)
    assert limiter.cooling("a.test") == 0.0
    limiter.note_blocked("a.test", hours=1, reason="cloudflare_challenge")
    assert limiter.cooling("a.test") == pytest.approx(3600, abs=5)
    assert limiter.blocked_reason("a.test") == "cloudflare_challenge"
    assert limiter.cooling("b.test") == 0.0                  # 按 host，不串
    assert limiter.cooling("") == 0.0


def test_cooling_uses_store_when_given(ratelimit_mod, store_mod, tmp_path):
    """有 store 时冷却落 kv（跨重启保持）；`hours` 可调。"""
    store = store_mod.Store(db_path=tmp_path / "r.db")
    store.init()
    limiter = ratelimit_mod.RateLimiter(store)
    limiter.note_blocked("a.test", hours=2, reason="age_verification")
    assert limiter.cooling("a.test") == pytest.approx(7200, abs=5)
    assert store.kv_get("host:cold:a.test", 0) > 0
    assert limiter.blocked_reason("a.test") == "age_verification"


# --- 订阅检查的政策夹取（不许放宽） ----------------------------------------

def test_policy_clamp_still_holds(ratelimit_mod):
    """★ 用户明确定的政策：每天 ≤6 次、间隔 ≥240 分钟 —— 规则里写 100 / 1 也不放行。"""
    limiter = ratelimit_mod.RateLimiter(None, now=lambda: 1000.0, sleep=lambda _s: None)
    assert limiter.check_allowed(100, 1) == (True, "")       # 还没有记录 → 允许
    for _ in range(6):
        limiter.note_check()
    allowed, why = limiter.check_allowed(100, 1)
    assert allowed is False and "达到上限 6 次/天" in why
    # 用户把间隔写成 1 分钟：政策值 240 分钟仍然生效（2026-10-13 修的就是这个洞）
    limiter2 = ratelimit_mod.RateLimiter(None, now=lambda: 1000.0, sleep=lambda _s: None)
    limiter2.note_check()
    allowed, why = limiter2.check_allowed(100, 1)
    assert allowed is False and "间隔 ≥240 分钟" in why


def test_store_optional_memory_state(ratelimit_mod):
    """`store=None` 退化成内存态（单测、启动早期都要能用）。"""
    limiter = ratelimit_mod.RateLimiter(None)
    limiter.note_check()
    assert limiter.state()["checked_today"] == 1
    limiter.site_cooldown("javdb")
    ok, why = limiter.site_available("javdb")
    assert ok is False and "冷却" in why


def test_state_exposes_rate_config(ratelimit_mod):
    limiter = ratelimit_mod.RateLimiter(None, default_rate_limit=3, rate_limits={"a": 4})
    state = limiter.state()
    assert state["default_rate_limit"] == 3 and state["rate_limits"] == {"a": 4}
