<script setup lang="ts">
/**
 * 设置台 · 运行与缓存。
 *
 * - **缓存上限（0.6.3 加，用户要求）**：一个可编辑的 GB 输入框，属于**宿主插件配置**
 *   （`cache_max_gb`，与 `proxy` 同类：点「保存修改」时随整份配置 PUT 上去）。
 *   默认 1G —— 老版本写死 60G，对小硬盘用户是纯粹的恐吓，实测长期占用不到 0.3G。
 *   输入框旁边实时给出「已用 / 上限」的占比，改完不必保存也能先看到效果。
 * - 缓存占用（`/bootstrap.cacheSizeText`，拿不到就用 `cacheSize` 自己换算，都没有显示 `—`）
 *   与「清理缓存」按钮（破坏性操作，先过注入的宿主确认弹窗）。
 * - 订阅检查限流**只读展示**：今天已检查 n/上限、上次检查时间、下次可检查时间、间隔下限。
 *   限流参数是按用户明确要求定的（每天 ≤6 次、间隔 ≥240 分钟），界面不给编辑入口。
 * - javdb 二进制状态后端暂时没有对应字段：不显示，也不编造。
 *
 * 口径提醒：输入框里的空/乱码/0 由 `toCacheGbText()`（前端）与 `paths.cache_limit_gb()`
 * （后端）按同一套规则归一成 1G，**不是**「不限制」——上限归零会让每晚的淘汰清空缓存目录。
 *
 * 数据来源：`/bootstrap` 的 `cacheSize*` 与 `check`、`POST /cache/clean`、
 * 宿主配置草稿（`config.cache_max_gb`）。
 */
import { computed } from 'vue'
import {
  CACHE_MAX_GB_FALLBACK,
  CACHE_MAX_GB_MIN,
  formatBytes,
  formatCheckTime,
  toCacheGb,
} from '../../composables/settingsModel'
import type { CheckInfo, HostConfigDraft } from '../../composables/settingsModel'

const props = defineProps<{
  /** 宿主配置草稿（本栏只关心 `cache_max_gb`）。 */
  config: HostConfigDraft
  /** 缓存占用可读文本；空串 = 拿不到。 */
  cacheText: string
  /** 缓存占用字节数；`null` = 拿不到（占比就不显示）。 */
  cacheBytes: number | null
  check: CheckInfo | null
  cleaning: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (event: 'clean'): void
  (event: 'refresh'): void
  /** 打补丁到宿主配置草稿（只传改动的字段）。 */
  (event: 'patch', patch: Partial<HostConfigDraft>): void
}>()

const DASH = '—'

const cacheLabel = computed(() => (props.cacheText ? props.cacheText : DASH))

/** 上限（归一后的数值）：输入框里是 0.05 也按 0.1 算，与保存后真正生效的一样。 */
const limitGb = computed(() => toCacheGb(props.config.cache_max_gb))

/** 「已用 180 MB / 上限 1 GB（18%）」：占比拿不到字节数就只报上限。 */
const usageLabel = computed(() => {
  const limitText = `${limitGb.value} GB`
  const bytes = props.cacheBytes
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) {
    return `上限 ${limitText}`
  }
  const percent = limitGb.value > 0 ? Math.round((bytes / (limitGb.value * 1024 ** 3)) * 100) : 0
  return `已用 ${props.cacheText || formatBytes(bytes)} / 上限 ${limitText}（${percent}%）`
})

/** 输入框的提示：默认值 + 现在到底按几 G 生效（用户填了 0.05 也能立刻看到会被抬到 0.1）。 */
const limitHint = computed(() => {
  const raw = String(props.config.cache_max_gb ?? '').trim()
  const normalized = toCacheGb(raw)
  const base = `超过上限就按最旧淘汰（每天 4 点跑一次）。默认 ${CACHE_MAX_GB_FALLBACK}G 就够用：`
    + `实测长期占用不到 0.3G；留空按默认值处理。`
  if (!raw || Number.parseFloat(raw) === normalized) return base
  return `${base} 当前输入按 ${normalized}G 生效（下限 ${CACHE_MAX_GB_MIN}G）。`
})

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
      <v-card-subtitle>缓存上限与清理 · 限流参数只读</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <div class="avh-cache">
        <div>
          <div class="text-caption text-medium-emphasis">缓存占用</div>
          <div class="text-h6">{{ cacheLabel }}</div>
          <div class="text-caption text-medium-emphasis">{{ usageLabel }}</div>
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

      <v-text-field
        class="mt-4"
        :model-value="props.config.cache_max_gb"
        label="缓存上限（GB）"
        placeholder="留空 = 1"
        type="number"
        min="0.1"
        step="0.5"
        suffix="GB"
        :hint="limitHint"
        persistent-hint
        variant="outlined"
        density="comfortable"
        clearable
        @update:model-value="(value: any) => emit('patch', { cache_max_gb: value ?? '' })"
      />

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
