<script setup lang="ts">
/**
 * 设置台 · 下载规则（全局默认规则）。
 *
 * 字段与文案对齐旧界面的「默认规则」弹窗（`ui/views/subs.js` 的 `ruleFieldsHtml`），
 * 只是搬进设置台常驻，不再每次开弹窗。数据归属：插件自管（`POST /rule`），
 * 点顶条「保存修改」才落库。
 *
 * `minIntervalMin` **只读展示**：它是按用户明确要求定的政策值（间隔 ≥240 分钟），
 * 界面不给编辑入口，保存时原样回传。
 */
import type { RuleState } from '../../composables/settingsModel'
import { POLICY_MIN_INTERVAL_MIN } from '../../composables/settingsPolicy'

const props = defineProps<{
  rule: RuleState
  /** `/bootstrap.check.minIntervalMin`（拿不到时按政策固定值展示）。 */
  policyMinInterval: number
  /** 搜索范围站点数（规则栏只做提示，勾选在「搜索站点」栏）。 */
  siteScopeCount: number
}>()

const emit = defineEmits<{
  (event: 'patch', patch: Partial<RuleState>): void
}>()

const RES_OPTIONS = [
  { value: '1080p', label: '1080P 优先' },
  { value: '2160p', label: '4K 优先' },
  { value: 'only4k', label: '仅 4K' },
] as const

function patch<K extends keyof RuleState>(key: K, value: RuleState[K]): void {
  emit('patch', { [key]: value } as Partial<RuleState>)
}

/** 数字输入：空串/非法先按 0 显示，真正归一交给草稿层（保存时再 floor + 兜底）。 */
function patchNumber(key: 'minSeeders' | 'maxPerDay', raw: string): void {
  const parsed = Number.parseInt(raw, 10)
  patch(key, Number.isFinite(parsed) ? parsed : 0)
}
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-filter-cog" color="primary" />
      </template>
      <v-card-title>下载规则</v-card-title>
      <v-card-subtitle>手动搜索与新建订阅的基准 · 数据走 POST /rule</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <div class="text-caption text-medium-emphasis mb-1">分辨率策略</div>
      <v-btn-toggle
        :model-value="props.rule.res"
        mandatory
        density="comfortable"
        variant="outlined"
        color="primary"
        class="mb-4"
        @update:model-value="(value: any) => value && patch('res', value)"
      >
        <v-btn
          v-for="option in RES_OPTIONS"
          :key="option.value"
          :value="option.value"
        >{{ option.label }}</v-btn>
      </v-btn-toggle>

      <v-switch
        :model-value="props.rule.mustCnsub"
        color="primary"
        hide-details
        inset
        label="必须中文字幕"
        class="mb-1"
        @update:model-value="(value: any) => patch('mustCnsub', value === true)"
      />
      <p class="text-caption text-medium-emphasis mb-3">
        打开则没有中字的种直接淘汰；默认关（AV 站中字少，关掉时中字仍加 32 分优先选）。
      </p>

      <v-switch
        :model-value="props.rule.preferUncensored"
        color="primary"
        hide-details
        inset
        label="破解 / 无码版优先"
        class="mb-3"
        @update:model-value="(value: any) => patch('preferUncensored', value === true)"
      />

      <v-switch
        :model-value="props.rule.allow4k"
        color="primary"
        hide-details
        inset
        label="允许 4K 择优"
        class="mb-1"
        @update:model-value="(value: any) => patch('allow4k', value === true)"
      />
      <p class="text-caption text-medium-emphasis mb-3">1080P 没有好种时升级 4K。</p>

      <div class="avh-grid mb-2">
        <v-text-field
          :model-value="String(props.rule.minSeeders)"
          type="number"
          min="0"
          label="做种数下限"
          hint="低于此值不下载"
          persistent-hint
          variant="outlined"
          density="comfortable"
          @update:model-value="(value: any) => patchNumber('minSeeders', String(value ?? ''))"
        />
        <v-text-field
          :model-value="String(props.rule.maxPerDay)"
          type="number"
          min="1"
          label="每日检查上限"
          hint="每天最多检查订阅几次"
          persistent-hint
          variant="outlined"
          density="comfortable"
          @update:model-value="(value: any) => patchNumber('maxPerDay', String(value ?? ''))"
        />
        <v-text-field
          :model-value="String(props.policyMinInterval || POLICY_MIN_INTERVAL_MIN)"
          label="检查间隔下限（分钟，只读）"
          hint="政策固定值，界面不放宽"
          persistent-hint
          variant="outlined"
          density="comfortable"
          readonly
          disabled
        />
      </div>

      <v-switch
        :model-value="props.rule.btFallback"
        color="primary"
        hide-details
        inset
        label="PT 搜不到时允许 BT 磁力兜底"
        class="mb-3"
        @update:model-value="(value: any) => patch('btFallback', value === true)"
      />

      <div class="text-caption text-medium-emphasis mb-1">命中之后</div>
      <v-btn-toggle
        :model-value="props.rule.trigger"
        mandatory
        density="comfortable"
        variant="outlined"
        color="primary"
        class="mb-1"
        @update:model-value="(value: any) => value && patch('trigger', value)"
      >
        <v-btn value="notify">仅通知</v-btn>
        <v-btn value="auto">自动下载</v-btn>
      </v-btn-toggle>
      <p class="text-caption text-medium-emphasis mb-4">
        「仅通知」时命中的片进「任务」页等你手动下载。
      </p>

      <v-alert type="info" variant="tonal" density="compact" class="text-caption">
        搜索范围由左栏「搜索站点」决定：当前
        {{ props.siteScopeCount ? `限定 ${props.siteScopeCount} 个站点` : '全部已配置站点' }}。
        保存路径 / 下载器 / qB 分类仍在插件存储里沿用现值（本栏暂不提供编辑入口）。
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

.avh-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 16px;
}
</style>
