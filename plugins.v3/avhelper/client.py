"""javdb-cli 子进程封装：发现层（榜单/演员/详情/磁力）。

所有调用走子进程，输出按 utf-8 解码；失败返回 None 由上层降级，不抛异常到 UI。

**失败一律留痕**（2026-10-11 加）：这里曾经是裸 `except Exception: return None`，于是
「榜单加载不出来」在宿主日志里一行都不留 —— 分不清是二进制没下下来、代理不通、站点超时，
还是站点返回了错误页。现在每次失败都记 warning（含脱敏后的命令行、耗时、stderr 摘要），
原因同时存进 `_LAST_ERROR` 供接口透出到界面提示：用户看到的就不再是笼统的
「站点超时或代理不可达」，而是子进程真正吐出来的那句话。

二进制路径与代理都不写死：路径由 `paths.javdb_bin()` 按配置/历史路径/PATH 依次解析，
代理留空时**不传 `--proxy`**，让 javdb-cli 自己回落 `HTTPS_PROXY`/`ALL_PROXY` 或它的本地配置。
"""

import json
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from app.sdk.logging import logger

from . import paths

# 默认不内置任何代理：内地以外直连即可，内地用户在插件设置里填自己的代理
DEFAULT_PROXY = ""
TIMEOUT = 60
# 连续失败冷却：同一命令连续 2 次失败 → 冷却 1 小时（§8.2）
COOLDOWN_AFTER = 2
COOLDOWN_SECONDS = 3600
_FAIL_COUNT: Dict[str, int] = {}
_COOLDOWN_UNTIL: Dict[str, float] = {}
_LAST_ERROR: Dict[str, str] = {}       # key → 最近一次失败原因（进程内，重启即清）
_LAST_FAIL_AT: Dict[str, float] = {}   # key → 最近一次失败时间戳


def mask(text: Any) -> str:
    """抹掉 URL 里的 `user:pass@`（代理可能带凭据，日志与界面都不能落明文）。"""
    return re.sub(r"://[^/@\s]+@", "://***@", str(text or ""))


# javdb 的报错里每个候选主机都挂着一条上百字符的查询串，真正的原因排在它后面
_URL_QUERY = re.compile(r"\?[^\"\s;]*")


def _tail(blob: Any, limit: int = 300) -> str:
    """把子进程输出压成一行短摘要。

    javdb 的失败长这样：`auto select host: route selection failed: https://<host>:
    Get "https://<host>/api/v1/startup?<一长串>": dial tcp 1.2.3.4:443: i/o timeout; …`
    —— 真正的原因（`dial tcp` / `i/o timeout` / `connection refused`）在**查询串后面**，
    硬截 300 字正好把原因截没，所以先把查询串抹掉再截。
    """
    raw = blob.decode("utf-8", "replace") if isinstance(blob, (bytes, bytearray)) else str(blob or "")
    raw = _URL_QUERY.sub("", mask(raw))
    return " ".join(raw.split())[:limit] or "（无输出）"


def last_error(key: str) -> str:
    """某条命令最近一次失败的原因（没有就空串）。"""
    return _LAST_ERROR.get(key, "")


def cooldown_left(key: str) -> int:
    """某条命令还剩多少秒冷却（0 = 没在冷却）。"""
    return max(0, int(_COOLDOWN_UNTIL.get(key, 0) - time.time()))


def state() -> Dict[str, Any]:
    """失败快照（供 `/diag` 输出）：原因、计数、冷却剩余。"""
    return {
        "lastError": dict(_LAST_ERROR),
        "lastFailAt": {k: int(v) for k, v in _LAST_FAIL_AT.items()},
        "failCount": dict(_FAIL_COUNT),
        "cooldownLeft": {k: left for k in list(_COOLDOWN_UNTIL) if (left := cooldown_left(k)) > 0},
    }


def reset() -> None:
    """清空失败计数与冷却（`init_plugin` 每次都会调）。

    冷却挂在模块级，改代理 / 换网络后必然重跑 `init_plugin`：不在这里清零，用户
    「改完代理点重试」会继续吃上一个代理留下的 1 小时冷却，把「已经修好了」误判成没修好。
    """
    _FAIL_COUNT.clear()
    _COOLDOWN_UNTIL.clear()
    _LAST_ERROR.clear()
    _LAST_FAIL_AT.clear()


class JavdbClient:
    """javdb-cli 调用门面。"""

    def __init__(self, bin_path: Optional[str] = None, proxy: str = DEFAULT_PROXY):
        self.bin_path = bin_path or paths.javdb_bin()
        self.proxy = proxy

    def last_error(self, key: str) -> str:
        """最近一次失败原因（转发模块级函数，方便调用方只持有 client）。"""
        return last_error(key)

    def cooldown_left(self, key: str) -> int:
        """该命令还剩多少秒冷却。"""
        return cooldown_left(key)

    def _fail(self, key: str, reason: str) -> None:
        """记一次失败：留日志、存原因、连续 2 次就进 1 小时冷却。"""
        _LAST_ERROR[key] = reason
        _LAST_FAIL_AT[key] = time.time()
        _FAIL_COUNT[key] = _FAIL_COUNT.get(key, 0) + 1
        count = _FAIL_COUNT[key]
        if count >= COOLDOWN_AFTER:
            _COOLDOWN_UNTIL[key] = time.time() + COOLDOWN_SECONDS
            _FAIL_COUNT[key] = 0
            logger.warning(f"AVHelper javdb 连续 {COOLDOWN_AFTER} 次失败，冷却 "
                           f"{COOLDOWN_SECONDS // 60} 分钟：{key}；原因：{reason}")
        else:
            logger.warning(f"AVHelper javdb 调用失败（第 {count} 次）：{key}；原因：{reason}")

    def _run(self, key: str, args: List[str], force: bool = False,
             timeout: Optional[int] = None) -> Optional[Any]:
        """执行一次 javdb-cli 并解析 JSON；失败/冷却中返回 None（原因见 `last_error`）。

        :param force: 跳过冷却检查（`/diag` 自检用：用户刚改完代理就要能立刻复测）
        :param timeout: 覆盖默认超时（自检用短超时，别让人干等 60 秒）
        """
        wait = timeout or TIMEOUT
        if not force:
            left = cooldown_left(key)
            if left > 0:
                logger.info(f"AVHelper javdb 冷却中（{left // 60} 分钟后才重试）：{key}；"
                            f"上次失败：{_LAST_ERROR.get(key, '未知')}")
                return None
        # 代理留空就不传 --proxy：显式传空串会把 javdb-cli 自己的环境变量/配置一并压掉
        cmd = [self.bin_path] + (["--proxy", self.proxy] if self.proxy else []) + args + ["--json"]
        shown = mask(" ".join(cmd))
        started = time.time()
        try:
            # stdin 必须显式置为 DEVNULL：javdb 在继承到打开的管道时会阻塞等待 EOF，
            # 导致 uvicorn 进程内每次调用都被 60s 超时（命令行 docker exec 不复现）。
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=wait,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self._fail(key, f"javdb 二进制不存在或不可执行：{self.bin_path}"
                            f"（设置台「常规」里的 javdb 路径，或启动时自动下载失败）；命令：{shown}")
            return None
        except PermissionError:
            self._fail(key, f"javdb 二进制没有执行权限：{self.bin_path}；命令：{shown}")
            return None
        except subprocess.TimeoutExpired:
            self._fail(key, f"调用超时 {wait}s（网络不通 / 代理不可达 / 站点无响应）；命令：{shown}")
            return None
        except Exception as error:
            self._fail(key, f"调用异常 {type(error).__name__}：{error}；命令：{shown}")
            return None
        elapsed = time.time() - started
        if proc.returncode != 0:
            self._fail(key, f"javdb 退出码 {proc.returncode}（{elapsed:.1f}s）："
                            f"{_tail(proc.stderr)}；命令：{shown}")
            return None
        try:
            data = json.loads(proc.stdout.decode("utf-8", "replace"))
        except Exception:
            self._fail(key, f"javdb 输出不是合法 JSON（{elapsed:.1f}s，退出码 0）："
                            f"{_tail(proc.stdout)}；命令：{shown}")
            return None
        if _LAST_ERROR.pop(key, None):
            logger.info(f"AVHelper javdb 恢复正常：{key}（{elapsed:.1f}s）")
        _FAIL_COUNT[key] = 0
        return data

    def rankings(self, period: str = "week", kind: str = "censored") -> Optional[Dict]:
        """榜单：period=day/week/month，kind=censored/uncensored/fc2。"""
        return self._run(f"rank:{period}:{kind}",
                         ["rankings", "movies", "--period", period, "--type", kind])

    def actors_rank(self) -> Optional[Dict]:
        """演员榜。"""
        return self._run("actors_rank", ["rankings", "actors"])

    def actor(self, name: str, page: int = 1, limit: int = 30) -> Optional[Dict]:
        """演员档案 + 作品史（一次只取一页；站点单页上限 50）。

        不再用 `--all`：它最多连抓 50 页（20/页）≈ 35 秒，且上千部的大牌演员只能拿到 1000 部
        （实测 4376 部的演员）。调用方按页取，翻页键即缓存键，避免一个演员只坏一页就整体冷却。
        """
        page = max(1, int(page or 1))
        limit = max(1, int(limit or 30))
        args = ["actor", name, "--page", str(page), "--limit", str(limit)]
        return self._run(f"actor:{name}:p{page}:l{limit}", args)

    def search(self, keyword: str) -> Optional[Dict]:
        """番号/关键词搜索。"""
        return self._run(f"search:{keyword}", ["search", keyword])

    def detail(self, number: str, mid: str = "", with_magnets: bool = False) -> Optional[Dict]:
        """影片详情。

        :param number: 番号（决定失败计数与缓存键，日志里也用它）
        :param mid: javdb 内部 id；已知时走 --id，省掉一次「番号 → id」的搜索往返
        :param with_magnets: 同一条命令一并取磁力，省掉第二次进程启动与重复解析
        :return: 影片字段字典；with_magnets 时额外带一个 `magnets` 列表
        """
        args = ["detail"]
        if mid:
            args += ["--id", str(mid)]
        else:
            args.append(str(number))
        if with_magnets:
            args.append("--magnets")
        return self._run(f"detail:{number}", args)

    def magnets(self, number: str, cnsub: bool = True) -> Optional[Dict]:
        """磁力链接列表。"""
        args = ["magnets", number] + (["--cnsub"] if cnsub else [])
        return self._run(f"magnets:{number}:{cnsub}", args)
