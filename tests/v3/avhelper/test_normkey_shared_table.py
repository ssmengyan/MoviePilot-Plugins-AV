"""番号归一化：前端 `normKey()` 与后端 `emby.norm_key()` **共用一份用例表**（0.9.3 D2）。

表在 `plugins.v3/avhelper/frontend/tests/normkey-cases.json`，前端 `tests/norm-key.test.ts`
读的是同一个文件。两边算法一旦漂开（例如谁动了「抹数字段前导零」），后端或前端单测就会红。

为什么值得单独一条：台账行的 key、Emby 索引的键、演员匹配全靠这条口径对齐；漂了之后
症状是「一部片在库里、下载历史里也有一条，两边却对不上」——最难查的一类静默错。
"""

import json
from pathlib import Path

CASES = (Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper" / "frontend"
         / "tests" / "normkey-cases.json")


def test_shared_case_table_is_not_empty():
    data = json.loads(CASES.read_text(encoding="utf-8"))
    assert len(data.get("cases") or []) >= 8


def test_norm_key_matches_the_shared_table(emby_mod):
    data = json.loads(CASES.read_text(encoding="utf-8"))
    mismatched = [
        (item["input"], item["key"], emby_mod.norm_key(item["input"]))
        for item in data["cases"]
        if emby_mod.norm_key(item["input"]) != item["key"]
    ]
    assert mismatched == [], f"后端 emby.norm_key() 与共用用例表不一致：{mismatched}"
