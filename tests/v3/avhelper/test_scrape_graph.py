"""取数图（0.8.0 / P0-1）的回归：声明表自洽 + 链编译 + 闸门。

链编译的语义要逐条钉住（它是"谁在什么时候被问"的唯一真值）：
上游 `compile_priority` 的四条不变量 + 我们自己加的启停/闸门。

0.8.1 起 MetaTube 下线，取数链只剩 javdb → javtxt；`phase`/`only_if_missing` 这套闸门
**留着**（将来新增 DMM 这类"很贵、要先看缺不缺"的源要用），所以这里用合成的 `SourceSpec`
测闸门语义，而不是绑在某个真实源上。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.filterwarnings("error")


@pytest.fixture(scope="module")
def graph(graph_mod):
    return graph_mod


# --- 声明表自洽 -------------------------------------------------------------

def test_tables_are_self_consistent(graph):
    for kind, route in graph.DEFAULT_CHAIN.items():
        assert route, f"{kind} 的链是空的"
        for site in route:
            assert site in graph.SOURCES, f"{kind} 链里的 {site} 没有声明"
        assert graph.ALWAYS_ON <= set(route), f"{kind} 的链漏了骨架源"

    for spec in graph.SOURCES.values():
        assert spec.phase in (1, 2), f"{spec.id} 的 phase 只能是 1/2"
        assert spec.provides, f"{spec.id} 什么都没提供"
        for name in spec.provides:
            assert name in graph.FIELDS, f"{spec.id} 提供了未知字段 {name}"
        if spec.phase == 2:
            # 第二段必须有闸门：它存在的理由就是"这一次很贵，得先看看缺不缺"
            assert spec.only_if_missing, f"{spec.id} 在第二段却没有 only_if_missing"
            assert set(spec.only_if_missing) <= set(graph.FIELDS)


def test_every_content_type_has_a_route(graph, classify_mod):
    for kind in classify_mod.CONTENT_TYPES:
        assert kind in graph.DEFAULT_CHAIN
    assert graph.DEFAULT_CHAIN["_default"]


def test_today_all_types_share_one_chain(graph, classify_mod):
    """今天只有 2 个源 → 所有类型的链是同一条（造 7 张相同的表是过度设计）。

    将来给某类型分链时（例：`uncensored` 加 DMM），**只改 DEFAULT_CHAIN 这一行**，
    这条用例到那时改成"至少两条不同"即可。
    """
    routes = {kind: graph.route_for(kind) for kind in classify_mod.CONTENT_TYPES}
    assert len(set(routes.values())) == 1
    assert set(routes.values()) == {("javdb", "javtxt")}
    assert graph.route_for("不存在的类型") == ("javdb", "javtxt")


def test_metatube_is_gone(graph):
    """0.8.1：MetaTube 整体下线 —— 源表与默认链里都不许再出现它。"""
    assert "metatube" not in graph.SOURCES
    assert all("metatube" not in route for route in graph.DEFAULT_CHAIN.values())
    assert "metatube" not in graph.EXEC_ORDER


# --- 链编译 -----------------------------------------------------------------

def test_compile_chain_defaults_to_route(graph):
    chains = graph.compile_chain("censored")
    assert set(chains) == set(graph.FIELDS)
    for name, chain in chains.items():
        assert chain == ["javdb", "javtxt"], name


def test_compile_chain_prefer_moves_to_front(graph):
    chains = graph.compile_chain("censored", field_priority={"plot_zh": ("javtxt",)})
    # prefer ∩ 链 去重前置 → 其余保序接上
    assert chains["plot_zh"] == ["javtxt", "javdb"]
    # 只影响这一个字段
    assert chains["title_jp"] == ["javdb", "javtxt"]


def test_compile_chain_blacklist_removes(graph):
    chains = graph.compile_chain("censored", field_blacklist={"plot_zh": ("javtxt",)})
    assert chains["plot_zh"] == ["javdb"]
    assert chains["plot_jp"] == ["javdb", "javtxt"]


def test_compile_chain_exclude_beats_prefer(graph):
    """同一站同时出现在 prefer 与 exclude → **以 exclude 为准**（上游口径）。"""
    chains = graph.compile_chain("censored", field_priority={"plot_zh": ("javtxt",)},
                                 field_blacklist={"plot_zh": ("javtxt",)})
    assert chains["plot_zh"] == ["javdb"]


def test_compile_chain_ignores_unknown_sources(graph):
    """不在链里的站（写错了 / 已停用）**无效**：不许凭空产生请求。"""
    chains = graph.compile_chain("censored", field_priority={"plot_zh": ("dmm",)},
                                 field_blacklist={"plot_zh": ("dmm", "r18dev")})
    assert chains["plot_zh"] == ["javdb", "javtxt"]


def test_compile_chain_drops_disabled_sources(graph):
    chains = graph.compile_chain("censored", enabled=("javdb",))
    for name, chain in chains.items():
        assert chain == ["javdb"], name


def test_compile_chain_keeps_route_order(graph):
    """保序：链上站点的相对顺序不因 prefer/exclude 而变化。"""
    chains = graph.compile_chain("censored", field_priority={"actors": ("javtxt",)})
    assert chains["actors"] == ["javtxt", "javdb"]
    assert chains["tags"] == ["javdb", "javtxt"]


# --- 第二段闸门 -------------------------------------------------------------

def test_should_run_gate(graph):
    """闸门语义用合成源测（真实源里今天没有第二段）。"""
    spec = graph.SourceSpec(
        id="dmm", label="DMM", provides=("title_jp", "cover_url"),
        phase=2, only_if_missing=("plot_zh", "title_jp", "cover_url"))
    filled = {"plot_zh": "中文简介", "title_jp": "标题", "cover_url": "http://x/1.jpg"}
    assert not graph.should_run(spec, filled)                    # 什么都不缺 → 别花那 10 秒
    assert graph.should_run(spec, {**filled, "plot_zh": ""})     # 缺中文简介 → 跑
    assert graph.should_run(spec, {**filled, "title_jp": None})  # 缺标题 → 跑
    assert graph.should_run(spec, {})                            # 什么都没有 → 跑


def test_should_run_respects_enabled(graph):
    spec = graph.SourceSpec(id="javtxt", label="Javtxt", provides=("plot_zh",),
                            phase=1, option="javtxt")
    assert not graph.should_run(spec, {}, enabled=("javdb",))
    assert graph.should_run(spec, {}, enabled=("javdb", "javtxt"))


def test_phase_one_sources_have_no_gate(graph):
    assert graph.should_run(graph.SOURCES["javdb"], {}) is True
    assert graph.should_run(graph.SOURCES["javtxt"], {}) is True


def test_enabled_sources_reads_both_keys(graph):
    """新键 `sources` 优先；旧键 `plot_sources` 兼容（0.7.x 的两个布尔开关）。"""
    assert graph.enabled_sources({"sources": ["javtxt"]}) == frozenset({"javdb", "javtxt"})
    assert graph.enabled_sources({"plot_sources": ("javtxt",)}) == \
        frozenset({"javdb", "javtxt"})
    assert graph.enabled_sources({}) == frozenset({"javdb"})      # 骨架永在
    assert graph.enabled_sources({"sources": ["javdb"]}) == frozenset({"javdb"})


# --- 待补字段与可下发形状 ---------------------------------------------------

def test_pending_fields(graph):
    values = {"title_jp": "标题", "plot_zh": "简介"}
    pending = graph.pending_fields("censored", values)
    assert "cover_url" in pending and "actors" in pending
    assert "title_jp" not in pending and "plot_zh" not in pending


def test_describe_shape(graph):
    info = graph.describe("censored", enabled=("javdb", "javtxt"))
    assert info["content_type"] == "censored"
    assert info["route"] == ["javdb", "javtxt"]
    assert info["phases"][1] == ["javdb", "javtxt"]
    assert info["phases"][2] == []
    by_id = {row["id"]: row for row in info["sources"]}
    assert by_id["javdb"]["always_on"] is True and by_id["javdb"]["enabled"] is True
    assert by_id["javtxt"]["enabled"] is True
    # 链里只出现启用的站（前端按它渲染，不许自己拼）
    assert all(set(chain) <= {"javdb", "javtxt"} for chain in info["chains"].values())


def test_exec_order_matches_phases(graph):
    """`EXEC_ORDER` 必须与 `SOURCES[*].phase` 的先后一致（`gather()` 就按它顺序问）。

    给后人的提醒：改了 `gather()` 的执行顺序（或给源换 phase）就得同步改 `EXEC_ORDER`，
    否则 `may_fill()` 的"留给优先源"会判错。
    """
    by_phase = tuple(spec.id for spec in
                     sorted(graph.SOURCES.values(), key=lambda s: (s.phase, s.id)))
    assert graph.EXEC_ORDER == by_phase
    assert set(graph.EXEC_ORDER) == set(graph.SOURCES)
