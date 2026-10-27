"""设置台「通知」栏的数据面单测（0.9.1，2026-10-27 用户反馈）。

用户原话：

> 1. 当前设置-通知菜单中，缺少选择哪些信息发送至 Telegram 的配置项
> 2. 需要列出所有可用的通知渠道供我选取
> 3. 通知设置中需包含时间频率配置，使用 CRON 表达式，默认值固定写入即可

这里钉住四件事：

1. **渠道清单**：`notify.CHANNELS` 与宿主 `NotificationChannel` 的中文标签逐一对应
   （清单变短/写错一个字 = 发给宿主的 `channel=` 反查不到，消息静默丢弃）；
2. **推送分类**：`PUSH_KINDS` 的键与 `Notifier` 各模板的 `pkind` 对得上；
3. **推送门**：没选渠道 = 推给全部渠道（老口径）；选了就只发选中的；`notifyPush` 关掉一个都不发；
   限流/界面提示永远不推；
4. **cron**：`notify.parse_cron()` 的展开与报错、`schedule.host_kwargs()` 的形状
   （**整数列表**，APScheduler 直接收；字符串会让整条服务注册失败）、
   `pick_cron()` 的兜底回默认。
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
PKG_NAME = "avhelper_under_test"          # 与 conftest.py 同一个合成包名


def _install_host_stubs() -> None:
    """`notify.py` 只依赖 `app.schemas.types.MessageType`。"""
    for name in ("app", "app.schemas"):
        sys.modules.setdefault(name, types.ModuleType(name))
    types_mod = sys.modules.get("app.schemas.types") or types.ModuleType("app.schemas.types")

    class _MessageType:
        Plugin = "Plugin"

    if not hasattr(types_mod, "MessageType"):
        types_mod.MessageType = _MessageType
    sys.modules["app.schemas.types"] = types_mod


def _load(name: str):
    _install_host_stubs()
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


@pytest.fixture(scope="module")
def notify_mod():
    return _load("notify")


@pytest.fixture(scope="module")
def schedule_mod():
    return _load("schedule")


class _Store:
    def __init__(self):
        self.rows = []

    def notice_add(self, notice):
        self.rows.append(dict(notice))
        return notice


class _Plugin:
    """插件替身：记下每一次 `post_message` 的 channel。"""

    def __init__(self, conf=None):
        self.conf = conf
        self.posts = []

    def post_message(self, **kwargs):
        self.posts.append(kwargs)

    def notify_conf(self):
        if self.conf is None:
            raise AttributeError("no conf")
        return dict(self.conf)


def _notifier(notify_mod, conf=None):
    plugin = _Plugin(conf)
    store = _Store()
    return notify_mod.Notifier(plugin, store), plugin, store


# ---------- 1. 渠道清单 ----------


class TestChannels:
    def test_channels_match_host_enum_labels(self, notify_mod):
        """宿主 MP v3.1.5 的 `NotificationChannel` 中文标签（容器内实测，不要凭印象改）。"""
        assert notify_mod.CHANNELS == [
            "Telegram", "微信", "飞书", "Discord", "Slack", "钉钉", "QQ",
            "SynologyChat", "VoceChat", "WebPush", "Web", "WebAgent", "微信ClawBot",
        ]

    def test_telegram_is_first_and_available(self, notify_mod):
        """用户报的就是"送 Telegram"：它必须在第一项且可选。"""
        names = [item["name"] for item in notify_mod.Notifier.available_channels()]
        assert names[0] == "Telegram"

    def test_available_channels_shape(self, notify_mod):
        rows = notify_mod.Notifier.available_channels()
        assert rows and all(set(row) == {"name", "label", "enabled"} for row in rows)


# ---------- 2. 推送分类 ----------


class TestKinds:
    def test_push_kinds_cover_every_pushing_template(self, notify_mod):
        """每个会推送到渠道的模板都得落在 `PUSH_KINDS` 里，否则用户勾不到它。"""
        assert set(notify_mod.PUSH_KINDS) == {"sub", "download", "scrape", "candidate"}
        assert notify_mod.PUSH_ALL not in notify_mod.PUSH_KINDS


# ---------- 3. 推送门 ----------


class TestPushGate:
    def test_no_conf_pushes_everything(self, notify_mod):
        """单测替身/老规则：读不到设置 = 老口径，所有业务通知都推。"""
        notifier, plugin, _ = _notifier(notify_mod)
        notifier.download_start("IPZZ-961", {"size": "1 GB"})
        assert len(plugin.posts) == 1
        assert plugin.posts[0]["channel"] is None      # None = 宿主全部渠道

    def test_no_channels_selected_means_all(self, notify_mod):
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": True, "notifyChannels": [], "notifyKinds": []})
        notifier.download_start("IPZZ-961", {})
        assert [p["channel"] for p in plugin.posts] == [None]

    def test_selected_channels_only(self, notify_mod):
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": True, "notifyChannels": ["Telegram", "Discord"],
                         "notifyKinds": []})
        notifier.download_start("IPZZ-961", {})
        assert [p["channel"] for p in plugin.posts] == ["Telegram", "Discord"]

    def test_unknown_channel_is_dropped(self, notify_mod):
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": True, "notifyChannels": ["电报"], "notifyKinds": []})
        notifier.download_start("IPZZ-961", {})
        # 全都不认得 → 回"不过滤"，推给宿主全部渠道（而不是一个都不发）
        assert [p["channel"] for p in plugin.posts] == [None]

    def test_push_switch_off_sends_nothing_but_still_records(self, notify_mod):
        notifier, plugin, store = _notifier(
            notify_mod, {"notifyPush": False, "notifyChannels": [], "notifyKinds": []})
        notifier.download_start("IPZZ-961", {})
        assert plugin.posts == []
        assert len(store.rows) == 1        # 收件箱照记

    def test_kind_filter(self, notify_mod):
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": True, "notifyChannels": [], "notifyKinds": ["sub"]})
        notifier.sub_hit_number("IPZZ-961")
        notifier.download_start("IPZZ-961", {})
        notifier.stored("IPZZ-961")
        assert len(plugin.posts) == 1
        assert plugin.posts[0]["title"] == "订阅命中，开始搜索"

    def test_star_kind_pushes_all(self, notify_mod):
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": True, "notifyChannels": [], "notifyKinds": ["*"]})
        notifier.sub_hit_number("IPZZ-961")
        notifier.download_start("IPZZ-961", {})
        notifier.candidate_ready("IPZZ-961", 3)
        assert len(plugin.posts) == 3

    def test_limited_and_info_never_push(self, notify_mod):
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": True, "notifyChannels": [], "notifyKinds": ["*"]})
        notifier.limited("距上次检查不足间隔")
        notifier.info("检查完成", "没有新片")
        assert plugin.posts == []

    def test_post_failure_never_raises(self, notify_mod):
        notifier, plugin, store = _notifier(notify_mod, {"notifyPush": True})

        def boom(**kwargs):
            raise RuntimeError("宿主通知渠道炸了")

        plugin.post_message = boom
        notice = notifier.download_start("IPZZ-961", {})     # 不抛
        assert notice["title"] == "开始下载" and len(store.rows) == 1

    def test_send_to_channel_bypasses_gate(self, notify_mod):
        """「测试」按钮：`notifyPush` 关着也要能测，且只发那一个渠道。"""
        notifier, plugin, _ = _notifier(
            notify_mod, {"notifyPush": False, "notifyChannels": ["Discord"], "notifyKinds": []})
        assert notifier.send_to_channel("Telegram", "标题", "正文") is True
        assert [p["channel"] for p in plugin.posts] == ["Telegram"]

    def test_send_to_unknown_channel_refused(self, notify_mod):
        notifier, plugin, _ = _notifier(notify_mod, {"notifyPush": True})
        assert notifier.send_to_channel("电报", "标题", "正文") is False
        assert plugin.posts == []


# ---------- 4. cron ----------


class TestCron:
    def test_default_matches_legacy_schedule(self, notify_mod):
        """默认值必须与 0.9.0 之前写死的 `{"hour": "9,14,21", "minute": 30}` 同一时刻。"""
        assert notify_mod.DEFAULT_SUBCHECK_CRON == "30 9,14,21 * * *"
        parsed = notify_mod.parse_cron(notify_mod.DEFAULT_SUBCHECK_CRON)
        assert parsed["minute"] == [30]
        assert parsed["hour"] == [9, 14, 21]
        assert parsed["day"] == list(range(1, 32))

    def test_host_kwargs_are_cron_field_strings(self, notify_mod, schedule_mod):
        """宿主把 kwargs 原样展开给 APScheduler：值必须是 cron 字段**字符串**。

        容器里实测（2026-10-27）：`CronTrigger(minute=[5, 20, 35, 50])` 抛
        `Unrecognized expression "[5" for field "minute"`（列表被当字符串解析），
        而 `CronTrigger(minute="9,14,21")` 正常 —— 所以这里断言的是字符串。
        """
        kwargs = schedule_mod.host_kwargs(notify_mod.DEFAULT_SUBCHECK_CRON)
        assert set(kwargs) == {"minute", "hour", "day", "month", "day_of_week"}
        assert kwargs["hour"] == "9,14,21"
        assert kwargs["minute"] == "30"
        assert all(isinstance(value, str) for value in kwargs.values())

    def test_host_kwargs_keeps_step_and_range_syntax(self, notify_mod, schedule_mod):
        """`*/6` / `1-5` 这类写法要原样交给 apscheduler（改写成展开列表反而会炸）。"""
        kwargs = schedule_mod.host_kwargs("0 */6 * * 1-5")
        assert kwargs["hour"] == "*/6"
        assert kwargs["day_of_week"] == "1-5"

    def test_host_kwargs_rejects_garbage(self, notify_mod, schedule_mod):
        with pytest.raises(ValueError):
            schedule_mod.host_kwargs("0 */6 * *")

    @pytest.mark.parametrize("field,lo,hi,expect", [
        ("*/15", 0, 59, [0, 15, 30, 45]),
        ("5/15", 0, 59, [5, 20, 35, 50]),
        ("9-11", 0, 23, [9, 10, 11]),
        ("mon-fri", 0, 6, [1, 2, 3, 4, 5]),
        ("1,3,5", 0, 6, [1, 3, 5]),
        ("7", 0, 6, "raise"),
    ])
    def test_field_expansion(self, notify_mod, field, lo, hi, expect):
        if expect == "raise":
            with pytest.raises(ValueError):
                notify_mod._parse_cron_field(field, lo, hi)
            return
        assert notify_mod._parse_cron_field(field, lo, hi) == expect

    @pytest.mark.parametrize("expr", ["30 9,14,21 * *", "30 9 14 21 * *", "61 * * * *",
                                      "* 25 * * *", "abc * * * *", "*/0 * * * *", ""])
    def test_parse_cron_rejects_garbage(self, notify_mod, expr):
        with pytest.raises(ValueError):
            notify_mod.parse_cron(expr)
