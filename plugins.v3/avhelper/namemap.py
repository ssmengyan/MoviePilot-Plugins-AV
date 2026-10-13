# -*- coding: utf-8 -*-
"""三语标准映射（演员 / 标签）与繁→简字形转换 —— 刮削线 v4 唯一的「名字与标签」口径来源。

数据来自随包内置的三份上游社区映射表（`resources/`，见 `resources/NOTICE.md`；用户可用
`{data_root}/resources/` 同名文件覆盖，走 `paths.resource_file()`）：

| 文件 | 结构（实测，不是文档转述） | 用途 |
| --- | --- | --- |
| `mapping_actor.xml` | 根 `<actor>`，5351 条**属性式**记录 `<a zh_cn= zh_tw= jp= keyword=",a,b," href=…/>`（无子元素） | 演员三语名 + 别名 + javdb 演员 id |
| `mapping_info.xml` | 根 `<info>`，347 条同构记录（管标签/导演/系列/制作/发行，**无 `href`**） | 标签标准简中 + 删除规则 |
| `zhcdict.json` | 8 个顶层键；**只用 `zh2Hans`**（9149 键 = 8505 单字 + 644 词组，最长 4 字） | 繁 → 简字形转换 |

六条硬口径（前五条来自 `_tmp/p0/REPORT-4.md` 的实测，第 4 条来自 S11 全库实测，改代码前先读报告）：

1. **别名索引必须是多值表**（`Dict[str, List[str]]`）：归一化去掉标点后，不同的人会撞成同一个
   键 —— `男優` 一个键命中 207 条记录（男演员的通用占位别名）。单值 dict 会**静默丢数据**。
   `actor_lookup()` 只在这个键指向多条记录时才消歧（`jp` 精确 → `zh_cn` 精确 → 归一化后精确），
   挑不出唯一候选就返回 `None`（**不许猜**）；`actor_lookup_all()` 把全部候选交回上层。
2. **带 `【誤認注意】`/`【同名異人】` 的别名一律不入索引**：那是上游自己标注的"多人共用"警告
   （531 条片段）。把它们也建索引，冲突键会从 6 涨到 190。
3. **演员名只走演员表、标签只走 info 表**，不做全局并表：两张表有 7 个归一化关键词重叠
   （`女优/素人/人妻/…`），并表会让一条标签命中一位演员。
4. **复合名要拆**：写进 Emby 的 `People[].Name` 是 D13 的 `中文（日文）`（如
   `皆川千遥（みながわ千遥）`），归一化会把全角括号连同里面的日文名一起吃掉、整串查不到，
   所以 `actor_lookup()` 按「整串 → 括号外 → 括号内」依次试。**整串必须排第一**：上游自己
   就有带括号的别名（`素人(多人)`、`素人(円光娘)`），它们的"括号外" `素人` 指向**另一位**
   记录（实测 14 个写法会被错抢），整串先试才能保证这些老写法行为一个字不变。
5. **标签表要建两层索引**（info 表的 `keyword` 是简繁混写：1031 项里 359 项含繁体字）：
   `normalize(原文)` 与 `normalize(to_simplified(原文))`；查询先原样、后转简
   （实测 `獨占配信` 原样查不到、转简后命中删除规则）。
6. **`to_simplified()` 自带语言保护**：文本含假名（平假名/片假名）就**原样返回**。日文标题
   （如 `一ヶ月間の禁欲…`）过一遍转换器会被改字（`間→间`、`頭→头`），是**错字**；句子级语言
   判定器实测都不可靠（REPORT-4 §4.4），所以这里只做"含假名即不动"这一条确定性保护，
   中文标题/标签/演员名照常转换。

`zh2TW` / `zh2HK` / `zh2CN` **一律禁止使用**：它们是「换词」不是「换字形」（`軟體→軟件`、
`鼠标→滑鼠`），与上游映射表的口径直接冲突（实测准确率反而下降）。

本模块的失败模式是**降级而不是抛异常**：任何一份资源缺失/损坏都只 warning，
`ready()` 转 `False`，查询返回 `None`/`[]`/`{}`，转换退化成恒等函数 —— 刮削可以少一层映射，
但绝不能因为映射表而让插件起不来。`load()` 只解析一次并缓存（`force=True` 才重来），
全程 `threading.RLock` 保护。
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import paths

try:  # 宿主日志；离线脚本/单测直接导入本模块时退回标准库（本模块不依赖宿主任何 API）
    from app.sdk.logging import logger
except Exception:  # pragma: no cover - 只在本机脚本与无宿主环境走到
    import logging

    logger = logging.getLogger("avhelper.namemap")

# ---------------------------------------------------------------- 常量

ACTOR_XML = "mapping_actor.xml"
INFO_XML = "mapping_info.xml"
ZHC_DICT = "zhcdict.json"

#: 入库时的来源标记：内置 XML 导入的行用 `builtin_xml`，用户手工映射是 `user_custom`
#: （`sync_store()` **绝不覆盖** `user_custom` 行）
SOURCE_BUILTIN = "builtin_xml"
#: `actor_lookup()` 返回的记录里 `source` 字段的值（数据出处，与入库来源是两回事）
SOURCE_UPSTREAM = "amane"

ENTITY_ACTOR = "actor"
ENTITY_TAG = "tag"

#: 演员 `canonical_id` 前缀：`amane:三上悠亚`（实测 `zh_cn` 5351/5351 唯一）
ACTOR_ID_PREFIX = "amane:"
#: info 表前缀：`amane:tag:单体作品`。**必须与演员表分开命名空间** —— 实测两张表有
#: `SOD` / `S级素人` 两个同名 `zh_cn`，共用前缀会让一条标签覆盖一位演员。
TAG_ID_PREFIX = "amane:tag:"
#: 删除规则的 `canonical_id` 前缀：42 条删除记录的 `zh_cn` **全是「删除」**，
#: 用 `amane:tag:删除` 会让 42 条塌成一条；改用它自己的首个关键词（实测 42/42 唯一）。
DELETE_ID_PREFIX = "amane:del:"

#: info 表里「删除规则」的判据（REPORT-4 §2.2：42 条的 `zh_tw`/`jp` 也都是「删除」，只看 `zh_cn`）
DELETE_ZH = "删除"
#: 用户手工映射的来源标记（`store.namemap_user_set` 写的就是它）
SOURCE_USER = "user_custom"

#: 归一化时丢弃的 Unicode 类别：标点/符号/空白/控制符（保留 `Lm` 的 `々`、保留汉字与假名）
_SKIP_CATEGORIES = frozenset({
    "Pc", "Pd", "Pe", "Pf", "Pi", "Po", "Ps", "Sm", "Sk", "So",
    "Zs", "Zl", "Zp", "Cc", "Cf",
})

#: 上游的歧义警告标记：整条别名不入索引（见模块 docstring 第 2 条）
_MARK_RE = re.compile(r"[【\[]\s*(?:誤認注意|误认注意|同名異人|同名异人)\s*[】\]]")

#: 假名（含半角片假名与片假名音标扩展）：命中即认定"这是日文文本"，`to_simplified()` 原样返回
_KANA_RE = re.compile(r"[\u3041-\u309f\u30a0-\u30ff\u31f0-\u31ff\uff66-\uff9f]")

#: 复合名（D13：写进 Emby 的 `People[].Name` 就是 `中文（日文）` 形态）里的括号：
#: 全角/半角圆括号与方括号（`（…）` / `(…)` / `［…］` / `[…]`）。括号里不嵌套括号。
_BRACKET_RE = re.compile(r"[（(\[［]\s*([^）)\]］]*?)\s*[）)\]］]")


# ---------------------------------------------------------------- 归一化 / 别名解析

def normalize(text: Any) -> str:
    """NFKC → 去空白/标点/符号 → `lower()`，用于**一切索引键**（内存索引与入库同一口径）。

    实测三个坑（REPORT-4 §3）：NFKC 只改动 3/11249 个串（全角数字、`＠`），但第三方文本不可控，
    仍要留着；丢标点会让不同的人撞键（`Marin`/`Marin.`），所以索引必须是多值表；
    `.lower()` 会改动 218 个别名（`AV女優→av女優`），拉丁部分必须小写。

    注意：归一化**不做**繁简转换（`女优` 与 `女優` 是两个键），也**不**把 `々` 当标点丢掉
    （`奈々 ≠ 奈奈`）。
    """
    s = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(ch for ch in s
                   if not ch.isspace() and unicodedata.category(ch) not in _SKIP_CATEGORIES).lower()


def parse_keywords(raw: Any) -> List[Tuple[str, str]]:
    """`keyword` 属性（`,a,b【誤認注意】,`）→ `[('a', ''), ('b', '【誤認注意】')]`。

    只按 **ASCII 逗号**切分（实测别名里没有 ASCII 逗号；6 条含全角 `，` 的应被当成一个别名，
    切了就错）。返回 `(裸名, 命中的标记)`；**纯标记片段**（整条就是 `【同名異人】`，实测 88 条）
    回 `('', 标记)` —— 它进不了索引，但统计口径要数得到它（它与另外 1 条噪声别名一起构成
    REPORT-4 的「归一化后为空的别名 89 条」）。
    """
    out: List[Tuple[str, str]] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        hit = _MARK_RE.search(part)
        bare = _MARK_RE.sub("", part).strip()
        if bare or hit:
            out.append((bare, hit.group(0) if hit else ""))
    return out


def keywords_norm(tokens: Iterable[Any]) -> str:
    """归一化别名串 `,k1,k2,`（首尾带逗号）。

    **口径与 S1 的 `store.namemap_find()` 对齐**：它在 SQL 里用
    `keywords_norm LIKE '%,'||?||',%'` 做整词匹配，所以必须首尾带逗号，否则子串会误命中
    （`女优` 会命中 `未知男优`）。REPORT-4 §5.1 的参考实现用的是 `|k1|k2|`，S1 落地时统一定成
    逗号版，两边只能有一份口径 —— 这里跟随 store。
    """
    seen: set = set()
    keys: List[str] = []
    for token in tokens or []:
        text = str(token or "").strip().strip(",")
        if text and text not in seen:
            seen.add(text)
            keys.append(text)
    return "," + ",".join(keys) + "," if keys else ","


# ---------------------------------------------------------------- 模块状态（load 时一次性重建）

_LOCK = threading.RLock()

_LOADED = False
_ACTOR_OK = False
_TAG_OK = False
_ZHC_OK = False

_ACTOR_INDEX: Dict[str, List[str]] = {}      # normalize(别名) → [canonical_id, ...]（多值！）
_ACTOR_BY_ID: Dict[str, Dict[str, Any]] = {}  # canonical_id → 记录
_TAG_INDEX: Dict[str, str] = {}              # normalize(关键词原文) → 简中名 | ''（删除规则）
_TAG_SIMP_INDEX: Dict[str, str] = {}         # normalize(转简后的关键词) → 同上（覆盖简繁混写）
_TAG_META: Dict[str, Dict[str, Any]] = {}    # 键 → 记录元信息（展示用）
_TAG_CONFLICTS: set = set()                  # 一个键指向 ≥2 个不同目标的那些键（诊断/自检用）
_ZHC: Dict[str, str] = {}                    # zh2Hans（繁→简单字表）
_ZHC_PHRASES: Dict[str, str] = {}            # zh2Hans 里的多字词（644 条）
_ZHC_MAXLEN = 1
_SYNC_ROWS: List[Dict[str, Any]] = []        # 给 store 的批量行（演员 + info），load 时构建

_COUNTS: Dict[str, int] = {}


def _resource_path(name: str):
    """资源定位（**单测的注入点**）：默认走 `paths.resource_file()`，用户覆盖目录优先（D3）。"""
    return paths.resource_file(name)


def _warn(message: str, *args: Any) -> None:
    """降级日志：任何一份资源出问题都只 warning，绝不抛异常。"""
    try:
        logger.warning(message, *args)
    except Exception:  # pragma: no cover - 日志本身不该成为失败点
        pass


# ---------------------------------------------------------------- 装载：三份资源

def _load_zhc(path) -> Tuple[Dict[str, str], Dict[str, str], int]:
    """读 `zhcdict.json`，**只取 `zh2Hans`**（繁→简）。

    `zh2TW`/`zh2HK`/`zh2CN` 是"换词"（`軟體→軟件`、`鼠标→滑鼠`），用了准确率反而降
    （REPORT-4 §4.2C），一律不读。返回 `(单字+词组总表, 词组表, 最长词组长度)`。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("zh2Hans") if isinstance(data, dict) else None
    if not isinstance(raw, dict) or not raw:
        raise ValueError("zhcdict.json 里没有可用的 zh2Hans 段")
    chars = {str(k): str(v) for k, v in raw.items() if k and str(k)}
    phrases = {k: v for k, v in chars.items() if len(k) > 1}
    return chars, phrases, max((len(k) for k in phrases), default=1)


def _fmm(text: str, chars: Dict[str, str], phrases: Dict[str, str], maxlen: int) -> str:
    """正向最大匹配：先试最长词组、再退单字。

    必须做 FMM 而不是逐字替换：实测 464/644 条词组规则会改变结果
    （`么九` FMM→`幺九`、逐字→`么九`）。
    """
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        for size in range(min(maxlen, n - i), 1, -1):
            hit = phrases.get(text[i:i + size])
            if hit is not None:
                out.append(hit)
                i += size
                break
        else:
            ch = text[i]
            out.append(chars.get(ch, ch))
            i += 1
    return "".join(out)


def _unique_id(base: str, used: Dict[str, Any]) -> str:
    """`canonical_id` 防撞：上游将来新增同名记录时也不能静默丢掉一条（当前数据 0 次触发）。"""
    if base not in used:
        return base
    for index in range(2, 1000):
        candidate = f"{base}#{index}"
        if candidate not in used:
            return candidate
    return base  # pragma: no cover - 1000 个同名记录，现实中不存在


def _name_tokens(names: Iterable[Any]) -> List[str]:
    """把记录自己的三语名也并进别名 token（入库与内存索引共用同一份 token 串）。"""
    out: List[str] = []
    for name in names:
        key = normalize(name)
        if key and key not in out:
            out.append(key)
    return out


def _load_actors(path) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]],
                                List[Dict[str, Any]], Dict[str, int]]:
    """解析 `mapping_actor.xml` → `(别名索引, canonical_id → 记录, 入库行, 计数)`。"""
    index: Dict[str, List[str]] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    counts = {"actors": 0, "alias_keys": 0, "multi_target_keys": 0,
              "marker_aliases": 0, "empty_aliases": 0, "javdb_actor_ids": 0}

    for element in ET.parse(path).getroot():
        pairs = parse_keywords(element.get("keyword"))
        zh = str(element.get("zh_cn") or "").strip()
        tw = str(element.get("zh_tw") or "").strip()
        jp = str(element.get("jp") or "").strip()
        href = str(element.get("href") or "").strip()
        head = zh or jp or tw
        if not head:
            continue                     # 三个名字全空的记录没法建索引（当前数据 0 条）
        cid = _unique_id(ACTOR_ID_PREFIX + head, by_id)

        tokens: List[str] = []
        for bare, mark in pairs:
            key = normalize(bare)
            if mark:
                counts["marker_aliases"] += 1     # 上游自己标注的歧义别名（含纯标记那 88 条）
            if not key:
                counts["empty_aliases"] += 1
            if not key or mark:
                continue                 # 歧义别名/空别名一律不入索引
            if key not in tokens:
                tokens.append(key)
        for key in _name_tokens((zh, tw, jp)):
            if key not in tokens:
                tokens.append(key)

        javdb_id = href.rsplit("/actors/", 1)[1].strip() if "/actors/" in href else ""
        if javdb_id and "/" in javdb_id:
            javdb_id = javdb_id.split("/")[0]
        if javdb_id:
            counts["javdb_actor_ids"] += 1

        record = {
            "canonical_id": cid,
            "entity_type": ENTITY_ACTOR,
            "zh": zh, "zh_cn": zh,
            "tw": tw, "zh_tw": tw,
            "jp": jp,
            "avatar": "",                # 上游这张表**没有头像 URL**（只有主页链接），上层另取
            "javdb_actor_id": javdb_id,
            "href": href,
            "source": SOURCE_UPSTREAM,
            # 给前端展示的别名（标记已剥掉，含被标记的歧义别名）；**索引只看未被标记的那些**
            "aliases": [bare for bare, _mark in pairs if bare],
            "keywords_raw": str(element.get("keyword") or ""),
            "keywords_norm": keywords_norm(tokens),
        }
        by_id[cid] = record
        rows.append({
            "canonical_id": cid, "entity_type": ENTITY_ACTOR,
            "zh_cn": zh, "zh_tw": tw, "jp": jp,
            "keywords_norm": record["keywords_norm"],
            "javdb_actor_id": javdb_id, "source": SOURCE_BUILTIN, "is_delete_rule": 0,
        })
        for key in tokens:
            bucket = index.setdefault(key, [])
            if cid not in bucket:
                bucket.append(cid)
        counts["actors"] += 1

    counts["alias_keys"] = len(index)
    counts["multi_target_keys"] = sum(1 for bucket in index.values() if len(bucket) > 1)
    return index, by_id, rows, counts


def _load_info(path, chars: Dict[str, str], phrases: Dict[str, str], maxlen: int
               ) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Dict[str, Any]],
                          List[Dict[str, Any]], Dict[str, int], set]:
    """解析 `mapping_info.xml` → `(原样索引, 转简索引, 元信息, 入库行, 计数, 冲突键)`。

    两趟建索引，顺序无关：**第一趟只认记录自己的 `keyword` 列表**（上游的权威口径），
    第二趟才把记录的三语名补进"还没有人认领"的键（只填空位，不抢别人的键，因此不会平白
    制造歧义 —— 实测新增 17 个键、冲突键不变）。
    """
    index: Dict[str, str] = {}
    simp_index: Dict[str, str] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    counts = {"tags": 0, "tags_simplified": 0, "delete_rules": 0,
              "tag_conflicts": 0, "delete_records": 0}
    conflicts: set = set()
    used_ids: Dict[str, Any] = {}
    pending: List[Dict[str, Any]] = []

    def put(bare: str, target: str, info: Dict[str, Any], tokens: List[str],
            fill_only: bool = False) -> None:
        """一个名字落两层键：`normalize(原文)` 与 `normalize(转简后)`（info 表简繁混写）。

        `fill_only=True`（记录自己的名字）时只填空位、不参与冲突判定。
        """
        key = normalize(bare)
        if not key:
            return
        if key not in tokens:
            tokens.append(key)
        if key not in index:
            index[key] = target
        elif not fill_only and index[key] != target:
            conflicts.add(key)
        simple = normalize(_fmm(bare, chars, phrases, maxlen))
        if simple:
            if simple not in simp_index:
                simp_index[simple] = target
            elif not fill_only and simp_index[simple] != target:
                conflicts.add(simple)
        meta.setdefault(key, info)
        if simple:
            meta.setdefault(simple, info)

    for element in ET.parse(path).getroot():
        zh = str(element.get("zh_cn") or "").strip()
        tw = str(element.get("zh_tw") or "").strip()
        jp = str(element.get("jp") or "").strip()
        is_delete = zh == DELETE_ZH
        target = "" if is_delete else zh          # 契约：'' = 删除规则，None = 无映射
        info = {"zh": zh, "tw": tw, "jp": jp, "is_delete": is_delete}
        tokens: List[str] = []
        for bare, _mark in parse_keywords(element.get("keyword")):
            put(bare, target, info, tokens)

        if is_delete:
            counts["delete_records"] += 1
            head = tokens[0] if tokens else f"record{counts['delete_records']}"
            cid = _unique_id(DELETE_ID_PREFIX + head, used_ids)
        else:
            cid = _unique_id(TAG_ID_PREFIX + (zh or jp or tw), used_ids)
        used_ids[cid] = True
        entry = {
            "canonical_id": cid, "entity_type": ENTITY_TAG,
            "zh_cn": zh, "zh_tw": tw, "jp": jp,
            "javdb_actor_id": "", "source": SOURCE_BUILTIN,
            "is_delete_rule": 1 if is_delete else 0,
        }
        rows.append(entry)
        if not is_delete:
            # 删除记录的「删除」是规则说明而不是名字，不补进索引
            pending.append({"target": target, "info": info, "entry": entry, "tokens": tokens,
                            "names": [zh, tw, jp]})
        counts["tags"] += 1

    for ctx in pending:                           # 第二趟：名字只填空位
        for name in ctx["names"]:
            put(name, ctx["target"], ctx["info"], ctx["tokens"], fill_only=True)
        ctx["entry"]["keywords_norm"] = keywords_norm(ctx["tokens"])

    counts["tags_simplified"] = len(simp_index)
    counts["delete_rules"] = sum(1 for value in index.values() if value == "")
    counts["tag_conflicts"] = len(conflicts)
    return index, simp_index, meta, rows, counts, conflicts


def load(force: bool = False) -> None:
    """解析三份资源并缓存（`force=True` 才重来）。**线程安全，绝不抛异常**。

    装载顺序有依赖：`zhcdict.json` 先（info 表的转简索引要用 FMM），然后演员表、info 表。
    任何一份失败只 warning + 把对应部分置空/关闭，其余部分照常可用（`stats()` 里能看到
    哪一部分没装上；`ready()` 只在**三份都成功**时为 True）。

    资源缺失后想恢复，必须 `load(force=True)`（`load()` 的语义是"只解析一次并缓存"）。
    """
    global _LOADED, _ACTOR_OK, _TAG_OK, _ZHC_OK, _ACTOR_INDEX, _ACTOR_BY_ID
    global _TAG_INDEX, _TAG_SIMP_INDEX, _TAG_META, _TAG_CONFLICTS
    global _ZHC, _ZHC_PHRASES, _ZHC_MAXLEN
    global _SYNC_ROWS, _COUNTS

    with _LOCK:
        if _LOADED and not force:
            return

        chars: Dict[str, str] = {}
        phrases: Dict[str, str] = {}
        maxlen = 1
        zhc_ok = False
        try:
            path = _resource_path(ZHC_DICT)
            chars, phrases, maxlen = _load_zhc(path)
            zhc_ok = True
        except Exception as error:
            _warn("namemap: 简繁词典不可用（%s: %s），繁→简转换退化为原样返回",
                  type(error).__name__, error)

        actor_index: Dict[str, List[str]] = {}
        actor_by_id: Dict[str, Dict[str, Any]] = {}
        actor_rows: List[Dict[str, Any]] = []
        actor_counts = {"actors": 0, "alias_keys": 0, "multi_target_keys": 0,
                        "marker_aliases": 0, "empty_aliases": 0, "javdb_actor_ids": 0}
        actor_ok = False
        try:
            actor_index, actor_by_id, actor_rows, actor_counts = _load_actors(
                _resource_path(ACTOR_XML))
            actor_ok = True
        except Exception as error:
            _warn("namemap: 演员映射表不可用（%s: %s），演员查询返回 None",
                  type(error).__name__, error)

        tag_index: Dict[str, str] = {}
        tag_simp: Dict[str, str] = {}
        tag_meta: Dict[str, Dict[str, Any]] = {}
        tag_rows: List[Dict[str, Any]] = []
        tag_counts = {"tags": 0, "tags_simplified": 0, "delete_rules": 0,
                      "tag_conflicts": 0, "delete_records": 0}
        tag_conflicts: set = set()
        tag_ok = False
        try:
            tag_index, tag_simp, tag_meta, tag_rows, tag_counts, tag_conflicts = _load_info(
                _resource_path(INFO_XML), chars, phrases, maxlen)
            tag_ok = True
        except Exception as error:
            _warn("namemap: 标签映射表不可用（%s: %s），标签查询返回 None",
                  type(error).__name__, error)

        # 全部构建完再一次性换绑全局（读侧不加锁也不会看到半张表）
        _ZHC, _ZHC_PHRASES, _ZHC_MAXLEN = chars, phrases, maxlen
        _ACTOR_INDEX, _ACTOR_BY_ID = actor_index, actor_by_id
        _TAG_INDEX, _TAG_SIMP_INDEX, _TAG_META = tag_index, tag_simp, tag_meta
        _TAG_CONFLICTS = tag_conflicts
        _SYNC_ROWS = actor_rows + tag_rows
        _ZHC_OK, _ACTOR_OK, _TAG_OK = zhc_ok, actor_ok, tag_ok
        _LOADED = True
        _COUNTS = {
            **actor_counts, **tag_counts,
            "chars": sum(1 for key in chars if len(key) == 1),
            "phrases": len(phrases),
            "zhc_entries": len(chars),
            "sync_rows": len(_SYNC_ROWS),
        }

        if not (actor_ok and tag_ok and zhc_ok):
            _warn("namemap: 资源不完整（演员=%s 标签=%s 词典=%s），刮削映射已降级；"
                  "把同名文件放进 {data_root}/resources/ 可覆盖内置那份",
                  actor_ok, tag_ok, zhc_ok)


def ready() -> bool:
    """三份资源是否都装载成功。缺任何一份都是 False（查询仍会尽力返回已装载那部分的结果）。"""
    return bool(_LOADED and _ACTOR_OK and _TAG_OK and _ZHC_OK)


# ---------------------------------------------------------------- 演员查询

def _split_composite(name: Any) -> Tuple[List[str], List[str]]:
    """把 D13 的复合名 `中文（日文）` 拆成 `(括号外的段, 括号内的段)`，各自保序去重。

    全角/半角圆括号与方括号都认（`（…）`/`(…)`/`［…］`/`[…]`）。不是复合名（没有括号）时
    回 `([整串], [])` —— 调用方据此原地走老路径。多组括号（`A（B）C（D）`）时括号外会给
    `['A', 'C']`、括号内 `['B', 'D']`。
    """
    text = str(name or "").strip()
    if not text or not _BRACKET_RE.search(text):
        return ([text], []) if text else ([], [])
    outside: List[str] = []
    inside: List[str] = []
    pos = 0
    for match in _BRACKET_RE.finditer(text):
        segment = text[pos:match.start()].strip()
        if segment and segment not in outside:
            outside.append(segment)
        inner = match.group(1).strip()
        if inner and inner not in inside:
            inside.append(inner)
        pos = match.end()
    tail = text[pos:].strip()
    if tail and tail not in outside:
        outside.append(tail)
    if not outside and not inside:       # `（）` 这种整串都是括号的写法：原样当整串试
        return [text], []
    return outside, inside


def _lookup_index(name: Any) -> Tuple[str, List[str]]:
    """按候选写法查别名索引，返回 `(命中的写法, canonical_id 列表)`；都没命中回 `("", [])`。

    顺序：**整串 → 括号外 → 括号内**。

    - **整串排第一**是实测逼出来的：上游自己就有带括号的别名，`素人(多人)` 整串是
      `amane:素人(多人)` 的键，而它的"括号外" `素人` 指向**另一位**记录（14 个上游写法会
      被错抢，见 `_tmp/s3/recon7_brackets.py`）。整串先试 → 这些写法行为一个字不变。
    - D13 写进 Emby 的 `皆川千遥（みながわ千遥）` 整串不是任何键（实测 12/12），于是落到
      "括号外 → 括号内"，两种情况都能命中。
    """
    text = str(name or "").strip()
    if not text:
        return "", []
    outside, inside = _split_composite(text)
    ordered: List[str] = [text]
    if outside != [text]:                # 是复合名才追加拆分结果（否则只有整串一个候选）
        ordered += outside + inside
    for candidate in ordered:
        ids = _ACTOR_INDEX.get(normalize(candidate))
        if ids:
            return candidate, ids
    return "", []


def _pick(records: List[Dict[str, Any]], probe: str) -> Optional[Dict[str, Any]]:
    """从一个键的多个候选里挑唯一命中：只有一个候选直接用；多个时 `jp` 精确 → `zh_cn` 精确
    → 归一化后精确。

    每一层只要**恰好一个**候选才算命中；某一层有多个候选说明这个名字本身就歧义
    （`Marin`/`Marin.` 只能靠原文精确区分），交给下一层，全都挑不出就回 `None` —— **不许猜**。
    """
    if not records:
        return None
    if len(records) == 1:
        return records[0]       # 键只指向一条记录：命中的是它的别名，不存在歧义
    key = normalize(probe)
    for field in ("jp", "zh_cn"):
        for level in ("exact", "normalized"):
            hits = [r for r in records
                    if (str(r.get(field) or "") == probe if level == "exact"
                        else normalize(r.get(field)) == key)]
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                break
    return None


def actor_lookup(name: Any) -> Optional[dict]:
    """按任意写法查一位演员：`{canonical_id, zh, zh_cn, tw, zh_tw, jp, avatar, javdb_actor_id, …}`。

    支持 **D13 的复合名**（`皆川千遥（みながわ千遥）`）—— 这正是写进 Emby 的 `People[].Name`
    形态，二次刮削拿它回查必须命中：先试整串（上游自己就有带括号的别名），再试括号外、括号内。

    命中多个候选时优先 `jp` 精确 → `zh_cn` 精确 → 归一化后精确；**挑不出唯一候选返回 `None`**
    （如 `男優` 一个键命中 207 条记录，任何"取第一个"都是瞎猜）。要全部候选用
    `actor_lookup_all()`。

    返回的是**缓存里的记录本身**（µs 级），调用方只读、不要就地改它。
    """
    probe, ids = _lookup_index(name)
    if not ids:
        return None
    records = [_ACTOR_BY_ID[cid] for cid in ids if cid in _ACTOR_BY_ID]
    return _pick(records, probe) if records else None


def actor_lookup_all(name: Any) -> List[dict]:
    """一个写法命中**全部**候选记录（REPORT-4 §4.2 要求：冲突键必须暴露而不是丢掉）。

    复合名（`中文（日文）`）按 `_lookup_index()` 的顺序取**第一个命中**的写法，
    再把那个键的全部候选交回来。
    """
    _probe, ids = _lookup_index(name)
    return [_ACTOR_BY_ID[cid] for cid in ids if cid in _ACTOR_BY_ID]


def actor_glossary(names: Iterable[Any]) -> Dict[str, str]:
    """`{日文名: 中文名}`（只收三语都有、且中日文不同的），注入翻译 Prompt 用。"""
    out: Dict[str, str] = {}
    for name in names or []:
        record = actor_lookup(name)
        if not record:
            continue
        jp = str(record.get("jp") or "")
        zh = str(record.get("zh") or "")
        if jp and zh and jp != zh:
            out[jp] = zh
    return out


def actor_display(name: Any, alias: str = "") -> Dict[str, str]:
    """给上层的展示三元组 `{'name', 'jp', 'zh', 'alias'}`。

    `alias` 是用户手工备注（`actor_alias`）时优先拿它去查表；查不到就退回站点给的 `name`，
    `name` 字段最终取映射的简中名、没有映射时原样回传 `name`。

    传进来的是**复合名**（`皆川千遥（みながわ千遥）`）时，查不到映射就按括号**拆开兜底**：
    `name`/`zh` 给括号外的中文名、`jp` 给括号内的日文名（不再把整串当成一个中文名）。
    非复合名且查不到映射时 `zh`/`jp` 仍是空串 —— 调用方要能区分"映射里没这个人"和
    "原样把站点给的名字回传"，`name` 字段负责后者。
    """
    record = actor_lookup(alias) or actor_lookup(name) or {}
    outside, inside = _split_composite(name)
    composite = bool(inside)
    raw = str(name or "").strip()
    return {
        "name": str(record.get("zh") or (outside[0] if composite and outside else raw)),
        "jp": str(record.get("jp") or (inside[0] if composite else "")),
        "zh": str(record.get("zh") or (outside[0] if composite and outside else "")),
        "alias": str(alias or ""),
    }


# ---------------------------------------------------------------- 标签查询

def tag_lookup(tag: Any) -> Optional[str]:
    """标准简中名 / `''` = 删除规则 / `None` = 无映射。

    两层索引：先按**原文**归一化查，再按**转简后**归一化查（info 表 `keyword` 简繁混写，
    实测 1031 项里 359 项含繁体字；`獨占配信` 原样查不到、转简后命中删除规则）。

    第二层不能加「转简结果与原文不同才查」的短路：查询本身已经是简体时
    （`10枚组`）两层键相同，短路会让它查不到 `10枚組` 那条删除规则。
    """
    key = normalize(tag)
    if not key:
        return None
    if key in _TAG_INDEX:
        return _TAG_INDEX[key]
    simple = normalize(to_simplified(tag))
    if not simple:
        return None
    return _TAG_SIMP_INDEX.get(simple)


def clean_tags(tags: Any, limit: int = 0) -> List[str]:
    """标签清洗：无映射的做字形转换、删除规则丢弃、去重保序。

    接受 `['巨乳', …]`、javdb 的 `[{'id','name'}, …]`（取 `name`）或单个字符串。
    `limit > 0` 时截断（§3.6.1 写 Emby 的 `GenreItems` 上限 10 个，由写侧决定传不传）。
    """
    if isinstance(tags, (str, bytes)) or not isinstance(tags, Iterable):
        tags = [tags]
    out: List[str] = []
    seen: set = set()
    for item in tags:
        if isinstance(item, dict):
            item = item.get("name") or item.get("zh") or ""
        if item is None:
            continue
        value = tag_lookup(item)
        if value == "":
            continue                     # 删除规则
        value = value or to_simplified(item)
        if value and value not in seen:
            seen.add(value)
            out.append(value)
            if limit and len(out) >= limit:
                break
    return out


# ---------------------------------------------------------------- 繁 → 简（字形，不换词）

def to_simplified(text: Any) -> str:
    """`zh2Hans` 正向最大匹配（**只换字形，不换词**）。

    **含假名即原样返回**：日文标题过转换器会被改字（实测
    `一ヶ月間の禁欲…` → `一ヶ月间の…`，`間→间`/`頭→头`），句子级语言判定器实测都不可靠
    （REPORT-4 §4.4），所以这里用"含平假名/片假名就一个字都不动"这条确定性规则兜底；
    中文标题/标签/演员名照常转换。空值/`None` 回 `""`。
    """
    if text is None:
        return ""
    raw = str(text)
    if not raw or not _ZHC or _KANA_RE.search(raw):
        return raw
    return _fmm(raw, _ZHC, _ZHC_PHRASES, _ZHC_MAXLEN)


# ---------------------------------------------------------------- 入库同步（name_map）

def _store_rows(store: Any) -> Optional[List[Dict[str, Any]]]:
    """读库里的 `name_map` 行；store 不支持 `namemap_list()` 时返回 `None`（表示"查不了"）。"""
    lister = getattr(store, "namemap_list", None)
    if not callable(lister):
        return None
    try:
        rows = lister()
    except Exception as error:
        _warn("namemap.sync_store: 读取 name_map 失败（%s: %s），按空库处理",
              type(error).__name__, error)
        return None
    return [row for row in (rows or []) if isinstance(row, dict)]


def sync_store(store: Any, force: bool = False) -> int:
    """把演员表 + info 表灌进 `store.name_map`，返回写入条数。

    - `source='builtin_xml'`；**绝不覆盖 `source='user_custom'` 的行**（用户手工称呼最高优先级，
      `force=True` 也不例外）。
    - **幂等**：默认只在库里**还没有任何内置行**时才灌（`force=True` 才无条件重灌）。
      `namemap_bulk_upsert()` 本身是 `ON CONFLICT(canonical_id) DO UPDATE`，重灌也不会翻倍。
    - store 没有 `namemap_list()`（探不到现状）时退化成"每次都灌"，正确性由
      `namemap_bulk_upsert()` 自己的 `user_custom` 保护兜底。
    - store 缺失/不支持/抛异常一律吞掉并 warning，返回 0（绝不连累插件启动）。
    """
    load()
    rows = [dict(row) for row in _SYNC_ROWS]
    if store is None or not rows:
        return 0
    upsert = getattr(store, "namemap_bulk_upsert", None)
    if not callable(upsert):
        _warn("namemap.sync_store: store 不支持 namemap_bulk_upsert，跳过映射入库")
        return 0
    current = _store_rows(store)
    if current is not None:
        if not force and any(str(row.get("source") or "") == SOURCE_BUILTIN for row in current):
            return 0                     # 已经灌过内置表：幂等返回
        blocked = {str(row.get("canonical_id") or "") for row in current
                   if str(row.get("source") or "") == SOURCE_USER}
        if blocked:
            rows = [row for row in rows if row["canonical_id"] not in blocked]
    if not rows:
        return 0
    try:
        return int(upsert(rows) or 0)
    except Exception as error:
        _warn("namemap.sync_store: 写入 name_map 失败（%s: %s）", type(error).__name__, error)
        return 0


# ---------------------------------------------------------------- 自检

def stats() -> Dict[str, int]:
    """映射表规模与健康度（全部整数）。`actors*`/`tags*` 的 `*_loaded` 是 0/1 旗标。"""
    return {
        "actors": int(_COUNTS.get("actors", 0)),
        "alias_keys": int(_COUNTS.get("alias_keys", 0)),
        "multi_target_keys": int(_COUNTS.get("multi_target_keys", 0)),
        "marker_aliases": int(_COUNTS.get("marker_aliases", 0)),
        "empty_aliases": int(_COUNTS.get("empty_aliases", 0)),
        "javdb_actor_ids": int(_COUNTS.get("javdb_actor_ids", 0)),
        "tags": len(_TAG_INDEX),
        "tags_simplified": len(_TAG_SIMP_INDEX),
        "tag_records": int(_COUNTS.get("tags", 0)),
        "tag_conflicts": int(_COUNTS.get("tag_conflicts", 0)),
        "delete_rules": int(_COUNTS.get("delete_rules", 0)),
        "delete_records": int(_COUNTS.get("delete_records", 0)),
        "chars": int(_COUNTS.get("chars", 0)),
        "phrases": int(_COUNTS.get("phrases", 0)),
        "zhc_entries": int(_COUNTS.get("zhc_entries", 0)),
        "sync_rows": int(_COUNTS.get("sync_rows", 0)),
        "loaded": 1 if _LOADED else 0,
        "ready": 1 if ready() else 0,
        "actors_loaded": 1 if _ACTOR_OK else 0,
        "tags_loaded": 1 if _TAG_OK else 0,
        "dict_loaded": 1 if _ZHC_OK else 0,
    }


def _selfcheck() -> None:  # pragma: no cover - 供 `python -m` 式手跑，单测覆盖同一批断言
    load()
    for key, value in stats().items():
        print(f"  {key:18} {value}")
    for name in ("三上悠亜", "橋本ありな", "雛形みくる", "男優"):
        hit = actor_lookup(name)
        print(f"  actor {name:8} → {(hit or {}).get('zh') or '—'}"
              f"（候选 {len(actor_lookup_all(name))}）")
    for tag in ("單體作品", "10枚組", "獨占配信", "ハイビジョン"):
        print(f"  tag   {tag:8} → {tag_lookup(tag)!r}")
    print("  conv  ", to_simplified("學校泳裝"), to_simplified("一ヶ月間の禁欲"))


if __name__ == "__main__":  # pragma: no cover
    _selfcheck()
