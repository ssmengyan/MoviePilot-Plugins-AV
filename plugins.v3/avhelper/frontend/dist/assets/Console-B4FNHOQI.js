import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {defineComponent:_defineComponent$y} = await importShared('vue');

const {openBlock:_openBlock$y,createElementBlock:_createElementBlock$x} = await importShared('vue');

const _hoisted_1$w = ["src"];
const {computed: computed$s} = await importShared('vue');

const _sfc_main$y = /* @__PURE__ */ _defineComponent$y({
  __name: "AppFrame",
  props: {
    pluginId: {},
    version: { default: "" },
    sectionKey: { default: "discover" }
  },
  setup(__props) {
    const props = __props;
    const src = computed$s(() => {
      const params = new URLSearchParams();
      if (props.version) params.set("v", props.version);
      if (props.sectionKey) params.set("view", props.sectionKey);
      const query = params.toString();
      return `/api/v1/plugin/${props.pluginId}/ui/${query ? `?${query}` : ""}`;
    });
    return (_ctx, _cache) => {
      return _openBlock$y(), _createElementBlock$x("iframe", {
        key: `${_ctx.pluginId}:${_ctx.sectionKey}`,
        src: src.value,
        class: "avh-app-frame",
        title: "AV 资源助手 · 内嵌应用",
        referrerpolicy: "no-referrer",
        allow: "clipboard-write"
      }, null, 8, _hoisted_1$w);
    };
  }
});

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const AppFrame = /* @__PURE__ */ _export_sfc(_sfc_main$y, [["__scopeId", "data-v-d2cb29e5"]]);

const DEFAULT_MAX_WIDTH = "90rem";

const CONSOLE_EMIT_NAMES = ["save", "layout", "switch", "close", "action"];

function noop() {
}
function unwrap(res) {
  if (res && typeof res === "object" && !Array.isArray(res) && "data" in res && "success" in res) {
    return res.data;
  }
  return res;
}
function apiMessage(res) {
  if (!res || typeof res !== "object") return "";
  for (const key of ["message", "detail", "msg", "error"]) {
    const value = res[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}
function errorText(err) {
  const fromPayload = apiMessage(err?.payload) || apiMessage(err?.response?.data);
  if (fromPayload) return fromPayload;
  const message = err?.message;
  return typeof message === "string" && message.trim() ? message.trim() : String(err ?? "未知错误");
}
function hostToast(toast) {
  return {
    success: typeof toast?.success === "function" ? toast.success.bind(toast) : noop,
    info: typeof toast?.info === "function" ? toast.info.bind(toast) : noop,
    warning: typeof toast?.warning === "function" ? toast.warning.bind(toast) : noop,
    error: typeof toast?.error === "function" ? toast.error.bind(toast) : noop
  };
}
function bindPluginApi(api, pluginId) {
  const id = String(pluginId || "").trim();
  if (!id) return api;
  const head = "plugin/";
  const prefix = `${head}${id}/`;
  function one(path) {
    if (typeof path !== "string") return path;
    if (!path.startsWith(head) || path.startsWith(prefix)) return path;
    return prefix + path.slice(head.length);
  }
  function oneConfig(config) {
    if (!config || typeof config !== "object") return config;
    const url = config.url;
    const next = one(url);
    return next === url ? config : { ...config, url: next };
  }
  const bound = {
    get: (url, config) => api.get(one(url), config),
    post: (url, data, config) => api.post(one(url), data, config)
  };
  if (api.put) {
    bound.put = (url, data, config) => api.put(one(url), data, config);
  }
  if (api.delete) {
    bound.delete = (url, config) => api.delete(one(url), config);
  }
  if (api.request) {
    bound.request = (config) => api.request(oneConfig(config));
  }
  return bound;
}

const POLICY_MIN_INTERVAL_MIN = 240;
const POLICY_MAX_PER_DAY = 6;

const RULE_FALLBACK$1 = {
  res: "1080p",
  mustCnsub: false,
  preferUncensored: true,
  allow4k: true,
  minSeeders: 3,
  sites: [],
  prefSites: ["馒头", "Rousi"],
  btFallback: true,
  trigger: "notify",
  maxPerDay: 6,
  minIntervalMin: POLICY_MIN_INTERVAL_MIN,
  savePath: "",
  category: "avi",
  downloader: ""
};
function str(value, fallback = "") {
  return typeof value === "string" ? value : value === null || value === void 0 ? fallback : String(value);
}
const CACHE_MAX_GB_FALLBACK = 1;
const CACHE_MAX_GB_MIN = 0.1;
const CACHE_MAX_GB_MAX = 4096;
function toCacheGbText(value) {
  if (typeof value === "string" && !value.trim()) return String(CACHE_MAX_GB_FALLBACK);
  const parsed = typeof value === "number" ? value : Number.parseFloat(str(value));
  if (!Number.isFinite(parsed) || parsed <= 0) return String(CACHE_MAX_GB_FALLBACK);
  const clamped = Math.min(Math.max(parsed, CACHE_MAX_GB_MIN), CACHE_MAX_GB_MAX);
  return String(Number(clamped.toFixed(3)));
}
function toCacheGb(value) {
  return Number.parseFloat(toCacheGbText(value));
}
function strList(value) {
  return Array.isArray(value) ? value.map((item) => str(item)).filter(Boolean) : [];
}
function bool(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}
function num(value, fallback, floor = false, min = null) {
  let parsed = typeof value === "number" ? value : Number.parseFloat(str(value));
  if (!Number.isFinite(parsed)) return fallback;
  if (floor) parsed = Math.floor(parsed);
  if (min !== null && parsed < min) return min;
  return parsed;
}
function toRuleState(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  const res = str(src.res, RULE_FALLBACK$1.res);
  return {
    res: res === "2160p" || res === "only4k" || res === "1080p" ? res : RULE_FALLBACK$1.res,
    mustCnsub: bool(src.mustCnsub, RULE_FALLBACK$1.mustCnsub),
    preferUncensored: bool(src.preferUncensored, RULE_FALLBACK$1.preferUncensored),
    allow4k: bool(src.allow4k, RULE_FALLBACK$1.allow4k),
    minSeeders: num(src.minSeeders, RULE_FALLBACK$1.minSeeders, true, 0),
    sites: strList(src.sites),
    prefSites: strList(src.prefSites),
    btFallback: bool(src.btFallback, RULE_FALLBACK$1.btFallback),
    trigger: str(src.trigger) === "auto" ? "auto" : "notify",
    // 限流参数不由界面放宽：每日上限封顶政策值 6（后端 `merge_rule()` 还会再夹一道），
    // 间隔拿不到就把政策固定值原样带回去。
    maxPerDay: Math.min(num(src.maxPerDay, RULE_FALLBACK$1.maxPerDay, true, 1), POLICY_MAX_PER_DAY),
    minIntervalMin: Math.max(
      num(src.minIntervalMin, RULE_FALLBACK$1.minIntervalMin, true, 1),
      POLICY_MIN_INTERVAL_MIN
    ),
    savePath: str(src.savePath, RULE_FALLBACK$1.savePath),
    category: str(src.category, RULE_FALLBACK$1.category),
    downloader: str(src.downloader, RULE_FALLBACK$1.downloader)
  };
}
function toCheckInfo(raw) {
  if (!raw || typeof raw !== "object") return null;
  const src = raw;
  const info = {
    allowed: typeof src.allowed === "boolean" ? src.allowed : void 0,
    reason: str(src.reason) || void 0,
    nextAt: epochSecondsToMs(src.nextAt),
    checkedToday: Number.isFinite(Number(src.checkedToday)) ? Number(src.checkedToday) : void 0,
    lastCheck: epochSecondsToMs(src.lastCheck),
    maxPerDay: Number.isFinite(Number(src.maxPerDay)) ? Number(src.maxPerDay) : void 0,
    minIntervalMin: Number.isFinite(Number(src.minIntervalMin)) ? Number(src.minIntervalMin) : void 0
  };
  const known = Object.values(info).some((value) => value !== void 0);
  return known ? info : null;
}
function epochSecondsToMs(value) {
  if (value === null || value === void 0 || value === "") return void 0;
  const parsed = typeof value === "number" ? value : Number.parseFloat(str(value));
  if (!Number.isFinite(parsed) || parsed < 0) return void 0;
  return parsed > 1e12 ? Math.floor(parsed) : Math.floor(parsed * 1e3);
}
function formatBytes(value) {
  const parsed = typeof value === "number" ? value : Number.parseFloat(str(value));
  if (!Number.isFinite(parsed) || parsed < 0) return "";
  if (parsed < 1024) return `${Math.round(parsed)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = parsed / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 100 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}
function formatMoment(value) {
  let date;
  if (typeof value === "number") {
    date = new Date(value);
  } else {
    const text = str(value).trim();
    if (!text) return "";
    date = /^\d+$/.test(text) ? new Date(Number(text)) : new Date(text.includes("T") ? text : text.replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return text;
  }
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function formatCheckTime(value, kind) {
  if (value === void 0) return "—";
  if (value <= 0) return kind === "next" ? "现在可检查" : "从未检查";
  return formatMoment(value) || "—";
}
function sameValue(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    const left = Array.isArray(a) ? a.map((item) => str(item)) : [];
    const right = Array.isArray(b) ? b.map((item) => str(item)) : [];
    return left.length === right.length && left.every((item, index) => item === right[index]);
  }
  return a === b;
}
function sameRule(a, b) {
  if (!a || !b) return a === b;
  return Object.keys(RULE_FALLBACK$1).every((key) => sameValue(a[key], b[key]));
}
function sameHost(a, b) {
  if (!a || !b) return a === b;
  return a.enabled === b.enabled && a.proxy === b.proxy && a.javdb_bin === b.javdb_bin && a.data_root === b.data_root && a.emby_host === b.emby_host && a.emby_apikey === b.emby_apikey && a.cache_max_gb === b.cache_max_gb;
}
function embyHalfFilled(config) {
  const host = str(config?.emby_host).trim();
  const key = str(config?.emby_apikey).trim();
  if (host && !key || !host && key) {
    return "Emby 地址与 API 密钥要一起填；两栏都留空 = 复用 MoviePilot「设置 → 媒体服务器」。";
  }
  return "";
}

const {computed: computed$r,ref: ref$v} = await importShared('vue');
const POLL_INTERVAL_MS = 15e3;
function len(value) {
  return Array.isArray(value) ? value.length : null;
}
function useRuntimeInfo(api) {
  const data = ref$v(null);
  const error = ref$v("");
  const loading = ref$v(false);
  const updatedAt = ref$v("");
  let timer = null;
  const overview = computed$r(() => {
    const d = data.value;
    const queue = Array.isArray(d?.queue) ? d?.queue : null;
    const tasks = Array.isArray(d?.tasks) ? d?.tasks : null;
    const check = toCheckInfo(d?.check);
    const cacheText = typeof d?.cacheSizeText === "string" ? d.cacheSizeText.trim() : "";
    const cacheBytes = Number.isFinite(Number(d?.cacheSize)) ? Number(d?.cacheSize) : null;
    return {
      enabled: typeof d?.enabled === "boolean" ? d.enabled : null,
      subs: len(d?.subs),
      awaitTasks: tasks ? tasks.filter((item) => item?.state === "await").length : null,
      downloading: queue ? queue.filter((item) => item?.state !== "done").length : null,
      favorites: len(d?.favs),
      notices: len(d?.notices),
      // 两个字段都是后端本轮在补的：取不到就 `—`，不编造。
      cacheSize: cacheText || formatBytes(cacheBytes) || "—",
      nextCheck: formatCheckTime(check?.nextAt, "next"),
      check
    };
  });
  const recovery = computed$r(() => ({
    subs: Array.isArray(data.value?.subs) ? data.value?.subs ?? [] : [],
    tasks: Array.isArray(data.value?.tasks) ? data.value?.tasks ?? [] : [],
    queue: Array.isArray(data.value?.queue) ? data.value?.queue ?? [] : []
  }));
  async function refresh(fresh = false) {
    if (loading.value) return;
    loading.value = true;
    try {
      const res = await api.get(
        "plugin/bootstrap",
        fresh ? { params: { fresh: 1 } } : void 0
      );
      const payload = res && typeof res === "object" && "data" in res && "success" in res ? res.data ?? {} : res ?? {};
      data.value = payload;
      error.value = "";
      const now = /* @__PURE__ */ new Date();
      updatedAt.value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
    } catch (err) {
      error.value = errorText(err);
    } finally {
      loading.value = false;
    }
  }
  function onVisibility() {
    if (!document.hidden) void refresh();
  }
  function start() {
    void refresh();
    if (timer !== null) return;
    timer = setInterval(() => {
      if (document.hidden) return;
      void refresh();
    }, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", onVisibility);
  }
  function stop() {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
    document.removeEventListener("visibilitychange", onVisibility);
  }
  return { data, error, loading, updatedAt, overview, recovery, refresh, start, stop };
}

const SETTINGS_SECTIONS = [
  { key: "general", title: "常规", icon: "mdi-cog-outline" },
  { key: "sites", title: "搜索站点", icon: "mdi-web" },
  { key: "rule", title: "下载规则", icon: "mdi-filter-cog" },
  { key: "scrape", title: "刮削", icon: "mdi-auto-fix" },
  { key: "scrapeRule", title: "刮削规则", icon: "mdi-file-document-edit-outline" },
  // 「演员」（0.9.0 演员线 S5 加）：头像源开关 / gFriends 索引 / 自动同步 / 一键补齐。
  // 紧跟「刮削规则」——演员线是刮削线的一部分，排序上跟着走。
  { key: "actor", title: "演员", icon: "mdi-account-star" },
  { key: "notify", title: "通知", icon: "mdi-bell" },
  { key: "library", title: "媒体库", icon: "mdi-server" },
  { key: "runtime", title: "运行与缓存", icon: "mdi-database-cog" },
  { key: "about", title: "关于", icon: "mdi-information-outline" }
];
const DIRTY_GROUPS = {
  general: "host",
  sites: "rule",
  rule: "rule",
  scrape: "none",
  scrapeRule: "none",
  actor: "none",
  notify: "none",
  library: "host",
  runtime: "host",
  about: "none"
};
const SCRAPE_SECTIONS = ["scrape", "scrapeRule"];
const ACTOR_SECTIONS = ["actor"];
const SCRAPE_DEFAULTS = {
  scrapeMode: "off",
  plotJavtxt: true,
  translateModel: "hy3",
  translateModelFallback: "deepseek-v4.1-flash",
  trailerMode: "off",
  autoScrapeTier1: false,
  autoScrapeTier2: false,
  scrapeOnDownload: true,
  cleanSuffixes: ["-UC", "_4K", "-4K", "-C", "-L", "-VR", "-ISO", "CD1", "CD2", "中字", "流出"],
  nameTemplate: "{number}{badge} {title}",
  sources: ["javdb", "javtxt"],
  fieldPriority: {},
  fieldBlacklist: {},
  defaultRateLimit: "2",
  rateLimits: {}
};
const MODES = ["off", "fill", "hybrid", "own"];
const TRAILERS = ["off", "remote", "local"];
function pick(value, allowed, fallback) {
  const text = typeof value === "string" ? value.trim() : "";
  return allowed.includes(text) ? text : fallback;
}
function boolOf(value, fallback) {
  if (typeof value === "boolean") return value;
  if (value === "true" || value === 1 || value === "1") return true;
  if (value === "false" || value === 0 || value === "0") return false;
  return fallback;
}
function intOf(value, fallback, min, max) {
  const num = typeof value === "number" ? value : Number(String(value ?? "").trim());
  if (!Number.isFinite(num)) return fallback;
  return Math.min(max, Math.max(min, Math.round(num)));
}
function textOf$1(value, fallback) {
  const text = typeof value === "string" ? value.trim() : "";
  return text || fallback;
}
function listOf$1(value, fallback) {
  if (!Array.isArray(value)) return [...fallback];
  const out = value.map((item) => String(item ?? "").trim()).filter(Boolean);
  return out.length ? out : [...fallback];
}
function sourcesOf(value, fallback) {
  const out = Array.isArray(value) ? value.map((item) => String(item ?? "").trim()).filter(Boolean) : [];
  const merged = /* @__PURE__ */ new Set([...out.length ? out : fallback, "javdb"]);
  return [...merged];
}
function fieldMapOf(value) {
  if (!value || typeof value !== "object") return {};
  const out = {};
  for (const [key, raw] of Object.entries(value)) {
    if (!Array.isArray(raw)) continue;
    const list = raw.map((item) => String(item ?? "").trim()).filter(Boolean);
    if (key.trim() && list.length) out[key.trim()] = list;
  }
  return out;
}
function rateMapOf(value) {
  if (!value || typeof value !== "object") return {};
  const out = {};
  for (const [key, raw] of Object.entries(value)) {
    const name = key.trim();
    const text = String(raw ?? "").trim();
    if (name && text) out[name] = text;
  }
  return out;
}
function toScrapeSettings(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  return {
    scrapeMode: pick(src.scrapeMode, MODES, SCRAPE_DEFAULTS.scrapeMode),
    plotJavtxt: boolOf(src.plotJavtxt, SCRAPE_DEFAULTS.plotJavtxt),
    translateModel: textOf$1(src.translateModel, SCRAPE_DEFAULTS.translateModel),
    translateModelFallback: textOf$1(src.translateModelFallback, SCRAPE_DEFAULTS.translateModelFallback),
    trailerMode: pick(src.trailerMode, TRAILERS, SCRAPE_DEFAULTS.trailerMode),
    autoScrapeTier1: boolOf(src.autoScrapeTier1, SCRAPE_DEFAULTS.autoScrapeTier1),
    autoScrapeTier2: boolOf(src.autoScrapeTier2, SCRAPE_DEFAULTS.autoScrapeTier2),
    scrapeOnDownload: boolOf(src.scrapeOnDownload, SCRAPE_DEFAULTS.scrapeOnDownload),
    cleanSuffixes: listOf$1(src.cleanSuffixes, SCRAPE_DEFAULTS.cleanSuffixes),
    nameTemplate: textOf$1(src.nameTemplate, SCRAPE_DEFAULTS.nameTemplate),
    // P1-5 / P1-2：启用源、字段级择优、限流参数
    sources: sourcesOf(src.sources, SCRAPE_DEFAULTS.sources),
    fieldPriority: fieldMapOf(src.fieldPriority),
    fieldBlacklist: fieldMapOf(src.fieldBlacklist),
    defaultRateLimit: textOf$1(src.defaultRateLimit, SCRAPE_DEFAULTS.defaultRateLimit),
    rateLimits: rateMapOf(src.rateLimits)
  };
}
const ACTOR_DEFAULTS = {
  actorEnabled: true,
  actorGfriends: true,
  actorJavdbFallback: true,
  actorAutoSync: true,
  actorBatchSize: 20,
  actorInterval: 2
};
function toActorSettings(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  return {
    actorEnabled: boolOf(src.actorEnabled, ACTOR_DEFAULTS.actorEnabled),
    actorGfriends: boolOf(src.actorGfriends, ACTOR_DEFAULTS.actorGfriends),
    actorJavdbFallback: boolOf(src.actorJavdbFallback, ACTOR_DEFAULTS.actorJavdbFallback),
    actorAutoSync: boolOf(src.actorAutoSync, ACTOR_DEFAULTS.actorAutoSync),
    actorBatchSize: intOf(src.actorBatchSize, ACTOR_DEFAULTS.actorBatchSize, 1, 200),
    actorInterval: intOf(src.actorInterval, ACTOR_DEFAULTS.actorInterval, 1, 60)
  };
}

const {computed: computed$q,reactive: reactive$3,ref: ref$u,shallowRef: shallowRef$1} = await importShared('vue');
function useSettingsDraft(options) {
  const t = hostToast(options.toast);
  const rulePlain = ref$u(null);
  const rule = rulePlain;
  const hostConfig = reactive$3({
    enabled: options.initialConfig?.enabled === true,
    proxy: str(options.initialConfig?.proxy),
    javdb_bin: str(options.initialConfig?.javdb_bin),
    data_root: str(options.initialConfig?.data_root),
    emby_host: str(options.initialConfig?.emby_host),
    emby_apikey: str(options.initialConfig?.emby_apikey),
    cache_max_gb: toCacheGbText(options.initialConfig?.cache_max_gb)
  });
  const sites = ref$u([]);
  const sitesLoaded = ref$u(false);
  const notices = ref$u([]);
  const cacheText = ref$u("");
  const cacheBytes = ref$u(null);
  const checkInfo = ref$u(null);
  const bootstrapEnabled = ref$u(null);
  const hostLoaded = ref$u(
    Boolean(options.initialConfig && Object.keys(options.initialConfig).length > 0)
  );
  const loading = ref$u(false);
  const saving = ref$u(false);
  const noticeLoading = ref$u(false);
  const cacheCleaning = ref$u(false);
  const error = ref$u("");
  const ruleBase = shallowRef$1(null);
  const hostBase = shallowRef$1(null);
  let hostHydrated = false;
  let ruleHydrated = false;
  function hostFromProps() {
    return {
      enabled: options.initialConfig?.enabled === true,
      proxy: str(options.initialConfig?.proxy),
      javdb_bin: str(options.initialConfig?.javdb_bin),
      data_root: str(options.initialConfig?.data_root),
      emby_host: str(options.initialConfig?.emby_host),
      emby_apikey: str(options.initialConfig?.emby_apikey),
      cache_max_gb: toCacheGbText(options.initialConfig?.cache_max_gb)
    };
  }
  function hydrateHostFromProps() {
    if (hostHydrated) return;
    hostHydrated = true;
    hostBase.value = hostFromProps();
    Object.assign(hostConfig, hostBase.value);
  }
  hydrateHostFromProps();
  function hydrateHost(conf) {
    if (!conf || typeof conf !== "object") return;
    if (hostDirty.value) return;
    const next = {
      enabled: conf.enabled === true,
      proxy: str(conf.proxy),
      javdb_bin: str(conf.javdb_bin),
      data_root: str(conf.data_root),
      emby_host: str(conf.emby_host),
      emby_apikey: str(conf.emby_apikey),
      cache_max_gb: toCacheGbText(conf.cache_max_gb)
    };
    hostHydrated = true;
    Object.assign(hostConfig, next);
    hostBase.value = { ...next };
    hostLoaded.value = true;
  }
  function applyBootstrap(data) {
    if (!data || typeof data !== "object") return;
    if (Array.isArray(data.sites)) {
      sites.value = data.sites.map((item) => {
        const site = item || {};
        return {
          id: site.id ?? null,
          name: str(site.name),
          adapter: str(site.adapter) || void 0,
          adapterLabel: str(site.adapterLabel) || void 0
        };
      }).filter((item) => item.name);
      sitesLoaded.value = true;
    }
    if (Array.isArray(data.notices)) notices.value = data.notices;
    const text = str(data.cacheSizeText).trim();
    const bytes = Number.isFinite(Number(data.cacheSize)) ? Number(data.cacheSize) : null;
    cacheBytes.value = bytes;
    cacheText.value = text || formatBytes(bytes);
    checkInfo.value = toCheckInfo(data.check);
    if (typeof data.enabled === "boolean") bootstrapEnabled.value = data.enabled;
    if (!ruleHydrated && !rule.value && data.defaultRule) {
      ruleHydrated = true;
      rule.value = toRuleState(data.defaultRule);
    }
    if (!hostLoaded.value && typeof data.enabled === "boolean") {
      hostBase.value = { ...hostConfig, enabled: data.enabled };
      hostConfig.enabled = data.enabled;
    }
  }
  async function loadRule() {
    const res = await options.api.get("plugin/rule");
    const payload = unwrap(res) ?? {};
    const raw = payload && typeof payload === "object" && "rule" in payload ? payload.rule : payload;
    const loaded = toRuleState(raw);
    rule.value = loaded;
    ruleBase.value = { ...loaded };
  }
  async function loadNotices() {
    noticeLoading.value = true;
    try {
      const res = await options.api.get("plugin/notices");
      const payload = unwrap(res) ?? {};
      const list = Array.isArray(payload) ? payload : payload?.notices;
      notices.value = Array.isArray(list) ? list : [];
    } catch (err) {
      error.value = errorText(err);
      t.warning(`通知读取失败：${error.value}`);
    } finally {
      noticeLoading.value = false;
    }
  }
  async function load() {
    loading.value = true;
    error.value = "";
    try {
      await loadRule();
    } catch (err) {
      error.value = errorText(err);
      if (!rule.value) {
        rule.value = { ...RULE_FALLBACK$1 };
        ruleBase.value = { ...RULE_FALLBACK$1 };
      }
    } finally {
      loading.value = false;
    }
    await loadNotices();
  }
  const ruleDirty = computed$q(() => !sameRule(rule.value, ruleBase.value));
  const hostDirty = computed$q(() => !sameHost(hostConfig, hostBase.value));
  const dirty = computed$q(() => ruleDirty.value || hostDirty.value);
  const saveButtonLabel = computed$q(() => dirty.value ? "保存修改 ● 未保存" : "保存修改");
  const enabledKnown = computed$q(
    () => hostLoaded.value || typeof options.initialConfig?.enabled === "boolean" || bootstrapEnabled.value !== null
  );
  const validation = computed$q(() => embyHalfFilled(hostConfig));
  function sectionDirty(key) {
    const group = DIRTY_GROUPS[key] || "none";
    if (group === "rule") return ruleDirty.value;
    if (group === "host") return hostDirty.value;
    if (group === "both") return dirty.value;
    return false;
  }
  async function save() {
    if (saving.value || !dirty.value) return !dirty.value;
    saving.value = true;
    try {
      if (ruleDirty.value && rule.value) {
        const res = await options.api.post("plugin/rule", { rule: { ...rule.value } });
        const payload = unwrap(res) ?? {};
        if (payload?.success === false) {
          t.error(str(payload?.message) || "默认规则保存失败");
          return false;
        }
        ruleBase.value = { ...rule.value };
      }
      const host = {
        enabled: hostConfig.enabled,
        proxy: str(hostConfig.proxy).trim(),
        javdb_bin: str(hostConfig.javdb_bin).trim(),
        data_root: str(hostConfig.data_root).trim(),
        emby_host: str(hostConfig.emby_host).trim(),
        emby_apikey: str(hostConfig.emby_apikey).trim(),
        // 空/乱码/0 在**保存时**就归一成兜底值（1G）再提交：后端还会夹一道，
        // 但存进去的应当是「真正生效的那个数」——否则整份 GET 回来是个空串，
        // 用户下次打开只看到一个空输入框，根本不知道现在按几 G 淘汰。
        cache_max_gb: toCacheGbText(str(hostConfig.cache_max_gb).trim())
      };
      await options.onSaveHost({ ...host });
      Object.assign(hostConfig, host);
      hostBase.value = { ...host };
      t.success("已保存");
      return true;
    } catch (err) {
      t.error(`保存失败：${errorText(err)}`);
      return false;
    } finally {
      saving.value = false;
    }
  }
  function resetRule() {
    if (ruleBase.value) rule.value = { ...ruleBase.value };
  }
  function reset() {
    resetRule();
    if (hostBase.value) Object.assign(hostConfig, hostBase.value);
  }
  async function clearNotices() {
    try {
      const res = await options.api.delete?.("plugin/notices");
      const payload = unwrap(res) ?? {};
      if (payload?.success === false) {
        t.warning(str(payload?.message) || "清空通知失败");
        return false;
      }
      notices.value = [];
      t.success("通知已清空");
      return true;
    } catch (err) {
      t.error(`清空通知失败：${errorText(err)}`);
      return false;
    }
  }
  async function cleanCache() {
    if (cacheCleaning.value) return false;
    cacheCleaning.value = true;
    try {
      const res = await options.api.post("plugin/cache/clean", {});
      const payload = unwrap(res) ?? {};
      if (payload?.success === false) {
        t.warning(str(payload?.message) || "清理缓存失败");
        return false;
      }
      const freed = str(payload?.freedText).trim();
      const message = str(payload?.message).trim();
      t.success(message || (freed ? `缓存已清理，释放 ${freed}` : "缓存已清理"));
      return true;
    } catch (err) {
      t.error(`清理缓存失败：${errorText(err)}`);
      return false;
    } finally {
      cacheCleaning.value = false;
    }
  }
  return {
    rule,
    hostConfig,
    sites,
    sitesLoaded,
    notices,
    cacheText,
    cacheBytes,
    checkInfo,
    ruleDirty,
    hostDirty,
    dirty,
    enabledKnown,
    hostLoaded,
    saveButtonLabel,
    validation,
    loading,
    saving,
    noticeLoading,
    cacheCleaning,
    error,
    sectionDirty,
    load,
    applyBootstrap,
    hydrateHost,
    save,
    reset,
    resetRule,
    loadNotices,
    clearNotices,
    cleanCache
  };
}

const {inject: inject$1} = await importShared('vue');

function useHostConfirm() {
  const injected = inject$1("moviepilot:confirm", null);
  return async function confirm(options) {
    if (typeof injected === "function") {
      const result = await injected(options);
      return result === true;
    }
    const text = [options?.title, options?.content].filter(Boolean).join("\n\n");
    return typeof window !== "undefined" && typeof window.confirm === "function" ? window.confirm(text || "确认继续？") : false;
  };
}

const {defineComponent:_defineComponent$x} = await importShared('vue');

const {resolveComponent:_resolveComponent$s,createVNode:_createVNode$t,createTextVNode:_createTextVNode$q,withCtx:_withCtx$s,createElementVNode:_createElementVNode$v,openBlock:_openBlock$x,createElementBlock:_createElementBlock$w,createCommentVNode:_createCommentVNode$p,createBlock:_createBlock$r} = await importShared('vue');

const _hoisted_1$v = {
  key: 0,
  class: "text-caption text-medium-emphasis mb-4"
};
const _sfc_main$x = /* @__PURE__ */ _defineComponent$x({
  __name: "GeneralPanel",
  props: {
    config: {},
    enabledKnown: { type: Boolean }
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$s("v-icon");
      const _component_v_card_title = _resolveComponent$s("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$s("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$s("v-card-item");
      const _component_v_switch = _resolveComponent$s("v-switch");
      const _component_v_text_field = _resolveComponent$s("v-text-field");
      const _component_v_card_text = _resolveComponent$s("v-card-text");
      const _component_v_card = _resolveComponent$s("v-card");
      return _openBlock$x(), _createBlock$r(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$s(() => [
          _createVNode$t(_component_v_card_item, null, {
            prepend: _withCtx$s(() => [
              _createVNode$t(_component_v_icon, {
                icon: "mdi-cog-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$s(() => [
              _createVNode$t(_component_v_card_title, null, {
                default: _withCtx$s(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$q("常规")
                ])),
                _: 1
              }),
              _createVNode$t(_component_v_card_subtitle, null, {
                default: _withCtx$s(() => _cache[5] || (_cache[5] = [
                  _createTextVNode$q("插件开关、代理与路径 · 属于宿主插件配置")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$t(_component_v_card_text, null, {
            default: _withCtx$s(() => [
              _createVNode$t(_component_v_switch, {
                "model-value": props.config.enabled,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "启用插件",
                class: "mb-2",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("enabled", value === true))
              }, null, 8, ["model-value"]),
              !props.enabledKnown ? (_openBlock$x(), _createElementBlock$w("p", _hoisted_1$v, _cache[6] || (_cache[6] = [
                _createTextVNode$q(" 拿不到当前开关状态（"),
                _createElementVNode$v("code", null, "/bootstrap", -1),
                _createTextVNode$q(" 未返回 "),
                _createElementVNode$v("code", null, "enabled", -1),
                _createTextVNode$q("），保存前请确认。 ")
              ]))) : _createCommentVNode$p("", true),
              _cache[7] || (_cache[7] = _createElementVNode$v("p", { class: "text-caption text-medium-emphasis mb-4" }, " 关闭后定时订阅检查与「运行一次」都不执行，界面仍可浏览。 ", -1)),
              _createVNode$t(_component_v_text_field, {
                "model-value": props.config.proxy,
                label: "javdb 代理地址",
                placeholder: "http://host:port",
                hint: "javdb 子进程与站点请求走这个代理；站点自己开了代理时按站点配置走。留空 = 直连。",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                class: "mb-4",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("proxy", value ?? ""))
              }, null, 8, ["model-value"]),
              _createVNode$t(_component_v_text_field, {
                "model-value": props.config.javdb_bin,
                label: "javdb 路径",
                placeholder: "留空 = 自动下载 / 自动查找",
                hint: "发现层依赖 javdb-cli 单文件二进制。留空时插件启动后自动下一份到数据目录；网络不通就手工放一份再填这里。",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                class: "mb-4",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("javdb_bin", value ?? ""))
              }, null, 8, ["model-value"]),
              _createVNode$t(_component_v_text_field, {
                "model-value": props.config.data_root,
                label: "数据目录",
                placeholder: "留空 = MP 插件数据目录（/config/plugins/AVHelper）",
                hint: "SQLite 台账、JSON 缓存与图片缓存同根。改这里等于换一套数据，旧数据不会自动搬过去。",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("data_root", value ?? ""))
              }, null, 8, ["model-value"])
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const GeneralPanel = /* @__PURE__ */ _export_sfc(_sfc_main$x, [["__scopeId", "data-v-0c3f0ccd"]]);

const {defineComponent:_defineComponent$w} = await importShared('vue');

const {resolveComponent:_resolveComponent$r,createVNode:_createVNode$s,createTextVNode:_createTextVNode$p,withCtx:_withCtx$r,createElementVNode:_createElementVNode$u,toDisplayString:_toDisplayString$v,openBlock:_openBlock$w,createBlock:_createBlock$q,createCommentVNode:_createCommentVNode$o,renderList:_renderList$l,Fragment:_Fragment$n,createElementBlock:_createElementBlock$v} = await importShared('vue');

const _hoisted_1$u = { class: "avh-row" };
const _hoisted_2$t = { class: "avh-row-main" };
const _hoisted_3$p = { class: "avh-scope text-body-1" };
const _hoisted_4$m = { class: "avh-scope text-body-2" };
const _hoisted_5$k = { class: "avh-row-actions" };
const _hoisted_6$j = { class: "d-flex align-center mb-2" };
const _hoisted_7$i = { class: "text-caption text-medium-emphasis" };
const _hoisted_8$h = { class: "avh-list" };
const _hoisted_9$f = { class: "text-caption text-medium-emphasis" };
const _hoisted_10$f = {
  key: 0,
  class: "text-caption text-medium-emphasis pa-2"
};
const _hoisted_11$d = { class: "text-caption text-medium-emphasis mb-1" };
const _hoisted_12$d = { class: "text-caption text-medium-emphasis avh-idx" };
const _hoisted_13$d = { class: "avh-chips" };
const _hoisted_14$d = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const {computed: computed$p,ref: ref$t} = await importShared('vue');

const _sfc_main$w = /* @__PURE__ */ _defineComponent$w({
  __name: "SitesPanel",
  props: {
    sites: {},
    prefSites: {},
    options: {},
    loaded: { type: Boolean }
  },
  emits: ["update:sites", "update:prefSites"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const scopeText = computed$p(
      () => props.sites.length ? props.sites.join("、") : "全部站点"
    );
    const prefText = computed$p(
      () => props.prefSites.length ? props.prefSites.join(" › ") : "未设置（按站点清单顺序）"
    );
    const pickOpen = ref$t(false);
    const pickQuery = ref$t("");
    const pickDraft = ref$t([]);
    const filteredOptions = computed$p(() => {
      const keyword = pickQuery.value.trim().toLowerCase();
      const list = props.options.filter((item) => item.name);
      if (!keyword) return list;
      return list.filter(
        (item) => `${item.name} ${item.adapter || ""} ${item.adapterLabel || ""}`.toLowerCase().includes(keyword)
      );
    });
    function openPick() {
      pickDraft.value = [...props.sites];
      pickQuery.value = "";
      pickOpen.value = true;
    }
    function pickToggle(name) {
      const index = pickDraft.value.indexOf(name);
      if (index >= 0) pickDraft.value.splice(index, 1);
      else pickDraft.value.push(name);
    }
    function pickAll() {
      const names = filteredOptions.value.map((item) => item.name);
      pickDraft.value = Array.from(/* @__PURE__ */ new Set([...pickDraft.value, ...names]));
    }
    function pickNone() {
      const names = new Set(filteredOptions.value.map((item) => item.name));
      pickDraft.value = pickDraft.value.filter((name) => !names.has(name));
    }
    function pickConfirm() {
      const order = new Map(props.options.map((item, index) => [item.name, index]));
      emit("update:sites", [...pickDraft.value].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0)));
      pickOpen.value = false;
    }
    const prefOpen = ref$t(false);
    const prefDraft = ref$t([]);
    const prefCandidates = computed$p(
      () => props.options.filter((item) => item.name && !prefDraft.value.includes(item.name))
    );
    function openPref() {
      prefDraft.value = [...props.prefSites];
      prefOpen.value = true;
    }
    function prefAdd(name) {
      if (!prefDraft.value.includes(name)) prefDraft.value.push(name);
    }
    function prefRemove(index) {
      prefDraft.value.splice(index, 1);
    }
    function prefMove(index, delta) {
      const target = index + delta;
      if (target < 0 || target >= prefDraft.value.length) return;
      const next = [...prefDraft.value];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      prefDraft.value = next;
    }
    function prefConfirm() {
      emit("update:prefSites", [...prefDraft.value]);
      prefOpen.value = false;
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$r("v-icon");
      const _component_v_card_title = _resolveComponent$r("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$r("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$r("v-card-item");
      const _component_v_btn = _resolveComponent$r("v-btn");
      const _component_v_alert = _resolveComponent$r("v-alert");
      const _component_v_card_text = _resolveComponent$r("v-card-text");
      const _component_v_card = _resolveComponent$r("v-card");
      const _component_v_text_field = _resolveComponent$r("v-text-field");
      const _component_v_spacer = _resolveComponent$r("v-spacer");
      const _component_v_divider = _resolveComponent$r("v-divider");
      const _component_v_checkbox = _resolveComponent$r("v-checkbox");
      const _component_v_card_actions = _resolveComponent$r("v-card-actions");
      const _component_v_dialog = _resolveComponent$r("v-dialog");
      const _component_v_list_item_title = _resolveComponent$r("v-list-item-title");
      const _component_v_list_item = _resolveComponent$r("v-list-item");
      const _component_v_list = _resolveComponent$r("v-list");
      const _component_v_chip = _resolveComponent$r("v-chip");
      return _openBlock$w(), _createElementBlock$v(_Fragment$n, null, [
        _createVNode$s(_component_v_card, {
          variant: "tonal",
          class: "avh-panel"
        }, {
          default: _withCtx$r(() => [
            _createVNode$s(_component_v_card_item, null, {
              prepend: _withCtx$r(() => [
                _createVNode$s(_component_v_icon, {
                  icon: "mdi-web",
                  color: "primary"
                })
              ]),
              default: _withCtx$r(() => [
                _createVNode$s(_component_v_card_title, null, {
                  default: _withCtx$r(() => _cache[5] || (_cache[5] = [
                    _createTextVNode$p("搜索站点")
                  ])),
                  _: 1
                }),
                _createVNode$s(_component_v_card_subtitle, null, {
                  default: _withCtx$r(() => _cache[6] || (_cache[6] = [
                    _createTextVNode$p("勾选与排序都在弹窗里 · 数据走 POST /rule")
                  ])),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$s(_component_v_card_text, null, {
              default: _withCtx$r(() => [
                _createElementVNode$u("div", _hoisted_1$u, [
                  _createElementVNode$u("div", _hoisted_2$t, [
                    _cache[7] || (_cache[7] = _createElementVNode$u("div", { class: "text-caption text-medium-emphasis mb-1" }, "当前搜索范围", -1)),
                    _createElementVNode$u("div", _hoisted_3$p, _toDisplayString$v(scopeText.value), 1),
                    _cache[8] || (_cache[8] = _createElementVNode$u("div", { class: "text-caption text-medium-emphasis mt-3 mb-1" }, "优先站点（命中即停，顺序有意义）", -1)),
                    _createElementVNode$u("div", _hoisted_4$m, _toDisplayString$v(prefText.value), 1)
                  ]),
                  _createElementVNode$u("div", _hoisted_5$k, [
                    _createVNode$s(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                      class: "mb-2",
                      onClick: openPick
                    }, {
                      default: _withCtx$r(() => _cache[9] || (_cache[9] = [
                        _createTextVNode$p("选择站点")
                      ])),
                      _: 1
                    }),
                    _createVNode$s(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-sort",
                      onClick: openPref
                    }, {
                      default: _withCtx$r(() => _cache[10] || (_cache[10] = [
                        _createTextVNode$p("优先站点")
                      ])),
                      _: 1
                    })
                  ])
                ]),
                _ctx.loaded && !_ctx.options.length ? (_openBlock$w(), _createBlock$q(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mt-3 text-caption"
                }, {
                  default: _withCtx$r(() => _cache[11] || (_cache[11] = [
                    _createTextVNode$p("没有读到任何站点（MoviePilot 站点目录为空或读取失败），下面两个按钮打开也没有内容可选。")
                  ])),
                  _: 1
                })) : _createCommentVNode$o("", true),
                _cache[12] || (_cache[12] = _createElementVNode$u("p", { class: "text-caption text-medium-emphasis mt-4 mb-0" }, " 「当前搜索范围」留空 = 全部已配置站点；优先站点会先搜、命中即停，所以顺序有意义。 两处都只写进默认规则，按顶条「保存修改」才生效。 ", -1))
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$s(_component_v_dialog, {
          modelValue: pickOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$r(() => [
            _createVNode$s(_component_v_card, null, {
              default: _withCtx$r(() => [
                _createVNode$s(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$r(() => [
                    _createVNode$s(_component_v_icon, {
                      icon: "mdi-checkbox-multiple-marked-outline",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[13] || (_cache[13] = _createTextVNode$p(" 选择站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$s(_component_v_card_subtitle, null, {
                  default: _withCtx$r(() => [
                    _createTextVNode$p("不勾任何站点 = 搜索全部已配置站点（" + _toDisplayString$v(props.options.length) + " 个）", 1)
                  ]),
                  _: 1
                }),
                _createVNode$s(_component_v_card_text, null, {
                  default: _withCtx$r(() => [
                    _createVNode$s(_component_v_text_field, {
                      modelValue: pickQuery.value,
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => pickQuery.value = $event),
                      label: "按名字筛选",
                      "prepend-inner-icon": "mdi-magnify",
                      variant: "outlined",
                      density: "compact",
                      clearable: "",
                      "hide-details": "",
                      class: "mb-3"
                    }, null, 8, ["modelValue"]),
                    _createElementVNode$u("div", _hoisted_6$j, [
                      _createVNode$s(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickAll
                      }, {
                        default: _withCtx$r(() => _cache[14] || (_cache[14] = [
                          _createTextVNode$p("全选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$s(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickNone
                      }, {
                        default: _withCtx$r(() => _cache[15] || (_cache[15] = [
                          _createTextVNode$p("全不选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$s(_component_v_spacer),
                      _createElementVNode$u("span", _hoisted_7$i, "已选 " + _toDisplayString$v(pickDraft.value.length), 1)
                    ]),
                    _createVNode$s(_component_v_divider, { class: "mb-1" }),
                    _createElementVNode$u("div", _hoisted_8$h, [
                      (_openBlock$w(true), _createElementBlock$v(_Fragment$n, null, _renderList$l(filteredOptions.value, (item) => {
                        return _openBlock$w(), _createBlock$q(_component_v_checkbox, {
                          key: item.name,
                          "model-value": pickDraft.value.includes(item.name),
                          label: item.name,
                          density: "compact",
                          "hide-details": "",
                          color: "primary",
                          "onUpdate:modelValue": () => pickToggle(item.name)
                        }, {
                          append: _withCtx$r(() => [
                            _createElementVNode$u("span", _hoisted_9$f, _toDisplayString$v(item.adapterLabel || item.adapter || ""), 1)
                          ]),
                          _: 2
                        }, 1032, ["model-value", "label", "onUpdate:modelValue"]);
                      }), 128)),
                      !filteredOptions.value.length ? (_openBlock$w(), _createElementBlock$v("div", _hoisted_10$f, " 没有匹配的站点。 ")) : _createCommentVNode$o("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$s(_component_v_card_actions, null, {
                  default: _withCtx$r(() => [
                    _createVNode$s(_component_v_spacer),
                    _createVNode$s(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickOpen.value = false)
                    }, {
                      default: _withCtx$r(() => _cache[16] || (_cache[16] = [
                        _createTextVNode$p("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$s(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: pickConfirm
                    }, {
                      default: _withCtx$r(() => _cache[17] || (_cache[17] = [
                        _createTextVNode$p("确定")
                      ])),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode$s(_component_v_dialog, {
          modelValue: prefOpen.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => prefOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$r(() => [
            _createVNode$s(_component_v_card, null, {
              default: _withCtx$r(() => [
                _createVNode$s(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$r(() => [
                    _createVNode$s(_component_v_icon, {
                      icon: "mdi-sort",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[18] || (_cache[18] = _createTextVNode$p(" 优先站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$s(_component_v_card_subtitle, null, {
                  default: _withCtx$r(() => _cache[19] || (_cache[19] = [
                    _createTextVNode$p("先搜这些站，命中即停 —— 顺序就是搜索顺序")
                  ])),
                  _: 1
                }),
                _createVNode$s(_component_v_card_text, null, {
                  default: _withCtx$r(() => [
                    _createElementVNode$u("div", _hoisted_11$d, "优先顺序（" + _toDisplayString$v(prefDraft.value.length) + "）", 1),
                    _createVNode$s(_component_v_list, {
                      density: "compact",
                      class: "avh-list mb-3"
                    }, {
                      default: _withCtx$r(() => [
                        (_openBlock$w(true), _createElementBlock$v(_Fragment$n, null, _renderList$l(prefDraft.value, (name, index) => {
                          return _openBlock$w(), _createBlock$q(_component_v_list_item, {
                            key: `${name}:${index}`
                          }, {
                            prepend: _withCtx$r(() => [
                              _createElementVNode$u("span", _hoisted_12$d, _toDisplayString$v(index + 1), 1)
                            ]),
                            append: _withCtx$r(() => [
                              _createVNode$s(_component_v_btn, {
                                icon: "mdi-arrow-up",
                                size: "x-small",
                                variant: "text",
                                disabled: index === 0,
                                onClick: ($event) => prefMove(index, -1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$s(_component_v_btn, {
                                icon: "mdi-arrow-down",
                                size: "x-small",
                                variant: "text",
                                disabled: index === prefDraft.value.length - 1,
                                onClick: ($event) => prefMove(index, 1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$s(_component_v_btn, {
                                icon: "mdi-close",
                                size: "x-small",
                                variant: "text",
                                onClick: ($event) => prefRemove(index)
                              }, null, 8, ["onClick"])
                            ]),
                            default: _withCtx$r(() => [
                              _createVNode$s(_component_v_list_item_title, null, {
                                default: _withCtx$r(() => [
                                  _createTextVNode$p(_toDisplayString$v(name), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024);
                        }), 128)),
                        !prefDraft.value.length ? (_openBlock$w(), _createBlock$q(_component_v_list_item, { key: 0 }, {
                          default: _withCtx$r(() => [
                            _createVNode$s(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                              default: _withCtx$r(() => _cache[20] || (_cache[20] = [
                                _createTextVNode$p(" 还没有优先站点：按下面的候选加进来。 ")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        })) : _createCommentVNode$o("", true)
                      ]),
                      _: 1
                    }),
                    _createVNode$s(_component_v_divider, { class: "mb-2" }),
                    _cache[21] || (_cache[21] = _createElementVNode$u("div", { class: "text-caption text-medium-emphasis mb-1" }, "候选站点（点击加入优先顺序）", -1)),
                    _createElementVNode$u("div", _hoisted_13$d, [
                      (_openBlock$w(true), _createElementBlock$v(_Fragment$n, null, _renderList$l(prefCandidates.value, (item) => {
                        return _openBlock$w(), _createBlock$q(_component_v_chip, {
                          key: item.name,
                          size: "small",
                          variant: "tonal",
                          "prepend-icon": "mdi-plus",
                          onClick: ($event) => prefAdd(item.name)
                        }, {
                          default: _withCtx$r(() => [
                            _createTextVNode$p(_toDisplayString$v(item.name), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"]);
                      }), 128)),
                      !prefCandidates.value.length ? (_openBlock$w(), _createElementBlock$v("span", _hoisted_14$d, " 全部站点都已在优先列表里。 ")) : _createCommentVNode$o("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$s(_component_v_card_actions, null, {
                  default: _withCtx$r(() => [
                    _createVNode$s(_component_v_spacer),
                    _createVNode$s(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[3] || (_cache[3] = ($event) => prefOpen.value = false)
                    }, {
                      default: _withCtx$r(() => _cache[22] || (_cache[22] = [
                        _createTextVNode$p("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$s(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: prefConfirm
                    }, {
                      default: _withCtx$r(() => _cache[23] || (_cache[23] = [
                        _createTextVNode$p("确定")
                      ])),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ], 64);
    };
  }
});

const SitesPanel = /* @__PURE__ */ _export_sfc(_sfc_main$w, [["__scopeId", "data-v-b3e77efa"]]);

const {defineComponent:_defineComponent$v} = await importShared('vue');

const {resolveComponent:_resolveComponent$q,createVNode:_createVNode$r,createTextVNode:_createTextVNode$o,withCtx:_withCtx$q,createElementVNode:_createElementVNode$t,renderList:_renderList$k,Fragment:_Fragment$m,openBlock:_openBlock$v,createElementBlock:_createElementBlock$u,toDisplayString:_toDisplayString$u,unref:_unref$9,createBlock:_createBlock$p} = await importShared('vue');

const _hoisted_1$t = { class: "text-caption text-medium-emphasis mb-3" };
const _hoisted_2$s = { class: "avh-grid mb-2" };
const {computed: computed$o} = await importShared('vue');
const _sfc_main$v = /* @__PURE__ */ _defineComponent$v({
  __name: "RulePanel",
  props: {
    rule: {},
    policyMinInterval: {},
    siteScopeCount: {}
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const RES_OPTIONS = [
      { value: "1080p", label: "1080P 优先" },
      { value: "2160p", label: "4K 优先" },
      { value: "only4k", label: "仅 4K" }
    ];
    const allow4kMatters = computed$o(() => props.rule.res === "1080p");
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    function patchNumber(key, raw) {
      const parsed = Number.parseInt(raw, 10);
      patch(key, Number.isFinite(parsed) ? parsed : 0);
    }
    function patchMaxPerDay(raw) {
      const parsed = Number.parseInt(raw, 10);
      if (!Number.isFinite(parsed)) {
        patch("maxPerDay", POLICY_MAX_PER_DAY);
        return;
      }
      patch("maxPerDay", Math.min(Math.max(parsed, 1), POLICY_MAX_PER_DAY));
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$q("v-icon");
      const _component_v_card_title = _resolveComponent$q("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$q("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$q("v-card-item");
      const _component_v_btn = _resolveComponent$q("v-btn");
      const _component_v_btn_toggle = _resolveComponent$q("v-btn-toggle");
      const _component_v_switch = _resolveComponent$q("v-switch");
      const _component_v_text_field = _resolveComponent$q("v-text-field");
      const _component_v_alert = _resolveComponent$q("v-alert");
      const _component_v_card_text = _resolveComponent$q("v-card-text");
      const _component_v_card = _resolveComponent$q("v-card");
      return _openBlock$v(), _createBlock$p(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$q(() => [
          _createVNode$r(_component_v_card_item, null, {
            prepend: _withCtx$q(() => [
              _createVNode$r(_component_v_icon, {
                icon: "mdi-filter-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$q(() => [
              _createVNode$r(_component_v_card_title, null, {
                default: _withCtx$q(() => _cache[8] || (_cache[8] = [
                  _createTextVNode$o("下载规则")
                ])),
                _: 1
              }),
              _createVNode$r(_component_v_card_subtitle, null, {
                default: _withCtx$q(() => _cache[9] || (_cache[9] = [
                  _createTextVNode$o("手动搜索与新建订阅的基准 · 数据走 POST /rule")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$r(_component_v_card_text, null, {
            default: _withCtx$q(() => [
              _cache[12] || (_cache[12] = _createElementVNode$t("div", { class: "text-caption text-medium-emphasis mb-1" }, "分辨率策略", -1)),
              _createVNode$r(_component_v_btn_toggle, {
                "model-value": props.rule.res,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-4",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => value && patch("res", value))
              }, {
                default: _withCtx$q(() => [
                  (_openBlock$v(), _createElementBlock$u(_Fragment$m, null, _renderList$k(RES_OPTIONS, (option) => {
                    return _createVNode$r(_component_v_btn, {
                      key: option.value,
                      value: option.value
                    }, {
                      default: _withCtx$q(() => [
                        _createTextVNode$o(_toDisplayString$u(option.label), 1)
                      ]),
                      _: 2
                    }, 1032, ["value"]);
                  }), 64))
                ]),
                _: 1
              }, 8, ["model-value"]),
              _cache[13] || (_cache[13] = _createElementVNode$t("p", { class: "text-caption text-medium-emphasis mb-4" }, " 这一项会真正参与打分与淘汰：「仅 4K」把非 4K 的种子直接淘汰。 ", -1)),
              _createVNode$r(_component_v_switch, {
                "model-value": props.rule.mustCnsub,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "必须中文字幕",
                class: "mb-1",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("mustCnsub", value === true))
              }, null, 8, ["model-value"]),
              _cache[14] || (_cache[14] = _createElementVNode$t("p", { class: "text-caption text-medium-emphasis mb-3" }, " 打开则没有中字的种直接淘汰；默认关（AV 站中字少，关掉时中字仍加 32 分优先选）。 ", -1)),
              _createVNode$r(_component_v_switch, {
                "model-value": props.rule.preferUncensored,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "破解 / 无码版优先",
                class: "mb-3",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("preferUncensored", value === true))
              }, null, 8, ["model-value"]),
              _createVNode$r(_component_v_switch, {
                "model-value": props.rule.allow4k,
                color: "primary",
                "hide-details": "",
                inset: "",
                disabled: !allow4kMatters.value,
                label: "允许 4K 择优",
                class: "mb-1",
                "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("allow4k", value === true))
              }, null, 8, ["model-value", "disabled"]),
              _createElementVNode$t("p", _hoisted_1$t, [
                allow4kMatters.value ? (_openBlock$v(), _createElementBlock$u(_Fragment$m, { key: 0 }, [
                  _createTextVNode$o("1080P 没有好种时升级 4K。")
                ], 64)) : (_openBlock$v(), _createElementBlock$u(_Fragment$m, { key: 1 }, [
                  _createTextVNode$o("已选「4K 优先 / 仅 4K」，这一项不再起作用。")
                ], 64))
              ]),
              _createElementVNode$t("div", _hoisted_2$s, [
                _createVNode$r(_component_v_text_field, {
                  "model-value": String(props.rule.minSeeders),
                  type: "number",
                  min: "0",
                  label: "做种数下限",
                  hint: "低于此值不下载",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = (value) => patchNumber("minSeeders", String(value ?? "")))
                }, null, 8, ["model-value"]),
                _createVNode$r(_component_v_text_field, {
                  "model-value": String(props.rule.maxPerDay),
                  type: "number",
                  min: "1",
                  max: _unref$9(POLICY_MAX_PER_DAY),
                  label: "每日检查上限",
                  hint: `每天最多检查订阅几次（政策上限 ${_unref$9(POLICY_MAX_PER_DAY)}）`,
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = (value) => patchMaxPerDay(String(value ?? "")))
                }, null, 8, ["model-value", "max", "hint"]),
                _createVNode$r(_component_v_text_field, {
                  "model-value": String(props.policyMinInterval || _unref$9(POLICY_MIN_INTERVAL_MIN)),
                  label: "检查间隔下限（分钟，只读）",
                  hint: "政策固定值，界面不放宽",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  readonly: "",
                  disabled: ""
                }, null, 8, ["model-value"])
              ]),
              _createVNode$r(_component_v_switch, {
                "model-value": props.rule.btFallback,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "PT 搜不到时用 BT 兜底",
                class: "mb-1",
                "onUpdate:modelValue": _cache[6] || (_cache[6] = (value) => patch("btFallback", value === true))
              }, null, 8, ["model-value"]),
              _cache[15] || (_cache[15] = _createElementVNode$t("p", { class: "text-caption text-medium-emphasis mb-3" }, [
                _createTextVNode$o(" 关：PT 没搜到就直接进「任务」页待确认（标记「PT/BT 待确认」），不试 BT。"),
                _createElementVNode$t("br"),
                _createTextVNode$o(" 开：自动再去 javdb 搜磁力；BT 也没有则进「任务」页并提示「该资源在所有源中均未找到」。 ")
              ], -1)),
              _cache[16] || (_cache[16] = _createElementVNode$t("div", { class: "text-caption text-medium-emphasis mb-1" }, "命中之后", -1)),
              _createVNode$r(_component_v_btn_toggle, {
                "model-value": props.rule.trigger,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-1",
                "onUpdate:modelValue": _cache[7] || (_cache[7] = (value) => value && patch("trigger", value))
              }, {
                default: _withCtx$q(() => [
                  _createVNode$r(_component_v_btn, { value: "notify" }, {
                    default: _withCtx$q(() => _cache[10] || (_cache[10] = [
                      _createTextVNode$o("仅通知")
                    ])),
                    _: 1
                  }),
                  _createVNode$r(_component_v_btn, { value: "auto" }, {
                    default: _withCtx$q(() => _cache[11] || (_cache[11] = [
                      _createTextVNode$o("自动下载")
                    ])),
                    _: 1
                  })
                ]),
                _: 1
              }, 8, ["model-value"]),
              _cache[17] || (_cache[17] = _createElementVNode$t("p", { class: "text-caption text-medium-emphasis mb-4" }, " 「自动下载」＝ 详情页「⬇ 下载该影片」与订阅检查命中时都直接提交下载（挑打分最高的合格候选）； 「仅通知」时命中的片进「任务」页等你手动下载。 ", -1)),
              _createVNode$r(_component_v_alert, {
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption"
              }, {
                default: _withCtx$q(() => [
                  _createTextVNode$o(" 搜索范围由左栏「搜索站点」决定：当前 " + _toDisplayString$u(props.siteScopeCount ? `限定 ${props.siteScopeCount} 个站点` : "全部已配置站点") + "。 保存路径 / 下载器 / qB 分类仍在插件存储里沿用现值（本栏暂不提供编辑入口）。 ", 1)
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const RulePanel = /* @__PURE__ */ _export_sfc(_sfc_main$v, [["__scopeId", "data-v-aeba1be9"]]);

const {defineComponent:_defineComponent$u} = await importShared('vue');

const {resolveComponent:_resolveComponent$p,createVNode:_createVNode$q,createTextVNode:_createTextVNode$n,withCtx:_withCtx$p,createElementVNode:_createElementVNode$s,renderList:_renderList$j,Fragment:_Fragment$l,openBlock:_openBlock$u,createElementBlock:_createElementBlock$t,toDisplayString:_toDisplayString$t,createBlock:_createBlock$o,createCommentVNode:_createCommentVNode$n} = await importShared('vue');

const _hoisted_1$s = { class: "text-caption text-medium-emphasis mb-4" };
const _hoisted_2$r = { class: "avh-grid mb-2" };
const _hoisted_3$o = { class: "avh-row mb-2" };
const _hoisted_4$l = { class: "text-caption text-medium-emphasis mb-4" };
const {computed: computed$n,ref: ref$s} = await importShared('vue');
const _sfc_main$u = /* @__PURE__ */ _defineComponent$u({
  __name: "ScrapePanel",
  props: {
    settings: {},
    api: { default: null },
    toast: { default: null }
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    const MODES = [
      { value: "off", label: "关闭", hint: "不启用自建刮削层：Emby 侧维持现状。" },
      { value: "fill", label: "只补空缺", hint: "只写 Emby 里为空的字段，已有值不覆盖。" },
      { value: "hybrid", label: "混合", hint: "自建层优先，它拿不到的字段按站点链继续问（javdb → javtxt）。" },
      { value: "own", label: "仅自建", hint: "只用自建层的结果；拿不到就留空，不再问别的站点。" }
    ];
    const modeHint = computed$n(
      () => MODES.find((item) => item.value === props.settings.scrapeMode)?.hint || ""
    );
    const TRAILERS = [
      { value: "off", label: "关闭", hint: "默认关闭：不下载、不写入任何预告片信息。" },
      { value: "remote", label: "远端地址", hint: "写 Emby 的 RemoteTrailers —— 实测写不进去（204 但读回为空），留着给以后。" },
      { value: "local", label: "本地文件", hint: "把预告片下成 <片名>-trailer.mp4 放在影片同目录，靠 Emby 实时扫描认领。" }
    ];
    const trailerHint = computed$n(
      () => TRAILERS.find((item) => item.value === props.settings.trailerMode)?.hint || ""
    );
    const check = ref$s(null);
    const checking = ref$s(false);
    async function runSelfcheck() {
      if (checking.value) return;
      checking.value = true;
      check.value = null;
      t.info(`正在自检模型 ${props.settings.translateModel} …`);
      try {
        const api = props.api;
        if (!api || typeof api.post !== "function") throw new Error("宿主 api 不可用");
        const payload = unwrap(
          await api.post("plugin/scrape/selfcheck", { model: props.settings.translateModel })
        );
        if (payload && typeof payload === "object" && payload.success === false) {
          throw new Error(String(payload.message || "模型自检失败"));
        }
        const ok = payload?.ok === void 0 ? true : !!payload.ok;
        const latency = payload?.latency_ms ?? payload?.latencyMs;
        const text = [
          `模型 ${String(payload?.model || props.settings.translateModel)}`,
          latency === void 0 || latency === null ? "" : `${latency} ms`,
          ok ? "可用" : String(payload?.error || "不可用")
        ].filter(Boolean).join(" · ");
        check.value = { ok, text };
        if (ok) t.success("模型自检通过");
        else t.warning(`模型自检未通过：${String(payload?.error || "原因未知")}`);
      } catch (err) {
        check.value = { ok: false, text: `自检失败：${errorText(err)}` };
        t.warning(`模型自检失败：${errorText(err)}`);
      } finally {
        checking.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$p("v-icon");
      const _component_v_card_title = _resolveComponent$p("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$p("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$p("v-card-item");
      const _component_v_btn = _resolveComponent$p("v-btn");
      const _component_v_btn_toggle = _resolveComponent$p("v-btn-toggle");
      const _component_v_switch = _resolveComponent$p("v-switch");
      const _component_v_text_field = _resolveComponent$p("v-text-field");
      const _component_v_alert = _resolveComponent$p("v-alert");
      const _component_v_card_text = _resolveComponent$p("v-card-text");
      const _component_v_card = _resolveComponent$p("v-card");
      return _openBlock$u(), _createBlock$o(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$p(() => [
          _createVNode$q(_component_v_card_item, null, {
            prepend: _withCtx$p(() => [
              _createVNode$q(_component_v_icon, {
                icon: "mdi-auto-fix",
                color: "primary"
              })
            ]),
            default: _withCtx$p(() => [
              _createVNode$q(_component_v_card_title, null, {
                default: _withCtx$p(() => _cache[8] || (_cache[8] = [
                  _createTextVNode$n("刮削")
                ])),
                _: 1
              }),
              _createVNode$q(_component_v_card_subtitle, null, {
                default: _withCtx$p(() => _cache[9] || (_cache[9] = [
                  _createTextVNode$n("自建刮削层 · 简介 / 翻译 / 裁切 / 预告片 · 与「下载规则」同一份插件设置（POST /rule）")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$q(_component_v_card_text, null, {
            default: _withCtx$p(() => [
              _cache[12] || (_cache[12] = _createElementVNode$s("div", { class: "text-caption text-medium-emphasis mb-1" }, "刮削模式", -1)),
              _createVNode$q(_component_v_btn_toggle, {
                "model-value": props.settings.scrapeMode,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-1",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => value && patch("scrapeMode", value))
              }, {
                default: _withCtx$p(() => [
                  (_openBlock$u(), _createElementBlock$t(_Fragment$l, null, _renderList$j(MODES, (item) => {
                    return _createVNode$q(_component_v_btn, {
                      key: item.value,
                      value: item.value
                    }, {
                      default: _withCtx$p(() => [
                        _createTextVNode$n(_toDisplayString$t(item.label), 1)
                      ]),
                      _: 2
                    }, 1032, ["value"]);
                  }), 64))
                ]),
                _: 1
              }, 8, ["model-value"]),
              _createElementVNode$s("p", _hoisted_1$s, _toDisplayString$t(modeHint.value) + " 具体字段路由由后端按这一档执行；本栏只负责选择与保存。 ", 1),
              _cache[13] || (_cache[13] = _createElementVNode$s("div", { class: "text-caption text-medium-emphasis mb-1" }, "简介来源", -1)),
              _createVNode$q(_component_v_switch, {
                "model-value": props.settings.plotJavtxt,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "Javtxt（中文直出）",
                class: "mb-1",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("plotJavtxt", value === true))
              }, null, 8, ["model-value"]),
              _cache[14] || (_cache[14] = _createElementVNode$s("p", { class: "text-caption text-medium-emphasis mb-4" }, [
                _createTextVNode$n(" javdb 侧不给简介（实测 12/12 "),
                _createElementVNode$s("code", null, "summary"),
                _createTextVNode$n(" 为 null），所以简介只能来自 Javtxt； 关掉它这一档等于「只写核心字段」。MetaTube 已于 0.8.1 整体下线，不再有第二个兜底源。 ")
              ], -1)),
              _createElementVNode$s("div", _hoisted_2$r, [
                _createVNode$q(_component_v_text_field, {
                  "model-value": props.settings.translateModel,
                  label: "翻译模型",
                  hint: "默认 hy3（同一网关；hy3 会把 token 烧在推理上，后端已给足 max_tokens）",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  clearable: "",
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("translateModel", String(value ?? "").trim() || "hy3"))
                }, null, 8, ["model-value"]),
                _createVNode$q(_component_v_text_field, {
                  "model-value": props.settings.translateModelFallback,
                  label: "备用模型",
                  hint: "主模型失败/超时后降级用它（默认 deepseek-v4.1-flash）",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  clearable: "",
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("translateModelFallback", String(value ?? "").trim()))
                }, null, 8, ["model-value"])
              ]),
              _createElementVNode$s("div", _hoisted_3$o, [
                _createVNode$q(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  "prepend-icon": "mdi-connection",
                  loading: checking.value,
                  onClick: runSelfcheck
                }, {
                  default: _withCtx$p(() => _cache[10] || (_cache[10] = [
                    _createTextVNode$n("模型自检")
                  ])),
                  _: 1
                }, 8, ["loading"]),
                _cache[11] || (_cache[11] = _createElementVNode$s("span", { class: "text-caption text-medium-emphasis" }, "POST /scrape/selfcheck（后端转 translator.selfcheck）", -1))
              ]),
              check.value ? (_openBlock$u(), _createBlock$o(_component_v_alert, {
                key: 0,
                type: check.value.ok ? "success" : "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-3"
              }, {
                default: _withCtx$p(() => [
                  _createTextVNode$n(_toDisplayString$t(check.value.text), 1)
                ]),
                _: 1
              }, 8, ["type"])) : _createCommentVNode$n("", true),
              _cache[15] || (_cache[15] = _createElementVNode$s("div", { class: "text-caption text-medium-emphasis mb-1" }, "预告片", -1)),
              _createVNode$q(_component_v_btn_toggle, {
                "model-value": props.settings.trailerMode,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-1",
                "onUpdate:modelValue": _cache[4] || (_cache[4] = (value) => value && patch("trailerMode", value))
              }, {
                default: _withCtx$p(() => [
                  (_openBlock$u(), _createElementBlock$t(_Fragment$l, null, _renderList$j(TRAILERS, (item) => {
                    return _createVNode$q(_component_v_btn, {
                      key: item.value,
                      value: item.value
                    }, {
                      default: _withCtx$p(() => [
                        _createTextVNode$n(_toDisplayString$t(item.label), 1)
                      ]),
                      _: 2
                    }, 1032, ["value"]);
                  }), 64))
                ]),
                _: 1
              }, 8, ["model-value"]),
              _createElementVNode$s("p", _hoisted_4$l, _toDisplayString$t(trailerHint.value) + " 产品口径：写媒体目录（本地文件那档）会让 Emby 立刻扫一遍库，所以这里默认停在「关闭」。 ", 1),
              _cache[16] || (_cache[16] = _createElementVNode$s("div", { class: "text-caption text-medium-emphasis mb-1" }, "下载完成即刮", -1)),
              _createVNode$q(_component_v_switch, {
                "model-value": props.settings.scrapeOnDownload,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "下载完成后立即刮削",
                class: "mb-1",
                "onUpdate:modelValue": _cache[5] || (_cache[5] = (value) => patch("scrapeOnDownload", value === true))
              }, null, 8, ["model-value"]),
              _cache[17] || (_cache[17] = _createElementVNode$s("p", { class: "text-caption text-medium-emphasis mb-4" }, " 台账入账那一刻就把这一部片刮一遍，不用等每天 3 次的订阅检查、也不用手动点。 代价：会写 Emby 元数据，每条之间按限流间隔串行（后台线程逐条做，不卡界面）； 「刮削模式」关掉时这一项不生效。 ", -1)),
              _cache[18] || (_cache[18] = _createElementVNode$s("div", { class: "text-caption text-medium-emphasis mb-1" }, "定时重刮", -1)),
              _createVNode$q(_component_v_switch, {
                "model-value": props.settings.autoScrapeTier1,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "Tier 1：新片与残缺片（指数退避 6h→24h→72h→7d→14d）",
                class: "mb-1",
                "onUpdate:modelValue": _cache[6] || (_cache[6] = (value) => patch("autoScrapeTier1", value === true))
              }, null, 8, ["model-value"]),
              _createVNode$q(_component_v_switch, {
                "model-value": props.settings.autoScrapeTier2,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "Tier 2：全库冷数据滚动（每轮取最久未更新的 5 条）",
                class: "mb-1",
                "onUpdate:modelValue": _cache[7] || (_cache[7] = (value) => patch("autoScrapeTier2", value === true))
              }, null, 8, ["model-value"]),
              _cache[19] || (_cache[19] = _createElementVNode$s("p", { class: "text-caption text-medium-emphasis mb-0" }, " 两档默认都关：打开后由后端调度器按退避节奏跑，队列长度在数据台「刮削」栏顶部看。 ", -1))
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const ScrapePanel = /* @__PURE__ */ _export_sfc(_sfc_main$u, [["__scopeId", "data-v-139af106"]]);

const RULE_FALLBACK = {
  res: "1080p",
  mustCnsub: false,
  preferUncensored: true,
  allow4k: true,
  minSeeders: 3,
  sites: [],
  prefSites: ["馒头", "Rousi"],
  btFallback: true,
  // 保存路径与下载器留空 = 用 MoviePilot 的下载器默认值（后端 tasks.DEFAULT_RULE 同口径）
  savePath: "",
  category: "avi",
  downloader: "",
  trigger: "notify",
  maxPerDay: 6,
  minIntervalMin: 240
};
function toRule(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  const merged = { ...RULE_FALLBACK };
  Object.keys(RULE_FALLBACK).forEach((key) => {
    const value = src[key];
    if (value === void 0 || value === null) return;
    merged[key] = Array.isArray(value) ? value.slice() : value;
  });
  return merged;
}
function shortTime(value) {
  const text = String(value === null || value === void 0 ? "" : value);
  if (!text) return "—";
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return text.replace("T", " ").slice(0, 16);
  return text;
}
function nowStr() {
  return (/* @__PURE__ */ new Date()).toLocaleTimeString("zh-CN", { hour12: false });
}

const {defineComponent:_defineComponent$t} = await importShared('vue');

const {resolveComponent:_resolveComponent$o,createVNode:_createVNode$p,createTextVNode:_createTextVNode$m,withCtx:_withCtx$o,createElementVNode:_createElementVNode$r,toDisplayString:_toDisplayString$s,openBlock:_openBlock$t,createBlock:_createBlock$n,createCommentVNode:_createCommentVNode$m,createElementBlock:_createElementBlock$s,renderList:_renderList$i,Fragment:_Fragment$k} = await importShared('vue');

const _hoisted_1$r = { class: "avh-row mb-2" };
const _hoisted_2$q = {
  key: 1,
  class: "avh-row mb-2"
};
const _hoisted_3$n = { class: "text-caption text-medium-emphasis" };
const _hoisted_4$k = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_5$j = {
  key: 2,
  class: "avh-row mb-3"
};
const _hoisted_6$i = { class: "avh-grid mb-2" };
const _hoisted_7$h = { class: "avh-row mb-2" };
const _hoisted_8$g = { class: "text-caption text-medium-emphasis" };
const {computed: computed$m,onMounted: onMounted$b,ref: ref$r} = await importShared('vue');
const _sfc_main$t = /* @__PURE__ */ _defineComponent$t({
  __name: "ActorPanel",
  props: {
    settings: {},
    api: { default: null },
    toast: { default: null }
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const confirm = useHostConfirm();
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    function textOf(value) {
      return value === null || value === void 0 ? "" : String(value);
    }
    async function getJson(path) {
      const api = props.api;
      if (!api || typeof api.get !== "function") throw new Error("宿主 api 不可用");
      const payload = unwrap(await api.get(path));
      if (payload && typeof payload === "object" && payload.success === false) {
        throw new Error(textOf(payload.message) || "接口返回失败");
      }
      return payload;
    }
    async function postJson(path, body) {
      const api = props.api;
      if (!api || typeof api.post !== "function") throw new Error("宿主 api 不可用");
      const payload = unwrap(await api.post(path, body));
      if (payload && typeof payload === "object" && payload.success === false) {
        throw new Error(textOf(payload.message) || "接口返回失败");
      }
      return payload;
    }
    function intField(value, fallback, min, max) {
      const num = Number(String(value ?? "").trim());
      if (!Number.isFinite(num)) return fallback;
      return Math.min(max, Math.max(min, Math.round(num)));
    }
    const sources = ref$r([]);
    const index = ref$r(null);
    const indexLoading = ref$r(false);
    const indexError = ref$r("");
    const indexText = computed$m(() => {
      const value = index.value;
      if (!value) return "";
      if (!value.count) return "索引还没拉过（刷新一次即会下载并解析）";
      const when = value.fetched_at ? shortTime(value.fetched_at) : "时间未知";
      return "索引 " + value.count + " 条 · 更新于 " + when;
    });
    function applyIndex(raw) {
      if (raw && typeof raw === "object") {
        index.value = {
          count: Number(raw.count) || 0,
          fetched_at: textOf(raw.fetched_at),
          stale: raw.stale === true,
          source: textOf(raw.source)
        };
      } else {
        index.value = null;
      }
    }
    async function loadSources(notify = false) {
      if (indexLoading.value) return;
      indexLoading.value = true;
      indexError.value = "";
      try {
        const payload = await getJson("plugin/actor/sources");
        const list = Array.isArray(payload?.sources) ? payload.sources : [];
        sources.value = list.map((row) => ({
          name: textOf(row?.name) || textOf(row?.id) || "(未命名源)",
          enabled: row?.enabled === void 0 ? true : !!row.enabled,
          note: textOf(row?.note) || textOf(row?.role)
        }));
        applyIndex(payload?.index);
        if (notify) t.info(indexText.value || "索引状态已刷新");
      } catch (err) {
        indexError.value = errorText(err);
        if (notify) t.warning("索引状态读取失败：" + indexError.value);
      } finally {
        indexLoading.value = false;
      }
    }
    const refreshing = ref$r(false);
    async function refreshIndex() {
      if (refreshing.value) return;
      refreshing.value = true;
      indexError.value = "";
      t.info("正在刷新 gFriends 索引（会下载并重新解析）…");
      try {
        const payload = await postJson("plugin/actor/gfriends/refresh", {});
        if (payload?.index && typeof payload.index === "object") applyIndex(payload.index);
        else await loadSources(false);
        t.success("索引已刷新：" + (indexText.value || "条数未知"));
      } catch (err) {
        indexError.value = errorText(err);
        t.warning("刷新索引失败：" + indexError.value);
      } finally {
        refreshing.value = false;
      }
    }
    function countOf(source, keys) {
      for (const key of keys) {
        const value = source[key];
        if (value === void 0 || value === null) continue;
        const num = Number(value);
        if (Number.isFinite(num)) return num;
      }
      return null;
    }
    function countActors(payload) {
      const counts = payload?.counts && typeof payload.counts === "object" ? payload.counts : {};
      const items = Array.isArray(payload?.items) ? payload.items : [];
      let up = countOf(counts, ["uploaded", "applied", "ok", "done"]);
      let skip = countOf(counts, ["skipped", "skip"]);
      let fail = countOf(counts, ["failed", "error", "errors"]);
      if (up === null || skip === null || fail === null) {
        let okCount = 0;
        let skipCount = 0;
        let failCount = 0;
        for (const item of items) {
          const action = textOf(item?.action ?? item?.status).toLowerCase();
          if (/fail|error/.test(action)) failCount += 1;
          else if (/skip|no_avatar|person_missing|has_image/.test(action)) skipCount += 1;
          else okCount += 1;
        }
        if (up === null) up = okCount;
        if (skip === null) skip = skipCount;
        if (fail === null) fail = failCount;
      }
      const errors = (Array.isArray(payload?.errors) ? payload.errors : []).map((item) => textOf(item)).filter(Boolean);
      return { up: up || 0, skip: skip || 0, fail: fail || 0, errors };
    }
    const fillResult = ref$r(null);
    const filling = ref$r(false);
    function fillText(counts, dryRun) {
      const line = "上传 " + counts.up + " / 跳过 " + counts.skip + " / 失败 " + counts.fail;
      return dryRun ? "补齐计划（dry_run，零写请求）：" + line : line;
    }
    function headErrors(errors) {
      const head = errors.slice(0, 5);
      if (errors.length > head.length) head.push("…… 另有 " + (errors.length - head.length) + " 条失败明细（后端日志里有全部）");
      return head;
    }
    async function fillMissingAvatars() {
      if (filling.value) return;
      const limit = props.settings.actorBatchSize;
      const proceed = await confirm({
        type: "warn",
        title: "一键补齐缺失头像",
        content: "这一步只读：先跑一次 dry_run 计划（零写请求，不会向 Emby 写任何东西）。\n\n真正的上传在你看到计划条数、再确认一次之后才发生：届时会把头像写进 Emby 的 Person 实体（Primary 图），每批最多 " + limit + " 位。\n\n本批只处理「缺头像」的演员；设了 images 锁的不会被覆盖（锁要在演员详情里解锁）。",
        confirmText: "先看计划",
        cancelText: "取消"
      });
      if (!proceed) return;
      filling.value = true;
      fillResult.value = null;
      try {
        t.info("正在读取补齐计划（dry_run，零写请求）…");
        let plan;
        try {
          const planPayload = await postJson("plugin/actor/scrape", { dry_run: true, limit });
          plan = countActors(planPayload);
        } catch (err) {
          fillResult.value = { ok: false, text: "补齐计划读取失败", notes: [], errors: [errorText(err)] };
          t.warning("补齐计划读取失败：" + errorText(err));
          return;
        }
        fillResult.value = {
          ok: plan.fail === 0 && !plan.errors.length,
          text: fillText(plan, true),
          notes: plan.up ? [] : ["本次没有需要上传的头像（缺头像的演员不在这一批，或两个源都没图）"],
          errors: headErrors(plan.errors)
        };
        if (!plan.up) {
          t.info("没有需要上传的头像：" + fillText(plan, false));
          return;
        }
        const go = await confirm({
          type: "warn",
          title: "补齐缺失头像（写入 Emby）",
          content: "dry_run 计划：" + fillText(plan, false) + "。\n\n确认后真的开始上传：把这 " + plan.up + " 张头像写进 Emby 的 Person 实体（Primary 图）；计划里已跳过的 " + plan.skip + " 位不会动，也没有别的写入。",
          confirmText: "上传 " + plan.up + " 张",
          cancelText: "取消"
        });
        if (!go) {
          t.info("已取消，没有向 Emby 写入任何东西");
          return;
        }
        t.info("正在上传 " + plan.up + " 张头像…");
        const payload = await postJson("plugin/actor/scrape", { dry_run: false, limit });
        const done = countActors(payload);
        fillResult.value = {
          ok: done.fail === 0 && !done.errors.length,
          text: fillText(done, false),
          notes: [],
          errors: headErrors(done.errors)
        };
        if (fillResult.value.ok) t.success("补齐完成：" + fillText(done, false));
        else t.warning("补齐未全部成功：" + fillText(done, false));
      } catch (err) {
        fillResult.value = { ok: false, text: "补齐请求失败", notes: [], errors: [errorText(err)] };
        t.warning("补齐失败：" + errorText(err));
      } finally {
        filling.value = false;
      }
    }
    onMounted$b(() => {
      void loadSources(false);
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$o("v-icon");
      const _component_v_card_title = _resolveComponent$o("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$o("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$o("v-card-item");
      const _component_v_switch = _resolveComponent$o("v-switch");
      const _component_v_btn = _resolveComponent$o("v-btn");
      const _component_v_alert = _resolveComponent$o("v-alert");
      const _component_v_chip = _resolveComponent$o("v-chip");
      const _component_v_text_field = _resolveComponent$o("v-text-field");
      const _component_v_card_text = _resolveComponent$o("v-card-text");
      const _component_v_card = _resolveComponent$o("v-card");
      return _openBlock$t(), _createBlock$n(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$o(() => [
          _createVNode$p(_component_v_card_item, null, {
            prepend: _withCtx$o(() => [
              _createVNode$p(_component_v_icon, {
                icon: "mdi-account-star",
                color: "primary"
              })
            ]),
            default: _withCtx$o(() => [
              _createVNode$p(_component_v_card_title, null, {
                default: _withCtx$o(() => _cache[7] || (_cache[7] = [
                  _createTextVNode$m("演员")
                ])),
                _: 1
              }),
              _createVNode$p(_component_v_card_subtitle, null, {
                default: _withCtx$o(() => _cache[8] || (_cache[8] = [
                  _createTextVNode$m("演员刮削子系统 · 头像源 / gFriends 索引 / 自动同步 · 与「下载规则」同一份插件设置（POST /rule）")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$p(_component_v_card_text, null, {
            default: _withCtx$o(() => [
              _createVNode$p(_component_v_switch, {
                "model-value": props.settings.actorEnabled,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "启用演员刮削子系统",
                class: "mb-1",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("actorEnabled", value === true))
              }, null, 8, ["model-value"]),
              _cache[13] || (_cache[13] = _createElementVNode$r("p", { class: "text-caption text-medium-emphasis mb-4" }, " 关掉 = 不抓演员、不写头像（已经写进去的数据保持不动）。影片刮削本身不受影响。 ", -1)),
              _cache[14] || (_cache[14] = _createElementVNode$r("div", { class: "text-caption text-medium-emphasis mb-1" }, "头像来源", -1)),
              _createVNode$p(_component_v_switch, {
                "model-value": props.settings.actorGfriends,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "gFriends 索引图（整图，最高清）",
                class: "mb-1",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("actorGfriends", value === true))
              }, null, 8, ["model-value"]),
              _createVNode$p(_component_v_switch, {
                "model-value": props.settings.actorJavdbFallback,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "javdb 演员页缩略图（兜底，比整图小）",
                class: "mb-1",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("actorJavdbFallback", value === true))
              }, null, 8, ["model-value"]),
              _cache[15] || (_cache[15] = _createElementVNode$r("p", { class: "text-caption text-medium-emphasis mb-4" }, " 两个都关 = 没有头像可用，只抓文字资料。顺序是先 gFriends 后 javdb（后端按这个顺序取第一张能用的）。 MetaTube 已于 0.8.1 整体下线，不再有第三个源。 ", -1)),
              _cache[16] || (_cache[16] = _createElementVNode$r("div", { class: "text-caption text-medium-emphasis mb-1" }, "gFriends 索引", -1)),
              _createElementVNode$r("div", _hoisted_1$r, [
                _createVNode$p(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  "prepend-icon": "mdi-refresh",
                  loading: refreshing.value,
                  onClick: refreshIndex
                }, {
                  default: _withCtx$o(() => _cache[9] || (_cache[9] = [
                    _createTextVNode$m("刷新索引")
                  ])),
                  _: 1
                }, 8, ["loading"]),
                _createVNode$p(_component_v_btn, {
                  variant: "text",
                  size: "small",
                  "prepend-icon": "mdi-database-eye-outline",
                  loading: indexLoading.value,
                  onClick: _cache[3] || (_cache[3] = ($event) => loadSources(true))
                }, {
                  default: _withCtx$o(() => _cache[10] || (_cache[10] = [
                    _createTextVNode$m("重新读取状态")
                  ])),
                  _: 1
                }, 8, ["loading"]),
                _cache[11] || (_cache[11] = _createElementVNode$r("span", { class: "text-caption text-medium-emphasis" }, "POST /actor/gfriends/refresh · GET /actor/sources", -1))
              ]),
              indexError.value ? (_openBlock$t(), _createBlock$n(_component_v_alert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-3"
              }, {
                default: _withCtx$o(() => [
                  _createTextVNode$m("索引状态读取失败：" + _toDisplayString$s(indexError.value), 1)
                ]),
                _: 1
              })) : _createCommentVNode$m("", true),
              index.value ? (_openBlock$t(), _createElementBlock$s("div", _hoisted_2$q, [
                _createVNode$p(_component_v_chip, {
                  size: "x-small",
                  color: index.value.stale ? "warning" : "success",
                  variant: "flat",
                  label: ""
                }, {
                  default: _withCtx$o(() => [
                    _createTextVNode$m(_toDisplayString$s(index.value.stale ? "索引已过期" : "索引可用"), 1)
                  ]),
                  _: 1
                }, 8, ["color"]),
                _createElementVNode$r("span", _hoisted_3$n, _toDisplayString$s(indexText.value), 1),
                index.value.source ? (_openBlock$t(), _createElementBlock$s("span", _hoisted_4$k, "· 来源 " + _toDisplayString$s(index.value.source), 1)) : _createCommentVNode$m("", true)
              ])) : _createCommentVNode$m("", true),
              sources.value.length ? (_openBlock$t(), _createElementBlock$s("div", _hoisted_5$j, [
                (_openBlock$t(true), _createElementBlock$s(_Fragment$k, null, _renderList$i(sources.value, (item) => {
                  return _openBlock$t(), _createBlock$n(_component_v_chip, {
                    key: item.name,
                    size: "x-small",
                    color: item.enabled ? "primary" : void 0,
                    variant: "tonal",
                    label: "",
                    title: item.note || item.name
                  }, {
                    default: _withCtx$o(() => [
                      _createTextVNode$m(_toDisplayString$s(item.enabled ? item.name : item.name + "（已关）"), 1)
                    ]),
                    _: 2
                  }, 1032, ["color", "title"]);
                }), 128))
              ])) : _createCommentVNode$m("", true),
              _cache[17] || (_cache[17] = _createElementVNode$r("p", { class: "text-caption text-medium-emphasis mb-4" }, " 索引是一份 gFriends 的「演员名 → 头像地址」表（拉一次缓存在本地，过期后由后端自动重拉）。 「刷新索引」立刻重下并重解析，不影响已经写进 Emby 的头像。 ", -1)),
              _cache[18] || (_cache[18] = _createElementVNode$r("div", { class: "text-caption text-medium-emphasis mb-1" }, "自动同步", -1)),
              _createVNode$p(_component_v_switch, {
                "model-value": props.settings.actorAutoSync,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "影片刮完后把该片女演员登记进队列，由定时任务慢慢补",
                class: "mb-1",
                "onUpdate:modelValue": _cache[4] || (_cache[4] = (value) => patch("actorAutoSync", value === true))
              }, null, 8, ["model-value"]),
              _createElementVNode$r("div", _hoisted_6$i, [
                _createVNode$p(_component_v_text_field, {
                  "model-value": String(props.settings.actorBatchSize),
                  label: "每轮条数",
                  hint: "定时任务每轮最多处理多少位（1–200，默认 20）",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  type: "number",
                  min: "1",
                  max: "200",
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = (value) => patch("actorBatchSize", intField(value, 20, 1, 200)))
                }, null, 8, ["model-value"]),
                _createVNode$p(_component_v_text_field, {
                  "model-value": String(props.settings.actorInterval),
                  label: "间隔（秒）",
                  hint: "每两位之间的最小间隔（1–60，默认 2）",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  type: "number",
                  min: "1",
                  max: "60",
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = (value) => patch("actorInterval", intField(value, 2, 1, 60)))
                }, null, 8, ["model-value"])
              ]),
              _cache[19] || (_cache[19] = _createElementVNode$r("p", { class: "text-caption text-medium-emphasis mb-4" }, " 队列不长在界面上：失败按 6h → 24h → 72h → 7d → 14d 退避，退避到顶后只等手动重刮。 下面这次「一键补齐」会立刻跑一批，不用等定时任务。 ", -1)),
              _cache[20] || (_cache[20] = _createElementVNode$r("div", { class: "text-caption text-medium-emphasis mb-1" }, "一键补齐缺失头像", -1)),
              _createElementVNode$r("div", _hoisted_7$h, [
                _createVNode$p(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  "prepend-icon": "mdi-account-sync-outline",
                  loading: filling.value,
                  onClick: fillMissingAvatars
                }, {
                  default: _withCtx$o(() => _cache[12] || (_cache[12] = [
                    _createTextVNode$m("一键补齐缺失头像")
                  ])),
                  _: 1
                }, 8, ["loading"]),
                _createElementVNode$r("span", _hoisted_8$g, " POST /actor/scrape（先 dry_run 看计划，再确认应用；每批 " + _toDisplayString$s(props.settings.actorBatchSize) + " 位） ", 1)
              ]),
              fillResult.value ? (_openBlock$t(), _createBlock$n(_component_v_alert, {
                key: 3,
                type: fillResult.value.ok ? "success" : "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-0"
              }, {
                default: _withCtx$o(() => [
                  _createElementVNode$r("div", null, _toDisplayString$s(fillResult.value.text), 1),
                  (_openBlock$t(true), _createElementBlock$s(_Fragment$k, null, _renderList$i(fillResult.value.notes, (line, index2) => {
                    return _openBlock$t(), _createElementBlock$s("div", {
                      key: "note#" + index2
                    }, _toDisplayString$s(line), 1);
                  }), 128)),
                  (_openBlock$t(true), _createElementBlock$s(_Fragment$k, null, _renderList$i(fillResult.value.errors, (line, index2) => {
                    return _openBlock$t(), _createElementBlock$s("div", { key: index2 }, _toDisplayString$s(line), 1);
                  }), 128))
                ]),
                _: 1
              }, 8, ["type"])) : _createCommentVNode$m("", true)
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const ActorPanel = /* @__PURE__ */ _export_sfc(_sfc_main$t, [["__scopeId", "data-v-a65bf8ed"]]);

const {defineComponent:_defineComponent$s} = await importShared('vue');

const {openBlock:_openBlock$s,createElementBlock:_createElementBlock$r,toDisplayString:_toDisplayString$r,normalizeClass:_normalizeClass$f} = await importShared('vue');

const _hoisted_1$q = ["src", "alt", "loading"];
const _hoisted_2$p = {
  key: 1,
  class: "avh-thumb__noimg"
};
const {computed: computed$l,ref: ref$q,watch: watch$c} = await importShared('vue');

const PROXY_MARK = "/img?url=";
const _sfc_main$s = /* @__PURE__ */ _defineComponent$s({
  __name: "Thumb",
  props: {
    src: { default: "" },
    alt: { default: "无图" },
    pluginId: { default: "" },
    variant: { default: "plain" },
    lazy: { type: Boolean, default: true },
    forcePlaceholder: { type: Boolean, default: false }
  },
  emits: ["failed"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const useProxy = ref$q(false);
    const failed = ref$q(false);
    watch$c(
      () => props.src,
      () => {
        useProxy.value = false;
        failed.value = false;
      }
    );
    const proxySrc = computed$l(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (raw.includes(PROXY_MARK)) return raw;
      if (!props.pluginId) return "";
      return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`;
    });
    const currentSrc = computed$l(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (!useProxy.value) return raw;
      return proxySrc.value;
    });
    const showPlaceholder = computed$l(
      () => props.forcePlaceholder || !String(props.src || "") || failed.value || !currentSrc.value
    );
    function onError() {
      const raw = String(props.src || "");
      if (!useProxy.value && proxySrc.value && proxySrc.value !== raw) {
        useProxy.value = true;
        return;
      }
      failed.value = true;
      emit("failed", raw);
    }
    return (_ctx, _cache) => {
      return _openBlock$s(), _createElementBlock$r("div", {
        class: _normalizeClass$f(["avh-thumb", `avh-thumb--${_ctx.variant}`])
      }, [
        !showPlaceholder.value ? (_openBlock$s(), _createElementBlock$r("img", {
          key: 0,
          src: currentSrc.value,
          alt: _ctx.alt,
          referrerpolicy: "no-referrer",
          loading: _ctx.lazy ? "lazy" : "eager",
          decoding: "async",
          onError
        }, null, 40, _hoisted_1$q)) : (_openBlock$s(), _createElementBlock$r("div", _hoisted_2$p, _toDisplayString$r(_ctx.alt || "无图"), 1))
      ], 2);
    };
  }
});

const Thumb = /* @__PURE__ */ _export_sfc(_sfc_main$s, [["__scopeId", "data-v-822d7759"]]);

const {defineComponent:_defineComponent$r} = await importShared('vue');

const {resolveComponent:_resolveComponent$n,createVNode:_createVNode$o,createTextVNode:_createTextVNode$l,withCtx:_withCtx$n,createElementVNode:_createElementVNode$q,toDisplayString:_toDisplayString$q,openBlock:_openBlock$r,createElementBlock:_createElementBlock$q,createCommentVNode:_createCommentVNode$l,renderList:_renderList$h,Fragment:_Fragment$j,createBlock:_createBlock$m,withKeys:_withKeys$3,normalizeClass:_normalizeClass$e} = await importShared('vue');

const _hoisted_1$p = { class: "text-caption text-medium-emphasis mb-2" };
const _hoisted_2$o = {
  key: 0,
  class: "text-warning"
};
const _hoisted_3$m = { class: "avh-row mb-2" };
const _hoisted_4$j = {
  key: 0,
  class: "ms-1"
};
const _hoisted_5$i = {
  key: 0,
  class: "text-caption text-medium-emphasis mb-2"
};
const _hoisted_6$h = { class: "avh-row mb-2" };
const _hoisted_7$g = { class: "avh-chips mb-1" };
const _hoisted_8$f = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_9$e = { class: "avh-chips mb-3" };
const _hoisted_10$e = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_11$c = { class: "avh-row mb-2" };
const _hoisted_12$c = { class: "avh-chips mb-3" };
const _hoisted_13$c = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_14$c = {
  key: 1,
  class: "avh-chain mb-4"
};
const _hoisted_15$b = { class: "avh-chain__k" };
const _hoisted_16$a = { class: "avh-chain__v" };
const _hoisted_17$a = {
  key: 2,
  class: "text-caption text-medium-emphasis mb-4"
};
const _hoisted_18$8 = { class: "avh-chips mb-2" };
const _hoisted_19$8 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_20$8 = { class: "avh-row mb-4" };
const _hoisted_21$6 = { class: "avh-row mb-1" };
const _hoisted_22$6 = { class: "text-caption text-medium-emphasis mb-4" };
const _hoisted_23$6 = { class: "text-subtitle-2 mb-1" };
const _hoisted_24$5 = {
  key: 3,
  class: "avh-preview mb-2"
};
const _hoisted_25$5 = { class: "avh-preview__row" };
const _hoisted_26$5 = { class: "avh-preview__row" };
const _hoisted_27$5 = { class: "avh-preview__row" };
const _hoisted_28$5 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_29$5 = { class: "avh-preview__row" };
const _hoisted_30$5 = { class: "avh-row mb-2" };
const _hoisted_31$5 = { class: "avh-map" };
const _hoisted_32$5 = { class: "avh-map__left" };
const _hoisted_33$5 = {
  key: 1,
  class: "avh-map__list"
};
const _hoisted_34$5 = ["onClick"];
const _hoisted_35$4 = { class: "avh-map__main" };
const _hoisted_36$4 = { class: "avh-map__name" };
const _hoisted_37$4 = { class: "avh-map__sub" };
const _hoisted_38$4 = {
  key: 0,
  class: "avh-map__sub"
};
const _hoisted_39$4 = {
  key: 2,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_40$4 = { class: "avh-map__right" };
const _hoisted_41$3 = {
  key: 1,
  class: "text-caption text-medium-emphasis mb-3"
};
const {computed: computed$k,onMounted: onMounted$a,ref: ref$p} = await importShared('vue');
const _sfc_main$r = /* @__PURE__ */ _defineComponent$r({
  __name: "ScrapeRulePanel",
  props: {
    settings: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    const graph = ref$p(null);
    const graphError = ref$p("");
    const graphLoading = ref$p(false);
    const enabledSources = computed$k(() => props.settings.sources || []);
    const allSources = computed$k(() => {
      const list = graph.value?.all_sources;
      return Array.isArray(list) ? list : [];
    });
    const fieldNames = computed$k(() => {
      const list = graph.value?.fields;
      return Array.isArray(list) && list.length ? list : [];
    });
    const chains = computed$k(() => {
      const raw = graph.value?.chains;
      return raw && typeof raw === "object" ? raw : {};
    });
    const FIELD_LABELS = {
      title_jp: "日文标题",
      origin_title: "原标题",
      title_zh: "中文标题",
      plot_jp: "日文简介",
      plot_zh: "中文简介",
      actors: "演员",
      tags: "标签",
      studio: "片商",
      publisher: "发行商",
      series: "系列",
      director: "导演",
      release_date: "发行日",
      duration: "时长",
      score: "评分",
      cover_url: "封面",
      thumb_url: "缩略图",
      preview_video_url: "预告片",
      preview_images: "剧照",
      javdb_id: "来源 ID"
    };
    function fieldLabel(name) {
      return FIELD_LABELS[name] || name;
    }
    async function loadGraph() {
      if (graphLoading.value) return;
      graphLoading.value = true;
      graphError.value = "";
      try {
        const api = props.api;
        if (!api || typeof api.get !== "function") throw new Error("宿主 api 不可用");
        const payload = unwrap(await api.get("plugin/scrape/graph"));
        if (payload && typeof payload === "object" && payload.success === false) {
          throw new Error(String(payload.message || "取数图读取失败"));
        }
        graph.value = payload && typeof payload === "object" ? payload : null;
      } catch (err) {
        graphError.value = errorText(err);
        graph.value = null;
      } finally {
        graphLoading.value = false;
      }
    }
    onMounted$a(() => {
      void loadGraph();
    });
    function toggleSource(id, on) {
      const current = new Set(enabledSources.value);
      if (on) current.add(id);
      else current.delete(id);
      current.add("javdb");
      patch("sources", [...current]);
    }
    const pickField = ref$p("");
    const pickSource = ref$p("");
    const pickKind = ref$p("fieldPriority");
    function fieldMap(name) {
      const raw = props.settings[name];
      return raw && typeof raw === "object" ? { ...raw } : {};
    }
    function pickRows(name) {
      const out = [];
      for (const [field, sites] of Object.entries(fieldMap(name))) {
        for (const source of sites) out.push({ field, source });
      }
      return out;
    }
    function addPick() {
      const field = pickField.value || fieldNames.value[0] || "";
      const source = pickSource.value || enabledSources.value[0] || "";
      if (!field || !source) return;
      const kind = pickKind.value;
      const current = fieldMap(kind);
      const list = [...current[field] || []];
      if (!list.includes(source)) list.push(source);
      current[field] = list;
      patch(kind, current);
    }
    function removePick(kind, field, source) {
      const current = fieldMap(kind);
      const list = (current[field] || []).filter((item) => item !== source);
      if (list.length) current[field] = list;
      else delete current[field];
      patch(kind, current);
    }
    const newHost = ref$p("");
    const newRate = ref$p("");
    const rateRows = computed$k(() => Object.entries(props.settings.rateLimits || {}));
    function addRate() {
      const host = String(newHost.value || "").trim();
      const rate = String(newRate.value || "").trim();
      if (!host || !rate) return;
      patch("rateLimits", { ...props.settings.rateLimits || {}, [host]: rate });
      newHost.value = "";
      newRate.value = "";
    }
    function removeRate(host) {
      const next = { ...props.settings.rateLimits || {} };
      delete next[host];
      patch("rateLimits", next);
    }
    const newSuffix = ref$p("");
    const suffixes = computed$k(() => props.settings.cleanSuffixes || []);
    function addSuffix() {
      const word = String(newSuffix.value || "").trim();
      if (!word) return;
      if (suffixes.value.some((item) => item.toLowerCase() === word.toLowerCase())) {
        t.info(`词表里已经有「${word}」了`);
        newSuffix.value = "";
        return;
      }
      patch("cleanSuffixes", [...suffixes.value, word]);
      newSuffix.value = "";
    }
    function removeSuffix(index) {
      patch("cleanSuffixes", suffixes.value.filter((_, i) => i !== index));
    }
    function resetSuffixes() {
      patch("cleanSuffixes", ["-UC", "_4K", "-4K", "-C", "-L", "-VR", "-ISO", "CD1", "CD2", "中字", "流出"]);
    }
    const TEMPLATE_VARS = ["{number}", "{badge}", "{title}"];
    function insertVar(token) {
      const current = String(props.settings.nameTemplate || "");
      patch("nameTemplate", `${current}${token}`);
    }
    const NOT_PREFIX = /* @__PURE__ */ new Set([
      "MP4",
      "MKV",
      "AVI",
      "WMV",
      "MOV",
      "FHD",
      "HD",
      "SD",
      "UHD",
      "XXX",
      "HEVC",
      "AVC",
      "X264",
      "X265",
      "H264",
      "H265",
      "AAC",
      "HDR",
      "VR",
      "ISO",
      "CD",
      "PPV"
    ]);
    function tagOf(word) {
      const w = word.toUpperCase().replace(/^[-_\s]+/, "");
      if (!w) return null;
      if (w.includes("中字") || w.includes("中文字幕") || w === "C" || w === "CN") return { label: "中字", tone: "cn" };
      if (w.includes("流出") || w.includes("UC") || w.includes("无码") || w.includes("破解")) return { label: "流出", tone: "uc" };
      if (w.includes("4K") || w.includes("2160")) return { label: "4K", tone: "res" };
      if (/^CD\d+$/.test(w)) return { label: w, tone: "part" };
      if (w === "ISO") return { label: "ISO", tone: "other" };
      if (w === "VR") return { label: "VR", tone: "other" };
      if (/^L$/.test(w)) return { label: "L", tone: "part" };
      return null;
    }
    function parsePreview(raw) {
      const empty = { matched: false, displayNumber: "", normKey: "", tags: [], renderedName: "", rest: "" };
      const input = String(raw || "").trim();
      if (!input) return empty;
      const base = input.replace(/\\/g, "/").split("/").pop() || "";
      let text = base.replace(/\.[A-Za-z0-9]{2,5}$/, "");
      const tags = [];
      const pushTag = (tag) => {
        if (tag && !tags.some((item) => item.label === tag.label)) tags.push(tag);
      };
      const words = [...suffixes.value, "中字", "流出", "无码", "破解", "4K"].sort((a, b) => b.length - a.length);
      let changed = true;
      while (changed) {
        changed = false;
        const head = text;
        for (const word of words) {
          const w = word.trim();
          if (!w) continue;
          const escaped = w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
          const re = new RegExp(`[-_\\s]*${escaped}$`, "i");
          if (re.test(text)) {
            text = text.replace(re, "");
            pushTag(tagOf(w));
            changed = true;
            break;
          }
        }
        if (text === head) changed = false;
      }
      text = text.replace(/[-_\s]+$/, "").trim();
      const upper = text.toUpperCase();
      let displayNumber = "";
      let normKey = "";
      const fc2 = /FC2[-_\s]*(?:PPV[-_\s]*)?(\d{4,})/.exec(upper);
      if (fc2) {
        const num = String(Number.parseInt(fc2[1], 10));
        displayNumber = `FC2-PPV-${num}`;
        normKey = `FC2PPV${num}`;
      } else {
        const std = /([A-Z]{2,10})[-_\s]?(\d{2,5})(?![0-9A-Z])/.exec(upper);
        if (std && !NOT_PREFIX.has(std[1])) {
          const prefix = std[1];
          const digits = std[2];
          displayNumber = `${prefix}-${digits.length >= 4 ? digits : digits.padStart(3, "0")}`;
          normKey = `${prefix}${Number.parseInt(digits, 10)}`;
        }
      }
      if (!displayNumber) {
        return { ...empty, tags, rest: text };
      }
      const order = ["中字", "流出", "4K", "ISO", "VR"];
      const badge = tags.filter((tag) => tag.tone === "cn" || tag.tone === "uc" || tag.tone === "res").map((tag) => tag.label).sort((a, b) => order.indexOf(a) - order.indexOf(b)).join("");
      const renderedName = String(props.settings.nameTemplate || "{number}{badge} {title}").split("{number}").join(displayNumber).split("{badge}").join(badge).split("{title}").join("中文标题");
      return { matched: true, displayNumber, normKey, tags, renderedName, rest: text };
    }
    const sampleName = ref$p("");
    const preview = computed$k(() => parsePreview(sampleName.value));
    const previewSummary = computed$k(() => {
      const result = preview.value;
      if (!String(sampleName.value || "").trim()) return "输入一段文件名（可带路径与扩展名）后立刻看到解析结果。";
      if (!result.matched) return "没认出番号：检查①里的词表是否缺词，或者换个写法再试。";
      return `display_number = ${result.displayNumber} · norm_key = ${result.normKey}`;
    });
    const entity = ref$p("actor");
    const q = ref$p("");
    const rows = ref$p([]);
    const listLoading = ref$p(false);
    const listError = ref$p("");
    const selected = ref$p(null);
    const draftName = ref$p("");
    const draftZh = ref$p("");
    const draftJp = ref$p("");
    const saving = ref$p(false);
    const entityLabel = computed$k(() => entity.value === "actor" ? "演员" : "标签");
    async function loadMap() {
      if (listLoading.value) return;
      listLoading.value = true;
      listError.value = "";
      try {
        const api = props.api;
        if (!api || typeof api.get !== "function") throw new Error("宿主 api 不可用");
        const path = entity.value === "actor" ? "plugin/namemap/actors" : "plugin/namemap/tags";
        const payload = unwrap(await api.get(path, { params: { q: q.value, limit: 30 } }));
        if (payload && typeof payload === "object" && payload.success === false) {
          throw new Error(String(payload.message || "映射读取失败"));
        }
        rows.value = Array.isArray(payload?.items) ? payload.items : [];
      } catch (err) {
        listError.value = errorText(err);
        rows.value = [];
      } finally {
        listLoading.value = false;
      }
    }
    function switchEntity(next) {
      if (entity.value === next) return;
      entity.value = next;
      selected.value = null;
      rows.value = [];
      void loadMap();
    }
    function pickRow(row) {
      selected.value = row;
      draftName.value = String(row?.canonical_id || row?.jp || row?.zh || "");
      draftZh.value = String(row?.zh || "");
      draftJp.value = String(row?.jp || "");
    }
    function extrasOf(row) {
      const out = [];
      if (row?.tw) out.push(`繁：${String(row.tw)}`);
      const aliases = Array.isArray(row?.aliases) ? row.aliases : [];
      if (aliases.length) out.push(`别名：${aliases.slice(0, 3).map((item) => String(item)).join("、")}`);
      if (row?.source) out.push(`来源：${String(row.source)}`);
      if (row?.is_delete_rule) out.push("命中即剔除");
      return out.join(" · ");
    }
    async function saveMapping() {
      if (saving.value) return;
      const name = String(draftName.value || "").trim();
      if (!name) {
        t.warning("请先填「键 / 原名」");
        return;
      }
      saving.value = true;
      try {
        const api = props.api;
        if (!api || typeof api.post !== "function") throw new Error("宿主 api 不可用");
        const body = { name, zh: String(draftZh.value ?? ""), entity_type: entity.value };
        const jp = String(draftJp.value || "").trim();
        if (jp) body.jp = jp;
        const payload = unwrap(await api.post("plugin/namemap/set", body));
        if (payload && typeof payload === "object" && payload.success === false) {
          throw new Error(String(payload.message || "映射保存失败"));
        }
        t.success(`已保存${entityLabel.value}映射`);
        if (payload?.canonical_id) t.info(`canonical_id = ${payload.canonical_id}`);
        await loadMap();
      } catch (err) {
        t.warning(`映射保存失败：${errorText(err)}`);
      } finally {
        saving.value = false;
      }
    }
    void loadMap();
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$n("v-icon");
      const _component_v_card_title = _resolveComponent$n("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$n("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$n("v-card-item");
      const _component_v_chip = _resolveComponent$n("v-chip");
      const _component_v_btn = _resolveComponent$n("v-btn");
      const _component_v_select = _resolveComponent$n("v-select");
      const _component_v_text_field = _resolveComponent$n("v-text-field");
      const _component_v_divider = _resolveComponent$n("v-divider");
      const _component_v_alert = _resolveComponent$n("v-alert");
      const _component_v_btn_toggle = _resolveComponent$n("v-btn-toggle");
      const _component_v_card_text = _resolveComponent$n("v-card-text");
      const _component_v_card = _resolveComponent$n("v-card");
      return _openBlock$r(), _createBlock$m(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$n(() => [
          _createVNode$o(_component_v_card_item, null, {
            prepend: _withCtx$n(() => [
              _createVNode$o(_component_v_icon, {
                icon: "mdi-file-document-edit-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$n(() => [
              _createVNode$o(_component_v_card_title, null, {
                default: _withCtx$n(() => _cache[14] || (_cache[14] = [
                  _createTextVNode$l("刮削规则")
                ])),
                _: 1
              }),
              _createVNode$o(_component_v_card_subtitle, null, {
                default: _withCtx$n(() => _cache[15] || (_cache[15] = [
                  _createTextVNode$l("数据源与取数链 · 字段择优 · 限流 · 后缀清洗 · 命名模板 · 演员/标签映射 · 文件名试跑（本地预览）")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$o(_component_v_card_text, null, {
            default: _withCtx$n(() => [
              _cache[38] || (_cache[38] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1" }, "数据源", -1)),
              _createElementVNode$q("p", _hoisted_1$p, [
                _cache[16] || (_cache[16] = _createTextVNode$l(" 关掉的源")),
                _cache[17] || (_cache[17] = _createElementVNode$q("b", null, "一个请求都不会发", -1)),
                _cache[18] || (_cache[18] = _createTextVNode$l("（取数图里直接没有它）。JavDB 是骨架源，不可关。 ")),
                graphError.value ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_2$o, "取数图读取失败：" + _toDisplayString$q(graphError.value), 1)) : _createCommentVNode$l("", true)
              ]),
              _createElementVNode$q("div", _hoisted_3$m, [
                (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(allSources.value, (src) => {
                  return _openBlock$r(), _createBlock$m(_component_v_chip, {
                    key: src.id,
                    size: "small",
                    color: enabledSources.value.includes(src.id) ? "primary" : void 0,
                    variant: enabledSources.value.includes(src.id) ? "flat" : "tonal",
                    disabled: src.always_on,
                    onClick: ($event) => toggleSource(src.id, !enabledSources.value.includes(src.id))
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l(_toDisplayString$q(src.label || src.id), 1),
                      src.phase === 2 ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_4$j, "（第二段）")) : _createCommentVNode$l("", true)
                    ]),
                    _: 2
                  }, 1032, ["color", "variant", "disabled", "onClick"]);
                }), 128)),
                _createVNode$o(_component_v_btn, {
                  variant: "text",
                  size: "x-small",
                  loading: graphLoading.value,
                  onClick: loadGraph
                }, {
                  default: _withCtx$n(() => _cache[19] || (_cache[19] = [
                    _createTextVNode$l("↻ 刷新当前链")
                  ])),
                  _: 1
                }, 8, ["loading"])
              ]),
              !allSources.value.length ? (_openBlock$r(), _createElementBlock$q("div", _hoisted_5$i, " （拿不到数据源清单：后端未就绪或接口未上线） ")) : _createCommentVNode$l("", true),
              _cache[39] || (_cache[39] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1 mt-3" }, "字段择优", -1)),
              _cache[40] || (_cache[40] = _createElementVNode$q("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _createElementVNode$q("b", null, "先问的源"),
                _createTextVNode$l("：只对选中的那个字段生效（链上其余站点顺序不变）；"),
                _createElementVNode$q("b", null, "不用的源"),
                _createTextVNode$l("：该字段不采用它。 两者都留空 = 用默认链。字段与站点清单来自后端，写错的值会被保存接口拦掉。 ")
              ], -1)),
              _createElementVNode$q("div", _hoisted_6$h, [
                _createVNode$o(_component_v_select, {
                  modelValue: pickKind.value,
                  "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => pickKind.value = $event),
                  class: "avh-pick-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  items: [{ title: "先问的源", value: "fieldPriority" }, { title: "不用的源", value: "fieldBlacklist" }]
                }, null, 8, ["modelValue"]),
                _createVNode$o(_component_v_select, {
                  modelValue: pickField.value,
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => pickField.value = $event),
                  class: "avh-pick-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  placeholder: "字段",
                  items: fieldNames.value.map((name) => ({ title: fieldLabel(name), value: name }))
                }, null, 8, ["modelValue", "items"]),
                _createVNode$o(_component_v_select, {
                  modelValue: pickSource.value,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickSource.value = $event),
                  class: "avh-pick-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  placeholder: "站点",
                  items: enabledSources.value.map((id) => ({ title: id, value: id }))
                }, null, 8, ["modelValue", "items"]),
                _createVNode$o(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  "prepend-icon": "mdi-plus",
                  onClick: addPick
                }, {
                  default: _withCtx$n(() => _cache[20] || (_cache[20] = [
                    _createTextVNode$l("添加")
                  ])),
                  _: 1
                })
              ]),
              _createElementVNode$q("div", _hoisted_7$g, [
                (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(pickRows("fieldPriority"), (row) => {
                  return _openBlock$r(), _createBlock$m(_component_v_chip, {
                    key: `p#${row.field}#${row.source}`,
                    size: "small",
                    color: "primary",
                    variant: "tonal",
                    closable: "",
                    "onClick:close": ($event) => removePick("fieldPriority", row.field, row.source)
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l("先问 " + _toDisplayString$q(fieldLabel(row.field)) + " → " + _toDisplayString$q(row.source), 1)
                    ]),
                    _: 2
                  }, 1032, ["onClick:close"]);
                }), 128)),
                !pickRows("fieldPriority").length ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_8$f, "（没有字段优先级）")) : _createCommentVNode$l("", true)
              ]),
              _createElementVNode$q("div", _hoisted_9$e, [
                (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(pickRows("fieldBlacklist"), (row) => {
                  return _openBlock$r(), _createBlock$m(_component_v_chip, {
                    key: `b#${row.field}#${row.source}`,
                    size: "small",
                    variant: "tonal",
                    closable: "",
                    "onClick:close": ($event) => removePick("fieldBlacklist", row.field, row.source)
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l("不用 " + _toDisplayString$q(fieldLabel(row.field)) + " ← " + _toDisplayString$q(row.source), 1)
                    ]),
                    _: 2
                  }, 1032, ["onClick:close"]);
                }), 128)),
                !pickRows("fieldBlacklist").length ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_10$e, "（没有字段排除）")) : _createCommentVNode$l("", true)
              ]),
              _cache[41] || (_cache[41] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1" }, "限流", -1)),
              _cache[42] || (_cache[42] = _createElementVNode$q("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _createTextVNode$l(" 每个域名两次请求的"),
                _createElementVNode$q("b", null, "最小间隔"),
                _createTextVNode$l('（秒，0.2~60）。只影响"调用方没写死间隔"的取数： '),
                _createElementVNode$q("code", null, "javtxt"),
                _createTextVNode$l(" 的 2 秒是硬要求，调这里不会让它变快。被站点拦截后该域名会自动冷却 6 小时。 ")
              ], -1)),
              _createElementVNode$q("div", _hoisted_11$c, [
                _createVNode$o(_component_v_text_field, {
                  "model-value": props.settings.defaultRateLimit,
                  class: "avh-pick-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  "single-line": "",
                  type: "number",
                  label: "默认间隔（秒）",
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("defaultRateLimit", String(value ?? "")))
                }, null, 8, ["model-value"]),
                _createVNode$o(_component_v_text_field, {
                  modelValue: newHost.value,
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => newHost.value = $event),
                  class: "avh-pick-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  "single-line": "",
                  placeholder: "域名，如 javtxt.com"
                }, null, 8, ["modelValue"]),
                _createVNode$o(_component_v_text_field, {
                  modelValue: newRate.value,
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => newRate.value = $event),
                  class: "avh-pick-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  "single-line": "",
                  type: "number",
                  placeholder: "秒"
                }, null, 8, ["modelValue"]),
                _createVNode$o(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  "prepend-icon": "mdi-plus",
                  onClick: addRate
                }, {
                  default: _withCtx$n(() => _cache[21] || (_cache[21] = [
                    _createTextVNode$l("添加")
                  ])),
                  _: 1
                })
              ]),
              _createElementVNode$q("div", _hoisted_12$c, [
                (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(rateRows.value, ([host, rate]) => {
                  return _openBlock$r(), _createBlock$m(_component_v_chip, {
                    key: `rate#${host}`,
                    size: "small",
                    variant: "tonal",
                    closable: "",
                    "onClick:close": ($event) => removeRate(host)
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l(_toDisplayString$q(host) + " = " + _toDisplayString$q(rate) + "s", 1)
                    ]),
                    _: 2
                  }, 1032, ["onClick:close"]);
                }), 128)),
                !rateRows.value.length ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_13$c, "（没有按域名覆盖）")) : _createCommentVNode$l("", true)
              ]),
              _cache[43] || (_cache[43] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1" }, "当前生效的链", -1)),
              _cache[44] || (_cache[44] = _createElementVNode$q("p", { class: "text-caption text-medium-emphasis mb-1" }, [
                _createTextVNode$l(" 这一份是"),
                _createElementVNode$q("b", null, "后端按已保存的配置"),
                _createTextVNode$l("算出来的（改完要保存才会变）；每个字段按链的顺序问， 取第一个非空值。 ")
              ], -1)),
              Object.keys(chains.value).length ? (_openBlock$r(), _createElementBlock$q("div", _hoisted_14$c, [
                (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(chains.value, (chain, field) => {
                  return _openBlock$r(), _createElementBlock$q("div", {
                    key: `chain#${field}`,
                    class: "avh-chain__row"
                  }, [
                    _createElementVNode$q("span", _hoisted_15$b, _toDisplayString$q(fieldLabel(String(field))), 1),
                    _createElementVNode$q("span", _hoisted_16$a, _toDisplayString$q(chain.join(" → ") || "（没有可用数据源）"), 1)
                  ]);
                }), 128))
              ])) : (_openBlock$r(), _createElementBlock$q("p", _hoisted_17$a, "（拿不到链：后端未就绪或接口未上线）")),
              _cache[45] || (_cache[45] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1" }, "后缀清洗词表", -1)),
              _cache[46] || (_cache[46] = _createElementVNode$q("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _createTextVNode$l(" 解析番号前从文件名末尾"),
                _createElementVNode$q("strong", null, "逐个剥离"),
                _createTextVNode$l("这些词，剥离结果决定番号与版本角标（"),
                _createElementVNode$q("code", null, "中字"),
                _createTextVNode$l(" / "),
                _createElementVNode$q("code", null, "流出"),
                _createTextVNode$l(" / "),
                _createElementVNode$q("code", null, "4K"),
                _createTextVNode$l("）。 顺序就是剥离顺序；大小写不敏感。 ")
              ], -1)),
              _createElementVNode$q("div", _hoisted_18$8, [
                (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(suffixes.value, (word, index) => {
                  return _openBlock$r(), _createBlock$m(_component_v_chip, {
                    key: `${word}#${index}`,
                    size: "small",
                    variant: "tonal",
                    closable: "",
                    "onClick:close": ($event) => removeSuffix(index)
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l(_toDisplayString$q(word), 1)
                    ]),
                    _: 2
                  }, 1032, ["onClick:close"]);
                }), 128)),
                !suffixes.value.length ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_19$8, "（词表为空：不做任何后缀清洗）")) : _createCommentVNode$l("", true)
              ]),
              _createElementVNode$q("div", _hoisted_20$8, [
                _createVNode$o(_component_v_text_field, {
                  modelValue: newSuffix.value,
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => newSuffix.value = $event),
                  class: "avh-suffix-input",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  "single-line": "",
                  placeholder: "新增一个词，如 -UC / _4K / CD1",
                  onKeydown: _withKeys$3(addSuffix, ["enter"])
                }, null, 8, ["modelValue"]),
                _createVNode$o(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  "prepend-icon": "mdi-plus",
                  onClick: addSuffix
                }, {
                  default: _withCtx$n(() => _cache[22] || (_cache[22] = [
                    _createTextVNode$l("添加")
                  ])),
                  _: 1
                }),
                _createVNode$o(_component_v_btn, {
                  variant: "text",
                  size: "small",
                  onClick: resetSuffixes
                }, {
                  default: _withCtx$n(() => _cache[23] || (_cache[23] = [
                    _createTextVNode$l("恢复默认")
                  ])),
                  _: 1
                })
              ]),
              _createVNode$o(_component_v_divider, { class: "my-4" }),
              _cache[47] || (_cache[47] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1" }, "命名模板（Emby Name）", -1)),
              _createVNode$o(_component_v_text_field, {
                "model-value": props.settings.nameTemplate,
                label: "命名模板",
                hint: "可用变量见下面三颗按钮；空模板按默认值 {number}{badge} {title} 处理",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                class: "mb-2",
                "onUpdate:modelValue": _cache[7] || (_cache[7] = (value) => patch("nameTemplate", String(value ?? "")))
              }, null, 8, ["model-value"]),
              _createElementVNode$q("div", _hoisted_21$6, [
                (_openBlock$r(), _createElementBlock$q(_Fragment$j, null, _renderList$h(TEMPLATE_VARS, (token) => {
                  return _createVNode$o(_component_v_chip, {
                    key: token,
                    size: "small",
                    variant: "outlined",
                    onClick: ($event) => insertVar(token)
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l(_toDisplayString$q(token), 1)
                    ]),
                    _: 2
                  }, 1032, ["onClick"]);
                }), 64)),
                _cache[24] || (_cache[24] = _createElementVNode$q("span", { class: "text-caption text-medium-emphasis" }, " {number} 展示番号 · {badge} 版本角标（无角标时是空串）· {title} 中文标题（取不到时保留原标题） ", -1))
              ]),
              _createElementVNode$q("p", _hoisted_22$6, [
                _cache[25] || (_cache[25] = _createTextVNode$l(" 预览：")),
                _createElementVNode$q("code", null, _toDisplayString$q(preview.value.renderedName || "（先在下面试跑一段文件名）"), 1)
              ]),
              _createVNode$o(_component_v_divider, { class: "my-4" }),
              _createElementVNode$q("div", _hoisted_23$6, [
                _cache[27] || (_cache[27] = _createTextVNode$l(" 单条文件名试跑 ")),
                _createVNode$o(_component_v_chip, {
                  size: "x-small",
                  color: "warning",
                  variant: "tonal",
                  class: "ms-2"
                }, {
                  default: _withCtx$n(() => _cache[26] || (_cache[26] = [
                    _createTextVNode$l("本地预览")
                  ])),
                  _: 1
                })
              ]),
              _cache[48] || (_cache[48] = _createElementVNode$q("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _createTextVNode$l(" 契约 §3.7 "),
                _createElementVNode$q("strong", null, "没有"),
                _createTextVNode$l("这条试跑端点，所以这里用前端复刻的规则当场算，"),
                _createElementVNode$q("strong", null, "不发任何请求"),
                _createTextVNode$l("； 真正落库的是后端 "),
                _createElementVNode$q("code", null, "parse_av_number()"),
                _createTextVNode$l("，两边不一致时以后端为准。 ")
              ], -1)),
              _createVNode$o(_component_v_text_field, {
                modelValue: sampleName.value,
                "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => sampleName.value = $event),
                label: "文件名（可带路径与扩展名）",
                placeholder: "例如：/media/9kg/avi/IPZZ-912-UC_4K.mp4",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                "hide-details": "",
                class: "mb-2"
              }, null, 8, ["modelValue"]),
              _createVNode$o(_component_v_alert, {
                type: preview.value.matched ? "success" : "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-2"
              }, {
                default: _withCtx$n(() => [
                  _createTextVNode$l(_toDisplayString$q(previewSummary.value), 1)
                ]),
                _: 1
              }, 8, ["type"]),
              preview.value.matched ? (_openBlock$r(), _createElementBlock$q("div", _hoisted_24$5, [
                _createElementVNode$q("div", _hoisted_25$5, [
                  _cache[28] || (_cache[28] = _createElementVNode$q("span", { class: "avh-preview__k" }, "display_number", -1)),
                  _createElementVNode$q("code", null, _toDisplayString$q(preview.value.displayNumber), 1)
                ]),
                _createElementVNode$q("div", _hoisted_26$5, [
                  _cache[29] || (_cache[29] = _createElementVNode$q("span", { class: "avh-preview__k" }, "norm_key", -1)),
                  _createElementVNode$q("code", null, _toDisplayString$q(preview.value.normKey), 1)
                ]),
                _createElementVNode$q("div", _hoisted_27$5, [
                  _cache[30] || (_cache[30] = _createElementVNode$q("span", { class: "avh-preview__k" }, "version_tags", -1)),
                  _createElementVNode$q("span", null, [
                    (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(preview.value.tags, (tag) => {
                      return _openBlock$r(), _createBlock$m(_component_v_chip, {
                        key: tag.label,
                        size: "x-small",
                        variant: "tonal",
                        class: "me-1"
                      }, {
                        default: _withCtx$n(() => [
                          _createTextVNode$l(_toDisplayString$q(tag.label), 1)
                        ]),
                        _: 2
                      }, 1024);
                    }), 128)),
                    !preview.value.tags.length ? (_openBlock$r(), _createElementBlock$q("span", _hoisted_28$5, "（无）")) : _createCommentVNode$l("", true)
                  ])
                ]),
                _createElementVNode$q("div", _hoisted_29$5, [
                  _cache[32] || (_cache[32] = _createElementVNode$q("span", { class: "avh-preview__k" }, "Emby Name", -1)),
                  _createElementVNode$q("span", null, [
                    _createElementVNode$q("code", null, _toDisplayString$q(preview.value.renderedName), 1),
                    _cache[31] || (_cache[31] = _createElementVNode$q("span", { class: "text-caption text-medium-emphasis ms-2" }, " （角标按契约 §3.6.1 直接接在番号后面，没有额外分隔符） ", -1))
                  ])
                ])
              ])) : _createCommentVNode$l("", true),
              _createVNode$o(_component_v_divider, { class: "my-4" }),
              _cache[49] || (_cache[49] = _createElementVNode$q("div", { class: "text-subtitle-2 mb-1" }, "演员 / 标签自定义映射", -1)),
              _cache[50] || (_cache[50] = _createElementVNode$q("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _createTextVNode$l(" 左查询、右编辑；保存走 "),
                _createElementVNode$q("code", null, "POST /namemap/set"),
                _createTextVNode$l("，"),
                _createElementVNode$q("strong", null, "当场写库"),
                _createTextVNode$l("（不等顶条「保存修改」）。 ")
              ], -1)),
              _createElementVNode$q("div", _hoisted_30$5, [
                _createVNode$o(_component_v_btn_toggle, {
                  "model-value": entity.value,
                  mandatory: "",
                  density: "comfortable",
                  variant: "outlined",
                  color: "primary",
                  "onUpdate:modelValue": _cache[9] || (_cache[9] = (value) => value && switchEntity(value))
                }, {
                  default: _withCtx$n(() => [
                    _createVNode$o(_component_v_btn, { value: "actor" }, {
                      default: _withCtx$n(() => _cache[33] || (_cache[33] = [
                        _createTextVNode$l("演员")
                      ])),
                      _: 1
                    }),
                    _createVNode$o(_component_v_btn, { value: "tag" }, {
                      default: _withCtx$n(() => _cache[34] || (_cache[34] = [
                        _createTextVNode$l("标签")
                      ])),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 8, ["model-value"]),
                _createVNode$o(_component_v_text_field, {
                  modelValue: q.value,
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => q.value = $event),
                  class: "avh-map-q",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  "single-line": "",
                  clearable: "",
                  "prepend-inner-icon": "mdi-magnify",
                  placeholder: entity.value === "actor" ? "查演员名（中文 / 日文 / 别名）" : "查标签名",
                  onKeydown: _withKeys$3(loadMap, ["enter"])
                }, null, 8, ["modelValue", "placeholder"]),
                _createVNode$o(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  loading: listLoading.value,
                  onClick: loadMap
                }, {
                  default: _withCtx$n(() => _cache[35] || (_cache[35] = [
                    _createTextVNode$l("查询")
                  ])),
                  _: 1
                }, 8, ["loading"])
              ]),
              _createElementVNode$q("div", _hoisted_31$5, [
                _createElementVNode$q("div", _hoisted_32$5, [
                  listError.value ? (_openBlock$r(), _createBlock$m(_component_v_alert, {
                    key: 0,
                    type: "warning",
                    variant: "tonal",
                    density: "compact",
                    class: "text-caption mb-2"
                  }, {
                    default: _withCtx$n(() => [
                      _createTextVNode$l(_toDisplayString$q(entityLabel.value) + "映射读取失败：" + _toDisplayString$q(listError.value), 1)
                    ]),
                    _: 1
                  })) : _createCommentVNode$l("", true),
                  rows.value.length ? (_openBlock$r(), _createElementBlock$q("div", _hoisted_33$5, [
                    (_openBlock$r(true), _createElementBlock$q(_Fragment$j, null, _renderList$h(rows.value, (row, index) => {
                      return _openBlock$r(), _createElementBlock$q("div", {
                        key: row.canonical_id || `${row.zh || ""}#${index}`,
                        class: _normalizeClass$e(["avh-map__item", { "avh-map__item--on": selected.value === row }]),
                        onClick: ($event) => pickRow(row)
                      }, [
                        entity.value === "actor" ? (_openBlock$r(), _createBlock$m(Thumb, {
                          key: 0,
                          class: "avh-map__avatar",
                          variant: "av",
                          src: String(row.avatar || ""),
                          alt: String(row.zh || row.jp || "头像"),
                          "plugin-id": _ctx.pluginId
                        }, null, 8, ["src", "alt", "plugin-id"])) : _createCommentVNode$l("", true),
                        _createElementVNode$q("div", _hoisted_35$4, [
                          _createElementVNode$q("div", _hoisted_36$4, _toDisplayString$q(row.zh || row.jp || row.canonical_id || "(无名)"), 1),
                          _createElementVNode$q("div", _hoisted_37$4, _toDisplayString$q(row.jp || ""), 1),
                          extrasOf(row) ? (_openBlock$r(), _createElementBlock$q("div", _hoisted_38$4, _toDisplayString$q(extrasOf(row)), 1)) : _createCommentVNode$l("", true)
                        ])
                      ], 10, _hoisted_34$5);
                    }), 128))
                  ])) : !listError.value ? (_openBlock$r(), _createElementBlock$q("div", _hoisted_39$4, _toDisplayString$q(listLoading.value ? "正在读取…" : "没有匹配的记录（后端还没有返回数据，或查询词没命中）"), 1)) : _createCommentVNode$l("", true)
                ]),
                _createElementVNode$q("div", _hoisted_40$4, [
                  _createVNode$o(_component_v_text_field, {
                    modelValue: draftName.value,
                    "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => draftName.value = $event),
                    label: "键 / 原名（name）",
                    hint: "写库的查找键：演员用规范 id 或原名，标签用站点标签名",
                    "persistent-hint": "",
                    variant: "outlined",
                    density: "comfortable",
                    class: "mb-2"
                  }, null, 8, ["modelValue"]),
                  _createVNode$o(_component_v_text_field, {
                    modelValue: draftZh.value,
                    "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => draftZh.value = $event),
                    label: entity.value === "actor" ? "中文名（zh）" : "标准简中（zh，留空 = 命中即剔除）",
                    variant: "outlined",
                    density: "comfortable",
                    class: _normalizeClass$e(entity.value === "actor" ? "mb-2" : "mb-1")
                  }, null, 8, ["modelValue", "label", "class"]),
                  entity.value === "actor" ? (_openBlock$r(), _createBlock$m(_component_v_text_field, {
                    key: 0,
                    modelValue: draftJp.value,
                    "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => draftJp.value = $event),
                    label: "日文原名（jp，可留空）",
                    variant: "outlined",
                    density: "comfortable",
                    class: "mb-3"
                  }, null, 8, ["modelValue"])) : (_openBlock$r(), _createElementBlock$q("p", _hoisted_41$3, _cache[36] || (_cache[36] = [
                    _createTextVNode$l(" 标签的 "),
                    _createElementVNode$q("code", null, "zh", -1),
                    _createTextVNode$l(" 留空 = 删除规则（后端 "),
                    _createElementVNode$q("code", null, "tag_lookup()", -1),
                    _createTextVNode$l(" 返回空串即剔除该标签）。 ")
                  ]))),
                  _createVNode$o(_component_v_btn, {
                    color: "primary",
                    variant: "flat",
                    size: "small",
                    "prepend-icon": "mdi-content-save",
                    loading: saving.value,
                    onClick: saveMapping
                  }, {
                    default: _withCtx$n(() => _cache[37] || (_cache[37] = [
                      _createTextVNode$l("保存这一条映射")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ])
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const ScrapeRulePanel = /* @__PURE__ */ _export_sfc(_sfc_main$r, [["__scopeId", "data-v-b04f6486"]]);

const {ref: ref$o} = await importShared('vue');

const NOTICES_SEEN_KEY = "avhnext.settings.noticesSeen";
const seenAt = ref$o(readSeen());
function readSeen() {
  try {
    return localStorage.getItem(NOTICES_SEEN_KEY) || "";
  } catch {
    return "";
  }
}
function saveSeen() {
  try {
    localStorage.setItem(NOTICES_SEEN_KEY, seenAt.value);
  } catch {
  }
}
function latestNoticeTime(notices, fallback = seenAt.value) {
  return (notices || []).reduce(
    (acc, item) => String(item?.time || "") > acc ? String(item?.time) : acc,
    fallback
  );
}
function countUnread(notices) {
  return (notices || []).filter((item) => String(item?.time || "") > seenAt.value).length;
}
function markNoticesSeen(notices) {
  const latest = latestNoticeTime(notices);
  if (latest === seenAt.value) return;
  seenAt.value = latest;
  saveSeen();
}

const {defineComponent:_defineComponent$q} = await importShared('vue');

const {resolveComponent:_resolveComponent$m,createVNode:_createVNode$n,createTextVNode:_createTextVNode$k,withCtx:_withCtx$m,toDisplayString:_toDisplayString$p,unref:_unref$8,openBlock:_openBlock$q,createBlock:_createBlock$l,createCommentVNode:_createCommentVNode$k,createElementVNode:_createElementVNode$p,renderList:_renderList$g,Fragment:_Fragment$i,createElementBlock:_createElementBlock$p} = await importShared('vue');

const _hoisted_1$o = { class: "avh-counts mb-3" };
const {computed: computed$j,watch: watch$b} = await importShared('vue');
const _sfc_main$q = /* @__PURE__ */ _defineComponent$q({
  __name: "NotifyPanel",
  props: {
    notices: {},
    loading: { type: Boolean },
    clearing: { type: Boolean }
  },
  emits: ["clear", "reload"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const total = computed$j(() => props.notices.length);
    const unread = computed$j(
      () => props.notices.filter((item) => String(item.time || "") > seenAt.value).length
    );
    watch$b(
      () => props.notices,
      () => markNoticesSeen(props.notices),
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$m("v-icon");
      const _component_v_card_title = _resolveComponent$m("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$m("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$m("v-card-item");
      const _component_v_chip = _resolveComponent$m("v-chip");
      const _component_v_list_item_title = _resolveComponent$m("v-list-item-title");
      const _component_v_list_item_subtitle = _resolveComponent$m("v-list-item-subtitle");
      const _component_v_list_item = _resolveComponent$m("v-list-item");
      const _component_v_list = _resolveComponent$m("v-list");
      const _component_v_alert = _resolveComponent$m("v-alert");
      const _component_v_card_text = _resolveComponent$m("v-card-text");
      const _component_v_btn = _resolveComponent$m("v-btn");
      const _component_v_spacer = _resolveComponent$m("v-spacer");
      const _component_v_card_actions = _resolveComponent$m("v-card-actions");
      const _component_v_card = _resolveComponent$m("v-card");
      return _openBlock$q(), _createBlock$l(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$m(() => [
          _createVNode$n(_component_v_card_item, null, {
            prepend: _withCtx$m(() => [
              _createVNode$n(_component_v_icon, {
                icon: "mdi-bell",
                color: "primary"
              })
            ]),
            default: _withCtx$m(() => [
              _createVNode$n(_component_v_card_title, null, {
                default: _withCtx$m(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$k("通知")
                ])),
                _: 1
              }),
              _createVNode$n(_component_v_card_subtitle, null, {
                default: _withCtx$m(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$k("渠道沿用 MoviePilot 原生通知 · 本插件不另建渠道")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$n(_component_v_card_text, null, {
            default: _withCtx$m(() => [
              _createElementVNode$p("div", _hoisted_1$o, [
                _createVNode$n(_component_v_chip, {
                  color: "primary",
                  variant: "tonal",
                  size: "small"
                }, {
                  default: _withCtx$m(() => [
                    _createTextVNode$k(" 未读 " + _toDisplayString$p(unread.value) + " / 共 " + _toDisplayString$p(total.value), 1)
                  ]),
                  _: 1
                }),
                _unref$8(seenAt) ? (_openBlock$q(), _createBlock$l(_component_v_chip, {
                  key: 0,
                  variant: "text",
                  size: "small",
                  class: "text-caption"
                }, {
                  default: _withCtx$m(() => [
                    _createTextVNode$k(" 已读到 " + _toDisplayString$p(_unref$8(seenAt)), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode$k("", true)
              ]),
              _cache[5] || (_cache[5] = _createElementVNode$p("p", { class: "text-caption text-medium-emphasis mb-2" }, " 通知由 MoviePilot 原生的通知渠道发出（在「设置 → 通知」里配置），这里看到的只是插件自己的收件箱。 打开本栏即算已读；这里的「未读」与数据台顶栏铃铛上的角标是同一个位点。 ", -1)),
              _ctx.notices.length ? (_openBlock$q(), _createBlock$l(_component_v_list, {
                key: 0,
                density: "compact",
                class: "avh-notices mb-2"
              }, {
                default: _withCtx$m(() => [
                  (_openBlock$q(true), _createElementBlock$p(_Fragment$i, null, _renderList$g(_ctx.notices.slice(0, 20), (item, index) => {
                    return _openBlock$q(), _createBlock$l(_component_v_list_item, { key: index }, {
                      prepend: _withCtx$m(() => [
                        _createVNode$n(_component_v_icon, {
                          icon: item.kind === "ok" ? "mdi-check-circle-outline" : item.kind === "warn" ? "mdi-alert-outline" : "mdi-robot-outline",
                          color: item.kind === "ok" ? "success" : item.kind === "warn" ? "warning" : "primary",
                          size: "small"
                        }, null, 8, ["icon", "color"])
                      ]),
                      default: _withCtx$m(() => [
                        _createVNode$n(_component_v_list_item_title, { class: "text-body-2" }, {
                          default: _withCtx$m(() => [
                            _createTextVNode$k(_toDisplayString$p(item.title || item.body || "（无标题）"), 1)
                          ]),
                          _: 2
                        }, 1024),
                        _createVNode$n(_component_v_list_item_subtitle, { class: "text-caption" }, {
                          default: _withCtx$m(() => [
                            _createTextVNode$k(_toDisplayString$p(item.type || "系统消息") + " · " + _toDisplayString$p(item.time || "—"), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024);
                  }), 128)),
                  _ctx.notices.length > 20 ? (_openBlock$q(), _createBlock$l(_component_v_list_item, { key: 0 }, {
                    default: _withCtx$m(() => [
                      _createVNode$n(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                        default: _withCtx$m(() => [
                          _createTextVNode$k(" 只显示最近 20 条，其余 " + _toDisplayString$p(_ctx.notices.length - 20) + " 条在数据台的铃铛里。 ", 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$k("", true)
                ]),
                _: 1
              })) : (_openBlock$q(), _createBlock$l(_component_v_alert, {
                key: 1,
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-0"
              }, {
                default: _withCtx$m(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$k(" 暂无通知。 ")
                ])),
                _: 1
              }))
            ]),
            _: 1
          }),
          _createVNode$n(_component_v_card_actions, null, {
            default: _withCtx$m(() => [
              _createVNode$n(_component_v_btn, {
                variant: "text",
                "prepend-icon": "mdi-refresh",
                loading: props.loading,
                onClick: _cache[0] || (_cache[0] = ($event) => emit("reload"))
              }, {
                default: _withCtx$m(() => _cache[6] || (_cache[6] = [
                  _createTextVNode$k("刷新")
                ])),
                _: 1
              }, 8, ["loading"]),
              _createVNode$n(_component_v_spacer),
              _createVNode$n(_component_v_btn, {
                color: "error",
                variant: "tonal",
                "prepend-icon": "mdi-bell-off-outline",
                disabled: !total.value,
                loading: props.clearing,
                onClick: _cache[1] || (_cache[1] = ($event) => emit("clear"))
              }, {
                default: _withCtx$m(() => _cache[7] || (_cache[7] = [
                  _createTextVNode$k("清空通知")
                ])),
                _: 1
              }, 8, ["disabled", "loading"])
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const NotifyPanel = /* @__PURE__ */ _export_sfc(_sfc_main$q, [["__scopeId", "data-v-fe8afc34"]]);

const {defineComponent:_defineComponent$p} = await importShared('vue');

const {resolveComponent:_resolveComponent$l,createVNode:_createVNode$m,createTextVNode:_createTextVNode$j,withCtx:_withCtx$l,Fragment:_Fragment$h,openBlock:_openBlock$p,createElementBlock:_createElementBlock$o,toDisplayString:_toDisplayString$o,createBlock:_createBlock$k} = await importShared('vue');

const {ref: ref$n} = await importShared('vue');

const _sfc_main$p = /* @__PURE__ */ _defineComponent$p({
  __name: "LibraryPanel",
  props: {
    config: {},
    validation: {}
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const showKey = ref$n(false);
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    function mode() {
      const host = (props.config.emby_host || "").trim();
      const key = (props.config.emby_apikey || "").trim();
      if (!host && !key) return "reuse";
      if (host && key) return "own";
      return "half";
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$l("v-icon");
      const _component_v_card_title = _resolveComponent$l("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$l("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$l("v-card-item");
      const _component_v_alert = _resolveComponent$l("v-alert");
      const _component_v_text_field = _resolveComponent$l("v-text-field");
      const _component_v_card_text = _resolveComponent$l("v-card-text");
      const _component_v_card = _resolveComponent$l("v-card");
      return _openBlock$p(), _createBlock$k(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$l(() => [
          _createVNode$m(_component_v_card_item, null, {
            prepend: _withCtx$l(() => [
              _createVNode$m(_component_v_icon, {
                icon: "mdi-server",
                color: "primary"
              })
            ]),
            default: _withCtx$l(() => [
              _createVNode$m(_component_v_card_title, null, {
                default: _withCtx$l(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$j("媒体库")
                ])),
                _: 1
              }),
              _createVNode$m(_component_v_card_subtitle, null, {
                default: _withCtx$l(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$j("Emby 地址与密钥 · 两栏都空 = 复用 MoviePilot 的媒体服务器")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$m(_component_v_card_text, null, {
            default: _withCtx$l(() => [
              _createVNode$m(_component_v_alert, {
                type: mode() === "half" ? "warning" : mode() === "own" ? "success" : "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-4"
              }, {
                default: _withCtx$l(() => [
                  mode() === "reuse" ? (_openBlock$p(), _createElementBlock$o(_Fragment$h, { key: 0 }, [
                    _createTextVNode$j(" 当前：复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby（两栏留空即是这个状态）。 ")
                  ], 64)) : mode() === "own" ? (_openBlock$p(), _createElementBlock$o(_Fragment$h, { key: 1 }, [
                    _createTextVNode$j(" 当前：使用下面填写的 Emby，不再走 MoviePilot 的媒体服务器配置。 ")
                  ], 64)) : (_openBlock$p(), _createElementBlock$o(_Fragment$h, { key: 2 }, [
                    _createTextVNode$j(_toDisplayString$o(props.validation || "Emby 地址与 API 密钥要一起填，否则会回落到 MoviePilot 的媒体服务器。"), 1)
                  ], 64))
                ]),
                _: 1
              }, 8, ["type"]),
              _createVNode$m(_component_v_text_field, {
                "model-value": props.config.emby_host,
                label: "Emby 地址",
                placeholder: "http://emby:8096",
                hint: "可留空；两栏都空时自动复用 MoviePilot 已配置的 Emby",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                class: "mb-4",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("emby_host", value ?? ""))
              }, null, 8, ["model-value"]),
              _createVNode$m(_component_v_text_field, {
                "model-value": props.config.emby_apikey,
                type: showKey.value ? "text" : "password",
                label: "Emby API 密钥",
                hint: "可留空；留空时自动复用 MoviePilot 已配置的 Emby",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                "append-inner-icon": showKey.value ? "mdi-eye-off" : "mdi-eye",
                "onClick:appendInner": _cache[1] || (_cache[1] = ($event) => showKey.value = !showKey.value),
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("emby_apikey", value ?? ""))
              }, null, 8, ["model-value", "type", "append-inner-icon"])
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const LibraryPanel = /* @__PURE__ */ _export_sfc(_sfc_main$p, [["__scopeId", "data-v-3801e593"]]);

const {defineComponent:_defineComponent$o} = await importShared('vue');

const {resolveComponent:_resolveComponent$k,createVNode:_createVNode$l,createTextVNode:_createTextVNode$i,withCtx:_withCtx$k,createElementVNode:_createElementVNode$o,toDisplayString:_toDisplayString$n,openBlock:_openBlock$o,createBlock:_createBlock$j,createCommentVNode:_createCommentVNode$j,createElementBlock:_createElementBlock$n} = await importShared('vue');

const _hoisted_1$n = { class: "avh-cache" };
const _hoisted_2$n = { class: "text-h6" };
const _hoisted_3$l = { class: "text-caption text-medium-emphasis" };
const _hoisted_4$i = { class: "avh-cache-actions" };
const _hoisted_5$h = { class: "text-body-2 font-weight-medium" };
const _hoisted_6$g = { class: "text-body-2" };
const _hoisted_7$f = { class: "text-body-2" };
const _hoisted_8$e = { class: "text-body-2" };
const _hoisted_9$d = { class: "text-caption text-medium-emphasis mt-3 mb-0" };
const _hoisted_10$d = { key: 0 };
const {computed: computed$i} = await importShared('vue');
const DASH$1 = "—";
const _sfc_main$o = /* @__PURE__ */ _defineComponent$o({
  __name: "RuntimePanel",
  props: {
    config: {},
    cacheText: {},
    cacheBytes: {},
    check: {},
    cleaning: { type: Boolean },
    loading: { type: Boolean }
  },
  emits: ["clean", "refresh", "patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const cacheLabel = computed$i(() => props.cacheText ? props.cacheText : DASH$1);
    const limitGb = computed$i(() => toCacheGb(props.config.cache_max_gb));
    const usageLabel = computed$i(() => {
      const limitText = `${limitGb.value} GB`;
      const bytes = props.cacheBytes;
      if (bytes === null || bytes === void 0 || !Number.isFinite(bytes)) {
        return `上限 ${limitText}`;
      }
      const percent = limitGb.value > 0 ? Math.round(bytes / (limitGb.value * 1024 ** 3) * 100) : 0;
      return `已用 ${props.cacheText || formatBytes(bytes)} / 上限 ${limitText}（${percent}%）`;
    });
    const limitHint = computed$i(() => {
      const raw = String(props.config.cache_max_gb ?? "").trim();
      const normalized = toCacheGb(raw);
      const base = `超过上限就按最旧淘汰（每天 4 点跑一次）。默认 ${CACHE_MAX_GB_FALLBACK}G 就够用：实测长期占用不到 0.3G；留空按默认值处理。`;
      if (!raw || Number.parseFloat(raw) === normalized) return base;
      return `${base} 当前输入按 ${normalized}G 生效（下限 ${CACHE_MAX_GB_MIN}G）。`;
    });
    const todayLabel = computed$i(() => {
      const info = props.check;
      if (!info || info.checkedToday === void 0) return DASH$1;
      const limit = info.maxPerDay === void 0 ? DASH$1 : info.maxPerDay;
      return `${info.checkedToday} / ${limit}`;
    });
    const lastCheckLabel = computed$i(() => formatCheckTime(props.check?.lastCheck, "last"));
    const nextCheckLabel = computed$i(() => formatCheckTime(props.check?.nextAt, "next"));
    const intervalLabel = computed$i(() => {
      const minutes = props.check?.minIntervalMin;
      return minutes === void 0 ? DASH$1 : `${minutes} 分钟`;
    });
    const checkMissing = computed$i(() => props.check === null);
    const blockedLabel = computed$i(() => {
      const info = props.check;
      if (!info) return "";
      if (info.allowed === false) return info.reason || "当前不可执行检查（受限流约束）";
      return "";
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$k("v-icon");
      const _component_v_card_title = _resolveComponent$k("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$k("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$k("v-card-item");
      const _component_v_btn = _resolveComponent$k("v-btn");
      const _component_v_text_field = _resolveComponent$k("v-text-field");
      const _component_v_divider = _resolveComponent$k("v-divider");
      const _component_v_list_item_title = _resolveComponent$k("v-list-item-title");
      const _component_v_list_item = _resolveComponent$k("v-list-item");
      const _component_v_list = _resolveComponent$k("v-list");
      const _component_v_alert = _resolveComponent$k("v-alert");
      const _component_v_card_text = _resolveComponent$k("v-card-text");
      const _component_v_card = _resolveComponent$k("v-card");
      return _openBlock$o(), _createBlock$j(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$k(() => [
          _createVNode$l(_component_v_card_item, null, {
            prepend: _withCtx$k(() => [
              _createVNode$l(_component_v_icon, {
                icon: "mdi-database-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$k(() => [
              _createVNode$l(_component_v_card_title, null, {
                default: _withCtx$k(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$i("运行与缓存")
                ])),
                _: 1
              }),
              _createVNode$l(_component_v_card_subtitle, null, {
                default: _withCtx$k(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$i("缓存上限与清理 · 限流参数只读")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$l(_component_v_card_text, null, {
            default: _withCtx$k(() => [
              _createElementVNode$o("div", _hoisted_1$n, [
                _createElementVNode$o("div", null, [
                  _cache[5] || (_cache[5] = _createElementVNode$o("div", { class: "text-caption text-medium-emphasis" }, "缓存占用", -1)),
                  _createElementVNode$o("div", _hoisted_2$n, _toDisplayString$n(cacheLabel.value), 1),
                  _createElementVNode$o("div", _hoisted_3$l, _toDisplayString$n(usageLabel.value), 1)
                ]),
                _createElementVNode$o("div", _hoisted_4$i, [
                  _createVNode$l(_component_v_btn, {
                    color: "warning",
                    variant: "tonal",
                    "prepend-icon": "mdi-broom",
                    loading: props.cleaning,
                    onClick: _cache[0] || (_cache[0] = ($event) => emit("clean"))
                  }, {
                    default: _withCtx$k(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$i("清理缓存")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode$l(_component_v_btn, {
                    variant: "text",
                    "prepend-icon": "mdi-refresh",
                    loading: props.loading,
                    class: "mt-2",
                    onClick: _cache[1] || (_cache[1] = ($event) => emit("refresh"))
                  }, {
                    default: _withCtx$k(() => _cache[7] || (_cache[7] = [
                      _createTextVNode$i("刷新")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              _createVNode$l(_component_v_text_field, {
                class: "mt-4",
                "model-value": props.config.cache_max_gb,
                label: "缓存上限（GB）",
                placeholder: "留空 = 1",
                type: "number",
                min: "0.1",
                step: "0.5",
                suffix: "GB",
                hint: limitHint.value,
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => emit("patch", { cache_max_gb: value ?? "" }))
              }, null, 8, ["model-value", "hint"]),
              _createVNode$l(_component_v_divider, { class: "my-4" }),
              _cache[14] || (_cache[14] = _createElementVNode$o("div", { class: "text-subtitle-2 mb-2" }, "订阅检查限流（只读）", -1)),
              _createVNode$l(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$k(() => [
                  _createVNode$l(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$k(() => [
                      _createElementVNode$o("span", _hoisted_5$h, _toDisplayString$n(todayLabel.value), 1)
                    ]),
                    default: _withCtx$k(() => [
                      _createVNode$l(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$k(() => _cache[8] || (_cache[8] = [
                          _createTextVNode$i("今天已检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$l(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$k(() => [
                      _createElementVNode$o("span", _hoisted_6$g, _toDisplayString$n(lastCheckLabel.value), 1)
                    ]),
                    default: _withCtx$k(() => [
                      _createVNode$l(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$k(() => _cache[9] || (_cache[9] = [
                          _createTextVNode$i("上次检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$l(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$k(() => [
                      _createElementVNode$o("span", _hoisted_7$f, _toDisplayString$n(nextCheckLabel.value), 1)
                    ]),
                    default: _withCtx$k(() => [
                      _createVNode$l(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$k(() => _cache[10] || (_cache[10] = [
                          _createTextVNode$i("下次可检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$l(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$k(() => [
                      _createElementVNode$o("span", _hoisted_8$e, _toDisplayString$n(intervalLabel.value), 1)
                    ]),
                    default: _withCtx$k(() => [
                      _createVNode$l(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$k(() => _cache[11] || (_cache[11] = [
                          _createTextVNode$i("间隔下限")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              blockedLabel.value ? (_openBlock$o(), _createBlock$j(_component_v_alert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mt-2"
              }, {
                default: _withCtx$k(() => [
                  _createTextVNode$i(_toDisplayString$n(blockedLabel.value), 1)
                ]),
                _: 1
              })) : _createCommentVNode$j("", true),
              _createElementVNode$o("p", _hoisted_9$d, [
                _cache[13] || (_cache[13] = _createTextVNode$i(" 限流参数按用户明确要求固定（每天 ≤6 次、间隔 ≥240 分钟），界面不提供放宽入口。 ")),
                checkMissing.value ? (_openBlock$o(), _createElementBlock$n("span", _hoisted_10$d, _cache[12] || (_cache[12] = [
                  _createTextVNode$i(" 当前后端还没返回 "),
                  _createElementVNode$o("code", null, "check", -1),
                  _createTextVNode$i(" 字段（本轮正在补），所以上面几行显示 "),
                  _createElementVNode$o("code", null, "—", -1),
                  _createTextVNode$i("；字段上线后自动显示。 ")
                ]))) : _createCommentVNode$j("", true)
              ])
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const RuntimePanel = /* @__PURE__ */ _export_sfc(_sfc_main$o, [["__scopeId", "data-v-0f556e47"]]);

const {defineComponent:_defineComponent$n} = await importShared('vue');

const {resolveComponent:_resolveComponent$j,createVNode:_createVNode$k,createTextVNode:_createTextVNode$h,withCtx:_withCtx$j,toDisplayString:_toDisplayString$m,createElementVNode:_createElementVNode$n,openBlock:_openBlock$n,createBlock:_createBlock$i,createCommentVNode:_createCommentVNode$i} = await importShared('vue');

const _hoisted_1$m = { class: "text-body-2 font-weight-medium" };
const _hoisted_2$m = { class: "text-body-2 font-weight-medium" };
const _hoisted_3$k = { class: "text-body-2" };
const DASH = "—";
const DATA_ROOT = "/avhelper/cache";
const JAVDB_BIN = "/avhelper/bin/javdb";
const _sfc_main$n = /* @__PURE__ */ _defineComponent$n({
  __name: "AboutPanel",
  props: {
    version: {},
    pluginId: {},
    sourcePluginId: {}
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$j("v-icon");
      const _component_v_card_title = _resolveComponent$j("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$j("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$j("v-card-item");
      const _component_v_list_item_title = _resolveComponent$j("v-list-item-title");
      const _component_v_list_item = _resolveComponent$j("v-list-item");
      const _component_v_list = _resolveComponent$j("v-list");
      const _component_v_divider = _resolveComponent$j("v-divider");
      const _component_v_card_text = _resolveComponent$j("v-card-text");
      const _component_v_card = _resolveComponent$j("v-card");
      return _openBlock$n(), _createBlock$i(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$j(() => [
          _createVNode$k(_component_v_card_item, null, {
            prepend: _withCtx$j(() => [
              _createVNode$k(_component_v_icon, {
                icon: "mdi-information-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$j(() => [
              _createVNode$k(_component_v_card_title, null, {
                default: _withCtx$j(() => _cache[0] || (_cache[0] = [
                  _createTextVNode$h("关于")
                ])),
                _: 1
              }),
              _createVNode$k(_component_v_card_subtitle, null, {
                default: _withCtx$j(() => _cache[1] || (_cache[1] = [
                  _createTextVNode$h("AVHelper · Vue 联邦渲染模式")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$k(_component_v_card_text, null, {
            default: _withCtx$j(() => [
              _createVNode$k(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$j(() => [
                  _createVNode$k(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$j(() => [
                      _createElementVNode$n("span", _hoisted_1$m, _toDisplayString$m(props.version || DASH), 1)
                    ]),
                    default: _withCtx$j(() => [
                      _createVNode$k(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$j(() => _cache[2] || (_cache[2] = [
                          _createTextVNode$h("版本号")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$k(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$j(() => [
                      _createElementVNode$n("span", _hoisted_2$m, _toDisplayString$m(props.pluginId || DASH), 1)
                    ]),
                    default: _withCtx$j(() => [
                      _createVNode$k(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$j(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$h("插件 ID")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  props.sourcePluginId ? (_openBlock$n(), _createBlock$i(_component_v_list_item, {
                    key: 0,
                    class: "px-0"
                  }, {
                    append: _withCtx$j(() => [
                      _createElementVNode$n("span", _hoisted_3$k, _toDisplayString$m(props.sourcePluginId), 1)
                    ]),
                    default: _withCtx$j(() => [
                      _createVNode$k(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$j(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$h("源插件 ID（分身）")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$i("", true),
                  _createVNode$k(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$j(() => [
                      _createElementVNode$n("span", { class: "text-body-2" }, [
                        _createElementVNode$n("code", null, _toDisplayString$m(DATA_ROOT))
                      ])
                    ]),
                    default: _withCtx$j(() => [
                      _createVNode$k(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$j(() => _cache[5] || (_cache[5] = [
                          _createTextVNode$h("数据根")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$k(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$j(() => [
                      _createElementVNode$n("span", { class: "text-body-2" }, [
                        _createElementVNode$n("code", null, _toDisplayString$m(JAVDB_BIN)),
                        _cache[7] || (_cache[7] = _createTextVNode$h("（与原版共用，只读）"))
                      ])
                    ]),
                    default: _withCtx$j(() => [
                      _createVNode$k(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$j(() => _cache[6] || (_cache[6] = [
                          _createTextVNode$h("javdb 二进制")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$k(_component_v_divider, { class: "my-3" }),
              _createElementVNode$n("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _cache[8] || (_cache[8] = _createTextVNode$h(" 数据根在插件数据卷上：SQLite 落在 ")),
                _createElementVNode$n("code", null, _toDisplayString$m(DATA_ROOT) + "/meta/avhelper.db"),
                _cache[9] || (_cache[9] = _createTextVNode$h("，图片与 JSON 缓存同根。 SQLite、图片与 JSON 缓存同根，全在插件数据卷上。 "))
              ]),
              _cache[10] || (_cache[10] = _createElementVNode$n("p", { class: "text-caption text-medium-emphasis mb-0" }, [
                _createTextVNode$h(" 界面上方是宿主的统一弹窗：标题栏、关闭按钮与 Toast 都由宿主提供，本插件复用 "),
                _createElementVNode$n("code", null, "moviepilot:toast"),
                _createTextVNode$h(" / "),
                _createElementVNode$n("code", null, "moviepilot:confirm"),
                _createTextVNode$h("，不自建。 版本号来自 "),
                _createElementVNode$n("code", null, "plugin/page/<id>"),
                _createTextVNode$h(" 的 "),
                _createElementVNode$n("code", null, "plugin_version"),
                _createTextVNode$h("，取不到显示 "),
                _createElementVNode$n("code", null, "—"),
                _createTextVNode$h("。 ")
              ], -1))
            ]),
            _: 1
          })
        ]),
        _: 1
      });
    };
  }
});

const AboutPanel = /* @__PURE__ */ _export_sfc(_sfc_main$n, [["__scopeId", "data-v-02ead8f0"]]);

const {ref: ref$m} = await importShared('vue');

function scoreLevel(score, pass) {
  if (!pass) return "lo";
  const value = Number(score);
  if (value >= 80) return "hi";
  if (value >= 55) return "mid";
  return "lo";
}
const FILL_LIMIT = 3;
const fillQueue = [];
const fillTried = /* @__PURE__ */ new Set();
let fillBusy = false;
const filledThumbs = ref$m({});
function queueThumb(api, number) {
  const num = String(number ?? "");
  if (!num || fillTried.has(num)) return;
  fillTried.add(num);
  fillQueue.push(num);
  void pumpThumbFill(api);
}
function queueMissingThumbs(api, items) {
  (items || []).filter((item) => item && item.number && !item.thumb).map((item) => item.number).slice(0, FILL_LIMIT).forEach((num) => queueThumb(api, num));
}
async function pumpThumbFill(api) {
  if (fillBusy) return;
  const num = fillQueue.shift();
  if (!num) return;
  fillBusy = true;
  try {
    const raw = await api.get("plugin/detail", { params: { number: num } });
    const payload = raw && typeof raw === "object" && "success" in raw ? raw.data ?? raw : raw;
    const thumb = payload?.movie?.thumb;
    if (typeof thumb === "string" && thumb) {
      filledThumbs.value = { ...filledThumbs.value, [num]: thumb };
    }
  } catch {
  } finally {
    fillBusy = false;
    void pumpThumbFill(api);
  }
}

const {defineComponent:_defineComponent$m} = await importShared('vue');

const {createVNode:_createVNode$j,toDisplayString:_toDisplayString$l,createElementVNode:_createElementVNode$m,openBlock:_openBlock$m,createElementBlock:_createElementBlock$m,createCommentVNode:_createCommentVNode$h,createTextVNode:_createTextVNode$g,resolveComponent:_resolveComponent$i,withCtx:_withCtx$i,Fragment:_Fragment$g,createBlock:_createBlock$h,renderList:_renderList$f,normalizeClass:_normalizeClass$d,unref:_unref$7} = await importShared('vue');

const _hoisted_1$l = { class: "avh-cand" };
const _hoisted_2$l = { class: "avh-cand__head" };
const _hoisted_3$j = { class: "avh-cand__no" };
const _hoisted_4$h = { class: "avh-cand__hint avh-cand__origin" };
const _hoisted_5$g = {
  key: 0,
  class: "avh-cand__hint"
};
const _hoisted_6$f = { class: "avh-cand__hint" };
const _hoisted_7$e = { class: "avh-cand__table" };
const _hoisted_8$d = { key: 0 };
const _hoisted_9$c = {
  key: 0,
  class: "avh-tag"
};
const _hoisted_10$c = { class: "avh-cand__marks" };
const _hoisted_11$b = {
  key: 1,
  class: "avh-cand__hint"
};
const _hoisted_12$b = ["title"];
const _hoisted_13$b = ["title"];
const _hoisted_14$b = { class: "avh-cand__act" };
const _hoisted_15$a = ["href"];
const _hoisted_16$9 = { colspan: "7" };
const _hoisted_17$9 = { class: "avh-cand__meta" };
const _hoisted_18$7 = ["title"];
const _hoisted_19$7 = {
  key: 0,
  class: "avh-cand__date"
};
const _hoisted_20$7 = { key: 0 };
const {computed: computed$h,onBeforeUnmount: onBeforeUnmount$9,ref: ref$l} = await importShared('vue');
const WATCHDOG_MS$1 = 18e4;
const _sfc_main$m = /* @__PURE__ */ _defineComponent$m({
  __name: "CandTable",
  props: {
    task: {},
    pluginId: { default: "" },
    cancelable: { type: Boolean, default: false },
    subscribeState: { default: "hidden" }
  },
  emits: ["download", "timeout", "cancel", "subscribe"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const pending = ref$l({});
    const cands = computed$h(() => Array.isArray(props.task.cands) ? props.task.cands : []);
    const passedCount = computed$h(() => cands.value.filter((item) => item.pass !== false).length);
    const taskId = computed$h(() => String(props.task.id ?? ""));
    const rows = computed$h(() => {
      const pt = cands.value.filter((item) => item.src !== "BT");
      const bt = cands.value.filter((item) => item.src === "BT");
      const out = pt.map((cand, index) => ({ kind: "cand", key: `pt-${index}`, cand }));
      if (bt.length) {
        out.push({ kind: "btnote", key: "bt-note", cand: {} });
        bt.forEach((cand, index) => out.push({ kind: "cand", key: `bt-${index}`, cand }));
      }
      return out;
    });
    const origin = computed$h(() => {
      const actor = props.task.actor ? String(props.task.actor) : "";
      if (props.task.source === "sub") return `来自订阅${actor ? `：${actor}` : ""}`;
      return `手动搜索${actor ? ` · 演员：${actor}` : ""}`;
    });
    function isPass(cand) {
      return cand.pass !== false;
    }
    function marks(cand) {
      const out = [];
      if (cand.cnsub) out.push({ text: "中字", cls: "avh-tag--on" });
      if (cand.uncensored) out.push({ text: "破解", cls: "avh-tag--uc" });
      if (cand.free) out.push({ text: "免费", cls: "avh-tag--free" });
      if (cand.pref) out.push({ text: "优先站", cls: "avh-tag--pref" });
      return out;
    }
    function rowClass(cand) {
      return [
        cand.picked ? "best" : "",
        isPass(cand) ? "" : "dead",
        cand.src === "BT" ? "bt" : "",
        subText(cand) ? "has-sub" : ""
      ].filter(Boolean);
    }
    function titleOf(cand) {
      return String(cand.title || "").trim();
    }
    function subText(cand) {
      return String(cand.sub || "").trim() || titleOf(cand);
    }
    function dateText(cand) {
      const match = /(\d{4}-\d{2}-\d{2})/.exec(String(cand.pubdate || ""));
      return match ? match[1] : "";
    }
    function metaTip(cand) {
      const parts = [subText(cand)];
      const title = titleOf(cand);
      if (title && title !== subText(cand)) parts.push(title);
      const date = dateText(cand);
      if (date) parts.push(date);
      return parts.filter(Boolean).join("\n");
    }
    function postUrl(cand) {
      const url = String(cand._page_url || "").trim();
      return /^https?:\/\//i.test(url) ? url : "";
    }
    function seedersText(cand) {
      if (cand.src === "BT") return "未知";
      return String(cand.seeders === null || cand.seeders === void 0 ? "—" : cand.seeders);
    }
    function scoreText(cand) {
      if (!isPass(cand)) return "淘汰";
      return String(cand.score === null || cand.score === void 0 ? "—" : cand.score);
    }
    function siteKey(cand) {
      return `${taskId.value}|${String(cand.site || "")}`;
    }
    const watchdogs = /* @__PURE__ */ new Map();
    function disarmWatchdog(key) {
      const timer = watchdogs.get(key);
      if (timer === void 0) return;
      window.clearTimeout(timer);
      watchdogs.delete(key);
    }
    function armWatchdog(key, payload) {
      disarmWatchdog(key);
      watchdogs.set(
        key,
        window.setTimeout(() => {
          watchdogs.delete(key);
          if (!pending.value[key]) return;
          const next = { ...pending.value };
          delete next[key];
          pending.value = next;
          emit("timeout", payload);
        }, WATCHDOG_MS$1)
      );
    }
    function onDownload(cand) {
      const key = siteKey(cand);
      if (pending.value[key]) return;
      pending.value = { ...pending.value, [key]: true };
      const payload = { taskId: taskId.value, site: String(cand.site || ""), force: !isPass(cand) };
      armWatchdog(key, { taskId: payload.taskId, site: payload.site });
      emit("download", payload);
    }
    const canceling = ref$l(false);
    function onCancel() {
      if (canceling.value || !taskId.value) return;
      canceling.value = true;
      emit("cancel", { taskId: taskId.value });
    }
    function clearCanceling(id) {
      if (id !== void 0 && String(id) !== taskId.value) return;
      canceling.value = false;
    }
    const pendingMark = computed$h(() => {
      const kind = String(props.task.pending || "");
      if (kind === "pt-only") {
        return { text: "PT/BT 待确认", color: "info", hint: "PT 没搜到，BT 兜底已关闭" };
      }
      if (kind === "none") {
        return { text: "所有源均未找到", color: "warning", hint: "PT 与 BT 都没有可用资源" };
      }
      return null;
    });
    const subscribing = ref$l(false);
    function onSubscribe() {
      if (subscribing.value || !taskId.value) return;
      subscribing.value = true;
      emit("subscribe", { taskId: taskId.value });
    }
    function clearSubscribing(id) {
      if (id !== void 0 && String(id) !== taskId.value) return;
      subscribing.value = false;
    }
    function clearRow(id, site) {
      const key = `${String(id ?? "")}|${String(site ?? "")}`;
      disarmWatchdog(key);
      if (!pending.value[key]) return;
      const next = { ...pending.value };
      delete next[key];
      pending.value = next;
    }
    function clearAllPending() {
      watchdogs.forEach((timer) => window.clearTimeout(timer));
      watchdogs.clear();
      pending.value = {};
    }
    __expose({ clearRow, clearAllPending, clearCanceling, clearSubscribing });
    onBeforeUnmount$9(() => {
      watchdogs.forEach((timer) => window.clearTimeout(timer));
      watchdogs.clear();
    });
    const poster = computed$h(() => {
      const own = String(props.task?.thumb || "");
      if (own) return own;
      return String(filledThumbs.value[String(props.task?.number || "")] || "");
    });
    return (_ctx, _cache) => {
      const _component_v_chip = _resolveComponent$i("v-chip");
      const _component_v_btn = _resolveComponent$i("v-btn");
      return _openBlock$m(), _createElementBlock$m("div", _hoisted_1$l, [
        _createElementVNode$m("div", _hoisted_2$l, [
          _createVNode$j(Thumb, {
            class: "avh-cand__poster",
            variant: "tposter",
            src: poster.value,
            alt: "无图",
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "plugin-id"]),
          _createElementVNode$m("div", null, [
            _createElementVNode$m("div", _hoisted_3$j, _toDisplayString$l(_ctx.task.number || ""), 1),
            _createElementVNode$m("div", _hoisted_4$h, _toDisplayString$l(origin.value) + " · 搜到 " + _toDisplayString$l(cands.value.length) + " · 合格 " + _toDisplayString$l(passedCount.value), 1)
          ]),
          _cache[1] || (_cache[1] = _createElementVNode$m("div", { class: "avh-cand__spacer" }, null, -1)),
          _ctx.task.auto && _ctx.task.source === "sub" ? (_openBlock$m(), _createElementBlock$m("span", _hoisted_5$g, " 订阅为自动下载，但无候选合格 ")) : _createCommentVNode$h("", true),
          pendingMark.value ? (_openBlock$m(), _createElementBlock$m(_Fragment$g, { key: 1 }, [
            _createVNode$j(_component_v_chip, {
              class: "avh-cand__mark",
              color: pendingMark.value.color,
              variant: "tonal",
              size: "small",
              label: ""
            }, {
              default: _withCtx$i(() => [
                _createTextVNode$g(_toDisplayString$l(pendingMark.value.text), 1)
              ]),
              _: 1
            }, 8, ["color"]),
            _createElementVNode$m("span", _hoisted_6$f, _toDisplayString$l(pendingMark.value.hint), 1)
          ], 64)) : _createCommentVNode$h("", true),
          _ctx.subscribeState !== "hidden" ? (_openBlock$m(), _createBlock$h(_component_v_btn, {
            key: 2,
            class: "avh-cand__subscribe",
            variant: "outlined",
            size: "small",
            disabled: _ctx.subscribeState === "done",
            loading: subscribing.value,
            title: "等这部片有资源时自动下载（订阅检查会盯它）",
            onClick: onSubscribe
          }, {
            default: _withCtx$i(() => [
              _createTextVNode$g(_toDisplayString$l(_ctx.subscribeState === "done" ? "已订阅" : "📌 订阅该影片"), 1)
            ]),
            _: 1
          }, 8, ["disabled", "loading"])) : _createCommentVNode$h("", true),
          _ctx.cancelable ? (_openBlock$m(), _createBlock$h(_component_v_btn, {
            key: 3,
            class: "avh-cand__cancel",
            variant: "outlined",
            size: "small",
            color: "error",
            loading: canceling.value,
            title: "不再等这部片：从待确认里移除（想找回就重新搜一次）",
            onClick: onCancel
          }, {
            default: _withCtx$i(() => _cache[0] || (_cache[0] = [
              _createTextVNode$g("取消任务")
            ])),
            _: 1
          }, 8, ["loading"])) : _createCommentVNode$h("", true)
        ]),
        _createElementVNode$m("table", _hoisted_7$e, [
          _cache[6] || (_cache[6] = _createElementVNode$m("colgroup", null, [
            _createElementVNode$m("col", { class: "avh-cand__col-site" }),
            _createElementVNode$m("col", { class: "avh-cand__col-mark" }),
            _createElementVNode$m("col", { class: "avh-cand__col-spec" }),
            _createElementVNode$m("col", { class: "avh-cand__col-size" }),
            _createElementVNode$m("col", { class: "avh-cand__col-seed" }),
            _createElementVNode$m("col", { class: "avh-cand__col-score" }),
            _createElementVNode$m("col", { class: "avh-cand__col-act" })
          ], -1)),
          _cache[7] || (_cache[7] = _createElementVNode$m("thead", null, [
            _createElementVNode$m("tr", null, [
              _createElementVNode$m("th", null, "站点"),
              _createElementVNode$m("th", null, "标记"),
              _createElementVNode$m("th", null, "规格"),
              _createElementVNode$m("th", null, "大小"),
              _createElementVNode$m("th", null, "做种"),
              _createElementVNode$m("th", null, "匹配分"),
              _createElementVNode$m("th", { class: "avh-cand__act" }, "操作")
            ])
          ], -1)),
          _createElementVNode$m("tbody", null, [
            (_openBlock$m(true), _createElementBlock$m(_Fragment$g, null, _renderList$f(rows.value, (row) => {
              return _openBlock$m(), _createElementBlock$m(_Fragment$g, {
                key: row.key
              }, [
                row.kind === "btnote" ? (_openBlock$m(), _createElementBlock$m("tr", _hoisted_8$d, _cache[2] || (_cache[2] = [
                  _createElementVNode$m("td", {
                    colspan: "7",
                    class: "avh-cand__hint avh-cand__btnote"
                  }, " — PT 没有合格候选，以下为 BT 磁力兜底 — ", -1)
                ]))) : (_openBlock$m(), _createElementBlock$m(_Fragment$g, { key: 1 }, [
                  _createElementVNode$m("tr", {
                    class: _normalizeClass$d(rowClass(row.cand))
                  }, [
                    _createElementVNode$m("td", null, [
                      row.cand.src === "BT" ? (_openBlock$m(), _createElementBlock$m("span", _hoisted_9$c, "BT")) : _createCommentVNode$h("", true),
                      _createTextVNode$g(" " + _toDisplayString$l(row.cand.site || ""), 1)
                    ]),
                    _createElementVNode$m("td", _hoisted_10$c, [
                      marks(row.cand).length ? (_openBlock$m(true), _createElementBlock$m(_Fragment$g, { key: 0 }, _renderList$f(marks(row.cand), (mark) => {
                        return _openBlock$m(), _createElementBlock$m("span", {
                          key: mark.text,
                          class: _normalizeClass$d(["avh-tag", mark.cls])
                        }, _toDisplayString$l(mark.text), 3);
                      }), 128)) : (_openBlock$m(), _createElementBlock$m("span", _hoisted_11$b, "—"))
                    ]),
                    _createElementVNode$m("td", {
                      class: "avh-cand__spec",
                      title: row.cand.spec || ""
                    }, _toDisplayString$l(row.cand.spec || ""), 9, _hoisted_12$b),
                    _createElementVNode$m("td", null, _toDisplayString$l(row.cand.size || ""), 1),
                    _createElementVNode$m("td", null, _toDisplayString$l(seedersText(row.cand)), 1),
                    _createElementVNode$m("td", {
                      title: row.cand.breakdown || ""
                    }, [
                      _createElementVNode$m("span", {
                        class: _normalizeClass$d(["avh-score", `avh-score--${_unref$7(scoreLevel)(row.cand.score, isPass(row.cand))}`])
                      }, _toDisplayString$l(scoreText(row.cand)), 3)
                    ], 8, _hoisted_13$b),
                    _createElementVNode$m("td", _hoisted_14$b, [
                      postUrl(row.cand) ? (_openBlock$m(), _createElementBlock$m("a", {
                        key: 0,
                        class: "avh-cand__post",
                        href: postUrl(row.cand),
                        target: "_blank",
                        rel: "noopener noreferrer",
                        title: "打开发布页：发布者、简介、截图等"
                      }, "原帖", 8, _hoisted_15$a)) : _createCommentVNode$h("", true),
                      isPass(row.cand) ? (_openBlock$m(), _createBlock$h(_component_v_btn, {
                        key: 1,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$i(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$g("下载")
                        ])),
                        _: 2
                      }, 1032, ["loading", "onClick"])) : (_openBlock$m(), _createBlock$h(_component_v_btn, {
                        key: 2,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        title: row.cand.breakdown || "",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$i(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$g("仍要下载")
                        ])),
                        _: 2
                      }, 1032, ["title", "loading", "onClick"]))
                    ])
                  ], 2),
                  subText(row.cand) ? (_openBlock$m(), _createElementBlock$m("tr", {
                    key: 0,
                    class: _normalizeClass$d(["avh-cand__sub", ...rowClass(row.cand)])
                  }, [
                    _createElementVNode$m("td", _hoisted_16$9, [
                      _createElementVNode$m("div", _hoisted_17$9, [
                        _createElementVNode$m("span", {
                          class: "avh-cand__ttl",
                          title: metaTip(row.cand)
                        }, _toDisplayString$l(subText(row.cand)), 9, _hoisted_18$7),
                        dateText(row.cand) ? (_openBlock$m(), _createElementBlock$m("span", _hoisted_19$7, _toDisplayString$l(dateText(row.cand)), 1)) : _createCommentVNode$h("", true)
                      ])
                    ])
                  ], 2)) : _createCommentVNode$h("", true)
                ], 64))
              ], 64);
            }), 128)),
            !cands.value.length ? (_openBlock$m(), _createElementBlock$m("tr", _hoisted_20$7, _cache[5] || (_cache[5] = [
              _createElementVNode$m("td", {
                colspan: "7",
                class: "avh-cand__hint avh-cand__empty"
              }, "没有搜到任何候选", -1)
            ]))) : _createCommentVNode$h("", true)
          ])
        ])
      ]);
    };
  }
});

const CandTable = /* @__PURE__ */ _export_sfc(_sfc_main$m, [["__scopeId", "data-v-19382d3f"]]);

const {defineComponent:_defineComponent$l} = await importShared('vue');

const {createElementVNode:_createElementVNode$l,toDisplayString:_toDisplayString$k,openBlock:_openBlock$l,createElementBlock:_createElementBlock$l,createCommentVNode:_createCommentVNode$g,renderSlot:_renderSlot} = await importShared('vue');

const _hoisted_1$k = { class: "avh-empty" };
const _hoisted_2$k = ["innerHTML"];
const _hoisted_3$i = {
  key: 0,
  class: "avh-empty__hint"
};
const _hoisted_4$g = {
  key: 1,
  class: "avh-empty__slot"
};
const _sfc_main$l = /* @__PURE__ */ _defineComponent$l({
  __name: "EmptyState",
  props: {
    text: { default: "" },
    hint: { default: "" }
  },
  setup(__props) {
    return (_ctx, _cache) => {
      return _openBlock$l(), _createElementBlock$l("div", _hoisted_1$k, [
        _createElementVNode$l("div", {
          class: "avh-empty__text",
          innerHTML: _ctx.text
        }, null, 8, _hoisted_2$k),
        _ctx.hint ? (_openBlock$l(), _createElementBlock$l("div", _hoisted_3$i, _toDisplayString$k(_ctx.hint), 1)) : _createCommentVNode$g("", true),
        _ctx.$slots.default ? (_openBlock$l(), _createElementBlock$l("div", _hoisted_4$g, [
          _renderSlot(_ctx.$slots, "default", {}, void 0, true)
        ])) : _createCommentVNode$g("", true)
      ]);
    };
  }
});

const EmptyState = /* @__PURE__ */ _export_sfc(_sfc_main$l, [["__scopeId", "data-v-d928276a"]]);

const {defineComponent:_defineComponent$k} = await importShared('vue');

const {toDisplayString:_toDisplayString$j,createElementVNode:_createElementVNode$k,createTextVNode:_createTextVNode$f,resolveComponent:_resolveComponent$h,withCtx:_withCtx$h,createVNode:_createVNode$i,openBlock:_openBlock$k,createElementBlock:_createElementBlock$k,createCommentVNode:_createCommentVNode$f} = await importShared('vue');

const _hoisted_1$j = {
  class: "avh-errbox",
  role: "alert"
};
const _hoisted_2$j = { class: "avh-errbox__msg" };
const _hoisted_3$h = {
  key: 0,
  class: "avh-errbox__act"
};
const _sfc_main$k = /* @__PURE__ */ _defineComponent$k({
  __name: "ErrorState",
  props: {
    message: { default: "" },
    retryable: { type: Boolean, default: true },
    retryText: { default: "重试" },
    retrying: { type: Boolean, default: false }
  },
  emits: ["retry"],
  setup(__props, { emit: __emit }) {
    const emit = __emit;
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$h("v-btn");
      return _openBlock$k(), _createElementBlock$k("div", _hoisted_1$j, [
        _createElementVNode$k("div", _hoisted_2$j, "⚠️ " + _toDisplayString$j(_ctx.message || "抓取失败，请稍后重试"), 1),
        _ctx.retryable ? (_openBlock$k(), _createElementBlock$k("div", _hoisted_3$h, [
          _createVNode$i(_component_v_btn, {
            color: "primary",
            variant: "flat",
            size: "small",
            loading: _ctx.retrying,
            onClick: _cache[0] || (_cache[0] = ($event) => emit("retry"))
          }, {
            default: _withCtx$h(() => [
              _createTextVNode$f(_toDisplayString$j(_ctx.retryText), 1)
            ]),
            _: 1
          }, 8, ["loading"])
        ])) : _createCommentVNode$f("", true)
      ]);
    };
  }
});

const ErrorState = /* @__PURE__ */ _export_sfc(_sfc_main$k, [["__scopeId", "data-v-8f8a571b"]]);

const {ref: ref$k} = await importShared('vue');

const BOTTOM_TOAST_MS = 4e3;
const BOTTOM_TOAST_STAGGER_MS = 320;
const bottomToasts = ref$k([]);
let seq = 0;
const timers = /* @__PURE__ */ new Map();
function dismissBottomToast(id) {
  const timer = timers.get(id);
  if (timer !== void 0) {
    window.clearTimeout(timer);
    timers.delete(id);
  }
  bottomToasts.value = bottomToasts.value.filter((item) => item.id !== id);
}
function pushBottomToast(level, text, timeout = BOTTOM_TOAST_MS) {
  const clean = String(text ?? "").trim();
  if (!clean) return 0;
  seq += 1;
  const id = seq;
  bottomToasts.value = [...bottomToasts.value, { id, level, text: clean }].slice(-4);
  if (timeout > 0) {
    timers.set(id, window.setTimeout(() => dismissBottomToast(id), timeout));
  }
  return id;
}
function normalizeLevel(raw) {
  const level = String(raw ?? "info");
  if (level === "success" || level === "warning" || level === "error") return level;
  return "info";
}
function playBottomToasts(raw, timeout = BOTTOM_TOAST_MS) {
  if (!Array.isArray(raw)) return;
  raw.forEach((item, index) => {
    const record = item || {};
    const level = normalizeLevel(record.level);
    const text = String(record.text ?? "");
    if (index === 0) {
      pushBottomToast(level, text, timeout);
      return;
    }
    window.setTimeout(
      () => pushBottomToast(level, text, timeout),
      index * BOTTOM_TOAST_STAGGER_MS
    );
  });
}

const KEY = "avhnext.pendingSettingsSection";
function requestSettingsSection(key) {
  try {
    window.localStorage.setItem(KEY, String(key || ""));
  } catch {
  }
}
function takePendingSettingsSection() {
  try {
    const value = window.localStorage.getItem(KEY) || "";
    if (value) window.localStorage.removeItem(KEY);
    return value;
  } catch {
    return "";
  }
}

const {defineComponent:_defineComponent$j} = await importShared('vue');

const {resolveComponent:_resolveComponent$g,withKeys:_withKeys$2,createVNode:_createVNode$h,toDisplayString:_toDisplayString$i,createTextVNode:_createTextVNode$e,withCtx:_withCtx$g,createElementVNode:_createElementVNode$j,openBlock:_openBlock$j,createBlock:_createBlock$g,createElementBlock:_createElementBlock$j} = await importShared('vue');

const _hoisted_1$i = { class: "avh-sitesearch" };
const _hoisted_2$i = { class: "avh-sitesearch__toolbar" };
const _hoisted_3$g = { class: "avh-sitesearch__hint" };
const _hoisted_4$f = { class: "avh-sitesearch__range" };
const _hoisted_5$f = ["title"];
const {computed: computed$g,nextTick: nextTick$5,ref: ref$j,watch: watch$a} = await importShared('vue');
const _sfc_main$j = /* @__PURE__ */ _defineComponent$j({
  __name: "SiteSearchView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["switch", "refreshSide"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const candTableRef = ref$j(null);
    const keyword = ref$j("");
    const searching = ref$j(false);
    const searchedAt = ref$j("");
    const task = ref$j(null);
    const errorText = ref$j("");
    const retrying = ref$j(false);
    const siteNames = computed$g(
      () => props.store.sites.value.map((item) => String(item?.name || "")).filter(Boolean)
    );
    const picked = computed$g(() => {
      const names = siteNames.value;
      return (props.store.rule.value.sites || []).map(String).filter((name) => names.indexOf(name) >= 0);
    });
    function labelOf(name) {
      const hit = props.store.sites.value.filter((item) => item.name === name)[0];
      return String(hit?.adapterLabel || "");
    }
    const scopeText = computed$g(() => {
      if (!picked.value.length) return "全部站点";
      return picked.value.map((name) => {
        const label = labelOf(name);
        return label ? `${name}（${label}）` : name;
      }).join("、");
    });
    const cands = computed$g(() => Array.isArray(task.value?.cands) ? task.value?.cands || [] : []);
    const hasResult = computed$g(() => !!task.value && cands.value.length > 0);
    const searchLabel = computed$g(() => searching.value ? "搜索中…" : "搜索站点");
    watch$a(task, async () => {
      candTableRef.value?.clearAllPending();
      await nextTick$5();
      candTableRef.value?.clearAllPending();
    });
    function clearPending() {
      candTableRef.value?.clearAllPending();
      void nextTick$5(() => candTableRef.value?.clearAllPending());
    }
    async function doSearch() {
      const kw = keyword.value.trim();
      if (!kw) {
        t.warning("先输入番号或关键词");
        return;
      }
      if (searching.value) return;
      searching.value = true;
      errorText.value = "";
      try {
        const sites = picked.value.slice();
        const res = await props.store.searchKeyword(kw, sites);
        if (!res.ok) {
          errorText.value = res.message || "请稍后重试";
          t.warning(res.message || "搜索失败，请稍后重试");
          return;
        }
        const result = res.data || null;
        task.value = result;
        searchedAt.value = nowStr();
        if (result && result.id !== void 0 && result.id !== null) {
          const next = props.store.tasks.value.filter((item) => String(item.id) !== String(result.id));
          props.store.tasks.value = [result, ...next];
        }
        const count = Array.isArray(result?.cands) ? (result?.cands || []).length : 0;
        if (count) {
          t.success(`搜到 ${count} 个候选`);
          t.info(`${kw} · 选一个点「下载」`);
        } else {
          t.warning("没有候选");
          t.info(result && result.reason || "换个关键词或站点再试");
        }
        if (result?.number && props.api) queueThumb(props.api, result.number);
        void props.store.refreshTasks(false);
        emit("refreshSide");
      } finally {
        searching.value = false;
        clearPending();
      }
    }
    async function retry() {
      retrying.value = true;
      try {
        await doSearch();
      } finally {
        retrying.value = false;
      }
    }
    async function onDownload(payload) {
      const res = await props.store.startDownload(payload.taskId, payload.site, payload.force);
      if (res.kind === "busy") return;
      const site = String(payload.site || "").trim();
      clearRow(payload.taskId, payload.site);
      if (!res.ok) {
        pushBottomToast("warning", `${site ? site + " · " : ""}下载失败：${res.message || "请稍后重试"}`);
        return;
      }
      pushBottomToast("success", `已提交下载：${site ? site + " · " : ""}进度见「下载」页`);
      void props.store.refreshTasks(false);
    }
    function clearRow(taskId, site) {
      candTableRef.value?.clearRow(taskId, site);
    }
    function changeScope() {
      t.info("搜索范围在「设置台 → 搜索站点」栏里改，保存后本页立即生效");
      requestSettingsSection("sites");
      emit("switch");
    }
    function onScopeClick() {
      t.info("搜索范围在「设置台 → 搜索站点」栏里改");
    }
    return (_ctx, _cache) => {
      const _component_v_text_field = _resolveComponent$g("v-text-field");
      const _component_v_btn = _resolveComponent$g("v-btn");
      return _openBlock$j(), _createElementBlock$j("div", _hoisted_1$i, [
        _createElementVNode$j("div", _hoisted_2$i, [
          _createVNode$h(_component_v_text_field, {
            modelValue: keyword.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => keyword.value = $event),
            class: "avh-sitesearch__input",
            placeholder: "番号或关键词（如 MIDV-946）…",
            autocomplete: "off",
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            disabled: searching.value,
            onKeydown: _withKeys$2(doSearch, ["enter"])
          }, null, 8, ["modelValue", "disabled"]),
          _createVNode$h(_component_v_btn, {
            color: "primary",
            variant: "flat",
            loading: searching.value,
            disabled: searching.value,
            "prepend-icon": "mdi-magnify",
            onClick: doSearch
          }, {
            default: _withCtx$g(() => [
              _createTextVNode$e(_toDisplayString$i(searchLabel.value), 1)
            ]),
            _: 1
          }, 8, ["loading", "disabled"]),
          _cache[1] || (_cache[1] = _createElementVNode$j("div", { class: "avh-sitesearch__spacer" }, null, -1)),
          _createElementVNode$j("span", _hoisted_3$g, _toDisplayString$i(searchedAt.value ? `上次搜索 ${searchedAt.value}` : "命中即停 · 站点间隔 3-8 秒"), 1)
        ]),
        _createElementVNode$j("div", _hoisted_4$f, [
          _cache[3] || (_cache[3] = _createElementVNode$j("div", { class: "avh-sitesearch__label" }, "搜索范围", -1)),
          _createElementVNode$j("div", {
            class: "avh-sitesearch__scope",
            title: scopeText.value,
            onClick: onScopeClick
          }, _toDisplayString$i(scopeText.value), 9, _hoisted_5$f),
          _createVNode$h(_component_v_btn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-tune",
            onClick: changeScope
          }, {
            default: _withCtx$g(() => _cache[2] || (_cache[2] = [
              _createTextVNode$e("改范围")
            ])),
            _: 1
          })
        ]),
        errorText.value ? (_openBlock$j(), _createBlock$g(ErrorState, {
          key: 0,
          message: `站点搜索失败：${errorText.value}`,
          retrying: retrying.value,
          onRetry: retry
        }, null, 8, ["message", "retrying"])) : hasResult.value && task.value ? (_openBlock$j(), _createBlock$g(CandTable, {
          key: 1,
          ref_key: "candTableRef",
          ref: candTableRef,
          task: task.value,
          "plugin-id": _ctx.pluginId,
          onDownload
        }, null, 8, ["task", "plugin-id"])) : (_openBlock$j(), _createBlock$g(EmptyState, {
          key: 2,
          text: "输入番号或关键词后点「搜索站点」"
        }))
      ]);
    };
  }
});

const SiteSearchView = /* @__PURE__ */ _export_sfc(_sfc_main$j, [["__scopeId", "data-v-1636ca0e"]]);

const {computed: computed$f,nextTick: nextTick$4,onBeforeUnmount: onBeforeUnmount$8,onMounted: onMounted$9,ref: ref$i,toValue,watch: watch$9} = await importShared('vue');

const PAGE_SIZE = 60;
const NEAR_BOTTOM = 200;
function usePagedList(source, options = {}) {
  const pageSize = Math.max(1, Math.floor(Number(options.pageSize) || PAGE_SIZE));
  const gapValue = Number(options.gap);
  const gap = Number.isFinite(gapValue) && gapValue > 0 ? gapValue : NEAR_BOTTOM;
  const all = computed$f(() => {
    const value = toValue(source);
    return Array.isArray(value) ? value : [];
  });
  const shown = ref$i(pageSize);
  const total = computed$f(() => all.value.length);
  const rows = computed$f(() => all.value.slice(0, shown.value));
  const hasMore = computed$f(() => shown.value < total.value);
  function loadMore() {
    if (!hasMore.value) return false;
    shown.value = Math.min(total.value, shown.value + pageSize);
    return true;
  }
  function loadAll() {
    shown.value = total.value;
  }
  function reset() {
    shown.value = pageSize;
  }
  watch$9(all, () => reset());
  const sentinel = ref$i(null);
  let scroller = null;
  let frame = 0;
  function findScroller(start) {
    let el = start;
    while (el && el !== document.body && el !== document.documentElement) {
      const overflowY = window.getComputedStyle(el).overflowY;
      if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") return el;
      el = el.parentElement;
    }
    return null;
  }
  function activeScroller() {
    const winTop = window.scrollY || document.documentElement.scrollTop || 0;
    const inner = scroller;
    if (inner && inner.scrollHeight - inner.clientHeight > 1) {
      if (inner.scrollTop > 0 || winTop <= 0) return inner;
    }
    return null;
  }
  function gapToBottom() {
    const el = sentinel.value;
    if (!el) return Number.POSITIVE_INFINITY;
    const rect = el.getBoundingClientRect();
    if (!rect.height && !rect.width) return Number.POSITIVE_INFINITY;
    const inner = activeScroller();
    const visibleBottom = inner ? Math.min(inner.getBoundingClientRect().bottom, window.innerHeight) : window.innerHeight;
    return rect.bottom - visibleBottom;
  }
  function pump() {
    if (!hasMore.value) return;
    if (gapToBottom() > gap) return;
    if (!loadMore()) return;
    void nextTick$4(pump);
  }
  function onScroll() {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      pump();
    });
  }
  function onResize() {
    detach();
    attach();
  }
  function detach() {
    if (scroller) scroller.removeEventListener("scroll", onScroll);
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", onResize);
  }
  function attach() {
    detach();
    scroller = findScroller(sentinel.value ? sentinel.value.parentElement : null);
    if (scroller) scroller.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize, { passive: true });
    void nextTick$4(pump);
  }
  watch$9(sentinel, () => attach(), { flush: "post" });
  onMounted$9(() => {
    if (sentinel.value) attach();
  });
  onBeforeUnmount$8(() => {
    detach();
    if (frame) {
      window.cancelAnimationFrame(frame);
      frame = 0;
    }
  });
  return {
    rows,
    shown,
    total,
    hasMore,
    pageSize,
    loadMore,
    loadAll,
    reset,
    sentinel
  };
}

function asItems(value) {
  return Array.isArray(value) ? value : null;
}
function asCounts(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value;
  const keys = ["total", "inLibrary", "missing"];
  if (!keys.some((k) => typeof raw[k] === "number")) return null;
  const counts = {};
  keys.forEach((k) => {
    if (typeof raw[k] === "number") counts[k] = raw[k];
  });
  return counts;
}
function parseDownloadList(response) {
  const raw = response;
  let items = asItems(raw);
  let counts = asCounts(raw?.counts);
  if (!items) items = asItems(raw?.items);
  if (!items) items = asItems(raw?.data);
  if (!items) items = asItems(raw?.data?.items);
  if (!counts) counts = asCounts(raw?.data?.counts);
  return { items: items || [], counts };
}
function normKey(value) {
  const raw = String(value ?? "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  if (!raw) return "";
  return raw.replace(/0*(\d+)/g, (_, digits) => String(parseInt(digits, 10)));
}
function inLibrary(item) {
  const lib = item?.lib;
  return !!lib && typeof lib === "object";
}
function recordKey(item, index) {
  const explicit = String(item?.key || "").trim();
  if (explicit) return explicit;
  const number = normKey(item?.number);
  if (number) return number;
  return `#${index}`;
}
function displayNumber(item) {
  const number = String(item?.number || "").trim();
  if (number) return number;
  return String(item?.key || "").trim();
}
function completedText(item) {
  const raw = String(item?.completedAt || item?.createdAt || "").trim();
  return raw || "—";
}
function sizeLabel(item) {
  const text = String(item?.sizeText || "").trim();
  return text || "—";
}
function filterRecords(items, query, onlyMissing) {
  const text = String(query || "").trim().toLowerCase();
  const key = normKey(text);
  return (items || []).filter((item) => {
    if (!item) return false;
    if (onlyMissing && inLibrary(item)) return false;
    if (!text) return true;
    const number = normKey(item.number || item.key);
    const title = String(item.title || "").toLowerCase();
    const actor = String(item.actor || "").toLowerCase();
    return !!key && number.includes(key) || title.includes(text) || actor.includes(text);
  });
}

const {defineComponent:_defineComponent$i} = await importShared('vue');

const {createElementVNode:_createElementVNode$i,resolveComponent:_resolveComponent$f,createVNode:_createVNode$g,createTextVNode:_createTextVNode$d,withCtx:_withCtx$f,toDisplayString:_toDisplayString$h,openBlock:_openBlock$i,createBlock:_createBlock$f,createCommentVNode:_createCommentVNode$e,createElementBlock:_createElementBlock$i,unref:_unref$6,renderList:_renderList$e,Fragment:_Fragment$f} = await importShared('vue');

const _hoisted_1$h = { class: "avh-history" };
const _hoisted_2$h = { class: "avh-history__toolbar" };
const _hoisted_3$f = {
  key: 0,
  class: "avh-history__stats"
};
const _hoisted_4$e = { class: "avh-history__hint" };
const _hoisted_5$e = {
  key: 1,
  class: "avh-history__tablewrap",
  "aria-busy": "true"
};
const _hoisted_6$e = { class: "avh-history__table" };
const _hoisted_7$d = {
  key: 3,
  class: "avh-history__tablewrap"
};
const _hoisted_8$c = { class: "avh-history__table" };
const _hoisted_9$b = { class: "avh-history__pic" };
const _hoisted_10$b = { class: "avh-history__no" };
const _hoisted_11$a = ["title"];
const _hoisted_12$a = ["title"];
const _hoisted_13$a = ["title"];
const _hoisted_14$a = ["title"];
const _hoisted_15$9 = ["href"];
const _hoisted_16$8 = { class: "avh-history__act" };
const _hoisted_17$8 = { class: "avh-history__hint" };
const {computed: computed$e,onMounted: onMounted$8,ref: ref$h} = await importShared('vue');
const ENDPOINT$1 = "plugin/downloads";
const SKELETON_ROWS = 6;
const HISTORY_PAGE_SIZE = 60;
const IMPORT_GRACE_H = 48;
const _sfc_main$i = /* @__PURE__ */ _defineComponent$i({
  __name: "HistoryView",
  props: {
    api: { default: null },
    pluginId: { default: "" },
    toast: { default: null }
  },
  setup(__props) {
    const props = __props;
    const t = hostToast(props.toast);
    const confirm = useHostConfirm();
    const items = ref$h([]);
    const serverCounts = ref$h(null);
    const loading = ref$h(false);
    const error = ref$h("");
    const loaded = ref$h(false);
    const query = ref$h("");
    const onlyMissing = ref$h(false);
    const deletingKey = ref$h("");
    const rows = computed$e(
      () => filterRecords(items.value, query.value, onlyMissing.value)
    );
    const filtered = computed$e(() => !!String(query.value || "").trim() || onlyMissing.value);
    const {
      rows: pagedRows,
      shown: shownRows,
      total: pagedTotal,
      hasMore,
      sentinel
    } = usePagedList(rows, { pageSize: HISTORY_PAGE_SIZE });
    const pagedHint = computed$e(() => hasMore.value ? `已显示 ${shownRows.value} / ${pagedTotal.value} 条 · 继续下滑自动加载` : `已全部加载（${pagedTotal.value} 条）`);
    const counts = computed$e(() => {
      const given = serverCounts.value;
      const local = {
        total: items.value.length,
        inLibrary: items.value.filter((item) => inLibrary(item)).length,
        missing: items.value.filter((item) => !inLibrary(item)).length
      };
      if (!given) return local;
      return {
        total: typeof given.total === "number" ? given.total : local.total,
        inLibrary: typeof given.inLibrary === "number" ? given.inLibrary : local.inLibrary,
        missing: typeof given.missing === "number" ? given.missing : local.missing
      };
    });
    function withinGrace(completedAt) {
      const text = String(completedAt || "").trim();
      if (!text) return false;
      const stamp = Date.parse(text.replace(/-/g, "/"));
      if (Number.isNaN(stamp)) return false;
      return Date.now() - stamp < IMPORT_GRACE_H * 3600 * 1e3;
    }
    function libTier(item) {
      if (inLibrary(item)) return "in";
      return withinGrace(item.completedAt || item.createdAt) ? "pending" : "gone";
    }
    function libraryText(item) {
      const tier = libTier(item);
      if (tier === "in") return "在库";
      return tier === "pending" ? "待入库" : "不在库（可能已删除）";
    }
    function libColor(item) {
      const tier = libTier(item);
      return tier === "in" ? "success" : tier === "pending" ? "warning" : void 0;
    }
    function libHint(item) {
      const tier = libTier(item);
      if (tier === "in") return String(item.lib?.path || "");
      if (tier === "pending") {
        return "刚下载完，Emby 还没扫到或刮削还没跑完；也可能这个番号刮不到（等一会儿再看）";
      }
      return "Emby 库里没有这个番号，文件可能已经删了";
    }
    const tiers = computed$e(() => {
      const out = { in: 0, pending: 0, gone: 0 };
      for (const item of items.value) out[libTier(item)] += 1;
      return out;
    });
    const summary = computed$e(
      () => `共 ${counts.value.total} 条 · 在库 ${tiers.value.in} · 待入库 ${tiers.value.pending} · 不在库 ${tiers.value.gone}`
    );
    function actorText(item) {
      const list = item.actors;
      if (Array.isArray(list)) {
        const names = list.map((row) => String((row || {}).name || (row || {}).zh || "").trim()).filter(Boolean);
        if (names.length) return names.join(" / ");
      }
      return String(item.actor || "");
    }
    function libUrl(item) {
      return String(item.lib?.url || "");
    }
    function readList(response) {
      return parseDownloadList(unwrap(response));
    }
    async function load(notify = false) {
      if (loading.value) return;
      loading.value = true;
      error.value = "";
      if (notify) t.info("正在刷新下载历史…");
      try {
        const client = props.api;
        if (!client || typeof client.get !== "function") throw new Error("宿主 api 不可用");
        const response = await client.get(ENDPOINT$1);
        const parsed = readList(response);
        items.value = parsed.items;
        serverCounts.value = parsed.counts;
        loaded.value = true;
      } catch (err) {
        error.value = errorText(err);
        if (notify) t.warning(`下载历史读取失败：${error.value}`);
      } finally {
        loading.value = false;
      }
    }
    async function removeRecord(item) {
      const key = recordKey(item, 0);
      if (!key || deletingKey.value) return;
      const label = displayNumber(item) || key;
      const ok = await confirm({
        type: "warn",
        title: "移除记录",
        content: `将从下载历史里移除「${label}」这条记录（只删台账记录，不动已下载的文件与 Emby 里的条目）。移除后这个番号再出现在榜单/搜索里时会重新显得"没下载过"。确认继续？`,
        confirmText: "移除记录",
        cancelText: "先留着"
      });
      if (!ok) return;
      const client = props.api;
      if (!client || typeof client.delete !== "function") {
        t.warning("移除记录失败");
        t.info("宿主请求器不支持 DELETE，无法执行该操作");
        return;
      }
      deletingKey.value = key;
      try {
        const response = await client.delete(ENDPOINT$1, { params: { key } });
        const parsed = readList(response);
        items.value = parsed.items;
        serverCounts.value = parsed.counts;
        loaded.value = true;
        t.success("已移除记录");
        t.info(label);
      } catch (err) {
        t.warning(`移除记录失败：${errorText(err)}`);
      } finally {
        deletingKey.value = "";
      }
    }
    function rowKey(item, index) {
      return recordKey(item, index);
    }
    function isDeleting(item, index) {
      return !!deletingKey.value && deletingKey.value === rowKey(item, index);
    }
    const skeletonRows = Array.from({ length: SKELETON_ROWS }, (_, index) => index);
    onMounted$8(() => {
      void load(false);
    });
    return (_ctx, _cache) => {
      const _component_v_text_field = _resolveComponent$f("v-text-field");
      const _component_v_switch = _resolveComponent$f("v-switch");
      const _component_v_btn = _resolveComponent$f("v-btn");
      const _component_v_chip = _resolveComponent$f("v-chip");
      return _openBlock$i(), _createElementBlock$i("div", _hoisted_1$h, [
        _createElementVNode$i("div", _hoisted_2$h, [
          _cache[5] || (_cache[5] = _createElementVNode$i("div", { class: "avh-history__spacer" }, null, -1)),
          _createVNode$g(_component_v_text_field, {
            modelValue: query.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => query.value = $event),
            class: "avh-history__q",
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            clearable: "",
            "single-line": "",
            "prepend-inner-icon": "mdi-magnify",
            placeholder: "番号 / 标题 / 演员",
            "aria-label": "按番号、标题或演员过滤下载历史"
          }, null, 8, ["modelValue"]),
          _createVNode$g(_component_v_switch, {
            modelValue: onlyMissing.value,
            "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => onlyMissing.value = $event),
            class: "avh-history__switch",
            color: "primary",
            density: "compact",
            "hide-details": "",
            label: "只看未入库"
          }, null, 8, ["modelValue"]),
          _createVNode$g(_component_v_btn, {
            variant: "outlined",
            size: "small",
            loading: loading.value,
            onClick: _cache[2] || (_cache[2] = ($event) => load(true))
          }, {
            default: _withCtx$f(() => _cache[4] || (_cache[4] = [
              _createTextVNode$d("↻ 刷新")
            ])),
            _: 1
          }, 8, ["loading"])
        ]),
        !error.value && (loaded.value || items.value.length) ? (_openBlock$i(), _createElementBlock$i("div", _hoisted_3$f, [
          _createVNode$g(_component_v_chip, {
            size: "x-small",
            variant: "flat",
            color: "success",
            label: ""
          }, {
            default: _withCtx$f(() => [
              _createTextVNode$d("在库 " + _toDisplayString$h(tiers.value.in), 1)
            ]),
            _: 1
          }),
          tiers.value.pending ? (_openBlock$i(), _createBlock$f(_component_v_chip, {
            key: 0,
            size: "x-small",
            variant: "flat",
            color: "warning",
            label: "",
            title: "刚下载完、Emby 还没扫到或刮削还没跑完；超过 48 小时仍未入库就归到「不在库」"
          }, {
            default: _withCtx$f(() => [
              _createTextVNode$d("待入库 " + _toDisplayString$h(tiers.value.pending), 1)
            ]),
            _: 1
          })) : _createCommentVNode$e("", true),
          _createVNode$g(_component_v_chip, {
            size: "x-small",
            variant: "outlined",
            label: ""
          }, {
            default: _withCtx$f(() => [
              _createTextVNode$d("不在库 " + _toDisplayString$h(tiers.value.gone), 1)
            ]),
            _: 1
          }),
          _createElementVNode$i("span", _hoisted_4$e, _toDisplayString$h(summary.value), 1)
        ])) : _createCommentVNode$e("", true),
        loading.value && !items.value.length ? (_openBlock$i(), _createElementBlock$i("div", _hoisted_5$e, [
          _cache[9] || (_cache[9] = _createElementVNode$i("div", { class: "avh-history__loading" }, "正在读取下载历史…", -1)),
          _createElementVNode$i("table", _hoisted_6$e, [
            _cache[7] || (_cache[7] = _createElementVNode$i("colgroup", null, [
              _createElementVNode$i("col", { class: "avh-history__col-pic" }),
              _createElementVNode$i("col", { class: "avh-history__col-no" }),
              _createElementVNode$i("col"),
              _createElementVNode$i("col", { class: "avh-history__col-actor" }),
              _createElementVNode$i("col", { class: "avh-history__col-size" }),
              _createElementVNode$i("col", { class: "avh-history__col-time" }),
              _createElementVNode$i("col", { class: "avh-history__col-lib" }),
              _createElementVNode$i("col", { class: "avh-history__col-act" })
            ], -1)),
            _cache[8] || (_cache[8] = _createElementVNode$i("thead", null, [
              _createElementVNode$i("tr", null, [
                _createElementVNode$i("th", null, "封面"),
                _createElementVNode$i("th", null, "番号"),
                _createElementVNode$i("th", null, "标题"),
                _createElementVNode$i("th", null, "演员"),
                _createElementVNode$i("th", null, "大小"),
                _createElementVNode$i("th", null, "完成时间"),
                _createElementVNode$i("th", null, "库状态"),
                _createElementVNode$i("th", { class: "avh-history__act" }, "操作")
              ])
            ], -1)),
            _createElementVNode$i("tbody", null, [
              (_openBlock$i(true), _createElementBlock$i(_Fragment$f, null, _renderList$e(_unref$6(skeletonRows), (row) => {
                return _openBlock$i(), _createElementBlock$i("tr", {
                  key: `sk-${row}`
                }, _cache[6] || (_cache[6] = [
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk avh-history__sk--pic" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$i("td", null, [
                    _createElementVNode$i("div", { class: "avh-history__sk" })
                  ], -1)
                ]));
              }), 128))
            ])
          ])
        ])) : error.value ? (_openBlock$i(), _createBlock$f(ErrorState, {
          key: 2,
          message: `下载历史读取失败：${error.value}`,
          retrying: loading.value,
          onRetry: _cache[3] || (_cache[3] = ($event) => load(false))
        }, null, 8, ["message", "retrying"])) : _unref$6(pagedRows).length ? (_openBlock$i(), _createElementBlock$i("div", _hoisted_7$d, [
          _createElementVNode$i("table", _hoisted_8$c, [
            _cache[11] || (_cache[11] = _createElementVNode$i("colgroup", null, [
              _createElementVNode$i("col", { class: "avh-history__col-pic" }),
              _createElementVNode$i("col", { class: "avh-history__col-no" }),
              _createElementVNode$i("col"),
              _createElementVNode$i("col", { class: "avh-history__col-actor" }),
              _createElementVNode$i("col", { class: "avh-history__col-size" }),
              _createElementVNode$i("col", { class: "avh-history__col-time" }),
              _createElementVNode$i("col", { class: "avh-history__col-lib" }),
              _createElementVNode$i("col", { class: "avh-history__col-act" })
            ], -1)),
            _cache[12] || (_cache[12] = _createElementVNode$i("thead", null, [
              _createElementVNode$i("tr", null, [
                _createElementVNode$i("th", null, "封面"),
                _createElementVNode$i("th", null, "番号"),
                _createElementVNode$i("th", null, "标题"),
                _createElementVNode$i("th", null, "演员"),
                _createElementVNode$i("th", null, "大小"),
                _createElementVNode$i("th", null, "完成时间"),
                _createElementVNode$i("th", null, "库状态"),
                _createElementVNode$i("th", { class: "avh-history__act" }, "操作")
              ])
            ], -1)),
            _createElementVNode$i("tbody", null, [
              (_openBlock$i(true), _createElementBlock$i(_Fragment$f, null, _renderList$e(_unref$6(pagedRows), (item, index) => {
                return _openBlock$i(), _createElementBlock$i("tr", {
                  key: rowKey(item, index)
                }, [
                  _createElementVNode$i("td", _hoisted_9$b, [
                    _createVNode$g(Thumb, {
                      class: "avh-history__thumb",
                      variant: "tposter",
                      src: String(item.thumb || ""),
                      alt: "无图",
                      "plugin-id": _ctx.pluginId
                    }, null, 8, ["src", "plugin-id"])
                  ]),
                  _createElementVNode$i("td", _hoisted_10$b, _toDisplayString$h(_unref$6(displayNumber)(item)), 1),
                  _createElementVNode$i("td", {
                    class: "avh-history__title",
                    title: String(item.title || "")
                  }, _toDisplayString$h(String(item.title || "") || "—"), 9, _hoisted_11$a),
                  _createElementVNode$i("td", {
                    title: actorText(item)
                  }, _toDisplayString$h(actorText(item) || "—"), 9, _hoisted_12$a),
                  _createElementVNode$i("td", null, _toDisplayString$h(_unref$6(sizeLabel)(item)), 1),
                  _createElementVNode$i("td", {
                    title: String(item.completedAt || item.createdAt || "")
                  }, _toDisplayString$h(_unref$6(completedText)(item)), 9, _hoisted_13$a),
                  _createElementVNode$i("td", {
                    title: libHint(item)
                  }, [
                    _createVNode$g(_component_v_chip, {
                      size: "x-small",
                      label: "",
                      variant: libTier(item) === "gone" ? "outlined" : "flat",
                      color: libColor(item),
                      class: "avh-history__lib"
                    }, {
                      default: _withCtx$f(() => [
                        _createTextVNode$d(_toDisplayString$h(libraryText(item)), 1)
                      ]),
                      _: 2
                    }, 1032, ["variant", "color"]),
                    libUrl(item) ? (_openBlock$i(), _createElementBlock$i("a", {
                      key: 0,
                      class: "avh-history__embylink",
                      href: libUrl(item),
                      target: "_blank",
                      rel: "noopener"
                    }, "打开 ↗", 8, _hoisted_15$9)) : _createCommentVNode$e("", true)
                  ], 8, _hoisted_14$a),
                  _createElementVNode$i("td", _hoisted_16$8, [
                    _createVNode$g(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      loading: isDeleting(item, index),
                      onClick: ($event) => removeRecord(item)
                    }, {
                      default: _withCtx$f(() => _cache[10] || (_cache[10] = [
                        _createTextVNode$d("移除记录")
                      ])),
                      _: 2
                    }, 1032, ["loading", "onClick"])
                  ])
                ]);
              }), 128))
            ])
          ]),
          _unref$6(pagedRows).length ? (_openBlock$i(), _createElementBlock$i("div", {
            key: 0,
            ref_key: "sentinel",
            ref: sentinel,
            class: "avh-history__more"
          }, [
            _createElementVNode$i("span", _hoisted_17$8, _toDisplayString$h(pagedHint.value), 1)
          ], 512)) : _createCommentVNode$e("", true)
        ])) : filtered.value && loaded.value ? (_openBlock$i(), _createBlock$f(EmptyState, {
          key: 4,
          text: "没有匹配的下载记录",
          hint: "试试清空搜索词，或关掉「只看不在库」"
        })) : (_openBlock$i(), _createBlock$f(EmptyState, {
          key: 5,
          text: "还没有下载记录<br>插件下载过的番号会自动登记在这里，删掉文件也不会消失"
        }))
      ]);
    };
  }
});

const HistoryView = /* @__PURE__ */ _export_sfc(_sfc_main$i, [["__scopeId", "data-v-36ac003f"]]);

const {defineComponent:_defineComponent$h} = await importShared('vue');

const {renderList:_renderList$d,Fragment:_Fragment$e,openBlock:_openBlock$h,createElementBlock:_createElementBlock$h,toDisplayString:_toDisplayString$g,createTextVNode:_createTextVNode$c,createCommentVNode:_createCommentVNode$d,normalizeClass:_normalizeClass$c,createElementVNode:_createElementVNode$h,resolveComponent:_resolveComponent$e,withCtx:_withCtx$e,createBlock:_createBlock$e,createVNode:_createVNode$f,normalizeStyle:_normalizeStyle$4,vShow:_vShow,withDirectives:_withDirectives} = await importShared('vue');

const _hoisted_1$g = { class: "avh-downloads" };
const _hoisted_2$g = { class: "avh-downloads__toolbar" };
const _hoisted_3$e = { class: "avh-tabs" };
const _hoisted_4$d = ["onClick"];
const _hoisted_5$d = {
  key: 0,
  class: "avh-vbadge"
};
const _hoisted_6$d = { class: "avh-q__hd" };
const _hoisted_7$c = { class: "avh-q__main" };
const _hoisted_8$b = { class: "avh-q__no" };
const _hoisted_9$a = {
  key: 0,
  class: "avh-q__ttl"
};
const _hoisted_10$a = { class: "avh-q__hint avh-q__meta" };
const _hoisted_11$9 = { class: "avh-q__hint avh-q__path" };
const _hoisted_12$9 = { class: "avh-q__right" };
const _hoisted_13$9 = { class: "avh-q__no" };
const _hoisted_14$9 = {
  key: 0,
  class: "avh-q__hint"
};
const _hoisted_15$8 = {
  key: 1,
  class: "avh-q__hint"
};
const _hoisted_16$7 = { class: "avh-bar" };
const _hoisted_17$7 = {
  key: 1,
  class: "avh-downloads__hint"
};
const _hoisted_18$6 = {
  key: 2,
  class: "avh-downloads__secttl"
};
const _hoisted_19$6 = {
  key: 0,
  class: "avh-vbadge"
};
const _hoisted_20$6 = { class: "avh-q__hd" };
const _hoisted_21$5 = { class: "avh-q__main" };
const _hoisted_22$5 = { class: "avh-q__no" };
const _hoisted_23$5 = {
  key: 0,
  class: "avh-q__ttl"
};
const _hoisted_24$4 = { class: "avh-q__hint avh-q__meta" };
const _hoisted_25$4 = ["title"];
const _hoisted_26$4 = { class: "avh-downloads__secttl" };
const _hoisted_27$4 = {
  key: 0,
  class: "avh-vbadge"
};
const _hoisted_28$4 = { class: "avh-q__hd" };
const _hoisted_29$4 = { class: "avh-q__main" };
const _hoisted_30$4 = { class: "avh-q__no" };
const _hoisted_31$4 = {
  key: 0,
  class: "avh-q__ttl"
};
const _hoisted_32$4 = { class: "avh-q__hint avh-q__meta" };
const _hoisted_33$4 = ["title"];
const _hoisted_34$4 = { class: "avh-q__exits" };
const {computed: computed$d,onBeforeUnmount: onBeforeUnmount$7,onMounted: onMounted$7,ref: ref$g,watch: watch$8} = await importShared('vue');
const WATCHDOG_MS = 18e4;
const POLL_MS$1 = 5e3;
const _sfc_main$h = /* @__PURE__ */ _defineComponent$h({
  __name: "DownloadsView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  setup(__props) {
    const props = __props;
    const t = hostToast(props.toast);
    const confirm = useHostConfirm();
    const pending = ref$g({});
    function pendingKey(action, item) {
      return `${action}:${String(item.id || item.hash || item.number || "")}`;
    }
    function isPending(action, item) {
      return !!pending.value[pendingKey(action, item)];
    }
    function withRowPending(action, item, run) {
      const key = pendingKey(action, item);
      if (pending.value[key]) return;
      pending.value = { ...pending.value, [key]: true };
      const clear = () => {
        if (!pending.value[key]) return;
        const next = { ...pending.value };
        delete next[key];
        pending.value = next;
      };
      window.setTimeout(clear, WATCHDOG_MS);
      void run().finally(clear);
    }
    function isCanceled(item) {
      return item.state === "canceled";
    }
    const TABS = [
      { key: "active", name: "下载中" },
      { key: "history", name: "下载历史" }
    ];
    const tab = ref$g("active");
    const historyMounted = ref$g(false);
    function pickTab(key) {
      tab.value = key;
      if (key === "history") historyMounted.value = true;
    }
    const rows = computed$d(
      () => Array.isArray(props.store.queue.value) ? props.store.queue.value : []
    );
    function isDone(item) {
      return item.state === "done";
    }
    function isFailed(item) {
      return item.state === "failed";
    }
    const activeRows = computed$d(
      () => rows.value.filter((item) => !isDone(item) && !isFailed(item) && !isCanceled(item))
    );
    const canceledRows = computed$d(
      () => rows.value.filter((item) => isCanceled(item))
    );
    const failedRows = computed$d(() => rows.value.filter((item) => isFailed(item)));
    function failReasonOf(item) {
      return String(item.failed_reason || item.failedReason || "").trim() || "原因未知";
    }
    function speedOf(item) {
      const row = item;
      const speed = String(row.speed || "").trim();
      const eta = String(row.eta || "").trim();
      const parts = [];
      if (speed && speed !== "0 B") parts.push(/\/s$/i.test(speed) ? speed : `${speed}/s`);
      if (eta) parts.push(`剩余 ${eta}`);
      return parts.join(" · ");
    }
    function hasBadge(item) {
      return !!versionBadgeOf(item);
    }
    function versionBadgeOf(item) {
      const row = item;
      const direct = String(row.badge ?? "").trim();
      const labels = [];
      const push = (value) => {
        const label = String(value ?? "").trim();
        if (label && !labels.includes(label)) labels.push(label);
      };
      if (!direct) {
        const tags = row.version_tags ?? row.versionTags;
        if (Array.isArray(tags)) tags.forEach(push);
        else if (tags && typeof tags === "object") {
          const dict = tags;
          if (dict.is_zh_sub) push("中字");
          if (dict.is_uncensored_leak) push("流出");
          const resolution = String(dict.resolution ?? "").trim();
          if (resolution) push(/2160|4k/i.test(resolution) ? "4K" : resolution.toUpperCase());
          if (dict.is_iso) push("ISO");
          if (dict.is_vr) push("VR");
          if (dict.part_no) push(String(dict.part_no));
          if (dict.edition) push(String(dict.edition));
        }
      }
      const merged = [direct, labels.join("/")].filter(Boolean).join(" ");
      const count = Number(row.version_count ?? row.versions ?? 0);
      if (count > 1) return merged ? `${merged} ${count}版本` : `${count}版本`;
      return merged;
    }
    function progressOf(item) {
      return Math.max(0, Math.min(100, Number(item.progress) || 0));
    }
    function metaOf(item) {
      return [item.site, item.spec, item.size].filter(Boolean).join(" · ") || "—";
    }
    function pathOf(item) {
      return String(item.savePath || "") + (item.added ? ` · ${item.added}` : "");
    }
    function rowKey(item, index) {
      return String(item.hash || item.id || `${item.number || ""}#${index}`);
    }
    function thumbOf(item) {
      return String(item.thumb || filledThumbs.value[String(item.number || "")] || "");
    }
    function labelOf(item) {
      return String(item.number || item.title || item.site || "这条下载");
    }
    async function cancelDownload(item) {
      const label = labelOf(item);
      const ok = await confirm({
        type: "warn",
        title: "取消下载",
        content: `将从下载器删除「${label}」的下载任务，并删除已下载的部分文件。条目会留在原位，之后可以「换资源」重新挑一个，或者「不要了」彻底取消。`,
        confirmText: "取消下载",
        cancelText: "先留着"
      });
      if (!ok) return;
      withRowPending("cancel", item, async () => {
        const res = await props.store.cancelDownload(String(item.id || ""));
        if (res.ok) {
          pushBottomToast("success", res.message || `已取消 ${label}`);
          return true;
        }
        pushBottomToast("warning", `取消失败：${res.message || "请稍后重试"}`);
        return false;
      });
    }
    async function returnDownload(item) {
      const label = labelOf(item);
      withRowPending("return", item, async () => {
        const res = await props.store.returnDownload(String(item.id || ""));
        if (res.ok) {
          pushBottomToast("success", res.message || `已把 ${label} 放回任务列表`);
          return true;
        }
        pushBottomToast("warning", `操作失败：${res.message || "请稍后重试"}`);
        return false;
      });
    }
    async function discardDownload(item) {
      const label = labelOf(item);
      const ok = await confirm({
        type: "warn",
        title: "不要了",
        content: `「${label}」会从下载列表移除，下载历史里也不再保留这条记录。如果它有番号订阅，会一并取消，以后不会再自动下载。`,
        confirmText: "不要了",
        cancelText: "先留着"
      });
      if (!ok) return;
      withRowPending("discard", item, async () => {
        const res = await props.store.discardDownload(String(item.id || ""), true);
        if (res.ok) {
          pushBottomToast("success", res.message || `已彻底取消 ${label}`);
          return true;
        }
        pushBottomToast("warning", `取消失败：${res.message || "请稍后重试"}`);
        return false;
      });
    }
    async function dropCanceledRow(item) {
      withRowPending("drop", item, async () => {
        const res = await props.store.dropDownloadRow(String(item.id || ""));
        if (res.ok) return true;
        pushBottomToast("warning", `移除失败：${res.message || "请稍后重试"}`);
        return false;
      });
    }
    async function refreshQueue() {
      const inflight = props.store.refreshTasks(false);
      t.info("正在刷新进度…");
      if (!await inflight) {
        t.warning(`任务读取失败：${props.store.error.value || "请稍后重试"}`);
      }
    }
    watch$8(
      rows,
      (items) => {
        if (props.api) queueMissingThumbs(props.api, items);
      },
      { immediate: true }
    );
    let timer = null;
    function shouldPoll() {
      return tab.value === "active" && document.visibilityState === "visible";
    }
    function startPolling() {
      if (timer !== null) return;
      timer = window.setInterval(() => {
        void props.store.refreshTasks(true);
      }, POLL_MS$1);
    }
    function stopPolling() {
      if (timer === null) return;
      window.clearInterval(timer);
      timer = null;
    }
    function syncPolling() {
      if (shouldPoll()) startPolling();
      else stopPolling();
    }
    function onVisibilityChange() {
      syncPolling();
    }
    watch$8(tab, (key) => {
      if (key === "active") void props.store.refreshTasks(true);
      syncPolling();
    });
    onMounted$7(() => {
      syncPolling();
      document.addEventListener("visibilitychange", onVisibilityChange);
    });
    onBeforeUnmount$7(() => {
      stopPolling();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$e("v-btn");
      const _component_v_chip = _resolveComponent$e("v-chip");
      return _openBlock$h(), _createElementBlock$h("div", _hoisted_1$g, [
        _createElementVNode$h("div", _hoisted_2$g, [
          _createElementVNode$h("div", _hoisted_3$e, [
            (_openBlock$h(), _createElementBlock$h(_Fragment$e, null, _renderList$d(TABS, (item) => {
              return _createElementVNode$h("button", {
                key: item.key,
                class: _normalizeClass$c({ "avh-tabs__on": item.key === tab.value }),
                onClick: ($event) => pickTab(item.key)
              }, [
                _createTextVNode$c(_toDisplayString$g(item.name), 1),
                item.key === "active" ? (_openBlock$h(), _createElementBlock$h(_Fragment$e, { key: 0 }, [
                  _createTextVNode$c("（" + _toDisplayString$g(activeRows.value.length) + "）", 1)
                ], 64)) : _createCommentVNode$d("", true)
              ], 10, _hoisted_4$d);
            }), 64))
          ]),
          _cache[1] || (_cache[1] = _createElementVNode$h("div", { class: "avh-downloads__spacer" }, null, -1)),
          tab.value === "active" ? (_openBlock$h(), _createBlock$e(_component_v_btn, {
            key: 0,
            variant: "outlined",
            size: "small",
            onClick: refreshQueue
          }, {
            default: _withCtx$e(() => _cache[0] || (_cache[0] = [
              _createTextVNode$c("↻ 刷新进度")
            ])),
            _: 1
          })) : _createCommentVNode$d("", true)
        ]),
        tab.value === "active" ? (_openBlock$h(), _createElementBlock$h(_Fragment$e, { key: 0 }, [
          rows.value.length ? (_openBlock$h(), _createElementBlock$h(_Fragment$e, { key: 0 }, [
            activeRows.value.length ? (_openBlock$h(true), _createElementBlock$h(_Fragment$e, { key: 0 }, _renderList$d(activeRows.value, (item, index) => {
              return _openBlock$h(), _createElementBlock$h("div", {
                key: rowKey(item, index),
                class: _normalizeClass$c(["avh-q", { "avh-q--vtag": hasBadge(item) }])
              }, [
                hasBadge(item) ? (_openBlock$h(), _createElementBlock$h("span", _hoisted_5$d, _toDisplayString$g(versionBadgeOf(item)), 1)) : _createCommentVNode$d("", true),
                _createElementVNode$h("div", _hoisted_6$d, [
                  _createVNode$f(Thumb, {
                    class: "avh-q__poster",
                    variant: "tposter",
                    src: thumbOf(item),
                    alt: "无图",
                    "plugin-id": _ctx.pluginId
                  }, null, 8, ["src", "plugin-id"]),
                  _createElementVNode$h("div", _hoisted_7$c, [
                    _createElementVNode$h("div", _hoisted_8$b, _toDisplayString$g(item.number || ""), 1),
                    item.title ? (_openBlock$h(), _createElementBlock$h("div", _hoisted_9$a, _toDisplayString$g(item.title), 1)) : _createCommentVNode$d("", true),
                    _createElementVNode$h("div", _hoisted_10$a, _toDisplayString$g(metaOf(item)), 1),
                    _createElementVNode$h("div", _hoisted_11$9, _toDisplayString$g(pathOf(item)), 1)
                  ]),
                  _createElementVNode$h("div", _hoisted_12$9, [
                    _createElementVNode$h("div", _hoisted_13$9, _toDisplayString$g(progressOf(item)) + "%", 1),
                    speedOf(item) ? (_openBlock$h(), _createElementBlock$h("div", _hoisted_14$9, _toDisplayString$g(speedOf(item)), 1)) : (_openBlock$h(), _createElementBlock$h("div", _hoisted_15$8, "下载中…")),
                    _createVNode$f(_component_v_btn, {
                      class: "avh-q__act",
                      variant: "text",
                      size: "x-small",
                      color: "error",
                      loading: isPending("cancel", item),
                      onClick: ($event) => cancelDownload(item)
                    }, {
                      default: _withCtx$e(() => _cache[2] || (_cache[2] = [
                        _createTextVNode$c("取消下载")
                      ])),
                      _: 2
                    }, 1032, ["loading", "onClick"])
                  ])
                ]),
                _createElementVNode$h("div", _hoisted_16$7, [
                  _createElementVNode$h("i", {
                    style: _normalizeStyle$4({ width: `${progressOf(item)}%` })
                  }, null, 4)
                ])
              ], 2);
            }), 128)) : (_openBlock$h(), _createElementBlock$h("div", _hoisted_17$7, "没有下载中的任务")),
            failedRows.value.length ? (_openBlock$h(), _createElementBlock$h("div", _hoisted_18$6, [
              _createElementVNode$h("span", null, "下载失败（" + _toDisplayString$g(failedRows.value.length) + "）", 1),
              _cache[3] || (_cache[3] = _createElementVNode$h("span", { class: "avh-downloads__secttl-note" }, "在「任务」页可重新挑种下载", -1))
            ])) : _createCommentVNode$d("", true),
            failedRows.value.length ? (_openBlock$h(true), _createElementBlock$h(_Fragment$e, { key: 3 }, _renderList$d(failedRows.value, (item, index) => {
              return _openBlock$h(), _createElementBlock$h("div", {
                key: rowKey(item, index),
                class: _normalizeClass$c(["avh-q avh-q--failed", { "avh-q--vtag": hasBadge(item) }])
              }, [
                hasBadge(item) ? (_openBlock$h(), _createElementBlock$h("span", _hoisted_19$6, _toDisplayString$g(versionBadgeOf(item)), 1)) : _createCommentVNode$d("", true),
                _createElementVNode$h("div", _hoisted_20$6, [
                  _createVNode$f(Thumb, {
                    class: "avh-q__poster",
                    variant: "tposter",
                    src: thumbOf(item),
                    alt: "无图",
                    "plugin-id": _ctx.pluginId
                  }, null, 8, ["src", "plugin-id"]),
                  _createElementVNode$h("div", _hoisted_21$5, [
                    _createElementVNode$h("div", _hoisted_22$5, [
                      _createTextVNode$c(_toDisplayString$g(item.number || "") + " ", 1),
                      _createVNode$f(_component_v_chip, {
                        size: "x-small",
                        color: "error",
                        variant: "tonal",
                        class: "ms-1"
                      }, {
                        default: _withCtx$e(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$c("下载失败")
                        ])),
                        _: 1
                      })
                    ]),
                    item.title ? (_openBlock$h(), _createElementBlock$h("div", _hoisted_23$5, _toDisplayString$g(item.title), 1)) : _createCommentVNode$d("", true),
                    _createElementVNode$h("div", _hoisted_24$4, _toDisplayString$g(metaOf(item)), 1),
                    _createElementVNode$h("div", {
                      class: "avh-q__hint avh-q__path",
                      title: failReasonOf(item)
                    }, " 失败原因：" + _toDisplayString$g(failReasonOf(item)), 9, _hoisted_25$4)
                  ])
                ])
              ], 2);
            }), 128)) : _createCommentVNode$d("", true),
            canceledRows.value.length ? (_openBlock$h(), _createElementBlock$h(_Fragment$e, { key: 4 }, [
              _createElementVNode$h("div", _hoisted_26$4, [
                _createElementVNode$h("span", null, "已取消（" + _toDisplayString$g(canceledRows.value.length) + "）", 1),
                _cache[5] || (_cache[5] = _createElementVNode$h("span", { class: "avh-downloads__secttl-note" }, "选「换资源」重新挑，或「不要了」彻底取消", -1))
              ]),
              (_openBlock$h(true), _createElementBlock$h(_Fragment$e, null, _renderList$d(canceledRows.value, (item, index) => {
                return _openBlock$h(), _createElementBlock$h("div", {
                  key: rowKey(item, index),
                  class: _normalizeClass$c(["avh-q avh-q--canceled", { "avh-q--vtag": hasBadge(item) }])
                }, [
                  hasBadge(item) ? (_openBlock$h(), _createElementBlock$h("span", _hoisted_27$4, _toDisplayString$g(versionBadgeOf(item)), 1)) : _createCommentVNode$d("", true),
                  _createElementVNode$h("div", _hoisted_28$4, [
                    _createVNode$f(Thumb, {
                      class: "avh-q__poster",
                      variant: "tposter",
                      src: thumbOf(item),
                      alt: "无图",
                      "plugin-id": _ctx.pluginId
                    }, null, 8, ["src", "plugin-id"]),
                    _createElementVNode$h("div", _hoisted_29$4, [
                      _createElementVNode$h("div", _hoisted_30$4, [
                        _createTextVNode$c(_toDisplayString$g(item.number || "") + " ", 1),
                        _createVNode$f(_component_v_chip, {
                          size: "x-small",
                          variant: "tonal",
                          class: "ms-1"
                        }, {
                          default: _withCtx$e(() => _cache[6] || (_cache[6] = [
                            _createTextVNode$c("已取消")
                          ])),
                          _: 1
                        })
                      ]),
                      item.title ? (_openBlock$h(), _createElementBlock$h("div", _hoisted_31$4, _toDisplayString$g(item.title), 1)) : _createCommentVNode$d("", true),
                      _createElementVNode$h("div", _hoisted_32$4, _toDisplayString$g(metaOf(item)), 1),
                      _createElementVNode$h("div", {
                        class: "avh-q__hint avh-q__path",
                        title: String(item.canceled_detail || "")
                      }, _toDisplayString$g(item.canceled_detail || pathOf(item)), 9, _hoisted_33$4)
                    ])
                  ]),
                  _createElementVNode$h("div", _hoisted_34$4, [
                    _createVNode$f(_component_v_btn, {
                      variant: "tonal",
                      size: "small",
                      loading: isPending("return", item),
                      onClick: ($event) => returnDownload(item)
                    }, {
                      default: _withCtx$e(() => _cache[7] || (_cache[7] = [
                        _createTextVNode$c("换资源")
                      ])),
                      _: 2
                    }, 1032, ["loading", "onClick"]),
                    _createVNode$f(_component_v_btn, {
                      variant: "text",
                      size: "small",
                      color: "error",
                      loading: isPending("discard", item),
                      onClick: ($event) => discardDownload(item)
                    }, {
                      default: _withCtx$e(() => _cache[8] || (_cache[8] = [
                        _createTextVNode$c("不要了")
                      ])),
                      _: 2
                    }, 1032, ["loading", "onClick"]),
                    _createVNode$f(_component_v_btn, {
                      variant: "text",
                      size: "small",
                      loading: isPending("drop", item),
                      onClick: ($event) => dropCanceledRow(item)
                    }, {
                      default: _withCtx$e(() => _cache[9] || (_cache[9] = [
                        _createTextVNode$c("移除")
                      ])),
                      _: 2
                    }, 1032, ["loading", "onClick"])
                  ])
                ], 2);
              }), 128))
            ], 64)) : _createCommentVNode$d("", true)
          ], 64)) : (_openBlock$h(), _createBlock$e(EmptyState, {
            key: 1,
            text: "下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看<br>完成的下载在「下载历史」页签"
          }))
        ], 64)) : _createCommentVNode$d("", true),
        historyMounted.value ? _withDirectives((_openBlock$h(), _createBlock$e(HistoryView, {
          key: 1,
          api: props.api,
          "plugin-id": props.pluginId,
          toast: props.toast
        }, null, 8, ["api", "plugin-id", "toast"])), [
          [_vShow, tab.value === "history"]
        ]) : _createCommentVNode$d("", true)
      ]);
    };
  }
});

const DownloadsView = /* @__PURE__ */ _export_sfc(_sfc_main$h, [["__scopeId", "data-v-4a7a71d3"]]);

const {defineComponent:_defineComponent$g} = await importShared('vue');

const {createVNode:_createVNode$e,openBlock:_openBlock$g,createElementBlock:_createElementBlock$g,createCommentVNode:_createCommentVNode$c,createElementVNode:_createElementVNode$g,normalizeClass:_normalizeClass$b,toDisplayString:_toDisplayString$f,withModifiers:_withModifiers,Fragment:_Fragment$d} = await importShared('vue');

const _hoisted_1$f = ["title"];
const _hoisted_2$f = { class: "avh-card__badges" };
const _hoisted_3$d = {
  key: 0,
  class: "avh-badge avh-badge--cn"
};
const _hoisted_4$c = {
  key: 1,
  class: "avh-badge avh-badge--uc"
};
const _hoisted_5$c = {
  key: 2,
  class: "avh-badge avh-badge--new"
};
const _hoisted_6$c = {
  key: 3,
  class: "avh-badge avh-badge--lib"
};
const _hoisted_7$b = {
  key: 4,
  class: "avh-badge avh-badge--dlg"
};
const _hoisted_8$a = {
  key: 5,
  class: "avh-badge avh-badge--dl"
};
const _hoisted_9$9 = {
  key: 6,
  class: "avh-badge avh-badge--unscraped"
};
const _hoisted_10$9 = { class: "avh-card__meta" };
const _hoisted_11$8 = { class: "avh-card__num" };
const _hoisted_12$8 = { class: "avh-card__sub" };
const _hoisted_13$8 = { key: 0 };
const _hoisted_14$8 = { key: 1 };
const _hoisted_15$7 = { class: "avh-card__sub" };
const _hoisted_16$6 = ["title"];
const _hoisted_17$6 = ["href"];
const _sfc_main$g = /* @__PURE__ */ _defineComponent$g({
  __name: "NumCard",
  props: {
    movie: {},
    pluginId: { default: "" },
    actorFavorited: { type: Boolean, default: false },
    mode: { default: "rank" }
  },
  emits: ["select", "hover"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const number = () => String(props.movie.number || "");
    const id = () => String(props.movie.id || "");
    const cardCover = () => String(props.movie.cover || props.movie.thumb || "");
    const library = () => props.mode === "library";
    const durationText = () => {
      const value = props.movie.duration;
      return value ? `${value}′` : "";
    };
    const addedText = () => {
      const day = String(props.movie.addedAt || "").slice(0, 10);
      return day ? `入库 ${day}` : "";
    };
    const fileName = () => String(props.movie.lib?.path || "").replace(/\\/g, "/").split("/").pop() || "";
    const actorLine = () => {
      const list = props.movie.actors;
      if (Array.isArray(list)) {
        const names = list.map((row) => String((row || {}).name || (row || {}).zh || "").trim()).filter(Boolean);
        if (names.length) return names.join(" / ");
      }
      return String(props.movie.actor || "") || "—";
    };
    const libBodyText = () => String(props.movie.title || "") || fileName();
    const watchUrl = () => String(props.movie.lib?.url || "");
    return (_ctx, _cache) => {
      return _openBlock$g(), _createElementBlock$g("div", {
        class: "avh-card",
        title: _ctx.movie.title || number(),
        onClick: _cache[1] || (_cache[1] = ($event) => emit("select", { number: number(), id: id() })),
        onMouseenter: _cache[2] || (_cache[2] = ($event) => emit("hover", { number: number(), id: id() }))
      }, [
        _createElementVNode$g("div", {
          class: _normalizeClass$b(["avh-card__thumb", { "avh-card__thumb--spread": !!_ctx.movie.cover }])
        }, [
          _createVNode$e(Thumb, {
            variant: "thumb",
            src: cardCover(),
            alt: number(),
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "alt", "plugin-id"]),
          _createElementVNode$g("div", _hoisted_2$f, [
            _ctx.movie.cnsub ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_3$d, "中字")) : _createCommentVNode$c("", true),
            _ctx.movie.uncensored ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_4$c, "破解")) : _createCommentVNode$c("", true),
            _ctx.actorFavorited ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_5$c, "⭐已收藏演员")) : _createCommentVNode$c("", true),
            _ctx.movie.lib ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_6$c, "✔已入库")) : _createCommentVNode$c("", true),
            _ctx.movie.downloading && !_ctx.movie.lib && !_ctx.movie.downloaded ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_7$b, "⏬下载中")) : _createCommentVNode$c("", true),
            _ctx.movie.downloaded && !_ctx.movie.lib ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_8$a, "✔已下载")) : _createCommentVNode$c("", true),
            library() && _ctx.movie.states?.scrape === "unscraped" ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_9$9, "未刮")) : _createCommentVNode$c("", true)
          ])
        ], 2),
        _createElementVNode$g("div", _hoisted_10$9, [
          _createElementVNode$g("div", _hoisted_11$8, _toDisplayString$f(number()), 1),
          _createElementVNode$g("div", _hoisted_12$8, [
            _createElementVNode$g("span", null, _toDisplayString$f(actorLine()), 1),
            library() ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_13$8, _toDisplayString$f(addedText()), 1)) : (_openBlock$g(), _createElementBlock$g("span", _hoisted_14$8, "🧲 " + _toDisplayString$f(_ctx.movie.magnets || 0), 1))
          ]),
          _createElementVNode$g("div", _hoisted_15$7, [
            library() ? (_openBlock$g(), _createElementBlock$g(_Fragment$d, { key: 0 }, [
              _createElementVNode$g("span", {
                title: String(_ctx.movie.lib?.path || "")
              }, _toDisplayString$f(libBodyText()), 9, _hoisted_16$6),
              watchUrl() ? (_openBlock$g(), _createElementBlock$g("a", {
                key: 0,
                class: "avh-card__watch",
                href: watchUrl(),
                target: "_blank",
                rel: "noopener",
                title: "在 Emby（MB）里观看",
                onClick: _cache[0] || (_cache[0] = _withModifiers(() => {
                }, ["stop"]))
              }, "▶ 观看", 8, _hoisted_17$6)) : _createCommentVNode$c("", true)
            ], 64)) : (_openBlock$g(), _createElementBlock$g(_Fragment$d, { key: 1 }, [
              _createElementVNode$g("span", null, _toDisplayString$f(_ctx.movie.date || ""), 1),
              _createElementVNode$g("span", null, _toDisplayString$f(durationText()), 1)
            ], 64))
          ])
        ])
      ], 40, _hoisted_1$f);
    };
  }
});

const NumCard = /* @__PURE__ */ _export_sfc(_sfc_main$g, [["__scopeId", "data-v-40465f5e"]]);

const {reactive: reactive$2} = await importShared('vue');

const detailCache = reactive$2(/* @__PURE__ */ new Map());
const longState = reactive$2(/* @__PURE__ */ new Map());
function cachedDetail(number) {
  const key = String(number ?? "");
  return key ? detailCache.get(key) : void 0;
}
function putDetail(number, data) {
  const key = String(number ?? "");
  if (!key) return;
  detailCache.set(key, { data: data || {}, t: Date.now(), error: "" });
}
function putDetailError(number, error) {
  const key = String(number ?? "");
  if (!key) return;
  detailCache.set(key, { data: {}, t: Date.now(), error });
}
function dropDetail(number) {
  const key = String(number ?? "");
  if (key) detailCache.delete(key);
}
function setLongUrl(number, url) {
  const entry = cachedDetail(number);
  if (entry && entry.data) entry.data.longimage = url;
}
async function fetchLongUrl(api, number, force = false) {
  if (!api || typeof api.get !== "function") return { ok: false, message: "宿主请求器不可用" };
  const params = { number };
  if (force) params.force = 1;
  try {
    const raw = await api.get("plugin/longimage", { params });
    const payload = raw && typeof raw === "object" && "data" in raw ? raw.data : raw;
    if (payload && typeof payload === "object" && payload.success === false) {
      return { ok: false, message: String(payload.message || payload.detail || "") };
    }
    const url = String(payload && (payload.url || payload.longimage) || "");
    return { ok: true, url };
  } catch (err) {
    const payload = err?.payload || err?.response?.data;
    const message = String(payload?.message || payload?.detail || err?.message || "请稍后重试");
    return { ok: false, message };
  }
}

const PREFETCH_N = 6;
function warmImage(url) {
  const src = String(url ?? "");
  if (!src) return;
  const image = new Image();
  image.decoding = "async";
  image.src = src;
}
const NUMBER_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const inFlight = /* @__PURE__ */ new Set();
function createDetailPrefetcher(api) {
  const queue = { jobs: [], busy: false, gen: 0, req: null };
  function getApi() {
    const value = api();
    return value && typeof value.get === "function" ? value : null;
  }
  async function pump() {
    if (queue.busy) return;
    let job = queue.jobs.shift();
    while (job && (cachedDetail(job.number) || inFlight.has(job.number))) job = queue.jobs.shift();
    if (!job) return;
    const client = getApi();
    if (!client) {
      queue.jobs = [];
      return;
    }
    const gen = queue.gen;
    const controller = new AbortController();
    const req = { controller, promise: null };
    queue.busy = true;
    queue.req = req;
    inFlight.add(job.number);
    req.promise = (async () => {
      try {
        const params = { number: job.number };
        if (job.id) params.id = job.id;
        const payload = unwrap(
          await client.get("plugin/detail", { params, signal: controller.signal })
        );
        if (gen !== queue.gen) return;
        if (payload && typeof payload === "object" && payload.success === false) return;
        putDetail(job.number, payload || {});
      } catch {
      } finally {
        inFlight.delete(job.number);
        if (queue.req === req) {
          queue.req = null;
          queue.busy = false;
        }
        void pump();
      }
    })();
  }
  function enqueue(number, id) {
    const num = String(number ?? "").trim();
    if (!num || !NUMBER_RE.test(num)) return;
    if (cachedDetail(num)) return;
    if (queue.jobs.some((job) => job.number === num)) return;
    if (inFlight.has(num)) return;
    queue.jobs.push({ number: num, id: String(id ?? "") });
    void pump();
  }
  function flush() {
    queue.jobs = [];
    queue.gen += 1;
    const req = queue.req;
    if (!req) {
      queue.busy = false;
      return;
    }
    queue.busy = true;
    try {
      req.controller.abort();
    } catch {
    }
    const resume = () => void pump();
    Promise.resolve(req.promise).then(resume, resume);
  }
  return {
    enqueue,
    enqueueMany(movies, n = PREFETCH_N) {
      (movies || []).slice(0, n).forEach((movie) => enqueue(movie?.number, movie?.id));
    },
    flush,
    idle: () => !queue.busy
  };
}

const {defineComponent:_defineComponent$f} = await importShared('vue');

const {createElementVNode:_createElementVNode$f,resolveComponent:_resolveComponent$d,createVNode:_createVNode$d,createTextVNode:_createTextVNode$b,withCtx:_withCtx$d,toDisplayString:_toDisplayString$e,openBlock:_openBlock$f,createElementBlock:_createElementBlock$f,createCommentVNode:_createCommentVNode$b,createBlock:_createBlock$d,unref:_unref$5,renderList:_renderList$c,Fragment:_Fragment$c} = await importShared('vue');

const _hoisted_1$e = { class: "avh-library" };
const _hoisted_2$e = { class: "avh-library__toolbar" };
const _hoisted_3$c = {
  key: 0,
  class: "avh-library__stats"
};
const _hoisted_4$b = { class: "avh-library__hint" };
const _hoisted_5$b = {
  key: 2,
  class: "avh-library__loading"
};
const _hoisted_6$b = { class: "avh-library__grid" };
const _hoisted_7$a = {
  key: 0,
  class: "avh-vbadge"
};
const _hoisted_8$9 = { class: "avh-library__hint" };
const {computed: computed$c,onBeforeUnmount: onBeforeUnmount$6,ref: ref$f,watch: watch$7} = await importShared('vue');
const ENDPOINT = "plugin/library";
const LIBRARY_PAGE_SIZE = 60;
const _sfc_main$f = /* @__PURE__ */ _defineComponent$f({
  __name: "LibraryView",
  props: {
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["openMovie"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const items = ref$f([]);
    const total = ref$f(0);
    const libraryReady = ref$f(true);
    const loading = ref$f(false);
    const error = ref$f("");
    const loaded = ref$f(false);
    const query = ref$f("");
    const rows = computed$c(() => {
      const keyword = String(query.value || "").trim().toLowerCase();
      if (!keyword) return items.value;
      return items.value.filter((item) => {
        const haystack = [item.number, item.title, item.actor].map((value) => String(value || "").toLowerCase()).join(" ");
        return haystack.includes(keyword);
      });
    });
    const filtered = computed$c(() => !!String(query.value || "").trim());
    const {
      rows: pagedRows,
      shown: shownRows,
      total: pagedTotal,
      hasMore,
      sentinel
    } = usePagedList(rows, { pageSize: LIBRARY_PAGE_SIZE });
    const pagedHint = computed$c(() => hasMore.value ? `已显示 ${shownRows.value} / ${pagedTotal.value} 部 · 继续下滑自动加载` : `已全部加载（${pagedTotal.value} 部）`);
    const summary = computed$c(() => {
      const all = total.value || items.value.length;
      return filtered.value ? `共 ${all} 部 · 筛出 ${rows.value.length} 部` : `共 ${all} 部`;
    });
    const prefetcher = createDetailPrefetcher(() => props.api);
    async function load(fresh = false, notify = false) {
      if (loading.value) return;
      loading.value = true;
      error.value = "";
      if (notify) t.info("正在读取媒体库…");
      try {
        const client = props.api;
        if (!client || typeof client.get !== "function") throw new Error("宿主 api 不可用");
        const response = await client.get(ENDPOINT, { params: fresh ? { fresh: 1 } : {} });
        const payload = unwrap(response);
        if (payload && typeof payload === "object" && payload.success === false) {
          throw new Error(String(payload.message || "已入库列表读取失败"));
        }
        const list = Array.isArray(payload?.items) ? payload.items : [];
        items.value = list;
        total.value = Number(payload?.total || list.length) || list.length;
        libraryReady.value = payload?.libraryReady === void 0 ? true : !!payload.libraryReady;
        loaded.value = true;
        if (notify) t.success(`共 ${total.value} 部`);
      } catch (err) {
        error.value = errorText(err);
        if (notify) t.warning(`已入库列表读取失败：${error.value}`);
      } finally {
        loading.value = false;
      }
    }
    function openCard(movie) {
      emit("openMovie", { number: String(movie.number || ""), id: String(movie.id || "") });
    }
    function hoverCard(movie) {
      prefetcher.enqueue(movie.number, movie.id);
    }
    function cardKey(movie, index) {
      return `${movie.number || ""}#${index}`;
    }
    function versionBadgeOf(movie) {
      const row = movie;
      const direct = String(row.badge ?? "").trim();
      const labels = [];
      const push = (value) => {
        const label = String(value ?? "").trim();
        if (label && !labels.includes(label)) labels.push(label);
      };
      if (!direct) {
        const tags = row.version_tags;
        if (Array.isArray(tags)) tags.forEach(push);
        else if (tags && typeof tags === "object") {
          const dict = tags;
          if (dict.is_zh_sub) push("中字");
          if (dict.is_uncensored_leak) push("流出");
          const resolution = String(dict.resolution ?? "").trim();
          if (resolution) push(/2160|4k/i.test(resolution) ? "4K" : resolution.toUpperCase());
          if (dict.is_iso) push("ISO");
          if (dict.is_vr) push("VR");
          if (dict.part_no) push(String(dict.part_no));
          if (dict.edition) push(String(dict.edition));
        }
      }
      const merged = [direct, labels.join("/")].filter(Boolean).join(" ");
      const count = Number(row.version_count ?? row.versions ?? 0);
      if (count > 1) return merged ? `${merged} ${count}版本` : `${count}版本`;
      return merged;
    }
    watch$7(rows, (list) => prefetcher.enqueueMany(list), { immediate: true });
    onBeforeUnmount$6(() => {
      prefetcher.flush();
    });
    void load(false, false);
    return (_ctx, _cache) => {
      const _component_v_text_field = _resolveComponent$d("v-text-field");
      const _component_v_btn = _resolveComponent$d("v-btn");
      const _component_v_chip = _resolveComponent$d("v-chip");
      return _openBlock$f(), _createElementBlock$f("div", _hoisted_1$e, [
        _createElementVNode$f("div", _hoisted_2$e, [
          _cache[4] || (_cache[4] = _createElementVNode$f("div", { class: "avh-library__spacer" }, null, -1)),
          _createVNode$d(_component_v_text_field, {
            modelValue: query.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => query.value = $event),
            class: "avh-library__q",
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            clearable: "",
            "single-line": "",
            "prepend-inner-icon": "mdi-magnify",
            placeholder: "番号 / 片名 / 演员",
            "aria-label": "按番号、片名或演员过滤已入库的番号"
          }, null, 8, ["modelValue"]),
          _createVNode$d(_component_v_btn, {
            variant: "outlined",
            size: "small",
            loading: loading.value,
            onClick: _cache[1] || (_cache[1] = ($event) => load(true, true))
          }, {
            default: _withCtx$d(() => _cache[3] || (_cache[3] = [
              _createTextVNode$b("↻ 刷新")
            ])),
            _: 1
          }, 8, ["loading"])
        ]),
        !error.value && (loaded.value || items.value.length) ? (_openBlock$f(), _createElementBlock$f("div", _hoisted_3$c, [
          _createVNode$d(_component_v_chip, {
            size: "x-small",
            variant: "flat",
            color: "success",
            label: ""
          }, {
            default: _withCtx$d(() => _cache[5] || (_cache[5] = [
              _createTextVNode$b("已入库")
            ])),
            _: 1
          }),
          _createElementVNode$f("span", _hoisted_4$b, _toDisplayString$e(summary.value), 1)
        ])) : _createCommentVNode$b("", true),
        error.value ? (_openBlock$f(), _createBlock$d(ErrorState, {
          key: 1,
          message: `已入库列表读取失败：${error.value}`,
          retrying: loading.value,
          onRetry: _cache[2] || (_cache[2] = ($event) => load(false, false))
        }, null, 8, ["message", "retrying"])) : loading.value && !items.value.length ? (_openBlock$f(), _createElementBlock$f("div", _hoisted_5$b, "正在读取媒体库…")) : !libraryReady.value && !items.value.length ? (_openBlock$f(), _createBlock$d(EmptyState, {
          key: 3,
          text: "没有连上 Emby 媒体库",
          hint: "插件默认复用 MoviePilot「设置 → 媒体服务器」里已启用的 Emby；也可以在「设置 → 媒体库」里单独填 host 与 api_key"
        })) : !items.value.length ? (_openBlock$f(), _createBlock$d(EmptyState, {
          key: 4,
          text: "媒体库里还没有片子<br>下载并整理入库后，这里会按入库时间列出全部番号"
        })) : filtered.value && !rows.value.length ? (_openBlock$f(), _createBlock$d(EmptyState, {
          key: 5,
          text: "没有匹配的番号",
          hint: "试试清空搜索词，或者换个番号 / 演员名"
        })) : (_openBlock$f(), _createElementBlock$f(_Fragment$c, { key: 6 }, [
          _createElementVNode$f("div", _hoisted_6$b, [
            (_openBlock$f(true), _createElementBlock$f(_Fragment$c, null, _renderList$c(_unref$5(pagedRows), (movie, index) => {
              return _openBlock$f(), _createElementBlock$f("div", {
                key: cardKey(movie, index),
                class: "avh-library__cell"
              }, [
                _createVNode$d(NumCard, {
                  movie,
                  "plugin-id": _ctx.pluginId,
                  mode: "library",
                  onSelect: ($event) => openCard(movie),
                  onHover: ($event) => hoverCard(movie)
                }, null, 8, ["movie", "plugin-id", "onSelect", "onHover"]),
                versionBadgeOf(movie) ? (_openBlock$f(), _createElementBlock$f("span", _hoisted_7$a, _toDisplayString$e(versionBadgeOf(movie)), 1)) : _createCommentVNode$b("", true)
              ]);
            }), 128))
          ]),
          _createElementVNode$f("div", {
            ref_key: "sentinel",
            ref: sentinel,
            class: "avh-library__more"
          }, [
            _createElementVNode$f("span", _hoisted_8$9, _toDisplayString$e(pagedHint.value), 1)
          ], 512)
        ], 64))
      ]);
    };
  }
});

const LibraryView = /* @__PURE__ */ _export_sfc(_sfc_main$f, [["__scopeId", "data-v-438aad50"]]);

const {defineComponent:_defineComponent$e} = await importShared('vue');

const {createElementVNode:_createElementVNode$e,createTextVNode:_createTextVNode$a,resolveComponent:_resolveComponent$c,withCtx:_withCtx$c,createVNode:_createVNode$c,toDisplayString:_toDisplayString$d,renderList:_renderList$b,Fragment:_Fragment$b,openBlock:_openBlock$e,createElementBlock:_createElementBlock$e,createBlock:_createBlock$c} = await importShared('vue');

const _hoisted_1$d = { class: "avh-tasks" };
const _hoisted_2$d = { class: "avh-tasks__toolbar" };
const _hoisted_3$b = { class: "avh-tasks__secttl" };
const {computed: computed$b,onBeforeUnmount: onBeforeUnmount$5,onMounted: onMounted$6,ref: ref$e,watch: watch$6} = await importShared('vue');
const POLL_MS = 5e3;
const _sfc_main$e = /* @__PURE__ */ _defineComponent$e({
  __name: "TasksView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  setup(__props) {
    const props = __props;
    const t = hostToast(props.toast);
    const tables = ref$e([]);
    const pending = computed$b(() => {
      const all = Array.isArray(props.store.tasks.value) ? props.store.tasks.value : [];
      return all.filter((item) => item.state === "await");
    });
    function rowKey(task, index) {
      return String(task.id ?? `${task.number || ""}#${index}`);
    }
    const subscribedKeys = computed$b(() => {
      const out = /* @__PURE__ */ new Set();
      const subs = Array.isArray(props.store.subs.value) ? props.store.subs.value : [];
      for (const sub of subs) {
        if (String(sub.type || "") !== "number") continue;
        const key = normKey(sub.name);
        if (key) out.add(key);
      }
      return out;
    });
    function subscribeStateOf(task) {
      const cands = Array.isArray(task.cands) ? task.cands : [];
      if (cands.some((item) => item.pass !== false)) return "hidden";
      const key = normKey(task.number);
      if (!key) return "hidden";
      return subscribedKeys.value.has(key) ? "done" : "ready";
    }
    function clearRow(taskId, site) {
      tables.value.forEach((table) => table?.clearRow(taskId, site));
    }
    function sitePrefix(site) {
      const clean = String(site || "").trim();
      return clean ? `${clean} · ` : "";
    }
    async function refreshTasks() {
      const inflight = props.store.refreshTasks(false);
      t.info("正在刷新…");
      if (!await inflight) {
        t.warning(`任务读取失败：${props.store.error.value || "请稍后重试"}`);
      }
    }
    async function onDownload(payload) {
      const res = await props.store.startDownload(payload.taskId, payload.site, payload.force);
      if (res.kind === "busy") return;
      if (!res.ok) {
        clearRow(payload.taskId, payload.site);
        pushBottomToast("warning", `${sitePrefix(payload.site)}下载失败：${res.message || "请稍后重试"}`);
        return;
      }
      pushBottomToast("success", `已提交下载：${sitePrefix(payload.site)}进度见「下载」页`);
      void props.store.refreshTasks(false);
    }
    function onDownloadTimeout(payload) {
      pushBottomToast("warning", `${sitePrefix(payload.site)}下载提交超时：请刷新任务后重试`);
    }
    async function onCancel(payload) {
      const num = pending.value.filter((item) => String(item.id ?? "") === payload.taskId)[0]?.number || "";
      const res = await props.store.cancelTask(payload.taskId);
      if (res.kind === "busy") return;
      if (!res.ok) {
        t.warning("取消任务失败");
        t.info(res.message || "请稍后重试");
      } else {
        t.warning("已取消任务");
        t.info(`${num ? num + " · " : ""}已从待确认里移除`);
        void props.store.refreshTasks(false);
      }
      tables.value.forEach((table) => table?.clearCanceling(payload.taskId));
    }
    async function onSubscribe(payload) {
      const task = pending.value.filter((item) => String(item.id ?? "") === payload.taskId)[0];
      const number = String(task?.number || "");
      if (!number) {
        t.warning("订阅失败");
        t.info("这条任务缺少番号");
      } else {
        const res = await props.store.subscribeNumber(number, "number", String(task?.actor || ""));
        if (res.kind === "busy") return;
        if (!res.ok) {
          t.warning("订阅失败");
          t.info(res.message || "请稍后重试");
        } else {
          t.success("订阅已创建");
          t.info(`${number} · 有资源时自动下载`);
        }
      }
      tables.value.forEach((table) => table?.clearSubscribing(payload.taskId));
    }
    watch$6(
      pending,
      (items) => {
        if (props.api) queueMissingThumbs(props.api, items);
      },
      { immediate: true }
    );
    let timer = null;
    function startPolling() {
      if (timer !== null) return;
      timer = window.setInterval(() => {
        void props.store.refreshTasks(true);
      }, POLL_MS);
    }
    function stopPolling() {
      if (timer === null) return;
      window.clearInterval(timer);
      timer = null;
    }
    function onVisibilityChange() {
      if (document.visibilityState === "visible") startPolling();
      else stopPolling();
    }
    onMounted$6(() => {
      void props.store.refreshTasks(true);
      if (document.visibilityState === "visible") startPolling();
      document.addEventListener("visibilitychange", onVisibilityChange);
    });
    onBeforeUnmount$5(() => {
      stopPolling();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$c("v-btn");
      return _openBlock$e(), _createElementBlock$e("div", _hoisted_1$d, [
        _createElementVNode$e("div", _hoisted_2$d, [
          _cache[1] || (_cache[1] = _createElementVNode$e("div", { class: "avh-tasks__spacer" }, null, -1)),
          _createVNode$c(_component_v_btn, {
            variant: "outlined",
            size: "small",
            onClick: refreshTasks
          }, {
            default: _withCtx$c(() => _cache[0] || (_cache[0] = [
              _createTextVNode$a("↻ 刷新任务")
            ])),
            _: 1
          })
        ]),
        pending.value.length ? (_openBlock$e(), _createElementBlock$e(_Fragment$b, { key: 0 }, [
          _createElementVNode$e("div", _hoisted_3$b, "待确认（" + _toDisplayString$d(pending.value.length) + "）", 1),
          (_openBlock$e(true), _createElementBlock$e(_Fragment$b, null, _renderList$b(pending.value, (task, index) => {
            return _openBlock$e(), _createBlock$c(CandTable, {
              key: rowKey(task, index),
              ref_for: true,
              ref_key: "tables",
              ref: tables,
              task,
              "plugin-id": _ctx.pluginId,
              "subscribe-state": subscribeStateOf(task),
              cancelable: "",
              onDownload,
              onTimeout: onDownloadTimeout,
              onCancel,
              onSubscribe
            }, null, 8, ["task", "plugin-id", "subscribe-state"]);
          }), 128))
        ], 64)) : (_openBlock$e(), _createBlock$c(EmptyState, {
          key: 1,
          text: "没有待确认的任务"
        }))
      ]);
    };
  }
});

const TasksView = /* @__PURE__ */ _export_sfc(_sfc_main$e, [["__scopeId", "data-v-3735d1a3"]]);

const {defineComponent:_defineComponent$d} = await importShared('vue');

const {toDisplayString:_toDisplayString$c,createElementVNode:_createElementVNode$d,createTextVNode:_createTextVNode$9,resolveComponent:_resolveComponent$b,withCtx:_withCtx$b,createVNode:_createVNode$b,renderList:_renderList$a,Fragment:_Fragment$a,openBlock:_openBlock$d,createElementBlock:_createElementBlock$d,normalizeClass:_normalizeClass$a,createBlock:_createBlock$b} = await importShared('vue');

const _hoisted_1$c = { class: "avh-subs" };
const _hoisted_2$c = { class: "avh-subs__toolbar" };
const _hoisted_3$a = { class: "avh-subs__hint" };
const _hoisted_4$a = { class: "avh-subs__rulecard" };
const _hoisted_5$a = { class: "avh-subs__rulehd" };
const _hoisted_6$a = { class: "avh-subs__hint" };
const _hoisted_7$9 = { class: "avh-subs__rulegrid" };
const _hoisted_8$8 = { class: "avh-subs__rulelabel" };
const _hoisted_9$8 = { key: 0 };
const _hoisted_10$8 = { class: "avh-sub__hd" };
const _hoisted_11$7 = { class: "avh-sub__main" };
const _hoisted_12$7 = { class: "avh-sub__name" };
const _hoisted_13$7 = { class: "avh-subs__hint avh-sub__rule" };
const _hoisted_14$7 = { class: "avh-subs__hint avh-sub__stat" };
const _hoisted_15$6 = { class: "avh-sub__right" };
const {computed: computed$a,ref: ref$d} = await importShared('vue');
const ALL = "";
const _sfc_main$d = /* @__PURE__ */ _defineComponent$d({
  __name: "SubsView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["switch", "refreshSide"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const confirm = useHostConfirm();
    const checking = ref$d("");
    const subs = computed$a(
      () => Array.isArray(props.store.subs.value) ? props.store.subs.value : []
    );
    const hasSubs = computed$a(() => subs.value.length > 0);
    const defaultSummary = computed$a(() => ruleSummary(props.store.rule.value));
    function ruleSummary(raw) {
      const r = raw || {};
      return `${r.res || "1080p"} 优先` + (r.mustCnsub ? " · 必须中字" : "") + (r.preferUncensored ? " · 破解优先" : "") + (r.allow4k ? " · 4K 择优" : "") + ` · 做种≥${r.minSeeders || 0}` + (r.btFallback ? " · BT 兜底" : "") + ` · ${r.trigger === "auto" ? "命中自动下载" : "命中仅通知"}` + ((r.sites || []).length ? ` · 限 ${(r.sites || []).length} 站` : "");
    }
    function subRule(sub) {
      return toRule(sub.rule);
    }
    function lastText(sub) {
      const raw = String(sub.last || sub.created || "");
      return raw ? shortTime(raw) : "—";
    }
    function hitsText(sub) {
      return Number(sub.hits) || 0;
    }
    function typeIcon(sub) {
      return sub.type === "actor" ? "mdi-account" : "mdi-movie-open";
    }
    function rowKey(sub, index) {
      return String(sub.id ?? `${sub.type || ""}:${sub.name || ""}#${index}`);
    }
    function labelOf(sub) {
      return String(sub.name || sub.id || "");
    }
    const RES_LABELS = {
      "1080p": "1080P 优先",
      "2160p": "4K 优先",
      only4k: "仅 4K"
    };
    const resText = computed$a(() => {
      const value = String(props.store.rule.value.res || "1080p");
      return RES_LABELS[value] || value;
    });
    const ruleRows = computed$a(() => {
      const r = props.store.rule.value;
      return [
        { label: "必须中文字幕", text: r.mustCnsub ? "开" : "关", on: !!r.mustCnsub },
        { label: "破解 / 无码版优先", text: r.preferUncensored ? "开" : "关", on: !!r.preferUncensored },
        { label: "允许 4K 择优", text: r.allow4k ? "开" : "关", on: !!r.allow4k },
        { label: "做种数下限", text: `${r.minSeeders || 0} 个`, on: false },
        { label: "PT 搜不到时允许 BT 磁力兜底", text: r.btFallback ? "开" : "关", on: !!r.btFallback },
        {
          label: "命中后自动下载",
          text: r.trigger === "auto" ? "自动下载" : "仅通知",
          on: r.trigger === "auto"
        },
        { label: "每日检查上限", text: `${r.maxPerDay || 6} 次`, on: false },
        {
          label: "搜索站点范围",
          text: (r.sites || []).length ? `限 ${(r.sites || []).length} 站` : "全部站点",
          on: false
        }
      ];
    });
    const checkBusy = computed$a(() => checking.value !== "");
    async function runCheck(name) {
      if (checkBusy.value) return;
      checking.value = name || ALL;
      t.info(name ? `正在检查 ${name}` : "正在检查全部订阅…");
      try {
        const res = await props.store.runCheck(name);
        if (!res.ok) {
          t.warning(`检查失败：${res.message || "请稍后重试"}`);
          return;
        }
        if (res.kind === "limited") {
          t.warning(res.message || "距上次检查不足间隔，已跳过");
        } else {
          t.success("检查完成");
          t.info(res.message || "检查完成");
        }
        emit("refreshSide");
      } finally {
        checking.value = "";
      }
    }
    async function onUnsubscribe(sub) {
      const id = String(sub.id ?? "");
      if (!id) {
        t.warning("取消失败");
        t.info("这条订阅缺少 id，无法删除");
        return;
      }
      const name = labelOf(sub);
      const ok = await confirm({
        type: "warn",
        title: "取消订阅",
        content: `将取消订阅「${name}」，之后的订阅检查不再包含它。此操作不可恢复，需要时得重新订阅。确认继续？`,
        confirmText: "取消订阅",
        cancelText: "先留着"
      });
      if (!ok) return;
      const res = await props.store.unsubscribe(id);
      if (!res.ok) {
        t.warning(res.message || "取消订阅失败，请稍后重试");
        return;
      }
      t.warning("已取消订阅");
      t.info(`id=${id}${name && name !== id ? ` · ${name}` : ""}`);
      emit("refreshSide");
    }
    function goRuleSettings() {
      t.info("规则在「设置台 → 下载规则」里改");
      requestSettingsSection("rule");
      emit("switch");
    }
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$b("v-btn");
      const _component_v_icon = _resolveComponent$b("v-icon");
      return _openBlock$d(), _createElementBlock$d("div", _hoisted_1$c, [
        _createElementVNode$d("div", _hoisted_2$c, [
          _createElementVNode$d("span", _hoisted_3$a, "默认规则：" + _toDisplayString$c(defaultSummary.value), 1),
          _cache[3] || (_cache[3] = _createElementVNode$d("div", { class: "avh-subs__spacer" }, null, -1)),
          _createVNode$b(_component_v_btn, {
            variant: "outlined",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            onClick: goRuleSettings
          }, {
            default: _withCtx$b(() => _cache[1] || (_cache[1] = [
              _createTextVNode$9(" 去设置台改规则 ")
            ])),
            _: 1
          }),
          _createVNode$b(_component_v_btn, {
            variant: "outlined",
            size: "small",
            "prepend-icon": "mdi-lightning-bolt",
            loading: checkBusy.value,
            disabled: checkBusy.value || !hasSubs.value,
            onClick: _cache[0] || (_cache[0] = ($event) => runCheck(ALL))
          }, {
            default: _withCtx$b(() => _cache[2] || (_cache[2] = [
              _createTextVNode$9("检查一次")
            ])),
            _: 1
          }, 8, ["loading", "disabled"])
        ]),
        _createElementVNode$d("div", _hoisted_4$a, [
          _createElementVNode$d("div", _hoisted_5$a, [
            _cache[4] || (_cache[4] = _createElementVNode$d("div", { class: "avh-subs__ruletitle" }, "默认规则（手动搜索与新建订阅的基准）", -1)),
            _createElementVNode$d("div", _hoisted_6$a, "分辨率策略：" + _toDisplayString$c(resText.value), 1),
            _cache[5] || (_cache[5] = _createElementVNode$d("div", { class: "avh-subs__hint" }, "规则在「设置台 → 下载规则」里改", -1))
          ]),
          _createElementVNode$d("div", _hoisted_7$9, [
            (_openBlock$d(true), _createElementBlock$d(_Fragment$a, null, _renderList$a(ruleRows.value, (row) => {
              return _openBlock$d(), _createElementBlock$d("div", {
                key: row.label,
                class: "avh-subs__ruleitem"
              }, [
                _createElementVNode$d("span", _hoisted_8$8, _toDisplayString$c(row.label), 1),
                _createElementVNode$d("span", {
                  class: _normalizeClass$a(["avh-subs__rulevalue", { "avh-subs__rulevalue--on": row.on }])
                }, _toDisplayString$c(row.text), 3)
              ]);
            }), 128))
          ])
        ]),
        hasSubs.value ? (_openBlock$d(), _createElementBlock$d("div", _hoisted_9$8, [
          (_openBlock$d(true), _createElementBlock$d(_Fragment$a, null, _renderList$a(subs.value, (sub, index) => {
            return _openBlock$d(), _createElementBlock$d("div", {
              key: rowKey(sub, index),
              class: "avh-sub"
            }, [
              _createElementVNode$d("div", _hoisted_10$8, [
                _createVNode$b(_component_v_icon, {
                  icon: typeIcon(sub),
                  size: "20",
                  class: "avh-sub__icon"
                }, null, 8, ["icon"]),
                _createElementVNode$d("div", _hoisted_11$7, [
                  _createElementVNode$d("div", _hoisted_12$7, _toDisplayString$c(sub.name), 1),
                  _createElementVNode$d("div", _hoisted_13$7, _toDisplayString$c(ruleSummary(subRule(sub))), 1),
                  _createElementVNode$d("div", _hoisted_14$7, " 命中 " + _toDisplayString$c(hitsText(sub)) + " 次 · 上次检查 " + _toDisplayString$c(lastText(sub)), 1)
                ]),
                _createElementVNode$d("div", _hoisted_15$6, [
                  _createVNode$b(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    loading: checking.value === String(sub.name || ""),
                    disabled: checkBusy.value,
                    onClick: ($event) => runCheck(String(sub.name || ""))
                  }, {
                    default: _withCtx$b(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$9("检查")
                    ])),
                    _: 2
                  }, 1032, ["loading", "disabled", "onClick"]),
                  _createVNode$b(_component_v_btn, {
                    variant: "outlined",
                    color: "error",
                    size: "small",
                    disabled: checkBusy.value,
                    onClick: ($event) => onUnsubscribe(sub)
                  }, {
                    default: _withCtx$b(() => _cache[7] || (_cache[7] = [
                      _createTextVNode$9("取消")
                    ])),
                    _: 2
                  }, 1032, ["disabled", "onClick"])
                ])
              ])
            ]);
          }), 128))
        ])) : (_openBlock$d(), _createBlock$b(EmptyState, {
          key: 1,
          text: "还没有订阅"
        }))
      ]);
    };
  }
});

const SubsView = /* @__PURE__ */ _export_sfc(_sfc_main$d, [["__scopeId", "data-v-1e2afa2f"]]);

const {defineComponent:_defineComponent$c} = await importShared('vue');

const {openBlock:_openBlock$c,createElementBlock:_createElementBlock$c,createCommentVNode:_createCommentVNode$a,createVNode:_createVNode$a,toDisplayString:_toDisplayString$b,createElementVNode:_createElementVNode$c,normalizeClass:_normalizeClass$9} = await importShared('vue');

const _hoisted_1$b = ["title"];
const _hoisted_2$b = {
  key: 0,
  class: "avh-actor__star"
};
const _hoisted_3$9 = { class: "avh-actor__nm" };
const _hoisted_4$9 = {
  key: 1,
  class: "avh-actor__zh"
};
const _hoisted_5$9 = {
  key: 2,
  class: "avh-actor__alias"
};
const _hoisted_6$9 = {
  key: 3,
  class: "avh-actor__tag"
};
const _sfc_main$c = /* @__PURE__ */ _defineComponent$c({
  __name: "ActorRow",
  props: {
    name: {},
    zh: { default: "" },
    alias: { default: "" },
    avatar: { default: "" },
    pluginId: { default: "" },
    favorited: { type: Boolean, default: false },
    picker: { type: Boolean, default: false },
    adding: { type: Boolean, default: false }
  },
  emits: ["select", "add"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    function onSelect() {
      if (props.picker && props.favorited) return;
      if (props.picker) {
        emit("add", props.name);
        return;
      }
      emit("select", props.name);
    }
    return (_ctx, _cache) => {
      return _openBlock$c(), _createElementBlock$c("div", {
        class: _normalizeClass$9(["avh-actor", { "avh-actor--picker": _ctx.picker, "avh-actor--faved": _ctx.picker && _ctx.favorited }]),
        title: _ctx.name,
        onClick: onSelect
      }, [
        !_ctx.picker && _ctx.favorited ? (_openBlock$c(), _createElementBlock$c("div", _hoisted_2$b, "⭐")) : _createCommentVNode$a("", true),
        _createVNode$a(Thumb, {
          class: "avh-actor__av",
          variant: "av",
          src: _ctx.avatar,
          alt: _ctx.name,
          "plugin-id": _ctx.pluginId
        }, null, 8, ["src", "alt", "plugin-id"]),
        _createElementVNode$c("div", _hoisted_3$9, _toDisplayString$b(_ctx.zh || _ctx.name), 1),
        _ctx.zh ? (_openBlock$c(), _createElementBlock$c("div", _hoisted_4$9, _toDisplayString$b(_ctx.name), 1)) : _createCommentVNode$a("", true),
        _ctx.alias ? (_openBlock$c(), _createElementBlock$c("div", _hoisted_5$9, _toDisplayString$b(_ctx.alias), 1)) : _createCommentVNode$a("", true),
        _ctx.picker ? (_openBlock$c(), _createElementBlock$c("div", _hoisted_6$9, [
          _createElementVNode$c("span", {
            class: _normalizeClass$9(["avh-tag", _ctx.favorited ? "avh-tag--on" : ""])
          }, _toDisplayString$b(_ctx.favorited ? "✓ 已收藏" : "➕ 收藏"), 3)
        ])) : _createCommentVNode$a("", true)
      ], 10, _hoisted_1$b);
    };
  }
});

const ActorRow = /* @__PURE__ */ _export_sfc(_sfc_main$c, [["__scopeId", "data-v-a1504c28"]]);

const {defineComponent:_defineComponent$b} = await importShared('vue');

const {createElementVNode:_createElementVNode$b,normalizeClass:_normalizeClass$8,normalizeStyle:_normalizeStyle$3,openBlock:_openBlock$b,createElementBlock:_createElementBlock$b} = await importShared('vue');

const {nextTick: nextTick$3,onBeforeUnmount: onBeforeUnmount$4,onMounted: onMounted$5,ref: ref$c} = await importShared('vue');

const _sfc_main$b = /* @__PURE__ */ _defineComponent$b({
  __name: "BackToTop",
  props: {
    threshold: { default: 260 },
    offset: { default: 18 }
  },
  setup(__props) {
    const props = __props;
    const hostEl = ref$c(null);
    const show = ref$c(false);
    let scroller = null;
    let frame = 0;
    function findScroller(start) {
      let el = start;
      while (el && el !== document.body && el !== document.documentElement) {
        const overflowY = window.getComputedStyle(el).overflowY;
        if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") return el;
        el = el.parentElement;
      }
      return null;
    }
    function active() {
      const winTop = window.scrollY || document.documentElement.scrollTop || 0;
      const inner = scroller;
      if (inner && inner.scrollHeight - inner.clientHeight > 1) {
        if (inner.scrollTop > 0 || winTop <= 0) return { el: inner, top: inner.scrollTop };
      }
      return { el: window, top: winTop };
    }
    function measure() {
      show.value = active().top > props.threshold;
    }
    function onScroll() {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        measure();
      });
    }
    function onResize() {
      detach();
      attach();
    }
    function detach() {
      if (scroller) scroller.removeEventListener("scroll", onScroll);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
    }
    function attach() {
      detach();
      scroller = findScroller(hostEl.value ? hostEl.value.parentElement : null);
      if (scroller) scroller.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onResize, { passive: true });
      measure();
    }
    function toTop() {
      active().el.scrollTo({ top: 0, behavior: "smooth" });
    }
    onMounted$5(() => {
      attach();
      void nextTick$3(measure);
    });
    onBeforeUnmount$4(() => {
      detach();
      if (frame) {
        window.cancelAnimationFrame(frame);
        frame = 0;
      }
    });
    return (_ctx, _cache) => {
      return _openBlock$b(), _createElementBlock$b("div", {
        ref_key: "hostEl",
        ref: hostEl,
        class: _normalizeClass$8(["avh-top", { "avh-top--on": show.value }]),
        style: _normalizeStyle$3({ "--avh-top-bottom": `${_ctx.offset}px` })
      }, [
        _createElementVNode$b("button", {
          type: "button",
          class: "avh-top__btn",
          title: "回到顶部",
          "aria-label": "回到顶部",
          onClick: toTop
        }, _cache[0] || (_cache[0] = [
          _createElementVNode$b("span", {
            class: "avh-top__ico",
            "aria-hidden": "true"
          }, [
            _createElementVNode$b("svg", {
              viewBox: "0 0 24 24",
              width: "17",
              height: "17"
            }, [
              _createElementVNode$b("path", {
                fill: "currentColor",
                d: "M12 4.4 4.6 11.8l1.5 1.5 4.9-4.9V19.6h2V8.4l4.9 4.9 1.5-1.5z"
              })
            ])
          ], -1),
          _createElementVNode$b("span", { class: "avh-top__txt" }, "回到顶部", -1)
        ]))
      ], 6);
    };
  }
});

const BackToTop = /* @__PURE__ */ _export_sfc(_sfc_main$b, [["__scopeId", "data-v-95b525fa"]]);

function cssUrl(value) {
  return String(value || "").replace(/["'()\\\s]/g, (char) => encodeURIComponent(char));
}

const {defineComponent:_defineComponent$a} = await importShared('vue');

const {createTextVNode:_createTextVNode$8,resolveComponent:_resolveComponent$a,withCtx:_withCtx$a,createVNode:_createVNode$9,createElementVNode:_createElementVNode$a,openBlock:_openBlock$a,createElementBlock:_createElementBlock$a,createCommentVNode:_createCommentVNode$9,createBlock:_createBlock$a,toDisplayString:_toDisplayString$a,normalizeClass:_normalizeClass$7,renderList:_renderList$9,Fragment:_Fragment$9,normalizeStyle:_normalizeStyle$2,unref:_unref$4} = await importShared('vue');

const _hoisted_1$a = { class: "avh-actors__toolbar" };
const _hoisted_2$a = {
  key: 0,
  class: "avh-loading"
};
const _hoisted_3$8 = { class: "avh-profile" };
const _hoisted_4$8 = { class: "avh-profile__av" };
const _hoisted_5$8 = { class: "avh-profile__main" };
const _hoisted_6$8 = { class: "avh-profile__name" };
const _hoisted_7$8 = {
  key: 0,
  class: "avh-profile__zh"
};
const _hoisted_8$7 = {
  key: 1,
  class: "avh-profile__alias"
};
const _hoisted_9$7 = { class: "avh-kv" };
const _hoisted_10$7 = { key: 0 };
const _hoisted_11$6 = { key: 1 };
const _hoisted_12$6 = { key: 2 };
const _hoisted_13$6 = { key: 3 };
const _hoisted_14$6 = { key: 4 };
const _hoisted_15$5 = { key: 5 };
const _hoisted_16$5 = { key: 6 };
const _hoisted_17$5 = { class: "avh-acts" };
const _hoisted_18$5 = { class: "avh-secttl" };
const _hoisted_19$5 = {
  key: 0,
  class: "avh-filmyears"
};
const _hoisted_20$5 = ["onClick"];
const _hoisted_21$4 = { class: "avh-filmyears__n" };
const _hoisted_22$4 = { class: "avh-films" };
const _hoisted_23$4 = ["title", "onClick", "onMouseenter"];
const _hoisted_24$3 = { class: "avh-film__ft" };
const _hoisted_25$3 = { class: "avh-film__fn" };
const _hoisted_26$3 = {
  key: 0,
  class: "avh-film__ftt"
};
const _hoisted_27$3 = { class: "avh-film__fd" };
const _hoisted_28$3 = {
  key: 0,
  class: "avh-tag avh-tag--lib"
};
const _hoisted_29$3 = {
  key: 0,
  class: "avh-morebar"
};
const _hoisted_30$3 = {
  key: 1,
  class: "avh-morebar"
};
const _hoisted_31$3 = { class: "avh-hint avh-morebar__tip" };
const _hoisted_32$3 = {
  key: 2,
  class: "avh-morebar"
};
const _hoisted_33$3 = { class: "avh-hint" };
const _hoisted_34$3 = { class: "avh-actors__toolbar" };
const _hoisted_35$3 = { class: "avh-hint" };
const _hoisted_36$3 = { class: "avh-actors" };
const _hoisted_37$3 = { class: "avh-hint" };
const _hoisted_38$3 = {
  key: 0,
  class: "avh-loading"
};
const _hoisted_39$3 = {
  key: 2,
  class: "avh-hint"
};
const _hoisted_40$3 = { class: "avh-actors avh-actors--pick" };
const {computed: computed$9,nextTick: nextTick$2,onUnmounted,reactive: reactive$1,ref: ref$b,watch: watch$5} = await importShared('vue');
const FILM_PAGE = 30;
const FAVS_PAGE_SIZE = 60;
const ALL_LIMIT = 50;
const ALL_MAX_PAGES = 20;
const _sfc_main$a = /* @__PURE__ */ _defineComponent$a({
  __name: "ActorsView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null },
    focusActor: { default: "" }
  },
  emits: ["refreshSide", "openMovie"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const pageCache = reactive$1(/* @__PURE__ */ new Map());
    const rankCache = { error: "", data: null };
    async function apiGet(path, params) {
      const api = props.api;
      if (!api || typeof api.get !== "function") return { ok: false, message: "宿主请求器不可用" };
      try {
        const raw = await api.get(`plugin/${path}`, params ? { params } : void 0);
        const payload = raw && typeof raw === "object" && "success" in raw && "data" in raw ? raw.data : raw;
        if (payload && typeof payload === "object" && payload.success === false) {
          return { ok: false, message: String(payload.message || payload.detail || "接口返回失败") };
        }
        return { ok: true, payload };
      } catch (err) {
        return { ok: false, message: errorText(err) };
      }
    }
    const rootEl = ref$b(null);
    const actor = ref$b("");
    const actorYear = ref$b("");
    const loadingMore = ref$b(false);
    const pageRetrying = ref$b(false);
    const year = computed$9(() => actorYear.value);
    const favs = computed$9(
      () => Array.isArray(props.store.favs.value) ? props.store.favs.value : []
    );
    const hasFavs = computed$9(() => favs.value.length > 0);
    const {
      rows: pagedRows,
      shown: shownRows,
      total: pagedTotal,
      hasMore: hasMoreRows,
      sentinel
    } = usePagedList(favs, { pageSize: FAVS_PAGE_SIZE });
    const pagedHint = computed$9(() => hasMoreRows.value ? `已显示 ${shownRows.value} / ${pagedTotal.value} 位 · 继续下滑自动加载` : `已全部加载（${pagedTotal.value} 位）`);
    function findFav(name) {
      return favs.value.filter((item) => item.name === name)[0] || null;
    }
    function actorAvatarOf(name) {
      const fav = findFav(name);
      if (fav && fav.avatar) return fav.avatar;
      const rank = rankCache.data;
      if (rank) {
        const hit = rank.filter((item) => item.name === name)[0];
        if (hit && hit.avatar) return hit.avatar;
      }
      const page = pageCache.get(`page:actor:${name}`);
      if (page && page.data && page.data.entity && page.data.entity.avatar) return page.data.entity.avatar;
      return "";
    }
    function favAvatar(item) {
      return String(item.avatar || actorAvatarOf(String(item.name || "")));
    }
    const aliases = computed$9(
      () => props.store.aliases && typeof props.store.aliases.value === "object" && props.store.aliases.value ? props.store.aliases.value : {}
    );
    function aliasOf(name) {
      return aliases.value[String(name || "")] || "";
    }
    const aliasDraft = ref$b(null);
    const aliasSaving = ref$b(false);
    function openAliasDialog() {
      if (!actor.value) return;
      aliasDraft.value = aliasOf(actor.value);
    }
    async function saveAlias() {
      const name = actor.value;
      if (!name || aliasDraft.value === null || aliasSaving.value) return;
      aliasSaving.value = true;
      try {
        const res = await props.store.setAlias(name, aliasDraft.value);
        if (!res.ok) {
          t.warning("保存备注失败");
          t.info(res.message || "请稍后重试");
          return;
        }
        t.success(res.message || "已保存备注");
        t.info(name);
        aliasDraft.value = null;
      } finally {
        aliasSaving.value = false;
      }
    }
    async function clearAlias() {
      const name = actor.value;
      if (!name || aliasSaving.value) return;
      aliasDraft.value = "";
      await saveAlias();
    }
    const pageEntry = computed$9(
      () => actor.value ? pageCache.get(`page:actor:${actor.value}`) || null : null
    );
    const pageLoading = computed$9(() => !!actor.value && !pageEntry.value);
    const pageError = computed$9(() => pageEntry.value ? pageEntry.value.error : "");
    const pageData = computed$9(() => pageEntry.value ? pageEntry.value.data : {});
    const entity = computed$9(() => pageData.value.entity || {});
    const movies = computed$9(
      () => Array.isArray(pageData.value.movies) ? pageData.value.movies : []
    );
    const faved = computed$9(() => !!findFav(actor.value));
    const sub = computed$9(
      () => (Array.isArray(props.store.subs.value) ? props.store.subs.value : []).filter(
        (item) => item.type === "actor" && item.name === actor.value
      )[0] || null
    );
    const yearInfo = computed$9(() => {
      const years = [];
      const yearCount = {};
      movies.value.forEach((mv) => {
        const value = String(mv.date || "").slice(0, 4);
        if (/^\d{4}$/.test(value)) {
          if (!yearCount[value]) {
            yearCount[value] = 0;
            years.push(value);
          }
          yearCount[value] += 1;
        }
      });
      return { years, yearCount };
    });
    const list = computed$9(
      () => year.value ? movies.value.filter((mv) => String(mv.date || "").slice(0, 4) === year.value) : movies.value
    );
    const hasMore = computed$9(() => !!pageData.value.hasMore);
    const totalCount = computed$9(() => Number(pageData.value.total || 0) || movies.value.length);
    const filmsTitle = computed$9(() => {
      const loaded = `作品史（按发行时间倒序，已加载 ${movies.value.length} 部`;
      const site = totalCount.value > movies.value.length ? ` / 站点记录 ${totalCount.value} 部` : "";
      const scope = year.value ? `，${year.value} 年 ${list.value.length} 部` : "";
      return `${loaded}${site}${scope}）`;
    });
    const moreLabel = computed$9(
      () => year.value ? `继续加载 ${FILM_PAGE} 部（往更早的年份找）` : `加载更多（已显示 ${movies.value.length} / 共 ${totalCount.value} 部）`
    );
    const filmsEmptyText = computed$9(() => {
      if (!year.value) return "这位演员暂无作品数据。";
      if (hasMore.value) {
        return `已加载的 ${movies.value.length} 部里没有 ${year.value} 年的作品，继续加载试试。`;
      }
      return "该年份没有作品记录。";
    });
    async function loadPage(name, force = false) {
      const key = `page:actor:${name}`;
      if (!force && pageCache.has(key)) return;
      const res = await apiGet("actor", { name, page: 1, limit: FILM_PAGE });
      if (!res.ok) {
        pageCache.set(key, { error: res.message || "抓取失败，请稍后重试", data: {} });
        t.warning("演员抓取失败");
        t.info(res.message || "抓取失败，请稍后重试");
        return;
      }
      pageCache.set(key, { error: "", data: res.payload || {} });
    }
    function openActor(name) {
      const target = String(name || "");
      if (!target) return;
      actor.value = target;
      actorYear.value = "";
      allCapped.value = false;
      void loadPage(target);
      void nextTick$2(() => rootEl.value?.scrollIntoView({ block: "start" }));
    }
    function backToList() {
      actor.value = "";
    }
    watch$5(
      [actor, aliases],
      () => {
        if (aliasDraft.value === null) return;
        aliasDraft.value = aliasOf(actor.value);
      },
      { flush: "sync" }
    );
    async function retryPage() {
      const name = actor.value;
      if (!name) return;
      pageRetrying.value = true;
      allCapped.value = false;
      try {
        pageCache.delete(`page:actor:${name}`);
        await loadPage(name, true);
      } finally {
        pageRetrying.value = false;
      }
    }
    function pickYear(value) {
      actorYear.value = value;
    }
    function yearCountOf(items, target) {
      return items.filter((mv) => String(mv.date || "").slice(0, 4) === target).length;
    }
    async function loadMoreFilms() {
      const name = actor.value;
      const entry = pageEntry.value;
      if (!name || !entry || loadingMore.value || allLoading.value) return;
      const data = entry.data || {};
      const limit = Number(data.limit) || FILM_PAGE;
      const page = (Number(data.page) || 1) + 1;
      const before = year.value ? yearCountOf(movies.value, year.value) : 0;
      loadingMore.value = true;
      try {
        const res = await apiGet("actor", { name, page, limit });
        if (!res.ok) {
          t.warning("加载更多失败");
          t.info(res.message || "请稍后重试");
          return;
        }
        const next = res.payload || {};
        const base = Array.isArray(data.movies) ? data.movies : [];
        const seen = {};
        base.forEach((x) => {
          seen[`${x.id || ""}|${x.number || ""}`] = true;
        });
        const add = (next.movies || []).filter((x) => !seen[`${x.id || ""}|${x.number || ""}`]);
        data.movies = base.concat(add);
        data.page = page;
        data.hasMore = !!next.hasMore;
        data.total = next.total || data.total;
        data.entity = next.entity || data.entity;
        allCapped.value = false;
        if (actor.value !== name) return;
        if (year.value && yearCountOf(data.movies, year.value) === before) {
          t.warning("继续加载");
          t.info(`这一批没有 ${year.value} 年的作品，已加载 ${data.movies.length} 部`);
        }
      } finally {
        loadingMore.value = false;
      }
    }
    const allLoading = ref$b(false);
    const allStop = ref$b(false);
    const allPages = ref$b(0);
    const allCapped = ref$b(false);
    const allLabel = computed$9(() => {
      const loaded = movies.value.length;
      const total = totalCount.value;
      if (allLoading.value) {
        return total > loaded ? `⏸ 停止（已加载 ${loaded} / ${total} 部）` : `⏸ 停止（已加载 ${loaded} 部）`;
      }
      if (total > loaded) return `⏬ 加载全部（还有 ${total - loaded} 部）`;
      return "⏬ 加载全部";
    });
    async function loadAllFilms() {
      const name = actor.value;
      const entry = pageEntry.value;
      if (!name || !entry || loadingMore.value) return;
      if (allLoading.value) {
        allStop.value = true;
        return;
      }
      const data = entry.data || {};
      const loadedLimit = Number(data.limit) || FILM_PAGE;
      const loadedPage = Number(data.page) || 1;
      const resume = loadedLimit === ALL_LIMIT && loadedPage >= 1 && movies.value.length > 0;
      let page = resume ? loadedPage + 1 : 1;
      const acc = movies.value.slice();
      const seen = {};
      acc.forEach((mv) => {
        seen[`${mv.id || ""}|${mv.number || ""}`] = true;
      });
      let stopped = false;
      allLoading.value = true;
      allStop.value = false;
      allCapped.value = false;
      allPages.value = 0;
      try {
        for (let i = 0; i < ALL_MAX_PAGES; i++) {
          const res = await apiGet("actor", { name, page, limit: ALL_LIMIT });
          if (!res.ok) {
            t.warning(allPages.value ? "「加载全部」中断" : "「加载全部」失败");
            t.info(res.message || "请稍后重试");
            break;
          }
          const next = res.payload || {};
          const items = Array.isArray(next.movies) ? next.movies : [];
          items.forEach((mv) => {
            const key = `${mv.id || ""}|${mv.number || ""}`;
            if (!seen[key]) {
              seen[key] = true;
              acc.push(mv);
            }
          });
          data.movies = acc.slice();
          data.limit = ALL_LIMIT;
          data.page = page;
          data.total = Number(next.total || 0) || data.total;
          data.entity = next.entity || data.entity;
          data.hasMore = !!next.hasMore;
          allPages.value = i + 1;
          if (!items.length || !next.hasMore) break;
          if (allStop.value) {
            stopped = true;
            break;
          }
          if (actor.value !== name) break;
          if (allPages.value >= ALL_MAX_PAGES) {
            allCapped.value = true;
            break;
          }
          page += 1;
        }
      } finally {
        allLoading.value = false;
        allStop.value = false;
      }
      if (actor.value !== name) return;
      if (stopped) t.info(`已停止，共加载 ${acc.length} 部`);
      if (allCapped.value) {
        t.info(`已一次拉满 ${ALL_MAX_PAGES * ALL_LIMIT} 部（与 javdb-cli 的 --all 同口径），再点「加载全部」可以继续`);
      }
    }
    async function setFav(name, zh, avatar, next) {
      if (next) {
        const res2 = await props.store.addFav(name, zh, avatar);
        if (!res2.ok) {
          t.warning("收藏失败");
          t.info(res2.message || "请稍后重试");
          return false;
        }
        t.success("已收藏");
        t.info(`${name} 会出现在「我的演员」里`);
        emit("refreshSide");
        return true;
      }
      const res = await props.store.delFav(name);
      if (!res.ok) {
        t.warning("取消收藏失败");
        t.info(res.message || "请稍后重试");
        return false;
      }
      t.warning("已取消收藏");
      t.info(name);
      emit("refreshSide");
      return true;
    }
    async function toggleFav() {
      const name = actor.value;
      if (!name) return;
      const wasFav = !!findFav(name);
      const avatar = String(entity.value.avatar || "") || actorAvatarOf(name);
      await setFav(name, String(entity.value.zh || ""), avatar, !wasFav);
    }
    const subscribing = ref$b(false);
    async function subscribeActor() {
      const name = actor.value;
      if (!name || sub.value || subscribing.value) return;
      subscribing.value = true;
      t.info("按「设置台 → 下载规则」的默认规则订阅该演员的新片");
      try {
        const res = await props.store.subscribeNumber(name, "actor");
        if (!res.ok) {
          t.warning("订阅失败");
          t.info(res.message || "请稍后重试");
          return;
        }
        if (!findFav(name)) {
          await props.store.addFav(name, String(entity.value.zh || ""), String(entity.value.avatar || ""));
        }
        t.success("订阅已创建");
        t.info(`${name} · 在「订阅」栏里可以看到它`);
        emit("refreshSide");
      } finally {
        subscribing.value = false;
      }
    }
    const checking = ref$b(false);
    async function checkActor() {
      const name = actor.value;
      if (!name || checking.value) return;
      checking.value = true;
      t.info(`正在检查 ${name}`);
      try {
        const res = await props.store.runCheck(name);
        if (!res.ok) {
          t.warning(`检查失败：${res.message || "请稍后重试"}`);
          return;
        }
        if (res.kind === "limited") {
          t.warning(res.message || "距上次检查不足间隔，已跳过");
        } else {
          t.success("检查完成");
          t.info(res.message || "检查完成");
        }
        emit("refreshSide");
      } finally {
        checking.value = false;
      }
    }
    function picStyle(mv) {
      if (!mv.thumb) return void 0;
      return { "--bg": `url('${cssUrl(mv.thumb)}')` };
    }
    function filmKey(mv, index) {
      return `${mv.number || ""}#${index}`;
    }
    function openFilm(mv) {
      const num = String(mv.number || "");
      if (!num) return;
      emit("openMovie", { number: num, id: String(mv.id || "") });
    }
    const prefetcher = createDetailPrefetcher(() => props.api);
    function prefetchFilm(mv) {
      prefetcher.enqueue(mv.number, mv.id);
    }
    watch$5(
      list,
      (items) => prefetcher.enqueueMany(items, PREFETCH_N),
      { immediate: true }
    );
    watch$5(actor, () => prefetcher.flush());
    onUnmounted(() => prefetcher.flush());
    watch$5(
      () => favs.value.map((item) => favAvatar(item)).join("\n"),
      () => favs.value.forEach((item) => warmImage(favAvatar(item))),
      { immediate: true }
    );
    const pickerOpen = ref$b(false);
    const pickerLoading = ref$b(false);
    const pickerError = ref$b("");
    const pickerRows = ref$b([]);
    const pickerAdded = ref$b([]);
    const addingName = ref$b("");
    function pickerFaved(name) {
      return pickerAdded.value.indexOf(name) >= 0 || !!findFav(name);
    }
    async function loadRank(force) {
      if (!force && rankCache.data) {
        pickerRows.value = rankCache.data.slice();
        return;
      }
      pickerLoading.value = true;
      pickerError.value = "";
      const res = await apiGet("actors");
      pickerLoading.value = false;
      if (!res.ok) {
        const message = res.message || "演员榜抓取失败，请稍后重试";
        rankCache.data = null;
        rankCache.error = message;
        pickerError.value = message;
        t.warning("演员榜抓取失败");
        t.info(res.message || "请稍后重试");
        return;
      }
      const payload = res.payload || {};
      const rawList = Array.isArray(payload.actors) ? payload.actors : Array.isArray(payload.data && payload.data.actors) ? payload.data.actors : [];
      const rankList = rawList.filter((item) => item && typeof item === "object").map((item) => ({
        name: String(item.name || ""),
        zh: String(item.zh || ""),
        avatar: String(item.avatar || "")
      })).filter((item) => !!item.name);
      rankCache.error = "";
      rankCache.data = rankList;
      pickerRows.value = rankList.filter((item) => !findFav(item.name));
    }
    async function openPicker() {
      pickerOpen.value = true;
      pickerAdded.value = [];
      await loadRank(false);
    }
    async function retryRank() {
      rankCache.data = null;
      rankCache.error = "";
      pickerAdded.value = [];
      await loadRank(true);
    }
    async function pickAdd(row) {
      const name = String(row.name || "");
      if (!name || pickerFaved(name) || addingName.value) return;
      addingName.value = name;
      try {
        const ok = await setFav(name, String(row.zh || ""), String(row.avatar || ""), true);
        if (ok) pickerAdded.value = [...pickerAdded.value, name];
      } finally {
        addingName.value = "";
      }
    }
    watch$5(
      () => props.focusActor,
      (name) => {
        if (name) openActor(name);
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$a("v-btn");
      const _component_v_card_title = _resolveComponent$a("v-card-title");
      const _component_v_card_text = _resolveComponent$a("v-card-text");
      const _component_v_spacer = _resolveComponent$a("v-spacer");
      const _component_v_card_actions = _resolveComponent$a("v-card-actions");
      const _component_v_card = _resolveComponent$a("v-card");
      const _component_v_dialog = _resolveComponent$a("v-dialog");
      const _component_v_text_field = _resolveComponent$a("v-text-field");
      return _openBlock$a(), _createElementBlock$a("div", {
        ref_key: "rootEl",
        ref: rootEl,
        class: "avh-actors-view"
      }, [
        actor.value ? (_openBlock$a(), _createElementBlock$a(_Fragment$9, { key: 0 }, [
          _createElementVNode$a("div", _hoisted_1$a, [
            _createVNode$9(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: backToList
            }, {
              default: _withCtx$a(() => _cache[6] || (_cache[6] = [
                _createTextVNode$8("← 返回")
              ])),
              _: 1
            })
          ]),
          pageLoading.value ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_2$a, "正在抓取演员档案与作品史…")) : pageError.value ? (_openBlock$a(), _createBlock$a(ErrorState, {
            key: 1,
            message: pageError.value,
            retrying: pageRetrying.value,
            onRetry: retryPage
          }, null, 8, ["message", "retrying"])) : (_openBlock$a(), _createElementBlock$a(_Fragment$9, { key: 2 }, [
            _createElementVNode$a("div", _hoisted_3$8, [
              _createElementVNode$a("div", _hoisted_4$8, [
                _createVNode$9(Thumb, {
                  src: entity.value.avatar,
                  alt: actor.value,
                  "plugin-id": _ctx.pluginId
                }, null, 8, ["src", "alt", "plugin-id"])
              ]),
              _createElementVNode$a("div", _hoisted_5$8, [
                _createElementVNode$a("h2", _hoisted_6$8, _toDisplayString$a(entity.value.zh || entity.value.name || actor.value), 1),
                entity.value.zh ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_7$8, _toDisplayString$a(entity.value.name || actor.value), 1)) : _createCommentVNode$9("", true),
                aliasOf(actor.value) ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_8$7, _toDisplayString$a(aliasOf(actor.value)), 1)) : _createCommentVNode$9("", true),
                _createElementVNode$a("div", _hoisted_9$7, [
                  entity.value.videos_count ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_10$7, [
                    _cache[7] || (_cache[7] = _createElementVNode$a("b", null, "作品", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.videos_count), 1)
                  ])) : _createCommentVNode$9("", true),
                  entity.value.age ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_11$6, [
                    _cache[8] || (_cache[8] = _createElementVNode$a("b", null, "年龄", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.age), 1)
                  ])) : _createCommentVNode$9("", true),
                  entity.value.birthday ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_12$6, [
                    _cache[9] || (_cache[9] = _createElementVNode$a("b", null, "生日", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.birthday), 1)
                  ])) : _createCommentVNode$9("", true),
                  entity.value.height ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_13$6, [
                    _cache[10] || (_cache[10] = _createElementVNode$a("b", null, "身高", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.height) + "cm", 1)
                  ])) : _createCommentVNode$9("", true),
                  entity.value.cup ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_14$6, [
                    _cache[11] || (_cache[11] = _createElementVNode$a("b", null, "罩杯", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.cup), 1)
                  ])) : _createCommentVNode$9("", true),
                  entity.value.birthplace ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_15$5, [
                    _cache[12] || (_cache[12] = _createElementVNode$a("b", null, "出身", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.birthplace), 1)
                  ])) : _createCommentVNode$9("", true),
                  entity.value.instagram ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_16$5, [
                    _cache[13] || (_cache[13] = _createElementVNode$a("b", null, "IG", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(entity.value.instagram), 1)
                  ])) : _createCommentVNode$9("", true),
                  _createElementVNode$a("span", null, [
                    _cache[14] || (_cache[14] = _createElementVNode$a("b", null, "本次返回作品", -1)),
                    _createTextVNode$8(" " + _toDisplayString$a(movies.value.length) + " 部", 1)
                  ])
                ]),
                _createElementVNode$a("div", _hoisted_17$5, [
                  _createVNode$9(_component_v_btn, {
                    color: faved.value ? void 0 : "primary",
                    variant: faved.value ? "outlined" : "flat",
                    size: "small",
                    onClick: toggleFav
                  }, {
                    default: _withCtx$a(() => [
                      _createTextVNode$8(_toDisplayString$a(faved.value ? "★ 已收藏" : "☆ 收藏该演员"), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "variant"]),
                  _createVNode$9(_component_v_btn, {
                    color: sub.value ? void 0 : "primary",
                    variant: sub.value ? "outlined" : "flat",
                    size: "small",
                    loading: subscribing.value,
                    disabled: !!sub.value || subscribing.value,
                    onClick: subscribeActor
                  }, {
                    default: _withCtx$a(() => [
                      _createTextVNode$8(_toDisplayString$a(sub.value ? "✓ 已订阅新片" : "📌 订阅该演员的新片"), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "variant", "loading", "disabled"]),
                  _createVNode$9(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    loading: checking.value,
                    onClick: checkActor
                  }, {
                    default: _withCtx$a(() => _cache[15] || (_cache[15] = [
                      _createTextVNode$8(" ⚡ 检查她的新片 ")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode$9(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    onClick: openAliasDialog
                  }, {
                    default: _withCtx$a(() => _cache[16] || (_cache[16] = [
                      _createTextVNode$8("✎ 备注")
                    ])),
                    _: 1
                  })
                ])
              ])
            ]),
            _createElementVNode$a("div", _hoisted_18$5, _toDisplayString$a(filmsTitle.value), 1),
            yearInfo.value.years.length > 1 ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_19$5, [
              _createElementVNode$a("button", {
                type: "button",
                class: _normalizeClass$7({ "avh-filmyears__on": !year.value }),
                onClick: _cache[0] || (_cache[0] = ($event) => pickYear(""))
              }, "全部 " + _toDisplayString$a(movies.value.length) + _toDisplayString$a(hasMore.value ? "+" : ""), 3),
              (_openBlock$a(true), _createElementBlock$a(_Fragment$9, null, _renderList$9(yearInfo.value.years, (y) => {
                return _openBlock$a(), _createElementBlock$a("button", {
                  key: y,
                  type: "button",
                  class: _normalizeClass$7({ "avh-filmyears__on": year.value === y }),
                  onClick: ($event) => pickYear(y)
                }, [
                  _createTextVNode$8(_toDisplayString$a(y), 1),
                  _createElementVNode$a("span", _hoisted_21$4, _toDisplayString$a(" " + yearInfo.value.yearCount[y]), 1)
                ], 10, _hoisted_20$5);
              }), 128))
            ])) : _createCommentVNode$9("", true),
            list.value.length ? (_openBlock$a(), _createElementBlock$a(_Fragment$9, { key: 1 }, [
              _createElementVNode$a("div", _hoisted_22$4, [
                (_openBlock$a(true), _createElementBlock$a(_Fragment$9, null, _renderList$9(list.value, (mv, index) => {
                  return _openBlock$a(), _createElementBlock$a("div", {
                    key: filmKey(mv, index),
                    class: "avh-film",
                    title: mv.title || mv.number || "",
                    onClick: ($event) => openFilm(mv),
                    onMouseenter: ($event) => prefetchFilm(mv)
                  }, [
                    _createElementVNode$a("div", {
                      class: "avh-film__pic",
                      style: _normalizeStyle$2(picStyle(mv))
                    }, [
                      _createVNode$9(Thumb, {
                        variant: "film",
                        src: mv.thumb,
                        alt: mv.number || "",
                        "plugin-id": _ctx.pluginId
                      }, null, 8, ["src", "alt", "plugin-id"])
                    ], 4),
                    _createElementVNode$a("div", _hoisted_24$3, [
                      _createElementVNode$a("div", _hoisted_25$3, _toDisplayString$a(mv.number || ""), 1),
                      mv.title ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_26$3, _toDisplayString$a(mv.title), 1)) : _createCommentVNode$9("", true),
                      _createElementVNode$a("div", _hoisted_27$3, [
                        _createElementVNode$a("span", null, _toDisplayString$a(mv.date || ""), 1),
                        _createElementVNode$a("span", {
                          class: _normalizeClass$7(["avh-tag", { "avh-tag--on": !!mv.cnsub }])
                        }, _toDisplayString$a(mv.cnsub ? "中字" : "无中字"), 3),
                        _createElementVNode$a("span", null, "🧲 " + _toDisplayString$a(mv.magnets || 0), 1),
                        mv.lib ? (_openBlock$a(), _createElementBlock$a("span", _hoisted_28$3, "已入库")) : _createCommentVNode$9("", true)
                      ])
                    ])
                  ], 40, _hoisted_23$4);
                }), 128))
              ]),
              hasMore.value ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_29$3, [
                _createVNode$9(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  loading: loadingMore.value,
                  disabled: allLoading.value,
                  onClick: loadMoreFilms
                }, {
                  default: _withCtx$a(() => [
                    _createTextVNode$8(_toDisplayString$a(moreLabel.value), 1)
                  ]),
                  _: 1
                }, 8, ["loading", "disabled"]),
                _createVNode$9(_component_v_btn, {
                  variant: allLoading.value ? "outlined" : "tonal",
                  color: allLoading.value ? "warning" : "primary",
                  size: "small",
                  disabled: loadingMore.value,
                  onClick: loadAllFilms
                }, {
                  default: _withCtx$a(() => [
                    _createTextVNode$8(_toDisplayString$a(allLabel.value), 1)
                  ]),
                  _: 1
                }, 8, ["variant", "color", "disabled"])
              ])) : _createCommentVNode$9("", true),
              allCapped.value ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_30$3, [
                _createElementVNode$a("span", _hoisted_31$3, " 已一次拉满 " + _toDisplayString$a(ALL_MAX_PAGES * ALL_LIMIT) + " 部（与 javdb-cli 的 --all 同口径）， 再点一次「加载全部」可以接着往下拉。 ", 1)
              ])) : !hasMore.value && movies.value.length > FILM_PAGE ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_32$3, [
                _createElementVNode$a("span", _hoisted_33$3, "已加载全部 " + _toDisplayString$a(movies.value.length) + " 部", 1)
              ])) : _createCommentVNode$9("", true)
            ], 64)) : (_openBlock$a(), _createBlock$a(EmptyState, {
              key: 2,
              text: filmsEmptyText.value
            }, null, 8, ["text"]))
          ], 64))
        ], 64)) : (_openBlock$a(), _createElementBlock$a(_Fragment$9, { key: 1 }, [
          hasFavs.value ? (_openBlock$a(), _createElementBlock$a(_Fragment$9, { key: 0 }, [
            _createElementVNode$a("div", _hoisted_34$3, [
              _createElementVNode$a("span", _hoisted_35$3, "共 " + _toDisplayString$a(favs.value.length) + " 位", 1),
              _cache[18] || (_cache[18] = _createElementVNode$a("div", { class: "avh-actors__spacer" }, null, -1)),
              _createVNode$9(_component_v_btn, {
                variant: "outlined",
                size: "small",
                onClick: openPicker
              }, {
                default: _withCtx$a(() => _cache[17] || (_cache[17] = [
                  _createTextVNode$8("➕ 添加演员")
                ])),
                _: 1
              })
            ]),
            _createElementVNode$a("div", _hoisted_36$3, [
              (_openBlock$a(true), _createElementBlock$a(_Fragment$9, null, _renderList$9(_unref$4(pagedRows), (item) => {
                return _openBlock$a(), _createBlock$a(ActorRow, {
                  key: item.name,
                  favorited: "",
                  name: String(item.name || ""),
                  zh: item.zh || "",
                  avatar: favAvatar(item),
                  "plugin-id": _ctx.pluginId,
                  alias: aliasOf(String(item.name || "")),
                  onSelect: openActor
                }, null, 8, ["name", "zh", "avatar", "plugin-id", "alias"]);
              }), 128))
            ]),
            _createElementVNode$a("div", {
              ref_key: "sentinel",
              ref: sentinel,
              class: "avh-actors__more"
            }, [
              _createElementVNode$a("span", _hoisted_37$3, _toDisplayString$a(pagedHint.value), 1)
            ], 512)
          ], 64)) : (_openBlock$a(), _createBlock$a(EmptyState, {
            key: 1,
            text: "还没有收藏演员"
          }, {
            default: _withCtx$a(() => [
              _createVNode$9(_component_v_btn, {
                color: "primary",
                variant: "flat",
                onClick: openPicker
              }, {
                default: _withCtx$a(() => _cache[19] || (_cache[19] = [
                  _createTextVNode$8("➕ 从演员榜挑选")
                ])),
                _: 1
              })
            ]),
            _: 1
          }))
        ], 64)),
        _createVNode$9(_component_v_dialog, {
          modelValue: pickerOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickerOpen.value = $event),
          "max-width": "880",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$a(() => [
            _createVNode$9(_component_v_card, null, {
              default: _withCtx$a(() => [
                _createVNode$9(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$a(() => _cache[20] || (_cache[20] = [
                    _createTextVNode$8("从演员榜挑选")
                  ])),
                  _: 1
                }),
                _createVNode$9(_component_v_card_text, null, {
                  default: _withCtx$a(() => [
                    pickerLoading.value ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_38$3, "正在抓取演员榜…")) : pickerError.value ? (_openBlock$a(), _createBlock$a(ErrorState, {
                      key: 1,
                      message: pickerError.value,
                      retrying: pickerLoading.value,
                      onRetry: retryRank
                    }, null, 8, ["message", "retrying"])) : !pickerRows.value.length ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_39$3, "演员榜里的人都已收藏。")) : (_openBlock$a(), _createElementBlock$a(_Fragment$9, { key: 3 }, [
                      _cache[21] || (_cache[21] = _createElementVNode$a("div", { class: "avh-actorpick__tip avh-hint" }, "点 ➕ 加入收藏", -1)),
                      _createElementVNode$a("div", _hoisted_40$3, [
                        (_openBlock$a(true), _createElementBlock$a(_Fragment$9, null, _renderList$9(pickerRows.value, (row) => {
                          return _openBlock$a(), _createBlock$a(ActorRow, {
                            key: row.name,
                            picker: "",
                            name: String(row.name || ""),
                            zh: row.zh || "",
                            avatar: row.avatar || "",
                            "plugin-id": _ctx.pluginId,
                            favorited: pickerFaved(String(row.name || "")),
                            adding: addingName.value === String(row.name || ""),
                            onAdd: ($event) => pickAdd(row)
                          }, null, 8, ["name", "zh", "avatar", "plugin-id", "favorited", "adding", "onAdd"]);
                        }), 128))
                      ])
                    ], 64))
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_actions, null, {
                  default: _withCtx$a(() => [
                    _createVNode$9(_component_v_spacer),
                    _createVNode$9(_component_v_btn, {
                      color: "error",
                      variant: "outlined",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickerOpen.value = false)
                    }, {
                      default: _withCtx$a(() => _cache[22] || (_cache[22] = [
                        _createTextVNode$8("关闭")
                      ])),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        actor.value ? (_openBlock$a(), _createBlock$a(BackToTop, { key: 2 })) : _createCommentVNode$9("", true),
        _createVNode$9(_component_v_dialog, {
          "model-value": aliasDraft.value !== null,
          "max-width": "460",
          attach: "body",
          "onUpdate:modelValue": _cache[5] || (_cache[5] = (value) => {
            if (!value) aliasDraft.value = null;
          })
        }, {
          default: _withCtx$a(() => [
            _createVNode$9(_component_v_card, null, {
              default: _withCtx$a(() => [
                _createVNode$9(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$a(() => [
                    _createTextVNode$8("备注：" + _toDisplayString$a(actor.value), 1)
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_text, null, {
                  default: _withCtx$a(() => [
                    _createVNode$9(_component_v_text_field, {
                      "model-value": aliasDraft.value ?? "",
                      label: "备注名",
                      placeholder: "例如：桥本有菜",
                      variant: "outlined",
                      density: "comfortable",
                      autofocus: "",
                      "hide-details": "",
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => aliasDraft.value = String(value ?? ""))
                    }, null, 8, ["model-value"]),
                    _cache[23] || (_cache[23] = _createElementVNode$a("div", {
                      class: "avh-hint",
                      style: { "margin-top": "8px" }
                    }, " 只影响界面显示，原名不变；清空后保存即等于清除备注。 ", -1))
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_actions, null, {
                  default: _withCtx$a(() => [
                    _createVNode$9(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      disabled: aliasSaving.value || !aliasOf(actor.value),
                      onClick: clearAlias
                    }, {
                      default: _withCtx$a(() => _cache[24] || (_cache[24] = [
                        _createTextVNode$8("清除")
                      ])),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode$9(_component_v_spacer),
                    _createVNode$9(_component_v_btn, {
                      variant: "outlined",
                      onClick: _cache[4] || (_cache[4] = ($event) => aliasDraft.value = null)
                    }, {
                      default: _withCtx$a(() => _cache[25] || (_cache[25] = [
                        _createTextVNode$8("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$9(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      loading: aliasSaving.value,
                      onClick: saveAlias
                    }, {
                      default: _withCtx$a(() => _cache[26] || (_cache[26] = [
                        _createTextVNode$8("保存")
                      ])),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["model-value"])
      ], 512);
    };
  }
});

const ActorsView = /* @__PURE__ */ _export_sfc(_sfc_main$a, [["__scopeId", "data-v-2c9a2e8e"]]);

const {defineComponent:_defineComponent$9} = await importShared('vue');

const {createTextVNode:_createTextVNode$7,resolveComponent:_resolveComponent$9,withCtx:_withCtx$9,createVNode:_createVNode$8,toDisplayString:_toDisplayString$9,createElementVNode:_createElementVNode$9,openBlock:_openBlock$9,createBlock:_createBlock$9,createCommentVNode:_createCommentVNode$8,createElementBlock:_createElementBlock$9,Fragment:_Fragment$8,renderList:_renderList$8,normalizeClass:_normalizeClass$6,normalizeStyle:_normalizeStyle$1,unref:_unref$3} = await importShared('vue');

const _hoisted_1$9 = { class: "avh-actlib" };
const _hoisted_2$9 = { class: "avh-actlib__toolbar" };
const _hoisted_3$7 = { class: "avh-actlib__hint" };
const _hoisted_4$7 = {
  key: 1,
  class: "avh-actlib__loading"
};
const _hoisted_5$7 = { class: "avh-actlib__head" };
const _hoisted_6$7 = { class: "avh-actlib__names" };
const _hoisted_7$7 = { class: "avh-actlib__nm" };
const _hoisted_8$6 = {
  key: 0,
  class: "avh-actlib__sub"
};
const _hoisted_9$6 = {
  key: 1,
  class: "avh-actlib__sub"
};
const _hoisted_10$6 = { class: "avh-actlib__detail" };
const _hoisted_11$5 = { class: "avh-actlib__gallery" };
const _hoisted_12$5 = {
  key: 0,
  class: "avh-actlib__stage"
};
const _hoisted_13$5 = { class: "avh-actlib__badge" };
const _hoisted_14$5 = {
  key: 0,
  class: "avh-actlib__badge avh-actlib__badge--primary"
};
const _hoisted_15$4 = {
  key: 2,
  class: "avh-actlib__strip"
};
const _hoisted_16$4 = ["title", "onClick"];
const _hoisted_17$4 = { class: "avh-actlib__ops" };
const _hoisted_18$4 = { class: "avh-actlib__row mb-2" };
const _hoisted_19$4 = { class: "avh-actlib__row mb-2" };
const _hoisted_20$4 = { class: "avh-actlib__cropbox" };
const _hoisted_21$3 = { class: "avh-actlib__row mb-1" };
const _hoisted_22$3 = { class: "avh-actlib__hint" };
const _hoisted_23$3 = { class: "text-caption text-medium-emphasis mb-2" };
const _hoisted_24$2 = {
  key: 2,
  class: "text-caption text-medium-emphasis mb-0"
};
const _hoisted_25$2 = { class: "avh-actlib__fields" };
const _hoisted_26$2 = { class: "avh-actlib__field" };
const _hoisted_27$2 = { class: "avh-actlib__field" };
const _hoisted_28$2 = { class: "avh-actlib__field" };
const _hoisted_29$2 = { class: "avh-actlib__field" };
const _hoisted_30$2 = { class: "avh-actlib__field" };
const _hoisted_31$2 = { class: "avh-actlib__field" };
const _hoisted_32$2 = { class: "avh-actlib__field" };
const _hoisted_33$2 = { class: "avh-actlib__field" };
const _hoisted_34$2 = { class: "avh-actlib__section" };
const _hoisted_35$2 = { class: "text-caption text-medium-emphasis mb-1" };
const _hoisted_36$2 = {
  key: 0,
  class: "avh-actlib__chips"
};
const _hoisted_37$2 = {
  key: 1,
  class: "text-caption text-medium-emphasis mb-0"
};
const _hoisted_38$2 = { class: "avh-actlib__section" };
const _hoisted_39$2 = { class: "text-caption text-medium-emphasis mb-1" };
const _hoisted_40$2 = {
  key: 0,
  class: "avh-actlib__history"
};
const _hoisted_41$2 = { class: "avh-actlib__hint" };
const _hoisted_42$2 = { class: "avh-actlib__hint" };
const _hoisted_43$2 = {
  key: 1,
  class: "text-caption text-medium-emphasis mb-0"
};
const _hoisted_44$2 = { class: "avh-actlib__toolbar" };
const _hoisted_45$1 = {
  key: 0,
  class: "avh-actlib__stats"
};
const _hoisted_46$1 = { class: "avh-actlib__hint" };
const _hoisted_47$1 = {
  key: 2,
  class: "avh-actlib__loading"
};
const _hoisted_48$1 = { class: "avh-actlib__grid" };
const _hoisted_49$1 = {
  key: 0,
  class: "avh-actlib__abadge"
};
const _hoisted_50$1 = {
  key: 1,
  class: "avh-actlib__abadge avh-actlib__abadge--lock"
};
const _hoisted_51$1 = { class: "avh-actlib__hint" };
const {computed: computed$8,onMounted: onMounted$4,ref: ref$a} = await importShared('vue');
const ACTOR_PAGE_SIZE = 60;
const FETCH_LIMIT = 200;
const _sfc_main$9 = /* @__PURE__ */ _defineComponent$9({
  __name: "ActorLibraryView",
  props: {
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null },
    store: { default: null }
  },
  emits: ["refreshSide"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const confirm = useHostConfirm();
    function textOf(value) {
      return value === null || value === void 0 ? "" : String(value);
    }
    async function getJson(path, params) {
      const api = props.api;
      if (!api || typeof api.get !== "function") throw new Error("宿主 api 不可用");
      const payload = unwrap(await api.get(path, params ? { params } : void 0));
      if (payload && typeof payload === "object" && payload.success === false) {
        throw new Error(textOf(payload.message) || "接口返回失败");
      }
      return payload;
    }
    async function postJson(path, body) {
      const api = props.api;
      if (!api || typeof api.post !== "function") throw new Error("宿主 api 不可用");
      const payload = unwrap(await api.post(path, body));
      if (payload && typeof payload === "object" && payload.success === false) {
        throw new Error(textOf(payload.message) || "接口返回失败");
      }
      return payload;
    }
    const FILTERS = [
      { value: "", label: "全部" },
      { value: "missing_avatar", label: "缺头像" },
      { value: "locked", label: "已锁定" },
      { value: "failed", label: "失败" }
    ];
    const items = ref$a([]);
    const total = ref$a(0);
    const loading = ref$a(false);
    const error = ref$a("");
    const loaded = ref$a(false);
    const query = ref$a("");
    const filter = ref$a("");
    const rows = computed$8(() => {
      const keyword = String(query.value || "").trim().toLowerCase();
      if (!keyword) return items.value;
      return items.value.filter((item) => {
        const haystack = [
          item.name,
          item.zh,
          item.jp,
          item.person,
          ...Array.isArray(item.aliases) ? item.aliases : []
        ].map((value) => textOf(value).toLowerCase()).join(" ");
        return haystack.includes(keyword);
      });
    });
    const filtered = computed$8(() => !!String(query.value || "").trim());
    const {
      rows: pagedRows,
      shown: shownRows,
      total: pagedTotal,
      hasMore,
      sentinel
    } = usePagedList(rows, { pageSize: ACTOR_PAGE_SIZE });
    const pagedHint = computed$8(() => hasMore.value ? "已显示 " + shownRows.value + " / " + pagedTotal.value + " 位 · 继续下滑自动加载" : "已全部加载（" + pagedTotal.value + " 位）");
    const summary = computed$8(() => {
      const all = total.value || items.value.length;
      const parts = ["共 " + all + " 位"];
      if (items.value.length && all > items.value.length) parts.push("本屏 " + items.value.length + " 位");
      if (filtered.value) parts.push("筛出 " + rows.value.length + " 位");
      return parts.join(" · ");
    });
    async function load(notify = false) {
      if (loading.value) return;
      loading.value = true;
      error.value = "";
      if (notify) t.info("正在读取演员库…");
      try {
        const payload = await getJson("plugin/actor/list", {
          filter: filter.value,
          page: 1,
          limit: FETCH_LIMIT
        });
        const list = Array.isArray(payload?.items) ? payload.items : [];
        items.value = list;
        total.value = Number(payload?.total || list.length) || list.length;
        loaded.value = true;
        if (notify) t.success("共 " + total.value + " 位");
      } catch (err) {
        error.value = errorText(err);
        if (notify) t.warning("演员库读取失败：" + error.value);
      } finally {
        loading.value = false;
      }
    }
    function pickFilter(value) {
      if (filter.value === value) return;
      filter.value = value;
      void load(false);
    }
    function avatarOf(item) {
      const images2 = Array.isArray(item.images) ? item.images : [];
      const primary = images2.find((image) => image?.primary) || images2[0];
      return textOf(primary?.url);
    }
    function missingAvatar(item) {
      return !avatarOf(item);
    }
    function imagesLocked(item) {
      return (Array.isArray(item.locked_fields) ? item.locked_fields : []).includes("images");
    }
    function rowKey(item, index) {
      return textOf(item.id) || textOf(item.name) || "row#" + index;
    }
    const detailId = ref$a("");
    const detail = ref$a(null);
    const detailLoading = ref$a(false);
    const detailError = ref$a("");
    const busy = ref$a("");
    const actor = computed$8(() => detail.value?.actor || null);
    const images = computed$8(() => Array.isArray(actor.value?.images) ? actor.value.images : []);
    const numbers = computed$8(() => Array.isArray(detail.value?.numbers) ? detail.value.numbers : []);
    const history = computed$8(() => Array.isArray(detail.value?.history) ? detail.value.history : []);
    function numberText(entry) {
      return typeof entry === "string" ? entry : textOf(entry?.number) || textOf(entry?.title);
    }
    function numberTitle(entry) {
      return typeof entry === "string" ? "" : textOf(entry?.title);
    }
    function openActor(item) {
      const id = textOf(item.id);
      if (!id) {
        t.warning("这位演员还没有 id（后端没入库），暂时打不开详情");
        return;
      }
      detailId.value = id;
      detail.value = null;
      imageIndex.value = 0;
      scrapeResult.value = null;
      cropOffset.value = 50;
      void loadDetail();
    }
    async function loadDetail() {
      if (!detailId.value) return;
      detailLoading.value = true;
      detailError.value = "";
      try {
        const payload = await getJson("plugin/actor/detail", { id: detailId.value });
        const raw = payload?.actor && typeof payload.actor === "object" ? payload.actor : payload;
        detail.value = {
          actor: raw || {},
          numbers: Array.isArray(payload?.numbers) ? payload.numbers : [],
          history: Array.isArray(payload?.history) ? payload.history : []
        };
        if (imageIndex.value >= images.value.length) imageIndex.value = 0;
      } catch (err) {
        detailError.value = errorText(err);
      } finally {
        detailLoading.value = false;
      }
    }
    function backToList() {
      detailId.value = "";
      detail.value = null;
      detailError.value = "";
      scrapeResult.value = null;
    }
    const imageIndex = ref$a(0);
    const currentImage = computed$8(() => images.value[imageIndex.value] || null);
    const currentMeta = computed$8(() => {
      const image = currentImage.value;
      if (!image) return "";
      const parts = [];
      const source = textOf(image.source) || "未知来源";
      parts.push(source === "gfriends" ? "gfriends" : source === "javdb" ? "javdb" : source === "manual" ? "手动上传" : source);
      const w = Number(image.w) || 0;
      const h = Number(image.h) || 0;
      if (w && h) parts.push(w + "×" + h);
      const bytes = Number(image.bytes) || 0;
      if (bytes) parts.push(Math.round(bytes / 1024) + " KB");
      return parts.join(" · ");
    });
    function stepImage(delta) {
      const count = images.value.length;
      if (!count) return;
      imageIndex.value = (imageIndex.value + delta + count) % count;
      cropOffset.value = 50;
    }
    function pickImage(index) {
      imageIndex.value = index;
      cropOffset.value = 50;
    }
    const scrapeResult = ref$a(null);
    function scrapeSummary(payload, dryRun) {
      const counts = payload?.counts && typeof payload.counts === "object" ? payload.counts : {};
      const items2 = Array.isArray(payload?.items) ? payload.items : [];
      const errors = (Array.isArray(payload?.errors) ? payload.errors : []).map((item) => textOf(item)).filter(Boolean);
      const first = (keys) => {
        for (const key of keys) {
          const value = counts[key];
          if (value === void 0 || value === null) continue;
          const num = Number(value);
          if (Number.isFinite(num)) return num;
        }
        return null;
      };
      let up = first(["uploaded", "applied", "ok", "done"]);
      let skip = first(["skipped", "skip"]);
      let fail = first(["failed", "error"]);
      if (up === null || skip === null || fail === null) {
        let okCount = 0;
        let skipCount = 0;
        let failCount = 0;
        for (const item of items2) {
          const action = textOf(item?.action ?? item?.status).toLowerCase();
          if (/fail|error/.test(action)) failCount += 1;
          else if (/skip|no_avatar|person_missing|has_image|locked/.test(action)) skipCount += 1;
          else okCount += 1;
        }
        if (up === null) up = okCount;
        if (skip === null) skip = skipCount;
        if (fail === null) fail = failCount;
      }
      const line = "更新 " + (up || 0) + " / 跳过 " + (skip || 0) + " / 失败 " + (fail || 0);
      return {
        ok: (fail || 0) === 0 && !errors.length,
        text: (dryRun ? "重刮计划（dry_run，零写请求）：" : "") + line,
        errors: errors.slice(0, 5)
      };
    }
    async function rescrape() {
      if (busy.value) return;
      const id = detailId.value;
      if (!id) return;
      const name = textOf(actor.value?.zh || actor.value?.name) || "这位演员";
      busy.value = "scrape";
      scrapeResult.value = null;
      try {
        t.info("正在读取重刮计划（dry_run，零写请求）…");
        let plan;
        try {
          const payload2 = await postJson("plugin/actor/scrape", { id, dry_run: true, force: true });
          plan = scrapeSummary(payload2, true);
        } catch (err) {
          scrapeResult.value = { ok: false, text: "重刮计划读取失败", errors: [errorText(err)] };
          t.warning("重刮计划读取失败：" + errorText(err));
          return;
        }
        scrapeResult.value = plan;
        const go = await confirm({
          type: "warn",
          title: "重刮演员资料与头像",
          content: "dry_run 计划：" + plan.text.replace("重刮计划（dry_run，零写请求）：", "") + "。\n\n确认后真的开始抓取：会重新问一遍 gFriends / javdb，并把新头像写进 Emby 的 Person 实体（Primary 图）。" + (imagesLocked(actor.value || {}) ? "\n\n★ 这位演员的 images 字段当前是锁住的：只补资料，不会换图。" : ""),
          confirmText: "开始重刮",
          cancelText: "取消"
        });
        if (!go) {
          t.info("已取消，没有向 Emby 写入任何东西");
          return;
        }
        const payload = await postJson("plugin/actor/scrape", { id, dry_run: false, force: true });
        const done = scrapeSummary(payload, false);
        scrapeResult.value = done;
        if (done.ok) t.success(name + " 重刮完成：" + done.text);
        else t.warning(name + " 重刮未全部成功：" + done.text);
        await loadDetail();
        emit("refreshSide");
      } catch (err) {
        scrapeResult.value = { ok: false, text: "重刮请求失败", errors: [errorText(err)] };
        t.warning("重刮失败：" + errorText(err));
      } finally {
        busy.value = "";
      }
    }
    async function toggleLock() {
      if (busy.value) return;
      const id = detailId.value;
      if (!id) return;
      const on = !imagesLocked(actor.value || {});
      busy.value = "lock";
      try {
        const payload = await postJson("plugin/actor/lock", { id, field: "images", on });
        applyActor(payload);
        t.success(on ? "已锁定 images：重刮只补资料、不换图" : "已解锁 images：下次重刮会换图");
        emit("refreshSide");
      } catch (err) {
        t.warning("锁定状态切换失败：" + errorText(err));
      } finally {
        busy.value = "";
      }
    }
    function applyActor(raw) {
      const nested = raw && typeof raw === "object" ? raw.actor : null;
      const flat = raw && typeof raw === "object" && raw.id !== void 0 ? raw : null;
      const row = nested && typeof nested === "object" ? nested : flat;
      if (row && detail.value) {
        detail.value = { ...detail.value, actor: row };
      } else {
        void loadDetail();
      }
    }
    const cropOffset = ref$a(50);
    function isPrimary(index) {
      const image = images.value[index];
      return !!image?.primary || index === 0;
    }
    const primaryImage = computed$8(() => images.value.find((image) => image?.primary) || images.value[0] || null);
    const cropRect = computed$8(() => {
      const image = primaryImage.value;
      if (!image) return null;
      const w = Math.round(Number(image.w) || 0);
      const h = Math.round(Number(image.h) || 0);
      if (!w || !h) return null;
      const target = 3 / 4;
      let boxW = w;
      let boxH = Math.round(w / target);
      if (boxH > h) {
        boxH = h;
        boxW = Math.round(h * target);
      }
      const x = Math.round((w - boxW) / 2);
      const maxY = Math.max(0, h - boxH);
      const y = Math.round(maxY * (cropOffset.value / 100));
      return { x, y, w: boxW, h: boxH };
    });
    const cropStyle = computed$8(() => ({ "--avh-crop-y": cropOffset.value + "%" }));
    const primaryUrl = computed$8(() => textOf(primaryImage.value?.url));
    async function applyCrop() {
      if (busy.value) return;
      const id = detailId.value;
      if (!id) return;
      const rect = cropRect.value;
      const ok = await confirm({
        type: "warn",
        title: "裁剪为主图（3:4）",
        content: "确认后按 3:4 裁掉边缘，生成一张派生图并**设为主图**写进 Emby 的 Person 实体；原图保留。" + (rect ? "\n\n本次裁剪框：x " + rect.x + " · y " + rect.y + " · " + rect.w + "×" + rect.h + "（基于当前主图）。" : "\n\n这张图没有尺寸信息，将由后端按默认 3:4 居中裁切。") + "\n\n裁剪成功后 images 会被自动锁住，避免下次重刮又换掉这张。",
        confirmText: "裁剪并设为主图",
        cancelText: "取消"
      });
      if (!ok) return;
      busy.value = "crop";
      try {
        const body = { id };
        if (rect) body.rect = rect;
        const payload = await postJson("plugin/actor/crop-avatar", body);
        applyActor(payload);
        imageIndex.value = 0;
        t.success("已裁剪并设为主图");
        emit("refreshSide");
      } catch (err) {
        t.warning("裁剪失败：" + errorText(err));
      } finally {
        busy.value = "";
      }
    }
    onMounted$4(() => {
      void load(false);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$9("v-btn");
      const _component_v_chip = _resolveComponent$9("v-chip");
      const _component_v_alert = _resolveComponent$9("v-alert");
      const _component_v_divider = _resolveComponent$9("v-divider");
      const _component_v_slider = _resolveComponent$9("v-slider");
      const _component_v_btn_toggle = _resolveComponent$9("v-btn-toggle");
      const _component_v_text_field = _resolveComponent$9("v-text-field");
      return _openBlock$9(), _createElementBlock$9("div", _hoisted_1$9, [
        detailId.value ? (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 0 }, [
          _createElementVNode$9("div", _hoisted_2$9, [
            _createVNode$8(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: backToList
            }, {
              default: _withCtx$9(() => _cache[7] || (_cache[7] = [
                _createTextVNode$7("← 返回")
              ])),
              _: 1
            }),
            _createElementVNode$9("span", _hoisted_3$7, " 演员详情 · " + _toDisplayString$9(actor.value?.zh || actor.value?.name || "—"), 1),
            _cache[9] || (_cache[9] = _createElementVNode$9("div", { class: "avh-actlib__spacer" }, null, -1)),
            _createVNode$8(_component_v_btn, {
              variant: "outlined",
              size: "small",
              loading: detailLoading.value,
              onClick: loadDetail
            }, {
              default: _withCtx$9(() => _cache[8] || (_cache[8] = [
                _createTextVNode$7("↻ 重新读取")
              ])),
              _: 1
            }, 8, ["loading"])
          ]),
          detailError.value ? (_openBlock$9(), _createBlock$9(ErrorState, {
            key: 0,
            message: "演员详情读取失败：" + detailError.value,
            retrying: detailLoading.value,
            onRetry: loadDetail
          }, null, 8, ["message", "retrying"])) : detailLoading.value && !actor.value ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_4$7, "正在读取演员详情…")) : actor.value ? (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 2 }, [
            _createElementVNode$9("div", _hoisted_5$7, [
              _createElementVNode$9("div", _hoisted_6$7, [
                _createElementVNode$9("div", _hoisted_7$7, _toDisplayString$9(actor.value.zh || actor.value.name || "—"), 1),
                actor.value.zh && actor.value.name ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_8$6, _toDisplayString$9(actor.value.name), 1)) : actor.value.jp ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_9$6, _toDisplayString$9(actor.value.jp), 1)) : _createCommentVNode$8("", true)
              ]),
              imagesLocked(actor.value) ? (_openBlock$9(), _createBlock$9(_component_v_chip, {
                key: 0,
                size: "x-small",
                color: "warning",
                variant: "flat",
                label: ""
              }, {
                default: _withCtx$9(() => _cache[10] || (_cache[10] = [
                  _createTextVNode$7("🔒 images 已锁定")
                ])),
                _: 1
              })) : (_openBlock$9(), _createBlock$9(_component_v_chip, {
                key: 1,
                size: "x-small",
                variant: "tonal",
                label: ""
              }, {
                default: _withCtx$9(() => _cache[11] || (_cache[11] = [
                  _createTextVNode$7("images 未锁")
                ])),
                _: 1
              })),
              actor.value.status ? (_openBlock$9(), _createBlock$9(_component_v_chip, {
                key: 2,
                size: "x-small",
                variant: "tonal",
                label: ""
              }, {
                default: _withCtx$9(() => [
                  _createTextVNode$7("状态 " + _toDisplayString$9(actor.value.status), 1)
                ]),
                _: 1
              })) : _createCommentVNode$8("", true)
            ]),
            _createElementVNode$9("div", _hoisted_10$6, [
              _createElementVNode$9("div", _hoisted_11$5, [
                images.value.length ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_12$5, [
                  _createVNode$8(Thumb, {
                    class: "avh-actlib__shot",
                    variant: "film",
                    src: textOf(currentImage.value?.url),
                    alt: actor.value.zh || actor.value.name || "无图",
                    "plugin-id": _ctx.pluginId
                  }, null, 8, ["src", "alt", "plugin-id"]),
                  _createElementVNode$9("span", _hoisted_13$5, _toDisplayString$9(currentMeta.value), 1),
                  isPrimary(imageIndex.value) ? (_openBlock$9(), _createElementBlock$9("span", _hoisted_14$5, "主图")) : _createCommentVNode$8("", true),
                  images.value.length > 1 ? (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 1 }, [
                    _createElementVNode$9("button", {
                      class: "avh-actlib__nav avh-actlib__nav--prev",
                      type: "button",
                      "aria-label": "上一张",
                      onClick: _cache[0] || (_cache[0] = ($event) => stepImage(-1))
                    }, "‹"),
                    _createElementVNode$9("button", {
                      class: "avh-actlib__nav avh-actlib__nav--next",
                      type: "button",
                      "aria-label": "下一张",
                      onClick: _cache[1] || (_cache[1] = ($event) => stepImage(1))
                    }, "›")
                  ], 64)) : _createCommentVNode$8("", true)
                ])) : (_openBlock$9(), _createBlock$9(EmptyState, {
                  key: 1,
                  text: "这位演员还没有图",
                  hint: "去「设置 → 演员」确认头像源开关，或点下面的「重刮」抓一次"
                })),
                images.value.length > 1 ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_15$4, [
                  (_openBlock$9(true), _createElementBlock$9(_Fragment$8, null, _renderList$8(images.value, (image, index) => {
                    return _openBlock$9(), _createElementBlock$9("button", {
                      key: "img#" + index,
                      type: "button",
                      class: _normalizeClass$6(["avh-actlib__thumb", { "avh-actlib__thumb--on": index === imageIndex.value }]),
                      title: textOf(image.source) + " " + (image.w || "?") + "×" + (image.h || "?"),
                      onClick: ($event) => pickImage(index)
                    }, [
                      _createVNode$8(Thumb, {
                        src: textOf(image.url),
                        alt: "图 " + (index + 1),
                        "plugin-id": _ctx.pluginId
                      }, null, 8, ["src", "alt", "plugin-id"])
                    ], 10, _hoisted_16$4);
                  }), 128))
                ])) : _createCommentVNode$8("", true)
              ]),
              _createElementVNode$9("div", _hoisted_17$4, [
                _cache[17] || (_cache[17] = _createElementVNode$9("div", { class: "text-caption text-medium-emphasis mb-1" }, "维护", -1)),
                _createElementVNode$9("div", _hoisted_18$4, [
                  _createVNode$8(_component_v_btn, {
                    size: "small",
                    variant: "outlined",
                    "prepend-icon": "mdi-auto-fix",
                    loading: busy.value === "scrape",
                    onClick: rescrape
                  }, {
                    default: _withCtx$9(() => _cache[12] || (_cache[12] = [
                      _createTextVNode$7("重刮")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _cache[13] || (_cache[13] = _createElementVNode$9("span", { class: "avh-actlib__hint" }, "先 dry_run 预览，再确认应用", -1))
                ]),
                _createElementVNode$9("div", _hoisted_19$4, [
                  _createVNode$8(_component_v_btn, {
                    size: "small",
                    variant: "outlined",
                    "prepend-icon": imagesLocked(actor.value) ? "mdi-lock-open-variant" : "mdi-lock",
                    loading: busy.value === "lock",
                    onClick: toggleLock
                  }, {
                    default: _withCtx$9(() => [
                      _createTextVNode$7(_toDisplayString$9(imagesLocked(actor.value) ? "解锁 images" : "锁定 images"), 1)
                    ]),
                    _: 1
                  }, 8, ["prepend-icon", "loading"]),
                  _cache[14] || (_cache[14] = _createElementVNode$9("span", { class: "avh-actlib__hint" }, "锁住后重刮只补资料、不换图", -1))
                ]),
                scrapeResult.value ? (_openBlock$9(), _createBlock$9(_component_v_alert, {
                  key: 0,
                  type: scrapeResult.value.ok ? "success" : "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "text-caption mb-3"
                }, {
                  default: _withCtx$9(() => [
                    _createElementVNode$9("div", null, _toDisplayString$9(scrapeResult.value.text), 1),
                    (_openBlock$9(true), _createElementBlock$9(_Fragment$8, null, _renderList$8(scrapeResult.value.errors, (line, index) => {
                      return _openBlock$9(), _createElementBlock$9("div", { key: index }, _toDisplayString$9(line), 1);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["type"])) : _createCommentVNode$8("", true),
                _createVNode$8(_component_v_divider, { class: "mb-3" }),
                _cache[18] || (_cache[18] = _createElementVNode$9("div", { class: "text-caption text-medium-emphasis mb-1" }, "裁剪为主图（3:4）", -1)),
                primaryUrl.value ? (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 1 }, [
                  _createElementVNode$9("div", _hoisted_20$4, [
                    _createVNode$8(Thumb, {
                      class: "avh-actlib__crop",
                      style: _normalizeStyle$1(cropStyle.value),
                      variant: "film",
                      src: primaryUrl.value,
                      alt: "裁剪预览",
                      "plugin-id": _ctx.pluginId
                    }, null, 8, ["style", "src", "plugin-id"])
                  ]),
                  _createElementVNode$9("div", _hoisted_21$3, [
                    _cache[15] || (_cache[15] = _createElementVNode$9("span", { class: "avh-actlib__hint" }, "上下微调", -1)),
                    _createVNode$8(_component_v_slider, {
                      "model-value": cropOffset.value,
                      min: 0,
                      max: 100,
                      step: 1,
                      density: "compact",
                      "hide-details": "",
                      class: "avh-actlib__slider",
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => cropOffset.value = Number(value) || 0)
                    }, null, 8, ["model-value"]),
                    _createElementVNode$9("span", _hoisted_22$3, _toDisplayString$9(cropOffset.value) + "%", 1)
                  ]),
                  _createElementVNode$9("p", _hoisted_23$3, [
                    cropRect.value ? (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 0 }, [
                      _createTextVNode$7(" 裁剪框：x " + _toDisplayString$9(cropRect.value.x) + " · y " + _toDisplayString$9(cropRect.value.y) + " · " + _toDisplayString$9(cropRect.value.w) + "×" + _toDisplayString$9(cropRect.value.h) + "（基于当前主图 " + _toDisplayString$9(primaryImage.value?.w || "?") + "×" + _toDisplayString$9(primaryImage.value?.h || "?") + "） ", 1)
                    ], 64)) : (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 1 }, [
                      _createTextVNode$7(" 这张图没有尺寸信息，裁切换后端默认的 3:4 居中框。 ")
                    ], 64))
                  ]),
                  _createVNode$8(_component_v_btn, {
                    size: "small",
                    variant: "outlined",
                    "prepend-icon": "mdi-crop",
                    loading: busy.value === "crop",
                    onClick: applyCrop
                  }, {
                    default: _withCtx$9(() => _cache[16] || (_cache[16] = [
                      _createTextVNode$7("裁剪并设为主图")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ], 64)) : (_openBlock$9(), _createElementBlock$9("p", _hoisted_24$2, " 还没有主图可裁：先「重刮」拿到一张图。 "))
              ])
            ]),
            _createElementVNode$9("div", _hoisted_25$2, [
              _createElementVNode$9("div", _hoisted_26$2, [
                _cache[19] || (_cache[19] = _createElementVNode$9("span", null, "原名", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.name || "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_27$2, [
                _cache[20] || (_cache[20] = _createElementVNode$9("span", null, "中文名", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.zh || "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_28$2, [
                _cache[21] || (_cache[21] = _createElementVNode$9("span", null, "日文名", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.jp || "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_29$2, [
                _cache[22] || (_cache[22] = _createElementVNode$9("span", null, "性别", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.gender || "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_30$2, [
                _cache[23] || (_cache[23] = _createElementVNode$9("span", null, "javdb 演员 id", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.javdb_actor_id || "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_31$2, [
                _cache[24] || (_cache[24] = _createElementVNode$9("span", null, "别名", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9((actor.value.aliases || []).join(" / ") || "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_32$2, [
                _cache[25] || (_cache[25] = _createElementVNode$9("span", null, "最后刮削", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.last_scraped_at ? _unref$3(shortTime)(actor.value.last_scraped_at) : "—"), 1)
              ]),
              _createElementVNode$9("div", _hoisted_33$2, [
                _cache[26] || (_cache[26] = _createElementVNode$9("span", null, "重试", -1)),
                _createElementVNode$9("b", null, _toDisplayString$9(actor.value.retry_count || 0) + _toDisplayString$9(actor.value.next_retry ? " · 下次 " + _unref$3(shortTime)(actor.value.next_retry) : ""), 1)
              ])
            ]),
            _createElementVNode$9("div", _hoisted_34$2, [
              _createElementVNode$9("div", _hoisted_35$2, "作品番号（" + _toDisplayString$9(numbers.value.length) + "）", 1),
              numbers.value.length ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_36$2, [
                (_openBlock$9(true), _createElementBlock$9(_Fragment$8, null, _renderList$8(numbers.value, (entry, index) => {
                  return _openBlock$9(), _createBlock$9(_component_v_chip, {
                    key: numberText(entry) + "#" + index,
                    size: "x-small",
                    variant: "tonal",
                    label: "",
                    title: numberTitle(entry)
                  }, {
                    default: _withCtx$9(() => [
                      _createTextVNode$7(_toDisplayString$9(numberText(entry)), 1)
                    ]),
                    _: 2
                  }, 1032, ["title"]);
                }), 128))
              ])) : (_openBlock$9(), _createElementBlock$9("p", _hoisted_37$2, "还没有关联到作品番号。"))
            ]),
            _createElementVNode$9("div", _hoisted_38$2, [
              _createElementVNode$9("div", _hoisted_39$2, "最近动作（" + _toDisplayString$9(history.value.length) + "）", 1),
              history.value.length ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_40$2, [
                (_openBlock$9(true), _createElementBlock$9(_Fragment$8, null, _renderList$8(history.value, (row, index) => {
                  return _openBlock$9(), _createElementBlock$9("div", {
                    key: "h#" + index,
                    class: "avh-actlib__hrow"
                  }, [
                    _createElementVNode$9("span", _hoisted_41$2, _toDisplayString$9(row.at ? _unref$3(shortTime)(row.at) : "—"), 1),
                    _createElementVNode$9("span", null, _toDisplayString$9(row.action || "—"), 1),
                    _createElementVNode$9("span", _hoisted_42$2, _toDisplayString$9(row.reason || ""), 1)
                  ]);
                }), 128))
              ])) : (_openBlock$9(), _createElementBlock$9("p", _hoisted_43$2, "还没有执行过动作。"))
            ])
          ], 64)) : _createCommentVNode$8("", true)
        ], 64)) : (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 1 }, [
          _createElementVNode$9("div", _hoisted_44$2, [
            _createVNode$8(_component_v_btn_toggle, {
              "model-value": filter.value,
              mandatory: "",
              density: "compact",
              variant: "outlined",
              color: "primary",
              class: "avh-actlib__filters",
              "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => value !== void 0 && pickFilter(String(value)))
            }, {
              default: _withCtx$9(() => [
                (_openBlock$9(), _createElementBlock$9(_Fragment$8, null, _renderList$8(FILTERS, (item) => {
                  return _createVNode$8(_component_v_btn, {
                    key: item.value,
                    value: item.value,
                    size: "small"
                  }, {
                    default: _withCtx$9(() => [
                      _createTextVNode$7(_toDisplayString$9(item.label), 1)
                    ]),
                    _: 2
                  }, 1032, ["value"]);
                }), 64))
              ]),
              _: 1
            }, 8, ["model-value"]),
            _cache[28] || (_cache[28] = _createElementVNode$9("div", { class: "avh-actlib__spacer" }, null, -1)),
            _createVNode$8(_component_v_text_field, {
              modelValue: query.value,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => query.value = $event),
              class: "avh-actlib__q",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              clearable: "",
              "single-line": "",
              "prepend-inner-icon": "mdi-magnify",
              placeholder: "艺名 / 中文名 / 别名",
              "aria-label": "按艺名、中文名或别名过滤已取回的演员"
            }, null, 8, ["modelValue"]),
            _createVNode$8(_component_v_btn, {
              variant: "outlined",
              size: "small",
              loading: loading.value,
              onClick: _cache[5] || (_cache[5] = ($event) => load(true))
            }, {
              default: _withCtx$9(() => _cache[27] || (_cache[27] = [
                _createTextVNode$7("↻ 刷新")
              ])),
              _: 1
            }, 8, ["loading"])
          ]),
          !error.value && (loaded.value || items.value.length) ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_45$1, [
            _createVNode$8(_component_v_chip, {
              size: "x-small",
              variant: "flat",
              color: "success",
              label: ""
            }, {
              default: _withCtx$9(() => _cache[29] || (_cache[29] = [
                _createTextVNode$7("演员库")
              ])),
              _: 1
            }),
            _createElementVNode$9("span", _hoisted_46$1, _toDisplayString$9(summary.value), 1)
          ])) : _createCommentVNode$8("", true),
          error.value ? (_openBlock$9(), _createBlock$9(ErrorState, {
            key: 1,
            message: "演员库读取失败：" + error.value,
            retrying: loading.value,
            onRetry: _cache[6] || (_cache[6] = ($event) => load(false))
          }, null, 8, ["message", "retrying"])) : loading.value && !items.value.length ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_47$1, "正在读取演员库…")) : !items.value.length && filter.value ? (_openBlock$9(), _createBlock$9(EmptyState, {
            key: 3,
            text: "这个筛选下没有演员",
            hint: "换个筛选档看看，或者点「全部」"
          })) : !items.value.length ? (_openBlock$9(), _createBlock$9(EmptyState, {
            key: 4,
            text: "演员库里还没有演员<br>影片刮削过一次之后，演员会自动登记进来",
            hint: "也可以去「设置 → 演员」点「一键补齐缺失头像」立刻跑一批"
          })) : filtered.value && !rows.value.length ? (_openBlock$9(), _createBlock$9(EmptyState, {
            key: 5,
            text: "没有匹配的演员",
            hint: "试试清空搜索词，或者换个艺名 / 中文名"
          })) : (_openBlock$9(), _createElementBlock$9(_Fragment$8, { key: 6 }, [
            _createElementVNode$9("div", _hoisted_48$1, [
              (_openBlock$9(true), _createElementBlock$9(_Fragment$8, null, _renderList$8(_unref$3(pagedRows), (item, index) => {
                return _openBlock$9(), _createElementBlock$9("div", {
                  key: rowKey(item, index),
                  class: "avh-actlib__cell"
                }, [
                  _createVNode$8(ActorRow, {
                    name: textOf(item.name) || textOf(item.zh) || "—",
                    zh: textOf(item.zh),
                    avatar: avatarOf(item),
                    "plugin-id": _ctx.pluginId,
                    onSelect: ($event) => openActor(item)
                  }, null, 8, ["name", "zh", "avatar", "plugin-id", "onSelect"]),
                  missingAvatar(item) ? (_openBlock$9(), _createElementBlock$9("span", _hoisted_49$1, "缺头像")) : _createCommentVNode$8("", true),
                  imagesLocked(item) ? (_openBlock$9(), _createElementBlock$9("span", _hoisted_50$1, "🔒")) : _createCommentVNode$8("", true)
                ]);
              }), 128))
            ]),
            _createElementVNode$9("div", {
              ref_key: "sentinel",
              ref: sentinel,
              class: "avh-actlib__more"
            }, [
              _createElementVNode$9("span", _hoisted_51$1, _toDisplayString$9(pagedHint.value), 1)
            ], 512)
          ], 64))
        ], 64))
      ]);
    };
  }
});

const ActorLibraryView = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-88f6d3ad"]]);

const {reactive,ref: ref$9} = await importShared('vue');
const rankCache = reactive(/* @__PURE__ */ new Map());
const periodState = ref$9("week");
const kindState = ref$9("censored");
const rankPrefetcher = createDetailPrefetcher(() => hostApi);
let hostApi = null;
function prefetchDetail(api, number, id) {
  if (!api || typeof api.get !== "function") return;
  hostApi = api;
  rankPrefetcher.enqueue(number, id);
}
function prefetchCards(api, movies, n = PREFETCH_N) {
  if (!api || typeof api.get !== "function") return;
  hostApi = api;
  rankPrefetcher.enqueueMany(movies, n);
}

const {defineComponent:_defineComponent$8} = await importShared('vue');

const {openBlock:_openBlock$8,createElementBlock:_createElementBlock$8,createCommentVNode:_createCommentVNode$7,renderList:_renderList$7,Fragment:_Fragment$7,toDisplayString:_toDisplayString$8,normalizeClass:_normalizeClass$5,createElementVNode:_createElementVNode$8,createTextVNode:_createTextVNode$6,resolveComponent:_resolveComponent$8,withCtx:_withCtx$8,createBlock:_createBlock$8,createVNode:_createVNode$7} = await importShared('vue');

const _hoisted_1$8 = { class: "avh-discover" };
const _hoisted_2$8 = {
  key: 0,
  class: "avh-discover__loading"
};
const _hoisted_3$6 = { class: "avh-discover__toolbar" };
const _hoisted_4$6 = { class: "avh-tabs" };
const _hoisted_5$6 = ["onClick"];
const _hoisted_6$6 = { class: "avh-tabs" };
const _hoisted_7$6 = ["onClick"];
const _hoisted_8$5 = {
  key: 0,
  class: "avh-discover__hint"
};
const _hoisted_9$5 = {
  key: 1,
  class: "avh-discover__loading"
};
const _hoisted_10$5 = {
  key: 3,
  class: "avh-discover__grid"
};
const {computed: computed$7,ref: ref$8,watch: watch$4} = await importShared('vue');
const _sfc_main$8 = /* @__PURE__ */ _defineComponent$8({
  __name: "DiscoverView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["openMovie"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const PERIOD_TABS = [
      { key: "day", name: "日榜" },
      { key: "week", name: "周榜" },
      { key: "month", name: "月榜" }
    ];
    const ZONE_TABS = [
      { key: "censored", name: "有码" },
      { key: "uncensored", name: "无码" },
      { key: "fc2", name: "FC2" }
    ];
    const period = computed$7(() => periodState.value);
    const kind = computed$7(() => kindState.value);
    function pickPeriod(key) {
      periodState.value = key;
    }
    function pickKind(key) {
      kindState.value = key;
    }
    const booted = computed$7(() => props.store.booted.value === true);
    const bootError = computed$7(() => String(props.store.error.value || ""));
    const rankKey = computed$7(() => `rank:${period.value}:${kind.value}`);
    const entry = computed$7(() => rankCache.get(rankKey.value) || null);
    const movies = computed$7(() => entry.value && entry.value.data || []);
    const rankError = computed$7(() => String(entry.value && entry.value.error || ""));
    const inflight = /* @__PURE__ */ new Set();
    const retrying = ref$8(false);
    async function loadRank(p, k, force) {
      const key = `rank:${p}:${k}`;
      if (!force && rankCache.has(key)) return;
      if (inflight.has(key)) return;
      inflight.add(key);
      try {
        const res = await fetchRank(p, k);
        if (!res.ok) {
          rankCache.set(key, { error: res.message || "抓取失败，请稍后重试" });
          t.warning("榜单抓取失败");
          t.info(res.message || "抓取失败，请稍后重试");
          return;
        }
        rankCache.set(key, { error: "", data: res.movies });
      } catch (err) {
        rankCache.set(key, { error: `抓取失败，请稍后重试（${errorText(err)}）` });
      } finally {
        inflight.delete(key);
      }
    }
    function transportMessage(err) {
      const status = Number(err?.response?.status || err?.status || 0);
      if (status) return `请求失败（HTTP ${status}）`;
      return `网络请求失败：${errorText(err)}`;
    }
    async function fetchRank(p, k) {
      const api = props.api;
      if (!api || typeof api.get !== "function") return { ok: false, message: "宿主请求器不可用" };
      let raw;
      try {
        raw = await api.get("plugin/rankings", { params: { period: p, kind: k } });
      } catch (err) {
        return { ok: false, message: transportMessage(err) };
      }
      const payload = unwrap(raw);
      if (payload && typeof payload === "object" && payload.success === false) {
        return { ok: false, message: String(payload.message || payload.detail || "") };
      }
      const list = Array.isArray(payload?.movies) ? payload.movies : Array.isArray(payload?.data?.movies) ? payload.data.movies : [];
      return { ok: true, movies: list };
    }
    async function ensureRank() {
      if (bootError.value || !booted.value) return;
      await loadRank(period.value, kind.value, false);
    }
    async function reloadRank() {
      const p = period.value;
      const k = kind.value;
      const key = `rank:${p}:${k}`;
      rankCache.delete(key);
      t.info("javdb-cli");
      t.info("正在重新抓取榜单…");
      await loadRank(p, k, true);
      const done = rankCache.get(key);
      if (done && !done.error) {
        t.success("榜单已更新");
        t.info(`${(done.data || []).length} 条`);
      } else {
        t.warning("重新抓取失败");
        t.info(done && done.error || "");
      }
    }
    async function retryRank() {
      retrying.value = true;
      try {
        if (bootError.value && !rankCache.has(rankKey.value)) {
          await props.store.refresh();
          return;
        }
        await reloadRank();
      } finally {
        retrying.value = false;
      }
    }
    function isActorFaved(movie) {
      const actor = String(movie.actor || "");
      if (!actor) return false;
      return (props.store.favs.value || []).some((item) => item.name === actor);
    }
    function cardKey(movie, index) {
      return `${movie.number || ""}#${index}`;
    }
    function openCard(movie) {
      emit("openMovie", { number: String(movie.number || ""), id: String(movie.id || "") });
    }
    function hoverCard(movie) {
      prefetchDetail(props.api, movie.number, movie.id);
    }
    watch$4([booted, bootError, rankKey], () => void ensureRank(), { immediate: true });
    watch$4(movies, (list) => prefetchCards(props.api, list), { immediate: true });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$8("v-btn");
      return _openBlock$8(), _createElementBlock$8("div", _hoisted_1$8, [
        !booted.value && !bootError.value ? (_openBlock$8(), _createElementBlock$8("div", _hoisted_2$8, "正在读取插件状态…")) : (_openBlock$8(), _createElementBlock$8(_Fragment$7, { key: 1 }, [
          _createElementVNode$8("div", _hoisted_3$6, [
            _createElementVNode$8("div", _hoisted_4$6, [
              (_openBlock$8(), _createElementBlock$8(_Fragment$7, null, _renderList$7(PERIOD_TABS, (item) => {
                return _createElementVNode$8("button", {
                  key: item.key,
                  class: _normalizeClass$5({ "avh-tabs__on": item.key === period.value }),
                  onClick: ($event) => pickPeriod(item.key)
                }, _toDisplayString$8(item.name), 11, _hoisted_5$6);
              }), 64))
            ]),
            _createElementVNode$8("div", _hoisted_6$6, [
              (_openBlock$8(), _createElementBlock$8(_Fragment$7, null, _renderList$7(ZONE_TABS, (item) => {
                return _createElementVNode$8("button", {
                  key: item.key,
                  class: _normalizeClass$5({ "avh-tabs__on": item.key === kind.value }),
                  onClick: ($event) => pickKind(item.key)
                }, _toDisplayString$8(item.name), 11, _hoisted_7$6);
              }), 64))
            ]),
            !bootError.value && entry.value && entry.value.data ? (_openBlock$8(), _createElementBlock$8("span", _hoisted_8$5, _toDisplayString$8(entry.value.data.length) + " 部 ", 1)) : _createCommentVNode$7("", true),
            _cache[1] || (_cache[1] = _createElementVNode$8("div", { class: "avh-discover__spacer" }, null, -1)),
            !bootError.value ? (_openBlock$8(), _createBlock$8(_component_v_btn, {
              key: 1,
              variant: "outlined",
              size: "small",
              onClick: reloadRank
            }, {
              default: _withCtx$8(() => _cache[0] || (_cache[0] = [
                _createTextVNode$6(" ↻ 重新抓取 ")
              ])),
              _: 1
            })) : _createCommentVNode$7("", true)
          ]),
          bootError.value ? (_openBlock$8(), _createBlock$8(ErrorState, {
            key: 0,
            message: `插件状态读取失败：${bootError.value}（仍可尝试直接抓取榜单）`,
            retrying: retrying.value,
            onRetry: retryRank
          }, null, 8, ["message", "retrying"])) : (_openBlock$8(), _createElementBlock$8(_Fragment$7, { key: 1 }, [
            rankError.value ? (_openBlock$8(), _createBlock$8(ErrorState, {
              key: 0,
              message: rankError.value,
              retrying: retrying.value,
              onRetry: retryRank
            }, null, 8, ["message", "retrying"])) : !entry.value ? (_openBlock$8(), _createElementBlock$8("div", _hoisted_9$5, "正在抓取榜单…")) : !movies.value.length ? (_openBlock$8(), _createBlock$8(EmptyState, {
              key: 2,
              text: "该榜单暂无数据，换个周期 / 分类试试"
            })) : (_openBlock$8(), _createElementBlock$8("div", _hoisted_10$5, [
              (_openBlock$8(true), _createElementBlock$8(_Fragment$7, null, _renderList$7(movies.value, (movie, index) => {
                return _openBlock$8(), _createBlock$8(NumCard, {
                  key: cardKey(movie, index),
                  movie,
                  "plugin-id": _ctx.pluginId,
                  "actor-favorited": isActorFaved(movie),
                  onSelect: ($event) => openCard(movie),
                  onHover: ($event) => hoverCard(movie)
                }, null, 8, ["movie", "plugin-id", "actor-favorited", "onSelect", "onHover"]);
              }), 128))
            ]))
          ], 64))
        ], 64)),
        _createVNode$7(BackToTop)
      ]);
    };
  }
});

const DiscoverView = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-18d36688"]]);

const {defineComponent:_defineComponent$7} = await importShared('vue');

const {resolveComponent:_resolveComponent$7,createVNode:_createVNode$6,toDisplayString:_toDisplayString$7,openBlock:_openBlock$7,createElementBlock:_createElementBlock$7,createCommentVNode:_createCommentVNode$6,createTextVNode:_createTextVNode$5,withCtx:_withCtx$7,createBlock:_createBlock$7,renderList:_renderList$6,Fragment:_Fragment$6,createElementVNode:_createElementVNode$7,normalizeClass:_normalizeClass$4} = await importShared('vue');

const _hoisted_1$7 = {
  key: 0,
  class: "avh-sd__subtitle"
};
const _hoisted_2$7 = {
  key: 0,
  class: "avh-sd__loading"
};
const _hoisted_3$5 = {
  key: 0,
  class: "avh-sd__media"
};
const _hoisted_4$5 = {
  key: 0,
  class: "avh-sd__cover"
};
const _hoisted_5$5 = ["src"];
const _hoisted_6$5 = { class: "avh-sd__mediainfo" };
const _hoisted_7$5 = {
  key: 0,
  class: "avh-sd__checkline"
};
const _hoisted_8$4 = {
  key: 1,
  class: "avh-sd__checkline"
};
const _hoisted_9$4 = {
  key: 2,
  class: "avh-sd__hint"
};
const _hoisted_10$4 = {
  key: 1,
  class: "avh-sd__sources"
};
const _hoisted_11$4 = { class: "avh-sd__head" };
const _hoisted_12$4 = {
  key: 2,
  class: "avh-sd__tablewrap"
};
const _hoisted_13$4 = { class: "avh-sd__table" };
const _hoisted_14$4 = ["title"];
const _hoisted_15$3 = {
  key: 0,
  class: "avh-sd__src"
};
const _hoisted_16$3 = {
  key: 1,
  class: "avh-sd__hint"
};
const _hoisted_17$3 = ["title"];
const _hoisted_18$3 = ["title"];
const _hoisted_19$3 = { key: 0 };
const _hoisted_20$3 = {
  key: 1,
  class: "avh-sd__hint"
};
const _hoisted_21$2 = {
  key: 4,
  class: "avh-sd__more"
};
const _hoisted_22$2 = { class: "avh-sd__head" };
const _hoisted_23$2 = { class: "avh-sd__people" };
const {computed: computed$6,ref: ref$7} = await importShared('vue');
const _sfc_main$7 = /* @__PURE__ */ _defineComponent$7({
  __name: "ScrapeDialog",
  props: {
    api: { default: null },
    pluginId: { default: "" },
    toast: { default: null }
  },
  emits: ["done"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    function text(value) {
      return value === null || value === void 0 ? "" : String(value);
    }
    async function getJson(path, params) {
      const api = props.api;
      if (!api || typeof api.get !== "function") throw new Error("宿主 api 不可用");
      const payload2 = unwrap(await api.get(path, params ? { params } : void 0));
      if (payload2 && typeof payload2 === "object" && payload2.success === false) {
        throw new Error(text(payload2.message) || "接口返回失败");
      }
      return payload2;
    }
    async function postJson(path, body) {
      const api = props.api;
      if (!api || typeof api.post !== "function") throw new Error("宿主 api 不可用");
      const payload2 = unwrap(await api.post(path, body));
      if (payload2 && typeof payload2 === "object" && payload2.success === false) {
        throw new Error(text(payload2.message) || "接口返回失败");
      }
      return payload2;
    }
    const FIELD_LABELS = {
      Name: "标题",
      OriginalTitle: "原名",
      Overview: "简介",
      PremiereDate: "发行日",
      ProductionYear: "年份",
      Studios: "制作商",
      SeriesName: "系列",
      GenreItems: "标签",
      CommunityRating: "评分",
      People: "演员",
      ProviderIds: "番号标识"
    };
    const FIELD_HINTS = {
      Name: "Emby 列表里显示的名字：番号 + 版本角标 + 标题",
      OriginalTitle: "日文原名（Emby 用它做二次匹配）",
      Overview: "简介正文：中文优先，没有中文才写日文",
      People: "写入的演员（只写女演员，导演不写）",
      ProviderIds: "番号标识，用于 Emby 侧识别（不会覆盖别的插件写的键）"
    };
    function valueText(value) {
      if (value === null || value === void 0 || value === "") return "";
      if (Array.isArray(value)) {
        return value.map((item) => {
          if (item && typeof item === "object") {
            const obj = item;
            return text(obj.Name ?? obj.name);
          }
          return text(item);
        }).filter(Boolean).join("、");
      }
      if (typeof value === "object") {
        const obj = value;
        return Object.keys(obj).map((key2) => `${key2}=${text(obj[key2])}`).join(" · ");
      }
      const raw = text(value);
      return /^\d{4}-\d{2}-\d{2}T/.test(raw) ? raw.slice(0, 10) : raw;
    }
    function clip(value, size = 110) {
      return value.length > size ? `${value.slice(0, size)}…` : value;
    }
    const open = ref$7(false);
    const loading = ref$7(false);
    const busy = ref$7(false);
    const error = ref$7("");
    const warnings = ref$7([]);
    const key = ref$7("");
    const number = ref$7("");
    const title = ref$7("");
    const payload = ref$7(null);
    const picked = ref$7({});
    const coverOn = ref$7(false);
    const samplesOn = ref$7(false);
    const showEmpty = ref$7(false);
    const fieldRows = computed$6(() => {
      const list = Array.isArray(payload.value?.fields) ? payload.value.fields : [];
      return list.map((item) => {
        const name = text(item?.name);
        return {
          name,
          label: FIELD_LABELS[name] || name,
          hint: FIELD_HINTS[name] || "",
          current: valueText(item?.current),
          target: valueText(item?.target),
          changed: item?.changed === true,
          hasValue: item?.target !== null && item?.target !== void 0,
          source: text(item?.source)
        };
      });
    });
    const shownRows = computed$6(() => fieldRows.value.filter((row) => row.hasValue || showEmpty.value));
    const emptyCount = computed$6(() => fieldRows.value.filter((row) => !row.hasValue).length);
    const coverUrl = computed$6(() => text(payload.value?.images?.cover));
    const sampleCount = computed$6(() => {
      const list = payload.value?.images?.samples;
      return Array.isArray(list) ? list.length : 0;
    });
    const people = computed$6(() => {
      const list = payload.value?.people;
      return Array.isArray(list) ? list.map((item) => text(item)).filter(Boolean) : [];
    });
    const sourceRows = computed$6(() => {
      const src = payload.value?.sources;
      if (!src || typeof src !== "object") return [];
      return Object.keys(src).map((name) => {
        const row = src[name];
        const info = row && typeof row === "object" ? row : {};
        return {
          name,
          status: text(info.status) || (row ? text(row) : ""),
          why: text(info.why) || text(info.error)
        };
      });
    });
    const writeFields = computed$6(() => {
      const out = fieldRows.value.filter((row) => row.hasValue && picked.value[row.name]).map((row) => row.name);
      if (coverOn.value && coverUrl.value) out.push("Primary");
      if (samplesOn.value && sampleCount.value) out.push("Backdrop");
      return out;
    });
    const checkedCount = computed$6(() => writeFields.value.length);
    function proxySrc(url) {
      if (!url) return "";
      const id = props.pluginId || "AVHelper";
      return `/api/v1/plugin/${id}/img?url=${encodeURIComponent(url)}`;
    }
    function resetChecks() {
      const next = {};
      for (const row of fieldRows.value) next[row.name] = row.hasValue;
      picked.value = next;
      coverOn.value = Boolean(coverUrl.value);
      samplesOn.value = sampleCount.value > 0;
      showEmpty.value = false;
    }
    async function reload() {
      if (!key.value) return;
      loading.value = true;
      error.value = "";
      warnings.value = [];
      try {
        const data = await getJson("plugin/scrape/preview", { key: key.value });
        payload.value = data;
        if (text(data?.number)) number.value = text(data.number);
        title.value = text(data?.title);
        warnings.value = Array.isArray(data?.warnings) ? data.warnings.map((item) => text(item)).filter(Boolean) : [];
        resetChecks();
      } catch (err) {
        payload.value = null;
        error.value = errorText(err);
      } finally {
        loading.value = false;
      }
    }
    function openFor(row) {
      key.value = text(row?.key) || text(row?.number);
      number.value = text(row?.number) || key.value;
      title.value = text(row?.title);
      payload.value = null;
      error.value = "";
      warnings.value = [];
      picked.value = {};
      coverOn.value = false;
      samplesOn.value = false;
      open.value = true;
      void reload();
    }
    async function write() {
      if (busy.value || !writeFields.value.length) return;
      busy.value = true;
      try {
        const body = { keys: [key.value], fields: writeFields.value };
        const result = await postJson("plugin/scrape/run", body);
        const rows = Array.isArray(result?.results) ? result.results : [];
        const failed = rows.filter((row) => text(row?.error));
        const changed = rows.reduce(
          (sum, row) => sum + (Array.isArray(row?.changed) ? row.changed.length : 0),
          0
        );
        if (failed.length) {
          t.warning(`写入未全部成功：${text(failed[0]?.error) || "原因未知"}`);
        } else {
          t.success(`已写入 ${number.value || key.value}：${changed} 个字段（勾选 ${checkedCount.value} 项）`);
        }
        open.value = false;
        emit("done");
      } catch (err) {
        t.warning(`写入失败：${errorText(err)}`);
      } finally {
        busy.value = false;
      }
    }
    function toggleAll(value) {
      const next = {};
      for (const row of fieldRows.value) next[row.name] = value && row.hasValue;
      picked.value = next;
      coverOn.value = value && Boolean(coverUrl.value);
      samplesOn.value = value && sampleCount.value > 0;
    }
    __expose({ openFor });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$7("v-icon");
      const _component_v_toolbar_title = _resolveComponent$7("v-toolbar-title");
      const _component_v_spacer = _resolveComponent$7("v-spacer");
      const _component_v_chip = _resolveComponent$7("v-chip");
      const _component_v_btn = _resolveComponent$7("v-btn");
      const _component_v_toolbar = _resolveComponent$7("v-toolbar");
      const _component_v_divider = _resolveComponent$7("v-divider");
      const _component_v_alert = _resolveComponent$7("v-alert");
      const _component_v_checkbox = _resolveComponent$7("v-checkbox");
      const _component_v_card_text = _resolveComponent$7("v-card-text");
      const _component_v_card_actions = _resolveComponent$7("v-card-actions");
      const _component_v_card = _resolveComponent$7("v-card");
      const _component_v_dialog = _resolveComponent$7("v-dialog");
      return _openBlock$7(), _createBlock$7(_component_v_dialog, {
        modelValue: open.value,
        "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => open.value = $event),
        "max-width": "900",
        scrollable: ""
      }, {
        default: _withCtx$7(() => [
          _createVNode$6(_component_v_card, null, {
            default: _withCtx$7(() => [
              _createVNode$6(_component_v_toolbar, {
                density: "comfortable",
                color: "surface"
              }, {
                default: _withCtx$7(() => [
                  _createVNode$6(_component_v_icon, {
                    icon: "mdi-auto-fix",
                    color: "primary",
                    class: "ms-2"
                  }),
                  _createVNode$6(_component_v_toolbar_title, { class: "text-body-1" }, {
                    default: _withCtx$7(() => [
                      _createTextVNode$5(" 手动刮削 · " + _toDisplayString$7(number.value || key.value) + " ", 1),
                      title.value ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_1$7, _toDisplayString$7(clip(title.value, 60)), 1)) : _createCommentVNode$6("", true)
                    ]),
                    _: 1
                  }),
                  _createVNode$6(_component_v_spacer),
                  !loading.value && !error.value ? (_openBlock$7(), _createBlock$7(_component_v_chip, {
                    key: 0,
                    size: "small",
                    variant: "tonal",
                    class: "me-2"
                  }, {
                    default: _withCtx$7(() => [
                      _createTextVNode$5(" 将写入 " + _toDisplayString$7(checkedCount.value) + " 项 ", 1)
                    ]),
                    _: 1
                  })) : _createCommentVNode$6("", true),
                  _createVNode$6(_component_v_btn, {
                    variant: "text",
                    icon: "mdi-close",
                    onClick: _cache[0] || (_cache[0] = ($event) => open.value = false)
                  })
                ]),
                _: 1
              }),
              _createVNode$6(_component_v_divider),
              _createVNode$6(_component_v_card_text, null, {
                default: _withCtx$7(() => [
                  loading.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_2$7, " 正在抓取「" + _toDisplayString$7(number.value || key.value) + "」的信息…（javdb / Javtxt / 翻译逐个跑一遍，通常几秒） ", 1)) : error.value ? (_openBlock$7(), _createBlock$7(EmptyState, {
                    key: 1,
                    text: "抓取失败",
                    hint: `GET /scrape/preview 返回：${error.value}`
                  }, null, 8, ["hint"])) : payload.value ? (_openBlock$7(), _createElementBlock$7(_Fragment$6, { key: 2 }, [
                    (_openBlock$7(true), _createElementBlock$7(_Fragment$6, null, _renderList$6(warnings.value, (line, index) => {
                      return _openBlock$7(), _createBlock$7(_component_v_alert, {
                        key: `warn#${index}`,
                        type: "warning",
                        variant: "tonal",
                        density: "compact",
                        class: "text-caption mb-2"
                      }, {
                        default: _withCtx$7(() => [
                          _createTextVNode$5(_toDisplayString$7(line), 1)
                        ]),
                        _: 2
                      }, 1024);
                    }), 128)),
                    coverUrl.value || sampleCount.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_3$5, [
                      coverUrl.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_4$5, [
                        _createElementVNode$7("img", {
                          src: proxySrc(coverUrl.value),
                          alt: "封面",
                          referrerpolicy: "no-referrer"
                        }, null, 8, _hoisted_5$5)
                      ])) : _createCommentVNode$6("", true),
                      _createElementVNode$7("div", _hoisted_6$5, [
                        coverUrl.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_7$5, [
                          _createVNode$6(_component_v_checkbox, {
                            "model-value": coverOn.value,
                            density: "compact",
                            "hide-details": "",
                            label: "写入封面",
                            "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => coverOn.value = Boolean(value))
                          }, null, 8, ["model-value"]),
                          _cache[8] || (_cache[8] = _createElementVNode$7("span", { class: "avh-sd__hint" }, "右边这张图会写进 Emby 的主图（Primary）", -1))
                        ])) : _createCommentVNode$6("", true),
                        sampleCount.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_8$4, [
                          _createVNode$6(_component_v_checkbox, {
                            "model-value": samplesOn.value,
                            density: "compact",
                            "hide-details": "",
                            label: `写入剧照（${sampleCount.value} 张）`,
                            "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => samplesOn.value = Boolean(value))
                          }, null, 8, ["model-value", "label"]),
                          _cache[9] || (_cache[9] = _createElementVNode$7("span", { class: "avh-sd__hint" }, "写进 Emby 的横版剧照位（Backdrop）", -1))
                        ])) : _createCommentVNode$6("", true),
                        !coverUrl.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_9$4, "这次没抓到封面图")) : _createCommentVNode$6("", true)
                      ])
                    ])) : _createCommentVNode$6("", true),
                    sourceRows.value.length ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_10$4, [
                      _cache[10] || (_cache[10] = _createElementVNode$7("span", { class: "avh-sd__hint" }, "数据源：", -1)),
                      (_openBlock$7(true), _createElementBlock$7(_Fragment$6, null, _renderList$6(sourceRows.value, (row) => {
                        return _openBlock$7(), _createBlock$7(_component_v_chip, {
                          key: row.name,
                          size: "x-small",
                          variant: "tonal",
                          class: "me-1",
                          title: row.why
                        }, {
                          default: _withCtx$7(() => [
                            _createTextVNode$5(_toDisplayString$7(row.name) + " " + _toDisplayString$7(row.status), 1)
                          ]),
                          _: 2
                        }, 1032, ["title"]);
                      }), 128))
                    ])) : _createCommentVNode$6("", true),
                    _createElementVNode$7("div", _hoisted_11$4, [
                      _cache[13] || (_cache[13] = _createElementVNode$7("span", null, "抓到的信息（勾上的才会写进 Emby）", -1)),
                      _createVNode$6(_component_v_spacer),
                      _createVNode$6(_component_v_btn, {
                        variant: "text",
                        size: "x-small",
                        onClick: _cache[3] || (_cache[3] = ($event) => toggleAll(true))
                      }, {
                        default: _withCtx$7(() => _cache[11] || (_cache[11] = [
                          _createTextVNode$5("全选")
                        ])),
                        _: 1
                      }),
                      _createVNode$6(_component_v_btn, {
                        variant: "text",
                        size: "x-small",
                        onClick: _cache[4] || (_cache[4] = ($event) => toggleAll(false))
                      }, {
                        default: _withCtx$7(() => _cache[12] || (_cache[12] = [
                          _createTextVNode$5("全不选")
                        ])),
                        _: 1
                      })
                    ]),
                    shownRows.value.length ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_12$4, [
                      _createElementVNode$7("table", _hoisted_13$4, [
                        _cache[15] || (_cache[15] = _createElementVNode$7("colgroup", null, [
                          _createElementVNode$7("col", { style: { "width": "40px" } }),
                          _createElementVNode$7("col", { style: { "width": "110px" } }),
                          _createElementVNode$7("col"),
                          _createElementVNode$7("col")
                        ], -1)),
                        _cache[16] || (_cache[16] = _createElementVNode$7("thead", null, [
                          _createElementVNode$7("tr", null, [
                            _createElementVNode$7("th"),
                            _createElementVNode$7("th", null, "字段"),
                            _createElementVNode$7("th", null, "来源"),
                            _createElementVNode$7("th", null, "Emby 现在的值"),
                            _createElementVNode$7("th", null, "这次抓到的值")
                          ])
                        ], -1)),
                        _createElementVNode$7("tbody", null, [
                          (_openBlock$7(true), _createElementBlock$7(_Fragment$6, null, _renderList$6(shownRows.value, (row) => {
                            return _openBlock$7(), _createElementBlock$7("tr", {
                              key: row.name,
                              class: _normalizeClass$4({ "avh-sd__row--off": !row.hasValue })
                            }, [
                              _createElementVNode$7("td", null, [
                                _createVNode$6(_component_v_checkbox, {
                                  "model-value": Boolean(picked.value[row.name]) && row.hasValue,
                                  disabled: !row.hasValue,
                                  density: "compact",
                                  "hide-details": "",
                                  "onUpdate:modelValue": (value) => picked.value = { ...picked.value, [row.name]: Boolean(value) }
                                }, null, 8, ["model-value", "disabled", "onUpdate:modelValue"])
                              ]),
                              _createElementVNode$7("td", {
                                title: row.hint
                              }, [
                                _createTextVNode$5(_toDisplayString$7(row.label) + " ", 1),
                                row.changed ? (_openBlock$7(), _createBlock$7(_component_v_chip, {
                                  key: 0,
                                  size: "x-small",
                                  color: "warning",
                                  variant: "tonal",
                                  class: "ms-1"
                                }, {
                                  default: _withCtx$7(() => _cache[14] || (_cache[14] = [
                                    _createTextVNode$5(" 有变化 ")
                                  ])),
                                  _: 1
                                })) : _createCommentVNode$6("", true)
                              ], 8, _hoisted_14$4),
                              _createElementVNode$7("td", null, [
                                row.source ? (_openBlock$7(), _createElementBlock$7("code", _hoisted_15$3, _toDisplayString$7(row.source), 1)) : (_openBlock$7(), _createElementBlock$7("span", _hoisted_16$3, "—"))
                              ]),
                              _createElementVNode$7("td", {
                                class: "avh-sd__cell",
                                title: row.current
                              }, _toDisplayString$7(clip(row.current) || "—"), 9, _hoisted_17$3),
                              _createElementVNode$7("td", {
                                class: "avh-sd__cell",
                                title: row.target
                              }, [
                                row.hasValue ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_19$3, _toDisplayString$7(clip(row.target)), 1)) : (_openBlock$7(), _createElementBlock$7("span", _hoisted_20$3, "没抓到"))
                              ], 8, _hoisted_18$3)
                            ], 2);
                          }), 128))
                        ])
                      ])
                    ])) : (_openBlock$7(), _createBlock$7(EmptyState, {
                      key: 3,
                      text: "这次什么都没抓到",
                      hint: "三个数据源都没有这部片的值，换一部或稍后重试"
                    })),
                    emptyCount.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_21$2, [
                      _createVNode$6(_component_v_btn, {
                        variant: "text",
                        size: "x-small",
                        onClick: _cache[5] || (_cache[5] = ($event) => showEmpty.value = !showEmpty.value)
                      }, {
                        default: _withCtx$7(() => [
                          _createTextVNode$5(_toDisplayString$7(showEmpty.value ? "收起" : `展开没抓到的 ${emptyCount.value} 项`), 1)
                        ]),
                        _: 1
                      })
                    ])) : _createCommentVNode$6("", true),
                    people.value.length ? (_openBlock$7(), _createElementBlock$7(_Fragment$6, { key: 5 }, [
                      _createElementVNode$7("div", _hoisted_22$2, "要写入的演员（" + _toDisplayString$7(people.value.length) + "）", 1),
                      _createElementVNode$7("div", _hoisted_23$2, [
                        (_openBlock$7(true), _createElementBlock$7(_Fragment$6, null, _renderList$6(people.value, (name) => {
                          return _openBlock$7(), _createBlock$7(_component_v_chip, {
                            key: name,
                            size: "x-small",
                            variant: "tonal",
                            class: "me-1 mb-1"
                          }, {
                            default: _withCtx$7(() => [
                              _createTextVNode$5(_toDisplayString$7(name), 1)
                            ]),
                            _: 2
                          }, 1024);
                        }), 128)),
                        _cache[17] || (_cache[17] = _createElementVNode$7("span", { class: "avh-sd__hint" }, "只写女演员，导演不写；不想要演员就取消上面「演员」那一行的勾", -1))
                      ])
                    ], 64)) : _createCommentVNode$6("", true)
                  ], 64)) : _createCommentVNode$6("", true)
                ]),
                _: 1
              }),
              _createVNode$6(_component_v_divider),
              _createVNode$6(_component_v_card_actions, null, {
                default: _withCtx$7(() => [
                  _createVNode$6(_component_v_btn, {
                    variant: "text",
                    loading: loading.value,
                    onClick: reload
                  }, {
                    default: _withCtx$7(() => _cache[18] || (_cache[18] = [
                      _createTextVNode$5("↻ 重新抓取")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode$6(_component_v_spacer),
                  _cache[20] || (_cache[20] = _createElementVNode$7("span", { class: "avh-sd__hint" }, " 写入前会自动存一份完整的 Emby 原数据（出问题可回滚），界面上不出现这一步 ", -1)),
                  _createVNode$6(_component_v_btn, {
                    variant: "text",
                    onClick: _cache[6] || (_cache[6] = ($event) => open.value = false)
                  }, {
                    default: _withCtx$7(() => _cache[19] || (_cache[19] = [
                      _createTextVNode$5("取消")
                    ])),
                    _: 1
                  }),
                  _createVNode$6(_component_v_btn, {
                    color: "primary",
                    variant: "flat",
                    disabled: !checkedCount.value || loading.value,
                    loading: busy.value,
                    onClick: write
                  }, {
                    default: _withCtx$7(() => [
                      _createTextVNode$5("写入 Emby（" + _toDisplayString$7(checkedCount.value) + " 项）", 1)
                    ]),
                    _: 1
                  }, 8, ["disabled", "loading"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"]);
    };
  }
});

const ScrapeDialog = /* @__PURE__ */ _export_sfc(_sfc_main$7, [["__scopeId", "data-v-9c9d1182"]]);

const {defineComponent:_defineComponent$6} = await importShared('vue');

const {renderList:_renderList$5,Fragment:_Fragment$5,openBlock:_openBlock$6,createElementBlock:_createElementBlock$6,toDisplayString:_toDisplayString$6,normalizeClass:_normalizeClass$3,createElementVNode:_createElementVNode$6,createCommentVNode:_createCommentVNode$5,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$6,withCtx:_withCtx$6,createVNode:_createVNode$5,createBlock:_createBlock$6,mergeProps:_mergeProps,unref:_unref$2} = await importShared('vue');

const _hoisted_1$6 = { class: "avh-scrape" };
const _hoisted_2$6 = { class: "avh-scrape__toolbar" };
const _hoisted_3$4 = { class: "avh-tabs" };
const _hoisted_4$4 = ["onClick"];
const _hoisted_5$4 = {
  key: 0,
  class: "avh-scrape__hint"
};
const _hoisted_6$4 = {
  key: 1,
  class: "avh-scrape__hint"
};
const _hoisted_7$4 = { class: "avh-stats" };
const _hoisted_8$3 = ["title", "onClick"];
const _hoisted_9$3 = { class: "avh-stat__num" };
const _hoisted_10$3 = { class: "avh-stat__label" };
const _hoisted_11$3 = { class: "avh-stat__num" };
const _hoisted_12$3 = { class: "avh-scrape__legend" };
const _hoisted_13$3 = { class: "avh-scrape__meta" };
const _hoisted_14$3 = { class: "avh-scrape__hint" };
const _hoisted_15$2 = {
  key: 0,
  class: "avh-scrape__hint"
};
const _hoisted_16$2 = {
  key: 2,
  class: "mb-2"
};
const _hoisted_17$2 = {
  key: 3,
  class: "avh-scrape__actions"
};
const _hoisted_18$2 = {
  key: 4,
  class: "avh-scrape__loading"
};
const _hoisted_19$2 = {
  key: 7,
  class: "avh-tablewrap"
};
const _hoisted_20$2 = { class: "avh-table" };
const _hoisted_21$1 = { class: "avh-table__num" };
const _hoisted_22$1 = {
  key: 0,
  class: "avh-vbadge avh-vbadge--inline"
};
const _hoisted_23$1 = ["title"];
const _hoisted_24$1 = {
  key: 0,
  class: "avh-scrape__hint"
};
const _hoisted_25$1 = { class: "avh-table__right" };
const _hoisted_26$1 = { class: "avh-rowbtns" };
const _hoisted_27$1 = { class: "avh-scrape__actions" };
const _hoisted_28$1 = { class: "avh-scrape__secttl" };
const _hoisted_29$1 = {
  key: 1,
  class: "avh-tablewrap"
};
const _hoisted_30$1 = { class: "avh-table" };
const _hoisted_31$1 = ["title"];
const _hoisted_32$1 = {
  key: 0,
  class: "avh-scrape__reason"
};
const _hoisted_33$1 = { class: "avh-scrape__secttl" };
const _hoisted_34$1 = {
  key: 0,
  class: "avh-scrape__hint"
};
const _hoisted_35$1 = {
  key: 4,
  class: "avh-tablewrap"
};
const _hoisted_36$1 = { class: "avh-table" };
const _hoisted_37$1 = {
  key: 0,
  class: "avh-scrape__reason ms-1"
};
const _hoisted_38$1 = ["title"];
const _hoisted_39$1 = {
  key: 5,
  class: "avh-scrape__hint"
};
const _hoisted_40$1 = {
  key: 6,
  class: "avh-scrape__secttl"
};
const _hoisted_41$1 = {
  key: 7,
  class: "avh-tablewrap"
};
const _hoisted_42$1 = { class: "avh-table" };
const _hoisted_43$1 = {
  key: 0,
  class: "avh-scrape__reason"
};
const _hoisted_44$1 = ["title"];
const {computed: computed$5,ref: ref$6} = await importShared('vue');
const _sfc_main$6 = /* @__PURE__ */ _defineComponent$6({
  __name: "ScrapeView",
  props: {
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null },
    store: { default: null }
  },
  emits: ["refreshSide"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const t = hostToast(props.toast);
    const confirm = useHostConfirm();
    function text(value) {
      return value === null || value === void 0 ? "" : String(value);
    }
    async function getJson(path, params) {
      const api = props.api;
      if (!api || typeof api.get !== "function") throw new Error("宿主 api 不可用");
      const payload = unwrap(await api.get(path, params ? { params } : void 0));
      if (payload && typeof payload === "object" && payload.success === false) {
        throw new Error(text(payload.message) || "接口返回失败");
      }
      return payload;
    }
    async function postJson(path, body) {
      const api = props.api;
      if (!api || typeof api.post !== "function") throw new Error("宿主 api 不可用");
      const payload = unwrap(await api.post(path, body));
      if (payload && typeof payload === "object" && payload.success === false) {
        throw new Error(text(payload.message) || "接口返回失败");
      }
      return payload;
    }
    function firstArray(source, keys) {
      if (!source || typeof source !== "object") return null;
      for (const key of keys) {
        if (Array.isArray(source[key])) return source[key];
      }
      return null;
    }
    const TABS = [
      { key: "workbench", name: "全库刮削工作台" },
      { key: "sources", name: "数据源自检" }
    ];
    const tab = ref$6("workbench");
    const sourcesLoaded = ref$6(false);
    function pickTab(key) {
      tab.value = key;
      if (key === "sources" && !sourcesLoaded.value) void loadLog();
    }
    const STATUS_META = {
      full: {
        label: "已完整",
        color: "success",
        hint: "标题、简介、演员、封面都齐了",
        legend: "已完整＝标题/简介/演员/封面都齐了"
      },
      missing_plot: {
        label: "缺简介",
        color: "warning",
        hint: "标题/封面/演员都有，只差简介（定时任务会隔一段时间重试）",
        legend: "缺简介＝别的都有，只差简介"
      },
      missing_core: {
        label: "缺核心信息",
        color: "error",
        hint: "刮过了，但标题/封面/演员/发行日这些核心信息一个都没拿到",
        legend: "缺核心信息＝刮过了，但标题/封面/演员/发行日都没拿到"
      },
      unscraped: {
        label: "未刮削",
        color: "info",
        hint: "还没刮过，Emby 里什么都没有（点行内「刮削」手动补）",
        legend: "未刮削＝还没刮过"
      }
    };
    const STATUS_ORDER = ["full", "missing_plot", "missing_core", "unscraped"];
    function statusOf(row) {
      const direct = text(row.status).trim().toLowerCase();
      if (direct === "full" || direct === "missing_plot" || direct === "missing_core" || direct === "unscraped") {
        return { key: direct, raw: text(row.status) };
      }
      const state = text(row.states?.scrape ?? row.scrape_state).trim().toLowerCase();
      if (state === "scraped_full") return { key: "full", raw: state };
      if (state === "scraped_partial") return { key: "missing_plot", raw: state };
      const completeness = text(row.completeness).trim().toLowerCase();
      if (completeness === "full") return { key: "full", raw: completeness };
      if (completeness === "missing_plot") return { key: "missing_plot", raw: completeness };
      if (completeness === "missing_core") return { key: "missing_core", raw: completeness };
      return { key: "unscraped", raw: state || completeness };
    }
    function itemKeyOf(row) {
      const direct = text(row.item_key || row.itemKey);
      if (direct) return direct;
      const emby = text(row.emby_id || row.embyId);
      return emby ? `emby:${emby}` : "";
    }
    function normalizeRow(row) {
      const number = text(row.number || row.display_number || row.key);
      const key = text(row.key || number);
      const status = statusOf(row);
      return {
        key,
        number: number || key,
        title: text(row.title),
        embyId: text(row.emby_id || row.embyId),
        itemKey: itemKeyOf(row),
        status: status.key,
        statusRaw: status.raw,
        versionTags: row.version_tags ?? row.versionTags ?? null,
        updatedAt: text(row.updated_at || row.updatedAt),
        raw: row
      };
    }
    const loading = ref$6(false);
    const error = ref$6("");
    const statusError = ref$6("");
    const statusData = ref$6(null);
    const rows = ref$6([]);
    const stats = computed$5(() => {
      const raw = (statusData.value && typeof statusData.value === "object" ? statusData.value.stats : null) || {};
      const out = {};
      for (const key of STATUS_ORDER) out[key] = Number(raw?.[key]) || 0;
      out.total = Number(raw?.total) || rows.value.length;
      return out;
    });
    const queueInfo = computed$5(() => {
      const queue = statusData.value?.queue;
      if (!queue || typeof queue !== "object") return { tier1: null, tier2: null };
      const numOf = (value) => Number.isFinite(Number(value)) ? Number(value) : null;
      return { tier1: numOf(queue.tier1), tier2: numOf(queue.tier2) };
    });
    const lastRun = computed$5(() => text(statusData.value?.last_run));
    const filter = ref$6("");
    const filterLabel = computed$5(() => filter.value ? STATUS_META[filter.value].label : "");
    function toggleFilter(key) {
      filter.value = filter.value === key ? "" : key;
    }
    const visibleRows = computed$5(
      () => filter.value ? rows.value.filter((row) => row.status === filter.value) : rows.value
    );
    const selected = ref$6(/* @__PURE__ */ new Set());
    function rowId(row) {
      return row.itemKey || row.key || row.number;
    }
    function isSelected(row) {
      return selected.value.has(rowId(row));
    }
    function toggleRow(row) {
      const next = new Set(selected.value);
      const id = rowId(row);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      selected.value = next;
    }
    const allVisibleSelected = computed$5(
      () => visibleRows.value.length > 0 && visibleRows.value.every((row) => isSelected(row))
    );
    function toggleAll() {
      const next = new Set(selected.value);
      if (allVisibleSelected.value) {
        for (const row of visibleRows.value) next.delete(rowId(row));
      } else {
        for (const row of visibleRows.value) next.add(rowId(row));
      }
      selected.value = next;
    }
    async function loadStatus() {
      statusError.value = "";
      try {
        statusData.value = await getJson("plugin/scrape/status");
      } catch (err) {
        statusData.value = null;
        statusError.value = errorText(err);
      }
    }
    async function loadLibraryRows() {
      const payload = await getJson("plugin/library");
      const list = firstArray(payload, ["items", "list"]) || [];
      return list.filter((item) => item && typeof item === "object").map((item) => normalizeRow({
        key: item.key,
        number: item.number,
        title: item.title,
        emby_id: item.emby_id || item.id,
        // `/library` 没有 `status`：把 `states.scrape` 原样带过来（`statusOf()` 认它）
        states: item.states,
        version_tags: item.version_tags,
        updated_at: item.updated_at
      }));
    }
    async function load(notify = false) {
      if (loading.value) return;
      loading.value = true;
      error.value = "";
      if (notify) t.info("正在读取刮削状态…");
      try {
        await loadStatus();
        const inline = firstArray(statusData.value, ["items", "list", "films"]);
        if (inline) {
          rows.value = inline.filter((item) => item && typeof item === "object").map((item) => normalizeRow(item));
        } else {
          try {
            rows.value = await loadLibraryRows();
          } catch (err) {
            rows.value = [];
            error.value = statusError.value || errorText(err);
          }
        }
        if (!rows.value.length && statusError.value && !error.value) error.value = statusError.value;
        const alive = new Set(rows.value.map((row) => rowId(row)));
        selected.value = new Set(Array.from(selected.value).filter((id) => alive.has(id)));
        if (notify && !error.value) t.success(`共 ${rows.value.length} 条`);
        if (notify && error.value) t.warning(`刮削状态读取失败：${error.value}`);
      } finally {
        loading.value = false;
      }
    }
    void load(false);
    const scrapeDialog = ref$6(null);
    function openScrape(row) {
      scrapeDialog.value?.openFor({ key: row.key, number: row.number, title: row.title });
    }
    const busy = ref$6("");
    const runResult = ref$6(null);
    function summarizeRun(payload) {
      const results = Array.isArray(payload?.results) ? payload.results : [];
      const errors = [];
      let okCount = 0;
      for (const item of results) {
        const err = text(item?.error);
        const status = text(item?.status);
        if (err || status === "error" || status === "failed") {
          errors.push(`${text(item?.key) || "(未知)"}：${err || status || "失败"}`);
          continue;
        }
        okCount += 1;
      }
      const declared = payload?.ok;
      const ok = declared === void 0 ? errors.length === 0 : declared !== false && errors.length === 0;
      return {
        ok,
        text: `成功 ${okCount} 条${errors.length ? ` · 失败 ${errors.length} 条` : ""}`,
        errors
      };
    }
    async function runSelected() {
      if (busy.value) return;
      const chosen = visibleRows.value.filter((row) => isSelected(row));
      if (!chosen.length) return;
      const keys = chosen.map((row) => row.key || row.number).filter(Boolean);
      const ok = await confirm({
        type: "warn",
        title: "批量刮削",
        content: `将写入 Emby：共 ${keys.length} 部影片。

插件会向这些影片写入标题 / 原名 / 简介 / 演员 / 封面 / 发行日等字段，覆盖它们在 Emby 里的现有取值。确认现在开始？`,
        confirmText: "开始刮削",
        cancelText: "取消"
      });
      if (!ok) return;
      busy.value = "run:batch";
      runResult.value = null;
      t.info(`正在批量刮削 ${keys.length} 部…`);
      try {
        const body = { keys, all: false, force: false, confirm: true };
        const payload = await postJson("plugin/scrape/run", body);
        const summary = summarizeRun(payload);
        runResult.value = summary;
        if (summary.ok) t.success(`批量刮削完成：${summary.text}`);
        else t.warning(`批量刮削未全部成功：${summary.text}`);
        selected.value = /* @__PURE__ */ new Set();
        emit("refreshSide");
        await load(false);
      } catch (err) {
        runResult.value = { ok: false, text: "批量刮削请求失败", errors: [errorText(err)] };
        t.warning(`批量刮削失败：${errorText(err)}`);
      } finally {
        busy.value = "";
      }
    }
    function countAvatarActions(payload) {
      const num = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
      const planned = Array.isArray(payload?.planned) ? payload.planned : [];
      const applied = Array.isArray(payload?.applied) ? payload.applied : [];
      let up = 0;
      let skip = 0;
      let fail = 0;
      for (const entry of planned) {
        const action = text(entry?.action);
        if (action === "upload_avatar") up += 1;
        else if (action === "failed") fail += 1;
        else skip += 1;
      }
      if (!up && !planned.length && applied.length) up = applied.length;
      const errors = (Array.isArray(payload?.errors) ? payload.errors : []).map((item) => text(item)).filter(Boolean);
      return {
        up,
        skip,
        fail,
        missing: num(payload?.missing_person),
        genderUnknown: num(payload?.gender_unknown),
        errors
      };
    }
    function avatarText(counts, dryRun) {
      const line = `上传 ${counts.up} / 跳过 ${counts.skip} / 失败 ${counts.fail}`;
      return dryRun ? `同步计划（dry_run，零写请求）：${line}` : line;
    }
    function avatarNotes(counts) {
      const notes = [
        `其中 ${counts.genderUnknown} 位是旧数据、没有性别字段（按"保守保留"放行，不算失败；重刮一遍后性别会补齐）`
      ];
      if (counts.missing > 0) {
        notes.push(`跳过里 ${counts.missing} 位还没在 Emby 建过 Person 实体（影片 People 写对后自会收敛）`);
      }
      return notes;
    }
    function headErrors(errors) {
      const head = errors.slice(0, 5);
      if (errors.length > head.length) head.push(`…… 另有 ${errors.length - head.length} 条失败明细（后端日志里有全部）`);
      return head;
    }
    function avatarResult(counts, dryRun, extraNotes = []) {
      return {
        ok: counts.fail === 0 && !counts.errors.length,
        text: avatarText(counts, dryRun),
        notes: [...avatarNotes(counts), ...extraNotes],
        errors: headErrors(counts.errors)
      };
    }
    async function syncAvatars(force = false) {
      if (busy.value) return;
      const proceed = await confirm({
        type: "warn",
        title: force ? "重新同步全部演员头像（覆盖已有）" : "同步演员头像",
        content: "这一步只读：先跑一次 dry_run 计划，零写请求，不会向 Emby 写任何东西。\n\n真正的上传在你看到计划条数、再确认一次之后才发生：届时会把头像写进 Emby 的 Person 实体（Person 的 Primary 图，必要时合并写 ProviderIds.JavDB）。" + (force ? "\n\n★ 这次带 force：**已经写过头像的 Person 也会被重新上传覆盖**（用来把旧的糊头像换成高清图）。" : "已经写过头像的 Person 会跳过。"),
        confirmText: "先看计划",
        cancelText: "取消"
      });
      if (!proceed) return;
      busy.value = "avatars";
      runResult.value = null;
      try {
        t.info("正在读取头像同步计划（dry_run，零写请求）…");
        let plan;
        try {
          const planPayload = await postJson(
            "plugin/scrape/avatars",
            { dry_run: true, force }
          );
          plan = countAvatarActions(planPayload);
        } catch (err) {
          runResult.value = { ok: false, text: "头像同步计划读取失败", errors: [errorText(err)] };
          t.warning(`头像同步计划读取失败：${errorText(err)}`);
          return;
        }
        runResult.value = avatarResult(plan, true, plan.up ? [] : ["本次没有需要上传的头像（已经写过的、还没建过 Person 实体的都会跳过）"]);
        if (!plan.up) {
          t.info(`没有需要上传的头像：上传 0 / 跳过 ${plan.skip} / 失败 ${plan.fail}`);
          return;
        }
        const go = await confirm({
          type: "warn",
          title: "同步演员头像（写入 Emby）",
          content: `dry_run 计划：上传 ${plan.up} / 跳过 ${plan.skip} / 失败 ${plan.fail}。

确认后真的开始上传：把这 ${plan.up} 张头像写进 Emby 的 Person 实体（Primary 图）；计划里已跳过的 ${plan.skip} 位不会动，也没有别的写入。`,
          confirmText: `上传 ${plan.up} 张`,
          cancelText: "取消"
        });
        if (!go) {
          t.info("已取消，没有向 Emby 写入任何东西");
          return;
        }
        t.info(`正在上传 ${plan.up} 张头像…`);
        const payload = await postJson("plugin/scrape/avatars", { dry_run: false, force });
        const done = countAvatarActions(payload);
        runResult.value = avatarResult(done, false);
        if (runResult.value.ok) t.success(`头像同步完成：${avatarText(done, false)}`);
        else t.warning(`头像同步未全部成功：${avatarText(done, false)}`);
      } catch (err) {
        runResult.value = { ok: false, text: "头像同步请求失败", errors: [errorText(err)] };
        t.warning(`头像同步失败：${errorText(err)}`);
      } finally {
        busy.value = "";
      }
    }
    const sources = computed$5(() => {
      const list = firstArray(statusData.value, ["sources"]);
      return Array.isArray(list) ? list : [];
    });
    const logItems = ref$6([]);
    const logSummary = ref$6([]);
    const logLoading = ref$6(false);
    const logError = ref$6("");
    function sourceName(row) {
      return text(row?.name ?? row?.source ?? row?.source_name) || "(未命名源)";
    }
    function sourceState(row) {
      const status = text(row?.status ?? row?.state).trim();
      const okFlag = row?.ok;
      const bad = /fail|error|down|异常|失败/i.test(status) || okFlag === false;
      const good = /ok|success|ready|正常|成功/i.test(status) || okFlag === true;
      const label = status || (okFlag === true ? "ok" : okFlag === false ? "error" : "—");
      return { text: label, color: bad ? "error" : good ? "success" : "info" };
    }
    function latencyText(value) {
      const num = Number(value);
      return Number.isFinite(num) && num > 0 ? `${Math.round(num)} ms` : "—";
    }
    function sourceError(row) {
      return text(row?.error ?? row?.error_summary) || text(row?.detail?.why) || "—";
    }
    function sourceReason(row) {
      return text(row?.reason);
    }
    function reasonText(row) {
      const counts = row?.reasons;
      if (!counts || typeof counts !== "object") return "—";
      const pairs = Object.entries(counts).filter(([, n]) => Number(n) > 0).sort((a, b) => Number(b[1]) - Number(a[1]));
      if (!pairs.length) return "—";
      const head = pairs.slice(0, 3).map(([key, n]) => `${key}×${Number(n)}`);
      const rest = pairs.length - head.length;
      return rest > 0 ? `${head.join("、")} +${rest}` : head.join("、");
    }
    function sourceCheckedAt(row) {
      return shortTime(row?.checked_at ?? row?.updated_at ?? row?.at ?? row?.time ?? row?.created_at);
    }
    async function loadLog() {
      if (logLoading.value) return;
      logLoading.value = true;
      logError.value = "";
      sourcesLoaded.value = true;
      try {
        const payload = await getJson("plugin/scrape/log", { limit: 50 });
        logItems.value = Array.isArray(payload?.items) ? payload.items : [];
        logSummary.value = Array.isArray(payload?.summary) ? payload.summary : [];
      } catch (err) {
        logItems.value = [];
        logSummary.value = [];
        logError.value = errorText(err);
      } finally {
        logLoading.value = false;
      }
    }
    async function refreshSelfcheck() {
      if (busy.value) return;
      busy.value = "selfcheck";
      t.info("正在重新读取各数据源状态…");
      try {
        await loadStatus();
        await loadLog();
        if (statusError.value) t.warning(`状态读取失败：${statusError.value}`);
        else t.success("已刷新各数据源状态");
      } finally {
        busy.value = "";
      }
    }
    function badgeOf(row) {
      const direct = text(row.raw?.badge).trim();
      if (direct) return direct;
      const tags = row.versionTags;
      if (Array.isArray(tags)) return tags.map((item) => text(item)).filter(Boolean).join("/");
      if (tags && typeof tags === "object") {
        const dict = tags;
        const out = [];
        if (dict.is_zh_sub) out.push("中字");
        if (dict.is_uncensored_leak) out.push("流出");
        const res = text(dict.resolution).trim();
        if (res) out.push(/2160|4k/i.test(res) ? "4K" : res.toUpperCase());
        if (dict.is_iso) out.push("ISO");
        if (dict.is_vr) out.push("VR");
        return out.join("/");
      }
      return "";
    }
    function logStatusColor(status) {
      const value = text(status).toLowerCase();
      if (value === "ok" || value === "success") return "success";
      if (value === "error" || value === "failed" || value === "fail") return "error";
      return "info";
    }
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$6("v-btn");
      const _component_v_icon = _resolveComponent$6("v-icon");
      const _component_v_alert = _resolveComponent$6("v-alert");
      const _component_v_checkbox = _resolveComponent$6("v-checkbox");
      const _component_v_list_item = _resolveComponent$6("v-list-item");
      const _component_v_list = _resolveComponent$6("v-list");
      const _component_v_menu = _resolveComponent$6("v-menu");
      const _component_v_chip = _resolveComponent$6("v-chip");
      return _openBlock$6(), _createElementBlock$6("div", _hoisted_1$6, [
        _createElementVNode$6("div", _hoisted_2$6, [
          _createElementVNode$6("div", _hoisted_3$4, [
            (_openBlock$6(), _createElementBlock$6(_Fragment$5, null, _renderList$5(TABS, (item) => {
              return _createElementVNode$6("button", {
                key: item.key,
                class: _normalizeClass$3({ "avh-tabs__on": item.key === tab.value }),
                onClick: ($event) => pickTab(item.key)
              }, _toDisplayString$6(item.name), 11, _hoisted_4$4);
            }), 64))
          ]),
          tab.value === "workbench" ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_5$4, " 点行内「刮削」可以自己挑这次写哪些信息；批量刮削会把抓到的全部信息写一遍 ")) : (_openBlock$6(), _createElementBlock$6("span", _hoisted_6$4, "各源最近状态取自 GET /scrape/status · 流水取自 GET /scrape/log")),
          _cache[7] || (_cache[7] = _createElementVNode$6("div", { class: "avh-scrape__spacer" }, null, -1)),
          _createVNode$5(_component_v_btn, {
            variant: "outlined",
            size: "small",
            loading: loading.value,
            onClick: _cache[0] || (_cache[0] = ($event) => load(true))
          }, {
            default: _withCtx$6(() => _cache[6] || (_cache[6] = [
              _createTextVNode$4("↻ 刷新")
            ])),
            _: 1
          }, 8, ["loading"])
        ]),
        tab.value === "workbench" ? (_openBlock$6(), _createElementBlock$6(_Fragment$5, { key: 0 }, [
          _createElementVNode$6("div", _hoisted_7$4, [
            (_openBlock$6(), _createElementBlock$6(_Fragment$5, null, _renderList$5(STATUS_ORDER, (key) => {
              return _createElementVNode$6("div", {
                key,
                class: _normalizeClass$3(["avh-stat", { "avh-stat--on": filter.value === key }]),
                title: STATUS_META[key].hint,
                onClick: ($event) => toggleFilter(key)
              }, [
                _createElementVNode$6("div", _hoisted_9$3, _toDisplayString$6(stats.value[key]), 1),
                _createElementVNode$6("div", _hoisted_10$3, _toDisplayString$6(STATUS_META[key].label), 1)
              ], 10, _hoisted_8$3);
            }), 64)),
            _createElementVNode$6("div", {
              class: _normalizeClass$3(["avh-stat", { "avh-stat--on": filter.value === "" }]),
              title: "全部（点一下清掉筛选）",
              onClick: _cache[1] || (_cache[1] = ($event) => filter.value = "")
            }, [
              _createElementVNode$6("div", _hoisted_11$3, _toDisplayString$6(stats.value.total), 1),
              _cache[8] || (_cache[8] = _createElementVNode$6("div", { class: "avh-stat__label" }, "全部", -1))
            ], 2)
          ]),
          _createElementVNode$6("div", _hoisted_12$3, [
            (_openBlock$6(), _createElementBlock$6(_Fragment$5, null, _renderList$5(STATUS_ORDER, (key) => {
              return _createElementVNode$6("span", {
                key: `legend#${key}`,
                class: "avh-scrape__legenditem"
              }, [
                _createVNode$5(_component_v_icon, {
                  icon: "mdi-circle",
                  color: STATUS_META[key].color,
                  size: "8",
                  class: "me-1"
                }, null, 8, ["color"]),
                _createTextVNode$4(" " + _toDisplayString$6(STATUS_META[key].legend), 1)
              ]);
            }), 64))
          ]),
          _createElementVNode$6("div", _hoisted_13$3, [
            _createElementVNode$6("span", _hoisted_14$3, " 定时重刮队列：等重试 " + _toDisplayString$6(queueInfo.value.tier1 === null ? "—" : queueInfo.value.tier1) + " · 排队补刮 " + _toDisplayString$6(queueInfo.value.tier2 === null ? "—" : queueInfo.value.tier2) + " · 上次运行 " + _toDisplayString$6(lastRun.value || "—"), 1),
            filter.value ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_15$2, "· 正在筛选「" + _toDisplayString$6(filterLabel.value) + "」（" + _toDisplayString$6(visibleRows.value.length) + " 条）", 1)) : _createCommentVNode$5("", true)
          ]),
          error.value && !rows.value.length ? (_openBlock$6(), _createBlock$6(ErrorState, {
            key: 0,
            message: `刮削状态读取失败：${error.value}`,
            retrying: loading.value,
            onRetry: _cache[2] || (_cache[2] = ($event) => load(false))
          }, null, 8, ["message", "retrying"])) : error.value && rows.value.length ? (_openBlock$6(), _createBlock$6(_component_v_alert, {
            key: 1,
            type: "warning",
            variant: "tonal",
            density: "compact",
            class: "text-caption mb-2"
          }, {
            default: _withCtx$6(() => [
              _createTextVNode$4(_toDisplayString$6(error.value) + "（列表已回落到 GET /library）", 1)
            ]),
            _: 1
          })) : _createCommentVNode$5("", true),
          runResult.value ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_16$2, [
            _createVNode$5(_component_v_alert, {
              type: runResult.value.ok ? "success" : "warning",
              variant: "tonal",
              density: "compact",
              class: "text-caption"
            }, {
              default: _withCtx$6(() => [
                _createElementVNode$6("div", null, _toDisplayString$6(runResult.value.text), 1),
                (_openBlock$6(true), _createElementBlock$6(_Fragment$5, null, _renderList$5(runResult.value.notes || [], (line, index) => {
                  return _openBlock$6(), _createElementBlock$6("div", {
                    key: `note#${index}`
                  }, _toDisplayString$6(line), 1);
                }), 128)),
                (_openBlock$6(true), _createElementBlock$6(_Fragment$5, null, _renderList$5(runResult.value.errors, (line, index) => {
                  return _openBlock$6(), _createElementBlock$6("div", { key: index }, _toDisplayString$6(line), 1);
                }), 128))
              ]),
              _: 1
            }, 8, ["type"])
          ])) : _createCommentVNode$5("", true),
          rows.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_17$2, [
            _createVNode$5(_component_v_checkbox, {
              "model-value": allVisibleSelected.value,
              density: "compact",
              "hide-details": "",
              label: "全选当前列表",
              class: "avh-scrape__checkall",
              "onUpdate:modelValue": toggleAll
            }, null, 8, ["model-value"]),
            _createVNode$5(_component_v_btn, {
              color: "primary",
              variant: "flat",
              size: "small",
              "prepend-icon": "mdi-auto-fix",
              disabled: !selected.value.size || !!busy.value,
              loading: busy.value === "run:batch",
              onClick: runSelected
            }, {
              default: _withCtx$6(() => [
                _createTextVNode$4("批量刮削（" + _toDisplayString$6(selected.value.size) + "）", 1)
              ]),
              _: 1
            }, 8, ["disabled", "loading"]),
            _cache[10] || (_cache[10] = _createElementVNode$6("span", { class: "avh-scrape__hint" }, "批量会先弹一次确认，把抓到的全部信息写一遍", -1)),
            _createVNode$5(_component_v_btn, {
              variant: "outlined",
              size: "small",
              "prepend-icon": "mdi-account-box-outline",
              disabled: !!busy.value,
              loading: busy.value === "avatars",
              onClick: _cache[3] || (_cache[3] = ($event) => syncAvatars(false))
            }, {
              default: _withCtx$6(() => _cache[9] || (_cache[9] = [
                _createTextVNode$4("同步演员头像")
              ])),
              _: 1
            }, 8, ["disabled", "loading"]),
            _createVNode$5(_component_v_menu, { location: "bottom" }, {
              activator: _withCtx$6(({ props: menuProps }) => [
                _createVNode$5(_component_v_btn, _mergeProps({
                  variant: "text",
                  size: "small",
                  icon: "mdi-dots-vertical",
                  disabled: !!busy.value
                }, menuProps), null, 16, ["disabled"])
              ]),
              default: _withCtx$6(() => [
                _createVNode$5(_component_v_list, { density: "compact" }, {
                  default: _withCtx$6(() => [
                    _createVNode$5(_component_v_list_item, {
                      title: "重新同步全部头像（覆盖已有）",
                      subtitle: "把旧的糊头像换成高清图",
                      onClick: _cache[4] || (_cache[4] = ($event) => syncAvatars(true))
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[11] || (_cache[11] = _createElementVNode$6("span", { class: "avh-scrape__hint" }, " 全库同步、与勾选无关 · 先出计划（零写请求），确认后才写 Person 实体 · 头像优先取高清源（Gfriends），换不掉旧图时用右边菜单里的「重新同步全部」 ", -1))
          ])) : _createCommentVNode$5("", true),
          loading.value && !rows.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_18$2, "正在读取刮削状态…")) : !rows.value.length && !error.value ? (_openBlock$6(), _createBlock$6(EmptyState, {
            key: 5,
            text: "还没有可刮削的条目<br>后端把 meta 表建起来、或 Emby 库里已有影片后，这里会按状态列出全部番号",
            hint: "本页数据来自 GET /scrape/status（items）与 GET /library；接口没上线时只会看到这句空态"
          })) : !visibleRows.value.length && filter.value ? (_openBlock$6(), _createBlock$6(EmptyState, {
            key: 6,
            text: "该状态下没有条目",
            hint: "点顶部「全部」清掉筛选"
          })) : visibleRows.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_19$2, [
            _createElementVNode$6("table", _hoisted_20$2, [
              _cache[13] || (_cache[13] = _createElementVNode$6("colgroup", null, [
                _createElementVNode$6("col", { style: { "width": "36px" } }),
                _createElementVNode$6("col", { style: { "width": "152px" } }),
                _createElementVNode$6("col"),
                _createElementVNode$6("col", { style: { "width": "96px" } }),
                _createElementVNode$6("col", { style: { "width": "190px" } })
              ], -1)),
              _cache[14] || (_cache[14] = _createElementVNode$6("thead", null, [
                _createElementVNode$6("tr", null, [
                  _createElementVNode$6("th"),
                  _createElementVNode$6("th", null, "番号"),
                  _createElementVNode$6("th", null, "标题"),
                  _createElementVNode$6("th", null, "状态"),
                  _createElementVNode$6("th", { class: "avh-table__right" }, "操作")
                ])
              ], -1)),
              _createElementVNode$6("tbody", null, [
                (_openBlock$6(true), _createElementBlock$6(_Fragment$5, null, _renderList$5(visibleRows.value, (row) => {
                  return _openBlock$6(), _createElementBlock$6("tr", {
                    key: rowId(row)
                  }, [
                    _createElementVNode$6("td", null, [
                      _createVNode$5(_component_v_checkbox, {
                        "model-value": isSelected(row),
                        density: "compact",
                        "hide-details": "",
                        "onUpdate:modelValue": ($event) => toggleRow(row)
                      }, null, 8, ["model-value", "onUpdate:modelValue"])
                    ]),
                    _createElementVNode$6("td", _hoisted_21$1, [
                      _createTextVNode$4(_toDisplayString$6(row.number) + " ", 1),
                      badgeOf(row) ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_22$1, _toDisplayString$6(badgeOf(row)), 1)) : _createCommentVNode$5("", true)
                    ]),
                    _createElementVNode$6("td", {
                      title: row.title
                    }, _toDisplayString$6(row.title || "—"), 9, _hoisted_23$1),
                    _createElementVNode$6("td", null, [
                      _createVNode$5(_component_v_chip, {
                        size: "x-small",
                        color: STATUS_META[row.status].color,
                        variant: "tonal"
                      }, {
                        default: _withCtx$6(() => [
                          _createTextVNode$4(_toDisplayString$6(STATUS_META[row.status].label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"]),
                      row.statusRaw && row.statusRaw !== row.status ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_24$1, _toDisplayString$6(row.statusRaw), 1)) : _createCommentVNode$5("", true)
                    ]),
                    _createElementVNode$6("td", _hoisted_25$1, [
                      _createElementVNode$6("div", _hoisted_26$1, [
                        _createVNode$5(_component_v_btn, {
                          size: "x-small",
                          variant: "outlined",
                          color: "primary",
                          disabled: !!busy.value,
                          onClick: ($event) => openScrape(row)
                        }, {
                          default: _withCtx$6(() => _cache[12] || (_cache[12] = [
                            _createTextVNode$4("刮削")
                          ])),
                          _: 2
                        }, 1032, ["disabled", "onClick"])
                      ])
                    ])
                  ]);
                }), 128))
              ])
            ])
          ])) : _createCommentVNode$5("", true)
        ], 64)) : (_openBlock$6(), _createElementBlock$6(_Fragment$5, { key: 1 }, [
          _createElementVNode$6("div", _hoisted_27$1, [
            _createVNode$5(_component_v_btn, {
              color: "primary",
              variant: "flat",
              size: "small",
              "prepend-icon": "mdi-stethoscope",
              loading: busy.value === "selfcheck",
              disabled: !!busy.value && busy.value !== "selfcheck",
              onClick: refreshSelfcheck
            }, {
              default: _withCtx$6(() => _cache[15] || (_cache[15] = [
                _createTextVNode$4("立即自检")
              ])),
              _: 1
            }, 8, ["loading", "disabled"]),
            _cache[16] || (_cache[16] = _createElementVNode$6("span", { class: "avh-scrape__hint" }, [
              _createTextVNode$4(" 契约 §3.7 没有触发式自检端点，这里如实重新读取 "),
              _createElementVNode$6("code", null, "GET /scrape/status"),
              _createTextVNode$4(" 的 "),
              _createElementVNode$6("code", null, "sources"),
              _createTextVNode$4("（各源最近状态就是它给的） ")
            ], -1))
          ]),
          statusError.value ? (_openBlock$6(), _createBlock$6(_component_v_alert, {
            key: 0,
            type: "warning",
            variant: "tonal",
            density: "compact",
            class: "text-caption mb-2"
          }, {
            default: _withCtx$6(() => [
              _createTextVNode$4("状态读取失败：" + _toDisplayString$6(statusError.value), 1)
            ]),
            _: 1
          })) : _createCommentVNode$5("", true),
          _createElementVNode$6("div", _hoisted_28$1, "数据源（" + _toDisplayString$6(sources.value.length) + "）", 1),
          sources.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_29$1, [
            _createElementVNode$6("table", _hoisted_30$1, [
              _cache[17] || (_cache[17] = _createElementVNode$6("colgroup", null, [
                _createElementVNode$6("col", { style: { "width": "150px" } }),
                _createElementVNode$6("col", { style: { "width": "96px" } }),
                _createElementVNode$6("col", { style: { "width": "88px" } }),
                _createElementVNode$6("col"),
                _createElementVNode$6("col", { style: { "width": "130px" } })
              ], -1)),
              _cache[18] || (_cache[18] = _createElementVNode$6("thead", null, [
                _createElementVNode$6("tr", null, [
                  _createElementVNode$6("th", null, "源"),
                  _createElementVNode$6("th", null, "最近状态"),
                  _createElementVNode$6("th", null, "耗时"),
                  _createElementVNode$6("th", null, "错误摘要"),
                  _createElementVNode$6("th", null, "检查时间")
                ])
              ], -1)),
              _createElementVNode$6("tbody", null, [
                (_openBlock$6(true), _createElementBlock$6(_Fragment$5, null, _renderList$5(sources.value, (row, index) => {
                  return _openBlock$6(), _createElementBlock$6("tr", {
                    key: `${sourceName(row)}#${index}`
                  }, [
                    _createElementVNode$6("td", null, _toDisplayString$6(sourceName(row)), 1),
                    _createElementVNode$6("td", null, [
                      _createVNode$5(_component_v_chip, {
                        size: "x-small",
                        color: sourceState(row).color,
                        variant: "tonal"
                      }, {
                        default: _withCtx$6(() => [
                          _createTextVNode$4(_toDisplayString$6(sourceState(row).text), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    _createElementVNode$6("td", null, _toDisplayString$6(latencyText(row?.latency_ms ?? row?.latency ?? row?.ms)), 1),
                    _createElementVNode$6("td", {
                      class: "avh-table__ellipsis",
                      title: sourceError(row)
                    }, [
                      sourceReason(row) ? (_openBlock$6(), _createElementBlock$6("code", _hoisted_32$1, _toDisplayString$6(sourceReason(row)), 1)) : _createCommentVNode$5("", true),
                      _createTextVNode$4(" " + _toDisplayString$6(sourceError(row)), 1)
                    ], 8, _hoisted_31$1),
                    _createElementVNode$6("td", null, _toDisplayString$6(sourceCheckedAt(row)), 1)
                  ]);
                }), 128))
              ])
            ])
          ])) : (_openBlock$6(), _createBlock$6(EmptyState, {
            key: 2,
            text: "还没有数据源状态",
            hint: "GET /scrape/status 的 sources 为空（接口没上线，或后端还没跑过自检）"
          })),
          _createElementVNode$6("div", _hoisted_33$1, [
            _createElementVNode$6("span", null, "最近流水（" + _toDisplayString$6(logItems.value.length) + "）", 1),
            logSummary.value.length ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_34$1, "summary " + _toDisplayString$6(logSummary.value.length) + " 组", 1)) : _createCommentVNode$5("", true),
            _createVNode$5(_component_v_btn, {
              variant: "text",
              size: "x-small",
              class: "ms-2",
              loading: logLoading.value,
              onClick: loadLog
            }, {
              default: _withCtx$6(() => _cache[19] || (_cache[19] = [
                _createTextVNode$4("↻ 重新读取")
              ])),
              _: 1
            }, 8, ["loading"])
          ]),
          logError.value ? (_openBlock$6(), _createBlock$6(_component_v_alert, {
            key: 3,
            type: "warning",
            variant: "tonal",
            density: "compact",
            class: "text-caption mb-2"
          }, {
            default: _withCtx$6(() => [
              _createTextVNode$4("流水读取失败（GET /scrape/log）：" + _toDisplayString$6(logError.value), 1)
            ]),
            _: 1
          })) : _createCommentVNode$5("", true),
          logItems.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_35$1, [
            _createElementVNode$6("table", _hoisted_36$1, [
              _cache[20] || (_cache[20] = _createElementVNode$6("colgroup", null, [
                _createElementVNode$6("col", { style: { "width": "120px" } }),
                _createElementVNode$6("col", { style: { "width": "88px" } }),
                _createElementVNode$6("col", { style: { "width": "130px" } }),
                _createElementVNode$6("col", { style: { "width": "88px" } }),
                _createElementVNode$6("col"),
                _createElementVNode$6("col", { style: { "width": "130px" } })
              ], -1)),
              _cache[21] || (_cache[21] = _createElementVNode$6("thead", null, [
                _createElementVNode$6("tr", null, [
                  _createElementVNode$6("th", null, "源"),
                  _createElementVNode$6("th", null, "状态"),
                  _createElementVNode$6("th", null, "番号"),
                  _createElementVNode$6("th", null, "耗时"),
                  _createElementVNode$6("th", null, "错误"),
                  _createElementVNode$6("th", null, "时间")
                ])
              ], -1)),
              _createElementVNode$6("tbody", null, [
                (_openBlock$6(true), _createElementBlock$6(_Fragment$5, null, _renderList$5(logItems.value, (row, index) => {
                  return _openBlock$6(), _createElementBlock$6("tr", {
                    key: `${row?.created_at || ""}#${index}`
                  }, [
                    _createElementVNode$6("td", null, _toDisplayString$6(sourceName(row)), 1),
                    _createElementVNode$6("td", null, [
                      _createVNode$5(_component_v_chip, {
                        size: "x-small",
                        color: logStatusColor(row?.status),
                        variant: "tonal"
                      }, {
                        default: _withCtx$6(() => [
                          _createTextVNode$4(_toDisplayString$6(text(row?.status) || "—"), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"]),
                      sourceReason(row) ? (_openBlock$6(), _createElementBlock$6("code", _hoisted_37$1, _toDisplayString$6(sourceReason(row)), 1)) : _createCommentVNode$5("", true)
                    ]),
                    _createElementVNode$6("td", null, _toDisplayString$6(text(row?.key) || "—"), 1),
                    _createElementVNode$6("td", null, _toDisplayString$6(latencyText(row?.latency_ms)), 1),
                    _createElementVNode$6("td", {
                      class: "avh-table__ellipsis",
                      title: text(row?.error)
                    }, _toDisplayString$6(text(row?.error) || "—"), 9, _hoisted_38$1),
                    _createElementVNode$6("td", null, _toDisplayString$6(_unref$2(shortTime)(row?.created_at)), 1)
                  ]);
                }), 128))
              ])
            ])
          ])) : !logLoading.value && !logError.value ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_39$1, "还没有流水记录。")) : _createCommentVNode$5("", true),
          logSummary.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_40$1, "summary")) : _createCommentVNode$5("", true),
          logSummary.value.length ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_41$1, [
            _createElementVNode$6("table", _hoisted_42$1, [
              _cache[22] || (_cache[22] = _createElementVNode$6("thead", null, [
                _createElementVNode$6("tr", null, [
                  _createElementVNode$6("th", null, "源"),
                  _createElementVNode$6("th", null, "条数"),
                  _createElementVNode$6("th", null, "失败"),
                  _createElementVNode$6("th", null, "原因分布")
                ])
              ], -1)),
              _createElementVNode$6("tbody", null, [
                (_openBlock$6(true), _createElementBlock$6(_Fragment$5, null, _renderList$5(logSummary.value, (row, index) => {
                  return _openBlock$6(), _createElementBlock$6("tr", {
                    key: `sum#${index}`
                  }, [
                    _createElementVNode$6("td", null, _toDisplayString$6(sourceName(row)), 1),
                    _createElementVNode$6("td", null, _toDisplayString$6(text(row?.total ?? row?.count ?? "—")), 1),
                    _createElementVNode$6("td", null, [
                      _createTextVNode$4(_toDisplayString$6(text(row?.fail ?? row?.failed ?? row?.errors ?? "—")) + " ", 1),
                      Number(row?.skipped) > 0 ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_43$1, " 跳过 " + _toDisplayString$6(row.skipped), 1)) : _createCommentVNode$5("", true)
                    ]),
                    _createElementVNode$6("td", {
                      class: "avh-table__ellipsis",
                      title: reasonText(row)
                    }, _toDisplayString$6(reasonText(row)), 9, _hoisted_44$1)
                  ]);
                }), 128))
              ])
            ])
          ])) : _createCommentVNode$5("", true)
        ], 64)),
        _createVNode$5(ScrapeDialog, {
          ref_key: "scrapeDialog",
          ref: scrapeDialog,
          api: _ctx.api,
          "plugin-id": _ctx.pluginId,
          toast: _ctx.toast,
          onDone: _cache[5] || (_cache[5] = ($event) => load(false))
        }, null, 8, ["api", "plugin-id", "toast"])
      ]);
    };
  }
});

const ScrapeView = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-8bc44df4"]]);

const {defineComponent:_defineComponent$5} = await importShared('vue');

const {createElementVNode:_createElementVNode$5,toDisplayString:_toDisplayString$5,openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,createCommentVNode:_createCommentVNode$4,resolveComponent:_resolveComponent$5,withKeys:_withKeys$1,withCtx:_withCtx$5,createBlock:_createBlock$5} = await importShared('vue');

const _hoisted_1$5 = ["src"];
const _hoisted_2$5 = { class: "avh-lb__ctr" };
const {onBeforeUnmount: onBeforeUnmount$3,onMounted: onMounted$3,ref: ref$5} = await importShared('vue');

const _sfc_main$5 = /* @__PURE__ */ _defineComponent$5({
  __name: "Lightbox",
  emits: ["closed"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const open = ref$5(false);
    const list = ref$5([]);
    const idx = ref$5(0);
    const failed = ref$5(false);
    const emit = __emit;
    function show(index) {
      idx.value = index;
      failed.value = false;
    }
    function openAt(images, index = 0) {
      const items = (images || []).filter(Boolean).map((item) => String(item));
      if (!items.length) return;
      list.value = items;
      let next = Number(index) || 0;
      if (next < 0) next = items.length - 1;
      if (next < 0 || next >= items.length) next = 0;
      show(next);
      open.value = true;
    }
    function step(delta) {
      const total = list.value.length;
      if (!total) return;
      show(((idx.value + delta + total) % total + total) % total);
    }
    function close() {
      open.value = false;
      emit("closed");
    }
    function onImgError() {
      failed.value = true;
    }
    function onKeydown(event) {
      if (!open.value) return;
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        step(-1);
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        step(1);
      }
    }
    onMounted$3(() => document.addEventListener("keydown", onKeydown, true));
    onBeforeUnmount$3(() => document.removeEventListener("keydown", onKeydown, true));
    function onBackdrop(event) {
      if (event.target === event.currentTarget) close();
    }
    const isOpen = () => open.value;
    __expose({ openAt, step, close, isOpen });
    return (_ctx, _cache) => {
      const _component_v_overlay = _resolveComponent$5("v-overlay");
      return _openBlock$5(), _createBlock$5(_component_v_overlay, {
        modelValue: open.value,
        "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => open.value = $event),
        "z-index": 3e3,
        class: "avh-lb-overlay",
        onKeydown: _withKeys$1(close, ["esc"])
      }, {
        default: _withCtx$5(() => [
          open.value ? (_openBlock$5(), _createElementBlock$5("div", {
            key: 0,
            class: "avh-lb",
            onClick: onBackdrop
          }, [
            _createElementVNode$5("img", {
              class: "avh-lb__img",
              src: list.value[idx.value] || "",
              alt: "",
              onError: onImgError
            }, null, 40, _hoisted_1$5),
            _createElementVNode$5("div", {
              class: "avh-lb__nav avh-lb__prev",
              role: "button",
              "aria-label": "上一张",
              onClick: _cache[0] || (_cache[0] = ($event) => step(-1))
            }, "‹"),
            _createElementVNode$5("div", {
              class: "avh-lb__nav avh-lb__next",
              role: "button",
              "aria-label": "下一张",
              onClick: _cache[1] || (_cache[1] = ($event) => step(1))
            }, "›"),
            _createElementVNode$5("div", _hoisted_2$5, _toDisplayString$5(idx.value + 1) + " / " + _toDisplayString$5(list.value.length) + _toDisplayString$5(failed.value ? "（图片加载失败）" : ""), 1),
            _createElementVNode$5("div", {
              class: "avh-lb__close",
              role: "button",
              "aria-label": "关闭",
              onClick: close
            }, "✕")
          ])) : _createCommentVNode$4("", true)
        ]),
        _: 1
      }, 8, ["modelValue"]);
    };
  }
});

const Lightbox = /* @__PURE__ */ _export_sfc(_sfc_main$5, [["__scopeId", "data-v-174e2165"]]);

const {defineComponent:_defineComponent$4} = await importShared('vue');

const {toDisplayString:_toDisplayString$4,createElementVNode:_createElementVNode$4,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$4,withCtx:_withCtx$4,openBlock:_openBlock$4,createBlock:_createBlock$4,createCommentVNode:_createCommentVNode$3,createVNode:_createVNode$4,createElementBlock:_createElementBlock$4,Fragment:_Fragment$4,renderList:_renderList$4,normalizeClass:_normalizeClass$2,normalizeStyle:_normalizeStyle} = await importShared('vue');

const _hoisted_1$4 = { class: "avh-detail__head" };
const _hoisted_2$4 = { class: "avh-detail__title" };
const _hoisted_3$3 = { class: "avh-hero" };
const _hoisted_4$3 = { class: "avh-hero__big" };
const _hoisted_5$3 = ["src", "alt"];
const _hoisted_6$3 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_7$3 = { class: "avh-hero__info" };
const _hoisted_8$2 = { class: "avh-hero__num" };
const _hoisted_9$2 = {
  key: 0,
  class: "avh-librow"
};
const _hoisted_10$2 = ["href"];
const _hoisted_11$2 = {
  key: 1,
  class: "avh-dlrow"
};
const _hoisted_12$2 = {
  key: 2,
  class: "avh-hero__ttl"
};
const _hoisted_13$2 = { class: "avh-actorchips" };
const _hoisted_14$2 = ["title", "onClick"];
const _hoisted_15$1 = { class: "avh-actorchip__body" };
const _hoisted_16$1 = { class: "avh-actorchip__nm" };
const _hoisted_17$1 = {
  key: 0,
  class: "avh-actorchip__zh"
};
const _hoisted_18$1 = {
  key: 1,
  class: "avh-actorchip__alias"
};
const _hoisted_19$1 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_20$1 = { class: "avh-kv" };
const _hoisted_21 = {
  key: 0,
  style: { "color": "rgb(var(--v-theme-success))" }
};
const _hoisted_22 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_23 = { key: 0 };
const _hoisted_24 = { key: 1 };
const _hoisted_25 = { class: "avh-acts" };
const _hoisted_26 = { class: "avh-secttl" };
const _hoisted_27 = { class: "avh-shots" };
const _hoisted_28 = ["onClick"];
const _hoisted_29 = {
  key: 0,
  class: "avh-shot__noimg"
};
const _hoisted_30 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_31 = { class: "avh-secttl" };
const _hoisted_32 = { key: 0 };
const _hoisted_33 = { class: "avh-mag__mg" };
const _hoisted_34 = { class: "avh-mag__mn" };
const _hoisted_35 = { class: "avh-mag__mh" };
const _hoisted_36 = {
  key: 0,
  class: "avh-tag avh-tag--pref"
};
const _hoisted_37 = {
  key: 1,
  class: "avh-tag"
};
const _hoisted_38 = {
  key: 0,
  class: "avh-mag__mh avh-mag__mh--link"
};
const _hoisted_39 = ["href"];
const _hoisted_40 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_41 = { class: "avh-longwrap" };
const _hoisted_42 = {
  key: 0,
  class: "avh-longerr"
};
const _hoisted_43 = {
  key: 0,
  class: "avh-longerr__url"
};
const _hoisted_44 = { class: "avh-longerr__act" };
const _hoisted_45 = ["src", "width", "height"];
const _hoisted_46 = {
  key: 2,
  class: "avh-hint"
};
const _hoisted_47 = {
  key: 3,
  class: "avh-hint"
};
const _hoisted_48 = {
  key: 2,
  class: "avh-hero"
};
const _hoisted_49 = { class: "avh-hero__big" };
const _hoisted_50 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_51 = { class: "avh-hero__info" };
const _hoisted_52 = { class: "avh-hero__num" };
const _hoisted_53 = { class: "avh-kv" };
const _hoisted_54 = { key: 0 };
const _hoisted_55 = { key: 1 };
const {computed: computed$4,nextTick: nextTick$1,onBeforeUnmount: onBeforeUnmount$2,onMounted: onMounted$2,ref: ref$4,watch: watch$3} = await importShared('vue');
const _sfc_main$4 = /* @__PURE__ */ _defineComponent$4({
  __name: "DetailDrawer",
  props: {
    open: { type: Boolean, default: false },
    number: { default: "" },
    id: { default: "" },
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["close", "openActor", "refreshSide"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    function onKeydown(event) {
      if (event.key !== "Escape" || !props.open) return;
      if (lightbox.value?.isOpen?.()) return;
      emit("close");
    }
    onMounted$2(() => document.addEventListener("keydown", onKeydown, true));
    onBeforeUnmount$2(() => document.removeEventListener("keydown", onKeydown, true));
    const t = hostToast(props.toast);
    const IMG_FALLBACK = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="100%" height="100%" fill="#1c232d"/><text x="50%" y="50%" fill="#6b7887" font-size="16" text-anchor="middle">图片加载失败</text></svg>'
    );
    let freshNumber = "";
    const bodyEl = ref$4(null);
    const lightbox = ref$4(null);
    function scrollHostOf(el) {
      if (!el) return null;
      const root = el.closest(".v-navigation-drawer") || el.closest(".avh-detail");
      let node = el;
      while (node) {
        if (node.scrollHeight - node.clientHeight > 1) return node;
        if (node === root) break;
        node = node.parentElement;
      }
      return el;
    }
    function scrollTopIfFresh() {
      if (freshNumber !== activeNumber.value) return;
      freshNumber = "";
      const el = bodyEl.value;
      if (!el) return;
      el.scrollTop = 0;
      const host = scrollHostOf(el);
      if (host && host !== el) host.scrollTop = 0;
    }
    const activeNumber = computed$4(() => String(props.number || ""));
    const lastId = ref$4("");
    const fetching = ref$4(false);
    const entry = computed$4(() => activeNumber.value ? cachedDetail(activeNumber.value) : void 0);
    const detail = computed$4(() => entry.value && entry.value.data || {});
    const movie = computed$4(() => detail.value.movie || {});
    const actors = computed$4(() => Array.isArray(detail.value.actors) ? detail.value.actors : []);
    const previews = computed$4(
      () => Array.isArray(detail.value.previews) ? detail.value.previews : []
    );
    const magnets = computed$4(() => Array.isArray(detail.value.magnets) ? detail.value.magnets : []);
    const num = computed$4(() => String(movie.value.number || activeNumber.value || ""));
    const lightboxImages = computed$4(
      () => [String(movie.value.cover || ""), ...previews.value.map((item) => String(item || ""))].filter(Boolean)
    );
    const detailError = computed$4(() => String(entry.value && entry.value.error || ""));
    const hasDetail = computed$4(() => !!entry.value && !entry.value.error);
    function findMovie(number) {
      if (!number) return null;
      for (const item of rankCache.values()) {
        const list = item && Array.isArray(item.data) ? item.data : null;
        if (!list) continue;
        const hit = list.filter((movie2) => movie2 && String(movie2.number || "") === number)[0];
        if (hit) return hit;
      }
      return null;
    }
    const skeletonMovie = computed$4(() => findMovie(activeNumber.value) || {});
    function findFav(name) {
      const list = props.store.favs.value || [];
      return list.filter((item) => String(item.name || "") === name)[0] || null;
    }
    const faved = computed$4(() => {
      const actor = String(movie.value.actor || "");
      return actor ? !!findFav(actor) : false;
    });
    const actorChips = computed$4(() => {
      if (actors.value.length) {
        return actors.value.map((item) => ({
          name: String(item?.name || ""),
          zh: String(item?.zh || ""),
          avatar: String(item?.avatar || ""),
          alias: aliasOf(String(item?.name || ""))
        }));
      }
      const single = String(movie.value.actor || "");
      if (single) {
        return [{ name: single, zh: "", avatar: String(movie.value.actor_avatar || ""), alias: aliasOf(single) }];
      }
      return [];
    });
    const title = computed$4(() => `影片详情 · ${activeNumber.value}`);
    function aliasOf(name) {
      const key = String(name || "");
      if (!key) return "";
      return String(props.store?.aliases?.value?.[key] || "");
    }
    const coverSrc = ref$4("");
    function syncCover() {
      coverSrc.value = String(movie.value.cover || movie.value.thumb || "");
    }
    function onCoverError() {
      const thumb = String(movie.value.thumb || "");
      if (thumb && coverSrc.value !== thumb) {
        coverSrc.value = thumb;
        return;
      }
      if (coverSrc.value !== IMG_FALLBACK) coverSrc.value = IMG_FALLBACK;
    }
    async function fetchDetail() {
      const number = activeNumber.value;
      if (!number || fetching.value) return;
      fetching.value = true;
      try {
        const res = await fetchDetailRaw(number, number === activeNumber.value ? lastId.value : "");
        if (!res.ok) {
          putDetailError(number, res.message || "抓取失败，请稍后重试");
          t.warning("详情抓取失败");
          t.info(res.message || "抓取失败，请稍后重试");
          return;
        }
        putDetail(number, res.data);
      } finally {
        fetching.value = false;
        void nextTick$1(() => scrollTopIfFresh());
      }
    }
    async function fetchDetailRaw(number, id) {
      const api = props.api;
      if (!api || typeof api.get !== "function") return { ok: false, message: "宿主请求器不可用" };
      const params = { number };
      if (id) params.id = id;
      try {
        const raw = await api.get("plugin/detail", { params });
        const payload = raw && typeof raw === "object" && "data" in raw ? raw.data : raw;
        if (payload && typeof payload === "object" && payload.success === false) {
          return { ok: false, message: String(payload.message || payload.detail || "抓取失败，请稍后重试") };
        }
        return { ok: true, data: payload || {} };
      } catch (err) {
        const status = Number(err?.response?.status || err?.status || 0);
        if (status) return { ok: false, message: `请求失败（HTTP ${status}）` };
        const payload = err?.payload || err?.response?.data;
        const message = String(payload?.message || payload?.detail || err?.message || "");
        return { ok: false, message: message ? `网络请求失败：${message}` : "网络请求失败" };
      }
    }
    function syncCursor(number, id = "") {
      const numValue = String(number || "");
      if (!numValue) return;
      if (activeNumber.value !== numValue) lastId.value = "";
      if (id) lastId.value = String(id);
    }
    function focusFresh() {
      if (freshNumber && freshNumber !== activeNumber.value) acquired.value = false;
      freshNumber = activeNumber.value;
      void nextTick$1(() => scrollTopIfFresh());
    }
    function magnetUri(hash) {
      return hash ? `magnet:?xt=urn:btih:${hash}` : "";
    }
    const dlState = ref$4({});
    function dlLabel(hash) {
      const state = dlState.value[hash] || "idle";
      if (state === "busy") return "⏳ 提交中…";
      if (state === "done") return "✅ 已提交";
      return "⬇ 下载";
    }
    async function downloadMagnet(magnet) {
      const hash = String(magnet?.hash || "");
      if (!hash) return;
      const current = dlState.value[hash] || "idle";
      if (current !== "idle") return;
      const name = String(magnet?.name || "");
      dlState.value = { ...dlState.value, [hash]: "busy" };
      const res = await props.store.downloadMagnet(hash, name, activeNumber.value);
      if (!res.ok) {
        dlState.value = { ...dlState.value, [hash]: "idle" };
        t.warning("下载失败");
        t.info(res.message || "请检查下载器配置");
        return;
      }
      dlState.value = { ...dlState.value, [hash]: "done" };
      t.success("已提交下载");
      t.info(res.message || "进度见「下载」页");
      emit("refreshSide");
    }
    const ptSearching = ref$4(false);
    const acquired = ref$4(false);
    async function ptSearch() {
      const number = num.value;
      if (!number || ptSearching.value) return;
      ptSearching.value = true;
      try {
        const res = await props.store.acquireMovie(number, {
          actor: String(movie.value.actor || ""),
          thumb: String(movie.value.thumb || "")
        });
        if (!res.ok) {
          pushBottomToast("warning", "下载失败");
          pushBottomToast("info", res.message || "抓取失败，请稍后重试");
          return;
        }
        const payload = res.data || {};
        playBottomToasts(payload.toasts);
        if (payload.outcome === "downloaded") acquired.value = true;
        emit("refreshSide");
      } finally {
        ptSearching.value = false;
      }
    }
    const subscribing = ref$4(false);
    async function subscribeNumber() {
      const number = num.value;
      if (!number || subscribing.value) return;
      subscribing.value = true;
      try {
        const res = await props.store.subscribeNumber(number);
        if (!res.ok) {
          t.warning("订阅失败");
          t.info(res.message || "请稍后重试");
          return;
        }
        t.success("订阅已创建");
        t.info(number);
        emit("refreshSide");
      } finally {
        subscribing.value = false;
      }
    }
    const favBusy = ref$4(false);
    async function toggleFav() {
      const actor = String(movie.value.actor || "");
      if (!actor || favBusy.value) return;
      favBusy.value = true;
      try {
        if (findFav(actor)) {
          const res2 = await props.store.delFav(actor);
          if (!res2.ok) {
            t.warning("取消收藏失败");
            t.info(res2.message || "请稍后重试");
            return;
          }
          t.warning("已取消收藏");
          t.info(actor);
          emit("refreshSide");
          return;
        }
        const res = await props.store.addFav(
          actor,
          "",
          String(movie.value.actor_avatar || actorChips.value[0] && actorChips.value[0].avatar || "")
        );
        if (!res.ok) {
          t.warning("收藏失败");
          t.info(res.message || "请稍后重试");
          return;
        }
        t.success("已收藏");
        t.info(`${actor} 会出现在「我的演员」里`);
        emit("refreshSide");
      } finally {
        favBusy.value = false;
      }
    }
    function shotStyle(url) {
      const raw = String(url || "");
      if (!raw) return void 0;
      return { "--bg": `url('${cssUrl(raw)}')` };
    }
    function openShot(index) {
      const offset = movie.value.cover ? 1 : 0;
      lightbox.value?.openAt(lightboxImages.value, index + offset);
    }
    function openCover() {
      lightbox.value?.openAt(lightboxImages.value, 0);
    }
    const long = computed$4(() => longState.get(activeNumber.value) || null);
    const longSrc = ref$4("");
    const longUseProxy = ref$4(false);
    const longError = ref$4(null);
    const longLoading = ref$4(false);
    let longLoadId = 0;
    const longNaturalW = ref$4(0);
    const longNaturalH = ref$4(0);
    function resetLongLoad() {
      longLoadId++;
      longLoading.value = false;
      longError.value = null;
      longSrc.value = "";
      longUseProxy.value = false;
      longNaturalW.value = 0;
      longNaturalH.value = 0;
    }
    function proxySrcOf(raw) {
      const url = String(raw || "");
      if (!url || !props.pluginId) return "";
      return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(url)}`;
    }
    const longProxySrc = computed$4(() => proxySrcOf(String(longSrc.value || long.value?.url || "")));
    const longSrcAttr = computed$4(() => longUseProxy.value ? longProxySrc.value : longSrc.value);
    const longImgKey = computed$4(
      () => `${activeNumber.value}|${longUseProxy.value ? "p" : "d"}#${longSrc.value}`
    );
    function paintLong(url, useProxy = false) {
      const raw = String(url || "");
      if (!raw) return;
      const token = ++longLoadId;
      const target = useProxy ? proxySrcOf(raw) : raw;
      longSrc.value = "";
      longUseProxy.value = useProxy;
      longError.value = null;
      longNaturalW.value = 0;
      longNaturalH.value = 0;
      if (!target) {
        longLoading.value = false;
        longFail("长缩略图加载失败：浏览器直连与插件代理都没取到。");
        return;
      }
      longLoading.value = true;
      const probe = new Image();
      probe.decoding = "async";
      probe.referrerPolicy = "no-referrer";
      probe.onload = () => {
        if (token !== longLoadId) return;
        longNaturalW.value = probe.naturalWidth;
        longNaturalH.value = probe.naturalHeight;
        longLoading.value = false;
        longSrc.value = raw;
      };
      probe.onerror = () => {
        if (token !== longLoadId) return;
        if (!useProxy && proxySrcOf(raw)) {
          paintLong(raw, true);
          return;
        }
        longLoading.value = false;
        longFail("长缩略图加载失败：浏览器直连与插件代理都没取到。");
      };
      probe.src = target;
    }
    function longFail(text) {
      longError.value = text;
      longSrc.value = "";
    }
    const longHint = computed$4(() => {
      if (longError.value) return "";
      if (longLoading.value) return "⏳ 正在加载长缩略图…";
      if (!longSrc.value && long.value && long.value.loading) return "⏳ 正在获取长缩略图…";
      return "";
    });
    const longFetching = computed$4(() => !longSrc.value && !longError.value && !longLoading.value);
    function onLongError(token) {
      if (token !== longLoadId) return;
      longLoading.value = false;
      if (!longUseProxy.value && longProxySrc.value) {
        longUseProxy.value = true;
        return;
      }
      longFail("长缩略图加载失败：浏览器直连与插件代理都没取到。");
    }
    function currentLongToken() {
      return longLoadId;
    }
    async function loadLong(force = false) {
      const number = activeNumber.value;
      if (!number) return;
      if (force) longState.delete(number);
      const known = String(detail.value.longimage || "");
      if (known) longState.set(number, { url: known });
      const state = longState.get(number);
      if (state && state.url) {
        paintLong(state.url);
        return;
      }
      if (state && state.err) {
        longFail(state.err);
        return;
      }
      longError.value = null;
      longSrc.value = "";
      if (state && state.loading) return;
      longState.set(number, { loading: true });
      const res = await fetchLongUrl(props.api, number, force);
      const url = res.ok ? String(res.url || "") : "";
      if (res.ok) {
        longState.set(number, url ? { url } : { err: "该番号在 projectjav / javfree 里都没找到长图。" });
      } else {
        longState.set(number, { err: `长图地址查询失败：${res.message || "请稍后重试"}` });
      }
      if (url) setLongUrl(number, url);
      if (number === activeNumber.value) {
        if (url) paintLong(url);
        else longFail(String((longState.get(number) || {}).err || "长图地址查询失败"));
      }
    }
    function onLongLoad() {
      longError.value = null;
      longLoading.value = false;
    }
    function openLong() {
      const src = longSrcAttr.value;
      if (src) lightbox.value?.openAt([src], 0);
    }
    watch$3(
      () => [props.open, activeNumber.value, props.id],
      ([isOpen, number, id]) => {
        if (!isOpen || !number) return;
        syncCursor(number, String(id || ""));
        focusFresh();
        syncCover();
        dlState.value = {};
        resetLongLoad();
        if (!entry.value) void fetchDetail();
        else void loadLong(false);
      },
      { immediate: true }
    );
    watch$3(
      () => [activeNumber.value, movie.value.cover, movie.value.thumb, detail.value.longimage],
      () => {
        if (!props.open || !activeNumber.value) return;
        syncCover();
        void loadLong(false);
      }
    );
    const retrying = ref$4(false);
    async function retryDetail() {
      const number = activeNumber.value;
      if (!number || retrying.value) return;
      retrying.value = true;
      try {
        dropDetail(number);
        await fetchDetail();
      } finally {
        retrying.value = false;
      }
    }
    const refreshing = ref$4(false);
    async function refreshDetail() {
      const number = activeNumber.value;
      if (!number || refreshing.value) return;
      refreshing.value = true;
      try {
        const res = await fetchDetailRaw(number, number === activeNumber.value ? lastId.value : "");
        if (!res.ok) {
          t.warning("详情抓取失败");
          t.info(res.message || "抓取失败，请稍后重试");
          return;
        }
        putDetail(number, res.data);
        longState.delete(number);
        if (number === activeNumber.value) {
          resetLongLoad();
          void loadLong(false);
        }
      } finally {
        refreshing.value = false;
        void nextTick$1(() => scrollTopIfFresh());
      }
    }
    async function reloadDetail() {
      await refreshDetail();
    }
    async function retryLong() {
      await loadLong(true);
    }
    function pickActor(name) {
      const target = String(name || "");
      if (!target) return;
      emit("openActor", target);
    }
    __expose({ syncCursor, focusFresh, reloadDetail, retryDetail });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$4("v-btn");
      const _component_v_navigation_drawer = _resolveComponent$4("v-navigation-drawer");
      return _openBlock$4(), _createBlock$4(_component_v_navigation_drawer, {
        "model-value": _ctx.open,
        location: "right",
        temporary: "",
        "disable-resize-watcher": "",
        width: 1080,
        class: "avh-detail",
        "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => {
          if (!value) emit("close");
        })
      }, {
        default: _withCtx$4(() => [
          _createElementVNode$4("div", _hoisted_1$4, [
            _createElementVNode$4("b", _hoisted_2$4, _toDisplayString$4(title.value), 1),
            _cache[5] || (_cache[5] = _createElementVNode$4("div", { class: "avh-detail__spacer" }, null, -1)),
            activeNumber.value ? (_openBlock$4(), _createBlock$4(_component_v_btn, {
              key: 0,
              variant: "outlined",
              size: "small",
              onClick: reloadDetail
            }, {
              default: _withCtx$4(() => _cache[3] || (_cache[3] = [
                _createTextVNode$3("↻ 重新抓取")
              ])),
              _: 1
            })) : _createCommentVNode$3("", true),
            _createVNode$4(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
            }, {
              default: _withCtx$4(() => _cache[4] || (_cache[4] = [
                _createTextVNode$3("关闭")
              ])),
              _: 1
            })
          ]),
          _createElementVNode$4("div", {
            ref_key: "bodyEl",
            ref: bodyEl,
            class: "avh-detail__body"
          }, [
            hasDetail.value ? (_openBlock$4(), _createElementBlock$4(_Fragment$4, { key: 0 }, [
              _createElementVNode$4("div", _hoisted_3$3, [
                _createElementVNode$4("div", _hoisted_4$3, [
                  coverSrc.value ? (_openBlock$4(), _createElementBlock$4("img", {
                    key: 0,
                    src: coverSrc.value,
                    alt: num.value,
                    referrerpolicy: "no-referrer",
                    decoding: "async",
                    onError: onCoverError,
                    onClick: openCover
                  }, null, 40, _hoisted_5$3)) : (_openBlock$4(), _createElementBlock$4("div", _hoisted_6$3, "后端未返回封面（/img 代理可能不可用）"))
                ]),
                _createElementVNode$4("div", _hoisted_7$3, [
                  _createElementVNode$4("h2", _hoisted_8$2, _toDisplayString$4(num.value), 1),
                  movie.value.lib ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_9$2, [
                    _cache[7] || (_cache[7] = _createTextVNode$3(" ✅ 已在 Emby 库中 ")),
                    movie.value.lib.url ? (_openBlock$4(), _createElementBlock$4(_Fragment$4, { key: 0 }, [
                      _cache[6] || (_cache[6] = _createTextVNode$3(" · ")),
                      _createElementVNode$4("a", {
                        href: String(movie.value.lib.url),
                        target: "_blank",
                        rel: "noopener"
                      }, "在 Emby 中打开 ↗", 8, _hoisted_10$2)
                    ], 64)) : _createCommentVNode$3("", true)
                  ])) : _createCommentVNode$3("", true),
                  movie.value.downloaded && !movie.value.lib ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_11$2, _cache[8] || (_cache[8] = [
                    _createTextVNode$3(" ✔ 已下载 "),
                    _createElementVNode$4("span", { class: "avh-hint" }, "下载台账里有这个番号（文件可能已不在库）", -1)
                  ]))) : _createCommentVNode$3("", true),
                  movie.value.title ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_12$2, _toDisplayString$4(movie.value.title), 1)) : _createCommentVNode$3("", true),
                  _createElementVNode$4("div", _hoisted_13$2, [
                    actorChips.value.length ? (_openBlock$4(true), _createElementBlock$4(_Fragment$4, { key: 0 }, _renderList$4(actorChips.value, (actor, index) => {
                      return _openBlock$4(), _createElementBlock$4("div", {
                        key: `${actor.name}#${index}`,
                        class: "avh-actorchip",
                        title: actor.name,
                        onClick: ($event) => pickActor(actor.name)
                      }, [
                        _createVNode$4(Thumb, {
                          class: "avh-actorchip__av",
                          variant: "av",
                          src: actor.avatar,
                          alt: actor.name,
                          "plugin-id": _ctx.pluginId
                        }, null, 8, ["src", "alt", "plugin-id"]),
                        _createElementVNode$4("span", _hoisted_15$1, [
                          _createElementVNode$4("span", _hoisted_16$1, _toDisplayString$4(actor.zh || actor.name), 1),
                          actor.zh ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_17$1, _toDisplayString$4(actor.name), 1)) : _createCommentVNode$3("", true),
                          actor.alias ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_18$1, _toDisplayString$4(actor.alias), 1)) : _createCommentVNode$3("", true)
                        ]),
                        _cache[9] || (_cache[9] = _createElementVNode$4("span", { class: "avh-hint" }, "看全部作品 ›", -1))
                      ], 8, _hoisted_14$2);
                    }), 128)) : (_openBlock$4(), _createElementBlock$4("span", _hoisted_19$1, "未识别到演员"))
                  ]),
                  _createElementVNode$4("div", _hoisted_20$1, [
                    _createElementVNode$4("span", null, [
                      _cache[10] || (_cache[10] = _createElementVNode$4("b", null, "发行", -1)),
                      _createTextVNode$3(" " + _toDisplayString$4(movie.value.date || "—"), 1)
                    ]),
                    _createElementVNode$4("span", null, [
                      _cache[11] || (_cache[11] = _createElementVNode$4("b", null, "时长", -1)),
                      _createTextVNode$3(" " + _toDisplayString$4(movie.value.duration || "—") + " 分钟", 1)
                    ]),
                    _createElementVNode$4("span", null, [
                      _cache[12] || (_cache[12] = _createElementVNode$4("b", null, "中文字幕", -1)),
                      movie.value.cnsub ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_21, "有")) : (_openBlock$4(), _createElementBlock$4("span", _hoisted_22, "无"))
                    ]),
                    _createElementVNode$4("span", null, [
                      _cache[13] || (_cache[13] = _createElementVNode$4("b", null, "磁力", -1)),
                      _createTextVNode$3(" " + _toDisplayString$4(movie.value.magnets || magnets.value.length || 0) + " 个", 1)
                    ]),
                    movie.value.maker ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_23, [
                      _cache[14] || (_cache[14] = _createElementVNode$4("b", null, "片商", -1)),
                      _createTextVNode$3(" " + _toDisplayString$4(movie.value.maker), 1)
                    ])) : _createCommentVNode$3("", true),
                    movie.value.score ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_24, [
                      _cache[15] || (_cache[15] = _createElementVNode$4("b", null, "评分", -1)),
                      _createTextVNode$3(" " + _toDisplayString$4(movie.value.score), 1)
                    ])) : _createCommentVNode$3("", true)
                  ]),
                  _createElementVNode$4("div", _hoisted_25, [
                    _createVNode$4(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      size: "small",
                      loading: ptSearching.value,
                      onClick: ptSearch
                    }, {
                      default: _withCtx$4(() => [
                        _createTextVNode$3(_toDisplayString$4(acquired.value ? "✅ 已提交" : "⬇ 下载该影片"), 1)
                      ]),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode$4(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      loading: subscribing.value,
                      onClick: subscribeNumber
                    }, {
                      default: _withCtx$4(() => _cache[16] || (_cache[16] = [
                        _createTextVNode$3(" 📌 订阅这个番号 ")
                      ])),
                      _: 1
                    }, 8, ["loading"]),
                    movie.value.actor ? (_openBlock$4(), _createBlock$4(_component_v_btn, {
                      key: 0,
                      variant: "outlined",
                      size: "small",
                      loading: favBusy.value,
                      onClick: toggleFav
                    }, {
                      default: _withCtx$4(() => [
                        _createTextVNode$3(_toDisplayString$4(faved.value ? "★ 已收藏" : "☆ 收藏该演员"), 1)
                      ]),
                      _: 1
                    }, 8, ["loading"])) : _createCommentVNode$3("", true)
                  ])
                ])
              ]),
              _createElementVNode$4("div", _hoisted_26, "预览图（" + _toDisplayString$4(previews.value.length) + " 张）", 1),
              _createElementVNode$4("div", _hoisted_27, [
                previews.value.length ? (_openBlock$4(true), _createElementBlock$4(_Fragment$4, { key: 0 }, _renderList$4(previews.value, (shot, index) => {
                  return _openBlock$4(), _createElementBlock$4("div", {
                    key: `${index}#${String(shot).slice(-24)}`,
                    class: _normalizeClass$2(["avh-shot", { "avh-shot--blur": !!shot }]),
                    style: _normalizeStyle(shotStyle(shot)),
                    onClick: ($event) => openShot(index)
                  }, [
                    _createVNode$4(Thumb, {
                      variant: "plain",
                      src: shot,
                      alt: "预览图",
                      "plugin-id": _ctx.pluginId
                    }, null, 8, ["src", "plugin-id"]),
                    !shot ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_29, "预览图加载失败")) : _createCommentVNode$3("", true)
                  ], 14, _hoisted_28);
                }), 128)) : (_openBlock$4(), _createElementBlock$4("span", _hoisted_30, "该片没有预览图"))
              ]),
              _createElementVNode$4("div", _hoisted_31, "磁力链接（" + _toDisplayString$4(magnets.value.length) + " 条）", 1),
              magnets.value.length ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_32, [
                (_openBlock$4(true), _createElementBlock$4(_Fragment$4, null, _renderList$4(magnets.value, (magnet, index) => {
                  return _openBlock$4(), _createElementBlock$4("div", {
                    key: `${magnet.hash}#${index}`,
                    class: "avh-mag"
                  }, [
                    _createElementVNode$4("div", _hoisted_33, [
                      _createElementVNode$4("div", _hoisted_34, _toDisplayString$4(magnet.name || magnet.hash || "未命名"), 1),
                      _createElementVNode$4("div", _hoisted_35, [
                        _createElementVNode$4("span", {
                          class: _normalizeClass$2(["avh-tag", { "avh-tag--on": !!magnet.cnsub }])
                        }, _toDisplayString$4(magnet.cnsub ? "中字" : "无中字"), 3),
                        magnet.hd ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_36, "高清")) : _createCommentVNode$3("", true),
                        magnet.size ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_37, _toDisplayString$4(magnet.size), 1)) : _createCommentVNode$3("", true)
                      ]),
                      magnetUri(String(magnet.hash || "")) ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_38, [
                        _createElementVNode$4("a", {
                          href: magnetUri(String(magnet.hash || "")),
                          title: "用系统下载器打开",
                          class: "avh-mag__hash"
                        }, _toDisplayString$4(magnet.hash), 9, _hoisted_39)
                      ])) : _createCommentVNode$3("", true)
                    ]),
                    _createVNode$4(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      disabled: (dlState.value[String(magnet.hash || "")] || "idle") !== "idle",
                      onClick: ($event) => downloadMagnet(magnet)
                    }, {
                      default: _withCtx$4(() => [
                        _createTextVNode$3(_toDisplayString$4(dlLabel(String(magnet.hash || ""))), 1)
                      ]),
                      _: 2
                    }, 1032, ["disabled", "onClick"])
                  ]);
                }), 128))
              ])) : (_openBlock$4(), _createElementBlock$4("div", _hoisted_40, "没有磁力链接")),
              _createElementVNode$4("div", _hoisted_41, [
                longError.value ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_42, [
                  _createTextVNode$3(_toDisplayString$4(longError.value) + " ", 1),
                  longSrc.value ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_43, _toDisplayString$4(longSrcAttr.value || longSrc.value), 1)) : _createCommentVNode$3("", true),
                  _createElementVNode$4("div", _hoisted_44, [
                    _createVNode$4(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      onClick: retryLong
                    }, {
                      default: _withCtx$4(() => _cache[17] || (_cache[17] = [
                        _createTextVNode$3("重试")
                      ])),
                      _: 1
                    })
                  ])
                ])) : longSrc.value ? (_openBlock$4(), _createElementBlock$4("img", {
                  key: longImgKey.value,
                  class: "avh-longimg",
                  src: longSrcAttr.value,
                  width: longNaturalW.value || void 0,
                  height: longNaturalH.value || void 0,
                  alt: "长缩略图",
                  referrerpolicy: "no-referrer",
                  decoding: "async",
                  onLoad: onLongLoad,
                  onError: _cache[1] || (_cache[1] = ($event) => onLongError(currentLongToken())),
                  onClick: openLong
                }, null, 40, _hoisted_45)) : longHint.value ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_46, _toDisplayString$4(longHint.value), 1)) : longFetching.value ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_47, "⏳ 正在获取长缩略图…")) : _createCommentVNode$3("", true)
              ])
            ], 64)) : detailError.value ? (_openBlock$4(), _createBlock$4(ErrorState, {
              key: 1,
              message: detailError.value,
              retrying: retrying.value,
              onRetry: retryDetail
            }, null, 8, ["message", "retrying"])) : (_openBlock$4(), _createElementBlock$4("div", _hoisted_48, [
              _createElementVNode$4("div", _hoisted_49, [
                skeletonMovie.value.cover ? (_openBlock$4(), _createBlock$4(Thumb, {
                  key: 0,
                  variant: "plain",
                  src: skeletonMovie.value.cover,
                  alt: activeNumber.value,
                  "plugin-id": _ctx.pluginId,
                  lazy: false
                }, null, 8, ["src", "alt", "plugin-id"])) : (_openBlock$4(), _createElementBlock$4("div", _hoisted_50, "正在获取封面…"))
              ]),
              _createElementVNode$4("div", _hoisted_51, [
                _createElementVNode$4("h2", _hoisted_52, _toDisplayString$4(activeNumber.value), 1),
                _createElementVNode$4("div", _hoisted_53, [
                  skeletonMovie.value.date ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_54, [
                    _cache[18] || (_cache[18] = _createElementVNode$4("b", null, "发行", -1)),
                    _createTextVNode$3(" " + _toDisplayString$4(skeletonMovie.value.date), 1)
                  ])) : _createCommentVNode$3("", true),
                  skeletonMovie.value.actor ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_55, [
                    _cache[19] || (_cache[19] = _createElementVNode$4("b", null, "演员", -1)),
                    _createTextVNode$3(" " + _toDisplayString$4(skeletonMovie.value.actor), 1)
                  ])) : _createCommentVNode$3("", true)
                ]),
                _cache[20] || (_cache[20] = _createElementVNode$4("div", { class: "avh-hint avh-skeleton__tip" }, "⏳ 正在抓取影片详情（预览图与磁力随后填充）…", -1))
              ])
            ])),
            !activeNumber.value ? (_openBlock$4(), _createBlock$4(EmptyState, {
              key: 3,
              text: "没有指定番号"
            })) : _createCommentVNode$3("", true)
          ], 512),
          _createVNode$4(Lightbox, {
            ref_key: "lightbox",
            ref: lightbox
          }, null, 512)
        ]),
        _: 1
      }, 8, ["model-value"]);
    };
  }
});

const DetailDrawer = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-95588827"]]);

const {defineComponent:_defineComponent$3} = await importShared('vue');

const {createElementVNode:_createElementVNode$3,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$3,withCtx:_withCtx$3,createVNode:_createVNode$3,renderList:_renderList$3,Fragment:_Fragment$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,toDisplayString:_toDisplayString$3,createCommentVNode:_createCommentVNode$2,createBlock:_createBlock$3,normalizeClass:_normalizeClass$1} = await importShared('vue');

const _hoisted_1$3 = { class: "avh-notify__head" };
const _hoisted_2$3 = { class: "avh-notify__bub" };
const _hoisted_3$2 = { class: "avh-notify__h" };
const _hoisted_4$2 = {
  key: 0,
  class: "avh-notify__ttl"
};
const _hoisted_5$2 = { class: "avh-notify__b" };
const _hoisted_6$2 = {
  key: 1,
  class: "avh-notify__meta"
};
const _hoisted_7$2 = { class: "avh-notify__f" };
const {computed: computed$3,nextTick,onBeforeUnmount: onBeforeUnmount$1,onMounted: onMounted$1,ref: ref$3,watch: watch$2} = await importShared('vue');
const _sfc_main$3 = /* @__PURE__ */ _defineComponent$3({
  __name: "NotifyDrawer",
  props: {
    open: { type: Boolean, default: false },
    notices: { default: () => [] },
    pluginId: { default: "" },
    clearing: { type: Boolean, default: false }
  },
  emits: ["close", "clear"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const confirm = useHostConfirm();
    const bodyEl = ref$3(null);
    function kindOf(item) {
      if (item.kind === "ok") return "ok";
      if (item.kind === "warn") return "warn";
      return "";
    }
    function headText(item) {
      return `MoviePilot · ${item.type || "系统消息"}`;
    }
    async function askClear() {
      if (props.clearing) return;
      const ok = await confirm({
        type: "warn",
        title: "清空通知",
        content: `将清空全部 ${props.notices.length} 条通知，且无法恢复。确认继续？`,
        confirmText: "清空",
        cancelText: "取消"
      });
      if (!ok) return;
      emit("clear");
    }
    function onKeydown(event) {
      if (event.key !== "Escape" || !props.open) return;
      emit("close");
    }
    onMounted$1(() => document.addEventListener("keydown", onKeydown, true));
    onBeforeUnmount$1(() => document.removeEventListener("keydown", onKeydown, true));
    watch$2(
      () => props.open,
      (value) => {
        if (!value) return;
        markNoticesSeen(props.notices);
        void nextTick(() => {
          if (bodyEl.value) bodyEl.value.scrollTop = 0;
        });
      },
      { immediate: true }
    );
    watch$2(
      () => props.notices,
      (list) => {
        if (props.open) markNoticesSeen(list);
      }
    );
    const rows = computed$3(
      () => (props.notices || []).map((item, index) => ({
        key: `${item.time || ""}#${index}`,
        item,
        kind: kindOf(item),
        head: headText(item),
        time: shortTime(item.time)
      }))
    );
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$3("v-btn");
      const _component_v_navigation_drawer = _resolveComponent$3("v-navigation-drawer");
      return _openBlock$3(), _createBlock$3(_component_v_navigation_drawer, {
        "model-value": _ctx.open,
        location: "right",
        temporary: "",
        "disable-resize-watcher": "",
        width: 470,
        class: "avh-notify",
        "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => {
          if (!value) emit("close");
        })
      }, {
        default: _withCtx$3(() => [
          _createElementVNode$3("div", _hoisted_1$3, [
            _cache[4] || (_cache[4] = _createElementVNode$3("b", { class: "avh-notify__title" }, "🔔 通知", -1)),
            _cache[5] || (_cache[5] = _createElementVNode$3("div", { class: "avh-notify__spacer" }, null, -1)),
            _createVNode$3(_component_v_btn, {
              variant: "outlined",
              size: "small",
              disabled: !rows.value.length,
              loading: _ctx.clearing,
              onClick: askClear
            }, {
              default: _withCtx$3(() => _cache[2] || (_cache[2] = [
                _createTextVNode$2("清空")
              ])),
              _: 1
            }, 8, ["disabled", "loading"]),
            _createVNode$3(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
            }, {
              default: _withCtx$3(() => _cache[3] || (_cache[3] = [
                _createTextVNode$2("关闭")
              ])),
              _: 1
            })
          ]),
          _createElementVNode$3("div", {
            ref_key: "bodyEl",
            ref: bodyEl,
            class: "avh-notify__body"
          }, [
            rows.value.length ? (_openBlock$3(true), _createElementBlock$3(_Fragment$3, { key: 0 }, _renderList$3(rows.value, (row) => {
              return _openBlock$3(), _createElementBlock$3("div", {
                key: row.key,
                class: _normalizeClass$1(["avh-notify__msg", row.kind ? `avh-notify__msg--${row.kind}` : ""])
              }, [
                _cache[6] || (_cache[6] = _createElementVNode$3("div", { class: "avh-notify__ico" }, "🤖", -1)),
                _createElementVNode$3("div", _hoisted_2$3, [
                  _createElementVNode$3("div", _hoisted_3$2, _toDisplayString$3(row.head), 1),
                  row.item.title ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_4$2, _toDisplayString$3(row.item.title), 1)) : _createCommentVNode$2("", true),
                  _createElementVNode$3("div", _hoisted_5$2, _toDisplayString$3(row.item.body || ""), 1),
                  row.item.meta ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_6$2, _toDisplayString$3(row.item.meta), 1)) : _createCommentVNode$2("", true),
                  row.item.image ? (_openBlock$3(), _createBlock$3(Thumb, {
                    key: 2,
                    class: "avh-notify__img",
                    variant: "plain",
                    src: row.item.image,
                    alt: "主图加载失败",
                    "plugin-id": _ctx.pluginId,
                    lazy: false
                  }, null, 8, ["src", "plugin-id"])) : _createCommentVNode$2("", true),
                  _createElementVNode$3("div", _hoisted_7$2, _toDisplayString$3(row.time), 1)
                ])
              ], 2);
            }), 128)) : (_openBlock$3(), _createBlock$3(EmptyState, {
              key: 1,
              text: "暂无通知"
            }))
          ], 512)
        ]),
        _: 1
      }, 8, ["model-value"]);
    };
  }
});

const NotifyDrawer = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-0a21181e"]]);

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {toDisplayString:_toDisplayString$2,createElementVNode:_createElementVNode$2,resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,withCtx:_withCtx$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$1,createBlock:_createBlock$2,renderList:_renderList$2,Fragment:_Fragment$2,createTextVNode:_createTextVNode$1} = await importShared('vue');

const _hoisted_1$2 = { class: "avh-search__title" };
const _hoisted_2$2 = {
  key: 0,
  class: "avh-search__loading"
};
const _hoisted_3$1 = { class: "avh-actors avh-search__actors" };
const _hoisted_4$1 = {
  key: 1,
  class: "avh-search__secttl avh-hint"
};
const _hoisted_5$1 = ["title", "onClick"];
const _hoisted_6$1 = { class: "avh-searchrow__mini" };
const _hoisted_7$1 = { class: "avh-searchrow__main" };
const _hoisted_8$1 = { class: "avh-searchrow__num" };
const _hoisted_9$1 = { class: "avh-searchrow__sub avh-hint" };
const _hoisted_10$1 = {
  key: 0,
  class: "avh-tag avh-tag--on"
};
const _hoisted_11$1 = {
  key: 1,
  class: "avh-tag avh-tag--uc"
};
const _hoisted_12$1 = {
  key: 2,
  class: "avh-tag avh-tag--lib"
};
const _hoisted_13$1 = { class: "avh-searchrow__ttl avh-hint" };
const _hoisted_14$1 = {
  key: 2,
  class: "avh-hint"
};
const {computed: computed$2,ref: ref$2,watch: watch$1} = await importShared('vue');
const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
  __name: "SearchDialog",
  props: {
    open: { type: Boolean, default: false },
    pluginId: { default: "" },
    api: { default: null }
  },
  emits: ["close", "openMovie", "openActor"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const keyword = ref$2("");
    const loading = ref$2(false);
    const error = ref$2("");
    const movies = ref$2([]);
    const actors = ref$2([]);
    const searched = ref$2(false);
    const title = computed$2(() => {
      const head = `搜索「${keyword.value}」`;
      if (!searched.value) return head;
      const actorPart = actors.value.length ? ` / ${actors.value.length} 位演员` : "";
      return `${head} · ${movies.value.length} 部影片${actorPart}`;
    });
    function titleText(movie) {
      return String(movie.title || "").slice(0, 60);
    }
    function preload(list) {
      list.forEach((movie) => {
        const url = String(movie.thumb || "");
        if (!url) return;
        const image = new Image();
        image.decoding = "async";
        image.src = url;
      });
    }
    async function search(raw) {
      const kw = String(raw || "").trim();
      if (!kw) return;
      keyword.value = kw;
      loading.value = true;
      error.value = "";
      try {
        const api = props.api;
        if (!api || typeof api.get !== "function") {
          error.value = "宿主请求器不可用";
          return;
        }
        const res = await api.get("plugin/search", { params: { keyword: kw } });
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        if (payload && typeof payload === "object" && payload.success === false) {
          error.value = String(payload.message || payload.detail || "搜索失败，请稍后重试");
          return;
        }
        const rawMovies = Array.isArray(payload?.movies) ? payload.movies : [];
        const rawActors = Array.isArray(payload?.actors) ? payload.actors : [];
        movies.value = rawMovies.filter((item) => item && typeof item === "object");
        actors.value = rawActors.filter((item) => item && typeof item === "object" && item.name).map((item) => ({
          name: String(item.name || ""),
          zh: String(item.zh || ""),
          avatar: String(item.avatar || "")
        }));
        searched.value = true;
        preload(movies.value);
      } catch (err) {
        const status = Number(err?.response?.status || err?.status || 0);
        error.value = status ? `请求失败（HTTP ${status}）` : errorText(err);
      } finally {
        loading.value = false;
      }
    }
    function reset() {
      loading.value = false;
      error.value = "";
      movies.value = [];
      actors.value = [];
      searched.value = false;
    }
    watch$1(
      () => props.open,
      (value) => {
        if (!value) reset();
      }
    );
    function retry() {
      void search(keyword.value);
    }
    function pickMovie(movie) {
      emit("openMovie", { number: String(movie.number || ""), id: String(movie.id || "") });
    }
    function pickActor(name) {
      if (name) emit("openActor", name);
    }
    __expose({ search });
    return (_ctx, _cache) => {
      const _component_v_spacer = _resolveComponent$2("v-spacer");
      const _component_v_card_title = _resolveComponent$2("v-card-title");
      const _component_v_card_text = _resolveComponent$2("v-card-text");
      const _component_v_btn = _resolveComponent$2("v-btn");
      const _component_v_card_actions = _resolveComponent$2("v-card-actions");
      const _component_v_card = _resolveComponent$2("v-card");
      const _component_v_dialog = _resolveComponent$2("v-dialog");
      return _openBlock$2(), _createBlock$2(_component_v_dialog, {
        "model-value": _ctx.open,
        "max-width": "920",
        scrollable: "",
        attach: "body",
        "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => {
          if (!value) emit("close");
        })
      }, {
        default: _withCtx$2(() => [
          _createVNode$2(_component_v_card, null, {
            default: _withCtx$2(() => [
              _createVNode$2(_component_v_card_title, { class: "d-flex align-center" }, {
                default: _withCtx$2(() => [
                  _createElementVNode$2("span", _hoisted_1$2, _toDisplayString$2(title.value), 1),
                  _createVNode$2(_component_v_spacer)
                ]),
                _: 1
              }),
              _createVNode$2(_component_v_card_text, null, {
                default: _withCtx$2(() => [
                  loading.value ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_2$2, "正在搜索…")) : error.value ? (_openBlock$2(), _createBlock$2(ErrorState, {
                    key: 1,
                    message: error.value,
                    retrying: loading.value,
                    onRetry: retry
                  }, null, 8, ["message", "retrying"])) : (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 2 }, [
                    actors.value.length ? (_openBlock$2(), _createElementBlock$2(_Fragment$2, { key: 0 }, [
                      _cache[2] || (_cache[2] = _createElementVNode$2("div", { class: "avh-search__secttl avh-hint" }, "演员", -1)),
                      _createElementVNode$2("div", _hoisted_3$1, [
                        (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(actors.value, (actor) => {
                          return _openBlock$2(), _createBlock$2(ActorRow, {
                            key: actor.name,
                            name: String(actor.name || ""),
                            zh: actor.zh || "",
                            avatar: actor.avatar || "",
                            "plugin-id": _ctx.pluginId,
                            onSelect: pickActor
                          }, null, 8, ["name", "zh", "avatar", "plugin-id"]);
                        }), 128))
                      ])
                    ], 64)) : _createCommentVNode$1("", true),
                    searched.value ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_4$1, "影片")) : _createCommentVNode$1("", true),
                    (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(movies.value, (movie, index) => {
                      return _openBlock$2(), _createElementBlock$2("div", {
                        key: `${movie.number}#${index}`,
                        class: "avh-searchrow",
                        title: movie.title || movie.number || "",
                        onClick: ($event) => pickMovie(movie)
                      }, [
                        _createElementVNode$2("div", _hoisted_6$1, [
                          _createVNode$2(Thumb, {
                            variant: "mini",
                            src: movie.thumb,
                            alt: String(movie.number || ""),
                            "plugin-id": _ctx.pluginId
                          }, null, 8, ["src", "alt", "plugin-id"])
                        ]),
                        _createElementVNode$2("div", _hoisted_7$1, [
                          _createElementVNode$2("div", _hoisted_8$1, _toDisplayString$2(movie.number), 1),
                          _createElementVNode$2("div", _hoisted_9$1, [
                            _createElementVNode$2("span", null, _toDisplayString$2(movie.actor || "—") + " · " + _toDisplayString$2(movie.date || "") + " · 🧲 " + _toDisplayString$2(movie.magnets || 0), 1),
                            movie.cnsub ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_10$1, "中字")) : _createCommentVNode$1("", true),
                            movie.uncensored ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_11$1, "破解")) : _createCommentVNode$1("", true),
                            movie.lib ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_12$1, "已入库")) : _createCommentVNode$1("", true)
                          ]),
                          _createElementVNode$2("div", _hoisted_13$1, _toDisplayString$2(titleText(movie)), 1)
                        ]),
                        _cache[3] || (_cache[3] = _createElementVNode$2("span", { class: "avh-hint" }, "查看 ›", -1))
                      ], 8, _hoisted_5$1);
                    }), 128)),
                    searched.value && !movies.value.length ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_14$1, "没有匹配的影片")) : _createCommentVNode$1("", true),
                    !searched.value ? (_openBlock$2(), _createBlock$2(EmptyState, {
                      key: 3,
                      text: "输入番号或演员名后点「搜索」"
                    })) : _createCommentVNode$1("", true)
                  ], 64))
                ]),
                _: 1
              }),
              _createVNode$2(_component_v_card_actions, null, {
                default: _withCtx$2(() => [
                  _createVNode$2(_component_v_spacer),
                  _createVNode$2(_component_v_btn, {
                    color: "error",
                    variant: "outlined",
                    onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
                  }, {
                    default: _withCtx$2(() => _cache[4] || (_cache[4] = [
                      _createTextVNode$1("关闭")
                    ])),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["model-value"]);
    };
  }
});

const SearchDialog = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-955b3a36"]]);

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {unref:_unref$1,renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$1,withCtx:_withCtx$1,createBlock:_createBlock$1} = await importShared('vue');

const _hoisted_1$1 = {
  class: "avh-bottomtoast",
  "data-avh": "bottom-toast",
  "aria-live": "polite"
};
const _hoisted_2$1 = { class: "avh-bottomtoast__text" };
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "BottomToast",
  setup(__props) {
    const COLORS = {
      success: "success",
      info: "info",
      warning: "warning",
      error: "error"
    };
    const ICONS = {
      success: "mdi-check-circle",
      info: "mdi-information",
      warning: "mdi-alert-circle",
      error: "mdi-close-circle"
    };
    function colorOf(item) {
      return COLORS[item.level] || "info";
    }
    function iconOf(item) {
      return ICONS[item.level] || "mdi-information";
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_card = _resolveComponent$1("v-card");
      return _openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
        (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(_unref$1(bottomToasts), (item) => {
          return _openBlock$1(), _createBlock$1(_component_v_card, {
            key: item.id,
            class: "avh-bottomtoast__item",
            color: colorOf(item),
            variant: "flat",
            elevation: "8"
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_v_icon, {
                icon: iconOf(item),
                size: "small"
              }, null, 8, ["icon"]),
              _createElementVNode$1("span", _hoisted_2$1, _toDisplayString$1(item.text), 1),
              _createVNode$1(_component_v_btn, {
                icon: "mdi-close",
                size: "x-small",
                variant: "text",
                title: "收起这条提示",
                onClick: ($event) => _unref$1(dismissBottomToast)(item.id)
              }, null, 8, ["onClick"])
            ]),
            _: 2
          }, 1032, ["color"]);
        }), 128))
      ]);
    };
  }
});

const BottomToast = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-38f05692"]]);

const {computed: computed$1,ref: ref$1,shallowRef} = await importShared('vue');
const NOOP_API = {
  get: () => Promise.reject(new Error("宿主 api 不可用")),
  post: () => Promise.reject(new Error("宿主 api 不可用"))
};
function textOf(value) {
  if (!value || typeof value !== "object") return "";
  const record = value;
  for (const key of ["message", "detail", "msg"]) {
    const text = record[key];
    if (typeof text === "string" && text.trim()) return text.trim();
  }
  return "";
}
function listOf(value) {
  return Array.isArray(value) ? value : null;
}
function mapOf(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const out = {};
  Object.keys(value).forEach((key) => {
    out[key] = String(value[key] ?? "");
  });
  return out;
}
function usePluginStore(api) {
  const client = api && typeof api.get === "function" ? api : NOOP_API;
  const enabled = ref$1(true);
  const sites = ref$1([]);
  const favs = ref$1([]);
  const aliases = ref$1({});
  const subs = ref$1([]);
  const known = shallowRef(/* @__PURE__ */ new Set());
  const notices = ref$1([]);
  const tasks = ref$1([]);
  const queue = ref$1([]);
  const rule = ref$1(toRule(null));
  const ruleRaw = ref$1(toRule(null));
  const loading = ref$1(false);
  const error = ref$1("");
  const updatedAt = ref$1("");
  const booted = ref$1(false);
  const busy = ref$1({});
  const awaitTasks = computed$1(() => tasks.value.filter((item) => item.state === "await").length);
  const downloading = computed$1(
    () => queue.value.filter((item) => item.state !== "done" && item.state !== "failed" && item.state !== "canceled").length
  );
  async function guarded(key, run) {
    if (busy.value[key]) {
      return { ok: false, kind: "busy", message: "上一次操作还在进行中，请稍候" };
    }
    busy.value = { ...busy.value, [key]: true };
    try {
      return await run();
    } finally {
      const next = { ...busy.value };
      delete next[key];
      busy.value = next;
    }
  }
  async function send(method, path, body, query) {
    try {
      let raw;
      if (method === "get") {
        raw = await client.get(`plugin/${path}`);
      } else if (method === "post") {
        raw = await client.post(`plugin/${path}`, body === void 0 ? {} : body);
      } else {
        if (typeof client.delete !== "function") {
          return { ok: false, message: "宿主请求器不支持 DELETE，无法执行该操作" };
        }
        const config = query && Object.keys(query).length ? { params: query } : void 0;
        raw = await client.delete(`plugin/${path}`, config);
      }
      if (raw && typeof raw === "object" && !Array.isArray(raw)) {
        const record = raw;
        if (record.success === false) {
          return { ok: false, message: textOf(record) || "接口返回失败" };
        }
        return { ok: true, res: record };
      }
      return { ok: true, res: { data: raw } };
    } catch (err) {
      return { ok: false, message: textOf(err?.payload) || errorText(err) };
    }
  }
  function syncLists(res) {
    const nextSubs = listOf(res.subs);
    if (nextSubs) subs.value = nextSubs;
    const nextTasks = listOf(res.tasks);
    if (nextTasks) tasks.value = nextTasks;
    const nextQueue = listOf(res.queue);
    if (nextQueue) queue.value = nextQueue;
  }
  function prependNotices(incoming) {
    const items = listOf(incoming);
    if (!items?.length) return;
    notices.value = [...items, ...notices.value];
  }
  async function ensureSites() {
    if (sites.value.length) return true;
    const outcome = await send("get", "sites");
    if (!outcome.ok) return false;
    const payload = outcome.res.data ?? outcome.res;
    const list = listOf(payload.sites) || listOf(payload) || [];
    if (list.length) sites.value = list;
    return sites.value.length > 0;
  }
  async function hydrate(payload) {
    const envelope = payload && typeof payload === "object" && "data" in payload ? payload : null;
    if (envelope && envelope.success === false) {
      error.value = textOf(envelope) || "bootstrap 失败";
      return false;
    }
    const data = (envelope ? envelope.data : payload) || {};
    if (typeof data.enabled === "boolean") enabled.value = data.enabled;
    const nextSites = listOf(data.sites);
    if (nextSites?.length) sites.value = nextSites;
    const nextFavs = listOf(data.favs);
    if (nextFavs) favs.value = nextFavs;
    const nextSubs = listOf(data.subs);
    if (nextSubs) subs.value = nextSubs;
    const nextTasks = listOf(data.tasks);
    if (nextTasks) tasks.value = nextTasks;
    const nextQueue = listOf(data.queue);
    if (nextQueue) queue.value = nextQueue;
    const nextNotices = listOf(data.notices);
    if (nextNotices) notices.value = nextNotices;
    const nextKnown = listOf(data.known);
    if (nextKnown) known.value = new Set(nextKnown.map((item) => String(item)));
    const nextAliases = mapOf(data.aliases);
    if (nextAliases) aliases.value = nextAliases;
    if (data.defaultRule && typeof data.defaultRule === "object") {
      ruleRaw.value = data.defaultRule;
      rule.value = toRule(data.defaultRule);
    }
    await ensureSites();
    error.value = "";
    booted.value = true;
    const now = /* @__PURE__ */ new Date();
    updatedAt.value = [now.getHours(), now.getMinutes(), now.getSeconds()].map((part) => String(part).padStart(2, "0")).join(":");
    return true;
  }
  async function refresh() {
    if (loading.value) return false;
    loading.value = true;
    try {
      const outcome = await send("get", "bootstrap");
      if (!outcome.ok) {
        error.value = outcome.message || "bootstrap 失败";
        return false;
      }
      return await hydrate(outcome.res);
    } finally {
      loading.value = false;
    }
  }
  function runCheck(name = "") {
    return guarded("check", async () => {
      const outcome = await send("post", "check", name ? { name } : {});
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      const payload = outcome.res.data ?? outcome.res;
      syncLists(outcome.res);
      prependNotices(payload.notices);
      const limited = payload.limited === true;
      return {
        ok: true,
        kind: limited ? "limited" : "ok",
        limited,
        message: payload.message || (limited ? "距上次检查不足间隔，已跳过" : "检查完成"),
        data: payload
      };
    });
  }
  function unsubscribe(kindOrId) {
    return guarded("unsubscribe", async () => {
      const raw = String(kindOrId ?? "").trim();
      if (!raw) return { ok: false, kind: "error", message: "这条订阅缺少 id，无法删除" };
      let id = raw;
      if (!/^\d+$/.test(raw)) {
        const hit = subs.value.find((item) => String(item.name ?? "") === raw);
        if (!hit || hit.id === void 0 || hit.id === null || !/^\d+$/.test(String(hit.id))) {
          return { ok: false, kind: "error", message: `找不到订阅「${raw}」的 id，无法删除` };
        }
        id = String(hit.id);
      }
      const outcome = await send("delete", "subs", void 0, { id });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      subs.value = subs.value.filter((item) => String(item.id ?? "") !== id);
      return { ok: true, kind: "ok", message: textOf(outcome.res) || "已取消订阅" };
    });
  }
  function addFav(name, zh = "", avatar = "") {
    return guarded("fav", async () => {
      const target = String(name ?? "").trim();
      if (!target) return { ok: false, kind: "error", message: "缺少演员名" };
      const hit = favs.value.find((item) => item.name === target);
      if (hit) return { ok: true, kind: "ok", message: "已收藏", data: hit };
      const outcome = await send("post", "favs", { name: target, zh: zh || "", avatar: avatar || "" });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const entry = { name: target, zh: zh || "", avatar: avatar || "" };
      if (!favs.value.some((item) => item.name === target)) favs.value = [...favs.value, entry];
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || `已收藏 ${target}`,
        data: entry
      };
    });
  }
  function delFav(name) {
    return guarded("fav", async () => {
      const target = String(name ?? "").trim();
      if (!target) return { ok: false, kind: "error", message: "缺少演员名" };
      const outcome = await send("delete", "favs", void 0, { name: target });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      favs.value = favs.value.filter((item) => item.name !== target);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || `已取消收藏 ${target}`
      };
    });
  }
  function setAlias(name, alias) {
    return guarded("alias", async () => {
      const target = String(name ?? "").trim();
      if (!target) return { ok: false, kind: "error", message: "缺少演员名" };
      const text = String(alias ?? "").trim();
      const outcome = await send("post", "aliases", { name: target, alias: text });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const next = { ...aliases.value };
      if (text) next[target] = text;
      else delete next[target];
      aliases.value = next;
      const synced = mapOf(outcome.res.aliases);
      if (synced) aliases.value = synced;
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || (text ? `已保存备注 ${text}` : `已清除备注 ${target}`),
        data: aliases.value
      };
    });
  }
  function subscribeNumber(name, kind = "number", actor = "", rule2) {
    const target = String(name ?? "").trim();
    return guarded(`subscribe:${kind}:${target}`, async () => {
      if (!target) return { ok: false, kind: "error", message: "订阅参数不完整" };
      const body = { type: kind, name: target };
      if (kind === "number" && actor) body.actor = actor;
      if (rule2 && typeof rule2 === "object") body.rule = rule2;
      const outcome = await send("post", "subs", body);
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const nextSubs = listOf(outcome.res.subs);
      if (nextSubs) subs.value = nextSubs;
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || `已订阅 ${target}`
      };
    });
  }
  function searchKeyword(keyword, sites2, extra = {}) {
    return guarded("search", async () => {
      const target = String(keyword ?? "").trim();
      if (!target) return { ok: false, kind: "error", message: "先输入番号或关键词" };
      const body = { keyword: target };
      if (sites2 && sites2.length) body.sites = sites2.slice();
      if (extra.actor) body.actor = extra.actor;
      if (extra.thumb) body.thumb = extra.thumb;
      const outcome = await send("post", "tasks/search", body);
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      const task = outcome.res.task ?? outcome.res;
      const cands = listOf(task.cands) || [];
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || `搜到 ${cands.length} 个候选`,
        data: task
      };
    });
  }
  function acquireMovie(number, extra = {}) {
    return guarded("acquire", async () => {
      const target = String(number ?? "").trim();
      if (!target) return { ok: false, kind: "error", message: "缺少番号" };
      const body = { number: target };
      if (extra.actor) body.actor = extra.actor;
      if (extra.thumb) body.thumb = extra.thumb;
      const outcome = await send("post", "tasks/acquire", body);
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const payload = outcome.res.data ?? outcome.res;
      const nextQueue = listOf(outcome.res.queue);
      if (nextQueue) queue.value = nextQueue;
      const task = payload.task;
      if (task && typeof task === "object" && task.id) {
        tasks.value = [
          task,
          ...tasks.value.filter((item) => String(item.id ?? "") !== String(task.id))
        ];
      }
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "",
        data: payload
      };
    });
  }
  function startDownload(taskId, site, force = false) {
    const id = String(taskId ?? "").trim();
    return guarded(`download:${id}|${String(site ?? "")}`, async () => {
      if (!id) return { ok: false, kind: "error", message: "缺少任务 id" };
      const body = { id, site: site || "" };
      if (force) body.force = true;
      const outcome = await send("post", "tasks/download", body);
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const payload = outcome.res.data ?? outcome.res;
      const nextQueue = listOf(outcome.res.queue);
      if (nextQueue) queue.value = nextQueue;
      const notice = outcome.res.notice ?? (outcome.res.id ? outcome.res : null);
      if (notice && (notice.body || notice.title)) prependNotices([notice]);
      tasks.value = tasks.value.map(
        (item) => String(item.id ?? "") === id ? { ...item, state: "pushed" } : item
      );
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已提交下载",
        data: payload
      };
    });
  }
  function downloadMagnet(hash, name = "", number = "") {
    const digest = String(hash ?? "").trim();
    return guarded(`magnet:${digest}`, async () => {
      if (!digest) return { ok: false, kind: "error", message: "缺少磁力 Hash" };
      const body = { hash: digest, name: name || "" };
      if (number) body.number = number;
      const outcome = await send("post", "magnet-download", body);
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请检查下载器配置" };
      }
      const nextQueue = listOf(outcome.res.queue);
      if (nextQueue) queue.value = nextQueue;
      if (number) known.value = /* @__PURE__ */ new Set([...known.value, String(number)]);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已提交下载",
        data: outcome.res.data ?? outcome.res
      };
    });
  }
  function cancelTask(taskId) {
    const id = String(taskId ?? "").trim();
    return guarded(`cancel:${id}`, async () => {
      if (!id) return { ok: false, kind: "error", message: "这条任务缺少 id，无法取消" };
      const outcome = await send("post", "tasks/cancel", { id });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const nextTasks = listOf(outcome.res.tasks);
      if (nextTasks) tasks.value = nextTasks;
      const nextQueue = listOf(outcome.res.queue);
      if (nextQueue) queue.value = nextQueue;
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已取消任务",
        data: outcome.res
      };
    });
  }
  function cancelDownload(rowId) {
    const id = String(rowId ?? "").trim();
    return guarded(`qcancel:${id}`, async () => {
      if (!id) return { ok: false, kind: "error", message: "这条下载缺少 id，无法取消" };
      const outcome = await send("post", "queue/cancel", { id });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      syncLists(outcome.res);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已取消下载",
        data: outcome.res
      };
    });
  }
  function returnDownload(rowId) {
    const id = String(rowId ?? "").trim();
    return guarded(`qreturn:${id}`, async () => {
      if (!id) return { ok: false, kind: "error", message: "这条下载缺少 id" };
      const outcome = await send("post", "queue/return", { id });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      syncLists(outcome.res);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已放回任务列表",
        data: outcome.res
      };
    });
  }
  function discardDownload(rowId, unsubscribe2 = true) {
    const id = String(rowId ?? "").trim();
    return guarded(`qdiscard:${id}`, async () => {
      if (!id) return { ok: false, kind: "error", message: "这条下载缺少 id" };
      const outcome = await send("post", "queue/discard", { id, unsubscribe: !!unsubscribe2 });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      syncLists(outcome.res);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已彻底取消",
        data: outcome.res
      };
    });
  }
  function dropDownloadRow(rowId) {
    const id = String(rowId ?? "").trim();
    return guarded(`qdrop:${id}`, async () => {
      if (!id) return { ok: false, kind: "error", message: "这条下载缺少 id" };
      const outcome = await send("delete", "queue", void 0, { id });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      syncLists(outcome.res);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "已移出下载列表",
        data: outcome.res
      };
    });
  }
  function clearNotices() {
    return guarded("clearNotices", async () => {
      const outcome = await send("delete", "notices");
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const nextNotices = listOf(outcome.res.notices);
      notices.value = nextNotices ?? [];
      return { ok: true, kind: "ok", message: textOf(outcome.res) || "通知已清空" };
    });
  }
  function saveRule(next) {
    return guarded("saveRule", async () => {
      if (!next || typeof next !== "object") {
        return { ok: false, kind: "error", message: "规则内容为空" };
      }
      const outcome = await send("post", "rule", { rule: next });
      if (!outcome.ok) return { ok: false, kind: "error", message: outcome.message };
      if (outcome.res.success !== true) {
        return { ok: false, kind: "error", message: textOf(outcome.res) || "请稍后重试" };
      }
      const saved = outcome.res.rule ?? next;
      ruleRaw.value = saved;
      rule.value = toRule(saved);
      return {
        ok: true,
        kind: "ok",
        message: textOf(outcome.res) || "默认规则已保存",
        data: rule.value
      };
    });
  }
  async function refreshTasks(silent = true) {
    const outcome = await send("get", "tasks");
    if (!outcome.ok) {
      if (!silent) error.value = outcome.message;
      return false;
    }
    syncLists(outcome.res);
    return true;
  }
  return {
    // 状态
    enabled,
    sites,
    favs,
    aliases,
    subs,
    known,
    notices,
    tasks,
    queue,
    rule,
    ruleRaw,
    loading,
    error,
    updatedAt,
    booted,
    busy,
    // 派生
    awaitTasks,
    downloading,
    // 动作
    refresh,
    /** 用壳已经拉到的 `/bootstrap` 载荷灌状态（不发请求，S6 站点搜索视图靠它拿 `rule.sites`）。 */
    hydrate,
    refreshTasks,
    ensureSites,
    runCheck,
    unsubscribe,
    addFav,
    delFav,
    setAlias,
    subscribeNumber,
    searchKeyword,
    acquireMovie,
    startDownload,
    cancelTask,
    cancelDownload,
    returnDownload,
    discardDownload,
    dropDownloadRow,
    downloadMagnet,
    clearNotices,
    saveRule
  };
}

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,unref:_unref,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass,resolveDynamicComponent:_resolveDynamicComponent} = await importShared('vue');

const _hoisted_1 = { class: "avh-console" };
const _hoisted_2 = { class: "avh-topbar__left" };
const _hoisted_3 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_4 = { class: "avh-searchbox" };
const _hoisted_5 = { class: "avh-topbar__right" };
const _hoisted_6 = {
  key: 0,
  class: "avh-bellbadge"
};
const _hoisted_7 = { class: "avh-body" };
const _hoisted_8 = { class: "avh-nav" };
const _hoisted_9 = { class: "avh-nav__scroll" };
const _hoisted_10 = { class: "text-body-2 font-weight-medium" };
const _hoisted_11 = { class: "text-body-2 font-weight-medium" };
const _hoisted_12 = { class: "text-body-2 font-weight-medium" };
const _hoisted_13 = { class: "text-body-2 font-weight-medium" };
const _hoisted_14 = { class: "text-body-2 font-weight-medium" };
const _hoisted_15 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_16 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_17 = { class: "avh-content" };
const _hoisted_18 = { class: "avh-settings__body" };
const _hoisted_19 = { class: "avh-settings__nav" };
const _hoisted_20 = { class: "avh-settings__content" };
const {computed,inject,onBeforeUnmount,onMounted,ref,watch} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Console",
  props: {
    initialConfig: { default: () => ({}) },
    api: { default: () => ({
      get: () => Promise.reject(new Error("宿主 api 不可用")),
      post: () => Promise.reject(new Error("宿主 api 不可用"))
    }) },
    pluginId: { default: "" },
    sourcePluginId: { default: "" },
    nativeSubscribe: { type: [Function, null], default: null },
    show_switch: { type: Boolean, default: true },
    mode: { default: "data" }
  },
  emits: CONSOLE_EMIT_NAMES,
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const DATA_SECTIONS = [
      { key: "discover", title: "发现榜单", icon: "mdi-chart-line" },
      { key: "actors", title: "我的演员", icon: "mdi-account-star" },
      // 「演员库」（0.9.0 演员线 S5 加）：后端 actor 表的全部演员（卡片墙 + 缺头像筛选 + 详情）。
      // 与「我的演员」分工：那一栏是**我收藏的**演员作品史，这一栏是**刮削得到的**演员与头像维护。
      // 图标刻意与「我的演员」区分开（同一个 mdi-account-star 会让左栏出现两个一模一样的图标）。
      { key: "actorLibrary", title: "演员库", icon: "mdi-account-box-multiple" },
      { key: "subs", title: "订阅", icon: "mdi-rss" },
      { key: "tasks", title: "任务", icon: "mdi-clipboard-list" },
      // 「下载」内部有两个页签（下载中 / 下载历史，2026-10-12 融合）：完成的番号落到台账后
      // 由同栏的「下载历史」页签兜底（删了文件也还在），所以左栏不再单列「下载历史」。
      { key: "downloads", title: "下载", icon: "mdi-download" },
      // 「已入库的番号」（2026-10-12 加）：Emby 库里**此刻**的片子，实时口径，删了就不在其中。
      // 与「下载历史」分工明确：这一栏答"库里有什么"，那一栏答"插件下过什么"。
      { key: "library", title: "已入库的番号", icon: "mdi-library-shelves" },
      // 「刮削」（v4 刮削线 0.7.0 加）：全库刮削工作台 + 数据源自检两个页签（`ScrapeView.vue`）。
      // 排在最后：它是"收拾已入库的片子"，读的顺序本来就在下载/入库之后。
      { key: "scrape", title: "刮削", icon: "mdi-auto-fix" },
      { key: "sitesearch", title: "站点搜索", icon: "mdi-magnify" }
    ];
    const pluginId = computed(() => props.pluginId || props.sourcePluginId || "");
    const NATIVE_VIEWS = {
      discover: DiscoverView,
      sitesearch: SiteSearchView,
      downloads: DownloadsView,
      library: LibraryView,
      tasks: TasksView,
      subs: SubsView,
      actors: ActorsView,
      // 第九栏（0.9.0 演员线 S5）：演员库（卡片墙 + 详情：轮播 / 重刮 / 锁 / 3:4 裁剪）。
      actorLibrary: ActorLibraryView,
      // 第八栏（v4 刮削线 0.7.0）：全库刮削工作台 + 数据源自检。
      scrape: ScrapeView
    };
    const framePluginId = computed(() => props.pluginId || props.sourcePluginId || "");
    const section = ref(DATA_SECTIONS[0].key);
    const settingsSection = ref(SETTINGS_SECTIONS[0].key);
    const settingsOpen = ref(props.mode === "settings");
    const version = ref("");
    const noticeClearing = ref(false);
    const drawerOpen = ref(false);
    const drawerNumber = ref("");
    const drawerId = ref("");
    const searchOpen = ref(false);
    const searchDialog = ref(null);
    const query = ref("");
    const actorFocus = ref("");
    const actorNonce = ref(0);
    const notifyOpen = ref(false);
    function notifyUnread() {
      return Math.max(countUnread(store.notices.value), countUnread(notices.value));
    }
    function openNotify() {
      drawerOpen.value = false;
      searchOpen.value = false;
      notifyOpen.value = true;
    }
    async function clearNoticesFromDrawer() {
      noticeClearing.value = true;
      try {
        const result = await store.clearNotices();
        if (!result.ok) {
          toast.warning(result.message || "清空通知失败");
          return;
        }
        notices.value = [];
        toast.success(result.message || "通知已清空");
        await refreshRuntime();
      } finally {
        noticeClearing.value = false;
      }
    }
    const settingsEntry = computed(() => props.mode === "settings");
    const activeSetting = computed(
      () => SETTINGS_SECTIONS.find((item) => item.key === settingsSection.value) || SETTINGS_SECTIONS[0]
    );
    const nativeView = computed(() => NATIVE_VIEWS[section.value] || null);
    const injectedToast = inject("moviepilot:toast", null);
    const toast = hostToast(injectedToast);
    const confirm = useHostConfirm();
    const FALLBACK_API = {
      get: () => Promise.reject(new Error("宿主 api 不可用")),
      post: () => Promise.reject(new Error("宿主 api 不可用"))
    };
    function rawApi() {
      return props.api && typeof props.api.get === "function" ? props.api : FALLBACK_API;
    }
    const boundApi = computed(() => bindPluginApi(rawApi(), pluginId.value));
    function currentApi() {
      return boundApi.value;
    }
    const runtime = useRuntimeInfo(currentApi());
    const { data: bootstrap, overview, updatedAt, error: runtimeError, loading: runtimeLoading, refresh: refreshRuntime } = runtime;
    const store = usePluginStore(currentApi());
    watch(
      bootstrap,
      (payload) => {
        if (payload) store.hydrate(payload);
      },
      { immediate: true }
    );
    const navBadges = computed(() => ({
      actors: { count: store.favs.value.length, warn: false },
      subs: { count: store.subs.value.length, warn: false },
      tasks: { count: store.awaitTasks.value, warn: true },
      downloads: { count: store.downloading.value, warn: false }
    }));
    const dataSections = computed(
      () => DATA_SECTIONS.map((item) => ({ ...item, badge: navBadges.value[item.key] ?? null }))
    );
    const draft = useSettingsDraft({
      api: currentApi(),
      initialConfig: props.initialConfig,
      toast: injectedToast,
      // 第 2 步（宿主配置）由 `saveHostConfig` 按入口选路：宿主接 save 就交给宿主，不接就自己 PUT。
      onSaveHost: saveHostConfig
    });
    const {
      rule: ruleDraft,
      hostConfig,
      sites,
      sitesLoaded,
      notices,
      cacheText,
      cacheBytes,
      checkInfo,
      dirty,
      enabledKnown,
      hostLoaded,
      saveButtonLabel,
      validation,
      loading: draftLoading,
      saving: draftSaving,
      noticeLoading,
      cacheCleaning,
      error: draftError,
      sectionDirty,
      load: loadDraft,
      applyBootstrap,
      hydrateHost,
      save: saveDraft,
      loadNotices,
      cleanCache: cleanCacheDraft
    } = draft;
    watch(bootstrap, (value) => applyBootstrap(value), { immediate: true });
    const activeNavKey = computed(() => `data:${section.value}`);
    const ruleView = computed(() => ruleDraft.value);
    function patchRule(patch) {
      const current = ruleDraft.value;
      if (!current) return;
      ruleDraft.value = { ...current, ...patch };
    }
    const scrapeSettings = ref({ ...SCRAPE_DEFAULTS });
    const scrapePatches = ref({});
    const scrapeDirty = computed(() => Object.keys(scrapePatches.value).length > 0);
    const scrapeView = computed(() => ({ ...scrapeSettings.value, ...scrapePatches.value }));
    let scrapeLoaded = false;
    function ensureScrapeLoaded() {
      if (scrapeLoaded) return;
      scrapeLoaded = true;
      void loadScrapeSettings();
    }
    async function loadScrapeSettings() {
      try {
        const res = await currentApi().get("plugin/rule");
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        const raw = payload && typeof payload === "object" && "rule" in payload ? payload.rule : payload;
        scrapeSettings.value = toScrapeSettings(raw);
      } catch {
        scrapeSettings.value = { ...SCRAPE_DEFAULTS };
      }
    }
    function patchScrape(patch) {
      scrapePatches.value = { ...scrapePatches.value, ...patch };
    }
    async function saveScrapeSettings() {
      if (!scrapeDirty.value) return true;
      try {
        const res = await currentApi().post("plugin/rule", { rule: { ...scrapePatches.value } });
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        if (payload && typeof payload === "object" && payload.success === false) {
          toast.error(String(payload.message || "刮削设置保存失败"));
          return false;
        }
        scrapeSettings.value = { ...scrapeSettings.value, ...scrapePatches.value };
        scrapePatches.value = {};
        return true;
      } catch (err) {
        toast.error(`刮削设置保存失败：${errorText(err)}`);
        return false;
      }
    }
    const actorSettings = ref({ ...ACTOR_DEFAULTS });
    const actorPatches = ref({});
    const actorDirty = computed(() => Object.keys(actorPatches.value).length > 0);
    const actorView = computed({ ...actorSettings.value, ...actorPatches.value });
    let actorLoaded = false;
    function ensureActorLoaded() {
      if (actorLoaded) return;
      actorLoaded = true;
      void loadActorSettings();
    }
    async function loadActorSettings() {
      try {
        const res = await currentApi().get("plugin/rule");
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        const raw = payload && typeof payload === "object" && "rule" in payload ? payload.rule : payload;
        actorSettings.value = toActorSettings(raw);
      } catch {
        actorSettings.value = { ...ACTOR_DEFAULTS };
      }
    }
    function patchActor(patch) {
      actorPatches.value = { ...actorPatches.value, ...patch };
    }
    async function saveActorSettings() {
      if (!actorDirty.value) return true;
      try {
        const res = await currentApi().post("plugin/rule", { rule: { ...actorPatches.value } });
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        if (payload && typeof payload === "object" && payload.success === false) {
          toast.error(String(payload.message || "演员设置保存失败"));
          return false;
        }
        actorSettings.value = { ...actorSettings.value, ...actorPatches.value };
        actorPatches.value = {};
        return true;
      } catch (err) {
        toast.error(`演员设置保存失败：${errorText(err)}`);
        return false;
      }
    }
    function sectionDirtyEx(key) {
      return sectionDirty(key) || scrapeDirty.value && SCRAPE_SECTIONS.includes(key) || actorDirty.value && ACTOR_SECTIONS.includes(key);
    }
    function pick(item) {
      section.value = item.key;
    }
    function pickSetting(item) {
      settingsSection.value = item.key;
      if (SCRAPE_SECTIONS.includes(item.key)) ensureScrapeLoaded();
      if (ACTOR_SECTIONS.includes(item.key)) ensureActorLoaded();
    }
    function onOpenMovie(payload) {
      const number = String(payload?.number || "");
      if (!number) return;
      drawerNumber.value = number;
      drawerId.value = String(payload?.id || "");
      drawerOpen.value = true;
    }
    function openActorFromOverlay(name) {
      const target = String(name || "");
      if (!target) return;
      drawerOpen.value = false;
      searchOpen.value = false;
      actorFocus.value = target;
      actorNonce.value += 1;
      section.value = "actors";
    }
    function runSearch() {
      const kw = String(query.value || "").trim();
      if (!kw) return;
      searchOpen.value = true;
      searchDialog.value?.search(kw);
    }
    function onSearchPickMovie(payload) {
      searchOpen.value = false;
      onOpenMovie(payload);
    }
    async function loadVersion() {
      if (!framePluginId.value) return;
      try {
        const res = await rawApi().get(`plugin/page/${framePluginId.value}`);
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        const value = payload?.plugin_version;
        if (typeof value === "string" && value) {
          version.value = value;
          return;
        }
      } catch {
      }
      try {
        const remotes = await rawApi().get("plugin/remotes?token=moviepilot");
        const list = Array.isArray(remotes) ? remotes : remotes?.data ?? [];
        const mine = (Array.isArray(list) ? list : []).find(
          (item) => String(item?.id || "").toLowerCase() === framePluginId.value.toLowerCase()
        );
        const matched = /[?&]v=([^&]+)/.exec(String(mine?.url || ""));
        if (matched) version.value = decodeURIComponent(matched[1]);
      } catch {
      }
    }
    function messageOf(res) {
      if (!res || typeof res !== "object") return "";
      for (const key of ["message", "detail", "msg"]) {
        const value = res[key];
        if (typeof value === "string" && value.trim()) return value.trim();
      }
      return "";
    }
    async function saveAll() {
      if (draftSaving.value) return;
      const scrapeOk = await saveScrapeSettings();
      if (!scrapeOk) return;
      const actorOk = await saveActorSettings();
      if (!actorOk) return;
      const ok = await saveDraft();
      if (!ok) return;
      emit("action");
      await refreshRuntime();
    }
    async function cleanCache() {
      const ok = await confirm({
        type: "warn",
        title: "清理缓存",
        content: "将删除插件缓存目录里的图片与 JSON 缓存（不影响已下载的媒体、不删数据库）。确认继续？",
        confirmText: "清理",
        cancelText: "取消"
      });
      if (!ok) return;
      const done = await cleanCacheDraft();
      if (!done) return;
      await refreshRuntime();
    }
    async function clearNotices() {
      const ok = await confirm({
        type: "warn",
        title: "清空通知",
        content: `将清空全部 ${notices.value.length} 条通知，且无法恢复。确认继续？`,
        confirmText: "清空",
        cancelText: "取消"
      });
      if (!ok) return;
      noticeClearing.value = true;
      try {
        const result = await store.clearNotices();
        if (!result.ok) {
          toast.warning(result.message || "清空通知失败");
          return;
        }
        notices.value = [];
        await refreshRuntime();
      } finally {
        noticeClearing.value = false;
      }
    }
    function closePanel() {
      emit("close");
    }
    function openSettings() {
      applyPendingSection();
      ensureDraft();
      settingsOpen.value = true;
    }
    let draftLoaded = false;
    function ensureDraft() {
      if (draftLoaded) return;
      draftLoaded = true;
      void loadHostConfig();
      void loadDraft();
    }
    async function loadHostConfig() {
      if (hostLoaded.value) return;
      const api = rawApi();
      if (!api.get || !pluginId.value) return;
      try {
        const res = await api.get(`plugin/${pluginId.value}`, { feedback: "silent" });
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        hydrateHost(payload);
      } catch {
      }
    }
    function closeSettings() {
      settingsOpen.value = false;
    }
    async function saveHostConfig(config) {
      if (settingsEntry.value) {
        emit("save", config);
        return;
      }
      if (!hostLoaded.value) {
        throw new Error("尚未读到插件配置，本次未提交宿主配置（请关掉设置窗口重开一次再保存）");
      }
      const api = rawApi();
      if (!api.put || !pluginId.value) {
        throw new Error("宿主不支持保存插件配置（缺少 PUT 能力）");
      }
      const res = await api.put(`plugin/${pluginId.value}`, config, { feedback: "silent" });
      const payload = res && typeof res === "object" && "data" in res ? res.data : res;
      if (payload?.success === false) {
        throw new Error(messageOf(payload) || "插件配置保存失败");
      }
    }
    watch(
      () => props.mode,
      (mode) => {
        if (mode === "settings") openSettings();
        else closeSettings();
      }
    );
    function applyPendingSection() {
      const pending = takePendingSettingsSection();
      if (pending && SETTINGS_SECTIONS.some((item) => item.key === pending)) {
        settingsSection.value = pending;
        if (SCRAPE_SECTIONS.includes(pending)) ensureScrapeLoaded();
        if (ACTOR_SECTIONS.includes(pending)) ensureActorLoaded();
      }
    }
    onMounted(() => {
      emit("layout", { maxWidth: DEFAULT_MAX_WIDTH });
      runtime.start();
      void loadVersion();
      if (props.mode === "settings") {
        openSettings();
      }
    });
    onBeforeUnmount(() => {
      runtime.stop();
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_toolbar_title = _resolveComponent("v-toolbar-title");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_toolbar = _resolveComponent("v-toolbar");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_list_subheader = _resolveComponent("v-list-subheader");
      const _component_v_list_item = _resolveComponent("v-list-item");
      const _component_v_list = _resolveComponent("v-list");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_subtitle = _resolveComponent("v-card-subtitle");
      const _component_v_card_item = _resolveComponent("v-card-item");
      const _component_v_list_item_title = _resolveComponent("v-list-item-title");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_skeleton_loader = _resolveComponent("v-skeleton-loader");
      const _component_v_dialog = _resolveComponent("v-dialog");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_toolbar, {
          density: "comfortable",
          color: "surface",
          class: "avh-topbar"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-movie-open-star",
                color: "primary",
                class: "ms-2"
              }),
              _createVNode(_component_v_toolbar_title, { class: "avh-title" }, {
                default: _withCtx(() => [
                  _cache[15] || (_cache[15] = _createElementVNode("span", { class: "text-h6" }, "AV 资源助手", -1)),
                  version.value ? (_openBlock(), _createElementBlock("span", _hoisted_3, "v" + _toDisplayString(version.value), 1)) : _createCommentVNode("", true),
                  _unref(overview).enabled === false ? (_openBlock(), _createBlock(_component_v_chip, {
                    key: 1,
                    size: "x-small",
                    color: "warning",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => _cache[14] || (_cache[14] = [
                      _createTextVNode("已停用")
                    ])),
                    _: 1
                  })) : _createCommentVNode("", true)
                ]),
                _: 1
              })
            ]),
            _createElementVNode("div", _hoisted_4, [
              _createVNode(_component_v_text_field, {
                modelValue: query.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => query.value = $event),
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                "single-line": "",
                autocomplete: "off",
                placeholder: "搜索番号 / 演员（如 SSIS-001）…",
                class: "avh-searchbox__input",
                onKeydown: _withKeys(runSearch, ["enter"])
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_btn, {
                color: "primary",
                variant: "flat",
                size: "small",
                onClick: runSearch
              }, {
                default: _withCtx(() => _cache[16] || (_cache[16] = [
                  _createTextVNode("搜索")
                ])),
                _: 1
              })
            ]),
            _createElementVNode("div", _hoisted_5, [
              _createVNode(_component_v_btn, {
                variant: "text",
                class: "avh-bell",
                title: "通知",
                onClick: openNotify
              }, {
                default: _withCtx(() => [
                  _cache[17] || (_cache[17] = _createTextVNode(" 🔔 通知 ")),
                  notifyUnread() > 0 ? (_openBlock(), _createElementBlock("span", _hoisted_6, _toDisplayString(notifyUnread()), 1)) : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_v_btn, {
                variant: "text",
                "prepend-icon": "mdi-close",
                class: "me-2",
                onClick: closePanel
              }, {
                default: _withCtx(() => _cache[18] || (_cache[18] = [
                  _createTextVNode("关闭")
                ])),
                _: 1
              })
            ])
          ]),
          _: 1
        }),
        _createVNode(_component_v_divider),
        _createElementVNode("div", _hoisted_7, [
          _createElementVNode("nav", _hoisted_8, [
            _createElementVNode("div", _hoisted_9, [
              _createVNode(_component_v_list, {
                density: "compact",
                nav: "",
                selected: [activeNavKey.value],
                mandatory: ""
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_list_subheader, null, {
                    default: _withCtx(() => _cache[19] || (_cache[19] = [
                      _createTextVNode("数据台")
                    ])),
                    _: 1
                  }),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(dataSections.value, (item) => {
                    return _openBlock(), _createBlock(_component_v_list_item, {
                      key: item.key,
                      value: `data:${item.key}`,
                      "prepend-icon": item.icon,
                      title: item.title,
                      onClick: ($event) => pick(item)
                    }, {
                      append: _withCtx(() => [
                        item.badge ? (_openBlock(), _createElementBlock("span", {
                          key: 0,
                          class: _normalizeClass(["avh-pill", { "avh-pill--warn": item.badge.warn, "avh-pill--zero": item.badge.count === 0 }])
                        }, _toDisplayString(item.badge.count), 3)) : _createCommentVNode("", true)
                      ]),
                      _: 2
                    }, 1032, ["value", "prepend-icon", "title", "onClick"]);
                  }), 128))
                ]),
                _: 1
              }, 8, ["selected"]),
              _createVNode(_component_v_card, {
                variant: "outlined",
                class: "avh-overview mt-2"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card_item, null, {
                    prepend: _withCtx(() => [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-gauge",
                        color: "primary"
                      })
                    ]),
                    default: _withCtx(() => [
                      _createVNode(_component_v_card_title, { class: "text-body-2 font-weight-medium" }, {
                        default: _withCtx(() => _cache[20] || (_cache[20] = [
                          _createTextVNode("运行概况")
                        ])),
                        _: 1
                      }),
                      _unref(updatedAt) ? (_openBlock(), _createBlock(_component_v_card_subtitle, {
                        key: 0,
                        class: "text-caption"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("更新于 " + _toDisplayString(_unref(updatedAt)), 1)
                        ]),
                        _: 1
                      })) : _createCommentVNode("", true)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_card_text, null, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_list, {
                        density: "compact",
                        class: "pa-0"
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_10, _toDisplayString(_unref(overview).subs === null ? "—" : _unref(overview).subs), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[21] || (_cache[21] = [
                                  _createTextVNode("订阅")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_11, _toDisplayString(_unref(overview).awaitTasks === null ? "—" : _unref(overview).awaitTasks), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[22] || (_cache[22] = [
                                  _createTextVNode("待确认任务")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_12, _toDisplayString(_unref(overview).downloading === null ? "—" : _unref(overview).downloading), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[23] || (_cache[23] = [
                                  _createTextVNode("下载中")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_13, _toDisplayString(_unref(overview).favorites === null ? "—" : _unref(overview).favorites), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[24] || (_cache[24] = [
                                  _createTextVNode("收藏演员")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_14, _toDisplayString(_unref(overview).notices === null ? "—" : _unref(overview).notices), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[25] || (_cache[25] = [
                                  _createTextVNode("通知")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_divider, { class: "my-2" }),
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_15, _toDisplayString(_unref(overview).cacheSize), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[26] || (_cache[26] = [
                                  _createTextVNode("缓存")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_list_item, { class: "px-0" }, {
                            append: _withCtx(() => [
                              _createElementVNode("span", _hoisted_16, _toDisplayString(_unref(overview).nextCheck), 1)
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                default: _withCtx(() => _cache[27] || (_cache[27] = [
                                  _createTextVNode("下次检查")
                                ])),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        block: "",
                        size: "small",
                        variant: "text",
                        "prepend-icon": "mdi-refresh",
                        loading: _unref(runtimeLoading),
                        class: "mt-2",
                        onClick: _cache[1] || (_cache[1] = ($event) => _unref(refreshRuntime)(true))
                      }, {
                        default: _withCtx(() => _cache[28] || (_cache[28] = [
                          _createTextVNode("刷新")
                        ])),
                        _: 1
                      }, 8, ["loading"]),
                      _unref(runtimeError) ? (_openBlock(), _createBlock(_component_v_alert, {
                        key: 0,
                        type: "warning",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-2 text-caption"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(_unref(runtimeError)), 1)
                        ]),
                        _: 1
                      })) : _createCommentVNode("", true)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _createVNode(_component_v_btn, {
              block: "",
              size: "small",
              variant: "text",
              "prepend-icon": "mdi-cog-outline",
              class: "avh-nav__switch",
              onClick: openSettings
            }, {
              default: _withCtx(() => _cache[29] || (_cache[29] = [
                _createTextVNode("打开设置")
              ])),
              _: 1
            })
          ]),
          _createVNode(_component_v_divider, { vertical: "" }),
          _createElementVNode("section", _hoisted_17, [
            nativeView.value && framePluginId.value ? (_openBlock(), _createBlock(_resolveDynamicComponent(nativeView.value), {
              key: section.value === "actors" ? `actors:${actorNonce.value}` : section.value,
              store: _unref(store),
              "plugin-id": framePluginId.value,
              api: currentApi(),
              toast: _unref(injectedToast),
              "focus-actor": section.value === "actors" ? actorFocus.value : "",
              onSwitch: openSettings,
              onRefreshSide: _cache[2] || (_cache[2] = ($event) => _unref(refreshRuntime)(true)),
              onOpenMovie,
              onOpenActor: openActorFromOverlay
            }, null, 40, ["store", "plugin-id", "api", "toast", "focus-actor"])) : framePluginId.value ? (_openBlock(), _createBlock(AppFrame, {
              key: 1,
              "plugin-id": framePluginId.value,
              "section-key": section.value,
              version: version.value
            }, null, 8, ["plugin-id", "section-key", "version"])) : (_openBlock(), _createBlock(_component_v_alert, {
              key: 2,
              type: "warning",
              variant: "tonal"
            }, {
              default: _withCtx(() => _cache[30] || (_cache[30] = [
                _createTextVNode(" 宿主没有传入 pluginId，无法定位内嵌应用。 ")
              ])),
              _: 1
            }))
          ])
        ]),
        _createVNode(_component_v_dialog, {
          modelValue: settingsOpen.value,
          "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => settingsOpen.value = $event),
          "max-width": "1120",
          scrollable: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { class: "avh-settings" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_toolbar, {
                  density: "comfortable",
                  color: "surface",
                  class: "avh-settings__bar"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: "mdi-cog-outline",
                      color: "primary",
                      class: "ms-2"
                    }),
                    _createVNode(_component_v_toolbar_title, { class: "text-h6" }, {
                      default: _withCtx(() => _cache[31] || (_cache[31] = [
                        _createTextVNode("设置")
                      ])),
                      _: 1
                    }),
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      color: _unref(dirty) || scrapeDirty.value || actorDirty.value ? "warning" : "primary",
                      variant: _unref(dirty) || scrapeDirty.value || actorDirty.value ? "flat" : "tonal",
                      "prepend-icon": "mdi-content-save",
                      loading: _unref(draftSaving),
                      class: "me-2",
                      onClick: saveAll
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(_unref(dirty) || scrapeDirty.value || actorDirty.value ? "保存修改 ● 未保存" : _unref(saveButtonLabel)), 1)
                      ]),
                      _: 1
                    }, 8, ["color", "variant", "loading"]),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      icon: "mdi-close",
                      title: "关闭设置（回到数据台）",
                      class: "me-2",
                      onClick: closeSettings
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_divider),
                _createElementVNode("div", _hoisted_18, [
                  _createElementVNode("nav", _hoisted_19, [
                    _createVNode(_component_v_list, {
                      density: "compact",
                      nav: "",
                      selected: [settingsSection.value],
                      mandatory: ""
                    }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(SETTINGS_SECTIONS), (item) => {
                          return _openBlock(), _createBlock(_component_v_list_item, {
                            key: item.key,
                            value: item.key,
                            "prepend-icon": item.icon,
                            title: item.title,
                            onClick: ($event) => pickSetting(item)
                          }, {
                            append: _withCtx(() => [
                              sectionDirtyEx(item.key) ? (_openBlock(), _createBlock(_component_v_icon, {
                                key: 0,
                                icon: "mdi-circle",
                                size: "8",
                                color: "warning",
                                title: "本栏有未保存改动"
                              })) : _createCommentVNode("", true)
                            ]),
                            _: 2
                          }, 1032, ["value", "prepend-icon", "title", "onClick"]);
                        }), 128))
                      ]),
                      _: 1
                    }, 8, ["selected"])
                  ]),
                  _createVNode(_component_v_divider, { vertical: "" }),
                  _createElementVNode("section", _hoisted_20, [
                    _unref(draftError) ? (_openBlock(), _createBlock(_component_v_alert, {
                      key: 0,
                      type: "warning",
                      variant: "tonal",
                      density: "compact",
                      class: "text-caption mb-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(_unref(draftError)), 1)
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true),
                    _unref(draftLoading) && !ruleView.value ? (_openBlock(), _createBlock(_component_v_skeleton_loader, {
                      key: 1,
                      type: "article",
                      class: "mb-3"
                    })) : _createCommentVNode("", true),
                    settingsSection.value === "general" ? (_openBlock(), _createBlock(GeneralPanel, {
                      key: 2,
                      config: _unref(hostConfig),
                      "enabled-known": _unref(enabledKnown),
                      onPatch: _cache[3] || (_cache[3] = (patch) => Object.assign(_unref(hostConfig), patch))
                    }, null, 8, ["config", "enabled-known"])) : settingsSection.value === "sites" ? (_openBlock(), _createBlock(SitesPanel, {
                      key: 3,
                      sites: ruleView.value?.sites || [],
                      "pref-sites": ruleView.value?.prefSites || [],
                      options: _unref(sites),
                      loaded: _unref(sitesLoaded),
                      "onUpdate:sites": _cache[4] || (_cache[4] = (value) => patchRule({ sites: value })),
                      "onUpdate:prefSites": _cache[5] || (_cache[5] = (value) => patchRule({ prefSites: value }))
                    }, null, 8, ["sites", "pref-sites", "options", "loaded"])) : settingsSection.value === "rule" && ruleView.value ? (_openBlock(), _createBlock(RulePanel, {
                      key: 4,
                      rule: ruleView.value,
                      "policy-min-interval": _unref(checkInfo)?.minIntervalMin || 0,
                      "site-scope-count": ruleView.value.sites.length,
                      onPatch: patchRule
                    }, null, 8, ["rule", "policy-min-interval", "site-scope-count"])) : settingsSection.value === "scrape" ? (_openBlock(), _createBlock(ScrapePanel, {
                      key: 5,
                      settings: scrapeView.value,
                      api: currentApi(),
                      toast: _unref(injectedToast),
                      onPatch: patchScrape
                    }, null, 8, ["settings", "api", "toast"])) : settingsSection.value === "scrapeRule" ? (_openBlock(), _createBlock(ScrapeRulePanel, {
                      key: 6,
                      settings: scrapeView.value,
                      "plugin-id": pluginId.value,
                      api: currentApi(),
                      toast: _unref(injectedToast),
                      onPatch: patchScrape
                    }, null, 8, ["settings", "plugin-id", "api", "toast"])) : settingsSection.value === "actor" ? (_openBlock(), _createBlock(ActorPanel, {
                      key: 7,
                      settings: actorView.value,
                      api: currentApi(),
                      toast: _unref(injectedToast),
                      onPatch: patchActor
                    }, null, 8, ["settings", "api", "toast"])) : settingsSection.value === "notify" ? (_openBlock(), _createBlock(NotifyPanel, {
                      key: 8,
                      notices: _unref(notices),
                      loading: _unref(noticeLoading),
                      clearing: noticeClearing.value,
                      onClear: clearNotices,
                      onReload: _unref(loadNotices)
                    }, null, 8, ["notices", "loading", "clearing", "onReload"])) : settingsSection.value === "library" ? (_openBlock(), _createBlock(LibraryPanel, {
                      key: 9,
                      config: _unref(hostConfig),
                      validation: _unref(validation),
                      onPatch: _cache[6] || (_cache[6] = (patch) => Object.assign(_unref(hostConfig), patch))
                    }, null, 8, ["config", "validation"])) : settingsSection.value === "runtime" ? (_openBlock(), _createBlock(RuntimePanel, {
                      key: 10,
                      config: _unref(hostConfig),
                      "cache-text": _unref(cacheText),
                      "cache-bytes": _unref(cacheBytes),
                      check: _unref(checkInfo),
                      cleaning: _unref(cacheCleaning),
                      loading: _unref(runtimeLoading),
                      onPatch: _cache[7] || (_cache[7] = (patch) => Object.assign(_unref(hostConfig), patch)),
                      onClean: cleanCache,
                      onRefresh: _cache[8] || (_cache[8] = ($event) => _unref(refreshRuntime)(true))
                    }, null, 8, ["config", "cache-text", "cache-bytes", "check", "cleaning", "loading"])) : settingsSection.value === "about" ? (_openBlock(), _createBlock(AboutPanel, {
                      key: 11,
                      version: version.value,
                      "plugin-id": props.pluginId,
                      "source-plugin-id": props.sourcePluginId
                    }, null, 8, ["version", "plugin-id", "source-plugin-id"])) : (_openBlock(), _createBlock(_component_v_alert, {
                      key: 12,
                      type: "info",
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(" 未知栏目：" + _toDisplayString(activeSetting.value.title), 1)
                      ]),
                      _: 1
                    }))
                  ])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        framePluginId.value ? (_openBlock(), _createBlock(DetailDrawer, {
          key: 0,
          open: drawerOpen.value,
          number: drawerNumber.value,
          id: drawerId.value,
          store: _unref(store),
          "plugin-id": framePluginId.value,
          api: currentApi(),
          toast: _unref(injectedToast),
          onClose: _cache[10] || (_cache[10] = ($event) => drawerOpen.value = false),
          onOpenActor: openActorFromOverlay,
          onRefreshSide: _cache[11] || (_cache[11] = ($event) => _unref(refreshRuntime)(true))
        }, null, 8, ["open", "number", "id", "store", "plugin-id", "api", "toast"])) : _createCommentVNode("", true),
        framePluginId.value ? (_openBlock(), _createBlock(SearchDialog, {
          key: 1,
          ref_key: "searchDialog",
          ref: searchDialog,
          open: searchOpen.value,
          "plugin-id": framePluginId.value,
          api: currentApi(),
          onClose: _cache[12] || (_cache[12] = ($event) => searchOpen.value = false),
          onOpenMovie: onSearchPickMovie,
          onOpenActor: openActorFromOverlay
        }, null, 8, ["open", "plugin-id", "api"])) : _createCommentVNode("", true),
        _createVNode(NotifyDrawer, {
          open: notifyOpen.value,
          notices: _unref(store).notices.value,
          "plugin-id": framePluginId.value,
          clearing: noticeClearing.value,
          onClose: _cache[13] || (_cache[13] = ($event) => notifyOpen.value = false),
          onClear: clearNoticesFromDrawer
        }, null, 8, ["open", "notices", "plugin-id", "clearing"]),
        _createVNode(BottomToast)
      ]);
    };
  }
});

const Console = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-228305ec"]]);

export { CONSOLE_EMIT_NAMES as C, Console as a };
