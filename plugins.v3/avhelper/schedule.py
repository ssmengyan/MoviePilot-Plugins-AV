"""订阅检查的时间表：5 段 cron 与**宿主 `add_job()` 直接收下的 kwargs** 之间的换算。

MP v3 的 `app/scheduler/catalog.py::Scheduler.update_plugin_job()` 把插件 `get_service()`
返回的 `kwargs` **原样展开**成 `BackgroundScheduler.add_job(self.start, service["trigger"], …)`；
`trigger == "cron"` 时传给 apscheduler 的就是 `apscheduler.triggers.cron.CronTrigger`。所以：

- 参数名只能用 apscheduler 的那几个：`minute` / `hour` / `day` / `month` / `day_of_week`；
  **`weekday` 不行**（MP 自己的定时任务写的是 `day_of_week`）；
- 值必须是 **cron 字段字符串**（`"9,14,21"` / `"*/6"` / `"mon-fri"`）。

⚠️ **不要改成整数列表**：容器里实测（2026-10-27，MP v3.1.5 + APScheduler 3.x）
`CronTrigger(minute=[5, 20, 35, 50])` 直接抛
`ValueError: Unrecognized expression "[5" for field "minute"` —— 列表会被当成字符串
`"[5, 20, 35, 50]"` 去解析，整条服务注册失败，订阅检查/演员同步就静默停摆。
字符串才是对的（`CronTrigger.from_crontab("30 9,14,21 * * *")` 与
`CronTrigger(minute="9,14,21", hour=9)` 两种写法都通过）。
"""

from typing import Any, Dict

from .notify import parse_cron


def host_kwargs(expr: str) -> Dict[str, Any]:
    """5 段 cron → 宿主 `add_job()` 的 kwargs（每段都是**原始字段字符串**）。

    非法表达式抛 `ValueError`（调用方 `get_service()` 之前已过 `pick_cron()` 兜底；
    走到这里还非法说明库里存了坏值 —— 宁可抛也不静默错开）。

    每一段先过 `parse_cron()` 的校验（段数、取值范围、步长），再**原样**交回字符串：
    归一化（`9,14,21` 保持原写法）由 `pick_cron()` 负责，这里不做二次改写 ——
    apscheduler 认得 `*/6`、`mon-fri`、`1-5/2` 这些写法，改写成展开列表反而会炸。
    """
    parse_cron(expr)      # 只校验，不用它的展开结果（见文件头的 ⚠️）
    minute, hour, day, month, weekday = " ".join(str(expr).split()).split()
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": weekday,
    }
