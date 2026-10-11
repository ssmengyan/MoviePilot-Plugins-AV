<script setup lang="ts">
/**
 * 设置台 · 关于。静态信息 + 只读接口：版本号取 `plugin/page/<id>` 的 `plugin_version`，
 * 拿不到就显示 `—`（不编造）。数据根一行来自后端常量（只读展示，界面不可改）。
 *
 * ⚠️ `props` 必须从 `defineProps()` 接出来才能在模板里用：不接的话模板里的
 * `props.xxx` 会被编译成 `_ctx.props.xxx`，而 setup 状态上没有 `props` 这个键，
 * 运行时直接 `Cannot read properties of undefined`（实测踩过）。
 */
const props = defineProps<{
  /** `plugin/page/<id>` 里的 `plugin_version`；空串 = 没取到。 */
  version: string
  /** 宿主传进来的插件实例 id（分身时是分身 id）。 */
  pluginId: string
  /** 分身共享的源插件 id；普通插件为空。 */
  sourcePluginId: string
}>()

const DASH = '—'

/** 后端常量：与 `__init__.py` 的 `CACHE_ROOT`、`store.py` 的 `DATA_ROOT` 保持一致。 */
const DATA_ROOT = '/avhelper/cache'
const JAVDB_BIN = '/avhelper/bin/javdb'
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-information-outline" color="primary" />
      </template>
      <v-card-title>关于</v-card-title>
      <v-card-subtitle>AVHelper · Vue 联邦渲染模式</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <v-list density="compact" class="pa-0">
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">版本号</v-list-item-title>
          <template #append>
            <span class="text-body-2 font-weight-medium">{{ props.version || DASH }}</span>
          </template>
        </v-list-item>
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">插件 ID</v-list-item-title>
          <template #append>
            <span class="text-body-2 font-weight-medium">{{ props.pluginId || DASH }}</span>
          </template>
        </v-list-item>
        <v-list-item v-if="props.sourcePluginId" class="px-0">
          <v-list-item-title class="text-body-2">源插件 ID（分身）</v-list-item-title>
          <template #append>
            <span class="text-body-2">{{ props.sourcePluginId }}</span>
          </template>
        </v-list-item>
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">数据根</v-list-item-title>
          <template #append>
            <span class="text-body-2"><code>{{ DATA_ROOT }}</code></span>
          </template>
        </v-list-item>
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">javdb 二进制</v-list-item-title>
          <template #append>
            <span class="text-body-2"><code>{{ JAVDB_BIN }}</code>（与原版共用，只读）</span>
          </template>
        </v-list-item>
      </v-list>

      <v-divider class="my-3" />

      <p class="text-caption text-medium-emphasis mb-2">
        数据根在插件数据卷上：SQLite 落在
        <code>{{ DATA_ROOT }}/meta/avhelper.db</code>，图片与 JSON 缓存同根。
        SQLite、图片与 JSON 缓存同根，全在插件数据卷上。
      </p>
      <p class="text-caption text-medium-emphasis mb-0">
        界面上方是宿主的统一弹窗：标题栏、关闭按钮与 Toast 都由宿主提供，本插件复用
        <code>moviepilot:toast</code> / <code>moviepilot:confirm</code>，不自建。
        版本号来自 <code>plugin/page/&lt;id&gt;</code> 的 <code>plugin_version</code>，取不到显示 <code>—</code>。
      </p>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}
</style>
