"""限流守卫（执行方案 §8.2，参数不得放宽）：

- 订阅检查：每天 ≤ 配置上限（默认 6 次，全局含手动）、两次间隔 ≥ 240 分钟；
- 站点搜索：先搜优先站点，命中即停；站点之间串行并间隔 3-8 秒；全局 ≤ 1 请求/秒；
- 单站上限：≤ 10 次/小时；站点返回 403/429 → 该站冷却 24 小时且不重试。

计数落在插件自有 kv 表（随 /vol3 卷持久化），进程重启不丢限流状态。
"""

import random
import time
from typing import TYPE_CHECKING, Any, Tuple

if TYPE_CHECKING:  # 仅用于类型标注：运行时不需要导入 Store，便于单测独立加载本模块
    from .store import Store

GLOBAL_RPS = 1.0          # 全局最小请求间隔（秒）
SITE_GAP_MIN = 3.0        # 站点之间最小间隔
SITE_GAP_MAX = 8.0        # 站点之间最大间隔
SITE_HOURLY_MAX = 10      # 单站每小时上限
SITE_COOLDOWN_HOURS = 24  # 403/429 冷却时长

_last_request = 0.0


class RateLimiter:
    """把执行方案 §8.2 的限流规则集中到一处，便于审计。"""

    def __init__(self, store: "Store"):
        self.store = store

    # ---------- 全局请求节流 ----------

    def throttle(self) -> None:
        """全局 ≤1 请求/秒：必要时 sleep 到下一个可用窗口。"""
        global _last_request
        now = time.time()
        wait = GLOBAL_RPS - (now - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.time()

    def site_gap(self) -> None:
        """站点之间随机间隔 3-8 秒（防触发站点防爬）。"""
        time.sleep(random.uniform(SITE_GAP_MIN, SITE_GAP_MAX))

    # ---------- 订阅检查 ----------

    def check_allowed(self, max_per_day: int, min_interval_min: int) -> Tuple[bool, str]:
        """判断此刻能否执行订阅检查，返回（是否允许, 原因）。"""
        today = time.strftime("%Y-%m-%d")
        count = int(self.store.kv_get(f"subcheck:count:{today}", 0) or 0)
        if count >= int(max_per_day or 6):
            return False, f"今天已检查 {count} 次，达到上限 {max_per_day} 次/天"
        last = float(self.store.kv_get("subcheck:last", 0) or 0)
        if last:
            passed_min = (time.time() - last) / 60.0
            if passed_min < float(min_interval_min or 240):
                remain = int(float(min_interval_min or 240) - passed_min)
                return False, f"距上次检查仅 {int(passed_min)} 分钟，需间隔 ≥{min_interval_min} 分钟（还需 {remain} 分钟）"
        return True, ""

    def note_check(self) -> None:
        """记录一次成功的订阅检查。"""
        today = time.strftime("%Y-%m-%d")
        key = f"subcheck:count:{today}"
        count = int(self.store.kv_get(key, 0) or 0) + 1
        self.store.kv_set(key, count, ttl=86400 * 2)
        self.store.kv_set("subcheck:last", time.time())

    # ---------- 站点搜索 ----------

    def site_available(self, site_name: str) -> Tuple[bool, str]:
        """站点是否可用：先看 403/429 冷却，再看每小时次数上限。"""
        until = float(self.store.kv_get(f"site:cold:{site_name}", 0) or 0)
        if until > time.time():
            left = int((until - time.time()) / 60)
            return False, f"{site_name} 处于冷却中（约 {left} 分钟后恢复）"
        hour = time.strftime("%Y-%m-%d %H")
        used = int(self.store.kv_get(f"site:used:{site_name}:{hour}", 0) or 0)
        if used >= SITE_HOURLY_MAX:
            return False, f"{site_name} 本小时已达 {SITE_HOURLY_MAX} 次上限"
        return True, ""

    def note_site_search(self, site_name: str) -> None:
        """记录一次站点搜索。"""
        hour = time.strftime("%Y-%m-%d %H")
        key = f"site:used:{site_name}:{hour}"
        self.store.kv_set(key, int(self.store.kv_get(key, 0) or 0) + 1, ttl=7200)

    def site_cooldown(self, site_name: str) -> None:
        """站点被防爬（403/429）时冷却 24 小时。"""
        self.store.kv_set(f"site:cold:{site_name}", time.time() + SITE_COOLDOWN_HOURS * 3600,
                          ttl=SITE_COOLDOWN_HOURS * 3600 + 60)

    def state(self) -> dict:
        """返回当前限流状态，供界面展示。"""
        today = time.strftime("%Y-%m-%d")
        return {
            "checked_today": int(self.store.kv_get(f"subcheck:count:{today}", 0) or 0),
            "last_check": float(self.store.kv_get("subcheck:last", 0) or 0),
            "global_rps": GLOBAL_RPS,
            "site_hourly_max": SITE_HOURLY_MAX,
        }


def is_antibot_error(text: Any) -> bool:
    """判断异常文本是否属于站点防爬（403/429/频繁）。"""
    low = str(text or "").lower()
    return any(k in low for k in ("403", "429", "too many", "频繁", "forbidden", "rate limit"))
