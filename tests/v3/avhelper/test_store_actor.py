"""0.9.0 演员线数据层（`store.actor*`）的单测。

覆盖 S1 的交付口径：

- **迁移 v2**：0.8.0 形状的老库（无 `actor` 表、`schema_meta.schema_version='1'`）反复 `init()`
  不炸、版本升到 2、老数据不丢、索引在补列之后建；全新库连跑两次同样收敛；
- `actor_upsert` 按 `person` 幂等、只覆盖非空字段、**绝不冲掉状态列**（图/锁/退避）；
- `actor_set_images` 在 `locked_fields=["images"]` 时**拒绝覆盖**并原样返回；
- 失败退避 6 / 24 / 72 / 168 / 336 小时，第 6 次到顶后不再排期；
- `actor_queue_push` 自举（不存在的 person 先落最小行再入队）、重复 push 幂等；
  `actor_queue_pop` 取走后 state 变 `taken`；
- `actor_backfill` 幂等，第二次调用返回 `skipped: True`。

全部落在 pytest 临时目录；不联网、不碰 Emby、不依赖插件包 `__init__.py`。
"""

import sqlite3
from datetime import datetime, timedelta

import pytest


#: 建表 DDL 的列名与列序（`docs/AVHelper-演员刮削子系统方案.md` §2 原样，一个字都不许改）
ACTOR_COLUMNS = [
    "id", "person", "name", "zh", "jp", "gender", "aliases_json", "javdb_actor_id",
    "images_json", "field_sources_json", "locked_fields_json", "last_scraped_at",
    "retry_count", "next_retry", "updated_at",
]
QUEUE_COLUMNS = ["actor_id", "person", "state", "created_at", "taken_at"]

STAMP = "%Y-%m-%d %H:%M:%S"

MZ_PERSON = "松本一香（松本いちか）"
TN_PERSON = "七海ティナ（ななみてぃな）"


def make_store(store_mod, tmp_path, name="actor.db"):
    """在临时目录上建一个干净（已迁移到最新版）的库。"""
    store = store_mod.Store(db_path=tmp_path / name)
    store.init()
    return store


def columns_of(store, table):
    """表结构（PRAGMA 是 per-connection 的，读 Store 自己那条长连接）。"""
    return [r[1] for r in store._connect().execute(f"PRAGMA table_info({table})").fetchall()]


def names_of(store, kind):
    rows = store._connect().execute(
        "SELECT name FROM sqlite_master WHERE type=?", (kind,)).fetchall()
    return {r[0] for r in rows}


def clear_backfill_flag(store):
    """把"回填只做一次"的标记清掉，用来验证**数据层面**的幂等（而不是标记挡住了）。"""
    store._exec("DELETE FROM schema_meta WHERE key='actor_backfill_done'")


class FakeNamemap:
    """`namemap.actor_lookup()` 的最小替身。

    真模块要加载 5351 条内置映射（还有用户覆盖文件），单测只需要它的**返回形状**；
    `calls` 记下被问过的名字，用来确认回填确实去查了映射。
    """

    def __init__(self, table=None):
        self.table = dict(table or {})
        self.calls = []

    def actor_lookup(self, name):
        self.calls.append(name)
        return self.table.get(name)


class TestMigrationV2:
    """老库升级（0.9.0 最容易出事的一步）：建表在迁移里、索引在补列之后。"""

    #: 0.8.0 形状的库：没有 actor / actor_queue，版本戳停在 1（线上容器里的就是这个形状）
    LEGACY_DDL = """
    CREATE TABLE schema_meta(key TEXT PRIMARY KEY, val TEXT DEFAULT '');
    CREATE TABLE meta(key TEXT PRIMARY KEY, display_number TEXT NOT NULL,
                      actors_json TEXT DEFAULT '[]', updated_at TEXT DEFAULT '');
    CREATE TABLE kv(key TEXT PRIMARY KEY, val TEXT, expires_at TEXT);
    """

    def _legacy_db(self, tmp_path):
        db = tmp_path / "legacy080.db"
        with sqlite3.connect(db) as conn:
            conn.executescript(self.LEGACY_DDL)
            conn.execute("INSERT INTO schema_meta(key, val) VALUES('schema_version', '1')")
            conn.execute("INSERT INTO kv(key, val) VALUES('probe', 'kept')")
            conn.execute("INSERT INTO meta(key, display_number, actors_json, updated_at) "
                         "VALUES('IPZZ961', 'IPZZ-961', '[]', '2026-10-01 00:00:00')")
        return db

    def test_legacy_db_upgrades_and_survives_init_twice(self, store_mod, tmp_path):
        """老库 `init()` 两次：不抛、actor 表建出来、版本升到 2、老数据一条不丢。"""
        db = self._legacy_db(tmp_path)
        first = store_mod.Store(db_path=db)
        first.init()
        assert {"actor", "actor_queue"} <= names_of(first, "table")
        assert first.schema_version() == 2
        assert first.schema_info()["note"] == "actor"
        # 插件每次加载都会再跑一遍 init()：第二次必须是纯空转
        second = store_mod.Store(db_path=db)
        second.init()
        assert second.schema_version() == 2
        assert columns_of(second, "actor") == ACTOR_COLUMNS
        assert columns_of(second, "actor_queue") == QUEUE_COLUMNS
        # 老库里的数据一条都不许丢（迁移绝不 DROP 重建）
        assert second._exec("SELECT val FROM kv WHERE key='probe'", fetch=True)[0][0] == "kept"
        assert second._exec("SELECT display_number FROM meta", fetch=True)[0][0] == "IPZZ-961"

    def test_legacy_db_gets_actor_indexes(self, store_mod, tmp_path):
        """老库升级后索引真的建上了（索引在 `_ensure_indexes()`，补列之后）。"""
        store = store_mod.Store(db_path=self._legacy_db(tmp_path))
        store.init()
        assert {"idx_actor_next_retry", "idx_actor_last_scraped",
                "idx_actor_queue_state"} <= names_of(store, "index")

    def test_broken_actor_index_only_warns(self, store_mod, tmp_path, monkeypatch):
        """单条索引建不起来（列真丢了）只记日志：索引是性能，不是数据完整性。"""
        monkeypatch.setattr(store_mod, "_INDEXES",
                            store_mod._INDEXES + (("idx_actor_broken", "actor(不存在的列)"),))
        store = store_mod.Store(db_path=self._legacy_db(tmp_path))
        store.init()                                   # 不抛
        assert "actor" in names_of(store, "table")
        assert "idx_actor_next_retry" in names_of(store, "index")

    def test_fresh_db_init_twice(self, store_mod, tmp_path):
        db = tmp_path / "fresh.db"
        store_mod.Store(db_path=db).init()
        store = store_mod.Store(db_path=db)
        store.init()
        assert store.schema_version() == 2
        assert columns_of(store, "actor") == ACTOR_COLUMNS
        assert store.actor_stats()["total"] == 0

    def test_dropped_actor_table_self_heals(self, store_mod, tmp_path):
        """版本是 2、表却被手工 DROP：`init()` 幂等建表自愈，且**不改版本**。"""
        store = make_store(store_mod, tmp_path)
        store._exec("DROP TABLE actor")
        again = store_mod.Store(db_path=tmp_path / "actor.db")
        again.init()
        assert "actor" in names_of(again, "table")
        assert again.schema_version() == 2


class TestActorUpsert:
    """`actor_upsert`：按 person 幂等、只覆盖非空、状态列不许被冲。"""

    def test_upsert_is_idempotent_by_person(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        first = store.actor_upsert({"person": MZ_PERSON, "name": "松本一香",
                                    "zh": "松本一香", "jp": "松本いちか", "gender": 0})
        assert first > 0
        assert store.actor_upsert({"person": MZ_PERSON, "name": "松本一香"}) == first
        assert store.actor_list()["total"] == 1
        row = store.actor_get(first)
        assert row["jp"] == "松本いちか" and row["gender"] == 0

    def test_unknown_gender_stays_null(self, store_mod, tmp_path):
        """没给性别就是 NULL（未知），**不是 0**：0 在写侧等于"确定为女"。"""
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        assert store.actor_get(actor_id)["gender"] is None

    def test_empty_values_do_not_clobber(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "name": "松本一香",
                                       "zh": "松本一香", "jp": "松本いちか"})
        store.actor_upsert({"person": MZ_PERSON, "name": "", "zh": "  ", "jp": ""})
        row = store.actor_get(actor_id)
        assert (row["name"], row["zh"], row["jp"]) == ("松本一香", "松本一香", "松本いちか")
        store.actor_upsert({"person": MZ_PERSON, "zh": "松本一香(新)"})
        assert store.actor_get(actor_id)["zh"] == "松本一香(新)"

    def test_status_columns_never_clobbered_by_upsert(self, store_mod, tmp_path):
        """**这条是 S1 的核心回归**：upsert 不许碰图、锁、溯源、退避。"""
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "name": "松本一香"})
        store.actor_set_images(actor_id, [{"url": "https://raw.githubusercontent.com/x/y.jpg",
                                           "source": "gfriends", "w": 800, "h": 1200}],
                               {"images": "gfriends"})
        store.actor_lock(actor_id, "images")
        store.actor_mark_failed(actor_id, "timeout")
        before = store.actor_get(actor_id)
        assert before["images"] and before["locked_fields"] == ["images"]
        assert before["retry_count"] == 1 and before["next_retry"]
        store.actor_upsert({"person": MZ_PERSON, "name": "松本一香",
                            "images_json": "[]", "field_sources_json": "{}",
                            "locked_fields_json": "[]", "last_scraped_at": "",
                            "retry_count": 0, "next_retry": ""})
        after = store.actor_get(actor_id)
        assert after["images"] == before["images"]
        assert after["field_sources"] == before["field_sources"]
        assert after["locked_fields"] == ["images"]
        assert after["retry_count"] == 1
        assert after["next_retry"] == before["next_retry"]
        assert after["last_scraped_at"] == before["last_scraped_at"]

    def test_locked_profile_field_is_skipped(self, store_mod, tmp_path):
        """手工锁优先于任何来源：锁了 zh，upsert 带来的新 zh 不许落地，但 jp 照写。"""
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "zh": "松本一香"})
        store.actor_lock(actor_id, "zh")
        store.actor_upsert({"person": MZ_PERSON, "zh": "别的名字", "jp": "松本いちか"})
        row = store.actor_get(actor_id)
        assert row["zh"] == "松本一香"
        assert row["jp"] == "松本いちか"

    def test_empty_person_is_rejected(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.actor_upsert({"person": "   "}) == 0
        assert store.actor_upsert({}) == 0
        assert store.actor_list()["total"] == 0

    def test_alias_key_is_accepted(self, store_mod, tmp_path):
        """`aliases` 是给调用方的糖，落到列 `aliases_json` 上。"""
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "aliases": ["a", "b"]})
        assert store.actor_get(actor_id)["aliases"] == ["a", "b"]

    def test_get_by_person_and_missing(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        assert store.actor_get(person=MZ_PERSON)["id"] == actor_id
        assert store.actor_get() is None                 # 两个都没给
        assert store.actor_get(9999) is None
        assert store.actor_get(person="查无此人") is None


class TestActorListAndStats:
    """卡片墙的筛选/计数：`actor_stats()` 与 `actor_list(filter=…)` 必须是同一个口径。"""

    def test_filters_match_stats(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        plain = store.actor_upsert({"person": MZ_PERSON})
        locked = store.actor_upsert({"person": TN_PERSON})
        store.actor_set_images(locked, [{"url": "https://a/b.jpg", "source": "javdb"}])
        store.actor_lock(locked, "images")
        broken = store.actor_upsert({"person": "三上悠亜（みかみゆあ）"})
        store.actor_mark_failed(broken, "no_avatar")
        stats = store.actor_stats()
        assert stats["total"] == 3
        assert stats["missing_avatar"] == 2          # plain 与 broken
        assert stats["locked"] == 1
        assert stats["failed"] == 1
        assert stats["due"] == 2                     # broken 的 next_retry 在 6 小时后
        assert store.actor_list(flt="missing_avatar")["total"] == stats["missing_avatar"]
        assert store.actor_list(flt="locked")["total"] == stats["locked"]
        assert store.actor_list(flt="failed")["total"] == stats["failed"]
        assert store.actor_list(q="松本")["total"] == 1
        assert store.actor_list(q="查无此人")["total"] == 0

    def test_paging_reports_total(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        for index in range(5):
            store.actor_upsert({"person": f"演员{index}（えんしゅつ{index}）"})
        page = store.actor_list(limit=2, offset=3)
        assert page["total"] == 5
        assert len(page["items"]) == 2
        assert store.actor_list(limit=0, offset=4)["items"][0]["id"] == 5

    def test_unknown_filter_is_ignored(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.actor_upsert({"person": MZ_PERSON})
        assert store.actor_list(flt="随便写的")["total"] == 1     # 只 warning，不拼 SQL

    def test_due_order_is_oldest_first(self, store_mod, tmp_path):
        """`actor_due()` 按 `last_scraped_at` 升序，**从没抓过的排最前**。"""
        store = make_store(store_mod, tmp_path)
        ids = [store.actor_upsert({"person": f"演员{i}"}) for i in range(3)]
        store.actor_mark_ok(ids[0], "2026-01-01 00:00:00")
        store.actor_mark_ok(ids[1], "2026-02-01 00:00:00")
        due = store.actor_due(limit=10)
        assert [row["id"] for row in due] == [ids[2], ids[0], ids[1]]

    def test_due_skips_future_retry(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        assert [row["id"] for row in store.actor_due()] == [actor_id]
        store.actor_mark_failed(actor_id, "timeout")       # 6 小时后才到点
        assert store.actor_due() == []
        assert store.actor_stats()["due"] == 0


class TestActorImages:
    """头像写入与锁：手工图绝不能被重刮覆盖。"""

    GFIGHTS = [{"url": "https://raw.githubusercontent.com/gfriends/Content/a/y.jpg",
                "source": "gfriends", "w": 800, "h": 1200}]
    JAVDB = [{"url": "https://c0.jdbstatic.com/avatars/z.jpg", "source": "javdb"}]

    def test_locked_images_rejects_overwrite(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        store.actor_set_images(actor_id, self.GFIGHTS, {"images": "gfriends"})
        store.actor_lock(actor_id, "images")
        out = store.actor_set_images(actor_id, self.JAVDB)
        assert [item["url"] for item in out["images"]] == [self.GFIGHTS[0]["url"]]
        row = store.actor_get(actor_id)                     # 一个字节都没落库
        assert [item["url"] for item in row["images"]] == [self.GFIGHTS[0]["url"]]
        assert row["field_sources"]["images"] == "gfriends"

    def test_unlock_allows_overwrite(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        store.actor_set_images(actor_id, self.GFIGHTS)
        store.actor_lock(actor_id, "images")
        store.actor_lock(actor_id, "images", on=False)
        out = store.actor_set_images(actor_id, self.JAVDB)
        assert [item["url"] for item in out["images"]] == [self.JAVDB[0]["url"]]

    def test_items_without_url_are_dropped(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        out = store.actor_set_images(actor_id, [{"source": "gfriends"}, {"url": " "},
                                                self.JAVDB[0]])
        assert [item["url"] for item in out["images"]] == [self.JAVDB[0]["url"]]

    def test_field_sources_are_merged(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        store.actor_set_profile(actor_id, {"zh": "松本一香"}, {"zh": "namemap"})
        out = store.actor_set_images(actor_id, self.GFIGHTS, {"images": "gfriends"})
        assert out["field_sources"] == {"zh": "namemap", "images": "gfriends"}

    def test_unknown_actor_returns_empty(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.actor_set_images(999, self.JAVDB) == {}

    def test_profile_merge_and_field_lock(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "name": "松本一香"})
        out = store.actor_set_profile(actor_id, {"zh": "松本一香", "jp": "松本いちか", "gender": 0},
                                      {"zh": "namemap"})
        assert (out["zh"], out["jp"], out["gender"]) == ("松本一香", "松本いちか", 0)
        assert out["field_sources"]["zh"] == "namemap"
        store.actor_lock(actor_id, "zh")
        out = store.actor_set_profile(actor_id, {"zh": "新名字", "jp": "新しい",
                                                "aliases": ["a", "b"], "images_json": "[]"})
        assert out["zh"] == "松本一香"                      # 锁住的不动
        assert out["jp"] == "新しい" and out["aliases"] == ["a", "b"]
        assert out["images"] == []                          # 非资料列一律不认

    def test_lock_is_idempotent_and_ordered(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        assert store.actor_lock(actor_id)["locked_fields"] == ["images"]
        assert store.actor_lock(actor_id)["locked_fields"] == ["images"]
        assert store.actor_lock(actor_id, "zh")["locked_fields"] == ["images", "zh"]
        assert store.actor_lock(actor_id, "zh", on=False)["locked_fields"] == ["images"]
        assert store.actor_lock(actor_id, "zh", on=False)["locked_fields"] == ["images"]
        assert store.actor_lock(actor_id, "  ")["locked_fields"] == ["images"]   # 空字段忽略
        assert store.actor_lock(999, "images") == {}


class TestActorBackoff:
    """失败退避：6h → 24h → 72h → 7d → 14d，第 6 次到顶不再排期。"""

    def test_sequence_and_cap(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        for step, hours in enumerate((6, 24, 72, 168, 336), start=1):
            before = datetime.now()
            row = store.actor_mark_failed(actor_id, "timeout")
            after = datetime.now()
            assert row["retry_count"] == step
            due = datetime.strptime(row["next_retry"], STAMP)
            low = before + timedelta(hours=hours) - timedelta(seconds=2)
            high = after + timedelta(hours=hours) + timedelta(seconds=2)
            assert low <= due <= high, (step, hours, row["next_retry"])
        sixth = store.actor_mark_failed(actor_id, "still broken")
        assert sixth["retry_count"] == 6
        assert sixth["next_retry"] == ""                     # 到顶：只等手动
        seventh = store.actor_mark_failed(actor_id)
        assert seventh["retry_count"] == 7 and seventh["next_retry"] == ""

    def test_mark_ok_resets_backoff(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        store.actor_mark_failed(actor_id)
        store.actor_mark_failed(actor_id)
        row = store.actor_mark_ok(actor_id, "2026-10-20 12:00:00")
        assert row["retry_count"] == 0
        assert row["next_retry"] == ""
        assert row["last_scraped_at"] == "2026-10-20 12:00:00"
        assert store.actor_due()[0]["id"] == actor_id

    def test_mark_ok_defaults_to_now(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON})
        row = store.actor_mark_ok(actor_id)
        assert row["last_scraped_at"]
        assert datetime.strptime(row["last_scraped_at"], STAMP)

    def test_unknown_actor_returns_empty(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.actor_mark_ok(999) == {}
        assert store.actor_mark_failed(999) == {}


class TestActorQueue:
    """队列：自举（不存在的 person 先落最小行）、幂等、领取即 taken。"""

    def test_push_bootstraps_minimal_row(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.actor_queue_push([MZ_PERSON]) == 1
        row = store.actor_get(person=MZ_PERSON)
        assert row is not None
        assert row["name"] == MZ_PERSON          # 最小行：person 有值、name 暂用 person
        assert row["gender"] is None
        assert row["images"] == [] and row["aliases"] == [] and row["zh"] == ""
        assert row["locked_fields"] == [] and row["retry_count"] == 0
        assert store._exec("SELECT person, state FROM actor_queue",
                           fetch=True) == [(MZ_PERSON, "wait")]

    def test_push_is_idempotent(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.actor_queue_push([MZ_PERSON, MZ_PERSON, "   "]) == 1
        assert store.actor_queue_push([MZ_PERSON]) == 0
        assert store._exec("SELECT COUNT(*) FROM actor_queue", fetch=True)[0][0] == 1
        assert store.actor_list()["total"] == 1        # 自举不会长出第二行

    def test_push_does_not_touch_existing_profile(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "name": "松本一香",
                                       "zh": "松本一香", "jp": "松本いちか"})
        assert store.actor_queue_push([MZ_PERSON]) == 1
        row = store.actor_get(actor_id)
        assert (row["name"], row["zh"], row["jp"]) == ("松本一香", "松本一香", "松本いちか")

    def test_push_empty_list(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.actor_queue_push([]) == 0
        assert store.actor_queue_push(None) == 0

    def test_pop_takes_rows_and_returns_actor_rows(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.actor_queue_push([MZ_PERSON, TN_PERSON])
        popped = store.actor_queue_pop(limit=1)
        assert len(popped) == 1
        assert popped[0]["person"] == MZ_PERSON          # 先进先出
        assert {"id", "person", "images", "locked_fields"} <= set(popped[0])
        state, taken_at = store._exec(
            "SELECT state, taken_at FROM actor_queue WHERE actor_id=?",
            (popped[0]["id"],), fetch=True)[0]
        assert state == "taken" and taken_at
        rest = store.actor_queue_pop(limit=10)
        assert [row["person"] for row in rest] == [TN_PERSON]
        assert store.actor_queue_pop(limit=10) == []     # 没有 wait 的行就回空

    def test_pop_skips_orphan_rows(self, store_mod, tmp_path):
        """指向已删演员的孤儿行：跳过并照样标 taken，不许每轮白领一次。"""
        store = make_store(store_mod, tmp_path)
        store._exec("INSERT INTO actor_queue(actor_id, person, state, created_at) "
                    "VALUES(9999, '孤儿', 'wait', '2026-01-01 00:00:00')")
        assert store.actor_queue_pop() == []
        assert store._exec("SELECT state FROM actor_queue WHERE actor_id=9999",
                           fetch=True)[0][0] == "taken"


class TestActorBackfill:
    """一次性回填：meta 聚合 → actor 行，namemap 补三语名，只做一次。"""

    def _seed(self, store):
        store.meta_upsert("IPZZ961", display_number="IPZZ-961", actors_json=[
            {"person": MZ_PERSON, "name": "松本一香", "zh": "松本一香",
             "jp": "松本いちか", "gender": None, "javdb_actor_id": "AbC123"},
            {"person": TN_PERSON, "name": "七海蒂娜", "zh": "七海蒂娜",
             "jp": "七海ティナ", "gender": 0, "javdb_actor_id": ""},
        ])
        store.meta_upsert("SNOS380", display_number="SNOS-380", actors_json=[
            {"person": TN_PERSON, "name": "七海蒂娜", "gender": 0},
            {"person": MZ_PERSON, "name": "松本一香", "gender": 0},
        ])

    def test_backfill_runs_once(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path, name="bf.db")
        self._seed(store)
        first = store.actor_backfill()
        assert first == {"created": 2, "updated": 0, "total": 2, "skipped": False}
        rows = {row["person"]: row for row in store.actor_list()["items"]}
        assert set(rows) == {MZ_PERSON, TN_PERSON}
        assert rows[MZ_PERSON]["javdb_actor_id"] == "AbC123"
        assert rows[MZ_PERSON]["gender"] == 0        # 第一个非空值来自 SNOS380 那行
        assert rows[TN_PERSON]["gender"] == 0
        second = store.actor_backfill()
        assert second == {"created": 0, "updated": 0, "total": 0, "skipped": True}

    def test_backfill_idempotent_when_flag_cleared(self, store_mod, tmp_path):
        """把"只做一次"的标记清掉再跑一遍：合并不长重复行（`created` 归 0）。"""
        store = make_store(store_mod, tmp_path, name="bf2.db")
        self._seed(store)
        store.actor_backfill()
        clear_backfill_flag(store)
        again = store.actor_backfill()
        assert again == {"created": 0, "updated": 2, "total": 2, "skipped": False}
        assert store.actor_list()["total"] == 2

    def test_backfill_fills_from_namemap(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path, name="bf3.db")
        fake = FakeNamemap({MZ_PERSON: {"zh": "松本一香", "zh_cn": "松本一香",
                                        "jp": "松本いちか", "javdb_actor_id": "map-1",
                                        "aliases": ["松本いちか", "まつもと いちか"]}})
        store.meta_upsert("IPZZ961", display_number="IPZZ-961",
                          actors_json=[{"person": MZ_PERSON, "name": "松本一香"}])
        out = store.actor_backfill(namemap_mod=fake)
        assert out["created"] == 1
        row = store.actor_get(person=MZ_PERSON)
        assert row["zh"] == "松本一香" and row["jp"] == "松本いちか"
        assert row["javdb_actor_id"] == "map-1"
        assert "まつもと いちか" in row["aliases"]
        assert MZ_PERSON not in row["aliases"]       # 规范名本身不算别名
        assert fake.calls == [MZ_PERSON]

    def test_backfill_keeps_state_columns(self, store_mod, tmp_path):
        """回填走的是 upsert，状态列（图/锁/退避）一个都不许被冲掉。"""
        store = make_store(store_mod, tmp_path, name="bf4.db")
        self._seed(store)
        actor_id = store.actor_upsert({"person": MZ_PERSON, "name": "松本一香"})
        store.actor_set_images(actor_id, [{"url": "https://x/y.jpg", "source": "manual"}],
                               {"images": "manual"})
        store.actor_lock(actor_id, "images")
        store.actor_mark_failed(actor_id, "timeout")
        before = store.actor_get(actor_id)
        out = store.actor_backfill()
        assert out["created"] == 1 and out["updated"] == 1
        after = store.actor_get(actor_id)
        assert after["images"] == before["images"]
        assert after["field_sources"] == before["field_sources"]
        assert after["locked_fields"] == ["images"]
        assert after["retry_count"] == 1 and after["next_retry"] == before["next_retry"]

    def test_backfill_accepts_explicit_actors(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path, name="bf5.db")
        out = store.actor_backfill(actors=["新人（しんじん）", "新人（しんじん）"],
                                   namemap_mod=FakeNamemap())
        assert out == {"created": 1, "updated": 0, "total": 1, "skipped": False}
        assert store.actor_get(person="新人（しんじん）")["name"] == "新人（しんじん）"
        assert store.actor_backfill(actors=["别人"], namemap_mod=FakeNamemap())["skipped"] is True

    def test_backfill_survives_broken_namemap(self, store_mod, tmp_path):
        """映射查一次就抛：只 warning、只少那一层名字，整批回填照跑完。"""
        class BrokenNamemap:
            def actor_lookup(self, name):
                raise RuntimeError("映射炸了")

        store = make_store(store_mod, tmp_path, name="bf6.db")
        self._seed(store)
        out = store.actor_backfill(namemap_mod=BrokenNamemap())
        assert out["created"] == 2 and out["skipped"] is False
        assert store.actor_get(person=MZ_PERSON)["jp"] == "松本いちか"
