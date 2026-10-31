"""`actor_sources.py` 单测：gFriends 索引（解析 / 匹配 / TTL / 失败 / 单飞）+ javdb 头像兜底。

全程**不联网**：`load_index(fetch=...)` 的抓取函数注入成假函数，`paths.meta_dir()` 指向
`tmp_path`（落盘缓存不碰线上数据根）。

样本按**实测结构**裁剪，不是随手编的 JSON：`{"Content": {文件夹: {"艺名.jpg": "实际文件名?t=…"}},
"Information": {...}}` —— 值一律带 `?t=` 时间戳、约半数带 `AI-Fix-` 前缀，文件夹名带
`0-/7-/z-` 前缀（`z-*` 是低质源）。因此这里的断言是"真实形状下必须成立"，不是玩具断言。
"""

import datetime
import http.client
import importlib.util
import json
import sys
import threading
import types
import urllib.error
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
# 与 conftest 用同一个合成包名：同一份模块不能被加载成两个互不相干的副本
PKG_NAME = "avhelper_under_test"


def _load(name: str):
    """按 conftest 的口径加载插件目录下的单个模块。"""
    if PKG_NAME not in sys.modules:
        pkg = types.ModuleType(PKG_NAME)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PKG_NAME] = pkg
    key = f"{PKG_NAME}.{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 样本：真实形状（Content 壳 + Information + z-* 低质源 + ?t= + AI-Fix-）
# ---------------------------------------------------------------------------

SAMPLE_TREE = {
    "Content": {
        "7-S1": {
            "葵つかさ.jpg": "葵つかさ.jpg?t=1667007583",
            "あかり.png": "あかり.png?t=1667007584",
            "みなみ(無碼).jpg": "みなみ.jpg?t=1667007585",
            "上書き.JPG": "上書き.JPG?t=1",
            # 键是图片但值是 gif：值也要过扩展名校验
            "値がgif.jpg": "画像.gif?t=1",
            # 键没有图片扩展名（或干脆没扩展名）：一律丢
            "無効.gif": "無効.gif?t=1",
            "拡張子なし": "拡張子なし",
            # 值为空：没有可拼的文件名，丢
            "空の値.jpg": "",
        },
        "z-DMM(步)": {
            "葵つかさ.jpg": "AI-Fix-葵つかさ.jpg?t=1607433576",
            "あかり.jpg": "AI-Fix-あかり.jpg?t=1607433616",
        },
        "0-Hand-Storage": {
            "葵つかさ.jpg": "葵つかさ.jpg?t=1610423702",
            "みなみ.png": "みなみ.png?t=1610423703",
        },
    },
    "Information": {"TotalNum": 9, "TotalSize": 10298257975},
}

SAMPLE_BYTES = json.dumps(SAMPLE_TREE, ensure_ascii=False).encode("utf-8")


def _good_fetch(calls=None, payload=SAMPLE_BYTES):
    """造一个假抓取函数（记录调用、回固定正文）。"""
    def fetch(url, proxy=""):
        if calls is not None:
            calls.append(url)
        return payload
    return fetch


def _boom_fetch(calls=None):
    """造一个必抛的假抓取函数（模拟代理不通）。"""
    def fetch(url, proxy=""):
        if calls is not None:
            calls.append(url)
        raise OSError("proxy unreachable")
    return fetch


@pytest.fixture(scope="session")
def actor_sources():
    """actor_sources 模块（只依赖标准库与 paths）。"""
    return _load("actor_sources")


@pytest.fixture(autouse=True)
def fresh_state(actor_sources, monkeypatch, tmp_path):
    """每个用例：数据根指到 tmp_path（缓存落临时目录）、进程内状态清空。"""
    paths_mod = _load("paths")
    monkeypatch.setattr(paths_mod, "_DATA_ROOT", tmp_path)
    actor_sources.reset_cache()
    yield
    actor_sources.reset_cache()


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

class TestParseFiletree:
    """Filetree.json → {艺名: [候选…]}。"""

    def test_same_name_keeps_all_candidates_sorted_by_folder(self, actor_sources):
        """同一艺名的候选**全部保留**，按文件夹名排序，z-* 排最后。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        rows = index["葵つかさ"]
        assert [row["folder"] for row in rows] == ["0-Hand-Storage", "7-S1", "z-DMM(步)"]
        assert len(rows) == 3

    def test_z_prefixed_folder_sorts_last_even_against_lowercase_letters(self, actor_sources):
        """z-* 靠后是**显式规则**，不靠字典序：大写 Z- 也排最后。"""
        payload = {"Content": {
            "z-低质源": {"あき.jpg": "a.jpg?t=1"},
            "Z-低质源": {"あき.jpg": "b.jpg?t=1"},
            "7-S1": {"あき.jpg": "c.jpg?t=1"},
        }}
        index = actor_sources.parse_filetree(payload)
        assert [row["folder"] for row in index["あき"]] == ["7-S1", "z-低质源", "Z-低质源"]

    def test_url_keeps_query_string_and_ai_fix_prefix_verbatim(self, actor_sources):
        """直链**原样拼接**：?t= 与 AI-Fix- 以及中日文都不二次编码（编了就 404）。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        url = index["葵つかさ"][-1]["url"]
        assert url == ("https://raw.githubusercontent.com/gfriends/gfriends/master/Content/"
                       "z-DMM(步)/AI-Fix-葵つかさ.jpg?t=1607433576")
        assert "%3F" not in url and "%E8" not in url and "AI-Fix-" in url

    def test_candidate_shape_is_exactly_three_keys(self, actor_sources):
        """候选固定三格：url / folder / file（下一环按这个形状取值）。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        row = index["あかり"][1]
        assert set(row) == {"url", "folder", "file"}
        assert row["folder"] == "z-DMM(步)"
        assert row["file"] == "AI-Fix-あかり.jpg?t=1607433616"

    def test_extension_filter_accepts_jpg_png_any_case(self, actor_sources):
        """扩展名只认 .jpg/.png，且**不分大小写**（.JPG 也得进）。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        assert "上書き" in index                      # .JPG
        assert "あかり" in index                      # .png
        assert "葵つかさ" in index                    # .jpg

    def test_extension_filter_drops_gif_and_extensionless(self, actor_sources):
        """非图片扩展名（键或值任一侧）与没有扩展名的一律丢。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        assert "無効" not in index                    # 键是 .gif
        assert "拡張子なし" not in index
        assert "値がgif" not in index                 # 键 .jpg 但值是 .gif
        assert "空の値" not in index                  # 值为空

    def test_accepts_str_and_parsed_dict(self, actor_sources):
        """bytes / str / 已解析 dict 三种入参同一个结果。"""
        from_bytes = actor_sources.parse_filetree(SAMPLE_BYTES)
        from_str = actor_sources.parse_filetree(SAMPLE_BYTES.decode("utf-8"))
        from_dict = actor_sources.parse_filetree(SAMPLE_TREE)
        assert from_bytes == from_str == from_dict

    def test_payload_without_content_shell_still_parses(self, actor_sources):
        """没有 Content 壳（顶层就是 folder→files）也认 —— 结构探测，不猜版本。"""
        index = actor_sources.parse_filetree({"7-S1": {"あき.jpg": "a.jpg?t=1"}})
        assert index["あき"][0]["folder"] == "7-S1"

    def test_truncated_or_garbage_payload_returns_empty(self, actor_sources):
        """截断 / 乱码正文 → 空索引（**不抛**：调用方据此换源）。"""
        truncated = SAMPLE_BYTES[: len(SAMPLE_BYTES) // 2]      # 真截断（不是假字符串）
        assert actor_sources.parse_filetree(truncated) == {}
        assert actor_sources.parse_filetree("<html>403</html>") == {}
        assert actor_sources.parse_filetree(None) == {}
        assert actor_sources.parse_filetree(b"") == {}

    def test_duplicate_folder_file_only_kept_once(self, actor_sources):
        """同一 (folder, file) 重复出现只留一条（真数据里没有，防御用）。"""
        payload = {"Content": {"7-S1": {"あき.jpg": "a.jpg?t=1", "あき.png": "a.jpg?t=1"}}}
        index = actor_sources.parse_filetree(payload)
        assert len(index["あき"]) == 1


# ---------------------------------------------------------------------------
# 匹配
# ---------------------------------------------------------------------------

class TestMatchCandidates:
    """精确匹配：jp → 别名 → 剥后缀；绝不模糊。"""

    def test_jp_exact_hit(self, actor_sources):
        """jp 精确命中，并按 (folder, file) 顺序给全部候选。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        rows = actor_sources.match_candidates(index, ["葵つかさ"])
        assert [row["folder"] for row in rows] == ["0-Hand-Storage", "7-S1", "z-DMM(步)"]
        assert all(row["name"] == "葵つかさ" for row in rows)

    def test_alias_hit_in_given_order(self, actor_sources):
        """jp 没命中就按给定顺序试别名，命中哪个就用哪个。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        rows = actor_sources.match_candidates(index, ["三上悠亚", "みかみゆあ", "あかり"])
        assert rows and rows[0]["name"] == "あかり"

    def test_strip_uncensored_suffix_japanese(self, actor_sources):
        """剥 (無碼) 后缀再试：全角括号也认（剥出来的"みなみ"只命中它自己那条）。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        rows = actor_sources.match_candidates(index, ["みなみ（無碼）"])
        assert [row["name"] for row in rows] == ["みなみ"]
        assert [row["folder"] for row in rows] == ["0-Hand-Storage"]

    def test_halfwidth_suffix_hits_exact_key_before_stripping(self, actor_sources):
        """半角写法若本身就是索引键，则**精确命中**它（不去剥成另一个艺名）。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        rows = actor_sources.match_candidates(index, ["みなみ(無碼)"])
        assert [row["name"] for row in rows] == ["みなみ(無碼)"]
        assert [row["folder"] for row in rows] == ["7-S1"]

    def test_strip_uncensored_suffix_simplified_and_english(self, actor_sources):
        """(无码) 与 (Uncensored)（大小写不分）同样剥。"""
        index = {"みなみ": [{"url": "u", "folder": "f", "file": "x.jpg"}]}
        assert actor_sources.match_candidates(index, ["みなみ(无码)"])
        assert actor_sources.match_candidates(index, ["みなみ (uncensored)"])
        assert actor_sources.match_candidates(index, ["みなみ(無碼)(Uncensored)"])

    def test_exact_hit_wins_over_suffix_stripped_hit(self, actor_sources):
        """精确命中永远优先：索引里同时有 'X' 与 'X(無碼)' 时，后者不该被剥成前者。"""
        index = {
            "みなみ": [{"url": "u1", "folder": "a", "file": "1.jpg"}],
            "みなみ(無碼)": [{"url": "u2", "folder": "b", "file": "2.jpg"}],
        }
        rows = actor_sources.match_candidates(index, ["みなみ(無碼)"])
        assert [row["name"] for row in rows] == ["みなみ(無碼)"]
        assert rows[0]["folder"] == "b"

    def test_near_miss_is_not_matched(self, actor_sources):
        """近似名一律不命中：子串 / 插空格 / 多字 / 大小写都不算。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        for name in ("葵", "つかさ", "葵つかさ 改", "葵 つかさ", "葵つかさ2", "あかりん"):
            assert actor_sources.match_candidates(index, [name]) == [], name

    def test_simplified_chinese_is_not_fuzzy_matched(self, actor_sources):
        """简中写法不等于索引里的日文写法 —— 不做任何归一化（靠别名列表，不靠猜）。"""
        index = {"三上悠亜": [{"url": "u", "folder": "f", "file": "x.jpg"}]}
        assert actor_sources.match_candidates(index, ["三上悠亚"]) == []
        assert actor_sources.match_candidates(index, ["三上悠亜"])

    def test_empty_names_returns_empty(self, actor_sources):
        """空名字 / None / 空白串 → 空列表（不抛）。"""
        index = actor_sources.parse_filetree(SAMPLE_BYTES)
        assert actor_sources.match_candidates(index, []) == []
        assert actor_sources.match_candidates(index, [None, "", "   "]) == []
        assert actor_sources.match_candidates({}, ["葵つかさ"]) == []


# ---------------------------------------------------------------------------
# 缓存 / TTL / 落盘
# ---------------------------------------------------------------------------

class TestCacheAndTtl:
    """7 天 TTL + 落盘缓存 + 紧凑原子写。"""

    def _cache_file(self, tmp_path, actor_sources):
        return tmp_path / "meta" / actor_sources.CACHE_NAME

    def test_within_ttl_fetches_only_once(self, actor_sources):
        """7 天内重复调用只真拉 1 次（fetch 调用计数断言）。"""
        calls = []
        fetch = _good_fetch(calls)
        first = actor_sources.load_index(fetch=fetch)
        assert len(calls) == 1
        assert first["葵つかさ"][0]["folder"] == "0-Hand-Storage"
        assert actor_sources.load_index(fetch=fetch) == first
        assert actor_sources.load_index(proxy="http://127.0.0.1:7890", fetch=fetch) == first
        assert len(calls) == 1

    def test_cache_file_is_compact_and_has_three_keys(self, actor_sources, tmp_path):
        """落盘缓存紧凑（无空格/换行）、只有 fetched_at/source/items 三键、无 .tmp 残留。"""
        actor_sources.load_index(fetch=_good_fetch())
        path = self._cache_file(tmp_path, actor_sources)
        raw = path.read_bytes()
        assert raw and b" " not in raw and b"\n" not in raw
        data = json.loads(raw.decode("utf-8"))
        assert set(data) == {"fetched_at", "source", "items"}
        assert data["source"] == actor_sources.GFRIENDS_URL
        assert data["items"]["葵つかさ"][0]["folder"] == "0-Hand-Storage"
        assert list(path.parent.glob("*.tmp")) == []

    def test_disk_cache_is_reused_after_restart(self, actor_sources, tmp_path):
        """进程内状态清空（= 重启）后仍走落盘缓存：**不重新拉**。"""
        actor_sources.load_index(fetch=_good_fetch())
        actor_sources.reset_cache()
        calls = []
        again = actor_sources.load_index(fetch=_good_fetch(calls))
        assert calls == []
        assert again["あかり"][0]["folder"] == "7-S1"
        # source 跟着落盘缓存走：重启后仍能回答"这份索引当初是从哪个源拉的"
        assert actor_sources.index_status()["source"] == actor_sources.GFRIENDS_URL

    def test_expired_cache_refetches(self, actor_sources, tmp_path):
        """缓存超过 7 天 → 下一次 load 重新拉（fetch 第二次被调用）。"""
        calls = []
        fetch = _good_fetch(calls)
        actor_sources.load_index(fetch=fetch)
        assert len(calls) == 1
        # 把落盘缓存的时间改到 8 天前，再清进程内状态（等价于"8 天后重启"）
        path = self._cache_file(tmp_path, actor_sources)
        data = json.loads(path.read_text(encoding="utf-8"))
        old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)
        data["fetched_at"] = old.isoformat(timespec="seconds")
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
        actor_sources.reset_cache()
        assert actor_sources.index_status()["stale"] is True      # 过期先被看见
        actor_sources.load_index(fetch=fetch)
        assert len(calls) == 2

    def test_force_refetches_even_within_ttl(self, actor_sources):
        """force=True 跳过 TTL 强制刷新，返回刷新后的状态。"""
        calls = []
        fetch = _good_fetch(calls)
        actor_sources.load_index(fetch=fetch)
        status = actor_sources.refresh_index(fetch=fetch)
        assert len(calls) == 2
        assert status["count"] == len(actor_sources.load_index(fetch=fetch))
        assert status["stale"] is False
        assert status["source"] == actor_sources.GFRIENDS_URL
        assert status["fetched_at"]

    def test_index_status_before_any_load_is_stale_and_empty(self, actor_sources):
        """一次都没加载过：count=0 / stale=True / 空串，不抛也不联网。"""
        status = actor_sources.index_status()
        assert status == {"count": 0, "fetched_at": "", "stale": True, "source": ""}

    def test_corrupt_cache_file_is_ignored(self, actor_sources, tmp_path):
        """落盘缓存损坏 → 当没有，正常重新拉（不抛）。"""
        path = self._cache_file(tmp_path, actor_sources)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        calls = []
        index = actor_sources.load_index(fetch=_good_fetch(calls))
        assert index and len(calls) == 1


# ---------------------------------------------------------------------------
# 失败路径
# ---------------------------------------------------------------------------

class TestFailurePath:
    """拉取失败必须保住旧缓存、标 stale、且绝不抛给调用方。"""

    def test_fetch_error_keeps_old_index_and_marks_stale(self, actor_sources):
        """拉取抛错：返回**旧索引**、stale=True、last_error('index') 有原因。"""
        good = actor_sources.load_index(fetch=_good_fetch())
        calls = []
        still = actor_sources.load_index(force=True, fetch=_boom_fetch(calls))
        assert still == good
        assert len(calls) == 2                       # 主源 + 镜像各试一次
        status = actor_sources.index_status()
        assert status["stale"] is True
        assert status["count"] == len(good)
        assert actor_sources.last_error("index")

    def test_truncated_payload_falls_through_to_mirror(self, actor_sources):
        """主源正文被截断（解析不出条目）→ 自动换镜像，拿到即用。"""
        seen = []

        def fetch(url, proxy=""):
            seen.append(url)
            if url == actor_sources.GFRIENDS_URL:
                return SAMPLE_BYTES[: len(SAMPLE_BYTES) // 2]     # 截断
            return SAMPLE_BYTES

        index = actor_sources.load_index(fetch=fetch)
        assert seen == [actor_sources.GFRIENDS_URL, actor_sources.GFRIENDS_MIRROR]
        assert index["葵つかさ"]
        assert actor_sources.index_status()["source"] == actor_sources.GFRIENDS_MIRROR
        assert actor_sources.index_status()["stale"] is False

    def test_first_load_failure_returns_empty_dict(self, actor_sources):
        """一次都没成功过就失败：返回 {}（不抛），stale=True。"""
        index = actor_sources.load_index(fetch=_boom_fetch())
        assert index == {}
        assert actor_sources.index_status()["stale"] is True

    def test_failure_after_expiry_keeps_disk_cache(self, actor_sources, tmp_path):
        """过期 + 拉取失败：落盘旧缓存继续可用（不是空索引）。"""
        actor_sources.load_index(fetch=_good_fetch())
        actor_sources.reset_cache()
        index = actor_sources.load_index(force=True, fetch=_boom_fetch())
        assert index["葵つかさ"][0]["folder"] == "0-Hand-Storage"
        assert actor_sources.index_status()["stale"] is True


# ---------------------------------------------------------------------------
# 单飞
# ---------------------------------------------------------------------------

class TestSingleFlight:
    """并发调用只应发生一次真实拉取（6.5 MB，别重复拉）。"""

    def _run_two(self, actor_sources, force: bool):
        calls = []
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def fetch(url, proxy=""):
            calls.append(url)
            # 真拉 6.5 MB 要几秒；这里睡一下让第二个线程确实撞在锁上
            threading.Event().wait(0.3)
            return SAMPLE_BYTES

        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(actor_sources.load_index(force=force, fetch=fetch))
            except Exception as error:                            # pragma: no cover - 失败即测红
                errors.append(error)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert errors == []
        return calls, results

    def test_concurrent_loads_trigger_one_fetch(self, actor_sources):
        """两个线程同时 load_index → fetch 只被调用 1 次，两边拿到同一份索引。"""
        calls, results = self._run_two(actor_sources, force=False)
        assert len(calls) == 1
        assert len(results) == 2
        assert results[0] == results[1]
        assert results[0]["葵つかさ"]

    def test_concurrent_force_loads_trigger_one_fetch(self, actor_sources):
        """force=True 并发同样只拉一次：等锁期间别人刷过了就直接复用。"""
        calls, results = self._run_two(actor_sources, force=True)
        assert len(calls) == 1
        assert results[0] == results[1]


# ---------------------------------------------------------------------------
# HTTP 层：Range 续传（实测必需 —— 6.5 MB 正文经代理几乎每次都被掐断）
# ---------------------------------------------------------------------------

class _Resp:
    """`urllib` 响应的最小替身：可回字节，也可"读到一半断掉"。"""

    def __init__(self, status=200, length=None, body=b"", partial=None):
        self.status = status
        self.headers = {"Content-Length": str(length)} if length is not None else {}
        self._body = body
        self._partial = partial

    def read(self) -> bytes:
        if self._partial is not None:
            raise http.client.IncompleteRead(self._partial)
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_open(script, seen):
    """按脚本依次回响应（或抛异常），并记录每次请求头。"""
    def opener(url, headers, proxy, timeout):
        seen.append(dict(headers))
        step = script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step
    return opener


class TestHttpFetchResume:
    """`_http_fetch()` 的续传分支：真机上否则必然踩到（不联网，全部是假响应）。"""

    def test_incomplete_read_resumes_with_range(self, actor_sources, monkeypatch):
        """正文被掐断 → 用 Range 从断点续传，最终拼回完整字节。"""
        body = b"x" * 1000
        seen = []
        script = [_Resp(200, 1000, partial=body[:600]),
                  _Resp(206, 400, body=body[600:])]
        monkeypatch.setattr(actor_sources, "_open", _fake_open(script, seen))
        assert actor_sources._http_fetch("https://h/Filetree.json", attempts=3) == body
        assert "Range" not in seen[0]
        assert seen[1]["Range"] == "bytes=600-"

    def test_range_rejected_416_restarts_without_range(self, actor_sources, monkeypatch):
        """服务器不认续传（416，实测 jsdelivr）→ 丢掉偏移整拉重来。"""
        body = b"y" * 500
        seen = []
        script = [_Resp(200, 500, partial=body[:200]),
                  urllib.error.HTTPError("https://h", 416, "Range Not Satisfiable", None, None),
                  _Resp(200, 500, body=body)]
        monkeypatch.setattr(actor_sources, "_open", _fake_open(script, seen))
        assert actor_sources._http_fetch("https://h/Filetree.json", attempts=3) == body
        assert "Range" not in seen[2]

    def test_missing_content_length_returns_clean_body(self, actor_sources, monkeypatch):
        """没有 Content-Length（jsdelivr 是分块传输）时，正常读到 EOF 即算完整。"""
        body = b"z" * 42
        seen = []
        monkeypatch.setattr(actor_sources, "_open", _fake_open([_Resp(200, None, body=body)], seen))
        assert actor_sources._http_fetch("https://h/Filetree.json", attempts=3) == body
        assert len(seen) == 1


# ---------------------------------------------------------------------------
# javdb 演员页兜底
# ---------------------------------------------------------------------------

class _FakeClient:
    """javdb client 的最小替身：可回数据 / 回 None / 抛异常 / 只收一个参数。"""

    def __init__(self, data=None, error="", raises=None, single_arg=False):
        self.data = data
        self.error = error
        self.raises = raises
        self.single_arg = single_arg
        self.calls = []

    def actor(self, name, page=1, limit=30):
        if self.single_arg:
            raise TypeError("unexpected keyword argument 'page'")
        self.calls.append((name, page, limit))
        if self.raises:
            raise self.raises
        return self.data

    def last_error(self, key=""):
        return self.error


class _SingleArgClient(_FakeClient):
    """只实现 actor(name) 的老/替身实现。"""

    def __init__(self, data):
        super().__init__(data)
        self.single_calls = []

    def actor(self, name, page=None, limit=None):
        if page is not None or limit is not None:
            raise TypeError("only name")
        self.single_calls.append(name)
        return self.data


class TestJavdbAvatar:
    """javdb 演员页兜底：取值口径 + 占位图 + 未登录 + 不抛。"""

    AVATAR = "https://c0.jdbstatic.com/actresses/ab/cd/abcd.jpg"

    def test_entity_avatar_is_returned(self, actor_sources):
        """entity.avatar_url 命中 → 返回候选（source=javdb，带 javdb_actor_id）。"""
        client = _FakeClient({"entity": {"avatar_url": self.AVATAR, "id": "AbCd"},
                              "movies": []})
        row = actor_sources.fetch_javdb_avatar(client, " 葵つかさ ")
        assert row == {"name": "葵つかさ", "url": self.AVATAR, "source": "javdb",
                       "javdb_actor_id": "AbCd"}
        assert client.calls == [("葵つかさ", 1, 1)]        # 只要 entity，作品列表取最小页

    def test_flat_avatar_and_avatar_alias_accepted(self, actor_sources):
        """entity 缺失时认顶层；avatar_url / avatar 两种键都认。"""
        flat = _FakeClient({"avatar_url": self.AVATAR})
        assert actor_sources.fetch_javdb_avatar(flat, "葵つかさ")["url"] == self.AVATAR
        alias = _FakeClient({"entity": {"avatar": self.AVATAR}})
        assert actor_sources.fetch_javdb_avatar(alias, "葵つかさ")["url"] == self.AVATAR

    def test_placeholder_actor_unknow_is_dropped(self, actor_sources):
        """actor_unknow 占位图当"没有头像"：返回 None，原因 no_avatar。"""
        client = _FakeClient({"entity": {"avatar_url":
                                         "https://c0.jdbstatic.com/actresses/actor_unknow.jpg"}})
        assert actor_sources.fetch_javdb_avatar(client, "誰か") is None
        assert actor_sources.last_error("誰か") == "no_avatar"

    def test_login_required_is_detected_and_returns_none(self, actor_sources):
        """未登录页（client 回报中文说明）→ None + login_required（不抛）。"""
        client = _FakeClient(None, error="javdb 退出码 1：未登录或登录已过期，请更新 cookie")
        assert actor_sources.fetch_javdb_avatar(client, "葵つかさ") is None
        assert actor_sources.last_error("葵つかさ") == "login_required"

    def test_english_login_marker_also_detected(self, actor_sources):
        """英文说明（login required）同样判 login_required。"""
        client = _FakeClient(None, error="403 login required")
        assert actor_sources.fetch_javdb_avatar(client, "葵つかさ") is None
        assert actor_sources.last_error("葵つかさ") == "login_required"

    def test_client_error_never_raises(self, actor_sources):
        """client.actor 抛异常 → 返回 None（原因 unexpected），调用方不吃异常。"""
        client = _FakeClient(None, raises=RuntimeError("boom"))
        assert actor_sources.fetch_javdb_avatar(client, "葵つかさ") is None
        assert actor_sources.last_error("葵つかさ") == "unexpected"

    def test_single_arg_client_is_supported(self, actor_sources):
        """只实现 actor(name) 的替身也能用（退回默认分页）。"""
        client = _SingleArgClient({"entity": {"avatar_url": self.AVATAR}})
        assert actor_sources.fetch_javdb_avatar(client, "葵つかさ")["url"] == self.AVATAR
        assert client.single_calls == ["葵つかさ"]

    def test_missing_client_or_name_returns_none(self, actor_sources):
        """没有 client / 名字为空 / client 没有 actor → None（不抛）。"""
        assert actor_sources.fetch_javdb_avatar(None, "葵つかさ") is None
        assert actor_sources.fetch_javdb_avatar(_FakeClient({}), "") is None
        assert actor_sources.fetch_javdb_avatar(object(), "葵つかさ") is None

    def test_proxy_argument_is_accepted(self, actor_sources):
        """proxy 参数与其它源同形（javdb 的代理在 client 里，这里只保证签名一致）。"""
        client = _FakeClient({"entity": {"avatar_url": self.AVATAR}})
        # 地址用 RFC 5737 TEST-NET-1 占位：`tests/` 会随公开仓库发布，不写真实内网坐标
        row = actor_sources.fetch_javdb_avatar(client, "葵つかさ",
                                              proxy="http://192.0.2.11:7890")
        assert row["url"] == self.AVATAR


# ---------------------------------------------------------------------------
# 白名单（本任务唯一允许改的既有文件）
# ---------------------------------------------------------------------------

class TestWhitelist:
    """gFriends 的两个 host 必须在 imgproxy 白名单里（否则下一环取图会被 SSRF 边界挡掉）。"""

    def test_gfriends_hosts_are_allowlisted(self, actor_sources):
        imgproxy = _load("imgproxy")
        assert imgproxy.is_allowed(actor_sources.GFRIENDS_URL)
        assert imgproxy.is_allowed(actor_sources.GFRIENDS_MIRROR)
        assert imgproxy.is_allowed(actor_sources.GFRIENDS_RAW_BASE + "/7-S1/葵つかさ.jpg?t=1")
