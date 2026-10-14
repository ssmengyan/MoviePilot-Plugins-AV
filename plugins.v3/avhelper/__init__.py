"""AV 资源助手：JAV 榜单/演员/详情浏览 + 番号订阅、PT 选种下载、通知与缓存治理。

后端为 2026-10 的前端重写版（Vue 联邦界面 + `/ui` 静态应用）。数据根、javdb 二进制路径
都不写死，由 `paths.py` 按「插件配置 → 历史固定路径 → MoviePilot 插件数据目录」解析，
别人装到自己机器上也能直接跑（详见仓库 README 的「安装」一节）。

界面说明：宿主 Vuetify JSON 页面无法承载搜索框、灯箱等交互（当前宿主前端在事件调用后不会
重新拉取页面），因此完整界面由本插件自带的静态目录 `ui/`（拆分前是单文件 `webui.html`）经
匿名路由 `/ui/` 下发，插件页用 iframe 承载；前端自己带状态、自己调接口（契约见
docs/AVHelper-API契约.md）。

安全边界：只有 `/ui`、`/ui/`（含 `ui/` 下的静态资源）与 `/img` 匿名；`/img` 仅反代白名单图床
且无写能力，其余数据接口一律 bear 鉴权。`API_TOKEN` 不出现在任何 URL 或页面里，前端从同源
localStorage 取会话 JWT。
"""

import asyncio
import hashlib
import json
import mimetypes
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote, unquote

from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.plugin import _PluginBase
from app.sdk.scheduler import add_plugin_once_job, remove_plugin_once_job

from . import emby, imgproxy, longshot, paths, scoring
from .client import JavdbClient, mask, reset as reset_javdb_state
from .notify import Notifier
from .ratelimit import RateLimiter
from .store import PLUGIN_SOURCES, Store
from .tasks import DEFAULT_RULE, TaskEngine, merge_rule

PLUGIN_ID = "AVHelper"
# 前端静态目录与 MIME 表：多文件前端由 `/ui/` 下发，ES module 的相对导入依赖目录语义
UI_DIR = Path(__file__).with_name("ui")
UI_EXT_MIME: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}
# 默认不内置代理：内地以外直连即可，内地用户在插件设置里填自己的代理
DEFAULT_PROXY = ""
GLOBAL_RULE_KEY = "global_rule"
THUMB_KEY = "num2thumb"      # 番号 → 封面原图的本地索引（任务/下载队列补图用）
# 缓存 TTL（执行方案 §8.1，不得放宽）
TTL_RANK = 6 * 3600        # 榜单 6 小时
TTL_DETAIL = 7 * 86400     # 番号详情 7 天
TTL_ACTOR = 24 * 3600      # 演员作品史 24 小时
ACTOR_PAGE = 30            # 演员作品史每页条数（界面按需续拉，§8.1）
ACTOR_PAGE_MAX = 50        # 站点单页硬上限：请求更大也只回 50 条（实测）
TTL_LONG = 7 * 86400       # 长图 URL 7 天
FAIL_TTL = 120             # 抓取失败后的负缓存：这段时间内不再重试（避免每次打开都重付等待）
# 缓存总量上限**不再是常量**（0.6.3 起）：配置键 `cache_max_gb`，默认 1G、可设范围见
# `paths.cache_limit_gb()`（0.1G 下限是硬保护，归零会把缓存目录清空）。
CACHE_SIZE_TTL = 60        # 缓存体积的内存缓存时长（秒）：前端 15 秒轮询一次，不能每次 rglob 整个目录
ONCE_JOB_ID = "subcheck_now"
# 启动预热（§8.2）：MP/插件启动时先把「发现榜单」首屏要用的数据与封面落进缓存，
# 用户第一次打开插件时直接命中缓存，不必现抓 javdb、也不必现拉几十张封面。
WARM_RANK_PERIODS = ("week", "day", "month")   # 预热哪几档（默认分类，见 WARM_KIND）
WARM_KIND = "censored"     # 只预热默认分类；无码/FC2 换过去时按需抓（各约 1.5 秒）
WARM_IMAGE_LIMIT = 60      # 每档榜单最多预热多少张封面（榜单本身约 60 条）
WARM_IMAGE_GAP = 0.05      # 封面之间的间隔（秒）：串行 + 轻微间隔，别在启动瞬间打满 NAS 代理
WARM_MIN_INTERVAL = 900    # 两次预热的最小间隔（秒）：reload/改配置会重跑 init_plugin，别重复抓
WARM_KV_KEY = "warmup_at"  # 上次预热完成时间（防抖用）
# 台账「已下载番号」的内存缓存时长（秒）：`_movie()` **每条电影**都要问一次（榜单一次 60 条），
# 直查库等于把一次请求放大成几十次 SQLite 读；台账只在下载完成时变，晚 30 秒打徽标没有影响
DOWNLOAD_KEYS_TTL = 30
# 刮削线 v4（契约 §3.7 / §4）：读侧统一投影 `film_view` 的进程内缓存时长（秒）。
# 与 `DOWNLOAD_KEYS_TTL` 同一套写法：`/library` 一次上百行、界面又是 15 秒轮询，
# 投影要么走 S7 的 `scraper.film_view()`、要么走本模块的**一次** meta/item/台账批量读，
# 两条路都吃这份缓存；刮削写完（`/scrape/run`）主动失效，不靠它收敛。
FILM_VIEW_TTL = 30
# `/scrape/status` 的队列计数探测条数：`store.meta_due()` 没有 COUNT 口子（limit<=0 按 5 处理），
# 取一批再数；两档队列都是给人看的规模提示，200 条足够、也不至于把整表 raw_json 拉进内存。
SCRAPE_QUEUE_PROBE = 200
# 依赖模块（S4 的 translator / S7 的 scraper）还没落盘时的统一对外文案
SCRAPE_NOT_READY = "刮削模块未就绪"
# 没配 Emby（插件与 MP 两处都取不到连接信息）时 `/scrape/*` 的文案：写线离开 Emby 没有意义
EMBY_NOT_READY = "Emby 未配置"
# 配置里的枚举项（任务书 E）：不认识的值一律回落默认，老配置缺这个键也不会报错
SCRAPE_MODES = ("off", "fill", "hybrid", "own")
CROP_ANCHORS = ("auto", "right", "center", "left", "raw")
TRAILER_MODES = ("off", "remote", "local")
# `states{}`（契约 §4）三个字段各自的合法取值，投影时用来兜底
DOWNLOAD_STATES = ("downloading", "paused", "completed", "failed", "cancelled", "none")
LIBRARY_STATES = ("in_library", "pending_import", "not_in_library")
SCRAPE_STATES = ("scraped_full", "scraped_partial", "unscraped")
# 台账 `state` → `film_view().states.download`（契约 §4 的取值集）
_DOWNLOAD_STATE_MAP = {"downloaded": "completed", "downloading": "downloading",
                       "paused": "paused", "failed": "failed", "cancelled": "cancelled"}
# `meta.completeness` → `states.scrape`（老行没有 media_item 时按作品级完整度兜底）
_SCRAPE_STATE_MAP = {"full": "scraped_full", "missing_plot": "scraped_partial",
                     "missing_core": "unscraped"}


def num_key(number: Any) -> str:
    """番号索引键：去空白 + 统一大写（只用于本地索引，不改显示用的原值）。"""
    return str(number or "").strip().upper()


def canon_of(number: Any) -> str:
    """跨层匹配键：`emby.canon_key()`（干净号，`IPZZ-912-UC` → `IPZZ912`）优先。

    与 `tasks._canon()` 同一口径；函数不在（老 host 里那份 emby 还没升级）时退回旧口径
    `norm_key()`，绝不在这里自己发明第三套规则（D1 裁决）。
    """
    fn = getattr(emby, "canon_key", None)
    if callable(fn):
        try:
            return str(fn(number) or "")
        except Exception:
            pass
    return emby.norm_key(number)


def shown_of(number: Any) -> str:
    """展示番号：`emby.parse_av_number()` 解析得出就用它（`IPOK-025L` → `IPOK-025`），
    解析不出就原样回传 —— 不在这一层发明写法。"""
    fn = getattr(emby, "parse_av_number", None)
    if callable(fn):
        try:
            return str(getattr(fn(number), "display_number", "") or "")
        except Exception:
            pass
    return str(number or "").strip()


def pick_choice(value: Any, choices: Iterable[str], default: str) -> str:
    """配置里的枚举项：不认识（含老配置没这个键）一律回默认值，绝不抛。"""
    text = str(value or "").strip().lower()
    return text if text in tuple(choices) else default


def pick_bool(value: Any, default: bool) -> bool:
    """配置里的开关：缺键/空串回落默认；`"false"` / `0` / `off` / `no` 这类字符串写法也认。"""
    if value is None or value == "":
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("false", "0", "off", "no", "none"):
        return False
    if text in ("true", "1", "on", "yes"):
        return True
    return bool(default)


def to_int(value: Any, default: int = 0) -> int:
    """容错的整数转换：读接口拿到字符串/None 也不抛（`^0` 除外，一律按默认值）。"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def version_labels(tags: Any) -> List[str]:
    """`version_tags` 字典 → 展示角标数组（契约 §4 的 `version_tags` / `badge`）。

    顺序固定（中字 → 流出 → 分辨率 → VR → 版本/分集），拼法与 §3.6.1 的 `Name` 角标同一套词；
    认不出形状（串、None、别的对象）回空数组，**不在这一层自己解释 JSON**。
    """
    if not isinstance(tags, dict):
        return []
    out: List[str] = []

    def add(label: str) -> None:
        if label and label not in out:
            out.append(label)

    if tags.get("is_zh_sub"):
        add("中字")
    if tags.get("is_uncensored_leak"):
        add("流出")
    add(str(tags.get("resolution") or "").strip())
    if tags.get("is_vr"):
        add("VR")
    add(str(tags.get("edition") or "").strip())
    part = tags.get("part_no")
    if part not in (None, "", 0, "0"):
        text = str(part).strip().upper()
        add(text if text.startswith("CD") else f"CD{text}")
    if tags.get("is_iso"):
        add("ISO")
    return out


def json_tags(value: Any) -> Dict[str, Any]:
    """`downloads.version_tags` 是 **JSON 串**（S1 报告 §2.1），`media_item` 那份是 dict：

    这里统一成 dict 给 `version_labels()` 用；解析失败回空字典。
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            loaded = json.loads(value)
        except ValueError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def download_state_name(value: Any) -> str:
    """台账 `state` → `film_view().states.download`（契约 §4 的取值集）。"""
    text = _DOWNLOAD_STATE_MAP.get(str(value or "").strip().lower(), "")
    return text if text in DOWNLOAD_STATES else "none"


def scrape_state_of(meta: Any, item: Any = None) -> str:
    """`states.scrape`：实例行有 `scrape_state` 就用它，否则按作品级 `completeness` 兜底。"""
    if isinstance(item, dict):
        state = str(item.get("scrape_state") or "").strip()
        if state in SCRAPE_STATES:
            return state
    completeness = str((meta or {}).get("completeness") or "").strip() if isinstance(meta, dict) else ""
    return _SCRAPE_STATE_MAP.get(completeness, "unscraped")


# 展示番号（`display_number`）与「一部片挑哪个键」（`emby.key_rank` / `emby.best_keys`）
# 2026-10-12 起都住在 `emby.py`：与 `emby.norm_key()` 是同一套番号口径的几半，放一处才不会漂，
# 顺带让「Emby 库 → 界面行」（`emby.library_rows()`）能脱离宿主被单测直接加载。

# 映射表（S3 的 `namemap`）的**进程内就绪闸门**（S10 验收缺口）：`namemap.load()` 原先在插件
# 启动路径上从来没被调用过，后果是**静默**的 —— `ready()=False`、`actor_lookup()/tag_lookup()`
# 恒 None、`to_simplified('騎乗位')` 原样返回（繁→简失效）、`clean_tags()` 不过滤删除规则，
# 而且一声不响。现在：第一次用到映射表时 `load()` + `sync_store()` 各跑一次（实测 76ms + 43ms，
# 都幂等），成功与否都只在这一个进程里试一次，避免坏资源文件把日志刷爆。
_NAMEMAP_TRIED = False
_NAMEMAP_LOCK = threading.Lock()


def ui_file(path: str) -> Optional[Path]:
    """把 `/ui/{path}` 的子路径安全地解析成 `ui/` 目录内的文件；越界或不存在返回 None。

    含 `..` 的路径（包括被二次百分号编码、解码后才现形的）一律拒绝，解析后必须仍在 `ui/`
    目录内；只服务文件，不列目录。
    """
    rel = unquote(str(path or "")).strip("/")
    if not rel or ".." in rel:
        return None
    base = UI_DIR.resolve()
    try:
        target = (base / rel).resolve()
    except OSError:
        return None
    if not target.is_relative_to(base) or not target.is_file():
        return None
    return target


def ui_media_type(path: Path) -> str:
    """静态资源的 Content-Type：先查扩展名表，再退回标准库猜测，最后 octet-stream。"""
    guessed = mimetypes.guess_type(path.name)[0]
    return UI_EXT_MIME.get(path.suffix.lower()) or guessed or "application/octet-stream"


def size_text(size: Any) -> str:
    """字节数 → 人类可读文本（B 取整，KB/MB/GB 保留 1 位小数，「4.2 GB」这种）。"""
    try:
        value = max(float(size or 0), 0.0)
    except (TypeError, ValueError):
        value = 0.0
    if value < 1024:
        return f"{value:.0f} B"
    for unit in ("KB", "MB"):
        value /= 1024
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value / 1024:.1f} GB"


def is_keep_file(path: Path) -> bool:
    """缓存清理必须保留的文件：插件自管的 SQLite 库与它的事务副产物。

    数据库就落在元数据目录（`<数据根>/meta/avhelper.db`），与 JSON 缓存同目录；
    而孤儿扫描按「不在 cache_idx 里就删」判定，不排除它会把订阅/收藏/任务一起删掉。
    """
    return path.name.startswith("avhelper.db")


class AVHelper(_PluginBase):
    """AV 资源助手：JAV 番号订阅、榜单浏览、PT 自动选种下载。"""

    plugin_name = "AV 资源助手"
    plugin_desc = "JAV 榜单/演员/详情浏览，番号与演员订阅，PT 选种下载与 Telegram 通知"
    plugin_icon = ("https://raw.githubusercontent.com/ssmengyan/"
                   "MoviePilot-Plugins-AV/main/icons/avhelper.png")
    # 版本：0.7.0 = 自建刮削层（番号解析/中文简介/翻译/封面裁切/Emby 安全写入与回滚）
    plugin_version = "0.7.0"
    plugin_label = "发现"
    plugin_author = "ssmengyan"
    plugin_config_prefix = "avhelper_"
    plugin_order = 100
    auth_level = 1

    _enabled = False
    _proxy = DEFAULT_PROXY
    _javdb_bin = ""          # 手动指定的 javdb 二进制路径；留空按 paths 的默认顺序解析
    _data_root = ""          # 手动指定的数据根；留空按 paths 的默认顺序解析
    # 缓存总量上限（GB，超出按最旧淘汰）：配置键 `cache_max_gb`，默认 1G，见 paths.cache_limit_gb()
    _cache_max_gb = paths.DEFAULT_CACHE_MAX_GB
    _client: Optional[JavdbClient] = None
    _store: Optional[Store] = None
    _limiter: Optional[RateLimiter] = None
    _notifier: Optional[Notifier] = None
    _engine: Optional[TaskEngine] = None
    _emby_host = ""
    _emby_apikey = ""
    _emby_lib: Optional[emby.EmbyLibrary] = None
    _emby_sig: Optional[Tuple[str, str]] = None
    # 写侧客户端（S2 的 `EmbyClient`）：同样按连接信息惰性创建，见 emby_client()
    _emby_client: Optional[Any] = None
    _emby_client_sig: Optional[Tuple[str, str]] = None
    _cache_size_cache: Tuple[float, int] = (0.0, 0)   # (取样时间, 字节数)：缓存体积的内存缓存
    # (取样时间, 已下载番号键)：台账「已下载」徽标的 30 秒内存缓存，见 _downloaded_keys()
    _download_keys: Tuple[float, Set[str]] = (0.0, set())
    _warm_thread: Optional[threading.Thread] = None   # 启动预热线程（守护线程，见 warm_up）
    _warm_stop: Optional[threading.Event] = None      # 当前这次预热的停机信号（每次新建一份）
    # 刮削线 v4 的 11 项配置**存在 kv 的 `global_rule` 里**（前端设置台 S9 已在用这套 camelCase
    # 键名），不落宿主配置、也不进 `DEFAULT_RULE`：只由 `scrape_conf()` 读 + 回落默认值，见它。
    # film_view 投影的进程内缓存：(取样时间, {meta/media_item/台账 索引})，见 _film_index()
    _film_cache: Tuple[float, Dict[str, Any]] = (0.0, {})
    # 逐番号的投影结果缓存（S7 的 `scraper.film_view()` 那条路也吃它，见 film_views）
    _view_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    # 数据源自检的内存缓存：(取样时间, 行表)，见 _scrape_sources()
    _sources_cache: Tuple[float, List[Dict[str, Any]]] = (0.0, [])
    # `/scrape/run` 的单飞闸门：全库写入不允许并发（与限流政策无关，是"别自己踩自己"）
    _scrape_busy = threading.Lock()

    # ---------- 生命周期 ----------

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """读取配置并装配存储、限流、通知与任务引擎；允许重复调用。"""
        self.stop_service()
        self._enabled = False
        self._emby_host = ""
        self._emby_apikey = ""
        self._data_root = ""
        # 缓存上限每次都从默认值重来：老配置里没有这个键（0.6.3 之前存的），
        # 上面那次 `if config` 又不会执行赋值，必须在这里显式回落，否则会留着上一轮的值
        self._cache_max_gb = paths.DEFAULT_CACHE_MAX_GB
        if config:
            self._enabled = bool(config.get("enabled"))
            self._proxy = str(config.get("proxy") or "")
            self._javdb_bin = str(config.get("javdb_bin") or "").strip()
            self._data_root = str(config.get("data_root") or "").strip()
            self._emby_host = str(config.get("emby_host") or "").strip()
            self._emby_apikey = str(config.get("emby_apikey") or "").strip()
            self._cache_max_gb = paths.cache_limit_gb(config.get("cache_max_gb"))
        # 路径必须在建 Store 之前定型：SQLite 文件、JSON 缓存、图片缓存都按数据根落盘
        paths.configure(data_root=self._data_root, javdb_bin=self._javdb_bin,
                        fallback_root=self.get_data_path())

        self._store = Store()
        self._store.init()
        self._limiter = RateLimiter(self._store)
        self._notifier = Notifier(self, self._store)
        self._engine = TaskEngine(self, self._store, self._limiter, self._notifier)

        self._emby_lib = None
        self._emby_sig = None
        self._emby_client = None
        self._emby_client_sig = None
        self._client = JavdbClient(bin_path=self._javdb_bin or None, proxy=self._proxy)
        # 失败冷却挂在 client 模块级：改完代理重跑 init_plugin 时一并清零，
        # 否则「改完代理点重试」还要再等满 1 小时，等于告诉用户没修好
        reset_javdb_state()
        # 启动留一条可查的状态行：远程用户报「榜单加载不出来」时，这一行就能区分
        # 「二进制没下下来」（未就绪）和「二进制在但抓不到」（就绪 + 后面的失败原因）
        logger.info(f"AVHelper 启动：数据根 {paths.data_root()}；javdb {paths.javdb_bin()}"
                    f"（{'可执行' if paths.javdb_ready() else '不存在'}）；"
                    f"代理 {mask(self._proxy) if self._proxy else '未配置（直连）'}")
        # 清掉上次留的抓取失败负缓存：刚改完代理/换完网络，第一次打开就该真抓一次，
        # 而不是继续吃 120 秒前的旧结论（进程内的 1 小时冷却会随 reload 一起归零）
        self.drop_fail_cache()
        # 映射表预热（S10 验收缺口）：`namemap.load()` 历史上从来没被调用过，导致启动后
        # 繁简转换/标签清洗/演员中文名全是**静默**空操作。这里 best-effort 跑一次（幂等，约 120ms），
        # 端点上（`_namemap_rows()` / `actor_zh()`）还有同一道闸门兜底；失败不让 init_plugin 抛。
        try:
            self.namemap_module()
        except Exception as error:
            logger.warning(f"AVHelper 映射表预热失败（端点首次访问会再试一次）：{error}")
        self.start_javdb_bootstrap()
        self.start_warm_up()

    def drop_fail_cache(self) -> int:
        """删掉所有 `fail:` 负缓存（启动/reload/存配置时调用），返回清掉的条数。"""
        try:
            stale = [str(row.get("key") or "") for row in self.store.cache_all()
                     if str(row.get("key") or "").startswith("fail:")]
            for key in stale:
                self._cache_forget(key)
            if stale:
                logger.info(f"AVHelper 清掉 {len(stale)} 条上次的抓取失败负缓存，本次重抓")
            return len(stale)
        except Exception as error:
            logger.warning(f"AVHelper 清理失败负缓存出错：{error}")
            return 0

    def get_state(self) -> bool:
        """获取插件启用状态。"""
        return self._enabled

    def stop_service(self) -> None:
        """释放后台资源：取消挂起的“立即检查”任务、让启动预热收手（宿主会自动摘除 cron 服务）。"""
        if self._warm_stop is not None:
            self._warm_stop.set()
        self._warm_thread = None
        try:
            remove_plugin_once_job(self.__class__.__name__, ONCE_JOB_ID)
        except Exception:
            pass

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """本插件不注册远程命令。"""
        return []

    # ---------- 宿主扩展点 ----------

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时服务：订阅检查（每天 3 次）与缓存清理（每天 4 点）。

        本插件是在用插件，两个 cron 必须挂着 —— 否则订阅检查会静默停摆。
        （若用分身/副本再装一份，务必只让一边挂 cron：会重复抓站点、重复下载。）
        """
        return [
            {"id": "subcheck", "name": "AV 订阅检查", "trigger": "cron",
             "kwargs": {"hour": "9,14,21", "minute": "30"}, "func": self.job_subcheck},
            {"id": "cacheclean", "name": "AV 缓存清理", "trigger": "cron",
             "kwargs": {"hour": 4, "minute": 0}, "func": self.job_cacheclean},
        ]

    def get_media_source(self) -> Optional[List[Dict[str, Any]]]:
        """注册插件提供的 JAVDB 媒体数据源。

        与 `get_service` 同理：注册后宿主「媒体数据源」里才有 JAVDB。
        """
        return [{"name": "JAVDB", "media_source": "javdb", "media_types": ["电影"]}]

    def get_module(self) -> Optional[Dict[str, Any]]:
        """胁持媒体识别：只接手 javdb 来源的番号识别。"""
        return {"async_recognize_media": self._recognize_media}

    async def _recognize_media(self, meta: Any = None, mtype: Any = None,
                               media_source: Any = None, media_id: Any = None,
                               **kwargs: Any) -> Any:
        """番号识别钩子：仅处理 media_source == 'javdb' 的请求，其它一律返回 None。

        参数名必须与宿主分发实参一致（media_source/media_id），否则识别会静默失配；
        必须容忍 meta=None（详情端点不会传 meta）。
        """
        if str(media_source or "") != "javdb" or not media_id:
            return None
        # 与自带界面共用同一份 7 天详情缓存：任一侧抓过，另一侧就直接命中
        detail = await asyncio.to_thread(
            self._cached, f"detail:{media_id}", TTL_DETAIL,
            lambda: self.cli().detail(str(media_id)),
        )
        if not detail:
            return None
        try:
            from app.sdk.media import MediaInfo  # 延迟导入，避免模块导入期依赖宿主

            info = MediaInfo()
            info.media_source = "javdb"
            info.media_id = str(media_id)
            title = str(detail.get("title") or detail.get("origin_title") or media_id)
            info.title = title
            info.original_title = str(detail.get("origin_title") or "")
            info.year = str(detail.get("release_date") or "")[:4]
            info.poster = self.image_url(detail.get("cover_url"))
            info.overview = str(detail.get("summary") or "")
            info.actors = [
                {"name": a.get("name"), "avatar": self.image_url(a.get("avatar_url"))}
                for a in (detail.get("actors") or []) if isinstance(a, dict) and a.get("name")
            ]
            # v3 的响应模型要求这两项是**对象列表**（`MediaPerson` / `MediaCompany`）。
            # 塞纯字符串会让宿主 `GET /api/v1/media/{id}` 直接 500（ResponseValidationError：
            # `production_companies[0]` 收到 'S1 NO.1 STYLE' 不是对象）——2026-10-10 实测复现。
            director = str(detail.get("director_name") or "").strip()
            maker = str(detail.get("maker_name") or "").strip()
            info.directors = [{"name": director}] if director else []
            info.production_companies = [{"name": maker}] if maker else []
            self.remember_actor([str(media_id)], (info.actors or [{}])[0].get("name") or "")
            return info
        except Exception as error:  # 识别失败必须让原生模块继续工作
            logger.error(f"AVHelper 识别 {media_id} 失败：{error}")
            return None

    # ---------- 配置与页面 ----------

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """配置页：启用开关、javdb 代理、javdb 二进制路径、数据根、缓存上限与 Emby 覆盖项。"""
        form = [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VSwitch",
                                          "props": {"model": "enabled", "label": "启用插件"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VTextField",
                                          "props": {"model": "proxy", "label": "代理地址（可留空）",
                                                    "placeholder": "http://host:port，留空 = 直连"}}]},
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VTextField",
                                          "props": {"model": "javdb_bin", "label": "javdb 路径（可留空）",
                                                    "placeholder": "留空 = 自动下载 / 自动查找"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VTextField",
                                          "props": {"model": "data_root", "label": "数据目录（可留空）",
                                                    "placeholder": "留空 = MP 插件数据目录（/config/plugins/AVHelper）"}}]},
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VTextField",
                                          "props": {"model": "emby_host", "label": "Emby 地址（可留空）",
                                                    "placeholder": "留空则用 MoviePilot 已配置的媒体服务器"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VTextField",
                                          "props": {"model": "emby_apikey", "label": "Emby API 密钥（可留空）",
                                                    "placeholder": "留空则用 MoviePilot 已配置的媒体服务器"}}]},
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VTextField",
                                          "props": {"model": "cache_max_gb",
                                                    "label": "缓存上限 GB（默认 1）",
                                                    "placeholder": "留空 = 1G；实测长期占用 < 0.3G",
                                                    "type": "number"}}]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6},
                             "content": [{"component": "VAlert",
                                          "props": {"type": "info", "variant": "tonal",
                                                    "density": "compact", "class": "mt-1"},
                                          "text": "图片与番号元数据的缓存总量上限：超过就按最旧淘汰"
                                                  "（每天 4 点跑一次，也可随时在设置台点「清理缓存」）。"
                                                  "默认 1G 够用；填 0.1 以下会按 0.1 处理。"}]},
                        ],
                    },
                    {"component": "VAlert",
                     "props": {"type": "info", "variant": "tonal", "class": "mt-2"},
                     "text": "完整界面在插件详情页内（内嵌应用）：榜单、演员、订阅、任务、通知与站点检索都在里面。"},
                    {"component": "VAlert",
                     "props": {"type": "info", "variant": "tonal", "class": "mt-2"},
                     "text": "javdb 是发现层依赖（javdb-cli 单文件二进制）。留空时插件会在后台自动下载一份"
                             "到数据目录；网络不通就手工放一份并在上面填路径。"},
                    {"component": "VAlert",
                     "props": {"type": "info", "variant": "tonal", "class": "mt-2"},
                     "text": "Emby 用于给界面里的番号打「已入库」标记（没有的片不显示标记）。"
                             "两栏都留空时自动复用 MoviePilot「设置 → 媒体服务器」里的 Emby。"},
                ],
            }
        ]
        return form, {"enabled": self._enabled, "proxy": self._proxy,
                      "javdb_bin": self._javdb_bin, "data_root": self._data_root,
                      "emby_host": self._emby_host, "emby_apikey": self._emby_apikey,
                      "cache_max_gb": self._cache_max_gb}

    def get_page(self) -> Optional[List[dict]]:
        """详情页：内嵌自带应用界面（宿主 JSON 页面无法承载交互式界面）。"""
        if not self._enabled:
            return [{
                "component": "VAlert",
                "props": {"type": "warning", "variant": "tonal", "class": "ma-2"},
                "text": "插件尚未启用：请先在插件设置中开启。",
            }]
        # 尾斜杠不能省：文档 URL 带 `/ui/` 时 ES module 的 `./app.js` 才会解析到 `/ui/app.js`
        src = f"/api/v1/plugin/{PLUGIN_ID}/ui/?v={self.plugin_version}"
        return [
            {
                "component": "iframe",
                "props": {
                    "src": src,
                    "style": "width:100%;height:78vh;min-height:560px;border:0;margin-top:8px;"
                             "border-radius:10px;background:transparent",
                },
            },
        ]

    def get_render_mode(self) -> Tuple[str, Optional[str]]:
        """使用 Vue 联邦模式：弹窗正文交给 `frontend/dist/assets` 里的远程组件。

        切到 `vue` 之后宿主**不再画右下角那个齿轮按钮**（那是 `vuetify` 分支专有的 `VFab`），
        设置台与数据台都由组件自己绘制。`get_form()` 仍提供宿主配置模型的默认值，
        `get_page()` 保留 iframe 作为旧宿主/联邦加载失败时的回退。
        """
        return "vue", "frontend/dist/assets"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """侧栏联邦入口需要 Vue 构建产物，本插件不提供。"""
        return []

    # ---------- API 注册 ----------

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 列表：`/ui` 三连（含静态资源）与 `/img` 匿名，其余 bear 鉴权。"""
        return [
            {"path": "/ui", "endpoint": self.api_ui, "methods": ["GET"], "allow_anonymous": True,
             "summary": "应用界面入口(307→/ui/)", "description": "自带界面，无密钥，补尾斜杠"},
            {"path": "/ui/", "endpoint": self.api_ui_index, "methods": ["GET"], "allow_anonymous": True,
             "summary": "应用界面(HTML)", "description": "自带界面，无密钥"},
            {"path": "/ui/{path:path}", "endpoint": self.api_ui_file, "methods": ["GET"],
             "allow_anonymous": True, "summary": "界面静态资源",
             "description": "ui/ 目录下的 js/css/图片，按扩展名给 MIME，每次从盘上读"},
            {"path": "/img", "endpoint": self.api_img, "methods": ["GET"], "allow_anonymous": True,
             "summary": "图片代理(XOR解包)", "description": "白名单图床，匿名开放"},
            {"path": "/bootstrap", "endpoint": self.api_bootstrap, "methods": ["GET"], "auth": "bear",
             "summary": "首屏状态聚合"},
            {"path": "/rankings", "endpoint": self.api_rankings, "methods": ["GET"], "auth": "bear",
             "summary": "榜单", "description": "日/周/月 × 有码/无码/FC2"},
            {"path": "/actors", "endpoint": self.api_actors, "methods": ["GET"], "auth": "bear",
             "summary": "演员榜"},
            {"path": "/actor", "endpoint": self.api_actor, "methods": ["GET"], "auth": "bear",
             "summary": "演员档案+作品史"},
            {"path": "/search", "endpoint": self.api_search, "methods": ["GET"], "auth": "bear",
             "summary": "番号/演员搜索"},
            {"path": "/detail", "endpoint": self.api_detail, "methods": ["GET"], "auth": "bear",
             "summary": "影片详情"},
            {"path": "/longimage", "endpoint": self.api_longimage, "methods": ["GET"], "auth": "bear",
             "summary": "长缩略图 URL"},
            {"path": "/favs", "endpoint": self.api_favs, "methods": ["GET", "POST", "DELETE"],
             "auth": "bear", "summary": "收藏演员"},
            {"path": "/aliases", "endpoint": self.api_aliases, "methods": ["GET", "POST"],
             "auth": "bear", "summary": "演员自定义备注",
             "description": "GET 列出全部非空备注；POST {name,alias} 写入，alias 空串 = 清除。与收藏解耦"},
            {"path": "/subs", "endpoint": self.api_subs, "methods": ["GET", "POST", "DELETE"],
             "auth": "bear", "summary": "订阅管理"},
            {"path": "/rule", "endpoint": self.api_rule, "methods": ["GET", "POST"],
             "auth": "bear", "summary": "全局默认规则"},
            {"path": "/tasks", "endpoint": self.api_tasks, "methods": ["GET"], "auth": "bear",
             "summary": "任务与下载队列"},
            {"path": "/tasks/search", "endpoint": self.api_task_search, "methods": ["POST"],
             "auth": "bear", "summary": "搜种并打分"},
            {"path": "/tasks/acquire", "endpoint": self.api_task_acquire, "methods": ["POST"],
             "auth": "bear", "summary": "下载该影片(按规则自动下载或转待确认)",
             "description": "详情页按钮用：搜种后按全局规则的 trigger 决定直接下单还是落一条待确认任务；"
                            "与 /tasks/search 的检索语义分开，站点搜索页不受影响"},
            {"path": "/tasks/download", "endpoint": self.api_task_download, "methods": ["POST"],
             "auth": "bear", "summary": "提交下载"},
            {"path": "/tasks/cancel", "endpoint": self.api_task_cancel, "methods": ["POST"],
             "auth": "bear", "summary": "取消任务／不要了",
             "description": "{id} = 老行为，只取消待确认任务；{number|key, cancel_sub:true} = "
                            "三出口联动（删种子/台账/订阅/known），cancel_sub 默认 false，结果在 steps"},
            {"path": "/downloads", "endpoint": self.api_downloads, "methods": ["GET", "DELETE"],
             "auth": "bear", "summary": "下载台账(下载历史)",
             "description": "GET 列出**本插件下载过**的台账条目并迁移老队列；DELETE ?key= 移除一条记录后回最新列表"
                            "（?cancel_sub=true 才连种子/订阅一起清＝三出口联动，默认 false，结果在 steps）"},
            {"path": "/library", "endpoint": self.api_library, "methods": ["GET"],
             "auth": "bear", "summary": "已入库的番号",
             "description": "Emby 媒体库**实时**列表（已删除的不在其中）；?fresh=1 丢掉索引缓存重抓"},
            {"path": "/magnet-download", "endpoint": self.api_magnet_download, "methods": ["POST"],
             "auth": "bear", "summary": "详情页磁力直接下载"},
            {"path": "/check", "endpoint": self.api_check, "methods": ["POST"], "auth": "bear",
             "summary": "手动检查订阅(受限流)"},
            {"path": "/notices", "endpoint": self.api_notices, "methods": ["GET", "DELETE"],
             "auth": "bear", "summary": "通知列表/清空"},
            {"path": "/sites", "endpoint": self.api_sites, "methods": ["GET"], "auth": "bear",
             "summary": "已配置站点"},
            {"path": "/cache/clean", "endpoint": self.api_cache_clean, "methods": ["POST"],
             "auth": "bear", "summary": "清理缓存"},
            # ---- 刮削线 v4（契约 §3.7）：工作台 / 映射表，全部 bear 鉴权 ----
            {"path": "/scrape/status", "endpoint": self.api_scrape_status, "methods": ["GET"],
             "auth": "bear", "summary": "刮削状态",
             "description": "workspace：stats/sources/queue/last_run/items（支持 limit/offset/filter）"},
            {"path": "/scrape/preview", "endpoint": self.api_scrape_preview, "methods": ["GET"],
             "auth": "bear", "summary": "刮削字段级预览",
             "description": "?key= 单条试跑：只算 diff 不写 Emby（scraper.preview_one）"},
            {"path": "/scrape/run", "endpoint": self.api_scrape_run, "methods": ["POST"],
             "auth": "bear", "summary": "执行刮削",
             "description": "POST {keys?[],all?,force?,anchor?}；all=true 必须带 confirm=true（防误点全库写入）"},
            {"path": "/scrape/rollback", "endpoint": self.api_scrape_rollback, "methods": ["POST"],
             "auth": "bear", "summary": "回滚 Emby 元数据",
             "description": "POST {item_key}：用写前备份的完整 DTO 原样回灌（D7 闸门）"},
            {"path": "/scrape/log", "endpoint": self.api_scrape_log, "methods": ["GET"],
             "auth": "bear", "summary": "刮削日志与数据源汇总",
             "description": "?limit= 取 scrape_log 最近若干条 + 各源成功/失败/耗时汇总"},
            {"path": "/scrape/selfcheck", "endpoint": self.api_scrape_selfcheck, "methods": ["POST"],
             "auth": "bear", "summary": "翻译模型自检",
             "description": "POST {model?} → translator.selfcheck()：「模型自检」按钮；"
                            "另有 POST {sources:true} → scraper.sources_selfcheck()（真探针，3~5 秒）"},
            {"path": "/namemap/actors", "endpoint": self.api_namemap_actors, "methods": ["GET"],
             "auth": "bear", "summary": "演员映射表",
             "description": "?q=&limit= 查 name_map 的 actor 行（三语 + 别名 + 来源）"},
            {"path": "/namemap/tags", "endpoint": self.api_namemap_tags, "methods": ["GET"],
             "auth": "bear", "summary": "标签映射表",
             "description": "?q=&limit= 查 name_map 的 tag 行（含 is_delete_rule 删除规则）"},
            {"path": "/namemap/set", "endpoint": self.api_namemap_set, "methods": ["POST"],
             "auth": "bear", "summary": "写入用户映射",
             "description": "POST {name,zh,jp?,entity_type?}：写 source=user_custom 的最高优先级映射"},
        ]

    # ---------- 基础设施 ----------

    @property
    def store(self) -> Store:
        """存储入口（懒初始化，保证任一入口先到时也能用）。"""
        if self._store is None:
            self._store = Store()
            self._store.init()
        return self._store

    @property
    def limiter(self) -> RateLimiter:
        """限流器入口。"""
        if self._limiter is None:
            self._limiter = RateLimiter(self.store)
        return self._limiter

    @property
    def notifier(self) -> Notifier:
        """通知入口。"""
        if self._notifier is None:
            self._notifier = Notifier(self, self.store)
        return self._notifier

    @property
    def engine(self) -> TaskEngine:
        """任务引擎入口。"""
        if self._engine is None:
            self._engine = TaskEngine(self, self.store, self.limiter, self.notifier)
        return self._engine

    def cli(self) -> JavdbClient:
        """取 javdb 客户端，未初始化时按当前代理与二进制路径兜底。"""
        if self._client is None:
            self._client = JavdbClient(bin_path=self._javdb_bin or None, proxy=self._proxy)
        return self._client

    @property
    def proxy_kwargs(self) -> Dict[str, str]:
        """`RequestUtils` 要的代理参数；留空代理时返回空字典（不能传空串，等于给个坏代理）。"""
        if not self._proxy:
            return {}
        return {"http": self._proxy, "https": self._proxy}

    def emby(self) -> emby.EmbyLibrary:
        """Emby 库查询入口（连接信息变了就换实例，索引随之重建）。"""
        host, apikey = self._emby_conn()
        sig = (host, apikey)
        if self._emby_lib is None or self._emby_sig != sig:
            self._emby_lib = emby.EmbyLibrary(host, apikey)
            self._emby_sig = sig
        return self._emby_lib

    def _emby_conn(self) -> Tuple[str, str]:
        """Emby 连接：插件自己配了就用插件的，否则复用 MP 的媒体服务器配置。

        两条路都取不到时返回空串，查询一律落空 → 界面不显示任何「已入库」标记。
        """
        if self._emby_host and self._emby_apikey:
            return self._emby_host, self._emby_apikey
        return emby.mp_emby_conf()

    def image_url(self, url: Any) -> str:
        """把图床地址转成本插件图片代理地址（前端可直接 <img src>）。"""
        if not url:
            return ""
        return f"/api/v1/plugin/{PLUGIN_ID}/img?url={quote(str(url), safe='')}"

    def emby_image_url(self, item_id: Any, img_type: str = "Primary") -> str:
        """Emby 原图的插件代理地址（契约 §3.5 的 `?emby=` 分支）。

        **服务端回源**：Emby 主机名与 API Key 只在这一侧用，浏览器拿到的就是这个地址
        （所以 `/img` 才能保持匿名）。`item_id` 为空回空串（调用方据此回落远程图）。
        """
        target = str(item_id or "").strip()
        if not target:
            return ""
        kind = str(img_type or "Primary").strip() or "Primary"
        return (f"/api/v1/plugin/{PLUGIN_ID}/img?emby={quote(target, safe='')}"
                f"&type={quote(kind, safe='')}")

    def _raw_image(self, url: Any) -> str:
        """把插件图片代理地址还原成图床原地址（本来就是原地址时原样返回）。"""
        text = str(url or "")
        marker = f"/api/v1/plugin/{PLUGIN_ID}/img?url="
        return unquote(text.split(marker, 1)[1]) if marker in text else text

    def remember_thumbs(self, movies: Any) -> None:
        """登记「番号 → 封面原图」，供任务与下载队列补图（一次调用只写一次库）。

        来源是各类 javdb 列表与详情（都带 cover_url/thumb_url）。只存原地址，
        读的时候再转代理地址，免得出现「代理套代理」。
        """
        rows = movies if isinstance(movies, list) else [movies]
        index = self.store.kv_get(THUMB_KEY, {}) or {}
        changed = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = num_key(row.get("number"))
            # 优先小竖图（thumb_url 147x200）：正好塞进任务行 3:4 的方框，不用裁也不费流量
            raw = self._raw_image(row.get("thumb_url") or row.get("cover_url"))
            if key and raw and index.get(key) != raw:
                index[key] = raw
                changed = True
        if not changed:
            return
        if len(index) > 5000:      # 控制体量：超出后只留最近写入的一段
            index = dict(list(index.items())[-5000:])
        self.store.kv_set(THUMB_KEY, index)

    def thumbs_of(self, numbers: Iterable[str]) -> Dict[str, str]:
        """批量取番号封面（插件代理地址）。

        只读本地索引与 7 天详情缓存，**不发网络请求**（列表页首屏不能为了一张图去起子进程）；
        详情缓存命中的顺带补进索引。返回的 key 是调用方传进来的原字符串。
        """
        index = self.store.kv_get(THUMB_KEY, {}) or {}
        found: Dict[str, str] = {}
        fresh: List[Dict[str, str]] = []
        for number in (numbers or []):
            text = str(number or "")
            key = num_key(text)
            if not key or text in found:
                continue
            raw = str(index.get(key) or "")
            if not raw:
                detail = self._cache_read(f"detail:{text}", TTL_DETAIL)
                if isinstance(detail, dict):
                    raw = str(detail.get("thumb_url") or detail.get("cover_url") or "")
                    if raw:
                        fresh.append({"number": key, "cover_url": raw})
            if raw:
                found[text] = self.image_url(raw)
        if fresh:
            self.remember_thumbs(fresh)
        return found

    def fill_thumbs(self, *groups: Any) -> bool:
        """给任务 / 队列项就地补封面。

        索引里有这个番号就以索引为准（历史数据里存的老图会被顺带换成当前口径的小竖图）；
        索引里没有、自己又没图的，才去翻详情缓存。全程不发网络请求。

        :return: 是否有条目被改（下载队列据此决定要不要落库）
        """
        items = [x for group in groups for x in (group or []) if isinstance(x, dict)]
        missing = [str(x.get("number") or "") for x in items if x.get("number")]
        if not missing:
            return False
        thumbs = self.thumbs_of(missing)
        changed = False
        for item in items:
            hit = thumbs.get(str(item.get("number") or ""))
            if hit and item.get("thumb") != hit:
                item["thumb"] = hit
                changed = True
        return changed

    def global_rule(self) -> Dict[str, Any]:
        """全局默认规则：用户在界面编辑、存 kv 表；手动搜种与新建订阅都以它为基准。"""
        rule = self.store.kv_get(GLOBAL_RULE_KEY) or {}
        return merge_rule(rule)

    def scrape_conf(self) -> Dict[str, Any]:
        """刮削设置的 11 项（**存放在 kv 的 `global_rule` 里**，不是宿主插件配置）。

        口径（主统筹 2026-10-14 更正，覆盖任务书 E 段）：前端设置台 S9 已经在用这套
        camelCase 键名读写 `global_rule`，所以这里**只读不写**、缺键逐项回落默认值 ——
        老用户在 0.6.3 存下的规则里没有这些键，照样不能报错。`merge_rule()` 不认识也会
        原样透传（它只补默认 + 夹限流两项），所以 `/rule` POST 写进来的这些键能存住。

        键名一个字母都不许改（前端按这套读）：`scrapeMode` / `plotJavtxt` / `plotMetatube` /
        `translateModel` / `translateModelFallback` / `cropAnchor` / `trailerMode` /
        `autoScrapeTier1` / `autoScrapeTier2` / `cleanSuffixes` / `nameTemplate`。
        """
        rule = self.global_rule() or {}
        suffixes = rule.get("cleanSuffixes")
        return {
            "scrapeMode": pick_choice(rule.get("scrapeMode"), SCRAPE_MODES, "fill"),
            "plotJavtxt": pick_bool(rule.get("plotJavtxt"), True),
            "plotMetatube": pick_bool(rule.get("plotMetatube"), True),
            "translateModel": str(rule.get("translateModel") or "").strip() or "hy3",
            "translateModelFallback": (str(rule.get("translateModelFallback") or "").strip()
                                       or "deepseek-v4.1-flash"),
            "cropAnchor": pick_choice(rule.get("cropAnchor"), CROP_ANCHORS, "auto"),
            "trailerMode": pick_choice(rule.get("trailerMode"), TRAILER_MODES, "off"),
            "autoScrapeTier1": pick_bool(rule.get("autoScrapeTier1"), True),
            "autoScrapeTier2": pick_bool(rule.get("autoScrapeTier2"), True),
            "cleanSuffixes": [str(x).strip() for x in suffixes if str(x).strip()]
                             if isinstance(suffixes, list) else [],
            "nameTemplate": (str(rule.get("nameTemplate") or "").strip()
                             or "{number}{badge} {title}"),
        }

    def magnets_cached(self, number: str) -> Optional[List[Dict[str, Any]]]:
        """磁力列表：优先读 7 天文件缓存（与详情页共用同一个 key），未命中才起子进程。

        返回 None 表示抓取失败；空列表表示 javdb 上确实没有磁力。
        """
        data = self._cached(f"magnets:{number}", TTL_DETAIL,
                            lambda: self.cli().magnets(number, cnsub=False))
        if not isinstance(data, dict):
            return None
        return list(data.get("magnets") or [])

    def magnets_failed_recently(self, number: str) -> bool:
        """磁力抓取是否处于失败负缓存期内（该期间内不再重试）。"""
        return self._cache_read(f"fail:magnets:{number}", FAIL_TTL) is not None

    def remember_actor(self, numbers: List[str], actor: str) -> None:
        """记录“番号 → 演员”映射，让榜单卡片能显示演员与收藏徽标。"""
        if not actor:
            return
        index = self.store.kv_get("num2actor", {}) or {}
        changed = False
        for number in numbers:
            if number and index.get(number) != actor:
                index[number] = actor
                changed = True
        if not changed:
            return
        if len(index) > 5000:  # 控制体量，只保留最近的一部分
            index = dict(list(index.items())[-5000:])
        self.store.kv_set("num2actor", index)

    def _actor_of(self, number: str) -> str:
        """按番号查已知演员（未知返回空串）。"""
        index = self.store.kv_get("num2actor", {}) or {}
        return str(index.get(number) or "")

    def _cache_file(self, key: str) -> Path:
        """缓存文件路径（按 key 哈希命名）。"""
        return paths.meta_dir() / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

    def _cache_read(self, key: str, ttl: int) -> Any:
        """读 JSON 缓存；不存在或超过 TTL 返回 None。"""
        path = self._cache_file(key)
        try:
            if not path.exists() or time.time() - path.stat().st_mtime > ttl:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _cache_write(self, key: str, data: Any, ttl: int) -> None:
        """写 JSON 缓存并登记到清理索引。"""
        path = self._cache_file(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.store.cache_put(key, str(path), ttl)
        except Exception as error:
            logger.error(f"AVHelper 写缓存失败 {key}：{error}")

    def _cache_forget(self, key: str) -> None:
        """删掉某个 key 的缓存文件与索引行（用于清失败标记）。"""
        try:
            self._cache_file(key).unlink(missing_ok=True)
        except Exception:
            pass
        self.store.cache_drop([key])

    def _cached(self, key: str, ttl: int, loader: Any) -> Any:
        """带文件缓存的读取；失败写 FAIL_TTL 负缓存，避免每次重开都重付抓取时间。"""
        hit = self._cache_read(key, ttl)
        if hit is not None:
            return hit
        fail_key = f"fail:{key}"
        if self._cache_read(fail_key, FAIL_TTL) is not None:
            return None
        data = loader()
        if data is not None:
            self._cache_write(key, data, ttl)
            self._cache_forget(fail_key)
        else:
            # 原因一并落盘：进程重启后 `client` 的内存记录会清空，失败原因不能跟着丢
            self._cache_write(fail_key, {"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                         "reason": self.cli().last_error(key)}, FAIL_TTL)
        return data

    def fetch_error(self, key: str, default: str) -> str:
        """把发现层的失败原因翻成一句能贴到界面上的话。

        远程用户只有一个笼统的「抓取失败」时没法自救：这里把 javdb 子进程真正吐出来的
        那句话（二进制缺失 / 超时 / 退出码与 stderr 摘要）原样带出去，并补上冷却剩余时间
        —— 否则「改完代理点重试仍然失败」会被误判成没修好。
        """
        reason = self.cli().last_error(key)
        if not reason:
            marker = self._cache_read(f"fail:{key}", FAIL_TTL)
            if isinstance(marker, dict):
                reason = str(marker.get("reason") or "")
        reason = reason or default
        left = self.cli().cooldown_left(key)
        if left <= 0:
            return reason
        return f"{reason}（冷却中，约 {max(1, left // 60)} 分钟后自动重试）"

    # ---------- 启动预热 ----------

    def start_javdb_bootstrap(self) -> bool:
        """后台确保 javdb 二进制就位：缺文件就从官方 Release 下载一份，不阻塞宿主启动。

        别人新装这个插件时容器里没有 javdb，这一步让他们不必手工放二进制；已经有
        （配置指定 / 历史路径 / PATH）时只是校验一下，不发任何请求。
        """
        if paths.javdb_ready():
            logger.info(f"AVHelper javdb 就绪：{paths.javdb_bin()}")
            return False
        thread = threading.Thread(target=self._javdb_bootstrap, name="avhelper-javdb",
                                  daemon=True)
        thread.start()
        return True

    def _javdb_bootstrap(self) -> None:
        """下载 javdb 二进制（守护线程里跑，失败只记日志，不影响插件其它功能）。"""
        ok, detail = paths.ensure_javdb(proxy=self._proxy)
        if ok:
            logger.info(f"AVHelper javdb 已就位：{detail}")
        else:
            logger.warning(f"AVHelper javdb 未就绪：{detail}")

    def start_warm_up(self) -> bool:
        """启动后台首屏预热；宿主启动不被拖住。

        为什么要它：界面关掉再打开时，组件里的内存缓存（榜单 / 详情）会随弹窗卸载，
        真正能留下来的只有后端这几份文件缓存；而它们在 TTL 到点后又是「第一次打开才现抓」，
        首屏就要多等一次 javdb 抓取（约 1.5 秒）＋几十张封面逐张走代理（冷图最长约半分钟）。
        MP 启动时先把这一摊做掉，用户第一次打开插件就是纯缓存读取。

        只在插件启用时跑，并且带 `WARM_MIN_INTERVAL` 防抖（reload / 改配置都会重跑
        `init_plugin`，没必要每次重抓一遍）；真正干活的是守护线程 `warm_up`。
        """
        if not self._enabled:
            return False
        thread = self._warm_thread
        if thread is not None and thread.is_alive():
            return False
        try:
            last = float(self.store.kv_get(WARM_KV_KEY) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if last and time.time() - last < WARM_MIN_INTERVAL:
            return False
        # 停机信号按「这一次预热」新建并交给线程持有：`stop_service` 置位的是它自己那一份，
        # 不会误伤后来重载起的新线程（那是 2026-10-11 之前 `_warm_stop` 用类属性时的隐患）。
        stop = threading.Event()
        self._warm_stop = stop
        self._warm_thread = threading.Thread(
            target=self.warm_up, args=(stop,), name="avhelper-warmup", daemon=True,
        )
        self._warm_thread.start()
        return True

    def warm_up(self, stop: threading.Event) -> None:
        """预热首屏数据与封面（守护线程里跑，全程 best-effort，绝不向外抛）。"""
        try:
            # 缓存体积：先算一次，让首个 /bootstrap 直击 60 秒内存缓存（rglob 上万文件是它的大头）
            self.cache_size(force=True)
            # 台账补种（设计文档 §3「启动预热」）**放在榜单之前**：补种会把「已下载」写进台账，
            # 而下面的 `_warm_rank()` → `_movie()` 会读 `_downloaded_keys()` 的 30 秒缓存 ——
            # 先跑榜单会把一份**空**的键集合缓存住，用户启动后头 30 秒看到的卡片全都没有「已下载」
            # 标记（2026-10-11 真机实测到过这个空窗）。补种失败只在 seed_downloads 里记日志。
            if stop.is_set():
                return
            self.seed_downloads()
            failed: List[str] = []
            for period in WARM_RANK_PERIODS:
                if stop.is_set():
                    return
                if not self._warm_rank(period, stop):
                    failed.append(period)
            if stop.is_set():
                return
            # 演员榜：「我的演员」栏的候选列表，同样吃 TTL_RANK 缓存
            self._cached("actors", TTL_RANK, lambda: self.cli().actors_rank())
            self.store.kv_set(WARM_KV_KEY, int(time.time()))
            if failed:
                # 预热失败必须说话：否则日志里只剩「完成」，而首屏是空的（远程用户报障时无处可查）
                logger.warning(f"AVHelper 首屏预热部分失败：{'/'.join(failed)}（{WARM_KIND}）；"
                               f"原因：{self.fetch_error(f'rank:{failed[0]}:{WARM_KIND}', '未知')}")
            else:
                logger.info(f"AVHelper 首屏预热完成：榜单 {'/'.join(WARM_RANK_PERIODS)}（{WARM_KIND}）与封面")
        except Exception as error:            # 预热失败不影响任何功能，只是首屏回到原来的开销
            logger.error(f"AVHelper 首屏预热失败：{error}")

    def _warm_rank(self, period: str, stop: threading.Event) -> bool:
        """预热一档榜单：数据 + 番号封面索引 + 首屏封面图片 + Emby 索引；抓到数据返回 True。"""
        data = self._cached(
            f"rank:{period}:{WARM_KIND}", TTL_RANK,
            lambda: self.cli().rankings(period=period, kind=WARM_KIND),
        )
        if not isinstance(data, dict):
            return False
        movies = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
        self.remember_thumbs(movies)
        if movies:
            # 顺手做一次归一化：Emby 索引是懒建的（5 分钟内存缓存），首屏「已入库」标记要用
            self._movie(movies[0])
        for raw in movies[:WARM_IMAGE_LIMIT]:
            if stop.is_set():
                return True      # 停机不算失败，别再往下抓图
            # 预热哪一档必须与卡片实际显示的那一档一致（方案 B 起卡片用 `cover` 大图档）：
            # 这里还抓 `thumb` 就等于白抓一遍 —— 首屏照样要现拉 60 张大图，一张都省不下。
            # 代价：单档预热流量从约 0.7 MB 涨到约 9 MB（三档去重后约 20 MB），
            # 只付一次，之后 NAS 图片缓存与浏览器 30 天缓存都命中。
            url = str(raw.get("cover_url") or raw.get("thumb_url") or "")
            if not url or imgproxy.cached(url):
                continue
            imgproxy.fetch(url, proxy=self._proxy)
            time.sleep(WARM_IMAGE_GAP)
        return True

    def _detail_pair(self, number: str, mid: str = "") -> Tuple[Optional[Dict], Optional[Dict]]:
        """取「详情 + 磁力」，能合并就合并成一次子进程调用。

        两者都缺 → 一条 `detail --magnets`；只缺一样 → 只跑那一样；都命中缓存 → 不起进程。
        取回的结果分别落各自的 7 天缓存，下次（含另一入口 `_recognize_media`）直接命中。
        """
        detail_key, magnet_key = f"detail:{number}", f"magnets:{number}"
        detail = self._cache_read(detail_key, TTL_DETAIL)
        magnets = self._cache_read(magnet_key, TTL_DETAIL)
        if detail is None and magnets is None:
            data = self._cached(detail_key, TTL_DETAIL,
                                lambda: self.cli().detail(number, mid=mid, with_magnets=True))
            if isinstance(data, dict):
                raw = data.get("magnets")
                detail = data
                if isinstance(raw, list):
                    magnets = {"number": number, "magnets": raw}
                    # 详情里嵌着磁力，落一份到磁力缓存，省掉下一次单独跑 magnets
                    self._cache_write(magnet_key, magnets, TTL_DETAIL)
        elif detail is None:
            detail = self._cached(detail_key, TTL_DETAIL, lambda: self.cli().detail(number, mid=mid))
        elif magnets is None:
            magnets = self._cached(magnet_key, TTL_DETAIL,
                                   lambda: self.cli().magnets(number, cnsub=False))
        return detail, magnets

    def _movie(self, raw: Dict[str, Any], kind: str = "", actor: str = "") -> Dict[str, Any]:
        """把 javdb 记录归一化成契约里的 movie 结构（图片转代理地址）。

        额外带两个布尔线索（都不带时前端什么都不画）：

        - `lib`：番号此刻在 Emby 库里，值是 `{id,name,path,url}`；
        - `downloaded`：番号在下载台账里且 `state=='downloaded'`（契约 §5.2，只在没有 `lib`
          时画「已下载」）。判它走 `_downloaded_keys()` 的 30 秒内存缓存 —— 本方法每条电影
          都被调一次（榜单一次 60 条），**绝不能在这儿查库**。
        """
        number = str(raw.get("number") or "")
        who = actor or self._actor_of(number)
        uncensored = (
            kind == "uncensored"
            or str(raw.get("type") or "").lower() == "uncensored"
            or number.upper().startswith("FC2")
        )
        movie = {
            "number": number,
            "title": str(raw.get("title") or raw.get("origin_title") or ""),
            "cover": self.image_url(raw.get("cover_url")),
            "thumb": self.image_url(raw.get("thumb_url") or raw.get("cover_url")),
            "date": str(raw.get("release_date") or ""),
            "duration": int(raw.get("duration") or 0),
            "cnsub": bool(raw.get("has_cnsub")),
            "uncensored": bool(uncensored),
            "magnets": int(raw.get("magnets_count") or 0),
            "maker": str(raw.get("maker_name") or ""),
            "score": raw.get("score") or "",
            "actor": who,
            "actor_avatar": self.image_url(raw.get("actor_avatar")),
            "id": str(raw.get("id") or ""),
        }
        lib = self.emby().lookup(number)
        if lib:
            movie["lib"] = lib
        # 「已下载」徽标：走插件内存缓存（30 秒），本方法每条电影都跑一次也不碰库
        if emby.norm_key(number) in self._downloaded_keys():
            movie["downloaded"] = True
        return movie

    # ---------- 下载台账（下载历史）：徽标缓存 / 补种 / API ----------

    def _downloaded_keys(self) -> Set[str]:
        """台账里 `state=='downloaded'` **且是本插件下载的**番号键集合（30 秒内存缓存，契约 §4）。

        `_movie()` **每条电影**都要问一次「这个番号下载过吗」（榜单一次 60 条，演员作品史还有
        分页续拉），直接查库等于把一次请求放大成几十次 SQLite 读。台账只在下载完成时变，
        晚 30 秒打上徽标没有任何影响，所以写入侧不必主动失效。

        只看 `store.PLUGIN_SOURCES`（2026-10-12 用户重新定义「下载历史」后加）：老实现把
        Emby 库补种的 `source='library'` 行也算进来，于是"从没经插件下载、只是本来就在库里"
        的片子会打上「✔已下载」—— 那是「已入库」要说的事，现在由 `lib` 那条路负责。

        读失败**不写缓存**：把「全都没下载过」钉住 30 秒，比慢一次更糟。
        """
        now = time.time()
        stamp, keys = self._download_keys
        if stamp and now - stamp < DOWNLOAD_KEYS_TTL:
            return keys
        found: Set[str] = set()
        try:
            for key, row in (self.store.download_map(PLUGIN_SOURCES) or {}).items():
                if isinstance(row, dict) and str(row.get("state") or "") == "downloaded":
                    found.add(str(key))
        except Exception as error:
            logger.error(f"AVHelper 读取已下载台账失败：{error}")
            return keys
        self._download_keys = (now, found)
        return found

    def seed_downloads(self) -> None:
        """把「已经下载过」的线索补进台账（幂等、best-effort；`/downloads` 与启动预热共用）。

        只补**老下载队列里 `done` 的条目**（交给引擎迁移：落 `state='downloaded'` 后把该条从
        队列删掉，队列从此只留下载中）—— 那批是插件当年真推给下载器的，属于「下载历史」。

        2026-10-12 起**不再从 Emby 库补种**：用户把「下载历史」重新定义为
        「仅保留在当前插件上下载过的视频记录」，而 Emby 补种出来的那批（`source='library'`，
        本机实测 90/109 行）恰恰是"番号本来就在库里、跟插件下载无关"的记录 —— 它们现在由
        「已入库的番号」那一栏**实时**呈现（`/library` 直接读 `emby().index()`），
        在台账里再存一份既重复又是噪音（还会把「已下载」徽标和"重复下载"提示带偏）。
        数据库里已经存在的老 `library` 行**不删**：读法则一律按 `PLUGIN_SOURCES` 过滤
        （见 `_downloaded_keys()` / `_downloads_payload()`），需要时还能从库里翻出来。

        全程只记日志：台账是「锦上添花」，绝不能让 `/downloads` 或 `/bootstrap` 因补种失败而 500。
        """
        try:
            moved = int(self.engine.migrate_queue_to_ledger() or 0)
            if moved:
                logger.info(f"AVHelper 老下载队列迁移台账：{moved} 条")
                # 迁移改变了台账 → 让「已下载番号」那份 30 秒缓存立刻失效：否则打开榜单时，
                # 卡片上的「已下载」标记要等最长 30 秒才出现（缓存是给 `_movie()` 的每片一查做的，
                # 不是给这种一次性写入留的）。
                self._download_keys = (0.0, set())
        except Exception as error:
            logger.error(f"AVHelper 迁移老下载队列失败：{error}")

    def _duplicate_note(self, number: Any) -> str:
        """番号**本插件下载过** → 拼一句附在返回的 `message` 末尾（**只提示不拦**，契约 §3）。

        只看 `PLUGIN_SOURCES`（同 `_downloaded_keys()`）：已经在 Emby 库里的片子不该收到
        「已下载过」这句 —— 用户看到的「✔已入库」与详情页那行「已在 Emby 库中」已经说清楚了，
        而这条提示带着一个**入库日期**，拿它当"下载日期"会误导。

        这里直查 `download_map()` 而不复用 `_downloaded_keys()`：用户点一次下载才走一趟，代价
        可以忽略；而且要拿 `completed_at` 拼日期，那份 30 秒缓存里只有 key 集合、没有时间。
        """
        key = emby.norm_key(number)
        if not key:
            return ""
        try:
            row = (self.store.download_map(PLUGIN_SOURCES) or {}).get(key) or {}
        except Exception as error:
            logger.error(f"AVHelper 查询已下载台账失败：{error}")
            return ""
        if str(row.get("state") or "") != "downloaded":
            return ""
        done = str(row.get("completed_at") or row.get("created_at") or "")[:10]
        return (f"（该番号 {done} 已下载过，本次为重复下载）" if done
                else "（该番号已下载过，本次为重复下载）")

    def _downloads_payload(self) -> Dict[str, Any]:
        """组装 `/downloads` 的 `{success, items, counts}`（GET 与 DELETE 共用，删完立刻回一份）。

        **只回本插件下载过的行**（`store.PLUGIN_SOURCES`）：用户 2026-10-12 把「下载历史」
        定义为「仅保留在当前插件上下载过的视频记录」。Emby 库补种出来的 `library` 行不在其中
        —— 想看"库里现在有什么"请走 `/library`（「已入库的番号」栏），那是实时口径。

        逐条按契约 §4 的字段名给，`thumb`/`sizeText` 都在这儿算好（`image_url()` / `size_text()`）：
        同一个字节数在前端两处显示成不同写法，比缺省更糟。`lib` 是**此刻**的 Emby 命中
        （没配置 Emby、或片子不在库都是 `null` ——「从没入库」与「已被删」契约里统一成一句话）。

        台账读失败回 `success:false` + 空列表而不是抛出去：历史页有自己的错误态，
        但一个 500 会把宿主那次请求打成异常（前端只能靠 catch 猜原因）。
        """
        try:
            rows = self.store.download_list(PLUGIN_SOURCES) or []
        except Exception as error:
            logger.error(f"AVHelper 读取下载台账失败：{error}")
            return {"success": False, "message": "下载台账读取失败",
                    "items": [], "counts": {"total": 0, "inLibrary": 0, "missing": 0}}
        try:
            library = self.emby().index() or {}
        except Exception as error:
            logger.error(f"AVHelper 读取 Emby 索引失败（台账库状态一律算不在库）：{error}")
            library = {}
        items: List[Dict[str, Any]] = []
        # 读侧统一（契约 §3.7 末段）：行**追加** display_number/version_tags[]/states{}+
        # key/original_title/actors[]/cover，原有字段一个不改。批量投影走 film_views()。
        try:
            views = self.film_views([str(r.get("number") or r.get("key") or "")
                                     for r in rows if isinstance(r, dict)])
        except Exception as error:
            logger.error(f"AVHelper 组装 film_view 失败（台账只给原有字段）：{error}")
            views = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "")
            try:
                lib = library.get(key) or {}
                emby_id = str((lib or {}).get("id") or row.get("emby_id") or "")
                number = str(row.get("number") or "")
                item = {
                    "key": key,
                    # 台账里是什么就是什么：Emby 补种拼不出展示番号的键留着空串，
                    # 前端 `displayNumber()` 自会退回 `key`（契约允许空），别在这一层二次发明
                    "number": number,
                    "title": str(row.get("title") or ""),
                    "actor": str(row.get("actor") or ""),
                    "thumb": self.image_url(row.get("thumb")),
                    "size": int(row.get("size") or 0),
                    "sizeText": size_text(row.get("size")),
                    "hash": str(row.get("hash") or ""),
                    "state": str(row.get("state") or "downloading"),
                    "source": str(row.get("source") or "plugin"),
                    "createdAt": str(row.get("created_at") or ""),
                    "completedAt": str(row.get("completed_at") or ""),
                    "path": str(row.get("path") or ""),
                    "lib": library.get(key),
                    # 下载失败的原因（S6：台账 state='failed' 时必须有话可说，别显示成"下载中 0%"）
                    "failed_reason": str(row.get("failed_reason") or ""),
                }
                extra = self._film_extra(views.get(number) or views.get(key),
                                         number=number or key, emby_id=emby_id,
                                         download_state=item["state"])
                if not extra["version_tags"]:
                    # 台账行自己那份是 **JSON 串**（S1 报告 §2.1；media_item 那份才是 dict）
                    extra["version_tags"] = version_labels(json_tags(row.get("version_tags")))
                item.update(extra)
                items.append(item)
            except Exception as error:      # 一条烂数据不该把整页打挂（items 是列表，不是全有才给）
                logger.error(f"AVHelper 组装台账条目失败 {key}：{error}")
        in_library = sum(1 for item in items if item.get("lib"))
        payload = {
            "success": True,
            "items": items,
            "counts": {"total": len(items), "inLibrary": in_library,
                       "missing": len(items) - in_library},
        }
        # 下载器失联要能透出（v4.1 §9.2-3）：只挂 `/downloads`，**别挂 `/bootstrap`** 那条
        # 15 秒轮询 —— `downloader_state()` 每次调用都真问一次下载器（0.1~0.6 秒）。
        # 探测失败也只影响这两个字段，绝不把台账页打成 500。
        try:
            state = self.engine.downloader_state() or {}
            payload["downloader_offline"] = not bool(state.get("online"))
            payload["downloader_error"] = str(state.get("error") or "")
        except Exception as error:
            logger.error(f"AVHelper 探测下载器状态失败（按在线处理）：{error}")
            payload["downloader_offline"] = False
            payload["downloader_error"] = ""
        return payload

    def api_downloads(self, request: Request) -> Dict[str, Any]:
        """下载台账：GET 列表（顺带幂等迁移老队列）/ DELETE 移除一条记录（`?key=<归一化键或番号>`）。

        写成同步函数：宿主会丢线程池跑，迁移要读写库，不能占住事件循环。
        GET 每次都跑一次 `seed_downloads()`（只做老队列迁移，2026-10-12 起不再从 Emby 补种，
        见它的说明）；DELETE 按契约只删记录并回一份**最新**列表（复用同一个组装函数），
        不跑迁移：刚删掉的东西立刻被自己补回来，比不补更让人困惑。

        DELETE 还带**可选**的三出口联动（v4.1 §9.2 第 4 条）：`?cancel_sub=true`（**默认 false**）
        时才交给 `engine.cancel_all(key, cancel_sub=True)` —— 删下载器种子 → 台账打墓碑 →
        删番号/演员订阅 → 写 `known`，四步结果放在返回的 `steps` 里。
        **不带参数就是老行为**：只打台账墓碑（`store.download_delete()`）—— 界面上现有的
        「移除记录」按钮不带这个参数，绝不能因为一次改版就顺手把种子和订阅删掉。
        """
        if request.method == "DELETE":
            key = str(request.query_params.get("key") or "").strip()
            if not key:
                payload = self._downloads_payload()
                payload["success"] = False
                payload["message"] = "缺少 key"
                return payload
            cancel_sub = pick_bool(request.query_params.get("cancel_sub"), False)
            steps: Dict[str, Any] = {}
            if cancel_sub:
                try:
                    result = self.engine.cancel_all(key, cancel_sub=True) or {}
                    steps = result.get("steps") or {}
                    message = self._cancel_message(key, result)
                except Exception as error:
                    logger.error(f"AVHelper「不要了」执行失败（{key}）：{error}")
                    try:
                        removed = bool(self.store.download_delete(key))
                    except Exception as inner:
                        logger.error(f"AVHelper 移除台账记录失败 {key}：{inner}")
                        removed = False
                    message = ("已移除记录（清种子/订阅失败）" if removed
                               else f"取消失败：{error}")
            else:
                try:
                    removed = bool(self.store.download_delete(key))
                except Exception as error:
                    logger.error(f"AVHelper 移除台账记录失败 {key}：{error}")
                    removed = False
                message = "已移除记录" if removed else f"台账里没有 {key} 这条记录"
            payload = self._downloads_payload()
            payload["steps"] = steps
            payload["message"] = message
            return payload
        self.seed_downloads()
        return self._downloads_payload()

    # ---------- 读侧统一投影（film_view，契约 §4 / §3.7 末段） ----------

    def film_cache_forget(self) -> None:
        """丢掉 film_view 与数据源自检的进程内缓存（刮削写完之后调用，界面立刻看到新数据）。"""
        self._film_cache = (0.0, {})
        self._view_cache = {}
        self._sources_cache = (0.0, [])

    def _film_index(self) -> Dict[str, Any]:
        """一次读齐 meta / media_item / 下载台账建索引（进程内 TTL 缓存，见 `FILM_VIEW_TTL`）。

        **性能红线**（契约 §3.7 末段）：`/library` `/downloads` `/tasks` 是 15 秒轮询的热路径，
        绝不允许"每个番号一次 SQL"。所以投影只有两条路：S7 的 `scraper.film_view()`（逐番号，
        但吃 `_view_cache` 的 TTL 缓存），或这里的**三次全表读 + 内存索引**（S1 的
        `meta_list()` / `item_list()` 都支持一次拿全表，正好用上）。
        """
        now = time.time()
        stamp, cached = self._film_cache
        if stamp and now - stamp < FILM_VIEW_TTL and isinstance(cached, dict) and cached:
            return cached
        metas: Dict[str, Dict[str, Any]] = {}
        items: Dict[str, List[Dict[str, Any]]] = {}
        ledger: Dict[str, Dict[str, Any]] = {}
        try:
            for row in (self.store.meta_list() or []):
                if isinstance(row, dict) and str(row.get("key") or ""):
                    metas[str(row["key"])] = row
        except Exception as error:
            logger.error(f"AVHelper 读 meta 表失败（film_view 投影降级为零行）：{error}")
        try:
            for row in (self.store.item_list() or []):
                if isinstance(row, dict) and str(row.get("key") or ""):
                    items.setdefault(str(row["key"]), []).append(row)
        except Exception as error:
            logger.error(f"AVHelper 读 media_item 表失败（film_view 投影降级为零行）：{error}")
        try:
            ledger = dict(self.store.download_map(PLUGIN_SOURCES) or {})
        except Exception as error:
            logger.error(f"AVHelper 读下载台账失败（film_view 的下载态一律算 none）：{error}")
        index = {"meta": metas, "items": items, "ledger": ledger}
        self._film_cache = (now, index)
        return index

    @staticmethod
    def _pick_item(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """同一番号的多个实例里挑「代表实例」（契约 §4）：在库的 emby 实例 → 任意 emby 实例。"""
        if not rows:
            return {}

        def rank(row: Dict[str, Any]) -> Tuple[int, int, str]:
            in_lib = 0 if str(row.get("library_state") or "") == "in_library" else 1
            has_emby = 0 if str(row.get("emby_id") or "") else 1
            return (in_lib, has_emby, str(row.get("item_key") or ""))

        return sorted(rows, key=rank)[0]

    def _film_view_local(self, index: Dict[str, Any], text: str) -> Dict[str, Any]:
        """本地批量投影（契约 §4 的形状）：索引里三张表都没有这个番号时回空字典。

        这是 **S7 的 `scraper.film_view()` 未落地时的降级实现**：字段名与 §4 逐字一致，
        值取 `meta` / `media_item` / `downloads` 三张表里已经有的东西，绝不在这里发网络请求。
        """
        keys = [k for k in (canon_of(text), emby.norm_key(text)) if k]
        keys = list(dict.fromkeys(keys))
        if not keys:
            return {}
        meta: Dict[str, Any] = {}
        for key in keys:
            hit = (index.get("meta") or {}).get(key)
            if isinstance(hit, dict):
                meta = hit
                break
        rows: List[Dict[str, Any]] = []
        for key in keys:
            rows.extend((index.get("items") or {}).get(key) or [])
        ledger: Dict[str, Any] = {}
        for key in keys + [str(text or "").strip().upper()]:
            hit = (index.get("ledger") or {}).get(key)
            if isinstance(hit, dict):
                ledger = hit
                break
        if not meta and not rows and not ledger:
            return {}
        key = keys[0]
        number = str(meta.get("display_number") or "") or shown_of(text) or str(text or "").strip()
        item = self._pick_item(rows)
        emby_id = str(item.get("emby_id") or "")
        raw_tags = item.get("version_tags") if isinstance(item.get("version_tags"), dict) else {}
        if not raw_tags:
            # 实例行还没写版本标签时，从番号写法本身解析（`IPZZ-912-UC.mp4` → 中字/流出）
            parse = getattr(emby, "parse_av_number", None)
            if callable(parse):
                try:
                    raw_tags = json_tags(getattr(parse(text), "version_tags", None))
                except Exception:
                    raw_tags = {}
        labels = version_labels(raw_tags)
        title_zh = str(meta.get("title_zh") or "")
        title_jp = str(meta.get("title_jp") or "")
        library = str(item.get("library_state") or "").strip()
        if library not in LIBRARY_STATES:
            library = "in_library" if emby_id else "not_in_library"
        cover = self.emby_image_url(emby_id) or self.image_url(meta.get("cover_raw_url"))
        states = {
            "download": download_state_name(ledger.get("state")),
            "library": library,
            "scrape": scrape_state_of(meta, item),
        }
        return {
            "key": key,
            "number": number,
            "title": title_zh or title_jp,
            "original_title": title_jp,
            "plot": str(meta.get("plot_zh") or ""),
            "actors": [self._view_actor(a) for a in (meta.get("actors") or [])
                       if isinstance(a, dict)],
            "cover": cover,
            "cover_raw": str(meta.get("cover_raw_url") or ""),
            "crop_anchor": str(item.get("crop_anchor") or "auto"),
            "version_tags": labels,
            "badge": "/".join(labels),
            "states": states,
            "emby_id": emby_id,
            "item_key": str(item.get("item_key") or ""),
            "updated_at": str(meta.get("updated_at") or ""),
        }

    def _view_actor(self, raw: Dict[str, Any]) -> Dict[str, str]:
        """`meta.actors_json` 的一条 → 契约 §4 的 `{'name','jp','avatar'}`（头像走 `/img` 代理）。"""
        zh = str(raw.get("zh") or "")
        jp = str(raw.get("jp") or "")
        name = zh or jp or str(raw.get("name") or "")
        return {"name": name, "jp": jp,
                "avatar": self.image_url(raw.get("avatar") or raw.get("avatar_url"))}

    def film_views(self, numbers: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
        """批量取统一投影：`{调用方传进来的原串: film_view}`（取不到的键不在表里）。

        两条路（契约 §3.7 末段）：

        1. **S7 的 `scraper.film_view()` 已落地** → 用它（唯一权威投影），逐个番号调，
           结果进 `_view_cache`（TTL = `FILM_VIEW_TTL`），所以 15 秒轮询不会每次都重算；
        2. **未落地** → 本模块的本地批量投影（`_film_index()` 一次读全表 + `_film_view_local()`）。
        """
        wanted: List[str] = []
        for item in (numbers or []):
            text = str(item or "").strip()
            if text and text not in wanted:
                wanted.append(text)
        if not wanted:
            return {}
        cache = self._view_cache
        if not isinstance(cache, dict):
            cache = self._view_cache = {}
        now = time.time()
        out: Dict[str, Dict[str, Any]] = {}
        missing: List[str] = []
        for text in wanted:
            stamp, view = cache.get(text) or (0.0, {})
            if stamp and now - stamp < FILM_VIEW_TTL and isinstance(view, dict) and view:
                out[text] = dict(view)
            else:
                missing.append(text)
        if not missing:
            return out
        mod = self.scrape_module()
        if mod is not None and callable(getattr(mod, "film_view", None)):
            # S7 的实现签名是 `film_view(key_or_number, item_key=None, store=None, library=None)`
            # （契约 §3.6 的两参形状拿不到数据，见它自己的 docstring）；`library` 给
            # `EmbyLibrary` 实例：已建好索引时是纯内存查询，没配 Emby 时 `lookup()` 直接回 None。
            library = self.emby()
            for text in missing:
                try:
                    view = mod.film_view(text, None, self.store, library)
                except Exception as error:
                    logger.error(f"AVHelper film_view 失败（{text}）：{error}")
                    continue
                if isinstance(view, dict) and view:
                    cache[text] = (now, dict(view))
                    out[text] = dict(view)
            return out
        index = self._film_index()
        for text in missing:
            try:
                view = self._film_view_local(index, text)
            except Exception as error:
                logger.error(f"AVHelper 本地 film_view 投影失败（{text}）：{error}")
                continue
            if view:
                cache[text] = (now, dict(view))
                out[text] = dict(view)
        return out

    def _film_extra(self, view: Any, number: Any = "", emby_id: str = "",
                    download_state: str = "") -> Dict[str, Any]:
        """`film_view` → 行上要**追加**的那几个字段（契约 §3.7 末段，`/library` 与 `/downloads` 共用）。

        只给点名的键（`key`/`display_number`/`original_title`/`actors`/`cover`/`version_tags`/
        `states`），原有字段一个都不碰；`emby_id` 传进来时封面一律走 Emby 原图
        （`?emby={id}&type=Primary`），否则回落投影里的远程图。
        """
        data = view if isinstance(view, dict) else {}
        states = dict(data.get("states") or {}) if isinstance(data.get("states"), dict) else {}
        for name, allowed, fallback in (("download", DOWNLOAD_STATES, "none"),
                                        ("library", LIBRARY_STATES, "not_in_library"),
                                        ("scrape", SCRAPE_STATES, "unscraped")):
            if str(states.get(name) or "") not in allowed:
                states[name] = fallback
        if download_state:
            states["download"] = download_state_name(download_state)
        if emby_id:
            states["library"] = "in_library"
        return {
            "key": str(data.get("key") or "") or canon_of(number),
            "display_number": str(data.get("number") or "") or shown_of(number),
            "original_title": str(data.get("original_title") or ""),
            "actors": list(data.get("actors") or []),
            "cover": self.emby_image_url(emby_id) or str(data.get("cover") or ""),
            "version_tags": list(data.get("version_tags") or []),
            "states": states,
        }

    def actor_zh(self, name: Any) -> str:
        """演员名的中文写法：`namemap.actor_display()` 优先，缺失退回 `name_map` 表。

        查不到回空串（界面显示原名，**不发明音译**）——`/detail` 的 `actors[].zh` 用它。
        `namemap` 还没落盘时也会退回库里的用户映射（S1 的迁移把 `actor_alias` 写进去了）。
        """
        text = str(name or "").strip()
        if not text:
            return ""
        mod = self.namemap_module()
        if mod is not None and callable(getattr(mod, "actor_display", None)):
            try:
                info = mod.actor_display(text) or {}
                zh = str(info.get("zh") or "").strip()
                if zh:
                    return zh
            except Exception as error:
                logger.warning(f"AVHelper 查演员中文名失败（{text}）：{error}")
        try:
            row = self.store.namemap_find("actor", text) or {}
        except Exception as error:
            logger.warning(f"AVHelper 查 name_map 失败（{text}）：{error}")
            return ""
        return str(row.get("zh_cn") or "").strip()

    # ---------- API：已入库的番号（Emby 库实时列表） ----------

    def _library_items(self) -> List[Dict[str, Any]]:
        """Emby 库里**此刻**的番号 → `movie` 形状的卡片数据（契约 §4 的 `/library`）。

        口径（用户 2026-10-12）：**当前库中已有的番号视频，不包含已删除的数据**。
        所以数据源就是 `emby().index()` —— 它按 Emby 的 `Items` 接口现抓（索引缓存 5 分钟），
        文件被删/移走的条目下一轮就不在其中，天然满足"不含已删除"，**不需要跟台账对照**：
        台账记的是"插件下载过什么"，与"库里现在有什么"本来就是两件事。

        同一部片在索引里有好几个键（MetaTube 的 `ProviderIds`、文件名、标题各一份，本机实测
        按键展开是 148 个 vs 库里 109 条），所以按**条目 id** 归并 + `emby.key_rank()` 挑最干净的
        键 —— 归并与行组装本身是纯函数（`emby.library_rows()`），这里只负责取索引、取封面/演员索引。
        """
        try:
            index = self.emby().index() or {}
        except Exception as error:
            logger.error(f"AVHelper 读取 Emby 索引失败（已入库列表）：{error}")
            return []
        # 封面：本地「番号 → 封面原图」索引 + 7 天详情缓存，**不发网络请求**（`thumbs_of` 的纪律）。
        # 三种写法都试：Name 里的原始番号（`CAWB-040`，最可能与本地索引的 javdb 口径一致）、
        # 从键反推的展示番号、以及归一化键本身（`IPZZ961` 这种无连字符写法）。
        wanted: List[str] = []
        for key in emby.best_keys(index).values():
            entry = index.get(key) or {}
            wanted.append(emby.shown_number(key, entry.get("name")))
            wanted.append(emby.display_number(key))
            wanted.append(key)
        try:
            thumbs = self.thumbs_of(wanted)
        except Exception as error:
            logger.error(f"AVHelper 取已入库封面失败：{error}")
            thumbs = {}
        try:
            known_actors: Dict[str, Any] = self.store.kv_get("num2actor", {}) or {}
        except Exception as error:
            logger.error(f"AVHelper 取演员索引失败：{error}")
            known_actors = {}
        rows = emby.library_rows(index, thumbs, known_actors)
        # 读侧统一（契约 §3.7 末段）：每行**追加** key/original_title/actors[]/cover/version_tags[]/
        # states{}，原有字段一个不改。Emby 库的行天然知道条目 id，所以封面一律走原图。
        numbers = [str(r.get("number") or "") for r in rows if isinstance(r, dict)]
        try:
            views = self.film_views(numbers)
        except Exception as error:
            logger.error(f"AVHelper 组装 film_view 失败（已入库列表只给原有字段）：{error}")
            views = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            lib = row.get("lib") if isinstance(row.get("lib"), dict) else {}
            row.update(self._film_extra(views.get(str(row.get("number") or "")),
                                        number=row.get("number"), emby_id=str(lib.get("id") or "")))
        return rows

    def api_library(self, fresh: int = 0) -> Dict[str, Any]:
        """`/library`：已入库的番号（Emby 库实时列表，删除的不在其中）。

        `fresh=1`（界面上的「↻ 刷新」）= 先丢掉 Emby 索引那份 5 分钟缓存再抓，否则
        "我刚在 Emby 里删了这部片，列表里怎么还有"就解释不清了。默认走缓存：
        索引是**整个库**一次 HTTP（本机 109 条），每次都重抓纯属浪费。
        """
        if fresh:
            try:
                self.emby().invalidate()
            except Exception as error:
                logger.error(f"AVHelper 丢弃 Emby 索引缓存失败：{error}")
        try:
            items = self._library_items()
        except Exception as error:
            logger.error(f"AVHelper 组装已入库列表失败：{error}")
            return {"success": False, "message": "已入库列表读取失败", "items": [], "total": 0}
        if not items:
            # 空列表有两种可能：库里真没片子，或者媒体库根本没连上（`emby().index()` 静默降级成空）。
            # 让前端能区分并给出不同的空态引导（后者要去设置里填 Emby / 检查 MP 的媒体服务器配置）。
            ready = False
            try:
                ready = bool(self.emby().ready())
            except Exception:
                ready = False
            return {"success": True, "items": [], "total": 0, "libraryReady": ready}
        return {"success": True, "items": items, "total": len(items), "libraryReady": True}

    # ---------- API：界面与图片 ----------

    def api_ui(self, request: Request) -> Response:
        """`/ui`（缺尾斜杠）307 跳到 `/ui/`：ES module 的相对导入按文档所在目录解析。

        没有尾斜杠时 `./app.js` 会解析成 `…/app.js`（少一层 `ui/`），所以这里必须补上；
        查询串（如 `?v=`）原样保留，避免把版本参数丢掉。
        """
        target = f"/api/v1/plugin/{PLUGIN_ID}/ui/"
        query = request.url.query
        if query:
            target = f"{target}?{query}"
        return RedirectResponse(target, status_code=307)

    def api_ui_index(self) -> Response:
        """`/ui/` 下发界面入口页（无密钥，可匿名访问）。

        每次请求都从盘上读（前端调试改完刷新即生效，见 AGENTS.md 的硬要求）。
        `ui/index.html` 尚未拆出来时回落到老的 `webui.html`，保证多文件前端就位前也能用。
        """
        page = UI_DIR / "index.html"
        if not page.is_file():
            page = Path(__file__).with_name("webui.html")
        if not page.is_file():
            return HTMLResponse(
                "<meta charset='utf-8'><h2>界面文件缺失</h2>"
                "<p>请重新同步插件目录（ui/index.html 或 webui.html）。</p>", status_code=500,
            )
        try:
            html = page.read_text(encoding="utf-8")
        except Exception as error:
            return HTMLResponse(f"<meta charset='utf-8'>读取界面失败：{error}", status_code=500)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    def api_ui_file(self, path: str = "") -> Response:
        """`/ui/{path}` 下发 `ui/` 目录内的静态文件，按扩展名给 MIME（ES module 必须是对的 JS 类型）。

        每次请求都从盘上读，不做内存缓存；空路径、越界路径、不存在一律 404（不列目录）。
        """
        if not str(path or "").strip("/"):
            return self.api_ui_index()
        target = ui_file(path)
        if target is None:
            return Response(status_code=404)
        try:
            blob = target.read_bytes()
        except Exception as error:
            logger.error(f"AVHelper 读取界面资源失败 {target.name}：{error}")
            return Response(status_code=500)
        return Response(content=blob, media_type=ui_media_type(target),
                        headers={"Cache-Control": "no-cache"})

    def api_img(self, url: str = "", emby: str = "", emby_person: str = "",
                type: str = "Primary") -> Response:
        """图片代理：白名单内 URL → XOR 解包后的图片，否则 404。

        平时只服务 javdb 封面/预览图；长缩略图在浏览器直连失败时才退回这里（WebP 原样透传）。

        3.7 起多两个分支（**服务端回源，仍然匿名**，契约 §3.5 / v4.1 C2）：
        `?emby={item_id}&type=Primary`（影片原图）与 `?emby_person={person_id}`（演员原图）。
        Emby 的 host/apikey 只在服务端用，**绝不进 URL**（URL 里那两个参数只是条目 id）。
        """
        target = str(emby_person or emby or "").strip()
        if target:
            host, apikey = self._emby_conn()
            blob = (imgproxy.emby_image(host, apikey, target, type or "Primary")
                    if host and apikey else None)
        else:
            # 走插件配置里那份代理：这条路是「浏览器直连失败」的兜底，服务端同样可能需要代理
            blob = imgproxy.fetch(url or "", proxy=self._proxy)
        if blob is None:
            return Response(status_code=404)
        return Response(content=blob, media_type=imgproxy.media_type(blob),
                        headers={"Cache-Control": "public, max-age=2592000"})

    # ---------- 运行概况（bootstrap 用） ----------

    def cache_size(self, force: bool = False) -> int:
        """缓存目录当前占用（字节）。

        结果带 `CACHE_SIZE_TTL` 秒的内存缓存：前端每 15 秒轮询一次 `/bootstrap`，
        每次都对上万文件 rglob 会把请求拖慢。清理后要立刻拿到新值就传 `force=True`。

        :param force: 忽略内存缓存，重新统计
        :return: 缓存目录下所有文件的字节数之和（统计失败按已累计的部分返回）
        """
        now = time.time()
        stamp, cached = self._cache_size_cache
        if not force and stamp and now - stamp < CACHE_SIZE_TTL:
            return int(cached)
        total = 0
        try:
            for path in paths.data_root().rglob("*"):
                if not path.is_file():
                    continue
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
        except OSError as error:      # 目录不存在/权限异常都不要把 /bootstrap 打挂
            logger.error(f"AVHelper 统计缓存体积失败：{error}")
        self._cache_size_cache = (now, total)
        return int(total)

    def cache_size_forget(self) -> None:
        """让缓存体积的内存缓存失效（清理后调用，界面立刻拿到新值而不是 60 秒前的）。"""
        self._cache_size_cache = (0.0, 0)

    def check_state(self, rule: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """订阅检查的限流状态（只读展示，判定仍由 `RateLimiter.check_allowed` 负责）。

        界面要显示「现在能不能检查、下次什么时候能检查」，所以把判定结果翻译成一个时间点：
        现在允许 → `nextAt=0`；因每日上限被拒 → 今天 24:00；因间隔不足被拒 → 上次检查 + 最小间隔。

        :param rule: 已取到的全局默认规则；不传就现取一份
        """
        rule = rule if isinstance(rule, dict) else self.global_rule()
        max_per_day = int(rule.get("maxPerDay") or 6)
        min_interval = int(rule.get("minIntervalMin") or 240)
        allowed, reason = self.limiter.check_allowed(max_per_day, min_interval)
        state = self.limiter.state()
        checked_today = int(state.get("checked_today") or 0)
        last_check = float(state.get("last_check") or 0)
        next_at = 0
        if not allowed:
            if checked_today >= max_per_day:
                # 计数键按本地日期分桶（rate_limit 里用 strftime），所以这里也按本地时间取今天 24:00
                next_at = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d")) + 86400
            elif last_check:
                next_at = last_check + min_interval * 60
        return {
            "allowed": bool(allowed),
            "reason": "" if allowed else str(reason),
            "nextAt": int(next_at),
            "checkedToday": checked_today,
            "lastCheck": int(last_check),
            "maxPerDay": max_per_day,
            "minIntervalMin": min_interval,
        }

    # ---------- API：只读数据 ----------

    def api_bootstrap(self, fresh: int = 0) -> Dict[str, Any]:
        """首屏状态聚合：收藏、订阅、任务、队列、通知、站点、默认规则与运行概况。

        `fresh=1`（界面上**手动**点刷新时带）= 下载进度同步问一次下载器；
        不带（15 秒轮询与首屏）走本地快照 + 后台补刷，见 `TaskEngine.queue()`。
        """
        queue = self.engine.queue(fresh=bool(fresh))
        rule = self.global_rule()
        size = self.cache_size()
        return {
            "success": True,
            "enabled": self._enabled,
            "sites": self.engine.site_options(),
            "favs": self.store.fav_list(),
            "aliases": self.store.alias_map(),
            "subs": self.store.sub_list(),
            "known": self.store.known_all(),
            "notices": self.store.notice_list(),
            "tasks": self.engine.task_list(),
            "queue": queue,
            "defaultRule": rule,
            # 运行概况（设置台「运行与缓存」/ 右栏）：体积带 60 秒内存缓存，检查状态是只读快照
            "cacheSize": size,
            "cacheSizeText": size_text(size),
            # 缓存上限（0.6.3 加）：设置台的占比与「已用 / 上限」都读这两个字段；
            # 真正生效的值在 `self._cache_max_gb`（配置里存的是原始输入，这里给的是夹过的）
            "cacheLimit": paths.cache_limit_bytes(self._cache_max_gb),
            "cacheLimitText": f"{self._cache_max_gb:g} GB",
            "check": self.check_state(rule),
        }

    def api_rankings(self, period: str = "week", kind: str = "censored") -> Dict[str, Any]:
        """榜单：period=day/week/month，kind=censored/uncensored/fc2。

        失败时把子进程的真原因（二进制缺失 / 超时 / 退出码与 stderr 摘要）放进 message：
        界面 toast 会原样显示，远程用户截一张图就能定位。
        """
        key = f"rank:{period}:{kind}"
        data = self._cached(key, TTL_RANK, lambda: self.cli().rankings(period=period, kind=kind))
        if data is None:
            message = self.fetch_error(key, "榜单抓取失败（站点超时或代理不可达）")
            logger.warning(f"AVHelper 榜单抓取失败（{period}/{kind}）：{message}")
            return {"success": False, "message": message, "movies": []}
        raw_movies = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
        self.remember_thumbs(raw_movies)
        movies = [self._movie(m, kind) for m in raw_movies]
        return {"success": True, "movies": movies, "period": period, "kind": kind}

    def api_actors(self) -> Dict[str, Any]:
        """演员榜。"""
        data = self._cached("actors", TTL_RANK, lambda: self.cli().actors_rank())
        if data is None:
            message = self.fetch_error("actors", "演员榜抓取失败")
            logger.warning(f"AVHelper 演员榜抓取失败：{message}")
            return {"success": False, "message": message, "actors": []}
        actors = [
            {"name": a.get("name") or "", "zh": a.get("name_zht") or "",
             "avatar": self.image_url(a.get("avatar_url")), "id": a.get("id") or ""}
            for a in (data.get("actors") or [])
        ]
        return {"success": True, "actors": actors}

    def api_actor(self, name: str, page: int = 1, limit: int = ACTOR_PAGE) -> Dict[str, Any]:
        """演员档案 + 作品史（分页：一次只抓一页，前端按需续拉下一页）。

        javdb 的 `actor --all` 最多连抓 50 页（20/页）≈ 35 秒，且上千部的大牌演员只能拿到
        1000 部（实测 4376 部的演员），所以改成显式分页：首屏只付一页的钱，翻页键即缓存键
        （`actor:{name}:p{page}:l{limit}`），某页失败也只冷却那一页。
        """
        if not name:
            return {"success": False, "message": "缺少演员名", "movies": []}
        page = max(1, int(page or 1))
        limit = min(max(int(limit or ACTOR_PAGE), 1), ACTOR_PAGE_MAX)
        data = self._cached(
            f"actor:{name}:p{page}:l{limit}", TTL_ACTOR,
            lambda: self.cli().actor(name, page=page, limit=limit),
        )
        if data is None:
            message = self.fetch_error(f"actor:{name}:p{page}:l{limit}", "演员数据抓取失败")
            logger.warning(f"AVHelper 演员数据抓取失败（{name} p{page}）：{message}")
            return {"success": False, "message": message, "movies": []}
        raw_entity = data.get("entity") or {}
        raw_movies = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
        self.remember_thumbs(raw_movies)
        movies = [self._movie(m, actor=name) for m in raw_movies]
        self.remember_actor([m["number"] for m in movies], name)
        total = int(raw_entity.get("videos_count") or 0)
        entity = {
            "name": raw_entity.get("name") or name,
            "zh": raw_entity.get("name_zht") or raw_entity.get("zh") or "",
            "avatar": self.image_url(raw_entity.get("avatar_url") or raw_entity.get("avatar")),
            "videos_count": total or len(movies),
            "age": raw_entity.get("age") or "",
            "birthday": raw_entity.get("birthday") or "",
            "height": raw_entity.get("height") or "",
            "cup": raw_entity.get("cup") or "",
            "birthplace": raw_entity.get("birthplace") or "",
            "instagram": raw_entity.get("instagram") or "",
        }
        # 满一页就假定还有下一页；站点有总数时再用总数收口（末页正好整除时少一次空请求）
        has_more = len(movies) >= limit and (not total or page * limit < total)
        return {"success": True, "entity": entity, "movies": movies,
                "page": page, "limit": limit, "total": total, "hasMore": has_more}

    def api_search(self, keyword: str) -> Dict[str, Any]:
        """番号/关键词搜索：同时返回影片与演员命中。"""
        if not keyword:
            return {"success": False, "message": "搜索词为空", "movies": [], "actors": []}
        data = self.cli().search(keyword)
        if data is None:
            message = self.fetch_error(f"search:{keyword}", "搜索失败")
            logger.warning(f"AVHelper 搜索失败（{keyword}）：{message}")
            return {"success": False, "message": message, "movies": [], "actors": []}
        raw_movies = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
        self.remember_thumbs(raw_movies)
        movies = [self._movie(m) for m in raw_movies]
        actors = [
            {"name": a.get("name") or "", "zh": a.get("name_zht") or "",
             "avatar": self.image_url(a.get("avatar_url")), "id": a.get("id") or ""}
            for a in (data.get("actors") or [])
        ]
        return {"success": True, "movies": movies[:24], "actors": actors[:24]}

    def api_detail(self, number: str, id: str = "") -> Dict[str, Any]:
        """影片详情：归一化信息 + 演员 + 预览图（代理地址）+ 磁力。

        `id` 是 javdb 内部 id（榜单卡片里就有），带上可省掉一次「番号 → id」搜索往返。
        长图地址只读缓存：未命中就留空，前端把详情画完后再自己调 /longimage 补上
        （projectjav/javfree 那一跳比详情本身还慢，不能挂在首屏关键路径上）。
        """
        if not number:
            return {"success": False, "message": "缺少番号"}
        data, magnets_raw = self._detail_pair(number, str(id or ""))
        if data is None:
            message = self.fetch_error(f"detail:{number}", "详情抓取失败，请稍后重试")
            logger.warning(f"AVHelper 详情抓取失败（{number}）：{message}")
            return {"success": False, "message": message}
        self.remember_thumbs(data)     # 打开过的番号都进封面索引，任务/队列补图就有源了
        actors = [
            {"name": a.get("name") or "", "zh": self.actor_zh(a.get("name")),
             "avatar": self.image_url(a.get("avatar_url")), "id": a.get("id") or ""}
            for a in (data.get("actors") or []) if isinstance(a, dict) and a.get("name")
        ]
        movie = self._movie(data, actor=(actors[0]["name"] if actors else ""))
        if actors:
            movie["actor_avatar"] = actors[0]["avatar"]
            self.remember_actor([movie["number"]], actors[0]["name"])
        previews = [
            self.image_url(p.get("large_url") or p.get("thumb_url"))
            for p in (data.get("preview_images") or []) if isinstance(p, dict)
        ]
        magnets = []
        if isinstance(magnets_raw, dict):
            for item in (magnets_raw.get("magnets") or []):
                if isinstance(item, dict) and item.get("hash"):
                    magnets.append({
                        "hash": item["hash"], "name": item.get("name") or "",
                        # javdb 磁力的 size 单位是 MB，转成人类可读（"7.7 GB"），空值给空串
                        "size": scoring.human_size(float(item.get("size") or 0) * 1024 * 1024)
                                if item.get("size") else "",
                        "cnsub": bool(item.get("cnsub")),
                        "hd": bool(item.get("hd")),
                    })
        payload = {
            "success": True,
            "movie": movie,
            "actors": actors,
            "previews": previews,
            "magnets": magnets,
            "longimage": self.long_cached(number),
        }
        # 读侧统一（契约 §3.7 末段）：已入库时**追加** `emby_id` 与 Emby 原图的 `cover`
        # （`movie.cover` 仍是 javdb 那张，语义不动）；`actors[].zh` 上面已经填上了。
        try:
            lib = self.emby().lookup(number) or {}
        except Exception as error:
            logger.error(f"AVHelper 查详情入库状态失败（按未入库处理）：{error}")
            lib = {}
        if lib:
            payload["emby_id"] = str(lib.get("id") or "")
            payload["cover"] = self.emby_image_url(lib.get("id"))
            # 备注/中文名以库里那份为准（`/detail` 的调用方是详情抽屉，拿它显示演员）
            payload["lib"] = lib
        return payload

    def long_cached(self, number: str) -> str:
        """只读长图 URL 缓存（不抓取）；未命中返回空串。"""
        return str(self.store.kv_get(f"long:{number}") or "")

    def _long_url(self, number: str, force: bool = False) -> str:
        """解析并缓存长图 URL（只解析不下载，图片由前端直连）。

        渠道与油猴脚本 JHS-enhance 一致，见 longshot.py：projectjav 列表卡片一次抓取通常就能
        拿到长图链接（实测卡片自带 data-featherlight），拿不到才进详情页，再不行退 javfree。
        首次约 5 秒、命中后 7 天免费；`force` 供界面上的「重试」绕过缓存重新解析。
        """
        cache_key = f"long:{number}"
        if not force:
            cached = self.store.kv_get(cache_key)
            if cached is not None:
                return str(cached or "")

        def fetcher(url: str, referer: str) -> Optional[str]:
            """带代理抓取 projectjav / javfree 页面。"""
            return RequestUtils().get(url, headers={"User-Agent": longshot.UA, "Referer": referer},
                                      proxies=self.proxy_kwargs)

        url = longshot.resolve_long(number, fetcher) or ""
        # 找到了压 7 天；没找到只压 2 分钟负缓存——否则新片/改版会被判「没有」整整一周，重试也没用
        self.store.kv_set(cache_key, url, ttl=TTL_LONG if url else FAIL_TTL)
        return url

    def api_longimage(self, number: str, force: bool = False) -> Dict[str, Any]:
        """只取长图 URL；`force=1` 绕过缓存重新解析（界面上的「重试」）。"""
        if not number:
            return {"success": False, "message": "缺少番号", "url": ""}
        return {"success": True, "url": self._long_url(number, force)}

    def api_sites(self) -> Dict[str, Any]:
        """返回 MoviePilot 已配置的站点清单。"""
        return {"success": True, "sites": self.engine.site_options()}

    # ---------- API：收藏 / 订阅 / 任务 / 通知 ----------

    async def api_favs(self, request: Request) -> Dict[str, Any]:
        """收藏演员：GET 列表、POST 新增、DELETE 取消。"""
        if request.method == "POST":
            payload = await self._json_body(request)
            name = str(payload.get("name") or "").strip()
            if not name:
                return {"success": False, "message": "缺少演员名"}
            await asyncio.to_thread(
                self.store.fav_add, name, str(payload.get("zh") or ""), str(payload.get("avatar") or "")
            )
            return {"success": True, "favs": self.store.fav_list(), "message": f"已收藏 {name}"}
        if request.method == "DELETE":
            name = str(request.query_params.get("name") or "").strip()
            if not name:
                return {"success": False, "message": "缺少演员名"}
            await asyncio.to_thread(self.store.fav_del, name)
            return {"success": True, "favs": self.store.fav_list(), "message": f"已取消收藏 {name}"}
        return {"success": True, "favs": self.store.fav_list()}

    async def api_aliases(self, request: Request) -> Dict[str, Any]:
        """演员自定义备注：GET 全表、POST 写一位。

        键是**演员原名**（与 `actor_fav.name`、`plugin/actor?name=` 同一个口径）—— 备注只影响显示，
        不改任何按名字匹配的逻辑。名字为空时回 `success=False`（与 `api_favs` 同一句文案）。
        写失败也一律回 `aliases`：前端拿它对齐本地表，不必再补一次 GET。
        """
        if request.method == "POST":
            payload = await self._json_body(request)
            name = str(payload.get("name") or "").strip()
            if not name:
                return {"success": False, "message": "缺少演员名", "aliases": self.store.alias_map()}
            alias = str(payload.get("alias") or "").strip()
            await asyncio.to_thread(self.store.alias_set, name, alias)
            action = f"已保存备注 {alias}" if alias else f"已清除备注 {name}"
            return {"success": True, "aliases": self.store.alias_map(), "message": action}
        return {"success": True, "aliases": self.store.alias_map()}

    async def api_subs(self, request: Request) -> Dict[str, Any]:
        """订阅：GET 列表、POST 新增（含规则）、DELETE 删除。"""
        if request.method == "POST":
            payload = await self._json_body(request)
            sub_type = str(payload.get("type") or "actor")
            name = str(payload.get("name") or "").strip()
            if sub_type not in ("actor", "number") or not name:
                return {"success": False, "message": "订阅参数不完整"}
            rule = merge_rule({**self.global_rule(), **(payload.get("rule") or {})})
            await asyncio.to_thread(self.store.sub_add, sub_type, name, rule)
            if sub_type == "actor":
                await asyncio.to_thread(self.store.fav_add, name, "", "")
            return {"success": True, "subs": self.store.sub_list(),
                    "message": f"已订阅 {name}"}
        if request.method == "DELETE":
            sid = str(request.query_params.get("id") or "")
            if not sid.isdigit():
                return {"success": False, "message": "订阅 id 无效"}
            await asyncio.to_thread(self.store.sub_del, int(sid))
            return {"success": True, "subs": self.store.sub_list(), "message": "已取消订阅"}
        return {"success": True, "subs": self.store.sub_list()}

    def fill_posters(self, *groups: Any) -> bool:
        """给任务 / 下载队列行补 `poster`（契约 §3.7：`/tasks` 行额外带它）。

        已入库的番号用 Emby 原图（`/img?emby={id}`），没入库的沿用行里那个 thumb 代理地址
        —— 与 `fill_thumbs()` 一样全程不发网络请求，只批量读一次投影。

        :return: 是否有条目被改
        """
        items = [x for group in groups for x in (group or []) if isinstance(x, dict)]
        missing = [str(x.get("number") or "") for x in items if x.get("number")]
        if not missing:
            return False
        try:
            views = self.film_views(missing)
        except Exception as error:
            logger.error(f"AVHelper 组装 poster 失败（任务行只给原有字段）：{error}")
            return False
        changed = False
        for item in items:
            view = views.get(str(item.get("number") or "")) or {}
            poster = str(view.get("cover") or "") or str(item.get("thumb") or "")
            if poster and item.get("poster") != poster:
                item["poster"] = poster
                changed = True
        return changed

    def api_tasks(self) -> Dict[str, Any]:
        """任务列表 + 下载队列（队列进度取自下载器真实状态；两者都补上番号封面）。

        界面上这是两个页面，但一次请求同时给两份数据：任务页的「待确认」角标与
        下载页的「下载中」角标用的都是同一份快照，前端一次轮询两边都刷新。
        `poster` 是 v4 读侧统一追加的字段（已入库→Emby 原图，否则 thumb 代理地址）。
        """
        tasks = self.engine.task_list()
        # 用户主动打开任务页/下载页：同步问一次下载器，宁可等这 0.6 秒
        queue = self.engine.queue(fresh=True)
        try:
            self.fill_posters(tasks, queue)
        except Exception as error:      # 补图失败不该让任务页整个挂掉
            logger.error(f"AVHelper 补任务封面失败：{error}")
        return {"success": True, "tasks": tasks, "queue": queue}

    async def api_rule(self, request: Request) -> Dict[str, Any]:
        """全局默认规则：GET 读取、POST 保存（以已存规则为基准合并）。"""
        if request.method == "POST":
            payload = await self._json_body(request)
            rule = merge_rule({**self.global_rule(), **(payload.get("rule") or {})})
            await asyncio.to_thread(self.store.kv_set, GLOBAL_RULE_KEY, rule)
            return {"success": True, "rule": self.global_rule(), "message": "默认规则已保存"}
        return {"success": True, "rule": self.global_rule()}

    async def api_task_search(self, request: Request) -> Dict[str, Any]:
        """按番号/关键词搜索站点并打分（真实站点搜索，受 §8.2 限流约束）。

        `keyword` 与 `number` 等价（单独检索时用 keyword 更贴切）；
        `sites` 可只搜指定站点（界面里做单站/多站检索）。
        """
        payload = await self._json_body(request)
        keyword = str(payload.get("keyword") or payload.get("number") or "").strip()
        if not keyword:
            return {"success": False, "message": "缺少搜索词"}
        actor = str(payload.get("actor") or "")
        rule = merge_rule({**self.global_rule(), **(payload.get("rule") or {})})
        thumb = str(payload.get("thumb") or "")
        sites = payload.get("sites")
        only_sites = [str(x) for x in sites] if isinstance(sites, list) and sites else None
        task = await asyncio.to_thread(self.engine.build_task, keyword, actor, rule, False,
                                       thumb, only_sites)
        return {"success": True, "task": task,
                "message": f"搜到 {len(task.get('cands') or [])} 个候选"}

    async def api_task_acquire(self, request: Request) -> Dict[str, Any]:
        """「下载该影片」：搜种后**按规则当场决定**是直接下载还是落一条待确认任务。

        与 `/tasks/search` 的分工（别把两者合并）：
        - `/tasks/search` 是**检索**（站点搜索页用），只搜不下种，行为一字不改；
        - 本端点是**把这部片拿到手**（详情抽屉那颗按钮），走全局规则的 `trigger`。

        返回里的 `toasts` 是后端定好的提示语（级别 + 文案），前端按序弹即可；
        `pt` / `bt` / `pending` 见 `tasks.rule_verdict()`。
        """
        payload = await self._json_body(request)
        number = str(payload.get("number") or payload.get("keyword") or "").strip()
        if not number:
            return {"success": False, "message": "缺少番号"}
        rule = merge_rule({**self.global_rule(), **(payload.get("rule") or {})})
        result = await asyncio.to_thread(
            self.engine.acquire, number, str(payload.get("actor") or ""), rule,
            str(payload.get("thumb") or ""), str(request.base_url).rstrip("/"),
        )
        message = str(result.get("message") or "")
        if result.get("outcome") == "downloaded":
            message += self._duplicate_note((result.get("task") or {}).get("number"))
        # `**result` 放最前：它自己带一个 `message`（不含"已下载过"提示），
        # 写成 `..., **result` 会被它覆盖掉。
        return {**result, "success": True, "message": message,
                "queue": self.engine.queue(fresh=True)}

    async def api_task_download(self, request: Request) -> Dict[str, Any]:
        """提交下载：优先站点命中项或用户指定站点。

        `force=true` 表示“仍要下载”被规则淘汰的候选（界面里手动挑选时用）。
        """
        payload = await self._json_body(request)
        tid = str(payload.get("id") or "").strip()
        if not tid:
            return {"success": False, "message": "缺少任务 id"}
        result = await asyncio.to_thread(
            self.engine.download, tid, str(payload.get("site") or ""),
            str(request.base_url).rstrip("/"), bool(payload.get("force")),
        )
        # 重复下载提示（契约 §3）：番号只能从引擎返回值里找 —— 请求体里只有任务 id，而
        # `TaskEngine.download()` 目前只回 ok/message/notice/hash/downloader（没有番号），
        # 所以这条路径**现在不会出提示**；tasks.py 的返回值补一个 "number" 即自动生效。
        message = str(result.get("message") or "")
        if result.get("ok"):
            message += self._duplicate_note(result.get("number"))
        return {"success": bool(result.get("ok")), "message": message,
                "notice": result.get("notice"), "hash": result.get("hash"),
                "downloader": result.get("downloader"), "queue": self.engine.queue(fresh=True)}

    async def api_task_cancel(self, request: Request) -> Dict[str, Any]:
        """「不要了」三出口联动 / 老「取消任务」，由一个显式开关分开。

        - `cancel_sub=true`（请求体优先，其次查询串；**默认 false**）**且**带 `number` / `key`
          → 转调 `engine.cancel_all(number_or_key, cancel_sub=True)`：删下载器种子 →
          台账打墓碑 → 删番号/演员订阅 → 写 `known`，四步独立成败，结果在返回的 `steps` 里。
          **默认不联动**：界面上现有的「取消任务」按钮不带这个参数，绝不能因为一次改版就
          顺手把种子和订阅删掉（主统筹 2026-10-14 裁决；等前端做显式「不要了」时再传 true）。
        - 否则 → 老行为一字不改：`engine.cancel_task(tid)` 只把 `state='await'` 的待确认
          任务置成 `canceled`（因此这条路**必须带 `id`**），不碰下载器与订阅、返回形状不变。
        """
        payload = await self._json_body(request)
        cancel_sub = pick_bool(payload.get("cancel_sub")
                               if payload.get("cancel_sub") is not None
                               else request.query_params.get("cancel_sub"), False)
        number = str(payload.get("number") or payload.get("key") or "").strip()
        if cancel_sub and number:
            try:
                result = await asyncio.to_thread(self.engine.cancel_all, number,
                                                 cancel_sub=True)
            except Exception as error:
                logger.error(f"AVHelper「不要了」执行失败（{number}）：{error}")
                return {"success": False, "message": f"取消失败：{error}", "steps": {},
                        "tasks": self.engine.task_list(), "queue": self.engine.queue()}
            return {"success": bool(result.get("ok")), "message": self._cancel_message(number, result),
                    "steps": result.get("steps") or {}, "error": str(result.get("error") or ""),
                    "tasks": self.engine.task_list(), "queue": self.engine.queue()}
        tid = str(payload.get("id") or "").strip()
        if not tid:
            return {"success": False,
                    "message": ("缺少任务 id（三出口联动请带 number/key + cancel_sub=true）"
                                if number else "缺少任务 id 或番号"),
                    "tasks": self.engine.task_list(), "queue": self.engine.queue()}
        result = await asyncio.to_thread(self.engine.cancel_task, tid)
        return {"success": bool(result.get("ok")), "message": result.get("message") or "",
                "tasks": self.engine.task_list(), "queue": self.engine.queue()}

    @staticmethod
    def _cancel_message(number: str, result: Dict[str, Any]) -> str:
        """把 `cancel_all()` 的四步结果拼成一句能贴到界面上的话（失败步骤逐条点名）。"""
        steps = result.get("steps") if isinstance(result.get("steps"), dict) else {}
        failed = [f"{name}：{str((step or {}).get('detail') or '未完成')}"
                  for name, step in steps.items() if not (step or {}).get("ok")]
        if not failed:
            return f"已取消 {number}"
        return f"已取消 {number}（{len(failed)} 步未完成：{'；'.join(failed)}）"

    async def api_magnet_download(self, request: Request) -> Dict[str, Any]:
        """把详情页某条磁力直接推给下载器（界面上的「下载」按钮）。

        以前只有磁力 Hash 可复制，用户得自己粘到下载器里；现在一步到位。
        用的是全局规则里的保存路径 / 分类 / 下载器，推成功会进「下载」队列。
        """
        payload = await self._json_body(request)
        info_hash = str(payload.get("hash") or "").strip()
        if not info_hash:
            return {"success": False, "message": "缺少磁力 Hash"}
        result = await asyncio.to_thread(
            self.engine.download_magnet, str(payload.get("number") or ""), info_hash,
            str(payload.get("name") or ""),
        )
        # 重复下载提示（契约 §3）：番号就在请求体里（详情页的「下载」一定带），
        # 已下载过就追加一句，**不拦** —— 用户可能就是想再下一遍。
        message = str(result.get("message") or "")
        if result.get("ok"):
            message += self._duplicate_note(payload.get("number"))
        return {"success": bool(result.get("ok")), "message": message,
                "hash": result.get("hash"), "downloader": result.get("downloader"),
                "queue": self.engine.queue(fresh=True)}

    async def api_check(self, request: Request) -> Dict[str, Any]:
        """手动检查订阅（受限流；也可由定时任务触发）。"""
        payload = await self._json_body(request)
        name = str(payload.get("name") or "").strip() or None
        result = await asyncio.to_thread(self.engine.check, name)
        return {"success": True, "limited": bool(result.get("limited")),
                "notices": result.get("notices") or [], "message": result.get("message") or "",
                "subs": self.store.sub_list(), "tasks": self.engine.task_list(),
                # 检查可能刚提交了下载：这一次同步问下载器（用户点完正等着看结果）
                "queue": self.engine.queue(fresh=True)}

    async def api_notices(self, request: Request) -> Dict[str, Any]:
        """通知列表 / 清空。"""
        if request.method == "DELETE":
            await asyncio.to_thread(self.store.notice_clear)
            return {"success": True, "notices": [], "message": "已清空通知"}
        return {"success": True, "notices": self.store.notice_list()}

    @staticmethod
    async def _json_body(request: Request) -> Dict[str, Any]:
        """安全读取 JSON 请求体（空体或非法 JSON 都返回空字典）。"""
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    # ---------- API：刮削工作台与映射表（v4 写线，契约 §3.7） ----------

    def scrape_module(self) -> Any:
        """延迟导入 S7 的 `scraper`：缺失/导入失败一律回 None，**绝不让插件在 import 期崩掉**。"""
        try:
            from . import scraper  # noqa: F401  pylint: disable=import-outside-toplevel
            return scraper
        except Exception as error:
            logger.warning(f"AVHelper 刮削模块不可用（延迟导入 scraper 失败）：{error}")
            return None

    def translator_module(self) -> Any:
        """延迟导入 S4 的 `translator`（模型自检用）：同上，回 None 让端点给明确错误。"""
        try:
            from . import translator  # noqa: F401  pylint: disable=import-outside-toplevel
            return translator
        except Exception as error:
            logger.warning(f"AVHelper 翻译模块不可用（延迟导入 translator 失败）：{error}")
            return None

    def namemap_module(self) -> Any:
        """延迟导入 S3 的 `namemap`，并**保证映射表已就绪**（load + 内置映射入库，各只跑一次）。

        为什么必须在这里做（S10 独立验收抓到的功能性缺口）：`namemap.load()` 原先在插件启动
        路径上**从来没被调用过** —— 未 load 时 `ready()=False`、`actor_lookup()/tag_lookup()`
        恒 None、`to_simplified('騎乗位')` 原样返回（繁→简静默失效）、`clean_tags()` 不过滤删除
        规则、`stats()` 全 0，**无异常也无日志**；`name_map` 里只剩 `actor_alias` 搬来的那几行。

        所以导入成功 → `prepare_namemap()`：`load()`（实测 76ms，幂等、有内部缓存）+
        `sync_store(self.store)`（实测 43ms，幂等；库里已有内置记录时不重复灌）。
        **全程 best-effort**：失败只 warning（+ 一条 `scrape_log`），绝不抛 —— 映射缺位时读接口
        退回"只有用户映射"的老样子，总好过 500。
        """
        global _NAMEMAP_TRIED
        try:
            from . import namemap  # noqa: F401  pylint: disable=import-outside-toplevel
        except Exception as error:
            logger.warning(f"AVHelper 映射表模块不可用（延迟导入 namemap 失败）：{error}")
            return None
        if not _NAMEMAP_TRIED:
            with _NAMEMAP_LOCK:
                if not _NAMEMAP_TRIED:
                    _NAMEMAP_TRIED = True      # 先置位：坏资源文件不该每个请求都刷一遍日志
                    self.prepare_namemap(namemap)
        return namemap

    def prepare_namemap(self, mod: Any) -> bool:
        """跑一次 `load()` + `sync_store()`（幂等；失败只 warning + `scrape_log`）。

        :return: `load()` 是否成功（`sync_store()` 的成败不影响返回值，它只是把内置映射
                 灌进库；灌失败时 `/namemap/*` 仍能显示库里已有的用户映射）
        """
        ok = False
        loader = getattr(mod, "load", None)
        if callable(loader):
            try:
                loader()
                ok = True
            except Exception as error:
                logger.warning(f"AVHelper 加载映射表失败（繁简转换/标签清洗会退化成空操作）：{error}")
                self._namemap_note("load", error)
        syncer = getattr(mod, "sync_store", None)
        if callable(syncer):
            try:
                rows = syncer(self.store)
                logger.info(f"AVHelper 内置映射已同步进 name_map：{rows} 行")
            except Exception as error:
                logger.warning(f"AVHelper 同步内置映射失败（/namemap/* 只有用户映射）：{error}")
                self._namemap_note("sync", error)
        return ok

    def _namemap_note(self, status: str, error: Any) -> None:
        """映射表初始化失败往 `scrape_log` 记一条（读接口本身不报错，事后要查得到）。"""
        try:
            self.store.scrape_log_add("namemap", status, "", 0,
                                      f"{type(error).__name__}: {error}"[:200])
        except Exception:
            pass

    def emby_client(self) -> Any:
        """S2 的 `EmbyClient`（写侧）入口：惰性创建，连接信息变了就换实例（照 `emby()` 的写法）。

        **全仓库唯一的 `EmbyClient(...)` 构造点**（S2 报告点名：`scraper.py` 只收注入的实例）。
        没配 Emby（插件与 MP 两处都取不到）、或类还没落地一律回 None —— `/scrape/*` 据此回
        「Emby 未配置」；**绝不把空 host/apikey 传进去**（`ready()` 为假时那些方法全是空操作，
        拿不到真实 DTO 的预览/回滚只会更误导）。
        """
        host, apikey = self._emby_conn()
        cls = getattr(emby, "EmbyClient", None)
        if not host or not apikey or not callable(cls):
            self._emby_client = None
            self._emby_client_sig = None
            return None
        sig = (host, apikey)
        if self._emby_client is None or self._emby_client_sig != sig:
            try:
                self._emby_client = cls(host, apikey)
                self._emby_client_sig = sig
            except Exception as error:
                logger.error(f"AVHelper 创建 EmbyClient 失败：{error}")
                self._emby_client = None
                self._emby_client_sig = None
        return self._emby_client

    def scrape_opts(self) -> Dict[str, Any]:
        """给 `scraper.*` 的 `opts`：设置台那 11 项（`scrape_conf()`）+ `proxy` + **`library`**。

        **`library` 是必需项**（S10 试点批抓到的阻塞级集成缺口）：`scraper.locate_items()` 的定位顺序是
        「显式 `emby:<id>` → `store.item_list(key=…)` → `opts['emby_id']` → **`opts['library']`
        的 Emby 内存索引 `lookup()`**」。全新库里 `meta` / `media_item` 都是 0 行，前三条全空 ——
        少了 `library`，**「按番号（而不是按实例键）刮削」这条主路径永远走不通**：`/scrape/preview`
        回 `items: []` + 「没有找到对应的 Emby 条目」，`/scrape/run` 全条 `找不到该番号对应的 Emby 条目`
        且零写入。而这正是工作台与 P4 全库写入的唯一入口。

        这里给的就是 `self.emby()` 那个 `EmbyLibrary` 实例（惰性 + 按 `(host, apikey)` 换实例）；
        **没配 Emby 时给 `None`** —— `locate_items()` 用的是 `library is not None` 判断，容忍 None，
        不会 KeyError。**别把它塞进 `emby_client`**：一个是只读全库索引（`lookup()`/`index()`），
        一个是写侧客户端（`get_item()`/`update_item()`），两个对象不能互换。

        口径补充（S11 全库实测）：`IPZZ586` 这种一个 key 对应两个**文件**的情形，Emby 把它们当
        同一部影片的备用版本、`/Items` 只回主条目（11452）—— 所以「一个 key → 一个 Emby **可见**条目」
        是正常的，写到主条目就是对的；`media_item` 一行一个 **Emby 可见条目**，不是一行一个文件。
        """
        opts = dict(self.scrape_conf())
        opts["proxy"] = self._proxy
        host, apikey = self._emby_conn()
        opts["library"] = self.emby() if (host and apikey) else None
        return opts

    def scrape_deps(self) -> Dict[str, Any]:
        """刮削编排的依赖注入包（契约 §3.6 的四个关键字：`store`/`cli`/`emby_client`/`opts`）。"""
        return {"store": self.store, "cli": self.cli(),
                "emby_client": self.emby_client(), "opts": self.scrape_opts()}

    @staticmethod
    def api_error(message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """统一错误体：`success:false` + 一句话；契约点名的键由 `extra` 补齐（前端不必猜缺哪个）。"""
        out: Dict[str, Any] = {"success": False, "message": message}
        if extra:
            out.update(extra)
        return out

    @classmethod
    def scrape_not_ready(cls, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """依赖模块没落盘时的统一错误体（`success:false` + 明确文案），处理器照它返回。"""
        return cls.api_error(SCRAPE_NOT_READY, extra)

    @classmethod
    def emby_not_ready(cls, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Emby 连接信息缺失时的统一错误体（`/scrape/preview|run|rollback` 要先过这一关）。"""
        return cls.api_error(EMBY_NOT_READY, extra)

    def _scrape_sources(self, deep: bool = False) -> List[Dict[str, Any]]:
        """数据源健康表。

        **默认廉价**（`/scrape/status` 与 `/scrape/log` 用）：`store.scrape_log_summary()`
        —— 一条 SQL、零网络。这两个端点会被工作台轮询，**绝不能在这里打站点**：
        S7 的 `sources_selfcheck()` 是真探针（javdb 子进程 + javtxt + MetaTube + LLM 自检，
        3~5 秒，还会吃掉站点限流与 javdb 的 1 小时冷却）。

        `deep=True`（只由 `/scrape/selfcheck` 的「数据源自检」按钮触发）才跑那套探针，
        结果吃 30 秒内存缓存；探针失败或模块缺失时退回日志汇总，绝不抛。
        """
        now = time.time()
        stamp, cached = self._sources_cache
        if deep:
            if stamp and now - stamp < FILM_VIEW_TTL and cached:
                return list(cached)
            rows: List[Dict[str, Any]] = []
            mod = self.scrape_module()
            if mod is not None and callable(getattr(mod, "sources_selfcheck", None)):
                try:
                    rows = [dict(r) for r in (mod.sources_selfcheck(self.store, self.cli(),
                                                                    self.scrape_opts()) or [])
                            if isinstance(r, dict)]
                except Exception as error:
                    logger.error(f"AVHelper 数据源自检失败（退回 scrape_log 汇总）：{error}")
                    rows = []
            if rows:
                self._sources_cache = (now, rows)
                return list(rows)
        try:
            raw = [dict(r) for r in (self.store.scrape_log_summary() or []) if isinstance(r, dict)]
        except Exception as error:
            logger.error(f"AVHelper 读 scrape_log 汇总失败：{error}")
            return []
        # 汇总行的列名是 `last_status`/`avg_latency_ms`/`last_error`/`last_created_at`，
        # 而前端（S9 的 `ScrapeView.vue`）按自检行那四个名字容错读：`status`/`latency_ms`/
        # `error`/`checked_at`。这里**补一份**给界面用（原始列名一个不删，诊断还要看它）。
        out: List[Dict[str, Any]] = []
        for row in raw:
            item = dict(row)
            item["source"] = str(row.get("source") or row.get("source_name") or "")
            item["status"] = str(row.get("last_status") or row.get("status") or "")
            item["latency_ms"] = to_int(row.get("avg_latency_ms") or row.get("latency_ms"))
            item["error"] = str(row.get("last_error") or row.get("error") or "")
            item["checked_at"] = str(row.get("last_created_at") or row.get("checked_at") or "")
            out.append(item)
        return out

    def _resolve_item_key(self, value: Any) -> str:
        """番号 / 作品键 / `emby:12598` → `media_item` 的**实例键**（回滚按钮只给一个键）。

        工作台列表给的是作品键（`items[].key`），而 `rollback_item()` 要的是实例键；
        这里按 `_pick_item()` 的同一套规则挑代表实例。解析不出来就原样回传 ——
        让 S7 去报"没有写前备份"，而不是在这里假装成功。
        """
        text = str(value or "").strip()
        if not text:
            return ""
        if ":" in text:
            try:
                if self.store.item_get(text):
                    return text
            except Exception as error:
                logger.error(f"AVHelper 取实例行失败（{text}）：{error}")
        try:
            index = self._film_index()
            rows: List[Dict[str, Any]] = []
            for key in [k for k in (canon_of(text), emby.norm_key(text)) if k]:
                rows.extend((index.get("items") or {}).get(key) or [])
            picked = self._pick_item(rows)
            if picked.get("item_key"):
                return str(picked["item_key"])
        except Exception as error:
            logger.error(f"AVHelper 解析实例键失败（{text}）：{error}")
        return text

    def _scrape_items(self, limit: int = 0, offset: int = 0,
                      filter_text: str = "") -> List[Dict[str, Any]]:
        """`/scrape/status` 的 `items[]`：`meta` 行 + 代表实例（`media_item`）合并。

        字段名与主统筹跟前端定死的那份**逐字一致**：`key` / `number` / `title` / `emby_id` /
        `completeness` / `scrape_state` / `has_backup` / `crop_anchor` / `version_tags[]` /
        `updated_at`。

        - `has_backup` 取 S1 的**布尔位**（`item_list()` 给的，不是 `emby_backup_json` 本体）
          —— 回滚按钮的判据就是它，`False` 才禁用；
        - `version_tags` 用 **media_item 行的 dict**（S1 提过：`downloads` 行那个同名键是 JSON 串，
          两份别混用）；
        - 只有实例、没有作品行（`media_item` 里有、`meta` 里没有）的 key 也算一条，
          `completeness` 按 `missing_core` 计（作品级元数据确实什么都没有）。
        """
        index = self._film_index()
        metas: Dict[str, Any] = index.get("meta") or {}
        items: Dict[str, Any] = index.get("items") or {}
        rows: List[Dict[str, Any]] = []
        for key in list(metas.keys()) + [k for k in items.keys() if k not in metas]:
            meta = metas.get(key) if isinstance(metas.get(key), dict) else {}
            item = self._pick_item(items.get(key) or [])
            completeness = str(meta.get("completeness") or "") or "missing_core"
            rows.append({
                "key": key,
                "number": (str(meta.get("display_number") or "")
                           or str(item.get("display_number") or "") or key),
                "title": str(meta.get("title_zh") or "") or str(meta.get("title_jp") or ""),
                "emby_id": str(item.get("emby_id") or ""),
                "completeness": completeness,
                "scrape_state": scrape_state_of(meta, item),
                "has_backup": bool(item.get("has_backup")),
                "crop_anchor": str(item.get("crop_anchor") or "auto"),
                "version_tags": version_labels(item.get("version_tags")),
                "updated_at": str(meta.get("updated_at") or ""),
            })
        rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
        wanted = str(filter_text or "").strip()
        if wanted:
            rows = [row for row in rows if str(row.get("completeness") or "") == wanted]
        skip = max(to_int(offset), 0)
        size = max(to_int(limit), 0)
        if skip:
            rows = rows[skip:]
        return rows[:size] if size else rows

    def api_scrape_status(self, limit: int = 0, offset: int = 0,
                          filter: str = "") -> Dict[str, Any]:
        """`/scrape/status`：工作台首屏（契约 §3.7 + 主统筹 2026-10-14 补充的 `items[]`）。

        `?limit=&offset=&filter=` 三个参数（`filter` 就是 completeness 档位：前端点状态卡片筛选）。

        `stats.unscraped` 的口径是**本模块定的**（契约没写怎么算）：「作品表里 completeness
        落在三档之外的行」＋「Emby 库里已经入库、但 `meta` 表里还没有的番号」，于是
        `full + missing_plot + missing_core + unscraped == total`，四张状态卡能对上账。
        拿不到 Emby 索引时只算前半部分，不影响出数。
        """
        try:
            raw = self.store.meta_stats() or {}
        except Exception as error:
            logger.error(f"AVHelper 读刮削统计失败：{error}")
            raw = {}
        full = int(raw.get("full") or 0)
        missing_plot = int(raw.get("missing_plot") or 0)
        missing_core = int(raw.get("missing_core") or 0)
        meta_total = int(raw.get("total") or 0)
        others = max(meta_total - full - missing_plot - missing_core, 0)
        unscraped = others
        try:
            index = self.emby().index() or {}
            meta_keys = {str(k) for k in (self._film_index().get("meta") or {})}
            lib_keys = {canon_of(key) for key in index.keys()}
            unscraped += len({k for k in lib_keys if k and k not in meta_keys})
        except Exception as error:
            logger.error(f"AVHelper 统计未刮条目失败（只按 meta 表算）：{error}")
        stats = {"full": full, "missing_plot": missing_plot, "missing_core": missing_core,
                 "unscraped": unscraped,
                 "total": full + missing_plot + missing_core + unscraped}
        try:
            queue = {"tier1": len(self.store.meta_due(tier=1, limit=SCRAPE_QUEUE_PROBE)),
                     "tier2": len(self.store.meta_due(tier=2, limit=SCRAPE_QUEUE_PROBE))}
        except Exception as error:
            logger.error(f"AVHelper 读重刮队列失败：{error}")
            queue = {"tier1": 0, "tier2": 0}
        last_run = ""
        try:
            recent = self.store.scrape_log_recent(limit=1) or []
            if recent and isinstance(recent[0], dict):
                last_run = str(recent[0].get("created_at") or "")
        except Exception as error:
            logger.error(f"AVHelper 读最近一次刮削时间失败：{error}")
        try:
            items = self._scrape_items(limit=limit, offset=offset, filter_text=filter)
        except Exception as error:
            logger.error(f"AVHelper 组装刮削列表失败：{error}")
            items = []
        return {"success": True, "stats": stats, "sources": self._scrape_sources(),
                "queue": queue, "last_run": last_run, "items": items,
                "scraper": bool(self.scrape_module() is not None)}

    def api_scrape_preview(self, key: str = "") -> Dict[str, Any]:
        """`/scrape/preview?key=`：单条字段级 diff（`scraper.preview_one()`，**只算不写**）。

        出参照契约：`{key, number, fields:[{name,current,target,changed}],
        sources:{javdb,javtxt,metatube}, warnings:[]}`。
        """
        target = str(key or "").strip()
        if not target:
            return {"success": False, "message": "缺少番号 key"}
        mod = self.scrape_module()
        if mod is None or not callable(getattr(mod, "preview_one", None)):
            return self.scrape_not_ready({"key": target})
        if self.emby_client() is None:
            # 预览要拿 Emby 的**当前值**做 diff，没有连接信息时给不了有意义的对比
            return self.emby_not_ready({"key": target, "number": "", "fields": [],
                                        "sources": {}, "warnings": []})
        try:
            view = mod.preview_one(target, **self.scrape_deps())
        except Exception as error:
            logger.error(f"AVHelper 刮削预览失败（{target}）：{error}")
            return {"success": False, "message": f"预览失败：{error}", "key": target}
        data = dict(view) if isinstance(view, dict) else {}
        data.setdefault("key", target)
        data.setdefault("fields", [])
        data.setdefault("sources", {})
        data.setdefault("warnings", [])
        return {"success": True, **data}

    async def api_scrape_run(self, request: Request) -> Dict[str, Any]:
        """`/scrape/run`：执行刮削（`{keys?[], all?, force?, anchor?}`）。

        **闸门**（任务书 A）：`all=true` 必须同时带 `confirm=true`，否则直接拒绝 ——
        这个端点是真往 Emby 写元数据的，界面上一次误点不该把全库都改一遍。
        另外同一时刻只允许一路（`_scrape_busy` 单飞），返回形状照契约
        `{ok, results:[{key,status,changed:[],error}]}`。
        """
        payload = await self._json_body(request)
        keys_raw = payload.get("keys")
        keys = [str(x).strip() for x in keys_raw if str(x).strip()] if isinstance(keys_raw, list) else []
        all_flag = pick_bool(payload.get("all"), False)
        if all_flag and not pick_bool(payload.get("confirm"), False):
            return {"success": False, "ok": False, "results": [], "message":
                    "全库刮削需要确认：请求体里带 confirm=true 才会执行"}
        if all_flag and not keys:
            try:
                keys = [str(row.get("key") or "") for row in (self.store.meta_list() or [])
                        if isinstance(row, dict) and str(row.get("key") or "")]
            except Exception as error:
                logger.error(f"AVHelper 取全库待刮清单失败：{error}")
                return {"success": False, "ok": False, "results": [],
                        "message": f"读取全库清单失败：{error}"}
        if not keys:
            return {"success": True, "ok": True, "results": [], "message": "没有待刮削的条目"}
        mod = self.scrape_module()
        if mod is None or not callable(getattr(mod, "scrape_batch", None)):
            return self.scrape_not_ready({"ok": False, "results": []})
        if self.emby_client() is None:
            return self.emby_not_ready({"ok": False, "results": []})
        if not self._scrape_busy.acquire(blocking=False):
            return {"success": False, "ok": False, "results": [],
                    "message": "上一次刮削还在进行中，请稍候"}
        try:
            deps = self.scrape_deps()
            opts = dict(deps.get("opts") or {})
            if payload.get("anchor") not in (None, ""):
                opts["anchor"] = str(payload.get("anchor") or "").strip()
            opts["force"] = pick_bool(payload.get("force"), False)
            deps["opts"] = opts
            raw = await asyncio.to_thread(mod.scrape_batch, keys, **deps)
        except Exception as error:
            logger.error(f"AVHelper 执行刮削失败：{error}")
            return {"success": False, "ok": False, "results": [], "message": f"刮削失败：{error}"}
        finally:
            self._scrape_busy.release()
            # 写完了：投影缓存立刻失效，界面刷新就能看到新字段（不靠 30 秒 TTL 收敛）
            self.film_cache_forget()
        results: List[Dict[str, Any]] = []
        for row in (raw or []):
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["key"] = str(item.get("key") or "")
            item["status"] = str(item.get("status") or "")
            item["changed"] = list(item.get("changed") or [])
            item["error"] = str(item.get("error") or "")
            results.append(item)
        failed = sum(1 for row in results if str(row.get("error") or ""))
        return {"success": True, "ok": True, "results": results,
                "message": f"已处理 {len(results)} 条" + (f"，其中 {failed} 条失败" if failed else "")}

    async def api_scrape_rollback(self, request: Request) -> Dict[str, Any]:
        """`/scrape/rollback`：用写前备份的完整 DTO 回灌（`scraper.rollback_item()`）。

        入参 `{item_key}`（`emby:12598` 这种实例键）；`key` 是兼容写法，两者都收 ——
        工作台列表（`/scrape/status.items[]`）给的是**作品键**，所以这里先把番号/作品键
        解析成代表实例键（`_resolve_item_key()`），回滚按钮不必自己拼 `emby:` 前缀。
        判据在 `store.item_backup_save()` 那道 D7 闸门里：没有备份的实例由 S7 拒绝回滚。
        """
        payload = await self._json_body(request)
        raw_key = str(payload.get("item_key") or payload.get("key") or "").strip()
        if not raw_key:
            return {"success": False, "ok": False, "restored": [], "error": "缺少 item_key"}
        mod = self.scrape_module()
        if mod is None or not callable(getattr(mod, "rollback_item", None)):
            return self.scrape_not_ready({"ok": False, "restored": [], "error": SCRAPE_NOT_READY})
        if self.emby_client() is None:
            return self.emby_not_ready({"ok": False, "restored": [], "error": EMBY_NOT_READY})
        item_key = self._resolve_item_key(raw_key)
        try:
            result = await asyncio.to_thread(mod.rollback_item, item_key, store=self.store,
                                             emby_client=self.emby_client())
        except Exception as error:
            logger.error(f"AVHelper 回滚失败（{item_key}）：{error}")
            return {"success": False, "ok": False, "restored": [], "error": str(error)}
        data = dict(result) if isinstance(result, dict) else {}
        restored = list(data.get("restored") or [])
        self.film_cache_forget()
        return {"success": bool(data.get("ok")), "ok": bool(data.get("ok")),
                "restored": restored, "error": str(data.get("error") or "")}

    def api_scrape_log(self, limit: int = 50) -> Dict[str, Any]:
        """`/scrape/log`：最近若干条刮削日志 + 各源汇总（契约 §3.7）。

        `items[]` 的键名照契约（`source`/`status`/`key`/`latency_ms`/`error`/`created_at`）；
        S1 的行里 `source`/`error` 与 `source_name`/`error_summary` 两份都给，这里取前者。
        """
        size = min(max(to_int(limit, 50), 1), 500)
        try:
            rows = self.store.scrape_log_recent(limit=size) or []
        except Exception as error:
            logger.error(f"AVHelper 读刮削日志失败：{error}")
            return {"success": False, "message": "刮削日志读取失败", "items": [], "summary": []}
        items = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            items.append({
                "source": str(row.get("source") or row.get("source_name") or ""),
                "status": str(row.get("status") or ""),
                "key": str(row.get("key") or ""),
                "latency_ms": to_int(row.get("latency_ms")),
                "error": str(row.get("error") or row.get("error_summary") or ""),
                "created_at": str(row.get("created_at") or ""),
            })
        return {"success": True, "items": items, "summary": self._scrape_sources()}

    async def api_scrape_selfcheck(self, request: Request) -> Dict[str, Any]:
        """`/scrape/selfcheck`：翻译模型自检（设置台的「模型自检」按钮）。

        出参照契约 `{ok, model, latency_ms, error}`，转 `translator.selfcheck(model)`；
        `model` 留空就用设置台配的主模型（`translateModel`）。
        """
        payload = await self._json_body(request)
        # `{"sources": true}`：顺带跑一次真探针（S7 的 `sources_selfcheck`，3~5 秒 + 吃限流），
        # 它是「数据源自检」页签那个按钮的入口；不带该键时就是契约 §3.7 的模型自检。
        if pick_bool(payload.get("sources"), False):
            rows = await asyncio.to_thread(self._scrape_sources, True)
            ok = bool(rows) and all(str(row.get("status") or "") in ("ok", "skipped")
                                    for row in rows)
            return {"success": ok, "ok": ok, "model": "", "latency_ms": 0,
                    "error": "" if ok else "有数据源自检未通过", "sources": rows}
        model = str(payload.get("model") or "").strip() or str(self.scrape_conf()["translateModel"])
        mod = self.translator_module()
        if mod is None or not callable(getattr(mod, "selfcheck", None)):
            return self.scrape_not_ready({"ok": False, "model": model, "latency_ms": 0,
                                          "error": SCRAPE_NOT_READY})
        try:
            result = await asyncio.to_thread(mod.selfcheck, model)
        except Exception as error:
            logger.error(f"AVHelper 模型自检失败（{model}）：{error}")
            return {"success": False, "ok": False, "model": model, "latency_ms": 0,
                    "error": str(error)}
        data = dict(result) if isinstance(result, dict) else {}
        return {"success": bool(data.get("ok")), "ok": bool(data.get("ok")),
                "model": str(data.get("model") or model),
                "latency_ms": to_int(data.get("latency_ms")),
                "error": str(data.get("error") or "")}

    def _namemap_rows(self, entity_type: str, q: str, limit: int) -> List[Dict[str, Any]]:
        """查 `name_map`（`?q=` 走 `namemap_list(like=…)` 的模糊匹配，一 SQL 搞定）。

        先过 `namemap_module()` 这道闸门：它保证内置映射已经 `load()` 且**灌进库**
        （`sync_store()`）—— 否则首次访问这里只有 `actor_alias` 搬来的那几行（S10 实测）。
        """
        self.namemap_module()
        size = min(max(to_int(limit, 50), 1), 200)
        try:
            return [row for row in (self.store.namemap_list(entity_type=entity_type, limit=size,
                                                            like=str(q or "")) or [])
                    if isinstance(row, dict)]
        except Exception as error:
            logger.error(f"AVHelper 读 {entity_type} 映射表失败：{error}")
            return []

    def api_namemap_actors(self, q: str = "", limit: int = 50) -> Dict[str, Any]:
        """`/namemap/actors?q=&limit=`：演员三语映射（契约 §3.7）。"""
        items = [{
            "canonical_id": str(row.get("canonical_id") or ""),
            "zh": str(row.get("zh_cn") or ""),
            "jp": str(row.get("jp") or ""),
            "tw": str(row.get("zh_tw") or ""),
            "avatar": self.image_url(row.get("avatar_url")),
            "aliases": list(row.get("keywords") or []),
            "source": str(row.get("source") or ""),
        } for row in self._namemap_rows("actor", q, limit)]
        return {"success": True, "items": items}

    def api_namemap_tags(self, q: str = "", limit: int = 50) -> Dict[str, Any]:
        """`/namemap/tags?q=&limit=`：标签映射（`is_delete_rule=True` = 命中即丢弃，契约 §3.7）。"""
        items = [{
            "canonical_id": str(row.get("canonical_id") or ""),
            "zh": str(row.get("zh_cn") or ""),
            "jp": str(row.get("jp") or ""),
            "is_delete_rule": bool(row.get("is_delete_rule")),
        } for row in self._namemap_rows("tag", q, limit)]
        return {"success": True, "items": items}

    async def api_namemap_set(self, request: Request) -> Dict[str, Any]:
        """`/namemap/set`：写入用户映射（`{name, zh, jp?, entity_type?}` → `{ok, canonical_id}`）。

        `name` 是**原名**（日文名/标签原文），`zh` 是用户要显示的中文名；落库走 S1 的
        `namemap_user_set()`（`source='user_custom'`，最高优先级，内置重导顶不掉）。
        """
        payload = await self._json_body(request)
        name = str(payload.get("name") or "").strip()
        zh = str(payload.get("zh") or "").strip()
        jp = str(payload.get("jp") or "").strip()
        entity = str(payload.get("entity_type") or "actor").strip() or "actor"
        if not name:
            return {"success": False, "ok": False, "canonical_id": "", "message": "缺少原名 name"}
        if not zh:
            return {"success": False, "ok": False, "canonical_id": "", "message": "缺少中文名 zh"}
        try:
            cid = await asyncio.to_thread(self.store.namemap_user_set, entity, zh, jp or name)
        except Exception as error:
            logger.error(f"AVHelper 写映射失败（{name} → {zh}）：{error}")
            return {"success": False, "ok": False, "canonical_id": "", "message": str(error)}
        return {"success": True, "ok": True, "canonical_id": str(cid or ""),
                "message": f"已保存 {name} → {zh}"}

    # ---------- API：缓存维护 ----------

    def api_cache_clean(self) -> Dict[str, Any]:
        """手动清理缓存：过期项 → 孤儿文件 → 容量上限淘汰，与定时任务共用同一套逻辑。

        同步磁盘 IO（缓存里可能上万文件）由宿主线程池执行；返回本次释放量、清理后的占用，
        并顺手让体积内存缓存失效，免得界面最长 60 秒还显示旧值。
        """
        freed = self.job_cacheclean()
        size = self.cache_size(force=True)
        return {
            "success": True,
            "message": f"已清理，释放 {size_text(freed)}",
            "freed": int(freed),
            "freedText": size_text(freed),
            "cacheSize": int(size),
            "cacheSizeText": size_text(size),
        }

    # ---------- 定时任务 ----------

    def job_subcheck(self) -> None:
        """定时订阅检查（受每天次数与最小间隔约束）。"""
        if not self._enabled:
            return
        result = self.engine.check()
        logger.info(f"AVHelper 订阅检查：{result.get('message')}")
        if result.get("limited"):
            logger.info(f"AVHelper 订阅检查被限流：{result.get('message')}")

    def job_cacheclean(self) -> int:
        """缓存清理：过期文件 → 孤儿文件 → 容量上限淘汰（§8.1）。

        定时任务与界面上的「清理缓存」共用本方法；SQLite 库与它的事务副产物（同目录下的
        `avhelper.db*`）永远跳过——它们不在缓存索引里，按孤儿删会连订阅/收藏/任务一起丢。

        :return: 本次释放的字节数（cron 调用方忽略该值）
        """
        removed_bytes = 0
        # 1. 过期项
        expired = self.store.cache_expired()
        keys, freed = [], 0
        for item in expired:
            path = Path(item["path"])
            try:
                if path.exists():
                    freed += path.stat().st_size
                    path.unlink()
                keys.append(item["key"])
            except Exception as error:
                logger.error(f"AVHelper 删除过期缓存失败 {path}：{error}")
        self.store.cache_drop(keys)
        removed_bytes += freed

        # 2. 孤儿文件（在缓存目录里但不在索引里；数据库文件除外）
        #
        # **只扫元数据目录，不扫 images**：图片缓存从不登记索引（`imgproxy.fetch()` 与 `/img`
        # 路由都不调 `cache_put`），所以"不在索引里"对图片而言恒真 —— 把 images 一起扫等于
        # 每晚把整个图片缓存删光（2026-10-10 实测：847 个文件被判孤儿）。图片本该由下面第 3 步
        # 的「容量上限 + 按 mtime 淘汰」来兜底。原实现两处并存，属既有缺陷，本次修正。
        indexed = {item["path"] for item in self.store.cache_all()}
        for folder in (paths.meta_dir(),):
            if not folder.exists():
                continue
            for path in folder.glob("*"):
                if path.is_file() and not is_keep_file(path) and str(path) not in indexed:
                    try:
                        removed_bytes += path.stat().st_size
                        path.unlink()
                    except Exception:
                        pass

        # 3. 容量上限：按 mtime 由旧到新淘汰（同样不碰数据库文件）
        #    上限来自配置 `cache_max_gb`（默认 1G），不再写死 60G —— 见 paths.cache_limit_gb()
        limit = int(self._cache_max_gb * 1024 ** 3)
        files = [p for p in paths.data_root().rglob("*") if p.is_file() and not is_keep_file(p)]
        total = sum(p.stat().st_size for p in files)
        if total > limit:
            for path in sorted(files, key=lambda p: p.stat().st_mtime):
                if total <= limit:
                    break
                try:
                    size = path.stat().st_size
                    path.unlink()
                    total -= size
                    removed_bytes += size
                except Exception:
                    pass

        self.cache_size_forget()      # 体积变了，让 /bootstrap 的 60 秒缓存失效
        if removed_bytes > 5 * 1024 ** 3:
            self.notifier.info("缓存清理", f"本次清理释放 {removed_bytes / 1024 ** 3:.1f} GB")
        logger.info(f"AVHelper 缓存清理完成，释放 {removed_bytes / 1024 ** 2:.1f} MB")
        return int(removed_bytes)

    def trigger_check_now(self) -> None:
        """界面“立即检查”入口：挂一次性任务，避免阻塞请求线程。"""
        try:
            add_plugin_once_job(self.__class__.__name__, ONCE_JOB_ID, self.job_subcheck,
                                name="AV 订阅立即检查")
        except Exception as error:
            logger.error(f"AVHelper 挂起立即检查任务失败：{error}")
