"""打分与候选转换的单测：只覆盖纯函数，不碰网络与宿主。

模块按文件路径独立加载——插件包 `__init__.py` 依赖宿主 `app.sdk`，在有宿主的环境外不可导入，
而 scoring/store/longshot/ratelimit 这几个模块只用标准库，适合独立验证。
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"


def load_module(name: str):
    """按文件路径加载插件模块（与 conftest 用同一份缓存，避免重复加载）。"""
    key = f"avhelper_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


scoring = load_module("scoring")

# 真实站点种名（取自 MoviePilot 实际搜索结果），用于验证标题解析
REAL_1080P = "The Wandering Earth 2 2023 GBR BluRay 1080p x265 10bit DTS 5.1 2Audios-CMCT"
REAL_2160P = "The Wandering Earth 2 2023 2160p GBR UHD BluRay HEVC DV DTS-HD MA 5.1-DIY@Audies"
REAL_UNCENSORED = "ABP-557 無碼流出 4K 中字"


def rule(**overrides):
    """构造一份订阅规则，未指定字段用默认值。"""
    base = {
        "res": "1080p", "mustCnsub": True, "preferUncensored": True, "allow4k": True,
        "minSeeders": 3, "sites": [], "prefSites": [], "btFallback": True,
        "trigger": "notify", "savePath": "/downloads/av", "downloader": "qb",
    }
    base.update(overrides)
    return base


class TestTitleDetection:
    """种名特征识别。"""

    def test_resolution(self):
        assert scoring.detect_resolution(REAL_1080P) == "1080p"
        assert scoring.detect_resolution(REAL_2160P) == "2160p"
        assert scoring.detect_resolution("movie 720p x264") == "720p"
        assert scoring.detect_resolution("no marker here") == ""

    def test_cnsub(self):
        assert scoring.detect_cnsub("XXX-001 中文字幕 1080p")
        assert scoring.detect_cnsub("XXX-001 CHS")
        assert not scoring.detect_cnsub(REAL_1080P)  # 这条真实种名没有中字特征

    def test_uncensored(self):
        assert scoring.detect_uncensored(REAL_UNCENSORED)
        assert scoring.detect_uncensored("leaked version")
        assert not scoring.detect_uncensored(REAL_1080P)

    def test_codec_and_group(self):
        assert scoring.detect_codec(REAL_1080P) == "H265"
        assert scoring.detect_codec("movie 1080p x264-GRP") == "H264"
        assert scoring.detect_group(REAL_1080P) == "CMCT"
        assert scoring.detect_group("no group marker") == ""


class TestCandidateConversion:
    """宿主 TorrentInfo / javdb 磁力 → 统一候选结构。"""

    def test_from_torrent(self):
        torrent = SimpleNamespace(
            title=REAL_1080P, site_name="观众", seeders=31, size=11.3 * 1024 ** 3,
            downloadvolumefactor=1.0, enclosure="http://site/download/1", page_url="http://site/1",
        )
        cand = scoring.candidate_from_torrent(torrent, ["观众"])
        assert cand["src"] == "PT"
        assert cand["site"] == "观众"
        assert cand["res"] == "1080p"
        assert cand["cnsub"] is False
        assert cand["pref"] is True
        assert cand["size"] == "11.3 GB"

    def test_from_torrent_free_flag(self):
        torrent = SimpleNamespace(title=REAL_1080P, site_name="站", seeders=1, size=0,
                                  downloadvolumefactor=0.0)
        assert scoring.candidate_from_torrent(torrent, [])["free"] is True

    def test_magnet_size_is_megabytes(self):
        """javdb 磁力的 size 单位是 MB：7895 应显示为 7.7 GB，而不是 8 KB。"""
        cand = scoring.candidate_from_magnet({"hash": "a" * 40, "name": "IPZZ-961-C", "size": 7895,
                                              "cnsub": True})
        assert cand["size"] == "7.7 GB"
        assert cand["src"] == "BT"
        assert cand["hash"] == "a" * 40

    def test_torrent_carries_subtitle_and_pubdate(self):
        """副标题与发布时间要进候选（0.6.3）：任务页靠它们区分同名的多条记录。

        实测 `SONE-565` 在馒头成人区有 10 条，其中 6 条种名一字不差；
        站点副标题（馒头 `smallDescr` → `description`）才是「这一条特殊在哪」。
        """
        torrent = SimpleNamespace(
            title="SONE-565 エスワン20周年記念 AV業界史に残る最強タッグ作品",
            description="  S1美女20周年纪念版 4k x265 简体中文软字幕  ",
            site_name="馒头", seeders=44, size=8991212125, downloadvolumefactor=1.0,
            pubdate="2025-06-21 20:02:12",
        )
        cand = scoring.candidate_from_torrent(torrent, [])
        assert cand["sub"] == "S1美女20周年纪念版 4k x265 简体中文软字幕"
        assert cand["pubdate"] == "2025-06-21 20:02:12"

    def test_torrent_without_station_metadata_keeps_fields_empty(self):
        """站点没给副标题/发布时间时留空（界面据此回落显示种子原名，不编造）。"""
        torrent = SimpleNamespace(title=REAL_1080P, site_name="观众", seeders=31, size=0)
        cand = scoring.candidate_from_torrent(torrent, [])
        assert cand["sub"] == ""
        assert cand["pubdate"] == ""

    def test_magnet_has_no_subtitle_and_no_page(self):
        """BT 兜底没有发布页、也没有站点填的副标题：字段留空，别从种名里编一个。"""
        cand = scoring.candidate_from_magnet({"hash": "b" * 40, "name": "IPZZ-961-C", "size": 7895})
        assert cand["sub"] == ""
        assert cand["pubdate"] == ""


class TestPublisherLabel:
    """「发布源」文案：站点与发布组不能重复（旧版会拼出「馒头 / 馒头 发布 发布」）。"""

    def test_site_only(self):
        assert scoring.publisher_label({"site": "馒头", "group": ""}) == "馒头"

    def test_legacy_site_as_group(self):
        """历史数据里发布组被兜底成「馒头 发布」：只留站点，不再叠模板自带的「 发布」。"""
        assert scoring.publisher_label({"site": "馒头", "group": "馒头 发布"}) == "馒头"
        assert scoring.publisher_label({"site": "馒头", "group": "馒头"}) == "馒头"

    def test_real_group(self):
        assert scoring.publisher_label({"site": "馒头", "group": "CMCT"}) == "馒头 / CMCT 发布"

    def test_group_carrying_suffix(self):
        assert scoring.publisher_label({"site": "BT 公网", "group": "BT 匿名发布"}) == "BT 公网 / BT 匿名发布"

    def test_torrent_without_group_marker(self):
        """馒头成人区这类种名解析不出发布组：候选里 group 留空，文案只写站点。"""
        torrent = SimpleNamespace(title="ABP-557 無碼流出 4K 中字", site_name="馒头", seeders=5, size=0)
        cand = scoring.candidate_from_torrent(torrent, [])
        assert cand["group"] == ""
        assert scoring.publisher_label(cand) == "馒头"


class TestScoring:
    """打分规则（数值取交互演示原型口径）。"""

    def test_real_case_score_86(self):
        """真实搜索里出现过的组合：1080P + 中字 + PT + 优先站 + 做种31 = 86 分。"""
        cand = {"src": "PT", "site": "观众", "res": "1080p", "cnsub": True, "uncensored": False,
                "pref": True, "seeders": 31, "free": False}
        scoring.score_candidate(cand, rule(mustCnsub=True, preferUncensored=False))
        assert cand["score"] == 86
        assert cand["pass"] is True
        assert "1080P +30" in cand["breakdown"] and "中字 +32" in cand["breakdown"]

    def test_missing_cnsub_is_eliminated_when_required(self):
        cand = {"src": "PT", "site": "站", "res": "1080p", "cnsub": False, "pref": False,
                "seeders": 10, "free": False}
        scoring.score_candidate(cand, rule(mustCnsub=True))
        assert cand["pass"] is False
        assert "缺中字 ✗" in cand["breakdown"]

    def test_missing_cnsub_allowed_when_not_required(self):
        cand = {"src": "PT", "site": "站", "res": "1080p", "cnsub": False, "pref": False,
                "seeders": 10, "free": False}
        scoring.score_candidate(cand, rule(mustCnsub=False))
        assert cand["pass"] is True

    def test_low_seeders_eliminated(self):
        cand = {"src": "PT", "site": "站", "res": "1080p", "cnsub": True, "pref": False,
                "seeders": 1, "free": False}
        scoring.score_candidate(cand, rule(minSeeders=3))
        assert cand["pass"] is False

    def test_bt_with_unknown_seeders_not_eliminated(self):
        """BT 磁力不提供做种数，不能因此淘汰，否则兜底永远不成立。"""
        cand = {"src": "BT", "site": "BT 公网", "res": "1080p", "cnsub": True, "pref": False,
                "seeders": 0, "free": True}
        scoring.score_candidate(cand, rule(minSeeders=3))
        assert cand["pass"] is True
        assert "做种未知" in cand["breakdown"]

    def test_4k_only_counts_when_allowed(self):
        cand = {"src": "PT", "site": "站", "res": "2160p", "cnsub": True, "pref": False,
                "seeders": 10, "free": False}
        scoring.score_candidate(cand, rule(allow4k=True))
        assert "4K 择优 +16" in cand["breakdown"]
        cand2 = dict(cand, breakdown="")
        scoring.score_candidate(cand2, rule(allow4k=False))
        assert "4K 未开择优 +0" in cand2["breakdown"]

    def test_score_clamped_to_100(self):
        cand = {"src": "PT", "site": "站", "res": "1080p", "cnsub": True, "uncensored": True,
                "pref": True, "seeders": 100, "free": True}
        scoring.score_candidate(cand, rule())
        assert cand["score"] <= 100


class TestRanking:
    """排序、推荐标记与说明文案。"""

    def test_rank_orders_pass_first_then_score(self):
        good = {"src": "PT", "site": "A", "res": "1080p", "cnsub": True, "pref": False,
                "seeders": 30, "free": False}
        bad = {"src": "PT", "site": "B", "res": "1080p", "cnsub": True, "pref": False,
               "seeders": 1, "free": False}
        ranked = scoring.rank_candidates([bad, good], rule(minSeeders=3))
        assert ranked[0] is good
        assert good["picked"] is True
        assert bad["picked"] is False

    def test_explain_mentions_best_and_breakdown(self):
        good = {"src": "PT", "site": "观众", "res": "1080p", "spec": "1080p / H265",
                "cnsub": True, "pref": True, "seeders": 31, "free": False}
        ranked = scoring.rank_candidates([good], rule())
        text = scoring.explain(ranked, rule())
        assert "观众" in text and "明细" in text

    def test_explain_without_pass(self):
        bad = {"src": "PT", "site": "站", "res": "1080p", "cnsub": False, "pref": False,
               "seeders": 0, "free": False}
        ranked = scoring.rank_candidates([bad], rule(mustCnsub=True, minSeeders=5))
        assert "没有候选满足规则" in scoring.explain(ranked, rule(mustCnsub=True, minSeeders=5))
