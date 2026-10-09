"""AV 资源助手（重构版 AVHelperNext）：JAV 榜单/演员/详情浏览 + 番号订阅、PT 选种下载、通知与缓存治理。

本副本是 `AVHelper` 的重构实验版，按「与原版并存、互不干扰」设计：插件 ID / 类名 / 配置前缀 /
数据根全部独立（详见模块常量），两边不读写对方的 SQLite 与图片缓存；只共用只读的 javdb
二进制 `/avhelper/bin/javdb`。

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
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, unquote

from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.plugin import _PluginBase
from app.sdk.scheduler import add_plugin_once_job, remove_plugin_once_job

from . import emby, imgproxy, longshot, scoring
from .client import JavdbClient
from .notify import Notifier
from .ratelimit import RateLimiter
from .store import Store
from .tasks import DEFAULT_RULE, TaskEngine, merge_rule

PLUGIN_ID = "AVHelperNext"
# 数据根：与原版 `/avhelper/cache` 完全隔离（同一个挂载卷下的子目录，容器重建不丢数据）
CACHE_ROOT = Path("/avhelper/next/cache")
META_DIR = CACHE_ROOT / "meta"
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
DEFAULT_PROXY = "http://192.0.2.11:7890"
GLOBAL_RULE_KEY = "global_rule"
THUMB_KEY = "num2thumb"      # 番号 → 封面原图的本地索引（任务/下载队列补图用）
# 缓存 TTL（执行方案 §8.1，不得放宽）
TTL_RANK = 6 * 3600        # 榜单 6 小时
TTL_DETAIL = 7 * 86400     # 番号详情 7 天
TTL_ACTOR = 24 * 3600      # 演员作品史 24 小时
TTL_LONG = 7 * 86400       # 长图 URL 7 天
FAIL_TTL = 120             # 抓取失败后的负缓存：这段时间内不再重试（避免每次打开都重付等待）
CACHE_MAX_GB = 60          # 缓存总量上限（超出按最旧淘汰）
ONCE_JOB_ID = "subcheck_now"


def num_key(number: Any) -> str:
    """番号索引键：去空白 + 统一大写（只用于本地索引，不改显示用的原值）。"""
    return str(number or "").strip().upper()


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


class AVHelperNext(_PluginBase):
    """AV 资源助手（重构版）：JAV 番号订阅、榜单浏览、PT 自动选种下载。"""

    plugin_name = "AV 资源助手（重构版）"
    plugin_desc = "JAV 榜单/演员/详情浏览，番号与演员订阅，PT 选种下载与 Telegram 通知"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "0.3.0-next.1"
    plugin_label = "发现"
    plugin_author = "local"
    plugin_config_prefix = "avhelpernext_"
    plugin_order = 100
    auth_level = 1

    _enabled = False
    _proxy = DEFAULT_PROXY
    _client: Optional[JavdbClient] = None
    _store: Optional[Store] = None
    _limiter: Optional[RateLimiter] = None
    _notifier: Optional[Notifier] = None
    _engine: Optional[TaskEngine] = None
    _emby_host = ""
    _emby_apikey = ""
    _emby_lib: Optional[emby.EmbyLibrary] = None
    _emby_sig: Optional[Tuple[str, str]] = None

    # ---------- 生命周期 ----------

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """读取配置并装配存储、限流、通知与任务引擎；允许重复调用。"""
        self.stop_service()
        self._store = Store()
        self._store.init()
        self._limiter = RateLimiter(self._store)
        self._notifier = Notifier(self, self._store)
        self._engine = TaskEngine(self, self._store, self._limiter, self._notifier)

        self._enabled = False
        self._emby_host = ""
        self._emby_apikey = ""
        if config:
            self._enabled = bool(config.get("enabled"))
            self._proxy = str(config.get("proxy") or self._proxy)
            self._emby_host = str(config.get("emby_host") or "").strip()
            self._emby_apikey = str(config.get("emby_apikey") or "").strip()
        self._emby_lib = None
        self._emby_sig = None
        self._client = JavdbClient(proxy=self._proxy)

    def get_state(self) -> bool:
        """获取插件启用状态。"""
        return self._enabled

    def stop_service(self) -> None:
        """释放后台资源：取消挂起的“立即检查”任务，宿主会自动摘除 cron 服务。"""
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
        """重构期不注册任何定时任务（返回空表）。

        重构版与原版并存，两边都挂 cron 会对同一批站点重复抓取、重复下载，所以这里一律不注册。
        合并回原插件时恢复原来的两个服务：
          {"id": "subcheck", "name": "AV 订阅检查", "trigger": "cron",
           "kwargs": {"hour": "9,14,21", "minute": "30"}, "func": self.job_subcheck}
          {"id": "cacheclean", "name": "AV 缓存清理", "trigger": "cron",
           "kwargs": {"hour": 4, "minute": 0}, "func": self.job_cacheclean}
        """
        return []

    def get_media_source(self) -> Optional[List[Dict[str, Any]]]:
        """重构期不注册媒体数据源（返回 None）。

        重构版与原版并存：两边都注册会在宿主「媒体数据源」里出现两条 JAVDB，
        且识别链路会重复抓 javdb（多付一次限流额度）。番号识别仍由原版负责。
        合并回原插件时恢复：
          return [{"name": "JAVDB", "media_source": "javdb", "media_types": ["电影"]}]
        """
        return None

    def get_module(self) -> Optional[Dict[str, Any]]:
        """重构期不胁持媒体识别（返回 None）。

        合并回原插件时恢复：
          return {"async_recognize_media": self._recognize_media}
        """
        return None

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
            info.directors = [detail.get("director_name")] if detail.get("director_name") else []
            info.production_companies = (
                [detail.get("maker_name")] if detail.get("maker_name") else []
            )
            self.remember_actor([str(media_id)], (info.actors or [{}])[0].get("name") or "")
            return info
        except Exception as error:  # 识别失败必须让原生模块继续工作
            logger.error(f"AVHelper 识别 {media_id} 失败：{error}")
            return None

    # ---------- 配置与页面 ----------

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """配置页：启用开关与 javdb 用的代理地址。"""
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
                                          "props": {"model": "proxy", "label": "代理地址",
                                                    "placeholder": "http://host:port"}}]},
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
                    {"component": "VAlert",
                     "props": {"type": "info", "variant": "tonal", "class": "mt-2"},
                     "text": "完整界面在插件详情页内（内嵌应用）：榜单、演员、订阅、任务、通知与站点检索都在里面。"},
                    {"component": "VAlert",
                     "props": {"type": "info", "variant": "tonal", "class": "mt-2"},
                     "text": "Emby 用于给界面里的番号打「已入库」标记（没有的片不显示标记）。"
                             "两栏都留空时自动复用 MoviePilot「设置 → 媒体服务器」里的 Emby。"},
                ],
            }
        ]
        return form, {"enabled": self._enabled, "proxy": self._proxy,
                      "emby_host": self._emby_host, "emby_apikey": self._emby_apikey}

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
            {"path": "/subs", "endpoint": self.api_subs, "methods": ["GET", "POST", "DELETE"],
             "auth": "bear", "summary": "订阅管理"},
            {"path": "/rule", "endpoint": self.api_rule, "methods": ["GET", "POST"],
             "auth": "bear", "summary": "全局默认规则"},
            {"path": "/tasks", "endpoint": self.api_tasks, "methods": ["GET"], "auth": "bear",
             "summary": "任务与下载队列"},
            {"path": "/tasks/search", "endpoint": self.api_task_search, "methods": ["POST"],
             "auth": "bear", "summary": "搜种并打分"},
            {"path": "/tasks/download", "endpoint": self.api_task_download, "methods": ["POST"],
             "auth": "bear", "summary": "提交下载"},
            {"path": "/magnet-download", "endpoint": self.api_magnet_download, "methods": ["POST"],
             "auth": "bear", "summary": "详情页磁力直接下载"},
            {"path": "/check", "endpoint": self.api_check, "methods": ["POST"], "auth": "bear",
             "summary": "手动检查订阅(受限流)"},
            {"path": "/notices", "endpoint": self.api_notices, "methods": ["GET", "DELETE"],
             "auth": "bear", "summary": "通知列表/清空"},
            {"path": "/sites", "endpoint": self.api_sites, "methods": ["GET"], "auth": "bear",
             "summary": "已配置站点"},
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
        """取 javdb 客户端，未初始化时按当前代理兜底。"""
        if self._client is None:
            self._client = JavdbClient(proxy=self._proxy)
        return self._client

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
        return META_DIR / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

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
            self._cache_write(fail_key, {"at": time.strftime("%Y-%m-%d %H:%M:%S")}, FAIL_TTL)
        return data

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

        额外带一个 `lib` 字段：番号已在 Emby 库中时是 `{id,name,path,url}`，否则不带该字段
        （前端只在有 `lib` 时显示「已入库」，没有就什么都不显示）。
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
        return movie

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
            logger.error(f"AVHelperNext 读取界面资源失败 {target.name}：{error}")
            return Response(status_code=500)
        return Response(content=blob, media_type=ui_media_type(target),
                        headers={"Cache-Control": "no-cache"})

    def api_img(self, url: str) -> Response:
        """图片代理：白名单内 URL → XOR 解包后的图片，否则 404。

        平时只服务 javdb 封面/预览图；长缩略图在浏览器直连失败时才退回这里（WebP 原样透传）。
        """
        blob = imgproxy.fetch(url or "")
        if blob is None:
            return Response(status_code=404)
        return Response(content=blob, media_type=imgproxy.media_type(blob),
                        headers={"Cache-Control": "public, max-age=2592000"})

    # ---------- API：只读数据 ----------

    def api_bootstrap(self) -> Dict[str, Any]:
        """首屏状态聚合：收藏、订阅、任务、队列、通知、站点与默认规则。"""
        queue = self.engine.queue()
        return {
            "success": True,
            "enabled": self._enabled,
            "sites": self.engine.site_options(),
            "favs": self.store.fav_list(),
            "subs": self.store.sub_list(),
            "known": self.store.known_all(),
            "notices": self.store.notice_list(),
            "tasks": self.engine.task_list(),
            "queue": queue,
            "defaultRule": self.global_rule(),
        }

    def api_rankings(self, period: str = "week", kind: str = "censored") -> Dict[str, Any]:
        """榜单：period=day/week/month，kind=censored/uncensored/fc2。"""
        data = self._cached(
            f"rank:{period}:{kind}", TTL_RANK,
            lambda: self.cli().rankings(period=period, kind=kind),
        )
        if data is None:
            return {"success": False, "message": "榜单抓取失败（站点超时或代理不可达）", "movies": []}
        raw_movies = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
        self.remember_thumbs(raw_movies)
        movies = [self._movie(m, kind) for m in raw_movies]
        return {"success": True, "movies": movies, "period": period, "kind": kind}

    def api_actors(self) -> Dict[str, Any]:
        """演员榜。"""
        data = self._cached("actors", TTL_RANK, lambda: self.cli().actors_rank())
        if data is None:
            return {"success": False, "message": "演员榜抓取失败", "actors": []}
        actors = [
            {"name": a.get("name") or "", "zh": a.get("name_zht") or "",
             "avatar": self.image_url(a.get("avatar_url")), "id": a.get("id") or ""}
            for a in (data.get("actors") or [])
        ]
        return {"success": True, "actors": actors}

    def api_actor(self, name: str, limit: int = 0) -> Dict[str, Any]:
        """演员档案 + 作品史。"""
        if not name:
            return {"success": False, "message": "缺少演员名", "movies": []}
        data = self._cached(
            f"actor:{name}:{limit}", TTL_ACTOR,
            lambda: self.cli().actor(name, limit=limit),
        )
        if data is None:
            return {"success": False, "message": "演员数据抓取失败", "movies": []}
        raw_entity = data.get("entity") or {}
        raw_movies = [m for m in (data.get("movies") or []) if isinstance(m, dict)]
        self.remember_thumbs(raw_movies)
        movies = [self._movie(m, actor=name) for m in raw_movies]
        self.remember_actor([m["number"] for m in movies], name)
        entity = {
            "name": raw_entity.get("name") or name,
            "zh": raw_entity.get("name_zht") or raw_entity.get("zh") or "",
            "avatar": self.image_url(raw_entity.get("avatar_url") or raw_entity.get("avatar")),
            "videos_count": raw_entity.get("videos_count") or len(movies),
            "age": raw_entity.get("age") or "",
            "birthday": raw_entity.get("birthday") or "",
            "height": raw_entity.get("height") or "",
            "cup": raw_entity.get("cup") or "",
            "birthplace": raw_entity.get("birthplace") or "",
            "instagram": raw_entity.get("instagram") or "",
        }
        return {"success": True, "entity": entity, "movies": movies}

    def api_search(self, keyword: str) -> Dict[str, Any]:
        """番号/关键词搜索：同时返回影片与演员命中。"""
        if not keyword:
            return {"success": False, "message": "搜索词为空", "movies": [], "actors": []}
        data = self.cli().search(keyword)
        if data is None:
            return {"success": False, "message": "搜索失败", "movies": [], "actors": []}
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
            return {"success": False, "message": "详情抓取失败，请稍后重试"}
        self.remember_thumbs(data)     # 打开过的番号都进封面索引，任务/队列补图就有源了
        actors = [
            {"name": a.get("name") or "", "zh": "", "avatar": self.image_url(a.get("avatar_url")),
             "id": a.get("id") or ""}
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
        return {
            "success": True,
            "movie": movie,
            "actors": actors,
            "previews": previews,
            "magnets": magnets,
            "longimage": self.long_cached(number),
        }

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
                                      proxies={"http": self._proxy, "https": self._proxy})

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

    def api_tasks(self) -> Dict[str, Any]:
        """任务列表 + 下载队列（队列进度取自下载器真实状态；两者都补上番号封面）。

        界面上这是两个页面，但一次请求同时给两份数据：任务页的「待确认」角标与
        下载页的「下载中」角标用的都是同一份快照，前端一次轮询两边都刷新。
        """
        return {"success": True, "tasks": self.engine.task_list(), "queue": self.engine.queue()}

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
        return {"success": bool(result.get("ok")), "message": result.get("message") or "",
                "notice": result.get("notice"), "hash": result.get("hash"),
                "downloader": result.get("downloader"), "queue": self.engine.queue()}

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
        return {"success": bool(result.get("ok")), "message": result.get("message") or "",
                "hash": result.get("hash"), "downloader": result.get("downloader"),
                "queue": self.engine.queue()}

    async def api_check(self, request: Request) -> Dict[str, Any]:
        """手动检查订阅（受限流；也可由定时任务触发）。"""
        payload = await self._json_body(request)
        name = str(payload.get("name") or "").strip() or None
        result = await asyncio.to_thread(self.engine.check, name)
        return {"success": True, "limited": bool(result.get("limited")),
                "notices": result.get("notices") or [], "message": result.get("message") or "",
                "subs": self.store.sub_list(), "tasks": self.engine.task_list(),
                "queue": self.engine.queue()}

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

    # ---------- 定时任务 ----------

    def job_subcheck(self) -> None:
        """定时订阅检查（受每天次数与最小间隔约束）。"""
        if not self._enabled:
            return
        result = self.engine.check()
        logger.info(f"AVHelper 订阅检查：{result.get('message')}")
        if result.get("limited"):
            logger.info(f"AVHelper 订阅检查被限流：{result.get('message')}")

    def job_cacheclean(self) -> None:
        """缓存清理：过期文件 → 孤儿文件 → 容量上限淘汰（§8.1）。"""
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

        # 2. 孤儿文件（在缓存目录里但不在索引里）
        indexed = {item["path"] for item in self.store.cache_all()}
        for folder in (META_DIR, CACHE_ROOT / "images"):
            if not folder.exists():
                continue
            for path in folder.glob("*"):
                if path.is_file() and str(path) not in indexed:
                    try:
                        removed_bytes += path.stat().st_size
                        path.unlink()
                    except Exception:
                        pass

        # 3. 容量上限：按 mtime 由旧到新淘汰
        limit = CACHE_MAX_GB * 1024 ** 3
        files = [p for p in CACHE_ROOT.rglob("*") if p.is_file()]
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

        if removed_bytes > 5 * 1024 ** 3:
            self.notifier.info("缓存清理", f"本次清理释放 {removed_bytes / 1024 ** 3:.1f} GB")
        logger.info(f"AVHelper 缓存清理完成，释放 {removed_bytes / 1024 ** 2:.1f} MB")

    def trigger_check_now(self) -> None:
        """界面“立即检查”入口：挂一次性任务，避免阻塞请求线程。"""
        try:
            add_plugin_once_job(self.__class__.__name__, ONCE_JOB_ID, self.job_subcheck,
                                name="AV 订阅立即检查")
        except Exception as error:
            logger.error(f"AVHelper 挂起立即检查任务失败：{error}")
