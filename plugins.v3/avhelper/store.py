"""插件自管 SQLite 存储：收藏演员 / 订阅 / 已知番号 / 搜索任务 / 通知 / 缓存索引。

数据库落在缓存盘 `/avhelper/cache/meta/avhelper.db`（对应 NAS 的 /vol3）。全部方法同步实现，
由 FastAPI 的线程池或插件定时任务调用；连接按调用短生命周期创建，避免跨线程复用。
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("/avhelper/cache/meta/avhelper.db")

# 建表语句：与执行方案 §6.3 的表结构一致，另加 notice/kv 两张辅助表
_SCHEMA = """
CREATE TABLE IF NOT EXISTS actor_fav(
  name TEXT PRIMARY KEY, zh TEXT, avatar TEXT, added_at TEXT);
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
  source TEXT DEFAULT 'manual');
CREATE TABLE IF NOT EXISTS notice(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, title TEXT, type TEXT,
  body TEXT, meta TEXT, image TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS cache_idx(
  key TEXT PRIMARY KEY, path TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS kv(
  key TEXT PRIMARY KEY, val TEXT, expires_at TEXT);
"""


def _now() -> str:
    """当前时间字符串，统一写库格式。"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


class Store:
    """插件自有数据的唯一入口（线程安全，短连接）。"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
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
            "SELECT id, number, actor, cands, reason, state, thumb, auto, created_at, rule, source "
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
                "source": r[10] or "manual",
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
            "INSERT OR REPLACE INTO task(id, number, actor, cands, reason, state, thumb, auto, created_at, rule, source) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (task["id"], task["number"], task.get("actor", ""),
             json.dumps(task.get("cands", []), ensure_ascii=False),
             task.get("reason", ""), task.get("state", "await"),
             task.get("thumb", ""), 1 if task.get("auto") else 0, _now(),
             json.dumps(task.get("rule") or {}, ensure_ascii=False),
             str(task.get("source") or "manual")),
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
        """返回通知（新到旧）。"""
        rows = self._exec(
            "SELECT kind, title, type, body, meta, image, created_at FROM notice ORDER BY id DESC",
            fetch=True,
        ) or []
        return [{"kind": r[0], "title": r[1], "type": r[2], "body": r[3],
                 "meta": r[4], "image": r[5], "time": r[6]} for r in rows]

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
