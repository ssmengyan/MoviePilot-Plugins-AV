"""`number_classify` 的回归（0.8.0 P0-0：内容类型 / 马赛克 / 分集 / 分辨率）。

词表在测试里**再独立抄一遍**（两边不一致就是有人抄错了）—— 这是这套"事实性数据"唯一
能自查的办法。上游坐标：`sqzw-x/amane` `src/amane/parsing/file_info.py`（GPL-3.0）。

三处**有意差异**（见 `number_classify.py` 模块 docstring，这里各有用例钉住）：
推不出落 `censored` 而非 `western`；`-U/-UC` 记 `leaked` 而非 `cracked`；不认 `getchu` 目录兜底。
"""

from __future__ import annotations

import pytest

# --- 独立转录的上游词表（file_info.py:83-204）--------------------------------

#: `_UNCENSORED_PREFIXES`（47 条，file_info.py:83-130）
UNCENSORED = (
    "BT-", "CT-", "EMP-", "CCDV-", "CWP-", "CWPBD-", "DSAM-", "DRC-", "DRG-", "GACHI-",
    "HEYDOUGA", "JAV-", "LAF-", "LAFBD-", "HEYZO-", "KTG-", "KP-", "KG-", "LLDV-", "MCDV-",
    "MKD-", "MKBD-", "MMDV-", "NIP-", "PB-", "PT-", "QE-", "RED-", "RHJ-", "S2M-",
    "SKY-", "SKYHD-", "SMD-", "SSDV-", "SSKP-", "TRG-", "TS-", "XXX-AV-", "YKB-", "BIRD",
    "BOUGA", "H4610-", "C0930-", "H0930-", "S2M", "MCB3D",
)

#: `_SUREN_PREFIXES`（5 条，file_info.py:132-138）
SUREN = {"LUXU-": "259LUXU-", "ARA-": "200GANA-", "MIUM-": "300MIUM-",
         "NTK-": "300NTK-", "MAAN-": "300MAAN-"}

#: `_WESTERN_NAMES`（13 条，file_info.py:140-154）
WESTERN = {"vixen": "Vixen", "blacked": "Blacked", "tushy": "Tushy", "sexart": "SexArt",
           "x-art": "X-Art", "nubilefilms": "NubileFilms", "babes": "Babes",
           "wgp": "WhenGirlsPlay", "twistys": "Twistys", "deeper": "Deeper",
           "slayed": "Slayed", "tushy raw": "TushyRaw", "blackedraw": "BlackedRaw"}

#: `_MOSAIC_DIR_TOKENS`（7 条，file_info.py:193-204）
MOSAIC_DIRS = {"uncensored": "uncensored", "無碼": "uncensored", "无码": "uncensored",
               "cracked": "cracked", "破解": "cracked", "leaked": "leaked", "流出": "leaked"}


@pytest.fixture(scope="module")
def mod(classify_mod):
    """`number_classify` 模块（走 conftest 的 `classify_mod`）。"""
    return classify_mod


# --- 词表本身 ---------------------------------------------------------------

def test_tables_match_upstream(mod):
    assert set(mod.UNCENSORED_PREFIXES) == set(UNCENSORED)
    # ⚠️ 是 **46** 条：早先手抄成"47 条"（清单与 amane 笔记里也这么写过），按上游
    # `file_info.py:83-130` 逐行数就是 46（`S2M-` 与 `S2M`、`MCB3D` 这类都在其中）。
    assert len(mod.UNCENSORED_PREFIXES) == 46 == len(UNCENSORED)
    assert len(set(UNCENSORED)) == 46
    assert mod.SUREN_PREFIXES == SUREN
    assert mod.WESTERN_NAMES == WESTERN
    assert mod.MOSAIC_DIR_TOKENS == MOSAIC_DIRS
    assert mod.CONTENT_TYPES == ("censored", "uncensored", "chinese", "western", "fc2",
                                 "amateur", "hentai")
    assert mod.MOSAIC_VALUES == ("censored", "uncensored", "cracked", "leaked")
    assert mod.DEFINITION_VALUES == ("8K", "4K", "1440p", "1080p", "720p", "480p", "HD", "SD")


# --- 类型：无码前缀白名单（47 条逐条）---------------------------------------

@pytest.mark.parametrize("prefix", UNCENSORED)
def test_every_uncensored_prefix(mod, prefix):
    kind, why = mod.type_from_number(f"{prefix}1234")
    assert kind == "uncensored", f"{prefix} → {kind} / {why}"
    assert why.startswith("prefix:")


# --- 类型：素人 / FC2 / 国产 / 日期号 / 目录关键词 ---------------------------

@pytest.mark.parametrize("key", sorted(SUREN))
def test_suren_prefixes(mod, key):
    kind, why = mod.type_from_number(f"{key}123")
    assert kind == "amateur" and why == f"suren:{key}"


@pytest.mark.parametrize("number", ["SIRO-4321", "300MIUM-123", "200GANA-1234"])
def test_amateur_shapes(mod, number):
    kind, why = mod.type_from_number(number)
    assert kind == "amateur", f"{number} → {kind} / {why}"


@pytest.mark.parametrize("number", ["FC2-1234567", "FC2PPV-1234567", "FC21234567",
                                    "fc2-ppv-1234567"])
def test_fc2(mod, number):
    assert mod.type_from_number(number)[0] == "fc2"


@pytest.mark.parametrize("number", ["MD0165", "MD0165-1", "MD-0123", "MKY-AB-123"])
def test_chinese(mod, number):
    kind, why = mod.type_from_number(number)
    assert kind == "chinese", f"{number} → {kind} / {why}"


def test_mdvr_is_not_chinese(mod):
    """上游明确排除 `MDVR`（VR 国产片走另一条链），别"顺手"把它当国产。"""
    assert mod.type_from_number("MDVR1234")[0] == "censored"


@pytest.mark.parametrize("number", ["010115_001", "010115-001", "120115_318"])
def test_six_digit_catalog(mod, number):
    """六位目录号是**无码**系；`_` 与 `-` 在这里都算分隔符（与"比对键不折叠 `_`"不冲突：
    那是比对口径，这是形态识别）。"""
    assert mod.type_from_number(number)[0] == "uncensored"


@pytest.mark.parametrize("number", ["N1234", "N0123"])
def test_n_series(mod, number):
    assert mod.type_from_number(number)[0] == "uncensored"


@pytest.mark.parametrize("number", ["Blacked.16.07.09", "Studio.2025.07.09", "Tushy.24.01.02"])
def test_western_date(mod, number):
    """欧美日期号 → `western`：上游真链路（`_match:448-456`）也是这个结论。

    ⚠️ 番号**改写**（`blacked.16.07.09 → Blacked.16.07.09`）不在这里做，见清单 P1-1(b)。"""
    kind, why = mod.type_from_number(number)
    assert kind == "western" and why == "western-date"


@pytest.mark.parametrize("number", ["KIN8-123", "KIN8TENGOKU-123", "KIN8123"])
def test_kin8_is_western(mod, number):
    """单厂牌 KIN8 归欧美链（上游 `_match:477-478`）：类型表示**路由归属**，与马赛克标记正交。"""
    kind, why = mod.type_from_number(number)
    assert kind == "western" and why == "kin8"


@pytest.mark.parametrize("number", ["IPZZ-961", "SNOS-380", "MIDV-946", "ssis-001"])
def test_plain_catalog_is_censored(mod, number):
    kind, why = mod.type_from_number(number)
    assert kind == "censored" and why in ("catalog", "default")


@pytest.mark.parametrize("number", ["", "ABC123", "zzz", None])
def test_unknown_falls_back_to_censored(mod, number):
    """★ 差异 1：上游落 `western`，我们落 `censored`（默认链）。

    猜成欧美会把片子送进一条**没有源能用**的链；"不许猜"是落默认链，不是随便挑一条。
    """
    assert mod.type_from_number(number)[0] == "censored"


@pytest.mark.parametrize("dirs,expect", [
    (("欧美",), "western"),
    (("里番",), "hentai"),
    (("裏番",), "hentai"),
    (("getchu",), "hentai"),
    (("欧美合集",), "western"),
    (("/", ".", ""), ""),                       # 根/空段不算关键词
])
def test_path_keywords(mod, dirs, expect):
    kind, _why = mod.type_from_path(*dirs)
    assert kind == expect


def test_path_keywords_must_be_at_segment_start(mod):
    """上游 `_classify_from_path` 的段首要求：`这里番号` / `非欧美` 不许命中。"""
    assert mod.type_from_path("这里番号")[0] == ""
    assert mod.type_from_path("非欧美")[0] == ""
    assert mod.type_from_path("欧美")[0] == "western"


def test_dir_keyword_beats_number_shape(mod):
    """目录关键词优先（上游同序）：欧美目录里的普通目录号也算欧美。"""
    kind, why = mod.content_type("IPZZ-961", dirs=("欧美",))
    assert kind == "western" and why.startswith("dir:")
    assert mod.content_type("IPZZ-961")[0] == "censored"


def test_media_extension_is_stripped(mod):
    assert mod.type_from_number("HEYZO-1234.mp4")[0] == "uncensored"
    assert mod.type_from_number("MD0165.mkv")[0] == "chinese"


# --- 马赛克 -----------------------------------------------------------------

@pytest.mark.parametrize("name,expect", [
    ("ABC-123-破解", "cracked"),
    ("ABC-123-克破", "cracked"),
    ("ABC-123-CRACKED", "cracked"),
    ("ABC-123-流出", "leaked"),
    ("ABC-123-LEAKED", "leaked"),
    ("ABC-123-無碼", "uncensored"),
    ("ABC-123-无码", "uncensored"),
    ("ABC-123-UNCENSORED", "uncensored"),
])
def test_mosaic_from_name(mod, name, expect):
    assert mod.mosaic(name)[0] == expect


def test_mosaic_priority_cracked_beats_leaked_beats_uncensored(mod):
    """★ 上游硬约束：**破解 > 流出 > 无码**，多标记时按这个顺序取第一个。"""
    assert mod.mosaic("ABC-123-破解-流出-无码")[0] == "cracked"
    assert mod.mosaic("ABC-123-流出-无码")[0] == "leaked"
    assert mod.mosaic("ABC-123-无码")[0] == "uncensored"


def test_mosaic_from_version_tags_uses_leaked(mod):
    """★ 差异 2：`-U/-UC` 记 `leaked`（上游记 `cracked`）—— 沿用 `emby.parse_av_number()`
    的既有口径（`is_uncensored_leak`），不改已有语义。"""
    kind, why = mod.mosaic("IPZZ-961", version_tags={"is_uncensored_leak": True})
    assert kind == "leaked" and why == "tags:-U"


def test_mosaic_from_dirs_inner_first(mod):
    """目录段名：从**最内层**往外找（内层更具体）。"""
    assert mod.mosaic("IPZZ-961", dirs=("无码", "破解"))[0] == "cracked"
    assert mod.mosaic("IPZZ-961", dirs=("破解", "无码"))[0] == "uncensored"
    assert mod.mosaic("IPZZ-961", dirs=("【无码】",))[0] == "uncensored"   # 去括号后整段相等


def test_mosaic_fill_by_content_type(mod):
    """`fill_mosaic`：有码类型 → censored、无码类型 → uncensored，其它类型**留空**。"""
    assert mod.mosaic("IPZZ-961", content="censored")[0] == "censored"
    assert mod.mosaic("HEYZO-1234", content="uncensored")[0] == "uncensored"
    assert mod.mosaic("FC2-1234567", content="fc2")[0] == ""
    assert mod.mosaic("MD0165", content="chinese")[0] == ""
    assert mod.fill_mosaic("censored", "leaked") == "leaked"       # 已有标记不覆盖


# --- 分集 -------------------------------------------------------------------

@pytest.mark.parametrize("name,expect", [
    ("ABC-123-CD2", 2), ("ABC-123_CD1", 1), ("ABC-123.PART3", 3),
    ("ABC-123-A", 1), ("ABC-123-B", 2), ("ABC-123-3", 3),
    ("ABC-123-CD10", 10),                       # 上游 `\d{1,2}`：两位数照样返回
    ("ABC-123", 0),
])
def test_detect_cd(mod, name, expect):
    assert mod.detect_cd(name) == expect


def test_detect_cd_from_parent_dir(mod):
    assert mod.detect_cd("ABC-123", dirs=("CD2",)) == 2
    assert mod.detect_cd("ABC-123", dirs=("part1",)) == 1
    assert mod.detect_cd("ABC-123", dirs=("CD0",)) == 0
    assert mod.detect_cd("ABC-123", dirs=("S1",)) == 0


# --- 分辨率 -----------------------------------------------------------------

@pytest.mark.parametrize("name,expect", [
    ("ABC-123-4K", "4K"),
    ("ABC-123-2160P", "4K"),          # 归一
    ("ABC-123-8K", "8K"),
    ("ABC-123-1440p", "1440p"),
    ("ABC-123-1080p", "1080p"),
    ("ABC-123-1080p60", "1080p"),     # 数字标记允许紧跟帧率
    ("ABC-123-720P", "720p"),
    ("ABC-123-480P", "480p"),
    ("ABC-123-HD", "HD"),
    ("ABC-123-SD", "SD"),
    ("ABC-123-4KS", ""),              # K 后不得再接字母
    ("HD-123", ""),                   # HD 不得是番号前缀
    ("HD_123", ""),                   # 下划线归一成点后同形，同样不认
    ("ABC-123", ""),
])
def test_definition(mod, name, expect):
    assert mod.definition(name) == expect


# --- 一次算全 ---------------------------------------------------------------

def test_classify_full(mod):
    got = mod.classify("HEYZO-1234", version_tags={"is_uncensored_leak": True})
    assert got["content_type"] == "uncensored"
    assert got["mosaic"] == "leaked"          # version_tags 优先于 fill
    assert got["cd"] == 0 and got["definition"] == ""
    assert got["why"]["content_type"].startswith("prefix:")
    assert got["why"]["mosaic"] == "tags:-U"


def test_classify_prefers_name_over_number(mod):
    """`name` 比 `number` 全（可能带后缀标记）→ 分类看 `name`，形态看 `number`。"""
    got = mod.classify("IPZZ-961", name="IPZZ-961-4K-破解.mp4")
    assert got["content_type"] == "censored"      # 形态仍是普通目录号
    assert got["mosaic"] == "cracked"
    assert got["definition"] == "4K"


def test_classify_reads_cd_from_dirs(mod):
    got = mod.classify("ABC-123", dirs=("CD2", "无码"))
    assert got["cd"] == 2 and got["mosaic"] == "uncensored"
