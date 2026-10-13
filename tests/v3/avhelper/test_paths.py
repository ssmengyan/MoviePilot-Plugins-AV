"""`paths` 模块的单测：数据根与 javdb 路径的解析顺序、平台资源名、压缩包解包。

全部不联网：`ensure_javdb()` 的下载分支用 monkeypatch 顶掉。
"""

import io
import tarfile
import zipfile
from pathlib import Path


def _tar_gz(payload: bytes) -> bytes:
    """造一个只含 javdb 的 tar.gz。"""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        info = tarfile.TarInfo("javdb")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _zip(payload: bytes) -> bytes:
    """造一个只含 javdb 的 zip。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("javdb", payload)
    return buffer.getvalue()


class TestResolveRoot:
    """数据根解析：配置优先，其次历史挂载卷，最后宿主插件数据目录。"""

    def test_configured_value_wins(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "nonexistent")
        fallback = tmp_path / "plugin-data"
        paths_mod.configure(data_root=str(tmp_path / "custom"),
                            javdb_bin="", fallback_root=fallback)
        assert paths_mod.data_root() == tmp_path / "custom"
        assert paths_mod.meta_dir() == tmp_path / "custom" / "meta"
        assert paths_mod.db_path() == tmp_path / "custom" / "meta" / "avhelper.db"

    def test_legacy_mount_wins_over_host_dir(self, paths_mod, tmp_path, monkeypatch):
        legacy = tmp_path / "avhelper"
        legacy.mkdir()
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", legacy)
        monkeypatch.setattr(paths_mod, "LEGACY_DATA_ROOT", legacy / "cache")
        paths_mod.configure(data_root="", javdb_bin="", fallback_root=tmp_path / "plugin-data")
        assert paths_mod.data_root() == legacy / "cache"

    def test_falls_back_to_host_plugin_dir(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "avhelper")
        fallback = tmp_path / "plugin-data"
        paths_mod.configure(data_root="  ", javdb_bin="", fallback_root=fallback)
        assert paths_mod.data_root() == fallback


class TestResolveBin:
    """javdb 路径解析：配置 > 历史路径 > PATH > 数据根下 bin。"""

    def test_configured_value_wins(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "avhelper")
        paths_mod.configure(data_root=str(tmp_path / "data"),
                            javdb_bin="/opt/bin/javdb", fallback_root=tmp_path)
        assert paths_mod.javdb_bin() == "/opt/bin/javdb"

    def test_legacy_path_when_executable(self, paths_mod, tmp_path, monkeypatch):
        legacy = tmp_path / "avhelper"
        binary = legacy / "bin" / "javdb"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(0o755)
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", legacy)
        monkeypatch.setattr(paths_mod, "LEGACY_JAVDB", binary)
        paths_mod.configure(data_root=str(tmp_path / "data"), javdb_bin="", fallback_root=tmp_path)
        assert paths_mod.javdb_bin() == str(binary)
        assert paths_mod.javdb_ready() is True

    def test_defaults_to_data_root_bin(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "avhelper")
        monkeypatch.setattr(paths_mod, "LEGACY_JAVDB", tmp_path / "avhelper" / "bin" / "javdb")
        monkeypatch.setattr(paths_mod.shutil, "which", lambda _name: None)
        paths_mod.configure(data_root=str(tmp_path / "data"), javdb_bin="", fallback_root=tmp_path)
        assert Path(paths_mod.javdb_bin()) == tmp_path / "data" / "bin" / "javdb"
        assert paths_mod.javdb_ready() is False


class TestPlatformAsset:
    """Release 资源名按 GOOS/GOARCH 口径拼装。"""

    def test_linux_amd64_uses_tar_gz(self, paths_mod, monkeypatch):
        monkeypatch.setattr(paths_mod.platform, "system", lambda: "Linux")
        monkeypatch.setattr(paths_mod.platform, "machine", lambda: "x86_64")
        name, ext = paths_mod._pick_asset()
        assert name == f"javdb-cli_{paths_mod.JAVDB_VERSION}_linux_amd64.tar.gz"
        assert ext == "tar.gz"

    def test_windows_arm64_uses_zip(self, paths_mod, monkeypatch):
        monkeypatch.setattr(paths_mod.platform, "system", lambda: "Windows")
        monkeypatch.setattr(paths_mod.platform, "machine", lambda: "ARM64")
        name, ext = paths_mod._pick_asset()
        assert name.endswith("_windows_arm64.zip")
        assert ext == "zip"

    def test_unknown_platform_returns_empty(self, paths_mod, monkeypatch):
        monkeypatch.setattr(paths_mod.platform, "system", lambda: "Plan9")
        monkeypatch.setattr(paths_mod.platform, "machine", lambda: "mips")
        assert paths_mod._pick_asset() == ("", "")


class TestExtractArchive:
    """两种压缩格式都能取出 javdb 可执行文件并加上执行位。"""

    def test_tar_gz(self, paths_mod, tmp_path):
        target = tmp_path / "bin" / "javdb"
        assert paths_mod._extract_archive(_tar_gz(b"BIN"), "tar.gz", target) is True
        assert target.read_bytes() == b"BIN"

    def test_zip(self, paths_mod, tmp_path):
        target = tmp_path / "bin" / "javdb"
        assert paths_mod._extract_archive(_zip(b"BIN"), "zip", target) is True
        assert target.read_bytes() == b"BIN"

    def test_missing_member_is_reported(self, paths_mod, tmp_path):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("readme.txt", "nope")
        assert paths_mod._extract_archive(buffer.getvalue(), "zip", tmp_path / "javdb") is False

    def test_corrupt_bytes_are_reported(self, paths_mod, tmp_path):
        assert paths_mod._extract_archive(b"not an archive", "tar.gz", tmp_path / "javdb") is False


class TestEnsureJavdb:
    """`ensure_javdb()`：已就位不发请求；缺文件时下载并解包；失败只回原因不抛异常。"""

    def test_ready_short_circuits(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "avhelper")
        binary = tmp_path / "data" / "bin" / "javdb"
        binary.parent.mkdir(parents=True)
        binary.write_text("x", encoding="utf-8")
        binary.chmod(0o755)
        paths_mod.configure(data_root=str(tmp_path / "data"), javdb_bin="", fallback_root=tmp_path)
        monkeypatch.setattr(paths_mod, "_download",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("不该下载")))
        ok, detail = paths_mod.ensure_javdb()
        assert ok is True and detail == str(binary)

    def test_downloads_and_extracts(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "avhelper")
        paths_mod.configure(data_root=str(tmp_path / "data"), javdb_bin="", fallback_root=tmp_path)
        monkeypatch.setattr(paths_mod.platform, "system", lambda: "Linux")
        monkeypatch.setattr(paths_mod.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(paths_mod, "_download", lambda url, proxy, **k: _tar_gz(b"BIN"))
        ok, detail = paths_mod.ensure_javdb(proxy="http://proxy:7890")
        assert ok is True
        assert Path(detail).read_bytes() == b"BIN"

    def test_download_failure_is_reported(self, paths_mod, tmp_path, monkeypatch):
        monkeypatch.setattr(paths_mod, "LEGACY_ROOT", tmp_path / "avhelper")
        paths_mod.configure(data_root=str(tmp_path / "data"), javdb_bin="", fallback_root=tmp_path)
        monkeypatch.setattr(paths_mod.platform, "system", lambda: "Linux")
        monkeypatch.setattr(paths_mod.platform, "machine", lambda: "x86_64")

        def boom(*_args, **_kwargs):
            raise OSError("network down")

        monkeypatch.setattr(paths_mod, "_download", boom)
        ok, detail = paths_mod.ensure_javdb()
        assert ok is False
        assert "javdb" in detail and "network down" in detail


class TestCacheLimit:
    """缓存上限（GB）归一（0.6.3）：默认 1G，脏数据回落默认值，上下夹取。

    这一条是**用户点名的默认值**：老版本写死 60G，对小硬盘用户过于吓人；
    实测数据根长期占用不到 0.3G，所以默认 1G。归零**不等于**「不限制」：
    淘汰逻辑拿它当字节上限，0 会让每晚 4 点的清理把缓存目录整个清空。
    """

    def test_default_is_one_gigabyte(self, paths_mod):
        assert paths_mod.DEFAULT_CACHE_MAX_GB == 1.0
        assert paths_mod.cache_limit_gb(None) == 1.0
        assert paths_mod.cache_limit_gb("") == 1.0
        assert paths_mod.cache_limit_gb("   ") == 1.0
        assert paths_mod.cache_limit_gb("abc") == 1.0

    def test_zero_and_negative_fall_back_instead_of_unlimited(self, paths_mod):
        assert paths_mod.cache_limit_gb(0) == 1.0
        assert paths_mod.cache_limit_gb("0") == 1.0
        assert paths_mod.cache_limit_gb(-5) == 1.0
        assert paths_mod.cache_limit_gb(float("nan")) == 1.0
        assert paths_mod.cache_limit_gb(float("inf")) == 1.0

    def test_parses_and_clamps(self, paths_mod):
        assert paths_mod.cache_limit_gb("2.5") == 2.5
        assert paths_mod.cache_limit_gb(3) == 3.0
        assert paths_mod.cache_limit_gb(0.01) == paths_mod.CACHE_MAX_GB_MIN
        assert paths_mod.cache_limit_gb(999999) == paths_mod.CACHE_MAX_GB_MAX

    def test_bytes_form(self, paths_mod):
        assert paths_mod.cache_limit_bytes("2") == 2 * 1024 ** 3
        assert paths_mod.cache_limit_bytes("") == 1024 ** 3
