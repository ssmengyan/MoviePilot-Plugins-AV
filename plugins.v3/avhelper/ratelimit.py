"""限流守卫（执行方案 §8.2，参数不得放宽）：

- 订阅检查：每天 ≤ 配置上限（默认 6 次，全局含手动）、两次间隔 ≥ 240 分钟；
- 站点搜索：先搜优先站点，命中即停；站点之间串行并间隔 3-8 秒；全局 ≤ 1 请求/秒；
- 单站上限：≤ 30 次/小时；站点返回 403/429 → 该站冷却 24 小时且不重试；
  **10 次/小时是旧值（2026-10-21 上调）**：手动点「下载该影片」也计数，批量洗版连点 10 部就
  打满，第 11 部起优先站被静默跳过、整单只剩 BT —— 用户实报「馒头明明有却搜不到」；
- **每 host 平滑漏桶**（0.8.0 / P1-2）：元数据取数（javtxt）也走这里 ——
  容量 1、**不允许突发**（突发才是反爬的触发条件）；间隔优先级
  `调用方显式 interval` > `rate_limits[host]` > `rate_limits[站点]` > `default_rate_limit`；
  被拦（CF/年龄墙/IP 封/429）时按 **host** 冷却（`BLOCK_COOLDOWN_HOURS`）——
  轮换域名的站换个域名也绕不过冷却，这是按站点名记冷却时漏掉的洞。

计数落在插件自有 kv 表（在数据根下持久化），进程重启不丢限流状态。
**`store=None` 时退化成进程内内存态**（单测与"还没接上 store"的启动早期都要能用）。
"""

import random
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

if TYPE_CHECKING:  # 仅用于类型标注：运行时不需要导入 Store，便于单测独立加载本模块
    from .store import Store

GLOBAL_RPS = 1.0          # 全局最小请求间隔（秒）
SITE_GAP_MIN = 3.0        # 站点之间最小间隔
SITE_GAP_MAX = 8.0        # 站点之间最大间隔
SITE_HOURLY_MAX = 30      # 单站每小时上限（2026-10-21 由 10 上调：10 次在批量洗版时会跳过优先站）
SITE_COOLDOWN_HOURS = 24  # 403/429 冷却时长
#: 默认请求间隔（秒）。**只作用于"调用方没给间隔"的那条路**：javtxt 的调用点仍显式传
#: `JAVTXT_MIN_INTERVAL=2.0`，所以这条默认值不会把既有节奏放松（P1-2 的硬纪律）。
DEFAULT_RATE_LIMIT = 2.0
#: 元数据源被拦后的冷却时长。**比 PT 侧的 24 小时短**：PT 是"今天别搜了"，
#: 元数据是"这个镜像先别打、别的源顶上"，6 小时足够错过一次风控窗口。
BLOCK_COOLDOWN_HOURS = 6

# 订阅检查的政策固定值（用户明确要求定的）：每天 ≤ 6 次、两次间隔 ≥ 240 分钟。
# 前端 `settingsPolicy.ts` 是同一对值的镜像；本模块是**唯一的执行点** —— 规则里的这两个
# 字段用户可写，`check_allowed()` 每次都再夹一遍（2026-10-13 修：早先界面能填 100，
# 写进规则后就真的按 100 放行）。
POLICY_MAX_PER_DAY = 6
POLICY_MIN_INTERVAL_MIN = 240

_last_request = 0.0


def _int_or(value: Any, default: int) -> int:
    """把规则里的数字字段转成整数，认不出来就用政策默认值（不抛异常）。"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float_or(value: Any, default: float) -> float:
    """同 `_int_or`，要浮点。**不接受 0/负数**（间隔归零等于关掉限流）。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _host_key(value: Any) -> str:
    """请求键统一成 **host**：调用方给完整 URL（javtxt 的镜像列表就是）或裸 host 都认。

    为什么必须统一：配置键（`rateLimits`）与冷却键都按 host 写，调用方却常常拿着
    `https://javtxt.com` 这种整串 —— 不归一就会得到"配置了却不生效""冷却记在另一个键上"。
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if "//" in text:
        try:
            return str(urlparse(text).hostname or text).lower()
        except Exception:                                       # pragma: no cover - 防御
            return text.lower()
    return text.rstrip("/").lower()


class RateLimiter:
    """把执行方案 §8.2 的限流规则集中到一处，便于审计。

    **唯一执行点**：站点搜索、元数据取数、订阅检查都从这里走。
    """

    def __init__(self, store: Optional["Store"] = None, *,
                 default_rate_limit: Any = None, rate_limits: Any = None,
                 now: Optional[Callable[[], float]] = None,
                 sleep: Optional[Callable[[float], None]] = None):
        self.store = store
        # `now` 默认 `time.monotonic`（间隔是**相对时间**，不受系统改钟影响）；
        # 两者都可注入，单测用假钟 + 假睡把节奏测成确定值。
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self._lock = threading.Lock()
        self._last: Dict[str, float] = {}
        self._memory: Dict[str, Any] = {}                 # store=None 时的内存态
        self.default_rate_limit = _float_or(default_rate_limit, DEFAULT_RATE_LIMIT)
        self.rate_limits: Dict[str, float] = {
            str(k): _float_or(v, 0.0) for k, v in (rate_limits or {}).items()
            if _float_or(v, 0.0) > 0
        }

    # ---------- 键值（store 缺失时退化成内存态） ----------

    def _kv_get(self, key: str, default: Any = None) -> Any:
        if self.store is None:
            return self._memory.get(key, default)
        return self.store.kv_get(key, default)

    def _kv_set(self, key: str, value: Any, ttl: int = 0) -> None:
        if self.store is None:
            self._memory[key] = value
            return
        self.store.kv_set(key, value, ttl=ttl)

    # ---------- 配置（热更新） ----------

    def reconfigure(self, *, default_rate_limit: Any = None, rate_limits: Any = None) -> None:
        """把设置台里当前的 `rateLimits` / `defaultRateLimit` 推给限流器。

        每次刮削前由 `__init__.scrape_opts()` 调一次 —— 配置改完不必重载插件，
        也**不需要**为它造第二个执行点。
        """
        if default_rate_limit is not None:
            self.default_rate_limit = _float_or(default_rate_limit,
                                                self.default_rate_limit or DEFAULT_RATE_LIMIT)
        if rate_limits is not None:
            with self._lock:
                self.rate_limits = {str(k): _float_or(v, 0.0)
                                    for k, v in (rate_limits or {}).items()
                                    if _float_or(v, 0.0) > 0}

    def interval_for(self, host: str = "", site: str = "") -> float:
        """该 host（或站点）的请求间隔：`rate_limits[host]` > `rate_limits[site]` > 默认。

        host 会归一成裸 hostname（`https://javtxt.com` → `javtxt.com`），所以配置键一律写域名。
        """
        for key in (_host_key(host), str(site or "").strip().lower()):
            if key and key in self.rate_limits:
                return self.rate_limits[key]
        return self.default_rate_limit or DEFAULT_RATE_LIMIT

    # ---------- 全局请求节流 ----------

    def throttle(self) -> None:
        """全局 ≤1 请求/秒：必要时 sleep 到下一个可用窗口。"""
        global _last_request
        now = time.time()
        wait = GLOBAL_RPS - (now - _last_request)
        if wait > 0:
            self._sleep(wait)
        _last_request = time.time()

    def site_gap(self) -> None:
        """站点之间随机间隔 3-8 秒（防触发站点防爬）。"""
        self._sleep(random.uniform(SITE_GAP_MIN, SITE_GAP_MAX))

    # ---------- 每 host 平滑漏桶（元数据取数也走这里） ----------

    def wait_host(self, host: str, *, site: str = "", interval: Any = None) -> float:
        """把「对 `host` 的下一次请求」推迟到距上次 ≥间隔；返回实际等待秒数。

        容量 1 的**严格平滑桶**（无突发）：一个 host 的相邻两次请求至少隔 `interval` 秒，
        间隔优先级见 `interval_for()`；调用方显式给了 `interval` 就以它为准
        （javtxt 的 `2.0` 就是这么传的）。
        """
        key = _host_key(host) or _host_key(site) or "?"
        gap = _float_or(interval, 0.0) or self.interval_for(host, site)
        wait = 0.0
        with self._lock:
            now = self._now()
            last = self._last.get(key)
            if last is not None:
                wait = max(0.0, gap - (now - last))
                if wait > 0:
                    self._sleep(wait)
            self._last[key] = self._now()
        return wait

    def last_seen(self, key: str) -> Optional[float]:
        """上次放行时刻（相对钟；给自检/排障看"这个 host 安静多久了"）。"""
        return self._last.get(str(key or ""))

    # ---------- 被拦 → 按 host 冷却 ----------

    def cooling(self, host: str) -> float:
        """该 host 还剩多少秒冷却（0 = 可用）。**按 host 判**（站点名会被轮换域名绕过）。"""
        name = _host_key(host)
        if not name:
            return 0.0
        until = _float_or(self._kv_get(f"host:cold:{name}", 0), 0.0)
        return max(0.0, until - time.time())

    def note_blocked(self, host: str, *, hours: Any = None, reason: str = "") -> None:
        """被拦（CF / 年龄墙 / IP 封 / 429）→ 该 host 冷却（默认 `BLOCK_COOLDOWN_HOURS`）。"""
        name = _host_key(host)
        if not name:
            return
        span = _float_or(hours, BLOCK_COOLDOWN_HOURS) * 3600
        self._kv_set(f"host:cold:{name}", time.time() + span, ttl=int(span) + 60)
        if reason:
            self._kv_set(f"host:blocked:{name}", str(reason), ttl=int(span) + 60)

    def blocked_reason(self, host: str) -> str:
        """上次被拦的原因（排障用；没有回空串）。"""
        return str(self._kv_get(f"host:blocked:{_host_key(host)}", "") or "")

    # ---------- 订阅检查 ----------

    def check_allowed(self, max_per_day: int, min_interval_min: int) -> Tuple[bool, str]:
        """判断此刻能否执行订阅检查，返回（是否允许, 原因）。

        两个入参都来自规则（用户可写），所以**先夹到政策值再判**：每天 ≤ 6 次、
        间隔 ≥ 240 分钟。界面上限也做了同样的事，这里是最后一道闸。
        """
        max_per_day = min(max(_int_or(max_per_day, POLICY_MAX_PER_DAY), 1), POLICY_MAX_PER_DAY)
        min_interval_min = max(_int_or(min_interval_min, POLICY_MIN_INTERVAL_MIN), POLICY_MIN_INTERVAL_MIN)
        today = time.strftime("%Y-%m-%d")
        count = int(self._kv_get(f"subcheck:count:{today}", 0) or 0)
        if count >= max_per_day:
            return False, f"今天已检查 {count} 次，达到上限 {max_per_day} 次/天"
        last = float(self._kv_get("subcheck:last", 0) or 0)
        if last:
            passed_min = (time.time() - last) / 60.0
            if passed_min < float(min_interval_min):
                remain = int(float(min_interval_min) - passed_min)
                return False, f"距上次检查仅 {int(passed_min)} 分钟，需间隔 ≥{min_interval_min} 分钟（还需 {remain} 分钟）"
        return True, ""

    def note_check(self) -> None:
        """记录一次成功的订阅检查。"""
        today = time.strftime("%Y-%m-%d")
        key = f"subcheck:count:{today}"
        count = int(self._kv_get(key, 0) or 0) + 1
        self._kv_set(key, count, ttl=86400 * 2)
        self._kv_set("subcheck:last", time.time())

    # ---------- 站点搜索 ----------

    def site_available(self, site_name: str) -> Tuple[bool, str]:
        """站点是否可用：先看 403/429 冷却，再看每小时次数上限。"""
        until = float(self._kv_get(f"site:cold:{site_name}", 0) or 0)
        if until > time.time():
            left = int((until - time.time()) / 60)
            return False, f"{site_name} 处于冷却中（约 {left} 分钟后恢复）"
        hour = time.strftime("%Y-%m-%d %H")
        used = int(self._kv_get(f"site:used:{site_name}:{hour}", 0) or 0)
        if used >= SITE_HOURLY_MAX:
            return False, f"{site_name} 本小时已达 {SITE_HOURLY_MAX} 次上限"
        return True, ""

    def note_site_search(self, site_name: str) -> None:
        """记录一次站点搜索。"""
        hour = time.strftime("%Y-%m-%d %H")
        key = f"site:used:{site_name}:{hour}"
        self._kv_set(key, int(self._kv_get(key, 0) or 0) + 1, ttl=7200)

    def site_cooldown(self, site_name: str) -> None:
        """站点被防爬（403/429）时冷却 24 小时。"""
        self._kv_set(f"site:cold:{site_name}", time.time() + SITE_COOLDOWN_HOURS * 3600,
                     ttl=SITE_COOLDOWN_HOURS * 3600 + 60)

    def state(self) -> dict:
        """返回当前限流状态，供界面展示。"""
        today = time.strftime("%Y-%m-%d")
        return {
            "checked_today": int(self._kv_get(f"subcheck:count:{today}", 0) or 0),
            "last_check": float(self._kv_get("subcheck:last", 0) or 0),
            "global_rps": GLOBAL_RPS,
            "site_hourly_max": SITE_HOURLY_MAX,
            "default_rate_limit": self.default_rate_limit,
            "rate_limits": dict(self.rate_limits),
        }


def is_antibot_error(text: Any) -> bool:
    """判断异常文本是否属于站点防爬（403/429/频繁）。"""
    low = str(text or "").lower()
    return any(k in low for k in ("403", "429", "too many", "频繁", "forbidden", "rate limit"))
