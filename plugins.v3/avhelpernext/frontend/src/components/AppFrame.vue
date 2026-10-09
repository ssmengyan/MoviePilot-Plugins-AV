<script setup lang="ts">
import { computed } from 'vue'

/**
 * 第一阶段数据台：用 iframe 承载插件自带的单文件应用。
 *
 * - `src` 必须带**尾斜杠**：`/api/v1/plugin/<id>/ui/`。后端 `GET /ui`（无尾斜杠）
 *   会 307 到 `/ui/`，而 `ui/index.html` 里的 `<script type="module" src="./app.js">`
 *   在无尾斜杠时会被解析成 `/…/app.js`（少一层），模块直接 404。
 * - 高度沿用现有实现的 `78vh`（设计文档 §7 风险：改 `calc(100vh-…)` 需真机调）。
 * - `border: 0` 去 iframe 默认边框。
 */
const props = withDefaults(
  defineProps<{
    /** 插件实例 id（普通插件 = pluginId，分身用 sourcePluginId 取同一份界面）。 */
    pluginId: string
    /** 宿主管的插件版本，仅用于破缓存（可选）。 */
    version?: string
    /** 数据台版块 key，变化时重挂 iframe（内部导航由被嵌应用自己管）。 */
    sectionKey?: string
  }>(),
  { version: '', sectionKey: 'discover' },
)

const src = computed(() => {
  const base = `/api/v1/plugin/${props.pluginId}/ui/`
  const query = props.version ? `?v=${encodeURIComponent(props.version)}` : ''
  return `${base}${query}`
})
</script>

<template>
  <iframe
    :key="`${pluginId}:${sectionKey}`"
    :src="src"
    class="avh-app-frame"
    title="AV 资源助手 · 内嵌应用"
    referrerpolicy="no-referrer"
    allow="clipboard-write"
  />
</template>

<style scoped>
.avh-app-frame {
  display: block;
  width: 100%;
  height: 78vh;
  border: 0;
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}
</style>
