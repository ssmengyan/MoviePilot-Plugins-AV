<script setup lang="ts">
/**
 * 设置台 · 运行与缓存。
 *
 * - 缓存占用（`/bootstrap.cacheSizeText`，拿不到就用 `cacheSize` 自己换算，都没有显示 `—`）
 *   与「清理缓存」按钮（破坏性操作，先过注入的宿主确认弹窗）。
 * - 订阅检查限流**只读展示**：今天已检查 n/上限、上次检查时间、下次可检查时间、间隔下限。
 *   限流参数是按用户明确要求定的（每天 ≤6 次、间隔 ≥240 分钟），界面不给编辑入口。
 * - javdb 二进制状态后端暂时没有对应字段：不显示，也不编造。
 *
 * 数据来源：`/bootstrap` 的 `cacheSize*` 与 `check`（后端本轮正在补，取不到就 `—`）、
 * `POST /cache/clean`。
 */
import { computed } from 'vue'
import { formatCheckTime } from '../../composables/settingsModel'
import type { CheckInfo } from '../../composables/settingsModel'

const props = defineProps<{
  /** 缓存占用可读文本；空串 = 拿不到。 */
  cacheText: string
  check: CheckInfo | null
  cleaning: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (event: 'clean'): void
  (event: 'refresh'): void
}>()

const DASH = '—'

const cacheLabel = computed(() => (props.cacheText ? props.cacheText : DASH))

const todayLabel = computed(() => {
  const info = props.check
  if (!info || info.checkedToday === undefined) return DASH
  const limit = info.maxPerDay === undefined ? DASH : info.maxPerDay
  return `${info.checkedToday} / ${limit}`
})

const lastCheckLabel = computed(() => formatCheckTime(props.check?.lastCheck, 'last'))
const nextCheckLabel = computed(() => formatCheckTime(props.check?.nextAt, 'next'))

const intervalLabel = computed(() => {
  const minutes = props.check?.minIntervalMin
  return minutes === undefined ? DASH : `${minutes} 分钟`
})

/** 后端 `check` 字段还没上线时给一句解释，避免以为是界面坏了。 */
const checkMissing = computed(() => props.check === null)

const blockedLabel = computed(() => {
  const info = props.check
  if (!info) return ''
  if (info.allowed === false) return info.reason || '当前不可执行检查（受限流约束）'
  return ''
})
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-database-cog" color="primary" />
      </template>
      <v-card-title>运行与缓存</v-card-title>
      <v-card-subtitle>缓存占用与清理 · 限流参数只读</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <div class="avh-cache">
        <div>
          <div class="text-caption text-medium-emphasis">缓存占用</div>
          <div class="text-h6">{{ cacheLabel }}</div>
        </div>
        <div class="avh-cache-actions">
          <v-btn
            color="warning"
            variant="tonal"
            prepend-icon="mdi-broom"
            :loading="props.cleaning"
            @click="emit('clean')"
          >清理缓存</v-btn>
          <v-btn
            variant="text"
            prepend-icon="mdi-refresh"
            :loading="props.loading"
            class="mt-2"
            @click="emit('refresh')"
          >刷新</v-btn>
        </div>
      </div>

      <v-divider class="my-4" />

      <div class="text-subtitle-2 mb-2">订阅检查限流（只读）</div>
      <v-list density="compact" class="pa-0">
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">今天已检查</v-list-item-title>
          <template #append>
            <span class="text-body-2 font-weight-medium">{{ todayLabel }}</span>
          </template>
        </v-list-item>
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">上次检查</v-list-item-title>
          <template #append>
            <span class="text-body-2">{{ lastCheckLabel }}</span>
          </template>
        </v-list-item>
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">下次可检查</v-list-item-title>
          <template #append>
            <span class="text-body-2">{{ nextCheckLabel }}</span>
          </template>
        </v-list-item>
        <v-list-item class="px-0">
          <v-list-item-title class="text-body-2">间隔下限</v-list-item-title>
          <template #append>
            <span class="text-body-2">{{ intervalLabel }}</span>
          </template>
        </v-list-item>
      </v-list>

      <v-alert
        v-if="blockedLabel"
        type="warning"
        variant="tonal"
        density="compact"
        class="text-caption mt-2"
      >{{ blockedLabel }}</v-alert>

      <p class="text-caption text-medium-emphasis mt-3 mb-0">
        限流参数按用户明确要求固定（每天 ≤6 次、间隔 ≥240 分钟），界面不提供放宽入口。
        <span v-if="checkMissing">
          当前后端还没返回 <code>check</code> 字段（本轮正在补），所以上面几行显示
          <code>—</code>；字段上线后自动显示。
        </span>
      </p>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

.avh-cache {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.avh-cache-actions {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  margin-left: auto;
}
</style>
