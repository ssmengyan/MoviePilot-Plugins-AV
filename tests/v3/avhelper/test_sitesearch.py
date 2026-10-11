"""站点搜索适配层的单测：只覆盖纯函数与解析分支，不碰网络。

`app.sdk.network` 是延迟导入的，因此本模块可以在无宿主环境下直接加载——
这也是 sitesearch.py 把「请求」与「映射」分开的原因。
"""

import importlib.util
import json
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"


def load_module(name: str):
    """按文件路径加载插件模块（与 conftest 共用同一份缓存）。"""
    key = f"avhelper_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


ss = load_module("sitesearch")

MTEAM_SITE = {"id": 10, "name": "馒头", "domain": "m-team.cc", "url": "https://kp.m-team.cc/",
              "apikey": "k" * 36, "ua": "UA-TEST", "proxy": 0}
MTEAM_SITE_PROXY = dict(MTEAM_SITE, proxy=1)
ROUSI_SITE = {"id": 11, "name": "Rousi", "domain": "rousi.pro", "apikey": "pgk_test",
              "cookie": "c_secure=x", "ua": "UA-TEST", "proxy": 0}
GENERIC_SITE = {"id": 3, "name": "观众", "domain": "audiences.me", "cookie": "c=1"}

# 真实响应裁剪（2026-10-11 馒头成人区实测字段形状）
MTEAM_PAYLOAD = {
    "code": 0,
    "data": {
        "pageNumber": 1,
        "totalPages": 1,
        "data": [{
            "id": "1267679",
            "category": "410",
            "name": "IPZZ-973 元芸能人お姉さん 白石るな",
            "smallDescr": "1080p 中字",
            "size": "6544468366",
            "labelsNew": ["中字"],
            "status": {"seeders": "12", "leechers": "3", "timesCompleted": "7",
                       "createdDate": "2026-10-09 23:20:43", "discount": "PERCENT_50"},
        }],
    },
}

ROUSI_PAYLOAD = {
    "code": 0,
    "data": {"torrents": [{
        "id": 98765,
        "title": "MIDV-946 日曜の朝 石川澪",
        "subtitle": "1080p 中字",
        "size": 6544468366,
        "seeders": 21,
        "leechers": 2,
        "downloads": 33,
        "created_at": "2026-10-08T12:00:00+08:00",
        "category": {"slug": "9kg", "name": "9kg"},
        "promotion": {"is_active": True, "down_multiplier": 0.0, "up_multiplier": 1.0,
                      "until": "2026-10-12 00:00:00"},
    }]},
}


class TestAdapter:
    """站点 → 适配器分派。"""

    def test_mteam(self):
        assert ss.detect_adapter(MTEAM_SITE) == ss.ADAPTER_MTEAM

    def test_rousi(self):
        assert ss.detect_adapter(ROUSI_SITE) == ss.ADAPTER_ROUSI

    def test_generic(self):
        assert ss.detect_adapter(GENERIC_SITE) == ss.ADAPTER_MP

    def test_label_is_chinese_hint(self):
        assert "成人区" in ss.adapter_label(MTEAM_SITE)
        assert "原生" in ss.adapter_label(GENERIC_SITE)

    def test_api_host_falls_back_to_api_prefix(self):
        assert ss.mteam_api_host(MTEAM_SITE) == "api.m-team.cc"
        assert ss.mteam_api_host(dict(MTEAM_SITE, domain="api.m-team.cc")) == "api.m-team.cc"

    def test_api_host_strips_entry_subdomain(self):
        """宿主给插件的 domain 是入口子域 kp.m-team.cc（实测），不能拼成 api.kp.m-team.cc。"""
        assert ss.mteam_api_host({"domain": "kp.m-team.cc"}) == "api.m-team.cc"
        assert ss.mteam_api_host({"url": "https://kp.m-team.cc/"}) == "api.m-team.cc"
        assert ss.registered_domain("kp.m-team.cc") == "m-team.cc"
        assert ss.registered_domain("m-team.cc") == "m-team.cc"
        assert ss.registered_domain("") == ""

    def test_api_host_prefers_configured_value(self):
        assert ss.mteam_api_host(dict(MTEAM_SITE, api_domain="https://api.example.cc")) == "api.example.cc"


class TestSiteHost:
    """站点主机名口径：`domain` 可能为空或本身写成完整地址（2026-10-11 肉丝故障根因）。"""

    def test_prefers_domain(self):
        assert ss.site_host(ROUSI_SITE) == "rousi.pro"
        assert ss.site_host(dict(ROUSI_SITE, domain="kp.rousi.pro")) == "kp.rousi.pro"

    def test_falls_back_to_url(self):
        """宿主 `domain` 为空、`url` 是完整地址时，必须剥掉协议头与路径。"""
        assert ss.site_host({"url": "https://rousi.pro/"}) == "rousi.pro"
        assert ss.host_of("https://kp.m-team.cc/") == "kp.m-team.cc"
        assert ss.host_of("https://https://rousi.pro//api/x") == "rousi.pro"
        assert ss.host_of("api.m-team.cc:443/path?x=1") == "api.m-team.cc:443"
        assert ss.host_of("") == "" and ss.host_of(None) == ""

    def test_registered_domain_tolerates_full_url(self):
        assert ss.registered_domain("https://rousi.pro/") == "rousi.pro"
        assert ss.registered_domain("https://kp.m-team.cc/") == "m-team.cc"


class TestNormalizeUrl:
    """历史坏地址的修复：只认「协议头写了两遍」这一种形态。"""

    def test_repairs_double_scheme(self):
        bad = "https://https://rousi.pro//api/v1/torrents/2335"
        assert ss.normalize_url(bad) == "https://rousi.pro/api/v1/torrents/2335"

    def test_keeps_clean_url(self):
        good = "https://rousi.pro/api/v1/torrents/2335"
        assert ss.normalize_url(good) == good
        magnet = "magnet:?xt=urn:btih:abc"
        assert ss.normalize_url(magnet) == magnet
        assert ss.normalize_url("") == "" and ss.normalize_url(None) == ""

    def test_keeps_scheme_inside_query(self):
        """查询串里合法带着 `://` 的直链不能被切坏（所以不能无条件按 `://` 切分）。"""
        link = "https://jp.audiences.me/dl.php?id=1&next=https://audiences.me/x.torrent"
        assert ss.normalize_url(link) == link


class TestMteamParams:
    """馒头请求体：成人区必须显式带 mode=adult，且不带分类过滤。"""

    def test_adult_mode_default(self):
        payload = ss.mteam_search_payload("SSIS-001")
        assert payload["mode"] == "adult"
        assert payload["categories"] == []
        assert payload["pageNumber"] == 1
        assert payload["visible"] == 1

    def test_normal_mode_for_fallback(self):
        payload = ss.mteam_search_payload("SSIS-001", None)
        assert "mode" not in payload


class TestRecipe:
    """`[base64]{url}` 换票协议的编解码（与 MP 内部一致）。"""

    def test_mteam_recipe_roundtrip(self):
        enclosure = ss.mteam_recipe("api.m-team.cc", "KEY", "1267679")
        recipe, url = ss.parse_recipe(enclosure)
        assert url == "https://api.m-team.cc/api/torrent/genDlToken"
        assert recipe["method"] == "post"
        assert recipe["params"] == {"id": "1267679"}
        assert recipe["header"]["x-api-key"] == "KEY"
        assert recipe["result"] == "data"

    def test_rousi_recipe_roundtrip(self):
        enclosure = ss.rousi_recipe("rousi.pro", "pgk_x", 98765)
        recipe, url = ss.parse_recipe(enclosure)
        assert url == "https://rousi.pro/api/v1/torrents/98765"
        assert recipe["method"] == "get"
        assert recipe["header"]["Authorization"] == "Bearer pgk_x"
        assert recipe["result"] == "data.download_url"

    def test_parse_recipe_rejects_plain_url(self):
        assert ss.parse_recipe("https://example.com/a.torrent") is None
        assert ss.parse_recipe("") is None

    def test_parse_recipe_rejects_bad_base64(self):
        assert ss.parse_recipe("[not-base64]https://example.com/x") is None

    def test_pick_result(self):
        assert ss.pick_result({"data": {"download_url": "u"}}, "data.download_url") == "u"
        assert ss.pick_result({"data": {}}, "data.download_url") is None
        assert ss.pick_result(None, "data") is None


class TestRows:
    """响应 → 种子结构。"""

    def test_mteam_rows(self):
        rows = ss.mteam_rows(MTEAM_SITE, MTEAM_PAYLOAD, "KEY")
        assert len(rows) == 1
        row = rows[0]
        assert row["title"].startswith("IPZZ-973")
        assert row["seeders"] == 12
        assert row["size"] == 6544468366
        assert row["site"] == 10
        assert row["adapter"] == ss.ADAPTER_MTEAM
        assert row["downloadvolumefactor"] == 0.5
        assert row["page_url"] == "https://kp.m-team.cc/detail/1267679"
        assert ss.parse_recipe(row["enclosure"]) is not None

    def test_mteam_rows_empty_on_bad_payload(self):
        assert ss.mteam_rows(MTEAM_SITE, {"code": 0, "data": {}}, "KEY") == []
        assert ss.mteam_rows(MTEAM_SITE, None, "KEY") == []

    def test_mteam_discount_promotion_overrides(self):
        dvf, uvf, _ = ss.mteam_discount({"discount": "PERCENT_50", "promotionRule": {"discount": "FREE"}})
        assert dvf == 0.0 and uvf == 1.0

    def test_mteam_discount_mall_single_free(self):
        dvf, _, freedate = ss.mteam_discount({"discount": "NORMAL",
                                             "mallSingleFree": {"status": "ONGOING",
                                                                "endDate": "2026-10-20 00:00:00"}})
        assert dvf == 0.0
        assert freedate == "2026-10-20 00:00:00"

    def test_rousi_rows(self):
        rows = ss.rousi_rows(ROUSI_SITE, ROUSI_PAYLOAD, "pgk_test")
        assert len(rows) == 1
        row = rows[0]
        assert row["title"].startswith("MIDV-946")
        assert row["seeders"] == 21
        assert row["downloadvolumefactor"] == 0.0
        assert row["labels"] == ["9kg"]
        assert row["page_url"] == "https://rousi.pro/torrents/98765"
        assert ss.parse_recipe(row["enclosure"]) is not None

    def test_rousi_rows_host_from_url_when_domain_empty(self):
        """回归：`domain` 为空会退回 `url`（完整地址），不能拼成 `https://https://…`。"""
        site = dict(ROUSI_SITE, domain="")
        site["url"] = "https://rousi.pro/"
        rows = ss.rousi_rows(site, ROUSI_PAYLOAD, "pgk_test")
        _, url = ss.parse_recipe(rows[0]["enclosure"])
        assert url == "https://rousi.pro/api/v1/torrents/98765"
        assert rows[0]["page_url"] == "https://rousi.pro/torrents/98765"

    def test_rousi_rows_empty(self):
        assert ss.rousi_rows(ROUSI_SITE, {"data": {}}, "k") == []


class TestResolve:
    """enclosure → 下载器能直接吃的内容。"""

    def test_magnet_passthrough(self):
        searcher = ss.SiteSearcher()
        content, why = searcher.resolve("magnet:?xt=urn:btih:abc")
        assert content == "magnet:?xt=urn:btih:abc" and why == ""

    def test_empty_enclosure(self):
        searcher = ss.SiteSearcher()
        content, why = searcher.resolve("")
        assert content is None and "缺少下载地址" in why

    def test_recipe_redeem_and_fetch(self, monkeypatch):
        searcher = ss.SiteSearcher()
        monkeypatch.setattr(searcher, "_redeem",
                            lambda recipe, url, site: ("https://api.m-team.cc/api/rss/dlv2?sign=x", ""))
        monkeypatch.setattr(searcher, "_fetch_bytes",
                            lambda url, site=None, recipe=None: b"d8:announce" + b"x" * 200)
        enclosure = ss.mteam_recipe("api.m-team.cc", "KEY", "1")
        content, why = searcher.resolve(enclosure, MTEAM_SITE)
        assert isinstance(content, bytes) and why == ""

    def test_recipe_redeem_failure(self, monkeypatch):
        searcher = ss.SiteSearcher()
        monkeypatch.setattr(searcher, "_redeem", lambda recipe, url, site: (None, ""))
        enclosure = ss.rousi_recipe("rousi.pro", "k", 1)
        content, why = searcher.resolve(enclosure, ROUSI_SITE)
        assert content is None and "换票失败" in why

    def test_recipe_redeem_failure_carries_reason(self, monkeypatch):
        """失败原因必须透出来：旧版只有一句话，坏地址与接口报错长得一模一样。"""
        searcher = ss.SiteSearcher()
        monkeypatch.setattr(searcher, "_redeem",
                            lambda recipe, url, site: (None, "站点返回 HTTP 403"))
        content, why = searcher.resolve(ss.rousi_recipe("rousi.pro", "k", 1), ROUSI_SITE)
        assert content is None and "换票失败" in why and "403" in why

    def test_redeem_normalizes_request_url(self, monkeypatch):
        """回归：任务候选里躺着的 `https://https://host//…` 要在请求前修回来。"""
        searcher = ss.SiteSearcher()
        seen = {}

        def fake_call(client, method, url, **kwargs):
            seen["url"] = url
            return None, "InvalidURL: bad url"

        monkeypatch.setattr(searcher, "_http", lambda **kwargs: object())
        monkeypatch.setattr(searcher, "_call", fake_call)
        url, why = searcher._redeem({"method": "get", "result": "data.download_url"},
                                   "https://https://rousi.pro//api/v1/torrents/2335", ROUSI_SITE)
        assert seen["url"] == "https://rousi.pro/api/v1/torrents/2335"
        assert url is None and "InvalidURL" in why

    def test_redeem_reports_status_and_missing_field(self, monkeypatch):
        searcher = ss.SiteSearcher()
        monkeypatch.setattr(searcher, "_http", lambda **kwargs: object())

        class Resp:
            def __init__(self, status, payload=None):
                self.status_code = status
                self._payload = payload

            def json(self):
                return self._payload

        monkeypatch.setattr(searcher, "_call", lambda *a, **k: (Resp(502), ""))
        assert searcher._redeem({"method": "get", "result": "data.download_url"}, "https://rousi.pro/x", ROUSI_SITE) \
            == (None, "站点返回 HTTP 502")

        monkeypatch.setattr(searcher, "_call",
                            lambda *a, **k: (Resp(200, {"message": "api key 无效", "data": {}}), ""))
        url, why = searcher._redeem({"method": "get", "result": "data.download_url"},
                                    "https://rousi.pro/x", ROUSI_SITE)
        assert url is None and "data.download_url" in why and "api key 无效" in why

    def test_direct_url_falls_back_to_url(self, monkeypatch):
        """直链取不回字节时，把直链交给下载器（由下载器带 Cookie 去取）。"""
        searcher = ss.SiteSearcher()
        monkeypatch.setattr(searcher, "_fetch_bytes", lambda url, site=None, recipe=None: None)
        content, why = searcher.resolve("https://audiences.me/download.php?id=1", GENERIC_SITE)
        assert content == "https://audiences.me/download.php?id=1" and why == ""

    def test_direct_url_returns_bytes(self, monkeypatch):
        searcher = ss.SiteSearcher()
        monkeypatch.setattr(searcher, "_fetch_bytes",
                            lambda url, site=None, recipe=None: b"d8:announce" + b"y" * 200)
        content, _ = searcher.resolve("https://audiences.me/download.php?id=1", GENERIC_SITE)
        assert isinstance(content, bytes)


class TestSearchDispatch:
    """站点搜索分派：馒头/肉丝/其它三条路径各自走到对应实现。"""

    def test_mteam_without_apikey_reports_reason(self):
        searcher = ss.SiteSearcher()
        rows, note = searcher.search(dict(MTEAM_SITE, apikey=""), "SSIS-001")
        assert rows == [] and "API Key" in note

    def test_generic_uses_chain_without_mtype(self):
        calls = {}

        class FakeChain:
            def search_site_torrents(self, site, keyword, mtype=None, page=0):
                calls["mtype"] = mtype
                calls["keyword"] = keyword
                return [{"title": "MIDV-946 1080p", "site_name": "观众", "enclosure": "http://x/a.torrent",
                         "size": 100, "seeders": 5, "site": 3}]

        rows, note = ss.SiteSearcher(chain=FakeChain()).search(GENERIC_SITE, "MIDV-946")
        assert calls == {"mtype": None, "keyword": "MIDV-946"}
        assert len(rows) == 1 and rows[0]["adapter"] == ss.ADAPTER_MP
        assert "命中" in note

    def test_adapter_exception_is_contained(self):
        searcher = ss.SiteSearcher()

        def boom(site, keyword):
            raise RuntimeError("boom")

        searcher._search_mteam = boom
        rows, note = searcher.search(MTEAM_SITE, "X")
        assert rows == [] and "搜索异常" in note

    def test_rousi_search_url_falls_back_to_site_url(self, monkeypatch):
        """回归：搜索地址也要用 `site_host()`，否则 domain 为空会拼成 `https:///api/v1/torrents`。"""
        searcher = ss.SiteSearcher()
        seen = {}

        def fake_call(client, method, url, **kwargs):
            seen["url"] = url
            return None, "stop here"

        monkeypatch.setattr(searcher, "_http", lambda **kwargs: object())
        monkeypatch.setattr(searcher, "_call", fake_call)
        rows, note = searcher.search({"name": "Rousi", "domain": "", "url": "https://rousi.pro/",
                                      "apikey": "pgk_test"}, "MIDV-946")
        assert seen["url"] == "https://rousi.pro/api/v1/torrents"
        assert rows == [] and "搜索失败" in note

    def test_rousi_search_without_host_reports_reason(self):
        """肉丝这条路径：主机名为空时给明确原因，而不是拼出 `https:///api/v1/torrents`。"""
        searcher = ss.SiteSearcher()
        rows, note = searcher._search_rousi({"name": "Rousi", "domain": "", "url": "",
                                            "apikey": "k"}, "X")
        assert rows == [] and "域名" in note
