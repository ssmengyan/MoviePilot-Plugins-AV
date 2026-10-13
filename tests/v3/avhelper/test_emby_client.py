"""`EmbyClient` 写侧的单测：**全部用假 HTTP 层，绝不连真 Emby**。

为什么必须这样测：`EmbyClient` 的每一条行为都是「真机上会写坏用户媒体库」的那种 ——
差量 DTO 会 400、`ProviderIds` 会整份覆盖顶掉 MetaTube 的键、头像编码错了会 500。
这些口径来自 P0-① / P0-② 的实机报告（`_tmp/p0/REPORT-1.md` / `REPORT-2.md`），
所以这里把「发出去的请求长什么样」逐条钉死，而不是验「差不多能跑」。

假 HTTP 层替换的是 `emby_mod.RequestUtils`（模块级符号），不是宿主里那个真货：
`conftest.py` 已经把 `app.sdk.network` 装成空壳，这里再换成本文件的 `FakeRequestUtils`。
"""

import base64
import json

import pytest


class FakeReply:
    """一次假响应：状态码 + JSON 正文（或纯文本正文）。"""

    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text if text else (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeRequestUtils:
    """按 `(method, path-substring)` 路由的假 `RequestUtils`，记录每一次调用。

    用法：`fake.on("get", "/emby/Users", [ ... ])`；同一条路由可以 `on()` 多次，
    第 N 次调用取第 N 个回复（用来演「第一次 404、第二次 200」这种序列）。
    """

    calls = []          # 类属性只是给类型提示，实例里会覆盖
    routes = {}
    hits = {}

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")
        self.calls = []
        self.routes = {}
        self.hits = {}

    def on(self, method, path_part, reply):
        self.routes.setdefault((method.lower(), path_part), []).append(reply)
        self.hits.setdefault((method.lower(), path_part), 0)
        return self

    # ---- 假 HTTP 方法（与真 RequestUtils 同签名）----
    def get_res(self, url, params=None, **kwargs):
        return self._reply("get", url, params, kwargs)

    def post_res(self, url, data=None, params=None, **kwargs):
        return self._reply("post", url, params, kwargs, data=data)

    def delete_res(self, url, data=None, params=None, **kwargs):
        return self._reply("delete", url, params, kwargs, data=data)

    def _reply(self, method, url, params, kwargs, data=None):
        self.calls.append({
            "method": method, "url": url, "params": dict(params or {}),
            "data": data, "headers": dict(kwargs.get("headers") or {}),
            "json": kwargs.get("json"),
        })
        # 同一路由排多个回复 = 按调用次序依次返回（第一次搜索回空、第二次回全量…）；
        # 最后一个回复会被复用，所以「排 2 个却调了 3 次」不会 IndexError。
        # 匹配顺序按 path_part 长度**从长到短**：`/emby/Items/7` 与 `/emby/Users` 都能
        # 命中 `/emby/Users/u9/Items/7`，不排序就会让短的把长的抢走。
        matches = sorted((k for k in self.routes if k[0] == method and k[1] in url),
                         key=lambda k: len(k[1]), reverse=True)
        if not matches:
            return FakeReply(404, text="not routed")
        key = matches[0]
        replies = self.routes[key]
        nth = self.hits[key]
        self.hits[key] = nth + 1
        return replies[min(nth, len(replies) - 1)]


@pytest.fixture
def fake_http(emby_mod, monkeypatch):
    """装好假 HTTP 层，返回**那个**假实例（用例先排路由，再调插件方法）。

    插件代码每次都 `RequestUtils(timeout=…)` 新建实例（与真宿主一样），所以工厂
    统一返回同一个假实例 —— 这样路由可以在发请求**之前**排好，调用记录也连续。
    """
    inst = FakeRequestUtils()

    def factory(*args, **kwargs):
        return inst

    monkeypatch.setattr(emby_mod, "RequestUtils", factory)
    return inst


@pytest.fixture
def boom_http(emby_mod, monkeypatch):
    """让底层每次请求都抛异常 —— 验「绝不抛异常」这条纪律。"""
    class Boom:
        def __init__(self, *args, **kwargs):
            pass

        def _raise(self, *args, **kwargs):
            raise RuntimeError("connection reset")

        get_res = post_res = delete_res = _raise

    monkeypatch.setattr(emby_mod, "RequestUtils", Boom)
    return Boom


def _client(emby_mod, host="http://emby.test:8096", apikey="KEY"):
    return emby_mod.EmbyClient(host, apikey)


def _last(fake_http, method, path_part=""):
    for call in reversed(fake_http.calls):
        if call["method"] == method and path_part in call["url"]:
            return call
    return None


def _calls(fake_http, method, path_part=""):
    return [c for c in fake_http.calls
            if c["method"] == method and path_part in c["url"]]


def _ends(fake_http, method, suffix):
    """URL **以 `suffix` 结尾**的调用。

    子串匹配在这里不够用：管理员维度的 `/emby/Users/cfa1/Items/12598` 也包含
    `/emby/Items/12598`，用它判「有没有走无维度直查」会假阳性。
    """
    return [c for c in fake_http.calls
            if c["method"] == method and c["url"].endswith(suffix)]


USERS = [
    {"Id": "u1", "Name": "sky", "Policy": {"IsAdministrator": False}},
    {"Id": "cfa1", "Name": "av", "Policy": {"IsAdministrator": True}},
    {"Id": "u3", "Name": "guest", "Policy": {"IsAdministrator": True}},
]


class TestAdminUserId:
    """`admin_user_id()` 必须挑**管理员**，不是"第一个用户"。"""

    def test_picks_first_administrator(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        assert c.admin_user_id() == "cfa1"

    def test_caches_the_answer(self, emby_mod, fake_http):
        """写一次要读一遍 DTO，不该每次都顺手再查一遍用户表。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        c.admin_user_id()
        c.admin_user_id()
        assert len(_calls(fake_http, "get", "/emby/Users")) == 1

    def test_no_admin_degrades_to_first_user(self, emby_mod, fake_http):
        """一个管理员都没有时降级用第一个用户（并留 warning），不能返回空串就罢工。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, [
            {"Id": "only", "Name": "x", "Policy": {}},
        ]))
        assert c.admin_user_id() == "only"

    def test_unreachable_returns_blank(self, emby_mod, fake_http):
        """拿不到就返回空串，**不抛异常**。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(500, text="boom"))
        assert c.admin_user_id() == ""

    def test_request_exception_is_swallowed(self, emby_mod, fake_http, boom_http):
        """HTTP 层自己炸了也不能把调用方带崩。"""
        c = emby_mod.EmbyClient("http://emby.test:8096", "KEY")
        assert c.admin_user_id() == ""
        assert c.get_item("12598") is None
        assert c.people_of("12598") == []
        assert c.find_person("某人") is None


class TestGetItem:
    """`get_item()` 走管理员维度（本机唯一可用的完整 DTO 读法）。"""

    def test_uses_admin_dimension(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/emby/Users/cfa1/Items/12598", FakeReply(200, {"Id": "12598", "Name": "SNOS-380"}))
        dto = c.get_item("12598")
        assert dto["Name"] == "SNOS-380"
        assert _calls(fake_http, "get", "/emby/Users/cfa1/Items/12598")
        assert not _ends(fake_http, "get", "/emby/Items/12598")     # 没走无维度直查

    def test_explicit_user_id_wins(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users/u9/Items/7", FakeReply(200, {"Id": "7"}))
        assert c.get_item("7", "u9") == {"Id": "7"}
        # 明确给了 user_id 就不该再去查用户表（精确到"就是 /emby/Users 这一条"）
        assert not _ends(fake_http, "get", "/emby/Users")

    def test_falls_back_to_plain_items(self, emby_mod, fake_http):
        """管理员维度不通时的兜底（别的 Emby 版本可能需要它）。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/emby/Users/cfa1/Items/7", FakeReply(404, text="nope"))
        fake_http.on("get", "/emby/Items/7", FakeReply(200, {"Id": "7", "Name": "fallback"}))
        assert c.get_item("7")["Name"] == "fallback"

    def test_missing_item_returns_none(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/Items/404", FakeReply(404, text="gone"))
        assert c.get_item("404") is None

    def test_unconfigured_is_none(self, emby_mod, fake_http):
        assert emby_mod.EmbyClient("", "").get_item("1") is None


class TestUpdateItem:
    """`update_item()` 自己 read-modify-write（P0-① 的唯一安全写法）。"""

    BASE = {
        "Id": "12598", "Etag": "abc", "Path": "/Media/9kg/avi/SNOS-380.mp4",
        "Name": "SNOS-380", "SortName": "SNOS-380", "Overview": "",
        "ProviderIds": {"MetaTube": "JavBus:SNOS-380"},
        "People": [], "Studios": [], "Genres": [], "GenreItems": [],
        "MediaSources": [{"Id": "mediasource_12598", "Size": 7932643525}],
        "RunTimeTicks": 99493394000, "DateCreated": "2026-10-13T17:40:41.0000000Z",
    }

    def _prep(self, fake_http, base=None):
        """排好一条完整的 read-modify-write 路由，返回「被读的那份 DTO」。

        `base` 给了就替掉默认 DTO；缺的集合键补成 `None` —— 模拟 Emby 把空集合返回成 null
        的那种 DTO（P0-③ 要的就是这个分支）。
        """
        dto = dict(self.BASE if base is None else base)
        for key in ("People", "Studios", "Genres", "GenreItems"):
            dto.setdefault(key, None)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/emby/Users/cfa1/Items/12598", FakeReply(200, dto))
        fake_http.on("post", "/emby/Items/12598", FakeReply(204))
        return dto

    def test_posts_full_dto_with_readonly_stripped(self, emby_mod, fake_http):
        """载荷是「完整 DTO 剔只读键」，不是差量 DTO（差量会 400）。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, detail = c.update_item("12598", {"Name": "SNOS-380 新标题"})
        assert (ok, detail) == (True, "")
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["Name"] == "SNOS-380 新标题"
        for gone in ("Id", "Etag", "Path", "MediaSources", "RunTimeTicks", "DateCreated"):
            assert gone not in body, f"{gone} 是只读键，必须剔掉"
        assert body["ProviderIds"] == {"MetaTube": "JavBus:SNOS-380"}

    def test_provider_ids_are_merged_not_replaced(self, emby_mod, fake_http):
        """核心红线：只写自己的键不能顶掉 MetaTube 的键。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, _ = c.update_item("12598", {"ProviderIds": {"AVHelper": "SNOS-380"}})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["ProviderIds"] == {"MetaTube": "JavBus:SNOS-380", "AVHelper": "SNOS-380"}

    def test_provider_ids_replace_when_asked(self, emby_mod, fake_http):
        """要整份覆盖必须显式说 —— 默认不允许悄悄抹掉别人的 provider。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, _ = c.update_item("12598", {"ProviderIds": {"AVHelper": "SNOS-380"},
                                        "provider_ids_replace": True})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["ProviderIds"] == {"AVHelper": "SNOS-380"}

    def test_null_collections_become_empty_lists(self, emby_mod, fake_http):
        """P0-③：`null` 集合会 400（ToList(null)）→ 出去之前写成 `[]`。"""
        c = _client(emby_mod)
        self._prep(fake_http, dict(self.BASE, People=None, Studios=None, Genres=None))
        ok, _ = c.update_item("12598", {"Name": "x"})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        for key in ("People", "Studios", "Genres", "GenreItems"):
            assert body[key] == [], f"{key} 为 null 必须收尾成 []"

    def test_provider_ids_always_present(self, emby_mod, fake_http):
        """`ProviderIds` 缺席 = 400，所以哪怕原 DTO 里没有也必须补一个非 null 值。"""
        c = _client(emby_mod)
        self._prep(fake_http, {k: v for k, v in self.BASE.items() if k != "ProviderIds"})
        ok, _ = c.update_item("12598", {"Name": "x"})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["ProviderIds"] == {}

    def test_ineffective_keys_are_dropped(self, emby_mod, fake_http):
        """`RunTimeTicks` / `RemoteTrailers` / 排序名三件套：实测无效 → 丢掉，不报错不重试。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, _ = c.update_item("12598", {
            "RunTimeTicks": 123456789000,
            "RemoteTrailers": [{"Url": "https://x/y.mp4"}],
            "sort_name": "SNOS-380",
            "Name": "SNOS-380 新",
        })
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["Name"] == "SNOS-380 新"
        for gone in ("RunTimeTicks", "RemoteTrailers", "ForcedSortName", "LockedFields"):
            assert gone not in body, f"{gone} 实测无效，不该出现在写载荷里"
        # `SortName` 是只读键（派生字段，且 P0-③ 裁决不写），所以也不在载荷里
        assert "SortName" not in body

    def test_sort_name_only_when_explicitly_asked(self, emby_mod, fake_http):
        """留的显式开关：确实要钉死排序名时才写三件套。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, _ = c.update_item("12598", {"Name": "SNOS-380 新", "sort_name": "SNOS-380",
                                        "_allow_sort_name": True})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["ForcedSortName"] == "SNOS-380"
        assert "SortName" in (body.get("LockedFields") or [])

    def test_genres_marker_translates_to_genre_items(self, emby_mod, fake_http):
        """`Genres` 字符串数组被忽略 → 标记位翻译成 `GenreItems=[{Name,Id}]`。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, _ = c.update_item("12598", {"genres": [{"Name": "4K", "Id": 10808}]})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert body["GenreItems"] == [{"Name": "4K", "Id": 10808}]
        assert body["Genres"] == ["4K"]

    def test_readonly_override_is_rejected(self, emby_mod, fake_http):
        """调用方误传只读键 → 丢掉（既不写进去，也不原样回灌）。"""
        c = _client(emby_mod)
        self._prep(fake_http)
        ok, _ = c.update_item("12598", {"Name": "x", "Path": "/evil/path.mp4"})
        assert ok
        body = _last(fake_http, "post", "/emby/Items/12598")["json"]
        assert "Path" not in body, "只读键不该出现在写载荷里（传了也不会被采纳）"
        assert body["Name"] == "x"


class TestUpdateItemFailures:
    """失败一律 `(False, 原因)`，**绝不抛异常**。"""

    def test_http_400_is_reported(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/Items/12598", FakeReply(200, {"Id": "12598"}))
        fake_http.on("post", "/emby/Items/12598", FakeReply(400, text="Value cannot be null"))
        ok, detail = c.update_item("12598", {"Name": "x"})
        assert ok is False and "400" in detail

    def test_unreadable_dto_does_not_post(self, emby_mod, fake_http):
        """read-modify-write 的第一半失败时，**一个写请求都不许发**。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/Items/12598", FakeReply(404, text="gone"))
        ok, detail = c.update_item("12598", {"Name": "x"})
        assert ok is False and "读不到" in detail
        assert not _calls(fake_http, "post")

    def test_empty_override_is_refused(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        ok, detail = c.update_item("12598", {})
        assert ok is False and detail
        assert not _calls(fake_http, "post")

    def test_unconfigured_is_refused(self, emby_mod, fake_http):
        ok, detail = emby_mod.EmbyClient("", "").update_item("1", {"Name": "x"})
        assert ok is False and detail

    def test_network_exception_is_swallowed(self, emby_mod, fake_http, boom_http):
        """底层抛异常时返回 (False, 原因)，不往外冒泡。"""
        c = emby_mod.EmbyClient("http://emby.test:8096", "KEY")
        ok, detail = c.update_item("12598", {"Name": "x"})
        assert ok is False and detail
        assert c.get_item("12598") is None
        assert c.upload_image("12598", "Primary", b"\xff\xd8\xff")[0] is False
        assert c.delete_image("12598", "Primary")[0] is False


class TestUploadImage:
    """★ D16：body 必须是 **base64 的 ASCII 文本**，`Content-Type` 必须是 `image/jpeg`。"""

    RAW = b"\xff\xd8\xff\xdb" + b"\x00" * 60      # 一段"像 JPEG"的字节

    def test_body_is_base64_ascii_with_jpeg_header(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("post", "/Images/Primary", FakeReply(204))
        ok, detail = c.upload_image("12598", "Primary", self.RAW)
        assert (ok, detail) == (True, "")
        call = _last(fake_http, "post", "/Images/Primary")
        assert call["headers"].get("Content-Type") == "image/jpeg"
        # body 是 ASCII 文本，且解码回来正是原字节（裸字节会 500）
        assert isinstance(call["data"], str)
        assert call["data"].isascii()
        assert base64.b64decode(call["data"]) == self.RAW
        # 不能是裸字节（那是 P0-① 的第一条反例：500 not a valid Base-64 string）
        assert not isinstance(call["data"], (bytes, bytearray))

    def test_api_key_travels_in_params(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("post", "/Images/Primary", FakeReply(204))
        c.upload_image("12598", "Primary", self.RAW)
        assert _last(fake_http, "post", "/Images/Primary")["params"]["api_key"] == "KEY"

    def test_person_image_uses_same_rules(self, emby_mod, fake_http):
        """头像（Person 的 Primary）与影片封面走的是同一条格式约束。"""
        c = _client(emby_mod)
        fake_http.on("post", "/emby/Items/11265/Images/Primary", FakeReply(204))
        ok, _ = c.upload_image("11265", "Primary", self.RAW)
        assert ok
        call = _last(fake_http, "post", "/emby/Items/11265/Images/Primary")
        assert call["headers"]["Content-Type"] == "image/jpeg"
        assert base64.b64decode(call["data"]) == self.RAW

    @pytest.mark.parametrize("status", [400, 500])
    def test_failure_is_a_tuple_not_an_exception(self, emby_mod, fake_http, status):
        c = _client(emby_mod)
        fake_http.on("post", "/Images/Primary",
                             FakeReply(status, text="not a valid Base-64 string"))
        ok, detail = c.upload_image("12598", "Primary", self.RAW)
        assert ok is False and str(status) in detail

    def test_empty_bytes_refused(self, emby_mod, fake_http):
        c = _client(emby_mod)
        ok, detail = c.upload_image("12598", "Primary", b"")
        assert ok is False and detail
        assert not _calls(fake_http, "post")

    def test_delete_image_accepts_404(self, emby_mod, fake_http):
        """删一张本来就有的/没有的图都算成功（幂等），回滚流程才不会被 404 卡住。"""
        c = _client(emby_mod)
        fake_http.on("delete", "/Images/Primary", FakeReply(204))
        assert c.delete_image("12598", "Primary") == (True, "")

    def test_delete_image_404_is_ok(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("delete", "/Images/Primary", FakeReply(404, text="no image"))
        assert c.delete_image("12598", "Primary") == (True, "")

    def test_delete_image_failure(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("delete", "/Images/Primary", FakeReply(500, text="boom"))
        ok, detail = c.delete_image("12598", "Primary")
        assert ok is False and "500" in detail


class TestImageUrl:
    """`image_url()` 的拼接形状（局域网直取原图，带 api_key）。"""

    def test_shape(self, emby_mod, fake_http):
        c = _client(emby_mod)
        assert (c.image_url("12598")
                == "http://emby.test:8096/emby/Items/12598/Images/Primary?api_key=KEY")

    def test_custom_type_and_trailing_slash_host(self, emby_mod, fake_http):
        c = emby_mod.EmbyClient("http://emby.test:8096/", "KEY")
        assert (c.image_url("11265", "Thumb")
                == "http://emby.test:8096/emby/Items/11265/Images/Thumb?api_key=KEY")

    def test_blank_inputs_are_harmless(self, emby_mod, fake_http):
        c = _client(emby_mod)
        assert c.image_url("") == ""
        assert emby_mod.EmbyClient("", "KEY").image_url("1") == ""

    def test_no_apikey_no_query(self, emby_mod, fake_http):
        c = emby_mod.EmbyClient("http://emby.test:8096", "")
        assert c.image_url("1") == "http://emby.test:8096/emby/Items/1/Images/Primary"


class TestPeople:
    """`people_of()` / `person_item()`：读，不写。"""

    def test_people_of_returns_list(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/emby/Users/cfa1/Items/12598", FakeReply(200, {
            "Id": "12598",
            "People": [{"Name": "某某（そめそめ）", "Type": "Actor"},
                       {"Name": "导演甲", "Type": "Director"}],
        }))
        people = c.people_of("12598")
        assert [p["Name"] for p in people] == ["某某（そめそめ）", "导演甲"]

    def test_people_of_empty_and_missing(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/Items/1", FakeReply(200, {"Id": "1"}))
        assert c.people_of("1") == []
        assert c.people_of("") == []

    def test_person_item_by_id(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Items/11265", FakeReply(200, {"Id": "11265"}))
        assert c.person_item("11265") == {"Id": "11265"}
        assert c.person_item("") is None


class TestFindPerson:
    """`find_person()` 按 `Name` **精确相等**匹配（D13）；判空看 `Items`（D19）。"""

    PERSON = {"Id": "11265", "Name": "皆川千遥（みながわ千遥）", "Type": "Person"}

    def test_exact_match(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Persons", FakeReply(200, {
            "Items": [self.PERSON], "TotalRecordCount": 1,
        }))
        assert c.find_person("皆川千遥（みながわ千遥）") == self.PERSON

    def test_uses_items_not_total_record_count(self, emby_mod, fake_http):
        """D19：实测出现过 `total=0` 但 `Items` 非空 —— 判空必须看 `Items`。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Persons", FakeReply(200, {
            "Items": [self.PERSON], "TotalRecordCount": 0,
        }))
        assert c.find_person("皆川千遥（みながわ千遥）") == self.PERSON

    def test_non_exact_names_do_not_match(self, emby_mod, fake_http):
        """整名匹配，不做子串/前缀 —— 搜 `皆川千遥` 不该命中 `皆川千遥（みながわ千遥）`。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Users", FakeReply(200, USERS))
        fake_http.on("get", "/emby/Persons", FakeReply(200, {"Items": [self.PERSON]}))
        for wrong in ("皆川千遥", "みながわ千遥", "皆川", "千遥"):
            assert c.find_person(wrong) is None, wrong

    def test_picks_the_exact_one_out_of_many(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Persons", FakeReply(200, {"Items": [
            {"Id": "1", "Name": "皆川千遥"},
            {"Id": "2", "Name": "皆川千遥（みながわ千遥）"},
            {"Id": "3", "Name": "みながわ千遥"},
        ]}))
        assert c.find_person("皆川千遥")["Id"] == "1"
        assert c.find_person("みながわ千遥")["Id"] == "3"

    def test_falls_back_to_full_roster(self, emby_mod, fake_http):
        """`SearchTerm` 那条回空时退回全量名册（本机 179 个 Person，一个请求的事）。"""
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Persons?SearchTerm=", FakeReply(200, {"Items": [], "TotalRecordCount": 0}))
        fake_http.on("get", "/emby/Persons", FakeReply(200, {"Items": [self.PERSON]}))
        assert c.find_person(self.PERSON["Name"]) == self.PERSON

    def test_not_found_returns_none(self, emby_mod, fake_http):
        c = _client(emby_mod)
        fake_http.on("get", "/emby/Persons", FakeReply(200, {"Items": [], "TotalRecordCount": 0}))
        assert c.find_person("不存在的人") is None

    def test_blank_name_short_circuits(self, emby_mod, fake_http):
        c = _client(emby_mod)
        assert c.find_person("") is None
        assert not fake_http.calls


class TestDisplayNumberNormalisation:
    """`display_number` 的数字段**先 int 再补零**（S11 全库实测的丢数据级口径）。

    真实文件名里有多余前导零（`ipzz00586_1_4K.mp4`）：保留就会产出 `IPZZ-00586`，
    拿它去 javdb 查**直接「找不到番号」**；`IPZZ-586` 立刻命中。
    """

    @pytest.mark.parametrize("text,display,key", [
        ("ipzz00586_1_4K.mp4", "IPZZ-586", "IPZZ586"),
        ("IPZZ-00586.mp4", "IPZZ-586", "IPZZ586"),
        ("MIDV-0946.mp4", "MIDV-946", "MIDV946"),
        ("MIDV-0946", "MIDV-946", "MIDV946"),
        # 不足 3 位补零的行为不变
        ("CAWB-040.mp4", "CAWB-040", "CAWB40"),
        ("SSIS-001.mp4", "SSIS-001", "SSIS1"),
    ])
    def test_extra_leading_zeros_dropped(self, emby_mod, text, display, key):
        parsed = emby_mod.parse_av_number(text)
        assert (parsed.display_number, parsed.norm_key) == (display, key)

    def test_three_digit_padding_still_works(self, emby_mod):
        """补零方向没被改坏：两位数字段仍然补成三位（`SSIS-01` → `SSIS-001`）。

        注意 `SSIS-1`（一位）本来就**不解析**：`_BODY_NUM` 的数字段是 `\\d{2,7}`，
        一位数在真实文件名里太容易撞（版本号、碟号、分辨率），宁可认不出。
        """
        assert emby_mod.parse_av_number("SSIS-01.mp4").display_number == "SSIS-001"
        assert emby_mod.parse_av_number("SSIS-1.mp4").matched is False


class TestProviderIdsCaseInsensitive:
    """`_item_keys()` 取 `ProviderIds` 必须**大小写不敏感**（S11：112 条里 50 条是小写）。"""

    @staticmethod
    def _item(provider_ids):
        return {"Id": "12292", "Name": "", "Path": "/Media/9kg/avi/zzz.mp4",
                "ProviderIds": provider_ids}

    @pytest.mark.parametrize("spelling", ["MetaTube", "metatube", "METATUBE", "Metatube"])
    def test_any_spelling_yields_the_key(self, emby_mod, spelling):
        keys = emby_mod._item_keys(self._item({spelling: "JavBus:CAWD-989"}))
        assert "CAWD989" in keys, keys

    def test_lower_and_upper_agree(self, emby_mod):
        """同一份索引里两种写法必须给出同一套键，否则等于同一部片算两个号。"""
        low = emby_mod._item_keys(self._item({"metatube": "JavBus:CAWD-989"}))
        up = emby_mod._item_keys(self._item({"MetaTube": "JavBus:CAWD-989"}))
        assert low == up

    @pytest.mark.parametrize("spelling", ["JavDB", "javdb", "JAVDB"])
    def test_javdb_provider_also_read(self, emby_mod, spelling):
        """`JavDB` 是我们自己写进去的键，一并兼容。"""
        keys = emby_mod._item_keys(self._item({spelling: "javdb:abc123"}))
        assert "ABC123" in keys, keys

    def test_missing_or_null_provider_ids_is_harmless(self, emby_mod):
        """全库有 6 条完全没有 ProviderIds，不能因此报错。"""
        assert emby_mod._item_keys(self._item(None))
        assert emby_mod._item_keys({"Id": "1", "Name": "", "Path": "/x/y.mp4"})


class TestNameWithTrailingText:
    """「番号在前、后面挂内容」→ `matched=False` 是**预期行为**（S11 已通知 S7）。

    MetaTube 会把中文翻译标题整串写进 `Name`，那种串**不是**番号源：
    实测 `Name` 解析只有 6/112 命中，所以宁可认不出，也不要在标题里乱猜番号。
    """

    @pytest.mark.parametrize("text", [
        "IPZZ-912 某部片",
        "SNOS-380 中文翻译标题在这里",
        "IPZZ-912 完全不是番号的一段中文标题",
    ])
    def test_trailing_content_is_not_matched(self, emby_mod, text):
        parsed = emby_mod.parse_av_number(text)
        assert parsed.matched is False
        assert parsed.display_number == "" and parsed.norm_key == ""

    def test_pure_version_suffix_still_matches(self, emby_mod):
        """但「番号 + 版本后缀」要照旧命中（`中字`/`流出` 是后缀词，不是标题）。"""
        assert emby_mod.parse_av_number("MIDV-946 中字").matched is True


class TestWritePayloadHelpers:
    """模块级写载荷助手（S7 的 `/scrape/preview` 会直接用它们做字段级 diff）。"""

    def test_merge_provider_ids_keeps_existing(self, emby_mod):
        got = emby_mod.merge_provider_ids({"MetaTube": "JavBus:X"}, {"AVHelper": "Y"})
        assert got == {"MetaTube": "JavBus:X", "AVHelper": "Y"}

    def test_merge_provider_ids_handles_garbage(self, emby_mod):
        assert emby_mod.merge_provider_ids(None, None) == {}
        assert emby_mod.merge_provider_ids("nope", {"A": "1"}) == {"A": "1"}

    def test_sanitize_null_collections(self, emby_mod):
        payload, notes = emby_mod.sanitize_payload(
            {"Name": "x", "People": None, "Studios": None})
        assert payload["People"] == [] and payload["Studios"] == []
        assert notes and payload["ProviderIds"] == {}

    def test_sanitize_drops_ineffective_keys(self, emby_mod):
        payload, notes = emby_mod.sanitize_payload(
            {"Name": "x", "RunTimeTicks": 1, "RemoteTrailers": [{"Url": "u"}],
             "ProviderIds": {}})
        assert "RunTimeTicks" not in payload and "RemoteTrailers" not in payload
        assert any("RunTimeTicks" in n for n in notes)

    def test_writable_overrides_rejects_readonly(self, emby_mod):
        overrides, notes = emby_mod.writable_overrides({"Name": "x", "Path": "/evil"})
        assert overrides == {"Name": "x"}
        assert any("Path" in n for n in notes)

    def test_writable_overrides_skips_control_markers(self, emby_mod):
        overrides, _ = emby_mod.writable_overrides({"Name": "x", "provider_ids_replace": True})
        assert overrides == {"Name": "x"}

    def test_writable_overrides_drops_sort_name_by_default(self, emby_mod):
        """P0-③ 裁决：排序名三件套默认不写。"""
        overrides, _ = emby_mod.writable_overrides({"Name": "x", "sort_name": "SNOS-380"})
        assert overrides == {"Name": "x"}

    def test_series_name_is_writable(self, emby_mod):
        """契约 §3.6.1 要写 `SeriesName`（javdb `series_name`，实测 26.9% 的片有值）。

        S7 集成时踩过：它原先不在白名单里 → 被当成"未知键"丢掉、还多留一条 warning。
        """
        overrides, notes = emby_mod.writable_overrides({"Name": "x", "SeriesName": "某系列"})
        assert overrides.get("SeriesName") == "某系列"
        assert "SeriesName" in emby_mod.WRITABLE_KEYS
        assert not [n for n in notes if "SeriesName" in n]


class TestBareDigitsAreNotNumbers:
    """纯数字串**绝不许**被当番号（S11/S7 实测的真实后果）。

    `12598` 是 SNOS-380 的 Emby 实例 id、`11311` 是 JAV 库 id：认成番号就会被拿去查站点、
    或写进 `ProviderIds.AVHelper`。兜底形态因此也要求前缀里有字母。
    """

    @pytest.mark.parametrize("text", ["12598", "11311", "007", "2026", "12345678",
                                      "0", "99999999999"])
    def test_pure_digits_rejected(self, emby_mod, text):
        parsed = emby_mod.parse_av_number(text)
        assert parsed.matched is False
        assert parsed.display_number == "" and parsed.norm_key == ""

    @pytest.mark.parametrize("text,display,key", [
        ("SSIS-001", "SSIS-001", "SSIS1"),
        ("FC2-PPV-1234567", "FC2-PPV-1234567", "FC2PPV1234567"),
        ("CAWB-040", "CAWB-040", "CAWB40"),
        ("1PONDO123", "1PONDO-123", "1PONDO123"),
    ])
    def test_real_numbers_still_match(self, emby_mod, text, display, key):
        """收紧兜底时**不能误伤**真番号（S7 点名要保住的几个）。"""
        parsed = emby_mod.parse_av_number(text)
        assert (parsed.display_number, parsed.norm_key) == (display, key)

    def test_domain_watermark_fragment_rejected(self, emby_mod):
        """`hhd800`（`hhd800.com` 剥掉 `.com@` 的残段）也不是番号。

        这条是收紧兜底时的连带发现：`hhd`+`800` 的切分点纯靠猜，认了就会产出假键 `HHD800`。
        整条 `hhd800.com@MIDV-946.mp4` 仍然正常命中 `MIDV-946`。
        """
        assert emby_mod.parse_av_number("hhd800").matched is False
        assert emby_mod.parse_av_number("hhd800.com@MIDV-946.mp4").norm_key == "MIDV946"

    def test_canon_key_still_never_empty(self, emby_mod):
        """`canon_key()` 的契约是「绝不返回空串（调用方拿它当查询键）」—— 这条不受影响。"""
        assert emby_mod.canon_key("12598") == "12598"
        assert emby_mod.canon_key("12598") == emby_mod.norm_key("12598")
