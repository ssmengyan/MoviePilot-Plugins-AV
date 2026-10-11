import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {defineComponent:_defineComponent$p} = await importShared('vue');

const {openBlock:_openBlock$p,createElementBlock:_createElementBlock$o} = await importShared('vue');

const _hoisted_1$o = ["src"];
const {computed: computed$j} = await importShared('vue');

const _sfc_main$p = /* @__PURE__ */ _defineComponent$p({
  __name: "AppFrame",
  props: {
    pluginId: {},
    version: { default: "" },
    sectionKey: { default: "discover" }
  },
  setup(__props) {
    const props = __props;
    const src = computed$j(() => {
      const params = new URLSearchParams();
      if (props.version) params.set("v", props.version);
      if (props.sectionKey) params.set("view", props.sectionKey);
      const query = params.toString();
      return `/api/v1/plugin/${props.pluginId}/ui/${query ? `?${query}` : ""}`;
    });
    return (_ctx, _cache) => {
      return _openBlock$p(), _createElementBlock$o("iframe", {
        key: `${_ctx.pluginId}:${_ctx.sectionKey}`,
        src: src.value,
        class: "avh-app-frame",
        title: "AV 资源助手 · 内嵌应用",
        referrerpolicy: "no-referrer",
        allow: "clipboard-write"
      }, null, 8, _hoisted_1$o);
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

const AppFrame = /* @__PURE__ */ _export_sfc(_sfc_main$p, [["__scopeId", "data-v-d2cb29e5"]]);

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
    maxPerDay: num(src.maxPerDay, RULE_FALLBACK$1.maxPerDay, true, 1),
    // 限流参数不由界面放宽：拿不到就把政策固定值原样带回去。
    minIntervalMin: num(src.minIntervalMin, RULE_FALLBACK$1.minIntervalMin, true, 1),
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
  return a.enabled === b.enabled && a.proxy === b.proxy && a.javdb_bin === b.javdb_bin && a.data_root === b.data_root && a.emby_host === b.emby_host && a.emby_apikey === b.emby_apikey;
}
function embyHalfFilled(config) {
  const host = str(config?.emby_host).trim();
  const key = str(config?.emby_apikey).trim();
  if (host && !key || !host && key) {
    return "Emby 地址与 API 密钥要一起填；两栏都留空 = 复用 MoviePilot「设置 → 媒体服务器」。";
  }
  return "";
}

const {computed: computed$i,ref: ref$k} = await importShared('vue');
const POLL_INTERVAL_MS = 15e3;
function len(value) {
  return Array.isArray(value) ? value.length : null;
}
function useRuntimeInfo(api) {
  const data = ref$k(null);
  const error = ref$k("");
  const loading = ref$k(false);
  const updatedAt = ref$k("");
  let timer = null;
  const overview = computed$i(() => {
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
  const recovery = computed$i(() => ({
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
  { key: "notify", title: "通知", icon: "mdi-bell" },
  { key: "library", title: "媒体库", icon: "mdi-server" },
  { key: "runtime", title: "运行与缓存", icon: "mdi-database-cog" },
  { key: "about", title: "关于", icon: "mdi-information-outline" }
];
const DIRTY_GROUPS = {
  general: "host",
  sites: "rule",
  rule: "rule",
  notify: "none",
  library: "host",
  runtime: "none",
  about: "none"
};

const {computed: computed$h,reactive: reactive$3,ref: ref$j,shallowRef: shallowRef$1} = await importShared('vue');
function useSettingsDraft(options) {
  const t = hostToast(options.toast);
  const rulePlain = ref$j(null);
  const rule = rulePlain;
  const hostConfig = reactive$3({
    enabled: options.initialConfig?.enabled === true,
    proxy: str(options.initialConfig?.proxy),
    javdb_bin: str(options.initialConfig?.javdb_bin),
    data_root: str(options.initialConfig?.data_root),
    emby_host: str(options.initialConfig?.emby_host),
    emby_apikey: str(options.initialConfig?.emby_apikey)
  });
  const sites = ref$j([]);
  const sitesLoaded = ref$j(false);
  const notices = ref$j([]);
  const cacheText = ref$j("");
  const cacheBytes = ref$j(null);
  const checkInfo = ref$j(null);
  const bootstrapEnabled = ref$j(null);
  const hostLoaded = ref$j(
    Boolean(options.initialConfig && Object.keys(options.initialConfig).length > 0)
  );
  const loading = ref$j(false);
  const saving = ref$j(false);
  const noticeLoading = ref$j(false);
  const cacheCleaning = ref$j(false);
  const error = ref$j("");
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
      emby_apikey: str(options.initialConfig?.emby_apikey)
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
      emby_apikey: str(conf.emby_apikey)
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
  const ruleDirty = computed$h(() => !sameRule(rule.value, ruleBase.value));
  const hostDirty = computed$h(() => !sameHost(hostConfig, hostBase.value));
  const dirty = computed$h(() => ruleDirty.value || hostDirty.value);
  const saveButtonLabel = computed$h(() => dirty.value ? "保存修改 ● 未保存" : "保存修改");
  const enabledKnown = computed$h(
    () => hostLoaded.value || typeof options.initialConfig?.enabled === "boolean" || bootstrapEnabled.value !== null
  );
  const validation = computed$h(() => embyHalfFilled(hostConfig));
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
        emby_apikey: str(hostConfig.emby_apikey).trim()
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

const {defineComponent:_defineComponent$o} = await importShared('vue');

const {resolveComponent:_resolveComponent$k,createVNode:_createVNode$k,createTextVNode:_createTextVNode$j,withCtx:_withCtx$k,createElementVNode:_createElementVNode$m,openBlock:_openBlock$o,createElementBlock:_createElementBlock$n,createCommentVNode:_createCommentVNode$i,createBlock:_createBlock$j} = await importShared('vue');

const _hoisted_1$n = {
  key: 0,
  class: "text-caption text-medium-emphasis mb-4"
};
const _sfc_main$o = /* @__PURE__ */ _defineComponent$o({
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
      const _component_v_icon = _resolveComponent$k("v-icon");
      const _component_v_card_title = _resolveComponent$k("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$k("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$k("v-card-item");
      const _component_v_switch = _resolveComponent$k("v-switch");
      const _component_v_text_field = _resolveComponent$k("v-text-field");
      const _component_v_card_text = _resolveComponent$k("v-card-text");
      const _component_v_card = _resolveComponent$k("v-card");
      return _openBlock$o(), _createBlock$j(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$k(() => [
          _createVNode$k(_component_v_card_item, null, {
            prepend: _withCtx$k(() => [
              _createVNode$k(_component_v_icon, {
                icon: "mdi-cog-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$k(() => [
              _createVNode$k(_component_v_card_title, null, {
                default: _withCtx$k(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$j("常规")
                ])),
                _: 1
              }),
              _createVNode$k(_component_v_card_subtitle, null, {
                default: _withCtx$k(() => _cache[5] || (_cache[5] = [
                  _createTextVNode$j("插件开关、代理与路径 · 属于宿主插件配置")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$k(_component_v_card_text, null, {
            default: _withCtx$k(() => [
              _createVNode$k(_component_v_switch, {
                "model-value": props.config.enabled,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "启用插件",
                class: "mb-2",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("enabled", value === true))
              }, null, 8, ["model-value"]),
              !props.enabledKnown ? (_openBlock$o(), _createElementBlock$n("p", _hoisted_1$n, _cache[6] || (_cache[6] = [
                _createTextVNode$j(" 拿不到当前开关状态（"),
                _createElementVNode$m("code", null, "/bootstrap", -1),
                _createTextVNode$j(" 未返回 "),
                _createElementVNode$m("code", null, "enabled", -1),
                _createTextVNode$j("），保存前请确认。 ")
              ]))) : _createCommentVNode$i("", true),
              _cache[7] || (_cache[7] = _createElementVNode$m("p", { class: "text-caption text-medium-emphasis mb-4" }, " 关闭后定时订阅检查与「运行一次」都不执行，界面仍可浏览。 ", -1)),
              _createVNode$k(_component_v_text_field, {
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
              _createVNode$k(_component_v_text_field, {
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
              _createVNode$k(_component_v_text_field, {
                "model-value": props.config.data_root,
                label: "数据目录",
                placeholder: "留空 = 插件数据目录下的 cache",
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

const GeneralPanel = /* @__PURE__ */ _export_sfc(_sfc_main$o, [["__scopeId", "data-v-b5a5bdb2"]]);

const {defineComponent:_defineComponent$n} = await importShared('vue');

const {resolveComponent:_resolveComponent$j,createVNode:_createVNode$j,createTextVNode:_createTextVNode$i,withCtx:_withCtx$j,createElementVNode:_createElementVNode$l,toDisplayString:_toDisplayString$n,openBlock:_openBlock$n,createBlock:_createBlock$i,createCommentVNode:_createCommentVNode$h,renderList:_renderList$d,Fragment:_Fragment$e,createElementBlock:_createElementBlock$m} = await importShared('vue');

const _hoisted_1$m = { class: "avh-row" };
const _hoisted_2$k = { class: "avh-row-main" };
const _hoisted_3$i = { class: "avh-scope text-body-1" };
const _hoisted_4$f = { class: "avh-scope text-body-2" };
const _hoisted_5$e = { class: "avh-row-actions" };
const _hoisted_6$c = { class: "d-flex align-center mb-2" };
const _hoisted_7$c = { class: "text-caption text-medium-emphasis" };
const _hoisted_8$b = { class: "avh-list" };
const _hoisted_9$b = { class: "text-caption text-medium-emphasis" };
const _hoisted_10$a = {
  key: 0,
  class: "text-caption text-medium-emphasis pa-2"
};
const _hoisted_11$9 = { class: "text-caption text-medium-emphasis mb-1" };
const _hoisted_12$9 = { class: "text-caption text-medium-emphasis avh-idx" };
const _hoisted_13$8 = { class: "avh-chips" };
const _hoisted_14$8 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const {computed: computed$g,ref: ref$i} = await importShared('vue');

const _sfc_main$n = /* @__PURE__ */ _defineComponent$n({
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
    const scopeText = computed$g(
      () => props.sites.length ? props.sites.join("、") : "全部站点"
    );
    const prefText = computed$g(
      () => props.prefSites.length ? props.prefSites.join(" › ") : "未设置（按站点清单顺序）"
    );
    const pickOpen = ref$i(false);
    const pickQuery = ref$i("");
    const pickDraft = ref$i([]);
    const filteredOptions = computed$g(() => {
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
    const prefOpen = ref$i(false);
    const prefDraft = ref$i([]);
    const prefCandidates = computed$g(
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
      const _component_v_icon = _resolveComponent$j("v-icon");
      const _component_v_card_title = _resolveComponent$j("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$j("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$j("v-card-item");
      const _component_v_btn = _resolveComponent$j("v-btn");
      const _component_v_alert = _resolveComponent$j("v-alert");
      const _component_v_card_text = _resolveComponent$j("v-card-text");
      const _component_v_card = _resolveComponent$j("v-card");
      const _component_v_text_field = _resolveComponent$j("v-text-field");
      const _component_v_spacer = _resolveComponent$j("v-spacer");
      const _component_v_divider = _resolveComponent$j("v-divider");
      const _component_v_checkbox = _resolveComponent$j("v-checkbox");
      const _component_v_card_actions = _resolveComponent$j("v-card-actions");
      const _component_v_dialog = _resolveComponent$j("v-dialog");
      const _component_v_list_item_title = _resolveComponent$j("v-list-item-title");
      const _component_v_list_item = _resolveComponent$j("v-list-item");
      const _component_v_list = _resolveComponent$j("v-list");
      const _component_v_chip = _resolveComponent$j("v-chip");
      return _openBlock$n(), _createElementBlock$m(_Fragment$e, null, [
        _createVNode$j(_component_v_card, {
          variant: "tonal",
          class: "avh-panel"
        }, {
          default: _withCtx$j(() => [
            _createVNode$j(_component_v_card_item, null, {
              prepend: _withCtx$j(() => [
                _createVNode$j(_component_v_icon, {
                  icon: "mdi-web",
                  color: "primary"
                })
              ]),
              default: _withCtx$j(() => [
                _createVNode$j(_component_v_card_title, null, {
                  default: _withCtx$j(() => _cache[5] || (_cache[5] = [
                    _createTextVNode$i("搜索站点")
                  ])),
                  _: 1
                }),
                _createVNode$j(_component_v_card_subtitle, null, {
                  default: _withCtx$j(() => _cache[6] || (_cache[6] = [
                    _createTextVNode$i("勾选与排序都在弹窗里 · 数据走 POST /rule")
                  ])),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$j(_component_v_card_text, null, {
              default: _withCtx$j(() => [
                _createElementVNode$l("div", _hoisted_1$m, [
                  _createElementVNode$l("div", _hoisted_2$k, [
                    _cache[7] || (_cache[7] = _createElementVNode$l("div", { class: "text-caption text-medium-emphasis mb-1" }, "当前搜索范围", -1)),
                    _createElementVNode$l("div", _hoisted_3$i, _toDisplayString$n(scopeText.value), 1),
                    _cache[8] || (_cache[8] = _createElementVNode$l("div", { class: "text-caption text-medium-emphasis mt-3 mb-1" }, "优先站点（命中即停，顺序有意义）", -1)),
                    _createElementVNode$l("div", _hoisted_4$f, _toDisplayString$n(prefText.value), 1)
                  ]),
                  _createElementVNode$l("div", _hoisted_5$e, [
                    _createVNode$j(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                      class: "mb-2",
                      onClick: openPick
                    }, {
                      default: _withCtx$j(() => _cache[9] || (_cache[9] = [
                        _createTextVNode$i("选择站点")
                      ])),
                      _: 1
                    }),
                    _createVNode$j(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-sort",
                      onClick: openPref
                    }, {
                      default: _withCtx$j(() => _cache[10] || (_cache[10] = [
                        _createTextVNode$i("优先站点")
                      ])),
                      _: 1
                    })
                  ])
                ]),
                _ctx.loaded && !_ctx.options.length ? (_openBlock$n(), _createBlock$i(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mt-3 text-caption"
                }, {
                  default: _withCtx$j(() => _cache[11] || (_cache[11] = [
                    _createTextVNode$i("没有读到任何站点（MoviePilot 站点目录为空或读取失败），下面两个按钮打开也没有内容可选。")
                  ])),
                  _: 1
                })) : _createCommentVNode$h("", true),
                _cache[12] || (_cache[12] = _createElementVNode$l("p", { class: "text-caption text-medium-emphasis mt-4 mb-0" }, " 「当前搜索范围」留空 = 全部已配置站点；优先站点会先搜、命中即停，所以顺序有意义。 两处都只写进默认规则，按顶条「保存修改」才生效。 ", -1))
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$j(_component_v_dialog, {
          modelValue: pickOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$j(() => [
            _createVNode$j(_component_v_card, null, {
              default: _withCtx$j(() => [
                _createVNode$j(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$j(() => [
                    _createVNode$j(_component_v_icon, {
                      icon: "mdi-checkbox-multiple-marked-outline",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[13] || (_cache[13] = _createTextVNode$i(" 选择站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$j(_component_v_card_subtitle, null, {
                  default: _withCtx$j(() => [
                    _createTextVNode$i("不勾任何站点 = 搜索全部已配置站点（" + _toDisplayString$n(props.options.length) + " 个）", 1)
                  ]),
                  _: 1
                }),
                _createVNode$j(_component_v_card_text, null, {
                  default: _withCtx$j(() => [
                    _createVNode$j(_component_v_text_field, {
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
                    _createElementVNode$l("div", _hoisted_6$c, [
                      _createVNode$j(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickAll
                      }, {
                        default: _withCtx$j(() => _cache[14] || (_cache[14] = [
                          _createTextVNode$i("全选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$j(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickNone
                      }, {
                        default: _withCtx$j(() => _cache[15] || (_cache[15] = [
                          _createTextVNode$i("全不选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$j(_component_v_spacer),
                      _createElementVNode$l("span", _hoisted_7$c, "已选 " + _toDisplayString$n(pickDraft.value.length), 1)
                    ]),
                    _createVNode$j(_component_v_divider, { class: "mb-1" }),
                    _createElementVNode$l("div", _hoisted_8$b, [
                      (_openBlock$n(true), _createElementBlock$m(_Fragment$e, null, _renderList$d(filteredOptions.value, (item) => {
                        return _openBlock$n(), _createBlock$i(_component_v_checkbox, {
                          key: item.name,
                          "model-value": pickDraft.value.includes(item.name),
                          label: item.name,
                          density: "compact",
                          "hide-details": "",
                          color: "primary",
                          "onUpdate:modelValue": () => pickToggle(item.name)
                        }, {
                          append: _withCtx$j(() => [
                            _createElementVNode$l("span", _hoisted_9$b, _toDisplayString$n(item.adapterLabel || item.adapter || ""), 1)
                          ]),
                          _: 2
                        }, 1032, ["model-value", "label", "onUpdate:modelValue"]);
                      }), 128)),
                      !filteredOptions.value.length ? (_openBlock$n(), _createElementBlock$m("div", _hoisted_10$a, " 没有匹配的站点。 ")) : _createCommentVNode$h("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$j(_component_v_card_actions, null, {
                  default: _withCtx$j(() => [
                    _createVNode$j(_component_v_spacer),
                    _createVNode$j(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickOpen.value = false)
                    }, {
                      default: _withCtx$j(() => _cache[16] || (_cache[16] = [
                        _createTextVNode$i("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$j(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: pickConfirm
                    }, {
                      default: _withCtx$j(() => _cache[17] || (_cache[17] = [
                        _createTextVNode$i("确定")
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
        _createVNode$j(_component_v_dialog, {
          modelValue: prefOpen.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => prefOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$j(() => [
            _createVNode$j(_component_v_card, null, {
              default: _withCtx$j(() => [
                _createVNode$j(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$j(() => [
                    _createVNode$j(_component_v_icon, {
                      icon: "mdi-sort",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[18] || (_cache[18] = _createTextVNode$i(" 优先站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$j(_component_v_card_subtitle, null, {
                  default: _withCtx$j(() => _cache[19] || (_cache[19] = [
                    _createTextVNode$i("先搜这些站，命中即停 —— 顺序就是搜索顺序")
                  ])),
                  _: 1
                }),
                _createVNode$j(_component_v_card_text, null, {
                  default: _withCtx$j(() => [
                    _createElementVNode$l("div", _hoisted_11$9, "优先顺序（" + _toDisplayString$n(prefDraft.value.length) + "）", 1),
                    _createVNode$j(_component_v_list, {
                      density: "compact",
                      class: "avh-list mb-3"
                    }, {
                      default: _withCtx$j(() => [
                        (_openBlock$n(true), _createElementBlock$m(_Fragment$e, null, _renderList$d(prefDraft.value, (name, index) => {
                          return _openBlock$n(), _createBlock$i(_component_v_list_item, {
                            key: `${name}:${index}`
                          }, {
                            prepend: _withCtx$j(() => [
                              _createElementVNode$l("span", _hoisted_12$9, _toDisplayString$n(index + 1), 1)
                            ]),
                            append: _withCtx$j(() => [
                              _createVNode$j(_component_v_btn, {
                                icon: "mdi-arrow-up",
                                size: "x-small",
                                variant: "text",
                                disabled: index === 0,
                                onClick: ($event) => prefMove(index, -1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$j(_component_v_btn, {
                                icon: "mdi-arrow-down",
                                size: "x-small",
                                variant: "text",
                                disabled: index === prefDraft.value.length - 1,
                                onClick: ($event) => prefMove(index, 1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$j(_component_v_btn, {
                                icon: "mdi-close",
                                size: "x-small",
                                variant: "text",
                                onClick: ($event) => prefRemove(index)
                              }, null, 8, ["onClick"])
                            ]),
                            default: _withCtx$j(() => [
                              _createVNode$j(_component_v_list_item_title, null, {
                                default: _withCtx$j(() => [
                                  _createTextVNode$i(_toDisplayString$n(name), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024);
                        }), 128)),
                        !prefDraft.value.length ? (_openBlock$n(), _createBlock$i(_component_v_list_item, { key: 0 }, {
                          default: _withCtx$j(() => [
                            _createVNode$j(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                              default: _withCtx$j(() => _cache[20] || (_cache[20] = [
                                _createTextVNode$i(" 还没有优先站点：按下面的候选加进来。 ")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        })) : _createCommentVNode$h("", true)
                      ]),
                      _: 1
                    }),
                    _createVNode$j(_component_v_divider, { class: "mb-2" }),
                    _cache[21] || (_cache[21] = _createElementVNode$l("div", { class: "text-caption text-medium-emphasis mb-1" }, "候选站点（点击加入优先顺序）", -1)),
                    _createElementVNode$l("div", _hoisted_13$8, [
                      (_openBlock$n(true), _createElementBlock$m(_Fragment$e, null, _renderList$d(prefCandidates.value, (item) => {
                        return _openBlock$n(), _createBlock$i(_component_v_chip, {
                          key: item.name,
                          size: "small",
                          variant: "tonal",
                          "prepend-icon": "mdi-plus",
                          onClick: ($event) => prefAdd(item.name)
                        }, {
                          default: _withCtx$j(() => [
                            _createTextVNode$i(_toDisplayString$n(item.name), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"]);
                      }), 128)),
                      !prefCandidates.value.length ? (_openBlock$n(), _createElementBlock$m("span", _hoisted_14$8, " 全部站点都已在优先列表里。 ")) : _createCommentVNode$h("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$j(_component_v_card_actions, null, {
                  default: _withCtx$j(() => [
                    _createVNode$j(_component_v_spacer),
                    _createVNode$j(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[3] || (_cache[3] = ($event) => prefOpen.value = false)
                    }, {
                      default: _withCtx$j(() => _cache[22] || (_cache[22] = [
                        _createTextVNode$i("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$j(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: prefConfirm
                    }, {
                      default: _withCtx$j(() => _cache[23] || (_cache[23] = [
                        _createTextVNode$i("确定")
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

const SitesPanel = /* @__PURE__ */ _export_sfc(_sfc_main$n, [["__scopeId", "data-v-b3e77efa"]]);

const {defineComponent:_defineComponent$m} = await importShared('vue');

const {resolveComponent:_resolveComponent$i,createVNode:_createVNode$i,createTextVNode:_createTextVNode$h,withCtx:_withCtx$i,createElementVNode:_createElementVNode$k,renderList:_renderList$c,Fragment:_Fragment$d,openBlock:_openBlock$m,createElementBlock:_createElementBlock$l,toDisplayString:_toDisplayString$m,unref:_unref$4,createBlock:_createBlock$h} = await importShared('vue');

const _hoisted_1$l = { class: "avh-grid mb-2" };
const _sfc_main$m = /* @__PURE__ */ _defineComponent$m({
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
    function patch(key, value) {
      emit("patch", { [key]: value });
    }
    function patchNumber(key, raw) {
      const parsed = Number.parseInt(raw, 10);
      patch(key, Number.isFinite(parsed) ? parsed : 0);
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$i("v-icon");
      const _component_v_card_title = _resolveComponent$i("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$i("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$i("v-card-item");
      const _component_v_btn = _resolveComponent$i("v-btn");
      const _component_v_btn_toggle = _resolveComponent$i("v-btn-toggle");
      const _component_v_switch = _resolveComponent$i("v-switch");
      const _component_v_text_field = _resolveComponent$i("v-text-field");
      const _component_v_alert = _resolveComponent$i("v-alert");
      const _component_v_card_text = _resolveComponent$i("v-card-text");
      const _component_v_card = _resolveComponent$i("v-card");
      return _openBlock$m(), _createBlock$h(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$i(() => [
          _createVNode$i(_component_v_card_item, null, {
            prepend: _withCtx$i(() => [
              _createVNode$i(_component_v_icon, {
                icon: "mdi-filter-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$i(() => [
              _createVNode$i(_component_v_card_title, null, {
                default: _withCtx$i(() => _cache[8] || (_cache[8] = [
                  _createTextVNode$h("下载规则")
                ])),
                _: 1
              }),
              _createVNode$i(_component_v_card_subtitle, null, {
                default: _withCtx$i(() => _cache[9] || (_cache[9] = [
                  _createTextVNode$h("手动搜索与新建订阅的基准 · 数据走 POST /rule")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$i(_component_v_card_text, null, {
            default: _withCtx$i(() => [
              _cache[12] || (_cache[12] = _createElementVNode$k("div", { class: "text-caption text-medium-emphasis mb-1" }, "分辨率策略", -1)),
              _createVNode$i(_component_v_btn_toggle, {
                "model-value": props.rule.res,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-4",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => value && patch("res", value))
              }, {
                default: _withCtx$i(() => [
                  (_openBlock$m(), _createElementBlock$l(_Fragment$d, null, _renderList$c(RES_OPTIONS, (option) => {
                    return _createVNode$i(_component_v_btn, {
                      key: option.value,
                      value: option.value
                    }, {
                      default: _withCtx$i(() => [
                        _createTextVNode$h(_toDisplayString$m(option.label), 1)
                      ]),
                      _: 2
                    }, 1032, ["value"]);
                  }), 64))
                ]),
                _: 1
              }, 8, ["model-value"]),
              _createVNode$i(_component_v_switch, {
                "model-value": props.rule.mustCnsub,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "必须中文字幕",
                class: "mb-1",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("mustCnsub", value === true))
              }, null, 8, ["model-value"]),
              _cache[13] || (_cache[13] = _createElementVNode$k("p", { class: "text-caption text-medium-emphasis mb-3" }, " 打开则没有中字的种直接淘汰；默认关（AV 站中字少，关掉时中字仍加 32 分优先选）。 ", -1)),
              _createVNode$i(_component_v_switch, {
                "model-value": props.rule.preferUncensored,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "破解 / 无码版优先",
                class: "mb-3",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("preferUncensored", value === true))
              }, null, 8, ["model-value"]),
              _createVNode$i(_component_v_switch, {
                "model-value": props.rule.allow4k,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "允许 4K 择优",
                class: "mb-1",
                "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("allow4k", value === true))
              }, null, 8, ["model-value"]),
              _cache[14] || (_cache[14] = _createElementVNode$k("p", { class: "text-caption text-medium-emphasis mb-3" }, "1080P 没有好种时升级 4K。", -1)),
              _createElementVNode$k("div", _hoisted_1$l, [
                _createVNode$i(_component_v_text_field, {
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
                _createVNode$i(_component_v_text_field, {
                  "model-value": String(props.rule.maxPerDay),
                  type: "number",
                  min: "1",
                  label: "每日检查上限",
                  hint: "每天最多检查订阅几次",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = (value) => patchNumber("maxPerDay", String(value ?? "")))
                }, null, 8, ["model-value"]),
                _createVNode$i(_component_v_text_field, {
                  "model-value": String(props.policyMinInterval || _unref$4(POLICY_MIN_INTERVAL_MIN)),
                  label: "检查间隔下限（分钟，只读）",
                  hint: "政策固定值，界面不放宽",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  readonly: "",
                  disabled: ""
                }, null, 8, ["model-value"])
              ]),
              _createVNode$i(_component_v_switch, {
                "model-value": props.rule.btFallback,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "PT 搜不到时允许 BT 磁力兜底",
                class: "mb-3",
                "onUpdate:modelValue": _cache[6] || (_cache[6] = (value) => patch("btFallback", value === true))
              }, null, 8, ["model-value"]),
              _cache[15] || (_cache[15] = _createElementVNode$k("div", { class: "text-caption text-medium-emphasis mb-1" }, "命中之后", -1)),
              _createVNode$i(_component_v_btn_toggle, {
                "model-value": props.rule.trigger,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-1",
                "onUpdate:modelValue": _cache[7] || (_cache[7] = (value) => value && patch("trigger", value))
              }, {
                default: _withCtx$i(() => [
                  _createVNode$i(_component_v_btn, { value: "notify" }, {
                    default: _withCtx$i(() => _cache[10] || (_cache[10] = [
                      _createTextVNode$h("仅通知")
                    ])),
                    _: 1
                  }),
                  _createVNode$i(_component_v_btn, { value: "auto" }, {
                    default: _withCtx$i(() => _cache[11] || (_cache[11] = [
                      _createTextVNode$h("自动下载")
                    ])),
                    _: 1
                  })
                ]),
                _: 1
              }, 8, ["model-value"]),
              _cache[16] || (_cache[16] = _createElementVNode$k("p", { class: "text-caption text-medium-emphasis mb-4" }, " 「仅通知」时命中的片进「任务」页等你手动下载。 ", -1)),
              _createVNode$i(_component_v_alert, {
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption"
              }, {
                default: _withCtx$i(() => [
                  _createTextVNode$h(" 搜索范围由左栏「搜索站点」决定：当前 " + _toDisplayString$m(props.siteScopeCount ? `限定 ${props.siteScopeCount} 个站点` : "全部已配置站点") + "。 保存路径 / 下载器 / qB 分类仍在插件存储里沿用现值（本栏暂不提供编辑入口）。 ", 1)
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

const RulePanel = /* @__PURE__ */ _export_sfc(_sfc_main$m, [["__scopeId", "data-v-32a4e634"]]);

const {ref: ref$h} = await importShared('vue');

const NOTICES_SEEN_KEY = "avhnext.settings.noticesSeen";
const seenAt = ref$h(readSeen());
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

const {defineComponent:_defineComponent$l} = await importShared('vue');

const {resolveComponent:_resolveComponent$h,createVNode:_createVNode$h,createTextVNode:_createTextVNode$g,withCtx:_withCtx$h,toDisplayString:_toDisplayString$l,unref:_unref$3,openBlock:_openBlock$l,createBlock:_createBlock$g,createCommentVNode:_createCommentVNode$g,createElementVNode:_createElementVNode$j,renderList:_renderList$b,Fragment:_Fragment$c,createElementBlock:_createElementBlock$k} = await importShared('vue');

const _hoisted_1$k = { class: "avh-counts mb-3" };
const {computed: computed$f,watch: watch$a} = await importShared('vue');
const _sfc_main$l = /* @__PURE__ */ _defineComponent$l({
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
    const total = computed$f(() => props.notices.length);
    const unread = computed$f(
      () => props.notices.filter((item) => String(item.time || "") > seenAt.value).length
    );
    watch$a(
      () => props.notices,
      () => markNoticesSeen(props.notices),
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$h("v-icon");
      const _component_v_card_title = _resolveComponent$h("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$h("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$h("v-card-item");
      const _component_v_chip = _resolveComponent$h("v-chip");
      const _component_v_list_item_title = _resolveComponent$h("v-list-item-title");
      const _component_v_list_item_subtitle = _resolveComponent$h("v-list-item-subtitle");
      const _component_v_list_item = _resolveComponent$h("v-list-item");
      const _component_v_list = _resolveComponent$h("v-list");
      const _component_v_alert = _resolveComponent$h("v-alert");
      const _component_v_card_text = _resolveComponent$h("v-card-text");
      const _component_v_btn = _resolveComponent$h("v-btn");
      const _component_v_spacer = _resolveComponent$h("v-spacer");
      const _component_v_card_actions = _resolveComponent$h("v-card-actions");
      const _component_v_card = _resolveComponent$h("v-card");
      return _openBlock$l(), _createBlock$g(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$h(() => [
          _createVNode$h(_component_v_card_item, null, {
            prepend: _withCtx$h(() => [
              _createVNode$h(_component_v_icon, {
                icon: "mdi-bell",
                color: "primary"
              })
            ]),
            default: _withCtx$h(() => [
              _createVNode$h(_component_v_card_title, null, {
                default: _withCtx$h(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$g("通知")
                ])),
                _: 1
              }),
              _createVNode$h(_component_v_card_subtitle, null, {
                default: _withCtx$h(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$g("渠道沿用 MoviePilot 原生通知 · 本插件不另建渠道")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$h(_component_v_card_text, null, {
            default: _withCtx$h(() => [
              _createElementVNode$j("div", _hoisted_1$k, [
                _createVNode$h(_component_v_chip, {
                  color: "primary",
                  variant: "tonal",
                  size: "small"
                }, {
                  default: _withCtx$h(() => [
                    _createTextVNode$g(" 未读 " + _toDisplayString$l(unread.value) + " / 共 " + _toDisplayString$l(total.value), 1)
                  ]),
                  _: 1
                }),
                _unref$3(seenAt) ? (_openBlock$l(), _createBlock$g(_component_v_chip, {
                  key: 0,
                  variant: "text",
                  size: "small",
                  class: "text-caption"
                }, {
                  default: _withCtx$h(() => [
                    _createTextVNode$g(" 已读到 " + _toDisplayString$l(_unref$3(seenAt)), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode$g("", true)
              ]),
              _cache[5] || (_cache[5] = _createElementVNode$j("p", { class: "text-caption text-medium-emphasis mb-2" }, " 通知由 MoviePilot 原生的通知渠道发出（在「设置 → 通知」里配置），这里看到的只是插件自己的收件箱。 打开本栏即算已读；这里的「未读」与数据台顶栏铃铛上的角标是同一个位点。 ", -1)),
              _ctx.notices.length ? (_openBlock$l(), _createBlock$g(_component_v_list, {
                key: 0,
                density: "compact",
                class: "avh-notices mb-2"
              }, {
                default: _withCtx$h(() => [
                  (_openBlock$l(true), _createElementBlock$k(_Fragment$c, null, _renderList$b(_ctx.notices.slice(0, 20), (item, index) => {
                    return _openBlock$l(), _createBlock$g(_component_v_list_item, { key: index }, {
                      prepend: _withCtx$h(() => [
                        _createVNode$h(_component_v_icon, {
                          icon: item.kind === "ok" ? "mdi-check-circle-outline" : item.kind === "warn" ? "mdi-alert-outline" : "mdi-robot-outline",
                          color: item.kind === "ok" ? "success" : item.kind === "warn" ? "warning" : "primary",
                          size: "small"
                        }, null, 8, ["icon", "color"])
                      ]),
                      default: _withCtx$h(() => [
                        _createVNode$h(_component_v_list_item_title, { class: "text-body-2" }, {
                          default: _withCtx$h(() => [
                            _createTextVNode$g(_toDisplayString$l(item.title || item.body || "（无标题）"), 1)
                          ]),
                          _: 2
                        }, 1024),
                        _createVNode$h(_component_v_list_item_subtitle, { class: "text-caption" }, {
                          default: _withCtx$h(() => [
                            _createTextVNode$g(_toDisplayString$l(item.type || "系统消息") + " · " + _toDisplayString$l(item.time || "—"), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024);
                  }), 128)),
                  _ctx.notices.length > 20 ? (_openBlock$l(), _createBlock$g(_component_v_list_item, { key: 0 }, {
                    default: _withCtx$h(() => [
                      _createVNode$h(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                        default: _withCtx$h(() => [
                          _createTextVNode$g(" 只显示最近 20 条，其余 " + _toDisplayString$l(_ctx.notices.length - 20) + " 条在数据台的铃铛里。 ", 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$g("", true)
                ]),
                _: 1
              })) : (_openBlock$l(), _createBlock$g(_component_v_alert, {
                key: 1,
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-0"
              }, {
                default: _withCtx$h(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$g(" 暂无通知。 ")
                ])),
                _: 1
              }))
            ]),
            _: 1
          }),
          _createVNode$h(_component_v_card_actions, null, {
            default: _withCtx$h(() => [
              _createVNode$h(_component_v_btn, {
                variant: "text",
                "prepend-icon": "mdi-refresh",
                loading: props.loading,
                onClick: _cache[0] || (_cache[0] = ($event) => emit("reload"))
              }, {
                default: _withCtx$h(() => _cache[6] || (_cache[6] = [
                  _createTextVNode$g("刷新")
                ])),
                _: 1
              }, 8, ["loading"]),
              _createVNode$h(_component_v_spacer),
              _createVNode$h(_component_v_btn, {
                color: "error",
                variant: "tonal",
                "prepend-icon": "mdi-bell-off-outline",
                disabled: !total.value,
                loading: props.clearing,
                onClick: _cache[1] || (_cache[1] = ($event) => emit("clear"))
              }, {
                default: _withCtx$h(() => _cache[7] || (_cache[7] = [
                  _createTextVNode$g("清空通知")
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

const NotifyPanel = /* @__PURE__ */ _export_sfc(_sfc_main$l, [["__scopeId", "data-v-fe8afc34"]]);

const {defineComponent:_defineComponent$k} = await importShared('vue');

const {resolveComponent:_resolveComponent$g,createVNode:_createVNode$g,createTextVNode:_createTextVNode$f,withCtx:_withCtx$g,Fragment:_Fragment$b,openBlock:_openBlock$k,createElementBlock:_createElementBlock$j,toDisplayString:_toDisplayString$k,createBlock:_createBlock$f} = await importShared('vue');

const {ref: ref$g} = await importShared('vue');

const _sfc_main$k = /* @__PURE__ */ _defineComponent$k({
  __name: "LibraryPanel",
  props: {
    config: {},
    validation: {}
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const showKey = ref$g(false);
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
      const _component_v_icon = _resolveComponent$g("v-icon");
      const _component_v_card_title = _resolveComponent$g("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$g("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$g("v-card-item");
      const _component_v_alert = _resolveComponent$g("v-alert");
      const _component_v_text_field = _resolveComponent$g("v-text-field");
      const _component_v_card_text = _resolveComponent$g("v-card-text");
      const _component_v_card = _resolveComponent$g("v-card");
      return _openBlock$k(), _createBlock$f(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$g(() => [
          _createVNode$g(_component_v_card_item, null, {
            prepend: _withCtx$g(() => [
              _createVNode$g(_component_v_icon, {
                icon: "mdi-server",
                color: "primary"
              })
            ]),
            default: _withCtx$g(() => [
              _createVNode$g(_component_v_card_title, null, {
                default: _withCtx$g(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$f("媒体库")
                ])),
                _: 1
              }),
              _createVNode$g(_component_v_card_subtitle, null, {
                default: _withCtx$g(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$f("Emby 地址与密钥 · 两栏都空 = 复用 MoviePilot 的媒体服务器")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$g(_component_v_card_text, null, {
            default: _withCtx$g(() => [
              _createVNode$g(_component_v_alert, {
                type: mode() === "half" ? "warning" : mode() === "own" ? "success" : "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-4"
              }, {
                default: _withCtx$g(() => [
                  mode() === "reuse" ? (_openBlock$k(), _createElementBlock$j(_Fragment$b, { key: 0 }, [
                    _createTextVNode$f(" 当前：复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby（两栏留空即是这个状态）。 ")
                  ], 64)) : mode() === "own" ? (_openBlock$k(), _createElementBlock$j(_Fragment$b, { key: 1 }, [
                    _createTextVNode$f(" 当前：使用下面填写的 Emby，不再走 MoviePilot 的媒体服务器配置。 ")
                  ], 64)) : (_openBlock$k(), _createElementBlock$j(_Fragment$b, { key: 2 }, [
                    _createTextVNode$f(_toDisplayString$k(props.validation || "Emby 地址与 API 密钥要一起填，否则会回落到 MoviePilot 的媒体服务器。"), 1)
                  ], 64))
                ]),
                _: 1
              }, 8, ["type"]),
              _createVNode$g(_component_v_text_field, {
                "model-value": props.config.emby_host,
                label: "Emby 地址",
                placeholder: "http://192.0.2.10:8096",
                hint: "可留空；两栏都空时自动复用 MoviePilot 已配置的 Emby",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                class: "mb-4",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("emby_host", value ?? ""))
              }, null, 8, ["model-value"]),
              _createVNode$g(_component_v_text_field, {
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

const LibraryPanel = /* @__PURE__ */ _export_sfc(_sfc_main$k, [["__scopeId", "data-v-d05104fc"]]);

const {defineComponent:_defineComponent$j} = await importShared('vue');

const {resolveComponent:_resolveComponent$f,createVNode:_createVNode$f,createTextVNode:_createTextVNode$e,withCtx:_withCtx$f,createElementVNode:_createElementVNode$i,toDisplayString:_toDisplayString$j,openBlock:_openBlock$j,createBlock:_createBlock$e,createCommentVNode:_createCommentVNode$f,createElementBlock:_createElementBlock$i} = await importShared('vue');

const _hoisted_1$j = { class: "avh-cache" };
const _hoisted_2$j = { class: "text-h6" };
const _hoisted_3$h = { class: "avh-cache-actions" };
const _hoisted_4$e = { class: "text-body-2 font-weight-medium" };
const _hoisted_5$d = { class: "text-body-2" };
const _hoisted_6$b = { class: "text-body-2" };
const _hoisted_7$b = { class: "text-body-2" };
const _hoisted_8$a = { class: "text-caption text-medium-emphasis mt-3 mb-0" };
const _hoisted_9$a = { key: 0 };
const {computed: computed$e} = await importShared('vue');
const DASH$1 = "—";
const _sfc_main$j = /* @__PURE__ */ _defineComponent$j({
  __name: "RuntimePanel",
  props: {
    cacheText: {},
    check: {},
    cleaning: { type: Boolean },
    loading: { type: Boolean }
  },
  emits: ["clean", "refresh"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const cacheLabel = computed$e(() => props.cacheText ? props.cacheText : DASH$1);
    const todayLabel = computed$e(() => {
      const info = props.check;
      if (!info || info.checkedToday === void 0) return DASH$1;
      const limit = info.maxPerDay === void 0 ? DASH$1 : info.maxPerDay;
      return `${info.checkedToday} / ${limit}`;
    });
    const lastCheckLabel = computed$e(() => formatCheckTime(props.check?.lastCheck, "last"));
    const nextCheckLabel = computed$e(() => formatCheckTime(props.check?.nextAt, "next"));
    const intervalLabel = computed$e(() => {
      const minutes = props.check?.minIntervalMin;
      return minutes === void 0 ? DASH$1 : `${minutes} 分钟`;
    });
    const checkMissing = computed$e(() => props.check === null);
    const blockedLabel = computed$e(() => {
      const info = props.check;
      if (!info) return "";
      if (info.allowed === false) return info.reason || "当前不可执行检查（受限流约束）";
      return "";
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$f("v-icon");
      const _component_v_card_title = _resolveComponent$f("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$f("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$f("v-card-item");
      const _component_v_btn = _resolveComponent$f("v-btn");
      const _component_v_divider = _resolveComponent$f("v-divider");
      const _component_v_list_item_title = _resolveComponent$f("v-list-item-title");
      const _component_v_list_item = _resolveComponent$f("v-list-item");
      const _component_v_list = _resolveComponent$f("v-list");
      const _component_v_alert = _resolveComponent$f("v-alert");
      const _component_v_card_text = _resolveComponent$f("v-card-text");
      const _component_v_card = _resolveComponent$f("v-card");
      return _openBlock$j(), _createBlock$e(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$f(() => [
          _createVNode$f(_component_v_card_item, null, {
            prepend: _withCtx$f(() => [
              _createVNode$f(_component_v_icon, {
                icon: "mdi-database-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$f(() => [
              _createVNode$f(_component_v_card_title, null, {
                default: _withCtx$f(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$e("运行与缓存")
                ])),
                _: 1
              }),
              _createVNode$f(_component_v_card_subtitle, null, {
                default: _withCtx$f(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$e("缓存占用与清理 · 限流参数只读")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$f(_component_v_card_text, null, {
            default: _withCtx$f(() => [
              _createElementVNode$i("div", _hoisted_1$j, [
                _createElementVNode$i("div", null, [
                  _cache[4] || (_cache[4] = _createElementVNode$i("div", { class: "text-caption text-medium-emphasis" }, "缓存占用", -1)),
                  _createElementVNode$i("div", _hoisted_2$j, _toDisplayString$j(cacheLabel.value), 1)
                ]),
                _createElementVNode$i("div", _hoisted_3$h, [
                  _createVNode$f(_component_v_btn, {
                    color: "warning",
                    variant: "tonal",
                    "prepend-icon": "mdi-broom",
                    loading: props.cleaning,
                    onClick: _cache[0] || (_cache[0] = ($event) => emit("clean"))
                  }, {
                    default: _withCtx$f(() => _cache[5] || (_cache[5] = [
                      _createTextVNode$e("清理缓存")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode$f(_component_v_btn, {
                    variant: "text",
                    "prepend-icon": "mdi-refresh",
                    loading: props.loading,
                    class: "mt-2",
                    onClick: _cache[1] || (_cache[1] = ($event) => emit("refresh"))
                  }, {
                    default: _withCtx$f(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$e("刷新")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              _createVNode$f(_component_v_divider, { class: "my-4" }),
              _cache[13] || (_cache[13] = _createElementVNode$i("div", { class: "text-subtitle-2 mb-2" }, "订阅检查限流（只读）", -1)),
              _createVNode$f(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$f(() => [
                  _createVNode$f(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$f(() => [
                      _createElementVNode$i("span", _hoisted_4$e, _toDisplayString$j(todayLabel.value), 1)
                    ]),
                    default: _withCtx$f(() => [
                      _createVNode$f(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$f(() => _cache[7] || (_cache[7] = [
                          _createTextVNode$e("今天已检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$f(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$f(() => [
                      _createElementVNode$i("span", _hoisted_5$d, _toDisplayString$j(lastCheckLabel.value), 1)
                    ]),
                    default: _withCtx$f(() => [
                      _createVNode$f(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$f(() => _cache[8] || (_cache[8] = [
                          _createTextVNode$e("上次检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$f(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$f(() => [
                      _createElementVNode$i("span", _hoisted_6$b, _toDisplayString$j(nextCheckLabel.value), 1)
                    ]),
                    default: _withCtx$f(() => [
                      _createVNode$f(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$f(() => _cache[9] || (_cache[9] = [
                          _createTextVNode$e("下次可检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$f(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$f(() => [
                      _createElementVNode$i("span", _hoisted_7$b, _toDisplayString$j(intervalLabel.value), 1)
                    ]),
                    default: _withCtx$f(() => [
                      _createVNode$f(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$f(() => _cache[10] || (_cache[10] = [
                          _createTextVNode$e("间隔下限")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              blockedLabel.value ? (_openBlock$j(), _createBlock$e(_component_v_alert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mt-2"
              }, {
                default: _withCtx$f(() => [
                  _createTextVNode$e(_toDisplayString$j(blockedLabel.value), 1)
                ]),
                _: 1
              })) : _createCommentVNode$f("", true),
              _createElementVNode$i("p", _hoisted_8$a, [
                _cache[12] || (_cache[12] = _createTextVNode$e(" 限流参数按用户明确要求固定（每天 ≤6 次、间隔 ≥240 分钟），界面不提供放宽入口。 ")),
                checkMissing.value ? (_openBlock$j(), _createElementBlock$i("span", _hoisted_9$a, _cache[11] || (_cache[11] = [
                  _createTextVNode$e(" 当前后端还没返回 "),
                  _createElementVNode$i("code", null, "check", -1),
                  _createTextVNode$e(" 字段（本轮正在补），所以上面几行显示 "),
                  _createElementVNode$i("code", null, "—", -1),
                  _createTextVNode$e("；字段上线后自动显示。 ")
                ]))) : _createCommentVNode$f("", true)
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

const RuntimePanel = /* @__PURE__ */ _export_sfc(_sfc_main$j, [["__scopeId", "data-v-cd2af22c"]]);

const {defineComponent:_defineComponent$i} = await importShared('vue');

const {resolveComponent:_resolveComponent$e,createVNode:_createVNode$e,createTextVNode:_createTextVNode$d,withCtx:_withCtx$e,toDisplayString:_toDisplayString$i,createElementVNode:_createElementVNode$h,openBlock:_openBlock$i,createBlock:_createBlock$d,createCommentVNode:_createCommentVNode$e} = await importShared('vue');

const _hoisted_1$i = { class: "text-body-2 font-weight-medium" };
const _hoisted_2$i = { class: "text-body-2 font-weight-medium" };
const _hoisted_3$g = { class: "text-body-2" };
const DASH = "—";
const DATA_ROOT = "/avhelper/cache";
const JAVDB_BIN = "/avhelper/bin/javdb";
const _sfc_main$i = /* @__PURE__ */ _defineComponent$i({
  __name: "AboutPanel",
  props: {
    version: {},
    pluginId: {},
    sourcePluginId: {}
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$e("v-icon");
      const _component_v_card_title = _resolveComponent$e("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$e("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$e("v-card-item");
      const _component_v_list_item_title = _resolveComponent$e("v-list-item-title");
      const _component_v_list_item = _resolveComponent$e("v-list-item");
      const _component_v_list = _resolveComponent$e("v-list");
      const _component_v_divider = _resolveComponent$e("v-divider");
      const _component_v_card_text = _resolveComponent$e("v-card-text");
      const _component_v_card = _resolveComponent$e("v-card");
      return _openBlock$i(), _createBlock$d(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$e(() => [
          _createVNode$e(_component_v_card_item, null, {
            prepend: _withCtx$e(() => [
              _createVNode$e(_component_v_icon, {
                icon: "mdi-information-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$e(() => [
              _createVNode$e(_component_v_card_title, null, {
                default: _withCtx$e(() => _cache[0] || (_cache[0] = [
                  _createTextVNode$d("关于")
                ])),
                _: 1
              }),
              _createVNode$e(_component_v_card_subtitle, null, {
                default: _withCtx$e(() => _cache[1] || (_cache[1] = [
                  _createTextVNode$d("AVHelper · Vue 联邦渲染模式")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$e(_component_v_card_text, null, {
            default: _withCtx$e(() => [
              _createVNode$e(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$e(() => [
                  _createVNode$e(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$e(() => [
                      _createElementVNode$h("span", _hoisted_1$i, _toDisplayString$i(props.version || DASH), 1)
                    ]),
                    default: _withCtx$e(() => [
                      _createVNode$e(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$e(() => _cache[2] || (_cache[2] = [
                          _createTextVNode$d("版本号")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$e(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$e(() => [
                      _createElementVNode$h("span", _hoisted_2$i, _toDisplayString$i(props.pluginId || DASH), 1)
                    ]),
                    default: _withCtx$e(() => [
                      _createVNode$e(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$e(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$d("插件 ID")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  props.sourcePluginId ? (_openBlock$i(), _createBlock$d(_component_v_list_item, {
                    key: 0,
                    class: "px-0"
                  }, {
                    append: _withCtx$e(() => [
                      _createElementVNode$h("span", _hoisted_3$g, _toDisplayString$i(props.sourcePluginId), 1)
                    ]),
                    default: _withCtx$e(() => [
                      _createVNode$e(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$e(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$d("源插件 ID（分身）")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$e("", true),
                  _createVNode$e(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$e(() => [
                      _createElementVNode$h("span", { class: "text-body-2" }, [
                        _createElementVNode$h("code", null, _toDisplayString$i(DATA_ROOT))
                      ])
                    ]),
                    default: _withCtx$e(() => [
                      _createVNode$e(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$e(() => _cache[5] || (_cache[5] = [
                          _createTextVNode$d("数据根")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$e(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$e(() => [
                      _createElementVNode$h("span", { class: "text-body-2" }, [
                        _createElementVNode$h("code", null, _toDisplayString$i(JAVDB_BIN)),
                        _cache[7] || (_cache[7] = _createTextVNode$d("（与原版共用，只读）"))
                      ])
                    ]),
                    default: _withCtx$e(() => [
                      _createVNode$e(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$e(() => _cache[6] || (_cache[6] = [
                          _createTextVNode$d("javdb 二进制")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$e(_component_v_divider, { class: "my-3" }),
              _createElementVNode$h("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _cache[8] || (_cache[8] = _createTextVNode$d(" 数据根在插件数据卷上：SQLite 落在 ")),
                _createElementVNode$h("code", null, _toDisplayString$i(DATA_ROOT) + "/meta/avhelper.db"),
                _cache[9] || (_cache[9] = _createTextVNode$d("，图片与 JSON 缓存同根。 SQLite、图片与 JSON 缓存同根，全在插件数据卷上。 "))
              ]),
              _cache[10] || (_cache[10] = _createElementVNode$h("p", { class: "text-caption text-medium-emphasis mb-0" }, [
                _createTextVNode$d(" 界面上方是宿主的统一弹窗：标题栏、关闭按钮与 Toast 都由宿主提供，本插件复用 "),
                _createElementVNode$h("code", null, "moviepilot:toast"),
                _createTextVNode$d(" / "),
                _createElementVNode$h("code", null, "moviepilot:confirm"),
                _createTextVNode$d("，不自建。 版本号来自 "),
                _createElementVNode$h("code", null, "plugin/page/<id>"),
                _createTextVNode$d(" 的 "),
                _createElementVNode$h("code", null, "plugin_version"),
                _createTextVNode$d("，取不到显示 "),
                _createElementVNode$h("code", null, "—"),
                _createTextVNode$d("。 ")
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

const AboutPanel = /* @__PURE__ */ _export_sfc(_sfc_main$i, [["__scopeId", "data-v-02ead8f0"]]);

const {defineComponent:_defineComponent$h} = await importShared('vue');

const {openBlock:_openBlock$h,createElementBlock:_createElementBlock$h,toDisplayString:_toDisplayString$h,normalizeClass:_normalizeClass$8} = await importShared('vue');

const _hoisted_1$h = ["src", "alt", "loading"];
const _hoisted_2$h = {
  key: 1,
  class: "avh-thumb__noimg"
};
const {computed: computed$d,ref: ref$f,watch: watch$9} = await importShared('vue');

const PROXY_MARK = "/img?url=";
const _sfc_main$h = /* @__PURE__ */ _defineComponent$h({
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
    const useProxy = ref$f(false);
    const failed = ref$f(false);
    watch$9(
      () => props.src,
      () => {
        useProxy.value = false;
        failed.value = false;
      }
    );
    const proxySrc = computed$d(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (raw.includes(PROXY_MARK)) return raw;
      if (!props.pluginId) return "";
      return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`;
    });
    const currentSrc = computed$d(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (!useProxy.value) return raw;
      return proxySrc.value;
    });
    const showPlaceholder = computed$d(
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
      return _openBlock$h(), _createElementBlock$h("div", {
        class: _normalizeClass$8(["avh-thumb", `avh-thumb--${_ctx.variant}`])
      }, [
        !showPlaceholder.value ? (_openBlock$h(), _createElementBlock$h("img", {
          key: 0,
          src: currentSrc.value,
          alt: _ctx.alt,
          referrerpolicy: "no-referrer",
          loading: _ctx.lazy ? "lazy" : "eager",
          decoding: "async",
          onError
        }, null, 40, _hoisted_1$h)) : (_openBlock$h(), _createElementBlock$h("div", _hoisted_2$h, _toDisplayString$h(_ctx.alt || "无图"), 1))
      ], 2);
    };
  }
});

const Thumb = /* @__PURE__ */ _export_sfc(_sfc_main$h, [["__scopeId", "data-v-983b098d"]]);

const {ref: ref$e} = await importShared('vue');

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
const filledThumbs = ref$e({});
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

const {defineComponent:_defineComponent$g} = await importShared('vue');

const {createVNode:_createVNode$d,toDisplayString:_toDisplayString$g,createElementVNode:_createElementVNode$g,openBlock:_openBlock$g,createElementBlock:_createElementBlock$g,createCommentVNode:_createCommentVNode$d,createTextVNode:_createTextVNode$c,resolveComponent:_resolveComponent$d,withCtx:_withCtx$d,createBlock:_createBlock$c,renderList:_renderList$a,Fragment:_Fragment$a,normalizeClass:_normalizeClass$7,unref:_unref$2} = await importShared('vue');

const _hoisted_1$g = { class: "avh-cand" };
const _hoisted_2$g = { class: "avh-cand__head" };
const _hoisted_3$f = { class: "avh-cand__no" };
const _hoisted_4$d = { class: "avh-cand__hint avh-cand__origin" };
const _hoisted_5$c = {
  key: 0,
  class: "avh-cand__hint"
};
const _hoisted_6$a = { class: "avh-cand__table" };
const _hoisted_7$a = { key: 0 };
const _hoisted_8$9 = {
  key: 0,
  class: "avh-tag"
};
const _hoisted_9$9 = { class: "avh-cand__marks" };
const _hoisted_10$9 = {
  key: 1,
  class: "avh-cand__hint"
};
const _hoisted_11$8 = ["title"];
const _hoisted_12$8 = ["title"];
const _hoisted_13$7 = { class: "avh-cand__act" };
const _hoisted_14$7 = { colspan: "7" };
const _hoisted_15$6 = ["title"];
const _hoisted_16$4 = { key: 0 };
const {computed: computed$c,ref: ref$d} = await importShared('vue');
const _sfc_main$g = /* @__PURE__ */ _defineComponent$g({
  __name: "CandTable",
  props: {
    task: {},
    pluginId: { default: "" },
    cancelable: { type: Boolean, default: false }
  },
  emits: ["download", "cancel"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const pending = ref$d({});
    const cands = computed$c(() => Array.isArray(props.task.cands) ? props.task.cands : []);
    const passedCount = computed$c(() => cands.value.filter((item) => item.pass !== false).length);
    const taskId = computed$c(() => String(props.task.id ?? ""));
    const rows = computed$c(() => {
      const pt = cands.value.filter((item) => item.src !== "BT");
      const bt = cands.value.filter((item) => item.src === "BT");
      const out = pt.map((cand, index) => ({ kind: "cand", key: `pt-${index}`, cand }));
      if (bt.length) {
        out.push({ kind: "btnote", key: "bt-note", cand: {} });
        bt.forEach((cand, index) => out.push({ kind: "cand", key: `bt-${index}`, cand }));
      }
      return out;
    });
    const origin = computed$c(() => {
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
        titleOf(cand) ? "has-sub" : ""
      ].filter(Boolean);
    }
    function titleOf(cand) {
      return String(cand.title || "").trim();
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
    function onDownload(cand) {
      const key = siteKey(cand);
      if (pending.value[key]) return;
      pending.value = { ...pending.value, [key]: true };
      emit("download", { taskId: taskId.value, site: String(cand.site || ""), force: !isPass(cand) });
    }
    const canceling = ref$d(false);
    function onCancel() {
      if (canceling.value || !taskId.value) return;
      canceling.value = true;
      emit("cancel", { taskId: taskId.value });
    }
    function clearCanceling() {
      canceling.value = false;
    }
    function clearPending(site) {
      const next = { ...pending.value };
      if (site === void 0) {
        Object.keys(next).forEach((key) => delete next[key]);
      } else {
        Object.keys(next).forEach((key) => {
          if (key === `${taskId.value}|${site}`) delete next[key];
        });
      }
      pending.value = next;
    }
    __expose({ clearPending, clearCanceling });
    const poster = computed$c(() => {
      const own = String(props.task?.thumb || "");
      if (own) return own;
      return String(filledThumbs.value[String(props.task?.number || "")] || "");
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$d("v-btn");
      return _openBlock$g(), _createElementBlock$g("div", _hoisted_1$g, [
        _createElementVNode$g("div", _hoisted_2$g, [
          _createVNode$d(Thumb, {
            class: "avh-cand__poster",
            variant: "tposter",
            src: poster.value,
            alt: "无图",
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "plugin-id"]),
          _createElementVNode$g("div", null, [
            _createElementVNode$g("div", _hoisted_3$f, _toDisplayString$g(_ctx.task.number || ""), 1),
            _createElementVNode$g("div", _hoisted_4$d, _toDisplayString$g(origin.value) + " · 搜到 " + _toDisplayString$g(cands.value.length) + " · 合格 " + _toDisplayString$g(passedCount.value), 1)
          ]),
          _cache[1] || (_cache[1] = _createElementVNode$g("div", { class: "avh-cand__spacer" }, null, -1)),
          _ctx.task.auto && _ctx.task.source === "sub" ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_5$c, " 订阅为自动下载，但无候选合格 ")) : _createCommentVNode$d("", true),
          _ctx.cancelable ? (_openBlock$g(), _createBlock$c(_component_v_btn, {
            key: 1,
            class: "avh-cand__cancel",
            variant: "outlined",
            size: "small",
            color: "error",
            loading: canceling.value,
            title: "不再等这部片：从待确认里移除（想找回就重新搜一次）",
            onClick: onCancel
          }, {
            default: _withCtx$d(() => _cache[0] || (_cache[0] = [
              _createTextVNode$c("取消任务")
            ])),
            _: 1
          }, 8, ["loading"])) : _createCommentVNode$d("", true)
        ]),
        _createElementVNode$g("table", _hoisted_6$a, [
          _cache[6] || (_cache[6] = _createElementVNode$g("colgroup", null, [
            _createElementVNode$g("col", { class: "avh-cand__col-site" }),
            _createElementVNode$g("col", { class: "avh-cand__col-mark" }),
            _createElementVNode$g("col", { class: "avh-cand__col-spec" }),
            _createElementVNode$g("col", { class: "avh-cand__col-size" }),
            _createElementVNode$g("col", { class: "avh-cand__col-seed" }),
            _createElementVNode$g("col", { class: "avh-cand__col-score" }),
            _createElementVNode$g("col", { class: "avh-cand__col-act" })
          ], -1)),
          _cache[7] || (_cache[7] = _createElementVNode$g("thead", null, [
            _createElementVNode$g("tr", null, [
              _createElementVNode$g("th", null, "站点"),
              _createElementVNode$g("th", null, "标记"),
              _createElementVNode$g("th", null, "规格"),
              _createElementVNode$g("th", null, "大小"),
              _createElementVNode$g("th", null, "做种"),
              _createElementVNode$g("th", null, "匹配分"),
              _createElementVNode$g("th", { class: "avh-cand__act" }, "操作")
            ])
          ], -1)),
          _createElementVNode$g("tbody", null, [
            (_openBlock$g(true), _createElementBlock$g(_Fragment$a, null, _renderList$a(rows.value, (row) => {
              return _openBlock$g(), _createElementBlock$g(_Fragment$a, {
                key: row.key
              }, [
                row.kind === "btnote" ? (_openBlock$g(), _createElementBlock$g("tr", _hoisted_7$a, _cache[2] || (_cache[2] = [
                  _createElementVNode$g("td", {
                    colspan: "7",
                    class: "avh-cand__hint avh-cand__btnote"
                  }, " — PT 没有合格候选，以下为 BT 磁力兜底 — ", -1)
                ]))) : (_openBlock$g(), _createElementBlock$g(_Fragment$a, { key: 1 }, [
                  _createElementVNode$g("tr", {
                    class: _normalizeClass$7(rowClass(row.cand))
                  }, [
                    _createElementVNode$g("td", null, [
                      row.cand.src === "BT" ? (_openBlock$g(), _createElementBlock$g("span", _hoisted_8$9, "BT")) : _createCommentVNode$d("", true),
                      _createTextVNode$c(" " + _toDisplayString$g(row.cand.site || ""), 1)
                    ]),
                    _createElementVNode$g("td", _hoisted_9$9, [
                      marks(row.cand).length ? (_openBlock$g(true), _createElementBlock$g(_Fragment$a, { key: 0 }, _renderList$a(marks(row.cand), (mark) => {
                        return _openBlock$g(), _createElementBlock$g("span", {
                          key: mark.text,
                          class: _normalizeClass$7(["avh-tag", mark.cls])
                        }, _toDisplayString$g(mark.text), 3);
                      }), 128)) : (_openBlock$g(), _createElementBlock$g("span", _hoisted_10$9, "—"))
                    ]),
                    _createElementVNode$g("td", {
                      class: "avh-cand__spec",
                      title: row.cand.spec || ""
                    }, _toDisplayString$g(row.cand.spec || ""), 9, _hoisted_11$8),
                    _createElementVNode$g("td", null, _toDisplayString$g(row.cand.size || ""), 1),
                    _createElementVNode$g("td", null, _toDisplayString$g(seedersText(row.cand)), 1),
                    _createElementVNode$g("td", {
                      title: row.cand.breakdown || ""
                    }, [
                      _createElementVNode$g("span", {
                        class: _normalizeClass$7(["avh-score", `avh-score--${_unref$2(scoreLevel)(row.cand.score, isPass(row.cand))}`])
                      }, _toDisplayString$g(scoreText(row.cand)), 3)
                    ], 8, _hoisted_12$8),
                    _createElementVNode$g("td", _hoisted_13$7, [
                      isPass(row.cand) ? (_openBlock$g(), _createBlock$c(_component_v_btn, {
                        key: 0,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$d(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$c("下载")
                        ])),
                        _: 2
                      }, 1032, ["loading", "onClick"])) : (_openBlock$g(), _createBlock$c(_component_v_btn, {
                        key: 1,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        title: row.cand.breakdown || "",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$d(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$c("仍要下载")
                        ])),
                        _: 2
                      }, 1032, ["title", "loading", "onClick"]))
                    ])
                  ], 2),
                  titleOf(row.cand) ? (_openBlock$g(), _createElementBlock$g("tr", {
                    key: 0,
                    class: _normalizeClass$7(["avh-cand__sub", ...rowClass(row.cand)])
                  }, [
                    _createElementVNode$g("td", _hoisted_14$7, [
                      _createElementVNode$g("div", {
                        class: "avh-cand__ttl",
                        title: titleOf(row.cand)
                      }, _toDisplayString$g(titleOf(row.cand)), 9, _hoisted_15$6)
                    ])
                  ], 2)) : _createCommentVNode$d("", true)
                ], 64))
              ], 64);
            }), 128)),
            !cands.value.length ? (_openBlock$g(), _createElementBlock$g("tr", _hoisted_16$4, _cache[5] || (_cache[5] = [
              _createElementVNode$g("td", {
                colspan: "7",
                class: "avh-cand__hint avh-cand__empty"
              }, "没有搜到任何候选", -1)
            ]))) : _createCommentVNode$d("", true)
          ])
        ])
      ]);
    };
  }
});

const CandTable = /* @__PURE__ */ _export_sfc(_sfc_main$g, [["__scopeId", "data-v-4c3555d9"]]);

const {defineComponent:_defineComponent$f} = await importShared('vue');

const {createElementVNode:_createElementVNode$f,toDisplayString:_toDisplayString$f,openBlock:_openBlock$f,createElementBlock:_createElementBlock$f,createCommentVNode:_createCommentVNode$c,renderSlot:_renderSlot} = await importShared('vue');

const _hoisted_1$f = { class: "avh-empty" };
const _hoisted_2$f = ["innerHTML"];
const _hoisted_3$e = {
  key: 0,
  class: "avh-empty__hint"
};
const _hoisted_4$c = {
  key: 1,
  class: "avh-empty__slot"
};
const _sfc_main$f = /* @__PURE__ */ _defineComponent$f({
  __name: "EmptyState",
  props: {
    text: { default: "" },
    hint: { default: "" }
  },
  setup(__props) {
    return (_ctx, _cache) => {
      return _openBlock$f(), _createElementBlock$f("div", _hoisted_1$f, [
        _createElementVNode$f("div", {
          class: "avh-empty__text",
          innerHTML: _ctx.text
        }, null, 8, _hoisted_2$f),
        _ctx.hint ? (_openBlock$f(), _createElementBlock$f("div", _hoisted_3$e, _toDisplayString$f(_ctx.hint), 1)) : _createCommentVNode$c("", true),
        _ctx.$slots.default ? (_openBlock$f(), _createElementBlock$f("div", _hoisted_4$c, [
          _renderSlot(_ctx.$slots, "default", {}, void 0, true)
        ])) : _createCommentVNode$c("", true)
      ]);
    };
  }
});

const EmptyState = /* @__PURE__ */ _export_sfc(_sfc_main$f, [["__scopeId", "data-v-d928276a"]]);

const {defineComponent:_defineComponent$e} = await importShared('vue');

const {toDisplayString:_toDisplayString$e,createElementVNode:_createElementVNode$e,createTextVNode:_createTextVNode$b,resolveComponent:_resolveComponent$c,withCtx:_withCtx$c,createVNode:_createVNode$c,openBlock:_openBlock$e,createElementBlock:_createElementBlock$e,createCommentVNode:_createCommentVNode$b} = await importShared('vue');

const _hoisted_1$e = {
  class: "avh-errbox",
  role: "alert"
};
const _hoisted_2$e = { class: "avh-errbox__msg" };
const _hoisted_3$d = {
  key: 0,
  class: "avh-errbox__act"
};
const _sfc_main$e = /* @__PURE__ */ _defineComponent$e({
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
      const _component_v_btn = _resolveComponent$c("v-btn");
      return _openBlock$e(), _createElementBlock$e("div", _hoisted_1$e, [
        _createElementVNode$e("div", _hoisted_2$e, "⚠️ " + _toDisplayString$e(_ctx.message || "抓取失败，请稍后重试"), 1),
        _ctx.retryable ? (_openBlock$e(), _createElementBlock$e("div", _hoisted_3$d, [
          _createVNode$c(_component_v_btn, {
            color: "primary",
            variant: "flat",
            size: "small",
            loading: _ctx.retrying,
            onClick: _cache[0] || (_cache[0] = ($event) => emit("retry"))
          }, {
            default: _withCtx$c(() => [
              _createTextVNode$b(_toDisplayString$e(_ctx.retryText), 1)
            ]),
            _: 1
          }, 8, ["loading"])
        ])) : _createCommentVNode$b("", true)
      ]);
    };
  }
});

const ErrorState = /* @__PURE__ */ _export_sfc(_sfc_main$e, [["__scopeId", "data-v-8f8a571b"]]);

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

const RULE_FALLBACK = {
  res: "1080p",
  mustCnsub: false,
  preferUncensored: true,
  allow4k: true,
  minSeeders: 3,
  sites: [],
  prefSites: ["馒头", "Rousi"],
  btFallback: true,
  savePath: "/media/9kg/avi",
  category: "avi",
  downloader: "qb",
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

const {defineComponent:_defineComponent$d} = await importShared('vue');

const {resolveComponent:_resolveComponent$b,withKeys:_withKeys$2,createVNode:_createVNode$b,toDisplayString:_toDisplayString$d,createTextVNode:_createTextVNode$a,withCtx:_withCtx$b,createElementVNode:_createElementVNode$d,openBlock:_openBlock$d,createBlock:_createBlock$b,createElementBlock:_createElementBlock$d} = await importShared('vue');

const _hoisted_1$d = { class: "avh-sitesearch" };
const _hoisted_2$d = { class: "avh-sitesearch__toolbar" };
const _hoisted_3$c = { class: "avh-sitesearch__hint" };
const _hoisted_4$b = { class: "avh-sitesearch__range" };
const _hoisted_5$b = ["title"];
const {computed: computed$b,nextTick: nextTick$3,ref: ref$c,watch: watch$8} = await importShared('vue');
const _sfc_main$d = /* @__PURE__ */ _defineComponent$d({
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
    const candTableRef = ref$c(null);
    const keyword = ref$c("");
    const searching = ref$c(false);
    const searchedAt = ref$c("");
    const task = ref$c(null);
    const errorText = ref$c("");
    const retrying = ref$c(false);
    const siteNames = computed$b(
      () => props.store.sites.value.map((item) => String(item?.name || "")).filter(Boolean)
    );
    const picked = computed$b(() => {
      const names = siteNames.value;
      return (props.store.rule.value.sites || []).map(String).filter((name) => names.indexOf(name) >= 0);
    });
    function labelOf(name) {
      const hit = props.store.sites.value.filter((item) => item.name === name)[0];
      return String(hit?.adapterLabel || "");
    }
    const scopeText = computed$b(() => {
      if (!picked.value.length) return "全部站点";
      return picked.value.map((name) => {
        const label = labelOf(name);
        return label ? `${name}（${label}）` : name;
      }).join("、");
    });
    const cands = computed$b(() => Array.isArray(task.value?.cands) ? task.value?.cands || [] : []);
    const hasResult = computed$b(() => !!task.value && cands.value.length > 0);
    const searchLabel = computed$b(() => searching.value ? "搜索中…" : "搜索站点");
    watch$8(task, async () => {
      candTableRef.value?.clearPending();
      await nextTick$3();
      candTableRef.value?.clearPending();
    });
    function clearPending() {
      candTableRef.value?.clearPending();
      void nextTick$3(() => candTableRef.value?.clearPending());
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
      if (!res.ok) {
        t.warning(res.message || "下载失败，请稍后重试");
      } else {
        t.success("已提交下载");
        t.info(`${payload.site} · 进度见「下载」页`);
        void props.store.refreshTasks(false);
      }
      clearPending();
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
      const _component_v_text_field = _resolveComponent$b("v-text-field");
      const _component_v_btn = _resolveComponent$b("v-btn");
      return _openBlock$d(), _createElementBlock$d("div", _hoisted_1$d, [
        _createElementVNode$d("div", _hoisted_2$d, [
          _createVNode$b(_component_v_text_field, {
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
          _createVNode$b(_component_v_btn, {
            color: "primary",
            variant: "flat",
            loading: searching.value,
            disabled: searching.value,
            "prepend-icon": "mdi-magnify",
            onClick: doSearch
          }, {
            default: _withCtx$b(() => [
              _createTextVNode$a(_toDisplayString$d(searchLabel.value), 1)
            ]),
            _: 1
          }, 8, ["loading", "disabled"]),
          _cache[1] || (_cache[1] = _createElementVNode$d("div", { class: "avh-sitesearch__spacer" }, null, -1)),
          _createElementVNode$d("span", _hoisted_3$c, _toDisplayString$d(searchedAt.value ? `上次搜索 ${searchedAt.value}` : "命中即停 · 站点间隔 3-8 秒"), 1)
        ]),
        _createElementVNode$d("div", _hoisted_4$b, [
          _cache[3] || (_cache[3] = _createElementVNode$d("div", { class: "avh-sitesearch__label" }, "搜索范围", -1)),
          _createElementVNode$d("div", {
            class: "avh-sitesearch__scope",
            title: scopeText.value,
            onClick: onScopeClick
          }, _toDisplayString$d(scopeText.value), 9, _hoisted_5$b),
          _createVNode$b(_component_v_btn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-tune",
            onClick: changeScope
          }, {
            default: _withCtx$b(() => _cache[2] || (_cache[2] = [
              _createTextVNode$a("改范围")
            ])),
            _: 1
          })
        ]),
        errorText.value ? (_openBlock$d(), _createBlock$b(ErrorState, {
          key: 0,
          message: `站点搜索失败：${errorText.value}`,
          retrying: retrying.value,
          onRetry: retry
        }, null, 8, ["message", "retrying"])) : hasResult.value && task.value ? (_openBlock$d(), _createBlock$b(CandTable, {
          key: 1,
          ref_key: "candTableRef",
          ref: candTableRef,
          task: task.value,
          "plugin-id": _ctx.pluginId,
          onDownload
        }, null, 8, ["task", "plugin-id"])) : (_openBlock$d(), _createBlock$b(EmptyState, {
          key: 2,
          text: "输入番号或关键词后点「搜索站点」"
        }))
      ]);
    };
  }
});

const SiteSearchView = /* @__PURE__ */ _export_sfc(_sfc_main$d, [["__scopeId", "data-v-bf4e56fe"]]);

const {defineComponent:_defineComponent$c} = await importShared('vue');

const {createElementVNode:_createElementVNode$c,createTextVNode:_createTextVNode$9,resolveComponent:_resolveComponent$a,withCtx:_withCtx$a,createVNode:_createVNode$a,toDisplayString:_toDisplayString$c,renderList:_renderList$9,Fragment:_Fragment$9,openBlock:_openBlock$c,createElementBlock:_createElementBlock$c,normalizeStyle:_normalizeStyle$2,createCommentVNode:_createCommentVNode$a,createBlock:_createBlock$a} = await importShared('vue');

const _hoisted_1$c = { class: "avh-downloads" };
const _hoisted_2$c = { class: "avh-downloads__toolbar" };
const _hoisted_3$b = { class: "avh-downloads__secttl" };
const _hoisted_4$a = { class: "avh-q__hd" };
const _hoisted_5$a = { class: "avh-q__main" };
const _hoisted_6$9 = { class: "avh-q__no" };
const _hoisted_7$9 = { class: "avh-q__hint avh-q__meta" };
const _hoisted_8$8 = { class: "avh-q__hint avh-q__path" };
const _hoisted_9$8 = { class: "avh-q__right" };
const _hoisted_10$8 = { class: "avh-q__no" };
const _hoisted_11$7 = { class: "avh-bar" };
const _hoisted_12$7 = {
  key: 1,
  class: "avh-downloads__hint"
};
const _hoisted_13$6 = { class: "avh-downloads__secttl" };
const _hoisted_14$6 = { class: "avh-q__hd" };
const _hoisted_15$5 = { class: "avh-q__main" };
const _hoisted_16$3 = { class: "avh-q__no" };
const _hoisted_17$3 = {
  key: 0,
  class: "avh-q__ttl"
};
const _hoisted_18$3 = { class: "avh-q__hint avh-q__meta" };
const _hoisted_19$3 = {
  key: 3,
  class: "avh-downloads__hint"
};
const {computed: computed$a,onBeforeUnmount: onBeforeUnmount$5,onMounted: onMounted$6,watch: watch$7} = await importShared('vue');
const POLL_MS$1 = 5e3;
const _sfc_main$c = /* @__PURE__ */ _defineComponent$c({
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
    const rows = computed$a(
      () => Array.isArray(props.store.queue.value) ? props.store.queue.value : []
    );
    function isDone(item) {
      return item.state === "done";
    }
    const activeRows = computed$a(() => rows.value.filter((item) => !isDone(item)));
    const doneRows = computed$a(() => rows.value.filter((item) => isDone(item)));
    function progressOf(item) {
      return Math.max(0, Math.min(100, Number(item.progress) || 0));
    }
    function metaOf(item) {
      return [item.site, item.spec, item.size].filter(Boolean).join(" · ") || "—";
    }
    function pathOf(item) {
      return String(item.savePath || "") + (item.added ? ` · ${item.added}` : "");
    }
    function doneInfoOf(item) {
      const completed = String(item.completedAt || "");
      const added = String(item.added || "");
      const when = completed ? `完成 ${completed}` : added ? `加入 ${added}` : "";
      const lib = "lib" in item ? item.lib ? "在库" : "不在库" : "";
      return [item.size, when, lib].filter(Boolean).join(" · ") || "—";
    }
    function rowKey(item, index) {
      return String(item.hash || item.id || `${item.number || ""}#${index}`);
    }
    function thumbOf(item) {
      return String(item.thumb || filledThumbs.value[String(item.number || "")] || "");
    }
    async function refreshQueue() {
      const inflight = props.store.refreshTasks(false);
      t.info("正在刷新进度…");
      if (!await inflight) {
        t.warning(`任务读取失败：${props.store.error.value || "请稍后重试"}`);
      }
    }
    watch$7(
      rows,
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
      }, POLL_MS$1);
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
      if (document.visibilityState === "visible") startPolling();
      document.addEventListener("visibilitychange", onVisibilityChange);
    });
    onBeforeUnmount$5(() => {
      stopPolling();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$a("v-btn");
      return _openBlock$c(), _createElementBlock$c("div", _hoisted_1$c, [
        _createElementVNode$c("div", _hoisted_2$c, [
          _cache[1] || (_cache[1] = _createElementVNode$c("span", { class: "avh-downloads__hint" }, "进度取自下载器，每 5 秒自动刷新", -1)),
          _cache[2] || (_cache[2] = _createElementVNode$c("div", { class: "avh-downloads__spacer" }, null, -1)),
          _createVNode$a(_component_v_btn, {
            variant: "outlined",
            size: "small",
            onClick: refreshQueue
          }, {
            default: _withCtx$a(() => _cache[0] || (_cache[0] = [
              _createTextVNode$9("↻ 刷新进度")
            ])),
            _: 1
          })
        ]),
        rows.value.length ? (_openBlock$c(), _createElementBlock$c(_Fragment$9, { key: 0 }, [
          _createElementVNode$c("div", _hoisted_3$b, "下载中（" + _toDisplayString$c(activeRows.value.length) + "）", 1),
          activeRows.value.length ? (_openBlock$c(true), _createElementBlock$c(_Fragment$9, { key: 0 }, _renderList$9(activeRows.value, (item, index) => {
            return _openBlock$c(), _createElementBlock$c("div", {
              key: rowKey(item, index),
              class: "avh-q"
            }, [
              _createElementVNode$c("div", _hoisted_4$a, [
                _createVNode$a(Thumb, {
                  class: "avh-q__poster",
                  variant: "tposter",
                  src: thumbOf(item),
                  alt: "无图",
                  "plugin-id": _ctx.pluginId
                }, null, 8, ["src", "plugin-id"]),
                _createElementVNode$c("div", _hoisted_5$a, [
                  _createElementVNode$c("div", _hoisted_6$9, _toDisplayString$c(item.number || ""), 1),
                  _createElementVNode$c("div", _hoisted_7$9, _toDisplayString$c(metaOf(item)), 1),
                  _createElementVNode$c("div", _hoisted_8$8, _toDisplayString$c(pathOf(item)), 1)
                ]),
                _createElementVNode$c("div", _hoisted_9$8, [
                  _createElementVNode$c("div", _hoisted_10$8, _toDisplayString$c(progressOf(item)) + "%", 1),
                  _cache[3] || (_cache[3] = _createElementVNode$c("div", { class: "avh-q__hint" }, "下载中…", -1))
                ])
              ]),
              _createElementVNode$c("div", _hoisted_11$7, [
                _createElementVNode$c("i", {
                  style: _normalizeStyle$2({ width: `${progressOf(item)}%` })
                }, null, 4)
              ])
            ]);
          }), 128)) : (_openBlock$c(), _createElementBlock$c("div", _hoisted_12$7, "没有下载中的任务")),
          _createElementVNode$c("div", _hoisted_13$6, [
            _createElementVNode$c("span", null, "已完成（" + _toDisplayString$c(doneRows.value.length) + "）", 1),
            _cache[4] || (_cache[4] = _createElementVNode$c("span", { class: "avh-downloads__secttl-note" }, "完整清单见「下载历史」", -1))
          ]),
          doneRows.value.length ? (_openBlock$c(true), _createElementBlock$c(_Fragment$9, { key: 2 }, _renderList$9(doneRows.value, (item, index) => {
            return _openBlock$c(), _createElementBlock$c("div", {
              key: rowKey(item, index),
              class: "avh-q avh-q--done"
            }, [
              _createElementVNode$c("div", _hoisted_14$6, [
                _createVNode$a(Thumb, {
                  class: "avh-q__poster",
                  variant: "tposter",
                  src: thumbOf(item),
                  alt: "无图",
                  "plugin-id": _ctx.pluginId
                }, null, 8, ["src", "plugin-id"]),
                _createElementVNode$c("div", _hoisted_15$5, [
                  _createElementVNode$c("div", _hoisted_16$3, _toDisplayString$c(item.number || ""), 1),
                  item.title ? (_openBlock$c(), _createElementBlock$c("div", _hoisted_17$3, _toDisplayString$c(item.title), 1)) : _createCommentVNode$a("", true),
                  _createElementVNode$c("div", _hoisted_18$3, _toDisplayString$c(doneInfoOf(item)), 1)
                ])
              ])
            ]);
          }), 128)) : (_openBlock$c(), _createElementBlock$c("div", _hoisted_19$3, _cache[5] || (_cache[5] = [
            _createTextVNode$9(" 暂无已完成条目"),
            _createElementVNode$c("br", null, null, -1),
            _createTextVNode$9("完成的下载会记入「下载历史」，这里只在旧快照与刷新间隙里短暂出现 ")
          ])))
        ], 64)) : (_openBlock$c(), _createBlock$a(EmptyState, {
          key: 1,
          text: "下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看<br>完成的下载在「下载历史」栏，删了文件也还在"
        }))
      ]);
    };
  }
});

const DownloadsView = /* @__PURE__ */ _export_sfc(_sfc_main$c, [["__scopeId", "data-v-738d381d"]]);

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

const {defineComponent:_defineComponent$b} = await importShared('vue');

const {createElementVNode:_createElementVNode$b,resolveComponent:_resolveComponent$9,createVNode:_createVNode$9,createTextVNode:_createTextVNode$8,withCtx:_withCtx$9,toDisplayString:_toDisplayString$b,openBlock:_openBlock$b,createElementBlock:_createElementBlock$b,createCommentVNode:_createCommentVNode$9,unref:_unref$1,renderList:_renderList$8,Fragment:_Fragment$8,createBlock:_createBlock$9} = await importShared('vue');

const _hoisted_1$b = { class: "avh-history" };
const _hoisted_2$b = { class: "avh-history__toolbar" };
const _hoisted_3$a = {
  key: 0,
  class: "avh-history__stats"
};
const _hoisted_4$9 = { class: "avh-history__hint" };
const _hoisted_5$9 = {
  key: 1,
  class: "avh-history__tablewrap",
  "aria-busy": "true"
};
const _hoisted_6$8 = { class: "avh-history__table" };
const _hoisted_7$8 = {
  key: 3,
  class: "avh-history__tablewrap"
};
const _hoisted_8$7 = { class: "avh-history__table" };
const _hoisted_9$7 = { class: "avh-history__pic" };
const _hoisted_10$7 = { class: "avh-history__no" };
const _hoisted_11$6 = ["title"];
const _hoisted_12$6 = ["title"];
const _hoisted_13$5 = ["title"];
const _hoisted_14$5 = ["title"];
const _hoisted_15$4 = { class: "avh-history__act" };
const {computed: computed$9,onMounted: onMounted$5,ref: ref$b} = await importShared('vue');
const ENDPOINT = "plugin/downloads";
const SKELETON_ROWS = 6;
const _sfc_main$b = /* @__PURE__ */ _defineComponent$b({
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
    const items = ref$b([]);
    const serverCounts = ref$b(null);
    const loading = ref$b(false);
    const error = ref$b("");
    const loaded = ref$b(false);
    const query = ref$b("");
    const onlyMissing = ref$b(false);
    const deletingKey = ref$b("");
    const rows = computed$9(
      () => filterRecords(items.value, query.value, onlyMissing.value)
    );
    const filtered = computed$9(() => !!String(query.value || "").trim() || onlyMissing.value);
    const counts = computed$9(() => {
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
    const summary = computed$9(
      () => `共 ${counts.value.total} 条 · 在库 ${counts.value.inLibrary} · 不在库 ${counts.value.missing}`
    );
    function libraryText(item) {
      return inLibrary(item) ? "在库" : "不在库（可能已删除）";
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
        const response = await client.get(ENDPOINT);
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
        const response = await client.delete(ENDPOINT, { params: { key } });
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
    onMounted$5(() => {
      void load(false);
    });
    return (_ctx, _cache) => {
      const _component_v_text_field = _resolveComponent$9("v-text-field");
      const _component_v_switch = _resolveComponent$9("v-switch");
      const _component_v_btn = _resolveComponent$9("v-btn");
      const _component_v_chip = _resolveComponent$9("v-chip");
      return _openBlock$b(), _createElementBlock$b("div", _hoisted_1$b, [
        _createElementVNode$b("div", _hoisted_2$b, [
          _cache[5] || (_cache[5] = _createElementVNode$b("span", { class: "avh-history__hint" }, "插件下载过的番号都在这里，文件删了也留着记录", -1)),
          _cache[6] || (_cache[6] = _createElementVNode$b("div", { class: "avh-history__spacer" }, null, -1)),
          _createVNode$9(_component_v_text_field, {
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
          _createVNode$9(_component_v_switch, {
            modelValue: onlyMissing.value,
            "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => onlyMissing.value = $event),
            class: "avh-history__switch",
            color: "primary",
            density: "compact",
            "hide-details": "",
            label: "只看不在库"
          }, null, 8, ["modelValue"]),
          _createVNode$9(_component_v_btn, {
            variant: "outlined",
            size: "small",
            loading: loading.value,
            onClick: _cache[2] || (_cache[2] = ($event) => load(true))
          }, {
            default: _withCtx$9(() => _cache[4] || (_cache[4] = [
              _createTextVNode$8("↻ 刷新")
            ])),
            _: 1
          }, 8, ["loading"])
        ]),
        !error.value && (loaded.value || items.value.length) ? (_openBlock$b(), _createElementBlock$b("div", _hoisted_3$a, [
          _createVNode$9(_component_v_chip, {
            size: "x-small",
            variant: "flat",
            color: "success",
            label: ""
          }, {
            default: _withCtx$9(() => [
              _createTextVNode$8("在库 " + _toDisplayString$b(counts.value.inLibrary), 1)
            ]),
            _: 1
          }),
          _createVNode$9(_component_v_chip, {
            size: "x-small",
            variant: "outlined",
            label: ""
          }, {
            default: _withCtx$9(() => [
              _createTextVNode$8("不在库 " + _toDisplayString$b(counts.value.missing), 1)
            ]),
            _: 1
          }),
          _createElementVNode$b("span", _hoisted_4$9, _toDisplayString$b(summary.value), 1)
        ])) : _createCommentVNode$9("", true),
        loading.value && !items.value.length ? (_openBlock$b(), _createElementBlock$b("div", _hoisted_5$9, [
          _cache[10] || (_cache[10] = _createElementVNode$b("div", { class: "avh-history__loading" }, "正在读取下载历史…", -1)),
          _createElementVNode$b("table", _hoisted_6$8, [
            _cache[8] || (_cache[8] = _createElementVNode$b("colgroup", null, [
              _createElementVNode$b("col", { class: "avh-history__col-pic" }),
              _createElementVNode$b("col", { class: "avh-history__col-no" }),
              _createElementVNode$b("col"),
              _createElementVNode$b("col", { class: "avh-history__col-actor" }),
              _createElementVNode$b("col", { class: "avh-history__col-size" }),
              _createElementVNode$b("col", { class: "avh-history__col-time" }),
              _createElementVNode$b("col", { class: "avh-history__col-lib" }),
              _createElementVNode$b("col", { class: "avh-history__col-act" })
            ], -1)),
            _cache[9] || (_cache[9] = _createElementVNode$b("thead", null, [
              _createElementVNode$b("tr", null, [
                _createElementVNode$b("th", null, "封面"),
                _createElementVNode$b("th", null, "番号"),
                _createElementVNode$b("th", null, "标题"),
                _createElementVNode$b("th", null, "演员"),
                _createElementVNode$b("th", null, "大小"),
                _createElementVNode$b("th", null, "完成时间"),
                _createElementVNode$b("th", null, "库状态"),
                _createElementVNode$b("th", { class: "avh-history__act" }, "操作")
              ])
            ], -1)),
            _createElementVNode$b("tbody", null, [
              (_openBlock$b(true), _createElementBlock$b(_Fragment$8, null, _renderList$8(_unref$1(skeletonRows), (row) => {
                return _openBlock$b(), _createElementBlock$b("tr", {
                  key: `sk-${row}`
                }, _cache[7] || (_cache[7] = [
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk avh-history__sk--pic" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1),
                  _createElementVNode$b("td", null, [
                    _createElementVNode$b("div", { class: "avh-history__sk" })
                  ], -1)
                ]));
              }), 128))
            ])
          ])
        ])) : error.value ? (_openBlock$b(), _createBlock$9(ErrorState, {
          key: 2,
          message: `下载历史读取失败：${error.value}`,
          retrying: loading.value,
          onRetry: _cache[3] || (_cache[3] = ($event) => load(false))
        }, null, 8, ["message", "retrying"])) : rows.value.length ? (_openBlock$b(), _createElementBlock$b("div", _hoisted_7$8, [
          _createElementVNode$b("table", _hoisted_8$7, [
            _cache[12] || (_cache[12] = _createElementVNode$b("colgroup", null, [
              _createElementVNode$b("col", { class: "avh-history__col-pic" }),
              _createElementVNode$b("col", { class: "avh-history__col-no" }),
              _createElementVNode$b("col"),
              _createElementVNode$b("col", { class: "avh-history__col-actor" }),
              _createElementVNode$b("col", { class: "avh-history__col-size" }),
              _createElementVNode$b("col", { class: "avh-history__col-time" }),
              _createElementVNode$b("col", { class: "avh-history__col-lib" }),
              _createElementVNode$b("col", { class: "avh-history__col-act" })
            ], -1)),
            _cache[13] || (_cache[13] = _createElementVNode$b("thead", null, [
              _createElementVNode$b("tr", null, [
                _createElementVNode$b("th", null, "封面"),
                _createElementVNode$b("th", null, "番号"),
                _createElementVNode$b("th", null, "标题"),
                _createElementVNode$b("th", null, "演员"),
                _createElementVNode$b("th", null, "大小"),
                _createElementVNode$b("th", null, "完成时间"),
                _createElementVNode$b("th", null, "库状态"),
                _createElementVNode$b("th", { class: "avh-history__act" }, "操作")
              ])
            ], -1)),
            _createElementVNode$b("tbody", null, [
              (_openBlock$b(true), _createElementBlock$b(_Fragment$8, null, _renderList$8(rows.value, (item, index) => {
                return _openBlock$b(), _createElementBlock$b("tr", {
                  key: rowKey(item, index)
                }, [
                  _createElementVNode$b("td", _hoisted_9$7, [
                    _createVNode$9(Thumb, {
                      class: "avh-history__thumb",
                      variant: "tposter",
                      src: String(item.thumb || ""),
                      alt: "无图",
                      "plugin-id": _ctx.pluginId
                    }, null, 8, ["src", "plugin-id"])
                  ]),
                  _createElementVNode$b("td", _hoisted_10$7, _toDisplayString$b(_unref$1(displayNumber)(item)), 1),
                  _createElementVNode$b("td", {
                    class: "avh-history__title",
                    title: String(item.title || "")
                  }, _toDisplayString$b(String(item.title || "") || "—"), 9, _hoisted_11$6),
                  _createElementVNode$b("td", {
                    title: String(item.actor || "")
                  }, _toDisplayString$b(String(item.actor || "") || "—"), 9, _hoisted_12$6),
                  _createElementVNode$b("td", null, _toDisplayString$b(_unref$1(sizeLabel)(item)), 1),
                  _createElementVNode$b("td", {
                    title: String(item.completedAt || item.createdAt || "")
                  }, _toDisplayString$b(_unref$1(completedText)(item)), 9, _hoisted_13$5),
                  _createElementVNode$b("td", {
                    title: String(item.lib?.path || "")
                  }, [
                    _createVNode$9(_component_v_chip, {
                      size: "x-small",
                      label: "",
                      variant: _unref$1(inLibrary)(item) ? "flat" : "outlined",
                      color: _unref$1(inLibrary)(item) ? "success" : void 0,
                      class: "avh-history__lib"
                    }, {
                      default: _withCtx$9(() => [
                        _createTextVNode$8(_toDisplayString$b(libraryText(item)), 1)
                      ]),
                      _: 2
                    }, 1032, ["variant", "color"])
                  ], 8, _hoisted_14$5),
                  _createElementVNode$b("td", _hoisted_15$4, [
                    _createVNode$9(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      loading: isDeleting(item, index),
                      onClick: ($event) => removeRecord(item)
                    }, {
                      default: _withCtx$9(() => _cache[11] || (_cache[11] = [
                        _createTextVNode$8("移除记录")
                      ])),
                      _: 2
                    }, 1032, ["loading", "onClick"])
                  ])
                ]);
              }), 128))
            ])
          ])
        ])) : filtered.value && loaded.value ? (_openBlock$b(), _createBlock$9(EmptyState, {
          key: 4,
          text: "没有匹配的下载记录",
          hint: "试试清空搜索词，或关掉「只看不在库」"
        })) : (_openBlock$b(), _createBlock$9(EmptyState, {
          key: 5,
          text: "还没有下载记录<br>插件下载过的番号会自动登记在这里，删掉文件也不会消失"
        }))
      ]);
    };
  }
});

const HistoryView = /* @__PURE__ */ _export_sfc(_sfc_main$b, [["__scopeId", "data-v-7af6c554"]]);

const {defineComponent:_defineComponent$a} = await importShared('vue');

const {createElementVNode:_createElementVNode$a,createTextVNode:_createTextVNode$7,resolveComponent:_resolveComponent$8,withCtx:_withCtx$8,createVNode:_createVNode$8,toDisplayString:_toDisplayString$a,renderList:_renderList$7,Fragment:_Fragment$7,openBlock:_openBlock$a,createElementBlock:_createElementBlock$a,createBlock:_createBlock$8} = await importShared('vue');

const _hoisted_1$a = { class: "avh-tasks" };
const _hoisted_2$a = { class: "avh-tasks__toolbar" };
const _hoisted_3$9 = { class: "avh-tasks__secttl" };
const {computed: computed$8,onBeforeUnmount: onBeforeUnmount$4,onMounted: onMounted$4,ref: ref$a,watch: watch$6} = await importShared('vue');
const POLL_MS = 5e3;
const _sfc_main$a = /* @__PURE__ */ _defineComponent$a({
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
    const tables = ref$a([]);
    const pending = computed$8(() => {
      const all = Array.isArray(props.store.tasks.value) ? props.store.tasks.value : [];
      return all.filter((item) => item.state === "await");
    });
    function rowKey(task, index) {
      return String(task.id ?? `${task.number || ""}#${index}`);
    }
    function clearAllPending() {
      tables.value.forEach((table) => table?.clearPending());
    }
    function clearSitePending(site) {
      tables.value.forEach((table) => table?.clearPending(site));
    }
    async function refreshTasks() {
      const inflight = props.store.refreshTasks(false);
      t.info("正在刷新…");
      if (!await inflight) {
        t.warning(`任务读取失败：${props.store.error.value || "请稍后重试"}`);
      }
      clearAllPending();
    }
    async function onDownload(payload) {
      const res = await props.store.startDownload(payload.taskId, payload.site, payload.force);
      if (!res.ok) {
        t.warning(res.message || "下载失败，请稍后重试");
      } else {
        t.success("已提交下载");
        t.info(`${payload.site} · 进度见「下载」页`);
        void props.store.refreshTasks(false);
      }
      clearSitePending(payload.site);
    }
    async function onCancel(payload) {
      const num = pending.value.filter((item) => String(item.id ?? "") === payload.taskId)[0]?.number || "";
      const res = await props.store.cancelTask(payload.taskId);
      if (!res.ok) {
        t.warning("取消任务失败");
        t.info(res.message || "请稍后重试");
      } else {
        t.warning("已取消任务");
        t.info(`${num ? num + " · " : ""}已从待确认里移除`);
        void props.store.refreshTasks(false);
      }
      tables.value.forEach((table) => table?.clearCanceling());
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
    onMounted$4(() => {
      void props.store.refreshTasks(true);
      if (document.visibilityState === "visible") startPolling();
      document.addEventListener("visibilitychange", onVisibilityChange);
    });
    onBeforeUnmount$4(() => {
      stopPolling();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$8("v-btn");
      return _openBlock$a(), _createElementBlock$a("div", _hoisted_1$a, [
        _createElementVNode$a("div", _hoisted_2$a, [
          _cache[1] || (_cache[1] = _createElementVNode$a("div", { class: "avh-tasks__spacer" }, null, -1)),
          _createVNode$8(_component_v_btn, {
            variant: "outlined",
            size: "small",
            onClick: refreshTasks
          }, {
            default: _withCtx$8(() => _cache[0] || (_cache[0] = [
              _createTextVNode$7("↻ 刷新任务")
            ])),
            _: 1
          })
        ]),
        pending.value.length ? (_openBlock$a(), _createElementBlock$a(_Fragment$7, { key: 0 }, [
          _createElementVNode$a("div", _hoisted_3$9, "待确认（" + _toDisplayString$a(pending.value.length) + "）", 1),
          (_openBlock$a(true), _createElementBlock$a(_Fragment$7, null, _renderList$7(pending.value, (task, index) => {
            return _openBlock$a(), _createBlock$8(CandTable, {
              key: rowKey(task, index),
              ref_for: true,
              ref_key: "tables",
              ref: tables,
              task,
              "plugin-id": _ctx.pluginId,
              cancelable: "",
              onDownload,
              onCancel
            }, null, 8, ["task", "plugin-id"]);
          }), 128))
        ], 64)) : (_openBlock$a(), _createBlock$8(EmptyState, {
          key: 1,
          text: "没有待确认的任务"
        }))
      ]);
    };
  }
});

const TasksView = /* @__PURE__ */ _export_sfc(_sfc_main$a, [["__scopeId", "data-v-65040ab1"]]);

const {defineComponent:_defineComponent$9} = await importShared('vue');

const {toDisplayString:_toDisplayString$9,createElementVNode:_createElementVNode$9,createTextVNode:_createTextVNode$6,resolveComponent:_resolveComponent$7,withCtx:_withCtx$7,createVNode:_createVNode$7,renderList:_renderList$6,Fragment:_Fragment$6,openBlock:_openBlock$9,createElementBlock:_createElementBlock$9,normalizeClass:_normalizeClass$6,createBlock:_createBlock$7} = await importShared('vue');

const _hoisted_1$9 = { class: "avh-subs" };
const _hoisted_2$9 = { class: "avh-subs__toolbar" };
const _hoisted_3$8 = { class: "avh-subs__hint" };
const _hoisted_4$8 = { class: "avh-subs__rulecard" };
const _hoisted_5$8 = { class: "avh-subs__rulehd" };
const _hoisted_6$7 = { class: "avh-subs__hint" };
const _hoisted_7$7 = { class: "avh-subs__rulegrid" };
const _hoisted_8$6 = { class: "avh-subs__rulelabel" };
const _hoisted_9$6 = { key: 0 };
const _hoisted_10$6 = { class: "avh-sub__hd" };
const _hoisted_11$5 = { class: "avh-sub__main" };
const _hoisted_12$5 = { class: "avh-sub__name" };
const _hoisted_13$4 = { class: "avh-subs__hint avh-sub__rule" };
const _hoisted_14$4 = { class: "avh-subs__hint avh-sub__stat" };
const _hoisted_15$3 = { class: "avh-sub__right" };
const {computed: computed$7,ref: ref$9} = await importShared('vue');
const ALL = "";
const _sfc_main$9 = /* @__PURE__ */ _defineComponent$9({
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
    const checking = ref$9("");
    const subs = computed$7(
      () => Array.isArray(props.store.subs.value) ? props.store.subs.value : []
    );
    const hasSubs = computed$7(() => subs.value.length > 0);
    const defaultSummary = computed$7(() => ruleSummary(props.store.rule.value));
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
    const resText = computed$7(() => {
      const value = String(props.store.rule.value.res || "1080p");
      return RES_LABELS[value] || value;
    });
    const ruleRows = computed$7(() => {
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
    const checkBusy = computed$7(() => checking.value !== "");
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
      const _component_v_btn = _resolveComponent$7("v-btn");
      const _component_v_icon = _resolveComponent$7("v-icon");
      return _openBlock$9(), _createElementBlock$9("div", _hoisted_1$9, [
        _createElementVNode$9("div", _hoisted_2$9, [
          _createElementVNode$9("span", _hoisted_3$8, "默认规则：" + _toDisplayString$9(defaultSummary.value), 1),
          _cache[3] || (_cache[3] = _createElementVNode$9("div", { class: "avh-subs__spacer" }, null, -1)),
          _createVNode$7(_component_v_btn, {
            variant: "outlined",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            onClick: goRuleSettings
          }, {
            default: _withCtx$7(() => _cache[1] || (_cache[1] = [
              _createTextVNode$6(" 去设置台改规则 ")
            ])),
            _: 1
          }),
          _createVNode$7(_component_v_btn, {
            variant: "outlined",
            size: "small",
            "prepend-icon": "mdi-lightning-bolt",
            loading: checkBusy.value,
            disabled: checkBusy.value || !hasSubs.value,
            onClick: _cache[0] || (_cache[0] = ($event) => runCheck(ALL))
          }, {
            default: _withCtx$7(() => _cache[2] || (_cache[2] = [
              _createTextVNode$6("检查一次")
            ])),
            _: 1
          }, 8, ["loading", "disabled"])
        ]),
        _createElementVNode$9("div", _hoisted_4$8, [
          _createElementVNode$9("div", _hoisted_5$8, [
            _cache[4] || (_cache[4] = _createElementVNode$9("div", { class: "avh-subs__ruletitle" }, "默认规则（手动搜索与新建订阅的基准）", -1)),
            _createElementVNode$9("div", _hoisted_6$7, "分辨率策略：" + _toDisplayString$9(resText.value), 1),
            _cache[5] || (_cache[5] = _createElementVNode$9("div", { class: "avh-subs__hint" }, "规则在「设置台 → 下载规则」里改", -1))
          ]),
          _createElementVNode$9("div", _hoisted_7$7, [
            (_openBlock$9(true), _createElementBlock$9(_Fragment$6, null, _renderList$6(ruleRows.value, (row) => {
              return _openBlock$9(), _createElementBlock$9("div", {
                key: row.label,
                class: "avh-subs__ruleitem"
              }, [
                _createElementVNode$9("span", _hoisted_8$6, _toDisplayString$9(row.label), 1),
                _createElementVNode$9("span", {
                  class: _normalizeClass$6(["avh-subs__rulevalue", { "avh-subs__rulevalue--on": row.on }])
                }, _toDisplayString$9(row.text), 3)
              ]);
            }), 128))
          ])
        ]),
        hasSubs.value ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_9$6, [
          (_openBlock$9(true), _createElementBlock$9(_Fragment$6, null, _renderList$6(subs.value, (sub, index) => {
            return _openBlock$9(), _createElementBlock$9("div", {
              key: rowKey(sub, index),
              class: "avh-sub"
            }, [
              _createElementVNode$9("div", _hoisted_10$6, [
                _createVNode$7(_component_v_icon, {
                  icon: typeIcon(sub),
                  size: "20",
                  class: "avh-sub__icon"
                }, null, 8, ["icon"]),
                _createElementVNode$9("div", _hoisted_11$5, [
                  _createElementVNode$9("div", _hoisted_12$5, _toDisplayString$9(sub.name), 1),
                  _createElementVNode$9("div", _hoisted_13$4, _toDisplayString$9(ruleSummary(subRule(sub))), 1),
                  _createElementVNode$9("div", _hoisted_14$4, " 命中 " + _toDisplayString$9(hitsText(sub)) + " 次 · 上次检查 " + _toDisplayString$9(lastText(sub)), 1)
                ]),
                _createElementVNode$9("div", _hoisted_15$3, [
                  _createVNode$7(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    loading: checking.value === String(sub.name || ""),
                    disabled: checkBusy.value,
                    onClick: ($event) => runCheck(String(sub.name || ""))
                  }, {
                    default: _withCtx$7(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$6("检查")
                    ])),
                    _: 2
                  }, 1032, ["loading", "disabled", "onClick"]),
                  _createVNode$7(_component_v_btn, {
                    variant: "outlined",
                    color: "error",
                    size: "small",
                    disabled: checkBusy.value,
                    onClick: ($event) => onUnsubscribe(sub)
                  }, {
                    default: _withCtx$7(() => _cache[7] || (_cache[7] = [
                      _createTextVNode$6("取消")
                    ])),
                    _: 2
                  }, 1032, ["disabled", "onClick"])
                ])
              ])
            ]);
          }), 128))
        ])) : (_openBlock$9(), _createBlock$7(EmptyState, {
          key: 1,
          text: "还没有订阅"
        }))
      ]);
    };
  }
});

const SubsView = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-1e2afa2f"]]);

const {defineComponent:_defineComponent$8} = await importShared('vue');

const {openBlock:_openBlock$8,createElementBlock:_createElementBlock$8,createCommentVNode:_createCommentVNode$8,createVNode:_createVNode$6,toDisplayString:_toDisplayString$8,createElementVNode:_createElementVNode$8,normalizeClass:_normalizeClass$5} = await importShared('vue');

const _hoisted_1$8 = ["title"];
const _hoisted_2$8 = {
  key: 0,
  class: "avh-actor__star"
};
const _hoisted_3$7 = { class: "avh-actor__nm" };
const _hoisted_4$7 = { class: "avh-actor__zh" };
const _hoisted_5$7 = {
  key: 1,
  class: "avh-actor__tag"
};
const _sfc_main$8 = /* @__PURE__ */ _defineComponent$8({
  __name: "ActorRow",
  props: {
    name: {},
    zh: { default: "" },
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
      return _openBlock$8(), _createElementBlock$8("div", {
        class: _normalizeClass$5(["avh-actor", { "avh-actor--picker": _ctx.picker, "avh-actor--faved": _ctx.picker && _ctx.favorited }]),
        title: _ctx.name,
        onClick: onSelect
      }, [
        !_ctx.picker && _ctx.favorited ? (_openBlock$8(), _createElementBlock$8("div", _hoisted_2$8, "⭐")) : _createCommentVNode$8("", true),
        _createVNode$6(Thumb, {
          class: "avh-actor__av",
          variant: "av",
          src: _ctx.avatar,
          alt: _ctx.name,
          "plugin-id": _ctx.pluginId
        }, null, 8, ["src", "alt", "plugin-id"]),
        _createElementVNode$8("div", _hoisted_3$7, _toDisplayString$8(_ctx.name), 1),
        _createElementVNode$8("div", _hoisted_4$7, _toDisplayString$8(_ctx.zh || ""), 1),
        _ctx.picker ? (_openBlock$8(), _createElementBlock$8("div", _hoisted_5$7, [
          _createElementVNode$8("span", {
            class: _normalizeClass$5(["avh-tag", _ctx.favorited ? "avh-tag--on" : ""])
          }, _toDisplayString$8(_ctx.favorited ? "✓ 已收藏" : "➕ 收藏"), 3)
        ])) : _createCommentVNode$8("", true)
      ], 10, _hoisted_1$8);
    };
  }
});

const ActorRow = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-077ee37d"]]);

function cssUrl(value) {
  return String(value || "").replace(/["'()\\\s]/g, (char) => encodeURIComponent(char));
}

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

const {defineComponent:_defineComponent$7} = await importShared('vue');

const {createTextVNode:_createTextVNode$5,resolveComponent:_resolveComponent$6,withCtx:_withCtx$6,createVNode:_createVNode$5,createElementVNode:_createElementVNode$7,openBlock:_openBlock$7,createElementBlock:_createElementBlock$7,createCommentVNode:_createCommentVNode$7,createBlock:_createBlock$6,toDisplayString:_toDisplayString$7,normalizeClass:_normalizeClass$4,renderList:_renderList$5,Fragment:_Fragment$5,normalizeStyle:_normalizeStyle$1} = await importShared('vue');

const _hoisted_1$7 = { class: "avh-actors__toolbar" };
const _hoisted_2$7 = {
  key: 0,
  class: "avh-loading"
};
const _hoisted_3$6 = { class: "avh-profile" };
const _hoisted_4$6 = { class: "avh-profile__av" };
const _hoisted_5$6 = { class: "avh-profile__main" };
const _hoisted_6$6 = { class: "avh-profile__name" };
const _hoisted_7$6 = {
  key: 0,
  class: "avh-profile__zh"
};
const _hoisted_8$5 = { class: "avh-kv" };
const _hoisted_9$5 = { key: 0 };
const _hoisted_10$5 = { key: 1 };
const _hoisted_11$4 = { key: 2 };
const _hoisted_12$4 = { key: 3 };
const _hoisted_13$3 = { key: 4 };
const _hoisted_14$3 = { key: 5 };
const _hoisted_15$2 = { key: 6 };
const _hoisted_16$2 = { class: "avh-acts" };
const _hoisted_17$2 = { class: "avh-secttl" };
const _hoisted_18$2 = {
  key: 0,
  class: "avh-filmyears"
};
const _hoisted_19$2 = ["onClick"];
const _hoisted_20$2 = { class: "avh-filmyears__n" };
const _hoisted_21$1 = { class: "avh-films" };
const _hoisted_22$1 = ["title", "onClick", "onMouseenter"];
const _hoisted_23$1 = { class: "avh-film__ft" };
const _hoisted_24$1 = { class: "avh-film__fn" };
const _hoisted_25$1 = {
  key: 0,
  class: "avh-film__ftt"
};
const _hoisted_26$1 = { class: "avh-film__fd" };
const _hoisted_27$1 = {
  key: 0,
  class: "avh-tag avh-tag--lib"
};
const _hoisted_28$1 = {
  key: 0,
  class: "avh-morebar"
};
const _hoisted_29$1 = {
  key: 1,
  class: "avh-morebar"
};
const _hoisted_30$1 = { class: "avh-hint" };
const _hoisted_31$1 = { class: "avh-actors__toolbar" };
const _hoisted_32$1 = { class: "avh-hint" };
const _hoisted_33$1 = { class: "avh-actors" };
const _hoisted_34$1 = {
  key: 0,
  class: "avh-loading"
};
const _hoisted_35$1 = {
  key: 2,
  class: "avh-hint"
};
const _hoisted_36$1 = { class: "avh-actors avh-actors--pick" };
const {computed: computed$6,nextTick: nextTick$2,onUnmounted,reactive: reactive$1,ref: ref$8,watch: watch$5} = await importShared('vue');
const FILM_PAGE = 30;
const _sfc_main$7 = /* @__PURE__ */ _defineComponent$7({
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
    const rootEl = ref$8(null);
    const actor = ref$8("");
    const actorYear = ref$8("");
    const loadingMore = ref$8(false);
    const pageRetrying = ref$8(false);
    const year = computed$6(() => actorYear.value);
    const favs = computed$6(
      () => Array.isArray(props.store.favs.value) ? props.store.favs.value : []
    );
    const hasFavs = computed$6(() => favs.value.length > 0);
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
    const pageEntry = computed$6(
      () => actor.value ? pageCache.get(`page:actor:${actor.value}`) || null : null
    );
    const pageLoading = computed$6(() => !!actor.value && !pageEntry.value);
    const pageError = computed$6(() => pageEntry.value ? pageEntry.value.error : "");
    const pageData = computed$6(() => pageEntry.value ? pageEntry.value.data : {});
    const entity = computed$6(() => pageData.value.entity || {});
    const movies = computed$6(
      () => Array.isArray(pageData.value.movies) ? pageData.value.movies : []
    );
    const faved = computed$6(() => !!findFav(actor.value));
    const sub = computed$6(
      () => (Array.isArray(props.store.subs.value) ? props.store.subs.value : []).filter(
        (item) => item.type === "actor" && item.name === actor.value
      )[0] || null
    );
    const yearInfo = computed$6(() => {
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
    const list = computed$6(
      () => year.value ? movies.value.filter((mv) => String(mv.date || "").slice(0, 4) === year.value) : movies.value
    );
    const hasMore = computed$6(() => !!pageData.value.hasMore);
    const totalCount = computed$6(() => Number(pageData.value.total || 0) || movies.value.length);
    const filmsTitle = computed$6(() => {
      const loaded = `作品史（按发行时间倒序，已加载 ${movies.value.length} 部`;
      const site = totalCount.value > movies.value.length ? ` / 站点记录 ${totalCount.value} 部` : "";
      const scope = year.value ? `，${year.value} 年 ${list.value.length} 部` : "";
      return `${loaded}${site}${scope}）`;
    });
    const moreLabel = computed$6(
      () => year.value ? `继续加载 ${FILM_PAGE} 部（往更早的年份找）` : `加载更多（已显示 ${movies.value.length} / 共 ${totalCount.value} 部）`
    );
    const filmsEmptyText = computed$6(() => {
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
      void loadPage(target);
      void nextTick$2(() => rootEl.value?.scrollIntoView({ block: "start" }));
    }
    function backToList() {
      actor.value = "";
    }
    async function retryPage() {
      const name = actor.value;
      if (!name) return;
      pageRetrying.value = true;
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
      if (!name || !entry || loadingMore.value) return;
      const data = entry.data || {};
      const page = (Number(data.page) || 1) + 1;
      const before = year.value ? yearCountOf(movies.value, year.value) : 0;
      loadingMore.value = true;
      try {
        const res = await apiGet("actor", { name, page, limit: FILM_PAGE });
        if (!res.ok) {
          t.warning("加载更多失败");
          t.info(res.message || "请稍后重试");
          return;
        }
        const next = res.payload || {};
        const seen = {};
        movies.value.forEach((x) => {
          seen[`${x.id || ""}|${x.number || ""}`] = true;
        });
        const add = (next.movies || []).filter((x) => !seen[`${x.id || ""}|${x.number || ""}`]);
        data.movies = movies.value.concat(add);
        data.page = page;
        data.hasMore = !!next.hasMore;
        data.total = next.total || data.total;
        data.entity = next.entity || data.entity;
        if (actor.value !== name) return;
        if (year.value && yearCountOf(data.movies, year.value) === before) {
          t.warning("继续加载");
          t.info(`这一批没有 ${year.value} 年的作品，已加载 ${data.movies.length} 部`);
        }
      } finally {
        loadingMore.value = false;
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
    const subscribing = ref$8(false);
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
    const checking = ref$8(false);
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
    const pickerOpen = ref$8(false);
    const pickerLoading = ref$8(false);
    const pickerError = ref$8("");
    const pickerRows = ref$8([]);
    const pickerAdded = ref$8([]);
    const addingName = ref$8("");
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
      const _component_v_btn = _resolveComponent$6("v-btn");
      const _component_v_card_title = _resolveComponent$6("v-card-title");
      const _component_v_card_text = _resolveComponent$6("v-card-text");
      const _component_v_spacer = _resolveComponent$6("v-spacer");
      const _component_v_card_actions = _resolveComponent$6("v-card-actions");
      const _component_v_card = _resolveComponent$6("v-card");
      const _component_v_dialog = _resolveComponent$6("v-dialog");
      return _openBlock$7(), _createElementBlock$7("div", {
        ref_key: "rootEl",
        ref: rootEl,
        class: "avh-actors-view"
      }, [
        actor.value ? (_openBlock$7(), _createElementBlock$7(_Fragment$5, { key: 0 }, [
          _createElementVNode$7("div", _hoisted_1$7, [
            _createVNode$5(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: backToList
            }, {
              default: _withCtx$6(() => _cache[3] || (_cache[3] = [
                _createTextVNode$5("← 返回")
              ])),
              _: 1
            })
          ]),
          pageLoading.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_2$7, "正在抓取演员档案与作品史…")) : pageError.value ? (_openBlock$7(), _createBlock$6(ErrorState, {
            key: 1,
            message: pageError.value,
            retrying: pageRetrying.value,
            onRetry: retryPage
          }, null, 8, ["message", "retrying"])) : (_openBlock$7(), _createElementBlock$7(_Fragment$5, { key: 2 }, [
            _createElementVNode$7("div", _hoisted_3$6, [
              _createElementVNode$7("div", _hoisted_4$6, [
                _createVNode$5(Thumb, {
                  src: entity.value.avatar,
                  alt: actor.value,
                  "plugin-id": _ctx.pluginId
                }, null, 8, ["src", "alt", "plugin-id"])
              ]),
              _createElementVNode$7("div", _hoisted_5$6, [
                _createElementVNode$7("h2", _hoisted_6$6, [
                  _createTextVNode$5(_toDisplayString$7(entity.value.name || actor.value) + " ", 1),
                  entity.value.zh ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_7$6, "/ " + _toDisplayString$7(entity.value.zh), 1)) : _createCommentVNode$7("", true)
                ]),
                _createElementVNode$7("div", _hoisted_8$5, [
                  entity.value.videos_count ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_9$5, [
                    _cache[4] || (_cache[4] = _createElementVNode$7("b", null, "作品", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.videos_count), 1)
                  ])) : _createCommentVNode$7("", true),
                  entity.value.age ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_10$5, [
                    _cache[5] || (_cache[5] = _createElementVNode$7("b", null, "年龄", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.age), 1)
                  ])) : _createCommentVNode$7("", true),
                  entity.value.birthday ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_11$4, [
                    _cache[6] || (_cache[6] = _createElementVNode$7("b", null, "生日", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.birthday), 1)
                  ])) : _createCommentVNode$7("", true),
                  entity.value.height ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_12$4, [
                    _cache[7] || (_cache[7] = _createElementVNode$7("b", null, "身高", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.height) + "cm", 1)
                  ])) : _createCommentVNode$7("", true),
                  entity.value.cup ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_13$3, [
                    _cache[8] || (_cache[8] = _createElementVNode$7("b", null, "罩杯", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.cup), 1)
                  ])) : _createCommentVNode$7("", true),
                  entity.value.birthplace ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_14$3, [
                    _cache[9] || (_cache[9] = _createElementVNode$7("b", null, "出身", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.birthplace), 1)
                  ])) : _createCommentVNode$7("", true),
                  entity.value.instagram ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_15$2, [
                    _cache[10] || (_cache[10] = _createElementVNode$7("b", null, "IG", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(entity.value.instagram), 1)
                  ])) : _createCommentVNode$7("", true),
                  _createElementVNode$7("span", null, [
                    _cache[11] || (_cache[11] = _createElementVNode$7("b", null, "本次返回作品", -1)),
                    _createTextVNode$5(" " + _toDisplayString$7(movies.value.length) + " 部", 1)
                  ])
                ]),
                _createElementVNode$7("div", _hoisted_16$2, [
                  _createVNode$5(_component_v_btn, {
                    color: faved.value ? void 0 : "primary",
                    variant: faved.value ? "outlined" : "flat",
                    size: "small",
                    onClick: toggleFav
                  }, {
                    default: _withCtx$6(() => [
                      _createTextVNode$5(_toDisplayString$7(faved.value ? "★ 已收藏" : "☆ 收藏该演员"), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "variant"]),
                  _createVNode$5(_component_v_btn, {
                    color: sub.value ? void 0 : "primary",
                    variant: sub.value ? "outlined" : "flat",
                    size: "small",
                    loading: subscribing.value,
                    disabled: !!sub.value || subscribing.value,
                    onClick: subscribeActor
                  }, {
                    default: _withCtx$6(() => [
                      _createTextVNode$5(_toDisplayString$7(sub.value ? "✓ 已订阅新片" : "📌 订阅该演员的新片"), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "variant", "loading", "disabled"]),
                  _createVNode$5(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    loading: checking.value,
                    onClick: checkActor
                  }, {
                    default: _withCtx$6(() => _cache[12] || (_cache[12] = [
                      _createTextVNode$5(" ⚡ 检查她的新片 ")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ])
            ]),
            _createElementVNode$7("div", _hoisted_17$2, _toDisplayString$7(filmsTitle.value), 1),
            yearInfo.value.years.length > 1 ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_18$2, [
              _createElementVNode$7("button", {
                type: "button",
                class: _normalizeClass$4({ "avh-filmyears__on": !year.value }),
                onClick: _cache[0] || (_cache[0] = ($event) => pickYear(""))
              }, "全部 " + _toDisplayString$7(movies.value.length) + _toDisplayString$7(hasMore.value ? "+" : ""), 3),
              (_openBlock$7(true), _createElementBlock$7(_Fragment$5, null, _renderList$5(yearInfo.value.years, (y) => {
                return _openBlock$7(), _createElementBlock$7("button", {
                  key: y,
                  type: "button",
                  class: _normalizeClass$4({ "avh-filmyears__on": year.value === y }),
                  onClick: ($event) => pickYear(y)
                }, [
                  _createTextVNode$5(_toDisplayString$7(y), 1),
                  _createElementVNode$7("span", _hoisted_20$2, _toDisplayString$7(" " + yearInfo.value.yearCount[y]), 1)
                ], 10, _hoisted_19$2);
              }), 128))
            ])) : _createCommentVNode$7("", true),
            list.value.length ? (_openBlock$7(), _createElementBlock$7(_Fragment$5, { key: 1 }, [
              _createElementVNode$7("div", _hoisted_21$1, [
                (_openBlock$7(true), _createElementBlock$7(_Fragment$5, null, _renderList$5(list.value, (mv, index) => {
                  return _openBlock$7(), _createElementBlock$7("div", {
                    key: filmKey(mv, index),
                    class: "avh-film",
                    title: mv.title || mv.number || "",
                    onClick: ($event) => openFilm(mv),
                    onMouseenter: ($event) => prefetchFilm(mv)
                  }, [
                    _createElementVNode$7("div", {
                      class: "avh-film__pic",
                      style: _normalizeStyle$1(picStyle(mv))
                    }, [
                      _createVNode$5(Thumb, {
                        variant: "film",
                        src: mv.thumb,
                        alt: mv.number || "",
                        "plugin-id": _ctx.pluginId
                      }, null, 8, ["src", "alt", "plugin-id"])
                    ], 4),
                    _createElementVNode$7("div", _hoisted_23$1, [
                      _createElementVNode$7("div", _hoisted_24$1, _toDisplayString$7(mv.number || ""), 1),
                      mv.title ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_25$1, _toDisplayString$7(mv.title), 1)) : _createCommentVNode$7("", true),
                      _createElementVNode$7("div", _hoisted_26$1, [
                        _createElementVNode$7("span", null, _toDisplayString$7(mv.date || ""), 1),
                        _createElementVNode$7("span", {
                          class: _normalizeClass$4(["avh-tag", { "avh-tag--on": !!mv.cnsub }])
                        }, _toDisplayString$7(mv.cnsub ? "中字" : "无中字"), 3),
                        _createElementVNode$7("span", null, "🧲 " + _toDisplayString$7(mv.magnets || 0), 1),
                        mv.lib ? (_openBlock$7(), _createElementBlock$7("span", _hoisted_27$1, "已入库")) : _createCommentVNode$7("", true)
                      ])
                    ])
                  ], 40, _hoisted_22$1);
                }), 128))
              ]),
              hasMore.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_28$1, [
                _createVNode$5(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  loading: loadingMore.value,
                  onClick: loadMoreFilms
                }, {
                  default: _withCtx$6(() => [
                    _createTextVNode$5(_toDisplayString$7(moreLabel.value), 1)
                  ]),
                  _: 1
                }, 8, ["loading"])
              ])) : movies.value.length > FILM_PAGE ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_29$1, [
                _createElementVNode$7("span", _hoisted_30$1, "已加载全部 " + _toDisplayString$7(movies.value.length) + " 部", 1)
              ])) : _createCommentVNode$7("", true)
            ], 64)) : (_openBlock$7(), _createBlock$6(EmptyState, {
              key: 2,
              text: filmsEmptyText.value
            }, null, 8, ["text"]))
          ], 64))
        ], 64)) : (_openBlock$7(), _createElementBlock$7(_Fragment$5, { key: 1 }, [
          hasFavs.value ? (_openBlock$7(), _createElementBlock$7(_Fragment$5, { key: 0 }, [
            _createElementVNode$7("div", _hoisted_31$1, [
              _createElementVNode$7("span", _hoisted_32$1, "共 " + _toDisplayString$7(favs.value.length) + " 位", 1),
              _cache[14] || (_cache[14] = _createElementVNode$7("div", { class: "avh-actors__spacer" }, null, -1)),
              _createVNode$5(_component_v_btn, {
                variant: "outlined",
                size: "small",
                onClick: openPicker
              }, {
                default: _withCtx$6(() => _cache[13] || (_cache[13] = [
                  _createTextVNode$5("➕ 添加演员")
                ])),
                _: 1
              })
            ]),
            _createElementVNode$7("div", _hoisted_33$1, [
              (_openBlock$7(true), _createElementBlock$7(_Fragment$5, null, _renderList$5(favs.value, (item) => {
                return _openBlock$7(), _createBlock$6(ActorRow, {
                  key: item.name,
                  favorited: "",
                  name: String(item.name || ""),
                  zh: item.zh || "",
                  avatar: favAvatar(item),
                  "plugin-id": _ctx.pluginId,
                  onSelect: openActor
                }, null, 8, ["name", "zh", "avatar", "plugin-id"]);
              }), 128))
            ])
          ], 64)) : (_openBlock$7(), _createBlock$6(EmptyState, {
            key: 1,
            text: "还没有收藏演员"
          }, {
            default: _withCtx$6(() => [
              _createVNode$5(_component_v_btn, {
                color: "primary",
                variant: "flat",
                onClick: openPicker
              }, {
                default: _withCtx$6(() => _cache[15] || (_cache[15] = [
                  _createTextVNode$5("➕ 从演员榜挑选")
                ])),
                _: 1
              })
            ]),
            _: 1
          }))
        ], 64)),
        _createVNode$5(_component_v_dialog, {
          modelValue: pickerOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickerOpen.value = $event),
          "max-width": "880",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$6(() => [
            _createVNode$5(_component_v_card, null, {
              default: _withCtx$6(() => [
                _createVNode$5(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$6(() => _cache[16] || (_cache[16] = [
                    _createTextVNode$5("从演员榜挑选")
                  ])),
                  _: 1
                }),
                _createVNode$5(_component_v_card_text, null, {
                  default: _withCtx$6(() => [
                    pickerLoading.value ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_34$1, "正在抓取演员榜…")) : pickerError.value ? (_openBlock$7(), _createBlock$6(ErrorState, {
                      key: 1,
                      message: pickerError.value,
                      retrying: pickerLoading.value,
                      onRetry: retryRank
                    }, null, 8, ["message", "retrying"])) : !pickerRows.value.length ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_35$1, "演员榜里的人都已收藏。")) : (_openBlock$7(), _createElementBlock$7(_Fragment$5, { key: 3 }, [
                      _cache[17] || (_cache[17] = _createElementVNode$7("div", { class: "avh-actorpick__tip avh-hint" }, "点 ➕ 加入收藏", -1)),
                      _createElementVNode$7("div", _hoisted_36$1, [
                        (_openBlock$7(true), _createElementBlock$7(_Fragment$5, null, _renderList$5(pickerRows.value, (row) => {
                          return _openBlock$7(), _createBlock$6(ActorRow, {
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
                _createVNode$5(_component_v_card_actions, null, {
                  default: _withCtx$6(() => [
                    _createVNode$5(_component_v_spacer),
                    _createVNode$5(_component_v_btn, {
                      color: "error",
                      variant: "outlined",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickerOpen.value = false)
                    }, {
                      default: _withCtx$6(() => _cache[18] || (_cache[18] = [
                        _createTextVNode$5("关闭")
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
      ], 512);
    };
  }
});

const ActorsView = /* @__PURE__ */ _export_sfc(_sfc_main$7, [["__scopeId", "data-v-96bd55da"]]);

const {defineComponent:_defineComponent$6} = await importShared('vue');

const {createVNode:_createVNode$4,openBlock:_openBlock$6,createElementBlock:_createElementBlock$6,createCommentVNode:_createCommentVNode$6,createElementVNode:_createElementVNode$6,toDisplayString:_toDisplayString$6} = await importShared('vue');

const _hoisted_1$6 = ["title"];
const _hoisted_2$6 = { class: "avh-card__thumb" };
const _hoisted_3$5 = { class: "avh-card__badges" };
const _hoisted_4$5 = {
  key: 0,
  class: "avh-badge avh-badge--cn"
};
const _hoisted_5$5 = {
  key: 1,
  class: "avh-badge avh-badge--uc"
};
const _hoisted_6$5 = {
  key: 2,
  class: "avh-badge avh-badge--new"
};
const _hoisted_7$5 = {
  key: 3,
  class: "avh-badge avh-badge--lib"
};
const _hoisted_8$4 = {
  key: 4,
  class: "avh-badge avh-badge--dl"
};
const _hoisted_9$4 = { class: "avh-card__meta" };
const _hoisted_10$4 = { class: "avh-card__num" };
const _hoisted_11$3 = { class: "avh-card__sub" };
const _hoisted_12$3 = { class: "avh-card__sub" };
const _sfc_main$6 = /* @__PURE__ */ _defineComponent$6({
  __name: "NumCard",
  props: {
    movie: {},
    pluginId: { default: "" },
    actorFavorited: { type: Boolean, default: false }
  },
  emits: ["select", "hover"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const number = () => String(props.movie.number || "");
    const id = () => String(props.movie.id || "");
    const durationText = () => {
      const value = props.movie.duration;
      return value ? `${value}′` : "";
    };
    return (_ctx, _cache) => {
      return _openBlock$6(), _createElementBlock$6("div", {
        class: "avh-card",
        title: _ctx.movie.title || number(),
        onClick: _cache[0] || (_cache[0] = ($event) => emit("select", { number: number(), id: id() })),
        onMouseenter: _cache[1] || (_cache[1] = ($event) => emit("hover", { number: number(), id: id() }))
      }, [
        _createElementVNode$6("div", _hoisted_2$6, [
          _createVNode$4(Thumb, {
            variant: "thumb",
            src: _ctx.movie.thumb,
            alt: number(),
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "alt", "plugin-id"]),
          _createElementVNode$6("div", _hoisted_3$5, [
            _ctx.movie.cnsub ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_4$5, "中字")) : _createCommentVNode$6("", true),
            _ctx.movie.uncensored ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_5$5, "破解")) : _createCommentVNode$6("", true),
            _ctx.actorFavorited ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_6$5, "⭐已收藏演员")) : _createCommentVNode$6("", true),
            _ctx.movie.lib ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_7$5, "✔已入库")) : _createCommentVNode$6("", true),
            _ctx.movie.downloaded && !_ctx.movie.lib ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_8$4, "✔已下载")) : _createCommentVNode$6("", true)
          ])
        ]),
        _createElementVNode$6("div", _hoisted_9$4, [
          _createElementVNode$6("div", _hoisted_10$4, _toDisplayString$6(number()), 1),
          _createElementVNode$6("div", _hoisted_11$3, [
            _createElementVNode$6("span", null, _toDisplayString$6(_ctx.movie.actor || "—"), 1),
            _createElementVNode$6("span", null, "🧲 " + _toDisplayString$6(_ctx.movie.magnets || 0), 1)
          ]),
          _createElementVNode$6("div", _hoisted_12$3, [
            _createElementVNode$6("span", null, _toDisplayString$6(_ctx.movie.date || ""), 1),
            _createElementVNode$6("span", null, _toDisplayString$6(durationText()), 1)
          ])
        ])
      ], 40, _hoisted_1$6);
    };
  }
});

const NumCard = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-bf2432e8"]]);

const {reactive,ref: ref$7} = await importShared('vue');
const rankCache = reactive(/* @__PURE__ */ new Map());
const periodState = ref$7("week");
const kindState = ref$7("censored");
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

const {defineComponent:_defineComponent$5} = await importShared('vue');

const {openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,createCommentVNode:_createCommentVNode$5,renderList:_renderList$4,Fragment:_Fragment$4,toDisplayString:_toDisplayString$5,normalizeClass:_normalizeClass$3,createElementVNode:_createElementVNode$5,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$5,withCtx:_withCtx$5,createBlock:_createBlock$5} = await importShared('vue');

const _hoisted_1$5 = { class: "avh-discover" };
const _hoisted_2$5 = {
  key: 0,
  class: "avh-discover__loading"
};
const _hoisted_3$4 = { class: "avh-discover__toolbar" };
const _hoisted_4$4 = { class: "avh-tabs" };
const _hoisted_5$4 = ["onClick"];
const _hoisted_6$4 = { class: "avh-tabs" };
const _hoisted_7$4 = ["onClick"];
const _hoisted_8$3 = {
  key: 0,
  class: "avh-discover__hint"
};
const _hoisted_9$3 = {
  key: 1,
  class: "avh-discover__loading"
};
const _hoisted_10$3 = {
  key: 3,
  class: "avh-discover__grid"
};
const {computed: computed$5,ref: ref$6,watch: watch$4} = await importShared('vue');
const _sfc_main$5 = /* @__PURE__ */ _defineComponent$5({
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
    const period = computed$5(() => periodState.value);
    const kind = computed$5(() => kindState.value);
    function pickPeriod(key) {
      periodState.value = key;
    }
    function pickKind(key) {
      kindState.value = key;
    }
    const booted = computed$5(() => props.store.booted.value === true);
    const bootError = computed$5(() => String(props.store.error.value || ""));
    const rankKey = computed$5(() => `rank:${period.value}:${kind.value}`);
    const entry = computed$5(() => rankCache.get(rankKey.value) || null);
    const movies = computed$5(() => entry.value && entry.value.data || []);
    const rankError = computed$5(() => String(entry.value && entry.value.error || ""));
    const inflight = /* @__PURE__ */ new Set();
    const retrying = ref$6(false);
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
      const _component_v_btn = _resolveComponent$5("v-btn");
      return _openBlock$5(), _createElementBlock$5("div", _hoisted_1$5, [
        !booted.value && !bootError.value ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_2$5, "正在读取插件状态…")) : (_openBlock$5(), _createElementBlock$5(_Fragment$4, { key: 1 }, [
          _createElementVNode$5("div", _hoisted_3$4, [
            _createElementVNode$5("div", _hoisted_4$4, [
              (_openBlock$5(), _createElementBlock$5(_Fragment$4, null, _renderList$4(PERIOD_TABS, (item) => {
                return _createElementVNode$5("button", {
                  key: item.key,
                  class: _normalizeClass$3({ "avh-tabs__on": item.key === period.value }),
                  onClick: ($event) => pickPeriod(item.key)
                }, _toDisplayString$5(item.name), 11, _hoisted_5$4);
              }), 64))
            ]),
            _createElementVNode$5("div", _hoisted_6$4, [
              (_openBlock$5(), _createElementBlock$5(_Fragment$4, null, _renderList$4(ZONE_TABS, (item) => {
                return _createElementVNode$5("button", {
                  key: item.key,
                  class: _normalizeClass$3({ "avh-tabs__on": item.key === kind.value }),
                  onClick: ($event) => pickKind(item.key)
                }, _toDisplayString$5(item.name), 11, _hoisted_7$4);
              }), 64))
            ]),
            !bootError.value && entry.value && entry.value.data ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_8$3, _toDisplayString$5(entry.value.data.length) + " 部 ", 1)) : _createCommentVNode$5("", true),
            _cache[1] || (_cache[1] = _createElementVNode$5("div", { class: "avh-discover__spacer" }, null, -1)),
            !bootError.value ? (_openBlock$5(), _createBlock$5(_component_v_btn, {
              key: 1,
              variant: "outlined",
              size: "small",
              onClick: reloadRank
            }, {
              default: _withCtx$5(() => _cache[0] || (_cache[0] = [
                _createTextVNode$4(" ↻ 重新抓取 ")
              ])),
              _: 1
            })) : _createCommentVNode$5("", true)
          ]),
          bootError.value ? (_openBlock$5(), _createBlock$5(ErrorState, {
            key: 0,
            message: `插件状态读取失败：${bootError.value}（仍可尝试直接抓取榜单）`,
            retrying: retrying.value,
            onRetry: retryRank
          }, null, 8, ["message", "retrying"])) : (_openBlock$5(), _createElementBlock$5(_Fragment$4, { key: 1 }, [
            rankError.value ? (_openBlock$5(), _createBlock$5(ErrorState, {
              key: 0,
              message: rankError.value,
              retrying: retrying.value,
              onRetry: retryRank
            }, null, 8, ["message", "retrying"])) : !entry.value ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_9$3, "正在抓取榜单…")) : !movies.value.length ? (_openBlock$5(), _createBlock$5(EmptyState, {
              key: 2,
              text: "该榜单暂无数据，换个周期 / 分类试试"
            })) : (_openBlock$5(), _createElementBlock$5("div", _hoisted_10$3, [
              (_openBlock$5(true), _createElementBlock$5(_Fragment$4, null, _renderList$4(movies.value, (movie, index) => {
                return _openBlock$5(), _createBlock$5(NumCard, {
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
        ], 64))
      ]);
    };
  }
});

const DiscoverView = /* @__PURE__ */ _export_sfc(_sfc_main$5, [["__scopeId", "data-v-29ff5987"]]);

const {defineComponent:_defineComponent$4} = await importShared('vue');

const {createElementVNode:_createElementVNode$4,toDisplayString:_toDisplayString$4,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$4,resolveComponent:_resolveComponent$4,withKeys:_withKeys$1,withCtx:_withCtx$4,createBlock:_createBlock$4} = await importShared('vue');

const _hoisted_1$4 = ["src"];
const _hoisted_2$4 = { class: "avh-lb__ctr" };
const {onBeforeUnmount: onBeforeUnmount$3,onMounted: onMounted$3,ref: ref$5} = await importShared('vue');

const _sfc_main$4 = /* @__PURE__ */ _defineComponent$4({
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
      const _component_v_overlay = _resolveComponent$4("v-overlay");
      return _openBlock$4(), _createBlock$4(_component_v_overlay, {
        modelValue: open.value,
        "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => open.value = $event),
        "z-index": 3e3,
        class: "avh-lb-overlay",
        onKeydown: _withKeys$1(close, ["esc"])
      }, {
        default: _withCtx$4(() => [
          open.value ? (_openBlock$4(), _createElementBlock$4("div", {
            key: 0,
            class: "avh-lb",
            onClick: onBackdrop
          }, [
            _createElementVNode$4("img", {
              class: "avh-lb__img",
              src: list.value[idx.value] || "",
              alt: "",
              onError: onImgError
            }, null, 40, _hoisted_1$4),
            _createElementVNode$4("div", {
              class: "avh-lb__nav avh-lb__prev",
              role: "button",
              "aria-label": "上一张",
              onClick: _cache[0] || (_cache[0] = ($event) => step(-1))
            }, "‹"),
            _createElementVNode$4("div", {
              class: "avh-lb__nav avh-lb__next",
              role: "button",
              "aria-label": "下一张",
              onClick: _cache[1] || (_cache[1] = ($event) => step(1))
            }, "›"),
            _createElementVNode$4("div", _hoisted_2$4, _toDisplayString$4(idx.value + 1) + " / " + _toDisplayString$4(list.value.length) + _toDisplayString$4(failed.value ? "（图片加载失败）" : ""), 1),
            _createElementVNode$4("div", {
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

const Lightbox = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-174e2165"]]);

const {defineComponent:_defineComponent$3} = await importShared('vue');

const {toDisplayString:_toDisplayString$3,createElementVNode:_createElementVNode$3,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$3,withCtx:_withCtx$3,openBlock:_openBlock$3,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$3,createVNode:_createVNode$3,createElementBlock:_createElementBlock$3,Fragment:_Fragment$3,renderList:_renderList$3,normalizeClass:_normalizeClass$2,normalizeStyle:_normalizeStyle} = await importShared('vue');

const _hoisted_1$3 = { class: "avh-detail__head" };
const _hoisted_2$3 = { class: "avh-detail__title" };
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
const _hoisted_15$1 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_16$1 = { class: "avh-kv" };
const _hoisted_17$1 = {
  key: 0,
  style: { "color": "rgb(var(--v-theme-success))" }
};
const _hoisted_18$1 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_19$1 = { key: 0 };
const _hoisted_20$1 = { key: 1 };
const _hoisted_21 = { class: "avh-acts" };
const _hoisted_22 = { class: "avh-secttl" };
const _hoisted_23 = { class: "avh-shots" };
const _hoisted_24 = ["onClick"];
const _hoisted_25 = {
  key: 0,
  class: "avh-shot__noimg"
};
const _hoisted_26 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_27 = { class: "avh-secttl" };
const _hoisted_28 = { key: 0 };
const _hoisted_29 = { class: "avh-mag__mg" };
const _hoisted_30 = { class: "avh-mag__mn" };
const _hoisted_31 = { class: "avh-mag__mh" };
const _hoisted_32 = {
  key: 0,
  class: "avh-tag avh-tag--pref"
};
const _hoisted_33 = {
  key: 1,
  class: "avh-tag"
};
const _hoisted_34 = {
  key: 0,
  class: "avh-mag__mh avh-mag__mh--link"
};
const _hoisted_35 = ["href"];
const _hoisted_36 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_37 = { class: "avh-longwrap" };
const _hoisted_38 = {
  key: 0,
  class: "avh-longerr"
};
const _hoisted_39 = {
  key: 0,
  class: "avh-longerr__url"
};
const _hoisted_40 = { class: "avh-longerr__act" };
const _hoisted_41 = ["src"];
const _hoisted_42 = {
  key: 2,
  class: "avh-hint"
};
const _hoisted_43 = {
  key: 2,
  class: "avh-hero"
};
const _hoisted_44 = { class: "avh-hero__big" };
const _hoisted_45 = {
  key: 1,
  class: "avh-hint"
};
const _hoisted_46 = { class: "avh-hero__info" };
const _hoisted_47 = { class: "avh-hero__num" };
const _hoisted_48 = { class: "avh-kv" };
const _hoisted_49 = { key: 0 };
const _hoisted_50 = { key: 1 };
const {computed: computed$4,nextTick: nextTick$1,onBeforeUnmount: onBeforeUnmount$2,onMounted: onMounted$2,ref: ref$4,watch: watch$3} = await importShared('vue');
const _sfc_main$3 = /* @__PURE__ */ _defineComponent$3({
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
          avatar: String(item?.avatar || "")
        }));
      }
      const single = String(movie.value.actor || "");
      if (single) {
        return [{ name: single, zh: "", avatar: String(movie.value.actor_avatar || "") }];
      }
      return [];
    });
    const title = computed$4(() => `影片详情 · ${activeNumber.value}`);
    function scrollTopIfFresh() {
      if (freshNumber !== activeNumber.value) return;
      freshNumber = "";
      const el = bodyEl.value;
      if (el) el.scrollTop = 0;
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
    async function ptSearch() {
      const number = num.value;
      if (!number || ptSearching.value) return;
      ptSearching.value = true;
      try {
        const res = await props.store.searchKeyword(number, null, {
          actor: String(movie.value.actor || ""),
          thumb: String(movie.value.thumb || "")
        });
        if (!res.ok) {
          t.warning("搜种失败");
          t.info(res.message || "抓取失败，请稍后重试");
          return;
        }
        const task = res.data || {};
        const cands = Array.isArray(task.cands) ? task.cands : [];
        t.success(String(task.number || number));
        t.info(cands.length ? "已搜索完成" : "没有找到候选");
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
    const longProxySrc = computed$4(() => {
      const raw = String(long.value?.url || "");
      if (!raw || !props.pluginId) return "";
      return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`;
    });
    const longSrcAttr = computed$4(() => longUseProxy.value ? longProxySrc.value : longSrc.value);
    const longImgKey = computed$4(() => `${longUseProxy.value ? "p" : "d"}#${longSrc.value}`);
    function paintLong(url) {
      const src = String(url || "");
      if (!src) return;
      longSrc.value = src;
      longUseProxy.value = false;
      longError.value = null;
    }
    function longFail(text) {
      longError.value = text;
    }
    const longHint = computed$4(() => {
      const state = long.value;
      if (longError.value && !longSrc.value && !(state && state.loading)) return "";
      if (longSrc.value) return "⏳ 正在加载长缩略图…";
      return "⏳ 正在获取长缩略图…";
    });
    function onLongError() {
      if (!longUseProxy.value && longProxySrc.value) {
        longUseProxy.value = true;
        return;
      }
      longFail("长缩略图加载失败：浏览器直连与插件代理都没取到。");
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
        longSrc.value = "";
        longUseProxy.value = false;
        longError.value = null;
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
    async function reloadDetail() {
      await retryDetail();
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
      const _component_v_btn = _resolveComponent$3("v-btn");
      const _component_v_navigation_drawer = _resolveComponent$3("v-navigation-drawer");
      return _openBlock$3(), _createBlock$3(_component_v_navigation_drawer, {
        "model-value": _ctx.open,
        location: "right",
        temporary: "",
        "disable-resize-watcher": "",
        width: 1080,
        class: "avh-detail",
        "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => {
          if (!value) emit("close");
        })
      }, {
        default: _withCtx$3(() => [
          _createElementVNode$3("div", _hoisted_1$3, [
            _createElementVNode$3("b", _hoisted_2$3, _toDisplayString$3(title.value), 1),
            _cache[4] || (_cache[4] = _createElementVNode$3("div", { class: "avh-detail__spacer" }, null, -1)),
            activeNumber.value ? (_openBlock$3(), _createBlock$3(_component_v_btn, {
              key: 0,
              variant: "outlined",
              size: "small",
              onClick: reloadDetail
            }, {
              default: _withCtx$3(() => _cache[2] || (_cache[2] = [
                _createTextVNode$3("↻ 重新抓取")
              ])),
              _: 1
            })) : _createCommentVNode$3("", true),
            _createVNode$3(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
            }, {
              default: _withCtx$3(() => _cache[3] || (_cache[3] = [
                _createTextVNode$3("关闭")
              ])),
              _: 1
            })
          ]),
          _createElementVNode$3("div", {
            ref_key: "bodyEl",
            ref: bodyEl,
            class: "avh-detail__body"
          }, [
            hasDetail.value ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
              _createElementVNode$3("div", _hoisted_3$3, [
                _createElementVNode$3("div", _hoisted_4$3, [
                  coverSrc.value ? (_openBlock$3(), _createElementBlock$3("img", {
                    key: 0,
                    src: coverSrc.value,
                    alt: num.value,
                    referrerpolicy: "no-referrer",
                    decoding: "async",
                    onError: onCoverError,
                    onClick: openCover
                  }, null, 40, _hoisted_5$3)) : (_openBlock$3(), _createElementBlock$3("div", _hoisted_6$3, "后端未返回封面（/img 代理可能不可用）"))
                ]),
                _createElementVNode$3("div", _hoisted_7$3, [
                  _createElementVNode$3("h2", _hoisted_8$2, _toDisplayString$3(num.value), 1),
                  movie.value.lib ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_9$2, [
                    _cache[6] || (_cache[6] = _createTextVNode$3(" ✅ 已在 Emby 库中 ")),
                    movie.value.lib.url ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                      _cache[5] || (_cache[5] = _createTextVNode$3(" · ")),
                      _createElementVNode$3("a", {
                        href: String(movie.value.lib.url),
                        target: "_blank",
                        rel: "noopener"
                      }, "在 Emby 中打开 ↗", 8, _hoisted_10$2)
                    ], 64)) : _createCommentVNode$3("", true)
                  ])) : _createCommentVNode$3("", true),
                  movie.value.downloaded && !movie.value.lib ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_11$2, _cache[7] || (_cache[7] = [
                    _createTextVNode$3(" ✔ 已下载 "),
                    _createElementVNode$3("span", { class: "avh-hint" }, "下载台账里有这个番号（文件可能已不在库）", -1)
                  ]))) : _createCommentVNode$3("", true),
                  movie.value.title ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_12$2, _toDisplayString$3(movie.value.title), 1)) : _createCommentVNode$3("", true),
                  _createElementVNode$3("div", _hoisted_13$2, [
                    actorChips.value.length ? (_openBlock$3(true), _createElementBlock$3(_Fragment$3, { key: 0 }, _renderList$3(actorChips.value, (actor, index) => {
                      return _openBlock$3(), _createElementBlock$3("div", {
                        key: `${actor.name}#${index}`,
                        class: "avh-actorchip",
                        title: actor.name,
                        onClick: ($event) => pickActor(actor.name)
                      }, [
                        _createVNode$3(Thumb, {
                          class: "avh-actorchip__av",
                          variant: "av",
                          src: actor.avatar,
                          alt: actor.name,
                          "plugin-id": _ctx.pluginId
                        }, null, 8, ["src", "alt", "plugin-id"]),
                        _createElementVNode$3("span", null, _toDisplayString$3(actor.name) + _toDisplayString$3(actor.zh ? ` / ${actor.zh}` : ""), 1),
                        _cache[8] || (_cache[8] = _createElementVNode$3("span", { class: "avh-hint" }, "看全部作品 ›", -1))
                      ], 8, _hoisted_14$2);
                    }), 128)) : (_openBlock$3(), _createElementBlock$3("span", _hoisted_15$1, "未识别到演员"))
                  ]),
                  _createElementVNode$3("div", _hoisted_16$1, [
                    _createElementVNode$3("span", null, [
                      _cache[9] || (_cache[9] = _createElementVNode$3("b", null, "发行", -1)),
                      _createTextVNode$3(" " + _toDisplayString$3(movie.value.date || "—"), 1)
                    ]),
                    _createElementVNode$3("span", null, [
                      _cache[10] || (_cache[10] = _createElementVNode$3("b", null, "时长", -1)),
                      _createTextVNode$3(" " + _toDisplayString$3(movie.value.duration || "—") + " 分钟", 1)
                    ]),
                    _createElementVNode$3("span", null, [
                      _cache[11] || (_cache[11] = _createElementVNode$3("b", null, "中文字幕", -1)),
                      movie.value.cnsub ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_17$1, "有")) : (_openBlock$3(), _createElementBlock$3("span", _hoisted_18$1, "无"))
                    ]),
                    _createElementVNode$3("span", null, [
                      _cache[12] || (_cache[12] = _createElementVNode$3("b", null, "磁力", -1)),
                      _createTextVNode$3(" " + _toDisplayString$3(movie.value.magnets || magnets.value.length || 0) + " 个", 1)
                    ]),
                    movie.value.maker ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_19$1, [
                      _cache[13] || (_cache[13] = _createElementVNode$3("b", null, "片商", -1)),
                      _createTextVNode$3(" " + _toDisplayString$3(movie.value.maker), 1)
                    ])) : _createCommentVNode$3("", true),
                    movie.value.score ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_20$1, [
                      _cache[14] || (_cache[14] = _createElementVNode$3("b", null, "评分", -1)),
                      _createTextVNode$3(" " + _toDisplayString$3(movie.value.score), 1)
                    ])) : _createCommentVNode$3("", true)
                  ]),
                  _createElementVNode$3("div", _hoisted_21, [
                    _createVNode$3(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      size: "small",
                      loading: ptSearching.value,
                      onClick: ptSearch
                    }, {
                      default: _withCtx$3(() => _cache[15] || (_cache[15] = [
                        _createTextVNode$3(" 🔎 搜索 PT 站 ")
                      ])),
                      _: 1
                    }, 8, ["loading"]),
                    _createVNode$3(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      loading: subscribing.value,
                      onClick: subscribeNumber
                    }, {
                      default: _withCtx$3(() => _cache[16] || (_cache[16] = [
                        _createTextVNode$3(" 📌 订阅这个番号 ")
                      ])),
                      _: 1
                    }, 8, ["loading"]),
                    movie.value.actor ? (_openBlock$3(), _createBlock$3(_component_v_btn, {
                      key: 0,
                      variant: "outlined",
                      size: "small",
                      loading: favBusy.value,
                      onClick: toggleFav
                    }, {
                      default: _withCtx$3(() => [
                        _createTextVNode$3(_toDisplayString$3(faved.value ? "★ 已收藏" : "☆ 收藏该演员"), 1)
                      ]),
                      _: 1
                    }, 8, ["loading"])) : _createCommentVNode$3("", true)
                  ])
                ])
              ]),
              _createElementVNode$3("div", _hoisted_22, "预览图（" + _toDisplayString$3(previews.value.length) + " 张）", 1),
              _createElementVNode$3("div", _hoisted_23, [
                previews.value.length ? (_openBlock$3(true), _createElementBlock$3(_Fragment$3, { key: 0 }, _renderList$3(previews.value, (shot, index) => {
                  return _openBlock$3(), _createElementBlock$3("div", {
                    key: `${index}#${String(shot).slice(-24)}`,
                    class: _normalizeClass$2(["avh-shot", { "avh-shot--blur": !!shot }]),
                    style: _normalizeStyle(shotStyle(shot)),
                    onClick: ($event) => openShot(index)
                  }, [
                    _createVNode$3(Thumb, {
                      variant: "plain",
                      src: shot,
                      alt: "预览图",
                      "plugin-id": _ctx.pluginId
                    }, null, 8, ["src", "plugin-id"]),
                    !shot ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_25, "预览图加载失败")) : _createCommentVNode$3("", true)
                  ], 14, _hoisted_24);
                }), 128)) : (_openBlock$3(), _createElementBlock$3("span", _hoisted_26, "该片没有预览图"))
              ]),
              _createElementVNode$3("div", _hoisted_27, "磁力链接（" + _toDisplayString$3(magnets.value.length) + " 条）", 1),
              magnets.value.length ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_28, [
                (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(magnets.value, (magnet, index) => {
                  return _openBlock$3(), _createElementBlock$3("div", {
                    key: `${magnet.hash}#${index}`,
                    class: "avh-mag"
                  }, [
                    _createElementVNode$3("div", _hoisted_29, [
                      _createElementVNode$3("div", _hoisted_30, _toDisplayString$3(magnet.name || magnet.hash || "未命名"), 1),
                      _createElementVNode$3("div", _hoisted_31, [
                        _createElementVNode$3("span", {
                          class: _normalizeClass$2(["avh-tag", { "avh-tag--on": !!magnet.cnsub }])
                        }, _toDisplayString$3(magnet.cnsub ? "中字" : "无中字"), 3),
                        magnet.hd ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_32, "高清")) : _createCommentVNode$3("", true),
                        magnet.size ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_33, _toDisplayString$3(magnet.size), 1)) : _createCommentVNode$3("", true)
                      ]),
                      magnetUri(String(magnet.hash || "")) ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_34, [
                        _createElementVNode$3("a", {
                          href: magnetUri(String(magnet.hash || "")),
                          title: "用系统下载器打开",
                          class: "avh-mag__hash"
                        }, _toDisplayString$3(magnet.hash), 9, _hoisted_35)
                      ])) : _createCommentVNode$3("", true)
                    ]),
                    _createVNode$3(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      disabled: (dlState.value[String(magnet.hash || "")] || "idle") !== "idle",
                      onClick: ($event) => downloadMagnet(magnet)
                    }, {
                      default: _withCtx$3(() => [
                        _createTextVNode$3(_toDisplayString$3(dlLabel(String(magnet.hash || ""))), 1)
                      ]),
                      _: 2
                    }, 1032, ["disabled", "onClick"])
                  ]);
                }), 128))
              ])) : (_openBlock$3(), _createElementBlock$3("div", _hoisted_36, "没有磁力链接")),
              _createElementVNode$3("div", _hoisted_37, [
                longError.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_38, [
                  _createTextVNode$3(_toDisplayString$3(longError.value) + " ", 1),
                  longSrc.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_39, _toDisplayString$3(longSrcAttr.value || longSrc.value), 1)) : _createCommentVNode$3("", true),
                  _createElementVNode$3("div", _hoisted_40, [
                    _createVNode$3(_component_v_btn, {
                      variant: "outlined",
                      size: "small",
                      onClick: retryLong
                    }, {
                      default: _withCtx$3(() => _cache[17] || (_cache[17] = [
                        _createTextVNode$3("重试")
                      ])),
                      _: 1
                    })
                  ])
                ])) : longSrc.value ? (_openBlock$3(), _createElementBlock$3("img", {
                  key: longImgKey.value,
                  class: "avh-longimg",
                  src: longSrcAttr.value,
                  alt: "长缩略图",
                  referrerpolicy: "no-referrer",
                  decoding: "async",
                  onLoad: onLongLoad,
                  onError: onLongError,
                  onClick: openLong
                }, null, 40, _hoisted_41)) : longHint.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_42, _toDisplayString$3(longHint.value), 1)) : _createCommentVNode$3("", true)
              ])
            ], 64)) : detailError.value ? (_openBlock$3(), _createBlock$3(ErrorState, {
              key: 1,
              message: detailError.value,
              retrying: retrying.value,
              onRetry: retryDetail
            }, null, 8, ["message", "retrying"])) : (_openBlock$3(), _createElementBlock$3("div", _hoisted_43, [
              _createElementVNode$3("div", _hoisted_44, [
                skeletonMovie.value.cover ? (_openBlock$3(), _createBlock$3(Thumb, {
                  key: 0,
                  variant: "plain",
                  src: skeletonMovie.value.cover,
                  alt: activeNumber.value,
                  "plugin-id": _ctx.pluginId,
                  lazy: false
                }, null, 8, ["src", "alt", "plugin-id"])) : (_openBlock$3(), _createElementBlock$3("div", _hoisted_45, "正在获取封面…"))
              ]),
              _createElementVNode$3("div", _hoisted_46, [
                _createElementVNode$3("h2", _hoisted_47, _toDisplayString$3(activeNumber.value), 1),
                _createElementVNode$3("div", _hoisted_48, [
                  skeletonMovie.value.date ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_49, [
                    _cache[18] || (_cache[18] = _createElementVNode$3("b", null, "发行", -1)),
                    _createTextVNode$3(" " + _toDisplayString$3(skeletonMovie.value.date), 1)
                  ])) : _createCommentVNode$3("", true),
                  skeletonMovie.value.actor ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_50, [
                    _cache[19] || (_cache[19] = _createElementVNode$3("b", null, "演员", -1)),
                    _createTextVNode$3(" " + _toDisplayString$3(skeletonMovie.value.actor), 1)
                  ])) : _createCommentVNode$3("", true)
                ]),
                _cache[20] || (_cache[20] = _createElementVNode$3("div", { class: "avh-hint avh-skeleton__tip" }, "⏳ 正在抓取影片详情（预览图与磁力随后填充）…", -1))
              ])
            ])),
            !activeNumber.value ? (_openBlock$3(), _createBlock$3(EmptyState, {
              key: 3,
              text: "没有指定番号"
            })) : _createCommentVNode$3("", true)
          ], 512),
          _createVNode$3(Lightbox, {
            ref_key: "lightbox",
            ref: lightbox
          }, null, 512)
        ]),
        _: 1
      }, 8, ["model-value"]);
    };
  }
});

const DetailDrawer = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-c3418b85"]]);

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {createElementVNode:_createElementVNode$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,toDisplayString:_toDisplayString$2,createCommentVNode:_createCommentVNode$2,createBlock:_createBlock$2,normalizeClass:_normalizeClass$1} = await importShared('vue');

const _hoisted_1$2 = { class: "avh-notify__head" };
const _hoisted_2$2 = { class: "avh-notify__bub" };
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
const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
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
      const _component_v_btn = _resolveComponent$2("v-btn");
      const _component_v_navigation_drawer = _resolveComponent$2("v-navigation-drawer");
      return _openBlock$2(), _createBlock$2(_component_v_navigation_drawer, {
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
        default: _withCtx$2(() => [
          _createElementVNode$2("div", _hoisted_1$2, [
            _cache[4] || (_cache[4] = _createElementVNode$2("b", { class: "avh-notify__title" }, "🔔 通知", -1)),
            _cache[5] || (_cache[5] = _createElementVNode$2("div", { class: "avh-notify__spacer" }, null, -1)),
            _createVNode$2(_component_v_btn, {
              variant: "outlined",
              size: "small",
              disabled: !rows.value.length,
              loading: _ctx.clearing,
              onClick: askClear
            }, {
              default: _withCtx$2(() => _cache[2] || (_cache[2] = [
                _createTextVNode$2("清空")
              ])),
              _: 1
            }, 8, ["disabled", "loading"]),
            _createVNode$2(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
            }, {
              default: _withCtx$2(() => _cache[3] || (_cache[3] = [
                _createTextVNode$2("关闭")
              ])),
              _: 1
            })
          ]),
          _createElementVNode$2("div", {
            ref_key: "bodyEl",
            ref: bodyEl,
            class: "avh-notify__body"
          }, [
            rows.value.length ? (_openBlock$2(true), _createElementBlock$2(_Fragment$2, { key: 0 }, _renderList$2(rows.value, (row) => {
              return _openBlock$2(), _createElementBlock$2("div", {
                key: row.key,
                class: _normalizeClass$1(["avh-notify__msg", row.kind ? `avh-notify__msg--${row.kind}` : ""])
              }, [
                _cache[6] || (_cache[6] = _createElementVNode$2("div", { class: "avh-notify__ico" }, "🤖", -1)),
                _createElementVNode$2("div", _hoisted_2$2, [
                  _createElementVNode$2("div", _hoisted_3$2, _toDisplayString$2(row.head), 1),
                  row.item.title ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_4$2, _toDisplayString$2(row.item.title), 1)) : _createCommentVNode$2("", true),
                  _createElementVNode$2("div", _hoisted_5$2, _toDisplayString$2(row.item.body || ""), 1),
                  row.item.meta ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_6$2, _toDisplayString$2(row.item.meta), 1)) : _createCommentVNode$2("", true),
                  row.item.image ? (_openBlock$2(), _createBlock$2(Thumb, {
                    key: 2,
                    class: "avh-notify__img",
                    variant: "plain",
                    src: row.item.image,
                    alt: "主图加载失败",
                    "plugin-id": _ctx.pluginId,
                    lazy: false
                  }, null, 8, ["src", "plugin-id"])) : _createCommentVNode$2("", true),
                  _createElementVNode$2("div", _hoisted_7$2, _toDisplayString$2(row.time), 1)
                ])
              ], 2);
            }), 128)) : (_openBlock$2(), _createBlock$2(EmptyState, {
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

const NotifyDrawer = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-0a21181e"]]);

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,withCtx:_withCtx$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,createBlock:_createBlock$1,renderList:_renderList$1,Fragment:_Fragment$1,createTextVNode:_createTextVNode$1} = await importShared('vue');

const _hoisted_1$1 = { class: "avh-search__title" };
const _hoisted_2$1 = {
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
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
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
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_card_title = _resolveComponent$1("v-card-title");
      const _component_v_card_text = _resolveComponent$1("v-card-text");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_card_actions = _resolveComponent$1("v-card-actions");
      const _component_v_card = _resolveComponent$1("v-card");
      const _component_v_dialog = _resolveComponent$1("v-dialog");
      return _openBlock$1(), _createBlock$1(_component_v_dialog, {
        "model-value": _ctx.open,
        "max-width": "920",
        scrollable: "",
        attach: "body",
        "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => {
          if (!value) emit("close");
        })
      }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_v_card, null, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_v_card_title, { class: "d-flex align-center" }, {
                default: _withCtx$1(() => [
                  _createElementVNode$1("span", _hoisted_1$1, _toDisplayString$1(title.value), 1),
                  _createVNode$1(_component_v_spacer)
                ]),
                _: 1
              }),
              _createVNode$1(_component_v_card_text, null, {
                default: _withCtx$1(() => [
                  loading.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, "正在搜索…")) : error.value ? (_openBlock$1(), _createBlock$1(ErrorState, {
                    key: 1,
                    message: error.value,
                    retrying: loading.value,
                    onRetry: retry
                  }, null, 8, ["message", "retrying"])) : (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 2 }, [
                    actors.value.length ? (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 0 }, [
                      _cache[2] || (_cache[2] = _createElementVNode$1("div", { class: "avh-search__secttl avh-hint" }, "演员", -1)),
                      _createElementVNode$1("div", _hoisted_3$1, [
                        (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(actors.value, (actor) => {
                          return _openBlock$1(), _createBlock$1(ActorRow, {
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
                    searched.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_4$1, "影片")) : _createCommentVNode$1("", true),
                    (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(movies.value, (movie, index) => {
                      return _openBlock$1(), _createElementBlock$1("div", {
                        key: `${movie.number}#${index}`,
                        class: "avh-searchrow",
                        title: movie.title || movie.number || "",
                        onClick: ($event) => pickMovie(movie)
                      }, [
                        _createElementVNode$1("div", _hoisted_6$1, [
                          _createVNode$1(Thumb, {
                            variant: "mini",
                            src: movie.thumb,
                            alt: String(movie.number || ""),
                            "plugin-id": _ctx.pluginId
                          }, null, 8, ["src", "alt", "plugin-id"])
                        ]),
                        _createElementVNode$1("div", _hoisted_7$1, [
                          _createElementVNode$1("div", _hoisted_8$1, _toDisplayString$1(movie.number), 1),
                          _createElementVNode$1("div", _hoisted_9$1, [
                            _createElementVNode$1("span", null, _toDisplayString$1(movie.actor || "—") + " · " + _toDisplayString$1(movie.date || "") + " · 🧲 " + _toDisplayString$1(movie.magnets || 0), 1),
                            movie.cnsub ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_10$1, "中字")) : _createCommentVNode$1("", true),
                            movie.uncensored ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_11$1, "破解")) : _createCommentVNode$1("", true),
                            movie.lib ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_12$1, "已入库")) : _createCommentVNode$1("", true)
                          ]),
                          _createElementVNode$1("div", _hoisted_13$1, _toDisplayString$1(titleText(movie)), 1)
                        ]),
                        _cache[3] || (_cache[3] = _createElementVNode$1("span", { class: "avh-hint" }, "查看 ›", -1))
                      ], 8, _hoisted_5$1);
                    }), 128)),
                    searched.value && !movies.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_14$1, "没有匹配的影片")) : _createCommentVNode$1("", true),
                    !searched.value ? (_openBlock$1(), _createBlock$1(EmptyState, {
                      key: 3,
                      text: "输入番号或演员名后点「搜索」"
                    })) : _createCommentVNode$1("", true)
                  ], 64))
                ]),
                _: 1
              }),
              _createVNode$1(_component_v_card_actions, null, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_v_spacer),
                  _createVNode$1(_component_v_btn, {
                    color: "error",
                    variant: "outlined",
                    onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
                  }, {
                    default: _withCtx$1(() => _cache[4] || (_cache[4] = [
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

const SearchDialog = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-955b3a36"]]);

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
function usePluginStore(api) {
  const client = api && typeof api.get === "function" ? api : NOOP_API;
  const enabled = ref$1(true);
  const sites = ref$1([]);
  const favs = ref$1([]);
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
  const downloading = computed$1(() => queue.value.filter((item) => item.state !== "done").length);
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
  function subscribeNumber(name, kind = "number", actor = "", rule2) {
    return guarded("subscribe", async () => {
      const target = String(name ?? "").trim();
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
  function startDownload(taskId, site, force = false) {
    return guarded("download", async () => {
      const id = String(taskId ?? "").trim();
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
    return guarded("magnet", async () => {
      const digest = String(hash ?? "").trim();
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
    return guarded("cancel", async () => {
      const id = String(taskId ?? "").trim();
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
    subscribeNumber,
    searchKeyword,
    startDownload,
    cancelTask,
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
      { key: "subs", title: "订阅", icon: "mdi-rss" },
      { key: "tasks", title: "任务", icon: "mdi-clipboard-list" },
      { key: "downloads", title: "下载", icon: "mdi-download" },
      // 「下载历史」紧挨「下载」：前者只留下载中，完成的番号落到台账后由这一栏兜底（删了文件也还在）
      { key: "history", title: "下载历史", icon: "mdi-history" },
      { key: "sitesearch", title: "站点搜索", icon: "mdi-magnify" }
    ];
    const pluginId = computed(() => props.pluginId || props.sourcePluginId || "");
    const NATIVE_VIEWS = {
      discover: DiscoverView,
      sitesearch: SiteSearchView,
      downloads: DownloadsView,
      history: HistoryView,
      tasks: TasksView,
      subs: SubsView,
      actors: ActorsView
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
    function pick(item) {
      section.value = item.key;
    }
    function pickSetting(item) {
      settingsSection.value = item.key;
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
      if (pending && SETTINGS_SECTIONS.some((item) => item.key === pending)) settingsSection.value = pending;
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
                  _cache[14] || (_cache[14] = _createElementVNode("span", { class: "text-h6" }, "AV 资源助手", -1)),
                  version.value ? (_openBlock(), _createElementBlock("span", _hoisted_3, "v" + _toDisplayString(version.value), 1)) : _createCommentVNode("", true),
                  _unref(overview).enabled === false ? (_openBlock(), _createBlock(_component_v_chip, {
                    key: 1,
                    size: "x-small",
                    color: "warning",
                    variant: "tonal"
                  }, {
                    default: _withCtx(() => _cache[13] || (_cache[13] = [
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
                default: _withCtx(() => _cache[15] || (_cache[15] = [
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
                  _cache[16] || (_cache[16] = _createTextVNode(" 🔔 通知 ")),
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
                default: _withCtx(() => _cache[17] || (_cache[17] = [
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
                    default: _withCtx(() => _cache[18] || (_cache[18] = [
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
                        default: _withCtx(() => _cache[19] || (_cache[19] = [
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
                                default: _withCtx(() => _cache[20] || (_cache[20] = [
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
                                default: _withCtx(() => _cache[21] || (_cache[21] = [
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
                                default: _withCtx(() => _cache[22] || (_cache[22] = [
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
                                default: _withCtx(() => _cache[23] || (_cache[23] = [
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
                                default: _withCtx(() => _cache[24] || (_cache[24] = [
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
                                default: _withCtx(() => _cache[25] || (_cache[25] = [
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
                                default: _withCtx(() => _cache[26] || (_cache[26] = [
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
                        default: _withCtx(() => _cache[27] || (_cache[27] = [
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
              default: _withCtx(() => _cache[28] || (_cache[28] = [
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
              default: _withCtx(() => _cache[29] || (_cache[29] = [
                _createTextVNode(" 宿主没有传入 pluginId，无法定位内嵌应用。 ")
              ])),
              _: 1
            }))
          ])
        ]),
        _createVNode(_component_v_dialog, {
          modelValue: settingsOpen.value,
          "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => settingsOpen.value = $event),
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
                      default: _withCtx(() => _cache[30] || (_cache[30] = [
                        _createTextVNode("设置")
                      ])),
                      _: 1
                    }),
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      color: _unref(dirty) ? "warning" : "primary",
                      variant: _unref(dirty) ? "flat" : "tonal",
                      "prepend-icon": "mdi-content-save",
                      loading: _unref(draftSaving),
                      class: "me-2",
                      onClick: saveAll
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(_unref(saveButtonLabel)), 1)
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
                              _unref(sectionDirty)(item.key) ? (_openBlock(), _createBlock(_component_v_icon, {
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
                    }, null, 8, ["rule", "policy-min-interval", "site-scope-count"])) : settingsSection.value === "notify" ? (_openBlock(), _createBlock(NotifyPanel, {
                      key: 5,
                      notices: _unref(notices),
                      loading: _unref(noticeLoading),
                      clearing: noticeClearing.value,
                      onClear: clearNotices,
                      onReload: _unref(loadNotices)
                    }, null, 8, ["notices", "loading", "clearing", "onReload"])) : settingsSection.value === "library" ? (_openBlock(), _createBlock(LibraryPanel, {
                      key: 6,
                      config: _unref(hostConfig),
                      validation: _unref(validation),
                      onPatch: _cache[6] || (_cache[6] = (patch) => Object.assign(_unref(hostConfig), patch))
                    }, null, 8, ["config", "validation"])) : settingsSection.value === "runtime" ? (_openBlock(), _createBlock(RuntimePanel, {
                      key: 7,
                      "cache-text": _unref(cacheText),
                      check: _unref(checkInfo),
                      cleaning: _unref(cacheCleaning),
                      loading: _unref(runtimeLoading),
                      onClean: cleanCache,
                      onRefresh: _cache[7] || (_cache[7] = ($event) => _unref(refreshRuntime)(true))
                    }, null, 8, ["cache-text", "check", "cleaning", "loading"])) : settingsSection.value === "about" ? (_openBlock(), _createBlock(AboutPanel, {
                      key: 8,
                      version: version.value,
                      "plugin-id": props.pluginId,
                      "source-plugin-id": props.sourcePluginId
                    }, null, 8, ["version", "plugin-id", "source-plugin-id"])) : (_openBlock(), _createBlock(_component_v_alert, {
                      key: 9,
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
          onClose: _cache[9] || (_cache[9] = ($event) => drawerOpen.value = false),
          onOpenActor: openActorFromOverlay,
          onRefreshSide: _cache[10] || (_cache[10] = ($event) => _unref(refreshRuntime)(true))
        }, null, 8, ["open", "number", "id", "store", "plugin-id", "api", "toast"])) : _createCommentVNode("", true),
        framePluginId.value ? (_openBlock(), _createBlock(SearchDialog, {
          key: 1,
          ref_key: "searchDialog",
          ref: searchDialog,
          open: searchOpen.value,
          "plugin-id": framePluginId.value,
          api: currentApi(),
          onClose: _cache[11] || (_cache[11] = ($event) => searchOpen.value = false),
          onOpenMovie: onSearchPickMovie,
          onOpenActor: openActorFromOverlay
        }, null, 8, ["open", "plugin-id", "api"])) : _createCommentVNode("", true),
        _createVNode(NotifyDrawer, {
          open: notifyOpen.value,
          notices: _unref(store).notices.value,
          "plugin-id": framePluginId.value,
          clearing: noticeClearing.value,
          onClose: _cache[12] || (_cache[12] = ($event) => notifyOpen.value = false),
          onClear: clearNoticesFromDrawer
        }, null, 8, ["open", "notices", "plugin-id", "clearing"])
      ]);
    };
  }
});

const Console = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-0d252e25"]]);

export { CONSOLE_EMIT_NAMES as C, Console as a };
