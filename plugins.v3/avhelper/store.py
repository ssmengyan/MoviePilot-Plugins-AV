"""插件自管 SQLite 存储：收藏演员 / 订阅 / 已知番号 / 搜索任务 / 通知 / 缓存索引 / 下载台账，
以及 v4 刮削层的五张表（作品元数据 · 媒体实例 · 三语映射 · 翻译缓存 · 数据源自检日志）。

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
from typing import Any, Callable, Dict, List, Optional


from . import paths


def _norm_key(text: Any) -> str:
    """番号归一化：借用 `emby.norm_key()`，延迟导入以便本模块在无宿主环境下被单测直接加载。

    台账的 key 与番号归一化必须共用同一份规则（`emby.norm_key`）：同一个番号在 javdb 番号、
    Emby 文件名、MetaTube 刮削 id 里写法不同，两边各写一份迟早会漂。`emby.py` 依赖 `app.sdk`，
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
  pending TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS notice(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, title TEXT, type TEXT,
  body TEXT, meta TEXT, image TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS cache_idx(
  key TEXT PRIMARY KEY, path TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS kv(
  key TEXT PRIMARY KEY, val TEXT, expires_at TEXT);
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
CREATE INDEX IF NOT EXISTS idx_downloads_completed ON downloads(completed_at DESC, created_at DESC);
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
    updated_at TEXT DEFAULT ''
);

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
CREATE INDEX IF NOT EXISTS idx_media_item_key ON media_item(key);
CREATE INDEX IF NOT EXISTS idx_media_item_emby ON media_item(emby_id);

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
    created_at TEXT DEFAULT ''
);
"""

# 老库动态补列（SQLite 的 ALTER TABLE ADD COLUMN 没有 IF NOT EXISTS，先看 PRAGMA table_info 再补）。
# `hidden` 是 0.3.4 加的墓碑列，后三条是 v4 刮削线加的，声明与 `_SCHEMA` 里的逐字一致。
_DL_ADD_COLUMNS = (
    ("hidden", "INTEGER DEFAULT 0"),
    ("version_tags", "TEXT DEFAULT '{}'"),
    ("emby_id", "TEXT DEFAULT ''"),
    ("failed_reason", "TEXT DEFAULT ''"),
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
    "last_scraped_at", "updated_at",
)
# 可写字段：主键与 updated_at 不能从外面传（updated_at 由 meta_upsert 自己写）
_META_FIELDS = frozenset(_META_COLUMNS) - {"key", "updated_at"}
_META_DEFAULTS: Dict[str, Any] = {
    "display_number": "", "javdb_id": "", "title_jp": "", "title_zh": "", "plot_jp": "",
    "plot_zh": "", "translation_status": "untranslated", "actors_json": "[]", "tags_json": "[]",
    "studio": "", "series": "", "director": "", "release_date": "", "runtime_min": 0, "rating": 0,
    "cover_raw_url": "", "samples_json": "[]", "trailer_url": "", "raw_json": "{}",
    "completeness": "missing_core", "retry_count": 0, "next_retry_at": "", "last_scraped_at": "",
}
_META_JSON_FIELDS = {"actors_json": "[]", "tags_json": "[]", "samples_json": "[]", "raw_json": "{}"}
_META_INT_FIELDS = frozenset({"runtime_min", "retry_count"})
_META_FLOAT_FIELDS = frozenset({"rating"})
_META_SELECT = ", ".join(_META_COLUMNS)

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
        conn.execute("PRAGMA busy_timeout=10000")
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
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._bootstrap(conn)
            # v4.1 §4.2 末条：用户手工备注（actor_alias）同步进 name_map，且拥有最高优先级
            self._sync_aliases(conn)
            conn.commit()

    def _bootstrap(self, conn: sqlite3.Connection) -> None:
        """建表 + 老库补列（幂等）。`init()` 与「库文件被换成空库」两条路径都走这里。"""
        conn.executescript(_SCHEMA)
        conn.executescript(_SCHEMA_SCRAPE_V4)
        # 兼容旧库：rule/source 是后加的列，缺失时补上（SQLite 无 IF NOT EXISTS 语法）
        try:
            conn.execute("ALTER TABLE task ADD COLUMN rule TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE task ADD COLUMN source TEXT DEFAULT 'manual'")
        except sqlite3.OperationalError:
            pass
        # 兼容旧库：pending 是 0.6.0 后加的列（任务卡上的
        # 「PT/BT 待确认」/「所有源均未找到」标记，口径见 tasks.rule_verdict）。
        # 老任务读出来是空串 = 普通待确认，界面不画标记。
        task_cols = {r[1] for r in conn.execute("PRAGMA table_info(task)").fetchall()}
        if "pending" not in task_cols:
            try:
                conn.execute("ALTER TABLE task ADD COLUMN pending TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        # 兼容旧库：downloads 的后加列（hidden 是 0.3.4 的墓碑列，v4 又加三条）。
        # 先看列在不在再 ALTER，绝不 DROP 重建——用户的台账不能丢。
        cols = {r[1] for r in conn.execute("PRAGMA table_info(downloads)").fetchall()}
        for name, decl in _DL_ADD_COLUMNS:
            if name in cols:
                continue
            try:
                conn.execute(f"ALTER TABLE downloads ADD COLUMN {name} {decl}")
            except sqlite3.OperationalError:
                pass

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
        if _is_read_sql(sql):
            cur = conn.execute(sql, args)
            return cur.fetchall() if fetch else None
        with self._lock:
            try:
                cur = conn.execute(sql, args)
                rows = cur.fetchall() if fetch else None
                conn.commit()
                return rows
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

    def task_set_state(self, tid: str, state: str) -> None:
        """更新任务状态（await/pushed）。"""
        self._exec("UPDATE task SET state=? WHERE id=?", (state, tid))

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

    def meta_list(self, limit: int = 0, offset: int = 0, where: str = "") -> List[Dict[str, Any]]:
        """列元数据（新改的在前）。

        `limit<=0` = 不限条数；`where` 是**原始 SQL 片段**（拼在 WHERE 后面），只给内部调用方
        用（`scraper`/`__init__` 拼的都是自己写死的条件，不要往里塞用户输入）。
        """
        sql = f"SELECT {_META_SELECT} FROM meta"
        clause = str(where or "").strip()
        if clause:
            sql += f" WHERE {clause}"
        sql += " ORDER BY updated_at DESC, key ASC"
        args: List[Any] = []
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
            sql = (f"SELECT {_META_SELECT} FROM meta "
                   "WHERE IFNULL(next_retry_at, '') <> '' AND next_retry_at <= ? "
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
        now = _now()
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
        `limit` / `offset` / `order`（原始 SQL 排序片段，如 `"last_synced_at DESC"`）。
        不认识的过滤键**直接忽略**（列名拼错不该把整个读接口炸掉）。
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
        sql = f"SELECT {_ITEM_SELECT} FROM media_item"
        if clause or raw_where:
            sql += " WHERE " + " AND ".join(clause + ([raw_where] if raw_where else []))
        sql += f" ORDER BY {filters.get('order') or 'item_key ASC'}"
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
                       error_summary: str = "") -> None:
        """记一条数据源调用结果（自检页与排障用）。

        `error_summary` 裁到 500 字符：这是给界面看的一句话摘要，不是堆栈仓库；
        表本身顺手裁到最近 `_SCRAPE_LOG_KEEP` 条（同 notice 只留 200 条的思路）。
        """
        self._exec(
            "INSERT INTO scrape_log(source_name, key, status, latency_ms, error_summary, "
            "created_at) VALUES(?,?,?,?,?,?)",
            (str(source_name or ""), str(key or ""), str(status or ""), _to_int(latency_ms),
             str(error_summary or "")[:500], _now()),
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
        """
        size = _to_int(limit) or 50
        sql = ("SELECT id, source_name, key, status, latency_ms, error_summary, created_at "
               "FROM scrape_log")
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
        } for r in rows]

    def scrape_log_summary(self) -> List[Dict[str, Any]]:
        """按数据源汇总：总数 / 成功 / 失败 / 平均耗时 / 最近一次状态与时间。"""
        rows = self._exec(
            "SELECT source_name, COUNT(*), "
            "SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END), AVG(latency_ms) "
            "FROM scrape_log GROUP BY source_name ORDER BY source_name",
            fetch=True,
        ) or []
        out: List[Dict[str, Any]] = []
        for source, total, ok, avg in rows:
            last = self._exec(
                "SELECT status, error_summary, created_at FROM scrape_log "
                "WHERE source_name=? ORDER BY id DESC LIMIT 1",
                (source,), fetch=True,
            ) or [("", "", "")]
            count = _to_int(total)
            good = _to_int(ok)
            out.append({
                "source_name": source, "source": source,
                "total": count, "ok": good, "fail": max(count - good, 0),
                "avg_latency_ms": int(_to_float(avg)),
                "last_status": last[0][0] or "", "last_error": last[0][1] or "",
                "last_created_at": last[0][2] or "",
            })
        return out

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
