"""0.9.2 A3 的门禁：`async def` 里不许同步问下载器 / 同步打库。

**问题**：`api_task_download` / `api_magnet_download` / `api_check` 等接口在 `async def` 里直接
调 `self.engine.queue(fresh=True)`（同步访问下载器，本机 0.6 秒、下载器卡住时更久）或者
`self.store.task_list()`（SQLite 慢盘上最多等 30 秒锁）。一个慢请求就会把 MoviePilot 的
**所有**接口一起卡住。

**判据**：`async def` 自己的函数体里（不含它内部定义的同步闭包 —— `asyncio.to_thread(collect)`
正是靠那个闭包把活挪到工作线程）不许出现 `self.engine.*()` / `self.store.*()` 的**调用**；
只传方法对象（`asyncio.to_thread(self.store.fav_list)`）是合法的，那是把调用本身交给线程。

第二条用例是行为判据：慢下载器在跑的时候，事件循环必须还能立刻处理别的协程。
"""

import ast
import asyncio
import threading
import time
import types
from pathlib import Path

from test_api_scrape import _load_entry

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
ENTRY = PLUGIN_DIR / "__init__.py"


# ---------------------------------------------------------- AST 守卫

def _own_body_calls(node):
    """遍历 `node` 自己的函数体（**跳过**内部定义的函数/闭包），收集 `self.<attr>.<meth>()`。"""
    found = []

    def walk(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue                     # 闭包/生成器表达式里的调用由各自负责
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute):
                    owner = func.value
                    if (isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name)
                            and owner.value.id == "self"
                            and owner.attr in ("engine", "store")
                            and not func.attr.startswith("_")):
                        found.append((node.name, child.lineno, f"{owner.attr}.{func.attr}"))
            walk(child)

    walk(node)
    return found


def _violations(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            out.extend(_own_body_calls(node))
    return out


SAMPLE = '''
class Demo:
    async def direct(self):
        return self.store.fav_list()

    async def via_closure(self):
        def collect():
            return {"tasks": self.engine.task_list()}
        return await asyncio.to_thread(collect)

    async def bound_method(self):
        return await asyncio.to_thread(self.store.fav_list)

    def sync_helper(self):
        return self.store.fav_list()
'''


def test_detector_flags_only_direct_calls_in_async_bodies():
    """守卫本身要有判别力：漏掉直接调用是假绿，误报闭包/方法对象会逼人写 `# noqa`。"""
    names = sorted({name for name, _, _ in _violations(ast.parse(SAMPLE))})
    assert names == ["direct"]


def test_no_sync_engine_or_store_calls_in_async_endpoints():
    violations = _violations(ast.parse(ENTRY.read_text(encoding="utf-8")))
    assert violations == [], "async 接口里出现了同步调用（应改用 asyncio.to_thread / _snapshot）：\n" + \
        "\n".join(f"  {name} 第 {line} 行：self.{call}" for name, line, call in violations)


# ---------------------------------------------------------- 行为判据

class _SlowEngine:
    """下载器很慢的替身：`queue()` 睡 `delay` 秒。"""

    def __init__(self, delay=0.4):
        self.delay = delay
        self.threads = []

    def task_list(self):
        self.threads.append(threading.current_thread())
        return []

    def queue(self, fresh=False):
        self.threads.append(threading.current_thread())
        time.sleep(self.delay)
        return []


def test_snapshot_runs_engine_calls_off_the_caller_thread():
    api_mod = _load_entry()
    engine = _SlowEngine(delay=0)
    fake = types.SimpleNamespace(engine=engine)
    caller = threading.current_thread()

    snap = asyncio.run(api_mod.AVHelper._snapshot(fake, fresh=True))

    assert snap == {"tasks": [], "queue": []}
    assert engine.threads, "快照没有真的调 engine"
    assert all(thread is not caller for thread in engine.threads)


def test_slow_downloader_does_not_block_the_event_loop():
    """下载器睡 0.4 秒的期间，事件循环必须能立刻处理别的协程（老写法会整整卡 0.4 秒）。"""
    api_mod = _load_entry()

    async def scenario():
        fake = types.SimpleNamespace(engine=_SlowEngine(delay=0.4))
        slow = asyncio.create_task(api_mod.AVHelper._queue_snapshot(fake, fresh=True))
        await asyncio.sleep(0.02)                 # 让慢任务先开工
        started = time.monotonic()
        await asyncio.sleep(0.01)                 # 事件循环能转就只需 0.01 秒
        elapsed = time.monotonic() - started
        await slow
        return elapsed

    assert asyncio.run(scenario()) < 0.2
