"""插件自管 SQLite 存储：收藏演员 / 订阅 / 已知番号 / 搜索任务 / 通知 / 缓存索引 / 下载台账。

数据库落在数据根的 `meta/avhelper.db`（数据根由 `paths` 解析：老部署仍是 `/avhelper/cache`，
新部署落到 MoviePilot 的插件数据目录）。全部方法同步实现，由 FastAPI 的线程池或插件定时任务
调用；连接按调用短生命周期创建，避免跨线程复用。
"""

import json
import re
import sqlite3
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

# 建表语句：与执行方案 §6.3 的表结构一致，另加 notice/kv 两张辅助表
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
  hidden       INTEGER DEFAULT 0   -- 1=用户点过「移除记录」的墓碑：列表不回它，补种也种不回来
);
CREATE INDEX IF NOT EXISTS idx_downloads_completed ON downloads(completed_at DESC, created_at DESC);
"""

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
                      state, source, created_at, completed_at, updated_at, hidden)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
ON CONFLICT(key) DO UPDATE SET
"""

# size 的「空」是 0（台账里 0 表示未知），文本列的「空」是空串；IFNULL 顺手兜住 NULL
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
  hidden       = 0                 -- 用户又下了一遍：之前「移除记录」的墓碑就此解除
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
  hidden       = downloads.hidden  -- 补种绝不解除墓碑：用户删过的记录不能被库里种回来
"""


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


class Store:
    """插件自有数据的唯一入口（线程安全，短连接）。"""

    def __init__(self, db_path: Optional[Path] = None):
        # 默认路径在调用时向 `paths` 取：`paths.configure()` 之后数据根才定型，
        # 写成默认参数会在模块导入那一刻被固化成老路径。
        self.db_path = Path(db_path) if db_path else paths.db_path()
        self._lock = threading.Lock()

    # ---------- 基础 ----------

    def init(self) -> None:
        """建库建表；目录不存在时先创建。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)
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
            # 兼容旧库：hidden 是后加的墓碑列（0.3.4 的「移除记录」要挡得住补种）。
            # 先看列在不在再 ALTER，绝不 DROP 重建——用户的台账不能丢。
            cols = {r[1] for r in conn.execute("PRAGMA table_info(downloads)").fetchall()}
            if "hidden" not in cols:
                try:
                    conn.execute("ALTER TABLE downloads ADD COLUMN hidden INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    pass

    def _exec(self, sql: str, args: tuple = (), fetch: bool = False) -> Any:
        """执行一条语句；fetch=True 时返回全部行。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(sql, args)
            rows = cur.fetchall() if fetch else None
            conn.commit()
            return rows

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
        """写入或更新一位演员的备注；`alias` 为空串 = 清除（删行）。"""
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
        self._exec(
            "INSERT INTO actor_alias(name, alias, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET alias=excluded.alias, updated_at=excluded.updated_at",
            (key, text, _now()),
        )

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
        with self._lock, sqlite3.connect(self.db_path) as conn:
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
    # created_at / completed_at（接口层要前端的驼峰形状，由接口层自己转）。
    # `hidden` 只能通过 `download_delete` 置位（墓碑），不开放给写入方传。

    def download_upsert(self, number: str, **fields: Any) -> None:
        """登记一条下载（插入或就地合并）。番号归一化后做 key。

        合并规则：`number` 非空才覆盖展示番号；空字符串不覆盖已有值；`created_at` 只在首次
        写入时落；每次都写 `updated_at`；`state='downloaded'` 时补 `completed_at`（已有则不动）。
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
        sql = ("SELECT key, number, title, actor, thumb, size, hash, path, downloader, "
               "state, source, created_at, completed_at, updated_at, hidden FROM downloads "
               "WHERE hidden = 0")
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
        with self._lock, sqlite3.connect(self.db_path) as conn:
            exists = conn.execute("SELECT 1 FROM downloads WHERE key=?", (key,)).fetchone() is not None
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
            ))
            conn.commit()
        return not exists

    @staticmethod
    def _download_row(row: Any) -> Dict[str, Any]:
        """一行 → dict（键名就是表列名：这是「台账行」本身，接口层再转前端形状）。

        `hidden` 也照原样给出去：读法已经滤掉墓碑行，这个字段留在行里是给调用方
        （以及测试）确认「墓碑确实解除了」用的，接口层不往外发。
        """
        return {
            "key": row[0], "number": row[1] or "", "title": row[2] or "",
            "actor": row[3] or "", "thumb": row[4] or "", "size": _to_int(row[5]),
            "hash": row[6] or "", "path": row[7] or "", "downloader": row[8] or "",
            "state": row[9] or "downloading", "source": row[10] or "plugin",
            "created_at": row[11] or "", "completed_at": row[12] or "",
            "updated_at": row[13] or "", "hidden": _to_int(row[14]),
        }
