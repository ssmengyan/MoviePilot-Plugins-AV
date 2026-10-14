"""取数图（0.8.0 / P0-1）的回归：声明表自洽 + 链编译 + 第二段闸门。

链编译的语义要逐条钉住（它是"谁在什么时候被问"的唯一真值）：
上游 `compile_priority` 的四条不变量 + 我们自己加的启停/闸门。
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
    """今天只有 3 个源 → 所有类型的链是同一条（造 7 张相同的表是过度设计）。

    将来给某类型分链时（例：`uncensored` 加 DMM），**只改 DEFAULT_CHAIN 这一行**，
    这条用例到那时改成"至少两条不同"即可。
    """
    routes = {kind: graph.route_for(kind) for kind in classify_mod.CONTENT_TYPES}
    assert len(set(routes.values())) == 1
    assert set(routes.values()) == {("javdb", "javtxt", "metatube")}
    assert graph.route_for("不存在的类型") == ("javdb", "javtxt", "metatube")


def test_metatube_is_phase_two_with_a_gate(graph):
    """MetaTube 恒定 ~10 秒 → 必须落在第二段，且只在"确实还缺"时跑。"""
    spec = graph.SOURCES["metatube"]
    assert spec.phase == 2
    assert spec.only_if_missing == ("plot_zh", "title_jp", "cover_url")
    assert spec.option == "metatube"


# --- 链编译 -----------------------------------------------------------------

def test_compile_chain_defaults_to_route(graph):
    chains = graph.compile_chain("censored")
    assert set(chains) == set(graph.FIELDS)
    for name, chain in chains.items():
        assert chain == ["javdb", "javtxt", "metatube"], name


def test_compile_chain_prefer_moves_to_front(graph):
    chains = graph.compile_chain("censored", field_priority={"plot_zh": ("metatube",)})
    # prefer ∩ 链 去重前置 → 其余保序接上
    assert chains["plot_zh"] == ["metatube", "javdb", "javtxt"]
    # 只影响这一个字段
    assert chains["title_jp"] == ["javdb", "javtxt", "metatube"]


def test_compile_chain_blacklist_removes(graph):
    chains = graph.compile_chain("censored", field_blacklist={"plot_zh": ("javtxt",)})
    assert chains["plot_zh"] == ["javdb", "metatube"]
    assert chains["plot_jp"] == ["javdb", "javtxt", "metatube"]


def test_compile_chain_exclude_beats_prefer(graph):
    """同一站同时出现在 prefer 与 exclude → **以 exclude 为准**（上游口径）。"""
    chains = graph.compile_chain("censored", field_priority={"plot_zh": ("javtxt", "metatube")},
                                 field_blacklist={"plot_zh": ("javtxt",)})
    assert chains["plot_zh"] == ["metatube", "javdb"]


def test_compile_chain_ignores_unknown_sources(graph):
    """不在链里的站（写错了 / 已停用）**无效**：不许凭空产生请求。"""
    chains = graph.compile_chain("censored", field_priority={"plot_zh": ("dmm",)},
                                 field_blacklist={"plot_zh": ("dmm", "r18dev")})
    assert chains["plot_zh"] == ["javdb", "javtxt", "metatube"]


def test_compile_chain_drops_disabled_sources(graph):
    chains = graph.compile_chain("censored", enabled=("javdb", "javtxt"))
    for name, chain in chains.items():
        assert chain == ["javdb", "javtxt"], name


def test_compile_chain_keeps_route_order(graph):
    """保序：链上站点的相对顺序不因 prefer/exclude 而变化。"""
    chains = graph.compile_chain("censored", field_priority={"actors": ("metatube",)})
    assert chains["actors"] == ["metatube", "javdb", "javtxt"]
    assert chains["tags"] == ["javdb", "javtxt", "metatube"]


# --- 第二段闸门 -------------------------------------------------------------

def test_should_run_gate(graph):
    spec = graph.SOURCES["metatube"]
    filled = {"plot_zh": "中文简介", "title_jp": "标题", "cover_url": "http://x/1.jpg"}
    assert not graph.should_run(spec, filled)                    # 什么都不缺 → 别花那 10 秒
    assert graph.should_run(spec, {**filled, "plot_zh": ""})     # 缺中文简介 → 跑
    assert graph.should_run(spec, {**filled, "title_jp": None})  # javdb 挂了 → 跑
    assert graph.should_run(spec, {})                            # 什么都没有 → 跑


def test_should_run_respects_enabled(graph):
    spec = graph.SOURCES["metatube"]
    assert not graph.should_run(spec, {}, enabled=("javdb", "javtxt"))
    assert graph.should_run(spec, {}, enabled=("javdb", "metatube"))


def test_phase_one_sources_have_no_gate(graph):
    assert graph.should_run(graph.SOURCES["javdb"], {}) is True
    assert graph.should_run(graph.SOURCES["javtxt"], {}) is True


def test_enabled_sources_reads_both_keys(graph):
    """新键 `sources` 优先；旧键 `plot_sources` 兼容（0.7.x 的两个布尔开关）。"""
    assert graph.enabled_sources({"sources": ["javtxt"]}) == frozenset({"javdb", "javtxt"})
    assert graph.enabled_sources({"plot_sources": ("metatube",)}) == \
        frozenset({"javdb", "metatube"})
    assert graph.enabled_sources({}) == frozenset({"javdb"})      # 骨架永在
    assert graph.enabled_sources({"sources": ["javdb"]}) == frozenset({"javdb"})


# --- 待补字段与可下发形状 ---------------------------------------------------

def test_pending_fields(graph):
    values = {"title_jp": "标题", "plot_zh": "简介"}
    pending = graph.pending_fields("censored", values)
    assert "cover_url" in pending and "actors" in pending
    assert "title_jp" not in pending and "plot_zh" not in pending


def test_describe_shape(graph):
    info = graph.describe("censored", enabled=("javdb", "metatube"))
    assert info["content_type"] == "censored"
    assert info["route"] == ["javdb", "metatube"]
    assert info["phases"][1] == ["javdb"]
    assert info["phases"][2] == ["metatube"]
    by_id = {row["id"]: row for row in info["sources"]}
    assert by_id["javdb"]["always_on"] is True and by_id["javdb"]["enabled"] is True
    assert by_id["javtxt"]["enabled"] is False
    assert by_id["metatube"]["phase"] == 2
    # 链里只出现启用的站（前端按它渲染，不许自己拼）
    assert all(set(chain) <= {"javdb", "metatube"} for chain in info["chains"].values())
