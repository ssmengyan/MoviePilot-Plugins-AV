"""AVHelper 插件单测的公共夹具：按文件路径独立加载插件模块。

插件包 `__init__.py` 依赖宿主 `app.sdk`，在无宿主环境下不可导入；被单测覆盖的模块
（scoring/store/longshot/ratelimit/client）只依赖标准库，可用本夹具单独加载。

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


@pytest.fixture(scope="session")
def store_mod():
    """store 模块。"""
    return _load("store")


@pytest.fixture(scope="session")
def scoring_mod():
    """scoring 模块。"""
    return _load("scoring")


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
