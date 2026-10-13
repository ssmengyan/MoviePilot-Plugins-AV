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
from typing import Any, Dict, List, Optional, Set, Tuple

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import SitesHelper

from . import emby
from . import scoring
from .ratelimit import (POLICY_MAX_PER_DAY, POLICY_MIN_INTERVAL_MIN, is_antibot_error)
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
# 「这个 hash 在下载器里查不到了」要连续这么多轮才认账（2026-10-12 加，见 `_flush_gone`）。
# 为什么要容忍：查询偶尔会抽风（下载器重启、模块把错误吞成空列表），凭一次失败就删掉一条
# 正在下载的记录，比多留十几秒的假记录更糟。中途又查到就立刻清零，所以只有真没了才会累计。
QUEUE_MISS_LIMIT = 2
# 「下完了」的判据用宿主归一后的状态（`DownloadTaskState`：downloading / paused / completed），
# **不是**进度数字 —— 同一个字段各家下载器给的口径不一样，见 `_percent()` 的说明。
# ⚠️ 但宿主这一步归一**是有损的**（2026-10-14 在容器里逐行核对 MP v3.1.5 的源码）：
# `app/modules/qbittorrent/__init__.py:370-379` 的 `__normalize_torrent_state()` 只认
# 「下载中」与「暂停」两组原始状态，其余**一律 `return DownloadTaskState.COMPLETED`** ——
# qB 的 `error` / `missingFiles` / `unknown` 三个失败态到插件这里已经变成 `'completed'`，
# 而 `DownloaderTorrent`（`app/schemas/transfer.py:14-43`）上**没有原始状态的透传字段**。
# 所以 `state == 'completed'` 只有在进度同时到 100% 时才算「真下完」，见 `_failure_reason()`。
QUEUE_DONE_STATE = "completed"
# 进度数字只作兜底：原生读数就是百分比口径时 ≥ 99.5 也算下完（状态万一没归一到 completed）。
QUEUE_DONE_RAW = 99.5

# 「这颗种子是失败的」（v4.1 §9.2 第 1 条）。qBittorrent 的原始状态里这三类是明确的失败态：
#   error        —— 种子出错（tracker / 磁盘 / 权限）
#   missingFiles —— 文件已经不在磁盘上了
#   unknown      —— qB 自己也认不出的状态
# 别名一并收着：qB 各版本与别的下载器写法不完全一样；判据只比字符串，多收几个不会误伤。
QUEUE_FAIL_STATES = frozenset({
    "error", "errored", "missingfiles", "missing_files", "unknown",
})
# 台账里「这个番号已经被占住」的两种状态（订阅查重用，见 `duplicate_reason()`）：
# `failed` **不算**占住 —— 失败了本来就该允许重下。
DOWNLOAD_TAKEN_STATES = ("downloading", "downloaded")
# 种子对象上可能挂着状态串的地方：`state` 是宿主归一后的那一份，其余是给别的宿主版本、
# 直接透传原始状态的下载器模块、以及单测替身留的口子（见 `_torrent_states()`）。
_TORRENT_STATE_ATTRS = ("state", "raw_state", "rawState", "torrent_state", "qbit_state", "qb_state")
_TORRENT_STATE_CONTAINERS = ("raw", "data", "info", "torrent_data", "source_data")

# 定时重刮每档一次取几条待办（Tier 1 到点重试 / Tier 2 冷数据滚动，契约 §3.2 的 `meta_due`）。
SCRAPE_TIER_LIMIT = 5


def _torrent_states(torrent: Any) -> Set[str]:
    """把种子对象上**所有**可能的状态串收齐（小写、去空白）。

    为什么要收一网：宿主的 `DownloaderTorrent.state` 是归一后的值（见 `QUEUE_DONE_STATE`
    上面那段），qB 的失败态在那一步就被吞掉了；但只要对象上还留着原始状态（别的宿主版本、
    直接透传的下载器模块、单测里的替身），这里就能认出来。判据是字符串，收多了不会误伤。
    """
    found: Set[str] = set()
    for name in _TORRENT_STATE_ATTRS:
        value = getattr(torrent, name, None)
        if isinstance(value, str) and value.strip():
            found.add(value.strip().lower())
    for name in _TORRENT_STATE_CONTAINERS:
        nested = getattr(torrent, name, None)
        if isinstance(nested, dict):
            value = nested.get("state")
            if isinstance(value, str) and value.strip():
                found.add(value.strip().lower())
    return found


def _failure_reason(torrent: Any, progress: float) -> str:
    """种子是不是失败态：失败给一句原因，不失败给空串。

    两条判据**都只看种子状态**，绝不看「队列里还在不在」或「完成时间有没有值」：

    1. 状态串本身落在 `QUEUE_FAIL_STATES`（宿主把 qB 原始状态透传过来时走这条）；
    2. 宿主归一成了 `completed` **而进度不到 100%** —— 真做完的种子（qB 的 uploading /
       stalledUP / queuedUP / checkingUP / moving）进度必然是 100，反过来说「说完成了却
       没到 100」只可能是被吞掉的 `error` / `missingFiles` / `unknown`。

    ⚠️ 已知的边界：`missingFiles` 且进度正好 100%（下完了才把文件挪走/删掉）在本判据下
    **仍算完成** —— 那一颗种子的事实是"文件不在了"，但这次下载确实下完过。这条边界在
    本机无从观测（没有处于该状态的种子），见交付报告的未验证项。
    """
    for state in sorted(_torrent_states(torrent)):
        if state in QUEUE_FAIL_STATES:
            return f"下载器报种子状态 {state}"
    if (str(getattr(torrent, "state", "") or "").strip().lower() == QUEUE_DONE_STATE
            and progress < QUEUE_DONE_RAW):
        return (f"下载器报已完成但进度只有 {progress:.0f}%"
                f"（宿主把 error/missingFiles/unknown 归一成了 completed）")
    return ""


def _canon(text: Any) -> str:
    """跨层匹配用的**规范号**（契约 D1：`emby.canon_key()` —— parse 优先，认不出退回旧口径）。

    S2 的 `canon_key()` 已落地（2026-10-14，`emby.py:358`），本层仍包着是为了两个兜底：

    ① 并行施工期 `emby.py` 还在被改（万一又没了这个函数）：`getattr` 探一下，退回
       `parse_av_number().norm_key`，再退旧口径 `norm_key()` —— 本文件的去重判定不能
       因为别的模块没就位就整条挂掉；
    ② `canon_key()` 内部抛异常时也不能把订阅检查带崩。
    """
    fn = getattr(emby, "canon_key", None)
    if callable(fn):
        try:
            key = str(fn(text) or "")
            if key:
                return key
        except Exception as error:      # 归一失败绝不能把调用方带崩
            logger.error(f"AVHelper canon_key({text!r}) 失败：{error}")
    parser = getattr(emby, "parse_av_number", None)
    if callable(parser):
        try:
            key = str(getattr(parser(text), "norm_key", "") or "")
            if key:
                return key
        except Exception as error:
            logger.error(f"AVHelper parse_av_number({text!r}) 失败：{error}")
    return emby.norm_key(text)


def _same_number(candidate: Any, keys: List[str], canon: str) -> bool:
    """候选番号是不是目标那一个：先按归一化键直查，再把候选过一遍 `canon_key()` 比一次。

    为什么要第二步（2026-10-14 实测）：台账与 Emby 索引里存的可能是**旧口径**键
    （保留后缀：`IPZZ912UC` / `CAWD9894K` / `IPZZ58624K`），而订阅拿到的是干净番号
    （`IPZZ-912`）—— 两边各过一遍 `canon_key()` 才能对上（`IPZZ912UC` → `IPZZ912` ✓）。
    也不能用「前缀匹配」凑：`IPZZ912` 是 `IPZZ912UC` 的前缀没错，但 `ABP123` 同样是
    `ABP1234` 的前缀 —— 那是两部不同的片，按前缀比会互相误判。
    """
    text = str(candidate or "").strip()
    if not text:
        return False
    if text in keys:
        return True
    return bool(canon) and _canon(text) == canon


def merge_rule(rule: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把用户规则与默认值合并，缺字段回落默认，并把限流两项夹回政策值。

    `maxPerDay` / `minIntervalMin` 是规则里**用户可写**的字段，而政策要求每天 ≤6 次、
    间隔 ≥240 分钟：在合并这一处夹一次，这样「存进 kv 的规则」「界面读回来的规则」
    「限流判定用的规则」三处永远是同一个数（2026-10-13 修：早先界面能填 100）。
    间隔只抬不降，所以想调**紧**（比如改成 480 分钟）依然可以。
    """
    merged = dict(DEFAULT_RULE)
    if isinstance(rule, dict):
        merged.update({k: v for k, v in rule.items() if v is not None})
    merged["maxPerDay"] = min(max(_int_or(merged.get("maxPerDay"), POLICY_MAX_PER_DAY), 1),
                              POLICY_MAX_PER_DAY)
    merged["minIntervalMin"] = max(_int_or(merged.get("minIntervalMin"), POLICY_MIN_INTERVAL_MIN),
                                   POLICY_MIN_INTERVAL_MIN)
    return merged


def _int_or(value: Any, default: int) -> int:
    """规则里的数字字段 → 整数；认不出来用默认值（合法 JSON 里也可能是字符串）。"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ---------- 搜种结论（手动「下载该影片」与订阅检查共用同一套判定） ----------

def split_segments(cands: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """按来源把候选切成（PT 段, BT 兜底段）；`src` 缺省当 PT。"""
    pt = [c for c in cands if str(c.get("src") or "") != "BT"]
    bt = [c for c in cands if str(c.get("src") or "") == "BT"]
    return pt, bt


def rule_verdict(cands: List[Dict[str, Any]], rule: Dict[str, Any]) -> Dict[str, Any]:
    """按候选与规则判定「PT 中没中、BT 兜底试没试/中没中」，并给出待确认标记。

    - `pt`：`hit` = PT 段至少一条合格候选；`miss` = 0 条，或结果全被规则淘汰；
    - `bt`：`skipped`（PT 已命中，不必兜底）/ `off`（兜底开关关着，根本没试）/
      `hit`（兜底段有合格候选）/ `miss`（试了但没有合格候选，含"javdb 上没有磁力"）；
    - `pending`：进「任务」页时卡片上的标记 —— `''` 普通待确认（有候选可挑）、
      `pt-only` = 「PT/BT 待确认」（PT 没中且没试 BT）、
      `none` = 「所有源均未找到」（PT 与 BT 都没有可用资源）。
    """
    pt, bt = split_segments(cands or [])
    pt_pass = any(c.get("pass") for c in pt)
    bt_pass = any(c.get("pass") for c in bt)
    if pt_pass:
        bt_state = "skipped"
    elif not rule.get("btFallback"):
        bt_state = "off"
    elif bt_pass:
        bt_state = "hit"
    else:
        bt_state = "miss"
    if pt_pass or bt_pass:
        pending = ""
    elif bt_state == "off":
        pending = "pt-only"
    else:
        pending = "none"
    return {
        "pt": "hit" if pt_pass else "miss",
        "bt": bt_state,
        "pending": pending,
        "pt_total": len(pt), "pt_pass": sum(1 for c in pt if c.get("pass")),
        "bt_total": len(bt), "bt_pass": sum(1 for c in bt if c.get("pass")),
    }


def acquire_feedback(task: Dict[str, Any], verdict: Dict[str, Any],
                     result: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """「下载该影片」按完要说的话（级别 + 文案），顺序就是界面弹出顺序。

    **文案由后端定**：前端只把 `toasts` 依次弹出来，不自己判断该说什么 ——
    这样"PT 没找到"「所有源都没找到」这两句只有一处实现，改文案不用两头找。
    """
    cands = [c for c in (task.get("cands") or []) if isinstance(c, dict)]
    pt, _bt = split_segments(cands)
    pt_hit = verdict.get("pt") == "hit"
    toasts: List[Dict[str, str]] = []

    if not pt_hit:
        toasts.append({"level": "warning", "text": "PT 站未找到资源"})
        rejected = [c for c in pt if not c.get("pass")]
        if rejected:
            # PT 其实搜到了，只是全被规则淘汰：主提示照旧，第二行把实情说清楚，
            # 否则用户会以为站点上一条都没有（那种情况可以点「仍要下载」硬下）。
            sites = "、".join(dict.fromkeys(str(c.get("site") or "") for c in rejected if c.get("site")))
            toasts.append({
                "level": "info",
                "text": f"{sites + ' ' if sites else ''}有 {len(rejected)} 条候选但不满足规则，"
                        f"可在「任务」页点「仍要下载」",
            })

    if result and result.get("ok"):
        if pt_hit:
            toasts.append({"level": "success", "text": "已提交下载"})
            detail = " · ".join(x for x in (str(result.get("site") or ""),
                                            str(result.get("spec") or "")) if x)
            toasts.append({"level": "info", "text": (detail + " · " if detail else "") + "进度见「下载」页"})
        else:
            toasts.append({"level": "success", "text": "已用 BT 磁力兜底提交下载"})
            toasts.append({"level": "info", "text": "进度见「下载」页"})
        return toasts

    if pt_hit:
        toasts.append({"level": "info",
                       "text": f"已找到 {int(verdict.get('pt_pass') or 0)} 个候选，去「任务」页挑一个"})
    elif verdict.get("bt") == "hit":
        toasts.append({"level": "info", "text": "已用 BT 磁力兜底找到候选，去「任务」页挑一个"})
    elif verdict.get("bt") == "off":
        toasts.append({"level": "info",
                       "text": "已放进「任务」页：可手动挑一条，或点「订阅该影片」等资源出现"})
    else:
        toasts.append({"level": "warning", "text": "该资源在所有源中均未找到"})
        toasts.append({"level": "info", "text": "已放进「任务」页：可点「订阅该影片」等资源出现"})
    return toasts


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
        # 「这台下载器给的进度已经是百分比了」：按下载器名记住，见 `_percent()`
        self._scales: Dict[str, bool] = {}
        self._queue_lock = threading.Lock()
        self._queue_busy = False
        # 最近一次「下载器失联」的原因（空串 = 上次是通的），见 `downloader_state()`
        self._downloader_error = ""

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

        :param source: 任务来源标记，manual=界面手动搜索 /「下载该影片」，sub=订阅检查产生。
            actor 只是元数据（番号对应的演员），不能拿它推断来源。
            **来源决定要不要查重**（v4.1 §9.2 第 2 条）：`sub` 先查三处（Emby 库 / 下载台账 /
            待确认任务），命中任一就**不建这条任务**（返回一条 `state='skipped'` 的空任务，
            并补写 known）；`manual` 是用户手动洗版的明确意图，一律放行 —— 详情抽屉
            「下载该影片」与站点搜索这两个入口落库写的就是 `manual`。
        """
        rule = merge_rule(rule)
        duplicate = self.duplicate_reason(number, source)
        if duplicate:
            # 只在订阅那条路上会走到（manual 恒放行）：补写 known 让下一轮作品史差集不再把它
            # 当新片，然后回一条空任务 —— 调用方按 `state == 'skipped'` 给提示（见 `_after_task`）。
            self.store.known_add(number, actor)
            logger.info(f"AVHelper 订阅下单跳过：{number} 已经存在（{duplicate}），只补写 known")
            return {"id": "", "number": number, "actor": actor or "", "cands": [],
                    "state": "skipped", "reason": duplicate, "thumb": "", "auto": False,
                    "rule": rule, "source": str(source or "manual"), "pending": "",
                    "duplicate": duplicate}
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
            # 卡片上的标记：'' = 普通待确认、'pt-only' = PT/BT 待确认、'none' = 所有源均未找到
            # （口径见 `rule_verdict()`；老任务没有这个字段，前端按空处理）
            "pending": rule_verdict(cands, rule)["pending"],
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
        # 带上 site/spec/src：`acquire()` 的成功提示要写清"下的是哪一条"
        return {"ok": True, "message": str(message or "已提交下载"), "notice": notice,
                "hash": torrent_hash, "downloader": downloader_name, "number": task["number"],
                "site": str(cand.get("site") or ""), "spec": str(cand.get("spec") or ""),
                "src": str(cand.get("src") or "")}

    def acquire(self, number: str, actor: str = "", rule: Optional[Dict[str, Any]] = None,
                thumb: str = "", image_base: str = "",
                only_sites: Optional[List[str]] = None) -> Dict[str, Any]:
        """「下载该影片」：搜种 → 按规则判定 → 当场下载，或落一条待确认任务。

        与 `build_task()` 的区别只有一个，但正是用户报的那个问题：**它按规则里的
        `trigger` 决定要不要当场下单**。手动这条路以前在接口层恒传 `auto=False`
        （`__init__.py` 的 `api_task_search`），规则写着「自动下载」也不会下。

        :param image_base: 通知附图的绝对地址前缀（同 `download()`）。
        """
        rule = merge_rule(rule)
        auto = str(rule.get("trigger") or "notify") == "auto"
        task = self.build_task(number, actor, rule, auto, thumb, only_sites, source="manual")
        verdict = rule_verdict(task.get("cands") or [], rule)

        result: Optional[Dict[str, Any]] = None
        if auto and (verdict["pt"] == "hit" or verdict["bt"] == "hit"):
            # `download()` 不传站点 = 取排序后 `picked` 的那条，也就是打分最高的合格候选
            result = self.download(str(task.get("id") or ""), image_base=image_base)

        downloaded = bool(result and result.get("ok"))
        if downloaded:
            # 状态已变成 pushed，回给界面的应当是刷新过的那一份
            task = self.store.task_get(str(task.get("id") or "")) or task

        toasts = acquire_feedback(task, verdict, result if downloaded else None)
        if result is not None and not result.get("ok"):
            toasts.append({"level": "warning",
                           "text": f"自动下载失败：{result.get('message') or '请稍后重试'}"})
        logger.info(f"AVHelper 下载该影片 {number}：pt={verdict['pt']} bt={verdict['bt']} "
                    f"pending={verdict['pending']!r} 候选 {len(task.get('cands') or [])} 条 "
                    f"→ {'已提交下载' if downloaded else '待确认'}")
        return {
            "task": task,
            "outcome": "downloaded" if downloaded else "pending",
            "pt": verdict["pt"],
            "bt": verdict["bt"],
            "pending": verdict["pending"],
            "candCount": len(task.get("cands") or []),
            "passCount": int(verdict["pt_pass"]) + int(verdict["bt_pass"]),
            "hash": str((result or {}).get("hash") or "") if downloaded else "",
            "downloader": str((result or {}).get("downloader") or "") if downloaded else "",
            "site": str((result or {}).get("site") or "") if downloaded else "",
            "spec": str((result or {}).get("spec") or "") if downloaded else "",
            "toasts": toasts,
            "message": "；".join(t["text"] for t in toasts),
        }

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

    def cancel_all(self, number_or_key: str, cancel_sub: bool = True) -> Dict[str, Any]:
        """「不要了」的三个出口一次做干净（v4.1 §9.2 第 4 条）。

        **返回形状定死了，S8 按这个接**::

            {
              'ok': bool,            # 四步全成功才 True
              'steps': {
                  'torrent': {'ok': bool, 'detail': str},   # 让下载器删种（不动磁盘文件）
                  'ledger':  {'ok': bool, 'detail': str},   # 台账打墓碑 hidden=1
                  'sub':     {'ok': bool, 'detail': str},   # 删对应的番号/演员订阅
                  'known':   {'ok': bool, 'detail': str},   # 写 known 忽略表
              },
              'error': str,          # 失败步骤的原因摘要（都成功时是空串）
            }

        每一步都**独立成败**：删种子失败不该拦住台账与订阅的清理（用户点了「不要了」，
        最要紧的是"它别再回来"）。`ok=False` 时 `error` 里会写清是哪一步没做成。

        :param cancel_sub: 默认 True = 连订阅一起删（界面上默认勾选）；False = 只清前三步。

        关于删文件：`remove_torrents(delete_file=False)` —— **只摘下载器里的任务，不删磁盘文件**。
        这条路径的语义是「我不要这个下载了」，而不是「删掉这个视频」；已经下好的正片在媒体库里，
        顺手删文件是破坏性动作，不该由一个取消按钮代劳（要清理由用户自己去下载器/文件管理里做）。
        """
        steps: Dict[str, Dict[str, Any]] = {
            "torrent": {"ok": True, "detail": ""},
            "ledger": {"ok": True, "detail": ""},
            "sub": {"ok": True, "detail": ""},
            "known": {"ok": True, "detail": ""},
        }
        raw = str(number_or_key or "").strip()
        if not raw:
            return {"ok": False, "steps": steps, "error": "缺少番号或归一化键"}
        keys = self._match_keys(raw)
        canon = _canon(raw)

        # 1) 下载器种子：队列里（正在下）与台账里（已完成/失败）两处的 hash 都要算上
        hashes: List[str] = []
        for entry in (self.store.kv_get(QUEUE_KEY, []) or []):
            if isinstance(entry, dict) and _same_number(entry.get("number"), keys, canon):
                digest = str(entry.get("hash") or "").strip()
                if digest:
                    hashes.append(digest)
        actor = ""
        try:
            for row in (self.store.download_list() or []):
                if not isinstance(row, dict) or not _same_number(row.get("key"), keys, canon):
                    continue
                actor = actor or str(row.get("actor") or "")
                digest = str(row.get("hash") or "").strip()
                if digest:
                    hashes.append(digest)
        except Exception as error:
            logger.error(f"AVHelper 取消时读台账失败（{raw}）：{error}")
        hashes = list(dict.fromkeys(h.lower() for h in hashes if h))
        if not hashes:
            steps["torrent"] = {"ok": True, "detail": "下载器里没有这个番号的种子（跳过）"}
        else:
            ok, detail = self._remove_torrents(hashes)
            steps["torrent"] = {"ok": ok, "detail": detail}

        # 2) 台账打墓碑（`download_delete` 是幂等的）
        try:
            done = bool(self.store.download_delete(raw))
            steps["ledger"] = {"ok": done,
                               "detail": "已从下载历史移除（hidden=1）" if done
                                         else "归一不出番号键，无法移除记录"}
        except Exception as error:
            logger.error(f"AVHelper 取消时写台账墓碑失败（{raw}）：{error}")
            steps["ledger"] = {"ok": False, "detail": f"移除下载记录失败：{str(error)[:120]}"}

        # 3) 订阅：番号订阅按番号对，演员订阅按台账里记的演员对
        if not cancel_sub:
            steps["sub"] = {"ok": True, "detail": "按参数跳过（cancel_sub=false）"}
        else:
            steps["sub"] = self._drop_subs(keys, canon, actor)

        # 4) known 忽略表：写进去，下次检查/下单就当它已经存在
        try:
            self.store.known_add(raw, actor)
            steps["known"] = {"ok": True, "detail": "已写入忽略表（known）"}
        except Exception as error:
            logger.error(f"AVHelper 取消时写 known 失败（{raw}）：{error}")
            steps["known"] = {"ok": False, "detail": f"写入忽略表失败：{str(error)[:120]}"}

        failed = [f"{name}：{step['detail']}" for name, step in steps.items() if not step["ok"]]
        logger.info(f"AVHelper「不要了」{raw}："
                    + "；".join(f"{name}={step['detail'] or 'ok'}" for name, step in steps.items()))
        return {"ok": not failed, "steps": steps, "error": "；".join(failed)}

    def _remove_torrents(self, hashes: List[str]) -> Tuple[bool, str]:
        """让下载器删掉这些种子（不删文件），返回 `(成功?, 说明)`。"""
        chain = getattr(self.plugin, "chain", None)
        if chain is None:
            return False, "宿主没有可用的下载链，删不了种子"
        try:
            try:
                result = chain.remove_torrents(hashs=list(hashes), delete_file=False)
            except TypeError:               # 老宿主的形参表不同
                result = chain.remove_torrents(hashs=list(hashes))
        except Exception as error:
            logger.error(f"AVHelper 删除下载器种子失败：{error}")
            return False, f"删除下载器种子失败：{str(error)[:120]}"
        if result:
            return True, f"已从下载器删除 {len(hashes)} 个种子（不动磁盘文件）"
        # 删返回 False 也可能是「这些 hash 本来就不在下载器里」（qB 对不存在的 id 就回 False）：
        # 复查一遍再下结论 —— 目标状态是"下载器里没有它"，已经达到就算成功。
        try:
            left, reliable = self._query_torrents(list(hashes))
        except Exception as error:
            left, reliable = {}, False
            logger.error(f"AVHelper 删除种子后复查失败：{error}")
        if reliable and not left:
            return True, "下载器里已经没有这些种子（无需删除）"
        return False, "下载器没有接受删除请求"

    def _drop_subs(self, keys: List[str], canon: str, actor: str) -> Dict[str, Any]:
        """删掉与这个番号相关的订阅（番号订阅按番号，演员订阅按台账里的演员）。"""
        try:
            subs = self.store.sub_list() or []
        except Exception as error:
            logger.error(f"AVHelper 取消时读订阅失败：{error}")
            return {"ok": False, "detail": f"读订阅失败：{str(error)[:120]}"}
        removed: List[str] = []
        for sub in subs:
            kind = str(sub.get("type") or "")
            name = str(sub.get("name") or "")
            hit = (kind == "number" and _same_number(name, keys, canon)) \
                or (kind == "actor" and actor and name == actor)
            if not hit:
                continue
            try:
                self.store.sub_del(int(sub.get("id") or 0))
                removed.append(f"{'番号' if kind == 'number' else '演员'}{name}")
            except Exception as error:
                logger.error(f"AVHelper 删除订阅失败（{name}）：{error}")
                return {"ok": False, "detail": f"删订阅失败：{str(error)[:120]}"}
        if not removed:
            return {"ok": True, "detail": "没有对应的订阅（跳过）"}
        if not actor:
            # 演员那半没得对：台账里没有演员字段时只能按番号删，说清楚免得看着像漏了
            return {"ok": True, "detail": "已删除订阅：" + "、".join(removed) + "（无演员信息，演员订阅未动）"}
        return {"ok": True, "detail": "已删除订阅：" + "、".join(removed)}

    def _percent(self, raw: float, downloader: str) -> float:
        """把下载器给的 `progress` 换算成百分比（0-100）。

        **同一个字段，宿主各下载器模块给的口径不一样**（2026-10-12 读宿主源码核对）：

        - qbittorrent：`progress=(torrent_data.get('progress') or 0) * 100` —— 已经是百分比；
        - transmission：直接透传 `percent_done` —— 还是 0-1 的小数。

        判据只能用读数本身：`> 1` 必然已是百分比，顺便把「这台下载器是百分比口径」记进
        `self._scales`；`<= 1` 时按记下的口径走，没见过的下载器沿用旧行为（当小数 ×100）。
        不这么认的话，qB 上真实的 0.5% 会被画成 50%，进度条一开始就乱跳。
        插件重启后这份记忆会丢，但任何一条超过 1% 的读数都会立刻把它补回来。
        """
        name = str(downloader or "")
        if raw > 1:
            self._scales[name] = True
            return min(100.0, max(0.0, raw))
        if self._scales.get(name):
            return min(100.0, max(0.0, raw))
        return min(100.0, max(0.0, raw * 100))

    def _merge_queue(self, queue: List[Dict[str, Any]], by_hash: Dict[str, Any],
                     thumbs: Dict[str, str],
                     missing: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """把补到的封面与下载器进度就地合并进队列。

        `queue` 传进来的是**当前**数据（由 `Store.kv_update` 持锁取出），只按 id/hash 改命中项，
        快照之外的条目一个都不动——被合并掉的那次丢记录就是这么来的。

        :param missing: 本轮**确认**下载器里已经没有的 hash 集合（小写）。`None` = 本轮没问、
            或者没问成，一个都不算缺失 —— 下载器连不上时绝不能把队列当成「全被删了」清空。
            命中缺失的条目累加 `miss` 轮数（查到就清零），够 `QUEUE_MISS_LIMIT` 由
            `_flush_gone` 收尾；用户手动在下载器里取消下载就是这么被发现的。
        """
        for entry in queue:
            tid = str(entry.get("id") or "")
            if tid and tid in thumbs and thumbs[tid] != entry.get("thumb"):
                entry["thumb"] = thumbs[tid]
            digest = str(entry.get("hash") or "").lower()
            torrent = by_hash.get(digest) if digest else None
            if not torrent:
                # 已经 `done` 的条目不算缺失：下完的种子被清理掉是正常的，它们由 `_flush_done`
                # 登记进台账后摘走，别在这里再记一笔「不见了」。
                if (digest and missing and digest in missing
                        and str(entry.get("state") or "") != "done"):
                    entry["miss"] = int(entry.get("miss") or 0) + 1
                continue
            entry["miss"] = 0
            name = str(getattr(torrent, "downloader", "") or entry.get("downloader") or "")
            try:
                raw = float(getattr(torrent, "progress", 0) or 0)
            except (TypeError, ValueError):
                raw = 0.0
            percent = self._percent(raw, name)
            entry["progress"] = int(round(percent))
            state = str(getattr(torrent, "state", "") or "").lower()
            reason = _failure_reason(torrent, percent)
            if reason:
                # 失败态优先：既不能算「下完了」，也不许被后面的轮次翻回来。台账那一笔交给
                # `_flush_failed()` 在本次 `kv_update` 之外写 —— 与 `_flush_done` / `_flush_gone`
                # 同一套分工：`_merge_queue` 只改快照（它跑在 `kv_update` 的锁里），
                # 「登记成功才打标记、失败留队列下轮重试」这条只能等锁放掉才做得了。
                if str(entry.get("state") or "") != "failed":
                    entry["failed_ledger"] = False      # 这一轮才判失败 → 等 `_flush_failed` 登记
                entry["state"] = "failed"
                entry["failed_reason"] = reason
                continue
            if str(entry.get("state") or "") == "failed":
                # 判过失败的条目只能被「下载器真的报完成」翻回来：进度到 100 才算
                # （`completed` + 进度不足 100 正是宿主吞掉 error/missingFiles/unknown 的样子）。
                if percent < QUEUE_DONE_RAW:
                    continue
                entry.pop("failed_reason", None)
                entry.pop("failed_ledger", None)
            # 状态是主判据；`upload`/`做种` 与进度数字都是给「宿主没把状态归一好」留的兜底。
            # 数字兜底仍然用**原始读数** `raw` 而不是换算后的 `percent`：`_percent()` 在
            # 「这台下载器还没有过 >1 的读数」时会按小数口径 ×100，于是 qB 上真实的 1%
            # （原生 1.0）会被算成 100% —— 拿它当完成判据就会把刚下 1% 的片子标成已下载。
            if (state == QUEUE_DONE_STATE or "upload" in state or "做种" in state
                    or raw >= QUEUE_DONE_RAW):
                entry["state"] = "done"
            elif state:
                entry["state"] = "down"
        return queue[:50]

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

        还有一类条目同样不该留在队列里：**下载器里已经没有它了**（用户手动取消了下载、
        或在下载器里删了任务）。合并只认「查到的 hash」，查不到就什么都不改，于是那条会
        永远停在最后一次读到的进度上，界面上挂着一条假的「下载中 0%」，刷新多少次都一样。
        `_merge_queue` 累计「连续查不到」的轮数，够 `QUEUE_MISS_LIMIT` 就交给 `_flush_gone`。
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
        missing: Optional[Set[str]] = None
        if fresh:
            by_hash, ok = self._query_torrents(active + done)
            if ok:
                # 问到的那些是「还在」，其余的才算「没了」——问失败时 `missing` 保持 None
                missing = {h.lower() for h in (active + done)} - set(by_hash)
            if active:
                self._queue_at["active"] = time.time()
            if done:
                self._queue_at["done"] = time.time()
        else:
            self._kick_refresh(active, done)

        if by_hash or thumbs or missing:
            queue = self.store.kv_update(
                QUEUE_KEY,
                lambda cur: self._merge_queue(cur or [], by_hash, thumbs, missing))
        # 收尾顺序：完成 → 失败 → 消失。失败排在「消失」前面，是因为它的证据更硬
        # （种子自己报的失败态），不能被「查不到它了 + Emby 库里恰好有这个番号」改写成已完成。
        return self._flush_gone(self._flush_failed(self._flush_done(queue)))

    def _flush_failed(self, queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把这一轮新判为失败的条目登记进台账（`state='failed'` + `failed_reason`），返回原队列。

        **不摘队列**（与 `_flush_done` 的差别）：失败要留在「下载中」列表里让用户看见 ——
        一条挂着假进度的记录比一条写着"失败：种子状态 error"的记录糟得多。它也不会卡死：
        ① 下载器里真做完（进度到 100）时 `_merge_queue` 把它翻回 `done`，交给 `_flush_done`；
        ② 用户在下载器里把种子删了 → 连续 `QUEUE_MISS_LIMIT` 轮查不到 → `_flush_gone` 摘掉；
        ③ 用户点「不要了」→ `cancel_all()` 直接清三处。

        台账只在**首次判失败**那一轮写一次（标记 `failed_ledger`），不是每 12 秒重写一遍。
        写台账放在这里、不写在 `_merge_queue` 里：那个函数跑在 `Store.kv_update` 的锁与事务里
        （v4 的 `Store._lock` 是 `RLock`，嵌套写不会锁死 —— 这一点 2026-10-14 用探针实测过；
        但那样会把第二个事务塞进同一把锁、同一个线程连接里），而且「这一笔登记成功了没有」
        要写回队列快照才能只登记一次，那条写只能等 `kv_update` 放掉锁再做。
        """
        rows = [e for e in (queue or [])
                if isinstance(e, dict) and str(e.get("state") or "") == "failed"
                and not e.get("failed_ledger")]
        if not rows:
            return queue
        stamped = set()
        for entry in rows:
            number = str(entry.get("number") or "")
            if not number:              # 没番号归一不出 key：留队列里下轮重试，别悄悄丢掉
                continue
            reason = str(entry.get("failed_reason") or "下载器报种子失败")
            if self._ledger_upsert(
                number,
                title=str(entry.get("title") or ""),
                thumb=self._ledger_thumb(entry.get("thumb")),
                size=_size_bytes(entry.get("size")),
                hash=str(entry.get("hash") or ""),
                path=str(entry.get("savePath") or ""),
                downloader=str(entry.get("downloader") or ""),
                state="failed",
                failed_reason=reason,
            ):
                stamped.add(_queue_fingerprint(entry))
                logger.info(f"AVHelper 下载失败登记：{number} —— {reason}")
                self.notifier.info("下载失败", f"{number}：{reason}")
        if not stamped:
            return queue

        def mark(cur: Any) -> List[Dict[str, Any]]:
            """就地打上「已登记」标记；其余条目与顺序原样保留（期间新插入的不能丢）。"""
            return [dict(item, failed_ledger=True)
                    if isinstance(item, dict) and _queue_fingerprint(item) in stamped
                    else item
                    for item in (cur or [])]

        try:
            return self.store.kv_update(QUEUE_KEY, mark)
        except Exception as error:
            logger.error(f"AVHelper 标记失败条目已登记失败：{error}")
            return queue

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

    def _flush_gone(self, queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """把「下载器里已经没有」的条目从队列摘掉，返回摘完的队列。

        谁会走到这里见 `_merge_queue`：连续 `QUEUE_MISS_LIMIT` 轮问下载器都查不到这个 hash
        （用户手动在下载器里取消下载、或在下载器里删了任务）。摘除沿用 `_flush_done` 那套
        指纹口径，期间新插入的条目不受影响。

        台账那一侧**只做加法，绝不抹记录**：

        - Emby 库里已经有这个番号 → 那是「下完了才把种子清理掉」，按已完成补记
          （`_flush_done` 的口径），「已下载」徽标与该有的提示照旧；
        - 不在库里 → 这次没下成，台账里那条（提交下载时写的 `state='downloading'`）
          **原样留着**：它不算「已下载」、也不触发重复下载提示，只是历史页里多一行
          「不在库（可能已删除）」的记录。反过来把记录撤掉（墓碑）看着更干净，但 Emby
          索引在媒体库不通时只会回空字典 —— 那时「不在库」并不等于「没下成」，撤掉一条
          真下好的记录比留一行噪音糟得多。

        一句话：**队列按事实说话（没了就摘），台账只往上补、不往下删。**
        """
        gone = [e for e in (queue or []) if isinstance(e, dict)
                and str(e.get("state") or "") != "done"
                and int(e.get("miss") or 0) >= QUEUE_MISS_LIMIT]
        if not gone:
            return queue

        try:
            library = self.plugin.emby().index() or {}
        except Exception as error:      # `index()` 自己不会抛，这里兜住配置异常之类
            logger.error(f"AVHelper 核对 Emby 索引失败（这次只摘队列）：{error}")
            library = {}

        for entry in gone:
            number = str(entry.get("number") or "")
            digest = str(entry.get("hash") or "")
            key = emby.norm_key(number) if number else ""
            failed = str(entry.get("state") or "") == "failed"
            # 判过失败的条目**不许**走「Emby 库里已经有这个番号 → 按已完成补记」那条路：
            # 库里那个番号可能是上一次下的另一份，而失败是这一颗种子自己报出来的硬证据。
            # 证据强弱：种子状态 > 「下载器里查不到它了」+「库里有同号」。
            if not key or key not in library or failed:
                logger.info(f"AVHelper 下载已不在下载器，从队列摘掉：{number or digest}"
                            f"{'（该条目判过下载失败）' if failed else ''}")
                self.notifier.info(
                    "下载已从下载器移除",
                    f"{number or digest} 在下载器里已经找不到了，已从「下载中」移除"
                    + ("（这一条判过下载失败，台账里那条保持失败，不会被记成已下载）" if failed else ""),
                )
                continue
            if self._ledger_upsert(
                number,
                title=str(entry.get("title") or ""),
                thumb=self._ledger_thumb(entry.get("thumb")),
                size=_size_bytes(entry.get("size")),
                hash=digest,
                path=str(entry.get("savePath") or ""),
                downloader=str(entry.get("downloader") or ""),
                state="downloaded",
                created_at=str(entry.get("added") or ""),   # 只在首次写入时生效
            ):
                logger.info(f"AVHelper 种子已不在下载器但 Emby 已有：{number} 按已完成登记")
                self.notifier.info("下载已完成",
                                   f"{number} 的种子已不在下载器里，Emby 库里已有，"
                                   "按已完成记入「下载历史」")

        removed = {_queue_fingerprint(entry) for entry in gone}

        def keep(cur: Any) -> List[Dict[str, Any]]:
            """就地摘掉这些条目；其余条目与顺序原样保留（期间新插入的不能丢）。"""
            return [item for item in (cur or [])
                    if not (isinstance(item, dict) and _queue_fingerprint(item) in removed)]

        try:
            return self.store.kv_update(QUEUE_KEY, keep)
        except Exception as error:
            logger.error(f"AVHelper 从队列移除已在下载器消失的条目失败：{error}")
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

    def _list_torrents(self, hashes: List[str]) -> List[Any]:
        """按 hash 点名问宿主下载器（`include_all_tags=True`，老宿主不认这个参数就退回）。

        为什么要那个参数：默认只查带宿主内置标签（`TORRENT_TAG`，默认 `MoviePilot`）的任务，
        种子一旦被别的工具摘掉标签，这里就「查不到」—— 而查不到会被当成「已从下载器移除」
        （见 `_merge_queue` / `_flush_gone`）。按 hash 点名本来就不需要标签过滤。
        """
        chain = self.plugin.chain
        try:
            return chain.list_torrents(hashs=hashes, include_all_tags=True)
        except TypeError:                   # 宿主版本没有这个形参
            return chain.list_torrents(hashs=hashes)

    def _query_torrents(self, hashes: List[str]) -> Tuple[Dict[str, Any], bool]:
        """问一次下载器，返回 `(hash → 种子对象, 这一轮问成了没有)`。

        第二个返回值就是「本轮结果可不可信」：只有可信时，调用方才会把「查不到的 hash」
        当成「下载器里真的没有」（`missing`）。异常、没有下载器可问、宿主不认参数等等一律
        按不可信处理 —— 宁可这一轮什么都不判，也不能凭一次失败把下载中的记录全摘掉。
        失败只记日志（不抛、不影响队列渲染）。
        """
        if not hashes:
            return {}, False
        try:
            torrents = self._list_torrents(list(hashes)) or []
        except Exception as error:
            logger.error(f"AVHelper 刷新下载进度失败：{error}")
            return {}, False
        by_hash: Dict[str, Any] = {}
        for item in torrents:
            h = str(getattr(item, "hash", "") or getattr(item, "hashString", "") or "").lower()
            if h:
                by_hash[h] = item
        return by_hash, True

    def downloader_state(self) -> Dict[str, Any]:
        """下载器是不是在线（给 `/downloads` 顶层的 `downloader_offline` 用）。

        **返回形状定死了，S8 按这个接**（v4.1 §9.2 第 3 条）::

            {'online': bool, 'error': str, 'checked_at': str}
            # online=True  → error 是空串
            # online=False → error 是给人看的一句原因（界面顶部告警条直接用）
            # checked_at   → 'YYYY-MM-DD HH:MM:SS'（本地时间，与库里其它时间戳同格式）
            #                = **这一次真的去问下载器**的时刻；不是快照时间

        每次调用都真问一次下载器（代价同 `queue(fresh=True)`），所以别挂到 `/bootstrap`
        那条 15 秒轮询上；`/downloads` 这种用户主动打开的读接口正合适。

        失联时把进度快照的两个时间戳清零（= **上一轮快照作废**）：下一轮 `queue()` 会重新问
        下载器，绝不沿用上一轮读到的进度 —— 下载器都连不上了，页面上还挂着「下载中 42%」
        是假话，而且真把种子删了也看不出来。
        """
        checked_at = time.strftime("%Y-%m-%d %H:%M:%S")
        online, why = self._probe_downloader()
        if online:
            self._downloader_error = ""
            return {"online": True, "error": "", "checked_at": checked_at}
        self._queue_at["active"] = 0.0
        self._queue_at["done"] = 0.0
        self._downloader_error = why or "下载器连接失败"
        logger.error(f"AVHelper 下载器失联：{self._downloader_error}")
        return {"online": False, "error": self._downloader_error, "checked_at": checked_at}

    def _probe_downloader(self) -> Tuple[bool, str]:
        """真问一次下载器（空 hash 列表 = 「把种子列表给我看看」），返回 `(在线?, 原因)`。

        判据只看「宿主回没回一个列表」：

        - **抛异常**（超时、认证失败、下载器没起来）→ 离线；
        - **回 `None`** → 宿主没找到可用的下载器模块（或模块没处理这次调用）→ 同样算离线；
        - **回空列表** → 在线。「下载器活着但一个种子都没有」是正常状态，不能当离线。

        ⚠️ 这是**问全部下载器**：装了第二台但没配好时，它也会把整体判成离线。本机只有
        qBittorrent（`AGENTS.md` §3），暂不为此加按下载器探测的分支。
        """
        chain = getattr(self.plugin, "chain", None)
        if chain is None:
            return False, "宿主没有可用的下载链（下载器未配置）"
        try:
            torrents = self._list_torrents([])
        except Exception as error:
            return False, f"下载器连接失败：{str(error)[:160]}"
        if torrents is None:
            return False, "下载器没有返回种子列表（未配置下载器或下载器模块不可用）"
        return True, ""

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
                by_hash, ok = self._query_torrents(hashes)
                if need_active:
                    self._queue_at["active"] = time.time()
                if need_done:
                    self._queue_at["done"] = time.time()
                # 同步那条路（`queue(fresh=True)`）也是同样的算法，两边不能各算一套
                missing = ({h.lower() for h in hashes} - set(by_hash)) if ok else None
                merged = None
                if by_hash or missing:
                    # 只并进度，不动封面：封面那条线上一次请求已经写过了
                    merged = self.store.kv_update(
                        QUEUE_KEY,
                        lambda cur: self._merge_queue(cur or [], by_hash, {}, missing))
                if merged:
                    # 失败态的台账登记这一路也要做（上面那次 kv_update 已经返回、锁已放掉）
                    self._flush_failed(merged)
            except Exception as error:         # 后台线程里的异常绝不能漏出去
                logger.error(f"AVHelper 后台刷新下载进度失败：{error}")
            finally:
                with self._queue_lock:
                    self._queue_busy = False

        threading.Thread(target=worker, name="avhelper-queue", daemon=True).start()

    # ---------- 订阅检查 ----------

    def _match_keys(self, number: Any) -> List[str]:
        """一个番号在「归一化键」上的**全部**写法（规范号在前，旧口径在后）。

        为什么要两种：Emby 索引与 `downloads` / `known` 的主键都是**旧口径**
        `emby.norm_key()`（保留后缀：`IPZZ-912-UC` → `IPZZ912UC`），而 v4.1 §9.2 要求用
        规范号（`IPZZ912`）去查三处。只查规范号会漏掉「库里存的是带后缀那条键」的情况
        （线上库快照里就有 `IPZZ58624K` / `MIRD277C` 这种残留，见契约 §0.2）。
        """
        keys: List[str] = []
        for key in (_canon(number), emby.norm_key(number)):
            if key and key not in keys:
                keys.append(key)
        return keys

    def duplicate_reason(self, number: str, source: str = "sub") -> str:
        """下单前查重：`''` = 放行；非空 = 拦下来的原因（中文，直接进日志/通知）。

        三处任一命中就不再下单（v4.1 §9.2 第 2 条），并把命中原因定位到具体那一处：

        1. **Emby 库**：已经入库的片子不必再下（`EmbyLibrary.index()`，内存索引，不发请求）；
        2. **下载台账**：`downloading`（正在下）或 `downloaded`（下过）都算占住 ——
           后者正是用户报的「订阅重复下单」；`failed` **不算**（失败了本来就该允许重下）；
        3. **待确认任务**：任务页还挂着 `state='await'` 的同号任务，再下一单就是两条一样的卡。

        `source` 是这台机器上**「用户手动洗版」的唯一标识**：任务的 `source` 列由调用方传入
        （`__init__.py` 的两条手动入口 —— `api_task_search` 与 `api_task_acquire`/`acquire()` ——
        落的都是 `'manual'`，订阅那条路落的都是 `'sub'`，见 `build_task()` 的 `:param source:`）。
        **非 `'sub'` 的来源一律放行**：手动点「下载该影片」洗版是用户的明确意图，不许拦。
        判据只认这一个字段，没有另外发明参数。
        """
        if str(source or "") != "sub":
            return ""
        keys = self._match_keys(number)
        canon = _canon(number)
        if not keys:
            return ""
        try:
            library = self.plugin.emby().index() or {}
        except Exception as error:      # 索引不通不能把下单也带崩，宁可漏判这一处
            logger.error(f"AVHelper 查重读 Emby 索引失败：{error}")
            library = {}
        for key in (library or {}):
            if _same_number(key, keys, canon):
                return f"番号已在 Emby 库中（{key}）"
        try:
            ledger = self.store.download_map() or {}
        except Exception as error:
            logger.error(f"AVHelper 查重读下载台账失败：{error}")
            ledger = {}
        for key, row in (ledger or {}).items():
            if not _same_number(key, keys, canon):
                continue
            if isinstance(row, dict) and str(row.get("state") or "") in DOWNLOAD_TAKEN_STATES:
                return f"下载台账里已有这个番号（{row.get('state')}）"
        try:
            tasks = self.store.task_list() or []
        except Exception as error:
            logger.error(f"AVHelper 查重读任务列表失败：{error}")
            tasks = []
        for task in tasks:
            if not isinstance(task, dict) or str(task.get("state") or "") != "await":
                continue
            if _same_number(task.get("number"), keys, canon):
                return "任务页已有这个番号的待确认任务"
        return ""

    def check(self, name: Optional[str] = None) -> Dict[str, Any]:
        """手动或有计划地检查订阅；受 §8.2 限流约束。"""
        # 定时重刮队列的挂点（v4.1 §9.2-5 / 契约 §3.2）：本方法就是本插件的**定时任务入口**
        # （`__init__.py:job_subcheck` 挂着 09:30/14:30/21:30 的 cron），所以挂在这里。
        # 放在限流判断之前：它只读本地 meta 表，不碰站点，不受订阅限流约束。
        self._scrape_tick()
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
        if str(task.get("state") or "") == "skipped":
            # 查重命中，这一单根本没建（见 `build_task()`）：说清为什么没下，别让用户以为
            # 订阅检查白跑了。`known` 已经补写，下一轮作品史差集不会再把它当新片。
            return [self.notifier.info(
                "订阅命中但已跳过",
                f"{task.get('number') or ''}：{task.get('duplicate') or '已存在'}，未重复下单")]
        best = next((c for c in (task.get("cands") or []) if c.get("pass")), None)
        if rule.get("trigger") == "auto" and best:
            result = self.download(task["id"])
            if result.get("ok"):
                return [result["notice"]] if result.get("notice") else []
            return [self.notifier.info("自动下载失败", str(result.get("message") or ""))]
        return [self.notifier.candidate_ready(task["number"], len(task.get("cands") or []))]

    # ---------- 定时重刮（Tier 1 / Tier 2 队列挂点） ----------

    def _meta_due(self, tier: int, limit: int = SCRAPE_TIER_LIMIT) -> List[Dict[str, Any]]:
        """`store.meta_due()` 的防御包装：取不到就回空列表，绝不让定时任务炸掉。

        S1 的 `meta_due()` 已经在主干上（契约 §3.2），但本插件的其它文件也在并行改，
        所以这里仍用 `getattr` 探一下：方法不在时记一条 info，而不是抛 AttributeError
        把整个订阅检查带停摆。
        """
        fn = getattr(self.store, "meta_due", None)
        if not callable(fn):
            logger.info("AVHelper 重刮队列：store.meta_due() 尚未落地，本轮跳过")
            return []
        try:
            return list(fn(now=time.strftime("%Y-%m-%d %H:%M:%S"), tier=tier, limit=limit) or [])
        except Exception as error:
            logger.error(f"AVHelper 取重刮待办失败（tier={tier}）：{error}")
            return []

    def _scrape_tick(self) -> Dict[str, Any]:
        """跑一轮 Tier 1 / Tier 2 定时重刮（S8 接线，契约 §3.6 / v4.1 §5.3）。

        见 v4.1 §9.2 与契约 §3.2 的 `meta_due(now, tier, limit)`：

        - tier=1：`next_retry_at` 到点的条目（上次失败/缺简介，按 +6h/24h/72h/7d/14d 退避），
          一批最多 **5** 条；
        - tier=2：全表按 `last_scraped_at` 最久的 **3** 条（治「新片饥饿」的滚动档）。

        配置从 `plugin.scrape_conf()` 读（11 项存在 kv 的 `global_rule` 里，不是宿主配置）：
        `scrapeMode == 'off'` 直接跳过，`autoScrapeTier1` / `autoScrapeTier2` 各自管一档。

        执行交 S7 的 `scraper.scrape_batch()`（依赖包走 `plugin.scrape_deps()`）——
        **逐条 try/except**，失败只往 `scrape_log` 记一条：本方法挂在 `check()` 的第一行，
        绝不能把订阅检查主流程带停摆（`scraper.py` 缺位、站点超时、Emby 抽风都算）。
        返回形状（`{'tier1','tier2','scraper','error'}`）与只记日志那版保持不变。
        """
        out: Dict[str, Any] = {"tier1": 0, "tier2": 0, "scraper": False, "error": ""}
        plugin = self.plugin
        conf: Dict[str, Any] = {}
        getter = getattr(plugin, "scrape_conf", None)
        if callable(getter):
            try:
                conf = dict(getter() or {})
            except Exception as error:
                logger.error(f"AVHelper 读刮削配置失败（按默认值跑）：{error}")
                conf = {}
        if str(conf.get("scrapeMode") or "fill").strip().lower() == "off":
            logger.info("AVHelper 重刮队列：scrapeMode=off，本轮跳过")
            return out
        due1 = self._meta_due(1, limit=5) if bool(conf.get("autoScrapeTier1", True)) else []
        due2 = self._meta_due(2, limit=3) if bool(conf.get("autoScrapeTier2", True)) else []
        out["tier1"], out["tier2"] = len(due1), len(due2)
        keys: List[str] = []
        for row in list(due1) + list(due2):
            key = str((row or {}).get("key") or "").strip()
            if key and key not in keys:
                keys.append(key)
        if not keys:
            return out
        loader = getattr(plugin, "scrape_module", None)
        scraper = None
        if callable(loader):
            try:
                scraper = loader()
            except Exception as error:      # 加载失败也算"没就绪"，不许往外抛
                logger.error(f"AVHelper 加载刮削模块失败：{error}")
        if scraper is None or not callable(getattr(scraper, "scrape_batch", None)):
            logger.info(f"AVHelper 重刮队列：待办 Tier1 {len(due1)} 条 / Tier2 {len(due2)} 条，"
                        f"scraper.py 尚未就绪，本轮只取不刮")
            out["error"] = "scraper 未落地"
            return out
        out["scraper"] = True
        deps: Dict[str, Any] = {}
        deps_loader = getattr(plugin, "scrape_deps", None)
        if callable(deps_loader):
            try:
                deps = dict(deps_loader() or {})
            except Exception as error:
                logger.error(f"AVHelper 组装刮削依赖失败（本轮按空依赖跑）：{error}")
                deps = {}
        done, failed = 0, 0
        for key in keys:
            try:
                scraper.scrape_batch([key], **deps)
                done += 1
            except Exception as error:      # 单条失败只记账，订阅检查还得往下跑
                failed += 1
                logger.error(f"AVHelper 定时重刮失败（{key}）：{error}")
                try:
                    self.store.scrape_log_add("scrape_tick", "error", key, 0, str(error)[:200])
                except Exception:
                    pass
        if failed:
            out["error"] = f"{failed} 条失败"
        logger.info(f"AVHelper 定时重刮：Tier1 {len(due1)} 条 / Tier2 {len(due2)} 条，"
                    f"成功 {done} 条，失败 {failed} 条")
        return out
