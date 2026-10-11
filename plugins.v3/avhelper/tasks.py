"""订阅检查与“搜种 → 打分 → 下载”编排（执行方案 §6.4/§6.5/§6.6/§6.7）。

订阅检查：
  演员订阅 → javdb 作品史（24h 缓存）与 known 表做差集 → 新片发“订阅命中新片”通知 → 搜种；
  番号订阅 → 直接搜该番号，文案固定为“订阅命中，开始搜索”。
  搜到候选后：rule.trigger == 'auto' 且有通过项 → 直接下载；否则建任务等用户点“下载”。

搜种（§6.7）：交给 `sitesearch.SiteSearcher` 按站点分派适配器——
馒头走成人区 API（`mode=adult`），肉丝不带分类过滤，其余站点走 MP 原生索引器但不带媒体类型；
顺序仍是“优先站点 → 其余站点”，命中即停，站点之间串行并随机间隔（§8.2）。

下载（§6.6）：候选的 enclosure 若为 `[base64]{url}` 两段式，先由 `SiteSearcher.resolve`
换票取回种子字节，再交给下载链；保存路径与下载器默认留空（用 MoviePilot 的下载器默认值），
分类默认 `avi` —— 配合 qBittorrent 的 auto_tmm（分类即目录）就不必手工维护目录。
"""

import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import SitesHelper

from . import scoring
from .ratelimit import is_antibot_error
from .sitesearch import SiteSearcher
from .store import Store

# 默认规则（与前端契约 defaultRule 一致；站点名对不上时自动忽略）
DEFAULT_RULE: Dict[str, Any] = {
    "res": "1080p",
    # 中字默认只加分不淘汰：AV 站上中字是少数（实测馒头成人区 240 条里仅 39 条带中字标记），
    # 默认「必须中字」会让绝大多数番号直接变成「没有合格候选」。想要硬门槛可在订阅规则里打开。
    "mustCnsub": False,
    "preferUncensored": True,
    "allow4k": True,
    "minSeeders": 3,
    "sites": [],
    "prefSites": ["馒头", "Rousi"],
    "btFallback": True,
    "trigger": "notify",
    "maxPerDay": 6,
    "minIntervalMin": 240,
    "savePath": "",
    "category": "avi",
    "downloader": "",
}

QUEUE_KEY = "queue"
# 保存路径与下载器留空 = 交给 MoviePilot 用「设置 → 下载器」里的默认值；
# 分类 `avi` 是给 qB 的一个标签，配合 qB 的 auto_tmm 就能自己落到分类目录。
DEFAULT_SAVE_PATH = ""
DEFAULT_CATEGORY = "avi"
# 进度快照的年龄上限（秒）。为什么分两档（2026-10-11 实测）：
# 队列里只要还有**带 hash 的历史条目**，原实现每次 `/bootstrap` 都要问一遍下载器
# （实测 17 条已完成的种子 → 每次 0.6 秒，而 `/bootstrap` 是 15 秒一轮，首屏也被它拖慢）。
# 已完成的种子进度不会再变，没必要按秒核对；真正在下载的才需要勤刷。
QUEUE_REFRESH_ACTIVE = 12      # 有未完成条目时：进度快照最多这么旧
QUEUE_REFRESH_DONE = 300       # 只有已完成条目时：多久回下载器核对一次（防被删/重新校验）


def merge_rule(rule: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把用户规则与默认值合并，缺字段回落默认。"""
    merged = dict(DEFAULT_RULE)
    if isinstance(rule, dict):
        merged.update({k: v for k, v in rule.items() if v is not None})
    return merged


def _merge_queue(queue: List[Dict[str, Any]], by_hash: Dict[str, Any],
                 thumbs: Dict[str, str]) -> List[Dict[str, Any]]:
    """把补到的封面与下载器进度就地合并进队列。

    `queue` 传进来的是**当前**数据（由 `Store.kv_update` 持锁取出），只按 id/hash 改命中项，
    快照之外的条目一个都不动——被合并掉的那次丢记录就是这么来的。
    """
    for entry in queue:
        tid = str(entry.get("id") or "")
        if tid and tid in thumbs and thumbs[tid] != entry.get("thumb"):
            entry["thumb"] = thumbs[tid]
        torrent = by_hash.get(str(entry.get("hash") or "").lower())
        if not torrent:
            continue
        try:
            raw = float(getattr(torrent, "progress", 0) or 0)
        except (TypeError, ValueError):
            raw = 0.0
        # 下载器返回的是 0-1 的小数（实测 0.4859 表示 0.49%），统一换算成百分比
        percent = raw * 100 if raw <= 1 else raw
        entry["progress"] = int(round(percent))
        state = str(getattr(torrent, "state", "") or "").lower()
        if entry["progress"] >= 100 or "upload" in state or "做种" in state:
            entry["state"] = "done"
        elif state:
            entry["state"] = "down"
    return queue[:50]


# 台账的 size 列是字节，而队列/候选里的 size 是 `scoring.human_size()` 的展示文本（"1.2 GB"）
_SIZE_RE = re.compile(r"([\d.]+)\s*(B|KB|MB|GB|TB)", re.I)


def _size_bytes(text: Any) -> int:
    """把「1.2 GB」这种展示文本还原成字节；认不出来返回 0（台账里 0 就是未知）。"""
    hit = _SIZE_RE.search(str(text or ""))
    if not hit:
        return 0
    try:
        value = float(hit.group(1))
    except ValueError:
        return 0
    scale = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
    return int(value * scale[hit.group(2).upper()])


def _queue_fingerprint(entry: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """队列条目的身份指纹：登记进台账后，据此把它从队列里摘掉。

    不能按整条 dict 相等去比——取快照与摘除之间进度/封面会被别的线程改掉，比不出来。
    只取不会变的四个字段；四个都空是坏数据（指纹全空），依旧不会误摘别人（见 `_flush_done`）。
    """
    return (str(entry.get("id") or ""), str(entry.get("number") or ""),
            str(entry.get("hash") or "").lower(), str(entry.get("added") or ""))


class TaskEngine:
    """把订阅、搜索、打分、下载四处逻辑收在一处，插件类只做薄壳调用。"""

    def __init__(self, plugin: Any, store: Store, limiter: Any, notifier: Any):
        self.plugin = plugin
        self.store = store
        self.limiter = limiter
        self.notifier = notifier
        self.searcher = SiteSearcher(chain=getattr(plugin, "chain", None),
                                     proxy=str(getattr(plugin, "_proxy", "") or ""))
        # 下载进度快照：两档时间戳（未完成 / 已完成）+ 单飞标记，见 `queue()`
        self._queue_at: Dict[str, float] = {"active": 0.0, "done": 0.0}
        self._queue_lock = threading.Lock()
        self._queue_busy = False

    # ---------- 站点 ----------

    def sites(self) -> List[Dict[str, Any]]:
        """返回全部可搜索站点配置（宿主 SitesHelper）。"""
        try:
            return SitesHelper().get_indexers() or []
        except Exception as error:  # 站点目录异常不应让整个页面崩掉
            logger.error(f"AVHelper 读取站点目录失败：{error}")
            return []

    def site_options(self) -> List[Dict[str, Any]]:
        """给界面用的站点清单（名称、id 与索引能力说明）。"""
        out = []
        for site in self.sites():
            if not site.get("name"):
                continue
            out.append(self.searcher.describe(site))
        return out

    def _site_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """按站点名取站点配置（搜索要用到 apikey/cookie，只在内存里流转）。"""
        for site in self.sites():
            if site.get("name") == name:
                return site
        return None

    def _site_cookie(self, site_name: str) -> str:
        """按站点名取 cookie（不落库，避免把密钥写进插件存储）。"""
        site = self._site_by_name(site_name)
        return str((site or {}).get("cookie") or "")

    # ---------- 搜索 ----------

    def _collect(self, cands: List[Dict[str, Any]], results: List[Any],
                 pref_sites: List[str], rule: Dict[str, Any]) -> None:
        """把站点搜索结果转成候选并即时打分。"""
        for torrent in results or []:
            cand = scoring.candidate_from_torrent(torrent, pref_sites)
            cand["_enclosure"] = str(scoring._get(torrent, "enclosure"))
            cand["_page_url"] = str(scoring._get(torrent, "page_url"))
            cand["_site_name"] = str(scoring._get(torrent, "site_name"))
            cand["adapter"] = str(scoring._get(torrent, "adapter"))
            scoring.score_candidate(cand, rule)
            cands.append(cand)

    def search_candidates(self, keyword: str, rule: Dict[str, Any],
                          only_sites: Optional[List[str]] = None
                          ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """按“优先站点 → 其余站点”顺序搜种，返回（候选, 过程说明）。

        :param keyword: 搜索词（AV 场景通常是番号，也支持任意关键词做单独检索）
        :param only_sites: 只搜这些站点（界面里单独检索时用），None 表示按规则选站
        """
        rule = merge_rule(rule)
        pref_names = [str(x) for x in (rule.get("prefSites") or [])]
        allow_names = [str(x) for x in (only_sites or rule.get("sites") or [])]
        all_sites = self.sites()
        by_name = {s.get("name"): s for s in all_sites if s.get("name")}
        pref = [by_name[n] for n in pref_names if n in by_name and (not allow_names or n in allow_names)]
        others = [
            s for s in all_sites
            if s not in pref and (not allow_names or s.get("name") in allow_names)
        ]

        cands: List[Dict[str, Any]] = []
        notes: List[str] = []
        for group, label in ((pref, "优先站点"), (others, "其余站点")):
            if not group or any(c.get("pass") for c in cands):
                continue
            for site in group:
                name = str(site.get("name") or "")
                ok, why = self.limiter.site_available(name)
                if not ok:
                    notes.append(why)
                    continue
                self.limiter.throttle()
                try:
                    results, note = self.searcher.search(site, keyword)
                    if note:
                        notes.append(f"{label}/{note}")
                except Exception as error:  # 单站失败不影响其它站
                    if is_antibot_error(error):
                        self.limiter.site_cooldown(name)
                        notes.append(f"{name} 触发站点防爬，已冷却 24 小时")
                    else:
                        notes.append(f"{name} 搜索异常：{str(error)[:120]}")
                    continue
                finally:
                    self.limiter.note_site_search(name)
                before = len(cands)
                self._collect(cands, results, pref_names, rule)
                logger.info(f"AVHelper 在 {name}（{label}）搜到 {len(cands) - before} 个候选：{keyword}")
                if any(c.get("pass") for c in cands):
                    notes.append(f"{label} {name} 已命中合格候选，停止继续搜索")
                    break
                if group is others:
                    self.limiter.site_gap()

        if not cands and not pref and not others:
            notes.append("没有可搜索的站点：请先在 MoviePilot 里配置站点，或在订阅规则里勾选站点")

        if not any(c.get("pass") for c in cands) and rule.get("btFallback"):
            # 兜底磁力优先读详情页已写好的 7 天文件缓存（详情与兜底用同一个 key），
            # 未命中才起子进程；抓取失败/无磁力都要写明，不能静默吞掉。
            magnets = self.plugin.magnets_cached(number=keyword)
            if not magnets:
                if magnets is None and self.plugin.magnets_failed_recently(keyword):
                    notes.append("BT 兜底未启用：javdb 磁力抓取失败（短时内不再重试）")
                else:
                    notes.append("BT 兜底未启用：该片在 javdb 没有可用磁力")
            else:
                for item in magnets[:5]:
                    if isinstance(item, dict) and item.get("hash"):
                        cand = scoring.candidate_from_magnet(item, pref_names)
                        scoring.score_candidate(cand, rule)
                        cands.append(cand)
                notes.append(f"PT 段没有合格候选，BT 兜底注入 {len([c for c in cands if c.get('src') == 'BT'])} 条磁力")

        scoring.rank_candidates(cands, rule)
        return cands, notes

    def build_task(self, number: str, actor: str = "", rule: Optional[Dict[str, Any]] = None,
                   auto: bool = False, thumb: str = "",
                   only_sites: Optional[List[str]] = None,
                   source: str = "manual") -> Dict[str, Any]:
        """搜种并落库一条任务（含打分明细），返回任务体。

        :param source: 任务来源标记，manual=界面手动搜索，sub=订阅检查产生。
            actor 只是元数据（番号对应的演员），不能拿它推断来源。
        """
        rule = merge_rule(rule)
        # 封面：调用方没给（番号订阅、站点搜索）时用本地索引 / 详情缓存补，补不到就留空
        thumb = str(thumb or "") or self.plugin.thumbs_of([number]).get(number, "")
        if thumb:
            self.plugin.remember_thumbs({"number": number, "cover_url": thumb})
        cands, notes = self.search_candidates(number, rule, only_sites)
        reason = scoring.explain(cands, rule)
        if notes:
            reason = reason + "｜" + "；".join(notes)
        task = {
            "id": "t" + uuid.uuid4().hex[:10],
            "number": number,
            "actor": actor or "",
            "cands": cands,
            "state": "await",
            "reason": reason,
            "thumb": thumb or "",
            "auto": bool(auto),
            "rule": rule,
            "source": str(source or "manual"),
        }
        self.store.task_add(task)
        return task

    # ---------- 下载 ----------

    def download(self, tid: str, site_name: str = "", image_base: str = "",
                 force: bool = False) -> Dict[str, Any]:
        """按任务 id 提交下载（用户点“下载”或自动订阅命中后调用）。

        :param image_base: 通知附图的绝对地址前缀（由调用方从请求里取），为空时退化为不带图
        :param force: 允许下载被规则淘汰的候选（界面上的「仍要下载」，手动挑选时用）
        """
        task = self.store.task_get(tid)
        if not task:
            return {"ok": False, "message": "任务不存在或已被清理", "notice": None}
        cands = task.get("cands") or []
        cand = None
        if site_name:
            cand = next((c for c in cands
                         if c.get("site") == site_name and (force or c.get("pass"))), None)
        if not cand and force and site_name:
            cand = next((c for c in cands if c.get("site") == site_name), None)
        cand = cand or next((c for c in cands if c.get("picked")), None) \
            or next((c for c in cands if c.get("pass")), None)
        if not cand:
            return {"ok": False, "message": "该任务没有可下载的候选", "notice": None}

        rule = merge_rule(task.get("rule"))
        save_path = str(rule.get("savePath") or DEFAULT_SAVE_PATH)
        category = str(rule.get("category") or DEFAULT_CATEGORY)
        content = str(cand.get("_enclosure") or "")
        if not content and cand.get("src") == "BT" and cand.get("hash"):
            content = f"magnet:?xt=urn:btih:{cand['hash']}"
        if not content:
            return {"ok": False, "message": "候选缺少下载地址（种子链接或磁力）", "notice": None}

        # 两段式 enclosure（馒头换票 / 肉丝详情）必须先在插件侧换成种子字节：
        # 下载链只认种子内容或磁力，宿主解析换票的 download_torrent() 不在插件的可用面上。
        site = self._site_by_name(str(cand.get("_site_name") or "")) or {}
        cookie = str(site.get("cookie") or "")
        resolved, why = self.searcher.resolve(content, site)
        if resolved is None:
            return {"ok": False, "message": why or "下载地址解析失败", "notice": None}
        try:
            result = self.plugin.chain.download(
                content=resolved,
                download_dir=Path(save_path),
                cookie=cookie,
                category=category or None,
                downloader=str(rule.get("downloader") or "") or None,
            )
        except Exception as error:
            logger.error(f"AVHelper 提交下载失败：{error}")
            return {"ok": False, "message": f"提交下载失败：{str(error)[:160]}", "notice": None}
        if not result:
            return {"ok": False, "message": "下载器没有接受该任务，请检查下载器配置", "notice": None}

        # 宿主返回 (下载器名, 种子Hash, 布局, 消息)：第 4 位是提示文案（成功时是“添加下载成功”），
        # 因此成功与否只能看 hash 是否存在——按消息判失败会把成功误报成失败。
        logger.info(f"AVHelper 下载返回：{result!r}")
        parts = list(result) if isinstance(result, (list, tuple)) else [result]
        downloader_name = parts[0] if len(parts) > 0 else None
        torrent_hash = parts[1] if len(parts) > 1 else None
        message = parts[3] if len(parts) > 3 else None
        if not torrent_hash:
            return {"ok": False, "message": f"下载器未返回种子 Hash：{message or '未知原因'}",
                    "notice": None}

        cand["picked"] = True
        self.store.task_set_state(tid, "pushed")
        self.store.known_add(task["number"], task.get("actor") or "")
        entry = {
            "id": "q" + uuid.uuid4().hex[:8],
            "number": task["number"],
            "thumb": task.get("thumb") or self.plugin.thumbs_of([task["number"]]).get(task["number"], ""),
            "site": cand.get("site") or "",
            "spec": cand.get("spec") or "",
            "size": cand.get("size") or "",
            "hash": str(torrent_hash or ""),
            "downloader": str(downloader_name or ""),
            "category": category,
            "savePath": save_path,
            "state": "down",
            "progress": 0,
            "added": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 队列与「进度刷新」共写：插入必须走原子读改写，别拿旧快照整份覆盖
        self.store.kv_update(QUEUE_KEY, lambda cur: ([entry] + (cur or []))[:50])
        # 台账登记（设计文档 §3）：提交成功先记「下载中」，完成时间等队列那一路补。
        # 写台账只是旁路记录，失败绝不影响这次提交的结果（`_ledger_upsert` 自己兜异常）。
        self._ledger_upsert(
            str(task["number"] or ""),
            title=str(cand.get("title") or ""),
            actor=str(task.get("actor") or ""),
            thumb=self._ledger_thumb(entry["thumb"]),
            size=_size_bytes(cand.get("size")),
            hash=str(torrent_hash or ""),
            path=save_path,
            downloader=str(downloader_name or ""),
            state="downloading",
            source="plugin",
        )

        notice = self.notifier.download_start(
            task["number"], cand, image=self._absolute(task.get("thumb"), image_base)
        )
        # 带上 number：接口层要靠它给「该番号已下载过」的提示（任务页那条路以前拿不到番号）
        return {"ok": True, "message": str(message or "已提交下载"), "notice": notice,
                "hash": torrent_hash, "downloader": downloader_name, "number": task["number"]}

    def download_magnet(self, number: str, info_hash: str, name: str = "") -> Dict[str, Any]:
        """详情页磁力直接推给下载器（界面上的「下载」，省掉复制再粘贴）。

        与 download() 的区别：候选不是站点搜来的，而是 javdb 详情页里的磁力 Hash，
        没有打分与规则淘汰一说，直接用全局规则里的保存路径、分类与下载器。
        """
        digest = re.sub(r"[^0-9a-fA-F]", "", str(info_hash or "")).lower()
        if len(digest) != 40:
            return {"ok": False, "message": "磁力 Hash 不是 40 位十六进制", "notice": None}
        rule = merge_rule(self.plugin.global_rule())
        save_path = str(rule.get("savePath") or DEFAULT_SAVE_PATH)
        category = str(rule.get("category") or DEFAULT_CATEGORY)
        try:
            result = self.plugin.chain.download(
                content=f"magnet:?xt=urn:btih:{digest}",
                download_dir=Path(save_path),
                cookie="",
                category=category or None,
                downloader=str(rule.get("downloader") or "") or None,
            )
        except Exception as error:
            logger.error(f"AVHelper 磁力提交失败：{error}")
            return {"ok": False, "message": f"提交下载失败：{str(error)[:160]}", "notice": None}
        if not result:
            return {"ok": False, "message": "下载器没有接受该磁力，请检查下载器配置", "notice": None}

        # 宿主返回 (下载器名, 种子Hash, 布局, 消息)：成功与否只能看 hash 是否存在
        logger.info(f"AVHelper 磁力下载返回：{result!r}")
        parts = list(result) if isinstance(result, (list, tuple)) else [result]
        downloader_name = parts[0] if len(parts) > 0 else None
        torrent_hash = parts[1] if len(parts) > 1 else None
        message = parts[3] if len(parts) > 3 else None
        if not torrent_hash:
            return {"ok": False, "message": f"下载器未返回种子 Hash：{message or '未知原因'}",
                    "notice": None}

        if number:
            self.store.known_add(number, "")
        entry = {
            "id": "q" + uuid.uuid4().hex[:8],
            "number": number,
            "thumb": self.plugin.thumbs_of([number]).get(number, "") if number else "",
            "site": "JavDB 磁力",
            "spec": str(name or "")[:60],
            "size": "",
            "hash": str(torrent_hash or ""),
            "downloader": str(downloader_name or ""),
            "category": category,
            "savePath": save_path,
            "state": "down",
            "progress": 0,
            "added": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 同 download()：插入走原子读改写，别拿旧快照整份覆盖
        self.store.kv_update(QUEUE_KEY, lambda cur: ([entry] + (cur or []))[:50])
        # 同 download()：磁力这条路径也没有演员/大小，能拿到的先记进台账（设计文档 §3）
        self._ledger_upsert(
            str(number or ""),
            title=str(name or ""),
            thumb=self._ledger_thumb(entry["thumb"]),
            hash=str(torrent_hash or ""),
            path=save_path,
            downloader=str(downloader_name or ""),
            state="downloading",
            source="plugin",
        )
        return {"ok": True, "message": str(message or "已提交下载"), "notice": None,
                "hash": torrent_hash, "downloader": downloader_name}

    @staticmethod
    def _absolute(path: Any, base: str = "") -> str:
        """把插件内的相对图片地址转成绝对地址（通知渠道要能直接取到图）。

        取不到任何可用前缀时返回空串，宁可不带图，也不发一个渠道取不到的相对地址。
        """
        url = str(path or "")
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if base:
            return base.rstrip("/") + url
        try:
            domain = settings.MP_DOMAIN(url)
            if domain:
                return str(domain)
        except Exception:
            pass
        return ""

    def task_list(self) -> List[Dict[str, Any]]:
        """任务列表：缺封面的任务用本地索引 / 详情缓存补上（不发网络请求）。"""
        tasks = self.store.task_list()
        self.plugin.fill_thumbs(tasks)
        return tasks

    def cancel_task(self, tid: str) -> Dict[str, Any]:
        """取消一条待确认任务：状态置 canceled，任务页与角标都不再算它。

        只允许取消还没提交下载的（state=await）：种子一旦推进下载器，
        插件这边说「已取消」就是假话，那种情况让用户去下载器里停。
        """
        task = self.store.task_get(tid)
        if not task:
            return {"ok": False, "message": "任务不存在或已被清理"}
        if str(task.get("state") or "") != "await":
            return {"ok": False, "message": "该任务已提交下载，取消请到下载器里操作"}
        self.store.task_set_state(tid, "canceled")
        logger.info(f"AVHelper 取消待确认任务：{task.get('number')}（{tid}）")
        return {"ok": True, "message": f"已取消 {task.get('number') or ''} 的待确认任务"}

    def queue(self, fresh: bool = False) -> List[Dict[str, Any]]:
        """返回下载队列（顺带补番号封面），并**按需**从下载器刷新真实进度。

        两条读法（2026-10-11 改，起因是 `/bootstrap` 每次 0.6 秒）：

        | 调用方 | `fresh` | 行为 |
        | --- | --- | --- |
        | `/bootstrap`（15 秒轮询、首屏） | `False` | **立刻**返回本地快照；该刷时丢一条守护线程去刷（单飞），下一轮就拿到新进度 |
        | `/tasks`、提交下载/磁力下载/检查之后 | `True` | **同步**问一次下载器：用户正盯着看，宁可等这 0.6 秒 |

        "该刷"分两档年龄（见 `QUEUE_REFRESH_ACTIVE` / `QUEUE_REFRESH_DONE`）：
        未完成的条目 12 秒一轮，已完成的 5 分钟才核对一次 —— 已完成的进度不会再变，
        按秒去问只是白等（本机队列里 17 条全是 done，改前每次请求都为此付 0.6 秒）。

        落库一律走 `Store.kv_update` 的就地合并：取快照之后还要等下载器回包（可能几秒），
        期间「提交下载」插入的新条目不能因为整份覆盖而丢（实测丢过一条已下载完成的记录）。

        返回前会把已完成的条目登记进台账并从队列里摘掉（见 `_flush_done`，设计文档 §3）：
        历史归台账、队列只留下载中，下载页不再为完成项画进度条，也免得每轮都拿一堆
        已完成的 hash 去问下载器。
        """
        queue = self.store.kv_get(QUEUE_KEY, []) or []
        thumbs: Dict[str, str] = {}
        if self.plugin.fill_thumbs(queue):     # 旧队列项没封面：补到就落库，省得每次重算
            thumbs = {str(x.get("id")): str(x.get("thumb") or "") for x in queue if x.get("id")}

        active = [str(q.get("hash")) for q in queue
                  if q.get("hash") and str(q.get("state") or "") != "done"]
        done = [str(q.get("hash")) for q in queue
                if q.get("hash") and str(q.get("state") or "") == "done"]
        by_hash: Dict[str, Any] = {}
        if fresh:
            by_hash = self._query_torrents(active + done)
            if active:
                self._queue_at["active"] = time.time()
            if done:
                self._queue_at["done"] = time.time()
        else:
            self._kick_refresh(active, done)

        if thumbs or by_hash:
            queue = self.store.kv_update(
                QUEUE_KEY, lambda cur: _merge_queue(cur or [], by_hash, thumbs))
        return self._flush_done(queue)

    def _flush_done(self, queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把已完成的条目登记进台账并从队列摘掉，返回摘完的队列（设计文档 §3）。

        `queue` 传进来的是刚合并完的快照，**摘除要在 `kv_update` 里按指纹就地做**：
        快照与摘除之间「提交下载」还会插入新条目，整份写回会把那条冲掉（老毛病）。
        只摘「登记成功」的那几条——台账写失败就留在队列里下轮重试，宁可在下载页多显示
        一行「已完成」，也不能让这条下载从两处记录里同时消失。
        """
        done = [e for e in (queue or [])
                if isinstance(e, dict) and str(e.get("state") or "") == "done"]
        if not done:
            return queue
        moved = set()
        for entry in done:
            number = str(entry.get("number") or "")
            if not number:
                continue            # 没番号归一不出 key：留在队列里当「已完成」显示，别悄悄丢掉
            if self._ledger_upsert(
                number,
                title=str(entry.get("title") or ""),
                thumb=self._ledger_thumb(entry.get("thumb")),
                size=_size_bytes(entry.get("size")),
                hash=str(entry.get("hash") or ""),
                path=str(entry.get("savePath") or ""),
                downloader=str(entry.get("downloader") or ""),
                state="downloaded",
                created_at=str(entry.get("added") or ""),   # 只在首次写入时生效
            ):
                moved.add(_queue_fingerprint(entry))
        if not moved:
            return queue

        def keep(cur: Any) -> List[Dict[str, Any]]:
            """就地摘掉已登记的条目；其余条目与顺序原样保留（期间新插入的不能丢）。"""
            return [item for item in (cur or [])
                    if not (isinstance(item, dict) and _queue_fingerprint(item) in moved)]

        try:
            return self.store.kv_update(QUEUE_KEY, keep)
        except Exception as error:
            logger.error(f"AVHelper 从队列移除已完成条目失败：{error}")
            return queue

    # ---------- 下载台账 ----------

    def migrate_queue_to_ledger(self) -> int:
        """把队列里还留着的、已完成的老条目补登记进台账（`source='queue'`），返回登记条数。

        给启动预热与打开历史页用：只登记、**不删队列条目**（摘除由 `queue()` 的常规路径做），
        所以反复调用是安全的——台账按归一化番号合并，重复登记只是刷新 `updated_at`。
        返回的是「这次交去登记的条数」（不是新增行数，新增多少看 `Store.download_seed`）；
        写库失败返回 0，调用方据此知道这一轮没补上。
        """
        rows: List[Dict[str, Any]] = []
        for entry in (self.store.kv_get(QUEUE_KEY, []) or []):
            if not isinstance(entry, dict) or str(entry.get("state") or "") != "done":
                continue
            number = str(entry.get("number") or "")
            if not number:          # 归一不出 key 的登记不了，跳过
                continue
            stamp = str(entry.get("added") or "")
            rows.append({
                "number": number,
                "title": str(entry.get("title") or ""),
                "thumb": self._ledger_thumb(entry.get("thumb")),
                "size": _size_bytes(entry.get("size")),
                "hash": str(entry.get("hash") or ""),
                "path": str(entry.get("savePath") or ""),
                "downloader": str(entry.get("downloader") or ""),
                "state": "downloaded",
                "source": "queue",
                # 老条目里 `added` 是它真正的提交时间，也是这批数据里唯一的时间戳；
                # 拿「迁移当天」当完成时间会把几天前的下载记录全拉到现在，所以两个时间都用它。
                "created_at": stamp,
                "completed_at": stamp,
            })
        if not rows:
            return 0
        try:
            self.store.download_seed(rows)
        except Exception as error:
            logger.error(f"AVHelper 迁移老队列到下载台账失败：{error}")
            return 0
        logger.info(f"AVHelper 老队列迁移：登记 {len(rows)} 条已完成下载")
        return len(rows)

    def _ledger_thumb(self, thumb: Any) -> str:
        """封面转台账口径：台账存图床**原地址**，读的时候才转 /img 代理。

        队列与任务里的 thumb 已经是插件代理地址（`thumbs_of`/`fill_thumbs` 的产物），
        原样写进台账会被读的那一侧再包一层代理——`__init__._raw_image()` 的注释里
        把「代理套代理」单独标出来过，所以这里先还原成原地址。
        """
        raw = str(thumb or "")
        unwrap = getattr(self.plugin, "_raw_image", None)
        if not raw or not callable(unwrap):
            return raw
        try:
            return str(unwrap(raw) or raw)
        except Exception:
            return raw

    def _ledger_upsert(self, number: str, **fields: Any) -> bool:
        """写一条台账，返回是否写入成功；失败只记日志。

        台账是「下载过什么」的旁路记录：写失败绝不能让提交下载或队列渲染跟着失败，
        但调用方要据此决定队列条目摘不摘——没登记成功的留在队列里下轮重试。
        番号为空同样返回 False（归一不出 key，登记不了），别让调用方以为记上了。
        """
        if not str(number or "").strip():
            return False
        try:
            self.store.download_upsert(number, **fields)
            return True
        except Exception as error:
            logger.error(f"AVHelper 写下载台账失败（{number}）：{error}")
            return False

    def _query_torrents(self, hashes: List[str]) -> Dict[str, Any]:
        """问一次下载器，返回 `hash → 种子对象`；失败只记日志（不抛、不影响队列渲染）。"""
        if not hashes:
            return {}
        try:
            torrents = self.plugin.chain.list_torrents(hashs=hashes) or []
        except Exception as error:
            logger.error(f"AVHelper 刷新下载进度失败：{error}")
            return {}
        by_hash: Dict[str, Any] = {}
        for item in torrents:
            h = str(getattr(item, "hash", "") or getattr(item, "hashString", "") or "").lower()
            if h:
                by_hash[h] = item
        return by_hash

    def _kick_refresh(self, active: List[str], done: List[str]) -> None:
        """到点了就在后台补一次进度（守护线程 + 单飞），请求本身不等它。"""
        now = time.time()
        need_active = bool(active) and now - self._queue_at["active"] >= QUEUE_REFRESH_ACTIVE
        need_done = bool(done) and now - self._queue_at["done"] >= QUEUE_REFRESH_DONE
        if not need_active and not need_done:
            return
        hashes = (active if need_active else []) + (done if need_done else [])
        with self._queue_lock:
            if self._queue_busy:
                return
            self._queue_busy = True

        def worker() -> None:
            try:
                by_hash = self._query_torrents(hashes)
                if need_active:
                    self._queue_at["active"] = time.time()
                if need_done:
                    self._queue_at["done"] = time.time()
                if by_hash:
                    # 只并进度，不动封面：封面那条线上一次请求已经写过了
                    self.store.kv_update(QUEUE_KEY, lambda cur: _merge_queue(cur or [], by_hash, {}))
            except Exception as error:         # 后台线程里的异常绝不能漏出去
                logger.error(f"AVHelper 后台刷新下载进度失败：{error}")
            finally:
                with self._queue_lock:
                    self._queue_busy = False

        threading.Thread(target=worker, name="avhelper-queue", daemon=True).start()

    # ---------- 订阅检查 ----------

    def check(self, name: Optional[str] = None) -> Dict[str, Any]:
        """手动或有计划地检查订阅；受 §8.2 限流约束。"""
        subs = self.store.sub_list()
        if name:
            subs = [s for s in subs if s.get("name") == name]
        if not subs:
            return {"limited": False, "notices": [], "message": "没有可检查的订阅"}

        max_per_day = max(int(merge_rule(s.get("rule")).get("maxPerDay") or 6) for s in subs)
        min_interval = max(int(merge_rule(s.get("rule")).get("minIntervalMin") or 240) for s in subs)
        allowed, why = self.limiter.check_allowed(max_per_day, min_interval)
        if not allowed:
            notice = self.notifier.limited(why)
            return {"limited": True, "notices": [notice], "message": why}

        notices: List[Dict[str, Any]] = []
        for sub in subs:
            rule = merge_rule(sub.get("rule"))
            if sub.get("type") == "number":
                notices.append(self.notifier.sub_hit_number(sub["name"]))
                task = self.build_task(sub["name"], "", rule,
                                        bool(rule.get("trigger") == "auto"), source="sub")
                notices.extend(self._after_task(task, sub, rule))
            else:
                notices.extend(self._check_actor(sub, rule))
            self.store.sub_touch(int(sub.get("id") or 0), int(sub.get("hits") or 0) + 1)
        self.limiter.note_check()
        return {"limited": False, "notices": notices, "message": f"已检查 {len(subs)} 条订阅"}

    def _check_actor(self, sub: Dict[str, Any], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """演员订阅：作品史与 known 差集 → 新片搜种。

        作品史按发行时间倒序，新片一定在头部：只看最新的一页（50 部）就够，不再拉全量
        （`--all` 对上千部的演员要 35 秒）。整页都是已知的（久未检查）才往后多翻一页。
        """
        name = sub.get("name") or ""
        known = set(self.store.known_all())
        movies: List[Dict[str, Any]] = []
        for page in (1, 2):
            data = self.plugin.cli().actor(name, page=page, limit=50) or {}
            batch = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
            movies.extend(batch)
            if any(m.get("number") and m.get("number") not in known for m in batch) or len(batch) < 50:
                break
        if not movies:
            return [self.notifier.info("检查完成", f"{name}：没有取到作品史")]
        known = set(self.store.known_all())
        fresh = [m for m in movies if m.get("number") and m.get("number") not in known]
        if not fresh:
            return [self.notifier.info("检查完成", f"{name}：没有新片")]
        notices: List[Dict[str, Any]] = []
        for movie in fresh[:3]:  # 单次最多处理 3 部，避免一次检查把站点打爆
            number = str(movie.get("number"))
            thumb = self.plugin.image_url(movie.get("cover_url") or movie.get("thumb_url"))
            self.store.known_add(number, name)
            notices.append(self.notifier.sub_new_actor(name, number))
            task = self.build_task(number, name, rule,
                                   bool(rule.get("trigger") == "auto"), thumb, source="sub")
            notices.extend(self._after_task(task, sub, rule))
        return notices

    def _after_task(self, task: Dict[str, Any], sub: Dict[str, Any],
                    rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """任务建好后：自动订阅命中即下载，否则发“等你确认”。"""
        best = next((c for c in (task.get("cands") or []) if c.get("pass")), None)
        if rule.get("trigger") == "auto" and best:
            result = self.download(task["id"])
            if result.get("ok"):
                return [result["notice"]] if result.get("notice") else []
            return [self.notifier.info("自动下载失败", str(result.get("message") or ""))]
        return [self.notifier.candidate_ready(task["number"], len(task.get("cands") or []))]
