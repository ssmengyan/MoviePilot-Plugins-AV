"""取数图：**字段 × 站点链**（声明式多源择优）。

借 `sqzw-x/amane` `aggregate/engine.py` 的模型（GPL-3.0），落到我们那 2 个元数据源上：

- `FIELDS` —— 我们真正会写进 Emby / 界面的字段名（与 `gather()` 返回的键同名）；
- `SOURCES` —— 每个源的声明：**提供哪些字段**、第几段跑、什么条件下才值得跑、由哪个开关控制；
- `DEFAULT_CHAIN` —— 内容类型 → 有序站点链；
- `compile_chain()` —— 把链 + 稀疏 `field_priority` + 稀疏 `field_blacklist` 编成"每字段一条链"
  （上游 `compile_priority` 的语义：prefer ∩ 链 去重前置 → 其余保序接上 → exclude 剔除，二者冲突以 exclude 为准）；
- `should_run()` —— 第二段的闸门；
- `describe()` —— 把编译结果摊平成可下发/可排障的形状（设置台与自检页读它）。

**为什么今天只有一条链**：我们只有 2 个源（javdb 出骨架 / javtxt 出中文简介），
7 种内容类型各自的链会长得一模一样 —— 造 7 张相同的表是过度设计（`最终方案` §13.4 自己也问过）。
所以类型 → 链这张表**留在这里**（`DEFAULT_CHAIN` 每个类型一行），今天全指向同一条；
将来加 DMM / r18.dev（最终方案 D10）只是**填一行数据**，不用改 `gather()` 的流程。

**MetaTube 已于 0.8.1 整体下线**（上游项目停更、结果不可信），取数链只剩 javdb → javtxt；
`only_if_missing` / `phase` 这套闸门留给将来新增的源，不在本次改造里删掉。

**与上游的一处有意差异**：上游只有"字段级提前/排除"两个旋钮；我们多一层**站点启停**
（`enabled_sources()`），因为界面上的开关是"这个源用不用"，与"这个字段要不要优先问它"是两件事。

**溯源（`field_sources`）在 `gather()` 里按"谁真的填了这个字段"打标**，不在这里反推：
填值规则有特例（javtxt 的占位简介要丢弃、LLM 覆盖前两者），事后按链反推会撒谎。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

from .number_classify import CONTENT_TYPES

#: 我们真正落 Emby / 下发给界面的字段（**与 `gather()` 返回的键同名**）。
FIELDS: Tuple[str, ...] = (
    "title_jp", "origin_title", "title_zh",
    "plot_jp", "plot_zh",
    "actors", "tags",
    "studio", "publisher", "series", "director",
    "release_date", "duration", "score",
    "cover_url", "thumb_url", "preview_video_url", "preview_images",
    "javdb_id",
)

#: 图像资产源（不是元数据源，不进链：它按 `assets` 决定用哪张图，见 `pick_assets`）。
IMAGE_SOURCE = "javdb_assets"
#: 翻译不是源：它把拿到的日文**派生**成中文，溯源记在 `title_zh` / `plot_zh` 上。
DERIVED_SOURCE = "llm"


@dataclass(frozen=True)
class SourceSpec:
    """一个源的声明。**只描述，不实现**（实现在 `scraper.py` 的取数函数里）。"""

    id: str
    label: str
    provides: Tuple[str, ...]
    phase: int = 1
    #: 第二段闸门：这些字段里**只要有空的**就值得跑这一次（空元组 = 总是值得跑）
    only_if_missing: Tuple[str, ...] = ()
    #: `opts` 里控制启停的键（空 = 常开，不可关）
    option: str = ""
    note: str = ""

    def covers(self, field: str) -> bool:
        return field in self.provides


#: 站点声明表。顺序无关（真正的顺序在 `DEFAULT_CHAIN` 里）。
SOURCES: Dict[str, SourceSpec] = {
    "javdb": SourceSpec(
        id="javdb", label="JavDB",
        provides=("title_jp", "origin_title", "actors", "tags", "studio", "publisher",
                  "series", "director", "release_date", "duration", "score",
                  "cover_url", "thumb_url", "preview_video_url", "preview_images",
                  "javdb_id"),
        phase=1,
        note="骨架主源（唯一能给演员 id/头像与剧照的源）；**不能关**",
    ),
    "javtxt": SourceSpec(
        id="javtxt", label="Javtxt",
        provides=("title_zh", "plot_zh", "plot_jp"),
        phase=1, option="javtxt",
        note="中文直出（站点机翻）：概述与中文标题的第一顺位",
    ),
}

#: 每类型的默认链。今天全指向同一条（见模块 docstring）；将来分链只改这一张表。
_DEFAULT_SOURCES: Tuple[str, ...] = ("javdb", "javtxt")
DEFAULT_CHAIN: Dict[str, Tuple[str, ...]] = {
    **{kind: _DEFAULT_SOURCES for kind in CONTENT_TYPES},
    "_default": _DEFAULT_SOURCES,
}

#: `javdb` 是骨架：任何链里都必须在，且不允许被开关关掉
#: 源的实际**执行顺序**（`gather()` 里就是按这个顺序依次问的：javdb 骨架 → javtxt）。
#: `may_fill()` 用它判断"链上排在前面的源是不是还没轮到执行" —— 是就先别填，留给那个优先源。
#: **改了 `gather()` 的执行顺序，这里必须同步改**（有一条单测盯着它与 `SOURCES` 的 phase 一致）。
EXEC_ORDER: Tuple[str, ...] = ("javdb", "javtxt")

#: 默认链（`DEFAULT_CHAIN`）里每个字段的落点；由 `compile_chain()` 使用
ALWAYS_ON: FrozenSet[str] = frozenset({"javdb"})


def route_for(content_type: Any) -> Tuple[str, ...]:
    """该内容类型的链；认不出的类型回默认链（**不报错**：类型来自番号形态，本就可疑）。"""
    return DEFAULT_CHAIN.get(str(content_type or "")) or DEFAULT_CHAIN["_default"]


def enabled_sources(opts: Optional[Mapping[str, Any]]) -> FrozenSet[str]:
    """从 `opts` 算出**启用了哪些源**。

    `opts['sources']`（新键，设置台由后端下发可选值）优先；没有就回落 `opts['plot_sources']`
    （0.7.x 的两个布尔开关合成的那一份）。`javdb` 永远在（骨架）。
    """
    options = dict(opts or {})
    raw = options.get("sources")
    if isinstance(raw, (list, tuple, set, frozenset)) and raw:
        return frozenset({str(s) for s in raw}) | ALWAYS_ON
    legacy = [str(s) for s in (options.get("plot_sources") or ())]
    return frozenset(legacy) | ALWAYS_ON


def compile_chain(content_type: Any, *, field_priority: Optional[Mapping[str, Sequence[str]]] = None,
                  field_blacklist: Optional[Mapping[str, Sequence[str]]] = None,
                  enabled: Optional[Iterable[str]] = None) -> Dict[str, List[str]]:
    """链 + 稀疏优先级 + 稀疏黑名单 → **每个字段一条站点链**。

    语义照上游 `compile_priority`（`aggregate/engine.py:71-106`）：
    `prefer` 与链**求交**后去重前置 → 其余链上站点保序接上 → `exclude` 从该字段链上剔除；
    同一站同时出现在 prefer 与 exclude 时**以 exclude 为准**；不在链里的站（写错了/已停用）**无效**。
    """
    route = [s for s in route_for(content_type)
             if enabled is None or s in set(enabled)]
    route_set = set(route)
    banned: Dict[str, FrozenSet[str]] = {
        str(field): frozenset(str(s) for s in sites)
        for field, sites in (field_blacklist or {}).items() if sites
    }
    prefer = field_priority or {}

    chains: Dict[str, List[str]] = {}
    for field_name in FIELDS:
        skip = banned.get(field_name, frozenset())
        seen: set = set()
        chain: List[str] = []
        for site in (str(s) for s in (prefer.get(field_name) or ())):
            if site in route_set and site not in seen and site not in skip:
                seen.add(site)
                chain.append(site)
        for site in route:
            if site not in seen and site not in skip:
                seen.add(site)
                chain.append(site)
        chains[field_name] = chain
    return chains


def should_run(spec: SourceSpec, values: Optional[Mapping[str, Any]] = None, *,
               enabled: Optional[Iterable[str]] = None) -> bool:
    """这个源现在**值不值得跑**：先看启停，再看它自己的第二段闸门。

    `values` 是"目前已经定值的字段"（空串/空列表/None 都算空）。
    """
    if enabled is not None and spec.id not in set(enabled):
        return False
    if not spec.only_if_missing:
        return True
    current = values or {}
    return any(not current.get(name) for name in spec.only_if_missing)


def pending_fields(content_type: Any, values: Optional[Mapping[str, Any]] = None, *,
                   field_priority: Optional[Mapping[str, Sequence[str]]] = None,
                   field_blacklist: Optional[Mapping[str, Sequence[str]]] = None,
                   enabled: Optional[Iterable[str]] = None) -> List[str]:
    """按链算：**还有哪些字段是空的**（谁都没给）。给自检页与 dry-run 报告用。"""
    chains = compile_chain(content_type, field_priority=field_priority,
                           field_blacklist=field_blacklist, enabled=enabled)
    current = values or {}
    return [name for name, chain in chains.items() if chain and not current.get(name)]


def describe(content_type: Any, *, field_priority: Optional[Mapping[str, Sequence[str]]] = None,
             field_blacklist: Optional[Mapping[str, Sequence[str]]] = None,
             enabled: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """编译结果的可下发形状：`{content_type, route, chains, sources, phases}`。

    设置台/自检页只读它（前端**不许自己拼链**）—— 与 P1-5「站点可选值由后端下发」同一条纪律。
    """
    route = [s for s in route_for(content_type)
             if enabled is None or s in set(enabled)]
    chains = compile_chain(content_type, field_priority=field_priority,
                           field_blacklist=field_blacklist, enabled=enabled)
    return {
        "content_type": str(content_type or ""),
        "route": list(route),
        "chains": {name: list(chain) for name, chain in chains.items()},
        "sources": [
            {"id": spec.id, "label": spec.label, "phase": spec.phase,
             "provides": list(spec.provides), "only_if_missing": list(spec.only_if_missing),
             "option": spec.option, "note": spec.note,
             "enabled": spec.id in set(route), "always_on": spec.id in ALWAYS_ON}
            for spec in sorted(SOURCES.values(), key=lambda s: (s.phase, s.id))
        ],
        "phases": {1: [s for s in route if SOURCES[s].phase == 1],
                   2: [s for s in route if SOURCES[s].phase == 2]},
    }
