import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {openBlock:_openBlock$1,createElementBlock:_createElementBlock$1} = await importShared('vue');

const _hoisted_1$1 = ["src"];
const {computed: computed$2} = await importShared('vue');

const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "AppFrame",
  props: {
    pluginId: {},
    version: { default: "" },
    sectionKey: { default: "discover" }
  },
  setup(__props) {
    const props = __props;
    const src = computed$2(() => {
      const base = `/api/v1/plugin/${props.pluginId}/ui/`;
      const query = props.version ? `?v=${encodeURIComponent(props.version)}` : "";
      return `${base}${query}`;
    });
    return (_ctx, _cache) => {
      return _openBlock$1(), _createElementBlock$1("iframe", {
        key: `${_ctx.pluginId}:${_ctx.sectionKey}`,
        src: src.value,
        class: "avh-app-frame",
        title: "AV 资源助手 · 内嵌应用",
        referrerpolicy: "no-referrer",
        allow: "clipboard-write"
      }, null, 8, _hoisted_1$1);
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

const AppFrame = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-38d61c16"]]);

const DEFAULT_MAX_WIDTH = "90rem";

function consoleEmits() {
  return () => {
  };
}

function noop() {
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

const {computed: computed$1,ref: ref$1} = await importShared('vue');
const POLL_INTERVAL_MS = 15e3;
function len(value) {
  return Array.isArray(value) ? value.length : null;
}
function useRuntimeInfo(api) {
  const data = ref$1(null);
  const error = ref$1("");
  const loading = ref$1(false);
  const updatedAt = ref$1("");
  let timer = null;
  const overview = computed$1(() => {
    const d = data.value;
    const queue = Array.isArray(d?.queue) ? d?.queue : null;
    const tasks = Array.isArray(d?.tasks) ? d?.tasks : null;
    return {
      enabled: typeof d?.enabled === "boolean" ? d.enabled : null,
      subs: len(d?.subs),
      awaitTasks: tasks ? tasks.filter((item) => item?.state === "await").length : null,
      downloading: queue ? queue.filter((item) => item?.state !== "done").length : null,
      favorites: len(d?.favs),
      notices: len(d?.notices),
      cacheSize: "—",
      nextCheck: "—"
    };
  });
  const recovery = computed$1(() => ({
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
const _hoisted_6 = { class: "mb-3" };
const _hoisted_7 = { class: "avh-side" };
const _hoisted_8 = { class: "text-body-2 font-weight-medium" };
const _hoisted_9 = { class: "text-body-2 font-weight-medium" };
const _hoisted_10 = { class: "text-body-2 font-weight-medium" };
const _hoisted_11 = { class: "text-body-2 font-weight-medium" };
const _hoisted_12 = { class: "text-body-2 font-weight-medium" };
const _hoisted_13 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_14 = { class: "text-body-2 text-medium-emphasis" };
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
    const SETTINGS_SECTIONS = [
      {
        key: "sites",
        title: "搜索站点",
        icon: "mdi-web",
        hint: "搜索范围站点与优先站点（优先站点命中即停）。按用户要求按钮化：主界面只显示已选站点 chips ＋「选择站点」「优先站点」两个按钮，勾选与排序都在弹窗里做，不再把十几个站点平铺在界面上。数据走 POST /rule 的 sites / prefSites。"
      },
      {
        key: "rule",
        title: "下载规则",
        icon: "mdi-filter-cog",
        hint: "分辨率策略、必须中文字幕、破解优先、允许 4K 择优、做种下限、BT 兜底、命中后自动下载还是仅通知、每日检查上限。数据走 POST /rule。"
      },
      {
        key: "notify",
        title: "通知",
        icon: "mdi-bell",
        hint: "通知渠道沿用 MoviePilot 原生通知（本插件不另建渠道）；本栏管已读位点与清空，数据走 GET / DELETE /notices。"
      },
      {
        key: "library",
        title: "媒体库",
        icon: "mdi-server",
        hint: "Emby 地址与 API 密钥；两栏都留空 = 自动复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby。本栏的改动属于宿主配置，走 emit(save) 交给宿主 PUT。"
      },
      {
        key: "runtime",
        title: "运行与缓存",
        icon: "mdi-database-cog",
        hint: "缓存占用与清理、javdb 二进制状态，以及限流参数只读展示（订阅检查每天 ≤6 次、间隔 ≥240 分钟，参数不放宽）。"
      },
      {
        key: "about",
        title: "关于",
        icon: "mdi-information-outline",
        hint: "版本号、仓库地址、文档链接。"
      }
    ];
    computed(() => props.pluginId || props.sourcePluginId || "");
    const framePluginId = computed(() => props.pluginId || props.sourcePluginId || "");
    const section = ref(props.mode === "settings" ? SETTINGS_SECTIONS[0].key : DATA_SECTIONS[0].key);
    const running = ref(false);
    const version = ref("");
    const activeSection = computed(
      () => SETTINGS_SECTIONS.find((item) => item.key === section.value) || SETTINGS_SECTIONS[0]
    );
    const injectedToast = inject("moviepilot:toast", null);
    const toast = hostToast(injectedToast);
    const FALLBACK_API = {
      get: () => Promise.reject(new Error("宿主 api 不可用")),
      post: () => Promise.reject(new Error("宿主 api 不可用"))
    };
    function currentApi() {
      return props.api && typeof props.api.get === "function" ? props.api : FALLBACK_API;
    }
    const runtime = useRuntimeInfo(currentApi());
    const { overview, updatedAt, error: runtimeError, loading: runtimeLoading, refresh: refreshRuntime } = runtime;
    const activeNavKey = computed(
      () => props.mode === "settings" ? section.value : `data:${section.value}`
    );
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
    function saveConfig() {
      if (props.mode !== "settings") return;
      emit("save", { ...props.initialConfig || {} });
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
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_subtitle = _resolveComponent("v-card-subtitle");
      const _component_v_card_item = _resolveComponent("v-card-item");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_list_item_title = _resolveComponent("v-list-item-title");
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
                _cache[3] || (_cache[3] = _createElementVNode("span", { class: "text-h6" }, "AV 资源助手", -1)),
                version.value ? (_openBlock(), _createElementBlock("span", _hoisted_2, "v" + _toDisplayString(version.value), 1)) : _createCommentVNode("", true),
                _unref(overview).enabled === false ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 1,
                  size: "x-small",
                  color: "warning",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => _cache[2] || (_cache[2] = [
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
              default: _withCtx(() => _cache[4] || (_cache[4] = [
                _createTextVNode("运行一次")
              ])),
              _: 1
            }, 8, ["loading"]),
            props.mode === "settings" ? (_openBlock(), _createBlock(_component_v_btn, {
              key: 0,
              color: "primary",
              variant: "tonal",
              "prepend-icon": "mdi-content-save",
              class: "me-2",
              onClick: saveConfig
            }, {
              default: _withCtx(() => _cache[5] || (_cache[5] = [
                _createTextVNode("保存修改")
              ])),
              _: 1
            })) : _createCommentVNode("", true),
            _createVNode(_component_v_btn, {
              variant: "text",
              "prepend-icon": "mdi-close",
              class: "me-2",
              onClick: closePanel
            }, {
              default: _withCtx(() => _cache[6] || (_cache[6] = [
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
                props.mode === "data" ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                  _createVNode(_component_v_list_subheader, null, {
                    default: _withCtx(() => _cache[7] || (_cache[7] = [
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
                    default: _withCtx(() => _cache[8] || (_cache[8] = [
                      _createTextVNode("设置台")
                    ])),
                    _: 1
                  }),
                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(SETTINGS_SECTIONS, (item) => {
                    return _createVNode(_component_v_list_item, {
                      key: item.key,
                      value: item.key,
                      "prepend-icon": item.icon,
                      title: item.title,
                      onClick: ($event) => pick(item)
                    }, null, 8, ["value", "prepend-icon", "title", "onClick"]);
                  }), 64))
                ], 64))
              ]),
              _: 1
            }, 8, ["selected"]),
            _createVNode(_component_v_btn, {
              block: "",
              size: "small",
              variant: "text",
              "prepend-icon": props.mode === "settings" ? "mdi-view-dashboard-outline" : "mdi-cog-outline",
              class: "mt-2",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("switch"))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(props.mode === "settings" ? "打开数据台" : "打开设置台"), 1)
              ]),
              _: 1
            }, 8, ["prepend-icon"])
          ]),
          _createVNode(_component_v_divider, { vertical: "" }),
          _createElementVNode("section", _hoisted_5, [
            props.mode === "data" ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
              framePluginId.value ? (_openBlock(), _createBlock(AppFrame, {
                key: 0,
                "plugin-id": framePluginId.value,
                "section-key": section.value,
                version: version.value
              }, null, 8, ["plugin-id", "section-key", "version"])) : (_openBlock(), _createBlock(_component_v_alert, {
                key: 1,
                type: "warning",
                variant: "tonal"
              }, {
                default: _withCtx(() => _cache[9] || (_cache[9] = [
                  _createTextVNode(" 宿主没有传入 pluginId，无法定位内嵌应用。 ")
                ])),
                _: 1
              }))
            ], 64)) : (_openBlock(), _createBlock(_component_v_card, {
              key: 1,
              variant: "tonal",
              class: "avh-placeholder"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_item, null, {
                  prepend: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: activeSection.value.icon,
                      color: "primary"
                    }, null, 8, ["icon"])
                  ]),
                  default: _withCtx(() => [
                    _createVNode(_component_v_card_title, null, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(activeSection.value.title), 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card_subtitle, null, {
                      default: _withCtx(() => _cache[10] || (_cache[10] = [
                        _createTextVNode("设置台骨架 · S5 阶段做实")
                      ])),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _createElementVNode("p", _hoisted_6, _toDisplayString(activeSection.value.hint), 1),
                    _createVNode(_component_v_divider, { class: "my-4" }),
                    _cache[11] || (_cache[11] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mb-2" }, [
                      _createTextVNode(" 保存语义（设计文档 §5）：先提交插件自管数据（"),
                      _createElementVNode("code", null, "POST /rule"),
                      _createTextVNode("），再 "),
                      _createElementVNode("code", null, "emit('save', config)"),
                      _createTextVNode(" 交给宿主保存插件配置；第一步失败就不提交第二步，弹窗不关。 ")
                    ], -1)),
                    _cache[12] || (_cache[12] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mb-0" }, " 未保存标记：任一字段变脏就在顶条显示「● 未保存」。 ", -1))
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }))
          ]),
          _createVNode(_component_v_divider, { vertical: "" }),
          _createElementVNode("aside", _hoisted_7, [
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
                      default: _withCtx(() => _cache[13] || (_cache[13] = [
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
                            _createElementVNode("span", _hoisted_8, _toDisplayString(_unref(overview).subs === null ? "—" : _unref(overview).subs), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[14] || (_cache[14] = [
                                _createTextVNode("订阅")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_9, _toDisplayString(_unref(overview).awaitTasks === null ? "—" : _unref(overview).awaitTasks), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[15] || (_cache[15] = [
                                _createTextVNode("待确认任务")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_10, _toDisplayString(_unref(overview).downloading === null ? "—" : _unref(overview).downloading), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[16] || (_cache[16] = [
                                _createTextVNode("下载中")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_11, _toDisplayString(_unref(overview).favorites === null ? "—" : _unref(overview).favorites), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[17] || (_cache[17] = [
                                _createTextVNode("收藏演员")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_12, _toDisplayString(_unref(overview).notices === null ? "—" : _unref(overview).notices), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[18] || (_cache[18] = [
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
                            _createElementVNode("span", _hoisted_13, _toDisplayString(_unref(overview).cacheSize), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[19] || (_cache[19] = [
                                _createTextVNode("缓存")
                              ])),
                              _: 1
                            })
                          ]),
                          _: 1
                        }),
                        _createVNode(_component_v_list_item, { class: "px-0" }, {
                          append: _withCtx(() => [
                            _createElementVNode("span", _hoisted_14, _toDisplayString(_unref(overview).nextCheck), 1)
                          ]),
                          default: _withCtx(() => [
                            _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                              default: _withCtx(() => _cache[20] || (_cache[20] = [
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
                      onClick: _cache[1] || (_cache[1] = ($event) => _unref(refreshRuntime)())
                    }, {
                      default: _withCtx(() => _cache[21] || (_cache[21] = [
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

const Console = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-1c4e9ce4"]]);

export { Console as C, consoleEmits as c };
