"""`emby.py` 里那几件纯逻辑的单测：番号展示 / 挑主键 / 库索引 → 「已入库的番号」行。

全都不连 Emby、不碰宿主：`library_rows()` 是纯函数（输入就是 `EmbyLibrary.index()` 那份字典），
`display_number()` / `key_rank()` / `best_keys()` 更是纯字符串与排序规则。
这几条规则 2026-10-12 从 `__init__.py` 搬到 `emby.py`（与 `norm_key()` 同一套番号口径），
搬动本身也就是为了让它们能被这里直接测。
"""

from datetime import datetime, timezone


class TestDisplayNumber:
    """归一化键 → 展示番号。"""

    def test_plain(self, emby_mod):
        assert emby_mod.display_number("IPZZ961") == "IPZZ-961"
        assert emby_mod.display_number("midv946") == "MIDV-946"

    def test_fc2(self, emby_mod):
        assert emby_mod.display_number("FC2PPV1234567") == "FC2-PPV-1234567"

    def test_undecidable_key_is_returned_as_is(self, emby_mod):
        """拼不出来就原样返回 —— 宁可显示得怪一点，也不猜成另一个番号。"""
        assert emby_mod.display_number("SNOS192C") == "SNOS192C"
        assert emby_mod.display_number("SSIS1") == "SSIS1"
        assert emby_mod.display_number("") == ""


class TestKeyRank:
    """同一部片多个键时挑哪个（小者优先）。"""

    def test_canonical_before_suffixed(self, emby_mod):
        assert emby_mod.key_rank("IPZZ961") < emby_mod.key_rank("IPZZ961C")

    def test_shorter_wins_between_two_non_canonical(self, emby_mod):
        assert emby_mod.key_rank("SNOS192") < emby_mod.key_rank("SNOS192C")

    def test_stable_for_same_index(self, emby_mod):
        """同一份索引每次挑出同一个键（否则列表与台账会今天一个明天一个）。"""
        keys = ["SNOS192C", "SNOS192", "SNOS1924K"]
        assert sorted(keys, key=emby_mod.key_rank) == ["SNOS192", "SNOS192C", "SNOS1924K"]


class TestBestKeys:
    """按键展开的索引 → 一部片一个键。"""

    def test_merges_keys_of_one_item(self, emby_mod):
        index = {
            "SNOS192": {"id": "1", "name": "A"},
            "SNOS192C": {"id": "1", "name": "A"},      # 同一部片的中字版键
            "IPZZ961": {"id": "2", "name": "B"},
        }
        assert emby_mod.best_keys(index) == {"1": "SNOS192", "2": "IPZZ961"}

    def test_keeps_index_order(self, emby_mod):
        """顺序 = 索引顺序（索引本身按 Emby 的 DateCreated 倒序抓），界面靠它做「最近入库在前」。"""
        index = {"AAA111": {"id": "1"}, "BBB222": {"id": "2"}, "CCC333": {"id": "3"}}
        assert list(emby_mod.best_keys(index)) == ["1", "2", "3"]

    def test_skips_non_dict_and_keyless_entries(self, emby_mod):
        index = {"AAA111": "坏数据", "BBB222": {"id": "2"}}
        assert emby_mod.best_keys(index) == {"2": "BBB222"}


class TestEmbyTimeText:
    """Emby 的 DateCreated（7 位小数 + Z）→ 本地 `YYYY-MM-DD HH:MM:SS`。"""

    def test_empty_and_garbage(self, emby_mod):
        assert emby_mod.emby_time_text("") == ""
        assert emby_mod.emby_time_text("不是时间") == ""

    def test_seven_digit_fraction_parses_as_utc(self, emby_mod):
        got = emby_mod.emby_time_text("2026-10-05T04:34:56.0000000Z")
        want = (datetime.fromisoformat("2026-10-05T04:34:56+00:00")
                .astimezone(timezone.utc).astimezone()
                .strftime("%Y-%m-%d %H:%M:%S"))
        assert got == want and got


class TestLibraryRows:
    """库索引 → `/library` 的 items[]（契约 §4）。"""

    INDEX = {
        "IPZZ961": {
            "id": "12334",
            "name": "IPZZ-961 某部片",
            "path": "/media/9kg/avi/IPZZ-961.mp4",
            "url": "http://emby:8096/web/index.html#!/item?id=12334&serverId=abc",
            "created": "2026-10-05T04:34:56.0000000Z",
        },
    }

    def test_shape(self, emby_mod):
        rows = emby_mod.library_rows(self.INDEX, {"IPZZ-961": "/img?url=x"}, {"IPZZ-961": "演员A"})
        assert len(rows) == 1
        row = rows[0]
        assert row["number"] == "IPZZ-961"
        assert row["title"] == "IPZZ-961 某部片"
        assert row["thumb"] == "/img?url=x"
        assert row["actor"] == "演员A"
        assert row["lib"] == {
            "id": "12334",
            "name": "IPZZ-961 某部片",
            "path": "/media/9kg/avi/IPZZ-961.mp4",
            "url": "http://emby:8096/web/index.html#!/item?id=12334&serverId=abc",
        }
        assert row["addedAt"] == emby_mod.emby_time_text("2026-10-05T04:34:56.0000000Z")

    def test_javdb_id_left_empty(self, emby_mod):
        """`movie.id` 必须是 **javdb 内部 id**；这里只有 Emby 的 id，塞进去会让 /detail 找个不存在的片。"""
        row = emby_mod.library_rows(self.INDEX)[0]
        assert row["id"] == ""
        assert row["lib"]["id"] == "12334"

    def test_library_only_fields_are_blank(self, emby_mod):
        """发行日 / 时长 / 磁力库列表里没有（要先抓详情），一律留空而不是编一个 0 骗卡片。"""
        row = emby_mod.library_rows(self.INDEX)[0]
        assert row["date"] == "" and row["duration"] == 0 and row["magnets"] == 0
        assert row["cover"] == "" and row["cnsub"] is False and row["uncensored"] is False

    def test_thumb_lookup_falls_back_to_normalised_key(self, emby_mod):
        """封面索引两种写法都要认：javdb 口径 `IPZZ-961` 与 Emby 归一化键 `IPZZ961`。"""
        assert emby_mod.library_rows(self.INDEX, {"IPZZ961": "/img?url=y"})[0]["thumb"] == "/img?url=y"

    def test_empty_index(self, emby_mod):
        assert emby_mod.library_rows({}) == []
        assert emby_mod.library_rows(None) == []
