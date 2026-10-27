"""`__init__.py` 的通知设置面单测（0.9.1，2026-10-27 用户反馈）。

覆盖四件事（都是设置台「通知」栏真正依赖的口径）：

1. **`notify_conf()`**：4 个键的默认值 + 清洗（认不出的渠道/分类丢掉、cron 非法回默认）；
   老规则里没有这些键时**逐项回落默认**（升级不改行为）；
2. **`pick_cron()` / `pick_channels()` / `pick_kinds()`**：写坏的值得被夹回默认，不抛错；
3. **`get_service()`**：订阅检查的 kwargs 来自 `notifyCron` 且是**整数列表**
   （字符串会让宿主整条服务注册失败，见 `schedule.py` 文件头）；
4. **`/notify` 与 `/notify/test` 路由**：都在 `get_api()` 里、`auth:"bear"`，
   `/notify/test` 是 POST；`notify_test()` 对未知渠道回失败、对已知渠道调 `send_to_channel`。
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
PKG_NAME = "avhelper_under_test"          # 与 conftest.py 同一个合成包名


def _install_host_stubs() -> None:
    for name in ("app", "app.sdk", "app.schemas"):
        sys.modules.setdefault(name, types.ModuleType(name))
    plugin = types.ModuleType("app.sdk.plugin")

    class _PluginBase:
        @staticmethod
        def get_data_path():
            return Path(".")

    plugin._PluginBase = _PluginBase
    sys.modules["app.sdk.plugin"] = plugin
    sched = types.ModuleType("app.sdk.scheduler")
    sched.add_plugin_once_job = lambda *a, **k: None
    sched.remove_plugin_once_job = lambda *a, **k: None
    sys.modules["app.sdk.scheduler"] = sched
    types_mod = sys.modules.get("app.schemas.types") or types.ModuleType("app.schemas.types")
    if not hasattr(types_mod, "MessageType"):
        class _MessageType:
            Plugin = "Plugin"
        types_mod.MessageType = _MessageType
    sys.modules["app.schemas.types"] = types_mod


def _load_entry():
    _install_host_stubs()
    if PKG_NAME not in sys.modules:
        pkg = types.ModuleType(PKG_NAME)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PKG_NAME] = pkg
    key = f"{PKG_NAME}.__init__"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


class FakeStore:
    """只实现 kv 两件套 + 通知表；`rule` 就是 `global_rule` 那份 dict。"""

    def __init__(self, rule=None):
        self.rule = dict(rule or {})
        self.notices = []

    def kv_get(self, key, default=None):
        return dict(self.rule) if key == "global_rule" else default

    def kv_set(self, key, val, ttl=0):
        if key == "global_rule":
            self.rule = dict(val or {})

    def notice_add(self, notice):
        self.notices.append(dict(notice))
        return notice

    def notice_list(self):
        return list(self.notices)

    def notice_clear(self):
        self.notices = []


class FakeNotifier:
    """记录 `send_to_channel` 的调用；其余方法一律空实现。"""

    def __init__(self):
        self.sent = []

    def send_to_channel(self, channel, title, body, image=""):
        self.sent.append((channel, title))
        return True


class FakeRequest:
    def __init__(self, method="POST", body=None, query=None):
        self.method = method
        self._body = dict(body or {})
        self.query_params = dict(query or {})

    async def json(self):
        return dict(self._body)


@pytest.fixture(scope="module")
def api_mod():
    return _load_entry()


@pytest.fixture
def plugin(api_mod):
    store = FakeStore()
    instance = api_mod.AVHelper()
    instance._enabled = True
    instance._store = store
    instance._notifier = FakeNotifier()
    return instance


def call(coro):
    return asyncio.run(coro)


# ---------- 1. notify_conf 的默认值与清洗 ----------


class TestNotifyConf:
    def test_defaults_when_keys_missing(self, plugin, api_mod):
        """老规则（没有这四个键）→ 全推、不过滤、时间表 = 老的三档。"""
        conf = plugin.notify_conf()
        assert conf["notifyPush"] is True
        assert conf["notifyChannels"] == []
        assert conf["notifyKinds"] == []
        assert conf["notifyCron"] == api_mod.DEFAULT_SUBCHECK_CRON == "30 9,14,21 * * *"

    def test_channels_are_cleaned_against_registry(self, plugin, api_mod):
        plugin._store.rule = {
            "notifyChannels": ["Telegram", "电报", "Telegram", "微信", ""],
        }
        conf = plugin.notify_conf()
        assert conf["notifyChannels"] == ["Telegram", "微信"]      # 认不出的丢掉、去重、保序
        assert "电报" not in conf["notifyChannels"]

    def test_kinds_are_cleaned(self, plugin):
        plugin._store.rule = {"notifyKinds": ["sub", "bogus", "*", "download"]}
        assert plugin.notify_conf()["notifyKinds"] == ["sub", "*", "download"]

    @pytest.mark.parametrize("bad", ["", "0 */6 * *", "61 * * * *", "abc", "30 9 14 21 * *"])
    def test_bad_cron_falls_back_to_default(self, plugin, api_mod, bad):
        plugin._store.rule = {"notifyCron": bad}
        assert plugin.notify_conf()["notifyCron"] == api_mod.DEFAULT_SUBCHECK_CRON

    def test_good_cron_is_kept_and_normalized(self, plugin):
        plugin._store.rule = {"notifyCron": "  0   */6 * * * "}
        assert plugin.notify_conf()["notifyCron"] == "0 */6 * * *"

    def test_available_lists_every_channel(self, plugin, api_mod):
        rows = plugin.notify_conf()["available"]
        assert [row["name"] for row in rows] == list(api_mod.CHANNELS)
        assert all(row["enabled"] is True for row in rows)


# ---------- 2. get_service 的 cron kwargs ----------


class TestServiceCron:
    def test_default_matches_legacy_three_times_a_day(self, plugin):
        """默认值必须等于 0.9.0 写死的 `{"hour": "9,14,21", "minute": 30}`。"""
        services = {item["id"]: item for item in plugin.get_service()}
        kwargs = services["subcheck"]["kwargs"]
        assert kwargs["minute"] == "30"
        assert kwargs["hour"] == "9,14,21"

    def test_values_are_cron_field_strings(self, plugin):
        """整数列表会让宿主整条服务注册失败（容器实测，见 `schedule.py` 文件头）。"""
        services = {item["id"]: item for item in plugin.get_service()}
        for key, value in services["subcheck"]["kwargs"].items():
            assert isinstance(value, str), f"{key} 不是字符串：{value!r}"

    def test_custom_cron_is_used(self, plugin):
        plugin._store.rule = {"notifyCron": "15 3 * * 1"}
        kwargs = {item["id"]: item for item in plugin.get_service()}["subcheck"]["kwargs"]
        assert kwargs["minute"] == "15"
        assert kwargs["hour"] == "3"
        assert kwargs["day_of_week"] == "1"

    def test_actor_sync_minute_is_a_cron_string(self, plugin):
        services = {item["id"]: item for item in plugin.get_service()}
        assert services["actorsync"]["kwargs"]["minute"] == "5,20,35,50"


# ---------- 3. /notify 与 /notify/test ----------


class TestNotifyRoutes:
    @staticmethod
    def routes(api_mod, plugin):
        return {row["path"]: row for row in plugin.get_api()}

    def test_routes_exist_and_are_bear(self, api_mod, plugin):
        routes = self.routes(api_mod, plugin)
        assert "/notify" in routes and routes["/notify"]["methods"] == ["GET"]
        assert routes["/notify"]["auth"] == "bear"
        assert "/notify/test" in routes and routes["/notify/test"]["methods"] == ["POST"]
        assert routes["/notify/test"]["auth"] == "bear"

    def test_notify_payload_shape(self, plugin, api_mod):
        payload = plugin.api_notify()
        assert payload["success"] is True
        assert {row["name"] for row in payload["channels"]} == set(api_mod.CHANNELS)
        assert {row["name"] for row in payload["kinds"]} == set(api_mod.PUSH_KINDS)
        assert payload["conf"]["notifyCron"] == api_mod.DEFAULT_SUBCHECK_CRON
        assert payload["conf"]["notifyCronDefault"] == api_mod.DEFAULT_SUBCHECK_CRON
        assert payload["cron"]["hour"] == "9,14,21"

    def test_notify_test_refuses_unknown_channel(self, plugin):
        out = plugin.notify_test("电报")
        assert out["success"] is False
        assert plugin._notifier.sent == []

    def test_notify_test_sends_to_one_channel(self, plugin):
        out = plugin.notify_test("Telegram")
        assert out["success"] is True and out["delivered"] is True
        assert plugin._notifier.sent == [("Telegram", "AV 资源助手 · 测试通知")]

    def test_notify_test_endpoint_reads_body(self, api_mod, plugin):
        out = call(plugin.api_notify_test(FakeRequest(body={"channel": "Discord"})))
        assert out["success"] is True
        assert plugin._notifier.sent == [("Discord", "AV 资源助手 · 测试通知")]
