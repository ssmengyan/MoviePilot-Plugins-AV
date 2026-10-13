"""运行期路径与外部依赖解析：数据根（SQLite/缓存）与 javdb-cli 二进制。

别人把这套插件装进自己的 MoviePilot 时，容器里既没有本机那个 `/avhelper` 挂载卷，
也没有预置好的 `javdb` 二进制，所以两条路径都不能写死。解析顺序固定为
「插件配置 → 历史固定路径（老部署原地不动）→ 通用回落」：

- **数据根**：配置 `data_root` → 存在 `/avhelper` 卷时用 `/avhelper/cache` →
  MoviePilot 的插件数据目录 `<PLUGIN_DATA_PATH>/AVHelper`（默认 `/config/plugins/AVHelper`，
  其下 `meta/` 放 SQLite 与 JSON 缓存、`images/` 放图片缓存、`bin/` 放 javdb）。
  SQLite 台账、JSON 缓存、图片缓存同根，容量淘汰也按这个根扫描。
- **javdb 二进制**：配置 `javdb_bin` → `/avhelper/bin/javdb` → `PATH` 上的 `javdb` →
  数据根下的 `bin/javdb`（缺文件时由 `ensure_javdb()` 自动从官方 Release 下载）。

解析结果由 `configure()` 在 `init_plugin()` 里写一次，其余模块只通过取值函数读取，
不各自缓存路径副本（否则改配置后要重启容器才生效）。
"""

from __future__ import annotations

import math
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Optional, Tuple

# 缓存容量预算（GB）：**默认 1G**（2026-10-14 用户要求，从写死的 60G 改成可配置）。
# 依据是实测：线上数据根长期占用 180 MB 左右（图片 + JSON 缓存 + SQLite 一起），
# 60G 的旧上限对 NAS 用户无所谓，对小硬盘用户却是一句「随时可能吃掉 60G」的恐吓。
# 留 0.1G 下限是硬保护：上限归零会让每晚的淘汰把缓存目录整个清空。
DEFAULT_CACHE_MAX_GB = 1.0
CACHE_MAX_GB_MIN = 0.1
CACHE_MAX_GB_MAX = 4096.0

# 老部署的固定坐标：数据卷挂到容器 `/avhelper`，插件数据与 javdb 二进制共用这个前缀
LEGACY_ROOT = Path("/avhelper")
LEGACY_DATA_ROOT = LEGACY_ROOT / "cache"
LEGACY_JAVDB = LEGACY_ROOT / "bin" / "javdb"

# javdb-cli 上游（Go 单文件二进制，官方 Release 提供各平台压缩包）
JAVDB_REPO = "FlanChanXwO/javdb-cli"
# 自动下载锁定的版本：本插件在这版上实测通过；不追 latest，避免上游改动把用户装崩
JAVDB_VERSION = "0.8.2"
# Go 的 GOOS/GOARCH 命名口径（平台的其它写法在 _platform_tag() 里归一）
_SYSTEMS = {"linux": "linux", "darwin": "darwin", "windows": "windows"}
_MACHINES = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}

_DATA_ROOT: Optional[Path] = None
_JAVDB_BIN: Optional[str] = None


def _fallback_root() -> Path:
    """拿不到宿主插件数据目录时的兜底数据根（历史坐标，保持与老部署一致）。"""
    return LEGACY_DATA_ROOT


def _resolve_root(configured: str, fallback: Optional[Path]) -> Path:
    """按「配置 → 历史卷 → 宿主插件数据目录」的顺序定出数据根。"""
    text = str(configured or "").strip()
    if text:
        return Path(text).expanduser()
    if LEGACY_ROOT.is_dir():
        return LEGACY_DATA_ROOT
    return Path(fallback) if fallback else _fallback_root()


def _resolve_bin(configured: str) -> str:
    """按「配置 → 历史路径 → PATH → 数据根 bin」的顺序定出 javdb 二进制路径。"""
    text = str(configured or "").strip()
    if text:
        return text
    if os.access(str(LEGACY_JAVDB), os.X_OK):
        return str(LEGACY_JAVDB)
    found = shutil.which("javdb")
    if found:
        return found
    return str(data_root() / "bin" / "javdb")


def configure(data_root: str = "", javdb_bin: str = "",
              fallback_root: Optional[Path] = None) -> None:
    """锁定本次运行的数据根与 javdb 路径；由 `init_plugin()` 调用。

    :param data_root: 插件配置里的 `data_root`，留空按默认顺序解析
    :param javdb_bin: 插件配置里的 `javdb_bin`，留空按默认顺序解析
    :param fallback_root: 宿主插件数据目录（`_PluginBase.get_data_path()`），最后的回落
    """
    global _DATA_ROOT, _JAVDB_BIN
    _DATA_ROOT = _resolve_root(data_root, fallback_root)
    _JAVDB_BIN = _resolve_bin(javdb_bin)


def data_root() -> Path:
    """数据根目录（SQLite 台账、JSON 缓存、图片缓存同根）。"""
    return _DATA_ROOT if _DATA_ROOT is not None else _fallback_root()


def meta_dir() -> Path:
    """元数据目录：JSON 缓存与插件自管 SQLite 都落在这里。"""
    return data_root() / "meta"


def db_path() -> Path:
    """插件自管 SQLite 台账的完整路径。"""
    return meta_dir() / "avhelper.db"


def images_dir() -> Path:
    """图片缓存目录（`/img` 代理与预热封面落盘处）。"""
    return data_root() / "images"


def bin_dir() -> Path:
    """外部二进制目录（自动下载的 javdb 落在这里）。"""
    return data_root() / "bin"


# 随包内置的资源目录（映射表、简繁词典等）：`plugins.v3/avhelper/resources/`。
# 与「数据根」分开：这些文件是**发行的代码资产**，随插件一起分发、不随用户数据变化；
# 用户想覆盖某一份时，把同名文件放进 `{data_root}/resources/` 即可（见 resource_file）。
BUILTIN_RESOURCES = Path(__file__).resolve().parent / "resources"


def resources_dir() -> Path:
    """资源目录：用户覆盖目录存在就用它，否则用随包内置的那份。

    只判断**目录是否已存在**：`{data_root}/resources` 是我们自己不会创建的位置，
    它一旦存在就一定是用户手工放的（打包与测试都不会凭空生成），可以放心当覆盖信号。
    """
    override = data_root() / "resources"
    return override if override.is_dir() else BUILTIN_RESOURCES


def resource_file(name: str) -> Path:
    """按「用户覆盖 → 内置」逐文件解析一份资源，返回第一个**已存在**的路径。

    逐文件而不是逐目录：用户可能只覆盖 `zhcdict.json` 一份，另外两份仍旧走内置。
    两份都没有时返回内置路径（调用方按「文件不存在」处理，不要在这里抛异常 ——
    资源缺失只该让刮削降级，不该让插件起不来）。
    """
    text = str(name or "").strip()
    if not text:
        return BUILTIN_RESOURCES
    override = data_root() / "resources" / text
    if override.is_file():
        return override
    return BUILTIN_RESOURCES / text


def cache_limit_gb(value: Any = None) -> float:
    """把「缓存上限（GB）」配置归一成一个安全值（默认 `DEFAULT_CACHE_MAX_GB`）。

    插件配置里这一个键来自用户输入（设置台「运行与缓存」的输入框，或宿主 JSON 表单），
    所以四种脏数据都要接住：空串 / 缺键 / 非数字 / 负数或 0。

    **0 与负数一律回落默认值，不是「不限制」**：淘汰逻辑拿它当字节上限用，
    归零等于每晚 4 点把缓存目录整个清空（`is_keep_file()` 只保得住 SQLite）。
    真要「不限制」就填一个大数，上限被夹在 `CACHE_MAX_GB_MAX`。

    :param value: 配置里的原始值（可能是 `"1"` / `2.5` / `None` / 乱码）
    :return: 夹在 [`CACHE_MAX_GB_MIN`, `CACHE_MAX_GB_MAX`] 里的 GB 数
    """
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_CACHE_MAX_GB
    if not math.isfinite(parsed) or parsed <= 0:
        return DEFAULT_CACHE_MAX_GB
    return min(max(parsed, CACHE_MAX_GB_MIN), CACHE_MAX_GB_MAX)


def cache_limit_bytes(value: Any = None) -> int:
    """缓存上限的字节数形式（`cache_limit_gb()` 的口径，给淘汰与界面共用）。"""
    return int(cache_limit_gb(value) * 1024 ** 3)


def javdb_bin() -> str:
    """javdb 可执行文件路径（可能尚不存在，用 `javdb_ready()` 判断）。"""
    return _JAVDB_BIN if _JAVDB_BIN else str(LEGACY_JAVDB)


def javdb_ready() -> bool:
    """javdb 二进制是否已就位且可执行。"""
    return os.access(javdb_bin(), os.X_OK)


def _platform_tag() -> Tuple[str, str]:
    """当前平台对应的 (GOOS, GOARCH)；不认识的平台返回两个空串。"""
    return (_SYSTEMS.get(platform.system().lower(), ""),
            _MACHINES.get(platform.machine().lower(), ""))


def _pick_asset() -> Tuple[str, str]:
    """算出 (Release 资源文件名, 压缩格式)；平台不受支持时返回两个空串。"""
    system, machine = _platform_tag()
    if not system or not machine:
        return "", ""
    ext = "zip" if system == "windows" else "tar.gz"
    name = f"javdb-cli_{JAVDB_VERSION}_{system}_{machine}.{ext}"
    return name, ext


def _download(url: str, proxy: str, timeout: int = 120) -> bytes:
    """下载一个 URL 的字节；给了代理就走代理，不给就用系统默认直连。"""
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": "AVHelper"})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def _extract_archive(blob: bytes, ext: str, target: Path) -> bool:
    """把压缩包里的 javdb 可执行文件解到 target 并加上执行位；失败返回 False。"""
    suffix = ".zip" if ext == "zip" else ".tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"javdb{suffix}"
        archive.write_bytes(blob)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if ext == "zip":
                with zipfile.ZipFile(archive) as zf:
                    member = next((n for n in zf.namelist()
                                   if Path(n).name in ("javdb", "javdb.exe")), "")
                    if not member:
                        return False
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
            else:
                with tarfile.open(archive, "r:gz") as tf:
                    member = next((m for m in tf.getmembers()
                                   if m.isfile() and Path(m.name).name == "javdb"), None)
                    if member is None:
                        return False
                    src = tf.extractfile(member)
                    if src is None:
                        return False
                    with src, open(target, "wb") as dst:
                        dst.write(src.read())
        except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError):
            return False
    target.chmod(0o755)
    return True


def ensure_javdb(proxy: str = "") -> Tuple[bool, str]:
    """确保 javdb 二进制可用：已经就位直接返回，否则从官方 Release 下载一次。

    :param proxy: 下载用的代理（内地直连 GitHub 通常不通，沿用插件里那份代理配置）
    :return: (是否可用, 说明文本)；说明文本用于日志与界面提示，失败原因不吞掉
    """
    current = javdb_bin()
    if javdb_ready():
        return True, current
    asset, ext = _pick_asset()
    system, machine = _platform_tag()
    if not asset:
        return False, (f"当前平台（{platform.system()}/{platform.machine()}）"
                       "没有对应的 javdb 预编译包，请手动指定 javdb_bin")
    url = (f"https://github.com/{JAVDB_REPO}/releases/download/"
           f"v{JAVDB_VERSION}/{asset}")
    target = Path(current)
    try:
        blob = _download(url, proxy)
    except Exception as error:  # 下载失败不能连累插件其它功能
        return False, (f"下载 javdb-cli 失败（{type(error).__name__}: {error}），"
                       "可在插件设置里手动指定 javdb_bin")
    if not _extract_archive(blob, ext, target):
        return False, f"javdb-cli（{system}/{machine}）压缩包解包失败，可手动指定 javdb_bin"
    return True, str(target)
