import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {defineComponent:_defineComponent$k} = await importShared('vue');

const {openBlock:_openBlock$k,createElementBlock:_createElementBlock$j} = await importShared('vue');

const _hoisted_1$j = ["src"];
const {computed: computed$f} = await importShared('vue');

const _sfc_main$k = /* @__PURE__ */ _defineComponent$k({
  __name: "AppFrame",
  props: {
    pluginId: {},
    version: { default: "" },
    sectionKey: { default: "discover" }
  },
  setup(__props) {
    const props = __props;
    const src = computed$f(() => {
      const params = new URLSearchParams();
      if (props.version) params.set("v", props.version);
      if (props.sectionKey) params.set("view", props.sectionKey);
      const query = params.toString();
      return `/api/v1/plugin/${props.pluginId}/ui/${query ? `?${query}` : ""}`;
    });
    return (_ctx, _cache) => {
      return _openBlock$k(), _createElementBlock$j("iframe", {
        key: `${_ctx.pluginId}:${_ctx.sectionKey}`,
        src: src.value,
        class: "avh-app-frame",
        title: "AV 资源助手 · 内嵌应用",
        referrerpolicy: "no-referrer",
        allow: "clipboard-write"
      }, null, 8, _hoisted_1$j);
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

const AppFrame = /* @__PURE__ */ _export_sfc(_sfc_main$k, [["__scopeId", "data-v-d2cb29e5"]]);

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

const {computed: computed$e,ref: ref$e} = await importShared('vue');
const POLL_INTERVAL_MS = 15e3;
function len(value) {
  return Array.isArray(value) ? value.length : null;
}
function useRuntimeInfo(api) {
  const data = ref$e(null);
  const error = ref$e("");
  const loading = ref$e(false);
  const updatedAt = ref$e("");
  let timer = null;
  const overview = computed$e(() => {
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
  const recovery = computed$e(() => ({
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

const {computed: computed$d,reactive: reactive$2,ref: ref$d,shallowRef: shallowRef$1} = await importShared('vue');
function useSettingsDraft(options) {
  const t = hostToast(options.toast);
  const rulePlain = ref$d(null);
  const rule = rulePlain;
  const hostConfig = reactive$2({
    enabled: options.initialConfig?.enabled === true,
    proxy: str(options.initialConfig?.proxy),
    emby_host: str(options.initialConfig?.emby_host),
    emby_apikey: str(options.initialConfig?.emby_apikey)
  });
  const sites = ref$d([]);
  const sitesLoaded = ref$d(false);
  const notices = ref$d([]);
  const cacheText = ref$d("");
  const cacheBytes = ref$d(null);
  const checkInfo = ref$d(null);
  const bootstrapEnabled = ref$d(null);
  const loading = ref$d(false);
  const saving = ref$d(false);
  const noticeLoading = ref$d(false);
  const cacheCleaning = ref$d(false);
  const error = ref$d("");
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
  const ruleDirty = computed$d(() => !sameRule(rule.value, ruleBase.value));
  const hostDirty = computed$d(() => !sameHost(hostConfig, hostBase.value));
  const dirty = computed$d(() => ruleDirty.value || hostDirty.value);
  const saveButtonLabel = computed$d(() => dirty.value ? "保存修改 ● 未保存" : "保存修改");
  const enabledKnown = computed$d(
    () => typeof options.initialConfig?.enabled === "boolean" || bootstrapEnabled.value !== null
  );
  const validation = computed$d(() => embyHalfFilled(hostConfig));
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

const {defineComponent:_defineComponent$j} = await importShared('vue');

const {resolveComponent:_resolveComponent$f,createVNode:_createVNode$g,createTextVNode:_createTextVNode$f,withCtx:_withCtx$f,createElementVNode:_createElementVNode$h,openBlock:_openBlock$j,createElementBlock:_createElementBlock$i,createCommentVNode:_createCommentVNode$d,createBlock:_createBlock$e} = await importShared('vue');

const _hoisted_1$i = {
  key: 0,
  class: "text-caption text-medium-emphasis mb-4"
};
const _sfc_main$j = /* @__PURE__ */ _defineComponent$j({
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
      const _component_v_icon = _resolveComponent$f("v-icon");
      const _component_v_card_title = _resolveComponent$f("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$f("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$f("v-card-item");
      const _component_v_switch = _resolveComponent$f("v-switch");
      const _component_v_text_field = _resolveComponent$f("v-text-field");
      const _component_v_card_text = _resolveComponent$f("v-card-text");
      const _component_v_card = _resolveComponent$f("v-card");
      return _openBlock$j(), _createBlock$e(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$f(() => [
          _createVNode$g(_component_v_card_item, null, {
            prepend: _withCtx$f(() => [
              _createVNode$g(_component_v_icon, {
                icon: "mdi-cog-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$f(() => [
              _createVNode$g(_component_v_card_title, null, {
                default: _withCtx$f(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$f("常规")
                ])),
                _: 1
              }),
              _createVNode$g(_component_v_card_subtitle, null, {
                default: _withCtx$f(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$f("插件开关与 javdb 代理 · 属于宿主插件配置")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$g(_component_v_card_text, null, {
            default: _withCtx$f(() => [
              _createVNode$g(_component_v_switch, {
                "model-value": props.config.enabled,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "启用插件",
                class: "mb-2",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => patch("enabled", value === true))
              }, null, 8, ["model-value"]),
              !props.enabledKnown ? (_openBlock$j(), _createElementBlock$i("p", _hoisted_1$i, _cache[4] || (_cache[4] = [
                _createTextVNode$f(" 拿不到当前开关状态（"),
                _createElementVNode$h("code", null, "/bootstrap", -1),
                _createTextVNode$f(" 未返回 "),
                _createElementVNode$h("code", null, "enabled", -1),
                _createTextVNode$f("），保存前请确认。 ")
              ]))) : _createCommentVNode$d("", true),
              _cache[5] || (_cache[5] = _createElementVNode$h("p", { class: "text-caption text-medium-emphasis mb-4" }, " 关闭后定时订阅检查与「运行一次」都不执行，界面仍可浏览。 ", -1)),
              _createVNode$g(_component_v_text_field, {
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

const GeneralPanel = /* @__PURE__ */ _export_sfc(_sfc_main$j, [["__scopeId", "data-v-3cb0e600"]]);

const {defineComponent:_defineComponent$i} = await importShared('vue');

const {resolveComponent:_resolveComponent$e,createVNode:_createVNode$f,createTextVNode:_createTextVNode$e,withCtx:_withCtx$e,createElementVNode:_createElementVNode$g,toDisplayString:_toDisplayString$i,openBlock:_openBlock$i,createBlock:_createBlock$d,createCommentVNode:_createCommentVNode$c,renderList:_renderList$9,Fragment:_Fragment$a,createElementBlock:_createElementBlock$h} = await importShared('vue');

const _hoisted_1$h = { class: "avh-row" };
const _hoisted_2$f = { class: "avh-row-main" };
const _hoisted_3$e = { class: "avh-scope text-body-1" };
const _hoisted_4$c = { class: "avh-scope text-body-2" };
const _hoisted_5$a = { class: "avh-row-actions" };
const _hoisted_6$8 = { class: "d-flex align-center mb-2" };
const _hoisted_7$8 = { class: "text-caption text-medium-emphasis" };
const _hoisted_8$8 = { class: "avh-list" };
const _hoisted_9$8 = { class: "text-caption text-medium-emphasis" };
const _hoisted_10$7 = {
  key: 0,
  class: "text-caption text-medium-emphasis pa-2"
};
const _hoisted_11$6 = { class: "text-caption text-medium-emphasis mb-1" };
const _hoisted_12$4 = { class: "text-caption text-medium-emphasis avh-idx" };
const _hoisted_13$4 = { class: "avh-chips" };
const _hoisted_14$3 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const {computed: computed$c,ref: ref$c} = await importShared('vue');

const _sfc_main$i = /* @__PURE__ */ _defineComponent$i({
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
    const scopeText = computed$c(
      () => props.sites.length ? props.sites.join("、") : "全部站点"
    );
    const prefText = computed$c(
      () => props.prefSites.length ? props.prefSites.join(" › ") : "未设置（按站点清单顺序）"
    );
    const pickOpen = ref$c(false);
    const pickQuery = ref$c("");
    const pickDraft = ref$c([]);
    const filteredOptions = computed$c(() => {
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
    const prefOpen = ref$c(false);
    const prefDraft = ref$c([]);
    const prefCandidates = computed$c(
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
      const _component_v_icon = _resolveComponent$e("v-icon");
      const _component_v_card_title = _resolveComponent$e("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$e("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$e("v-card-item");
      const _component_v_btn = _resolveComponent$e("v-btn");
      const _component_v_alert = _resolveComponent$e("v-alert");
      const _component_v_card_text = _resolveComponent$e("v-card-text");
      const _component_v_card = _resolveComponent$e("v-card");
      const _component_v_text_field = _resolveComponent$e("v-text-field");
      const _component_v_spacer = _resolveComponent$e("v-spacer");
      const _component_v_divider = _resolveComponent$e("v-divider");
      const _component_v_checkbox = _resolveComponent$e("v-checkbox");
      const _component_v_card_actions = _resolveComponent$e("v-card-actions");
      const _component_v_dialog = _resolveComponent$e("v-dialog");
      const _component_v_list_item_title = _resolveComponent$e("v-list-item-title");
      const _component_v_list_item = _resolveComponent$e("v-list-item");
      const _component_v_list = _resolveComponent$e("v-list");
      const _component_v_chip = _resolveComponent$e("v-chip");
      return _openBlock$i(), _createElementBlock$h(_Fragment$a, null, [
        _createVNode$f(_component_v_card, {
          variant: "tonal",
          class: "avh-panel"
        }, {
          default: _withCtx$e(() => [
            _createVNode$f(_component_v_card_item, null, {
              prepend: _withCtx$e(() => [
                _createVNode$f(_component_v_icon, {
                  icon: "mdi-web",
                  color: "primary"
                })
              ]),
              default: _withCtx$e(() => [
                _createVNode$f(_component_v_card_title, null, {
                  default: _withCtx$e(() => _cache[5] || (_cache[5] = [
                    _createTextVNode$e("搜索站点")
                  ])),
                  _: 1
                }),
                _createVNode$f(_component_v_card_subtitle, null, {
                  default: _withCtx$e(() => _cache[6] || (_cache[6] = [
                    _createTextVNode$e("勾选与排序都在弹窗里 · 数据走 POST /rule")
                  ])),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$f(_component_v_card_text, null, {
              default: _withCtx$e(() => [
                _createElementVNode$g("div", _hoisted_1$h, [
                  _createElementVNode$g("div", _hoisted_2$f, [
                    _cache[7] || (_cache[7] = _createElementVNode$g("div", { class: "text-caption text-medium-emphasis mb-1" }, "当前搜索范围", -1)),
                    _createElementVNode$g("div", _hoisted_3$e, _toDisplayString$i(scopeText.value), 1),
                    _cache[8] || (_cache[8] = _createElementVNode$g("div", { class: "text-caption text-medium-emphasis mt-3 mb-1" }, "优先站点（命中即停，顺序有意义）", -1)),
                    _createElementVNode$g("div", _hoisted_4$c, _toDisplayString$i(prefText.value), 1)
                  ]),
                  _createElementVNode$g("div", _hoisted_5$a, [
                    _createVNode$f(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                      class: "mb-2",
                      onClick: openPick
                    }, {
                      default: _withCtx$e(() => _cache[9] || (_cache[9] = [
                        _createTextVNode$e("选择站点")
                      ])),
                      _: 1
                    }),
                    _createVNode$f(_component_v_btn, {
                      color: "primary",
                      variant: "tonal",
                      "prepend-icon": "mdi-sort",
                      onClick: openPref
                    }, {
                      default: _withCtx$e(() => _cache[10] || (_cache[10] = [
                        _createTextVNode$e("优先站点")
                      ])),
                      _: 1
                    })
                  ])
                ]),
                _ctx.loaded && !_ctx.options.length ? (_openBlock$i(), _createBlock$d(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mt-3 text-caption"
                }, {
                  default: _withCtx$e(() => _cache[11] || (_cache[11] = [
                    _createTextVNode$e("没有读到任何站点（MoviePilot 站点目录为空或读取失败），下面两个按钮打开也没有内容可选。")
                  ])),
                  _: 1
                })) : _createCommentVNode$c("", true),
                _cache[12] || (_cache[12] = _createElementVNode$g("p", { class: "text-caption text-medium-emphasis mt-4 mb-0" }, " 「当前搜索范围」留空 = 全部已配置站点；优先站点会先搜、命中即停，所以顺序有意义。 两处都只写进默认规则，按顶条「保存修改」才生效。 ", -1))
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$f(_component_v_dialog, {
          modelValue: pickOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$e(() => [
            _createVNode$f(_component_v_card, null, {
              default: _withCtx$e(() => [
                _createVNode$f(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$e(() => [
                    _createVNode$f(_component_v_icon, {
                      icon: "mdi-checkbox-multiple-marked-outline",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[13] || (_cache[13] = _createTextVNode$e(" 选择站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$f(_component_v_card_subtitle, null, {
                  default: _withCtx$e(() => [
                    _createTextVNode$e("不勾任何站点 = 搜索全部已配置站点（" + _toDisplayString$i(props.options.length) + " 个）", 1)
                  ]),
                  _: 1
                }),
                _createVNode$f(_component_v_card_text, null, {
                  default: _withCtx$e(() => [
                    _createVNode$f(_component_v_text_field, {
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
                    _createElementVNode$g("div", _hoisted_6$8, [
                      _createVNode$f(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickAll
                      }, {
                        default: _withCtx$e(() => _cache[14] || (_cache[14] = [
                          _createTextVNode$e("全选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$f(_component_v_btn, {
                        size: "small",
                        variant: "text",
                        onClick: pickNone
                      }, {
                        default: _withCtx$e(() => _cache[15] || (_cache[15] = [
                          _createTextVNode$e("全不选（当前筛选）")
                        ])),
                        _: 1
                      }),
                      _createVNode$f(_component_v_spacer),
                      _createElementVNode$g("span", _hoisted_7$8, "已选 " + _toDisplayString$i(pickDraft.value.length), 1)
                    ]),
                    _createVNode$f(_component_v_divider, { class: "mb-1" }),
                    _createElementVNode$g("div", _hoisted_8$8, [
                      (_openBlock$i(true), _createElementBlock$h(_Fragment$a, null, _renderList$9(filteredOptions.value, (item) => {
                        return _openBlock$i(), _createBlock$d(_component_v_checkbox, {
                          key: item.name,
                          "model-value": pickDraft.value.includes(item.name),
                          label: item.name,
                          density: "compact",
                          "hide-details": "",
                          color: "primary",
                          "onUpdate:modelValue": () => pickToggle(item.name)
                        }, {
                          append: _withCtx$e(() => [
                            _createElementVNode$g("span", _hoisted_9$8, _toDisplayString$i(item.adapterLabel || item.adapter || ""), 1)
                          ]),
                          _: 2
                        }, 1032, ["model-value", "label", "onUpdate:modelValue"]);
                      }), 128)),
                      !filteredOptions.value.length ? (_openBlock$i(), _createElementBlock$h("div", _hoisted_10$7, " 没有匹配的站点。 ")) : _createCommentVNode$c("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$f(_component_v_card_actions, null, {
                  default: _withCtx$e(() => [
                    _createVNode$f(_component_v_spacer),
                    _createVNode$f(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickOpen.value = false)
                    }, {
                      default: _withCtx$e(() => _cache[16] || (_cache[16] = [
                        _createTextVNode$e("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$f(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: pickConfirm
                    }, {
                      default: _withCtx$e(() => _cache[17] || (_cache[17] = [
                        _createTextVNode$e("确定")
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
        _createVNode$f(_component_v_dialog, {
          modelValue: prefOpen.value,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => prefOpen.value = $event),
          "max-width": "640",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$e(() => [
            _createVNode$f(_component_v_card, null, {
              default: _withCtx$e(() => [
                _createVNode$f(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$e(() => [
                    _createVNode$f(_component_v_icon, {
                      icon: "mdi-sort",
                      color: "primary",
                      class: "me-2"
                    }),
                    _cache[18] || (_cache[18] = _createTextVNode$e(" 优先站点 "))
                  ]),
                  _: 1
                }),
                _createVNode$f(_component_v_card_subtitle, null, {
                  default: _withCtx$e(() => _cache[19] || (_cache[19] = [
                    _createTextVNode$e("先搜这些站，命中即停 —— 顺序就是搜索顺序")
                  ])),
                  _: 1
                }),
                _createVNode$f(_component_v_card_text, null, {
                  default: _withCtx$e(() => [
                    _createElementVNode$g("div", _hoisted_11$6, "优先顺序（" + _toDisplayString$i(prefDraft.value.length) + "）", 1),
                    _createVNode$f(_component_v_list, {
                      density: "compact",
                      class: "avh-list mb-3"
                    }, {
                      default: _withCtx$e(() => [
                        (_openBlock$i(true), _createElementBlock$h(_Fragment$a, null, _renderList$9(prefDraft.value, (name, index) => {
                          return _openBlock$i(), _createBlock$d(_component_v_list_item, {
                            key: `${name}:${index}`
                          }, {
                            prepend: _withCtx$e(() => [
                              _createElementVNode$g("span", _hoisted_12$4, _toDisplayString$i(index + 1), 1)
                            ]),
                            append: _withCtx$e(() => [
                              _createVNode$f(_component_v_btn, {
                                icon: "mdi-arrow-up",
                                size: "x-small",
                                variant: "text",
                                disabled: index === 0,
                                onClick: ($event) => prefMove(index, -1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$f(_component_v_btn, {
                                icon: "mdi-arrow-down",
                                size: "x-small",
                                variant: "text",
                                disabled: index === prefDraft.value.length - 1,
                                onClick: ($event) => prefMove(index, 1)
                              }, null, 8, ["disabled", "onClick"]),
                              _createVNode$f(_component_v_btn, {
                                icon: "mdi-close",
                                size: "x-small",
                                variant: "text",
                                onClick: ($event) => prefRemove(index)
                              }, null, 8, ["onClick"])
                            ]),
                            default: _withCtx$e(() => [
                              _createVNode$f(_component_v_list_item_title, null, {
                                default: _withCtx$e(() => [
                                  _createTextVNode$e(_toDisplayString$i(name), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024);
                        }), 128)),
                        !prefDraft.value.length ? (_openBlock$i(), _createBlock$d(_component_v_list_item, { key: 0 }, {
                          default: _withCtx$e(() => [
                            _createVNode$f(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                              default: _withCtx$e(() => _cache[20] || (_cache[20] = [
                                _createTextVNode$e(" 还没有优先站点：按下面的候选加进来。 ")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        })) : _createCommentVNode$c("", true)
                      ]),
                      _: 1
                    }),
                    _createVNode$f(_component_v_divider, { class: "mb-2" }),
                    _cache[21] || (_cache[21] = _createElementVNode$g("div", { class: "text-caption text-medium-emphasis mb-1" }, "候选站点（点击加入优先顺序）", -1)),
                    _createElementVNode$g("div", _hoisted_13$4, [
                      (_openBlock$i(true), _createElementBlock$h(_Fragment$a, null, _renderList$9(prefCandidates.value, (item) => {
                        return _openBlock$i(), _createBlock$d(_component_v_chip, {
                          key: item.name,
                          size: "small",
                          variant: "tonal",
                          "prepend-icon": "mdi-plus",
                          onClick: ($event) => prefAdd(item.name)
                        }, {
                          default: _withCtx$e(() => [
                            _createTextVNode$e(_toDisplayString$i(item.name), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"]);
                      }), 128)),
                      !prefCandidates.value.length ? (_openBlock$i(), _createElementBlock$h("span", _hoisted_14$3, " 全部站点都已在优先列表里。 ")) : _createCommentVNode$c("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode$f(_component_v_card_actions, null, {
                  default: _withCtx$e(() => [
                    _createVNode$f(_component_v_spacer),
                    _createVNode$f(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[3] || (_cache[3] = ($event) => prefOpen.value = false)
                    }, {
                      default: _withCtx$e(() => _cache[22] || (_cache[22] = [
                        _createTextVNode$e("取消")
                      ])),
                      _: 1
                    }),
                    _createVNode$f(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: prefConfirm
                    }, {
                      default: _withCtx$e(() => _cache[23] || (_cache[23] = [
                        _createTextVNode$e("确定")
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

const SitesPanel = /* @__PURE__ */ _export_sfc(_sfc_main$i, [["__scopeId", "data-v-b3e77efa"]]);

const {defineComponent:_defineComponent$h} = await importShared('vue');

const {resolveComponent:_resolveComponent$d,createVNode:_createVNode$e,createTextVNode:_createTextVNode$d,withCtx:_withCtx$d,createElementVNode:_createElementVNode$f,renderList:_renderList$8,Fragment:_Fragment$9,openBlock:_openBlock$h,createElementBlock:_createElementBlock$g,toDisplayString:_toDisplayString$h,unref:_unref$2,createBlock:_createBlock$c} = await importShared('vue');

const _hoisted_1$g = { class: "avh-grid mb-2" };
const _sfc_main$h = /* @__PURE__ */ _defineComponent$h({
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
      const _component_v_icon = _resolveComponent$d("v-icon");
      const _component_v_card_title = _resolveComponent$d("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$d("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$d("v-card-item");
      const _component_v_btn = _resolveComponent$d("v-btn");
      const _component_v_btn_toggle = _resolveComponent$d("v-btn-toggle");
      const _component_v_switch = _resolveComponent$d("v-switch");
      const _component_v_text_field = _resolveComponent$d("v-text-field");
      const _component_v_alert = _resolveComponent$d("v-alert");
      const _component_v_card_text = _resolveComponent$d("v-card-text");
      const _component_v_card = _resolveComponent$d("v-card");
      return _openBlock$h(), _createBlock$c(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$d(() => [
          _createVNode$e(_component_v_card_item, null, {
            prepend: _withCtx$d(() => [
              _createVNode$e(_component_v_icon, {
                icon: "mdi-filter-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$d(() => [
              _createVNode$e(_component_v_card_title, null, {
                default: _withCtx$d(() => _cache[8] || (_cache[8] = [
                  _createTextVNode$d("下载规则")
                ])),
                _: 1
              }),
              _createVNode$e(_component_v_card_subtitle, null, {
                default: _withCtx$d(() => _cache[9] || (_cache[9] = [
                  _createTextVNode$d("手动搜索与新建订阅的基准 · 数据走 POST /rule")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$e(_component_v_card_text, null, {
            default: _withCtx$d(() => [
              _cache[12] || (_cache[12] = _createElementVNode$f("div", { class: "text-caption text-medium-emphasis mb-1" }, "分辨率策略", -1)),
              _createVNode$e(_component_v_btn_toggle, {
                "model-value": props.rule.res,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-4",
                "onUpdate:modelValue": _cache[0] || (_cache[0] = (value) => value && patch("res", value))
              }, {
                default: _withCtx$d(() => [
                  (_openBlock$h(), _createElementBlock$g(_Fragment$9, null, _renderList$8(RES_OPTIONS, (option) => {
                    return _createVNode$e(_component_v_btn, {
                      key: option.value,
                      value: option.value
                    }, {
                      default: _withCtx$d(() => [
                        _createTextVNode$d(_toDisplayString$h(option.label), 1)
                      ]),
                      _: 2
                    }, 1032, ["value"]);
                  }), 64))
                ]),
                _: 1
              }, 8, ["model-value"]),
              _createVNode$e(_component_v_switch, {
                "model-value": props.rule.mustCnsub,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "必须中文字幕",
                class: "mb-1",
                "onUpdate:modelValue": _cache[1] || (_cache[1] = (value) => patch("mustCnsub", value === true))
              }, null, 8, ["model-value"]),
              _cache[13] || (_cache[13] = _createElementVNode$f("p", { class: "text-caption text-medium-emphasis mb-3" }, " 打开则没有中字的种直接淘汰；默认关（AV 站中字少，关掉时中字仍加 32 分优先选）。 ", -1)),
              _createVNode$e(_component_v_switch, {
                "model-value": props.rule.preferUncensored,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "破解 / 无码版优先",
                class: "mb-3",
                "onUpdate:modelValue": _cache[2] || (_cache[2] = (value) => patch("preferUncensored", value === true))
              }, null, 8, ["model-value"]),
              _createVNode$e(_component_v_switch, {
                "model-value": props.rule.allow4k,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "允许 4K 择优",
                class: "mb-1",
                "onUpdate:modelValue": _cache[3] || (_cache[3] = (value) => patch("allow4k", value === true))
              }, null, 8, ["model-value"]),
              _cache[14] || (_cache[14] = _createElementVNode$f("p", { class: "text-caption text-medium-emphasis mb-3" }, "1080P 没有好种时升级 4K。", -1)),
              _createElementVNode$f("div", _hoisted_1$g, [
                _createVNode$e(_component_v_text_field, {
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
                _createVNode$e(_component_v_text_field, {
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
                _createVNode$e(_component_v_text_field, {
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
              _createVNode$e(_component_v_switch, {
                "model-value": props.rule.btFallback,
                color: "primary",
                "hide-details": "",
                inset: "",
                label: "PT 搜不到时允许 BT 磁力兜底",
                class: "mb-3",
                "onUpdate:modelValue": _cache[6] || (_cache[6] = (value) => patch("btFallback", value === true))
              }, null, 8, ["model-value"]),
              _cache[15] || (_cache[15] = _createElementVNode$f("div", { class: "text-caption text-medium-emphasis mb-1" }, "命中之后", -1)),
              _createVNode$e(_component_v_btn_toggle, {
                "model-value": props.rule.trigger,
                mandatory: "",
                density: "comfortable",
                variant: "outlined",
                color: "primary",
                class: "mb-1",
                "onUpdate:modelValue": _cache[7] || (_cache[7] = (value) => value && patch("trigger", value))
              }, {
                default: _withCtx$d(() => [
                  _createVNode$e(_component_v_btn, { value: "notify" }, {
                    default: _withCtx$d(() => _cache[10] || (_cache[10] = [
                      _createTextVNode$d("仅通知")
                    ])),
                    _: 1
                  }),
                  _createVNode$e(_component_v_btn, { value: "auto" }, {
                    default: _withCtx$d(() => _cache[11] || (_cache[11] = [
                      _createTextVNode$d("自动下载")
                    ])),
                    _: 1
                  })
                ]),
                _: 1
              }, 8, ["model-value"]),
              _cache[16] || (_cache[16] = _createElementVNode$f("p", { class: "text-caption text-medium-emphasis mb-4" }, " 「仅通知」时命中的片进「任务」页等你手动下载。 ", -1)),
              _createVNode$e(_component_v_alert, {
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption"
              }, {
                default: _withCtx$d(() => [
                  _createTextVNode$d(" 搜索范围由左栏「搜索站点」决定：当前 " + _toDisplayString$h(props.siteScopeCount ? `限定 ${props.siteScopeCount} 个站点` : "全部已配置站点") + "。 保存路径 / 下载器 / qB 分类仍在插件存储里沿用现值（本栏暂不提供编辑入口）。 ", 1)
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

const RulePanel = /* @__PURE__ */ _export_sfc(_sfc_main$h, [["__scopeId", "data-v-32a4e634"]]);

const {defineComponent:_defineComponent$g} = await importShared('vue');

const {resolveComponent:_resolveComponent$c,createVNode:_createVNode$d,createTextVNode:_createTextVNode$c,withCtx:_withCtx$c,toDisplayString:_toDisplayString$g,openBlock:_openBlock$g,createBlock:_createBlock$b,createCommentVNode:_createCommentVNode$b,createElementVNode:_createElementVNode$e,renderList:_renderList$7,Fragment:_Fragment$8,createElementBlock:_createElementBlock$f} = await importShared('vue');

const _hoisted_1$f = { class: "avh-counts mb-3" };
const {computed: computed$b,ref: ref$b,watch: watch$6} = await importShared('vue');

const LEGACY_SEEN_KEY = "avh.noticesSeen";
const PANEL_SEEN_KEY = "avhnext.settings.noticesSeen";
const _sfc_main$g = /* @__PURE__ */ _defineComponent$g({
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
    const panelSeen = ref$b(readStorage(PANEL_SEEN_KEY));
    const legacySeen = ref$b(readStorage(LEGACY_SEEN_KEY));
    function readStorage(key) {
      try {
        return localStorage.getItem(key) || "";
      } catch {
        return "";
      }
    }
    const total = computed$b(() => props.notices.length);
    const unread = computed$b(
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
    watch$6(
      () => props.notices,
      () => {
        legacySeen.value = readStorage(LEGACY_SEEN_KEY);
        setTimeout(markSeen, 0);
      },
      { immediate: true }
    );
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$c("v-icon");
      const _component_v_card_title = _resolveComponent$c("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$c("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$c("v-card-item");
      const _component_v_chip = _resolveComponent$c("v-chip");
      const _component_v_list_item_title = _resolveComponent$c("v-list-item-title");
      const _component_v_list_item_subtitle = _resolveComponent$c("v-list-item-subtitle");
      const _component_v_list_item = _resolveComponent$c("v-list-item");
      const _component_v_list = _resolveComponent$c("v-list");
      const _component_v_alert = _resolveComponent$c("v-alert");
      const _component_v_card_text = _resolveComponent$c("v-card-text");
      const _component_v_btn = _resolveComponent$c("v-btn");
      const _component_v_spacer = _resolveComponent$c("v-spacer");
      const _component_v_card_actions = _resolveComponent$c("v-card-actions");
      const _component_v_card = _resolveComponent$c("v-card");
      return _openBlock$g(), _createBlock$b(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$c(() => [
          _createVNode$d(_component_v_card_item, null, {
            prepend: _withCtx$c(() => [
              _createVNode$d(_component_v_icon, {
                icon: "mdi-bell",
                color: "primary"
              })
            ]),
            default: _withCtx$c(() => [
              _createVNode$d(_component_v_card_title, null, {
                default: _withCtx$c(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$c("通知")
                ])),
                _: 1
              }),
              _createVNode$d(_component_v_card_subtitle, null, {
                default: _withCtx$c(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$c("渠道沿用 MoviePilot 原生通知 · 本插件不另建渠道")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$d(_component_v_card_text, null, {
            default: _withCtx$c(() => [
              _createElementVNode$e("div", _hoisted_1$f, [
                _createVNode$d(_component_v_chip, {
                  color: "primary",
                  variant: "tonal",
                  size: "small"
                }, {
                  default: _withCtx$c(() => [
                    _createTextVNode$c(" 未读 " + _toDisplayString$g(unread.value) + " / 共 " + _toDisplayString$g(total.value), 1)
                  ]),
                  _: 1
                }),
                legacySeen.value ? (_openBlock$g(), _createBlock$b(_component_v_chip, {
                  key: 0,
                  variant: "text",
                  size: "small",
                  class: "text-caption"
                }, {
                  default: _withCtx$c(() => [
                    _createTextVNode$c(" 内嵌应用已读到 " + _toDisplayString$g(legacySeen.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode$b("", true)
              ]),
              _cache[5] || (_cache[5] = _createElementVNode$e("p", { class: "text-caption text-medium-emphasis mb-2" }, " 通知由 MoviePilot 原生的通知渠道发出（在「设置 → 通知」里配置），这里看到的只是插件自己的收件箱。 打开本栏即算已读。 ", -1)),
              _ctx.notices.length ? (_openBlock$g(), _createBlock$b(_component_v_list, {
                key: 0,
                density: "compact",
                class: "avh-notices mb-2"
              }, {
                default: _withCtx$c(() => [
                  (_openBlock$g(true), _createElementBlock$f(_Fragment$8, null, _renderList$7(_ctx.notices.slice(0, 20), (item, index) => {
                    return _openBlock$g(), _createBlock$b(_component_v_list_item, { key: index }, {
                      prepend: _withCtx$c(() => [
                        _createVNode$d(_component_v_icon, {
                          icon: item.kind === "ok" ? "mdi-check-circle-outline" : item.kind === "warn" ? "mdi-alert-outline" : "mdi-robot-outline",
                          color: item.kind === "ok" ? "success" : item.kind === "warn" ? "warning" : "primary",
                          size: "small"
                        }, null, 8, ["icon", "color"])
                      ]),
                      default: _withCtx$c(() => [
                        _createVNode$d(_component_v_list_item_title, { class: "text-body-2" }, {
                          default: _withCtx$c(() => [
                            _createTextVNode$c(_toDisplayString$g(item.title || item.body || "（无标题）"), 1)
                          ]),
                          _: 2
                        }, 1024),
                        _createVNode$d(_component_v_list_item_subtitle, { class: "text-caption" }, {
                          default: _withCtx$c(() => [
                            _createTextVNode$c(_toDisplayString$g(item.type || "系统消息") + " · " + _toDisplayString$g(item.time || "—"), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024);
                  }), 128)),
                  _ctx.notices.length > 20 ? (_openBlock$g(), _createBlock$b(_component_v_list_item, { key: 0 }, {
                    default: _withCtx$c(() => [
                      _createVNode$d(_component_v_list_item_title, { class: "text-caption text-medium-emphasis" }, {
                        default: _withCtx$c(() => [
                          _createTextVNode$c(" 只显示最近 20 条，其余 " + _toDisplayString$g(_ctx.notices.length - 20) + " 条在数据台的铃铛里。 ", 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$b("", true)
                ]),
                _: 1
              })) : (_openBlock$g(), _createBlock$b(_component_v_alert, {
                key: 1,
                type: "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-0"
              }, {
                default: _withCtx$c(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$c(" 暂无通知。 ")
                ])),
                _: 1
              }))
            ]),
            _: 1
          }),
          _createVNode$d(_component_v_card_actions, null, {
            default: _withCtx$c(() => [
              _createVNode$d(_component_v_btn, {
                variant: "text",
                "prepend-icon": "mdi-refresh",
                loading: props.loading,
                onClick: _cache[0] || (_cache[0] = ($event) => emit("reload"))
              }, {
                default: _withCtx$c(() => _cache[6] || (_cache[6] = [
                  _createTextVNode$c("刷新")
                ])),
                _: 1
              }, 8, ["loading"]),
              _createVNode$d(_component_v_spacer),
              _createVNode$d(_component_v_btn, {
                color: "error",
                variant: "tonal",
                "prepend-icon": "mdi-bell-off-outline",
                disabled: !total.value,
                loading: props.clearing,
                onClick: _cache[1] || (_cache[1] = ($event) => emit("clear"))
              }, {
                default: _withCtx$c(() => _cache[7] || (_cache[7] = [
                  _createTextVNode$c("清空通知")
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

const NotifyPanel = /* @__PURE__ */ _export_sfc(_sfc_main$g, [["__scopeId", "data-v-0c6f3cc7"]]);

const {defineComponent:_defineComponent$f} = await importShared('vue');

const {resolveComponent:_resolveComponent$b,createVNode:_createVNode$c,createTextVNode:_createTextVNode$b,withCtx:_withCtx$b,Fragment:_Fragment$7,openBlock:_openBlock$f,createElementBlock:_createElementBlock$e,toDisplayString:_toDisplayString$f,createBlock:_createBlock$a} = await importShared('vue');

const {ref: ref$a} = await importShared('vue');

const _sfc_main$f = /* @__PURE__ */ _defineComponent$f({
  __name: "LibraryPanel",
  props: {
    config: {},
    validation: {}
  },
  emits: ["patch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const showKey = ref$a(false);
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
      const _component_v_icon = _resolveComponent$b("v-icon");
      const _component_v_card_title = _resolveComponent$b("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$b("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$b("v-card-item");
      const _component_v_alert = _resolveComponent$b("v-alert");
      const _component_v_text_field = _resolveComponent$b("v-text-field");
      const _component_v_card_text = _resolveComponent$b("v-card-text");
      const _component_v_card = _resolveComponent$b("v-card");
      return _openBlock$f(), _createBlock$a(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$b(() => [
          _createVNode$c(_component_v_card_item, null, {
            prepend: _withCtx$b(() => [
              _createVNode$c(_component_v_icon, {
                icon: "mdi-server",
                color: "primary"
              })
            ]),
            default: _withCtx$b(() => [
              _createVNode$c(_component_v_card_title, null, {
                default: _withCtx$b(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$b("媒体库")
                ])),
                _: 1
              }),
              _createVNode$c(_component_v_card_subtitle, null, {
                default: _withCtx$b(() => _cache[4] || (_cache[4] = [
                  _createTextVNode$b("Emby 地址与密钥 · 两栏都空 = 复用 MoviePilot 的媒体服务器")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$c(_component_v_card_text, null, {
            default: _withCtx$b(() => [
              _createVNode$c(_component_v_alert, {
                type: mode() === "half" ? "warning" : mode() === "own" ? "success" : "info",
                variant: "tonal",
                density: "compact",
                class: "text-caption mb-4"
              }, {
                default: _withCtx$b(() => [
                  mode() === "reuse" ? (_openBlock$f(), _createElementBlock$e(_Fragment$7, { key: 0 }, [
                    _createTextVNode$b(" 当前：复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby（两栏留空即是这个状态）。 ")
                  ], 64)) : mode() === "own" ? (_openBlock$f(), _createElementBlock$e(_Fragment$7, { key: 1 }, [
                    _createTextVNode$b(" 当前：使用下面填写的 Emby，不再走 MoviePilot 的媒体服务器配置。 ")
                  ], 64)) : (_openBlock$f(), _createElementBlock$e(_Fragment$7, { key: 2 }, [
                    _createTextVNode$b(_toDisplayString$f(props.validation || "Emby 地址与 API 密钥要一起填，否则会回落到 MoviePilot 的媒体服务器。"), 1)
                  ], 64))
                ]),
                _: 1
              }, 8, ["type"]),
              _createVNode$c(_component_v_text_field, {
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
              _createVNode$c(_component_v_text_field, {
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

const LibraryPanel = /* @__PURE__ */ _export_sfc(_sfc_main$f, [["__scopeId", "data-v-d05104fc"]]);

const {defineComponent:_defineComponent$e} = await importShared('vue');

const {resolveComponent:_resolveComponent$a,createVNode:_createVNode$b,createTextVNode:_createTextVNode$a,withCtx:_withCtx$a,createElementVNode:_createElementVNode$d,toDisplayString:_toDisplayString$e,openBlock:_openBlock$e,createBlock:_createBlock$9,createCommentVNode:_createCommentVNode$a,createElementBlock:_createElementBlock$d} = await importShared('vue');

const _hoisted_1$e = { class: "avh-cache" };
const _hoisted_2$e = { class: "text-h6" };
const _hoisted_3$d = { class: "avh-cache-actions" };
const _hoisted_4$b = { class: "text-body-2 font-weight-medium" };
const _hoisted_5$9 = { class: "text-body-2" };
const _hoisted_6$7 = { class: "text-body-2" };
const _hoisted_7$7 = { class: "text-body-2" };
const _hoisted_8$7 = { class: "text-caption text-medium-emphasis mt-3 mb-0" };
const _hoisted_9$7 = { key: 0 };
const {computed: computed$a} = await importShared('vue');
const DASH$1 = "—";
const _sfc_main$e = /* @__PURE__ */ _defineComponent$e({
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
    const cacheLabel = computed$a(() => props.cacheText ? props.cacheText : DASH$1);
    const todayLabel = computed$a(() => {
      const info = props.check;
      if (!info || info.checkedToday === void 0) return DASH$1;
      const limit = info.maxPerDay === void 0 ? DASH$1 : info.maxPerDay;
      return `${info.checkedToday} / ${limit}`;
    });
    const lastCheckLabel = computed$a(() => formatCheckTime(props.check?.lastCheck, "last"));
    const nextCheckLabel = computed$a(() => formatCheckTime(props.check?.nextAt, "next"));
    const intervalLabel = computed$a(() => {
      const minutes = props.check?.minIntervalMin;
      return minutes === void 0 ? DASH$1 : `${minutes} 分钟`;
    });
    const checkMissing = computed$a(() => props.check === null);
    const blockedLabel = computed$a(() => {
      const info = props.check;
      if (!info) return "";
      if (info.allowed === false) return info.reason || "当前不可执行检查（受限流约束）";
      return "";
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$a("v-icon");
      const _component_v_card_title = _resolveComponent$a("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$a("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$a("v-card-item");
      const _component_v_btn = _resolveComponent$a("v-btn");
      const _component_v_divider = _resolveComponent$a("v-divider");
      const _component_v_list_item_title = _resolveComponent$a("v-list-item-title");
      const _component_v_list_item = _resolveComponent$a("v-list-item");
      const _component_v_list = _resolveComponent$a("v-list");
      const _component_v_alert = _resolveComponent$a("v-alert");
      const _component_v_card_text = _resolveComponent$a("v-card-text");
      const _component_v_card = _resolveComponent$a("v-card");
      return _openBlock$e(), _createBlock$9(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$a(() => [
          _createVNode$b(_component_v_card_item, null, {
            prepend: _withCtx$a(() => [
              _createVNode$b(_component_v_icon, {
                icon: "mdi-database-cog",
                color: "primary"
              })
            ]),
            default: _withCtx$a(() => [
              _createVNode$b(_component_v_card_title, null, {
                default: _withCtx$a(() => _cache[2] || (_cache[2] = [
                  _createTextVNode$a("运行与缓存")
                ])),
                _: 1
              }),
              _createVNode$b(_component_v_card_subtitle, null, {
                default: _withCtx$a(() => _cache[3] || (_cache[3] = [
                  _createTextVNode$a("缓存占用与清理 · 限流参数只读")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$b(_component_v_card_text, null, {
            default: _withCtx$a(() => [
              _createElementVNode$d("div", _hoisted_1$e, [
                _createElementVNode$d("div", null, [
                  _cache[4] || (_cache[4] = _createElementVNode$d("div", { class: "text-caption text-medium-emphasis" }, "缓存占用", -1)),
                  _createElementVNode$d("div", _hoisted_2$e, _toDisplayString$e(cacheLabel.value), 1)
                ]),
                _createElementVNode$d("div", _hoisted_3$d, [
                  _createVNode$b(_component_v_btn, {
                    color: "warning",
                    variant: "tonal",
                    "prepend-icon": "mdi-broom",
                    loading: props.cleaning,
                    onClick: _cache[0] || (_cache[0] = ($event) => emit("clean"))
                  }, {
                    default: _withCtx$a(() => _cache[5] || (_cache[5] = [
                      _createTextVNode$a("清理缓存")
                    ])),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode$b(_component_v_btn, {
                    variant: "text",
                    "prepend-icon": "mdi-refresh",
                    loading: props.loading,
                    class: "mt-2",
                    onClick: _cache[1] || (_cache[1] = ($event) => emit("refresh"))
                  }, {
                    default: _withCtx$a(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$a("刷新")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              _createVNode$b(_component_v_divider, { class: "my-4" }),
              _cache[13] || (_cache[13] = _createElementVNode$d("div", { class: "text-subtitle-2 mb-2" }, "订阅检查限流（只读）", -1)),
              _createVNode$b(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$a(() => [
                  _createVNode$b(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$a(() => [
                      _createElementVNode$d("span", _hoisted_4$b, _toDisplayString$e(todayLabel.value), 1)
                    ]),
                    default: _withCtx$a(() => [
                      _createVNode$b(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$a(() => _cache[7] || (_cache[7] = [
                          _createTextVNode$a("今天已检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$b(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$a(() => [
                      _createElementVNode$d("span", _hoisted_5$9, _toDisplayString$e(lastCheckLabel.value), 1)
                    ]),
                    default: _withCtx$a(() => [
                      _createVNode$b(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$a(() => _cache[8] || (_cache[8] = [
                          _createTextVNode$a("上次检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$b(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$a(() => [
                      _createElementVNode$d("span", _hoisted_6$7, _toDisplayString$e(nextCheckLabel.value), 1)
                    ]),
                    default: _withCtx$a(() => [
                      _createVNode$b(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$a(() => _cache[9] || (_cache[9] = [
                          _createTextVNode$a("下次可检查")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$b(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$a(() => [
                      _createElementVNode$d("span", _hoisted_7$7, _toDisplayString$e(intervalLabel.value), 1)
                    ]),
                    default: _withCtx$a(() => [
                      _createVNode$b(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$a(() => _cache[10] || (_cache[10] = [
                          _createTextVNode$a("间隔下限")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              blockedLabel.value ? (_openBlock$e(), _createBlock$9(_component_v_alert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "text-caption mt-2"
              }, {
                default: _withCtx$a(() => [
                  _createTextVNode$a(_toDisplayString$e(blockedLabel.value), 1)
                ]),
                _: 1
              })) : _createCommentVNode$a("", true),
              _createElementVNode$d("p", _hoisted_8$7, [
                _cache[12] || (_cache[12] = _createTextVNode$a(" 限流参数按用户明确要求固定（每天 ≤6 次、间隔 ≥240 分钟），界面不提供放宽入口。 ")),
                checkMissing.value ? (_openBlock$e(), _createElementBlock$d("span", _hoisted_9$7, _cache[11] || (_cache[11] = [
                  _createTextVNode$a(" 当前后端还没返回 "),
                  _createElementVNode$d("code", null, "check", -1),
                  _createTextVNode$a(" 字段（本轮正在补），所以上面几行显示 "),
                  _createElementVNode$d("code", null, "—", -1),
                  _createTextVNode$a("；字段上线后自动显示。 ")
                ]))) : _createCommentVNode$a("", true)
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

const RuntimePanel = /* @__PURE__ */ _export_sfc(_sfc_main$e, [["__scopeId", "data-v-cd2af22c"]]);

const {defineComponent:_defineComponent$d} = await importShared('vue');

const {resolveComponent:_resolveComponent$9,createVNode:_createVNode$a,createTextVNode:_createTextVNode$9,withCtx:_withCtx$9,toDisplayString:_toDisplayString$d,createElementVNode:_createElementVNode$c,openBlock:_openBlock$d,createBlock:_createBlock$8,createCommentVNode:_createCommentVNode$9} = await importShared('vue');

const _hoisted_1$d = { class: "text-body-2 font-weight-medium" };
const _hoisted_2$d = { class: "text-body-2 font-weight-medium" };
const _hoisted_3$c = { class: "text-body-2" };
const DASH = "—";
const DATA_ROOT = "/avhelper/next/cache";
const JAVDB_BIN = "/avhelper/bin/javdb";
const _sfc_main$d = /* @__PURE__ */ _defineComponent$d({
  __name: "AboutPanel",
  props: {
    version: {},
    pluginId: {},
    sourcePluginId: {}
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$9("v-icon");
      const _component_v_card_title = _resolveComponent$9("v-card-title");
      const _component_v_card_subtitle = _resolveComponent$9("v-card-subtitle");
      const _component_v_card_item = _resolveComponent$9("v-card-item");
      const _component_v_list_item_title = _resolveComponent$9("v-list-item-title");
      const _component_v_list_item = _resolveComponent$9("v-list-item");
      const _component_v_list = _resolveComponent$9("v-list");
      const _component_v_divider = _resolveComponent$9("v-divider");
      const _component_v_card_text = _resolveComponent$9("v-card-text");
      const _component_v_card = _resolveComponent$9("v-card");
      return _openBlock$d(), _createBlock$8(_component_v_card, {
        variant: "tonal",
        class: "avh-panel"
      }, {
        default: _withCtx$9(() => [
          _createVNode$a(_component_v_card_item, null, {
            prepend: _withCtx$9(() => [
              _createVNode$a(_component_v_icon, {
                icon: "mdi-information-outline",
                color: "primary"
              })
            ]),
            default: _withCtx$9(() => [
              _createVNode$a(_component_v_card_title, null, {
                default: _withCtx$9(() => _cache[0] || (_cache[0] = [
                  _createTextVNode$9("关于")
                ])),
                _: 1
              }),
              _createVNode$a(_component_v_card_subtitle, null, {
                default: _withCtx$9(() => _cache[1] || (_cache[1] = [
                  _createTextVNode$9("AVHelperNext · Vue 联邦渲染模式")
                ])),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode$a(_component_v_card_text, null, {
            default: _withCtx$9(() => [
              _createVNode$a(_component_v_list, {
                density: "compact",
                class: "pa-0"
              }, {
                default: _withCtx$9(() => [
                  _createVNode$a(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$9(() => [
                      _createElementVNode$c("span", _hoisted_1$d, _toDisplayString$d(props.version || DASH), 1)
                    ]),
                    default: _withCtx$9(() => [
                      _createVNode$a(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$9(() => _cache[2] || (_cache[2] = [
                          _createTextVNode$9("版本号")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$a(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$9(() => [
                      _createElementVNode$c("span", _hoisted_2$d, _toDisplayString$d(props.pluginId || DASH), 1)
                    ]),
                    default: _withCtx$9(() => [
                      _createVNode$a(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$9(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$9("插件 ID")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  props.sourcePluginId ? (_openBlock$d(), _createBlock$8(_component_v_list_item, {
                    key: 0,
                    class: "px-0"
                  }, {
                    append: _withCtx$9(() => [
                      _createElementVNode$c("span", _hoisted_3$c, _toDisplayString$d(props.sourcePluginId), 1)
                    ]),
                    default: _withCtx$9(() => [
                      _createVNode$a(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$9(() => _cache[4] || (_cache[4] = [
                          _createTextVNode$9("源插件 ID（分身）")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })) : _createCommentVNode$9("", true),
                  _createVNode$a(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$9(() => [
                      _createElementVNode$c("span", { class: "text-body-2" }, [
                        _createElementVNode$c("code", null, _toDisplayString$d(DATA_ROOT))
                      ])
                    ]),
                    default: _withCtx$9(() => [
                      _createVNode$a(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$9(() => _cache[5] || (_cache[5] = [
                          _createTextVNode$9("数据根")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  _createVNode$a(_component_v_list_item, { class: "px-0" }, {
                    append: _withCtx$9(() => [
                      _createElementVNode$c("span", { class: "text-body-2" }, [
                        _createElementVNode$c("code", null, _toDisplayString$d(JAVDB_BIN)),
                        _cache[7] || (_cache[7] = _createTextVNode$9("（与原版共用，只读）"))
                      ])
                    ]),
                    default: _withCtx$9(() => [
                      _createVNode$a(_component_v_list_item_title, { class: "text-body-2" }, {
                        default: _withCtx$9(() => _cache[6] || (_cache[6] = [
                          _createTextVNode$9("javdb 二进制")
                        ])),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$a(_component_v_divider, { class: "my-3" }),
              _createElementVNode$c("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                _cache[8] || (_cache[8] = _createTextVNode$9(" 数据根在插件数据卷上：SQLite 落在 ")),
                _createElementVNode$c("code", null, _toDisplayString$d(DATA_ROOT) + "/meta/avhelper.db"),
                _cache[9] || (_cache[9] = _createTextVNode$9("，图片与 JSON 缓存同根。 重构版用 ")),
                _cache[10] || (_cache[10] = _createElementVNode$c("code", null, "/avhelper/next/…", -1)),
                _cache[11] || (_cache[11] = _createTextVNode$9(" 与原版 ")),
                _cache[12] || (_cache[12] = _createElementVNode$c("code", null, "/avhelper/cache", -1)),
                _cache[13] || (_cache[13] = _createTextVNode$9(" 完全隔离， 两边不共用同一个 SQLite（合并回原插件时才会收敛）。 "))
              ]),
              _cache[14] || (_cache[14] = _createElementVNode$c("p", { class: "text-caption text-medium-emphasis mb-0" }, [
                _createTextVNode$9(" 界面上方是宿主的统一弹窗：标题栏、关闭按钮与 Toast 都由宿主提供，本插件复用 "),
                _createElementVNode$c("code", null, "moviepilot:toast"),
                _createTextVNode$9(" / "),
                _createElementVNode$c("code", null, "moviepilot:confirm"),
                _createTextVNode$9("，不自建。 版本号来自 "),
                _createElementVNode$c("code", null, "plugin/page/<id>"),
                _createTextVNode$9(" 的 "),
                _createElementVNode$c("code", null, "plugin_version"),
                _createTextVNode$9("，取不到显示 "),
                _createElementVNode$c("code", null, "—"),
                _createTextVNode$9("。 ")
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

const AboutPanel = /* @__PURE__ */ _export_sfc(_sfc_main$d, [["__scopeId", "data-v-932b5a1b"]]);

const {defineComponent:_defineComponent$c} = await importShared('vue');

const {openBlock:_openBlock$c,createElementBlock:_createElementBlock$c,toDisplayString:_toDisplayString$c,normalizeClass:_normalizeClass$6} = await importShared('vue');

const _hoisted_1$c = ["src", "alt", "loading"];
const _hoisted_2$c = {
  key: 1,
  class: "avh-thumb__noimg"
};
const {computed: computed$9,ref: ref$9,watch: watch$5} = await importShared('vue');

const PROXY_MARK = "/img?url=";
const _sfc_main$c = /* @__PURE__ */ _defineComponent$c({
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
    const useProxy = ref$9(false);
    const failed = ref$9(false);
    watch$5(
      () => props.src,
      () => {
        useProxy.value = false;
        failed.value = false;
      }
    );
    const proxySrc = computed$9(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (raw.includes(PROXY_MARK)) return raw;
      if (!props.pluginId) return "";
      return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`;
    });
    const currentSrc = computed$9(() => {
      const raw = String(props.src || "");
      if (!raw) return "";
      if (!useProxy.value) return raw;
      return proxySrc.value;
    });
    const showPlaceholder = computed$9(
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
      return _openBlock$c(), _createElementBlock$c("div", {
        class: _normalizeClass$6(["avh-thumb", `avh-thumb--${_ctx.variant}`])
      }, [
        !showPlaceholder.value ? (_openBlock$c(), _createElementBlock$c("img", {
          key: 0,
          src: currentSrc.value,
          alt: _ctx.alt,
          referrerpolicy: "no-referrer",
          loading: _ctx.lazy ? "lazy" : "eager",
          decoding: "async",
          onError
        }, null, 40, _hoisted_1$c)) : (_openBlock$c(), _createElementBlock$c("div", _hoisted_2$c, _toDisplayString$c(_ctx.alt || "无图"), 1))
      ], 2);
    };
  }
});

const Thumb = /* @__PURE__ */ _export_sfc(_sfc_main$c, [["__scopeId", "data-v-983b098d"]]);

const {ref: ref$8} = await importShared('vue');

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
const filledThumbs = ref$8({});
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

const {defineComponent:_defineComponent$b} = await importShared('vue');

const {createVNode:_createVNode$9,toDisplayString:_toDisplayString$b,createElementVNode:_createElementVNode$b,openBlock:_openBlock$b,createElementBlock:_createElementBlock$b,createCommentVNode:_createCommentVNode$8,renderList:_renderList$6,Fragment:_Fragment$6,createTextVNode:_createTextVNode$8,normalizeClass:_normalizeClass$5,unref:_unref$1,resolveComponent:_resolveComponent$8,withCtx:_withCtx$8,createBlock:_createBlock$7} = await importShared('vue');

const _hoisted_1$b = { class: "avh-cand" };
const _hoisted_2$b = { class: "avh-cand__head" };
const _hoisted_3$b = { class: "avh-cand__no" };
const _hoisted_4$a = { class: "avh-cand__hint avh-cand__origin" };
const _hoisted_5$8 = {
  key: 0,
  class: "avh-cand__hint"
};
const _hoisted_6$6 = { class: "avh-cand__table" };
const _hoisted_7$6 = { key: 0 };
const _hoisted_8$6 = {
  key: 0,
  class: "avh-tag"
};
const _hoisted_9$6 = {
  key: 0,
  class: "avh-tag avh-tag--free"
};
const _hoisted_10$6 = {
  key: 1,
  class: "avh-tag avh-tag--pref"
};
const _hoisted_11$5 = ["title"];
const _hoisted_12$3 = { colspan: "9" };
const _hoisted_13$3 = ["title"];
const _hoisted_14$2 = { key: 0 };
const {computed: computed$8,ref: ref$7} = await importShared('vue');
const _sfc_main$b = /* @__PURE__ */ _defineComponent$b({
  __name: "CandTable",
  props: {
    task: {},
    pluginId: { default: "" }
  },
  emits: ["download"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const pending = ref$7({});
    const cands = computed$8(() => Array.isArray(props.task.cands) ? props.task.cands : []);
    const passedCount = computed$8(() => cands.value.filter((item) => item.pass !== false).length);
    const taskId = computed$8(() => String(props.task.id ?? ""));
    const rows = computed$8(() => {
      const pt = cands.value.filter((item) => item.src !== "BT");
      const bt = cands.value.filter((item) => item.src === "BT");
      const out = pt.map((cand, index) => ({ kind: "cand", key: `pt-${index}`, cand }));
      if (bt.length) {
        out.push({ kind: "btnote", key: "bt-note", cand: {} });
        bt.forEach((cand, index) => out.push({ kind: "cand", key: `bt-${index}`, cand }));
      }
      return out;
    });
    const origin = computed$8(() => {
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
    const poster = computed$8(() => {
      const own = String(props.task?.thumb || "");
      if (own) return own;
      return String(filledThumbs.value[String(props.task?.number || "")] || "");
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$8("v-btn");
      return _openBlock$b(), _createElementBlock$b("div", _hoisted_1$b, [
        _createElementVNode$b("div", _hoisted_2$b, [
          _createVNode$9(Thumb, {
            class: "avh-cand__poster",
            variant: "tposter",
            src: poster.value,
            alt: "无图",
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "plugin-id"]),
          _createElementVNode$b("div", null, [
            _createElementVNode$b("div", _hoisted_3$b, _toDisplayString$b(_ctx.task.number || ""), 1),
            _createElementVNode$b("div", _hoisted_4$a, _toDisplayString$b(origin.value) + " · 搜到 " + _toDisplayString$b(cands.value.length) + " · 合格 " + _toDisplayString$b(passedCount.value), 1)
          ]),
          _cache[0] || (_cache[0] = _createElementVNode$b("div", { class: "avh-cand__spacer" }, null, -1)),
          _ctx.task.auto && _ctx.task.source === "sub" ? (_openBlock$b(), _createElementBlock$b("span", _hoisted_5$8, " 订阅为自动下载，但无候选合格 ")) : _createCommentVNode$8("", true)
        ]),
        _createElementVNode$b("table", _hoisted_6$6, [
          _cache[5] || (_cache[5] = _createElementVNode$b("thead", null, [
            _createElementVNode$b("tr", null, [
              _createElementVNode$b("th", null, "站点"),
              _createElementVNode$b("th", null, "规格"),
              _createElementVNode$b("th", null, "中字"),
              _createElementVNode$b("th", null, "破解"),
              _createElementVNode$b("th", null, "大小"),
              _createElementVNode$b("th", null, "做种"),
              _createElementVNode$b("th", null, "标记"),
              _createElementVNode$b("th", null, "匹配分"),
              _createElementVNode$b("th")
            ])
          ], -1)),
          _createElementVNode$b("tbody", null, [
            (_openBlock$b(true), _createElementBlock$b(_Fragment$6, null, _renderList$6(rows.value, (row) => {
              return _openBlock$b(), _createElementBlock$b(_Fragment$6, {
                key: row.key
              }, [
                row.kind === "btnote" ? (_openBlock$b(), _createElementBlock$b("tr", _hoisted_7$6, _cache[1] || (_cache[1] = [
                  _createElementVNode$b("td", {
                    colspan: "9",
                    class: "avh-cand__hint avh-cand__btnote"
                  }, " — PT 没有合格候选，以下为 BT 磁力兜底 — ", -1)
                ]))) : (_openBlock$b(), _createElementBlock$b(_Fragment$6, { key: 1 }, [
                  _createElementVNode$b("tr", {
                    class: _normalizeClass$5(rowClass(row.cand))
                  }, [
                    _createElementVNode$b("td", null, [
                      row.cand.src === "BT" ? (_openBlock$b(), _createElementBlock$b("span", _hoisted_8$6, "BT")) : _createCommentVNode$8("", true),
                      _createTextVNode$8(" " + _toDisplayString$b(row.cand.site || ""), 1)
                    ]),
                    _createElementVNode$b("td", null, _toDisplayString$b(row.cand.spec || ""), 1),
                    _createElementVNode$b("td", null, [
                      _createElementVNode$b("span", {
                        class: _normalizeClass$5(["avh-tag", row.cand.cnsub ? "avh-tag--on" : ""])
                      }, _toDisplayString$b(row.cand.cnsub ? "有" : "无"), 3)
                    ]),
                    _createElementVNode$b("td", null, [
                      _createElementVNode$b("span", {
                        class: _normalizeClass$5(["avh-tag", row.cand.uncensored ? "avh-tag--uc" : ""])
                      }, _toDisplayString$b(row.cand.uncensored ? "破解" : "—"), 3)
                    ]),
                    _createElementVNode$b("td", null, _toDisplayString$b(row.cand.size || ""), 1),
                    _createElementVNode$b("td", null, _toDisplayString$b(seedersText(row.cand)), 1),
                    _createElementVNode$b("td", null, [
                      row.cand.free ? (_openBlock$b(), _createElementBlock$b("span", _hoisted_9$6, "免费")) : _createCommentVNode$8("", true),
                      row.cand.pref ? (_openBlock$b(), _createElementBlock$b("span", _hoisted_10$6, "优先站")) : _createCommentVNode$8("", true)
                    ]),
                    _createElementVNode$b("td", {
                      title: row.cand.breakdown || ""
                    }, [
                      _createElementVNode$b("span", {
                        class: _normalizeClass$5(["avh-score", `avh-score--${_unref$1(scoreLevel)(row.cand.score, isPass(row.cand))}`])
                      }, _toDisplayString$b(scoreText(row.cand)), 3)
                    ], 8, _hoisted_11$5),
                    _createElementVNode$b("td", null, [
                      isPass(row.cand) ? (_openBlock$b(), _createBlock$7(_component_v_btn, {
                        key: 0,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$8(() => _cache[2] || (_cache[2] = [
                          _createTextVNode$8("下载")
                        ])),
                        _: 2
                      }, 1032, ["loading", "onClick"])) : (_openBlock$b(), _createBlock$7(_component_v_btn, {
                        key: 1,
                        class: "avh-cand__dl",
                        variant: "outlined",
                        size: "small",
                        title: row.cand.breakdown || "",
                        loading: !!pending.value[siteKey(row.cand)],
                        onClick: ($event) => onDownload(row.cand)
                      }, {
                        default: _withCtx$8(() => _cache[3] || (_cache[3] = [
                          _createTextVNode$8("仍要下载")
                        ])),
                        _: 2
                      }, 1032, ["title", "loading", "onClick"]))
                    ])
                  ], 2),
                  titleOf(row.cand) ? (_openBlock$b(), _createElementBlock$b("tr", {
                    key: 0,
                    class: _normalizeClass$5(["avh-cand__sub", ...rowClass(row.cand)])
                  }, [
                    _createElementVNode$b("td", _hoisted_12$3, [
                      _createElementVNode$b("div", {
                        class: "avh-cand__ttl",
                        title: titleOf(row.cand)
                      }, _toDisplayString$b(titleOf(row.cand)), 9, _hoisted_13$3)
                    ])
                  ], 2)) : _createCommentVNode$8("", true)
                ], 64))
              ], 64);
            }), 128)),
            !cands.value.length ? (_openBlock$b(), _createElementBlock$b("tr", _hoisted_14$2, _cache[4] || (_cache[4] = [
              _createElementVNode$b("td", {
                colspan: "9",
                class: "avh-cand__hint avh-cand__empty"
              }, "没有搜到任何候选", -1)
            ]))) : _createCommentVNode$8("", true)
          ])
        ])
      ]);
    };
  }
});

const CandTable = /* @__PURE__ */ _export_sfc(_sfc_main$b, [["__scopeId", "data-v-c8aa0824"]]);

const {defineComponent:_defineComponent$a} = await importShared('vue');

const {createElementVNode:_createElementVNode$a,toDisplayString:_toDisplayString$a,openBlock:_openBlock$a,createElementBlock:_createElementBlock$a,createCommentVNode:_createCommentVNode$7,renderSlot:_renderSlot} = await importShared('vue');

const _hoisted_1$a = { class: "avh-empty" };
const _hoisted_2$a = ["innerHTML"];
const _hoisted_3$a = {
  key: 0,
  class: "avh-empty__hint"
};
const _hoisted_4$9 = {
  key: 1,
  class: "avh-empty__slot"
};
const _sfc_main$a = /* @__PURE__ */ _defineComponent$a({
  __name: "EmptyState",
  props: {
    text: { default: "" },
    hint: { default: "" }
  },
  setup(__props) {
    return (_ctx, _cache) => {
      return _openBlock$a(), _createElementBlock$a("div", _hoisted_1$a, [
        _createElementVNode$a("div", {
          class: "avh-empty__text",
          innerHTML: _ctx.text
        }, null, 8, _hoisted_2$a),
        _ctx.hint ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_3$a, _toDisplayString$a(_ctx.hint), 1)) : _createCommentVNode$7("", true),
        _ctx.$slots.default ? (_openBlock$a(), _createElementBlock$a("div", _hoisted_4$9, [
          _renderSlot(_ctx.$slots, "default", {}, void 0, true)
        ])) : _createCommentVNode$7("", true)
      ]);
    };
  }
});

const EmptyState = /* @__PURE__ */ _export_sfc(_sfc_main$a, [["__scopeId", "data-v-d928276a"]]);

const {defineComponent:_defineComponent$9} = await importShared('vue');

const {toDisplayString:_toDisplayString$9,createElementVNode:_createElementVNode$9,createTextVNode:_createTextVNode$7,resolveComponent:_resolveComponent$7,withCtx:_withCtx$7,createVNode:_createVNode$8,openBlock:_openBlock$9,createElementBlock:_createElementBlock$9,createCommentVNode:_createCommentVNode$6} = await importShared('vue');

const _hoisted_1$9 = {
  class: "avh-errbox",
  role: "alert"
};
const _hoisted_2$9 = { class: "avh-errbox__msg" };
const _hoisted_3$9 = {
  key: 0,
  class: "avh-errbox__act"
};
const _sfc_main$9 = /* @__PURE__ */ _defineComponent$9({
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
      const _component_v_btn = _resolveComponent$7("v-btn");
      return _openBlock$9(), _createElementBlock$9("div", _hoisted_1$9, [
        _createElementVNode$9("div", _hoisted_2$9, "⚠️ " + _toDisplayString$9(_ctx.message || "抓取失败，请稍后重试"), 1),
        _ctx.retryable ? (_openBlock$9(), _createElementBlock$9("div", _hoisted_3$9, [
          _createVNode$8(_component_v_btn, {
            color: "primary",
            variant: "flat",
            size: "small",
            loading: _ctx.retrying,
            onClick: _cache[0] || (_cache[0] = ($event) => emit("retry"))
          }, {
            default: _withCtx$7(() => [
              _createTextVNode$7(_toDisplayString$9(_ctx.retryText), 1)
            ]),
            _: 1
          }, 8, ["loading"])
        ])) : _createCommentVNode$6("", true)
      ]);
    };
  }
});

const ErrorState = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-8f8a571b"]]);

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

const {defineComponent:_defineComponent$8} = await importShared('vue');

const {resolveComponent:_resolveComponent$6,withKeys:_withKeys,createVNode:_createVNode$7,toDisplayString:_toDisplayString$8,createTextVNode:_createTextVNode$6,withCtx:_withCtx$6,createElementVNode:_createElementVNode$8,openBlock:_openBlock$8,createBlock:_createBlock$6,createElementBlock:_createElementBlock$8} = await importShared('vue');

const _hoisted_1$8 = { class: "avh-sitesearch" };
const _hoisted_2$8 = { class: "avh-sitesearch__toolbar" };
const _hoisted_3$8 = { class: "avh-sitesearch__hint" };
const _hoisted_4$8 = { class: "avh-sitesearch__range" };
const _hoisted_5$7 = ["title"];
const {computed: computed$7,nextTick: nextTick$1,ref: ref$6,watch: watch$4} = await importShared('vue');
const _sfc_main$8 = /* @__PURE__ */ _defineComponent$8({
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
    const candTableRef = ref$6(null);
    const keyword = ref$6("");
    const searching = ref$6(false);
    const searchedAt = ref$6("");
    const task = ref$6(null);
    const errorText = ref$6("");
    const retrying = ref$6(false);
    const siteNames = computed$7(
      () => props.store.sites.value.map((item) => String(item?.name || "")).filter(Boolean)
    );
    const picked = computed$7(() => {
      const names = siteNames.value;
      return (props.store.rule.value.sites || []).map(String).filter((name) => names.indexOf(name) >= 0);
    });
    function labelOf(name) {
      const hit = props.store.sites.value.filter((item) => item.name === name)[0];
      return String(hit?.adapterLabel || "");
    }
    const scopeText = computed$7(() => {
      if (!picked.value.length) return "全部站点";
      return picked.value.map((name) => {
        const label = labelOf(name);
        return label ? `${name}（${label}）` : name;
      }).join("、");
    });
    const cands = computed$7(() => Array.isArray(task.value?.cands) ? task.value?.cands || [] : []);
    const hasResult = computed$7(() => !!task.value && cands.value.length > 0);
    const searchLabel = computed$7(() => searching.value ? "搜索中…" : "搜索站点");
    watch$4(task, async () => {
      candTableRef.value?.clearPending();
      await nextTick$1();
      candTableRef.value?.clearPending();
    });
    function clearPending() {
      candTableRef.value?.clearPending();
      void nextTick$1(() => candTableRef.value?.clearPending());
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
      const _component_v_text_field = _resolveComponent$6("v-text-field");
      const _component_v_btn = _resolveComponent$6("v-btn");
      return _openBlock$8(), _createElementBlock$8("div", _hoisted_1$8, [
        _createElementVNode$8("div", _hoisted_2$8, [
          _createVNode$7(_component_v_text_field, {
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
          _createVNode$7(_component_v_btn, {
            color: "primary",
            variant: "flat",
            loading: searching.value,
            disabled: searching.value,
            "prepend-icon": "mdi-magnify",
            onClick: doSearch
          }, {
            default: _withCtx$6(() => [
              _createTextVNode$6(_toDisplayString$8(searchLabel.value), 1)
            ]),
            _: 1
          }, 8, ["loading", "disabled"]),
          _cache[1] || (_cache[1] = _createElementVNode$8("div", { class: "avh-sitesearch__spacer" }, null, -1)),
          _createElementVNode$8("span", _hoisted_3$8, _toDisplayString$8(searchedAt.value ? `上次搜索 ${searchedAt.value}` : "命中即停 · 站点间隔 3-8 秒"), 1)
        ]),
        _createElementVNode$8("div", _hoisted_4$8, [
          _cache[3] || (_cache[3] = _createElementVNode$8("div", { class: "avh-sitesearch__label" }, "搜索范围", -1)),
          _createElementVNode$8("div", {
            class: "avh-sitesearch__scope",
            title: scopeText.value,
            onClick: onScopeClick
          }, _toDisplayString$8(scopeText.value), 9, _hoisted_5$7),
          _createVNode$7(_component_v_btn, {
            variant: "text",
            size: "small",
            "prepend-icon": "mdi-tune",
            onClick: changeScope
          }, {
            default: _withCtx$6(() => _cache[2] || (_cache[2] = [
              _createTextVNode$6("改范围")
            ])),
            _: 1
          })
        ]),
        errorText.value ? (_openBlock$8(), _createBlock$6(ErrorState, {
          key: 0,
          message: `站点搜索失败：${errorText.value}`,
          retrying: retrying.value,
          onRetry: retry
        }, null, 8, ["message", "retrying"])) : hasResult.value && task.value ? (_openBlock$8(), _createBlock$6(CandTable, {
          key: 1,
          ref_key: "candTableRef",
          ref: candTableRef,
          task: task.value,
          "plugin-id": _ctx.pluginId,
          onDownload
        }, null, 8, ["task", "plugin-id"])) : (_openBlock$8(), _createBlock$6(EmptyState, {
          key: 2,
          text: "输入番号或关键词后点「搜索站点」"
        }))
      ]);
    };
  }
});

const SiteSearchView = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-bf4e56fe"]]);

const {defineComponent:_defineComponent$7} = await importShared('vue');

const {createElementVNode:_createElementVNode$7,createTextVNode:_createTextVNode$5,resolveComponent:_resolveComponent$5,withCtx:_withCtx$5,createVNode:_createVNode$6,renderList:_renderList$5,Fragment:_Fragment$5,openBlock:_openBlock$7,createElementBlock:_createElementBlock$7,toDisplayString:_toDisplayString$7,normalizeStyle:_normalizeStyle$1,normalizeClass:_normalizeClass$4,createBlock:_createBlock$5} = await importShared('vue');

const _hoisted_1$7 = { class: "avh-downloads" };
const _hoisted_2$7 = { class: "avh-downloads__toolbar" };
const _hoisted_3$7 = { key: 0 };
const _hoisted_4$7 = { class: "avh-q__hd" };
const _hoisted_5$6 = { class: "avh-q__main" };
const _hoisted_6$5 = { class: "avh-q__no" };
const _hoisted_7$5 = { class: "avh-q__hint avh-q__meta" };
const _hoisted_8$5 = { class: "avh-q__hint avh-q__path" };
const _hoisted_9$5 = { class: "avh-q__right" };
const _hoisted_10$5 = { class: "avh-q__no" };
const _hoisted_11$4 = { class: "avh-q__hint" };
const {computed: computed$6,onBeforeUnmount: onBeforeUnmount$2,onMounted: onMounted$2,watch: watch$3} = await importShared('vue');
const POLL_MS$1 = 5e3;
const _sfc_main$7 = /* @__PURE__ */ _defineComponent$7({
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
    const rows = computed$6(
      () => Array.isArray(props.store.queue.value) ? props.store.queue.value : []
    );
    function progressOf(item) {
      return Math.max(0, Math.min(100, Number(item.progress) || 0));
    }
    function isDone(item) {
      return item.state === "done";
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
    async function refreshQueue() {
      const inflight = props.store.refreshTasks(false);
      t.info("正在刷新进度…");
      if (!await inflight) {
        t.warning(`任务读取失败：${props.store.error.value || "请稍后重试"}`);
      }
    }
    watch$3(
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
    onMounted$2(() => {
      if (document.visibilityState === "visible") startPolling();
      document.addEventListener("visibilitychange", onVisibilityChange);
    });
    onBeforeUnmount$2(() => {
      stopPolling();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$5("v-btn");
      return _openBlock$7(), _createElementBlock$7("div", _hoisted_1$7, [
        _createElementVNode$7("div", _hoisted_2$7, [
          _cache[1] || (_cache[1] = _createElementVNode$7("span", { class: "avh-downloads__hint" }, "进度取自下载器，每 5 秒自动刷新", -1)),
          _cache[2] || (_cache[2] = _createElementVNode$7("div", { class: "avh-downloads__spacer" }, null, -1)),
          _createVNode$6(_component_v_btn, {
            variant: "outlined",
            size: "small",
            onClick: refreshQueue
          }, {
            default: _withCtx$5(() => _cache[0] || (_cache[0] = [
              _createTextVNode$5("↻ 刷新进度")
            ])),
            _: 1
          })
        ]),
        rows.value.length ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_3$7, [
          (_openBlock$7(true), _createElementBlock$7(_Fragment$5, null, _renderList$5(rows.value, (item, index) => {
            return _openBlock$7(), _createElementBlock$7("div", {
              key: rowKey(item, index),
              class: "avh-q"
            }, [
              _createElementVNode$7("div", _hoisted_4$7, [
                _createVNode$6(Thumb, {
                  class: "avh-q__poster",
                  variant: "tposter",
                  src: thumbOf(item),
                  alt: "无图",
                  "plugin-id": _ctx.pluginId
                }, null, 8, ["src", "plugin-id"]),
                _createElementVNode$7("div", _hoisted_5$6, [
                  _createElementVNode$7("div", _hoisted_6$5, _toDisplayString$7(item.number || ""), 1),
                  _createElementVNode$7("div", _hoisted_7$5, _toDisplayString$7(metaOf(item)), 1),
                  _createElementVNode$7("div", _hoisted_8$5, _toDisplayString$7(pathOf(item)), 1)
                ]),
                _createElementVNode$7("div", _hoisted_9$5, [
                  _createElementVNode$7("div", _hoisted_10$5, _toDisplayString$7(progressOf(item)) + "%", 1),
                  _createElementVNode$7("div", _hoisted_11$4, _toDisplayString$7(isDone(item) ? "已下载" : "下载中…"), 1)
                ])
              ]),
              _createElementVNode$7("div", {
                class: _normalizeClass$4(["avh-bar", { "avh-bar--done": isDone(item) }])
              }, [
                _createElementVNode$7("i", {
                  style: _normalizeStyle$1({ width: `${progressOf(item)}%` })
                }, null, 4)
              ], 2)
            ]);
          }), 128))
        ])) : (_openBlock$7(), _createBlock$5(EmptyState, {
          key: 1,
          text: "下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看"
        }))
      ]);
    };
  }
});

const DownloadsView = /* @__PURE__ */ _export_sfc(_sfc_main$7, [["__scopeId", "data-v-6fcb37c0"]]);

const {defineComponent:_defineComponent$6} = await importShared('vue');

const {toDisplayString:_toDisplayString$6,openBlock:_openBlock$6,createElementBlock:_createElementBlock$6,createCommentVNode:_createCommentVNode$5,createElementVNode:_createElementVNode$6,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$4,withCtx:_withCtx$4,createVNode:_createVNode$5,renderList:_renderList$4,Fragment:_Fragment$4,createBlock:_createBlock$4} = await importShared('vue');

const _hoisted_1$6 = { class: "avh-tasks" };
const _hoisted_2$6 = { class: "avh-tasks__toolbar" };
const _hoisted_3$6 = {
  key: 0,
  class: "avh-tasks__hint"
};
const _hoisted_4$6 = { class: "avh-tasks__secttl" };
const {computed: computed$5,onBeforeUnmount: onBeforeUnmount$1,onMounted: onMounted$1,ref: ref$5,watch: watch$2} = await importShared('vue');
const POLL_MS = 5e3;
const _sfc_main$6 = /* @__PURE__ */ _defineComponent$6({
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
    const tables = ref$5([]);
    const pending = computed$5(() => {
      const all = Array.isArray(props.store.tasks.value) ? props.store.tasks.value : [];
      return all.filter((item) => item.state === "await");
    });
    const submitted = computed$5(() => Number(props.store.downloading.value) || 0);
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
    watch$2(
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
    onMounted$1(() => {
      void props.store.refreshTasks(true);
      if (document.visibilityState === "visible") startPolling();
      document.addEventListener("visibilitychange", onVisibilityChange);
    });
    onBeforeUnmount$1(() => {
      stopPolling();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$4("v-btn");
      return _openBlock$6(), _createElementBlock$6("div", _hoisted_1$6, [
        _createElementVNode$6("div", _hoisted_2$6, [
          submitted.value ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_3$6, " ⏬ " + _toDisplayString$6(submitted.value) + " 个已提交，进度看「下载」页 ", 1)) : _createCommentVNode$5("", true),
          _cache[1] || (_cache[1] = _createElementVNode$6("div", { class: "avh-tasks__spacer" }, null, -1)),
          _createVNode$5(_component_v_btn, {
            variant: "outlined",
            size: "small",
            onClick: refreshTasks
          }, {
            default: _withCtx$4(() => _cache[0] || (_cache[0] = [
              _createTextVNode$4("↻ 刷新任务")
            ])),
            _: 1
          })
        ]),
        pending.value.length ? (_openBlock$6(), _createElementBlock$6(_Fragment$4, { key: 0 }, [
          _createElementVNode$6("div", _hoisted_4$6, "待确认（" + _toDisplayString$6(pending.value.length) + "）", 1),
          (_openBlock$6(true), _createElementBlock$6(_Fragment$4, null, _renderList$4(pending.value, (task, index) => {
            return _openBlock$6(), _createBlock$4(CandTable, {
              key: rowKey(task, index),
              ref_for: true,
              ref_key: "tables",
              ref: tables,
              task,
              "plugin-id": _ctx.pluginId,
              onDownload
            }, null, 8, ["task", "plugin-id"]);
          }), 128))
        ], 64)) : (_openBlock$6(), _createBlock$4(EmptyState, {
          key: 1,
          text: "没有待确认的任务"
        }))
      ]);
    };
  }
});

const TasksView = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-799f6d08"]]);

const {defineComponent:_defineComponent$5} = await importShared('vue');

const {toDisplayString:_toDisplayString$5,createElementVNode:_createElementVNode$5,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$3,withCtx:_withCtx$3,createVNode:_createVNode$4,renderList:_renderList$3,Fragment:_Fragment$3,openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,normalizeClass:_normalizeClass$3,createBlock:_createBlock$3} = await importShared('vue');

const _hoisted_1$5 = { class: "avh-subs" };
const _hoisted_2$5 = { class: "avh-subs__toolbar" };
const _hoisted_3$5 = { class: "avh-subs__hint" };
const _hoisted_4$5 = { class: "avh-subs__rulecard" };
const _hoisted_5$5 = { class: "avh-subs__rulehd" };
const _hoisted_6$4 = { class: "avh-subs__hint" };
const _hoisted_7$4 = { class: "avh-subs__rulegrid" };
const _hoisted_8$4 = { class: "avh-subs__rulelabel" };
const _hoisted_9$4 = { key: 0 };
const _hoisted_10$4 = { class: "avh-sub__hd" };
const _hoisted_11$3 = { class: "avh-sub__main" };
const _hoisted_12$2 = { class: "avh-sub__name" };
const _hoisted_13$2 = { class: "avh-subs__hint avh-sub__rule" };
const _hoisted_14$1 = { class: "avh-subs__hint avh-sub__stat" };
const _hoisted_15$1 = { class: "avh-sub__right" };
const {computed: computed$4,ref: ref$4} = await importShared('vue');
const ALL = "";
const _sfc_main$5 = /* @__PURE__ */ _defineComponent$5({
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
    const checking = ref$4("");
    const subs = computed$4(
      () => Array.isArray(props.store.subs.value) ? props.store.subs.value : []
    );
    const hasSubs = computed$4(() => subs.value.length > 0);
    const defaultSummary = computed$4(() => ruleSummary(props.store.rule.value));
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
    const resText = computed$4(() => {
      const value = String(props.store.rule.value.res || "1080p");
      return RES_LABELS[value] || value;
    });
    const ruleRows = computed$4(() => {
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
    const checkBusy = computed$4(() => checking.value !== "");
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
      const _component_v_btn = _resolveComponent$3("v-btn");
      const _component_v_icon = _resolveComponent$3("v-icon");
      return _openBlock$5(), _createElementBlock$5("div", _hoisted_1$5, [
        _createElementVNode$5("div", _hoisted_2$5, [
          _createElementVNode$5("span", _hoisted_3$5, "默认规则：" + _toDisplayString$5(defaultSummary.value), 1),
          _cache[3] || (_cache[3] = _createElementVNode$5("div", { class: "avh-subs__spacer" }, null, -1)),
          _createVNode$4(_component_v_btn, {
            variant: "outlined",
            size: "small",
            "prepend-icon": "mdi-cog-outline",
            onClick: goRuleSettings
          }, {
            default: _withCtx$3(() => _cache[1] || (_cache[1] = [
              _createTextVNode$3(" 去设置台改规则 ")
            ])),
            _: 1
          }),
          _createVNode$4(_component_v_btn, {
            variant: "outlined",
            size: "small",
            "prepend-icon": "mdi-lightning-bolt",
            loading: checkBusy.value,
            disabled: checkBusy.value || !hasSubs.value,
            onClick: _cache[0] || (_cache[0] = ($event) => runCheck(ALL))
          }, {
            default: _withCtx$3(() => _cache[2] || (_cache[2] = [
              _createTextVNode$3("检查一次")
            ])),
            _: 1
          }, 8, ["loading", "disabled"])
        ]),
        _createElementVNode$5("div", _hoisted_4$5, [
          _createElementVNode$5("div", _hoisted_5$5, [
            _cache[4] || (_cache[4] = _createElementVNode$5("div", { class: "avh-subs__ruletitle" }, "默认规则（手动搜索与新建订阅的基准）", -1)),
            _createElementVNode$5("div", _hoisted_6$4, "分辨率策略：" + _toDisplayString$5(resText.value), 1),
            _cache[5] || (_cache[5] = _createElementVNode$5("div", { class: "avh-subs__hint" }, "规则在「设置台 → 下载规则」里改", -1))
          ]),
          _createElementVNode$5("div", _hoisted_7$4, [
            (_openBlock$5(true), _createElementBlock$5(_Fragment$3, null, _renderList$3(ruleRows.value, (row) => {
              return _openBlock$5(), _createElementBlock$5("div", {
                key: row.label,
                class: "avh-subs__ruleitem"
              }, [
                _createElementVNode$5("span", _hoisted_8$4, _toDisplayString$5(row.label), 1),
                _createElementVNode$5("span", {
                  class: _normalizeClass$3(["avh-subs__rulevalue", { "avh-subs__rulevalue--on": row.on }])
                }, _toDisplayString$5(row.text), 3)
              ]);
            }), 128))
          ])
        ]),
        hasSubs.value ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_9$4, [
          (_openBlock$5(true), _createElementBlock$5(_Fragment$3, null, _renderList$3(subs.value, (sub, index) => {
            return _openBlock$5(), _createElementBlock$5("div", {
              key: rowKey(sub, index),
              class: "avh-sub"
            }, [
              _createElementVNode$5("div", _hoisted_10$4, [
                _createVNode$4(_component_v_icon, {
                  icon: typeIcon(sub),
                  size: "20",
                  class: "avh-sub__icon"
                }, null, 8, ["icon"]),
                _createElementVNode$5("div", _hoisted_11$3, [
                  _createElementVNode$5("div", _hoisted_12$2, _toDisplayString$5(sub.name), 1),
                  _createElementVNode$5("div", _hoisted_13$2, _toDisplayString$5(ruleSummary(subRule(sub))), 1),
                  _createElementVNode$5("div", _hoisted_14$1, " 命中 " + _toDisplayString$5(hitsText(sub)) + " 次 · 上次检查 " + _toDisplayString$5(lastText(sub)), 1)
                ]),
                _createElementVNode$5("div", _hoisted_15$1, [
                  _createVNode$4(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    loading: checking.value === String(sub.name || ""),
                    disabled: checkBusy.value,
                    onClick: ($event) => runCheck(String(sub.name || ""))
                  }, {
                    default: _withCtx$3(() => _cache[6] || (_cache[6] = [
                      _createTextVNode$3("检查")
                    ])),
                    _: 2
                  }, 1032, ["loading", "disabled", "onClick"]),
                  _createVNode$4(_component_v_btn, {
                    variant: "outlined",
                    color: "error",
                    size: "small",
                    disabled: checkBusy.value,
                    onClick: ($event) => onUnsubscribe(sub)
                  }, {
                    default: _withCtx$3(() => _cache[7] || (_cache[7] = [
                      _createTextVNode$3("取消")
                    ])),
                    _: 2
                  }, 1032, ["disabled", "onClick"])
                ])
              ])
            ]);
          }), 128))
        ])) : (_openBlock$5(), _createBlock$3(EmptyState, {
          key: 1,
          text: "还没有订阅"
        }))
      ]);
    };
  }
});

const SubsView = /* @__PURE__ */ _export_sfc(_sfc_main$5, [["__scopeId", "data-v-1e2afa2f"]]);

const {defineComponent:_defineComponent$4} = await importShared('vue');

const {openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$4,createVNode:_createVNode$3,toDisplayString:_toDisplayString$4,createElementVNode:_createElementVNode$4,normalizeClass:_normalizeClass$2} = await importShared('vue');

const _hoisted_1$4 = ["title"];
const _hoisted_2$4 = {
  key: 0,
  class: "avh-actor__star"
};
const _hoisted_3$4 = { class: "avh-actor__nm" };
const _hoisted_4$4 = { class: "avh-actor__zh" };
const _hoisted_5$4 = {
  key: 1,
  class: "avh-actor__tag"
};
const _sfc_main$4 = /* @__PURE__ */ _defineComponent$4({
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
      return _openBlock$4(), _createElementBlock$4("div", {
        class: _normalizeClass$2(["avh-actor", { "avh-actor--picker": _ctx.picker, "avh-actor--faved": _ctx.picker && _ctx.favorited }]),
        title: _ctx.name,
        onClick: onSelect
      }, [
        !_ctx.picker && _ctx.favorited ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_2$4, "⭐")) : _createCommentVNode$4("", true),
        _createVNode$3(Thumb, {
          class: "avh-actor__av",
          variant: "av",
          src: _ctx.avatar,
          alt: _ctx.name,
          "plugin-id": _ctx.pluginId
        }, null, 8, ["src", "alt", "plugin-id"]),
        _createElementVNode$4("div", _hoisted_3$4, _toDisplayString$4(_ctx.name), 1),
        _createElementVNode$4("div", _hoisted_4$4, _toDisplayString$4(_ctx.zh || ""), 1),
        _ctx.picker ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_5$4, [
          _createElementVNode$4("span", {
            class: _normalizeClass$2(["avh-tag", _ctx.favorited ? "avh-tag--on" : ""])
          }, _toDisplayString$4(_ctx.favorited ? "✓ 已收藏" : "➕ 收藏"), 3)
        ])) : _createCommentVNode$4("", true)
      ], 10, _hoisted_1$4);
    };
  }
});

const ActorRow = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-077ee37d"]]);

const {defineComponent:_defineComponent$3} = await importShared('vue');

const {createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,createElementVNode:_createElementVNode$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$3,createBlock:_createBlock$2,toDisplayString:_toDisplayString$3,normalizeClass:_normalizeClass$1,renderList:_renderList$2,Fragment:_Fragment$2,normalizeStyle:_normalizeStyle} = await importShared('vue');

const _hoisted_1$3 = { class: "avh-actors__toolbar" };
const _hoisted_2$3 = {
  key: 0,
  class: "avh-loading"
};
const _hoisted_3$3 = { class: "avh-profile" };
const _hoisted_4$3 = { class: "avh-profile__av" };
const _hoisted_5$3 = { class: "avh-profile__main" };
const _hoisted_6$3 = { class: "avh-profile__name" };
const _hoisted_7$3 = {
  key: 0,
  class: "avh-profile__zh"
};
const _hoisted_8$3 = { class: "avh-kv" };
const _hoisted_9$3 = { key: 0 };
const _hoisted_10$3 = { key: 1 };
const _hoisted_11$2 = { key: 2 };
const _hoisted_12$1 = { key: 3 };
const _hoisted_13$1 = { key: 4 };
const _hoisted_14 = { key: 5 };
const _hoisted_15 = { key: 6 };
const _hoisted_16 = { class: "avh-acts" };
const _hoisted_17 = { class: "avh-secttl" };
const _hoisted_18 = {
  key: 0,
  class: "avh-filmyears"
};
const _hoisted_19 = ["onClick"];
const _hoisted_20 = { class: "avh-filmyears__n" };
const _hoisted_21 = { class: "avh-films" };
const _hoisted_22 = ["title", "onClick"];
const _hoisted_23 = { class: "avh-film__ft" };
const _hoisted_24 = { class: "avh-film__fn" };
const _hoisted_25 = {
  key: 0,
  class: "avh-film__ftt"
};
const _hoisted_26 = { class: "avh-film__fd" };
const _hoisted_27 = {
  key: 0,
  class: "avh-tag avh-tag--lib"
};
const _hoisted_28 = {
  key: 0,
  class: "avh-morebar"
};
const _hoisted_29 = { class: "avh-actors__toolbar" };
const _hoisted_30 = { class: "avh-hint" };
const _hoisted_31 = { class: "avh-actors" };
const _hoisted_32 = {
  key: 0,
  class: "avh-loading"
};
const _hoisted_33 = {
  key: 2,
  class: "avh-hint"
};
const _hoisted_34 = { class: "avh-actors avh-actors--pick" };
const {computed: computed$3,nextTick,reactive: reactive$1,ref: ref$3} = await importShared('vue');
const FILM_FOLD = 12;
const ACTOR_LIMIT = 0;
const _sfc_main$3 = /* @__PURE__ */ _defineComponent$3({
  __name: "ActorsView",
  props: {
    store: {},
    pluginId: { default: "" },
    api: { default: null },
    toast: { default: null }
  },
  emits: ["refreshSide"],
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
    const rootEl = ref$3(null);
    const actor = ref$3("");
    const actorYear = ref$3("");
    const actorAll = ref$3(false);
    const pageRetrying = ref$3(false);
    const year = computed$3(() => actorYear.value);
    const favs = computed$3(
      () => Array.isArray(props.store.favs.value) ? props.store.favs.value : []
    );
    const hasFavs = computed$3(() => favs.value.length > 0);
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
    const pageEntry = computed$3(
      () => actor.value ? pageCache.get(`page:actor:${actor.value}`) || null : null
    );
    const pageLoading = computed$3(() => !!actor.value && !pageEntry.value);
    const pageError = computed$3(() => pageEntry.value ? pageEntry.value.error : "");
    const pageData = computed$3(() => pageEntry.value ? pageEntry.value.data : {});
    const entity = computed$3(() => pageData.value.entity || {});
    const movies = computed$3(
      () => Array.isArray(pageData.value.movies) ? pageData.value.movies : []
    );
    const faved = computed$3(() => !!findFav(actor.value));
    const sub = computed$3(
      () => (Array.isArray(props.store.subs.value) ? props.store.subs.value : []).filter(
        (item) => item.type === "actor" && item.name === actor.value
      )[0] || null
    );
    const yearInfo = computed$3(() => {
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
    const list = computed$3(
      () => year.value ? movies.value.filter((mv) => String(mv.date || "").slice(0, 4) === year.value) : movies.value
    );
    const fold = computed$3(() => !actorAll.value && list.value.length > FILM_FOLD);
    const shown = computed$3(
      () => fold.value ? list.value.slice(0, FILM_FOLD) : list.value
    );
    const moreLabel = computed$3(
      () => fold.value ? `展开其余 ${list.value.length - FILM_FOLD} 部` : "收起"
    );
    const filmsTitle = computed$3(() => {
      const total = `作品史（按发行时间倒序，共 ${movies.value.length} 部`;
      const scope = year.value ? `，${year.value} 年 ${list.value.length} 部` : "";
      return `${total}${scope}）`;
    });
    const filmsEmptyText = computed$3(
      () => year.value ? "该年份没有作品记录。" : "这位演员暂无作品数据。"
    );
    async function loadPage(name, force = false) {
      const key = `page:actor:${name}`;
      if (!force && pageCache.has(key)) return;
      const res = await apiGet("actor", { name, limit: ACTOR_LIMIT });
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
      actorAll.value = false;
      void loadPage(target);
      void nextTick(() => rootEl.value?.scrollIntoView({ block: "start" }));
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
      actorAll.value = false;
    }
    async function toggleAll() {
      const expanding = !actorAll.value;
      actorAll.value = expanding;
      if (expanding) return;
      await nextTick();
      const title = rootEl.value?.querySelector(".avh-secttl");
      if (title instanceof HTMLElement) title.scrollIntoView({ block: "start" });
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
    const subscribing = ref$3(false);
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
    const checking = ref$3(false);
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
    function cssUrl(value) {
      return String(value || "").replace(/["'()\\\s]/g, (char) => encodeURIComponent(char));
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
      t.info("影片详情抽屉还没搬进原生视图");
      t.info(num ? `先记下番号：${num}` : "这条记录没有番号");
    }
    const pickerOpen = ref$3(false);
    const pickerLoading = ref$3(false);
    const pickerError = ref$3("");
    const pickerRows = ref$3([]);
    const pickerAdded = ref$3([]);
    const addingName = ref$3("");
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
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$2("v-btn");
      const _component_v_card_title = _resolveComponent$2("v-card-title");
      const _component_v_card_text = _resolveComponent$2("v-card-text");
      const _component_v_spacer = _resolveComponent$2("v-spacer");
      const _component_v_card_actions = _resolveComponent$2("v-card-actions");
      const _component_v_card = _resolveComponent$2("v-card");
      const _component_v_dialog = _resolveComponent$2("v-dialog");
      return _openBlock$3(), _createElementBlock$3("div", {
        ref_key: "rootEl",
        ref: rootEl,
        class: "avh-actors-view"
      }, [
        actor.value ? (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 0 }, [
          _createElementVNode$3("div", _hoisted_1$3, [
            _createVNode$2(_component_v_btn, {
              variant: "outlined",
              size: "small",
              onClick: backToList
            }, {
              default: _withCtx$2(() => _cache[3] || (_cache[3] = [
                _createTextVNode$2("← 返回")
              ])),
              _: 1
            })
          ]),
          pageLoading.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_2$3, "正在抓取演员档案与作品史…")) : pageError.value ? (_openBlock$3(), _createBlock$2(ErrorState, {
            key: 1,
            message: pageError.value,
            retrying: pageRetrying.value,
            onRetry: retryPage
          }, null, 8, ["message", "retrying"])) : (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 2 }, [
            _createElementVNode$3("div", _hoisted_3$3, [
              _createElementVNode$3("div", _hoisted_4$3, [
                _createVNode$2(Thumb, {
                  src: entity.value.avatar,
                  alt: actor.value,
                  "plugin-id": _ctx.pluginId
                }, null, 8, ["src", "alt", "plugin-id"])
              ]),
              _createElementVNode$3("div", _hoisted_5$3, [
                _createElementVNode$3("h2", _hoisted_6$3, [
                  _createTextVNode$2(_toDisplayString$3(entity.value.name || actor.value) + " ", 1),
                  entity.value.zh ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_7$3, "/ " + _toDisplayString$3(entity.value.zh), 1)) : _createCommentVNode$3("", true)
                ]),
                _createElementVNode$3("div", _hoisted_8$3, [
                  entity.value.videos_count ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_9$3, [
                    _cache[4] || (_cache[4] = _createElementVNode$3("b", null, "作品", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.videos_count), 1)
                  ])) : _createCommentVNode$3("", true),
                  entity.value.age ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_10$3, [
                    _cache[5] || (_cache[5] = _createElementVNode$3("b", null, "年龄", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.age), 1)
                  ])) : _createCommentVNode$3("", true),
                  entity.value.birthday ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_11$2, [
                    _cache[6] || (_cache[6] = _createElementVNode$3("b", null, "生日", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.birthday), 1)
                  ])) : _createCommentVNode$3("", true),
                  entity.value.height ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_12$1, [
                    _cache[7] || (_cache[7] = _createElementVNode$3("b", null, "身高", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.height) + "cm", 1)
                  ])) : _createCommentVNode$3("", true),
                  entity.value.cup ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_13$1, [
                    _cache[8] || (_cache[8] = _createElementVNode$3("b", null, "罩杯", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.cup), 1)
                  ])) : _createCommentVNode$3("", true),
                  entity.value.birthplace ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_14, [
                    _cache[9] || (_cache[9] = _createElementVNode$3("b", null, "出身", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.birthplace), 1)
                  ])) : _createCommentVNode$3("", true),
                  entity.value.instagram ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_15, [
                    _cache[10] || (_cache[10] = _createElementVNode$3("b", null, "IG", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(entity.value.instagram), 1)
                  ])) : _createCommentVNode$3("", true),
                  _createElementVNode$3("span", null, [
                    _cache[11] || (_cache[11] = _createElementVNode$3("b", null, "本次返回作品", -1)),
                    _createTextVNode$2(" " + _toDisplayString$3(movies.value.length) + " 部", 1)
                  ])
                ]),
                _createElementVNode$3("div", _hoisted_16, [
                  _createVNode$2(_component_v_btn, {
                    color: faved.value ? void 0 : "primary",
                    variant: faved.value ? "outlined" : "flat",
                    size: "small",
                    onClick: toggleFav
                  }, {
                    default: _withCtx$2(() => [
                      _createTextVNode$2(_toDisplayString$3(faved.value ? "★ 已收藏" : "☆ 收藏该演员"), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "variant"]),
                  _createVNode$2(_component_v_btn, {
                    color: sub.value ? void 0 : "primary",
                    variant: sub.value ? "outlined" : "flat",
                    size: "small",
                    loading: subscribing.value,
                    disabled: !!sub.value || subscribing.value,
                    onClick: subscribeActor
                  }, {
                    default: _withCtx$2(() => [
                      _createTextVNode$2(_toDisplayString$3(sub.value ? "✓ 已订阅新片" : "📌 订阅该演员的新片"), 1)
                    ]),
                    _: 1
                  }, 8, ["color", "variant", "loading", "disabled"]),
                  _createVNode$2(_component_v_btn, {
                    variant: "outlined",
                    size: "small",
                    loading: checking.value,
                    onClick: checkActor
                  }, {
                    default: _withCtx$2(() => _cache[12] || (_cache[12] = [
                      _createTextVNode$2(" ⚡ 检查她的新片 ")
                    ])),
                    _: 1
                  }, 8, ["loading"])
                ])
              ])
            ]),
            _createElementVNode$3("div", _hoisted_17, _toDisplayString$3(filmsTitle.value), 1),
            yearInfo.value.years.length > 1 ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_18, [
              _createElementVNode$3("button", {
                type: "button",
                class: _normalizeClass$1({ "avh-filmyears__on": !year.value }),
                onClick: _cache[0] || (_cache[0] = ($event) => pickYear(""))
              }, "全部 " + _toDisplayString$3(movies.value.length), 3),
              (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2(yearInfo.value.years, (y) => {
                return _openBlock$3(), _createElementBlock$3("button", {
                  key: y,
                  type: "button",
                  class: _normalizeClass$1({ "avh-filmyears__on": year.value === y }),
                  onClick: ($event) => pickYear(y)
                }, [
                  _createTextVNode$2(_toDisplayString$3(y), 1),
                  _createElementVNode$3("span", _hoisted_20, _toDisplayString$3(" " + yearInfo.value.yearCount[y]), 1)
                ], 10, _hoisted_19);
              }), 128))
            ])) : _createCommentVNode$3("", true),
            list.value.length ? (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 1 }, [
              _createElementVNode$3("div", _hoisted_21, [
                (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2(shown.value, (mv, index) => {
                  return _openBlock$3(), _createElementBlock$3("div", {
                    key: filmKey(mv, index),
                    class: "avh-film",
                    title: mv.title || mv.number || "",
                    onClick: ($event) => openFilm(mv)
                  }, [
                    _createElementVNode$3("div", {
                      class: "avh-film__pic",
                      style: _normalizeStyle(picStyle(mv))
                    }, [
                      _createVNode$2(Thumb, {
                        variant: "film",
                        src: mv.thumb,
                        alt: mv.number || "",
                        "plugin-id": _ctx.pluginId
                      }, null, 8, ["src", "alt", "plugin-id"])
                    ], 4),
                    _createElementVNode$3("div", _hoisted_23, [
                      _createElementVNode$3("div", _hoisted_24, _toDisplayString$3(mv.number || ""), 1),
                      mv.title ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_25, _toDisplayString$3(mv.title), 1)) : _createCommentVNode$3("", true),
                      _createElementVNode$3("div", _hoisted_26, [
                        _createElementVNode$3("span", null, _toDisplayString$3(mv.date || ""), 1),
                        _createElementVNode$3("span", {
                          class: _normalizeClass$1(["avh-tag", { "avh-tag--on": !!mv.cnsub }])
                        }, _toDisplayString$3(mv.cnsub ? "中字" : "无中字"), 3),
                        _createElementVNode$3("span", null, "🧲 " + _toDisplayString$3(mv.magnets || 0), 1),
                        mv.lib ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_27, "已入库")) : _createCommentVNode$3("", true)
                      ])
                    ])
                  ], 8, _hoisted_22);
                }), 128))
              ]),
              list.value.length > FILM_FOLD ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_28, [
                _createVNode$2(_component_v_btn, {
                  variant: "outlined",
                  size: "small",
                  onClick: toggleAll
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$3(moreLabel.value), 1)
                  ]),
                  _: 1
                })
              ])) : _createCommentVNode$3("", true)
            ], 64)) : (_openBlock$3(), _createBlock$2(EmptyState, {
              key: 2,
              text: filmsEmptyText.value
            }, null, 8, ["text"]))
          ], 64))
        ], 64)) : (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 1 }, [
          hasFavs.value ? (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 0 }, [
            _createElementVNode$3("div", _hoisted_29, [
              _createElementVNode$3("span", _hoisted_30, "共 " + _toDisplayString$3(favs.value.length) + " 位", 1),
              _cache[14] || (_cache[14] = _createElementVNode$3("div", { class: "avh-actors__spacer" }, null, -1)),
              _createVNode$2(_component_v_btn, {
                variant: "outlined",
                size: "small",
                onClick: openPicker
              }, {
                default: _withCtx$2(() => _cache[13] || (_cache[13] = [
                  _createTextVNode$2("➕ 添加演员")
                ])),
                _: 1
              })
            ]),
            _createElementVNode$3("div", _hoisted_31, [
              (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2(favs.value, (item) => {
                return _openBlock$3(), _createBlock$2(ActorRow, {
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
          ], 64)) : (_openBlock$3(), _createBlock$2(EmptyState, {
            key: 1,
            text: "还没有收藏演员"
          }, {
            default: _withCtx$2(() => [
              _createVNode$2(_component_v_btn, {
                color: "primary",
                variant: "flat",
                onClick: openPicker
              }, {
                default: _withCtx$2(() => _cache[15] || (_cache[15] = [
                  _createTextVNode$2("➕ 从演员榜挑选")
                ])),
                _: 1
              })
            ]),
            _: 1
          }))
        ], 64)),
        _createVNode$2(_component_v_dialog, {
          modelValue: pickerOpen.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => pickerOpen.value = $event),
          "max-width": "880",
          scrollable: "",
          attach: "body"
        }, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_v_card, null, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$2(() => _cache[16] || (_cache[16] = [
                    _createTextVNode$2("从演员榜挑选")
                  ])),
                  _: 1
                }),
                _createVNode$2(_component_v_card_text, null, {
                  default: _withCtx$2(() => [
                    pickerLoading.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_32, "正在抓取演员榜…")) : pickerError.value ? (_openBlock$3(), _createBlock$2(ErrorState, {
                      key: 1,
                      message: pickerError.value,
                      retrying: pickerLoading.value,
                      onRetry: retryRank
                    }, null, 8, ["message", "retrying"])) : !pickerRows.value.length ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_33, "演员榜里的人都已收藏。")) : (_openBlock$3(), _createElementBlock$3(_Fragment$2, { key: 3 }, [
                      _cache[17] || (_cache[17] = _createElementVNode$3("div", { class: "avh-actorpick__tip avh-hint" }, "点 ➕ 加入收藏", -1)),
                      _createElementVNode$3("div", _hoisted_34, [
                        (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2(pickerRows.value, (row) => {
                          return _openBlock$3(), _createBlock$2(ActorRow, {
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
                _createVNode$2(_component_v_card_actions, null, {
                  default: _withCtx$2(() => [
                    _createVNode$2(_component_v_spacer),
                    _createVNode$2(_component_v_btn, {
                      color: "error",
                      variant: "outlined",
                      onClick: _cache[1] || (_cache[1] = ($event) => pickerOpen.value = false)
                    }, {
                      default: _withCtx$2(() => _cache[18] || (_cache[18] = [
                        _createTextVNode$2("关闭")
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

const ActorsView = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-0574d14c"]]);

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {createVNode:_createVNode$1,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$2,createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$2} = await importShared('vue');

const _hoisted_1$2 = ["title"];
const _hoisted_2$2 = { class: "avh-card__thumb" };
const _hoisted_3$2 = { class: "avh-card__badges" };
const _hoisted_4$2 = {
  key: 0,
  class: "avh-badge avh-badge--cn"
};
const _hoisted_5$2 = {
  key: 1,
  class: "avh-badge avh-badge--uc"
};
const _hoisted_6$2 = {
  key: 2,
  class: "avh-badge avh-badge--new"
};
const _hoisted_7$2 = {
  key: 3,
  class: "avh-badge avh-badge--lib"
};
const _hoisted_8$2 = { class: "avh-card__meta" };
const _hoisted_9$2 = { class: "avh-card__num" };
const _hoisted_10$2 = { class: "avh-card__sub" };
const _hoisted_11$1 = { class: "avh-card__sub" };
const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
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
      return _openBlock$2(), _createElementBlock$2("div", {
        class: "avh-card",
        title: _ctx.movie.title || number(),
        onClick: _cache[0] || (_cache[0] = ($event) => emit("select", { number: number(), id: id() })),
        onMouseenter: _cache[1] || (_cache[1] = ($event) => emit("hover", { number: number(), id: id() }))
      }, [
        _createElementVNode$2("div", _hoisted_2$2, [
          _createVNode$1(Thumb, {
            variant: "thumb",
            src: _ctx.movie.thumb,
            alt: number(),
            "plugin-id": _ctx.pluginId
          }, null, 8, ["src", "alt", "plugin-id"]),
          _createElementVNode$2("div", _hoisted_3$2, [
            _ctx.movie.cnsub ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_4$2, "中字")) : _createCommentVNode$2("", true),
            _ctx.movie.uncensored ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_5$2, "破解")) : _createCommentVNode$2("", true),
            _ctx.actorFavorited ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_6$2, "⭐已收藏演员")) : _createCommentVNode$2("", true),
            _ctx.movie.lib ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_7$2, "✔已入库")) : _createCommentVNode$2("", true)
          ])
        ]),
        _createElementVNode$2("div", _hoisted_8$2, [
          _createElementVNode$2("div", _hoisted_9$2, _toDisplayString$2(number()), 1),
          _createElementVNode$2("div", _hoisted_10$2, [
            _createElementVNode$2("span", null, _toDisplayString$2(_ctx.movie.actor || "—"), 1),
            _createElementVNode$2("span", null, "🧲 " + _toDisplayString$2(_ctx.movie.magnets || 0), 1)
          ]),
          _createElementVNode$2("div", _hoisted_11$1, [
            _createElementVNode$2("span", null, _toDisplayString$2(_ctx.movie.date || ""), 1),
            _createElementVNode$2("span", null, _toDisplayString$2(durationText()), 1)
          ])
        ])
      ], 40, _hoisted_1$2);
    };
  }
});

const NumCard = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-c5f8fb27"]]);

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,renderList:_renderList$1,Fragment:_Fragment$1,toDisplayString:_toDisplayString$1,normalizeClass:_normalizeClass,createElementVNode:_createElementVNode$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createBlock:_createBlock$1} = await importShared('vue');

const _hoisted_1$1 = { class: "avh-discover" };
const _hoisted_2$1 = {
  key: 0,
  class: "avh-discover__loading"
};
const _hoisted_3$1 = { class: "avh-discover__toolbar" };
const _hoisted_4$1 = { class: "avh-tabs" };
const _hoisted_5$1 = ["onClick"];
const _hoisted_6$1 = { class: "avh-tabs" };
const _hoisted_7$1 = ["onClick"];
const _hoisted_8$1 = {
  key: 0,
  class: "avh-discover__hint"
};
const _hoisted_9$1 = {
  key: 1,
  class: "avh-discover__loading"
};
const _hoisted_10$1 = {
  key: 3,
  class: "avh-discover__grid"
};
const {computed: computed$2,watch: watch$1} = await importShared('vue');
const {reactive,ref: ref$2} = await importShared('vue');
const PREFETCH_N = 6;
const rankCache = reactive(/* @__PURE__ */ new Map());
const detailCache = reactive(/* @__PURE__ */ new Map());
const periodState = ref$2("week");
const kindState = ref$2("censored");
const PRE = { queue: [], busy: false };
function prefetchDetail(api, number, id) {
  const num = String(number ?? "");
  if (!api || typeof api.get !== "function" || !num) return;
  if (detailCache.has(num)) return;
  if (PRE.queue.some((item) => item.number === num)) return;
  PRE.queue.push({ number: num, id: String(id ?? "") });
  void pumpPrefetch(api);
}
async function pumpPrefetch(api) {
  if (PRE.busy) return;
  const job = PRE.queue.shift();
  if (!job) return;
  if (detailCache.has(job.number)) {
    void pumpPrefetch(api);
    return;
  }
  PRE.busy = true;
  try {
    const params = { number: job.number };
    if (job.id) params.id = job.id;
    const payload = unwrap(await api.get("plugin/detail", { params }));
    if (payload && typeof payload === "object" && payload.success === false) return;
    detailCache.set(job.number, { data: payload || {}, t: Date.now() });
  } catch {
  } finally {
    PRE.busy = false;
    void pumpPrefetch(api);
  }
}
function prefetchCards(api, movies, n = PREFETCH_N) {
  (movies || []).slice(0, n).forEach((movie) => prefetchDetail(api, movie?.number, movie?.id));
}
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
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
    const period = computed$2(() => periodState.value);
    const kind = computed$2(() => kindState.value);
    function pickPeriod(key) {
      periodState.value = key;
    }
    function pickKind(key) {
      kindState.value = key;
    }
    const booted = computed$2(() => props.store.booted.value === true);
    const bootError = computed$2(() => String(props.store.error.value || ""));
    const rankKey = computed$2(() => `rank:${period.value}:${kind.value}`);
    const entry = computed$2(() => rankCache.get(rankKey.value) || null);
    const movies = computed$2(() => entry.value && entry.value.data || []);
    const rankError = computed$2(() => String(entry.value && entry.value.error || ""));
    const inflight = /* @__PURE__ */ new Set();
    const retrying = ref$2(false);
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
    watch$1([booted, bootError, rankKey], () => void ensureRank(), { immediate: true });
    watch$1(movies, (list) => prefetchCards(props.api, list), { immediate: true });
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$1("v-btn");
      return _openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
        !booted.value && !bootError.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, "正在读取插件状态…")) : (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 1 }, [
          _createElementVNode$1("div", _hoisted_3$1, [
            _createElementVNode$1("div", _hoisted_4$1, [
              (_openBlock$1(), _createElementBlock$1(_Fragment$1, null, _renderList$1(PERIOD_TABS, (item) => {
                return _createElementVNode$1("button", {
                  key: item.key,
                  class: _normalizeClass({ "avh-tabs__on": item.key === period.value }),
                  onClick: ($event) => pickPeriod(item.key)
                }, _toDisplayString$1(item.name), 11, _hoisted_5$1);
              }), 64))
            ]),
            _createElementVNode$1("div", _hoisted_6$1, [
              (_openBlock$1(), _createElementBlock$1(_Fragment$1, null, _renderList$1(ZONE_TABS, (item) => {
                return _createElementVNode$1("button", {
                  key: item.key,
                  class: _normalizeClass({ "avh-tabs__on": item.key === kind.value }),
                  onClick: ($event) => pickKind(item.key)
                }, _toDisplayString$1(item.name), 11, _hoisted_7$1);
              }), 64))
            ]),
            !bootError.value && entry.value && entry.value.data ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_8$1, _toDisplayString$1(entry.value.data.length) + " 部 ", 1)) : _createCommentVNode$1("", true),
            _cache[1] || (_cache[1] = _createElementVNode$1("div", { class: "avh-discover__spacer" }, null, -1)),
            !bootError.value ? (_openBlock$1(), _createBlock$1(_component_v_btn, {
              key: 1,
              variant: "outlined",
              size: "small",
              onClick: reloadRank
            }, {
              default: _withCtx$1(() => _cache[0] || (_cache[0] = [
                _createTextVNode$1(" ↻ 重新抓取 ")
              ])),
              _: 1
            })) : _createCommentVNode$1("", true)
          ]),
          bootError.value ? (_openBlock$1(), _createBlock$1(ErrorState, {
            key: 0,
            message: `插件状态读取失败：${bootError.value}（仍可尝试直接抓取榜单）`,
            retrying: retrying.value,
            onRetry: retryRank
          }, null, 8, ["message", "retrying"])) : (_openBlock$1(), _createElementBlock$1(_Fragment$1, { key: 1 }, [
            rankError.value ? (_openBlock$1(), _createBlock$1(ErrorState, {
              key: 0,
              message: rankError.value,
              retrying: retrying.value,
              onRetry: retryRank
            }, null, 8, ["message", "retrying"])) : !entry.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_9$1, "正在抓取榜单…")) : !movies.value.length ? (_openBlock$1(), _createBlock$1(EmptyState, {
              key: 2,
              text: "该榜单暂无数据，换个周期 / 分类试试"
            })) : (_openBlock$1(), _createElementBlock$1("div", _hoisted_10$1, [
              (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(movies.value, (movie, index) => {
                return _openBlock$1(), _createBlock$1(NumCard, {
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

const DiscoverView = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-b5be6a8f"]]);

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
    downloadMagnet,
    clearNotices,
    saveRule
  };
}

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,unref:_unref,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock,renderList:_renderList,Fragment:_Fragment,resolveDynamicComponent:_resolveDynamicComponent} = await importShared('vue');

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
    const NATIVE_VIEWS = {
      discover: DiscoverView,
      sitesearch: SiteSearchView,
      downloads: DownloadsView,
      tasks: TasksView,
      subs: SubsView,
      actors: ActorsView
    };
    const framePluginId = computed(() => props.pluginId || props.sourcePluginId || "");
    const section = ref(props.mode === "settings" ? SETTINGS_SECTIONS[0].key : DATA_SECTIONS[0].key);
    const running = ref(false);
    const version = ref("");
    const noticeClearing = ref(false);
    const isSettings = computed(() => props.mode === "settings");
    const activeSection = computed(
      () => SETTINGS_SECTIONS.find((item) => item.key === section.value) || SETTINGS_SECTIONS[0]
    );
    const nativeView = computed(() => NATIVE_VIEWS[section.value] || null);
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
    function onOpenMovie(payload) {
      const number = String(payload?.number || "");
      toast.info("详情抽屉将在下一步迁移");
      toast.info(number ? `先记下番号：${number}` : "这条记录没有番号");
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
    function applyPendingSection() {
      if (props.mode !== "settings") return;
      const pending = takePendingSettingsSection();
      if (pending && SETTINGS_SECTIONS.some((item) => item.key === pending)) section.value = pending;
    }
    applyPendingSection();
    onMounted(() => {
      emit("layout", { maxWidth: DEFAULT_MAX_WIDTH });
      runtime.start();
      void loadVersion();
      if (props.mode === "settings") {
        applyPendingSection();
        void loadDraft();
      }
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
              nativeView.value && framePluginId.value ? (_openBlock(), _createBlock(_resolveDynamicComponent(nativeView.value), {
                key: 0,
                store: _unref(store),
                "plugin-id": framePluginId.value,
                api: currentApi(),
                toast: _unref(injectedToast),
                onSwitch: _cache[1] || (_cache[1] = ($event) => emit("switch")),
                onRefreshSide: _cache[2] || (_cache[2] = ($event) => _unref(refreshRuntime)()),
                onOpenMovie
              }, null, 40, ["store", "plugin-id", "api", "toast"])) : framePluginId.value ? (_openBlock(), _createBlock(AppFrame, {
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

const Console = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-0f646e8d"]]);

export { Console as C, consoleEmits as c };
