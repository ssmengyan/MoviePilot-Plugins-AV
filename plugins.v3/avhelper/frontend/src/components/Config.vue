<script setup lang="ts">
import Console from './Console.vue'
import { CONSOLE_EMIT_NAMES } from './emitContract'
import { type ConfigProps } from './contract'

/**
 * 暴露给宿主的 `./Config`：插件配置弹窗正文（`initialConfig` = `get_form()` 的 model）。
 *
 * 和 `./Page` 共用 `Console.vue`，只差**设置窗口初始就是开着的**，并且关掉窗口后露出的是
 * 数据台（同一个 Console 画在下面）—— 用户的要求就是"关掉设置直接回主界面"。
 *
 * ⚠️ 事件声明方式同 `Page.vue`：必须用字符串数组（见 `emitContract.ts`）。
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
    mode="settings"
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
