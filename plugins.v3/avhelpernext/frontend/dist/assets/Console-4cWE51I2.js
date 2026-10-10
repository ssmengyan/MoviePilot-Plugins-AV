import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {defineComponent:_defineComponent$d} = await importShared('vue');

const {openBlock:_openBlock$d,createElementBlock:_createElementBlock$c} = await importShared('vue');

const _hoisted_1$c = ["src"];
const {computed: computed$a} = await importShared('vue');

const _sfc_main$d = /* @__PURE__ */ _defineComponent$d({
  __name: "AppFrame",
  props: {
    pluginId: {},
    version: { default: "" },
    sectionKey: { default: "discover" }
  },
  setup(__props) {
    const props = __props;
    const src = computed$a(() => {
      const params = new URLSearchParams();
      if (props.version) params.set("v", props.version);
      if (props.sectionKey) params.set("view", props.sectionKey);
      const query = params.toString();
      return `/api/v1/plugin/${props.pluginId}/ui/${query ? `?${query}` : ""}`;
    });
    return (_ctx, _cache) => {
      return _openBlock$d(), _createElementBlock$c("iframe", {
        key: `${_ctx.pluginId}:${_ctx.sectionKey}`,
        src: src.value,
        class: "avh-app-frame",
        title: "AV 资源助手 · 内嵌应用",
        referrerpolicy: "no-referrer",
        allow: "clipboard-write"
      }, null, 8, _hoisted_1$c);
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

const AppFrame = /* @__PURE__ */ _export_sfc(_sfc_main$d, [["__scopeId", "data-v-d2cb29e5"]]);

const DEFAULT_MAX_WIDTH = "90rem";

function consoleEmits() {
  return () => {
  };
}

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
  savePath: "/media/9kg/avi",
  category: "avi",
  downloader: "qb"
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
  return a.enabled === b.enabled && a.proxy === b.proxy && a.emby_host === b.emby_host && a.emby_apikey === b.emby_apikey;
}
function embyHalfFilled(config) {
  const host = str(config?.emby_host).trim();
  const key = str(config?.emby_apikey).trim();
  if (host && !key || !host && key) {
    return "Emby 地址与 API 密钥要一起填；两栏都留空 = 复用 MoviePilot「设置 → 媒体服务器」。";
  }
  return "";
}

const {computed: computed$9,ref: ref$a} = await importShared('vue');
const POLL_INTERVAL_MS = 15e3;
function len(value) {
  return Array.isArray(value) ? value.length : null;
}
function useRuntimeInfo(api) {
  const data = ref$a(null);
  const error = ref$a("");
  const loading = ref$a(false);
  const updatedAt = ref$a("");
  let timer = null;
  const overview = computed$9(() => {
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
  const recovery = computed$9(() => ({
    subs: Array.isArray(data.value?.subs) ? data.value?.subs ?? [] : [],
    tasks: Array.isArray(data.value?.tasks) ? data.value?.tasks ?? [] : [],
    queue: Array.isArray(data.value?.queue) ? data.value?.queue ?? [] : []
  }));
  async function refresh() {
    if (loading.value) return;
    loading.value = true;
    try {
      const res = await api.get("plugin/bootstrap");
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

const {computed: computed$8,reactive,ref: ref$9,shallowRef: shallowRef$1} = await importShared('vue');
function useSettingsDraft(options) {
  const t = hostToast(options.toast);
  const rulePlain = ref$9(null);
  const rule = rulePlain;
  const hostConfig = reactive({
    enabled: options.initialConfig?.enabled === true,
    proxy: str(options.initialConfig?.proxy),
    emby_host: str(options.initialConfig?.emby_host),
    emby_apikey: str(options.initialConfig?.emby_apikey)
  });
  const sites = ref$9([]);
  const sitesLoaded = ref$9(false);
  const notices = ref$9([]);
  const cacheText = ref$9("");
  const cacheBytes = ref$9(null);
  const checkInfo = ref$9(null);
  const bootstrapEnabled = ref$9(null);
  const loading = ref$9(false);
  const saving = ref$9(false);
  const noticeLoading = ref$9(false);
  const cacheCleaning = ref$9(false);
  const error = ref$9("");
  const ruleBase = shallowRef$1(null);
  const hostBase = shallowRef$1(null);
  let hostHydrated = false;
  let ruleHydrated = false;
  function hostFromProps() {
    return {
      enabled: options.initialConfig?.enabled === true,
      proxy: str(options.initialConfig?.proxy),
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
    if (!hostHydrated && typeof data.enabled === "boolean") {
      hostHydrated = true;
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
  const ruleDirty = computed$8(() => !sameRule(rule.value, ruleBase.value));
  const hostDirty = computed$8(() => !sameHost(hostConfig, hostBase.value));
  const dirty = computed$8(() => ruleDirty.value || hostDirty.value);
  const saveButtonLabel = computed$8(() => dirty.value ? "保存修改 ● 未保存" : "保存修改");
  const enabledKnown = computed$8(
    () => typeof options.initialConfig?.enabled === "boolean" || bootstrapEnabled.value !== null
  );
  const validation = computed$8(() => embyHalfFilled(hostConfig));
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
        emby_host: str(hostConfig.emby_host).trim(),
        emby_apikey: str(hostConfig.emby_apikey).trim()
      };
      Object.assign(hostConfig, host);
      hostBase.value = { ...host };
      options.onSaveHost({ ...host });
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

const {defineComponent:_defineComponent$c} = await importShared('vue');

const {resolveComponent:_resolveComponent$a,createVNode:_createVNode$a,createTextVNode:_createTextVNode$a,withCtx:_withCtx$a,createElementVNode:_createElementVNode$a,openBlock:_openBlock$c,createElementBlock:_createElementBlock$b,createCommentVNode:_createCommentVNode$8,createBlock:_createBlock$9} = await importShared('vue');

const _hoisted_1$b = {
  key: 0,
  class: "text-caption text-medium-emphasis mb-4"
};
const _sfc_main$c = /* @__PURE__ */ _defineComponent$c({
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
      const _component_v_icon = _resolveComponent$a("v-icon");
      const _component_v_card_title = _resolveComponent$a("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$a("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$a("v-card-item");
      const _component_v_switch = _resolveComponent$a("v-switch");
      const _component_v_text_field = _resolveComponent$a("v-text-field");
      const _component_v_card_text = _resolveComponent$a("v-card-text");
      const _component_v_card = _resolveComponent$a("v-card");
      return _openBlock$c(), _createBlock$9(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$a(() => [
          _createVNode$a(_component_v_card_item, null, {
            prepend: _withCtx$a(() => [
              _createVNode$a(_component_v_icon, {
                icon: "mdi-cog-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$a(() => [
              _createVNode$a(_component_v_card_title, null, {
                default: _withCtx$a(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$a("常规")
                ])),
                _: 1
              }),
              _createVNode$a(_component_v_card_subtitle, null, {
                default: _withCtx$a(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$a("插件开关与 javdb 代理 · 属于宿主插件配置")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$a(_component_v_card_text, null, {
            default: _withCtx$a(() => [
              _createVNode$a(_component_v_switch, {
                "model-value": props.config.enabled,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "启用插件",
                class: "mb-2",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("enabled", value === true))
              }, null, 8, ["model-value"]),
              !props.enabledKnown ? (_openBlock$c(), _createElementBlock$b("p", _hoisted_1$b, _cache[4] || (_cache[4] = [
                _createTextVNode$a(" 拿不到当前开关状态（"),
                _createElementVNode$a("code", null, "/bootstrap", -1),
                _createTextVNode$a(" 未返回 "),
                _createElementVNode$a("code", null, "enabled", -1),
                _createTextVNode$a("），保存前请确认。 ")
              ]))) : _createCommentVNode$8("", true),
              _cache[5] || (_cache[5] = _createElementVNode$a("p", { class: "text-caption text-medium-emphasis mb-4" }, " 关闭后定时订阅检查与「运行一次」都不执行，界面仍可浏览。 ", -1)),
              _createVNode$a(_component_v_text_field, {
                "model-value": props.config.proxy,
                label: "javdb 代理地址",
                placeholder: "http://host:port",
                hint: "javdb 子进程与站点请求走这个代理；站点自己开了代理时按站点配置走。留空 = 直连。",
                "persistent-hint": "",
                variant: "outlined",
                density: "comfortable",
                clearable: "",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("proxy", value ?? ""))
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

const GeneralPanel = /* @__PURE__ */ _export_sfc(_sfc_main$c, [["__scopeId", "data-v-3cb0e600"]]);

const {defineComponent:_defineComponent$b} = await importShared('vue');

const {resolveComponent:_resolveComponent$9,createVNode:_createVNode$9,createTextVNode:_createTextVNode$9,withCtx:_withCtx$9,createElementVNode:_createElementVNode$9,toDisplayString:_toDisplayString$b,openBlock:_openBlock$b,createBlock:_createBlock$8,createCommentVNode:_createCommentVNode$7,renderList:_renderList$4,Fragment:_Fragment$5,createElementBlock:_createElementBlock$a} = await importShared('vue');

const _hoisted_1$a = { class: "avh-row" };
const _hoisted_2$8 = { class: "avh-row-main" };
const _hoisted_3$7 = { class: "avh-scope text-body-1" };
const _hoisted_4$5 = { class: "avh-scope text-body-2" };
const _hoisted_5$4 = { class: "avh-row-actions" };
const _hoisted_6$3 = { class: "d-flex align-center mb-2" };
const _hoisted_7$3 = { class: "text-caption text-medium-emphasis" };
const _hoisted_8$3 = { class: "avh-list" };
const _hoisted_9$3 = { class: "text-caption text-medium-emphasis" };
const _hoisted_10$2 = {
  key: 0,
  class: "text-caption text-medium-emphasis pa-2"
};
const _hoisted_11$2 = { class: "text-caption text-medium-emphasis mb-1" };
const _hoisted_12$2 = { class: "text-caption text-medium-emphasis avh-idx" };
const _hoisted_13$2 = { class: "avh-chips" };
const _hoisted_14$1 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const {computed: computed$7,ref: ref$8} = await importShared('vue');

const _sfc_main$b = /* @__PURE__ */ _defineComponent$b({
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
    const scopeText = computed$7(
      () => props.sites.length ? props.sites.join("、") : "全部站点"
    );
    const prefText = computed$7(
      () => props.prefSites.length ? props.prefSites.join(" › ") : "未设置（按站点清单顺序）"
    );
    const pickOpen = ref$8(false);
    const pickQuery = ref$8("");
    const pickDraft = ref$8([]);
    const filteredOptions = computed$7(() => {
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
    const prefOpen = ref$8(false);
    const prefDraft = ref$8([]);
    const prefCandidates = computed$7(
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
      const _component_v_icon = _resolveComponent$9("v-icon");
      const _component_v_card_title = _resolveComponent$9("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$9("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$9("v-card-item");
      const _component_v_btn = _resolveComponent$9("v-btn");
      const _component_v_alert = _resolveComponent$9("v-alert");
      const _component_v_card_text = _resolveComponent$9("v-card-text");
      const _component_v_card = _resolveComponent$9("v-card");
      const _component_v_text_field = _resolveComponent$9("v-text-field");
      const _component_v_spacer = _resolveComponent$9("v-spacer");
      const _component_v_divider = _resolveComponent$9("v-divider");
      const _component_v_checkbox = _resolveComponent$9("v-checkbox");
      const _component_v_card_actions = _resolveComponent$9("v-card-actions");
      const _component_v_dialog = _resolveComponent$9("v-dialog");
      const _component_v_list_item_title = _resolveComponent$9("v-list-item-title");
      const _component_v_list_item = _resolveComponent$9("v-list-item");
      const _component_v_list = _resolveComponent$9("v-list");
      const _component_v_chip = _resolveComponent$9("v-chip");
      return _openBlock$b(), _createElementBlock$a(_Fragment$5, null, [
        _createVNode$9(_component_v_card, {
          variant: "tonal",
          class: "avh-panel"
        }, {
          default: _withCtx$9(() => [
            _createVNode$9(_component_v_card_item, null, {
              prepend: _withCtx$9(() => [
                _createVNode$9(_component_v_icon, {
                  icon: "mdi-web",
                  color: "primary"
                })
              ]),
              default: _withCtx$9(() => [
                _createVNode$9(_component_v_card_title, null, {
                  default: _withCtx$9(() => _cache[5] || (_cache[5] = [
                    _createTextVNode$9("搜索站点")
                  ])),
                  _: 1
                }),
                _createVNode$9(_component_v_card_subtitle, null, {
                  default: _withCtx$9(() => _cache[6] || (_cache[6] = [
                    _createTextVNode$9("勾选与排序都在弹窗里 · 数据走 POST /rule")
                  ])),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$9(_component_v_card_text, null, {
              default: _withCtx$9(() => [
                _createElementVNode$9("div", _hoisted_1$a, [
                  _createElementVNode$9("div", _hoisted_2$8, [
                    _cache[7] || (_cache[7] = _createElementVNode$9("div", { class: "text-caption text-medium-emphasis mb-1" }, "当前搜索范围", -1)),
                    _createElementVNode$9("div", _hoisted_3$7, _toDisplayString$b(scopeText.value), 1),
                    _cache[8] || (_cache[8] = _createElementVNode$9("div", { class: "text-caption text-medium-emphasis mt-3 mb-1" }, "优先站点（命中即停，顺序有意义）", -1)),
                    _createElementVNode$9("div", _hoisted_4$5, _toDisplayString$b(prefText.value), 1)
                  ]),
                  _createElementVNode$9("div", _hoisted_5$4, [
                    _createVNode$9(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                      class: "mb-2",
                      onClick: openPick
                    }, {
                      default: _withCtx$9(() => _cache[9] || (_cache[9] = [
                        _createTextVNode$9("选择站点")
                      ])),
                      _: 1
                    }),
                    _createVNode$9(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-sort",
                      onClick: openPref
                    }, {
                      default: _withCtx$9(() => _cache[10] || (_cache[10] = [
                        _createTextVNode$9("优先站点")
                      ])),
                      _: 1
                    })
                  ])
                ]),
                _ctx.loaded && !_ctx.options.length ? (_openBlock$b(), _createBlock$8(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mt-3 text-caption"
                }, {
                  default: _withCtx$9(() => _cache[11] || (_cache[11] = [
                    _createTextVNode$9("没有读到任何站点（MoviePilot 站点目录为空或读取失败），下面两个按钮打开也没有内容可选。")
                  ])),
                  _: 1
                })) : _createCommentVNode$7("", true),
                _cache[12] || (_cache[12] = _createElementVNode$9("p", { class: "text-caption text-medium-emphasis mt-4 mb-0" }, " 「当前搜索范围」留空 = 全部已配置站点；优先站点会先搜、命中即停，所以顺序有意义。 两处都只写进默认规则，按顶条「保存修改」才生效。 ", -1))
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$9(_component_v_dialog, {
          modelValue: pickOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$9(() => [
            _createVNode$9(_component_v_card, null, {
              default: _withCtx$9(() => [
                _createVNode$9(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$9(() => [
                    _createVNode$9(_component_v_icon, {
                      icon: "mdi-checkbox-multiple-marked-outline",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[13] || (_cache[13] = _createTextVNode$9(" 选择站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_subtitle, null, {
                  default: _withCtx$9(() => [
                    _createTextVNode$9("不勾任何站点 = 搜索全部已配置站点（" + _toDisplayString$b(props.options.length) + " 个）", 1)
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_text, null, {
                  default: _withCtx$9(() => [
                    _createVNode$9(_component_v_text_field, {
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
                    _createElementVNode$9("div", _hoisted_6$3, [
                      _createVNode$9(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickAll
                      }, {
                        default: _withCtx$9(() => _cache[14] || (_cache[14] = [
                          _createTextVNode$9("全选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$9(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickNone
                      }, {
                        default: _withCtx$9(() => _cache[15] || (_cache[15] = [
                          _createTextVNode$9("全不选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$9(_component_v_spacer),
                      _createElementVNode$9("span", _hoisted_7$3, "已选 " + _toDisplayString$b(pickDraft.value.length), 1)
                    ]),
                    _createVNode$9(_component_v_divider, { class: "mb-1" }),
                    _createElementVNode$9("div", _hoisted_8$3, [
                      (_openBlock$b(true), _createElementBlock$a(_Fragment$5, null, _renderList$4(filteredOptions.value, (item) => {
                        return _openBlock$b(), _createBlock$8(_component_v_checkbox, {
                          key: item.name,
                          "model-value": pickDraft.value.includes(item.name),
                          label: item.name,
                          density: "compact",
                          "hide-details": "",
                          color: "primary",
                          "onUpdate:modelValue": () => pickToggle(item.name)
                        }, {
                          append: _withCtx$9(() => [
                            _createElementVNode$9("span", _hoisted_9$3, _toDisplayString$b(item.adapterLabel || item.adapter || ""), 1)
                          ]),
                          _: 2
                        }, 1032, ["model-value", "label", "onUpdate:modelValue"]);
                      }), 128)),
                      !filteredOptions.value.length ? (_openBlock$b(), _createElementBlock$a("div", _hoisted_10$2, " 没有匹配的站点。 ")) : _createCommentVNode$7("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_actions, null, {
                  default: _withCtx$9(() => [
                    _createVNode$9(_component_v_spacer),
                    _createVNode$9(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickOpen.value = false)
                    }, {
                      default: _withCtx$9(() => _cache[16] || (_cache[16] = [
                        _createTextVNode$9("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$9(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: pickConfirm
                    }, {
                      default: _withCtx$9(() => _cache[17] || (_cache[17] = [
                        _createTextVNode$9("确定")
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
        _createVNode$9(_component_v_dialog, {
          modelValue: prefOpen.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => prefOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$9(() => [
            _createVNode$9(_component_v_card, null, {
              default: _withCtx$9(() => [
                _createVNode$9(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$9(() => [
                    _createVNode$9(_component_v_icon, {
                      icon: "mdi-sort",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[18] || (_cache[18] = _createTextVNode$9(" 优先站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_subtitle, null, {
                  default: _withCtx$9(() => _cache[19] || (_cache[19] = [
                    _createTextVNode$9("先搜这些站，命中即停 —— 顺序就是搜索顺序")
                  ])),
                  _: 1
                }),
                _createVNode$9(_component_v_card_text, null, {
                  default: _withCtx$9(() => [
                    _createElementVNode$9("div", _hoisted_11$2, "优先顺序（" + _toDisplayString$b(prefDraft.value.length) + "）", 1),
                    _createVNode$9(_component_v_list, {
                      density: "compact",
                      class: "avh-list mb-3"
                    }, {
                      default: _withCtx$9(() => [
                        (_openBlock$b(true), _createElementBlock$a(_Fragment$5, null, _renderList$4(prefDraft.value, (name, index) => {
                          return _openBlock$b(), _createBlock$8(_component_v_list_item, {
                            key: `${name}:${index}`
                          }, {
                            prepend: _withCtx$9(() => [
                              _createElementVNode$9("span", _hoisted_12$2, _toDisplayString$b(index + 1), 1)
                            ]),
                            append: _withCtx$9(() => [
                              _createVNode$9(_component_v_btn, {
                                icon: "mdi-arrow-up",
                                size: "x-small",
                                variant: "text",
                                disabled: index === 0,
                                onClick: ($event) => prefMove(index, -1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$9(_component_v_btn, {
                                icon: "mdi-arrow-down",
                                size: "x-small",
                                variant: "text",
                                disabled: index === prefDraft.value.length - 1,
                                onClick: ($event) => prefMove(index, 1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$9(_component_v_btn, {
                                icon: "mdi-close",
                                size: "x-small",
                                variant: "text",
                                onClick: ($event) => prefRemove(index)
                              }, null, 8, ["onClick"])
                            ]),
                            default: _withCtx$9(() => [
                              _createVNode$9(_component_v_list_item_title, null, {
                                default: _withCtx$9(() => [
                                  _createTextVNode$9(_toDisplayString$b(name), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024);
                        }), 128)),
                        !prefDraft.value.length ? (_openBlock$b(), _createBlock$8(_component_v_list_item, { key: 0 }, {
                          default: _withCtx$9(() => [
                            _createVNode$9(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                              default: _withCtx$9(() => _cache[20] || (_cache[20] = [
                                _createTextVNode$9(" 还没有优先站点：按下面的候选加进来。 ")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        })) : _createCommentVNode$7("", true)
                      ]),
                      _: 1
                    }),
                    _createVNode$9(_component_v_divider, { class: "mb-2" }),
                    _cache[21] || (_cache[21] = _createElementVNode$9("div", { class: "text-caption text-medium-emphasis mb-1" }, "候选站点（点击加入优先顺序）", -1)),
                    _createElementVNode$9("div", _hoisted_13$2, [
                      (_openBlock$b(true), _createElementBlock$a(_Fragment$5, null, _renderList$4(prefCandidates.value, (item) => {
                        return _openBlock$b(), _createBlock$8(_component_v_chip, {
                          key: item.name,
                          size: "small",
                          variant: "tonal",
                          "prepend-icon": "mdi-plus",
                          onClick: ($event) => prefAdd(item.name)
                        }, {
                          default: _withCtx$9(() => [
                            _createTextVNode$9(_toDisplayString$b(item.name), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"]);
                      }), 128)),
                      !prefCandidates.value.length ? (_openBlock$b(), _createElementBlock$a("span", _hoisted_14$1, " 全部站点都已在优先列表里。 ")) : _createCommentVNode$7("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$9(_component_v_card_actions, null, {
                  default: _withCtx$9(() => [
                    _createVNode$9(_component_v_spacer),
                    _createVNode$9(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[3] || (_cache[3] = ($event) => prefOpen.value = false)
                    }, {
                      default: _withCtx$9(() => _cache[22] || (_cache[22] = [
                        _createTextVNode$9("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$9(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: prefConfirm
                    }, {
                      default: _withCtx$9(() => _cache[23] || (_cache[23] = [
                        _createTextVNode$9("确定")
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

const SitesPanel = /* @__PURE__ */ _export_sfc(_sfc_main$b, [["__scopeId", "data-v-b3e77efa"]]);

const {defineComponent:_defineComponent$a} = await importShared('vue');

const {resolveComponent:_resolveComponent$8,createVNode:_createVNode$8,createTextVNode:_createTextVNode$8,withCtx:_withCtx$8,createElementVNode:_createElementVNode$8,renderList:_renderList$3,Fragment:_Fragment$4,openBlock:_openBlock$a,createElementBlock:_createElementBlock$9,toDisplayString:_toDisplayString$a,unref:_unref$2,createBlock:_createBlock$7} = await importShared('vue');

const _hoisted_1$9 = { class: "avh-grid mb-2" };
const _sfc_main$a = /* @__PURE__ */ _defineComponent$a({
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
      const _component_v_icon = _resolveComponent$8("v-icon");
      const _component_v_card_title = _resolveComponent$8("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$8("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$8("v-card-item");
      const _component_v_btn = _resolveComponent$8("v-btn");
      const _component_v_btn_toggle = _resolveComponent$8("v-btn-toggle");
      const _component_v_switch = _resolveComponent$8("v-switch");
      const _component_v_text_field = _resolveComponent$8("v-text-field");
      const _component_v_alert = _resolveComponent$8("v-alert");
      const _component_v_card_text = _resolveComponent$8("v-card-text");
      const _component_v_card = _resolveComponent$8("v-card");
      return _openBlock$a(), _createBlock$7(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$8(() => [
          _createVNode$8(_component_v_card_item, null, {
            prepend: _withCtx$8(() => [
              _createVNode$8(_component_v_icon, {
                icon: "mdi-filter-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$8(() => [
              _createVNode$8(_component_v_card_title, null, {
                default: _withCtx$8(() => _cache[8] || (_cache[8] = [
                  _createTextVNode$8("下载规则")
                ])),
                _: 1
              }),
              _createVNode$8(_component_v_card_subtitle, null, {
                default: _withCtx$8(() => _cache[9] || (_cache[9] = [
                  _createTextVNode$8("手动搜索与新建订阅的基准 · 数据走 POST /rule")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$8(_component_v_card_text, null, {
            default: _withCtx$8(() => [
              _cache[12] || (_cache[12] = _createElementVNode$8("div", { class: "text-caption text-medium-emphasis mb-1" }, "分辨率策略", -1)),
              _createVNode$8(_component_v_btn_toggle, {
                "model-value": props.rule.res,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-4",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => value && patch("res", value))
              }, {
                default: _withCtx$8(() => [
                  (_openBlock$a(), _createElementBlock$9(_Fragment$4, null, _renderList$3(RES_OPTIONS, (option) => {
                    return _createVNode$8(_component_v_btn, {
                      key: option.value,
                      value: option.value
                    }, {
                      default: _withCtx$8(() => [
                        _createTextVNode$8(_toDisplayString$a(option.label), 1)
                      ]),
                      _: 2
                    }, 1032, ["value"]);
                  }), 64))
                ]),
                _: 1
              }, 8, ["model-value"]),
              _createVNode$8(_component_v_switch, {
                "model-value": props.rule.mustCnsub,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "必须中文字幕",
                class: "mb-1",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("mustCnsub", value === true))
              }, null, 8, ["model-value"]),
              _cache[13] || (_cache[13] = _createElementVNode$8("p", { class: "text-caption text-medium-emphasis mb-3" }, " 打开则没有中字的种直接淘汰；默认关（AV 站中字少，关掉时中字仍加 32 分优先选）。 ", -1)),
              _createVNode$8(_component_v_switch, {
                "model-value": props.rule.preferUncensored,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "破解 / 无码版优先",
                class: "mb-3",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("preferUncensored", value === true))
              }, null, 8, ["model-value"]),
              _createVNode$8(_component_v_switch, {
                "model-value": props.rule.allow4k,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "允许 4K 择优",
                class: "mb-1",
                "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("allow4k", value === true))
              }, null, 8, ["model-value"]),
              _cache[14] || (_cache[14] = _createElementVNode$8("p", { class: "text-caption text-medium-emphasis mb-3" }, "1080P 没有好种时升级 4K。", -1)),
              _createElementVNode$8("div", _hoisted_1$9, [
                _createVNode$8(_component_v_text_field, {
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
                _createVNode$8(_component_v_text_field, {
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
                _createVNode$8(_component_v_text_field, {
                  "model-value": String(props.policyMinInterval || _unref$2(POLICY_MIN_INTERVAL_MIN)),
                  label: "检查间隔下限（分钟，只读）",
                  hint: "政策固定值，界面不放宽",
                  "persistent-hint": "",
                  variant: "outlined",
                  density: "comfortable",
                  readonly: "",
                  disabled: ""
                }, null, 8, ["model-value"])
              ]),
              _createVNode$8(_component_v_switch, {
                "model-value": props.rule.btFallback,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "PT 搜不到时允许 BT 磁力兜底",
                class: "mb-3",
                "onUpdate:modelValue": _cache[6] || (_cache[6] = (value) => patch("btFallback", value === true))
              }, null, 8, ["model-value"]),
              _cache[15] || (_cache[15] = _createElementVNode$8("div", { class: "text-caption text-medium-emphasis mb-1" }, "命中之后", -1)),
              _createVNode$8(_component_v_btn_toggle, {
                "model-value": props.rule.trigger,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-1",
                "onUpdate:modelValue": _cache[7] || (_cache[7] = (value) => value && patch("trigger", value))
              }, {
                default: _withCtx$8(() => [
                  _createVNode$8(_component_v_btn, { value: "notify" }, {
                    default: _withCtx$8(() => _cache[10] || (_cache[10] = [
                      _createTextVNode$8("仅通知")
                    ])),
                    _: 1
                  }),
                  _createVNode$8(_component_v_btn, { value: "auto" }, {
                    default: _withCtx$8(() => _cache[11] || (_cache[11] = [
                      _createTextVNode$8("自动下载")
                    ])),
                    _: 1
                  })
                ]),
                _: 1
              }, 8, ["model-value"]),
              _cache[16] || (_cache[16] = _createElementVNode$8("p", { class: "text-caption text-medium-emphasis mb-4" }, " 「仅通知」时命中的片进「任务」页等你手动下载。 ", -1)),
              _createVNode$8(_component_v_alert, {
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption"
              }, {
                default: _withCtx$8(() => [
                  _createTextVNode$8(" 搜索范围由左栏「搜索站点」决定：当前 " + _toDisplayString$a(props.siteScopeCount ? `限定 ${props.siteScopeCount} 个站点` : "全部已配置站点") + "。 保存路径 / 下载器 / qB 分类仍在插件存储里沿用现值（本栏暂不提供编辑入口）。 ", 1)
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

const RulePanel = /* @__PURE__ */ _export_sfc(_sfc_main$a, [["__scopeId", "data-v-32a4e634"]]);

const {defineComponent:_defineComponent$9} = await importShared('vue');

const {resolveComponent:_resolveComponent$7,createVNode:_createVNode$7,createTextVNode:_createTextVNode$7,withCtx:_withCtx$7,toDisplayString:_toDisplayString$9,openBlock:_openBlock$9,createBlock:_createBlock$6,createCommentVNode:_createCommentVNode$6,createElementVNode:_createElementVNode$7,renderList:_renderList$2,Fragment:_Fragment$3,createElementBlock:_createElementBlock$8} = await importShared('vue');

const _hoisted_1$8 = { class: "avh-counts mb-3" };
const {computed: computed$6,ref: ref$7,watch: watch$3} = await importShared('vue');

const LEGACY_SEEN_KEY = "avh.noticesSeen";
const PANEL_SEEN_KEY = "avhnext.settings.noticesSeen";
const _sfc_main$9 = /* @__PURE__ */ _defineComponent$9({
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
    const panelSeen = ref$7(readStorage(PANEL_SEEN_KEY));
    const legacySeen = ref$7(readStorage(LEGACY_SEEN_KEY));
    function readStorage(key) {
      try {
        return localStorage.getItem(key) || "";
      } catch {
        return "";
      }
    }
    const total = computed$6(() => props.notices.length);
    const unread = computed$6(
      () => props.notices.filter((item) => String(item.time || "") > panelSeen.value).length
    );
    function markSeen() {
      const latest = props.notices.reduce(
        (acc, item) => String(item.time || "") > acc ? String(item.time) : acc,
        panelSeen.value
      );
      if (latest === panelSeen.value) return;
      panelSeen.value = latest;
      try {
        localStorage.setItem(PANEL_SEEN_KEY, latest);
      } catch {
      }
    }
    watch$3(
      () => props.notices,
      () => {
        legacySeen.value = readStorage(LEGACY_SEEN_KEY);
        setTimeout(markSeen, 0);
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$7("v-icon");
      const _component_v_card_title = _resolveComponent$7("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$7("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$7("v-card-item");
      const _component_v_chip = _resolveComponent$7("v-chip");
      const _component_v_list_item_title = _resolveComponent$7("v-list-item-title");
      const _component_v_list_item_subtitle = _resolveComponent$7("v-list-item-subtitle");
      const _component_v_list_item = _resolveComponent$7("v-list-item");
      const _component_v_list = _resolveComponent$7("v-list");
      const _component_v_alert = _resolveComponent$7("v-alert");
      const _component_v_card_text = _resolveComponent$7("v-card-text");
      const _component_v_btn = _resolveComponent$7("v-btn");
      const _component_v_spacer = _resolveComponent$7("v-spacer");
      const _component_v_card_actions = _resolveComponent$7("v-card-actions");
      const _component_v_card = _resolveComponent$7("v-card");
      return _openBlock$9(), _createBlock$6(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$7(() => [
          _createVNode$7(_component_v_card_item, null, {
            prepend: _withCtx$7(() => [
              _createVNode$7(_component_v_icon, {
                icon: "mdi-bell",
                color: "primary"
              })
            ]),
            default: _withCtx$7(() => [
              _createVNode$7(_component_v_card_title, null, {
                default: _withCtx$7(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$7("通知")
                ])),
                _: 1
              }),
              _createVNode$7(_component_v_card_subtitle, null, {
                default: _withCtx$7(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$7("渠道沿用 MoviePilot 原生通知 · 本插件不另建渠道")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$7(_component_v_card_text, null, {
            default: _withCtx$7(() => [
              _createElementVNode$7("div", _hoisted_1$8, [
                _createVNode$7(_component_v_chip, {
                  color: "primary",
                  variant: "tonal",
                  size: "small"
                }, {
                  default: _withCtx$7(() => [
                    _createTextVNode$7(" 未读 " + _toDisplayString$9(unread.value) + " / 共 " + _toDisplayString$9(total.value), 1)
                  ]),
                  _: 1
                }),
                legacySeen.value ? (_openBlock$9(), _createBlock$6(_component_v_chip, {
                  key: 0,
                  variant: "text",
                  size: "small",
                  class: "text-caption"
                }, {
                  default: _withCtx$7(() => [
                    _createTextVNode$7(" 内嵌应用已读到 " + _toDisplayString$9(legacySeen.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode$6("", true)
              ]),
              _cache[5] || (_cache[5] = _createElementVNode$7("p", { class: "text-caption text-medium-emphasis mb-2" }, " 通知由 MoviePilot 原生的通知渠道发出（在「设置 → 通知」里配置），这里看到的只是插件自己的收件箱。 打开本栏即算已读。 ", -1)),
              _ctx.notices.length ? (_openBlock$9(), _createBlock$6(_component_v_list, {
                key: 0,
                density: "compact",
                class: "avh-notices mb-2"
              }, {
                default: _withCtx$7(() => [
                  (_openBlock$9(true), _createElementBlock$8(_Fragment$3, null, _renderList$2(_ctx.notices.slice(0, 20), (item, index) => {
                    return _openBlock$9(), _createBlock$6(_component_v_list_item, { key: index }, {
                      prepend: _withCtx$7(() => [
                        _createVNode$7(_component_v_icon, {
                          icon: item.kind === "ok" ? "mdi-check-circle-outline" : item.kind === "warn" ? "mdi-alert-outline" : "mdi-robot-outline",
                          color: item.kind === "ok" ? "success" : item.kind === "warn" ? "warning" : "primary",
                          size: "small"
                        }, null, 8, ["icon", "color"])
                      ]),
                      default: _withCtx$7(() => [
                        _createVNode$7(_component_v_list_item_title, { class: "text-body-2" }, {
                          default: _withCtx$7(() => [
                            _createTextVNode$7(_toDisplayString$9(item.title || item.body || "（无标题）"), 1)
                          ]),
                          _: 2
                        }, 1024),
                        _createVNode$7(_component_v_list_item_subtitle, { class: "text-caption" }, {
                          default: _withCtx$7(() => [
                            _createTextVNode$7(_toDisplayString$9(item.type || "系统消息") + " · " + _toDisplayString$9(item.time || "—"), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024);
                  }), 128)),
                  _ctx.notices.length > 20 ? (_openBlock$9(), _createBlock$6(_component_v_list_item, { key: 0 }, {
                    default: _withCtx$7(() => [
                      _createVNode$7(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                        default: _withCtx$7(() => [
                          _createTextVNode$7(" 只显示最近 20 条，其余 " + _toDisplayString$9(_ctx.notices.length - 20) + " 条在数据台的铃铛里。 ", 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$6("", true)
                ]),
                _: 1
              })) : (_openBlock$9(), _createBlock$6(_component_v_alert, {
                key: 1,
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-0"
              }, {
                default: _withCtx$7(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$7(" 暂无通知。 ")
                ])),
                _: 1
              }))
            ]),
            _: 1
          }),
          _createVNode$7(_component_v_card_actions, null, {
            default: _withCtx$7(() => [
              _createVNode$7(_component_v_btn, {
                variant: "text",
                "prepend-icon": "mdi-refresh",
                loading: props.loading,
                onClick: _cache[0] || (_cache[0] = ($event) => emit("reload"))
              }, {
                default: _withCtx$7(() => _cache[6] || (_cache[6] = [
                  _createTextVNode$7("刷新")
                ])),
                _: 1
              }, 8, ["loading"]),
              _createVNode$7(_component_v_spacer),
              _createVNode$7(_component_v_btn, {
                color: "error",
                variant: "tonal",
                "prepend-icon": "mdi-bell-off-outline",
                disabled: !total.value,
                loading: props.clearing,
                onClick: _cache[1] || (_cache[1] = ($event) => emit("clear"))
              }, {
                default: _withCtx$7(() => _cache[7] || (_cache[7] = [
                  _createTextVNode$7("清空通知")
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

const NotifyPanel = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-0c6f3cc7"]]);

const {defineComponent:_defineComponent$8} = await importShared('vue');

const {resolveComponent:_resolveComponent$6,createVNode:_createVNode$6,createTextVNode:_createTextVNode$6,withCtx:_withCtx$6,Fragment:_Fragment$2,openBlock:_openBlock$8,createElementBlock:_createElementBlock$7,toDisplayString:_toDisplayString$8,createBlock:_createBlock$5} = await importShared('vue');

const {ref: ref$6} = await importShared('vue');

const _sfc_main$8 = /* @__PURE__ */ _defineComponent$8({
  __name: "LibraryPanel",
  props: {
    config: {},
    validation: {}
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const showKey = ref$6(false);
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
      const _component_v_icon = _resolveComponent$6("v-icon");
      const _component_v_card_title = _resolveComponent$6("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$6("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$6("v-card-item");
      const _component_v_alert = _resolveComponent$6("v-alert");
      const _component_v_text_field = _resolveComponent$6("v-text-field");
      const _component_v_card_text = _resolveComponent$6("v-card-text");
      const _component_v_card = _resolveComponent$6("v-card");
      return _openBlock$8(), _createBlock$5(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$6(() => [
          _createVNode$6(_component_v_card_item, null, {
            prepend: _withCtx$6(() => [
              _createVNode$6(_component_v_icon, {
                icon: "mdi-server",
                color: "primary"
              })
            ]),
            default: _withCtx$6(() => [
              _createVNode$6(_component_v_card_title, null, {
                default: _withCtx$6(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$6("媒体库")
                ])),
                _: 1
              }),
              _createVNode$6(_component_v_card_subtitle, null, {
                default: _withCtx$6(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$6("Emby 地址与密钥 · 两栏都空 = 复用 MoviePilot 的媒体服务器")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$6(_component_v_card_text, null, {
            default: _withCtx$6(() => [
              _createVNode$6(_component_v_alert, {
                type: mode() === "half" ? "warning" : mode() === "own" ? "success" : "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-4"
              }, {
                default: _withCtx$6(() => [
                  mode() === "reuse" ? (_openBlock$8(), _createElementBlock$7(_Fragment$2, { key: 0 }, [
                    _createTextVNode$6(" 当前：复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby（两栏留空即是这个状态）。 ")
                  ], 64)) : mode() === "own" ? (_openBlock$8(), _createElementBlock$7(_Fragment$2, { key: 1 }, [
                    _createTextVNode$6(" 当前：使用下面填写的 Emby，不再走 MoviePilot 的媒体服务器配置。 ")
                  ], 64)) : (_openBlock$8(), _createElementBlock$7(_Fragment$2, { key: 2 }, [
                    _createTextVNode$6(_toDisplayString$8(props.validation || "Emby 地址与 API 密钥要一起填，否则会回落到 MoviePilot 的媒体服务器。"), 1)
                  ], 64))
                ]),
                _: 1
              }, 8, ["type"]),
              _createVNode$6(_component_v_text_field, {
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
              _createVNode$6(_component_v_text_field, {
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

const LibraryPanel = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-d05104fc"]]);

const {defineComponent:_defineComponent$7} = await importShared('vue');

const {resolveComponent:_resolveComponent$5,createVNode:_createVNode$5,createTextVNode:_createTextVNode$5,withCtx:_withCtx$5,createElementVNode:_createElementVNode$6,toDisplayString:_toDisplayString$7,openBlock:_openBlock$7,createBlock:_createBlock$4,createCommentVNode:_createCommentVNode$5,createElementBlock:_createElementBlock$6} = await importShared('vue');

const _hoisted_1$7 = { class: "avh-cache" };
const _hoisted_2$7 = { class: "text-h6" };
const _hoisted_3$6 = { class: "avh-cache-actions" };
const _hoisted_4$4 = { class: "text-body-2 font-weight-medium" };
const _hoisted_5$3 = { class: "text-body-2" };
const _hoisted_6$2 = { class: "text-body-2" };
const _hoisted_7$2 = { class: "text-body-2" };
const _hoisted_8$2 = { class: "text-caption text-medium-emphasis mt-3 mb-0" };
const _hoisted_9$2 = { key: 0 };
const {computed: computed$5} = await importShared('vue');
const DASH$1 = "—";
const _sfc_main$7 = /* @__PURE__ */ _defineComponent$7({
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
    const cacheLabel = computed$5(() => props.cacheText ? props.cacheText : DASH$1);
    const todayLabel = computed$5(() => {
      const info = props.check;
      if (!info || info.checkedToday === void 0) return DASH$1;
      const limit = info.maxPerDay === void 0 ? DASH$1 : info.maxPerDay;
      return `${info.checkedToday} / ${limit}`;
    });
    const lastCheckLabel = computed$5(() => formatCheckTime(props.check?.lastCheck, "last"));
    const nextCheckLabel = computed$5(() => formatCheckTime(props.check?.nextAt, "next"));
    const intervalLabel = computed$5(() => {
      const minutes = props.check?.minIntervalMin;
      return minutes === void 0 ? DASH$1 : `${minutes} 分钟`;
    });
    const checkMissing = computed$5(() => props.check === null);
    const blockedLabel = computed$5(() => {
      const info = props.check;
      if (!info) return "";
      if (info.allowed === false) return info.reason || "当前不可执行检查（受限流约束）";
      return "";
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$5("v-icon");
      const _component_v_card_title = _resolveComponent$5("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$5("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$5("v-card-item");
      const _component_v_btn = _resolveComponent$5("v-btn");
      const _component_v_divider = _resolveComponent$5("v-divider");
      const _component_v_list_item_title = _resolveComponent$5("v-list-item-title");
      const _component_v_list_item = _resolveComponent$5("v-list-item");
      const _component_v_list = _resolveComponent$5("v-list");
      const _component_v_alert = _resolveComponent$5("v-alert");
      const _component_v_card_text = _resolveComponent$5("v-card-text");
      const _component_v_card = _resolveComponent$5("v-card");
      return _openBlock$7(), _createBlock$4(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$5(() => [
          _createVNode$5(_component_v_card_item, null, {
            prepend: _withCtx$5(() => [
              _createVNode$5(_component_v_icon, {
                icon: "mdi-database-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$5(() => [
              _createVNode$5(_component_v_card_title, null, {
                default: _withCtx$5(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$5("运行与缓存")
                ])),
                _: 1
              }),
              _createVNode$5(_component_v_card_subtitle, null, {
                default: _withCtx$5(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$5("缓存占用与清理 · 限流参数只读")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$5(_component_v_card_text, null, {
            default: _withCtx$5(() => [
              _createElementVNode$6("div", _hoisted_1$7, [
                _createElementVNode$6("div", null, [
                  _cache[4] || (_cache[4] = _createElementVNode$6("div", { class: "text-caption text-medium-emphasis" }, "缓存占用", -1)),
                  _createElementVNode$6("div", _hoisted_2$7, _toDisplayString$7(cacheLabel.value), 1)
                ]),
                _createElementVNode$6("div", _hoisted_3$6, [
                  _createVNode$5(_component_v_btn, {
                    color: "warning",
                    variant: "tonal",
                    "prepend-icon": "mdi-broom",
                    loading: props.cleaning,
                    onClick: _cache[0] || (_cache[0] = ($event) => emit("clean"))
                  }, {
                    default: _withCtx$5(() => _cache[5] || (_cache[5] = [
                      _createTextVNode$5("清理缓存")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode$5(_component_v_btn, {
                    variant: "text",
                    "prepend-icon": "mdi-refresh",
                    loading: props.loading,
                    class: "mt-2",
                    onClick: _cache[1] || (_cache[1] = ($event) => emit("refresh"))
                  }, {
                    default: _withCtx$5(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$5("刷新")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              _createVNode$5(_component_v_divider, { class: "my-4" }),
              _cache[13] || (_cache[13] = _createElementVNode$6("div", { class: "text-subtitle-2 mb-2" }, "订阅检查限流（只读）", -1)),
              _createVNode$5(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$5(() => [
                  _createVNode$5(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$5(() => [
                      _createElementVNode$6("span", _hoisted_4$4, _toDisplayString$7(todayLabel.value), 1)
                    ]),
                    default: _withCtx$5(() => [
                      _createVNode$5(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$5(() => _cache[7] || (_cache[7] = [
                          _createTextVNode$5("今天已检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$5(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$5(() => [
                      _createElementVNode$6("span", _hoisted_5$3, _toDisplayString$7(lastCheckLabel.value), 1)
                    ]),
                    default: _withCtx$5(() => [
                      _createVNode$5(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$5(() => _cache[8] || (_cache[8] = [
                          _createTextVNode$5("上次检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$5(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$5(() => [
                      _createElementVNode$6("span", _hoisted_6$2, _toDisplayString$7(nextCheckLabel.value), 1)
                    ]),
                    default: _withCtx$5(() => [
                      _createVNode$5(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$5(() => _cache[9] || (_cache[9] = [
                          _createTextVNode$5("下次可检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$5(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$5(() => [
                      _createElementVNode$6("span", _hoisted_7$2, _toDisplayString$7(intervalLabel.value), 1)
                    ]),
                    default: _withCtx$5(() => [
                      _createVNode$5(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$5(() => _cache[10] || (_cache[10] = [
                          _createTextVNode$5("间隔下限")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              blockedLabel.value ? (_openBlock$7(), _createBlock$4(_component_v_alert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mt-2"
              }, {
                default: _withCtx$5(() => [
                  _createTextVNode$5(_toDisplayString$7(blockedLabel.value), 1)
                ]),
                _: 1
              })) : _createCommentVNode$5("", true),
              _createElementVNode$6("p", _hoisted_8$2, [
                _cache[12] || (_cache[12] = _createTextVNode$5(" 限流参数按用户明确要求固定（每天 ≤6 次、间隔 ≥240 分钟），界面不提供放宽入口。 ")),
                checkMissing.value ? (_openBlock$7(), _createElementBlock$6("span", _hoisted_9$2, _cache[11] || (_cache[11] = [
                  _createTextVNode$5(" 当前后端还没返回 "),
                  _createElementVNode$6("code", null, "check", -1),
                  _createTextVNode$5(" 字段（本轮正在补），所以上面几行显示 "),
                  _createElementVNode$6("code", null, "—", -1),
                  _createTextVNode$5("；字段上线后自动显示。 ")
                ]))) : _createCommentVNode$5("", true)
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

const RuntimePanel = /* @__PURE__ */ _export_sfc(_sfc_main$7, [["__scopeId", "data-v-cd2af22c"]]);

const {defineComponent:_defineComponent$6} = await importShared('vue');

const {resolveComponent:_resolveComponent$4,createVNode:_createVNode$4,createTextVNode:_createTextVNode$4,withCtx:_withCtx$4,toDisplayString:_toDisplayString$6,createElementVNode:_createElementVNode$5,openBlock:_openBlock$6,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$4} = await importShared('vue');

const _hoisted_1$6 = { class: "text-body-2 font-weight-medium" };
const _hoisted_2$6 = { class: "text-body-2 font-weight-medium" };
const _hoisted_3$5 = { class: "text-body-2" };
const DASH = "—";
const DATA_ROOT = "/avhelper/next/cache";
const JAVDB_BIN = "/avhelper/bin/javdb";
const _sfc_main$6 = /* @__PURE__ */ _defineComponent$6({
  __name: "AboutPanel",
  props: {
    version: {},
    pluginId: {},
    sourcePluginId: {}
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$4("v-icon");
      const _component_v_card_title = _resolveComponent$4("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$4("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$4("v-card-item");
      const _component_v_list_item_title = _resolveComponent$4("v-list-item-title");
      const _component_v_list_item = _resolveComponent$4("v-list-item");
      const _component_v_list = _resolveComponent$4("v-list");
      const _component_v_divider = _resolveComponent$4("v-divider");
      const _component_v_card_text = _resolveComponent$4("v-card-text");
      const _component_v_card = _resolveComponent$4("v-card");
      return _openBlock$6(), _createBlock$3(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$4(() => [
          _createVNode$4(_component_v_card_item, null, {
            prepend: _withCtx$4(() => [
              _createVNode$4(_component_v_icon, {
                icon: "mdi-information-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$4(() => [
              _createVNode$4(_component_v_card_title, null, {
                default: _withCtx$4(() => _cache[0] || (_cache[0] = [
                  _createTextVNode$4("关于")
                ])),
                _: 1
              }),
              _createVNode$4(_component_v_card_subtitle, null, {
                default: _withCtx$4(() => _cache[1] || (_cache[1] = [
                  _createTextVNode$4("AVHelperNext · Vue 联邦渲染模式")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$4(_component_v_card_text, null, {
            default: _withCtx$4(() => [
              _createVNode$4(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$4(() => [
                  _createVNode$4(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$4(() => [
                      _createElementVNode$5("span", _hoisted_1$6, _toDisplayString$6(props.version || DASH), 1)
                    ]),
                    default: _withCtx$4(() => [
                      _createVNode$4(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$4(() => _cache[2] || (_cache[2] = [
                          _createTextVNode$4("版本号")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$4(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$4(() => [
                      _createElementVNode$5("span", _hoisted_2$6, _toDisplayString$6(props.pluginId || DASH), 1)
                    ]),
                    default: _withCtx$4(() => [
                      _createVNode$4(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$4(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$4("插件 ID")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  props.sourcePluginId ? (_openBlock$6(), _createBlock$3(_component_v_list_item, {
                    key: 0,
                    class: "px-0"
                  }, {
                    append: _withCtx$4(() => [
                      _createElementVNode$5("span", _hoisted_3$5, _toDisplayString$6(props.sourcePluginId), 1)
                    ]),
                    default: _withCtx$4(() => [
                      _createVNode$4(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$4(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$4("源插件 ID（分身）")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$4("", true),
                  _createVNode$4(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$4(() => [
                      _createElementVNode$5("span", { class: "text-body-2" }, [
                        _createElementVNode$5("code", null, _toDisplayString$6(DATA_ROOT))
                      ])
                    ]),
                    default: _withCtx$4(() => [
                      _createVNode$4(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$4(() => _cache[5] || (_cache[5] = [
                          _createTextVNode$4("数据根")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$4(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$4(() => [
                      _createElementVNode$5("span", { class: "text-body-2" }, [
                        _createElementVNode$5("code", null, _toDisplayString$6(JAVDB_BIN)),
                        _cache[7] || (_cache[7] = _createTextVNode$4("（与原版共用，只读）"))
                      ])
                    ]),
                    default: _withCtx$4(() => [
                      _createVNode$4(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$4(() => _cache[6] || (_cache[6] = [
                          _createTextVNode$4("javdb 二进制")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$4(_component_v_divider, { class: "my-3" }),
              _createElementVNode$5("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _cache[8] || (_cache[8] = _createTextVNode$4(" 数据根在插件数据卷上：SQLite 落在 ")),
                _createElementVNode$5("code", null, _toDisplayString$6(DATA_ROOT) + "/meta/avhelper.db"),
                _cache[9] || (_cache[9] = _createTextVNode$4("，图片与 JSON 缓存同根。 重构版用 ")),
                _cache[10] || (_cache[10] = _createElementVNode$5("code", null, "/avhelper/next/…", -1)),
                _cache[11] || (_cache[11] = _createTextVNode$4(" 与原版 ")),
                _cache[12] || (_cache[12] = _createElementVNode$5("code", null, "/avhelper/cache", -1)),
                _cache[13] || (_cache[13] = _createTextVNode$4(" 完全隔离， 两边不共用同一个 SQLite（合并回原插件时才会收敛）。 "))
              ]),
              _cache[14] || (_cache[14] = _createElementVNode$5("p", { class: "text-caption text-medium-emphasis mb-0" }, [
                _createTextVNode$4(" 界面上方是宿主的统一弹窗：标题栏、关闭按钮与 Toast 都由宿主提供，本插件复用 "),
                _createElementVNode$5("code", null, "moviepilot:toast"),
                _createTextVNode$4(" / "),
                _createElementVNode$5("code", null, "moviepilot:confirm"),
                _createTextVNode$4("，不自建。 版本号来自 "),
                _createElementVNode$5("code", null, "plugin/page/<id>"),
                _createTextVNode$4(" 的 "),
                _createElementVNode$5("code", null, "plugin_version"),
                _createTextVNode$4("，取不到显示 "),
                _createElementVNode$5("code", null, "—"),
                _createTextVNode$4("。 ")
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

const AboutPanel = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-932b5a1b"]]);

const {defineComponent:_defineComponent$5} = await importShared('vue');

const {openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,toDisplayString:_toDisplayString$5,normalizeClass:_normalizeClass$1} = await importShared('vue');

const _hoisted_1$5 = ["src", "alt", "loading"];
const _hoisted_2$5 = {
  key: 1,
  class: "avh-thumb__noimg"
};
const {computed: computed$4,ref: ref$5,watch: watch$2} = await importShared('vue');

const PROXY_MARK = "/img?url=";
const _sfc_main$5 = /* @__PURE__ */ _defineComponent$5({
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
    const useProxy = ref$5(false);
    const failed = ref$5(false);
    watch$2(
      () => props.src,
      () => {
        useProxy.value = false;
        failed.value = false;
      }
    );
    const proxySrc = computed$4(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (raw.includes(PROXY_MARK)) return raw;
      if (!props.pluginId) return "";
      return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`;
    });
    const currentSrc = computed$4(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (!useProxy.value) return raw;
      return proxySrc.value;
    });
    const showPlaceholder = computed$4(
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
      return _openBlock$5(), _createElementBlock$5("div", {
        class: _normalizeClass$1(["avh-thumb", `avh-thumb--${_ctx.variant}`])
      }, [
        !showPlaceholder.value ? (_openBlock$5(), _createElementBlock$5("img", {
          key: 0,
          src: currentSrc.value,
          alt: _ctx.alt,
          referrerpolicy: "no-referrer",
          loading: _ctx.lazy ? "lazy" : "eager",
          decoding: "async",
          onError
        }, null, 40, _hoisted_1$5)) : (_openBlock$5(), _createElementBlock$5("div", _hoisted_2$5, _toDisplayString$5(_ctx.alt || "无图"), 1))
      ], 2);
    };
  }
});

const Thumb = /* @__PURE__ */ _export_sfc(_sfc_main$5, [["__scopeId", "data-v-983b098d"]]);

const {ref: ref$4} = await importShared('vue');

function scoreLevel(score, pass) {
  if (!pass) return "lo";
  const value = Number(score);
  if (value >= 80) return "hi";
  if (value >= 55) return "mid";
  return "lo";
}
const fillQueue = [];
const fillTried = /* @__PURE__ */ new Set();
let fillBusy = false;
const filledThumbs = ref$4({});
function queueThumb(api, number) {
  const num = String(number ?? "");
  if (!num || fillTried.has(num)) return;
  fillTried.add(num);
  fillQueue.push(num);
  void pumpThumbFill(api);
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

const {defineComponent:_defineComponent$4} = await importShared('vue');

const {createVNode:_createVNode$3,toDisplayString:_toDisplayString$4,createElementVNode:_createElementVNode$4,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$3,renderList:_renderList$1,Fragment:_Fragment$1,createTextVNode:_createTextVNode$3,normalizeClass:_normalizeClass,unref:_unref$1,resolveComponent:_resolveComponent$3,withCtx:_withCtx$3,createBlock:_createBlock$2} = await importShared('vue');

const _hoisted_1$4 = { class: "avh-cand" };
const _hoisted_2$4 = { class: "avh-cand__head" };
const _hoisted_3$4 = { class: "avh-cand__no" };
const _hoisted_4$3 = { class: "avh-cand__hint avh-cand__origin" };
const _hoisted_5$2 = {
  key: 0,
  class: "avh-cand__hint"
};
const _hoisted_6$1 = { class: "avh-cand__table" };
const _hoisted_7$1 = { key: 0 };
const _hoisted_8$1 = {
  key: 0,
  class: "avh-tag"
};
const _hoisted_9$1 = {
  key: 0,
  class: "avh-tag avh-tag--free"
};
const _hoisted_10$1 = {
  key: 1,
  class: "avh-tag avh-tag--pref"
};
const _hoisted_11$1 = ["title"];
const _hoisted_12$1 = { colspan: "9" };
const _hoisted_13$1 = ["title"];
const _hoisted_14 = { key: 0 };
const {computed: computed$3,ref: ref$3} = await importShared('vue');
const _sfc_main$4 = /* @__PURE__ */ _defineComponent$4({
  __name: "CandTable",
  props: {
    task: {},
    pluginId: { default: "" }
  },
  emits: ["download"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const pending = ref$3({});
    const cands = computed$3(() => Array.isArray(props.task.cands) ? props.task.cands : []);
    const passedCount = computed$3(() => cands.value.filter((item) => item.pass !== false).length);
    const taskId = computed$3(() => String(props.task.id ?? ""));
    const rows = computed$3(() => {
      const pt = cands.value.filter((item) => item.src !== "BT");
      const bt = cands.value.filter((item) => item.src === "BT");
      const out = pt.map((cand, index) => ({ kind: "cand", key: `pt-${index}`, cand }));
      if (bt.length) {
        out.push({ kind: "btnote", key: "bt-note", cand: {} });
        bt.forEach((cand, index) => out.push({ kind: "cand", key: `bt-${index}`, cand }));
      }
      return out;
    });
    const origin = computed$3(() => {
      const actor = props.task.actor ? String(props.task.actor) : "";
      if (props.task.source === "sub") return `来自订阅${actor ? `：${actor}` : ""}`;
      return `手动搜索${actor ? ` · 演员：${actor}` : ""}`;
    });
    function isPass(cand) {
      return cand.pass !== false;
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
    __expose({ clearPending });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$3("v-btn");
      return _openBlock$4(), _createElementBlock$4("div", _hoisted_1$4, [
        _createElementVNode$4("div", _hoisted_2$4, [
          _createVNode$3(Thumb, {
            class: "avh-cand__poster",
            variant: "tposter",
            src: _ctx.task.thumb,
            alt: "无图",
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "plugin-id"]),
          _createElementVNode$4("div", null, [
            _createElementVNode$4("div", _hoisted_3$4, _toDisplayString$4(_ctx.task.number || ""), 1),
            _createElementVNode$4("div", _hoisted_4$3, _toDisplayString$4(origin.value) + " · 搜到 " + _toDisplayString$4(cands.value.length) + " · 合格 " + _toDisplayString$4(passedCount.value), 1)
          ]),
          _cache[0] || (_cache[0] = _createElementVNode$4("div", { class: "avh-cand__spacer" }, null, -1)),
          _ctx.task.auto && _ctx.task.source === "sub" ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_5$2, " 订阅为自动下载，但无候选合格 ")) : _createCommentVNode$3("", true)
        ]),
        _createElementVNode$4("table", _hoisted_6$1, [
          _cache[5] || (_cache[5] = _createElementVNode$4("thead", null, [
            _createElementVNode$4("tr", null, [
              _createElementVNode$4("th", null, "站点"),
              _createElementVNode$4("th", null, "规格"),
              _createElementVNode$4("th", null, "中字"),
              _createElementVNode$4("th", null, "破解"),
              _createElementVNode$4("th", null, "大小"),
              _createElementVNode$4("th", null, "做种"),
              _createElementVNode$4("th", null, "标记"),
              _createElementVNode$4("th", null, "匹配分"),
              _createElementVNode$4("th")
            ])
          ], -1)),
          _createElementVNode$4("tbody", null, [
            (_openBlock$4(true), _createElementBlock$4(_Fragment$1, null, _renderList$1(rows.value, (row) => {
              return _openBlock$4(), _createElementBlock$4(_Fragment$1, {
                key: row.key
              }, [
                row.kind === "btnote" ? (_openBlock$4(), _createElementBlock$4("tr", _hoisted_7$1, _cache[1] || (_cache[1] = [
                  _createElementVNode$4("td", {
                    colspan: "9",
                    class: "avh-cand__hint avh-cand__btnote"
                  }, " — PT 没有合格候选，以下为 BT 磁力兜底 — ", -1)
                ]))) : (_openBlock$4(), _createElementBlock$4(_Fragment$1, { key: 1 }, [
                  _createElementVNode$4("tr", {
                    class: _normalizeClass(rowClass(row.cand))
                  }, [
                    _createElementVNode$4("td", null, [
                      row.cand.src === "BT" ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_8$1, "BT")) : _createCommentVNode$3("", true),
                      _createTextVNode$3(" " + _toDisplayString$4(row.cand.site || ""), 1)
                    ]),
                    _createElementVNode$4("td", null, _toDisplayString$4(row.cand.spec || ""), 1),
                    _createElementVNode$4("td", null, [
                      _createElementVNode$4("span", {
                        class: _normalizeClass(["avh-tag", row.cand.cnsub ? "avh-tag--on" : ""])
                      }, _toDisplayString$4(row.cand.cnsub ? "有" : "无"), 3)
                    ]),
                    _createElementVNode$4("td", null, [
                      _createElementVNode$4("span", {
                        class: _normalizeClass(["avh-tag", row.cand.uncensored ? "avh-tag--uc" : ""])
                      }, _toDisplayString$4(row.cand.uncensored ? "破解" : "—"), 3)
                    ]),
                    _createElementVNode$4("td", null, _toDisplayString$4(row.cand.size || ""), 1),
                    _createElementVNode$4("td", null, _toDisplayString$4(seedersText(row.cand)), 1),
                    _createElementVNode$4("td", null, [
                      row.cand.free ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_9$1, "免费")) : _createCommentVNode$3("", true),
                      row.cand.pref ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_10$1, "优先站")) : _createCommentVNode$3("", true)
                    ]),
                    _createElementVNode$4("td", {
                      title: row.cand.breakdown || ""
                    }, [
                      _createElementVNode$4("span", {
                        class: _normalizeClass(["avh-score", `avh-score--${_unref$1(scoreLevel)(row.cand.score, isPass(row.cand))}`])
                      }, _toDisplayString$4(scoreText(row.cand)), 3)
                    ], 8, _hoisted_11$1),
                    _createElementVNode$4("td", null, [
                      isPass(row.cand) ? (_openBlock$4(), _createBlock$2(_component_v_btn, {
                        key: 0,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$3(() => _cache[2] || (_cache[2] = [
                          _createTextVNode$3("下载")
                        ])),
                        _: 2
                      }, 1032, ["loading", "onClick"])) : (_openBlock$4(), _createBlock$2(_component_v_btn, {
                        key: 1,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        title: row.cand.breakdown || "",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$3(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$3("仍要下载")
                        ])),
                        _: 2
                      }, 1032, ["title", "loading", "onClick"]))
                    ])
                  ], 2),
                  titleOf(row.cand) ? (_openBlock$4(), _createElementBlock$4("tr", {
                    key: 0,
                    class: _normalizeClass(["avh-cand__sub", ...rowClass(row.cand)])
                  }, [
                    _createElementVNode$4("td", _hoisted_12$1, [
                      _createElementVNode$4("div", {
                        class: "avh-cand__ttl",
                        title: titleOf(row.cand)
                      }, _toDisplayString$4(titleOf(row.cand)), 9, _hoisted_13$1)
                    ])
                  ], 2)) : _createCommentVNode$3("", true)
                ], 64))
              ], 64);
            }), 128)),
            !cands.value.length ? (_openBlock$4(), _createElementBlock$4("tr", _hoisted_14, _cache[4] || (_cache[4] = [
              _createElementVNode$4("td", {
                colspan: "9",
                class: "avh-cand__hint avh-cand__empty"
              }, "没有搜到任何候选", -1)
            ]))) : _createCommentVNode$3("", true)
          ])
        ])
      ]);
    };
  }
});

const CandTable = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-22ec0c69"]]);

const {defineComponent:_defineComponent$3} = await importShared('vue');

const {createElementVNode:_createElementVNode$3,toDisplayString:_toDisplayString$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$2,renderSlot:_renderSlot} = await importShared('vue');

const _hoisted_1$3 = { class: "avh-empty" };
const _hoisted_2$3 = ["innerHTML"];
const _hoisted_3$3 = {
  key: 0,
  class: "avh-empty__hint"
};
const _hoisted_4$2 = {
  key: 1,
  class: "avh-empty__slot"
};
const _sfc_main$3 = /* @__PURE__ */ _defineComponent$3({
  __name: "EmptyState",
  props: {
    text: { default: "" },
    hint: { default: "" }
  },
  setup(__props) {
    return (_ctx, _cache) => {
      return _openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
        _createElementVNode$3("div", {
          class: "avh-empty__text",
          innerHTML: _ctx.text
        }, null, 8, _hoisted_2$3),
        _ctx.hint ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_3$3, _toDisplayString$3(_ctx.hint), 1)) : _createCommentVNode$2("", true),
        _ctx.$slots.default ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_4$2, [
          _renderSlot(_ctx.$slots, "default", {}, void 0, true)
        ])) : _createCommentVNode$2("", true)
      ]);
    };
  }
});

const EmptyState = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-d928276a"]]);

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {toDisplayString:_toDisplayString$2,createElementVNode:_createElementVNode$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$1} = await importShared('vue');

const _hoisted_1$2 = {
  class: "avh-errbox",
  role: "alert"
};
const _hoisted_2$2 = { class: "avh-errbox__msg" };
const _hoisted_3$2 = {
  key: 0,
  class: "avh-errbox__act"
};
const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
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
      const _component_v_btn = _resolveComponent$2("v-btn");
      return _openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
        _createElementVNode$2("div", _hoisted_2$2, "⚠️ " + _toDisplayString$2(_ctx.message || "抓取失败，请稍后重试"), 1),
        _ctx.retryable ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_3$2, [
          _createVNode$2(_component_v_btn, {
            color: "primary",
            variant: "flat",
            size: "small",
            loading: _ctx.retrying,
            onClick: _cache[0] || (_cache[0] = ($event) => emit("retry"))
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2(_toDisplayString$2(_ctx.retryText), 1)
            ]),
            _: 1
          }, 8, ["loading"])
        ])) : _createCommentVNode$1("", true)
      ]);
    };
  }
});

const ErrorState = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-8f8a571b"]]);

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
function nowStr() {
  return (/* @__PURE__ */ new Date()).toLocaleTimeString("zh-CN", { hour12: false });
}

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {resolveComponent:_resolveComponent$1,withKeys:_withKeys,createVNode:_createVNode$1,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,withCtx:_withCtx$1,createElementVNode:_createElementVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createElementBlock:_createElementBlock$1} = await importShared('vue');

const _hoisted_1$1 = { class: "avh-sitesearch" };
const _hoisted_2$1 = { class: "avh-sitesearch__toolbar" };
const _hoisted_3$1 = { class: "avh-sitesearch__hint" };
const _hoisted_4$1 = { class: "avh-sitesearch__range" };
const _hoisted_5$1 = ["title"];
const {computed: computed$2,nextTick,ref: ref$2,watch: watch$1} = await importShared('vue');
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
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
    const candTableRef = ref$2(null);
    const keyword = ref$2("");
    const searching = ref$2(false);
    const searchedAt = ref$2("");
    const task = ref$2(null);
    const errorText = ref$2("");
    const retrying = ref$2(false);
    const siteNames = computed$2(
      () => props.store.sites.value.map((item) => String(item?.name || "")).filter(Boolean)
    );
    const picked = computed$2(() => {
      const names = siteNames.value;
      return (props.store.rule.value.sites || []).map(String).filter((name) => names.indexOf(name) >= 0);
    });
    function labelOf(name) {
      const hit = props.store.sites.value.filter((item) => item.name === name)[0];
      return String(hit?.adapterLabel || "");
    }
    const scopeText = computed$2(() => {
      if (!picked.value.length) return "全部站点";
      return picked.value.map((name) => {
        const label = labelOf(name);
        return label ? `${name}（${label}）` : name;
      }).join("、");
    });
    const cands = computed$2(() => Array.isArray(task.value?.cands) ? task.value?.cands || [] : []);
    const hasResult = computed$2(() => !!task.value && cands.value.length > 0);
    const searchLabel = computed$2(() => searching.value ? "搜索中…" : "搜索站点");
    watch$1(task, async () => {
      candTableRef.value?.clearPending();
      await nextTick();
      candTableRef.value?.clearPending();
    });
    function clearPending() {
      candTableRef.value?.clearPending();
      void nextTick(() => candTableRef.value?.clearPending());
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
      emit("switch");
    }
    function onScopeClick() {
      t.info("搜索范围在「设置台 → 搜索站点」栏里改");
    }
    return (_ctx, _cache) => {
      const _component_v_text_field = _resolveComponent$1("v-text-field");
      const _component_v_btn = _resolveComponent$1("v-btn");
      return _openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
        _createElementVNode$1("div", _hoisted_2$1, [
          _createVNode$1(_component_v_text_field, {
            modelValue: keyword.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => keyword.value = $event),
            class: "avh-sitesearch__input",
            placeholder: "番号或关键词（如 MIDV-946）…",
            autocomplete: "off",
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            disabled: searching.value,
            onKeydown: _withKeys(doSearch, ["enter"])
          }, null, 8, ["modelValue", "disabled"]),
          _createVNode$1(_component_v_btn, {
            color: "primary",
            variant: "flat",
            loading: searching.value,
            disabled: searching.value,
            "prepend-icon": "mdi-magnify",
            onClick: doSearch
          }, {
            default: _withCtx$1(() => [
              _createTextVNode$1(_toDisplayString$1(searchLabel.value), 1)
            ]),
            _: 1
          }, 8, ["loading", "disabled"]),
          _cache[1] || (_cache[1] = _createElementVNode$1("div", { class: "avh-sitesearch__spacer" }, null, -1)),
          _createElementVNode$1("span", _hoisted_3$1, _toDisplayString$1(searchedAt.value ? `上次搜索 ${searchedAt.value}` : "命中即停 · 站点间隔 3-8 秒"), 1)
        ]),
        _createElementVNode$1("div", _hoisted_4$1, [
          _cache[3] || (_cache[3] = _createElementVNode$1("div", { class: "avh-sitesearch__label" }, "搜索范围", -1)),
          _createElementVNode$1("div", {
            class: "avh-sitesearch__scope",
            title: scopeText.value,
            onClick: onScopeClick
          }, _toDisplayString$1(scopeText.value), 9, _hoisted_5$1),
          _createVNode$1(_component_v_btn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-tune",
            onClick: changeScope
          }, {
            default: _withCtx$1(() => _cache[2] || (_cache[2] = [
              _createTextVNode$1("改范围")
            ])),
            _: 1
          })
        ]),
        errorText.value ? (_openBlock$1(), _createBlock$1(ErrorState, {
          key: 0,
          message: `站点搜索失败：${errorText.value}`,
          retrying: retrying.value,
          onRetry: retry
        }, null, 8, ["message", "retrying"])) : hasResult.value && task.value ? (_openBlock$1(), _createBlock$1(CandTable, {
          key: 1,
          ref_key: "candTableRef",
          ref: candTableRef,
          task: task.value,
          "plugin-id": _ctx.pluginId,
          onDownload
        }, null, 8, ["task", "plugin-id"])) : (_openBlock$1(), _createBlock$1(EmptyState, {
          key: 2,
          text: "输入番号或关键词后点「搜索站点」"
        }))
      ]);
    };
  }
});

const SiteSearchView = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-0c044025"]]);

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
    subscribeNumber,
    searchKeyword,
    startDownload,
    downloadMagnet,
    clearNotices,
    saveRule
  };
}

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,unref:_unref,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');

const _hoisted_1 = { class: "avh-console" };
const _hoisted_2 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_3 = { class: "avh-body" };
const _hoisted_4 = { class: "avh-nav" };
const _hoisted_5 = { class: "avh-content" };
const _hoisted_6 = { class: "avh-side" };
const _hoisted_7 = { class: "text-body-2 font-weight-medium" };
const _hoisted_8 = { class: "text-body-2 font-weight-medium" };
const _hoisted_9 = { class: "text-body-2 font-weight-medium" };
const _hoisted_10 = { class: "text-body-2 font-weight-medium" };
const _hoisted_11 = { class: "text-body-2 font-weight-medium" };
const _hoisted_12 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_13 = { class: "text-body-2 text-medium-emphasis" };
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
  emits: consoleEmits(),
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const DATA_SECTIONS = [
      { key: "discover", title: "发现榜单", icon: "mdi-chart-line" },
      { key: "actors", title: "我的演员", icon: "mdi-account-star" },
      { key: "subs", title: "订阅", icon: "mdi-rss" },
      { key: "tasks", title: "任务", icon: "mdi-clipboard-list" },
      { key: "downloads", title: "下载", icon: "mdi-download" },
      { key: "sitesearch", title: "站点搜索", icon: "mdi-magnify" }
    ];
    computed(() => props.pluginId || props.sourcePluginId || "");
    const framePluginId = computed(() => props.pluginId || props.sourcePluginId || "");
    const section = ref(props.mode === "settings" ? SETTINGS_SECTIONS[0].key : DATA_SECTIONS[0].key);
    const running = ref(false);
    const version = ref("");
    const noticeClearing = ref(false);
    const isSettings = computed(() => props.mode === "settings");
    const activeSection = computed(
      () => SETTINGS_SECTIONS.find((item) => item.key === section.value) || SETTINGS_SECTIONS[0]
    );
    const injectedToast = inject("moviepilot:toast", null);
    const toast = hostToast(injectedToast);
    const confirm = useHostConfirm();
    const FALLBACK_API = {
      get: () => Promise.reject(new Error("宿主 api 不可用")),
      post: () => Promise.reject(new Error("宿主 api 不可用"))
    };
    function currentApi() {
      return props.api && typeof props.api.get === "function" ? props.api : FALLBACK_API;
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
    const draft = useSettingsDraft({
      api: currentApi(),
      initialConfig: props.initialConfig,
      toast: injectedToast,
      onSaveHost: (config) => emit("save", config)
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
      save: saveDraft,
      loadNotices,
      clearNotices: clearNoticesDraft,
      cleanCache: cleanCacheDraft
    } = draft;
    watch(bootstrap, (value) => applyBootstrap(value), { immediate: true });
    const activeNavKey = computed(
      () => isSettings.value ? section.value : `data:${section.value}`
    );
    const ruleView = computed(() => ruleDraft.value);
    function patchRule(patch) {
      const current = ruleDraft.value;
      if (!current) return;
      ruleDraft.value = { ...current, ...patch };
    }
    function pick(item) {
      section.value = item.key;
    }
    async function loadVersion() {
      if (!framePluginId.value) return;
      try {
        const res = await currentApi().get(`plugin/page/${framePluginId.value}`);
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        const value = payload?.plugin_version;
        if (typeof value === "string" && value) version.value = value;
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
    async function runCheck() {
      if (running.value) return;
      running.value = true;
      try {
        const res = await currentApi().post(`plugin/check`, {});
        const payload = res && typeof res === "object" && "data" in res ? res.data : res;
        const message = messageOf(res) || messageOf(payload);
        if (payload?.limited) {
          toast.warning(message || "已达限流上限，本次未执行检查");
        } else {
          const hits = Array.isArray(payload?.notices) ? payload.notices.length : null;
          toast.success(message || (hits === null ? "检查完成" : `检查完成：新增 ${hits} 条通知`));
        }
        await refreshRuntime();
      } catch (err) {
        toast.error(errorText(err));
      } finally {
        running.value = false;
      }
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
        await clearNoticesDraft();
      } finally {
        noticeClearing.value = false;
      }
    }
    function closePanel() {
      emit("close");
    }
    watch(
      () => props.mode,
      (mode) => {
        section.value = mode === "settings" ? SETTINGS_SECTIONS[0].key : DATA_SECTIONS[0].key;
      }
    );
    onMounted(() => {
      emit("layout", { maxWidth: DEFAULT_MAX_WIDTH });
      runtime.start();
      void loadVersion();
      if (props.mode === "settings") void loadDraft();
    });
    onBeforeUnmount(() => {
      runtime.stop();
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_toolbar_title = _resolveComponent("v-toolbar-title");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_toolbar = _resolveComponent("v-toolbar");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_list_subheader = _resolveComponent("v-list-subheader");
      const _component_v_list_item = _resolveComponent("v-list-item");
      const _component_v_list = _resolveComponent("v-list");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_skeleton_loader = _resolveComponent("v-skeleton-loader");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_subtitle = _resolveComponent("v-card-subtitle");
      const _component_v_card_item = _resolveComponent("v-card-item");
      const _component_v_list_item_title = _resolveComponent("v-list-item-title");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_toolbar, {
          density: "comfortable",
          color: "surface",
          class: "avh-topbar"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_icon, {
              icon: "mdi-movie-open-star",
              color: "primary",
              class: "ms-2"
            }),
            _createVNode(_component_v_toolbar_title, { class: "avh-title" }, {
              default: _withCtx(() => [
                _cache[10] || (_cache[10] = _createElementVNode("span", { class: "text-h6" }, "AV 资源助手", -1)),
                version.value ? (_openBlock(), _createElementBlock("span", _hoisted_2, "v" + _toDisplayString(version.value), 1)) : _createCommentVNode("", true),
                _unref(overview).enabled === false ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 1,
                  size: "x-small",
                  color: "warning",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => _cache[9] || (_cache[9] = [
                    _createTextVNode("已停用")
                  ])),
                  _: 1
                })) : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_v_spacer),
            _createVNode(_component_v_btn, {
              color: "primary",
              variant: "flat",
              "prepend-icon": "mdi-play",
              loading: running.value,
              class: "me-2",
              onClick: runCheck
            }, {
              default: _withCtx(() => _cache[11] || (_cache[11] = [
                _createTextVNode("运行一次")
              ])),
              _: 1
            }, 8, ["loading"]),
            isSettings.value ? (_openBlock(), _createBlock(_component_v_btn, {
              key: 0,
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
            }, 8, ["color", "variant", "loading"])) : _createCommentVNode("", true),
            _createVNode(_component_v_btn, {
              variant: "text",
              "prepend-icon": "mdi-close",
              class: "me-2",
              onClick: closePanel
            }, {
              default: _withCtx(() => _cache[12] || (_cache[12] = [
                _createTextVNode("关闭")
              ])),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_divider),
        _createElementVNode("div", _hoisted_3, [
          _createElementVNode("nav", _hoisted_4, [
            _createVNode(_component_v_list, {
              density: "compact",
              nav: "",
              selected: [activeNavKey.value],
              mandatory: ""
            }, {
              default: _withCtx(() => [
                !isSettings.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                  _createVNode(_component_v_list_subheader, null, {
                    default: _withCtx(() => _cache[13] || (_cache[13] = [
                      _createTextVNode("数据台")
                    ])),
                    _: 1
                  }),
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(DATA_SECTIONS, (item) => {
                    return _createVNode(_component_v_list_item, {
                      key: item.key,
                      value: `data:${item.key}`,
                      "prepend-icon": item.icon,
                      title: item.title,
                      onClick: ($event) => pick(item)
                    }, null, 8, ["value", "prepend-icon", "title", "onClick"]);
                  }), 64))
                ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  _createVNode(_component_v_list_subheader, null, {
                    default: _withCtx(() => _cache[14] || (_cache[14] = [
                      _createTextVNode("设置台")
                    ])),
                    _: 1
                  }),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(SETTINGS_SECTIONS), (item) => {
                    return _openBlock(), _createBlock(_component_v_list_item, {
                      key: item.key,
                      value: item.key,
                      "prepend-icon": item.icon,
                      title: item.title,
                      onClick: ($event) => pick(item)
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
                ], 64))
              ]),
              _: 1
            }, 8, ["selected"]),
            _createVNode(_component_v_btn, {
              block: "",
              size: "small",
              variant: "text",
              "prepend-icon": isSettings.value ? "mdi-view-dashboard-outline" : "mdi-cog-outline",
              class: "mt-2",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("switch"))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(isSettings.value ? "打开数据台" : "打开设置台"), 1)
              ]),
              _: 1
            }, 8, ["prepend-icon"])
          ]),
          _createVNode(_component_v_divider, { vertical: "" }),
          _createElementVNode("section", _hoisted_5, [
            !isSettings.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
              section.value === "sitesearch" && framePluginId.value ? (_openBlock(), _createBlock(SiteSearchView, {
                key: 0,
                store: _unref(store),
                "plugin-id": framePluginId.value,
                api: currentApi(),
                toast: _unref(injectedToast),
                onSwitch: _cache[1] || (_cache[1] = ($event) => emit("switch")),
                onRefreshSide: _cache[2] || (_cache[2] = ($event) => _unref(refreshRuntime)())
              }, null, 8, ["store", "plugin-id", "api", "toast"])) : framePluginId.value ? (_openBlock(), _createBlock(AppFrame, {
                key: 1,
                "plugin-id": framePluginId.value,
                "section-key": section.value,
                version: version.value
              }, null, 8, ["plugin-id", "section-key", "version"])) : (_openBlock(), _createBlock(_component_v_alert, {
                key: 2,
                type: "warning",
                variant: "tonal"
              }, {
                default: _withCtx(() => _cache[15] || (_cache[15] = [
                  _createTextVNode(" 宿主没有传入 pluginId，无法定位内嵌应用。 ")
                ])),
                _: 1
              }))
            ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
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
              section.value === "general" ? (_openBlock(), _createBlock(GeneralPanel, {
                key: 2,
                config: _unref(hostConfig),
                "enabled-known": _unref(enabledKnown),
                onPatch: _cache[3] || (_cache[3] = (patch) => Object.assign(_unref(hostConfig), patch))
              }, null, 8, ["config", "enabled-known"])) : section.value === "sites" ? (_openBlock(), _createBlock(SitesPanel, {
                key: 3,
                sites: ruleView.value?.sites || [],
                "pref-sites": ruleView.value?.prefSites || [],
                options: _unref(sites),
                loaded: _unref(sitesLoaded),
                "onUpdate:sites": _cache[4] || (_cache[4] = (value) => patchRule({ sites: value })),
                "onUpdate:prefSites": _cache[5] || (_cache[5] = (value) => patchRule({ prefSites: value }))
              }, null, 8, ["sites", "pref-sites", "options", "loaded"])) : section.value === "rule" && ruleView.value ? (_openBlock(), _createBlock(RulePanel, {
                key: 4,
                rule: ruleView.value,
                "policy-min-interval": _unref(checkInfo)?.minIntervalMin || 0,
                "site-scope-count": ruleView.value.sites.length,
                onPatch: patchRule
              }, null, 8, ["rule", "policy-min-interval", "site-scope-count"])) : section.value === "notify" ? (_openBlock(), _createBlock(NotifyPanel, {
                key: 5,
                notices: _unref(notices),
                loading: _unref(noticeLoading),
                clearing: noticeClearing.value,
                onClear: clearNotices,
                onReload: _unref(loadNotices)
              }, null, 8, ["notices", "loading", "clearing", "onReload"])) : section.value === "library" ? (_openBlock(), _createBlock(LibraryPanel, {
                key: 6,
                config: _unref(hostConfig),
                validation: _unref(validation),
                onPatch: _cache[6] || (_cache[6] = (patch) => Object.assign(_unref(hostConfig), patch))
              }, null, 8, ["config", "validation"])) : section.value === "runtime" ? (_openBlock(), _createBlock(RuntimePanel, {
                key: 7,
                "cache-text": _unref(cacheText),
                check: _unref(checkInfo),
                cleaning: _unref(cacheCleaning),
                loading: _unref(runtimeLoading),
                onClean: cleanCache,
                onRefresh: _cache[7] || (_cache[7] = ($event) => _unref(refreshRuntime)())
              }, null, 8, ["cache-text", "check", "cleaning", "loading"])) : section.value === "about" ? (_openBlock(), _createBlock(AboutPanel, {
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
                  _createTextVNode(" 未知栏目：" + _toDisplayString(activeSection.value.title), 1)
                ]),
                _: 1
              }))
            ], 64))
          ]),
          _createVNode(_component_v_divider, { vertical: "" }),
          _createElementVNode("aside", _hoisted_6, [
            _createVNode(_component_v_card, {
              variant: "outlined",
              class: "avh-overview"
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
                    _createVNode(_component_v_card_title, { class: "text-subtitle-1" }, {
                      default: _withCtx(() => _cache[16] || (_cache[16] = [
                        _createTextVNode("运行概况")
                      ])),
                      _: 1
                    }),
                    _unref(updatedAt) ? (_openBlock(), _createBlock(_component_v_card_subtitle, { key: 0 }, {
                      default: _withCtx(() => [
                        _createTextVNode("更新于 " + _toDisplayString(_unref(updatedAt)), 1)
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, { class: "pt-0" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_list, {
                      density: "compact",
                      class: "pa-0"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_7, _toDisplayString(_unref(overview).subs === null ? "—" : _unref(overview).subs), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[17] || (_cache[17] = [
                                _createTextVNode("订阅")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_8, _toDisplayString(_unref(overview).awaitTasks === null ? "—" : _unref(overview).awaitTasks), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[18] || (_cache[18] = [
                                _createTextVNode("待确认任务")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_9, _toDisplayString(_unref(overview).downloading === null ? "—" : _unref(overview).downloading), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[19] || (_cache[19] = [
                                _createTextVNode("下载中")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_10, _toDisplayString(_unref(overview).favorites === null ? "—" : _unref(overview).favorites), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[20] || (_cache[20] = [
                                _createTextVNode("收藏演员")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_11, _toDisplayString(_unref(overview).notices === null ? "—" : _unref(overview).notices), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[21] || (_cache[21] = [
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
                            _createElementVNode("span", _hoisted_12, _toDisplayString(_unref(overview).cacheSize), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[22] || (_cache[22] = [
                                _createTextVNode("缓存")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_13, _toDisplayString(_unref(overview).nextCheck), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[23] || (_cache[23] = [
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
                      onClick: _cache[8] || (_cache[8] = ($event) => _unref(refreshRuntime)())
                    }, {
                      default: _withCtx(() => _cache[24] || (_cache[24] = [
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
          ])
        ])
      ]);
    };
  }
});

const Console = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-d5ddb4c4"]]);

export { Console as C, consoleEmits as c };
