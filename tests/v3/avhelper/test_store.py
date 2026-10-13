"""插件自管 SQLite 的读写单测：全部落在 pytest 的临时目录，不碰真实缓存盘。"""

import time


def make_store(store_mod, tmp_path):
    """在临时目录上建一个干净的库。"""
    store = store_mod.Store(db_path=tmp_path / "avhelper.db")
    store.init()
    return store


class TestFavorites:
    """收藏演员。"""

    def test_add_list_delete(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.fav_list() == []
        store.fav_add("桃園怜奈", "桃園憐奈", "/img/a.jpg")
        favs = store.fav_list()
        assert len(favs) == 1 and favs[0]["name"] == "桃園怜奈"
        assert favs[0]["zh"] == "桃園憐奈"
        store.fav_del("桃園怜奈")
        assert store.fav_list() == []

    def test_add_is_idempotent(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.fav_add("A", "甲", "")
        store.fav_add("A", "甲2", "avatar")
        favs = store.fav_list()
        assert len(favs) == 1 and favs[0]["zh"] == "甲2"


class TestSubscriptions:
    """订阅与规则存取。"""

    def test_add_and_read_rule(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        rule = {"res": "1080p", "mustCnsub": True, "minSeeders": 3}
        sid = store.sub_add("number", "IPZZ-961", rule)
        assert sid > 0
        subs = store.sub_list()
        assert len(subs) == 1
        assert subs[0]["type"] == "number" and subs[0]["name"] == "IPZZ-961"
        assert subs[0]["rule"]["mustCnsub"] is True

    def test_same_type_and_name_updates_rule(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.sub_add("actor", "桃園怜奈", {"res": "1080p"})
        store.sub_add("actor", "桃園怜奈", {"res": "2160p"})
        subs = store.sub_list()
        assert len(subs) == 1 and subs[0]["rule"]["res"] == "2160p"

    def test_touch_and_delete(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        sid = store.sub_add("actor", "A", {})
        store.sub_touch(sid, 3)
        subs = store.sub_list()
        assert subs[0]["hits"] == 3 and subs[0]["last"]
        store.sub_del(sid)
        assert store.sub_list() == []


class TestKnown:
    """已知番号。"""

    def test_add_and_list(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.known_add("IPZZ-961", "演员A")
        store.known_add("IPZZ-961", "演员B")  # 重复不报错也不重复记录
        assert store.known_all() == ["IPZZ-961"]


class TestTasks:
    """搜索任务（含规则持久化）。"""

    def test_add_get_and_state(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        task = {
            "id": "t1", "number": "IPZZ-961", "actor": "演员A",
            "cands": [{"site": "观众", "score": 86, "pass": True}],
            "reason": "因为所以", "state": "await", "thumb": "/img/x.jpg", "auto": False,
            "rule": {"savePath": "/downloads/av"},
        }
        store.task_add(task)
        got = store.task_get("t1")
        assert got is not None
        assert got["cands"][0]["score"] == 86
        assert got["rule"]["savePath"] == "/downloads/av"  # 规则必须落库，下载时才能沿用
        store.task_set_state("t1", "pushed")
        assert store.task_get("t1")["state"] == "pushed"


class TestDownloadLedger:
    """下载台账（「下载历史」的数据源）与**来源过滤**。

    2026-10-12 用户把「下载历史」重新定义成「仅保留在当前插件上下载过的视频记录」：
    `source='library'`（番号本来就在 Emby 库里，由补种登记）不再属于这一栏，
    界面侧一律传 `store.PLUGIN_SOURCES`，这里把那条规矩钉住。
    """

    def test_upsert_normalises_key(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.download_upsert("ipzz-00961", title="某部片", state="downloaded", source="plugin")
        rows = store.download_list()
        assert len(rows) == 1
        assert rows[0]["key"] == "IPZZ961"          # 主键是归一化番号
        assert rows[0]["number"] == "ipzz-00961"    # 展示番号原样保留
        assert rows[0]["state"] == "downloaded"
        assert rows[0]["completed_at"]              # 变 downloaded 时自动补完成时间

    def test_plugin_sources_excludes_library_rows(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.download_upsert("IPZZ-961", source="plugin", state="downloaded")
        store.download_upsert("MIMK-283", source="queue", state="downloaded")
        store.download_seed([{"key": "SNOS309", "source": "library", "state": "downloaded"}])

        everything = store.download_list()
        assert {row["key"] for row in everything} == {"IPZZ961", "MIMK283", "SNOS309"}
        assert store_mod.PLUGIN_SOURCES == ["plugin", "queue"]

        picked = store.download_list(store_mod.PLUGIN_SOURCES)
        assert {row["key"] for row in picked} == {"IPZZ961", "MIMK283"}
        assert set(store.download_map(store_mod.PLUGIN_SOURCES)) == {"IPZZ961", "MIMK283"}

    def test_hidden_rows_never_come_back(self, store_mod, tmp_path):
        """「移除记录」= 打墓碑：列表与 map 都不再回它，连来源过滤也救不回来。"""
        store = make_store(store_mod, tmp_path)
        store.download_upsert("IPZZ-961", source="plugin", state="downloaded")
        assert store.download_delete("IPZZ-961") is True
        assert store.download_list(store_mod.PLUGIN_SOURCES) == []
        assert store.download_map(store_mod.PLUGIN_SOURCES) == {}

    def test_reseed_does_not_change_source(self, store_mod, tmp_path):
        """`download_seed` 只补空、不覆盖已有来源：插件下载过的行不会被 library 补种改写。"""
        store = make_store(store_mod, tmp_path)
        store.download_upsert("IPZZ-961", source="plugin", state="downloading")
        store.download_seed([{"key": "IPZZ961", "source": "library", "state": "downloaded"}])
        row = store.download_map()[ "IPZZ961"]
        assert row["source"] == "plugin"
        assert row["state"] == "downloaded"


class TestNotices:
    """通知记录。"""

    def test_add_list_clear(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.notice_add({"kind": "ok", "title": "开始下载", "type": "✅ 任务成功",
                          "body": "IPZZ-961 正在下载", "meta": "分辨率：1080P", "image": "/img/a.jpg"})
        notices = store.notice_list()
        assert len(notices) == 1
        assert notices[0]["title"] == "开始下载" and notices[0]["image"] == "/img/a.jpg"
        store.notice_clear()
        assert store.notice_list() == []

    def test_legacy_publisher_meta_is_repaired_on_read(self, store_mod, tmp_path):
        """老通知的「发布源：馒头 / 馒头 发布 发布」读出来应还原成「发布源：馒头」（不改库）。"""
        store = make_store(store_mod, tmp_path)
        store.notice_add({"title": "开始下载", "body": "ABP-557 正在下载",
                          "meta": "分辨率：1080P  ·  大小：5.3 GB  ·  发布源：馒头 / 馒头 发布 发布"})
        store.notice_add({"title": "已入库", "body": "x", "meta": "发布源：观众 / CMCT 发布"})
        notices = store.notice_list()
        assert notices[0]["meta"] == "发布源：观众 / CMCT 发布"        # 正常文案原样通过
        assert notices[1]["meta"] == "分辨率：1080P  ·  大小：5.3 GB  ·  发布源：馒头"

    def test_keeps_only_latest_200(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        for i in range(205):
            store.notice_add({"title": f"n{i}", "body": "x"})
        notices = store.notice_list()
        assert len(notices) == 200
        assert notices[0]["title"] == "n204"


class TestActorAlias:
    """演员自定义备注（0.6.1 加）：与收藏**解耦**的两张表。

    钉住的规矩：键是演员原名（与 `actor_fav.name` 同口径）、空备注 = **删行**而不是留一条空串、
    `alias_map()` 只回非空项。
    """

    def test_set_and_read(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.alias_map() == {}
        store.alias_set("桃園怜奈", "桃子")
        assert store.alias_map() == {"桃園怜奈": "桃子"}

    def test_set_is_idempotent(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.alias_set("A", "甲")
        store.alias_set("A", "甲2")
        assert store.alias_map() == {"A": "甲2"}

    def test_empty_alias_deletes_row(self, store_mod, tmp_path):
        """「清除备注」= 删行：库里的行必须真的没了，否则下次读还要靠空串兜。"""
        store = make_store(store_mod, tmp_path)
        store.alias_set("A", "甲")
        store.alias_set("B", "乙")
        store.alias_set("A", "")
        assert store.alias_map() == {"B": "乙"}
        with store_mod.sqlite3.connect(store.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM actor_alias").fetchone()[0] == 1

    def test_whitespace_is_normalised(self, store_mod, tmp_path):
        """名字与备注都裁掉首尾空白：不裁的话「  相泽南  」会与「相泽南」存成两行，
        界面按原名查永远查不到（看着像"存了没生效"）。"""
        store = make_store(store_mod, tmp_path)
        store.alias_set("  相泽南  ", "  南南  ")
        assert store.alias_map() == {"相泽南": "南南"}
        store.alias_set("相泽南", "   ")      # 纯空格也算清除
        assert store.alias_map() == {}

    def test_independent_of_favorites(self, store_mod, tmp_path):
        """没收藏的演员也能有备注；取消收藏不该把备注一起带走。"""
        store = make_store(store_mod, tmp_path)
        store.alias_set("桃園怜奈", "桃子")
        assert store.fav_list() == []
        store.fav_add("桃園怜奈", "桃園憐奈", "/img/a.jpg")
        assert store.alias_map() == {"桃園怜奈": "桃子"}
        store.fav_del("桃園怜奈")
        assert store.fav_list() == [] and store.alias_map() == {"桃園怜奈": "桃子"}

    def test_survives_reopen(self, store_mod, tmp_path):
        """落盘：重开一个 Store（插件 reload / 容器重启）后备注仍在。"""
        db = tmp_path / "avhelper.db"
        first = store_mod.Store(db_path=db)
        first.init()
        first.alias_set("桃園怜奈", "桃子")
        second = store_mod.Store(db_path=db)
        second.init()
        assert second.alias_map() == {"桃園怜奈": "桃子"}

    def test_legacy_db_gets_new_table(self, store_mod, tmp_path):
        """向后兼容：老库没有 `actor_alias` 表，`init()` 直接补建（无需 ALTER），老数据不动。"""
        db = tmp_path / "avhelper.db"
        with store_mod.sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE actor_fav(name TEXT PRIMARY KEY, zh TEXT, avatar TEXT, added_at TEXT)")
            conn.execute("INSERT INTO actor_fav VALUES('旧用户','','','2026-01-01 00:00:00')")
        store = store_mod.Store(db_path=db)
        store.init()
        assert [f["name"] for f in store.fav_list()] == ["旧用户"]
        assert store.alias_map() == {}
        store.alias_set("旧用户", "老粉")
        assert store.alias_map() == {"旧用户": "老粉"}


class TestKv:
    """限流计数用的键值存储。"""

    def test_set_get_default(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        assert store.kv_get("missing", 7) == 7
        store.kv_set("num2actor", {"A": "演员"})
        assert store.kv_get("num2actor") == {"A": "演员"}

    def test_ttl_expiry(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.kv_set("short", "v", ttl=-1)  # 已过期
        assert store.kv_get("short") is None

    def test_delete(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.kv_set("k", 1)
        store.kv_del("k")
        assert store.kv_get("k") is None


class TestCacheIndex:
    """缓存文件索引（清理任务用）。"""

    def test_put_expired_and_drop(self, store_mod, tmp_path):
        store = make_store(store_mod, tmp_path)
        store.cache_put("k1", str(tmp_path / "a.jpg"), ttl=3600)
        store.cache_put("k2", str(tmp_path / "b.jpg"), ttl=-1)
        assert len(store.cache_all()) == 2
        expired = store.cache_expired()
        assert [e["key"] for e in expired] == ["k2"]
        store.cache_drop(["k2"])
        assert len(store.cache_all()) == 1

    def test_index_survives_reopen(self, store_mod, tmp_path):
        """索引要落盘：进程重启后清理任务仍能据此找到文件。"""
        db = tmp_path / "avhelper.db"
        first = store_mod.Store(db_path=db)
        first.init()
        first.cache_put("k", "/tmp/x.jpg", ttl=60)
        second = store_mod.Store(db_path=db)
        second.init()
        assert len(second.cache_all()) == 1
