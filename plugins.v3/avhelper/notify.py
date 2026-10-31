"""通知模板（执行方案 §10，用户逐条确认过，**只有这五种，不要加别的**）。

只有“开始下载”一条带封面缩略图，其余纯文字。所有通知同时写入插件自有通知表，
供应用界面的「通知」页展示；发往 Telegram 等渠道走宿主 `post_message`。

0.9.1 起多了**推送门**（`Notifier` 的 `push` 参数 + `CHANNELS` / `PUSH_KINDS`）：

- **推给哪些渠道**：设置台「通知」栏勾选的那几个（`notifyChannels`，存的是渠道**中文标签**）。
  宿主 `PluginBase.post_message(channel=…)` 的默认值就是 `None` = 推给它配置过的**全部**渠道，
  所以「没勾任何渠道」= 老行为，一个字母都不变 —— 老用户升级后收不到重复消息。
- **推哪些通知**：按 `PUSH_KINDS` 分类过滤（`notifyKinds`）。``'*'`` = 不按分类过滤，
  但**免限流**的分类照样推（与 0.9.0 之前一致：限流提示只进界面、不发渠道）。
- 发给**点名的某个渠道**（`send_to_channel`，宿主通知设置里的「测试」用）不过这张表。

渠道清单是**本文件写死的 13 个**，与 MP v3.1.5 的 `NotificationChannel` 枚举逐一对应
（容器里实测：微信 / 飞书 / 微信ClawBot / Telegram / Slack / Discord / 钉钉 / SynologyChat /
VoceChat / Web / WebAgent / WebPush / QQ）。**不从宿主枚举动态生成**：枚举值就是中文标签，
但真发给宿主的是 `channel=<标签>`，宿主按 `NotificationChannel` 反查 —— 标签拼错就等于发不出去，
所以这里只认这张表里的写法。
"""

from typing import Any, Dict, List, Optional

from app.schemas.types import MessageType

from .scoring import publisher_label
from .store import Store

KIND_OK = "ok"
KIND_WARN = "warn"
KIND_INFO = ""

RES_LABEL = {"2160p": "4K", "1080p": "1080P", "720p": "720P"}

#: 可推送的渠道（顺序 = 设置台里的勾选顺序，按使用频率排）。
CHANNELS: List[str] = [
    "Telegram",
    "微信",
    "飞书",
    "Discord",
    "Slack",
    "钉钉",
    "QQ",
    "SynologyChat",
    "VoceChat",
    "WebPush",
    "Web",
    "WebAgent",
    "微信ClawBot",
]

#: 推送分类：设置台「通知」栏的勾选项与 `Notifier` 各模板的 `kind=` 逐字对应。
#: 只列**真的会推送到渠道**的模板；`limited` / `info` / `system_ready` 是界面内提示，不入这张表。
PUSH_KINDS: Dict[str, str] = {
    "sub": "订阅命中（新片 / 番号命中开始搜索）",
    "download": "开始下载",
    "scrape": "刮削与入库（正在刮削 / 已入库）",
    "candidate": "发现候选、等待确认",
}

#: 不按分类过滤（`notifyKinds` 里含它 = 所有通知都推）。
PUSH_ALL = "*"

#: 免限流的分类：限流提示只进界面（老口径），别的分类不勾也会推。
EXEMPT_KIND = "notice"


def meta_line(cand: Dict[str, Any]) -> str:
    """拼“开始下载”的元信息块（分辨率/编码/大小/字幕/副标题/发布源）。"""
    res = RES_LABEL.get(str(cand.get("res") or ""), "1080P")
    spec = str(cand.get("spec") or "")
    codec = "—"
    if "/" in spec:
        codec = spec.split("/")[1].strip() or "—"
    return "  ·  ".join([
        f"分辨率：{res}",
        f"编码：{codec}",
        f"大小：{cand.get('size') or '—'}",
        f"字幕：{'中文简体' if cand.get('cnsub') else '无中字'}",
        f"副标题：{'无码破解' if cand.get('uncensored') else '有码原版'}",
        f"发布源：{publisher_label(cand)}",
    ])


class Notifier:
    """把“发通知”收口到一处：写库给界面看，同时交给宿主推送到已配置渠道。"""

    def __init__(self, plugin: Any, store: Store):
        self.plugin = plugin
        self.store = store

    # ---------- 推送门（读 `notify_conf()`，见 `__init__.py` 的同名方法） ----------

    def conf(self) -> Dict[str, Any]:
        """当前的通知设置；插件没有 `notify_conf()`（单测替身）时回默认：全推。"""
        reader = getattr(self.plugin, "notify_conf", None)
        if not callable(reader):
            return {"notifyPush": True, "notifyChannels": [], "notifyKinds": []}
        try:
            value = reader()
        except Exception:      # 读配置本身就是防御性的：读不到宁可照老口径全推
            return {"notifyPush": True, "notifyChannels": [], "notifyKinds": []}
        return value if isinstance(value, dict) else {}

    def _wanted(self, kind: str) -> bool:
        """这条通知要不要推送到渠道。

        - 首选看模板自己给的 `kind`（`sub` / `download` / `scrape` / `candidate`）；
        - 模板没给（如限流）就按“免限流”处理：不推，与老口径一致。
        """
        conf = self.conf()
        if not conf.get("notifyPush", True):
            return False
        kinds = [str(x) for x in (conf.get("notifyKinds") or []) if str(x)]
        if not kind or kind == EXEMPT_KIND:
            return False
        if not kinds:
            # 老规则里没有这个键：沿用老口径 —— 除限流/界面提示外都推
            return True
        return PUSH_ALL in kinds or kind in kinds

    def _channels(self) -> List[Optional[str]]:
        """要发给宿主的那几个 channel 值：没勾 = `[None]`（宿主全部渠道），勾了就逐个发。"""
        raw = self.conf().get("notifyChannels") or []
        picked = [str(x) for x in raw if str(x) in CHANNELS]
        return picked or [None]

    @staticmethod
    def available_channels() -> List[Dict[str, Any]]:
        """回给设置台的选择清单：`[{name, label, enabled}]`（`enabled` 只有一处来源 = 上面的表）。

        为什么不问宿主：宿主没有稳定接口列出"这个用户实际开了哪些渠道"，问也问不出；
        设置台把 13 个全列出来，用户勾他觉得有用的那几个即可（勾了但宿主没配，宿主自己会跳过）。
        """
        return [{"name": name, "label": name, "enabled": True} for name in CHANNELS]

    def send_to_channel(self, channel: str, title: str, body: str,
                        image: str = "") -> bool:
        """发一条到**点名的渠道**（宿主「设置 → 通知」里的「测试」用它），不过推送门。

        只写库、不推别的渠道：这是"试一试这个渠道通不通"，不该顺带把消息发给全部渠道。
        """
        if channel not in CHANNELS:
            return False
        notice = {
            "kind": KIND_INFO, "title": title, "type": self._type_label(KIND_INFO),
            "body": body, "meta": "", "image": image,
        }
        self.store.notice_add(notice)
        return self._post(title, body, image, channel)

    def _post(self, title: str, body: str, image: str,
              channel: Optional[str] = None) -> bool:
        """交给宿主推送。**失败绝不外抛**：通知失败不能影响主流程（老口径）。"""
        try:
            # `getattr` 而不是直接 `MessageType.Plugin`：单测/老宿主的 `MessageType`
            # 可能没有这个成员（真机一定有），直接取会让**整个推送**在参数求值阶段就抛错
            # —— 2026-10-27 本会话踩过：别的测试模块留下的空壳 `MessageType` 让通知
            # 一条都发不出去，而 `except` 又把原因吞了（症状是"渠道全空、0 报错"）。
            mtype = getattr(MessageType, "Plugin", None)
            self.plugin.post_message(
                channel=channel,
                mtype=mtype,
                title=title,
                text=body,
                image=image or None,
            )
            return True
        except Exception:  # noqa: BLE001 - 通知失败不能影响主流程
            return False

    # ---------- 五行模板 ----------

    def _emit(self, kind: str, title: str, body: str, *, meta: str = "",
              image: str = "", push: bool = True, pkind: str = "") -> Dict[str, Any]:
        """写一条通知；`push` 且 `pkind` 被设置台勾选时才交给宿主推送到渠道。"""
        notice = {
            "kind": kind, "title": title, "type": self._type_label(kind),
            "body": body, "meta": meta, "image": image,
        }
        self.store.notice_add(notice)
        if push and self._wanted(pkind):
            text = body + ("\n" + meta if meta else "")
            for channel in self._channels():
                self._post(title, text, image, channel)
        return notice

    @staticmethod
    def _type_label(kind: str) -> str:
        """通知类型文案，与演示原型一致。"""
        return {"ok": "✅ 任务成功", "warn": "⚠️ 需要确认"}.get(kind, "ℹ️ 系统消息")

    # ---------- 五行业务模板 ----------

    def sub_new_actor(self, actor: str, number: str, push: bool = True) -> Dict[str, Any]:
        """演员订阅命中新片。"""
        return self._emit(KIND_OK, "订阅命中新片",
                          f"{actor} 新作 {number} 已发布，开始搜索站点",
                          push=push, pkind="sub")

    def sub_hit_number(self, number: str, push: bool = True) -> Dict[str, Any]:
        """番号订阅命中（文案固定，不是“新作已发布”）。"""
        return self._emit(KIND_INFO, "订阅命中，开始搜索",
                          f"番号 {number} · 按规则搜索站点", push=push, pkind="sub")

    def download_start(self, number: str, cand: Dict[str, Any],
                       image: str = "", push: bool = True) -> Dict[str, Any]:
        """开始下载：唯一带封面缩略图的一条。"""
        return self._emit(KIND_OK, "开始下载", f"{number} 正在下载",
                          meta=meta_line(cand), image=image, push=push, pkind="download")

    def scraping(self, number: str, push: bool = True) -> Dict[str, Any]:
        """下载完成、开始刮削。"""
        return self._emit(KIND_INFO, "正在刮削",
                          f"{number} 下载已完成，MediaInfo 抓取中", push=push, pkind="scrape")

    def stored(self, number: str, save_path: str = "",
               push: bool = True) -> Dict[str, Any]:
        """已入库。"""
        where = f" {save_path}" if save_path else ""
        return self._emit(KIND_OK, "已入库",
                          f"{number} 已入库{where}，Emby 已扫描",
                          push=push, pkind="scrape")

    # ---------- 界面内提示（不推送） ----------

    def candidate_ready(self, number: str, count: int, push: bool = True) -> Dict[str, Any]:
        """发现候选、等待用户确认（半自动订阅的提示，界面内提示用；勾了 `candidate` 才会推送）。"""
        return self._emit(KIND_WARN, "发现候选，等你确认", f"{number} · {count} 个结果",
                          push=push, pkind="candidate")

    def limited(self, reason: str) -> Dict[str, Any]:
        """限流拦截提示（不推送，仅界面可见）。"""
        return self._emit(KIND_WARN, "检查被限流", reason, push=False)

    def info(self, title: str, body: str) -> Dict[str, Any]:
        """通用界面提示（不推送）。"""
        return self._emit(KIND_INFO, title, body, push=False)

    def system_ready(self) -> Dict[str, Any]:
        """启动就绪提示（仅界面）。"""
        return self._emit(KIND_INFO, "系统就绪", "javdb-cli 已连接 · MoviePilot 已连接", push=False)


def cover_for_notify(cover_url: Optional[str]) -> str:
    """通知附图直接用图片代理地址（Telegram 等渠道能取到 image/jpeg）。"""
    if not cover_url:
        return ""
    return cover_url


# ---------------------------------------------------------------------------
# 订阅检查的时间表（CRON，5 段：分 时 日 月 周）
# ---------------------------------------------------------------------------

#: 默认值（= 0.9.0 之前写死在 `get_service()` 里的那三档：09:30 / 14:30 / 21:30）。
#: 设置台「通知」栏把这一份当默认值渲染，用户可以改，改完写进 kv 的 `notifyCron`。
DEFAULT_SUBCHECK_CRON = "30 9,14,21 * * *"


#: 月份名 / 星期名（cron 的字母写法；宿主的调度器同样认这些）。
CRON_ALIASES: Dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
}
#: 5 段各自的范围（分 时 日 月 周）与中文名（报错时点名是哪一段）。
CRON_BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
CRON_NAMES = ("分钟", "小时", "日", "月", "星期")


def _cron_num(token: str) -> int:
    """`7` 或 `sun` → int（别的写法一律抛错，不猜）。"""
    token = token.strip().lower()
    if token in CRON_ALIASES:
        return CRON_ALIASES[token]
    if not token.lstrip("-").isdigit():
        raise ValueError(f"不是数字：{token!r}")
    return int(token)


def _parse_cron_field(text: str, lo: int, hi: int) -> List[int]:
    """一段字段 → 整数列表（`*` / `n` / `a-b` / `*/n` / `a-b/n` / `n/step` / 逗号组合）。

    **不支持的写法一律抛错，不静默近似** —— 宿主 scheduler 拿到的若是坏表达式，
    会静默跳过整条定时任务（订阅检查就停摆了）。
    """
    out: List[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            raise ValueError("空段")
        step = 1
        if "/" in part:
            part, _, raw_step = part.partition("/")
            step = _cron_num(raw_step)
            if step <= 0:
                raise ValueError("步长必须为正")
        if part in ("*", "?"):
            start, stop = lo, hi
        elif "-" in part:
            first, _, last = part.partition("-")
            start, stop = _cron_num(first), _cron_num(last)
        else:
            start = stop = _cron_num(part)
            if step != 1:
                stop = hi     # `5/15` = 从 5 开始每 15，到字段上限
        if lo <= start <= stop <= hi:
            out.extend(range(start, stop + 1, step))
            continue
        raise ValueError(f"超出范围：{part!r}（应为 {lo}–{hi}）")
    return sorted(set(out))


def parse_cron(expr: str) -> Dict[str, List[int]]:
    """把 5 段 cron 展开成 `{minute, hour, day, month, weekday}`；非法抛 `ValueError`。"""
    fields = str(expr or "").split()
    if len(fields) != 5:
        raise ValueError("cron 要 5 段：分 时 日 月 周")
    out: Dict[str, List[int]] = {}
    for key, field, (lo, hi), label in zip(
            ("minute", "hour", "day", "month", "weekday"), fields, CRON_BOUNDS, CRON_NAMES,
            strict=True):
        try:
            out[key] = _parse_cron_field(field, lo, hi)
        except ValueError as error:
            raise ValueError(f"{label}段不合法（{field}）：{error}") from error
    return out
