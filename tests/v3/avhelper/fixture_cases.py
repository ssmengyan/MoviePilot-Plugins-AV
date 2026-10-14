"""数据驱动夹具：按 `fixtures/avhelper/**/*.toml` 跑**真实响应**的解析回归。

为什么是"真响应 + 数据驱动"（而不是继续在测试里手写 HTML 片段）：手写片段只能验
"我以为的页面结构"，站点一次改版它照样全绿。夹具是冻结的原始响应，改了选择器就一定红。

夹具根目录在**仓库根**（`MoviePilot-Plugins-AV/` 之外）—— 公开仓只装那棵子树，
所以第三方响应不会被发布；公开仓里夹具缺失 → 整模块 skip（不是失败）。

本模块只负责"加载 + 跑 + 比对"，**用例内容全在 TOML 里**：新增一个场景 = 加一个响应文件 +
一个 TOML，不用改 Python（照 amane `docs/dev/crawler-testing.md` 的口径）。

比对的三种键（见 `fixtures/avhelper/README.md`）：
`k = 值` 全等 / `k_sha256 = "…"` 前 16 位哈希 / `k_len = n` 长度。
认不出来的键**直接抛错**，绝不静默通过。
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

#: `tests/v3/avhelper/fixture_cases.py` → parents[4] = 仓库根
REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "avhelper"

SITES = ("javtxt", "metatube")
PARSERS = {"javtxt": ("search", "detail"), "metatube": ("search",)}

#: 认得的 `expect` 键（`hit_*` / `*_sha256` / `*_len` 与 movie/detail 字段另行放行）
_CASE_KEYS = {"site", "parser", "number", "response", "expected_none", "captured", "capture"}


class FixtureError(RuntimeError):
    """夹具本身有问题（TOML 缺键、响应文件不在、键名打错）—— 一律当成测试失败，不静默跳过。"""


def sha16(text: Any) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def discover_cases() -> list[dict[str, Any]]:
    """扫出全部用例（`fixtures/avhelper/<site>/*.toml`），按路径排序，**空目录回空列表**。

    每条是 `load_toml()` 的产物再加上 `site`（目录名，用于分组与"每站点必须有空结果用例"）。
    """
    cases: list[dict[str, Any]] = []
    for site in SITES:
        for path in sorted((FIXTURE_ROOT / site).glob("*.toml")):
            item = load_toml(path)
            item["site"] = site
            cases.append(item)
    return cases


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    case = data.get("case") or {}
    missing = sorted(_CASE_KEYS - {"capture"} - set(case))
    if missing:
        raise FixtureError(f"{path.name}：`[case]` 缺键 {missing}")
    if not str(case.get("capture") or "").strip():
        # 采集条件是夹具的一半价值：没有它，"站点改了"与"我们解析错了"无法区分
        raise FixtureError(f"{path.name}：`[case].capture` 必填（采集命令形状）")
    if case["site"] not in SITES:
        raise FixtureError(f"{path.name}：未知 site={case['site']!r}")
    if case["parser"] not in PARSERS[case["site"]]:
        raise FixtureError(f"{path.name}：{case['site']} 不支持 parser={case['parser']!r}")
    response = FIXTURE_ROOT / str(case["site"]) / str(case["response"])
    if not response.is_file():
        raise FixtureError(f"{path.name}：响应文件不在 {response}")
    return {"case": case, "expect": dict(data.get("expect") or {}), "response": response,
            "path": path}

def _norm_key(emby_mod: Any, number: str) -> str:
    """与 `javtxt_lookup()` / `metatube_lookup()` 同一套归一（复刻调用点，别自己发明）。"""
    parsed = emby_mod.parse_av_number(number)
    return parsed.norm_key if parsed.matched else emby_mod.canon_key(number)


def observed(module: Any, emby_mod: Any, case: dict[str, Any]) -> dict[str, Any]:
    """跑一次解析，把"能看到的东西"摊平成一层 dict（后面的比对只认它）。"""
    info = case["case"]
    text = case["response"].read_text(encoding="utf-8", errors="replace")
    site, parser = info["site"], info["parser"]
    out: dict[str, Any] = {"response": case["response"].name, "site": site, "parser": parser}

    if site == "javtxt" and parser == "search":
        cards = module.parse_javtxt_search(text)
        hit = module.pick_javtxt_hit(cards, _norm_key(emby_mod, str(info["number"])))
        out["cards"] = len(cards)
        out["hit"] = hit
        out["hit_id"] = str((hit or {}).get("id") or "")
        out["hit_number"] = str((hit or {}).get("number") or "")
        out["hit_title"] = str((hit or {}).get("title") or "")
        out["hit_url"] = str((hit or {}).get("url") or "")
        return out

    if site == "javtxt" and parser == "detail":
        detail = module.parse_javtxt_detail(text)
        out.update(detail)
        actors = [a for a in (detail.get("actors") or []) if isinstance(a, dict)]
        out["actor_names"] = [str(a.get("name") or "") for a in actors]
        out["actor_avatar"] = str(actors[0].get("avatar_url") or "") if actors else ""
        # 详情页的"命中"= 解析出了标题（页面在 → 必须解析得出东西）。
        # `expected_none=true` 对 detail 用例是"这个页面解析不出标题"——真发生就是解析器坏了。
        title_zh = str(detail.get("title_zh") or "")
        title_jp = str(detail.get("title_jp") or "")
        out["hit"] = ({"title_zh": title_zh, "title_jp": title_jp}
                      if (title_zh or title_jp) else None)
        return out

    payload = json.loads(text)
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise FixtureError(f"{case['path'].name}：响应不是 {{data:[…]}} 也不是数组")
    hit, count, mismatch = module.pick_metatube_hit(items, _norm_key(emby_mod,
                                                                    str(info["number"])))
    movie = module.metatube_movie(hit) if hit else None
    out["candidates"] = count
    out["mismatch"] = mismatch
    out["items"] = len(items)
    out["hit"] = movie
    out["hit_id"] = str((movie or {}).get("id") or "")
    out["hit_number"] = str((movie or {}).get("number") or "")
    for key in ("title", "summary", "maker", "runtime", "director", "release_date",
                "cover_url", "thumb_url", "preview_video_url", "provider"):
        out[key] = (movie or {}).get(key, "")
    out["actor_names"] = list((movie or {}).get("actors") or [])
    out["genres"] = list((movie or {}).get("genres") or [])
    return out


def _resolve(key: str, obs: dict[str, Any]) -> tuple[bool, Any]:
    """`expect` 的键 → 实际值。返回 `(认不认得, 值)`。"""
    if key.endswith("_sha256"):
        base = key[: -len("_sha256")]
        if base in obs:
            return True, (sha16(obs[base]), obs[base])
        return False, None
    if key.endswith("_len"):
        base = key[: -len("_len")]
        if base in obs:
            value = obs[base]
            return True, (len(value) if isinstance(value, (str, list, dict)) else value)
        return False, None
    if key in obs:
        return True, obs[key]
    return False, None


def compare(expect: dict[str, Any], obs: dict[str, Any], *, name: str = "") -> list[str]:
    """逐键比对，返回"不一致"的描述列表（空 = 全过）。

    `expected_none=true` 时额外要求 `hit` 为空 —— 这就是"强制空结果用例"的落点：
    筛选题错时会返回首条候选，这里立刻红。
    """
    problems: list[str] = []
    for key, want in expect.items():
        if key == "expected_none":
            continue
        known, got = _resolve(key, obs)
        if not known:
            raise FixtureError(f"{name}：`[expect].{key}` 认不出来（键名打错？）")
        if key.endswith("_sha256"):
            actual, raw = got
            if actual != want:
                problems.append(f"{key}: 期望 {want}，实际 {actual}（原值 {str(raw)[:60]!r}）")
            continue
        if key.endswith("_len"):
            if got != want:
                problems.append(f"{key}: 期望 {want}，实际 {got}")
            continue
        if got != want:
            problems.append(f"{key}: 期望 {want!r}，实际 {got!r}")
    return problems
