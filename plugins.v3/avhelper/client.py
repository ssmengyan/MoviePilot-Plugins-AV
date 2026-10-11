"""javdb-cli 子进程封装：发现层（榜单/演员/详情/磁力）。

所有调用走子进程，输出按 utf-8 解码；失败返回 None 由上层降级，不抛异常到 UI。

二进制路径与代理都不写死：路径由 `paths.javdb_bin()` 按配置/历史路径/PATH 依次解析，
代理留空时**不传 `--proxy`**，让 javdb-cli 自己回落 `HTTPS_PROXY`/`ALL_PROXY` 或它的本地配置。
"""

import json
import subprocess
import time
from typing import Any, Dict, List, Optional

from . import paths

# 默认不内置任何代理：内地以外直连即可，内地用户在插件设置里填自己的代理
DEFAULT_PROXY = ""
TIMEOUT = 60
# 连续失败冷却：同一命令连续 2 次失败 → 冷却 1 小时（§8.2）
_FAIL_COUNT: Dict[str, int] = {}
_COOLDOWN_UNTIL: Dict[str, float] = {}


class JavdbClient:
    """javdb-cli 调用门面。"""

    def __init__(self, bin_path: Optional[str] = None, proxy: str = DEFAULT_PROXY):
        self.bin_path = bin_path or paths.javdb_bin()
        self.proxy = proxy

    def _run(self, key: str, args: List[str]) -> Optional[Any]:
        """执行一次 javdb-cli 并解析 JSON；失败/冷却中返回 None。"""
        now = time.time()
        if _COOLDOWN_UNTIL.get(key, 0) > now:
            return None
        # 代理留空就不传 --proxy：显式传空串会把 javdb-cli 自己的环境变量/配置一并压掉
        cmd = [self.bin_path] + (["--proxy", self.proxy] if self.proxy else []) + args + ["--json"]
        try:
            # stdin 必须显式置为 DEVNULL：javdb 在继承到打开的管道时会阻塞等待 EOF，
            # 导致 uvicorn 进程内每次调用都被 60s 超时（命令行 docker exec 不复现）。
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=TIMEOUT,
                stdin=subprocess.DEVNULL,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:300])
            data = json.loads(proc.stdout.decode("utf-8", "replace"))
            _FAIL_COUNT[key] = 0
            return data
        except Exception:
            _FAIL_COUNT[key] = _FAIL_COUNT.get(key, 0) + 1
            if _FAIL_COUNT[key] >= 2:
                _COOLDOWN_UNTIL[key] = now + 3600
                _FAIL_COUNT[key] = 0
            return None

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
