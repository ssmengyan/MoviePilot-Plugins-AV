import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { C as CONSOLE_EMIT_NAMES, a as Console } from './Console-DJ4rIvEW.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Page",
  props: {
    initialConfig: { default: () => ({}) },
    api: { default: () => ({ get: () => Promise.reject(new Error("宿主 api 不可用")), post: () => Promise.reject(new Error("宿主 api 不可用")) }) },
    pluginId: { default: "" },
    sourcePluginId: { default: "" },
    nativeSubscribe: { type: [Function, null], default: null },
    show_switch: { type: Boolean, default: true }
  },
  emits: CONSOLE_EMIT_NAMES,
  setup(__props, { emit: __emit }) {
    const emit = __emit;
    return (_ctx, _cache) => {
      return _openBlock(), _createBlock(Console, {
        mode: "data",
        api: _ctx.api,
        "plugin-id": _ctx.pluginId,
        "source-plugin-id": _ctx.sourcePluginId,
        "native-subscribe": _ctx.nativeSubscribe,
        show_switch: _ctx.show_switch,
        "initial-config": _ctx.initialConfig,
        onSave: _cache[0] || (_cache[0] = (config) => emit("save", config)),
        onLayout: _cache[1] || (_cache[1] = (payload) => emit("layout", payload)),
        onSwitch: _cache[2] || (_cache[2] = ($event) => emit("switch")),
        onClose: _cache[3] || (_cache[3] = ($event) => emit("close")),
        onAction: _cache[4] || (_cache[4] = ($event) => emit("action"))
      }, null, 8, ["api", "plugin-id", "source-plugin-id", "native-subscribe", "show_switch", "initial-config"]);
    };
  }
});

export { _sfc_main as _ };
