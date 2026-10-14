"""真实响应夹具的回归（数据驱动，用例在 `fixtures/avhelper/**/*.toml`）。

夹具根在仓库根（`MoviePilot-Plugins-AV/` 之外）→ **公开仓里整模块 skip**（不是失败）：
那棵子树不发布第三方响应，见 `fixtures/avhelper/README.md`。

夹具本身坏了（TOML 缺键 / 响应文件缺失 / expect 键名打错）会以 `FixtureError` **炸在收集期**，
不静默跳过 —— "夹具坏了"与"夹具不在"必须区分开。
"""

from __future__ import annotations

import pytest

from fixture_cases import (FIXTURE_ROOT, SITES, compare, discover_cases,  # noqa: I001
                           observed)

pytestmark = pytest.mark.skipif(
    not FIXTURE_ROOT.is_dir(),
    reason="fixtures/avhelper 不在（公开仓不带夹具；见该目录 README）",
)

CASES = discover_cases() if FIXTURE_ROOT.is_dir() else []


def _case_id(item: dict) -> str:
    return f"{item['site']}/{item['path'].stem}"


@pytest.mark.parametrize("item", CASES, ids=[_case_id(i) for i in CASES] or None)
def test_fixture_case(scraper_mod, emby_mod, item):
    """一条真实响应 → 跑解析 → 逐键比对 `[expect]`。"""
    info = item["case"]
    expect = item["expect"]
    obs = observed(scraper_mod, emby_mod, item)
    problems = compare(expect, obs, name=item["path"].name)
    assert not problems, "\n".join(problems)

    # 每个用例都必须**表态**：期望命中，还是期望一条都不选（`expected_none`）。
    # 没有这一条，"筛选恒返回首条"这类 bug 会在所有用例上静默通过。
    wants_hit = not bool(info["expected_none"])
    got_hit = obs.get("hit") is not None
    assert got_hit is wants_hit, (
        f"{item['path'].name}: expected_none={info['expected_none']}（期望命中={wants_hit}）"
        f" 但实际命中={got_hit}：{obs.get('hit')!r}"
    )


def test_every_site_has_an_empty_result_case():
    """★ 每个站点至少一条 `expected_none` 用例（照 amane 的硬规矩）。

    空结果用例防的是"筛选 bug 被首页/推广链接掩盖"：站点查不到时**必须**回空 ——
    javtxt 的空搜索页是 0 张卡片，MetaTube 查不到时会返回**随机**结果（必须被串号拦截挡住）。
    """
    if not CASES:
        pytest.skip("夹具不在")
    for site in SITES:
        site_cases = [c for c in CASES if c["site"] == site]
        assert site_cases, f"{site} 一条用例都没有"
        assert any(c["case"]["expected_none"] for c in site_cases), \
            f"{site} 缺 expected_none 用例（空结果必须有样本）"


def test_case_files_declare_capture_provenance():
    """`[case].capture` / `captured` 必填：夹具的价值一半在"它当时长什么样"。"""
    if not CASES:
        pytest.skip("夹具不在")
    for item in CASES:
        case = item["case"]
        assert str(case.get("captured") or "").strip(), f"{item['path'].name} 缺 captured"
        assert "<proxy>" in case["capture"] or "http" in case["capture"], \
            f"{item['path'].name} 的 capture 不像一条采集命令"
