"""v4 刮削线 `store.py` 新增能力的单测。

覆盖范围（对应 S1 的交付口径）：
- SQLite 连接升级：WAL / per-connection PRAGMA / 线程本地长连接 / 写仍持锁 / 读不排队 /
  库文件被换掉后按需重开（不做僵尸）；
- 五张新表（`meta` / `media_item` / `name_map` / `translate` / `scrape_log`）的建表与 CRUD；
- `downloads` 三个新列（`version_tags` / `emby_id` / `failed_reason`）的补列与合并口径；
- 迁移：`actor_alias` → `name_map(source='user_custom')` 幂等；
- `resolve_actor_keys()` 的汉化前后覆盖。

全部落在 pytest 的临时目录，不碰真实缓存盘；不依赖插件包 `__init__.py`（无宿主环境）。
"""

import os
import sqlite3
import sys
import threading
import types
from pathlib import Path


def make_store(store_mod, tmp_path, name="avhelper.db"):
    """在临时目录上建一个干净的库。"""
    store = store_mod.Store(db_path=tmp_path / name)
    store.init()
    return store


# 线上老库的 downloads 表长这样（照 `_tmp/recon/avh_live.db` 的 PRAGMA table_info 抄），
# 与 v4 的差别只有 hidden 之后的三列 —— 单测里的"老库"夹具必须与真实形状一致，
# 否则测的是自己编的表，而不是迁移真会撞上的那张表。
LEGACY_DOWNLOADS_DDL = """
CREATE TABLE downloads(
  key TEXT PRIMARY KEY, number TEXT DEFAULT '', title TEXT DEFAULT '', actor TEXT DEFAULT '',
  thumb TEXT DEFAULT '', size INTEGER DEFAULT 0, hash TEXT DEFAULT '', path TEXT DEFAULT '',
  downloader TEXT DEFAULT '', state TEXT DEFAULT 'downloading', source TEXT DEFAULT 'plugin',
  created_at TEXT DEFAULT '', completed_at TEXT DEFAULT '', updated_at TEXT DEFAULT '',
  hidden INTEGER DEFAULT 0)
"""


def columns_of(store, table):
    """通过 Store 自己那条长连接读表结构（PRAGMA 是 per-connection 的，别另开连接看）。"""
    return {r[1] for r in store._connect().execute(f"PRAGMA table_info({table})").fetchall()}


def tables_of(store):
    rows = store._connect().execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


class TestConnectionUpgrade:
    """连接模型：WAL + 线程本地长连接 + 写锁不变 + 库文件被换掉后重开。"""

    def test_wal_and_pragmas(self, store_mod, tmp_path):
        """`init()` 之后：journal_mode=wal、busy_timeout/synchronous/foreign_keys 都设上了。"""
        store = make_store(store_mod, tmp_path)
        conn = store._connect()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1        # NORMAL
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_wal_files_appear(self, store_mod, tmp_path):
        """WAL 生效的旁证：写过一次之后 `-wal` / `-shm` 文件真的出现在盘上。"""
        store = make_store(store_mod, tmp_path)
        store.kv_set("k", "v")
        assert Path(str(store.db_path) + "-wal").exists()
        assert Path(str(store.db_path) + "-shm").exists()

    def test_connection_is_thread_local(self, store_mod, tmp_path):
        """同线程复用同一条连接；**另一个线程拿到的是另一条**（连接不能跨线程复用）。"""
        store = make_store(store_mod, tmp_path)
        mine = store._connect()
        assert store._connect() is mine                     # 复用了同一条

        other = {}

        def worker():
            other["conn"] = store._connect()
            other["again"] = store._connect()
            store.kv_set("from_thread", 1)                  # 别的线程写也要能跑

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(10)
        assert other["conn"] is other["again"]               # 那个线程自己也复用
        assert other["conn"] is not mine                     # 但与本线程这条不是同一个
        assert store.kv_get("from_thread") == 1

    def test_writes_take_the_lock_reads_do_not(self, store_mod, tmp_path):
        """写必须排在同一把锁后面；读不再排队（WAL 升级的动机就在这）。"""
        store = make_store(store_mod, tmp_path)
        store.kv_set("k", "v")

        store._lock.acquire()                                # 主线程霸占写锁
        try:
            wrote = threading.Event()
            read = {}

            def writer():
                store.kv_set("blocked", 1)
                wrote.set()

            def reader():
                read["value"] = store.kv_get("k")
                read["done"] = True

            wt = threading.Thread(target=writer)
            wt.start()
            rt = threading.Thread(target=reader)
            rt.start()
            rt.join(5)
            assert read.get("done") is True                  # 读没被写锁挡住
            assert read.get("value") == "v"
            assert not wrote.wait(0.3)                        # 写被锁挡住了
        finally:
            store._lock.release()
        assert wrote.wait(5)                                 # 放锁后写完成
        assert store.kv_get("blocked") == 1

    def test_first_touch_on_missing_db_bootstraps(self, store_mod, tmp_path):
        """库文件不存在（甚至目录都不存在）时第一次调用就能用：建库 + 建表一条龙。"""
        db = tmp_path / "deep" / "avhelper.db"
        store = store_mod.Store(db_path=db)                  # 刻意不调 init()
        store.kv_set("k", "v")
        assert store.kv_get("k") == "v"
        assert store.meta_stats()["total"] == 0              # 五张新表也建好了

    def test_reopens_after_db_file_swapped(self, store_mod, tmp_path):
        """`docker cp` 换掉库文件后不能变僵尸：认出文件身份变了 → 重开 → 读到的是**新库**。"""
        db = tmp_path / "avhelper.db"
        store = store_mod.Store(db_path=db)
        store.init()
        store.kv_set("who", "old")
        assert store.kv_get("who") == "old"

        incoming = tmp_path / "incoming.db"
        fresh = store_mod.Store(db_path=incoming)
        fresh.init()
        fresh.kv_set("who", "new")
        fresh.close()                                        # 放开文件，才能在 Windows 上换过去

        # 把旧连接关掉但**保留 Store 记住的文件身份**：这一刻它就是"指着已删除 inode 的僵尸"
        store._local.conn.close()
        os.replace(incoming, db)
        for suffix in ("-wal", "-shm"):
            stale = Path(str(db) + suffix)
            if stale.exists():
                stale.unlink()

        assert store.kv_get("who") == "new"                  # 重开到新库，读的是新内容
        store.kv_set("after", 1)
        assert store.kv_get("after") == 1
        assert store._local.ident == store._db_ident()       # 身份记录也刷新了

    def test_stale_ident_forces_reconnect(self, store_mod, tmp_path):
        """身份对不上就重开（不依赖文件是否真被换过）—— 这就是重开判据本身。"""
        store = make_store(store_mod, tmp_path)
        store.kv_set("k", "v")
        old_conn = store._connect()
        store._local.ident = ("stale", 0)                    # 伪造"文件已经不是当初那个"
        assert store._connect() is not old_conn
        assert store.kv_get("k") == "v"                      # 数据一条不少


class TestSchemaUpgrade:
    """五张新表 + `downloads` 动态补列（幂等）。"""

    V4_TABLES = ("meta", "media_item", "name_map", "translate", "scrape_log")

    def test_new_tables_created(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        tables = tables_of(store)
        for name in self.V4_TABLES:
            assert name in tables

    def test_media_item_indexes(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        rows = store._connect().execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert {"idx_media_item_key", "idx_media_item_emby"} <= names

    def test_downloads_v4_columns(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert {"version_tags", "emby_id", "failed_reason"} <= columns_of(store, "downloads")

    def test_legacy_db_gets_v4_columns_and_keeps_rows(self, store_mod, tmp_path):
        """老库（没有这三列 / 没有新表）跑一次 init()：补列、建表、老行一条不动。"""
        db = tmp_path / "legacy.db"
        with sqlite3.connect(db) as conn:
            conn.executescript(LEGACY_DOWNLOADS_DDL)
            conn.execute("INSERT INTO downloads(key, number, title) VALUES('IPZZ961','IPZZ-961','老片')")
        store = store_mod.Store(db_path=db)
        store.init()
        assert {"version_tags", "emby_id", "failed_reason"} <= columns_of(store, "downloads")
        rows = store.download_list()
        assert len(rows) == 1 and rows[0]["title"] == "老片"
        assert rows[0]["version_tags"] == "{}" and rows[0]["emby_id"] == ""

    def test_init_is_idempotent(self, store_mod, tmp_path):
        """反复 init()：老表行数不变、新表不重复建、迁移不重复插。"""
        db = tmp_path / "avhelper.db"
        store = store_mod.Store(db_path=db)
        store.init()
        store.fav_add("演员A", "甲", "")
        store.alias_set("演员A", "小甲")
        store.known_add("IPZZ-961")
        before = (len(store.fav_list()), len(store.known_all()), len(store.alias_map()),
                  len(store.namemap_list()))
        for _ in range(3):
            store.init()
        after = (len(store.fav_list()), len(store.known_all()), len(store.alias_map()),
                 len(store.namemap_list()))
        assert before == after


class TestMeta:
    """作品级元数据（`meta`）。"""

    def test_upsert_only_overwrites_passed_fields(self, store_mod, tmp_path):
        """只覆盖传进来的字段：这一轮没拿到的字段绝不能被"顺手写空"。"""
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("IPZZ912", display_number="IPZZ-912", title_jp="日文原标题",
                          plot_zh="中文简介", actors_json=[{"zh": "三上悠亚"}],
                          completeness="missing_plot")
        store.meta_upsert("IPZZ912", title_zh="中文标题")          # 这轮只有标题
        row = store.meta_get("IPZZ912")
        assert row["display_number"] == "IPZZ-912"
        assert row["title_jp"] == "日文原标题"                      # 没传 → 保住
        assert row["plot_zh"] == "中文简介"
        assert row["title_zh"] == "中文标题"
        assert row["actors"] == [{"zh": "三上悠亚"}]                # JSON 列给解析副本
        assert row["actors_json"] == '[{"zh": "三上悠亚"}]'         # 原始串也在
        assert row["updated_at"]

    def test_explicit_empty_string_clears(self, store_mod, tmp_path):
        """想清空某列必须**显式传空串**（这是唯一的口子）。"""
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("IPZZ912", display_number="IPZZ-912", plot_zh="旧简介")
        store.meta_upsert("IPZZ912", plot_zh="")
        assert store.meta_get("IPZZ912")["plot_zh"] == ""

    def test_insert_fills_table_defaults(self, store_mod, tmp_path):
        """行不存在时按建表默认值补全后插入（display_number 缺省拿 key 兜底）。"""
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("SNOS380")
        row = store.meta_get("SNOS380")
        assert row["display_number"] == "SNOS380"
        assert row["translation_status"] == "untranslated"
        assert row["completeness"] == "missing_core"
        assert row["actors_json"] == "[]" and row["raw_json"] == "{}"
        assert row["retry_count"] == 0 and row["rating"] == 0

    def test_unknown_fields_are_ignored(self, store_mod, tmp_path):
        """拼错的字段名不该把整行写坏（更新走白名单）。"""
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("IPZZ912", display_number="IPZZ-912", title_jp="原标题", titlejj="手滑")
        row = store.meta_get("IPZZ912")
        assert row["title_jp"] == "原标题"
        assert "titlejj" not in row

    def test_meta_get_missing(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.meta_get("NOPE") is None
        assert store.meta_get("") is None

    def test_list_and_where(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        for idx in range(3):
            store.meta_upsert(f"KEY{idx}", display_number=f"KEY-{idx}",
                              completeness="full" if idx else "missing_core")
        assert len(store.meta_list()) == 3
        assert len(store.meta_list(limit=2)) == 2
        assert len(store.meta_list(limit=2, offset=2)) == 1
        assert {r["key"] for r in store.meta_list(where="completeness='full'")} == {"KEY1", "KEY2"}

    def test_stats(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.meta_stats() == {"total": 0, "full": 0, "missing_plot": 0,
                                      "missing_core": 0, "untranslated": 0}
        store.meta_upsert("A", display_number="A-1", completeness="full",
                          translation_status="done")
        store.meta_upsert("B", display_number="B-1", completeness="missing_plot")
        store.meta_upsert("C", display_number="C-1", completeness="missing_core",
                          translation_status="machine_fallback")
        stats = store.meta_stats()
        assert stats == {"total": 3, "full": 1, "missing_plot": 1, "missing_core": 1,
                         "untranslated": 1}                     # 只有默认 untranslated 那条算未翻

    def test_due_tier1_uses_next_retry_at(self, store_mod, tmp_path):
        """tier=1：只看约好重试时间且到点的，按时间升序。"""
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("OLD", display_number="OLD-1", next_retry_at="2026-10-01 00:00:00")
        store.meta_upsert("SOON", display_number="SOON-1", next_retry_at="2026-10-05 00:00:00")
        store.meta_upsert("LATER", display_number="LATER-1", next_retry_at="2030-01-01 00:00:00")
        store.meta_upsert("NEVER", display_number="NEVER-1")
        due = store.meta_due(now="2026-10-10 00:00:00", tier=1, limit=5)
        assert [r["key"] for r in due] == ["OLD", "SOON"]
        assert store.meta_due(now="2026-10-10 00:00:00", tier=1, limit=1)[0]["key"] == "OLD"
        assert store.meta_due(now="2025-01-01 00:00:00", tier=1) == []

    def test_due_tier2_prefers_never_scraped(self, store_mod, tmp_path):
        """tier=2：按 last_scraped_at 升序，空串（从没刮过）最优先。"""
        store = make_store(store_mod, tmp_path)
        store.meta_upsert("NEWEST", display_number="N-1", last_scraped_at="2026-10-10 00:00:00")
        store.meta_upsert("NEVER", display_number="N-2")
        store.meta_upsert("OLDEST", display_number="N-3", last_scraped_at="2026-01-01 00:00:00")
        due = store.meta_due(tier=2, limit=5)
        assert [r["key"] for r in due] == ["NEVER", "OLDEST", "NEWEST"]
        assert [r["key"] for r in store.meta_due(tier=2, limit=2)] == ["NEVER", "OLDEST"]
        # limit<=0 按默认 5 处理，不给"全取"的口子
        assert len(store.meta_due(tier=2, limit=0)) == 3


class TestMediaItem:
    """媒体实例（`media_item`）与写 Emby 前的备份闸门（裁决 D7）。"""

    def test_upsert_get_and_set(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380",
                          emby_id="12598", file_path="/Media/9kg/avi/SNOS-380.mp4",
                          version_tags_json={"is_zh_sub": True, "resolution": "1080p"},
                          library_state="in_library")
        row = store.item_get("emby:12598")
        assert row["key"] == "SNOS380" and row["emby_id"] == "12598"
        assert row["version_tags"] == {"is_zh_sub": True, "resolution": "1080p"}
        assert row["library_state"] == "in_library"
        assert row["has_backup"] is False

        store.item_set("emby:12598", scrape_state="scraped_full", crop_anchor="right")
        row = store.item_get("emby:12598")
        assert row["scrape_state"] == "scraped_full" and row["crop_anchor"] == "right"
        assert row["display_number"] == "SNOS-380"                # 没传的字段不动

    def test_upsert_keeps_unpassed_fields(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.item_upsert("dl:abc", "SNOS380", display_number="SNOS-380", file_path="/x.mp4")
        store.item_upsert("dl:abc", "SNOS380", download_state="completed")
        row = store.item_get("dl:abc")
        assert row["file_path"] == "/x.mp4" and row["download_state"] == "completed"

    def test_set_missing_row_returns_false(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.item_set("emby:404", scrape_state="scraped_full") is False
        assert store.item_get("emby:404") is None

    def test_list_filters_by_key_and_columns(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:1", "SNOS380", display_number="SNOS-380", library_state="in_library")
        store.item_upsert("dl:2", "SNOS380", display_number="SNOS-380", library_state="pending_import")
        store.item_upsert("emby:3", "IPZZ912", display_number="IPZZ-912", library_state="in_library")
        assert {r["item_key"] for r in store.item_list("SNOS380")} == {"emby:1", "dl:2"}
        assert [r["item_key"] for r in store.item_list(key="SNOS380",
                                                       library_state="in_library")] == ["emby:1"]
        assert len(store.item_list()) == 3
        assert len(store.item_list(limit=2)) == 2
        assert len(store.item_list(where="crop_anchor='auto'")) == 3

    def test_backup_save_is_write_once(self, store_mod, tmp_path):
        """已有非空备份时**绝不覆盖**，返回 False；第一次写入返回 True。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:12598", "SNOS380", display_number="SNOS-380", emby_id="12598")
        assert store.item_backup_save("emby:12598", '{"Name":"原始" }') is True
        assert store.item_backup_save("emby:12598", '{"Name":"第二次"}') is False
        assert store.item_backup_get("emby:12598") == '{"Name":"原始" }'
        assert store.item_get("emby:12598")["has_backup"] is True
        # 闸门的判据是 item_backup_get() 非空（False 也可能是「早就备份过」，不是「没备份成」）
        assert store.item_backup_get("emby:12598") != ""

    def test_backup_save_rejects_empty_and_creates_row(self, store_mod, tmp_path):
        """空备份不算备份（拿不到 DTO 就不许写 Emby）；行还不存在时补一条最小实例行。"""
        store = make_store(store_mod, tmp_path)
        assert store.item_backup_save("emby:12598", "") is False
        assert store.item_backup_get("emby:12598") == ""
        assert store.item_backup_save("emby:12598", '{"Name":"x"}') is True
        row = store.item_get("emby:12598")
        assert row["emby_id"] == "12598"                          # 从 item_key 拆出来的
        assert store.item_backup_save("emby:12598", '{"Name":"y"}') is False

    def test_item_set_cannot_touch_backup(self, store_mod, tmp_path):
        """`emby_backup_json` 不在通用可写字段里：闸门不能被 item_set 绕过去。"""
        store = make_store(store_mod, tmp_path)
        store.item_upsert("emby:1", "A1", display_number="A-1")
        store.item_backup_save("emby:1", '{"Name":"原始"}')
        store.item_set("emby:1", emby_backup_json='{"Name":"手改"}', scrape_state="scraped_full")
        assert store.item_backup_get("emby:1") == '{"Name":"原始"}'
        assert store.item_get("emby:1")["scrape_state"] == "scraped_full"


class TestNameMap:
    """三语映射（`name_map`）。"""

    BUILTIN = {
        "canonical_id": "actor:三上悠亚", "entity_type": "actor",
        "zh_cn": "三上悠亚", "zh_tw": "三上悠亞", "jp": "三上悠亜",
        "keywords_norm": ",mikamiyua,三上悠亚,三上悠亜,三上悠亞,",
        "javdb_actor_id": "javdb-1", "avatar_url": "https://tp/a.jpg",
    }

    def test_bulk_upsert_and_get(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.namemap_bulk_upsert([self.BUILTIN, {"entity_type": "actor"}]) == 1  # 缺主键的跳过
        row = store.namemap_get("actor:三上悠亚")
        assert row["zh_cn"] == "三上悠亚" and row["jp"] == "三上悠亜"
        assert row["keywords"] == ["mikamiyua", "三上悠亚", "三上悠亜", "三上悠亞"]
        assert row["source"] == "builtin_xml"
        assert store.namemap_bulk_upsert([self.BUILTIN]) == 1        # 重导不炸、还是那一行
        assert len(store.namemap_list()) == 1

    def test_find_matches_keywords_exactly(self, store_mod, tmp_path):
        """`keywords_norm` 精确包含匹配：日文名、中文名、罗马音都命中；部分匹配不命中。"""
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([self.BUILTIN])
        assert store.namemap_find("actor", "三上悠亜")["canonical_id"] == "actor:三上悠亚"
        assert store.namemap_find("actor", "三上悠亚")["canonical_id"] == "actor:三上悠亚"
        assert store.namemap_find("actor", "mikamiyua")["canonical_id"] == "actor:三上悠亚"
        assert store.namemap_find("actor", "MIKAMIYUA")["canonical_id"] == "actor:三上悠亚"
        assert store.namemap_find("actor", "三上") is None            # 只认整段 token
        assert store.namemap_find("tag", "三上悠亜") is None           # 实体类型不同
        # 先给的先算：第一个名字没有命中时才看后面的
        assert store.namemap_find("actor", "查不到", "三上悠亜")["canonical_id"] == "actor:三上悠亚"

    def test_find_is_whole_word_not_substring(self, store_mod, tmp_path):
        """`keywords_norm LIKE '%,'||?||',%'`：上游那种 `バカボン` / `バカボン×` 撞车不许复现。"""
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([{
            "canonical_id": "amane:バカボン×", "entity_type": "actor",
            "zh_cn": "笨蛋×", "jp": "バカボン×", "keywords_norm": ",バカボン×,笨蛋×,",
        }, {
            "canonical_id": "amane:男優", "entity_type": "actor",
            "zh_cn": "男优", "jp": "男優", "keywords_norm": ",男優,",
        }])
        assert store.namemap_find("actor", "バカボン") is None         # 前缀不算命中
        assert store.namemap_find("actor", "男優")["canonical_id"] == "amane:男優"
        assert store.namemap_find("actor", "バカボン×")["canonical_id"] == "amane:バカボン×"
        # 查询词里的逗号按 token 切开，不拼成子串去撞
        assert store.namemap_find("actor", "バカボン,男優")["canonical_id"] == "amane:男優"

    def test_find_normalises_query_term(self, store_mod, tmp_path, monkeypatch):
        """查询词先过 `namemap.normalize()` 再整词匹配（S3 落地后的真实通路，这里用假模块验）。"""
        fake = types.ModuleType(f"{store_mod.__package__}.namemap")
        fake.normalize = lambda text: str(text or "").replace(" ", "").lower()
        monkeypatch.setitem(sys.modules, f"{store_mod.__package__}.namemap", fake)
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([{
            "canonical_id": "amane:三上悠亚", "entity_type": "actor",
            "zh_cn": "三上悠亚", "jp": "三上悠亜", "keywords_norm": ",mikamiyua,三上悠亜,",
        }])
        assert store.namemap_find("actor", "Mikami Yua")["canonical_id"] == "amane:三上悠亚"
        assert store.namemap_find("actor", "mikamiyua")["canonical_id"] == "amane:三上悠亚"
        assert store.namemap_find("actor", "MikamiYuaExtra") is None    # 整词：多一点都不行

    def test_list_filters(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([
            self.BUILTIN,
            {"canonical_id": "tag:中出", "entity_type": "tag", "zh_cn": "中出",
             "keywords_norm": ",中出,creampie,"},
        ])
        assert len(store.namemap_list()) == 2
        assert [r["canonical_id"] for r in store.namemap_list("actor")] == ["actor:三上悠亚"]
        assert [r["canonical_id"] for r in store.namemap_list(like="creampie")] == ["tag:中出"]
        assert [r["canonical_id"] for r in store.namemap_list(like="三上")] == ["actor:三上悠亚"]

    def test_user_set_default_id_and_lookup(self, store_mod, tmp_path):
        """`canonical_id` 缺省按 `{entity_type}:{zh}` 生成，并塞进 keywords 供反查。"""
        store = make_store(store_mod, tmp_path)
        cid = store.namemap_user_set("tag", "中出")
        assert cid == "tag:中出"
        row = store.namemap_get(cid)
        assert row["source"] == "user_custom" and row["entity_type"] == "tag"
        assert store.namemap_find("tag", "中出")["canonical_id"] == "tag:中出"

    def test_user_set_updates_same_entity_in_place(self, store_mod, tmp_path):
        """同一实体已存在 → 就地更新（不新增行），并升格成 user_custom。"""
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([self.BUILTIN])
        cid = store.namemap_user_set("actor", "悠亚", jp="三上悠亜")
        assert cid == "actor:三上悠亚"                                # 沿用了已有那一行
        assert len(store.namemap_list()) == 1
        row = store.namemap_get(cid)
        assert row["zh_cn"] == "悠亚" and row["source"] == "user_custom"
        assert row["avatar_url"] == "https://tp/a.jpg"               # 头像/别的来源的列没被抹掉
        assert "mikamiyua" in row["keywords"]                        # 别名串取并集
        cid = store.namemap_user_set("actor", "悠亚酱", jp="三上悠亜")  # 用户又改了一次称呼
        assert cid == "actor:三上悠亚" and len(store.namemap_list()) == 1
        assert store.namemap_get(cid)["zh_cn"] == "悠亚酱"

    def test_user_mapping_survives_builtin_reimport(self, store_mod, tmp_path):
        """用户手工映射最高优先级：内置表重导不许顶掉它。"""
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([self.BUILTIN])
        store.namemap_user_set("actor", "悠亚", jp="三上悠亜")
        store.namemap_bulk_upsert([self.BUILTIN])                    # 重导内置表
        row = store.namemap_get("actor:三上悠亚")
        assert row["zh_cn"] == "悠亚" and row["source"] == "user_custom"

    def test_find_prefers_user_custom(self, store_mod, tmp_path):
        """两行都含同一个别名时，用户那行优先（最高优先级落到排序上）。"""
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([self.BUILTIN])
        store.namemap_bulk_upsert([{
            "canonical_id": "actor:三上悠亜", "entity_type": "actor",
            "zh_cn": "三上悠亜", "jp": "三上悠亜", "keywords_norm": ",三上悠亜,builtin2,",
        }])
        store.namemap_user_set("actor", "悠亚", jp="三上悠亜")
        hit = store.namemap_find("actor", "三上悠亜")
        assert hit["source"] == "user_custom"
        assert store.namemap_get("actor:三上悠亜")["zh_cn"] == "三上悠亜"   # 内置那行没被动


class TestAliasMigration:
    """`actor_alias` → `name_map(source='user_custom')` 的幂等迁移（v4.1 §4.2 末条）。"""

    def test_alias_rows_land_in_name_map(self, store_mod, tmp_path):
        db = tmp_path / "avhelper.db"
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE actor_alias(name TEXT PRIMARY KEY, alias TEXT, updated_at TEXT)")
            conn.execute("INSERT INTO actor_alias VALUES('桃園怜奈','桃子','2026-01-01')")
            conn.execute("INSERT INTO actor_alias VALUES('相泽南','南南','2026-01-01')")
            conn.execute("INSERT INTO actor_alias VALUES('空备注','','2026-01-01')")
        store = store_mod.Store(db_path=db)
        store.init()
        rows = {r["canonical_id"]: r for r in store.namemap_list("actor")}
        assert set(rows) == {"actor:桃園怜奈", "actor:相泽南"}         # 空备注不进
        assert rows["actor:桃園怜奈"]["zh_cn"] == "桃子"
        assert rows["actor:桃園怜奈"]["jp"] == "桃園怜奈"
        assert rows["actor:桃園怜奈"]["source"] == "user_custom"
        assert rows["actor:桃園怜奈"]["keywords"] == ["桃園怜奈", "桃子"]
        assert store.namemap_find("actor", "桃子")["canonical_id"] == "actor:桃園怜奈"
        assert store.namemap_find("actor", "桃園怜奈")["canonical_id"] == "actor:桃園怜奈"

    def test_repeated_init_is_idempotent(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.alias_set("桃園怜奈", "桃子")
        for _ in range(3):
            store.init()
        rows = store.namemap_list("actor")
        assert len(rows) == 1 and rows[0]["zh_cn"] == "桃子"

    def test_changed_alias_updates_same_row(self, store_mod, tmp_path):
        """用户改备注 → 同一行原地更新（不新增行，旧写法仍查得到）。"""
        store = make_store(store_mod, tmp_path)
        store.alias_set("桃園怜奈", "桃子")
        first = store.namemap_list("actor")
        store.alias_set("桃園怜奈", "桃桃")
        store.init()
        rows = store.namemap_list("actor")
        assert len(rows) == 1 and rows[0]["canonical_id"] == "actor:桃園怜奈"
        assert rows[0]["zh_cn"] == "桃桃"
        assert set(rows[0]["keywords"]) == {"桃園怜奈", "桃子", "桃桃"}
        assert first[0]["canonical_id"] == rows[0]["canonical_id"]

    def test_alias_set_syncs_immediately(self, store_mod, tmp_path):
        """备注写完立刻进 name_map（不等下次 init()）。"""
        store = make_store(store_mod, tmp_path)
        store.alias_set("相泽南", "南南")
        assert store.namemap_find("actor", "南南")["canonical_id"] == "actor:相泽南"

    def test_migration_keeps_builtin_columns(self, store_mod, tmp_path):
        """已存在同名内置行时：只改属于用户备注的那几列，头像/繁中名留着。"""
        store = make_store(store_mod, tmp_path)
        store.namemap_bulk_upsert([{
            "canonical_id": "actor:桃園怜奈", "entity_type": "actor",
            "zh_cn": "桃园怜奈", "zh_tw": "桃園憐奈", "jp": "桃園怜奈",
            "keywords_norm": ",taoyuanliannai,桃园怜奈,桃園怜奈,",
            "avatar_url": "https://tp/t.jpg", "javdb_actor_id": "j-1", "source": "builtin_xml",
        }])
        store.alias_set("桃園怜奈", "桃子")
        row = store.namemap_get("actor:桃園怜奈")
        assert row["zh_cn"] == "桃子" and row["source"] == "user_custom"
        assert row["zh_tw"] == "桃園憐奈"
        assert row["avatar_url"] == "https://tp/t.jpg"
        assert "taoyuanliannai" in row["keywords"]                   # 内置别名没丢


class TestResolveActorKeys:
    """`resolve_actor_keys()`：一位演员的全部写法（收藏/订阅匹配用）。"""

    def _seed(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.alias_set("桃園怜奈", "桃子")                            # 用户备注
        store.fav_add("桃園怜奈", "桃园怜奈", "")                       # 收藏里的中文名
        store.namemap_bulk_upsert([{
            "canonical_id": "actor:三上悠亚", "entity_type": "actor",
            "zh_cn": "三上悠亚", "zh_tw": "三上悠亞", "jp": "三上悠亜",
            "keywords_norm": ",mikamiyua,三上悠亚,三上悠亜,",
        }])
        return store

    def test_expands_alias_and_favorite_names(self, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path)
        keys = store.resolve_actor_keys("桃園怜奈")
        assert keys[0] == "桃園怜奈"
        assert {"桃子", "桃园怜奈"} <= set(keys)                       # 备注 + 收藏里的中文名

    def test_reverse_lookup_from_alias(self, store_mod, tmp_path):
        """传进来的就是备注时，要能回原名。"""
        store = self._seed(store_mod, tmp_path)
        keys = store.resolve_actor_keys("桃子")
        assert keys[0] == "桃子"
        assert "桃園怜奈" in keys
        assert "桃园怜奈" in keys

    def test_expands_romaji_and_cjk_from_name_map(self, store_mod, tmp_path):
        store = self._seed(store_mod, tmp_path)
        keys = store.resolve_actor_keys("mikamiyua")
        assert {"三上悠亚", "三上悠亜", "三上悠亞"} <= set(keys)
        keys = store.resolve_actor_keys("三上悠亜")
        assert {"三上悠亚", "mikamiyua"} <= set(keys)

    def test_covers_actor_subscription_names(self, store_mod, tmp_path):
        """`sub(type='actor')` 里存的名字（可能是罗马音写法）必须被展开覆盖。"""
        store = self._seed(store_mod, tmp_path)
        store.sub_add("actor", "mikamiyua", {})
        name = store.sub_list()[0]["name"]
        keys = store.resolve_actor_keys(name)
        assert "三上悠亚" in keys

    def test_unknown_name_returns_itself(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.resolve_actor_keys("查无此人") == ["查无此人"]
        assert store.resolve_actor_keys("") == []
        assert store.resolve_actor_keys(None) == []


class TestDownloadsV4Columns:
    """`downloads` 三列的写入与合并口径。"""

    def test_upsert_writes_and_exposes_new_columns(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.download_upsert("IPZZ-961", state="downloading", source="plugin",
                              version_tags={"is_zh_sub": True, "resolution": "1080p"},
                              emby_id="12598")
        row = store.download_map()["IPZZ961"]
        assert row["version_tags"] == '{"is_zh_sub": true, "resolution": "1080p"}'  # 原样给串
        assert row["emby_id"] == "12598"
        assert row["failed_reason"] == ""

        store.download_upsert("IPZZ-961", state="failed", source="plugin",
                              failed_reason="种子状态 error")
        row = store.download_map()["IPZZ961"]
        assert row["state"] == "failed" and row["failed_reason"] == "种子状态 error"
        assert row["emby_id"] == "12598"                      # 这轮没传 → 保住
        assert "is_zh_sub" in row["version_tags"]             # 这轮没传标签 → 不被抹成 {}

    def test_upsert_accepts_string_tags(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.download_upsert("IPZZ-961", version_tags='{"is_iso": true}')
        assert store.download_map()["IPZZ961"]["version_tags"] == '{"is_iso": true}'

    def test_seed_only_fills_empty(self, store_mod, tmp_path):
        """补种只补空：已有标签/emby_id/失败原因不被 seed 覆盖。"""
        store = make_store(store_mod, tmp_path)
        store.download_upsert("SNOS-380", source="plugin", state="downloading",
                              version_tags={"resolution": "1080p"}, emby_id="12598",
                              failed_reason="先前的失败")
        store.download_seed([{
            "number": "SNOS-380", "source": "library", "state": "downloaded",
            "version_tags": {"resolution": "2160p"}, "emby_id": "99999",
            "failed_reason": "库里的写法",
        }])
        row = store.download_map()["SNOS380"]
        assert row["version_tags"] == '{"resolution": "1080p"}'
        assert row["emby_id"] == "12598"
        assert row["failed_reason"] == "先前的失败"
        assert row["state"] == "downloaded"                    # 状态照旧能升级

    def test_seed_fills_empty_new_columns(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.download_seed([{
            "number": "SNOS-380", "source": "library", "state": "downloaded",
            "version_tags": {"is_zh_sub": True}, "emby_id": "12598",
        }])
        row = store.download_map()["SNOS380"]
        assert row["version_tags"] == '{"is_zh_sub": true}' and row["emby_id"] == "12598"

    def test_old_rows_read_as_empty_defaults(self, store_mod, tmp_path):
        """老库补列之后老行读出来是建表默认值（`{}` / 空串），不是 None。"""
        db = tmp_path / "legacy.db"
        with sqlite3.connect(db) as conn:
            conn.executescript(LEGACY_DOWNLOADS_DDL)
            conn.execute("INSERT INTO downloads(key, number, title) VALUES('IPZZ961','IPZZ-961','老片')")
        store = store_mod.Store(db_path=db)
        store.init()
        row = store.download_map()["IPZZ961"]
        assert row["version_tags"] == "{}" and row["emby_id"] == "" and row["failed_reason"] == ""
        assert set(row) == {"key", "number", "title", "actor", "thumb", "size", "hash", "path",
                            "downloader", "state", "source", "created_at", "completed_at",
                            "updated_at", "hidden", "version_tags", "emby_id", "failed_reason"}


class TestTranslateCache:
    """翻译缓存（`translate`）。"""

    def test_put_get_roundtrip(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.translate_get("k1") is None
        store.translate_put("k1", "日文原文", "中文译文", model_name="hy3", quality_tier="llm")
        assert store.translate_get("k1") == "中文译文"
        store.translate_put("k1", "日文原文", "第二版译文", model_name="deepseek", quality_tier="dict")
        assert store.translate_get("k1") == "第二版译文"
        assert store.translate_get("") is None
        assert store.translate_get("missing") is None
        assert store.translate_put("", "x", "y") is None            # 空键不写

    def test_empty_translation_is_a_value(self, store_mod, tmp_path):
        """空串译文是合法缓存值（不等于"没缓存"）。"""
        store = make_store(store_mod, tmp_path)
        store.translate_put("k", "原文", "")
        assert store.translate_get("k") == ""


class TestScrapeLog:
    """数据源自检日志（`scrape_log`）。"""

    def test_add_and_recent(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.scrape_log_add("javdb", "ok", key="IPZZ912", latency_ms=1200)
        store.scrape_log_add("javtxt", "timeout", key="IPZZ912", latency_ms=30000,
                             error_summary="读超时")
        store.scrape_log_add("javdb", "mismatch", key="SNOS380", latency_ms=800,
                             error_summary="番号对不上")
        recent = store.scrape_log_recent()
        assert [r["source"] for r in recent] == ["javdb", "javtxt", "javdb"]   # 新→旧
        assert recent[0]["status"] == "mismatch" and recent[0]["error"] == "番号对不上"
        assert recent[0]["error_summary"] == "番号对不上"                        # 两种键都给
        only = store.scrape_log_recent(source_name="javdb")
        assert len(only) == 2 and {r["key"] for r in only} == {"IPZZ912", "SNOS380"}

    def test_summary(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.scrape_log_add("javdb", "ok", latency_ms=1000)
        store.scrape_log_add("javdb", "not_found", latency_ms=2000)
        store.scrape_log_add("javtxt", "ok", latency_ms=500)
        summary = {r["source"]: r for r in store.scrape_log_summary()}
        assert summary["javdb"]["total"] == 2 and summary["javdb"]["fail"] == 1
        assert summary["javdb"]["avg_latency_ms"] == 1500
        assert summary["javdb"]["last_status"] == "not_found"
        assert summary["javtxt"]["ok"] == 1

    def test_error_summary_is_trimmed_and_log_pruned(self, store_mod, tmp_path, monkeypatch):
        """摘要裁到 500 字符；表只留最近 `_SCRAPE_LOG_KEEP` 条。"""
        store = make_store(store_mod, tmp_path)
        store.scrape_log_add("javdb", "error", error_summary="x" * 900)
        assert len(store.scrape_log_recent()[0]["error"]) == 500
        monkeypatch.setattr(store_mod, "_SCRAPE_LOG_KEEP", 3)
        for idx in range(5):
            store.scrape_log_add("javdb", "ok", key=f"K{idx}")
        rows = store.scrape_log_recent()
        assert len(rows) == 3
        assert [r["key"] for r in rows] == ["K4", "K3", "K2"]


class TestLegacyBehaviourKept:
    """老接口的语义没被这次升级动过（回归锚点，细节见 test_store.py）。"""

    def test_alias_kv_and_ledger_still_work(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.alias_set("桃園怜奈", "桃子")
        assert store.alias_map() == {"桃園怜奈": "桃子"}
        store.alias_set("桃園怜奈", "")
        assert store.alias_map() == {}
        value = store.kv_update("queue", lambda old: (old or []) + ["新的"])
        assert value == ["新的"]
        assert store.kv_get("queue") == ["新的"]

        store.download_upsert("IPZZ-961", source="plugin", state="downloaded")
        assert store.download_delete("IPZZ-961") is True
        assert store.download_list(store_mod.PLUGIN_SOURCES) == []

    def test_threads_writing_concurrently_do_not_lose_rows(self, store_mod, tmp_path):
        """多线程各写各的：写锁 + 线程本地连接下，一条都不能丢（升级前的主要风险点）。"""
        store = make_store(store_mod, tmp_path)

        def worker(tag):
            for idx in range(15):
                store.known_add(f"{tag}-{idx}")

        threads = [threading.Thread(target=worker, args=(f"T{n}",)) for n in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        assert len(store.known_all()) == 60
