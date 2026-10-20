"""退避时间戳的格式契约（0.8.x 真 bug 的回归锁）。

病根：写入侧 `scraper.apply_backoff()` 写 `2026-10-21T03:00:00`（`T` 分隔），
比较侧 `store.meta_due()` 拿它跟 `"%Y-%m-%d %H:%M:%S"` 做**字典序**比较 ——
`'T'(0x54) > ' '(0x20)`，于是同一天到点的行被判成「还没到」，Tier1 退避要等日期翻页才被领走。

这几条用例锁两件事：① 写入侧永远输出空格分隔（且能读老的 `T` 入参）；
② 迁移 v3 把存量行就地改写成同一口径、且幂等。
"""

import sqlite3
from datetime import datetime, timedelta


def _fresh(store_mod, tmp_path, name="backoff.db"):
    store = store_mod.Store(db_path=tmp_path / name)
    store.init()
    return store


class TestWriteFormat:
    def test_writes_space_separated(self, scraper_mod):
        count, due = scraper_mod.apply_backoff("missing_plot", 0, now="2026-10-21 03:00:00")
        assert count == 1
        assert "T" not in due
        assert due == "2026-10-21 09:00:00"

    def test_reads_legacy_t_input(self, scraper_mod):
        """入参是老的 `T` 分隔也必须解析得出来（存量行与老调用方都可能这么传）。"""
        _, due = scraper_mod.apply_backoff("missing_plot", 0, now="2026-10-21T03:00:00")
        assert due == "2026-10-21 09:00:00"

    def test_all_five_steps_are_space_separated(self, scraper_mod):
        for index in range(1, 6):
            _, due = scraper_mod.apply_backoff("missing_plot", index - 1,
                                               now="2026-10-21 00:00:00")
            assert "T" not in due, f"第 {index} 档又写成了 T 分隔：{due}"


class TestMetaDueComparison:
    def test_same_day_due_row_is_picked(self, store_mod, scraper_mod, tmp_path):
        """7 小时前失败 → 按 6h 退避的到点时间已过 → **同一天内**必须被 tier1 领到。

        这条就是那个 bug 的现场：`T` 分隔时 `due_at > now` 恒成立，行永远领不到。
        """
        store = _fresh(store_mod, tmp_path)
        now = datetime.now()
        past = (now - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
        _, due_at = scraper_mod.apply_backoff("missing_plot", 0, now=past)
        assert due_at <= now.strftime("%Y-%m-%d %H:%M:%S")
        store.meta_upsert("SSIS-001", next_retry_at=due_at,
                          completeness="missing_plot", retry_count=1)
        assert [row["key"] for row in store.meta_due(tier=1, limit=5)] == ["SSIS-001"]

    def test_future_due_row_is_not_picked(self, store_mod, scraper_mod, tmp_path):
        """刚失败的那条按 +6h 还在未来 → 不许被提前领走。"""
        store = _fresh(store_mod, tmp_path, "future.db")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _, due_at = scraper_mod.apply_backoff("missing_plot", 0, now=now)
        store.meta_upsert("SSIS-002", next_retry_at=due_at,
                          completeness="missing_plot", retry_count=1)
        assert store.meta_due(tier=1, limit=5) == []


class TestMigrationV3:
    def test_normalizes_legacy_timestamps(self, store_mod, tmp_path):
        store = _fresh(store_mod, tmp_path, "legacy.db")
        db = tmp_path / "legacy.db"
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, display_number, next_retry_at, last_scraped_at) "
                "VALUES(?,?,?,?)",
                ("ABC-123", "ABC-123", "2026-10-21T03:00:00", "2026-10-20T12:00:00"),
            )
            conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) "
                         "VALUES('schema_version','2')")
            conn.commit()

        again = store_mod.Store(db_path=db)
        again.init()
        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT next_retry_at, last_scraped_at FROM meta "
                               "WHERE key='ABC-123'").fetchone()
        assert row == ("2026-10-21 03:00:00", "2026-10-20 12:00:00")
        assert again.schema_version() == store_mod._SCHEMA_VERSION

    def test_is_idempotent(self, store_mod, tmp_path):
        store = _fresh(store_mod, tmp_path, "twice.db")
        db = tmp_path / "twice.db"
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT OR REPLACE INTO meta(key, display_number, next_retry_at) "
                         "VALUES(?,?,?)", ("XYZ-9", "XYZ-9", "2026-10-21T01:02:03"))
            conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) "
                         "VALUES('schema_version','2')")
            conn.commit()
        for _ in range(2):
            again = store_mod.Store(db_path=db)
            again.init()                      # 第二次不抛、值不变
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT next_retry_at FROM meta WHERE key='XYZ-9'"
                                ).fetchone()[0] == "2026-10-21 01:02:03"
