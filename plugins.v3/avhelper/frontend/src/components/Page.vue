<script setup lang="ts">
import Console from './Console.vue'
import { CONSOLE_EMIT_NAMES } from './emitContract'
import { type ConfigProps } from './contract'

/**
 * 暴露给宿主的 `./Page`：插件详情弹窗正文。
 *
 * 薄封装——和 `./Config` 渲染的是同一个 `Console.vue`，只差设置窗口的初始开合
 * （设计文档 §1：用户无论从哪个入口进来，看到的都是同一套界面）。
 *
 * ⚠️ 事件必须用**字符串数组**声明（`CONSOLE_EMIT_NAMES`），不能用 `defineEmits(consoleEmits())`
 * 那种返回空函数的写法：后者编译出的 `emits` 是个函数，Vue 认不出来，五个事件会退化成
 * fallthrough attrs 层层下传并双发（详见 `emitContract.ts` 里的真机实测记录）。
 */
withDefaults(defineProps<ConfigProps>(), {
  api: () => ({ get: () => Promise.reject(new Error('宿主 api 不可用')), post: () => Promise.reject(new Error('宿主 api 不可用')) }),
  pluginId: '',
  sourcePluginId: '',
  nativeSubscribe: null,
  show_switch: true,
  initialConfig: () => ({}),
})

const emit = defineEmits(CONSOLE_EMIT_NAMES)
</script>

<template>
  <Console
    mode="data"
    :api="api"
    :plugin-id="pluginId"
    :source-plugin-id="sourcePluginId"
    :native-subscribe="nativeSubscribe"
    :show_switch="show_switch"
    :initial-config="initialConfig"
    @save="(config: any) => emit('save', config)"
    @layout="(payload: any) => emit('layout', payload)"
    @switch="emit('switch')"
    @close="emit('close')"
    @action="emit('action')"
  />
</template>
