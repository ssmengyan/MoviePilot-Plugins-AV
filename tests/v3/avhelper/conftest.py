"""AVHelper 插件单测的公共夹具：按文件路径独立加载插件模块。

插件包 `__init__.py` 依赖宿主 `app.sdk`，在无宿主环境下不可导入；被单测覆盖的模块
（scoring/store/emby/longshot/ratelimit/client）只依赖标准库，可用本夹具单独加载。

加载时先把插件目录注册成一个**合成包**，模块里的 `from . import paths` 这类相对导入
才有父包可解析（否则报 `attempted relative import with no known parent package`）。
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
# 合成包名：与真实包名 `avhelper` 区分开，避免和宿主里已安装的那份撞名
PKG_NAME = "avhelper_under_test"


def _install_host_stubs() -> None:
    """把宿主 `app.sdk.*` 装成空壳（整场测试只装一次）。

    `emby.py` **模块级**就 import 了 `app.sdk.logging` / `app.sdk.network`（`logger` 与
    `RequestUtils`），无宿主环境下这两条导入会直接报 ModuleNotFoundError；而 `store.py`
    在归一化番号时又会延迟导入 `emby`（`_norm_key()`），所以凡是碰下载台账的用例都绕不开它。
    这里只补这两个符号：真去连 Emby 的用例不存在（`library_rows()` 是纯函数）。
    """
    for name in ("app", "app.sdk"):
        sys.modules.setdefault(name, types.ModuleType(name))
    log = types.ModuleType("app.sdk.logging")

    class _Logger:
        def info(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

        def warning(self, *args, **kwargs):
            pass

        def debug(self, *args, **kwargs):
            pass

    log.logger = _Logger()
    sys.modules["app.sdk.logging"] = log
    net = types.ModuleType("app.sdk.network")

    class _RequestUtils:
        def __init__(self, *args, **kwargs):
            pass

    net.RequestUtils = _RequestUtils

    class _SitesHelper:
        """站点目录门面：`tasks.sites()` 才用它，队列单测走不到。"""

        def get_indexers(self):
            return []

    net.SitesHelper = _SitesHelper
    sys.modules["app.sdk.network"] = net
    cfg = types.ModuleType("app.sdk.config")

    class _Settings:
        """宿主 `settings` 的空壳：`tasks.py` 只在拼通知图址时用到 `MP_DOMAIN`。"""

        @staticmethod
        def MP_DOMAIN(url=""):
            return ""

    cfg.settings = _Settings()
    sys.modules["app.sdk.config"] = cfg


_install_host_stubs()


def _ensure_package() -> str:
    """把插件源码目录挂成一个合成包，返回包名。"""
    if PKG_NAME not in sys.modules:
        pkg = types.ModuleType(PKG_NAME)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PKG_NAME] = pkg
    return PKG_NAME


def _load(name: str):
    """加载插件目录下的单个模块，同名模块复用缓存。"""
    key = f"{_ensure_package()}.{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def plugin_dir() -> Path:
    """插件源码目录。"""
    return PLUGIN_DIR


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """整目录把重试退避换成**不睡**的假函数（`scraper._SLEEP`）。

    0.8.0 的 `http_fetch()` 会为可重试失败真睡 `2±1`、`5±1` 秒；单测里"失败 + 重试"的组合
    很多（每个源都要覆盖），真睡会把一轮测试从几十秒拖到几分钟。放在 conftest 里是为了
    覆盖**所有**测试模块（api 侧的 preview 用例会走同一条取数链）。

    取不到模块就跳过：并行施工期 `scraper.py` 可能是半成品（见 scraper 模块 docstring 的
    `SyntaxError` 记要），不该因为一个提速夹具把整目录用例打挂。
    """
    try:
        module = _load("scraper")
    except Exception:                                           # pragma: no cover - 防御
        return
    monkeypatch.setattr(module, "_SLEEP", lambda _seconds: None)


@pytest.fixture(autouse=True)
def fresh_limiter():
    """每个用例一个**干净的限流器**。

    `scraper._LIMITER` 是模块级状态（P1-2 把它做成了"进程内唯一执行点"），而限流器里有
    两类跨调用状态：每 host 的漏桶时刻、以及**被拦后的冷却**。不隔离的话，前一个用例里
    "javtxt 被 CF 拦"会把 `j.test` 冷却 6 小时，后面所有用同一个假主机的用例全被跳过 ——
    症状是"单独跑绿、一起跑红"。
    """
    try:
        module = _load("scraper")
        ratelimit = _load("ratelimit")
    except Exception:                                           # pragma: no cover - 防御
        return
    module.set_limiter(ratelimit.RateLimiter(None, sleep=lambda _seconds: None))


@pytest.fixture(scope="session")
def store_mod():
    """store 模块。"""
    return _load("store")


@pytest.fixture
def sandbox_paths(paths_mod, tmp_path):
    """把数据根钉到临时目录，用完还原。

    ⚠️ **凡是会调 `job_cacheclean()` 的用例必须用它**：那个方法会按缓存目录真的删文件，
    而测试里没人 `configure()` 过数据根 → `paths.data_root()` 落到历史坐标 `/avhelper/cache`
    （Windows 上会解析成盘符根下的 `avhelper\\cache`）。本机恰好不存在所以"看起来没事"，
    换一台机器上真有这个目录就会删掉用户的东西。
    """
    before = (paths_mod._DATA_ROOT, paths_mod._JAVDB_BIN)
    root = tmp_path / "root"
    (root / "meta").mkdir(parents=True, exist_ok=True)
    paths_mod.configure(data_root=str(root))
    try:
        yield root
    finally:
        paths_mod._DATA_ROOT, paths_mod._JAVDB_BIN = before


@pytest.fixture(scope="session")
def scoring_mod():
    """scoring 模块。"""
    return _load("scoring")


@pytest.fixture(scope="session")
def emby_mod():
    """emby 模块（番号归一化 / 展示番号 / 库索引 → 界面行）。"""
    return _load("emby")


@pytest.fixture(scope="session")
def longshot_mod():
    """longshot 模块。"""
    return _load("longshot")


@pytest.fixture(scope="session")
def ratelimit_mod():
    """ratelimit 模块。"""
    return _load("ratelimit")


@pytest.fixture(scope="session")
def client_mod():
    """client 模块（javdb-cli 调用门面）。"""
    return _load("client")


@pytest.fixture(scope="session")
def paths_mod():
    """paths 模块（数据根 / javdb 二进制解析）。"""
    return _load("paths")


@pytest.fixture(scope="session")
def tasks_mod():
    """tasks 模块（下载队列的进度合并与台账收尾）。"""
    return _load("tasks")


@pytest.fixture(scope="session")
def scraper_mod():
    """scraper 模块（取数链：番号归一 → 站点解析 → 聚合）。

    单独给一个名字，是为了让**不叫 `test_scraper.py` 的**用例（如 `test_fixtures.py` 的真实响应
    夹具）也能拿到模块 —— `test_scraper.py` 里那个同名 `scraper` 夹具是它自己的，别依赖它。
    """
    return _load("scraper")


@pytest.fixture(scope="session")
def classify_mod():
    """`number_classify` 模块（内容类型 / 马赛克 / 分集 / 分辨率，纯标准库）。"""
    return _load("number_classify")


@pytest.fixture(scope="session")
def graph_mod():
    """`scrape_graph` 模块（取数图：字段 × 站点链，纯标准库）。"""
    return _load("scrape_graph")
