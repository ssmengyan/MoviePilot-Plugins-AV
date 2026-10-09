"""候选种子打分：逐项可解释，数值与交互演示原型完全一致（执行方案 §6.5）。

打分只依赖种子标题/站点/做种数等已有字段，不请求网络；`cnsub` 与 `uncensored` 由标题正则判定，
正则先在真实站点种名上验证过（中字/中文/chs/简体/gb、无码/破解/uncensored/leak/流出）。
"""

import re
from typing import Any, Dict, List, Optional

# 标题特征正则（执行方案 §6.5 指定的特征，并按方案要求"先在真实种名上调好再上线"）
# 注意：chs/gb 必须加词边界——裸 `gb` 会命中 `GBR`（英国区码），把普通种子误判成有中字。
_CNSUB_RE = re.compile(r"中字|中文|简体|\bchs\b|\bgb\b", re.IGNORECASE)
_UNCENSORED_RE = re.compile(r"无码|破解|uncensored|leak|流出", re.IGNORECASE)
_RES_2160_RE = re.compile(r"2160p|4k|uhd", re.IGNORECASE)
_RES_1080_RE = re.compile(r"1080p|fhd", re.IGNORECASE)
_RES_720_RE = re.compile(r"720p", re.IGNORECASE)
_H265_RE = re.compile(r"h\.?265|x265|hevc", re.IGNORECASE)
_H264_RE = re.compile(r"h\.?264|x264|avc", re.IGNORECASE)
_GROUP_RE = re.compile(r"-\[?([A-Za-z0-9@._-]{2,20})\]?\s*$")


def detect_resolution(title: str) -> str:
    """从种名判定分辨率，返回 2160p/1080p/720p 或空串。"""
    text = title or ""
    if _RES_2160_RE.search(text):
        return "2160p"
    if _RES_1080_RE.search(text):
        return "1080p"
    if _RES_720_RE.search(text):
        return "720p"
    return ""


def detect_cnsub(title: str) -> bool:
    """从种名判定是否带中文字幕。"""
    return bool(_CNSUB_RE.search(title or ""))


def detect_uncensored(title: str) -> bool:
    """从种名判定是否无码/破解版。"""
    return bool(_UNCENSORED_RE.search(title or ""))


def detect_codec(title: str) -> str:
    """从种名判定编码，未知时返回空串。"""
    text = title or ""
    if _H265_RE.search(text):
        return "H265"
    if _H264_RE.search(text):
        return "H264"
    return ""


def detect_group(title: str) -> str:
    """从种名尾部解析发布组，解析不到返回空串。"""
    match = _GROUP_RE.search((title or "").strip())
    return match.group(1) if match else ""


def human_size(size_bytes: Any) -> str:
    """字节数转人类可读大小。"""
    try:
        value = float(size_bytes or 0)
    except (TypeError, ValueError):
        return "—"
    if value <= 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit in ("GB", "TB") else f"{value:.0f} {unit}"
        value /= 1024
    return "—"


def candidate_from_torrent(torrent: Any, pref_sites: Optional[List[str]] = None) -> Dict[str, Any]:
    """把宿主 TorrentInfo 转成本插件统一的候选结构。"""
    title = str(getattr(torrent, "title", "") or "")
    site = str(getattr(torrent, "site_name", "") or "")
    res = detect_resolution(title)
    codec = detect_codec(title) or "—"
    uncensored = detect_uncensored(title)
    try:
        seeders = int(getattr(torrent, "seeders", 0) or 0)
    except (TypeError, ValueError):
        seeders = 0
    try:
        dvf = getattr(torrent, "downloadvolumefactor", None)
        free = dvf is not None and float(dvf) == 0
    except (TypeError, ValueError):
        free = False
    spec = f"{res or '未知'} / {codec}" + (" / 无码" if uncensored else "")
    return {
        "src": "PT",
        "site": site,
        "spec": spec,
        "cnsub": detect_cnsub(title),
        "uncensored": uncensored,
        "size": human_size(getattr(torrent, "size", 0)),
        "seeders": seeders,
        "free": free,
        "res": res,
        "pref": bool(pref_sites) and site in (pref_sites or []),
        "group": detect_group(title) or (str(getattr(torrent, "site_name", "") or "") + " 发布"),
        "title": title,
        "score": 0,
        "pass": True,
        "breakdown": "",
        "picked": False,
    }


def candidate_from_magnet(magnet: Dict[str, Any], pref_sites: Optional[List[str]] = None) -> Dict[str, Any]:
    """把 javdb 磁力记录转成 BT 兜底候选。

    注意：javdb 磁力记录的 `size` 单位是 **MB**（实测 7895 ≈ 7.9GB），不是字节，
    直接按字节格式化会得到荒唐的“8 KB”。
    """
    title = str(magnet.get("name") or "")
    uncensored = detect_uncensored(title) or bool(magnet.get("uncensored"))
    res = detect_resolution(title) or "1080p"
    spec = f"{res} / {detect_codec(title) or 'H264'}" + (" / 无码" if uncensored else "")
    try:
        size_mb = float(magnet.get("size") or 0)
    except (TypeError, ValueError):
        size_mb = 0.0
    return {
        "src": "BT",
        "site": "BT 公网",
        "spec": spec,
        "cnsub": bool(magnet.get("cnsub")) or detect_cnsub(title),
        "uncensored": uncensored,
        "size": human_size(size_mb * 1024 * 1024) if size_mb else "—",
        "seeders": int(magnet.get("seeders") or 0),
        "free": True,
        "res": res,
        "pref": False,
        "group": "BT 匿名发布",
        "title": title,
        "hash": str(magnet.get("hash") or ""),
        "score": 0,
        "pass": True,
        "breakdown": "",
        "picked": False,
    }


def score_candidate(cand: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
    """按订阅规则给单个候选打 0-100 分并生成明细（数值取演示原型口径）。"""
    score = 0
    passed = True
    why: List[str] = []

    res = cand.get("res") or ""
    if res == "1080p":
        score += 30
        why.append("1080P +30")
    elif res == "2160p":
        if rule.get("allow4k"):
            score += 16
            why.append("4K 择优 +16")
        else:
            why.append("4K 未开择优 +0")
    else:
        score += 5
        why.append(f"{res or '未知'} +5")

    if cand.get("cnsub"):
        score += 32
        why.append("中字 +32")
    elif rule.get("mustCnsub"):
        passed = False
        why.append("缺中字 ✗")

    if cand.get("uncensored") and rule.get("preferUncensored"):
        score += 14
        why.append("破解 +14")

    if cand.get("src") == "PT":
        score += 8
        why.append("PT 源 +8")
    else:
        score -= 6
        why.append("BT 兜底 -6")

    if cand.get("pref"):
        score += 10
        why.append("优先站 +10")

    seeders = int(cand.get("seeders") or 0)
    min_seeders = int(rule.get("minSeeders") or 0)
    if cand.get("src") == "BT" and seeders <= 0:
        # BT 磁力不提供做种数，按“未知”处理，不能因此淘汰（否则兜底永远不成立）
        why.append("做种未知（BT 磁力）")
    elif seeders >= 50:
        score += 10
        why.append(f"做种{seeders} +10")
    elif seeders >= 10:
        score += 6
        why.append(f"做种{seeders} +6")
    elif seeders >= min_seeders:
        score += 2
        why.append(f"做种{seeders} +2")
    else:
        passed = False
        why.append(f"做种{seeders} ✗")

    if cand.get("free"):
        score += 3
        why.append("免费 +3")

    cand["score"] = max(0, min(100, score))
    cand["pass"] = passed
    cand["breakdown"] = " · ".join(why)
    return cand


def rank_candidates(cands: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """给全部候选打分并排序：通过优先，其次按分数降序；首个通过的标记为推荐。"""
    for cand in cands:
        score_candidate(cand, rule)
    cands.sort(key=lambda c: (0 if c.get("pass") else 1, -int(c.get("score") or 0)))
    for cand in cands:
        cand["picked"] = False
    for cand in cands:
        if cand.get("pass"):
            cand["picked"] = True
            break
    return cands


def explain(task_cands: List[Dict[str, Any]], rule: Dict[str, Any]) -> str:
    """生成“为什么选它”的一句话说明（对应演示页脚文案）。"""
    best = next((c for c in task_cands if c.get("pass")), None)
    res_label = {"1080p": "1080P 优先", "2160p": "4K 优先", "only4k": "仅 4K"}.get(
        str(rule.get("res") or "1080p"), "1080P 优先"
    )
    rule_text = f"规则「{res_label}"
    if rule.get("mustCnsub"):
        rule_text += " / 必须中字"
    if rule.get("preferUncensored"):
        rule_text += " / 破解优先"
    rule_text += f" / 做种≥{int(rule.get('minSeeders') or 0)}」逐项打分；"
    if not best:
        return rule_text + "没有候选满足规则 → 不自动下载，等你自己判断"
    return (
        f"{rule_text}最高分 {best.get('src')} {best.get('site')} {best.get('spec')}。"
        f"明细：{best.get('breakdown')}"
    )
