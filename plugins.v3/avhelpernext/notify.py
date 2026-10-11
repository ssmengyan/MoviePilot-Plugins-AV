"""通知模板（执行方案 §10，用户逐条确认过，**只有这五种，不要加别的**）。

只有“开始下载”一条带封面缩略图，其余纯文字。所有通知同时写入插件自有通知表，
供应用界面的「通知」页展示；发往 Telegram 等渠道走宿主 `post_message`。
"""

from typing import Any, Dict, Optional

from app.schemas.types import MessageType

from .scoring import publisher_label
from .store import Store

KIND_OK = "ok"
KIND_WARN = "warn"
KIND_INFO = ""

RES_LABEL = {"2160p": "4K", "1080p": "1080P", "720p": "720P"}


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

    def _emit(self, kind: str, title: str, body: str, *, meta: str = "",
              image: str = "", push: bool = True) -> Dict[str, Any]:
        """写一条通知并推送到宿主渠道。"""
        notice = {
            "kind": kind, "title": title, "type": self._type_label(kind),
            "body": body, "meta": meta, "image": image,
        }
        self.store.notice_add(notice)
        if push:
            try:
                self.plugin.post_message(
                    mtype=MessageType.Plugin,
                    title=title,
                    text=(body + ("\n" + meta if meta else "")),
                    image=image or None,
                )
            except Exception:  # 通知失败不能影响主流程
                pass
        return notice

    @staticmethod
    def _type_label(kind: str) -> str:
        """通知类型文案，与演示原型一致。"""
        return {"ok": "✅ 任务成功", "warn": "⚠️ 需要确认"}.get(kind, "ℹ️ 系统消息")

    # ---------- 五种模板 ----------

    def sub_new_actor(self, actor: str, number: str, push: bool = True) -> Dict[str, Any]:
        """演员订阅命中新片。"""
        return self._emit(KIND_OK, "订阅命中新片",
                          f"{actor} 新作 {number} 已发布，开始搜索站点", push=push)

    def sub_hit_number(self, number: str, push: bool = True) -> Dict[str, Any]:
        """番号订阅命中（文案固定，不是“新作已发布”）。"""
        return self._emit(KIND_INFO, "订阅命中，开始搜索",
                          f"番号 {number} · 按规则搜索站点", push=push)

    def download_start(self, number: str, cand: Dict[str, Any],
                       image: str = "", push: bool = True) -> Dict[str, Any]:
        """开始下载：唯一带封面缩略图的一条。"""
        return self._emit(KIND_OK, "开始下载", f"{number} 正在下载",
                          meta=meta_line(cand), image=image, push=push)

    def scraping(self, number: str, push: bool = True) -> Dict[str, Any]:
        """下载完成、开始刮削。"""
        return self._emit(KIND_INFO, "正在刮削",
                          f"{number} 下载已完成，MediaInfo 抓取中", push=push)

    def stored(self, number: str, save_path: str = "/media/9kg/avi",
               push: bool = True) -> Dict[str, Any]:
        """已入库。"""
        return self._emit(KIND_OK, "已入库",
                          f"{number} 已入库 {save_path}，Emby 已扫描，MetaTube 已刮削",
                          push=push)

    def candidate_ready(self, number: str, count: int, push: bool = True) -> Dict[str, Any]:
        """发现候选、等待用户确认（半自动订阅的提示，非五种业务模板之一，界面内提示用）。"""
        return self._emit(KIND_WARN, "发现候选，等你确认", f"{number} · {count} 个结果", push=push)

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
