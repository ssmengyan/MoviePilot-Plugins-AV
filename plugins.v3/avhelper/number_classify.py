"""番号形态分类：内容类型 / 马赛克 / 分集 / 分辨率（**纯函数，零依赖、零 I/O**）。

借 `sqzw-x/amane`（GPL-3.0）`src/amane/parsing/file_info.py` 的**词表与判定顺序**（0.8.0 的 P0-0），
是本插件「类型路由 + 字段优先级」（P0-1）的输入：路由的键就是内容类型，
而类型只由**番号形态 + 目录关键词 + 版本标签**决定。

与上游的**三处有意差异**（都用 `why` 标出来，便于排查）：

1. **推不出来时落 `censored`（上游落 `western`）**。上游多数入口是媒体文件路径、且库里有欧美分区；
   我们多数入口只有一串番号（订阅/任务/Emby 条目），猜成欧美会把片子送进一条根本没有源能用的链。
   「不许猜」= 落默认链，而不是随便挑一条。
2. **`-U` / `-UC` 记 `leaked`（上游记 `cracked`）**。这是同一个现象的两套叫法：中文圈说"无码流出"，
   上游的 `CRACKED` 指"破解马赛克"。我们沿用 `emby.parse_av_number()` 既有口径
   （它把 `-U/-UC` 记成 `is_uncensored_leak`），**不改已有语义**。
3. **不加目录里的 `hentai` 兜底**（`getchu` 段名靠下载目录约定，我们的目录由 qB 分类统一落盘，
   没有这个信号源）；`里番/裏番` 段首关键词仍认（那是用户自己建的目录名）。

数据一致性：模块里的词表可以整表核对上游（`_UNCENSORED_PREFIXES` **46 条** / `_SUREN_PREFIXES` 5 条 /
`_WESTERN_NAMES` 13 条 / `_MOSAIC_DIR_TOKENS` 7 条 / 分辨率 9 档）。**只搬数据与顺序，函数体自己写**
（上游要求 Python ≥3.14 且是 asyncio 栈，逐行抄只会带进不属于插件的东西）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

#: 内容类型（= 路由的键，**只加不改**，改一个字母等于改所有路由表）
CONTENT_TYPES: Tuple[str, ...] = (
    "censored",      # 有码（默认链）
    "uncensored",    # 无码
    "chinese",       # 国产
    "western",       # 欧美
    "fc2",           # FC2
    "amateur",       # 素人
    "hentai",        # 里番 / 动漫
)

#: 马赛克标记；空串 = **判不出来**（不是"有码"，见 `fill_mosaic`）
MOSAIC_VALUES: Tuple[str, ...] = ("censored", "uncensored", "cracked", "leaked")
MOSAIC_NONE = ""

#: 无码前缀白名单（上游 `_UNCENSORED_PREFIXES`，**46 条**：`file_info.py:83-130` 逐条核过）
#: 注意 `BIRD` / `BOUGA` / `S2M` / `MCB3D` **不带尾短横**：它们是前缀字面量，不是"到分隔符为止"
UNCENSORED_PREFIXES: Tuple[str, ...] = (
    "BT-", "CT-", "EMP-", "CCDV-", "CWP-", "CWPBD-", "DSAM-", "DRC-", "DRG-", "GACHI-",
    "HEYDOUGA", "JAV-", "LAF-", "LAFBD-", "HEYZO-", "KTG-", "KP-", "KG-", "LLDV-", "MCDV-",
    "MKD-", "MKBD-", "MMDV-", "NIP-", "PB-", "PT-", "QE-", "RED-", "RHJ-", "S2M-",
    "SKY-", "SKYHD-", "SMD-", "SSDV-", "SSKP-", "TRG-", "TS-", "XXX-AV-", "YKB-", "BIRD",
    "BOUGA", "H4610-", "C0930-", "H0930-", "S2M", "MCB3D",
)

#: 素人前缀改写（上游 `_SUREN_PREFIXES`）：站点上这些号带三位站号前缀
SUREN_PREFIXES: Dict[str, str] = {
    "LUXU-": "259LUXU-",
    "ARA-": "200GANA-",
    "MIUM-": "300MIUM-",
    "NTK-": "300NTK-",
    "MAAN-": "300MAAN-",
}

#: 欧美厂牌名（上游 `_WESTERN_NAMES`）：小写匹配 → 站点标准写法。
#: 只在**要拿它拼检索词**时用（P0-1 起），本模块只负责判类型。
WESTERN_NAMES: Dict[str, str] = {
    "vixen": "Vixen", "blacked": "Blacked", "tushy": "Tushy", "sexart": "SexArt",
    "x-art": "X-Art", "nubilefilms": "NubileFilms", "babes": "Babes",
    "wgp": "WhenGirlsPlay", "twistys": "Twistys", "deeper": "Deeper", "slayed": "Slayed",
    "tushy raw": "TushyRaw", "blackedraw": "BlackedRaw",
}

#: 目录马赛克词表（上游 `_MOSAIC_DIR_TOKENS`）：段名整段相等才认（去括号、casefold）
MOSAIC_DIR_TOKENS: Dict[str, str] = {
    "uncensored": "uncensored", "無碼": "uncensored", "无码": "uncensored",
    "cracked": "cracked", "破解": "cracked",
    "leaked": "leaked", "流出": "leaked",
}
_DIR_BRACKET_STRIP = "[]【】()（）"

#: 分辨率档位（**元组顺序即优先级**，`2160P` 归一成 `4K`）
DEFINITION_MARKERS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("8K", re.compile(r"\b8K(?:\d+)?\b")),
    ("4K", re.compile(r"\b4K(?:\d+)?\b")),
    ("4K", re.compile(r"\b2160P(?:\d+)?\b")),
    ("1440p", re.compile(r"\b1440P(?:\d+)?\b")),
    ("1080p", re.compile(r"\b1080P(?:\d+)?\b")),
    ("720p", re.compile(r"\b720P(?:\d+)?\b")),
    ("480p", re.compile(r"\b480P(?:\d+)?\b")),
    # HD/SD 不得是番号前缀：`HD-123` / `HD_123`（下划线归一成点后同形）不命中
    ("HD", re.compile(r"\bHD\b(?![.-]\d)")),
    ("SD", re.compile(r"\bSD\b(?![.-]\d)")),
)
DEFINITION_VALUES: Tuple[str, ...] = tuple(dict.fromkeys(v for v, _ in DEFINITION_MARKERS))

_CATALOG_NUMBER = re.compile(r"[A-Z]{2,}-\d{2,}[Z]?")            # 普通目录号 ABC-123
_FC2_NUMBER = re.compile(r"FC2(?:-?PPV)?-?\d{5,}")               # FC2-1234567 / FC2PPV-1234567
_KIN8_NUMBER = re.compile(r"KIN8(?:TENGOKU)?-?\d{3,}")           # 单厂牌，上游归欧美链
_SIX_DIGIT_CATALOG = re.compile(r"(?<!\d)\d{6}[-_]\d{2,4}(?!\d)")  # 010115_001（**别把 `_` 当 `-`**）
_N_SERIES = re.compile(r"^N\d{4}")                               # N1234：无码系
#: 欧美日期号 `Studio.YY.MM.DD`（上游 `_WESTERN_PARSE`）：年份允许 `2?0?` 前缀，故 2 位与 4 位写法都认
_WESTERN_DATE = re.compile(r"([A-Z0-9_]{2,})[-.]2?0?(\d{2})[-.](\d{2})[-.](\d{2})")
_SUREN_SHAPE = re.compile(r"\d{3,}[A-Z]+-\d{2}")                 # 300MIUM-123 这类素人号
_MD_NUMBER = re.compile(r"([^A-Z]|^)MD[A-Z-]*\d{4,}")            # 国产 MD0165
_MKY_NUMBER = re.compile(r"MKY-[A-Z]+-\d{3,}")
_CD_DIR = re.compile(r"^(?:CD|PART)(\d{1,2})$", re.IGNORECASE)
_MEDIA_EXT = re.compile(r"\.(?:mp4|mkv|avi|wmv|ts|mov|iso|strm|rmvb|flv|m4v|mpg)$", re.I)


def normalize_markers(text: Any) -> str:
    """上游 `_normalize_markers`：下划线与非 ASCII 一律变 `.`。

    目的是让 `分辨率/序号` 这类标记只按 ASCII 分隔符匹配 —— `HD_123` 与 `HD.123` 同形（都不算 HD 前缀）。
    """
    return re.sub(r"_|[^\x00-\x7F]", ".", str(text or ""))


def _strip_ext(text: str) -> str:
    return _MEDIA_EXT.sub("", text.strip())


def _dir_names(dirs: Optional[Iterable[Any]]) -> Tuple[str, ...]:
    out = []
    for item in dirs or ():
        name = str(item or "").strip()
        if name and name not in ("/", ".", ""):
            out.append(name)
    return tuple(out)


def western_date(number: Any) -> str:
    """欧美日期号的**形态**命中则回 `Studio.YY.MM.DD`（原样，含 2 位年份写法），否则回空串。

    上游把日期校验交给 `parsing/normalize_calendar_date`；这里只做**便宜的合理性检查**
    （月 1-12、日 1-31）—— 分类不需要真日期，只需要"它长得像日期号"。
    """
    found = _WESTERN_DATE.search(str(number or "").upper())
    if not found:
        return ""
    month, day = int(found.group(3)), int(found.group(4))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return ""
    return found.group(0)


def type_from_path(*names: Any) -> Tuple[str, str]:
    """目录/文件名关键词 → `(类型, why)`；认不出回 `("", "")`。

    上游 `_classify_from_path`：`getchu` 整段相等；`里番/裏番/欧美` **必须段首**
    （不然「这里番号」「非欧美」这种目录名会被误判）。
    """
    for raw in names:
        name = str(raw or "").strip()
        if not name:
            continue
        if name.lower() == "getchu":
            return "hentai", f"dir:getchu={name}"
        if name.startswith(("里番", "裏番")):
            return "hentai", f"dir:里番={name}"
        if name.startswith("欧美"):
            return "western", f"dir:欧美={name}"
    return "", ""


def type_from_number(number: Any) -> Tuple[str, str]:
    """番号形态 → `(类型, why)`。顺序照上游 `_type_of_catalog_id` + `_match` 的专项规则，**别重排**。

    三处对齐上游的细节：
    - **欧美日期号 → `western`**（上游 `_match:448-456` 走 `_WESTERN_NAMES` 改写后回 `WESTERN`）；
      注意上游 `_type_of_catalog_id` 里同样的形状回的是 `UNCENSORED` —— 那是它 fallback 分支的
      不一致，真链路走的是 `WESTERN`，我们跟真链路。
    - **`KIN8*` → `western`**（单厂牌，上游同）；
    - **`N` + 四位数字 → `uncensored`**：上游那条正则是**小写裸 `n`**（`re.match(r"n\\d{4}", number)`），
      而上游调用点传进来的是已经大写过的串 → 实际永不命中（疑似上游 bug）。我们按**意图**实现
      （先 `upper()` 再匹配），并在 `why` 里写 `n-series` 便于日后核对。
    末尾上游是 `western`、我们是 `censored`（默认链，见模块 docstring 差异 1）。
    """
    text = _strip_ext(str(number or "")).strip()
    if not text:
        return "censored", "empty"
    upper = text.upper()
    if _FC2_NUMBER.search(upper):
        return "fc2", "fc2"
    if _KIN8_NUMBER.search(upper):
        return "western", "kin8"
    if re.fullmatch(r"\d{6}[-_]\d{2,4}", upper):
        return "uncensored", "six-digit-catalog"
    if western_date(upper):
        return "western", "western-date"
    if _N_SERIES.match(upper):
        return "uncensored", "n-series"
    for prefix in UNCENSORED_PREFIXES:
        if upper.startswith(prefix.upper()):
            return "uncensored", f"prefix:{prefix}"
    if "SIRO" in upper or _SUREN_SHAPE.search(upper):
        return "amateur", "siro/suren-shape"
    for key in SUREN_PREFIXES:
        if upper.startswith(key.upper()):
            return "amateur", f"suren:{key}"
    if _MD_NUMBER.search(upper) and "MDVR" not in upper:
        return "chinese", "md"
    if _MKY_NUMBER.search(upper):
        return "chinese", "mky"
    if _CATALOG_NUMBER.search(upper):
        return "censored", "catalog"
    return "censored", "default"


def content_type(number: Any, *, dirs: Optional[Sequence[Any]] = None,
                 ) -> Tuple[str, str]:
    """最终内容类型：**目录关键词优先**（上游同序），其次番号形态。返回 `(类型, why)`。"""
    kind, why = type_from_path(*_dir_names(dirs))
    if kind:
        return kind, why
    return type_from_number(number)


def mosaic(number: Any, *, dirs: Optional[Sequence[Any]] = None,
           version_tags: Optional[Dict[str, Any]] = None,
           content: str = "") -> Tuple[str, str]:
    """马赛克标记：**破解 > 流出 > 无码**（上游硬约束，别重排）。返回 `(标记, why)`；判不出回 `("", "")`。

    三个来源，优先级就是列出的顺序：
    1. 番号里的词（`破解/克破/CRACKED` > `流出/LEAKED` > `無碼/无码/UNCENSORED`）；
    2. `version_tags.is_uncensored_leak`（`-U`/`-UC`，`emby.parse_av_number()` 给的既有口径）；
    3. 目录段名（从**最内层**往外找，段名整段相等才认）。
    都判不出才用 `content` 兜底（`fill_mosaic`）。
    """
    text = _strip_ext(str(number or "")).upper()
    if re.search(r"破解|克破|CRACKED", text):
        return "cracked", "name:cracked"
    if re.search(r"流出|LEAKED", text):
        return "leaked", "name:leaked"
    if re.search(r"無碼|无码|UNCENSORED", text):
        return "uncensored", "name:uncensored"
    tags = version_tags or {}
    if tags.get("is_uncensored_leak"):
        # `-U` / `-UC`：中文圈叫"无码流出"（模块 docstring 差异 2）
        return "leaked", "tags:-U"
    for name in reversed(_dir_names(dirs)):
        token = name.strip().strip(_DIR_BRACKET_STRIP).casefold()
        if token in MOSAIC_DIR_TOKENS:
            return MOSAIC_DIR_TOKENS[token], f"dir:{token}"
    filled = fill_mosaic(content)
    return (filled, f"fill:{content}") if filled else (MOSAIC_NONE, "")


def fill_mosaic(content: str, marked: str = "") -> str:
    """上游 `_fill_mosaic`：已有标记不覆盖；否则**有码类型 → censored、无码类型 → uncensored**，
    其它类型（国产/FC2/欧美/素人/里番）**留空** —— 它们的马赛克是另一回事，不该被硬套。"""
    if marked:
        return marked
    if content == "censored":
        return "censored"
    if content == "uncensored":
        return "uncensored"
    return MOSAIC_NONE


def detect_cd(number: Any, *, dirs: Optional[Sequence[Any]] = None) -> int:
    """分集号（1 起的整数；判不出回 0）。

    番号里的四条（上游同序）：`[-_.]CDn` → `[-_.]PARTn` → `-A/-B`（按字母）→ `-1..-9`（结尾）；
    正则都不中再看**直接父目录**是不是整段的 `CDn` / `PARTn`。
    """
    base = _strip_ext(str(number or "")).upper()
    found = re.search(r"[-_.]CD(\d{1,2})", base) or re.search(r"[-_.]PART(\d{1,2})", base)
    if found:
        return int(found.group(1))
    letter = re.search(r"-([AB])(?:\.|$)", base)
    if letter:
        return ord(letter.group(1)) - ord("A") + 1
    digit = re.search(r"-([1-9])$", base)
    if digit:
        return int(digit.group(1))
    for name in reversed(_dir_names(dirs)):
        whole = _CD_DIR.fullmatch(name.strip())
        if whole:
            value = int(whole.group(1))
            return value if value >= 1 else 0
    return 0


def definition(text: Any) -> str:
    """分辨率档位（判不出回空串）。`2160P` 归一成 `4K`；匹配在 `upper()` + `normalize_markers()` 之后。

    先大写是因为上游把它作用在 `basename.upper()` 上 —— 少了这一步，`1080p` / `4k` 这类小写写法
    会静默判不出来（真机文件名两种写法都有）。
    """
    normalized = normalize_markers(_strip_ext(str(text or "")).upper())
    for value, pattern in DEFINITION_MARKERS:
        if pattern.search(normalized):
            return value
    return ""


def classify(number: Any, *, dirs: Optional[Sequence[Any]] = None,
             version_tags: Optional[Dict[str, Any]] = None,
             name: str = "") -> Dict[str, Any]:
    """一次算全：`{content_type, mosaic, cd, definition, why}`（`why` 说明每条结论从哪来）。

    `name` 是"文件名/原始串"（比 `number` 更全，可能带后缀标记）；不给就用 `number`。
    调用方（目前是 `/scrape/status` 与 P0-1 的路由）拿它选链；**读侧只是展示时不必调**。
    """
    text = str(name or number or "")
    content, why_type = content_type(number, dirs=dirs)
    marked, why_mosaic = mosaic(text, dirs=dirs, version_tags=version_tags, content=content)
    tags = version_tags or {}
    resolution = str(tags.get("resolution") or "") or definition(text)
    return {
        "content_type": content,
        "mosaic": marked,
        "cd": detect_cd(number, dirs=dirs),
        "definition": resolution,
        "why": {"content_type": why_type, "mosaic": why_mosaic},
    }
