# -*- coding: utf-8 -*-
"""`namemap.py` 的单测：三份映射表的解析口径、冲突消歧、标签双层索引、繁→简 FMM、资源降级、入库同步。

全部离线：只读随包 `resources/`（外加几个受控的小 XML 夹具与临时库），不联网、不碰线上数据。

断言的数字来自 `_tmp/p0/REPORT-4.md` 的实测；**三处与该报告不同**（都是本实现重新实测的值，
报告那几处口径不同，见 `_tmp/s3/REPORT-S3.md`）：
① `男優` 命中 **207** 条记录（报告写 220，那是含重复片段的计数）；
② 标签索引 **1017 / 724** 键（报告写 1000 / 716：本实现把记录自己的三语名补进"还没有人认领"的键）；
③ 标签冲突键 **4** 个（报告写 3：`騎乗位` 与 `骑乘位` 归一化后是两个不同的键）。
"""

import importlib.util
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
#: 与 conftest 的合成包**分开**：本文件加载的 namemap 不进入 conftest 那个包，
#: 避免给 `store.py` 的 `_norm_lookup()` 换掉归一化口径、影响别人的单测
PKG_NAME = "avhelper_namemap_under_test"

#: 真实数据里 `あやね遥菜` 记录上的一个**带标记别名**（`みさちゃん【誤認注意】`）：必须查不到
MARKED_ALIAS = "みさちゃん"
#: 真实冲突键的实测规模（REPORT-4 §3.2；本实现重新实测为 207）
MALE_ALIAS = "男優"
MALE_ALIAS_CANDIDATES = 207


def _load(name: str):
    """按路径加载插件模块（同 conftest 的手法：先挂一个合成包，相对导入才有父包）。"""
    if PKG_NAME not in sys.modules:
        package = types.ModuleType(PKG_NAME)
        package.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PKG_NAME] = package
    key = f"{PKG_NAME}.{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def nm():
    """加载好的 `namemap` 模块（真实三份资源，`load()` 已跑过一次）。"""
    module = _load("namemap")
    module.load()
    return module


@pytest.fixture(scope="module", autouse=True)
def _builtin_resources(nm, tmp_path_factory):
    """把数据根指到一个空目录：保证读的是**随包内置**那份资源，本机用户覆盖目录不干扰断言。"""
    paths_mod = sys.modules[f"{PKG_NAME}.paths"]
    saved = paths_mod._DATA_ROOT
    paths_mod._DATA_ROOT = tmp_path_factory.mktemp("namemap-empty-data-root")
    yield
    paths_mod._DATA_ROOT = saved


# ---------------------------------------------------------------- 归一化与别名解析

class TestNormalizeAndKeywords:
    """`normalize()` / `parse_keywords()` / `keywords_norm()` 的口径（REPORT-4 §3、§5.1）。"""

    def test_nfkc_punct_and_lower(self, nm):
        assert nm.normalize("Ａ＠Ｂ.") == "ab"                 # 全角 + 标点（NFKC + 丢 Po/Ps）
        assert nm.normalize("ギャル２人组") == "ギャル2人组"       # 全角数字被 NFKC 折半角
        assert nm.normalize("AV女優") == "av女優"               # 拉丁部分必须小写
        assert nm.normalize("エマ・ローレンス") == "エマローレンス"  # `・`(Po) 会被丢
        assert nm.normalize(None) == "" and nm.normalize("  ") == ""

    def test_iteration_mark_is_not_punctuation(self, nm):
        """`々` 是 `Lm` 不是标点：`奈々 ≠ 奈奈`，必须留着。"""
        assert nm.normalize("奈々") == "奈々"

    def test_only_ascii_comma_splits_aliases(self, nm):
        """全角逗号不是分隔符（实测 6 条别名含 `，`，切成 ASCII 逗号才正确）。"""
        assert [bare for bare, _ in nm.parse_keywords(",愛好，文化,x,")] == ["愛好，文化", "x"]

    def test_marker_pair_parsing(self, nm):
        assert nm.parse_keywords(",a,b【誤認注意】,") == [("a", ""), ("b", "【誤認注意】")]
        # 纯标记片段要保留下来（统计口径要数得到），裸名为空
        assert nm.parse_keywords(",【同名異人】,x,") == [("", "【同名異人】"), ("x", "")]

    def test_keywords_norm_is_comma_wrapped(self, nm):
        """S1 的 `store.namemap_find()` 用 `LIKE '%,'||?||',%'` 整词匹配，首尾逗号不能少。"""
        assert nm.keywords_norm(["a", "b", "a"]) == ",a,b,"
        assert nm.keywords_norm([]) == ","


# ---------------------------------------------------------------- 真实映射表的规模与结构

class TestRealTables:
    """随包资源的结构与规模（属性式解析、标记别名排除、冲突键）。"""

    def test_xml_is_attribute_style(self, nm):
        """`mapping_actor.xml` 是**属性式**记录（`<a zh_cn= … />`，无子元素）。"""
        root = ET.parse(PLUGIN_DIR / "resources" / "mapping_actor.xml").getroot()
        assert root.tag == "actor"
        records = list(root)
        assert len(records) == 5351
        assert {el.tag for el in records} == {"a"}
        assert all(len(el) == 0 for el in records[:50])            # 没有子元素
        info_root = ET.parse(PLUGIN_DIR / "resources" / "mapping_info.xml").getroot()
        assert info_root.tag == "info" and len(list(info_root)) == 347

    def test_actor_counts(self, nm):
        stats = nm.stats()
        assert stats["actors"] == 5351
        assert stats["alias_keys"] == 15588                        # distinct normalize(别名)
        assert stats["javdb_actor_ids"] == 5115                    # href 里的 /actors/<id>
        assert stats["marker_aliases"] == 531                      # 【誤認注意】445 + 【同名異人】86
        assert stats["empty_aliases"] == 89                        # 88 条纯标记 + 1 条噪声

    def test_conflict_keys_are_six_not_190(self, nm):
        """标记别名不入索引：实测冲突键 6 个；不排除会涨到 190。"""
        assert nm.stats()["multi_target_keys"] == 6

    def test_info_table_and_dict_counts(self, nm):
        stats = nm.stats()
        assert stats["tag_records"] == 347                         # info 表记录数
        assert stats["delete_records"] == 42                       # zh_cn == '删除'
        assert stats["delete_rules"] == 61                         # 展开成 61 个删除关键词
        assert stats["tags"] == 1017 and stats["tags_simplified"] == 724
        assert stats["zhc_entries"] == 9149                        # zh2Hans 总键数
        assert stats["chars"] == 8505 and stats["phrases"] == 644  # 单字 + 词组
        assert stats["sync_rows"] == 5698                          # 演员 5351 + info 347

    def test_stats_values_are_ints(self, nm):
        assert all(isinstance(value, int) for value in nm.stats().values())
        assert nm.stats()["loaded"] == 1 and nm.ready() is True

    def test_actor_record_shape(self, nm):
        record = nm.actor_lookup("三上悠亜")
        assert record["canonical_id"] == "amane:三上悠亚"           # 前缀 + zh_cn
        assert record["zh"] == record["zh_cn"] == "三上悠亚"
        assert record["tw"] == record["zh_tw"] == "三上悠亞"
        assert record["jp"] == "三上悠亜"
        assert record["javdb_actor_id"] == "Av2e"
        assert record["avatar"] == ""                              # 上游表里没有头像 URL
        assert record["source"] == "amane"
        assert record["keywords_norm"].startswith(",") and record["keywords_norm"].endswith(",")

    def test_marked_alias_is_excluded(self, nm):
        """`あやね遥菜` 有一条 `みさちゃん【誤認注意】`：裸名不入索引，记录本身仍可按名字查到。"""
        record = nm.actor_lookup("あやね遥菜")
        assert record and record["canonical_id"] == "amane:あやね遥菜"
        assert MARKED_ALIAS not in record["keywords_norm"]
        assert nm.actor_lookup(MARKED_ALIAS) is None
        assert nm.actor_lookup_all(MARKED_ALIAS) == []

    def test_marked_alias_does_not_leak_to_its_owner(self, nm):
        """`市川潤` 被 `石川サダフミ` 标了误认注意：命中只能来自真正用这个名字的那条记录。"""
        ids = [record["canonical_id"] for record in nm.actor_lookup_all("市川潤")]
        assert "amane:石川サダフミ" not in ids
        assert ids == ["amane:市川润"]


# ---------------------------------------------------------------- 演员查询

class TestActorLookup:
    """`actor_lookup()` 的消歧优先级与 `actor_lookup_all()` / `actor_glossary()` / `actor_display()`。"""

    def test_hit_by_jp_zh_and_tw(self, nm):
        assert nm.actor_lookup("三上悠亜")["zh"] == "三上悠亚"       # 日文原名
        assert nm.actor_lookup("三上悠亚")["canonical_id"] == "amane:三上悠亚"  # 简中
        assert nm.actor_lookup("三上悠亞")["jp"] == "三上悠亜"       # 繁中
        assert nm.actor_lookup("桃乃木かな")["zh"] == "桃乃木香奈"
        assert nm.actor_lookup("深田えいみ")["zh"] == "深田咏美"

    def test_conflict_prefers_exact_jp_then_zh(self, nm):
        """`バカボン`/`バカボン×` 归一化后同键：靠**原文精确**区分，不许取第一个。"""
        assert nm.actor_lookup("バカボン")["canonical_id"] == "amane:バカボン"
        assert nm.actor_lookup("バカボン×")["canonical_id"] == "amane:バカボン×"
        assert nm.actor_lookup("沙織")["canonical_id"] == "amane:沙织"     # jp 精确
        assert nm.actor_lookup("沙织")["canonical_id"] == "amane:沙织"     # zh_cn 精确
        # 小写 `marin` 两条候选在两层精确里都撞（Marin / Marin.）→ 不猜
        assert nm.actor_lookup("marin") is None
        assert nm.actor_lookup("Marin")["canonical_id"] == "amane:Marin"

    def test_ambiguous_key_returns_none_not_a_guess(self, nm):
        assert len(nm.actor_lookup_all(MALE_ALIAS)) == MALE_ALIAS_CANDIDATES
        assert nm.actor_lookup(MALE_ALIAS) is None

    def test_lookup_all_exposes_every_candidate(self, nm):
        ids = [record["canonical_id"] for record in nm.actor_lookup_all(MALE_ALIAS)]
        assert len(ids) == len(set(ids)) == MALE_ALIAS_CANDIDATES
        assert ids[0] == "amane:未知男优"
        assert nm.actor_lookup_all("三上悠亜")[0]["canonical_id"] == "amane:三上悠亚"

    def test_unknown_and_empty_return_none(self, nm):
        for name in ("雛形みくる", "石川澪", "辻あずき", "", None, "  "):
            assert nm.actor_lookup(name) is None
            assert nm.actor_lookup_all(name) == []

    def test_actor_glossary_shape(self, nm):
        """`{日文名: 中文名}`：中日同名（`トニー大木`）与查不到的（`雛形みくる`）都不进表。"""
        assert nm.actor_glossary(["三上悠亜", "橋本ありな", "深田えいみ"]) == {
            "三上悠亜": "三上悠亚", "橋本ありな": "桥本有菜", "深田えいみ": "深田咏美",
        }
        assert nm.actor_glossary(["トニー大木", "雛形みくる"]) == {}
        assert nm.actor_glossary([]) == {} and nm.actor_glossary(None) == {}

    def test_actor_display_shape(self, nm):
        assert nm.actor_display("桃乃木かな") == {
            "name": "桃乃木香奈", "jp": "桃乃木かな", "zh": "桃乃木香奈", "alias": "",
        }
        # 没有映射：name 原样回传，jp/zh 留空（不许拿别的名字顶上）
        assert nm.actor_display("雛形みくる") == {
            "name": "雛形みくる", "jp": "", "zh": "", "alias": "",
        }
        # 用户备注优先参与查表（命中就是映射里的规范名）
        assert nm.actor_display("雛形みくる", alias="桃乃木かな")["name"] == "桃乃木香奈"


class TestCompositeName:
    """D13 复合名 `中文（日文）`（= 写进 Emby `People[].Name` 的形态）必须能回查映射表。

    S11 全库实测：修复前 12/12 全 `None` —— `normalize()` 会把全角括号连里面的日文名一起
    吃掉，整串变成 `皆川千遥みながわ千遥` 这种不存在的键。
    """

    #: 库里真实存在的演员（`皆川千遥` ← `みながわ千遥`）
    EXPECT = "amane:皆川千遥"

    def test_all_three_forms_resolve_to_same_record(self, nm):
        assert nm.actor_lookup("みながわ千遥")["canonical_id"] == self.EXPECT
        assert nm.actor_lookup("皆川千遥")["canonical_id"] == self.EXPECT
        assert nm.actor_lookup("皆川千遥（みながわ千遥）")["canonical_id"] == self.EXPECT
        assert nm.actor_lookup_all("皆川千遥（みながわ千遥）")[0]["canonical_id"] == self.EXPECT

    def test_halfwidth_and_square_brackets(self, nm):
        assert nm.actor_lookup("皆川千遥(みながわ千遥)")["canonical_id"] == self.EXPECT    # 半角圆括号
        assert nm.actor_lookup("皆川千遥［みながわ千遥］")["canonical_id"] == self.EXPECT  # 全角方括号
        assert nm.actor_lookup("皆川千遥[みながわ千遥]")["canonical_id"] == self.EXPECT    # 半角方括号
        assert nm.actor_lookup("皆川千遥 ( みながわ千遥 )")["canonical_id"] == self.EXPECT  # 带空白

    def test_outside_wins_then_inside(self, nm):
        """优先级：括号外（中文名）→ 括号内（日文名）。"""
        assert nm.actor_lookup("三上悠亚（深田えいみ）")["canonical_id"] == "amane:三上悠亚"
        # 括号外查不到 → 退到括号内
        assert nm.actor_lookup("雛形みくる（みながわ千遥）")["canonical_id"] == self.EXPECT

    def test_whole_string_wins_over_the_outside_part(self, nm):
        """**回归锁**：上游自己有带括号的别名（实测 14 个写法），它们的"括号外" `素人`
        指向另一位记录 —— 整串必须优先，否则这些老写法会被静默错抢。"""
        assert nm.actor_lookup("素人(多人)")["canonical_id"] == "amane:素人(多人)"
        assert nm.actor_lookup("素人(円光娘)")["canonical_id"] == "amane:素人(援交)"
        assert nm.actor_lookup("素人(患者)")["canonical_id"] == "amane:素人(患者)"
        assert nm.actor_lookup("恵美梨（アニー丽）")["canonical_id"] == "amane:恵美梨"

    def test_unknown_composite_still_none(self, nm):
        assert nm.actor_lookup("雛形みくる（ひながたみくる）") is None
        assert nm.actor_lookup("石川澪（いしかわみお）") is None
        assert nm.actor_lookup_all("雛形みくる（ひながたみくる）") == []
        assert nm.actor_lookup("（）") is None and nm.actor_lookup("") is None

    def test_composite_with_conflict_key_still_disambiguates(self, nm):
        """括号外是冲突键时消歧规则照旧（`バカボン` 靠原文精确；`男優` 207 候选仍不许猜）。"""
        assert nm.actor_lookup("バカボン（ダミー）")["canonical_id"] == "amane:バカボン"
        assert nm.actor_lookup("男優（ダミー）") is None

    def test_actor_display_handles_composite(self, nm):
        # 有映射：用映射里的规范三语名
        assert nm.actor_display("皆川千遥（みながわ千遥）") == {
            "name": "皆川千遥", "jp": "みながわ千遥", "zh": "皆川千遥", "alias": "",
        }
        # 没有映射：按括号拆开兜底（括号外给 name/zh、括号内给 jp），不把整串当成一个中文名
        assert nm.actor_display("雛形みくる（ひながたみくる）") == {
            "name": "雛形みくる", "jp": "ひながたみくる", "zh": "雛形みくる", "alias": "",
        }

    def test_actor_glossary_accepts_composite(self, nm):
        assert nm.actor_glossary(["皆川千遥（みながわ千遥）"]) == {"みながわ千遥": "皆川千遥"}


# ---------------------------------------------------------------- 标签查询

class TestTagLookup:
    """`tag_lookup()` / `clean_tags()`：双层索引、删除规则、两表不互相污染。"""

    #: 真实 JavDB 标签（zh-TW 详情页实抓，`_tmp/p0/evidence_4/tw_samples.json`）
    REAL_TAGS = {
        "OL": "职业装", "巨乳": "巨乳", "苗條": "苗条", "單體作品": "单体作品",
        "潮吹": "潮吹", "美少女電影": "美少女", "白天出軌": "白天出轨", "口交": "口交",
        "精選綜合": "精选综合", "淫亂真實": "淫乱真实", "中出": "中出", "乳交": "乳交",
        "凌辱": "羞辱", "女教師": "女教师", "學校泳裝": "学生泳装", "戲劇": "剧情",
    }

    def test_real_javdb_tags(self, nm):
        for tag, expect in self.REAL_TAGS.items():
            assert nm.tag_lookup(tag) == expect

    def test_delete_rule_returns_empty_string(self, nm):
        assert nm.tag_lookup("10枚組") == ""            # 原样就是删除关键词
        assert nm.tag_lookup("素人作品") == ""
        assert nm.tag_lookup("獨占配信") == ""           # 原样查不到 → 转简后命中删除规则
        assert nm.tag_lookup("独占配信") == ""           # 已经简体：转简层也必须命中
        assert nm.tag_lookup("10枚组") == ""

    def test_no_mapping_returns_none(self, nm):
        """随包表删不掉介质噪音词（REPORT-4 §2.2 勘误）：返回 None，不是 ''。"""
        assert nm.tag_lookup("ハイビジョン") is None
        assert nm.tag_lookup("4K") is None
        assert nm.tag_lookup("多P") is None
        assert nm.tag_lookup("") is None and nm.tag_lookup(None) is None
        assert nm.tag_lookup("三上悠亜") is None        # 演员名不走标签表

    def test_tables_do_not_pollute_each_other(self, nm):
        """两表有 7 个重叠关键词：各自只在自己的表里查。"""
        assert nm.tag_lookup("素人") == "业余"                              # info 表
        assert nm.actor_lookup("素人")["canonical_id"] == "amane:素人"       # 演员表
        assert nm.tag_lookup("女优") == ""                                  # info 表：删除规则
        assert nm.actor_lookup("女优")["canonical_id"] == "amane:女优"       # 演员表：一位演员
        for tag in ("10枚組", "單體作品", "苗條", "獨占配信"):
            assert nm.actor_lookup(tag) is None                            # 标签不进演员表

    def test_clean_tags_dedup_and_delete(self, nm):
        tags = ["OL", "巨乳", "苗條", "單體作品", "潮吹", "美少女電影", "白天出軌", "口交",
                "精選綜合", "16小時以上作品", "淫亂真實", "中出", "素人作品", "苗條"]
        assert nm.clean_tags(tags) == ["职业装", "巨乳", "苗条", "单体作品", "潮吹", "美少女",
                                       "白天出轨", "口交", "精选综合", "16小时+", "淫乱真实", "中出"]
        assert nm.clean_tags(["巨乳", "10枚組", "獨占配信", "苗條", "苗条"]) == ["巨乳", "苗条"]

    def test_clean_tags_accepts_dicts_strings_and_limit(self, nm):
        dicts = [{"id": "17", "name": "巨乳"}, {"id": "68", "name": "潮吹"}]
        assert nm.clean_tags(dicts) == ["巨乳", "潮吹"]
        assert nm.clean_tags("巨乳") == ["巨乳"]
        assert nm.clean_tags(None) == [] and nm.clean_tags([]) == []
        assert nm.clean_tags(["巨乳", "潮吹", "中出"], limit=2) == ["巨乳", "潮吹"]

    def test_clean_tags_never_returns_deleted_words(self, nm):
        assert "素人作品" not in nm.clean_tags(["素人作品", "巨乳"])


# ---------------------------------------------------------------- 繁 → 简

class TestToSimplified:
    """`to_simplified()`：只用 `zh2Hans`、正向最大匹配、含假名原样返回、幂等。"""

    #: 真实繁体串（JavDB 实抓 + 映射表 zh_tw）
    SAMPLES = {
        "學校泳裝": "学校泳装", "無碼破解": "无码破解", "單體作品": "单体作品",
        "精選綜合": "精选综合", "淫亂真實": "淫乱真实", "戲劇": "戏剧", "苗條": "苗条",
        "美少女電影": "美少女电影", "白天出軌": "白天出轨", "觸摸打字": "触摸打字",
    }

    def test_real_traditional_samples(self, nm):
        for source, expect in self.SAMPLES.items():
            assert nm.to_simplified(source) == expect

    def test_fmm_beats_per_char(self, nm):
        """`么九` 是词组规则：FMM → `幺九`，逐字替换只会给 `么九`。"""
        assert nm.to_simplified("么九") == "幺九"
        assert nm.to_simplified("一釐") == "一厘"
        assert nm.to_simplified("（么九）") == "（幺九）"          # 词组嵌在标点之间也认得出来

    def test_kana_text_returns_unchanged(self, nm):
        """含假名的日文串一个字都不许动（REPORT-4 §4.4 的反例）。"""
        japanese = "一ヶ月間の禁欲の果てに彼女のルームメイト2人と浮気SEXだけに没頭した彼女不在の3日間。"
        assert nm.to_simplified(japanese) == japanese
        for text in ("素人(萬引き娘)", "は別人", "みながわ千遥", "トニー大木"):
            assert nm.to_simplified(text) == text
        # 反证：把假名拿掉，同样的字就会被转换（说明保护来自"含假名"这条判据）
        assert nm.to_simplified("間違頭痛") == "间违头痛"
        assert nm.to_simplified("萬里") == "万里"

    def test_only_zh2hans_is_used(self, nm):
        """`zh2TW`/`zh2HK`/`zh2CN` 是换词不是换字形，用了会得到 `軟件`/`滑鼠`。"""
        assert nm.to_simplified("軟體") == "软体"
        assert nm.to_simplified("鼠标") == "鼠标"
        assert nm.to_simplified("硬碟") == "硬碟"

    def test_idempotent(self, nm):
        for text in list(self.SAMPLES) + ["么九", "幺九", "間違頭痛", "一ヶ月間の禁欲", "巨乳", "OL"]:
            once = nm.to_simplified(text)
            assert nm.to_simplified(once) == once

    def test_empty_inputs(self, nm):
        assert nm.to_simplified("") == ""
        assert nm.to_simplified(None) == ""


# ---------------------------------------------------------------- 资源缺失 / 用户覆盖

class TestResourcesAndDegrade:
    """资源解析走 `paths.resource_file()`（用户覆盖优先，D3）；缺失只降级不抛异常。"""

    @pytest.fixture
    def real_tables(self, nm):
        """用完夹具资源后**无条件**换回随包真实资源（断言中途失败也不会污染后续用例）。"""
        yield
        nm.load(force=True)
        assert nm.stats()["actors"] == 5351

    def test_missing_resources_degrade(self, nm, real_tables):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(nm, "_resource_path", lambda name: Path("Z:/nope") / name)
            nm.load(force=True)
            assert nm.ready() is False
            assert nm.stats()["actors"] == 0 and nm.stats()["tags"] == 0
            assert nm.stats()["ready"] == 0 and nm.stats()["loaded"] == 1
            assert nm.actor_lookup("三上悠亜") is None
            assert nm.actor_lookup_all("三上悠亜") == []
            assert nm.tag_lookup("巨乳") is None
            assert nm.clean_tags(["巨乳", "10枚組"]) == ["巨乳", "10枚組"]   # 转换退化 → 原样
            assert nm.to_simplified("學校泳裝") == "學校泳裝"
            assert nm.actor_glossary(["三上悠亜"]) == {}
            assert nm.sync_store(None) == 0

    def test_user_override_directory_wins(self, nm, tmp_path, real_tables):
        """`{data_root}/resources/` 里的同名文件优先于随包内置那份（D3）。"""
        paths_mod = sys.modules[f"{PKG_NAME}.paths"]
        override = tmp_path / "resources"
        override.mkdir(parents=True)
        (override / "mapping_actor.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><actor>'
            '<a zh_cn="测试演员" zh_tw="測試演員" jp="テスト俳優" keyword=",テスト俳優," '
            'href="https://javdb.com/actors/TEST1"/></actor>', encoding="utf-8")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(paths_mod, "_DATA_ROOT", tmp_path)
            nm.load(force=True)
            assert nm.stats()["actors"] == 1
            assert nm.actor_lookup("テスト俳優")["canonical_id"] == "amane:测试演员"

    def test_synthetic_tables(self, nm, tmp_path, real_tables):
        """受控小夹具：解析、标记排除、删除规则、转简键、canonical_id 防撞一次跑全。"""
        (tmp_path / "mapping_actor.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><actor>'
            '<a zh_cn="甲" zh_tw="甲" jp="コウ" keyword=",コウ,甲,甲【誤認注意】,【同名異人】," '
            'href="https://javdb.com/actors/AAA"/></actor>', encoding="utf-8")
        (tmp_path / "mapping_info.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><info>'
            '<a zh_cn="删除" zh_tw="删除" jp="删除" keyword=",ノイズ,"/>'
            '<a zh_cn="單體作品" zh_tw="單體作品" jp="単体作品" keyword=",単体作品,"/>'
            '</info>', encoding="utf-8")
        (tmp_path / "zhcdict.json").write_text(
            '{"zh2Hans": {"單": "单", "體": "体", "么九": "幺九"}, "zh2TW": {"鼠标": "滑鼠"}}',
            encoding="utf-8")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(nm, "_resource_path", lambda name: tmp_path / name)
            nm.load(force=True)
            assert nm.ready() is True
            assert nm.stats()["actors"] == 1 and nm.stats()["tag_records"] == 2
            assert nm.stats()["marker_aliases"] == 2        # `甲【誤認注意】` + 纯标记 `【同名異人】`
            assert nm.stats()["empty_aliases"] == 1         # 纯标记那条归一化后为空（两类都数它）
            assert nm.stats()["delete_rules"] == 1
            assert nm.actor_lookup("甲")["javdb_actor_id"] == "AAA"
            assert nm.actor_lookup("甲【誤認注意】") is None   # 标记别名整条不入索引
            assert nm.tag_lookup("ノイズ") == ""
            assert nm.tag_lookup("單體作品") == "單體作品"      # 夹具表里就是自己
            assert nm.to_simplified("么九") == "幺九"
            assert nm.clean_tags(["ノイズ", "單體作品"]) == ["單體作品"]


# ---------------------------------------------------------------- 入库同步

class _FakeStore:
    """最小假 store：列现状 + 按 `canonical_id` 合并，并复刻 S1 的 user_custom 保护。"""

    def __init__(self, with_list: bool = True):
        self.rows = {}
        self.calls = 0
        self._with_list = with_list

    def namemap_bulk_upsert(self, rows):
        self.calls += 1
        written = 0
        for row in rows or []:
            cid = row["canonical_id"]
            old = self.rows.get(cid)
            if old and old.get("source") == "user_custom" and row.get("source") != "user_custom":
                continue
            self.rows[cid] = dict(row)
            written += 1
        return written

    def namemap_list(self, **kwargs):
        if not self._with_list:
            raise AttributeError("不支持")
        return [dict(row) for row in self.rows.values()]


class TestSyncStore:
    """`sync_store()`：幂等、绝不覆盖 `user_custom`、store 缺失不抛异常。"""

    def test_fake_store_is_idempotent(self, nm):
        fake = _FakeStore()
        assert nm.sync_store(fake) == nm.stats()["sync_rows"] == 5698
        assert nm.sync_store(fake) == 0                     # 库里已有内置行 → 幂等返回 0
        assert fake.calls == 1
        assert len(fake.rows) == 5698

    def test_fake_store_never_overwrites_user_custom(self, nm):
        fake = _FakeStore()
        nm.sync_store(fake)
        fake.rows["amane:三上悠亚"] = {
            "canonical_id": "amane:三上悠亚", "entity_type": "actor",
            "zh_cn": "悠亚", "source": "user_custom",
        }
        written = nm.sync_store(fake, force=True)           # force 也不许覆盖用户行
        assert written == 5697
        assert fake.rows["amane:三上悠亚"]["zh_cn"] == "悠亚"
        assert fake.rows["amane:三上悠亚"]["source"] == "user_custom"

    def test_rows_shape(self, nm):
        fake = _FakeStore()
        nm.sync_store(fake)
        actor = fake.rows["amane:三上悠亚"]
        assert set(actor) >= {"canonical_id", "entity_type", "zh_cn", "zh_tw", "jp",
                              "keywords_norm", "javdb_actor_id", "source"}
        assert actor["entity_type"] == "actor" and actor["source"] == "builtin_xml"
        assert "三上悠亜" in actor["keywords_norm"]
        assert fake.rows["amane:del:10枚組"]["is_delete_rule"] == 1
        assert fake.rows["amane:tag:单体作品"]["entity_type"] == "tag"
        # canonical_id 唯一（42 条删除记录全是 zh_cn='删除'，必须各自成行）
        assert len(fake.rows) == len({row["canonical_id"] for row in fake.rows.values()})

    def test_store_without_listing_still_imports(self, nm):
        """store 探不到现状时退化成每次重灌（幂等性靠 upsert 自己的合并语义）。"""
        class _Bare:
            def __init__(self):
                self.rows = {}

            def namemap_bulk_upsert(self, rows):
                self.rows.update({row["canonical_id"]: row for row in rows or []})
                return len(rows or [])

        bare = _Bare()
        assert nm.sync_store(bare) == 5698
        assert len(bare.rows) == 5698                       # 行数不翻倍

    def test_missing_or_broken_store_is_swallowed(self, nm):
        assert nm.sync_store(None) == 0
        assert nm.sync_store(object()) == 0                 # 没有 namemap_bulk_upsert

        class _Boom:
            def namemap_list(self):
                raise RuntimeError("库坏了")

            def namemap_bulk_upsert(self, rows):
                raise RuntimeError("写不进去")

        assert nm.sync_store(_Boom()) == 0

    def test_real_store_round_trip(self, nm, store_mod, tmp_path):
        """对 S1 真实的 `Store` 跑一遍：整词匹配、幂等、用户行保护（契约 §3.2 的接口）。"""
        store = store_mod.Store(db_path=tmp_path / "namemap.db")
        store.init()
        assert nm.sync_store(store) == 5698
        assert nm.sync_store(store) == 0
        assert store.namemap_get("amane:三上悠亚")["zh_cn"] == "三上悠亚"
        found = store.namemap_find("actor", "三上悠亜")       # 日文原名也要能整词命中
        assert found and found["canonical_id"] == "amane:三上悠亚"
        cid = store.namemap_user_set("actor", "三上悠亚", "三上悠亜")
        assert cid == "amane:三上悠亚"
        assert nm.sync_store(store, force=True) == 5697     # 用户行被挡在 upsert 之外
        assert store.namemap_get(cid)["source"] == "user_custom"
