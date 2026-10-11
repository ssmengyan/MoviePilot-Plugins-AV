<script setup lang="ts">
/**
 * 设置台 · 搜索站点。
 *
 * **用户明确要求：不要把十几个站点平铺在主界面上。** 主界面只回显当前搜索范围
 * （「当前搜索范围：馒头、Rousi」/「全部站点」），勾选、筛选、排序全在弹窗里做：
 *   - 「选择站点」：全选 / 全不选 / 按名字筛选 / 逐项勾选 → 写入 `rule.sites`；
 *   - 「优先站点」：先勾（默认沿用 `rule.sites`），再上下移排序 → 写入 `rule.prefSites`。
 *
 * 数据归属：插件自管（`POST /rule` 的 `sites` / `prefSites`），点「保存修改」才真正落库。
 *
 * 弹窗用 Vuetify 的 `v-dialog`（`attach="body"`，躲开宿主卡片的层叠上下文），
 * 不用注入的 `moviepilot:dialog`：设计文档 §4 明确两者二选一，而这两个弹窗自带数据、
 * 不需要宿主托管的复杂表单；宿主弹窗只留给「确认」这种简单场景（见 useHostDialogs）。
 */
import { computed, ref } from 'vue'
import type { SiteOption } from '../../composables/settingsModel'

const props = defineProps<{
  /** 搜索范围站点；空数组 = 全部站点。 */
  sites: string[]
  /** 优先站点（顺序有意义：命中即停）。 */
  prefSites: string[]
  /** 宿主索引器清单（`/bootstrap.sites`）。 */
  options: SiteOption[]
  /** 站点清单是否已经拿到（区分「没选」与「还没加载」）。 */
  loaded: boolean
}>()

const emit = defineEmits<{
  (event: 'update:sites', value: string[]): void
  (event: 'update:prefSites', value: string[]): void
}>()

/** 主界面回显：空 = 全部已配置站点。 */
const scopeText = computed(() =>
  props.sites.length ? props.sites.join('、') : '全部站点',
)

const prefText = computed(() =>
  props.prefSites.length ? props.prefSites.join(' › ') : '未设置（按站点清单顺序）',
)

/* ---------- 选择站点弹窗 ---------- */

const pickOpen = ref(false)
const pickQuery = ref('')
const pickDraft = ref<string[]>([])

const filteredOptions = computed(() => {
  const keyword = pickQuery.value.trim().toLowerCase()
  const list = props.options.filter(item => item.name)
  if (!keyword) return list
  return list.filter(item =>
    `${item.name} ${item.adapter || ''} ${item.adapterLabel || ''}`.toLowerCase().includes(keyword),
  )
})

function openPick(): void {
  pickDraft.value = [...props.sites]
  pickQuery.value = ''
  pickOpen.value = true
}

function pickToggle(name: string): void {
  const index = pickDraft.value.indexOf(name)
  if (index >= 0) pickDraft.value.splice(index, 1)
  else pickDraft.value.push(name)
}

function pickAll(): void {
  // 只对「当前筛选出来的」做全选，方便先筛再选。
  const names = filteredOptions.value.map(item => item.name)
  pickDraft.value = Array.from(new Set([...pickDraft.value, ...names]))
}

function pickNone(): void {
  const names = new Set(filteredOptions.value.map(item => item.name))
  pickDraft.value = pickDraft.value.filter(name => !names.has(name))
}

function pickConfirm(): void {
  // 顺序按站点清单排，免得勾选顺序影响存库内容。
  const order = new Map(props.options.map((item, index) => [item.name, index]))
  emit('update:sites', [...pickDraft.value].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0)))
  pickOpen.value = false
}

/* ---------- 优先站点弹窗 ---------- */

const prefOpen = ref(false)
const prefDraft = ref<string[]>([])
/** 未勾进优先列表的站点（弹窗里作为「候选」呈现）。 */
const prefCandidates = computed(() =>
  props.options.filter(item => item.name && !prefDraft.value.includes(item.name)),
)

function openPref(): void {
  prefDraft.value = [...props.prefSites]
  prefOpen.value = true
}

function prefAdd(name: string): void {
  if (!prefDraft.value.includes(name)) prefDraft.value.push(name)
}

function prefRemove(index: number): void {
  prefDraft.value.splice(index, 1)
}

/** 上下移：`delta` 为 -1 上移、+1 下移（优先站点命中即停，顺序有意义）。 */
function prefMove(index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= prefDraft.value.length) return
  const next = [...prefDraft.value]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item as string)
  prefDraft.value = next
}

function prefConfirm(): void {
  emit('update:prefSites', [...prefDraft.value])
  prefOpen.value = false
}
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-web" color="primary" />
      </template>
      <v-card-title>搜索站点</v-card-title>
      <v-card-subtitle>勾选与排序都在弹窗里 · 数据走 POST /rule</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <div class="avh-row">
        <div class="avh-row-main">
          <div class="text-caption text-medium-emphasis mb-1">当前搜索范围</div>
          <div class="avh-scope text-body-1">{{ scopeText }}</div>
          <div class="text-caption text-medium-emphasis mt-3 mb-1">优先站点（命中即停，顺序有意义）</div>
          <div class="avh-scope text-body-2">{{ prefText }}</div>
        </div>
        <div class="avh-row-actions">
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-checkbox-multiple-marked-outline"
            class="mb-2"
            @click="openPick"
          >选择站点</v-btn>
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-sort"
            @click="openPref"
          >优先站点</v-btn>
        </div>
      </div>

      <v-alert
        v-if="loaded && !options.length"
        type="warning"
        variant="tonal"
        density="compact"
        class="mt-3 text-caption"
      >没有读到任何站点（MoviePilot 站点目录为空或读取失败），下面两个按钮打开也没有内容可选。</v-alert>

      <p class="text-caption text-medium-emphasis mt-4 mb-0">
        「当前搜索范围」留空 = 全部已配置站点；优先站点会先搜、命中即停，所以顺序有意义。
        两处都只写进默认规则，按顶条「保存修改」才生效。
      </p>
    </v-card-text>
  </v-card>

  <!-- 选择站点 -->
  <v-dialog v-model="pickOpen" max-width="640" scrollable attach="body">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-checkbox-multiple-marked-outline" color="primary" class="me-2" />
        选择站点
      </v-card-title>
      <v-card-subtitle>不勾任何站点 = 搜索全部已配置站点（{{ props.options.length }} 个）</v-card-subtitle>
      <v-card-text>
        <v-text-field
          v-model="pickQuery"
          label="按名字筛选"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          clearable
          hide-details
          class="mb-3"
        />
        <div class="d-flex align-center mb-2">
          <v-btn size="small" variant="text" @click="pickAll">全选（当前筛选）</v-btn>
          <v-btn size="small" variant="text" @click="pickNone">全不选（当前筛选）</v-btn>
          <v-spacer />
          <span class="text-caption text-medium-emphasis">已选 {{ pickDraft.length }}</span>
        </div>
        <v-divider class="mb-1" />
        <div class="avh-list">
          <v-checkbox
            v-for="item in filteredOptions"
            :key="item.name"
            :model-value="pickDraft.includes(item.name)"
            :label="item.name"
            density="compact"
            hide-details
            color="primary"
            @update:model-value="() => pickToggle(item.name)"
          >
            <template #append>
              <span class="text-caption text-medium-emphasis">{{ item.adapterLabel || item.adapter || '' }}</span>
            </template>
          </v-checkbox>
          <div v-if="!filteredOptions.length" class="text-caption text-medium-emphasis pa-2">
            没有匹配的站点。
          </div>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="pickOpen = false">取消</v-btn>
        <v-btn color="primary" variant="flat" @click="pickConfirm">确定</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 优先站点（勾选 + 上下移排序） -->
  <v-dialog v-model="prefOpen" max-width="640" scrollable attach="body">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-sort" color="primary" class="me-2" />
        优先站点
      </v-card-title>
      <v-card-subtitle>先搜这些站，命中即停 —— 顺序就是搜索顺序</v-card-subtitle>
      <v-card-text>
        <div class="text-caption text-medium-emphasis mb-1">优先顺序（{{ prefDraft.length }}）</div>
        <v-list density="compact" class="avh-list mb-3">
          <v-list-item v-for="(name, index) in prefDraft" :key="`${name}:${index}`">
            <template #prepend>
              <span class="text-caption text-medium-emphasis avh-idx">{{ index + 1 }}</span>
            </template>
            <v-list-item-title>{{ name }}</v-list-item-title>
            <template #append>
              <v-btn
                icon="mdi-arrow-up"
                size="x-small"
                variant="text"
                :disabled="index === 0"
                @click="prefMove(index, -1)"
              />
              <v-btn
                icon="mdi-arrow-down"
                size="x-small"
                variant="text"
                :disabled="index === prefDraft.length - 1"
                @click="prefMove(index, 1)"
              />
              <v-btn
                icon="mdi-close"
                size="x-small"
                variant="text"
                @click="prefRemove(index)"
              />
            </template>
          </v-list-item>
          <v-list-item v-if="!prefDraft.length">
            <v-list-item-title class="text-caption text-medium-emphasis">
              还没有优先站点：按下面的候选加进来。
            </v-list-item-title>
          </v-list-item>
        </v-list>

        <v-divider class="mb-2" />
        <div class="text-caption text-medium-emphasis mb-1">候选站点（点击加入优先顺序）</div>
        <div class="avh-chips">
          <v-chip
            v-for="item in prefCandidates"
            :key="item.name"
            size="small"
            variant="tonal"
            prepend-icon="mdi-plus"
            @click="prefAdd(item.name)"
          >{{ item.name }}</v-chip>
          <span v-if="!prefCandidates.length" class="text-caption text-medium-emphasis">
            全部站点都已在优先列表里。
          </span>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="prefOpen = false">取消</v-btn>
        <v-btn color="primary" variant="flat" @click="prefConfirm">确定</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

.avh-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.avh-row-main {
  flex: 1 1 320px;
  min-width: 0;
}

.avh-row-actions {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.avh-scope {
  word-break: break-word;
}

.avh-list {
  max-height: 46vh;
  overflow-y: auto;
}

.avh-idx {
  display: inline-block;
  min-width: 18px;
}

.avh-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
