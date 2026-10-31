"""插件自管 SQLite 存储：收藏演员 / 订阅 / 已知番号 / 搜索任务 / 通知 / 缓存索引 / 下载台账，
以及 v4 刮削层的五张表（作品元数据 · 媒体实例 · 三语映射 · 翻译缓存 · 数据源自检日志），
以及 0.9.0 演员线的两张表（`actor` 演员主体 · `actor_queue` 待刮队列）。

数据库落在数据根的 `meta/avhelper.db`（数据根由 `paths` 解析：老部署仍是 `/avhelper/cache`，
新部署落到 MoviePilot 的插件数据目录）。全部方法同步实现，由 FastAPI 的线程池或插件定时任务调用。

**连接模型（v4 刮削线升级，v4.1 §4.1）**：每线程一条**长连接**（`threading.local()`），连接只被
创建它的线程使用（`sqlite3` 的 `check_same_thread` 保持默认 True）；库开 WAL，读直接并发走本线程
连接、**不再排在写锁后面**（`film_view()` 那种高频读是升级动机），写仍统一持 `self._lock` 互斥，
与升级前的并发语义一致。库文件被删/被换掉（`docker cp` 部署会换 db 文件）后由 `_connect()`
按**文件身份**（`st_dev, st_ino`）发现并重开，绝不留下写进已删除 inode 的僵尸连接。
"""

import json
import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


from . import paths

try:                                        # store.py 必须能被**独立加载**（单测就是这么用的）：
    from app.sdk.logging import logger      # 拿不到宿主 logger 就退回标准库，绝不因此 ImportError
except Exception:                           # pragma: no cover - 独立加载分支
    import logging

    logger = logging.getLogger("AVHelper")


#: 写锁等待上限（0.8.1，照 amane v0.22 的 NAS 实测）：10 秒在慢盘 + Emby 扫描时不够，
#: 一次 `database is locked` 会让整条刮削结果丢掉；30 秒仍失败才算真失败。
BUSY_TIMEOUT_MS = 30000
#: `database is locked` 的一次退避重试（秒）：先让出时间片，别把瞬时争用当失败。
LOCK_RETRY_SLEEP = 0.2
#: 慢 SQL 阈值与日志节流（同一进程内最多 60 秒一条，避免刷屏）。
SLOW_SQL_MS = 300
_SLOW_LOG_GAP = 60.0
_slow_lock = threading.Lock()
_slow_last = 0.0


def _log_slow(sql: Any, cost_ms: float) -> None:
    """记一条慢 SQL（阈值 300ms，60 秒节流）；只记语句首 160 字，不记参数（可能带密钥）。"""
    global _slow_last
    if cost_ms < SLOW_SQL_MS:
        return
    now = time.monotonic()
    with _slow_lock:
        if now - _slow_last < _SLOW_LOG_GAP:
            return
        _slow_last = now
    text = " ".join(str(sql or "").split())[:160]
    logger.warning(f"AVHelper SQL 慢查询 {cost_ms:.0f}ms：{text}")


def _run(conn: sqlite3.Connection, sql: str, args: tuple, fetch: bool) -> Any:
    """执行一条语句；`database is locked` 退避重试一次（0.8.1）。

    只对**锁冲突**重试：语句根本没开始执行，重试是安全的；语法/约束错误照旧立刻抛。
    """
    try:
        cur = conn.execute(sql, args)
    except sqlite3.OperationalError as error:
        if "locked" not in str(error).lower():
            raise
        time.sleep(LOCK_RETRY_SLEEP)
        cur = conn.execute(sql, args)
    return cur.fetchall() if fetch else None


def _run_count(conn: sqlite3.Connection, sql: str, args: tuple) -> int:
    """同 `_run` 的锁重试口径，但回受影响行数（`_exec_count` 的条件写要用）。"""
    try:
        cur = conn.execute(sql, args)
    except sqlite3.OperationalError as error:
        if "locked" not in str(error).lower():
            raise
        time.sleep(LOCK_RETRY_SLEEP)
        cur = conn.execute(sql, args)
    return int(cur.rowcount or 0)


def _norm_key(text: Any) -> str:
    """番号归一化：借用 `emby.norm_key()`，延迟导入以便本模块在无宿主环境下被单测直接加载。

    台账的 key 与番号归一化必须共用同一份规则（`emby.norm_key`）：同一个番号在 javdb 番号、
    Emby 文件名、历史刮削 id 里写法不同，两边各写一份迟早会漂。`emby.py` 依赖 `app.sdk`，
    模块级导入会让 `store` 无法脱离宿主被单测加载，所以放到调用点再导。
    """
    from . import emby

    return emby.norm_key(text)


# 台账里「**本插件下载的**」那几种来源：`plugin` = 插件提交下载 / 磁力下载，
# `queue` = 0.3.4 之前老下载队列里已完成、迁移进来的条目（同样是插件推给下载器的）。
# 反过来 `library` = 番号本来就在 Emby 库里、由补种登记的行 —— 用户 2026-10-12 明确
# 「下载历史只保留在当前插件上下载过的视频记录」，所以界面侧（列表/徽标/重复提示）
# 一律只看这几种来源，见 `AVHelper._downloads_payload()` 与 `_downloaded_keys()`。
PLUGIN_SOURCES: List[str] = ["plugin", "queue"]

# 建表语句：与执行方案 §6.3 的表结构一致，另加 notice/kv 两张辅助表。
# `downloads` 里 v4 新增的三列（version_tags/emby_id/failed_reason）同时写在这里与
# `_DL_ADD_COLUMNS`：新库一次建全，老库走 ALTER 补列，两条路径的列定义必须逐字相同。
_SCHEMA = """
CREATE TABLE IF NOT EXISTS actor_fav(
  name TEXT PRIMARY KEY, zh TEXT, avatar TEXT, added_at TEXT);
CREATE TABLE IF NOT EXISTS actor_alias(
  name TEXT PRIMARY KEY, alias TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS sub(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL, name TEXT NOT NULL, rule TEXT NOT NULL,
  hits INTEGER DEFAULT 0, last_check TEXT, created_at TEXT,
  UNIQUE(type, name));
CREATE TABLE IF NOT EXISTS known(
  number TEXT PRIMARY KEY, actor TEXT, added_at TEXT);
CREATE TABLE IF NOT EXISTS task(
  id TEXT PRIMARY KEY, number TEXT, actor TEXT,
  cands TEXT, reason TEXT, state TEXT,
  thumb TEXT, auto INTEGER DEFAULT 0, created_at TEXT, rule TEXT,
  source TEXT DEFAULT 'manual',
  pending TEXT DEFAULT '',
  updated_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS notice(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, title TEXT, type TEXT,
  body TEXT, meta TEXT, image TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS cache_idx(
  key TEXT PRIMARY KEY, path TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS kv(
  key TEXT PRIMARY KEY, val TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS schema_meta(
  key TEXT PRIMARY KEY, val TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS downloads(
  key          TEXT PRIMARY KEY,   -- emby.norm_key(番号)：IPZZ-961 / ipzz00961 / IPZZ961 归一到同一个
  number       TEXT DEFAULT '',    -- 展示用番号（javdb 口径 IPZZ-961）
  title        TEXT DEFAULT '',
  actor        TEXT DEFAULT '',
  thumb        TEXT DEFAULT '',    -- 图床**原地址**（读的时候再转 /img 代理，避免代理套代理）
  size         INTEGER DEFAULT 0,  -- 字节，未知 0
  hash         TEXT DEFAULT '',
  path         TEXT DEFAULT '',    -- 库里/整理后的路径（Emby 有就优先 Emby 的 Path）
  downloader   TEXT DEFAULT '',
  state        TEXT DEFAULT 'downloading',  -- downloading | downloaded
  source       TEXT DEFAULT 'plugin',       -- plugin=插件提交 | library=在 Emby 库里发现 | queue=老队列迁移
  created_at   TEXT DEFAULT '',    -- 首次登记（本地时间 'YYYY-MM-DD HH:MM:SS'）
  completed_at TEXT DEFAULT '',    -- 完成/确认已下载
  updated_at   TEXT DEFAULT '',
  hidden       INTEGER DEFAULT 0,  -- 1=用户点过「移除记录」的墓碑：列表不回它，补种也种不回来
  version_tags TEXT DEFAULT '{}',  -- v4：版本标签 JSON（中字/流出/分辨率…），'{}' = 未知
  emby_id      TEXT DEFAULT '',    -- v4：入库后的 Emby ItemId（跨「已下载 ↔ 已入库」对号）
  failed_reason TEXT DEFAULT ''    -- v4：下载失败原因（v4.1 §9.2-1，state='failed' 时才有值）
);
-- 索引见 `_ensure_indexes()`（与补列分开：老库可能缺索引用到的列，见那里的说明）
"""

# `schema_meta`（P1-8）：**这个库走在哪一版**的唯一真值。
# 与业务表分开一段、且在 `_bootstrap()` 里单独先跑一次 —— 老库连这张表都没有，
# 而"读版本 → 决定要不要备份"这一步必须发生在任何结构改动之前。
# 与 `_SCHEMA` 里那份是同一张表（都带 `IF NOT EXISTS`，重复执行无害）。
_SCHEMA_SCHEMA_META = """
CREATE TABLE IF NOT EXISTS schema_meta(
  key TEXT PRIMARY KEY, val TEXT DEFAULT '');
"""

# v4 刮削层五张表：**DDL 照 v4.1 §4.2 原样**（字段名与默认值一个都不许改）。
# 都是 `IF NOT EXISTS`，所以重复 init() 幂等。
_SCHEMA_SCRAPE_V4 = """
CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    display_number TEXT NOT NULL,
    javdb_id TEXT DEFAULT '',
    title_jp TEXT DEFAULT '',
    title_zh TEXT DEFAULT '',
    plot_jp TEXT DEFAULT '',
    plot_zh TEXT DEFAULT '',
    translation_status TEXT DEFAULT 'untranslated',
    actors_json TEXT DEFAULT '[]',
    tags_json TEXT DEFAULT '[]',
    studio TEXT DEFAULT '',
    series TEXT DEFAULT '',
    director TEXT DEFAULT '',
    release_date TEXT DEFAULT '',
    runtime_min INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    cover_raw_url TEXT DEFAULT '',
    samples_json TEXT DEFAULT '[]',
    trailer_url TEXT DEFAULT '',
    raw_json TEXT DEFAULT '{}',
    completeness TEXT DEFAULT 'missing_core',
    retry_count INTEGER DEFAULT 0,
    next_retry_at TEXT DEFAULT '',
    last_scraped_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    field_sources_json TEXT DEFAULT '{}'
);
-- P1-9：重刮两档队列的索引在 `_ensure_indexes()` 里建（**必须在补列之后** ——
-- 老库的 `meta` 可能还没有 `next_retry_at` 列，索引写在这里会直接让 init() 报错）。
-- 索引列与 `meta_due()` 的 ORDER BY 逐字对齐。

CREATE TABLE IF NOT EXISTS media_item(
    item_key TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    display_number TEXT NOT NULL,
    emby_id TEXT DEFAULT '',
    file_path TEXT DEFAULT '',
    version_tags_json TEXT DEFAULT '{}',
    crop_anchor TEXT DEFAULT 'auto',
    download_state TEXT DEFAULT 'none',
    library_state TEXT DEFAULT 'not_in_library',
    scrape_state TEXT DEFAULT 'unscraped',
    emby_backup_json TEXT DEFAULT '',
    last_synced_at TEXT DEFAULT ''
);
-- 索引见 `_ensure_indexes()`（必须在补列之后建）

CREATE TABLE IF NOT EXISTS name_map(
    canonical_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    zh_cn TEXT DEFAULT '',
    zh_tw TEXT DEFAULT '',
    jp TEXT DEFAULT '',
    keywords_norm TEXT DEFAULT ',',
    javdb_actor_id TEXT DEFAULT '',
    emby_person_id TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    is_delete_rule INTEGER DEFAULT 0,
    source TEXT DEFAULT 'builtin_xml',
    updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS translate(
    cache_key TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    model_name TEXT DEFAULT '',
    quality_tier TEXT DEFAULT 'llm',
    created_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scrape_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    key TEXT DEFAULT '',
    status TEXT NOT NULL,
    latency_ms INTEGER DEFAULT 0,
    error_summary TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    http_status INTEGER DEFAULT 0,
    run_id TEXT DEFAULT ''
);
-- 索引见 `_ensure_indexes()`（**必须在补列之后**：老库的 scrape_log 没有 run_id，
-- 索引写在这里会 `no such column: run_id` 直接把插件启动打挂 —— 2026-10-15 部署实测）

-- 0.8.0 / P0-3：**逐站快照**（"只重算不重抓"的凭据）。
-- 与 `meta.raw_json` 的分工：那边是给人看的**摘要**（URL/vid/长度，且受 5KB 上限），
-- 这里是给机器**复用**的完整结果（`javtxt_lookup()` 的返回形状），
-- 于是"换字段聚合策略时只重算不重抓"才能在**单个源**的粒度上成立。
CREATE TABLE IF NOT EXISTS site_snapshot(
    key TEXT NOT NULL,
    site TEXT NOT NULL,
    fetched_at TEXT DEFAULT '',
    status TEXT DEFAULT '',
    run_id TEXT DEFAULT '',
    payload_json TEXT DEFAULT '{}',
    PRIMARY KEY(key, site)
);
-- 索引见 `_ensure_indexes()`
"""

# 0.9.0 演员线两张表：**DDL 按 `docs/AVHelper-演员刮削子系统方案.md` §2 原样**（列名一个都不许改）。
# 一条演员一行，业务唯一键 `person` 是 Emby `People[].Name` 的 D13 规范名（全链路唯一的精确键）；
# 头像本体在 imgproxy 的 URL 缓存里（磁盘），所以这里只存 URL 与尺寸，**不建 actor_image 表**
# —— 删表不删图，缓存淘汰仍归现有清理逻辑。
_SCHEMA_ACTOR = """
CREATE TABLE IF NOT EXISTS actor(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  person TEXT UNIQUE NOT NULL,
  name TEXT DEFAULT '', zh TEXT DEFAULT '', jp TEXT DEFAULT '',
  gender INTEGER,
  aliases_json TEXT DEFAULT '[]',
  javdb_actor_id TEXT DEFAULT '',
  images_json TEXT DEFAULT '[]',
  field_sources_json TEXT DEFAULT '{}',
  locked_fields_json TEXT DEFAULT '[]',
  last_scraped_at TEXT DEFAULT '',
  retry_count INTEGER DEFAULT 0,
  next_retry TEXT DEFAULT '',
  updated_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS actor_queue(
  actor_id INTEGER PRIMARY KEY,
  person TEXT DEFAULT '',
  state TEXT DEFAULT 'wait',
  created_at TEXT DEFAULT '',
  taken_at TEXT DEFAULT ''
);
-- 索引见 `_ensure_indexes()`：建表脚本里不建索引（老库半截迁移时缺列，建索引会打挂启动）
"""

# 老库动态补列（SQLite 的 ALTER TABLE ADD COLUMN 没有 IF NOT EXISTS，先看 PRAGMA table_info 再补）。
# `hidden` 是 0.3.4 加的墓碑列，后三条是 v4 刮削线加的，声明与 `_SCHEMA` 里的逐字一致。
_DL_ADD_COLUMNS = (
    ("hidden", "INTEGER DEFAULT 0"),
    ("version_tags", "TEXT DEFAULT '{}'"),
    ("emby_id", "TEXT DEFAULT ''"),
    ("failed_reason", "TEXT DEFAULT ''"),
)

# 0.8.0 的 P0-2：scrape_log 补三列（**追加在末尾**，保证「新库建全」与「老库 ALTER」两条路径的
# 列顺序逐字相同 —— 0.6.3 定的口径）。`reason` 是机器可读的失败原因（`scraper.REASONS`），
# `http_status` 是 HTTP 状态码（0 = 没拿到响应），`run_id` 把同一次刮削的各源记录串成一组。
_SL_ADD_COLUMNS = (
    ("reason", "TEXT DEFAULT ''"),
    ("http_status", "INTEGER DEFAULT 0"),
    ("run_id", "TEXT DEFAULT ''"),
)

# 台账行固定的列顺序：`download_list` 的 SELECT 与 `_download_row` 的下标都按它来，
# 加列只能往后追加（老调用方拿到的是 dict，不受影响）。
_DL_COLUMNS = (
    "key", "number", "title", "actor", "thumb", "size", "hash", "path", "downloader",
    "state", "source", "created_at", "completed_at", "updated_at", "hidden",
    "version_tags", "emby_id", "failed_reason",
)
_DL_SELECT = ", ".join(_DL_COLUMNS)

# 两套合并规则共用同一段 INSERT，只有 DO UPDATE 那一段不同（并排放着好对照）：
#   _DL_UPSERT —— 提交下载 / 队列完成登记：**非空就覆盖**（谁最后登记听谁的）
#   _DL_SEED   —— Emby 库里补种 / 老队列迁移：**只补空，绝不覆盖已有非空值**
# seed 为什么要更保守：它的来源是 Emby 库，name/path 是从文件名派生的弱信息，而插件提交下载
# 写进来的 title/number/path 是权威口径（javdb 标题、真实的下载保存路径）；seed 每次打开历史页
# 都会跑一遍，允许覆盖就等于让库里的写法反复把权威值顶掉。
# 为什么「不覆盖」落到 SQL 里，而不是先读出来在 Python 里挑字段：同一番号会被多条路径反复登记
# （提交下载只有番号+hash+路径，队列完成才有状态），而补种与迁移可能同时在跑；先读后写中间有
# 窗口，晚写的会拿空值盖掉刚攒下的信息。
_DL_INSERT = """
INSERT INTO downloads(key, number, title, actor, thumb, size, hash, path, downloader,
                      state, source, created_at, completed_at, updated_at, hidden,
                      version_tags, emby_id, failed_reason)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)
ON CONFLICT(key) DO UPDATE SET
"""

# size 的「空」是 0（台账里 0 表示未知），文本列的「空」是空串；IFNULL 顺手兜住 NULL。
# `version_tags` 的「空」是 `'{}'`（与列默认值同口径：没拿到版本信息 ≠ 没有版本信息）——
# 不这么写的话，任何一次不带版本标签的普通登记（如队列完成）都会把已记下的标签抹成 `{}`。
_DL_UPSERT = _DL_INSERT + """
  number       = CASE WHEN excluded.number <> '' THEN excluded.number ELSE downloads.number END,
  title        = CASE WHEN excluded.title <> '' THEN excluded.title ELSE downloads.title END,
  actor        = CASE WHEN excluded.actor <> '' THEN excluded.actor ELSE downloads.actor END,
  thumb        = CASE WHEN excluded.thumb <> '' THEN excluded.thumb ELSE downloads.thumb END,
  size         = CASE WHEN excluded.size > 0 THEN excluded.size ELSE downloads.size END,
  hash         = CASE WHEN excluded.hash <> '' THEN excluded.hash ELSE downloads.hash END,
  path         = CASE WHEN excluded.path <> '' THEN excluded.path ELSE downloads.path END,
  downloader   = CASE WHEN excluded.downloader <> '' THEN excluded.downloader ELSE downloads.downloader END,
  state        = CASE WHEN excluded.state <> '' THEN excluded.state ELSE downloads.state END,
  source       = CASE WHEN excluded.source <> '' THEN excluded.source ELSE downloads.source END,
  created_at   = downloads.created_at,
  completed_at = CASE WHEN downloads.completed_at <> '' THEN downloads.completed_at
                      ELSE excluded.completed_at END,
  updated_at   = excluded.updated_at,
  hidden       = 0,                -- 用户又下了一遍：之前「移除记录」的墓碑就此解除
  version_tags = CASE WHEN excluded.version_tags NOT IN ('', '{}') THEN excluded.version_tags
                      ELSE downloads.version_tags END,
  emby_id      = CASE WHEN excluded.emby_id <> '' THEN excluded.emby_id ELSE downloads.emby_id END,
  failed_reason = CASE WHEN excluded.failed_reason <> '' THEN excluded.failed_reason
                       ELSE downloads.failed_reason END
"""

# 与 _DL_UPSERT 逐行对照：前八列（外加 source）都换成「只补空」，state / completed_at /
# updated_at 三条规则保持不变 —— 补种要能把记录标成已下载并补上完成时间，那是它的本职。
_DL_SEED = _DL_INSERT + """
  number       = CASE WHEN IFNULL(downloads.number, '') = '' THEN excluded.number ELSE downloads.number END,
  title        = CASE WHEN IFNULL(downloads.title, '') = '' THEN excluded.title ELSE downloads.title END,
  actor        = CASE WHEN IFNULL(downloads.actor, '') = '' THEN excluded.actor ELSE downloads.actor END,
  thumb        = CASE WHEN IFNULL(downloads.thumb, '') = '' THEN excluded.thumb ELSE downloads.thumb END,
  size         = CASE WHEN IFNULL(downloads.size, 0) = 0 THEN excluded.size ELSE downloads.size END,
  hash         = CASE WHEN IFNULL(downloads.hash, '') = '' THEN excluded.hash ELSE downloads.hash END,
  path         = CASE WHEN IFNULL(downloads.path, '') = '' THEN excluded.path ELSE downloads.path END,
  downloader   = CASE WHEN IFNULL(downloads.downloader, '') = '' THEN excluded.downloader
                      ELSE downloads.downloader END,
  state        = CASE WHEN excluded.state <> '' THEN excluded.state ELSE downloads.state END,
  source       = CASE WHEN IFNULL(downloads.source, '') = '' THEN excluded.source ELSE downloads.source END,
  created_at   = downloads.created_at,
  completed_at = CASE WHEN downloads.completed_at <> '' THEN downloads.completed_at
                      ELSE excluded.completed_at END,
  updated_at   = excluded.updated_at,
  hidden       = downloads.hidden,  -- 补种绝不解除墓碑：用户删过的记录不能被库里种回来
  version_tags = CASE WHEN IFNULL(downloads.version_tags, '') IN ('', '{}') THEN excluded.version_tags
                      ELSE downloads.version_tags END,
  emby_id      = CASE WHEN IFNULL(downloads.emby_id, '') = '' THEN excluded.emby_id
                      ELSE downloads.emby_id END,
  failed_reason = CASE WHEN IFNULL(downloads.failed_reason, '') = '' THEN excluded.failed_reason
                       ELSE downloads.failed_reason END
"""

# ---------- v4 新表的列清单（顺序 = DDL 顺序，「只覆盖传入字段 / 插入时按建表默认值补全」都读它） ----------

_META_COLUMNS = (
    "key", "display_number", "javdb_id", "title_jp", "title_zh", "plot_jp", "plot_zh",
    "translation_status", "actors_json", "tags_json", "studio", "series", "director",
    "release_date", "runtime_min", "rating", "cover_raw_url", "samples_json",
    "trailer_url", "raw_json", "completeness", "retry_count", "next_retry_at",
    "last_scraped_at", "updated_at", "field_sources_json",
)
# 可写字段：主键与 updated_at 不能从外面传（updated_at 由 meta_upsert 自己写）
_META_FIELDS = frozenset(_META_COLUMNS) - {"key", "updated_at"}
#: 可当**过滤条件**的列（P1-9：`meta_list(**filters)` 按列名等值过滤，白名单之外一律忽略）
_META_COLUMN_SET = frozenset(_META_COLUMNS)
_META_DEFAULTS: Dict[str, Any] = {
    "display_number": "", "javdb_id": "", "title_jp": "", "title_zh": "", "plot_jp": "",
    "plot_zh": "", "translation_status": "untranslated", "actors_json": "[]", "tags_json": "[]",
    "studio": "", "series": "", "director": "", "release_date": "", "runtime_min": 0, "rating": 0,
    "cover_raw_url": "", "samples_json": "[]", "trailer_url": "", "raw_json": "{}",
    "completeness": "missing_core", "retry_count": 0, "next_retry_at": "", "last_scraped_at": "",
    "field_sources_json": "{}",
}
_META_JSON_FIELDS = {"actors_json": "[]", "tags_json": "[]", "samples_json": "[]", "raw_json": "{}",
                     "field_sources_json": "{}"}
_META_INT_FIELDS = frozenset({"runtime_min", "retry_count"})
_META_FLOAT_FIELDS = frozenset({"rating"})
_META_SELECT = ", ".join(_META_COLUMNS)

#: `meta` 的后加列（老库走 ALTER 补；**追加在最后**，与新库 DDL 的顺序一致）。
#: 0.8.0 / P0-1 加的 `field_sources_json` = 逐字段溯源（`{"plot_zh": "javtxt", …}`）。
_META_ADD_COLUMNS = (
    ("field_sources_json", "TEXT DEFAULT '{}'"),
)

_ITEM_COLUMNS = (
    "item_key", "key", "display_number", "emby_id", "file_path", "version_tags_json",
    "crop_anchor", "download_state", "library_state", "scrape_state", "emby_backup_json",
    "last_synced_at",
)
# 可写字段：主键不能传；`emby_backup_json` **只能**由 item_backup_save() 写一次
# （v4.1 §8.1 / 裁决 D7：一切 Emby 写操作先落完整 DTO 备份，无备份不许写），
# 所以它不在通用写入字段里，`item_set` / `item_upsert` 都碰不到它。
_ITEM_FIELDS = frozenset(_ITEM_COLUMNS) - {"item_key", "emby_backup_json"}
_ITEM_COLUMN_SET = frozenset(_ITEM_COLUMNS)
_ITEM_DEFAULTS: Dict[str, Any] = {
    "key": "", "display_number": "", "emby_id": "", "file_path": "", "version_tags_json": "{}",
    "crop_anchor": "auto", "download_state": "none", "library_state": "not_in_library",
    "scrape_state": "unscraped", "emby_backup_json": "", "last_synced_at": "",
}
_ITEM_JSON_FIELDS = {"version_tags_json": "{}"}
_ITEM_SELECT = ", ".join(_ITEM_COLUMNS)

_NAME_MAP_COLUMNS = (
    "canonical_id", "entity_type", "zh_cn", "zh_tw", "jp", "keywords_norm",
    "javdb_actor_id", "emby_person_id", "avatar_url", "is_delete_rule", "source", "updated_at",
)
_NAME_MAP_FIELDS = frozenset(_NAME_MAP_COLUMNS) - {"canonical_id", "updated_at"}
_NAME_MAP_SELECT = ", ".join(_NAME_MAP_COLUMNS)
_NAME_MAP_DEFAULTS: Dict[str, Any] = {
    "entity_type": "", "zh_cn": "", "zh_tw": "", "jp": "", "keywords_norm": ",",
    "javdb_actor_id": "", "emby_person_id": "", "avatar_url": "", "is_delete_rule": 0,
    "source": "builtin_xml",
}

# ---------- 0.9.0 演员线（actor / actor_queue） ----------

_ACTOR_COLUMNS = (
    "id", "person", "name", "zh", "jp", "gender", "aliases_json", "javdb_actor_id",
    "images_json", "field_sources_json", "locked_fields_json", "last_scraped_at",
    "retry_count", "next_retry", "updated_at",
)
_ACTOR_SELECT = ", ".join(_ACTOR_COLUMNS)
_ACTOR_DEFAULTS: Dict[str, Any] = {
    "person": "", "name": "", "zh": "", "jp": "", "gender": None, "aliases_json": "[]",
    "javdb_actor_id": "", "images_json": "[]", "field_sources_json": "{}",
    "locked_fields_json": "[]", "last_scraped_at": "", "retry_count": 0,
    "next_retry": "", "updated_at": "",
}
_ACTOR_JSON_FIELDS = {"aliases_json": "[]", "images_json": "[]",
                      "field_sources_json": "{}", "locked_fields_json": "[]"}
#: 资料列：`actor_set_profile()` 与 `actor_upsert()` 共用（逐列判"空值不写"与"锁了就跳过"）
_ACTOR_PROFILE_FIELDS = frozenset({"name", "zh", "jp", "gender", "aliases_json", "javdb_actor_id"})
#: `actor_upsert()` 能写的列 = 资料列 + `person`。**状态列不在里面**（理由见 actor_upsert 的 docstring）
_ACTOR_UPSERT_FIELDS = _ACTOR_PROFILE_FIELDS | {"person"}

#: 演员失败退避序列（小时），第 1..5 档；第 6 次到顶后不再排期。
#: 与 `scraper.BACKOFF_HOURS` **同源同值**（方案 §4：与影片刮削同一个 6h→24h→72h→7d→14d 序列），
#: 这里另写一份是因为 `scraper` 已经 import 了 `store`，反向 import 会成环；**改序列时两处一起改**。
BACKOFF_HOURS: Tuple[int, ...] = (6, 24, 72, 168, 336)

# 自检日志保留条数：`scrape_log_add` 每次都顺手裁到最近这么多条（照 notice 只留 200 条的思路；
# 全库一轮刮削约 3 个源 × 每个番号一条，给足重扫余量又不让它无限长）。
_SCRAPE_LOG_KEEP = 2000

# 判定「这条 SQL 是读」的首关键字：`_exec` 据此决定要不要持锁（写一律持锁）。
# 只认死这几种，其余（含 `WITH …`，它可能是 CTE 包着的写）统统按写处理 —— 判断错的方向
# 必须是「多持一把锁」，绝不能是「写了却没持锁」。
_READ_VERBS = frozenset({"SELECT", "PRAGMA", "EXPLAIN", "VALUES"})


def _is_read_sql(sql: Any) -> bool:
    """这条 SQL 是不是只读的（`_exec` 的持锁判据）。"""
    text = str(sql or "").lstrip()
    if not text:
        return False
    return text.split(None, 1)[0].upper() in _READ_VERBS


def _now() -> str:
    """当前时间字符串，统一写库格式。"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _item_order(raw: Any) -> str:
    """`item_list(order=…)` 的**排序白名单**（P1-9）：只认 `media_item` 的列名。

    认这几种写法（其余一律回默认排序，绝不拼进 SQL）：
    `"last_synced_at"`（升序）/ `"-last_synced_at"`（降序）/ 老的 `"last_synced_at DESC"`。

    amane 的教训（`docs/dev/api.md`）：排序参数**必须走白名单**，不许反射列名 ——
    老写法是把调用方给的整段片段塞进 `ORDER BY`，那是个注入面。
    """
    text = str(raw or "").strip()
    if not text:
        return "item_key ASC"
    body = text[1:] if text[:1] in ("-", "+") else text
    parts = body.replace(",", " ").split()
    if not parts or parts[0] not in _ITEM_COLUMN_SET:
        logger.warning(f"AVHelper item_list(order=…) 认不出的排序（已回默认）：{text[:80]}")
        return "item_key ASC"
    if len(parts) == 2 and parts[1].upper() in ("ASC", "DESC"):
        return f"{parts[0]} {parts[1].upper()}"
    if len(parts) > 2:
        logger.warning(f"AVHelper item_list(order=…) 只认单列排序（已回默认）：{text[:80]}")
        return "item_key ASC"
    return f"{parts[0]} {'DESC' if text[:1] == '-' else 'ASC'}"


def _shift_days(days: int) -> str:
    """当前时间往前/后挪 `days` 天（同样的字符串格式；给快照淘汰算 cutoff 用）。"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + days * 86400))


def _shift_hours(hours: int, base: str = "") -> str:
    """把 `base`（缺省现在）往后挪 `hours` 小时，落库格式与 `_now()` 逐字相同。

    与 `_shift_days()` 分开写而不是让它转发，是因为退避排期要按**小时**算，而
    `actor_due()` 拿 `next_retry` 与 `_now()` 做**字典序**比较 —— 两头必须同一种格式，
    差一个字符就会把"到点"判成"没到"（`scraper.apply_backoff()` 用的是 ISO 的 `T`，
    ASCII 里比空格大 0x34，混着用会让比较整体偏一天的量级）。
    """
    stamp = str(base or "").strip()
    base_at = time.time()
    if stamp:
        try:
            base_at = time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            base_at = time.time()
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(base_at + int(hours) * 3600))


#: 单条快照的体积上限（64KB）：快照是加速器，超了就不写 —— 别把库撑爆
_SNAPSHOT_LIMIT = 65536


def _repair_columns(conn: sqlite3.Connection) -> None:
    """补列（v1 基线 + **结构自愈**）：`task` / `downloads` / `scrape_log` / `meta`。

    全部"先看列在不在再 ALTER"，幂等；**绝不 DROP 重建** —— 用户的台账、日志、任务不能丢。
    单独抽成一个函数是为了两处都用它：版本门控里的 v1 迁移，以及"版本表说已迁过、但列真的缺了"
    （人工 DROP / 半截迁移）时的自愈 —— 后者**只补列、不改版本**。
    """
    # 兼容旧库：rule/source 是后加的列，缺失时补上（SQLite 无 IF NOT EXISTS 语法）
    for name, decl in (("rule", "TEXT"), ("source", "TEXT DEFAULT 'manual'")):
        try:
            conn.execute(f"ALTER TABLE task ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass
    # pending 是 0.6.0 后加的列（任务卡上的「PT/BT 待确认」/「所有源均未找到」标记）。
    # updated_at 是 0.8.0（P1-7）加的列 —— 条件写要能看出"这条什么时候动过"。
    # 两列在老行上读出来都是空串（不是 NULL）：界面按空串显示"—"。
    task_cols = {r[1] for r in conn.execute("PRAGMA table_info(task)").fetchall()}
    for name, decl in (("pending", "TEXT DEFAULT ''"), ("updated_at", "TEXT DEFAULT ''")):
        if name in task_cols:
            continue
        try:
            conn.execute(f"ALTER TABLE task ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass
    # downloads：hidden 是 0.3.4 的墓碑列，v4 又加三条（见 `_DL_ADD_COLUMNS`）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(downloads)").fetchall()}
    for name, decl in _DL_ADD_COLUMNS:
        if name in cols:
            continue
        try:
            conn.execute(f"ALTER TABLE downloads ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass
    # scrape_log：0.8.0 的 reason / http_status / run_id（日志是排障凭据）
    log_cols = {r[1] for r in conn.execute("PRAGMA table_info(scrape_log)").fetchall()}
    for name, decl in _SL_ADD_COLUMNS:
        if name in log_cols:
            continue
        try:
            conn.execute(f"ALTER TABLE scrape_log ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass
    # meta：0.8.0 的 field_sources_json
    meta_cols = {r[1] for r in conn.execute("PRAGMA table_info(meta)").fetchall()}
    for name, decl in _META_ADD_COLUMNS:
        if name in meta_cols:
            continue
        try:
            conn.execute(f"ALTER TABLE meta ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass


#: 全部索引（**统一在这里、且只在补列之后建**）。列与 `meta_due()` 的 ORDER BY 逐字对齐。
_INDEXES: "Tuple[Tuple[str, str], ...]" = (
    ("idx_downloads_completed", "downloads(completed_at DESC, created_at DESC)"),
    ("idx_meta_next_retry", "meta(next_retry_at, updated_at)"),
    ("idx_meta_last_scraped", "meta(last_scraped_at, updated_at)"),
    ("idx_media_item_key", "media_item(key)"),
    ("idx_media_item_emby", "media_item(emby_id)"),
    ("idx_scrape_log_source", "scrape_log(source_name, id DESC)"),
    ("idx_scrape_log_run", "scrape_log(run_id)"),
    ("idx_site_snapshot_fetched", "site_snapshot(fetched_at)"),
    # 0.9.0 演员线：`actor_due()` 的 WHERE + ORDER BY（next_retry / last_scraped_at）与队列领取
    # 各一条。列序与 SQL 逐字对齐，且**只在这里建**（补齐列之后，单条失败只 warning）。
    ("idx_actor_next_retry", "actor(next_retry, last_scraped_at)"),
    ("idx_actor_last_scraped", "actor(last_scraped_at)"),
    ("idx_actor_queue_state", "actor_queue(state, created_at)"),
)


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    """建全部索引。**必须在补列之后调用**（列还不存在时 `CREATE INDEX` 会直接报错）。

    单条失败只记日志、继续建下一条：索引是**性能**优化，不是数据完整性的一部分 ——
    某个老库的列真出问题时，宁可少一条索引也不该让插件起不来（2026-10-15 的教训）。
    """
    for name, target in _INDEXES:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")
        except sqlite3.OperationalError as error:
            logger.warning(f"AVHelper 建索引 {name} 失败（跳过，不影响功能）：{error}")


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """迁移 v2（0.9.0 演员线）：建 `actor` / `actor_queue` 两张表。

    建表落在**迁移函数**里（而不是散落的 try/except ALTER）：`_MIGRATIONS` 是"这个库走在
    哪一版"的唯一执行序列，`schema_meta.schema_version` 与它一一对应 —— 表结构一次性建全，
    之后要改就再追加一条 v3，绝不回头改这一条。
    `IF NOT EXISTS` 让它天然幂等：老库上反复 init()、以及"版本已是 2 但表被手工 DROP"都收敛。
    **索引不在这里建**：老库的 actor 表可能来自半截迁移（缺列），建索引失败会打挂插件启动
    —— 统一放到 `_ensure_indexes()`（2026-10-15 的真机教训）。
    """
    conn.executescript(_SCHEMA_ACTOR)


#: schema 版本 + **有序**迁移表（P1-8）。加迁移 = 往后面追加一条，**不改已有条目**。
#: 版本号只增不减；`schema_meta.schema_version` 是"这个库走在哪一版"的唯一真值。
def _migrate_v3(conn: sqlite3.Connection) -> None:
    """迁移 v3（0.9.0 修复）：把 `meta` 里 `T` 分隔的时间戳统一改写成空格分隔。

    病根：`scraper.apply_backoff()` 过去写 `2026-10-21T03:00:00`，而 `meta_due()` 拿它跟
    `time.strftime("%Y-%m-%d %H:%M:%S")` 做**字典序比较** —— `'T'(0x54) > ' '(0x20)`，
    于是同一天到点的行被判成「还没到」，Tier1 退避要等**日期翻页**才被领走（6h 退化成「明天再说」）。
    写入侧已同步改成空格分隔，这里把存量行就地改写，两边收敛到同一口径。

    幂等：`WHERE ... LIKE '%T%'` 跑第二遍就是 0 行；列缺失（更老的老库）只 warning、不抛。
    """
    for column in ("next_retry_at", "last_scraped_at"):
        try:
            conn.execute(f"UPDATE meta SET {column}=REPLACE({column},'T',' ') "
                         f"WHERE {column} LIKE '%T%'")
        except sqlite3.OperationalError as error:                # 老库可能还没有这一列
            logger.warning(f"AVHelper 迁移 v3：改写 meta.{column} 失败（跳过）：{error}")


_SCHEMA_VERSION = 3
_MIGRATIONS: "List[Tuple[int, str, Callable[[sqlite3.Connection], None]]]" = [
    (1, "task/downloads/scrape_log/meta 补列", _repair_columns),
    (2, "actor", _migrate_v2),
    (3, "meta 时间戳统一成空格分隔", _migrate_v3),
]

#: 任务状态清单（0.8.0 / P1-7 / 0.9.2 A1）：**只加不改**，改一个旧值就等于让历史行"状态未知"。
#:
#: - `await`      待确认（搜到候选、等用户点下载）—— **唯一**允许认领下载的状态
#: - `submitting` 已认领、正在提交下载器（0.9.2 A1 加的原子占位态；同一任务只有一次提交能赢）。
#:                它是一瞬间的中间态：成功 → `pushed`、其余出口 → 放回 `await`。
#:                进程死在中间时会卡住，`init_plugin` 里 `task_recover_submitting()` 把它们放回去。
#: - `pushed`     已提交下载器（种子在里面跑）
#: - `canceled`   用户取消（只在 `await` 时允许 → `task_set_state(only_from=("await",))`）
#: - `failed`     下载失败 / 所有源都没找到（`pending` 里带标记）
TASK_STATES: Tuple[str, ...] = ("await", "submitting", "pushed", "canceled", "failed")

#: 「正在提交下载」的中间态（A1 的认领值）。见 `TASK_STATES`。
TASK_SUBMITTING = "submitting"


# 通知元信息里「发布源」永远是最后一段：「发布源：<站点> / <发布组> 发布」
_PUBLISHER_TAIL_RE = re.compile(r"发布源：\s*(?P<site>[^/·]+?)\s*/\s*(?P<group>[^·]+?)\s*$")


def _fix_publisher_meta(meta: str) -> str:
    """读通知时顺手纠正「发布源」的重复文案（旧版把站点兜底成了发布组）。

    「… ·  发布源：馒头 / 馒头 发布 发布」→「… ·  发布源：馒头」；其余元信息原样保留，
    认不出来就原样返回（幂等，所以不必改库）。
    """
    text = str(meta or "")
    hit = _PUBLISHER_TAIL_RE.search(text)
    if not hit:
        return text
    site = hit.group("site").strip()
    group = re.sub(r"(\s*发布)+$", "", hit.group("group").strip()).strip()
    if not site or group.replace(" ", "") in ("", site):
        label = site or group
    elif group.endswith("发布"):
        label = f"{site} / {group}"
    else:
        label = f"{site} / {group} 发布"
    return text[:hit.start()] + "发布源：" + label


def _to_int(value: Any) -> int:
    """字节数收敛成非负整数：台账的 size 列是字节（INTEGER），0 表示未知。

    调用方给的东西不保证是这个形状（老队列里存的是「1.2 GB」这种展示文本，由 tasks.py
    换成字节再进来；外部补种可能给字符串数字）。这里只保证落库类型干净——认不出来一律 0，
    绝不让 SQLite 把文本塞进整数列：列里出现文本，界面的「大小」就会算出乱数。
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    text = str(value or "").strip()
    try:
        return max(int(float(text)), 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _to_float(value: Any) -> float:
    """评分一类的数值列收敛成 float（认不出来 0.0）；理由同 `_to_int`。"""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value or "").strip())
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _json_text(value: Any, default: str = "{}") -> str:
    """写 JSON 列：dict/list 直接序列化，字符串原样（调用方可能已经序列化过），空值给默认。

    允许直接传对象是刻意的：调用方（scraper/namemap）手里本来就是 list/dict，
    让它们在每个调用点自己 `json.dumps` 一遍，序列化参数（`ensure_ascii`）迟早会漂。
    """
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text or default
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return default


def _json_load(text: Any, default: Any) -> Any:
    """读 JSON 列：解析失败或类型与默认值不同类时给默认值（不抛异常）。"""
    if isinstance(text, (list, dict)):
        return text
    raw = str(text or "").strip()
    if not raw:
        return default
    try:
        out = json.loads(raw)
    except ValueError:
        return default
    return out if isinstance(out, type(default)) else default


def _meta_value(column: str, value: Any) -> Any:
    """把调用方给的值收成该列的落库类型（JSON 列序列化、整数列转 int、评分转 float）。"""
    if column in _META_JSON_FIELDS:
        return _json_text(value, _META_JSON_FIELDS[column])
    if column in _META_INT_FIELDS:
        return _to_int(value)
    if column in _META_FLOAT_FIELDS:
        return _to_float(value)
    return "" if value is None else str(value)


def _item_value(column: str, value: Any) -> Any:
    """同 `_meta_value`，媒体实例表的列类型收敛。"""
    if column in _ITEM_JSON_FIELDS:
        return _json_text(value, _ITEM_JSON_FIELDS[column])
    return "" if value is None else str(value)


def _meta_row(row: Any) -> Dict[str, Any]:
    """一行 meta → dict。

    列名原样给（`actors_json` 等仍是串），**另给一份解析过的副本**（去掉 `_json` 后缀：
    `actors` / `tags` / `samples` / `raw`）：调用方（`scraper.film_view()`）要对象、
    诊断导出要原始串，两份都给，省得两边各自再解析一遍、口径漂掉。
    """
    out: Dict[str, Any] = {}
    for idx, name in enumerate(_META_COLUMNS):
        value = row[idx]
        out[name] = _META_DEFAULTS.get(name, "") if value is None else value
    out["retry_count"] = _to_int(out.get("retry_count"))
    out["runtime_min"] = _to_int(out.get("runtime_min"))
    out["rating"] = _to_float(out.get("rating"))
    out["actors"] = _json_load(out.get("actors_json"), [])
    out["tags"] = _json_load(out.get("tags_json"), [])
    out["samples"] = _json_load(out.get("samples_json"), [])
    out["raw"] = _json_load(out.get("raw_json"), {})
    # P0-1 溯源：另给解析副本 `field_sources`（`{"plot_zh": "javtxt", …}`）
    out["field_sources"] = _json_load(out.get("field_sources_json"), {})
    return out


def _item_row(row: Any) -> Dict[str, Any]:
    """一行 media_item → dict（`version_tags_json` 另给解析副本 `version_tags`）。

    **不回 `emby_backup_json`**（那是几十 KB 的完整 DTO，列表接口带上它纯属浪费）：
    它只经 `item_backup_get()` 取，另给一个 `has_backup` 布尔位让调用方判断闸门状态。
    """
    out: Dict[str, Any] = {}
    for idx, name in enumerate(_ITEM_COLUMNS):
        value = row[idx]
        out[name] = _ITEM_DEFAULTS.get(name, "") if value is None else value
    out["version_tags"] = _json_load(out.get("version_tags_json"), {})
    out["has_backup"] = bool(str(out.get("emby_backup_json") or ""))
    out.pop("emby_backup_json", None)
    return out


def _name_map_row(row: Any) -> Dict[str, Any]:
    """一行 name_map → dict（`keywords_norm` 另给解析副本 `keywords` = 别名 token 列表）。"""
    out: Dict[str, Any] = {}
    for idx, name in enumerate(_NAME_MAP_COLUMNS):
        value = row[idx]
        out[name] = _NAME_MAP_DEFAULTS.get(name, "") if value is None else value
    out["is_delete_rule"] = _to_int(out.get("is_delete_rule"))
    out["keywords"] = split_keywords(out.get("keywords_norm"))
    return out


def _actor_value(column: str, value: Any) -> Any:
    """把调用方给的值收成 `actor` 该列的落库类型（JSON 列序列化、gender 转 int/NULL、文本去空白）。"""
    if column in _ACTOR_JSON_FIELDS:
        return _json_text(value, _ACTOR_JSON_FIELDS[column])
    if column == "gender":
        text = "" if value is None else str(value).strip()
        return None if not text else _to_int(text)
    return "" if value is None else str(value).strip()


def _actor_blank(column: str, value: Any) -> bool:
    """这一格算不算「空」（`actor_upsert` / `actor_set_profile` 靠它决定跳过）。

    「空」的判据按列类型走：JSON 列是 `''`/`[]`/`{}`，`gender` 是 NULL，文本列是空串。
    混着用的后果很具体：一次 `gender=None` 的登记若当成 0 落库，"未知性别"就变成了"女"，
    而写侧正是按这个值过滤女演员的。
    """
    if column == "gender":
        return value is None
    if column in _ACTOR_JSON_FIELDS:
        return str(value or "") in ("", "[]", "{}")
    return not str(value or "").strip()


def _actor_row(row: Any) -> Dict[str, Any]:
    """一行 actor → dict（JSON 列另给解析副本：`aliases` / `images` / `field_sources` / `locked_fields`）。

    与 `_meta_row()` 同一套给法：原始串照给（排障要原样）、解析副本另给（调用方不必各自
    再解析一遍，口径不会漂）。`gender` 的 NULL 原样留成 `None`：0=女 / 1=男 / None=未知，
    把未知折成 0 等于凭空认定"是女的"。`images[0]` 就是主图（顺序有意义，这里不重排）。
    """
    out: Dict[str, Any] = {}
    for idx, name in enumerate(_ACTOR_COLUMNS):
        value = row[idx]
        if name == "gender":
            out[name] = None if value is None else _to_int(value)
        else:
            out[name] = _ACTOR_DEFAULTS.get(name, "") if value is None else value
    out["id"] = _to_int(out.get("id"))
    out["retry_count"] = _to_int(out.get("retry_count"))
    out["aliases"] = _json_load(out.get("aliases_json"), [])
    out["images"] = _json_load(out.get("images_json"), [])
    out["field_sources"] = _json_load(out.get("field_sources_json"), {})
    out["locked_fields"] = _json_load(out.get("locked_fields_json"), [])
    return out


def split_keywords(text: Any) -> List[str]:
    """`,a,b,` 形状的归一化别名串 → `['a', 'b']`（写入与匹配两边共用同一份解析）。"""
    return [t for t in str(text or "").split(",") if t]


def join_keywords(tokens: Any) -> str:
    """别名 token 列表 → `,a,b,`（逗号包裹，去重保序、丢掉空 token）。"""
    out: List[str] = []
    for token in tokens or []:
        text = str(token or "").strip().strip(",")
        if text and text not in out:
            out.append(text)
    return "," + ",".join(out) + "," if out else ","


def merge_keywords(existing: Any, *groups: Any) -> str:
    """把已有的 `keywords_norm` 与若干组新 token 合并成一个 `,a,b,`（去重保序）。"""
    tokens = split_keywords(existing)
    for group in groups:
        if group is None:
            continue
        items = [group] if isinstance(group, str) else list(group)
        for item in items:
            text = str(item or "").strip().strip(",")
            if text and text not in tokens:
                tokens.append(text)
    return join_keywords(tokens)


def _like_escape(text: Any) -> str:
    """LIKE 通配符转义（配合 `ESCAPE '\\'`）：演员名里真出现 `%`/`_` 时不至于变成通配。"""
    return (str(text or "")
            .replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"))


def _probe_forms(name: Any) -> List[str]:
    """一个名字的匹配探针：原文、`namemap.normalize()` 归一化结果、小写形式（去重保序）。

    `keywords_norm` 里存的是**整词**（逗号分隔的 token），所以查询词也要按 token 切：
    查 `a,b` 就是分别整词查 `a` 与 `b`，绝不把 `a,b` 当子串去撞 —— 上游实测过归一化后
    `男優` 一个键能命中 220 条、`バカボン` 与 `バカボン×` 撞车，子串匹配只会把误命中放大。
    """
    text = str(name or "").strip()
    parts = [p.strip() for p in text.split(",")] if text else []
    out: List[str] = []
    for part in [p for p in parts if p]:
        for candidate in (part, _norm_lookup(part), part.lower()):
            if candidate and candidate not in out:
                out.append(candidate)
    return out


def _norm_lookup(text: Any) -> str:
    """归一化一个名字，用于 `name_map.keywords_norm` 的**写入与匹配**。

    口径的唯一来源是 `namemap.normalize()`（S3 提供）：除了小写化/去空白，它可能还做全角、
    片假名一类的归一，store 自己再写一份迟早会漂。该模块还没落地（并行施工期）或导入失败时，
    退回本地最小规则（折叠空白 + 小写），保证 store 单测与最早期的调用都不炸。
    """
    raw = str(text or "").strip()
    if not raw:
        return ""
    module = sys.modules.get(f"{__package__}.namemap")
    if module is None:
        try:
            from . import namemap as module  # noqa: F401  延迟导入：避免与 S3 的模块互相拖死
        except Exception:
            module = None
    fn = getattr(module, "normalize", None)
    if callable(fn):
        try:
            out = fn(raw)
            if isinstance(out, str) and out.strip():
                return out.strip()
        except Exception:
            pass
    return re.sub(r"\s+", " ", raw).lower()


class Store:
    """插件自有数据的唯一入口（线程安全；每线程一条长连接 + 写锁）。"""

    def __init__(self, db_path: Optional[Path] = None):
        # 默认路径在调用时向 `paths` 取：`paths.configure()` 之后数据根才定型，
        # 写成默认参数会在模块导入那一刻被固化成老路径。
        self.db_path = Path(db_path) if db_path else paths.db_path()
        # RLock 而不是 Lock：读改写型方法（kv_update / _download_merge / meta_upsert…）自己持锁，
        # 而它们调用的 `_connect()` 在「库文件刚被建成空库」时还要再进一次锁建表（同一线程重入）。
        # 跨线程的互斥语义与 Lock 完全一致，写操作仍旧串行。
        self._lock = threading.RLock()
        # 线程本地连接：`sqlite3` 连接不能跨线程用（check_same_thread 保持默认 True），
        # 所以「复用连接」只能是**每线程一条**。
        self._local = threading.local()

    # ---------- 基础：连接 / 建表 / 迁移 ----------

    def _db_ident(self) -> Any:
        """库文件的身份 `(st_dev, st_ino)`；文件不在时 None。"""
        try:
            stat = os.stat(self.db_path)
        except OSError:
            return None
        return (stat.st_dev, stat.st_ino)

    def _close_local(self) -> None:
        """关掉本线程这条连接（幂等）。"""
        conn = getattr(self._local, "conn", None)
        self._local.conn = None
        self._local.ident = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def close(self) -> None:
        """关掉**本线程**的连接（测试与优雅收尾用；不影响别的线程）。"""
        self._close_local()

    def _connect(self) -> sqlite3.Connection:
        """取本线程的长连接；文件被换掉/连接坏掉时**按需重开**，不做僵尸。

        为什么要认文件身份：`docker cp` 部署会把 db 文件整个换掉（新 inode），而旧连接
        仍然指着已被删除的那个 inode —— 继续用它就是「写进空气里」：接口全 200、数据全丢。
        所以复用前先比 `(st_dev, st_ino)`，对不上就关掉重开；再叠一次 `SELECT 1` 健康检查兜底
        （文件大小/内容被原地改写这类识别不出的情况，SQLite 自己还有文件变更计数校验）。
        新建的库文件（或 0 字节文件）顺手建表：否则「换了库文件」之后每个调用都撞 no such table。
        """
        db_text = str(self.db_path)
        try:
            stat = os.stat(db_text)
            ident: Any = (stat.st_dev, stat.st_ino)
            fresh = stat.st_size == 0
        except OSError:
            ident = None        # 文件还不存在：马上会新建，算「新库」
            fresh = True

        conn = getattr(self._local, "conn", None)
        if conn is not None:
            if ident is not None and ident == getattr(self._local, "ident", None):
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    pass        # 连接坏了（磁盘/文件被换）：下面重开
            self._close_local()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_text)
        # PRAGMA 是 per-connection 的：只在建库时设一次不够，每条新连接都要重设。
        # `journal_mode` 是**库级且持久化**的（写进库头），所以只在 init() 里设一次。
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._local.conn = conn
        self._local.ident = self._db_ident()
        if fresh:
            with self._lock:
                self._bootstrap(conn)
                conn.commit()
        return conn

    def init(self) -> None:
        """建库建表 + WAL 配置 + 老库迁移；**幂等**，可以反复跑（每次插件加载都会跑）。

        WAL 与 `busy_timeout` 是这一版的重点：MP 的接口走线程池、定时任务各占线程，
        没有 WAL 时「读」会把「写」顶成 database is locked。
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._connect()
            # journal_mode 持久化在库头：这里设一次，之后每条新连接读到的都还是 wal。
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            conn.execute("PRAGMA foreign_keys=ON")
            self._bootstrap(conn)
            # v4.1 §4.2 末条：用户手工备注（actor_alias）同步进 name_map，且拥有最高优先级
            self._sync_aliases(conn)
            conn.commit()

    def _bootstrap(self, conn: sqlite3.Connection) -> None:
        """建表 + 按 `_MIGRATIONS` 顺序补迁移（幂等）。`init()` 与「库文件被换成空库」两条路都走这里。

        0.8.0 / P1-8 的三条纪律（照 amane `sqlite_migrate.py`，不引入 Alembic）：
        ① **迁移前在线备份**（`conn.backup()`，直接 `cp` 会丢 WAL 里没 checkpoint 的数据）；
        ② `schema_meta` 记版本 + **有序** `_MIGRATIONS` 列表（不是散落的 try/except ALTER）；
        ③ 迁移失败不吞：备份失败只记日志（保险不是前置条件），迁移本身失败照旧抛出。
        """
        current = self._schema_version(conn)
        backup = ""
        if not self._is_fresh_db(conn) and current < _SCHEMA_VERSION:
            backup = self._backup_before_migrate(conn, current)
        conn.executescript(_SCHEMA)
        conn.executescript(_SCHEMA_SCHEMA_META)
        conn.executescript(_SCHEMA_SCRAPE_V4)
        # 演员表在迁移 v2 里也建一次（幂等，且版本账本靠它推进）；这里先建是为了让
        # "版本已是 2、表却被手工 DROP" 的老库自愈 —— 与 `_repair_columns` 的两处调用同一思路。
        conn.executescript(_SCHEMA_ACTOR)
        for version, name, apply in _MIGRATIONS:
            if version <= current:
                continue
            apply(conn)
            self._schema_record(conn, version, name, backup=backup)
        # 结构自愈（P1-8）：版本表说"已迁过"，但某个列真的缺了（人工 DROP / 半截迁移）时只补列、
        # **不改版本**。补列是幂等的（4 次 PRAGMA + 命中即跳过），代价可以忽略；
        # 不这么做的话，一次中断的 init() 之后就得手工修库。
        _repair_columns(conn)
        # ★ 索引**必须**在补列之后建（2026-10-15 部署实测的真缺陷）：
        #   建表脚本里写着 `CREATE INDEX ... ON scrape_log(run_id)`，而老库的 scrape_log
        #   是**已存在的表**（`IF NOT EXISTS` 不会重建它），补列又排在后面 →
        #   索引引用一个还不存在的列，init() 直接 `no such column: run_id`、插件起不来。
        #   本机测试没抓到是因为造老库时只造了"缺列的 downloads"，没造"缺列的 scrape_log"。
        _ensure_indexes(conn)
        conn.commit()

    def schema_info(self) -> Dict[str, Any]:
        """schema 版本与最近一次迁移记录（排障用）。

        `version` 是 `schema_meta.schema_version`；老库（没有这张表）读出来是 0。
        `backup` 是迁移前那份 `.bak` 的路径（没迁过 / 备份失败则为空串）。
        """
        conn = self._connect()
        try:
            rows = dict(conn.execute("SELECT key, val FROM schema_meta").fetchall())
        except sqlite3.OperationalError:
            rows = {}
        return {
            "version": _to_int(rows.get("schema_version")),
            "target": _SCHEMA_VERSION,
            "migrated_at": str(rows.get("schema_migrated_at") or ""),
            "note": str(rows.get("schema_note") or ""),
            "backup": str(rows.get("schema_backup") or ""),
        }

    def schema_version(self) -> int:
        """当前库的 schema 版本（0 = 0.7.x 及更早的老库）。"""
        return _to_int(self.schema_info().get("version"))

    # ---------- schema 版本与迁移备份（P1-8） ----------

    def _schema_version(self, conn: sqlite3.Connection) -> int:
        """这个库走在哪一版：没有 `schema_meta` 表（≤0.7.x）就是 0。"""
        try:
            rows = conn.execute(
                "SELECT val FROM schema_meta WHERE key='schema_version'").fetchall()
        except sqlite3.OperationalError:
            return 0
        return _to_int(rows[0][0]) if rows else 0

    @staticmethod
    def _is_fresh_db(conn: sqlite3.Connection) -> bool:
        """全新空库（一个业务表都没有）→ 没什么可备份的，别为它写一个 .bak 出来。"""
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('meta','media_item','task','downloads','actor_alias','kv')").fetchall()
        return not rows

    def _schema_record(self, conn: sqlite3.Connection, version: int, name: str = "",
                       backup: str = "") -> None:
        """把版本与说明写进 `schema_meta`（`schema_version` 一行就是唯一真值）。"""
        conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) VALUES('schema_version', ?)",
                     (str(int(version)),))
        conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) VALUES('schema_migrated_at', ?)",
                     (_now(),))
        if name:
            conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) VALUES('schema_note', ?)",
                         (str(name),))
        if backup:
            conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) VALUES('schema_backup', ?)",
                         (str(backup),))
        conn.commit()

    def _prune_backups(self, keep: int = 3) -> int:
        """只留最近 `keep` 份迁移备份，返回删掉的份数。

        备份被 `__init__.is_keep_file()` 保护（缓存清理不许碰它），所以数量得自己管 ——
        否则每升一版都多留一个**完整库**大小的文件，永远不回收。
        """
        try:
            files = sorted(self.db_path.parent.glob(f"{self.db_path.name}.pre-migrate-*.bak"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:                                          # pragma: no cover - 防御
            return 0
        dropped = 0
        for stale in files[max(1, int(keep)):]:
            try:
                stale.unlink()
                dropped += 1
            except OSError:
                continue
        return dropped

    def _backup_before_migrate(self, conn: sqlite3.Connection, version: int) -> str:
        """迁移前用 SQLite **online backup API** 备份到 `<库名>.pre-migrate-v<旧版本>-<时间>.bak`。

        - 直接 `cp` 会丢掉 WAL 里还没 checkpoint 的数据（amane 同一条教训），所以用 `backup()`；
        - 备份失败**不阻断**迁移（它是保险不是前置条件），但要如实记 error 日志；
        - 备份文件名会被写进 `schema_meta.schema_backup`，且 `__init__.is_keep_file()` 认这个
          后缀 —— **否则每晚 4 点 `job_cacheclean` 的孤儿扫描会把它当缓存删掉**（P1-8 必改两处）。
        """
        try:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            target = Path(f"{self.db_path}.pre-migrate-v{int(version)}-{stamp}.bak")
            dest = sqlite3.connect(str(target))
            try:
                conn.backup(dest)
            finally:
                dest.close()
            logger.info(f"AVHelper 迁移前已备份数据库：{target.name}")
            self._prune_backups()
            return str(target)
        except Exception as error:                              # noqa: BLE001 - 备份失败不阻断
            logger.error(f"AVHelper 迁移前备份失败（继续迁移）：{error}")
            return ""

    def _sync_aliases(self, conn: sqlite3.Connection, only: str = "") -> int:
        """把用户备注（`actor_alias`）同步进 `name_map(source='user_custom')`，返回同步条数。

        幂等的关键在 **canonical_id 用演员原名**（`actor:{原名}`）而不是备注：用户改备注时是
        同一行原地更新，重复跑 `init()` 也不会多出行；拿备注当 id 的话，用户每改一次称呼就多
        一条新记录、旧的还留着（而且到底哪条算数要靠排序赌）。

        只覆盖 `zh_cn` / `jp` / `keywords_norm` / `source`：老行（内置映射导入的）上的
        `avatar_url` / `javdb_actor_id` / `zh_tw` 不该被这条备注抹掉。别名串取并集，
        用户改过称呼之后旧写法仍然能查到（查到的那行里 `zh_cn` 已经换成新备注了）。

        调用方必须**持 `self._lock`**（插入与去重读要在一起）。
        """
        if only:
            rows = conn.execute(
                "SELECT name, alias FROM actor_alias WHERE name=? AND IFNULL(alias, '') <> ''",
                (str(only),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, alias FROM actor_alias WHERE IFNULL(alias, '') <> ''"
            ).fetchall()
        count = 0
        for name, alias in rows:
            raw_name = str(name or "").strip()
            text = str(alias or "").strip()
            if not raw_name or not text:
                continue
            self._write_user_mapping(
                conn, canonical_id=f"actor:{raw_name}", entity_type="actor",
                zh=text, jp=raw_name,
                tokens=[_norm_lookup(raw_name), _norm_lookup(text)],
            )
            count += 1
        return count

    # ---------- 基础：内部读写原语 ----------

    def _exec(self, sql: str, args: tuple = (), fetch: bool = False) -> Any:
        """执行一条语句；`fetch=True` 时返回全部行。

        读（SELECT/PRAGMA/EXPLAIN/VALUES）直接走**本线程的长连接、不持锁**：WAL 下读与写互不
        阻塞，`film_view()` 那种高频读不再排在写锁后面（升级前每次调用都要开一次文件 + 抢锁）。
        写统一 `with self._lock:`，与升级前同样的互斥语义；出错回滚，绝不把半截事务留给下一条语句。
        """
        conn = self._connect()
        started = time.perf_counter()
        if _is_read_sql(sql):
            rows = _run(conn, sql, args, fetch)
            _log_slow(sql, (time.perf_counter() - started) * 1000)
            return rows
        with self._lock:
            try:
                rows = _run(conn, sql, args, fetch)
                conn.commit()
                _log_slow(sql, (time.perf_counter() - started) * 1000)
                return rows
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    def _exec_count(self, sql: str, args: tuple = ()) -> int:
        """执行一条**写**语句并返回受影响行数（条件写要靠它判断"赢没赢"）。

        与 `_exec` 的写路径同一把锁、同一套回滚语义；只是把 `rowcount` 带出来 ——
        `_exec` 对所有写都返回 `None`（那是个被几十处调用的原语，不为一处需求改它的返回值）。
        """
        conn = self._connect()
        started = time.perf_counter()
        with self._lock:
            try:
                count = _run_count(conn, sql, args)
                conn.commit()
                _log_slow(sql, (time.perf_counter() - started) * 1000)
                return count
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    # ---------- 收藏演员 ----------

    def fav_list(self) -> List[Dict[str, Any]]:
        """返回全部收藏演员。"""
        rows = self._exec(
            "SELECT name, zh, avatar FROM actor_fav ORDER BY added_at", fetch=True
        ) or []
        return [{"name": r[0], "zh": r[1] or "", "avatar": r[2] or ""} for r in rows]

    def fav_add(self, name: str, zh: str = "", avatar: str = "") -> None:
        """新增或更新一位收藏演员。"""
        self._exec(
            "INSERT INTO actor_fav(name, zh, avatar, added_at) VALUES(?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET zh=excluded.zh, avatar=excluded.avatar",
            (name, zh, avatar, _now()),
        )

    def fav_del(self, name: str) -> None:
        """取消收藏。"""
        self._exec("DELETE FROM actor_fav WHERE name=?", (name,))

    # ---------- 演员备注 ----------
    # 与 `actor_fav` **刻意分成两张表**（不 JOIN、不设外键）：备注是"我给这个演员起的称呼"，
    # 与"有没有收藏"是两件事 —— 没收藏的演员（详情页/搜索里点进来的）也必须能写备注；
    # 取消收藏不该顺手把备注删掉，反过来也一样。

    def alias_map(self) -> Dict[str, str]:
        """返回全部非空备注：`{演员原名: 备注}`，前端拿它直接查表。

        空的（清除备注留下的行）**不返回**：调用方一律按"查不到就是没备注"处理，
        省得每个显示点都得再判一次空串。
        """
        rows = self._exec(
            "SELECT name, alias FROM actor_alias WHERE IFNULL(alias, '') <> ''", fetch=True
        ) or []
        return {str(r[0]): str(r[1]) for r in rows if str(r[0])}

    def alias_set(self, name: str, alias: str) -> None:
        """写入或更新一位演员的备注；`alias` 为空串 = 清除（删行）。

        写完备注顺手把这条同步进 `name_map`（`source='user_custom'`）：用户的称呼是
        **最高优先级**的译名，不该等到下次插件加载跑 `init()` 才生效。
        清除备注**不回滚** `name_map` 里那一条（那行可能还并着内置映射的信息），
        只把它从同步范围里去掉 —— 已知取舍，见 `_sync_aliases()`。
        """
        # 键也过一遍 strip：写进来的名字带空白，就会与 `alias_map()` 的键（读回时按演员原名查）
        # 对不上 —— 界面上看着"存了没生效"，其实是同一人被存成了两行。没名字直接不写。
        key = str(name or "").strip()
        if not key:
            return
        # 存的与判空用的是同一个值：只判不裁的话，「  」（纯空格）会落库成一条
        # 看着有备注、`alias_map()` 却查不到的行。
        text = str(alias or "").strip()
        if not text:
            self._exec("DELETE FROM actor_alias WHERE name=?", (key,))
            return
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO actor_alias(name, alias, updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(name) DO UPDATE SET alias=excluded.alias, "
                    "updated_at=excluded.updated_at",
                    (key, text, _now()),
                )
                self._sync_aliases(conn, only=key)
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    # ---------- 订阅 ----------

    def sub_list(self) -> List[Dict[str, Any]]:
        """返回全部订阅（含规则）。"""
        rows = self._exec(
            "SELECT id, type, name, rule, hits, last_check, created_at FROM sub ORDER BY id",
            fetch=True,
        ) or []
        out = []
        for r in rows:
            try:
                rule = json.loads(r[3] or "{}")
            except ValueError:
                rule = {}
            out.append({
                "id": r[0], "type": r[1], "name": r[2], "rule": rule,
                "hits": int(r[4] or 0), "last": r[5] or "", "created": r[6] or "",
            })
        return out

    def sub_add(self, sub_type: str, name: str, rule: Dict[str, Any]) -> int:
        """新增订阅（同类型同名视为同一订阅，更新规则）。"""
        self._exec(
            "INSERT INTO sub(type, name, rule, hits, last_check, created_at) VALUES(?,?,?,0,?,?) "
            "ON CONFLICT(type, name) DO UPDATE SET rule=excluded.rule",
            (sub_type, name, json.dumps(rule, ensure_ascii=False), "", _now()),
        )
        rows = self._exec("SELECT id FROM sub WHERE type=? AND name=?", (sub_type, name), fetch=True)
        return int(rows[0][0]) if rows else 0

    def sub_del(self, sid: int) -> None:
        """删除订阅。"""
        self._exec("DELETE FROM sub WHERE id=?", (sid,))

    def sub_touch(self, sid: int, hits: int) -> None:
        """记录一次检查：更新时间与累计命中数。"""
        self._exec("UPDATE sub SET hits=?, last_check=? WHERE id=?", (hits, _now(), sid))

    # ---------- 已知番号 ----------

    def known_all(self) -> List[str]:
        """返回全部已知番号。"""
        return [r[0] for r in (self._exec("SELECT number FROM known", fetch=True) or [])]

    def known_add(self, number: str, actor: str = "") -> None:
        """记录一个已知番号（订阅快照或已下载）。"""
        self._exec(
            "INSERT INTO known(number, actor, added_at) VALUES(?,?,?) "
            "ON CONFLICT(number) DO NOTHING",
            (number, actor, _now()),
        )

    # ---------- 搜索任务 ----------

    def task_list(self, limit: int = 50) -> List[Dict[str, Any]]:
        """返回最近的任务（含候选与打分）。"""
        rows = self._exec(
            "SELECT id, number, actor, cands, reason, state, thumb, auto, created_at, rule, source, pending "
            "FROM task ORDER BY created_at DESC LIMIT ?", (limit,), fetch=True,
        ) or []
        out = []
        for r in rows:
            try:
                cands = json.loads(r[3] or "[]")
            except ValueError:
                cands = []
            try:
                rule = json.loads(r[9] or "{}")
            except ValueError:
                rule = {}
            out.append({
                "id": r[0], "number": r[1], "actor": r[2] or "", "cands": cands,
                "reason": r[4] or "", "state": r[5] or "await", "thumb": r[6] or "",
                "auto": bool(r[7]), "created": r[8] or "", "rule": rule,
                "source": r[10] or "manual", "pending": r[11] or "",
            })
        return out

    def task_get(self, tid: str) -> Optional[Dict[str, Any]]:
        """按 id 取单个任务。"""
        for t in self.task_list(limit=200):
            if t["id"] == tid:
                return t
        return None

    def task_add(self, task: Dict[str, Any]) -> None:
        """写入一条搜索任务（含生成它的订阅规则与任务来源，供后续下载沿用）。"""
        self._exec(
            "INSERT OR REPLACE INTO task(id, number, actor, cands, reason, state, thumb, auto, created_at, rule, source, pending) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (task["id"], task["number"], task.get("actor", ""),
             json.dumps(task.get("cands", []), ensure_ascii=False),
             task.get("reason", ""), task.get("state", "await"),
             task.get("thumb", ""), 1 if task.get("auto") else 0, _now(),
             json.dumps(task.get("rule") or {}, ensure_ascii=False),
             str(task.get("source") or "manual"),
             str(task.get("pending") or "")),
        )

    def task_set_state(self, tid: str, state: str, *, only_from: Any = None) -> bool:
        """更新任务状态；`only_from` 给了就**条件写**（P1-7 / 0.8.0），返回是否真的改到了。

        - 无条件（`only_from=None`）：记录"已经发生的事"（例：种子推进下载器 → `pushed`）。
        - 条件（`only_from=("await",)`）：**做判断**（例：取消待确认任务）。
          老写法是"读 state → 比对 → 写"，两次操作之间别人把任务推成 `pushed` 时，
          `canceled` 会把事实盖掉（用户看到"已取消"，下载器里却在跑）。
          条件写把判断交给一条 SQL：`UPDATE … WHERE state IN (…)`，靠受影响行数判断赢没赢。

        `TASK_STATES` 是这套取值的清单（**只加不改**）。
        """
        allowed = [str(item) for item in only_from] if only_from else []
        if allowed:
            marks = ",".join("?" * len(allowed))
            count = self._exec_count(
                f"UPDATE task SET state=?, updated_at=? WHERE id=? AND state IN ({marks})",
                (str(state or ""), _now(), str(tid or ""), *allowed))
        else:
            count = self._exec_count("UPDATE task SET state=?, updated_at=? WHERE id=?",
                                     (str(state or ""), _now(), str(tid or "")))
        return bool(count)

    def task_recover_submitting(self, before: str) -> List[Dict[str, Any]]:
        """把卡在 `submitting` 且 `updated_at` 早于 `before` 的任务放回 `await`，返回恢复的行。

        用途（0.9.2 A1 的收尾）：进程可能死在「认领成功、还没写终态」之间 —— 种子可能已经推进
        下载器了，也可能没有。这类任务既不显示在待确认里，也永远不会再被认领，只能靠启动时
        兜一把。`before` 传时间戳串（与库里同一个 `%Y-%m-%d %H:%M:%S` 口径），调用方负责留出
        「正常提交肯定做完」的余量。

        返回 `[{id, number}]`，调用方据此发通知（让用户去下载器核对到底有没有下单）。
        """
        stamp = str(before or "").strip()
        if not stamp:
            return []
        rows = self._exec(
            "SELECT id, number FROM task WHERE state=? AND updated_at < ?",
            (TASK_SUBMITTING, stamp), fetch=True,
        ) or []
        recovered: List[Dict[str, Any]] = []
        for row in rows:
            tid = str(row[0] or "")
            if tid and self.task_set_state(tid, "await", only_from=(TASK_SUBMITTING,)):
                recovered.append({"id": tid, "number": str(row[1] or "")})
        return recovered

    # ---------- 通知 ----------

    def notice_add(self, notice: Dict[str, Any]) -> None:
        """写入一条通知记录并只保留最近 200 条。"""
        self._exec(
            "INSERT INTO notice(kind, title, type, body, meta, image, created_at) VALUES(?,?,?,?,?,?,?)",
            (notice.get("kind", ""), notice.get("title", ""), notice.get("type", ""),
             notice.get("body", ""), notice.get("meta", ""), notice.get("image", ""), _now()),
        )
        self._exec(
            "DELETE FROM notice WHERE id NOT IN (SELECT id FROM notice ORDER BY id DESC LIMIT 200)"
        )

    def notice_list(self) -> List[Dict[str, Any]]:
        """返回通知（新到旧）；老记录的「发布源」重复文案在这里顺手纠正。"""
        rows = self._exec(
            "SELECT kind, title, type, body, meta, image, created_at FROM notice ORDER BY id DESC",
            fetch=True,
        ) or []
        return [{"kind": r[0], "title": r[1], "type": r[2], "body": r[3],
                 "meta": _fix_publisher_meta(r[4]), "image": r[5], "time": r[6]} for r in rows]

    def notice_clear(self) -> None:
        """清空通知。"""
        self._exec("DELETE FROM notice")

    # ---------- 通用键值（限流计数） ----------

    def kv_set(self, key: str, val: Any, ttl: int = 0) -> None:
        """写键值，ttl 秒后过期（0 表示不过期）。"""
        exp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + ttl)) if ttl else ""
        self._exec(
            "INSERT INTO kv(key, val, expires_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET val=excluded.val, expires_at=excluded.expires_at",
            (key, json.dumps(val, ensure_ascii=False), exp),
        )

    def kv_update(self, key: str, fn: Callable[[Any], Any]) -> Any:
        """原子读改写：`fn(旧值) -> 新值`，读与写在同一次持锁里完成。

        下载队列这种「多处都在改的同一份数据」必须走这里：先 `kv_get` 拿快照、算完再 `kv_set`
        整份写回，并发时后写的会把别人刚插入的条目冲掉（实测丢过一条已成功下载的记录）。
        只给无 TTL 的键用，过期时间一律写空。
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT val, expires_at FROM kv WHERE key=?", (key,)).fetchone()
                current = None
                if row:
                    raw, exp = row
                    if exp and exp < _now():
                        conn.execute("DELETE FROM kv WHERE key=?", (key,))
                    else:
                        try:
                            current = json.loads(raw)
                        except ValueError:
                            current = None
                new = fn(current)
                conn.execute(
                    "INSERT INTO kv(key, val, expires_at) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET val=excluded.val, expires_at=excluded.expires_at",
                    (key, json.dumps(new, ensure_ascii=False), ""),
                )
                conn.commit()
                return new
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    def kv_get(self, key: str, default: Any = None) -> Any:
        """读键值，过期即删并返回默认值。"""
        rows = self._exec("SELECT val, expires_at FROM kv WHERE key=?", (key,), fetch=True)
        if not rows:
            return default
        val, exp = rows[0]
        if exp and exp < _now():
            self._exec("DELETE FROM kv WHERE key=?", (key,))
            return default
        try:
            return json.loads(val)
        except ValueError:
            return default

    def kv_del(self, key: str) -> None:
        """删除键值。"""
        self._exec("DELETE FROM kv WHERE key=?", (key,))

    # ---------- 文件缓存索引 ----------

    def cache_put(self, key: str, path: str, ttl: int) -> None:
        """登记一个缓存文件（用于 TTL 清理）。"""
        exp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + ttl))
        self._exec(
            "INSERT INTO cache_idx(key, path, expires_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET path=excluded.path, expires_at=excluded.expires_at",
            (key, path, exp),
        )

    def cache_expired(self) -> List[Dict[str, str]]:
        """返回已过期的缓存文件记录。"""
        rows = self._exec(
            "SELECT key, path FROM cache_idx WHERE expires_at < ?", (_now(),), fetch=True
        ) or []
        return [{"key": r[0], "path": r[1]} for r in rows]

    def cache_all(self) -> List[Dict[str, str]]:
        """返回全部缓存文件记录（用于孤儿与容量治理）。"""
        rows = self._exec("SELECT key, path FROM cache_idx", fetch=True) or []
        return [{"key": r[0], "path": r[1]} for r in rows]

    def cache_drop(self, keys: List[str]) -> None:
        """从索引里移除若干 key。"""
        for k in keys:
            self._exec("DELETE FROM cache_idx WHERE key=?", (k,))

    # ---------- 下载台账 ----------
    #
    # 「下载过什么」在这里留下永久记录：文件被删、种子被清理都不影响它，界面据此打
    # 「已下载」徽标、避免重复下载。能传的字段就是建表列去掉 key / updated_at / hidden，全部下划线
    # 写法：number / title / actor / thumb / size / hash / path / downloader / state / source /
    # created_at / completed_at（接口层要前端的驼峰形状，由接口层自己转），v4 又加了
    # version_tags / emby_id / failed_reason。
    # `hidden` 只能通过 `download_delete` 置位（墓碑），不开放给写入方传。

    def download_upsert(self, number: str, **fields: Any) -> None:
        """登记一条下载（插入或就地合并）。番号归一化后做 key。

        合并规则：`number` 非空才覆盖展示番号；空字符串不覆盖已有值；`created_at` 只在首次
        写入时落；每次都写 `updated_at`；`state='downloaded'` 时补 `completed_at`（已有则不动）。
        v4 三个新字段同口径：`version_tags` 非空且非 `'{}'` 才覆盖、`emby_id` / `failed_reason`
        非空才覆盖（想显式清空请直接 `download_seed` 之外的老办法做不到 —— 台账不做"清空"语义，
        这是刻意的：空值一律当"这次没拿到"，不是"要抹掉"）。
        `version_tags` 可以直接给 dict/list（内部序列化），给串则原样存。
        """
        self._download_merge(number, number, fields)

    def download_seed(self, rows: List[Dict[str, Any]]) -> int:
        """批量登记（Emby 库里补种 / 老队列迁移用），返回**新插入**条数。

        合并规则比 `download_upsert` 保守一档：**只补空，绝不覆盖已有非空值**（`source` 也在内），
        只有 `state`（可升级成 downloaded）与空的 `completed_at` 照旧. 理由见 `_DL_SEED` 上面那段：
        seed 的来源是 Emby 库那种派生信息，而这里已有的值多半来自插件提交下载的权威口径。
        行里给 `number` 或 `key` 都行（Emby 索引本身就是按归一化 key 组织的）：只给 `key` 时
        展示番号留空，等后续带番号的登记来补——别把归一化结果当展示番号写进历史页。
        """
        inserted = 0
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            number = str(row.get("number") or "")
            if self._download_merge(number or str(row.get("key") or ""), number, row,
                                    only_fill_empty=True):
                inserted += 1
        return inserted

    def download_list(self, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """全量台账（不含被移除的墓碑行），完成时间新→旧；未完成的 `completed_at` 是空串，
        排序上自然落在最后。

        `sources` 给一组来源就只回那几种行（2026-10-12 加）：界面侧一律传
        `PLUGIN_SOURCES`，见 `__init__.py` 里 `_downloads_payload()` 的说明 ——
        `source='library'` 那批是「番号本来就在 Emby 库里」的补种行，不是这个插件下载的，
        对用户来说它们属于「已入库的番号」那一栏，不属于「下载历史」。
        `None`（默认）= 不过滤，给需要"全量台账"的调用方（诊断、导出）留着。
        """
        sql = f"SELECT {_DL_SELECT} FROM downloads WHERE hidden = 0"
        args: List[Any] = []
        picked = [str(s) for s in (sources or []) if str(s)]
        if picked:
            sql += f" AND source IN ({','.join('?' * len(picked))})"
            args.extend(picked)
        sql += " ORDER BY completed_at DESC, created_at DESC"
        rows = self._exec(sql, tuple(args), fetch=True) or []
        return [self._download_row(r) for r in rows]

    def download_map(self, sources: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """`归一化番号 → 行`（插件侧打「已下载」徽标用）；同样不回墓碑行。

        每个电影查一次库会把列表页拖慢（Emby 那套索引就是因此才做内存缓存的），
        调用方自己带 TTL 缓存，别每个番号调一次。`sources` 语义同 `download_list()`。
        """
        return {row["key"]: row for row in self.download_list(sources)}

    def download_delete(self, key_or_number: str) -> bool:
        """「移除记录」：打墓碑（`hidden=1`），**不是**物理删除。

        为什么必须留墓碑：`/downloads` 每次打开都从 Emby 库全量补种，真删的行下一轮就被库里的
        记录顶回来（用户点完「移除记录」几秒后又冒出来，比不给删更糟）。读法只回 `hidden=0`
        的行，所以对用户来说这条就此消失；行本身留着，用户重新下载时由 `download_upsert` 解除。
        台账里没有这个键时也占一行墓碑：否则下次补种照样会把它建出来。
        返回 True 表示「这条现在不会再出现在列表里」（幂等，重复移除同一个键仍返回 True）。
        """
        key = _norm_key(key_or_number)
        if not key:
            return False        # 归一不出 key 就无从打墓碑
        now = _now()
        self._exec(
            "INSERT INTO downloads(key, hidden, created_at, updated_at) VALUES(?,1,?,?) "
            "ON CONFLICT(key) DO UPDATE SET hidden=1, updated_at=excluded.updated_at",
            (key, now, now),
        )
        return True

    def _download_merge(self, key_from: str, number: str, fields: Dict[str, Any],
                        only_fill_empty: bool = False) -> bool:
        """插入或就地合并一条台账，返回是否**新插入**。

        `key_from` 只用来归一化成主键，`number` 才是写进展示列的值——两者分开是因为 Emby
        索引只给得出归一化 key：补种时展示番号必须留空（等后续带番号的登记来补），
        不能把 `IPZZ961` 这种归一化结果当展示番号写进历史页。

        `only_fill_empty` 选合并规则：False=非空覆盖（`download_upsert`）、True=只补空
        （`download_seed`）。两条规则都落在 SQL 里，理由见 `_DL_UPSERT` / `_DL_SEED` 上面。

        读与写放在同一次持锁里（照 `kv_update` 的写法）：Emby 补种、老队列迁移、提交下载
        三个写入方可能同时在跑，「是不是新插入」要数得准，否则 `download_seed` 的条数会飘。
        """
        key = _norm_key(key_from)
        if not key:
            return False        # 归一不出 key 就登记不了，也不能拿空 key 占掉主键那一行
        now = _now()
        state = str(fields.get("state") or "")
        completed = str(fields.get("completed_at") or "")
        if not completed and state == "downloaded":
            completed = now     # 变成已下载时补完成时间；已有值由 SQL 保持不动
        created = str(fields.get("created_at") or "") or now
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._connect()
            try:
                exists = conn.execute(
                    "SELECT 1 FROM downloads WHERE key=?", (key,)
                ).fetchone() is not None
                source = str(fields.get("source") or "")
                if not exists:
                    # 建表默认值只在「这一列没出现在 INSERT 里」时生效，而这几列每次都要绑值
                    source = source or "plugin"
                    state = state or "downloading"
                conn.execute(_DL_SEED if only_fill_empty else _DL_UPSERT, (
                    key, str(number or ""), str(fields.get("title") or ""),
                    str(fields.get("actor") or ""), str(fields.get("thumb") or ""),
                    _to_int(fields.get("size")), str(fields.get("hash") or ""),
                    str(fields.get("path") or ""), str(fields.get("downloader") or ""),
                    state, source, created, completed, now,
                    _json_text(fields.get("version_tags"), "{}"),
                    str(fields.get("emby_id") or ""),
                    str(fields.get("failed_reason") or ""),
                ))
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        return not exists

    @staticmethod
    def _download_row(row: Any) -> Dict[str, Any]:
        """一行 → dict（键名就是表列名：这是「台账行」本身，接口层再转前端形状）。

        `hidden` 也照原样给出去：读法已经滤掉墓碑行，这个字段留在行里是给调用方
        （以及测试）确认「墓碑确实解除了」用的，接口层不往外发。

        v4 三列**原样**给：`version_tags` 是 JSON **串**（列默认 `'{}'`），要对象请
        `json.loads`（`__init__.py` 的 `/downloads` 就是在这上面转出 `version_tags[]` 列表）；
        `emby_id` / `failed_reason` 是普通文本列。
        """
        return {
            "key": row[0], "number": row[1] or "", "title": row[2] or "",
            "actor": row[3] or "", "thumb": row[4] or "", "size": _to_int(row[5]),
            "hash": row[6] or "", "path": row[7] or "", "downloader": row[8] or "",
            "state": row[9] or "downloading", "source": row[10] or "plugin",
            "created_at": row[11] or "", "completed_at": row[12] or "",
            "updated_at": row[13] or "", "hidden": _to_int(row[14]),
            "version_tags": row[15] or "{}",
            "emby_id": row[16] or "",
            "failed_reason": row[17] or "",
        }

    # ---------- 作品级元数据（meta，v4 刮削层） ----------

    def meta_get(self, key: str) -> Optional[Dict[str, Any]]:
        """按归一化番号取一条作品元数据；没有回 None。

        返回的 dict 里 JSON 列给两份：原始串（`actors_json`…）与解析副本（`actors`/`tags`/
        `samples`/`raw`），见 `_meta_row()` 的说明。
        """
        name = str(key or "").strip()
        if not name:
            return None
        rows = self._exec(f"SELECT {_META_SELECT} FROM meta WHERE key=?", (name,), fetch=True) or []
        return _meta_row(rows[0]) if rows else None

    def meta_upsert(self, key: str, **fields: Any) -> None:
        """写一条作品级元数据：**只覆盖传进来的字段**，`updated_at` 自动刷新。

        为什么要「只覆盖传入字段」：刮削是分来源、分字段落地的（javdb 给标题/演员、javtxt 给
        简介、LLM 给汉化），一次 upsert 只该动它这次真拿到的东西；整行覆盖会让「这一轮没有简介」
        把上一轮刮到的简介抹成空串。**要显式写空串就显式传**（`meta_upsert(k, plot_zh="")`），
        这是清空某列的唯一方式。
        行不存在时按建表默认值补全后插入（`display_number` 是 NOT NULL 且没有默认值，
        缺省拿 key 兜底；S7/S8 正常都会显式传展示番号）。
        JSON 列（`actors_json`/`tags_json`/`samples_json`/`raw_json`）可以直接给 list/dict。
        """
        name = str(key or "").strip()
        if not name:
            return
        picked = {k: v for k, v in (fields or {}).items() if k in _META_FIELDS}
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                exists = conn.execute("SELECT 1 FROM meta WHERE key=?", (name,)).fetchone() is not None
                if exists:
                    sets = [f"{col}=?" for col in picked]
                    args = [_meta_value(col, val) for col, val in picked.items()]
                    sets.append("updated_at=?")
                    args.append(now)
                    conn.execute(
                        f"UPDATE meta SET {', '.join(sets)} WHERE key=?", (*args, name)
                    )
                else:
                    values: Dict[str, Any] = dict(_META_DEFAULTS)
                    values["display_number"] = name
                    for col, val in picked.items():
                        values[col] = _meta_value(col, val)
                    if not str(values.get("display_number") or "").strip():
                        values["display_number"] = name
                    values["updated_at"] = now
                    cols = ["key"] + list(values.keys())
                    conn.execute(
                        f"INSERT INTO meta({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                        (name, *values.values()),
                    )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    def meta_list(self, limit: int = 0, offset: int = 0, where: str = "",
                  **filters: Any) -> List[Dict[str, Any]]:
        """列元数据（新改的在前）。

        `limit<=0` = 不限条数；`filters` 里**列名同名**的键按等值过滤（`completeness="full"`），
        与 `item_list()` 同一套口径（不认识的列名直接忽略）。

        ⚠️ P1-9：`where` **已废止** —— 它是"把调用方给的片段原样拼进 SQL"，是一个注入面
        （amane `docs/dev/api.md` 明令禁止反射列名/拼串）。要过滤请加**列参数**：
        老写法 `meta_list(where="completeness='full'")` 现在等价于 `meta_list(completeness="full")`。
        """
        clause: List[str] = []
        args: List[Any] = []
        for name, value in (filters or {}).items():
            if name not in _META_COLUMN_SET:
                continue
            clause.append(f"{name} = ?")
            args.append(value)
        sql = f"SELECT {_META_SELECT} FROM meta"
        raw = str(where or "").strip()
        if raw:
            logger.warning("AVHelper meta_list(where=…) 已废止（P1-9 去掉原始 SQL 拼串）："
                           f"该片段被忽略 → {raw[:80]}；请改用列参数过滤")
        if clause:
            sql += " WHERE " + " AND ".join(clause)
        sql += " ORDER BY updated_at DESC, key ASC"
        size = _to_int(limit)
        skip = _to_int(offset)
        if size > 0:
            sql += " LIMIT ?"
            args.append(size)
            if skip > 0:
                sql += " OFFSET ?"
                args.append(skip)
        elif skip > 0:
            sql += " LIMIT -1 OFFSET ?"
            args.append(skip)
        rows = self._exec(sql, tuple(args), fetch=True) or []
        return [_meta_row(r) for r in rows]

    def meta_stats(self) -> Dict[str, int]:
        """完整度分档计数（`/scrape/status` 的 `stats`）。

        `untranslated` = `translation_status='untranslated'` 的行数（`machine_fallback`
        算已翻，机翻也是翻——它与「没翻」在界面上是两种状态）。
        """
        rows = self._exec(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN completeness='full' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN completeness='missing_plot' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN completeness='missing_core' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN translation_status='untranslated' THEN 1 ELSE 0 END) "
            "FROM meta",
            fetch=True,
        ) or []
        row = rows[0] if rows else (0, 0, 0, 0, 0)
        return {
            "total": _to_int(row[0]),
            "full": _to_int(row[1]),
            "missing_plot": _to_int(row[2]),
            "missing_core": _to_int(row[3]),
            "untranslated": _to_int(row[4]),
        }

    def meta_due(self, now: str = "", tier: int = 1, limit: int = 5) -> List[Dict[str, Any]]:
        """取「该重刮」的两档队列（v4.1 §5.3 双队列分层）。

        - tier=1：`next_retry_at` 非空且 <= now 的行，按 `next_retry_at` 升序 —— 这些是
          上次失败/缺简介、由刮削器约好下一次重试时间的条目（到点才回，早回就是空转）。
        - tier=2：全表按 `last_scraped_at` 升序（**空串最优先**，即从没刮过的排最前），
          取 limit 条 —— 新片饥饿问题就靠这一档兜。
        `now` 留空 = 用当前时间；`limit<=0` 按默认 5 处理（队列函数不给"全取"的口子）。
        """
        stamp = str(now or "").strip() or _now()
        size = _to_int(limit) or 5
        if _to_int(tier) == 2:
            sql = (f"SELECT {_META_SELECT} FROM meta "
                   "ORDER BY last_scraped_at ASC, updated_at ASC LIMIT ?")
            args: tuple = (size,)
        else:
            # P1-9：`IFNULL(next_retry_at,'') <> ''` 会让 `next_retry_at` 上的**索引失效**
            # （函数包住的列没法走索引），语义相同但索引可用的写法是 IS NOT NULL + <> ''。
            sql = (f"SELECT {_META_SELECT} FROM meta "
                   "WHERE next_retry_at IS NOT NULL AND next_retry_at <> '' "
                   "AND next_retry_at <= ? "
                   "ORDER BY next_retry_at ASC LIMIT ?")
            args = (stamp, size)
        rows = self._exec(sql, args, fetch=True) or []
        return [_meta_row(r) for r in rows]

    # ---------- 媒体实例（media_item，v4 刮削层） ----------

    def item_get(self, item_key: str) -> Optional[Dict[str, Any]]:
        """按实例键取一行（`emby:{id}` / `dl:{hash}`）；没有回 None。"""
        name = str(item_key or "").strip()
        if not name:
            return None
        rows = self._exec(
            f"SELECT {_ITEM_SELECT} FROM media_item WHERE item_key=?", (name,), fetch=True
        ) or []
        return _item_row(rows[0]) if rows else None

    def item_upsert(self, item_key: str, key: str, **fields: Any) -> None:
        """登记一个媒体实例：只覆盖传进来的字段（口径同 `meta_upsert`）。

        `item_key` 是实例主键（`emby:12598` / `dl:<hash>`），`key` 是它挂在哪个作品上
        （`meta.key`）——后者是位置参数、每次都会写（它决定这条实例归到哪部片）。
        行不存在时按建表默认值补全后插入；`display_number` 缺省拿 `key` 兜底。
        `emby_backup_json` **不在这里写**（只能由 `item_backup_save()` 写一次，裁决 D7）。
        """
        name = str(item_key or "").strip()
        if not name:
            return
        relation = str(key or "").strip()
        picked = {k: v for k, v in (fields or {}).items() if k in _ITEM_FIELDS}
        with self._lock:
            conn = self._connect()
            try:
                exists = conn.execute(
                    "SELECT 1 FROM media_item WHERE item_key=?", (name,)
                ).fetchone() is not None
                if exists:
                    sets = ["key=?"]
                    args: List[Any] = [relation]
                    for col, val in picked.items():
                        sets.append(f"{col}=?")
                        args.append(_item_value(col, val))
                    conn.execute(
                        f"UPDATE media_item SET {', '.join(sets)} WHERE item_key=?",
                        (*args, name),
                    )
                else:
                    values: Dict[str, Any] = dict(_ITEM_DEFAULTS)
                    values["key"] = relation
                    for col, val in picked.items():
                        values[col] = _item_value(col, val)
                    if not str(values.get("display_number") or "").strip():
                        values["display_number"] = relation or name
                    cols = ["item_key"] + list(values.keys())
                    conn.execute(
                        f"INSERT INTO media_item({', '.join(cols)}) "
                        f"VALUES({', '.join('?' * len(cols))})",
                        (name, *values.values()),
                    )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    def item_list(self, key: str = "", **filters: Any) -> List[Dict[str, Any]]:
        """列媒体实例。

        `key` 给作品 key 就只回该作品的实例；`filters` 里**列名同名**的键按等值过滤
        （如 `library_state='in_library'`、`emby_id='12598'`），另认三个保留键：
        `limit` / `offset` / `order`（**排序白名单**，见 `_item_order()`）。
        不认识的过滤键**直接忽略**（列名拼错不该把整个读接口炸掉）。

        ⚠️ P1-9：`order` 不再原样拼串（那是注入面），只认 `media_item` 的列名
        （`"last_synced_at"`、`"-last_synced_at"`，以及老的 `"last_synced_at DESC"` 写法）；
        `where` **已废止**（今天没有调用方，认不出的片段只记 warning）。
        """
        clause: List[str] = []
        args: List[Any] = []
        text = str(key or "").strip()
        if text:
            clause.append("key = ?")
            args.append(text)
        for name, value in (filters or {}).items():
            if name in ("limit", "offset", "order", "where") or name not in _ITEM_COLUMN_SET:
                continue
            clause.append(f"{name} = ?")
            args.append(value)
        raw_where = str(filters.get("where") or "").strip()
        if raw_where:
            logger.warning("AVHelper item_list(where=…) 已废止（P1-9 去掉原始 SQL 拼串）："
                           f"该片段被忽略 → {raw_where[:80]}")
        sql = f"SELECT {_ITEM_SELECT} FROM media_item"
        if clause:
            sql += " WHERE " + " AND ".join(clause)
        sql += f" ORDER BY {_item_order(filters.get('order'))}"
        size = _to_int(filters.get("limit"))
        skip = _to_int(filters.get("offset"))
        if size > 0:
            sql += " LIMIT ?"
            args.append(size)
            if skip > 0:
                sql += " OFFSET ?"
                args.append(skip)
        elif skip > 0:
            sql += " LIMIT -1 OFFSET ?"
            args.append(skip)
        rows = self._exec(sql, tuple(args), fetch=True) or []
        return [_item_row(r) for r in rows]

    def item_set(self, item_key: str, **fields: Any) -> bool:
        """改一个已存在实例的若干列，返回**是否真的改到了行**。

        只改现有的行（没有就是没得改，返回 False）：新实例必须带 `key`（它属于哪部作品）
        才能建，那是 `item_upsert()` 的活。`emby_backup_json` 不在可写字段里（见 D7）。
        """
        name = str(item_key or "").strip()
        picked = {k: v for k, v in (fields or {}).items() if k in _ITEM_FIELDS}
        if not name or not picked:
            return False
        sets = [f"{col}=?" for col in picked]
        args = [_item_value(col, val) for col, val in picked.items()]
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    f"UPDATE media_item SET {', '.join(sets)} WHERE item_key=?", (*args, name)
                )
                hit = cur.rowcount > 0
                conn.commit()
                return hit
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    def item_backup_save(self, item_key: str, dto_json: str) -> bool:
        """首次改写 Emby 前落一份完整 DTO 备份；**已有非空备份时绝不覆盖，返回 False**。

        这是 v4.1 §8.1 / 裁决 D7 的闸门本身。**调用方的正确用法**是"先存再查"：
        `scraper` 写 Emby 之前先调这里把这次读到的 DTO 尽力存下来，然后拿
        `item_backup_get(item_key)` 判闸门 —— 只在它**非空**时才允许写 Emby：

            store.item_backup_save(item_key, dto_json)      # 返回值示意"这次写进去没有"
            if not store.item_backup_get(item_key):         # 真正判"有没有备份"
                return 拒绝写入

        为什么不能只看返回值：False 有两种含义（已有备份、这次给的备份是空的），
        单看返回值会把「早就备份过」误判成「没备份成」而永远不敢写。空备份（`dto_json` 为空）
        一律不存：拿不到 DTO 就不该写 Emby。
        行不存在时补一条最小实例行（`key`/`display_number` 留空、`emby_id` 从 `emby:<id>` 拆，
        后面 `item_upsert()` 会补），免得"第一次就该备份"的路径因为行还没建而永远过不去。
        """
        name = str(item_key or "").strip()
        dto = str(dto_json or "")
        if not name or not dto:
            return False            # 空备份不算备份
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "UPDATE media_item SET emby_backup_json=?, last_synced_at=? "
                    "WHERE item_key=? AND IFNULL(emby_backup_json, '') = ''",
                    (dto, now, name),
                )
                saved = cur.rowcount > 0
                if not saved:
                    exists = conn.execute(
                        "SELECT 1 FROM media_item WHERE item_key=?", (name,)
                    ).fetchone()
                    if not exists:
                        prefix, _, tail = name.partition(":")
                        emby_id = tail if prefix == "emby" else ""
                        conn.execute(
                            "INSERT INTO media_item(item_key, key, display_number, emby_id, "
                            "emby_backup_json, last_synced_at) VALUES(?,?,?,?,?,?)",
                            (name, "", "", emby_id, dto, now),
                        )
                        saved = True
                conn.commit()
                return bool(saved)
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise

    def item_backup_get(self, item_key: str) -> str:
        """取回那份 DTO 备份（没有回空串）；回滚用。"""
        name = str(item_key or "").strip()
        if not name:
            return ""
        rows = self._exec(
            "SELECT emby_backup_json FROM media_item WHERE item_key=?", (name,), fetch=True
        ) or []
        return str(rows[0][0] or "") if rows else ""

    # ---------- 三语标准映射（name_map，v4 刮削层） ----------

    def namemap_bulk_upsert(self, rows: List[Dict[str, Any]]) -> int:
        """批量导入映射（内置 XML 那份），返回写入条数。

        入参约定（主统筹 2026-10-14 口径）：`canonical_id` 形如 `amane:三上悠亚`，
        `source='builtin_xml'`（内置）或 `'user_custom'`（用户）；`zh_cn`/`zh_tw`/`jp` 三列都可能非空；
        `keywords_norm` 是**已经归一化好的逗号包裹整词串**（`,mikamiyua,三上悠亚,`），
        **原样存字符串**（只有传 list/tuple/set 时才由这里逗号包裹起来）。

        两条规矩：
        1. **用户手工映射最高优先级**：已有行 `source='user_custom'` 时，非 user_custom 的
           导入行直接跳过（`init()` 每次都会跑，否则内置表一重导就把用户的称呼顶掉）。
        2. 内置行整列覆盖（XML 是它的权威来源）；`source='user_custom'` 的行取别名并集。
        """
        written = 0
        with self._lock:
            conn = self._connect()
            try:
                for row in rows or []:
                    if not isinstance(row, dict):
                        continue
                    cid = str(row.get("canonical_id") or "").strip()
                    entity = str(row.get("entity_type") or "").strip()
                    if not cid or not entity:
                        continue        # 主键/实体类型缺一个都落不了库
                    source = str(row.get("source") or "builtin_xml").strip() or "builtin_xml"
                    old = conn.execute(
                        "SELECT source, keywords_norm FROM name_map WHERE canonical_id=?", (cid,)
                    ).fetchone()
                    if old and str(old[0] or "") == "user_custom" and source != "user_custom":
                        continue
                    keywords = row.get("keywords_norm")
                    if keywords is None or isinstance(keywords, (list, tuple, set)):
                        tokens = list(keywords or [])
                        if old and source == "user_custom":
                            keywords = merge_keywords(old[1], tokens)
                        else:
                            keywords = join_keywords(tokens)
                    else:
                        keywords = merge_keywords(keywords) if source == "user_custom" \
                            else str(keywords)
                    values = dict(_NAME_MAP_DEFAULTS)
                    values.update({
                        "entity_type": entity,
                        "zh_cn": str(row.get("zh_cn") or ""),
                        "zh_tw": str(row.get("zh_tw") or ""),
                        "jp": str(row.get("jp") or ""),
                        "keywords_norm": keywords,
                        "javdb_actor_id": str(row.get("javdb_actor_id") or ""),
                        "emby_person_id": str(row.get("emby_person_id") or ""),
                        "avatar_url": str(row.get("avatar_url") or ""),
                        "is_delete_rule": 1 if row.get("is_delete_rule") else 0,
                        "source": source,
                    })
                    cols = ["canonical_id"] + list(values.keys()) + ["updated_at"]
                    conn.execute(
                        f"INSERT INTO name_map({', '.join(cols)}) "
                        f"VALUES({', '.join('?' * len(cols))}) "
                        "ON CONFLICT(canonical_id) DO UPDATE SET "
                        + ", ".join(f"{c}=excluded.{c}" for c in values) +
                        ", updated_at=excluded.updated_at",
                        (cid, *values.values(), _now()),
                    )
                    written += 1
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        return written

    def namemap_get(self, canonical_id: str) -> Optional[Dict[str, Any]]:
        """按 canonical_id 取一条映射。"""
        cid = str(canonical_id or "").strip()
        if not cid:
            return None
        rows = self._exec(
            f"SELECT {_NAME_MAP_SELECT} FROM name_map WHERE canonical_id=?", (cid,), fetch=True
        ) or []
        return _name_map_row(rows[0]) if rows else None

    def namemap_find(self, entity_type: str, *names: Any) -> Optional[Dict[str, Any]]:
        """按名字找映射：`keywords_norm` 是**逗号包裹的整词串**（`,mikamiyua,三上悠亚,三上悠亜,`），
        查询用**整词匹配** `keywords_norm LIKE '%,' || ? || ',%'`（`?` = **归一化后**的查询词，
        绑定值就是 `%,<词>,%`）。

        **不许用裸 `%…%` 子串匹配**：上游归一化之后 `男優` 一个键能命中 220 条、
        `バカボン` 与 `バカボン×` 撞车，子串匹配只会放大误命中（主统筹 2026-10-14 口径）。
        归一化走 `_norm_lookup()` → `namemap.normalize()`（S3 的口径唯一来源；模块没落地时
        退回本地最小规则），原文/归一化/小写三种形式各试一次，所以调用方给原文或给归一化后的
        词都能查到（重复归一化是幂等的）。
        一行有多个名字命中时，`source='user_custom'` 的行优先：用户手工设定的称呼是最高优先级，
        不能被内置表里同样含这个别名的行抢走。
        """
        entity = str(entity_type or "actor").strip() or "actor"
        tokens: List[str] = []
        for item in names:
            text = str(item or "").strip()
            if text and text not in tokens:
                tokens.append(text)
        if not tokens:
            return None
        # 「先给的先算」：按调用方给的名字顺序找，同一名字下 user_custom 优先（见 _namemap_rows_for）
        found = self._namemap_rows_for(self._connect(), entity, tokens)
        return found[0] if found else None

    def namemap_list(self, entity_type: str = "", limit: int = 0, offset: int = 0,
                     like: str = "") -> List[Dict[str, Any]]:
        """列映射（`/namemap/actors`、`/namemap/tags` 用）。

        `like` 同时匹配 `zh_cn` / `zh_tw` / `jp` / `canonical_id` / `keywords_norm`
        （界面上搜索框打中文、日文、罗马音都该搜得到）。`limit<=0` = 不限。
        """
        clause: List[str] = []
        args: List[Any] = []
        entity = str(entity_type or "").strip()
        if entity:
            clause.append("entity_type = ?")
            args.append(entity)
        text = str(like or "").strip()
        if text:
            pattern = f"%{text}%"
            clause.append(
                "(zh_cn LIKE ? OR zh_tw LIKE ? OR jp LIKE ? OR canonical_id LIKE ? "
                "OR keywords_norm LIKE ?)"
            )
            args.extend([pattern] * 5)
        sql = f"SELECT {_NAME_MAP_SELECT} FROM name_map"
        if clause:
            sql += " WHERE " + " AND ".join(clause)
        sql += " ORDER BY entity_type ASC, canonical_id ASC"
        size = _to_int(limit)
        skip = _to_int(offset)
        if size > 0:
            sql += " LIMIT ?"
            args.append(size)
            if skip > 0:
                sql += " OFFSET ?"
                args.append(skip)
        elif skip > 0:
            sql += " LIMIT -1 OFFSET ?"
            args.append(skip)
        rows = self._exec(sql, tuple(args), fetch=True) or []
        return [_name_map_row(r) for r in rows]

    def namemap_user_set(self, entity_type: str, zh: str, jp: str = "",
                         canonical_id: str = "") -> str:
        """写入一条**用户手工**映射（`source='user_custom'`），返回它的 canonical_id。

        - 用户手工映射是**最高优先级**：命中同一实体的内置行会被就地改成 user_custom
          （`namemap_bulk_upsert` 之后不会再覆盖它），`namemap_find` 也优先回它。
        - `canonical_id` 缺省时先按名字在库里找这个实体的已有行并**沿用它的 id**
          （用户改的是显示名，不该因为改了名就多出一行、旧行还留着）；实在找不到才按
          契约的默认规则 `f"{entity_type}:{zh}"` 生成。
        - 别名串取并集，中文名/日文名/罗马音都塞进 `keywords_norm`，汉化前后都查得到。
        """
        entity = str(entity_type or "actor").strip() or "actor"
        zh_text = str(zh or "").strip()
        jp_text = str(jp or "").strip()
        cid = str(canonical_id or "").strip()
        if not zh_text and not jp_text and not cid:
            return ""
        tokens = [_norm_lookup(zh_text), _norm_lookup(jp_text)]
        with self._lock:
            conn = self._connect()
            try:
                if not cid:
                    found = self._namemap_rows_for(conn, entity, [zh_text, jp_text])
                    if found:
                        cid = str(found[0]["canonical_id"])
                if not cid:
                    cid = f"{entity}:{zh_text or jp_text}"
                self._write_user_mapping(conn, canonical_id=cid, entity_type=entity,
                                         zh=zh_text, jp=jp_text, tokens=tokens)
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        return cid

    def _namemap_rows_for(self, conn: sqlite3.Connection, entity_type: str,
                          names: List[str]) -> List[Dict[str, Any]]:
        """按若干名字取所有命中的映射行（user_custom 优先）；`namemap_find` 与
        `namemap_user_set` 的「同一实体」判定共用。"""
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for item in names:
            for probe in _probe_forms(item):
                rows = conn.execute(
                    f"SELECT {_NAME_MAP_SELECT} FROM name_map "
                    "WHERE entity_type=? AND keywords_norm LIKE ? ESCAPE '\\' "
                    "ORDER BY CASE WHEN source='user_custom' THEN 0 ELSE 1 END, canonical_id",
                    (entity_type, f"%,{_like_escape(probe)},%"),
                ).fetchall()
                for row in rows:
                    parsed = _name_map_row(row)
                    if parsed["canonical_id"] in seen:
                        continue
                    seen.add(parsed["canonical_id"])
                    out.append(parsed)
        return out

    def _write_user_mapping(self, conn: sqlite3.Connection, *, canonical_id: str,
                            entity_type: str, zh: str = "", jp: str = "",
                            tokens: Any = ()) -> None:
        """写一条用户映射（`_sync_aliases` 与 `namemap_user_set` 共用；调用方须持锁）。

        只动 `zh_cn` / `jp` / `keywords_norm` / `source` / `updated_at`：已有行上的
        `zh_tw` / `avatar_url` / `javdb_actor_id` / `emby_person_id` 是别的来源（内置表、
        javdb 头像）填的，不该被一条备注抹掉。
        """
        old = conn.execute(
            "SELECT keywords_norm FROM name_map WHERE canonical_id=?", (canonical_id,)
        ).fetchone()
        keywords = merge_keywords(old[0] if old else "", tokens)
        conn.execute(
            "INSERT INTO name_map(canonical_id, entity_type, zh_cn, jp, keywords_norm, source, "
            "updated_at) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(canonical_id) DO UPDATE SET "
            "zh_cn=CASE WHEN excluded.zh_cn <> '' THEN excluded.zh_cn ELSE name_map.zh_cn END, "
            "jp=CASE WHEN excluded.jp <> '' THEN excluded.jp ELSE name_map.jp END, "
            "keywords_norm=excluded.keywords_norm, source='user_custom', "
            "updated_at=excluded.updated_at",
            (canonical_id, entity_type, str(zh or ""), str(jp or ""), keywords, "user_custom",
             _now()),
        )

    # ---------- 翻译缓存（translate，v4 刮削层） ----------

    def translate_get(self, cache_key: str) -> Optional[str]:
        """取一条翻译缓存；没有（或键为空）回 None。空串译文是合法值，照原样回。"""
        key = str(cache_key or "").strip()
        if not key:
            return None
        rows = self._exec(
            "SELECT translated_text FROM translate WHERE cache_key=?", (key,), fetch=True
        )
        if not rows:
            return None
        return str(rows[0][0] or "")

    def translate_put(self, cache_key: str, source_text: str, translated_text: str,
                      model_name: str = "", quality_tier: str = "llm") -> None:
        """写一条翻译缓存（同键覆盖；`created_at` 刷新成这次写入时间）。"""
        key = str(cache_key or "").strip()
        if not key:
            return
        self._exec(
            "INSERT INTO translate(cache_key, source_text, translated_text, model_name, "
            "quality_tier, created_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(cache_key) DO UPDATE SET source_text=excluded.source_text, "
            "translated_text=excluded.translated_text, model_name=excluded.model_name, "
            "quality_tier=excluded.quality_tier, created_at=excluded.created_at",
            (key, str(source_text or ""), str(translated_text or ""), str(model_name or ""),
             str(quality_tier or "llm"), _now()),
        )

    # ---------- 数据源自检日志（scrape_log，v4 刮削层） ----------

    def scrape_log_add(self, source_name: str, status: str, key: str = "", latency_ms: int = 0,
                       error_summary: str = "", reason: str = "", http_status: int = 0,
                       run_id: str = "") -> None:
        """记一条数据源调用结果（自检页与排障用）。

        `error_summary` 裁到 500 字符：这是给界面看的一句话摘要，不是堆栈仓库；
        表本身顺手裁到最近 `_SCRAPE_LOG_KEEP` 条（同 notice 只留 200 条的思路）。

        `reason` 是**机器可读**的失败原因（封闭枚举，值见 `scraper.REASONS`）：`status` 说
        "成没成"，`reason` 说"为什么" —— 只靠 status 分不清「站点没收录这部片（miss）」与
        「被 CF / 年龄墙拦了（error）」，而这两种的处置完全相反（前者换源，后者冷却 + 换 UA）。
        `run_id` 把同一次刮削的各源记录串成一组（`scrape_log_run()` 取回）。
        """
        self._exec(
            "INSERT INTO scrape_log(source_name, key, status, latency_ms, error_summary, "
            "created_at, reason, http_status, run_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (str(source_name or ""), str(key or ""), str(status or ""), _to_int(latency_ms),
             str(error_summary or "")[:500], _now(), str(reason or ""),
             _to_int(http_status), str(run_id or "")),
        )
        self._exec(
            "DELETE FROM scrape_log WHERE id NOT IN "
            "(SELECT id FROM scrape_log ORDER BY id DESC LIMIT ?)",
            (_SCRAPE_LOG_KEEP,),
        )

    def scrape_log_recent(self, limit: int = 50, source_name: str = "") -> List[Dict[str, Any]]:
        """最近的自检日志（新→旧）。

        行里 `source`/`error` 与 `source_name`/`error_summary` 两份键都给：REST 契约
        （§3.7 `/scrape/log`）写的是前者，表列名是后者，两边调用方都不用再改名。
        `reason` / `http_status` / `run_id` 照表列名给（0.8.0 加的排障字段）。
        """
        size = _to_int(limit) or 50
        sql = ("SELECT id, source_name, key, status, latency_ms, error_summary, created_at, "
               "reason, http_status, run_id FROM scrape_log")
        args: List[Any] = []
        source = str(source_name or "").strip()
        if source:
            sql += " WHERE source_name = ?"
            args.append(source)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(max(size, 1))
        rows = self._exec(sql, tuple(args), fetch=True) or []
        return [{
            "id": r[0], "source_name": r[1] or "", "source": r[1] or "", "key": r[2] or "",
            "status": r[3] or "", "latency_ms": _to_int(r[4]),
            "error_summary": r[5] or "", "error": r[5] or "", "created_at": r[6] or "",
            "reason": r[7] or "", "http_status": _to_int(r[8]), "run_id": r[9] or "",
        } for r in rows]

    def scrape_log_run(self, run_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        """取一次刮削（`run_id`）的全部站点记录，**旧→新**（按发生顺序读"当时发生了什么"）。

        与 `scrape_log_recent()` 的区别只在顺序与过滤：这里是"一次 run 的叙事"，
        那里是"最近发生了什么"。
        """
        text = str(run_id or "").strip()
        if not text:
            return []
        rows = self._exec(
            "SELECT id, source_name, key, status, latency_ms, error_summary, created_at, "
            "reason, http_status FROM scrape_log WHERE run_id = ? ORDER BY id ASC LIMIT ?",
            (text, max(_to_int(limit) or 200, 1)), fetch=True,
        ) or []
        return [{
            "id": r[0], "source_name": r[1] or "", "source": r[1] or "", "key": r[2] or "",
            "status": r[3] or "", "latency_ms": _to_int(r[4]),
            "error_summary": r[5] or "", "error": r[5] or "", "created_at": r[6] or "",
            "reason": r[7] or "", "http_status": _to_int(r[8]), "run_id": text,
        } for r in rows]

    def scrape_log_runs(self, key: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """按 `run_id` 归组列出最近的刮削批次（P0-4：挑一次现场来离线回放）。

        `key` 给了就只列这部片的批次；每行 `{run_id, started_at, ended_at, sources, failed}`。
        没有 `run_id` 的老记录（0.8.0 之前写的）不列 —— 回放按 `run_id` 找不到它们的现场。
        """
        args: List[Any] = []
        where = "run_id <> ''"
        if str(key or "").strip():
            where += " AND key = ?"
            args.append(str(key).strip())
        args.append(max(1, _to_int(limit) or 5))
        rows = self._exec(
            "SELECT run_id, MIN(created_at), MAX(created_at), COUNT(*), "
            "SUM(CASE WHEN status IN ('error','miss','timeout','blocked') THEN 1 ELSE 0 END) "
            f"FROM scrape_log WHERE {where} GROUP BY run_id "
            "ORDER BY MAX(id) DESC LIMIT ?", tuple(args), fetch=True) or []
        return [{"run_id": str(r[0] or ""), "started_at": str(r[1] or ""),
                 "ended_at": str(r[2] or ""), "sources": _to_int(r[3]), "failed": _to_int(r[4])}
                for r in rows]

    def scrape_log_summary(self) -> List[Dict[str, Any]]:
        """按数据源汇总：总数 / 成功 / 失败 / 平均耗时 / **各失败原因计数** / 最近一次状态与时间。

        `reasons` 是 0.8.0 加的那一维：`{"cloudflare_challenge": 3, "no_usable_metadata": 41}`。
        它把"这个源最近一直失败"从一句中文 error_summary 变成可分组的事实 ——
        `parse_error` 连着涨 = 站点改版，`cloudflare_challenge` 连着涨 = 被拦，
        `no_usable_metadata` 连着涨 = 站点确实没收录（换源，不是修解析器）。

        `skipped`（P1-3）单列且**不算失败**：那是"我们没试"（源被关掉 / 在冷却里 / dry-run），
        与"试了没拿到"是两件事；把它算进 `fail` 会让自检表的失败数天天虚高。
        """
        rows = self._exec(
            "SELECT source_name, COUNT(*), "
            "SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END), AVG(latency_ms) "
            "FROM scrape_log GROUP BY source_name ORDER BY source_name",
            fetch=True,
        ) or []
        out: List[Dict[str, Any]] = []
        for source, total, ok, skipped, avg in rows:
            last = self._exec(
                "SELECT status, error_summary, created_at, reason FROM scrape_log "
                "WHERE source_name=? ORDER BY id DESC LIMIT 1",
                (source,), fetch=True,
            ) or [("", "", "", "")]
            count = _to_int(total)
            good = _to_int(ok)
            idle = _to_int(skipped)
            reason_rows = self._exec(
                "SELECT reason, COUNT(*) FROM scrape_log WHERE source_name=? AND reason<>'' "
                "GROUP BY reason ORDER BY COUNT(*) DESC, reason",
                (source,), fetch=True,
            ) or []
            out.append({
                "source_name": source, "source": source,
                "total": count, "ok": good, "skipped": idle,
                # `fail` 只数"试了没拿到"：跳过的那些（源被关 / 在冷却 / dry-run）不算失败
                "fail": max(count - good - idle, 0),
                "avg_latency_ms": int(_to_float(avg)),
                "last_status": last[0][0] or "", "last_error": last[0][1] or "",
                "last_created_at": last[0][2] or "",
                "last_reason": (last[0][3] if len(last[0]) > 3 else "") or "",
                "reasons": {str(r[0] or ""): _to_int(r[1]) for r in reason_rows if r[0]},
            })
        return out

    # ---------- 逐站快照（0.8.0 / P0-3：只重算不重抓） ----------

    def snapshot_put(self, key: str, site: str, payload: Any, *, status: str = "",
                     run_id: str = "", fetched_at: str = "") -> None:
        """写/覆盖一个源的快照（`PRIMARY KEY(key, site)`：同一部片同一源只留最新一份）。

        `payload` 是该源**可复用的返回形状**（`javtxt_lookup()` 的 dict）——
        不是给人看的摘要（摘要仍在 `meta.raw_json`）。体积上限 64KB：超了就不写（快照是加速器，
        坏了只该"变慢"，不该把库撑爆）。
        """
        name = str(key or "").strip()
        source = str(site or "").strip()
        if not name or not source or not isinstance(payload, (dict, list)):
            return
        text = _json_text(payload, "{}")
        if len(text) > _SNAPSHOT_LIMIT:
            return
        self._exec(
            "INSERT INTO site_snapshot(key, site, fetched_at, status, run_id, payload_json) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(key, site) DO UPDATE SET "
            "fetched_at=excluded.fetched_at, status=excluded.status, run_id=excluded.run_id, "
            "payload_json=excluded.payload_json",
            (name, source, str(fetched_at or "") or _now(), str(status or ""),
             str(run_id or ""), text),
        )

    def snapshot_get(self, key: str, site: str) -> Optional[Dict[str, Any]]:
        """取一个源的快照（`{site, fetched_at, status, run_id, payload}`）；没有回 `None`。"""
        rows = self._exec(
            "SELECT fetched_at, status, run_id, payload_json FROM site_snapshot "
            "WHERE key=? AND site=?", (str(key or ""), str(site or "")), fetch=True,
        ) or []
        if not rows:
            return None
        return {"site": str(site or ""), "fetched_at": rows[0][0] or "",
                "status": rows[0][1] or "", "run_id": rows[0][2] or "",
                "payload": _json_load(rows[0][3], {})}

    def snapshot_map(self, key: str) -> Dict[str, Dict[str, Any]]:
        """一次取回某部片的**全部**源快照：`{site: {fetched_at, status, run_id, payload}}`。"""
        rows = self._exec(
            "SELECT site, fetched_at, status, run_id, payload_json FROM site_snapshot "
            "WHERE key=?", (str(key or ""),), fetch=True,
        ) or []
        return {str(r[0] or ""): {"site": str(r[0] or ""), "fetched_at": r[1] or "",
                                  "status": r[2] or "", "run_id": r[3] or "",
                                  "payload": _json_load(r[4], {})} for r in rows}

    def snapshot_prune(self, days: int = 30) -> int:
        """删掉 `fetched_at` 早于 `days` 天的快照（**必须有淘汰**：否则它按库的增长一直涨）。

        返回删除条数。`days<=0` 不删（防手滑把整表清空）。
        """
        span = _to_int(days)
        if span <= 0:
            return 0
        cutoff = _shift_days(-span)
        before = self._exec("SELECT COUNT(*) FROM site_snapshot WHERE fetched_at < ?",
                            (cutoff,), fetch=True) or [(0,)]
        self._exec("DELETE FROM site_snapshot WHERE fetched_at <> '' AND fetched_at < ?",
                   (cutoff,))
        return _to_int(before[0][0])

    def snapshot_stats(self) -> Dict[str, int]:
        """快照表概况（设置台的「运行与缓存」会读它）。"""
        rows = self._exec("SELECT COUNT(*), COUNT(DISTINCT key) FROM site_snapshot",
                          fetch=True) or [(0, 0)]
        return {"rows": _to_int(rows[0][0]), "keys": _to_int(rows[0][1])}

    # ---------- 演员名对齐（收藏 / 订阅匹配用） ----------

    def resolve_actor_keys(self, name: str) -> List[str]:
        """把一位演员的**一个写法**展开成全部候选写法（第一名是传进来的那个写法）。

        **谁在用**：收藏夹（`actor_fav`）与女优订阅（`sub` 表里 `type='actor'` 的行）在比对
        作品演员名之前，先拿这个函数把名字展开 —— 收藏/订阅存的是用户当时看到的名字
        （日文原名、汉化后的中文名、或他手工设的备注），而站点返回的演员名是另一套写法；
        汉化前后、上线前后都必须 100% 命得中，靠的就是候选集合够全。
        （线上 `sub` 表当前 0 行，但这条例外不改变口径：订阅名走同一个函数。）

        候选来源（按发现顺序）：
          1. 传进来的名字本身；
          2. `actor_alias` 备注（含反向：传进来的就是备注时，回它的原名）；
          3. `actor_fav.zh` 中文名（含反向）；
          4. `name_map` 命中行里的 `zh_cn` / `zh_tw` / `jp` / canonical_id 尾段，
             以及 `keywords_norm` 里的**每个别名 token**（罗马音就存在那里，如 `,mikamiyua,`）。
        逐层展开到收敛（最多 4 层，`visited` 防环）：备注 → 收藏中文名 → 映射里的日文名/罗马音，
        这条链要一路走到底 —— 只展开固定一两轮的话，最后一层发现的写法会被丢掉。
        认不出来的名字就只回它自己。
        """
        start = str(name or "").strip()
        if not start:
            return []
        out: List[str] = []
        seen: set = set()
        pending: List[str] = [start]
        depth = 0
        while pending and depth < 4:
            nxt: List[str] = []
            for item in pending:
                if not item or item in seen:
                    continue
                seen.add(item)
                out.append(item)
                nxt.extend(self._actor_related(item))
            pending = nxt
            depth += 1
        return out

    def _actor_related(self, name: str) -> List[str]:
        """一个名字的一跳邻居（`resolve_actor_keys` 用；不递归）。"""
        found: List[str] = []

        def add(value: Any) -> None:
            text = str(value or "").strip()
            if text and text != name and text not in found:
                found.append(text)

        rows = self._exec(
            "SELECT name, alias FROM actor_alias WHERE name=? OR alias=?", (name, name), fetch=True
        ) or []
        for raw_name, alias in rows:
            add(raw_name)
            add(alias)
        rows = self._exec(
            "SELECT name, zh FROM actor_fav WHERE name=? OR zh=?", (name, name), fetch=True
        ) or []
        for raw_name, zh in rows:
            add(raw_name)
            add(zh)
        conn = self._connect()
        for row in self._namemap_rows_for(conn, "actor", [name]):
            add(row.get("zh_cn"))
            add(row.get("zh_tw"))
            add(row.get("jp"))
            head, _, tail = str(row.get("canonical_id") or "").partition(":")
            if head == "actor":
                add(tail)
            for token in row.get("keywords") or []:
                add(token)
        return found

    # ---------- 演员主体表（actor / actor_queue，0.9.0 演员线） ----------

    @staticmethod
    def _actor_current(conn: sqlite3.Connection, actor_id: Any) -> Optional[Dict[str, Any]]:
        """在**已持锁**的同一事务里读一行 actor（`actor_set_*` / `actor_mark_*` 的前置读）。

        为什么不走 `actor_get()`：那边每次自己 `_connect()` 读一遍，读与随后的写之间没有
        任何保证；这里要的是"读到的就是马上要被改的那一行"，所以用调用方那条连接、在它的锁里读。
        """
        key = _to_int(actor_id)
        if key <= 0:
            return None
        rows = conn.execute(f"SELECT {_ACTOR_SELECT} FROM actor WHERE id=?", (key,)).fetchall()
        return _actor_row(rows[0]) if rows else None

    def actor_upsert(self, row: Dict[str, Any]) -> int:
        """按 `person` 幂等 upsert 一位演员，返回 `actor.id`（person 为空回 0、不入库）。

        为什么「只覆盖非空字段」：这一条 upsert 是三路的合流点 —— 影片刮完的 `actors_json`
        回填、namemap 补三语名、任务侧补 javdb id。每路只带自己这次真拿到的那几个字段，
        整行覆盖会让"这一轮没查到日文名"把上一轮查到的抹成空串（与 `meta_upsert()` 同一条口径）。

        为什么状态列**不在可写集合**里（`images_json` / `field_sources_json` /
        `locked_fields_json` / `last_scraped_at` / `retry_count` / `next_retry`）：
        头像是 `actor_set_images()` 的职责、退避是 `actor_mark_*` 的职责。让 upsert 也能写它们，
        任何一次"顺手登记"都会把手工锁和退避计数冲掉 —— 那正是本任务要防的事故。

        `locked_fields_json` 里点名的资料字段（name/zh/jp/gender/aliases/javdb id）在 upsert
        路径上同样跳过：手工锁优先于任何来源。`aliases` 这个入参名是给调用方的糖
        （列名是 `aliases_json`，让人传 JSON 后缀很奇怪）。
        """
        person = str((row or {}).get("person") or "").strip()
        if not person:
            return 0
        picked: Dict[str, Any] = {}
        for name, value in (row or {}).items():
            column = "aliases_json" if str(name) == "aliases" else str(name)
            if column not in _ACTOR_UPSERT_FIELDS or column == "person":
                continue
            conv = _actor_value(column, value)
            if _actor_blank(column, conv):
                continue
            picked[column] = conv
        now = _now()
        actor_id = 0
        with self._lock:
            conn = self._connect()
            try:
                hit = conn.execute("SELECT id, locked_fields_json FROM actor WHERE person=?",
                                   (person,)).fetchone()
                if hit is None:
                    values: Dict[str, Any] = dict(_ACTOR_DEFAULTS)
                    values.update(picked)
                    values["person"] = person
                    values["updated_at"] = now
                    cols = [c for c in _ACTOR_COLUMNS if c != "id"]
                    cur = conn.execute(
                        f"INSERT INTO actor({', '.join(cols)}) "
                        f"VALUES({', '.join('?' * len(cols))})",
                        tuple(values.get(c) for c in cols),
                    )
                    actor_id = _to_int(cur.lastrowid)
                else:
                    actor_id = _to_int(hit[0])
                    locked = {str(f) for f in (_json_load(hit[1], []) or [])}
                    sets = [c for c in picked if c not in locked]
                    if sets:
                        conn.execute(
                            "UPDATE actor SET " + ", ".join(f"{c}=?" for c in sets)
                            + ", updated_at=? WHERE id=?",
                            (*(picked[c] for c in sets), now, actor_id),
                        )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        return actor_id

    def actor_get(self, actor_id: int = 0, person: str = "") -> Optional[Dict[str, Any]]:
        """按 id 或 Emby 规范名取一位演员（id 优先）；没有回 None。

        两个入口都要，是因为上下游手里是两套标识：端点与任务拿 `actor.id`，而影片刮削链
        只有 `person_from_actor()` 算出的规范名（D15 的唯一精确键，Emby 按 `Name` 精确建人）。
        """
        key = _to_int(actor_id)
        if key > 0:
            rows = self._exec(f"SELECT {_ACTOR_SELECT} FROM actor WHERE id=?",
                              (key,), fetch=True) or []
        else:
            name = str(person or "").strip()
            if not name:
                return None
            rows = self._exec(f"SELECT {_ACTOR_SELECT} FROM actor WHERE person=?",
                              (name,), fetch=True) or []
        return _actor_row(rows[0]) if rows else None

    def actor_list(self, q: str = "", flt: str = "", limit: int = 60,
                   offset: int = 0) -> Dict[str, Any]:
        """演员卡片墙的一页：名称模糊查 + 四种筛选，返回 `{"items": [...], "total": n}`。

        为什么 `total` 必须和 `items` 一起给：卡片墙是分页的（`limit/offset`），前端要显示
        "共 N 位"，而 N 只能由**同一个 WHERE** 算出来 —— 两边分开写迟早对不上。

        `flt` 的四个口径与 `actor_stats()` 的计数逐字一致（点数字就跳到对应筛选）：
        `missing_avatar` = 还没有任何候选图（`images_json` 是 `''` 或 `'[]'`，两者都算）；
        `locked` = 有任意手工锁；`failed` = `retry_count > 0`（退避中或已退避到顶）。
        认不出的筛选只 warning 并忽略 —— 绝不把调用方给的片段拼进 SQL（P1-9 的注入面教训）。
        """
        clause: List[str] = []
        args: List[Any] = []
        text = str(q or "").strip()
        if text:
            like = f"%{_like_escape(text)}%"
            clause.append("(person LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\' "
                          "OR zh LIKE ? ESCAPE '\\' OR jp LIKE ? ESCAPE '\\' "
                          "OR aliases_json LIKE ? ESCAPE '\\')")
            args.extend([like] * 5)
        kind = str(flt or "").strip()
        if kind == "missing_avatar":
            clause.append("(images_json IS NULL OR images_json IN ('', '[]'))")
        elif kind == "locked":
            clause.append("(locked_fields_json IS NOT NULL "
                          "AND locked_fields_json NOT IN ('', '[]'))")
        elif kind == "failed":
            clause.append("retry_count > 0")
        elif kind:
            logger.warning(f"AVHelper actor_list(filter=…) 认不出的筛选（已忽略）：{kind[:40]}")
        where = (" WHERE " + " AND ".join(clause)) if clause else ""
        total_rows = self._exec(f"SELECT COUNT(*) FROM actor{where}", tuple(args), fetch=True) or [(0,)]
        sql = f"SELECT {_ACTOR_SELECT} FROM actor{where} ORDER BY updated_at DESC, id ASC"
        size = _to_int(limit)
        skip = _to_int(offset)
        if size > 0:
            sql += " LIMIT ?"
            args.append(size)
        if skip > 0:
            sql += (" OFFSET ?" if size > 0 else " LIMIT -1 OFFSET ?")
            args.append(skip)
        rows = self._exec(sql, tuple(args), fetch=True) or []
        return {"items": [_actor_row(r) for r in rows], "total": _to_int(total_rows[0][0])}

    def actor_set_images(self, actor_id: int, images: List[Dict[str, Any]],
                         field_sources: Dict[str, Any] = None) -> Dict[str, Any]:
        """写候选头像（`images[0]` 就是主图），返回写后的整行；行不存在回 `{}`。

        **锁了 `images` 就原样返回、一个字都不写**：手工裁剪/上传的图被下一次重刮覆盖是
        最难发现的事故（用户眼里"昨天还是对的图"），锁是唯一防线（方案 §5.6）。
        只收带 `url` 的条目：`images_json` 每一项都是"图从哪来、多大"，没有 url 的项下游
        下载必然失败，宁可在写入口就丢掉，也不要留给执行器去猜。
        `field_sources` 是**合并**不是替换：主图来源只是溯源里的一格，替换会把资料侧
        （`zh`/`jp` 是谁给的）整段抹掉。
        """
        key = _to_int(actor_id)
        if key <= 0:
            return {}
        picked = [dict(item) for item in (images if isinstance(images, list) else [])
                  if isinstance(item, dict) and str(item.get("url") or "").strip()]
        sources = {str(k): v for k, v in (field_sources or {}).items() if str(k).strip()}
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                current = self._actor_current(conn, key)
                if current is None:
                    return {}
                if "images" in {str(f) for f in (current.get("locked_fields") or [])}:
                    return current
                merged = dict(current.get("field_sources") or {})
                merged.update(sources)
                conn.execute(
                    "UPDATE actor SET images_json=?, field_sources_json=?, updated_at=? "
                    "WHERE id=?",
                    (_json_text(picked, "[]"), _json_text(merged, "{}"), now, key),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            return self._actor_current(conn, key) or {}

    def actor_set_profile(self, actor_id: int, fields: Dict[str, Any],
                          field_sources: Dict[str, Any] = None) -> Dict[str, Any]:
        """合并资料字段（name/zh/jp/gender/aliases/javdb_actor_id），返回写后的整行。

        与 `actor_upsert()` 的分工：upsert 认 `person`（顺手建行），这里认 `id`（行必须已存在）
        —— 任务侧手里是 `actor.id`，不该被迫再拼一遍 person 去撞唯一键。
        两条口径与 upsert 共用：**空值不写**（"这一轮没查到日文名"不是"日文名没了"）、
        **锁住的字段跳过**（锁是逐字段的，锁了 `zh` 不该连 `jp` 一起停更）。
        """
        key = _to_int(actor_id)
        if key <= 0:
            return {}
        picked: Dict[str, Any] = {}
        for name, value in (fields or {}).items():
            column = "aliases_json" if str(name) == "aliases" else str(name)
            if column not in _ACTOR_PROFILE_FIELDS:
                continue
            conv = _actor_value(column, value)
            if _actor_blank(column, conv):
                continue
            picked[column] = conv
        sources = {str(k): v for k, v in (field_sources or {}).items() if str(k).strip()}
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                current = self._actor_current(conn, key)
                if current is None:
                    return {}
                locked = {str(f) for f in (current.get("locked_fields") or [])}
                sets = [c for c in picked if c not in locked]
                values: List[Any] = [picked[c] for c in sets]
                if sources:
                    merged = dict(current.get("field_sources") or {})
                    merged.update(sources)
                    sets.append("field_sources_json")
                    values.append(_json_text(merged, "{}"))
                if not sets:
                    return current
                conn.execute(
                    "UPDATE actor SET " + ", ".join(f"{c}=?" for c in sets)
                    + ", updated_at=? WHERE id=?",
                    (*values, now, key),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            return self._actor_current(conn, key) or {}

    def actor_mark_ok(self, actor_id: int, when: str = "") -> Dict[str, Any]:
        """记一次抓取成功：`retry_count` 归零、退避清空、`last_scraped_at` 落到 `when`（缺省现在）。

        成功必须把 `retry_count` 清零：偶发失败留下的计数不清，这位演员此后只要再连败两次
        就直接吃到 72h 那一档 —— 退避序列被人为拉长了。`when` 让调用方补记"任务真正跑完
        的时刻"（而不是落库时刻），批量任务里这两者能差几分钟。
        """
        key = _to_int(actor_id)
        if key <= 0:
            return {}
        stamp = str(when or "").strip() or _now()
        with self._lock:
            conn = self._connect()
            try:
                if self._actor_current(conn, key) is None:
                    return {}
                conn.execute(
                    "UPDATE actor SET retry_count=0, next_retry='', last_scraped_at=?, "
                    "updated_at=? WHERE id=?", (stamp, _now(), key),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            return self._actor_current(conn, key) or {}

    def actor_mark_failed(self, actor_id: int, reason: str = "") -> Dict[str, Any]:
        """记一次失败：`retry_count += 1`，`next_retry` 按 `BACKOFF_HOURS` 排下一档。

        序列是 6h → 24h → 72h → 7d → 14d；跑完第 5 档 `next_retry` **留空**（到顶后自动重试
        是纯空转，方案 §4 定的是只等手动），但 `retry_count` 继续加 —— 界面要靠它区分
        "失败过一次"与"已经放弃自动重试"。
        `reason` 只进日志、不落表：`actor` 没有"失败原因"列，明细该进 `scrape_log`
        （`source_name='actor'`）；塞进 `field_sources_json` 会污染溯源列的语义。
        """
        key = _to_int(actor_id)
        if key <= 0:
            return {}
        with self._lock:
            conn = self._connect()
            try:
                current = self._actor_current(conn, key)
                if current is None:
                    return {}
                count = _to_int(current.get("retry_count")) + 1
                next_retry = ("" if count > len(BACKOFF_HOURS)
                              else _shift_hours(BACKOFF_HOURS[count - 1]))
                conn.execute(
                    "UPDATE actor SET retry_count=?, next_retry=?, updated_at=? WHERE id=?",
                    (count, next_retry, _now(), key),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            logger.warning(f"AVHelper 演员抓取失败（第 {count} 次，下次 {next_retry or '不排期'}）"
                           f" actor#{key}：{str(reason or '无原因')[:200]}")
            return self._actor_current(conn, key) or {}

    def actor_lock(self, actor_id: int, field: str = "images", on: bool = True) -> Dict[str, Any]:
        """加/解一个字段的手工锁，返回写后的整行；行不存在回 `{}`。

        锁落成 JSON 数组而不是每字段一个布尔列：字段还会长（生日/身高在 P2），加一个字符串
        比加一列省一次迁移；**去重保序**让重复加锁/重复解锁天然幂等（不会长出两份，
        也不会把释放顺序搞乱）。空 `field` 直接忽略 —— 空串锁等于锁了个不存在的东西。
        已经是目标状态时不写库（连 `updated_at` 都不动）：反复点同一个按钮不该让卡片墙重排。
        """
        key = _to_int(actor_id)
        name = str(field or "").strip()
        if key <= 0:
            return {}
        if not name:
            return self.actor_get(key) or {}
        with self._lock:
            conn = self._connect()
            try:
                current = self._actor_current(conn, key)
                if current is None:
                    return {}
                locked = [str(f) for f in (current.get("locked_fields") or []) if str(f).strip()]
                if on and name not in locked:
                    locked.append(name)
                elif not on and name in locked:
                    locked = [f for f in locked if f != name]
                else:
                    return current
                conn.execute(
                    "UPDATE actor SET locked_fields_json=?, updated_at=? WHERE id=?",
                    (_json_text(locked, "[]"), _now(), key),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
            return self._actor_current(conn, key) or {}

    def actor_due(self, limit: int = 20) -> List[Dict[str, Any]]:
        """这一轮该抓的演员：`next_retry` 为空（从没失败/已退避到顶）或已到点，最老的排前。

        排序按 `last_scraped_at` 升序（空串最优先 = 从没抓过的排最前），与 `meta_due()` 的
        tier2 同一套"饥饿兜底"口径：没有排序的队列会让同一批老面孔每轮都占满名额，
        新演员永远轮不到。
        `limit<=0` 按默认 20 —— 队列函数不给"全取"的口子（一轮的请求量必须可控）。
        WHERE 写成 `IS NULL / = '' / <=` 而不是 `IFNULL(next_retry,'') = ''`：函数包住列会让
        `idx_actor_next_retry` 失效（P1-9 的同一条教训），语义完全一样。
        """
        size = _to_int(limit) or 20
        rows = self._exec(
            f"SELECT {_ACTOR_SELECT} FROM actor "
            "WHERE next_retry IS NULL OR next_retry = '' OR next_retry <= ? "
            "ORDER BY last_scraped_at ASC, id ASC LIMIT ?",
            (_now(), size), fetch=True,
        ) or []
        return [_actor_row(r) for r in rows]

    def actor_queue_push(self, persons: List[str]) -> int:
        """登记一批待刮演员，返回**本次新入队**的条数（已在队列里的不计）。

        为什么要**自举**：影片刮完那一刻，`scraper.scrape_one()` 手里只有
        `person_from_actor()` 算出的规范名，而存量回填可能还没跑过、actor 表里根本没有这一行。
        所以对不认识的 person 先落一条最小行（`person` + `name`=person，其余留空、
        `gender` 为 NULL）再入队 —— 否则新片的新演员永远进不了队列，
        而"演员表覆盖全库"正是这条子系统的目的。

        幂等靠主键：`actor_queue.actor_id` 是 PK，插入用 `INSERT OR IGNORE`；已存在
        （含已取走的 `taken`）不重排 —— 重刮节奏归 `actor_due()` 的退避管，重复入队会把
        "正在跑"的行重新排一遍，返回的计数也就没意义了。空串与重复入参就地丢掉。
        """
        wanted: List[str] = []
        for item in (persons or []):
            name = str(item or "").strip()
            if name and name not in wanted:
                wanted.append(name)
        if not wanted:
            return 0
        now = _now()
        added = 0
        with self._lock:
            conn = self._connect()
            try:
                for person in wanted:
                    hit = conn.execute("SELECT id FROM actor WHERE person=?", (person,)).fetchone()
                    if hit is None:
                        cur = conn.execute(
                            "INSERT INTO actor(person, name, updated_at) VALUES(?,?,?)",
                            (person, person, now),
                        )
                        actor_id = _to_int(cur.lastrowid)
                    else:
                        actor_id = _to_int(hit[0])
                    if actor_id <= 0:
                        continue
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO actor_queue(actor_id, person, state, created_at) "
                        "VALUES(?,?,'wait',?)", (actor_id, person, now),
                    )
                    added += int(cur.rowcount or 0)
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        return added

    def actor_queue_pop(self, limit: int = 20) -> List[Dict[str, Any]]:
        """领取一批待刮演员，返回**actor 行**（不是队列行），并就地标成 `taken`。

        为什么返回 actor 行：调用方拿到队列行还得再查一次表，而两次读之间那行可能已经变了；
        它真正需要的是 person / 图 / 锁 / 退避这些字段。
        为什么取与标必须在**同一事务**里：先取后标若失败，这批行会一直停在 `wait`，
        下一轮被重复领取 —— 重复领不致命（演员任务单飞），但计数与日志会一路虚高。
        队列里指向已删演员的孤儿行照旧标 taken 并跳过：留着它们等于每轮都白领一次。
        """
        size = _to_int(limit) or 20
        now = _now()
        found: List[Any] = []
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT actor_id FROM actor_queue WHERE state='wait' "
                    "ORDER BY created_at ASC, actor_id ASC LIMIT ?", (size,),
                ).fetchall()
                ids = [_to_int(r[0]) for r in rows if _to_int(r[0]) > 0]
                if not ids:
                    conn.commit()
                    return []
                conn.execute(
                    "UPDATE actor_queue SET state='taken', taken_at=? "
                    f"WHERE actor_id IN ({', '.join('?' * len(ids))})", (now, *ids),
                )
                found = conn.execute(
                    f"SELECT {_ACTOR_SELECT} FROM actor "
                    f"WHERE id IN ({', '.join('?' * len(ids))})", tuple(ids),
                ).fetchall()
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        by_id: Dict[int, Dict[str, Any]] = {}
        for row in found:
            item = _actor_row(row)
            by_id[item["id"]] = item
        return [by_id[key] for key in ids if key in by_id]

    def actor_backfill(self, actors: Any = None, namemap_mod: Any = None) -> Dict[str, Any]:
        """一次性回填存量演员（`meta.actors_json` 聚合 → actor 行），返回
        `{"created", "updated", "total", "skipped"}`。

        为什么只做一次（标记在 `schema_meta['actor_backfill_done']`，**与 schema 版本分开的两行**）：
        这是给存量库补历史的动作，全表扫一遍在 NAS 上要几秒；每次插件加载都跑纯属浪费。
        回填之后的新演员由 `actor_queue_push()` 自举（影片刮完就落行），所以关掉它不会漏人。
        幂等的第二道保险在 `actor_upsert()`：即便标记被清掉再跑一遍，按 `person` 合并也只会
        更新、不会长出重复行（那时 `created` 为 0，`updated` 是本轮仍碰到的存量行数）。

        `actors` 缺省时自取 `meta_list()` 的 `actors`（老行只有 `actors_json` 串）；
        `namemap_mod` 缺省时**延迟导入** namemap —— 单测能塞假映射，不必真加载 5351 条资源。
        `gender` 取**第一个非空值**：同一演员散落在多部片里，javdb 只在部分行给了 gender。
        """
        with self._lock:
            conn = self._connect()
            try:
                hit = conn.execute(
                    "SELECT val FROM schema_meta WHERE key='actor_backfill_done'").fetchone()
            except sqlite3.OperationalError:
                hit = None
        if hit and str(hit[0] or "").strip() == "1":
            return {"created": 0, "updated": 0, "total": 0, "skipped": True}

        raw_rows: List[Any] = []
        if actors is None:
            for item in self.meta_list():
                raw = item.get("actors")
                if not isinstance(raw, list):
                    raw = _json_load(item.get("actors_json"), [])
                raw_rows.extend(raw)
        elif isinstance(actors, (list, tuple)):
            raw_rows = list(actors)
        else:
            raw_rows = [actors]

        slots: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for item in raw_rows:
            if isinstance(item, str):
                entry: Dict[str, Any] = {"person": item, "name": item}
            elif isinstance(item, dict):
                entry = item
            else:
                continue
            person = str(entry.get("person") or entry.get("name") or "").strip()
            if not person:
                continue
            slot = slots.get(person)
            if slot is None:
                slot = {"person": person, "name": "", "zh": "", "jp": "",
                        "gender": None, "javdb_actor_id": "", "aliases": []}
                slots[person] = slot
                order.append(person)
            for field in ("name", "zh", "jp", "javdb_actor_id"):
                if not slot[field]:
                    slot[field] = str(entry.get(field) or "").strip()
            gender = entry.get("gender")
            if slot["gender"] is None and gender is not None and str(gender).strip() != "":
                slot["gender"] = _to_int(gender)
            for alias in (entry.get("aliases") or []):
                text = str(alias or "").strip()
                if text and text not in slot["aliases"]:
                    slot["aliases"].append(text)

        module = namemap_mod
        if module is None:
            try:
                from . import namemap as module        # noqa: F401 - 延迟导入：避免与 S3 互相拖死
            except Exception as error:                 # noqa: BLE001 - 映射缺了只是少一层，不该中断回填
                logger.warning(f"AVHelper 回填取不到 namemap（只按 meta 里的记录回填）：{error}")
                module = None
        lookup = getattr(module, "actor_lookup", None) if module is not None else None

        created = updated = 0
        for person in order:
            slot = slots[person]
            record: Dict[str, Any] = {}
            if callable(lookup):
                try:
                    hit_record = lookup(person)
                except Exception as error:             # noqa: BLE001 - 单条映射坏掉不中断整批
                    logger.warning(f"AVHelper 回填查映射失败（{person}）：{error}")
                    hit_record = None
                if isinstance(hit_record, dict):
                    record = hit_record
            zh = slot["zh"] or str(record.get("zh_cn") or record.get("zh") or "").strip()
            jp = slot["jp"] or str(record.get("jp") or "").strip()
            javdb_id = slot["javdb_actor_id"] or str(record.get("javdb_actor_id") or "").strip()
            aliases = list(slot["aliases"])
            for candidate in list(record.get("aliases") or []) + [zh, jp]:
                text = str(candidate or "").strip()
                if text and text != person and text not in aliases:
                    aliases.append(text)
            existed = self.actor_get(person=person) is not None
            if not self.actor_upsert({"person": person, "name": slot["name"], "zh": zh, "jp": jp,
                                      "gender": slot["gender"], "javdb_actor_id": javdb_id,
                                      "aliases": aliases}):
                continue
            if existed:
                updated += 1
            else:
                created += 1

        total = created + updated
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("INSERT OR REPLACE INTO schema_meta(key, val) "
                             "VALUES('actor_backfill_done', '1')")
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
                raise
        logger.info(f"AVHelper 演员回填完成：新增 {created} / 合并 {updated}")
        return {"created": created, "updated": updated, "total": total, "skipped": False}

    def actor_stats(self) -> Dict[str, Any]:
        """演员表计数（设置台「演员」栏与 `GET /actor/stats`）：total / missing_avatar / locked /
        failed / due。

        `failed` 与 `due` 是两件事，都留着：`failed` 是"失败过"（含已退避到顶、只等手动），
        `due` 是"这一轮会被领走"的（`next_retry` 空或到点）—— 前者给用户看问题，后者给任务
        看余量。计数口径与 `actor_list(filter=…)` 逐字一致，界面上点数字就能跳到那张表。
        """
        rows = self._exec(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN images_json IS NULL OR images_json IN ('', '[]') THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN locked_fields_json IS NOT NULL "
            "AND locked_fields_json NOT IN ('', '[]') THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN next_retry IS NULL OR next_retry = '' OR next_retry <= ? "
            "THEN 1 ELSE 0 END) FROM actor",
            (_now(),), fetch=True,
        ) or [(0, 0, 0, 0, 0)]
        row = rows[0]
        return {
            "total": _to_int(row[0]),
            "missing_avatar": _to_int(row[1]),
            "locked": _to_int(row[2]),
            "failed": _to_int(row[3]),
            "due": _to_int(row[4]),
        }

