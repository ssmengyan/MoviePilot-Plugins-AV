"""`parse_av_number()` / `canon_key()` 的验收门槛（主统筹写，S2 实现后必须全绿）。

这个文件是 v4.1 §5.1 的**硬性用例**加上实测补充，**不允许为了让实现通过而改期望值**；
实现方只能改 `emby.py`。旧口径的 `norm_key()` 行为也在这里被锁死（D1：语义不变）。
"""

import pytest


def _p(emby_mod, text):
    """跑一次解析，返回 (display, key, tags)。"""
    parsed = emby_mod.parse_av_number(text)
    return parsed.display_number, parsed.norm_key, dict(parsed.version_tags or {})


class TestParseHardCases:
    """v4.1 §5.1 的四条硬性用例 —— 一条都不许改。"""

    def test_uc_leak(self, emby_mod):
        display, key, tags = _p(emby_mod, "IPZZ-912-UC.mp4")
        assert (display, key) == ("IPZZ-912", "IPZZ912")
        assert tags.get("is_zh_sub") is True
        assert tags.get("is_uncensored_leak") is True

    def test_iso_edition_l(self, emby_mod):
        display, key, tags = _p(emby_mod, "IPOK-025L.iso")
        assert (display, key) == ("IPOK-025", "IPOK25")
        assert tags.get("is_iso") is True
        assert tags.get("edition") == "L"

    def test_4k_suffix(self, emby_mod):
        display, key, tags = _p(emby_mod, "CAWD-989_4K.mp4")
        assert (display, key) == ("CAWD-989", "CAWD989")
        assert tags.get("resolution") == "4K"

    def test_plain(self, emby_mod):
        display, key, tags = _p(emby_mod, "CAWB-040.mp4")
        assert (display, key) == ("CAWB-040", "CAWB40")
        assert not tags


class TestParseExtras:
    """实测补充：真实文件名/路径里出现过的形态。"""

    def test_full_path(self, emby_mod):
        assert _p(emby_mod, "/Media/9kg/avi/SNOS-380.mp4")[:2] == ("SNOS-380", "SNOS380")

    def test_domain_watermark(self, emby_mod):
        assert _p(emby_mod, "hhd800.com@MIDV-946.mp4")[:2] == ("MIDV-946", "MIDV946")

    def test_bracket_site_tag(self, emby_mod):
        display, key, tags = _p(emby_mod, "[Thz.la]SSIS-001-C.mp4")
        assert (display, key) == ("SSIS-001", "SSIS1")
        assert tags.get("is_zh_sub") is True

    def test_cd_part(self, emby_mod):
        display, key, tags = _p(emby_mod, "/Media/9kg/avi/MIDV-946-CD2.mkv")
        assert (display, key) == ("MIDV-946", "MIDV946")
        assert int(tags.get("part_no") or 0) == 2

    def test_lowercase(self, emby_mod):
        assert _p(emby_mod, "ipzz-912")[:2] == ("IPZZ-912", "IPZZ912")

    def test_cn_sub_word(self, emby_mod):
        assert _p(emby_mod, "MIDV-946 中字.mp4")[2].get("is_zh_sub") is True

    def test_leak_word(self, emby_mod):
        assert _p(emby_mod, "MIDV-946流出.mp4")[2].get("is_uncensored_leak") is True

    def test_combined_suffixes(self, emby_mod):
        display, key, tags = _p(emby_mod, "SONE-561-UC_4K.mp4")
        assert (display, key) == ("SONE-561", "SONE561")
        assert tags.get("is_zh_sub") is True
        assert tags.get("is_uncensored_leak") is True
        assert tags.get("resolution") == "4K"

    def test_single_letter_suffix(self, emby_mod):
        display, key, tags = _p(emby_mod, "MIRD-277-C.mp4")
        assert (display, key) == ("MIRD-277", "MIRD277")
        assert tags.get("is_zh_sub") is True

    def test_fc2(self, emby_mod):
        # FC2 的规范键**必须**保留 PPV 段：线上台账与 MetaTube 的 ProviderIds 都是 `FC2PPV…`
        assert _p(emby_mod, "FC2-PPV-1234567.mp4")[:2] == ("FC2-PPV-1234567", "FC2PPV1234567")
        assert _p(emby_mod, "FC2PPV1234567.mp4")[:2] == ("FC2-PPV-1234567", "FC2PPV1234567")

    def test_three_digit_keeps_padding(self, emby_mod):
        assert _p(emby_mod, "SSIS-001.mp4")[:2] == ("SSIS-001", "SSIS1")

    @pytest.mark.parametrize("text,expected", [
        # 文件名里多写的前导零**不许**进 display_number：javdb 用 `IPZZ-586` 查得到，
        # 用 `IPZZ-00586` 直接 404（S11 全库实测抓到的真事故，2026-10-14）
        ("ipzz00586_1_4K.mp4", "IPZZ-586"),
        ("IPZZ-00586.mp4", "IPZZ-586"),
        ("MIDV-0946.mp4", "MIDV-946"),
        ("MIDV-0946", "MIDV-946"),
    ])
    def test_extra_leading_zeros_are_normalised(self, emby_mod, text, expected):
        assert _p(emby_mod, text)[0] == expected

    @pytest.mark.parametrize("text", ["", "   ", "sample", "翻译说明", None])
    def test_not_a_number(self, emby_mod, text):
        parsed = emby_mod.parse_av_number(text)
        assert parsed.matched is False
        assert parsed.display_number == ""
        assert parsed.norm_key == ""

    @pytest.mark.parametrize("text", ["12598", "11311", "007", "2026"])
    def test_bare_digits_are_not_numbers(self, emby_mod, text):
        """纯数字串**不是**番号（Emby 实例 id 就长这样，认成番号会把 id 当片子去查站点）。

        实测踩过：`12598`（= SNOS-380 的 Emby id）曾被解析成 `125-098`、`11311`（= JAV 库 id）
        曾成 `113-011`。番号必须有 ≥2 个字母的前缀。
        """
        parsed = emby_mod.parse_av_number(text)
        assert parsed.matched is False, f"{text} 不该被认成番号：{parsed.display_number}"


class TestLegacyCompatibility:
    """D1：`norm_key()` 语义**一个字节都不许变**（downloads/known/前端都按它对齐）。"""

    @pytest.mark.parametrize("text,expected", [
        ("IPZZ-912-UC", "IPZZ912UC"),
        ("ipzz00961", "IPZZ961"),
        ("CAWD-989_4K", "CAWD9894K"),
        ("FC2-PPV-1234567", "FC2PPV1234567"),
        ("MIDV-946-UC", "MIDV946UC"),
        ("CAWB-040", "CAWB40"),
        ("", ""),
    ])
    def test_norm_key_unchanged(self, emby_mod, text, expected):
        assert emby_mod.norm_key(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("IPZZ-912-UC", "IPZZ912"),
        ("CAWD-989_4K", "CAWD989"),
        ("CAWB-040", "CAWB40"),
        ("SNOS-380.mp4", "SNOS380"),
        ("", ""),
    ])
    def test_canon_key_strips_suffixes(self, emby_mod, text, expected):
        assert emby_mod.canon_key(text) == expected

    def test_canon_key_falls_back_to_norm_key(self, emby_mod):
        # 解析不出番号形态时退回旧口径，绝不返回空串（调用方拿它当查询键）
        assert emby_mod.canon_key("SSIS1") == emby_mod.norm_key("SSIS1")
