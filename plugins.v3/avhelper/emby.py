"""Emby 媒体库查询：判断番号是否已在库，供界面打「已入库」标记。

连接信息优先取插件配置；没配就复用 MoviePilot「设置 → 媒体服务器」里已启用的 Emby
（官方 SDK `app.sdk.services.MediaServerHelper`），不额外维护一份密钥。

实现要点：
- 一次 HTTP 取回整个 JAV 库的条目（本环境 93 条），按归一化番号建索引，之后是字典命中；
- 索引在内存里缓存 5 分钟，失败负缓存 2 分钟；媒体库不通只是没有标记，不影响插件其它功能；
- 番号来源按可靠性排序：`ProviderIds.MetaTube`（MetaTube 刮削写入，最准）→ 文件名开头 → 标题开头；
- 任何异常都静默降级成空索引（界面就当没有这个功能，用户要求「没有就什么都不显示」）。
"""

from __future__ import annotations

import base64
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.logging import logger
from app.sdk.network import RequestUtils

TTL_OK = 300          # 索引缓存 5 分钟
TTL_FAIL = 120        # 失败负缓存 2 分钟（媒体库重启期间不反复打）
TIMEOUT = 6           # 单次请求超时，媒体库不通时不能拖住界面
PAGE = 500            # 分页大小
MAX_ITEMS = 20000     # 单库索引上限，防异常大库吃内存

# 认库依据：库名或库路径里出现 jav / 9kg / avi（常见命名习惯）。
# 一个都命中不了时 `pick_libraries()` 会退回全部「电影」类型库，所以自定义库名也能用。
_JAV_HINT = re.compile(r"(?:^|[^a-z0-9])(?:jav|9kg|avi)(?:[^a-z0-9]|$)", re.I)
_FC2 = re.compile(r"FC2[-_ ]*PPV[-_ ]*(\d{3,8})", re.I)
_LEAD = re.compile(r"^([A-Za-z]{2,6}\d?[-_ ]?\d{2,7})")


# ---------- v4 番号解析（契约 §3.1 / D1 / D12）----------
#
# 与上面那套旧口径的关系：`norm_key()` **一个字节都不改**（D1）——它是 `downloads`/`known`
# 台账主键与前端 `downloadHistory.normKey()` 的对齐口径，「保留后缀」（`IPZZ-912-UC` →
# `IPZZ912UC`）是它的既定语义。新层要的是**干净号**（`IPZZ912`），那由下面的
# `parse_av_number().norm_key` 给，跨层匹配统一走 `canon_key()`。

# 版本后缀里出现的画质词（`D18` 之外的第一版口径，来自真实文件名：`CAWD-989_4K`、`MIDV-946 中字`）。
_VERSION_RES = {"4k": "4K", "8k": "8K", "fhd": "FHD", "hd": "HD", "sd": "SD"}
# ⚠️ `mp4` 这类**媒体扩展名**也必须在表里：老台账键（如 `IPZZ58624K` 旁边的 `xxx.mp4`）
# 会把扩展名当「分隔符 + 两字母版本号」再剥一层，剥不掉就会掉进 `_BODY_LOOSE`，
# 而那个形态只留给「前缀以数字开头」的写法。剥掉之后主体形态才认得出来。
_VERSION_MEDIA = {
    "mp4": "mp4", "mkv": "mkv", "avi": "avi", "wmv": "wmv", "mov": "mov",
    "m4v": "m4v", "rmvb": "rmvb", "rm": "rm", "flv": "flv", "mpg": "mpg",
    "mpeg": "mpeg", "ts": "ts", "iso": "iso", "strm": "strm",
}
# 后缀关键词 → `version_tags` 里的布尔位。顺序即匹配优先级。
_VERSION_WORDS = {
    "uc": "is_zh_sub",          # 无码流出（uncensored leak）同时也是中字来源
    "leak": "is_uncensored_leak",
    "无码": "is_uncensored_leak",
    "流出": "is_uncensored_leak",
    "中字": "is_zh_sub",
    "中文字幕": "is_zh_sub",
    "字幕": "is_zh_sub",
    "vr": "is_vr",
    **_VERSION_MEDIA,
}
# ★ 这些词**同时**点亮两个位（实测样本 `IPZZ-912-UC`：既有中字又是流出，契约 §3.1 的
#   `is_zh_sub` 与 `is_uncensored_leak` 都断言 True）。
_VERSION_WORD_BOTH = {"uc": ("is_zh_sub", "is_uncensored_leak")}

# 版本后缀形态（**按顺序循环剥，直到剥不动为止** —— 真实文件名会叠加 `-UC_4K` 这种）：
#   1. 分隔符 + 纯数字     → `part_no`（`-CD2` / `_4K` 里的 `4` 也是这个形态，由第 3 条抢先生效）
#   2. 纯字母关键词        → 画质 / 中字 / 流出 / VR
#   3. `CD`/`Part`/`Disc` + 数字 → `part_no`
#   4. 分隔符 + 1–2 个字母 → `edition`（`IPOK-025L` 的 `L`、`MIRD-277-C` 的 `C`）
#      ⚠️ 第 4 条的字母必须先试关键词（第 2 条），否则 `-UC` 会被当成「版本号 U + C」。
_VERSION_SUFFIX = re.compile(
    r"(?:"
    r"(?:[-_\s]+\d(?![0-9A-Za-z]))"
    r"|(?:(?<![A-Za-z])(?:4K|8K|FHD|HD|SD|VR|UC|LEAK|中字|中文字幕|字幕|无码|流出)(?![A-Za-z0-9]))"
    r"|(?:[-_\s]*(?:CD|PART|DISC)\d{1,2}(?![0-9]))"
    # 版本字母：1 个字母可以紧跟数字（`IPOK-025L` 的 L），2 个字母必须落在分隔符之后
    # ——否则 `IPOK-025L` 会被切成 `5L`、`FC2-PPV-…` 会被切成 `-PPV`。
    # 单字母只要求前面不是字母（数字可以紧跟）：`-UC` 仍由上面的关键词分支先吃掉。
    r"|(?:[-_\s]+[A-Za-z]{1,2}(?![A-Za-z0-9])|(?<![A-Za-z])[A-Za-z](?![A-Za-z0-9]))"
    r")\s*$",
    re.I,
)
_VERSION_KEYWORD = re.compile(
    r"(?:^|[-_\s])(4K|8K|FHD|HD|SD|VR|UC|LEAK|中字|中文字幕|字幕|无码|流出)\s*$", re.I)
_VERSION_PART = re.compile(r"(?:^|[-_\s])(?:CD|PART|DISC)(\d{1,2})\s*$", re.I)

# 后缀关键词的**兜底**扫描：后缀循环只吃紧邻结尾的那一个，`MIDV-946-UC_4KD` 这种怪写法会漏；
# 这里按整个字符串再扫一遍（同样要求前后不是字母数字，避免误伤 `HDD` / `4Koma` 这类词）。
_VERSION_WORD_SCAN = re.compile(
    r"(?<![A-Za-z0-9])(4K|8K|FHD|HD|SD|VR|UC|LEAK|中字|中文字幕|字幕|无码|流出)(?![A-Za-z0-9])", re.I)
_ZH_SUB_ONLY = re.compile(
    r"(?<![A-Za-z0-9])(?:中字|中文字幕|-C(?![A-Za-z0-9]))", re.I)

# 扩展名（只认媒体扩展名；**不能**用 `splitext` 无脑切 —— `MIDV-946.jp` 的 `.jp` 会
# 把 `P` 这个版本字母一起吃掉，而 `.4K` 这种「点分后缀」本来就要留给后缀循环去剥）。
_MEDIA_EXT = re.compile(r"\.(iso|mp4|mkv|avi|wmv|mov|m4v|ts|rmvb|rm|flv|mpg|mpeg|strm)$", re.I)

# 站点前缀 / 域名水印：`[Thz.la]SSIS-001-C.mp4`、`hhd800.com@MIDV-946.mp4`。
_SITE_PREFIX = re.compile(r"^\s*(?:\[[^\]]{1,40}\]|\([^)]{1,40}\)|【[^】]{1,40}】)\s*")
_DOMAIN_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{2,40}\.[A-Za-z]{2,6}[@_\-]+")

# FC2 单列一条解析路径（D12）：`PPV` 是规范键的一部分，**不能**走通用后缀循环
# ——`FC2-PPV-1234567` 的 `-PPV` 形态上就是个「分隔符 + 两字母版本号」，会被误剥。
_FC2_BODY = re.compile(r"^FC2[-_\s]*PPV?[-_\s]*(\d{3,8})$", re.I)

# 结尾的「连字符/空格 + 版本字母」由 `_VERSION_SUFFIX` 的第 4 条分支负责匹配，
# 语义（`L`=版本 / `-C`=中字 / 裸字母=略过）由 `_single_letter_tag()` 按**有没有分隔符**判定。

# 主体形态（兜底）：**数字打头**的写法（`1PONDO-123` / `1PONDO123`）。那三段 `[A-Za-z]`
# 是**硬性要求** —— 它保证这条只吃「字母数字混合」的前缀，把**纯数字串**挡在门外：
# `12598`（SNOS-380 的 Emby 实例 id）、`11311`（JAV 库 id）、`007`、`2026` 一律
# `matched=False`。认成番号就会被拿去查站点、或写进 `ProviderIds.AVHelper`（S11/S7 实测）。
_BODY_LEAD_DIGIT = re.compile(r"^(\d[A-Za-z0-9]{0,4}[A-Za-z])[-_ ]?(\d{2,7})$")
# 主体形态（首选）：**字母打头的前缀** + 数字段。前缀里那个 `\d?` 必须**懒匹配**，否则
# 「前缀吃掉一位数字」会把数字段截短：`SSIS001` 变成 `SSIS0`+`01` → 键 `SSIS01`（错），
# 正确是 `SSIS`+`001` → `SSIS1`。`DAS-123` 完全没有数字前缀，`\d?` 为空，不受影响。
_BODY_NUM = re.compile(r"^([A-Za-z]{2,8}\d??)[-_ ]?(\d{2,7})$")


def _prefix_ok(prefix: str) -> bool:
    """前缀必须是「≥2 个字母、≤1 位数字」的形态。

    真实番号前缀从不写成纯数字（那是 Emby 实例 id / 库 id），带数字的都是
    `1PONDO`（6 字母 + 1 位数字）这类形态。
    """
    text = str(prefix or "")
    letters = sum(1 for ch in text if ch.isalpha())
    digits = sum(1 for ch in text if ch.isdigit())
    return letters >= 2 and digits <= 1


def _body_ok(body: str, prefix: str, digits: str) -> bool:
    """主体形态的**有歧义时从严**判定。

    只有一种写法有歧义：**前缀与数字段之间没有分隔符，且前缀里没有数字**（`hhd800`）。
    这种「字母直接接数字」的写法里切分点完全靠猜，所以要求**前缀至少 4 个字母**
    —— `hhd800` 是域名 `hhd800.com` 剥掉 `.com@` 后的残段（3 字母，被挡），
    而真番号写成一整串时前缀都够长（`SSIS001`、`MIDV946`、`ABCDEF123`）。

    有分隔符（`IPZZ-912`）或前缀本就带数字（`1PONDO123`）时切分点是明确的，不适用这条。
    """
    prefix = str(prefix or "")
    if re.match(r"^[A-Za-z]{2,8}[-_ ]", body) or re.search(r"\d", prefix):
        return True
    return len(re.findall(r"[A-Za-z]", prefix)) >= 4


@dataclass
class ParsedNumber:
    """`parse_av_number()` 的返回：干净展示番号 + 规范键 + 版本角标。

    `display_number` 是**用户看得见的写法**（`IPZZ-912`，数字段不足 3 位补零、超过保持原样）；
    `norm_key` 是跨层匹配键（前缀 + 去前导零的整数，`IPZZ912`）；
    `version_tags` 只放「确实出现过」的键（没有版本后缀时是空字典，不是一堆 False）；
    `matched=False` 表示压根儿没解析出番号形态（调用方必须按「认不出」处理，别拿空串当键）。
    """

    raw: str = ""
    display_number: str = ""
    norm_key: str = ""
    version_tags: Dict[str, Any] = field(default_factory=dict)
    matched: bool = False


def _single_letter_tag(letter: str, sep: bool) -> str:
    """结尾的单个版本字母归哪个位：`L`→版本；分隔符后的 `C`→中字、`U`→流出、`D`→4K；裸字母→略过。

    取值依据（实测样本）：`IPOK-025L.iso` 是「L 版」（契约硬用例要 `edition="L"`）；
    `[Thz.la]SSIS-001-C.mp4` 与 `MIRD-277-C.mp4` 都是中字版（硬用例要 `is_zh_sub=True`）。
    不认识、也判不出来的裸字母（`SSIS-001X` 这种）**不猜** —— 返回空串，只把它从番号上剥掉。
    """
    text = str(letter or "").upper()
    if text == "L":
        return "edition"                        # `IPOK-025L`：L 版（契约硬用例）
    if not sep:
        return ""
    if text == "C":
        return "is_zh_sub"
    if text == "U":
        return "is_uncensored_leak"
    if text == "D":
        return "resolution"
    return ""


def _set_tag(tags: Dict[str, Any], name: str, value: Any) -> None:
    """写一个角标位（后写的不覆盖已有的非空值，同一位被两个后缀命中时以先到的为准）。"""
    if not name:
        return
    if name == "part_no":
        try:
            tags[name] = int(value)
        except (TypeError, ValueError):
            return
        return
    if tags.get(name):
        return
    tags[name] = value


def _apply_word(tags: Dict[str, Any], word: str) -> None:
    """把后缀关键词落到角标位上（媒体扩展名只用于「剥掉」，本身不是角标，所以落位时跳过）。"""
    text = str(word or "").strip().lower()
    for name in _VERSION_WORD_BOTH.get(text, ()):
        tags[name] = True
    if text in _VERSION_RES:
        _set_tag(tags, "resolution", _VERSION_RES[text])
    flag = _VERSION_WORDS.get(text)
    if flag and text not in _VERSION_MEDIA:
        _set_tag(tags, flag, True)


def _display_digits(digits: str) -> str:
    """数字段 → 展示用写法：**先转 int 再补零到 3 位**（`f"{int(digits):03d}"`）。

    ⚠️ 这是**丢数据**级别的口径，别改成「保留原始串、不足 3 位才补零」：
    真实文件名里有多余前导零（`ipzz00586_1_4K.mp4`、`MIDV-0946.mp4`），保留就会产出
    `IPZZ-00586` / `MIDV-0946` —— 拿它去 javdb 查**直接「找不到番号」**（S11 全库实测），
    而 `IPZZ-586` / `MIDV-946` 立刻命中。所以：多余的前导零一律去掉，不足 3 位才补
    （`CAWB-040`→`040`、`SSIS-001`→`001`，`IPZZ-912`→`912`，`MIDV-0946`→`946`）。
    """
    try:
        value = int(str(digits or "0"))
    except (TypeError, ValueError):
        return str(digits or "")
    return f"{value:03d}"


def _read_suffix(tail: str, tags: Dict[str, Any]) -> bool:
    """识别并记下一个被匹配到的版本后缀；返回「认得出」= 可以放心从番号上剥掉。

    **认不出就不许剥**：`136.1280x720` 里的 `.1280` 也符合「分隔符 + 数字」的形态，
    但它是分辨率的一部分，剥掉会把番号截成 `136`（认不出 → 整个解析失败）。
    所以「裸数字段」只在两种情况下算碟号：前面有分隔符（`IPZZ-912-2`），
    或者写明了 `CD`/`Part`/`Disc` 前缀（`MIDV-946-CD2`）。
    """
    text = str(tail or "").strip()
    lowered = text.lower()

    keyword = _VERSION_KEYWORD.search(text)
    if keyword:
        _apply_word(tags, keyword.group(1))
        return True

    part = _VERSION_PART.search(text)
    if part:
        _set_tag(tags, "part_no", part.group(1))
        if lowered.endswith("k"):                       # `_4K` / `_8K`：数字是画质不是碟号
            _set_tag(tags, "resolution", text.upper())
        return True

    if lowered.endswith(("4k", "8k")) and re.search(r"[-_\s]\d+[kK]$", lowered):
        _set_tag(tags, "resolution", text.upper())
        return True

    # 版本字母：`-C`（分隔符 + 单字母，中字）或 `025L` 这种**紧贴数字的裸版本号**。
    # 两种写法语义不同，所以要分别把「裸字母」与「分隔符版」各匹配一次（紧跟数字的 `5L`
    # 不算分隔符版，它由下面那条裸字母规则接住）。
    bare = re.search(r"(?<![A-Za-z0-9])([A-Za-z]{1,2})$", text)
    spaced = re.search(r"[-_\s]([A-Za-z]{1,2})$", text)
    if bare or spaced:
        if spaced:
            letter, sep = spaced.group(1), True
        else:
            letter, sep = bare.group(1), False
        name = _single_letter_tag(letter, sep)
        if name == "is_zh_sub":                         # `-C`：中字的常见简写
            tags["is_zh_sub"] = True
        elif name == "is_uncensored_leak":              # `-U`：流出（顺带中字）
            tags["is_uncensored_leak"] = True
            tags["is_zh_sub"] = True
        elif name:
            _set_tag(tags, name, letter.upper())
        return True

    digit = re.match(r"^[-_\s]+(\d)$", text)
    if digit:
        # 裸数字段**只收 1 位**：
        #   * `IPZZ-912-2` 的 `-2` 是碟号，要收；
        #   * `IPZZ-912` 的 `-912` 是番号自己，**不能**收（否则剥出个光秃秃的 `IPZZ`）；
        #   * `hhd800` 的 `-800` 是站点域名残段（`hhd800.com` 剥掉 `.com@` 之后剩的），
        #     收了就会把尾巴当碟号、把前缀剥成 `HHD` → 产出假番号。
        # 三者的区别只在位数，所以这条卡在 1 位最安全（2 位以上的碟号写 `CD2`/`Part2`）。
        _set_tag(tags, "part_no", digit.group(1))
        return True

    if re.match(r"^(?:CD|PART|DISC)\d{1,2}$", text, re.I):
        _set_tag(tags, "part_no", re.sub(r"\D", "", text))
        return True
    return False


def _strip_suffixes(text: str) -> Tuple[str, Dict[str, Any]]:
    """循环剥版本后缀，返回 `(主体, 角标)`（顺序与理由见 `_VERSION_SUFFIX` 的注释）。

    两道刹车，都是为了「宁可解析得保守，也不要截出一个错的番号」：

    - 只剥 `_read_suffix()` 认得出的那一层；认不出就停手，整串留给主体形态去匹配；
    - 剥完必须还**剩得下主体**（≥3 字符）：`SNOS-380` 的 `-380` 形态上完全符合「分隔符+数字」，
      没有这道闸就会把番号自己当后缀剥掉，出来一个光秃秃的 `SNOS`。
    """
    tags: Dict[str, Any] = {}
    body = text
    for _ in range(12):                     # 上限防病态输入打转；正常至多叠两三层
        stripped = body.rstrip("-_ .·")
        suffix = _VERSION_SUFFIX.search(stripped)
        if not suffix:
            if stripped == body:
                break
            body = stripped
            continue
        head = stripped[:suffix.start()].rstrip("-_ .·")
        # 剩下的必须是**还带数字的番号主体**：`SNOS-380` 的 `-380` 形态上完全符合
        # 「分隔符+数字」，没有这道闸就会把番号自己当后缀剥掉，出来一个光秃秃的 `SNOS`。
        if len(head) < 3 or not re.search(r"\d", head):
            body = stripped
            break
        if not _read_suffix(suffix.group(0), tags):
            body = stripped                 # 认不出 → 不再往下剥，交给主体形态
            break
        body = head
    return body, tags


def _normalize_tags(tags: Dict[str, Any]) -> Dict[str, Any]:
    """补全角标（`UC` 必然是中字+流出；单/双字母后缀也判一次），键值按契约 §3.1 固定形状。"""
    out: Dict[str, Any] = {}
    out["is_zh_sub"] = bool(tags.get("is_zh_sub"))
    out["is_uncensored_leak"] = bool(tags.get("is_uncensored_leak"))
    out["resolution"] = str(tags.get("resolution") or "")
    part = tags.get("part_no")
    out["part_no"] = int(part) if str(part or "").strip().isdigit() else 0
    out["edition"] = str(tags.get("edition") or "")
    out["is_iso"] = bool(tags.get("is_iso"))
    out["is_vr"] = bool(tags.get("is_vr"))
    return out


def _has_tags(tags: Dict[str, Any]) -> bool:
    """角标里有没有「实测出现过」的东西（空字典 = 干净裸番号，用例 `test_plain` 这么断言）。"""
    return any(bool(value) for value in (tags or {}).values())


def parse_av_number(raw_text: Any) -> ParsedNumber:
    """从文件名 / 路径 / 标题 / 台账番号里解析出规范番号与版本角标（契约 §3.1 + v4.1 §5.1）。

    三步走（每一步都为了消化真实世界里的一种写法）：

    1. **预处理**：统一分隔符 → 去掉路径、站点前缀（`[Thz.la]`）、域名水印（`hhd800.com@`）
       → 切掉媒体扩展名（`.iso` 记为 `is_iso`）；
    2. **循环剥版本后缀**：`-UC_4K`、` 中字`、`-CD2`、`.iso` 的 `L` 版……一个循环剥一层，
       直到剥不动为止（**不是**只剥一个后缀 —— 真实样本 `SONE-561-UC_4K.mp4` 要同时得到
       中字/流出/4K 三个角标）；
    3. **生成两个键**：`display_number`（前缀 + `-` + 数字段，不足 3 位补零、超过保持原样）与
       `norm_key`（前缀 + 去前导零的整数）。

    FC2 按其规范形态单独处理（D12）：`FC2-PPV-1234567` / `FC2PPV1234567` 两种写法都归到
    **`FC2PPV{int}`**（保留 `PPV` 段 —— 线上台账与 MetaTube 的 ProviderIds 都是这个口径）。

    认不出番号形态时返回 `matched=False` 的空结果：**绝不**把「翻译说明」这类文本的
    字符残渣当番号（宁可什么都不显示，也不要猜成另一部片）。
    """
    raw = "" if raw_text is None else str(raw_text)
    parsed = ParsedNumber(raw=raw)
    text = raw.strip().replace("\\", "/")
    if not text:
        return parsed

    tags: Dict[str, Any] = {}
    text = text.rsplit("/", 1)[-1]              # 去掉路径，只留文件名
    while True:                                 # 循环剥前缀/水印（可能叠着写）
        before = text
        text = _SITE_PREFIX.sub("", text)
        text = _DOMAIN_PREFIX.sub("", text)
        text = text.strip()
        if text == before:
            break
    ext = _MEDIA_EXT.search(text)
    if ext:
        text = text[:ext.start()]
        if ext.group(1).lower() == "iso":
            tags["is_iso"] = True
    text = text.strip()
    if not text:
        return parsed

    # FC2 先行（D12）：`FC2-PPV-1234567` / `FC2PPV1234567` / `FC2PPV 1234567` 三种写法
    # 都归到 `FC2PPV{int}`（**保留 PPV 段** —— 线上台账与 MetaTube ProviderIds 都是它）。
    # 必须在通用后缀循环**之前**判定，否则 `-PPV` 会被当成版本号剥掉。
    fc2 = _FC2_BODY.match(text)
    if fc2:
        digits = fc2.group(1)
        parsed.display_number = f"FC2-PPV-{int(digits)}"
        parsed.norm_key = f"FC2PPV{int(digits)}"
        parsed.matched = True
        for word in _VERSION_WORD_SCAN.findall(text):
            _apply_word(tags, word)
        parsed.version_tags = _normalize_tags(tags) if _has_tags(tags) else {}
        return parsed

    body, suffix_tags = _strip_suffixes(text)
    for name, value in suffix_tags.items():
        _set_tag(tags, name, value)
    body = body.strip(" -_.")
    if not body:
        return parsed

    # 四种主体形态，按可信度依次试；**四种都要求前缀里有 ≥2 个字母**。
    # 最后一条是硬约束：纯数字串（`12598` = Emby 实例 id、`11311` = 库 id）**绝不许**被当番号
    # —— 认成番号就会被拿去查站点、或写进 `ProviderIds.AVHelper`（S11/S7 实测的真实后果）。
    prefix, digits = "", ""
    mixed = re.match(r"^([A-Za-z]{2,8}\d?)(\d{1,6})(\d)(4K|8K)$", body, re.I)
    if mixed:
        # 老台账键把「分辨率」直接贴在数字段上（旧口径剥剩的 `IPZZ58624K`）：末尾那个 `4`
        # 到底属于番号还是属于 `4K`，字面上**判不出来**，所以两个都留着 ——
        # `norm_key` 用全部数字（`IPZZ5862`），`display_number` 少一位（`IPZZ-586`）。
        # 宁可显示得怪一点，也不要悄悄抹掉一位数字（那等于换了一部片）。
        prefix = mixed.group(1).upper()
        _set_tag(tags, "resolution", mixed.group(4).upper())
        parsed.display_number = f"{prefix}-{_display_digits(mixed.group(2))}"
        parsed.norm_key = f"{prefix}{int(mixed.group(2) + mixed.group(3))}"
    else:
        hit = _BODY_NUM.match(body) or _BODY_LEAD_DIGIT.match(body)
        if (not hit or not _prefix_ok(hit.group(1))
                or not _body_ok(body, hit.group(1), hit.group(2))):
            return parsed
        prefix, digits = hit.group(1).upper(), hit.group(2)
        parsed.display_number = f"{prefix}-{_display_digits(digits)}"
        parsed.norm_key = f"{prefix}{int(digits)}"

    # 角标兜底扫描：只认「前后不是字母数字」的词，避免把 `HDD`、`4Koma` 这种词误判成角标。
    for word in _VERSION_WORD_SCAN.findall(text):
        _apply_word(tags, word)
    if "中字" in text or _ZH_SUB_ONLY.search(text):
        tags["is_zh_sub"] = True
    parsed.matched = True
    parsed.version_tags = _normalize_tags(tags) if _has_tags(tags) else {}
    return parsed


def canon_key(text: Any) -> str:
    """跨层匹配用的**规范键**（契约 D1）：能解析出番号就用 `parse_av_number().norm_key`，
    解析不出退回旧口径 `norm_key()`，**绝不返回空串**（调用方拿它当查询键）。

    新层（元数据 / 库索引 / 台账对账）一律用它；`downloads`/`known` 的历史键仍是 `norm_key()`，
    两层靠 `EmbyLibrary._item_keys()` 的「两套键都留」搭桥。
    """
    parsed = parse_av_number(text)
    if parsed.matched and parsed.norm_key:
        return parsed.norm_key
    return norm_key(text)


def norm_key(text: Any) -> str:
    """番号归一化：去掉非字母数字、统一大写，并抹掉数字段的前导零。

    `MIDV-946` / `midv00946` / `MIDV-946-UC` → `MIDV946UC`；`FC2-PPV-1234567` → `FC2PPV1234567`。
    javdb 的番号与 Emby 里的文件名、MetaTube 刮削 id 写法各不相同，必须先归一化再比。

    ⚠️ 后**缀**（`-UC` 这种）不会被丢掉 —— 只抹数字段的前导零（原 docstring 写成 `MIDV946` 是错的，
    2026-10-11 由前端那条线实测指出；台账主键、`_download_keys()` 与前端 `downloadHistory.normKey()`
    都按这个"保留后缀"的口径对齐）。
    """
    raw = re.sub(r"[^0-9A-Za-z]", "", str(text or "")).upper()
    if not raw:
        return ""
    return re.sub(r"0*(\d+)", lambda m: str(int(m.group(1))), raw)


# 归一化番号键 → 展示番号（`IPZZ961` → `IPZZ-961`、`FC2PPV1234567` → `FC2-PPV-1234567`）。
# 设计稿给的是 `^([A-Z]{2,6}\d?)(\d{2,7})$`，但那个 `\d?` 贪婪，会把数字段的第一位抢进前缀：
# `IPZZ961` 切成 `IPZZ9` + `61`（`MIDV946` → `MIDV9-46`）——只有数字段正好 2 位时才靠回溯碰对。
# 去掉 `\d?` 后**能匹配的键集合完全不变**，只是切分点回到设计文档 §2 自己举的例子（`IPZZ-961`）。
_DISPLAY_NUM = re.compile(r"^([A-Z]{2,6})(\d{2,7})$")
_DISPLAY_FC2 = re.compile(r"^FC2PPV(\d+)$")


def display_number(key: Any) -> str:
    """归一化番号键 → 展示用番号（`IPZZ961` → `IPZZ-961`、`FC2PPV1234567` → `FC2-PPV-1234567`）。

    只用于「Emby 索引里只有文件名与 MetaTube 刮削 id（归一化后是 `IPZZ961` 这种无连字符写法）」
    的场合。拼不出来（`SSIS1` 数字段只有一位、`1PONDO123` 前置数字）就**原样返回键** ——
    宁可显示得怪一点，也不要猜成另一个番号（猜错会让人以为这是另一部片）。

    2026-10-12 从 `__init__.py` 搬到这里：与 `norm_key()` 是同一套番号口径的两半，
    放一处才不会漂；顺带让「Emby 库 → 界面行」（`library_rows()`）能脱离宿主单测。
    """
    text = str(key or "").strip().upper()
    fc2 = _DISPLAY_FC2.match(text)
    if fc2:
        return f"FC2-PPV-{fc2.group(1)}"
    plain = _DISPLAY_NUM.match(text)
    if plain:
        return f"{plain.group(1)}-{plain.group(2)}"
    return str(key or "")


def shown_number(key: Any, name: Any = "") -> str:
    """展示番号：**优先用库条目 Name 开头那一段原始写法**，退回 `display_number(key)`。

    为什么需要它：`norm_key()` 会抹掉数字段的前导零（`CAWB-040` → `CAWB40`），从键反推展示番号
    就成了 `CAWB-40` —— 与用户在 Emby / javdb 上看到的写法对不上（真机 109 条里 31 条如此）。
    Emby 条目的 `Name` 是 MetaTube 刮削写进去的原始番号写法，最权威。

    但只用它与键**归一化后相等**的那一种（`norm_key(lead) == key`）：对不上宁可按老规则显示，
    也不猜 —— 猜错会让人以为这是另一部片（`display_number()` 的注释里说过同一条纪律）。
    """
    lead = _LEAD.match(str(name or ""))
    if lead:
        candidate = lead.group(1).strip()
        if candidate and norm_key(candidate) == str(key or ""):
            return candidate
    return display_number(key)


def key_rank(key: str) -> Tuple[int, int, str]:
    """归一化番号键的「干净程度」排序键（小者优先），用于给一部片挑主键。

    同一部片在 Emby 里会有多个键：`SNOS192`（文件名/刮削 id 的基础号）与 `SNOS192C`（中字版）、
    `IPZZ8224K`（4K 版）。一部片只能显示一个番号，挑哪个？规则：

    1. **能拼出规范番号**的优先（`IPZZ961` 能拼成 `IPZZ-961`，`SNOS192C` 拼不出）；
    2. 其次**短**的优先（基础号比带后缀的短）；
    3. 最后按字典序，保证同一份索引每次挑出同一个键（列表与台账才不会今天一个明天一个）。
    """
    text = str(key or "")
    canonical = 0 if (_DISPLAY_NUM.match(text.upper()) or _DISPLAY_FC2.match(text.upper())) else 1
    return (canonical, len(text), text)


def best_keys(index: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """库索引 → `条目 id → 主键`（同一部片的多个键在这里收敛成一个）。

    键的顺序就是**索引的顺序**（`_build()` 按 Emby 的 `DateCreated` 倒序抓，所以是入库时间新→旧），
    调用方据此得到"最近入库的排在前面"，不必自己排序。
    """
    best: Dict[str, str] = {}
    for key, entry in (index or {}).items():
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id") or "") or key
        current = best.get(item_id)
        if current is None or key_rank(key) < key_rank(current):
            best[item_id] = key
    return best


def library_rows(index: Dict[str, Dict[str, Any]],
                 thumbs: Optional[Dict[str, str]] = None,
                 actors: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Emby 库索引 → 界面卡片行（`/library` 的 `items[]`，契约 §4）。

    纯函数（不发请求、不碰库），输入是 `EmbyLibrary.index()` 那份「归一化番号 → 条目」：

    - 一部片一行：先按条目 id 归并（`best_keys()`），否则同一部片会按刮削 id / 文件名 / 标题
      列成好几行（本机实测按键展开 148 个 vs 库里 109 条）；
    - `number` 是 `shown_number(主键, Name)`（优先用 Name 里的原始番号写法，见它的说明）；
      `title` / `path` / `url` 取 Emby 条目的 Name/Path/URL；
    - `thumb` / `actor` 由调用方从**本地索引**查好传进来（`thumbs` / `actors` 的键允许同时给
      「展示番号」「Name 里的原始番号」「归一化键」几种写法，几个都试）—— 这里不发网络请求，也不读缓存文件；
    - `id` 故意留空：契约里 `movie.id` 是 **javdb 内部 id**（详情抽屉回传给 `/detail` 省一次解析），
      这里手上只有 Emby 的条目 id，塞进去会让 `/detail` 去 javdb 找一个不存在的 id；
    - `addedAt` 是入库时间（Emby 的 `DateCreated` → 本地时间写法），解析不出来是空串，
      界面自己决定要不要画那一行。
    """
    thumbs = thumbs or {}
    actors = actors or {}
    rows: List[Dict[str, Any]] = []
    for item_id, key in best_keys(index).items():
        entry = index.get(key) or {}
        shown = shown_number(key, entry.get("name"))
        fallback = display_number(key)

        def pick(table: Dict[str, str]) -> str:
            """三种写法依次试：Name 原始番号 → 从键反推的展示番号 → 归一化键。"""
            for candidate in (shown, fallback, key):
                hit = str(table.get(candidate) or "")
                if hit:
                    return hit
            return ""

        rows.append({
            "number": shown,
            "title": str(entry.get("name") or ""),
            # 库列表里没有 javdb 的发行日 / 时长 / 磁力（那要先抓一遍详情），一律留空，
            # 由卡片按"库卡片"的样子渲染（`NumCard` 的 `mode="library"`）。
            "cover": "",
            "thumb": pick(thumbs),
            "date": "",
            "duration": 0,
            "cnsub": False,
            "uncensored": False,
            "magnets": 0,
            "maker": "",
            "score": "",
            "actor": pick(actors),
            "actor_avatar": "",
            "id": "",
            "lib": {
                "id": item_id,
                "name": str(entry.get("name") or ""),
                "path": str(entry.get("path") or ""),
                "url": str(entry.get("url") or ""),
            },
            "addedAt": emby_time_text(entry.get("created")),
        })
    return rows


def emby_time_text(value: Any) -> str:
    """Emby 的 `DateCreated`（UTC ISO，如 `2026-10-05T04:34:56.0000000Z`）→ 本地 `YYYY-MM-DD HH:MM:SS`。

    解析不出来返回空串：界面上空值显示「—」，总好过拿"列表生成当天"冒充入库时间。
    Emby 的小数位是 7 位（Python 3.11 的 `fromisoformat` 只吃 1–6 位），先截到 6 位；
    `Z` 结尾按 UTC 处理再转本地时区（插件与 Emby 同机，两个时区通常一致，但不假设）。
    """
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if stamp.tzinfo is not None:
        stamp = stamp.astimezone()
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


def mp_emby_conf() -> Tuple[str, str]:
    """从 MoviePilot 媒体服务器配置里取第一个已启用的 Emby（host, apikey）。

    取不到返回两个空串，调用方按「没有媒体库」处理。
    """
    try:
        from app.sdk.services import MediaServerHelper

        for conf in (MediaServerHelper().get_configs() or {}).values():
            if str(getattr(conf, "type", "") or "").lower() != "emby":
                continue
            cfg = getattr(conf, "config", None) or {}
            host = str(cfg.get("host") or "").strip()
            apikey = str(cfg.get("apikey") or "").strip()
            if host and apikey:
                return host, apikey
    except Exception as error:
        logger.error(f"AVHelper 读取 MoviePilot 媒体服务器配置失败：{error}")
    return "", ""


def pick_libraries(folders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """挑要索引的媒体库：优先 JAV 类库（名字或路径命中），没有才退回全部「电影」库。"""
    jav = [f for f in folders if _looks_jav(f)]
    if jav:
        return jav
    return [f for f in folders if str(f.get("CollectionType") or "") == "movies"]


def _looks_jav(folder: Dict[str, Any]) -> bool:
    """库名或库路径是否像 JAV 库。"""
    text = " ".join([str(folder.get("Name") or "")]
                    + [str(x) for x in (folder.get("Locations") or [])])
    return bool(_JAV_HINT.search(text))


def _file_stem(path: str) -> str:
    """取文件名的去扩展名部分（路径可能是 Windows 反斜杠写法）。"""
    stem = str(path or "").replace("\\", "/").rsplit("/", 1)[-1]
    dot = stem.rfind(".")
    return stem[:dot] if dot > 0 else stem


def _text_keys(text: str) -> List[str]:
    """从一段文本（文件名 / 标题）里抽出可能的番号键。"""
    if not text:
        return []
    keys: List[str] = []
    fc2 = _FC2.search(text)
    if fc2:
        keys.append(norm_key("FC2PPV" + fc2.group(1)))
    lead = _LEAD.match(text)
    if lead:
        keys.append(norm_key(lead.group(1)))
    if len(text) <= 16:            # 短名整体也当候选（如「SSIS001」「ipx-001」）
        keys.append(norm_key(text))
    return keys


def _item_keys(item: Dict[str, Any]) -> List[str]:
    """一条 Emby 条目的全部候选番号键（去重保序，**两套口径都留**）。

    `IPZZ-912-UC.mp4` 这条路径会同时产出两个键，它们是同一部片的两种写法：

    - 旧口径 `norm_key()` → `IPZZ912UC`（保留后缀；`downloads`/`known` 台账与前端
      `downloadHistory.normKey()` 都按它对齐，**不能**丢）；
    - 新口径 `canon_key()` → `IPZZ912`（干净号；v4 刮削层的 `media_item.key` 用它）。

    两个都留在同一个索引里，`lookup()` 就能任一种写法命中同一部片；`best_keys()` 仍按
    `key_rank()` 挑主键，所以「一部片一行」与「键挑选顺序」的对外行为不变。

    `ProviderIds` 的键按**小写**取（`metatube`/`javdb`）：S11 全库实测 112 条里 50 条的键
    写作小写 `metatube`，写死 `MetaTube` 会漏掉近一半 —— 现在靠文件名兜底不致命，
    但文件名形态一变就会丢片。
    """
    keys: List[str] = []
    # `ProviderIds` 的键**大小写不敏感**（S11 全库实测：112 条里 50 条的键是小写 `metatube`，
    # 只有写死的 `MetaTube` 会漏掉那 50 条）。`JavDB` 一并兼容 —— 它是我们自己写进去的键。
    providers = {str(k).lower(): v for k, v in (item.get("ProviderIds") or {}).items()
                 if isinstance(k, str)}
    for name in ("metatube", "javdb"):
        provider = str(providers.get(name) or "")
        if provider:               # "JavBus:IPZZ-802" / "JAV321:midv00946"
            keys.append(norm_key(provider.split(":")[-1]))
    for text in (_file_stem(str(item.get("Path") or "")), str(item.get("Name") or "")):
        keys.extend(_text_keys(text))
        # 新口径：整段文本过一次解析（`_text_keys()` 只认"开头那一段"，这里补上
        # 「番号前面还挂着别的东西」的写法，例如 `hhd800.com@MIDV-946.mp4`）。
        parsed = parse_av_number(text)
        if parsed.matched and parsed.norm_key:
            keys.append(parsed.norm_key)
        for candidate in _text_keys(text):
            canon = canon_key(candidate)
            if canon:
                keys.append(canon)
    return [k for k in dict.fromkeys(keys) if k]


class EmbyLibrary:
    """按番号查 Emby 媒体库；索引按需构建并缓存，线程安全。"""

    def __init__(self, host: str = "", apikey: str = "") -> None:
        self._host = str(host or "").strip().rstrip("/")
        self._apikey = str(apikey or "").strip()
        self._lock = threading.Lock()
        self._index: Optional[Dict[str, Dict[str, Any]]] = None
        self._built_at = 0.0
        self._failed_at = 0.0
        self._server_id = ""
        self._items_base = ""

    def ready(self) -> bool:
        """连接信息是否齐备。"""
        return bool(self._host and self._apikey)

    def lookup(self, number: str) -> Optional[Dict[str, Any]]:
        """番号 → {id, name, path, url}；不在库、未配置或查询失败一律返回 None。

        两种写法依次试（索引里两套键都有，见 `_item_keys()`）：

        1. `canon_key()` —— 干净号（`IPZZ-912-UC` 与 `IPZZ-912` 都→ `IPZZ912`），新层用这个；
        2. `norm_key()` —— 旧口径（保留后缀，`IPZZ912UC`），老台账/前端传来的历史键用这个。

        先试哪个不影响命中集合（两种键都在索引里），但先试 `canon_key()` 能让「同一部片的
        多个写法」收敛到同一个条目上，正是 v4 要的口径。
        """
        if not self.ready():
            return None
        index = self._ensure_index() or {}
        for key in dict.fromkeys([canon_key(number), norm_key(number)]):
            if key:
                hit = index.get(key)
                if hit:
                    return hit
        return None

    def index(self) -> Dict[str, Dict[str, Any]]:
        """整个库的 `归一化番号 → {id, name, path, url}`；未配置或查询失败返回空字典。

        与 `lookup()` 是同一份内存索引（同样的 5 分钟缓存与失败负缓存），只是不做单点查询：
        「从库里补种台账」「历史页显示在库状态」要的是一次拿到全部命中，一次 HTTP 抓完就够
        （本环境 93 条），逐个番号调 `lookup()` 会把已经建好的索引白白查一遍。
        """
        return self._ensure_index() or {}

    def invalidate(self) -> None:
        """丢掉索引缓存，下一次 `index()` / `lookup()` 重新抓一遍（界面上的「↻ 刷新」用）。

        失败负缓存也一起清：用户点刷新正是"我刚在 Emby 里改过东西"的场景，
        这时候还拿上一次失败的结论挡着他没有任何意义。
        """
        with self._lock:
            self._index = None
            self._built_at = 0.0
            self._failed_at = 0.0

    # ---------- 内部 ----------

    def _ensure_index(self) -> Dict[str, Dict[str, Any]]:
        """取索引：命中缓存直接返回，失败走负缓存，绝不抛异常。"""
        now = time.time()
        if self._index is not None and now - self._built_at <= TTL_OK:
            return self._index
        if now - self._failed_at <= TTL_FAIL:
            return self._index or {}
        with self._lock:
            now = time.time()
            if self._index is not None and now - self._built_at <= TTL_OK:
                return self._index
            if now - self._failed_at <= TTL_FAIL:
                return self._index or {}
            try:
                index = self._build()
            except Exception as error:
                logger.error(f"AVHelper 读取 Emby 媒体库失败：{error}")
                index = None
            if index is None:
                self._failed_at = time.time()
                return self._index or {}
            self._index = index
            self._built_at = time.time()
            self._failed_at = 0.0
            return index

    def _build(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """抓媒体库列表 → 索引目标库的全部条目。失败返回 None（记负缓存）。"""
        folders = self._api("/emby/Library/VirtualFolders")
        if not isinstance(folders, list):
            return None
        targets = pick_libraries([f for f in folders if isinstance(f, dict)])
        if not targets:
            logger.info("AVHelper 未在 Emby 找到 JAV 类媒体库，「已入库」标记跳过")
            return {}
        info = self._api("/emby/System/Info")
        if isinstance(info, dict):
            self._server_id = str(info.get("Id") or "")
        index: Dict[str, Dict[str, Any]] = {}
        total = 0
        for folder in targets:
            items = self._items(str(folder.get("ItemId") or ""))
            total += len(items)
            for item in items:
                entry = {
                    "id": str(item.get("Id") or ""),
                    "name": str(item.get("Name") or ""),
                    "path": str(item.get("Path") or ""),
                    "url": self._web_url(str(item.get("Id") or "")),
                    # 入库时间（Emby 的 UTC ISO）：下载台账拿它当「完成时间」——
                    # 片子是被整理入库那一刻进的库，比「插件第一次看到它」真实得多。
                    "created": str(item.get("DateCreated") or ""),
                }
                for key in _item_keys(item):
                    index.setdefault(key, entry)
        logger.info(f"AVHelper Emby 索引就绪：{len(index)} 个番号键 / {total} 条条目"
                    f"（库 {[f.get('Name') for f in targets]}）")
        return index

    def _items(self, parent: str) -> List[Dict[str, Any]]:
        """取某个媒体库的全部影片条目（带分页）。"""
        if not parent:
            return []
        out: List[Dict[str, Any]] = []
        start = 0
        while len(out) < MAX_ITEMS:
            data = self._api(self._items_base or "/emby/Items", ParentId=parent, Recursive="true",
                             IncludeItemTypes="Movie", Fields="Path,ProviderIds,Name,DateCreated",
                             StartIndex=start, Limit=PAGE, EnableTotalRecordCount="false",
                             SortBy="DateCreated", SortOrder="Descending")
            if not isinstance(data, dict) and not self._items_base:
                # 管理员直查不被接受时退回用户维度（Emby 各版本行为不一）
                self._items_base = self._user_items_base()
                data = self._api(self._items_base, ParentId=parent, Recursive="true",
                                 IncludeItemTypes="Movie", Fields="Path,ProviderIds,Name,DateCreated",
                                 StartIndex=start, Limit=PAGE, EnableTotalRecordCount="false")
            if not isinstance(data, dict):
                break
            items = [x for x in (data.get("Items") or []) if isinstance(x, dict)]
            out.extend(items)
            if len(items) < PAGE:
                break
            start += PAGE
        return out

    def _user_items_base(self) -> str:
        """退回用某个用户维度查条目（Emby 部分版本要求带 userId）。"""
        users = self._api("/emby/Users")
        if isinstance(users, list):
            admin = [u for u in users if isinstance(u, dict)
                     and (u.get("Policy") or {}).get("IsAdministrator")]
            pick = (admin or [u for u in users if isinstance(u, dict)] or [{}])[0]
            if pick.get("Id"):
                return f"/emby/Users/{pick['Id']}/Items"
        return "/emby/Items"

    def _web_url(self, item_id: str) -> str:
        """Emby 网页里该条目的地址（新标签页打开用）。"""
        if not item_id:
            return ""
        return (f"{self._host}/web/index.html#!/item?id={item_id}"
                + (f"&serverId={self._server_id}" if self._server_id else ""))

    def _api(self, path: str, **params: Any) -> Any:
        """带 api_key 的 GET，返回 JSON（失败返回 None）。"""
        if not self.ready():
            return None
        params["api_key"] = self._apikey
        res = RequestUtils(timeout=TIMEOUT).get_res(f"{self._host}{path}", params=params)
        if not res or res.status_code != 200:
            return None
        try:
            return res.json()
        except Exception:
            return None


# ---------- 写侧（v4 刮削层专用；只读那套 `EmbyLibrary` 行为一个字节都不动）----------

CLIENT_TIMEOUT = 30     # 写请求超时（上传头像/整份 DTO 比只读查询慢，给宽一点）

# 服务端 / 媒体探针维护的只读键（P0-① 实测，32 个）：写回时**剔除**。
# 剔掉后载荷从 11 782 B 缩到 286 B，而 `MediaSources`/`Path`/`DateCreated`/`RunTimeTicks`
# 一个都没丢（Emby 自己按探针维护它们）。反过来，**传了也不会被采纳** —— 例如
# `RunTimeTicks` 故意写 `123456789000`，读回仍是探针值 `99493394000`。
READONLY_KEYS = frozenset({
    "Id", "ServerId", "Etag", "DateCreated", "DateModified", "Path", "MediaSources",
    "MediaStreams", "Container", "Size", "Bitrate", "Width", "Height", "RunTimeTicks",
    "Chapters", "PartCount", "PresentationUniqueKey", "ParentId", "Type", "MediaType",
    "IsFolder", "CanDelete", "CanDownload", "SupportsSync", "UserData", "ImageTags",
    "BackdropImageTags", "DisplayPreferencesId", "FileName", "ExternalUrls",
    "LocalTrailerCount", "LockData",
})

# P0-③ 追加的**派生字段**：`SortName`/`ForcedSortName` 每次按 `Name` 重算。
# 它们**不在** P0-① 的 32 键清单里（那份报告只验证了「剔了照样 204」，清单本身不是安全边界）。
# 默认路径**绝不**写它们（锁定排序字段弊大于利）；写 `Name` 时 Emby 自己会重算，所以原值也不必回灌。
DERIVED_KEYS = frozenset({"SortName", "ForcedSortName", "LockedFields"})

# **允许**被覆盖表改动的元数据键。白名单而不是黑名单：未知键一律拒绝并记日志，
# 免得调用方顺手把 `Path`/`MediaSources` 这类探针字段塞进来（那正是 P0-① 要防的事）。
# ⚠️ `SortName` / `ForcedSortName` / `LockedFields` **故意不在表里**（P0-③ 裁决）：
#    这三个都是每次按 `Name` 重算的派生字段，锁住排序字段弊大于利 → 由 `Name` 以番号开头保证排序。
WRITABLE_KEYS = frozenset({
    "Name", "OriginalTitle", "Overview",
    "PremiereDate", "ProductionYear", "CommunityRating", "OfficialRating",
    "Studios", "SeriesName", "People", "GenreItems", "Genres", "Taglines",
    "ProviderIds",
})

# **本机实测无效**的字段（写了也白写 / 语义已被 Emby 改掉）。调用方传了就**丢掉 + debug**，
# 不报错不重试（P0-③ 明确要求）——S7 很可能照 v4.1 §8.1 顺手传来，静默丢弃比 400 更难查，
# 所以这里留一条 debug 日志作为痕迹。
INEFFECTIVE_KEYS = {
    "RunTimeTicks": "Emby 以媒体探针为准，写入被忽略（P0-①/P0-③ 双重复现）",
    "RemoteTrailers": "该端点对它既不写也不清（204 但读回 []，DB 列 NULL）→ 预告片走本地文件（D9）",
    "SortName": "派生字段，每次按 Name 重算；锁定弊大于利（P0-③ 裁决）",
    "ForcedSortName": "派生字段，每次按 Name 重算；锁定弊大于利（P0-③ 裁决）",
    "LockedFields": "锁定排序字段弊大于利（P0-③ 裁决），不写",
}

# 集合类键：P0-①/P0-③ 实测 **`null` 会 400**（`ToList(null)`），合并后一律写成 `[]`。
# 前四个是元数据集合，`MediaSources`/`MediaStreams` 在只读键里、正常查不出 null，
# 但它们是同一类「ToList 会炸」的字段，留着兜底不亏。
COLLECTION_KEYS = ("People", "Studios", "Genres", "GenreItems", "MediaSources", "MediaStreams")

# 标量元数据键：**回滚时 `None` 要当成「清空」写 `""`，不能静默丢掉**。
#
# 真机实测（S2 E2E，2026-10-14）：`SNOS-380` 的 `Overview` 在 DTO 与备份里都是 `null`。
# 若把 `None` 一律当"没给"跳过，备份回灌就**清不掉**验证时写进去的值
# （实测回滚后 `Overview` 仍是 `"S2-CT-OK 真机写路径验证"`，而基线是 `null`）
# → D7 的「写前备份 + 一键回滚」在这类字段上是失效的。
# 所以对这批键：拿到 `None` → 显式写 `""`（Emby 读回是 `null`，等价于原来的"没有值"）。
# ⚠️ **不放** `ProviderIds`（它有自己的合并/覆盖语义）与集合键（`None` 要写 `[]`）；
#    `PremiereDate`/`ProductionYear` 是日期/数值型，清空写法未实测，**故意留在表外**
#    —— 宁可保持"不动"，也不要拿空串去赌它不会 400。
NULL_CLEARABLE_KEYS = frozenset({
    "Name", "OriginalTitle", "Overview", "SeriesName",
    "OfficialRating", "CommunityRating", "Taglines",
})

# `update_item()` 的覆盖表里可以带这几个**控制标记**（下划线开头，不会被当成 DTO 字段）。
CONTROL_KEYS = frozenset({"provider_ids_replace", "_mode", "_allow_sort_name"})


def merge_provider_ids(existing: Any, extra: Any = None) -> Dict[str, str]:
    """合并 `ProviderIds`（P0-① 铁律：Emby 对该字段是**整份覆盖**，不合并就会顶掉别人的键）。

    实测反例：只写 `{AVHelper, JavDB}` 会把 MetaTube 写的 `MetaTube=JavBus:CAWD-989` 抹掉。
    所以写入点统一走这里：先摊平原值，再盖上自己要写的键。
    """
    out: Dict[str, str] = {}
    if isinstance(existing, dict):
        out.update({str(k): str(v) for k, v in existing.items() if v is not None})
    if isinstance(extra, dict):
        out.update({str(k): str(v) for k, v in extra.items() if v is not None})
    return out


def sanitize_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """写前收尾：丢掉实测无效的字段、把 `null` 集合写成 `[]`、保证 `ProviderIds` 非 null。

    返回 `(处理后的载荷, debug 说明列表)`。**纯函数**，不碰网络 —— 单测直接拿它验
    「null 集合 → []」「RunTimeTicks 被丢掉」这两条 P0-③ 口径。
    """
    data = dict(payload or {})
    notes: List[str] = []
    for key in list(data.keys()):
        if key in INEFFECTIVE_KEYS and key not in DERIVED_KEYS:
            notes.append(f"丢掉 {key}：{INEFFECTIVE_KEYS[key]}")
            data.pop(key, None)
    for key in COLLECTION_KEYS:
        if key in data and data[key] is None:       # 实测 null 会 400（ToList(null)）
            data[key] = []
            notes.append(f"{key} 为 null → 写成 []（null 会 400）")
    if not isinstance(data.get("ProviderIds"), dict):
        # ProviderIds 缺席/为 null = 400（P0-① 二分实测：`{Name,ProviderIds:{}}` 是 204 的最小载荷）
        data["ProviderIds"] = {}
        notes.append("ProviderIds 缺席或非字典 → 补成 {}（缺席会 400）")
    return data, notes


def writable_overrides(dto: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """把调用方的覆盖表过滤成「只读键以外的可写键」，返回 `(覆盖, 警告列表)`。

    顺便处理 P0-① 实测出的流派坑（`genres` 标记位翻译成真正生效的 `GenreItems`）。
    排序名默认**不写**（P0-③ 裁决），要写必须显式传 `_allow_sort_name=True`。

    导出成模块级函数是为了让 S7 能在**不真的写**的前提下预览「这次写会发什么字段」
    （`/scrape/preview` 的 `fields[]` diff 需要它）。
    """
    src = dto if isinstance(dto, dict) else {}
    out: Dict[str, Any] = {}
    notes: List[str] = []

    for key, value in src.items():
        name = str(key)
        if name in CONTROL_KEYS or name.startswith("_"):
            continue
        if name in READONLY_KEYS:
            notes.append(f"忽略只读键 {name!r}（服务端/探针维护，传了也不会被采纳）")
            continue
        if name in INEFFECTIVE_KEYS:
            continue                                # 静默丢弃，由 sanitize_payload 记 debug
        if name not in WRITABLE_KEYS:
            notes.append(f"忽略不在白名单里的键 {name!r}（防止误写探针字段）")
            continue
        if value is None and name in NULL_CLEARABLE_KEYS:
            # 回滚要把 `null` 还原成"没有值"：JSON 里这份 DTO 本来就是 `Overview: null`，
            # 静默跳过会让备份回灌清不掉验证时写进去的内容（真机踩过）。
            out[name] = ""
            continue
        out[name] = value

    # 流派：`Genres` 字符串数组被忽略，真正生效的是 `GenreItems`（{:Name, :Id}）
    items = src.get("genre_items")
    if items is None:
        items = src.get("genres")
    if isinstance(items, list):
        clean = [g for g in items if isinstance(g, dict) and str(g.get("Name") or "")]
        if clean:
            out["GenreItems"] = clean
            out["Genres"] = [str(g.get("Name")) for g in clean]

    # 排序名：**默认不写**（P0-③：SortName/ForcedSortName 是每次按 Name 重算的派生字段，
    # 锁住它们弊大于利）。留一个显式开关，只给"确实要钉死排序"的调用方用。
    sort_name = src.get("sort_name")
    if sort_name and bool(src.get("_allow_sort_name")):
        text = str(sort_name).strip()
        if text:
            out["ForcedSortName"] = text
            out["LockedFields"] = _with_sort_lock(src.get("LockedFields"))
    return out, notes


def _with_sort_lock(existing: Any) -> List[str]:
    """`LockedFields` 里补上 `"SortName"`（P0-①：不锁的话 `ForcedSortName` 会被 `Name` 覆盖）。

    只在调用方显式要求钉死排序名时才走到这里 —— 默认路径不写这三个字段（P0-③ 裁决）。
    """
    fields = [str(x) for x in existing] if isinstance(existing, list) else []
    if "SortName" not in fields:
        fields.append("SortName")
    return fields


def restore_overrides(backup: Dict[str, Any]) -> Dict[str, Any]:
    """备份 DTO → **能真正还原**的覆盖表（给 `rollback_item()` 用）。

    为什么不能直接把备份丢给 `update_item()`：`update_item` 是「以当前 DTO 为底、覆盖表改哪算哪」，
    **备份里没有的键 = 不动**，而不是清空。而 Emby 对没有值的可选字段**会整个省略该键** ——
    真机实测（S2 E2E，2026-10-14）：`SNOS-380` 写前的 DTO 与备份里都**没有 `Overview` 这个键**，
    写一次 `Overview` 之后它才出现（45 键 → 46 键）。于是「备份原样回灌」回滚不掉 `Overview`，
    条目会停在验证态、与备份 sha 不一致 —— D7 的「一键回滚」在这类字段上是失效的。

    本函数把这件事补上：对**基线里缺席、但属于可清空标量**的键，显式写 `None`
    （`writable_overrides()` 会把 `None` 落成 `""`，真机实测 `""` 能把 `Overview` 清成
    Emby 的"没有值"）。集合键缺席则写 `[]`（`null` 会 400）。

    调用方照旧必须是「已先 `store.item_backup_save()` 成功」的那条链（D7）；本函数不碰 store。
    `ProviderIds` 沿用备份里的完整字典（配上 `provider_ids_replace=True` 才是原样回灌）。
    """
    src = backup if isinstance(backup, dict) else {}
    out: Dict[str, Any] = {k: v for k, v in src.items()}
    out["provider_ids_replace"] = True          # 备份里的 ProviderIds 是"当时全貌"，要整份还原
    out.setdefault("ProviderIds", {})
    for key in WRITABLE_KEYS:
        if key in src or key in INEFFECTIVE_KEYS or key == "ProviderIds":
            continue
        if key in NULL_CLEARABLE_KEYS:
            out[key] = None                    # 基线没有这个键 → 显式清空
        elif key in COLLECTION_KEYS:
            out[key] = []                      # 集合：null 会 400，写 []
    return out


class EmbyClient:
    """Emby **写侧**客户端：读完整 DTO、更新条目、传/删图片、按名查人（契约 §3.1）。

    与只读的 `EmbyLibrary` 并存，**互不影响**：

    - `EmbyLibrary` 服务于界面上的「已入库」标记（一次抓完整个库建索引、5 分钟缓存）；
    - `EmbyClient` 服务于刮削写入（按 id 精读精写、不做缓存、每次都打真实请求）。

    **三条纪律**（写侧出错会把用户的库弄脏，所以这里比只读那套严格）：

    1. **任何方法都不抛异常** —— 失败返回 `(False, 原因)` 或 `None`，并留 `logger.error/warning`；
       调用方（`scraper.py`）据此往 `scrape_log` 记一条，绝不能因为 Emby 抽风把整批刮削带崩。
    2. **`update_item(item_id, dto)` 里 `dto` 是「字段覆盖表」，不是整份 DTO**（P0-① 裁决）——
       本类自己 `GET → 剔只读键 → 合并覆盖 → POST`。合并必须在**本类内**做，因为：
       差量 DTO 直接 POST 会 **400**（`Enumerable.ToList(null)`），而漏字段又等于清空字段。
       调用方只管「我想把 Name/Overview/People… 改成什么」，不用自己读一遍 Emby。
    3. **备份闸门仍在调用方**（D7）：本类不碰 `store`，`scraper.py` 必须先
       `store.item_backup_save()` 成功才能调这里。

    **与 v4.1 §8.1 的偏差**（P0-① / P0-③ 实测，`_tmp/p0/REPORT-1.md` §3 / `REPORT-3.md` —— S7 依赖这几条）：

    | v4.1 §8.1 的写法 | 实测 | 本类的处置 |
    | --- | --- | --- |
    | 直接写 `SortName` | ❌ 无效 / 派生字段：`SortName` 与 `ForcedSortName` 每次按 `Name` 重算 | **默认不写**（P0-③ 裁决：锁定排序字段弊大于利），排序由 `Name` 以番号开头保证；只留 `_allow_sort_name=True` 显式开关 |
    | 写 `Genres` 字符串数组 | ❌ 被忽略 | `genres` 标记位翻译成 `GenreItems=[{Name,Id}]`，并顺带派生 `Genres` |
    | `RunTimeTicks` 为空时补时长 | ❌ 写了 204 但不落库（以媒体探针为准） | **丢掉不写**，只记 `debug`（P0-③ 明确：不报错、不重试） |
    | 写 `RemoteTrailers` | ❌ 204 但读回 `[]`、DB 列 NULL | **丢掉不写**；预告片走 D9 的本地文件模式 |
    | `ProviderIds` 直接赋值 | ❌ **整份覆盖**，会顶掉 `MetaTube` 写的键；且该键缺席直接 **400** | 默认**合并**（`provider_ids` 只做增量）；要整份覆盖必须显式 `provider_ids_replace=True` |
    | 差量 DTO 直接 POST | ❌ **400**（`Enumerable.ToList(null)`，根因 `ProviderIds` 缺席） | 本类自己 read-modify-write，并把 `null` 集合收尾成 `[]` |

    ⚠️ 契约 §3.6.1 的 `SortName`「总是写」与 `LockedFields`「不写」两条，按上表**已被 P0-③
    裁决覆盖**（不写排序名与锁）；如主统筹另有裁决，改本类一处即可。
    """

    def __init__(self, host: str, apikey: str, timeout: int = CLIENT_TIMEOUT) -> None:
        self._host = str(host or "").strip().rstrip("/")
        self._apikey = str(apikey or "").strip()
        self._timeout = int(timeout or CLIENT_TIMEOUT)
        self._admin_id: Optional[str] = None

    def ready(self) -> bool:
        """连接信息是否齐备（不齐时所有方法都是空操作 + 一条 `warning`）。"""
        return bool(self._host and self._apikey)

    def admin_user_id(self) -> str:
        """第一个 `Policy.IsAdministrator` 的用户 id（拿不到返回空串）。

        Emby 4.9 的条目**读**接口只在管理员维度下存在（P0-① 实测：`GET /emby/Items/{id}`
        在本机 404，`GET /emby/Users/{admin}/Items/{id}` 才是唯一可用的读法），所以写侧的
        read-modify-write 全靠它。结果缓存起来 —— 每次写都去查一遍用户表没有必要。
        """
        if self._admin_id is None:
            users = self._get_json("/emby/Users")
            pick = ""
            if isinstance(users, list):
                admins = [u for u in users
                          if isinstance(u, dict) and (u.get("Policy") or {}).get("IsAdministrator")]
                if admins:
                    pick = str(admins[0].get("Id") or "")
                elif users:
                    # 一个管理员都没有：退回第一个用户，但要说清楚这是降级（不是管理员维度）
                    pick = str((users[0] or {}).get("Id") or "")
                    logger.warning("AVHelper Emby 用户表里没有 IsAdministrator，"
                                   f"降级用第一个用户 {pick!r} 作查询维度")
            if not pick:
                logger.error("AVHelper 取 Emby 管理员 id 失败：/emby/Users 不可用或返回为空")
            self._admin_id = pick
        return self._admin_id

    def get_item(self, item_id: str, user_id: str = "") -> Optional[Dict[str, Any]]:
        """按 id 取**完整**条目 DTO（拿不到返回 `None`）。

        `user_id` 给了就用它，否则用管理员维度（P0-① 实测这是本机**唯一**可用的完整 DTO 读法）；
        两条都不通时退回无维度直查 `GET /emby/Items/{id}` —— 那是给别的 Emby 版本留的兜底
        （本机 4.9.3.0 上据实测是 404，所以它排在后面而不是前面）。
        """
        item = str(item_id or "").strip()
        if not item or not self.ready():
            return None
        wanted = str(user_id or "").strip() or self.admin_user_id()
        if wanted:
            dto = self._get_json(f"/emby/Users/{wanted}/Items/{item}")
            if isinstance(dto, dict):
                return dto
        dto = self._get_json(f"/emby/Items/{item}")
        return dto if isinstance(dto, dict) else None

    def update_item(self, item_id: str, dto: Dict[str, Any]) -> Tuple[bool, str]:
        """**读-改-写**更新条目元数据。成功 `(True, '')`，失败 `(False, 原因)`。

        `dto` 是**字段覆盖表**（`{"Name": …, "Overview": …, "People": [...]}`），**不是**整份
        `BaseItemDto` —— 本类自己完成 P0-① 实测出的那条唯一安全写法：

        1. `GET /emby/Users/{admin}/Items/{id}` 拿完整 DTO（本机唯一可用的读法）；
        2. 剔掉 32 个服务端/探针只读键 → 载荷从 11 782 B 缩到 286 B（体积的 2.4%）；
        3. 覆盖调用方要改的字段；
        4. `POST /emby/Items/{id}` → 期望 **204**。

        **为什么不能图省事直接发差量 DTO**（P0-① 反例，写进这里是防止以后有人"优化"掉）：
        `{"Name": …, "Overview": …}` 直接 POST 会 **400** `Value cannot be null. (Parameter
        'source')`（`ItemUpdateService.UpdateItem` 里的 `Enumerable.ToList`）——
        唯一必须存在的键是 **`ProviderIds`**，所以下面无论如何都保证它非 null。

        **`ProviderIds` 默认合并**（同一条反例的另一面）：Emby 对该字段是**整份覆盖**，
        照调用方原样发会把 MetaTube 写的 `MetaTube=JavBus:CAWD-989` 抹掉。只有显式传
        `provider_ids_replace=True` 才覆盖整份。

        `null` 集合（`People`/`Studios`/`Genres`/`GenreItems`/`MediaSources`…）会 **400**
        （`ToList(null)`），所以出去之前统一由 `sanitize_payload()` 收尾成 `[]`；
        `RunTimeTicks`/`RemoteTrailers`/排序名三件套则直接丢掉（实测无效，见 `INEFFECTIVE_KEYS`）。

        本方法不碰备份 —— D7 的 `store.item_backup_save()` 闸门在 `scraper.py`。
        """
        item = str(item_id or "").strip()
        if not item:
            return False, "item_id 为空"
        if not isinstance(dto, dict) or not dto:
            return False, "覆盖表为空（拒绝空写：那只会白白多打一次请求）"
        if not self.ready():
            return False, "Emby 未配置 host/apikey"

        base = self.get_item(item)
        if not isinstance(base, dict):
            return False, "读不到条目的完整 DTO（read-modify-write 的第一半失败，未发出写请求）"

        overrides, notes = writable_overrides(dto)
        replace_providers = bool(dto.get("provider_ids_replace"))
        for note in notes:
            logger.warning(f"AVHelper Emby 写入 {item}：{note}")

        # 以完整 DTO 为底剔只读键，再盖覆盖表（顺序要紧：先剔后盖，否则盖进去的
        # `Path`/`RunTimeTicks` 这类会被自己剔掉）。
        # 以完整 DTO 为底，剔掉只读键**与派生键**（`SortName`/`ForcedSortName`/`LockedFields`）。
        payload = {k: v for k, v in base.items()
                   if k not in READONLY_KEYS and k not in DERIVED_KEYS}
        # 覆盖表只过「只读键」这一道闸，**不过**派生键闸 —— 否则
        # `_allow_sort_name=True` 这个显式逃生口永远进不来（默认路径不会产出派生键）。
        for key, value in overrides.items():
            if key not in READONLY_KEYS:
                payload[key] = value
        if replace_providers:
            payload["ProviderIds"] = dict(overrides.get("ProviderIds") or {})
        else:
            # 只合并 `overrides` 里的 **ProviderIds 那一项** —— 传整个 overrides 进去会把
            # `Name`/`People` 这些也摊成 provider 键（写坏数据，且很难看出来）。
            payload["ProviderIds"] = merge_provider_ids(base.get("ProviderIds"),
                                                       overrides.get("ProviderIds"))
        payload, drops = sanitize_payload(payload)
        for note in drops:
            logger.debug(f"AVHelper Emby 写入 {item}：{note}")

        # ★ Content-Type **必须显式给**，不能靠 `json=` 自己带（0.7.0 上线后第一个真机写请求就这么挂的）：
        # `RequestUtils.__init__` 的默认头是 `application/x-www-form-urlencoded; charset=UTF-8`，
        # 而 requests 只在「调用方没给 Content-Type」时才用 `json=` 的 `application/json`
        # —— 默认头把它占了，于是 JSON body 顶着表单头发出去，Emby 用表单解析器读它：
        # body 长度被当成"表单 key 长度"，**超过 2048 直接 500
        # `Form key length limit 2048 exceeded.`**（实测 8/10 条必挂，短条目碰运气能过）。
        # requests 的 `json=` 默认 `ensure_ascii=True`，中文全变 `\uXXXX`（6 字节/字），
        # 所以线上载荷轻松破 2 KB —— 这不是边缘情况，是必挂。
        res = self._request("post", f"/emby/Items/{item}", json=payload,
                            headers={"Content-Type": "application/json"})
        if res is None:
            return False, "请求未发出或超时"
        if res.status_code in (200, 204):                   # 实测成功码是 204
            return True, ""
        return False, f"HTTP {res.status_code}: {self._snippet(res)}"

    def upload_image(self, item_id: str, img_type: str, raw: bytes) -> Tuple[bool, str]:
        """上传图片（头像/封面/剧照）。成功 `(True, '')`，失败 `(False, 原因)`。

        ★ **格式是硬约束，不是可调项**（P0-② 四路对照实测，契约 D16）：

        | body | Content-Type | 结果 |
        | --- | --- | --- |
        | 裸 JPEG 字节 | `image/jpeg` | 500 `The input is not a valid Base-64 string` |
        | 裸 JPEG 字节 | `application/octet-stream` | 500 同上 |
        | **base64 ASCII** | **`image/jpeg`** | **204 ✅** |
        | base64 ASCII | `text/plain` | 400 `Unable to determine image file extension…` |

        所以这里固定 `base64.b64encode(raw)` 的 **ASCII 文本** + `image/jpeg`，不接受覆盖。

        副作用（回滚时要知道，D16）：每次成功上传都会**重算 `PrimaryImageTag`** ——
        回滚不能照搬备份里的 `ImageTags`，要重传原图再以回读值为准。
        """
        item = str(item_id or "").strip()
        kind = str(img_type or "Primary").strip() or "Primary"
        if not item:
            return False, "item_id 为空"
        if not raw:
            return False, "图片字节为空"
        if not self.ready():
            return False, "Emby 未配置 host/apikey"
        body = base64.b64encode(bytes(raw)).decode("ascii")
        res = self._request("post", f"/emby/Items/{item}/Images/{kind}",
                            data=body, headers={"Content-Type": "image/jpeg"})
        if res is None:
            return False, "请求未发出或超时"
        if res.status_code in (200, 204):
            return True, ""
        return False, f"HTTP {res.status_code}: {self._snippet(res)}"

    def delete_image(self, item_id: str, img_type: str) -> Tuple[bool, str]:
        """删掉条目的某张图（回滚用：先删掉写坏的图，再由调用方决定要不要重传原图）。"""
        item = str(item_id or "").strip()
        kind = str(img_type or "Primary").strip() or "Primary"
        if not item:
            return False, "item_id 为空"
        if not self.ready():
            return False, "Emby 未配置 host/apikey"
        res = self._request("delete", f"/emby/Items/{item}/Images/{kind}", data="")
        if res is None:
            return False, "请求未发出或超时"
        if res.status_code in (200, 204, 404):      # 404 = 本来就没有，按成功算（幂等）
            return True, ""
        return False, f"HTTP {res.status_code}: {self._snippet(res)}"

    def image_url(self, item_id: str, img_type: str = "Primary") -> str:
        """局域网**原图**直取地址（带 api_key）。

        `__init__.py` 的 `/img?emby=<id>` 会 302/转发到这里，缓存与裁切由 imgproxy 负责；
        这个地址是给「Emby 就在同一局域网」的场景直连用的，**不要**下发给浏览器
        （`api_key` 不能进前端，见 AGENTS.md §5 的鉴权分工）。
        """
        item = str(item_id or "").strip()
        kind = str(img_type or "Primary").strip() or "Primary"
        if not item or not self._host:
            return ""
        url = f"{self._host}/emby/Items/{item}/Images/{kind}"
        if self._apikey:
            url += f"?api_key={self._apikey}"
        return url

    def people_of(self, item_id: str) -> List[Dict[str, Any]]:
        """条目 DTO 里的 `People[]`（拿不到返回空列表）。

        契约 §3.6.1 要「重写整份 People 数组」时，先拿这个当原值（保留非 Actor/Director 元素）。
        D14：写回时**只给 `Name` + `Type`** —— `People[].Id` 会被 Emby 彻底忽略，
        所以本类不提供「回填 PersonId」的能力（那是条死路）。
        """
        dto = self.get_item(item_id)
        people = (dto or {}).get("People")
        return [p for p in people if isinstance(p, dict)] if isinstance(people, list) else []

    def person_item(self, person_id: str) -> Optional[Dict[str, Any]]:
        """按 Person 的 Emby id 取实体 DTO（拿不到返回 `None`）。"""
        person = str(person_id or "").strip()
        if not person:
            return None
        return self._get_json(f"/emby/Items/{person}")

    def find_person(self, name: str) -> Optional[Dict[str, Any]]:
        """按 **`Name` 精确相等**找 Person 实体（找不到返回 `None`）。

        为什么必须精确相等（D13 / P0-② 实测）：Emby 4.9 的 Person 搜索是**整名匹配**，
        不做子串/前缀匹配；而且 `SortName`/`ForcedSortName`/`OriginalTitle`/`ProviderIds`
        **一律不参与**匹配 —— 拿日文原名去搜「方案 A 写法的实体」永远是 0 命中。
        所以这里的匹配键只有 `Name` 一个，写法必须与 `scraper.py` 写入的那份规范名完全一致。

        判空**看 `Items` 不看 `TotalRecordCount`**（D19：实测出现过 `total=0` 但 `Items` 非空）。
        先试 `SearchTerm`；`Items` 为空再退回全量 `/emby/Persons` 名册（各版本搜索行为不一，
        本机 179 个 Person 全量拉一次也才一个请求）。
        """
        wanted = str(name or "").strip()
        if not wanted or not self.ready():
            return None
        for params in ({"SearchTerm": wanted}, {}):
            data = self._get_json("/emby/Persons", params)
            items = data.get("Items") if isinstance(data, dict) else None
            for person in (items if isinstance(items, list) else []):
                if isinstance(person, dict) and str(person.get("Name") or "") == wanted:
                    return person
        logger.warning(f"AVHelper 没在 Emby 找到名为 {wanted!r} 的 Person 实体")
        return None

    # ---------- 内部 ----------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """发一个带 api_key 的请求；**任何异常都吞掉**并返回 `None`（写侧不许把调用方带崩）。

        ⚠️ **造 `RequestUtils` 时故意不给 `content_type`**（用宿主默认的
        `application/x-www-form-urlencoded`）：本类的方法有三种截然不同的 body 语义 ——
        `update_item` 是 JSON、`upload_image` 是 base64 文本要 `image/jpeg`、
        GET/DELETE 没有 body。在**工厂这一层**钉死任何一种是错的，所以统一由**调用点**
        用 `headers={"Content-Type": …}` 显式覆盖（`RequestUtils.request()` 里
        `kwargs.get("headers", self._headers)` 会优先用调用方给的，已实测确认）。
        → 以后新增「带 JSON body」的写方法，**必须自己带上 `application/json`**。
        """
        if not self.ready():
            logger.warning("AVHelper Emby 写操作跳过：未配置 host/apikey")
            return None
        params = dict(kwargs.pop("params", {}) or {})
        params["api_key"] = self._apikey
        url = f"{self._host}{path}"
        try:
            util = RequestUtils(timeout=self._timeout)
            fn = getattr(util, f"{method}_res")
            return fn(url, params=params, **kwargs)
        except Exception as error:
            logger.error(f"AVHelper Emby {method.upper()} {path} 请求异常：{error}")
            return None

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """带 api_key 的 GET → JSON（非 200 或解析失败返回 `None`）。"""
        res = self._request("get", path, params=dict(params or {}))
        if res is None or res.status_code != 200:
            return None
        try:
            return res.json()
        except Exception as error:
            logger.warning(f"AVHelper Emby GET {path} 返回的不是 JSON：{error}")
            return None

    @staticmethod
    def _snippet(res: Any, limit: int = 200) -> str:
        """响应正文的短摘要（写进失败原因与日志，别把整份 HTML 错误页灌进去）。"""
        try:
            text = str(res.text or "")
        except Exception:
            return ""
        return text[:limit].replace("\n", " ").strip()
