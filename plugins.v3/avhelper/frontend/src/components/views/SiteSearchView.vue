<script setup lang="ts">
/**
 * 视图：站点搜索（S6 第一个原生化视图）。
 *
 * 对照老实现 `ui/views/sitesearch.js`（`renderSiteSearch` / `doSiteSearch` / `sitePickList`），
 * 逐条对齐的是**行为与文案**，DOM 换成 Vuetify 组件：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | `#ssInput` + Enter → `doSiteSearch()` | 同一个 `v-text-field`，`@keydown.enter` |
 * | `#ssBtn`「搜索站点」/ 搜索中禁用 + 文案「搜索中…」 | 同一个按钮，`:loading` + 文案切换由 `searching` 驱动 |
 * | `#ssPref`「只搜馒头 + 肉丝」、`#ssAll`「全选站点」、站点 chips 点击切换 | **不做**（用户明确反感把站点平铺成可点 chips）；范围改成只读回显一行 + 「改范围」跳设置台 |
 * | 范围默认 `S.sitePick`（缺省 `['馒头','Rousi']` ∩ 站点） | 默认 `store.rule.sites`，**空 = 全部站点**（与设置台「搜索站点」栏同一语义） |
 * | 空态 `输入番号或关键词后点「搜索站点」` | `EmptyState`，文案逐字一致 |
 * | 结果 `candTable(task, 0)` + `bindDownloadButtons` | `common/CandTable.vue` + `@download` → `store.startDownload` + 行内 loading |
 * | `queueThumb(task.number)` 补封面 | `common.queueThumb(api, task.number)`（同一套串行补图） |
 * | `renderPills()` + `loadTasks(false)` | `store.refreshTasks()`（角标与任务表由 store 统一持有） |
 * | 无错误态（只有 toast） | 加 `ErrorState`：正文「站点搜索失败：{原因}」，`reason` 照老实现显示 |
 *
 * 刻意**不做**：5 秒轮询（老站点搜索页也没有）。
 */
import { computed, nextTick, ref, watch, type Ref } from 'vue'
import CandTable from '../common/CandTable.vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import { queueThumb } from '../common/common'
import { pushBottomToast } from '../../composables/bottomToast'
import { hostToast, type PluginApi } from '../../composables/usePluginApi'
import { requestSettingsSection } from '../../composables/settingsJump'
import { nowStr } from '../../composables/storeTypes'
import type { PluginStore } from '../../composables/usePluginStore'
import type { SearchTask, SiteOption } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）。 */
    store: PluginStore
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用（后端给的相对地址也靠它）。 */
    pluginId?: string
    /**
     * 用请求器补封面（`plugin/detail`）。不传时退回 `NOOP_API`，补图失败不影响搜索。
     * 与 store 分开是因为 store 只暴露动作，不暴露底层请求器。
     */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null, toast: null },
)

const emit = defineEmits<{
  /** 用户点「改范围」：请壳把弹窗切到设置台的「搜索站点」栏（宿主合同里的 switch）。 */
  (event: 'switch'): void
  /** 搜索完成 / 范围栏被点：请壳刷新右栏「运行概况」。 */
  (event: 'refreshSide'): void
}>()

const t = hostToast(props.toast as any)
const candTableRef = ref<InstanceType<typeof CandTable> | null>(null)

const keyword = ref('')
/** 搜索在途：按钮 `:loading` + 文案「搜索中…」（老实现直接改按钮文字与 disabled）。 */
const searching = ref(false)
/** 上次成功搜索的时刻（`HH:MM:SS`）：老实现 `S.siteSearchAt`，只活在本页。 */
const searchedAt = ref('')
/** 最近一次搜索的结果任务：老实现 `S.siteTask`。 */
const task: Ref<SearchTask | null> = ref(null)
/** 搜索失败文案；成功后清空（老实现只 toast，这里同时留一条可重试的错误态）。 */
const errorText = ref('')
/** 「重试」按钮的转圈态。 */
const retrying = ref(false)

/** 站点名清单（老 `sitePickList()` 只回传 `S.sites` 的名字，不写回状态）。 */
const siteNames = computed<string[]>(() =>
  (props.store.sites.value as SiteOption[]).map(item => String(item?.name || '')).filter(Boolean),
)

/**
 * 本次搜索用的站点范围 = 规则里的 `sites`；**空数组 = 全部站点**。
 * 过滤掉规则里有、但当前站点清单里已没有的名字，避免给后端送一个不存在的站点名。
 */
const picked = computed<string[]>(() => {
  const names = siteNames.value
  return (props.store.rule.value.sites || []).map(String).filter(name => names.indexOf(name) >= 0)
})

/** 站点 → 适配器标签（老实现 `infoOf(n).adapterLabel`）。 */
function labelOf(name: string): string {
  const hit = (props.store.sites.value as SiteOption[]).filter(item => item.name === name)[0]
  return String(hit?.adapterLabel || '')
}

/** 范围回显：`馒头（馒头成人区…）、Rousi（…）`，空 = 「全部站点」。 */
const scopeText = computed<string>(() => {
  if (!picked.value.length) return '全部站点'
  return picked.value
    .map(name => {
      const label = labelOf(name)
      return label ? `${name}（${label}）` : name
    })
    .join('、')
})

/** 结果区展示：老实现是 `S.siteTask && cands.length ? candTable : 空态`。 */
const cands = computed(() => (Array.isArray(task.value?.cands) ? task.value?.cands || [] : []))
const hasResult = computed(() => !!task.value && cands.value.length > 0)

/** 按钮文案（老实现在飞行中把「搜索站点」改成「搜索中…」）。 */
const searchLabel = computed(() => (searching.value ? '搜索中…' : '搜索站点'))

/** 计数不等于 0 时先解挂行内 loading，再换表（老实现是整块 innerHTML 重建）。 */
watch(task, async () => {
  candTableRef.value?.clearAllPending()
  await nextTick()
  candTableRef.value?.clearAllPending()
})

/** 整表解锁：整块结果都要换新时才用（重搜 / 结果被替换）。 */
function clearPending(): void {
  candTableRef.value?.clearAllPending()
  void nextTick(() => candTableRef.value?.clearAllPending())
}

/** 搜索（老 `doSiteSearch()`）：空关键词只提示、不发请求。 */
async function doSearch(): Promise<void> {
  const kw = keyword.value.trim()
  if (!kw) {
    t.warning('先输入番号或关键词')
    return
  }
  // 老实现用 `#ssBtn` 的 disabled 兜住重复点击；这里是显式守卫（语义一致）。
  if (searching.value) return
  searching.value = true
  errorText.value = ''
  try {
    const sites = picked.value.slice()
    const res = await props.store.searchKeyword(kw, sites)
    if (!res.ok) {
      errorText.value = res.message || '请稍后重试'
      t.warning(res.message || '搜索失败，请稍后重试')
      return
    }
    const result = (res.data || null) as SearchTask | null
    task.value = result
    searchedAt.value = nowStr()
    if (result && result.id !== undefined && result.id !== null) {
      const next = props.store.tasks.value.filter(item => String(item.id) !== String(result.id))
      props.store.tasks.value = [result, ...next]
    }
    const count = Array.isArray(result?.cands) ? (result?.cands || []).length : 0
    // 老实现是一条 toast：命中走 ok（正文「kw · 选一个点「下载」」），没命中走 warn（正文取后端 reason）。
    if (count) {
      t.success(`搜到 ${count} 个候选`)
      t.info(`${kw} · 选一个点「下载」`)
    } else {
      t.warning('没有候选')
      t.info((result && result.reason) || '换个关键词或站点再试')
    }
    // 后端没有这个番号的封面时后台补一次（补到就换上）；老实现的调用点就是这里。
    if (result?.number && props.api) queueThumb(props.api, result.number)
    void props.store.refreshTasks(false)
    emit('refreshSide')
  } finally {
    searching.value = false
    clearPending()
  }
}

/** 失败后的「重试」：重放上一次搜索（老实现点「搜索站点」等价）。 */
async function retry(): Promise<void> {
  retrying.value = true
  try {
    await doSearch()
  } finally {
    retrying.value = false
  }
}

/**
 * 行内「下载 / 仍要下载」：老 `bindDownloadButtons` → `startDownload(id, site, btn, force)`。
 *
 * 与任务页的唯一差别：这张卡片本身就是"搜索结果"，下完**不会消失**，所以成功时也要把
 * 那一行的转圈解下来（否则那一行会一直转到卡片被换掉）。转圈仍然只由**这一行**的结论结束：
 * 别的行完成、重搜之外的任何动作都不碰它。
 */
async function onDownload(payload: { taskId: string; site: string; force: boolean }): Promise<void> {
  const res = await props.store.startDownload(payload.taskId, payload.site, payload.force)
  // 同一行重复触发被 store 合并（正常点不出来）：静默，别动在飞那一次的转圈。
  if (res.kind === 'busy') return
  const site = String(payload.site || '').trim()
  clearRow(payload.taskId, payload.site)
  if (!res.ok) {
    pushBottomToast('warning', `${site ? site + ' · ' : ''}下载失败：${res.message || '请稍后重试'}`)
    return
  }
  pushBottomToast('success', `已提交下载：${site ? site + ' · ' : ''}进度见「下载」页`)
  void props.store.refreshTasks(false)
}

/** 只解这一行（`任务id|站点`），同站点的别的行不受影响。 */
function clearRow(taskId: string, site: string): void {
  candTableRef.value?.clearRow(taskId, site)
}

/** 「改范围」：本视图不改规则，去设置台改（先告诉用户去哪儿改，避免"点了没反应"）。 */
function changeScope(): void {
  t.info('搜索范围在「设置台 → 搜索站点」栏里改，保存后本页立即生效')
  // `switch` 只互换两个弹窗、不带载荷：用一次性便签让设置台实例直接落在「搜索站点」栏。
  requestSettingsSection('sites')
  emit('switch')
}

/** 点范围那一行也当入口（老实现整行是可点 chips，这里退化成一句提示 + 跳转）。 */
function onScopeClick(): void {
  t.info('搜索范围在「设置台 → 搜索站点」栏里改')
}
</script>

<template>
  <div class="avh-sitesearch">
    <div class="avh-sitesearch__toolbar">
      <v-text-field
        v-model="keyword"
        class="avh-sitesearch__input"
        placeholder="番号或关键词（如 MIDV-946）…"
        autocomplete="off"
        density="compact"
        variant="outlined"
        hide-details
        :disabled="searching"
        @keydown.enter="doSearch"
      />
      <v-btn
        color="primary"
        variant="flat"
        :loading="searching"
        :disabled="searching"
        prepend-icon="mdi-magnify"
        @click="doSearch"
      >{{ searchLabel }}</v-btn>
      <div class="avh-sitesearch__spacer" />
      <span class="avh-sitesearch__hint">
        {{ searchedAt ? `上次搜索 ${searchedAt}` : '命中即停 · 站点间隔 3-8 秒' }}
      </span>
    </div>

    <div class="avh-sitesearch__range">
      <div class="avh-sitesearch__label">搜索范围</div>
      <div class="avh-sitesearch__scope" :title="scopeText" @click="onScopeClick">{{ scopeText }}</div>
      <v-btn variant="text" size="small" prepend-icon="mdi-tune" @click="changeScope">改范围</v-btn>
    </div>

    <ErrorState
      v-if="errorText"
      :message="`站点搜索失败：${errorText}`"
      :retrying="retrying"
      @retry="retry"
    />

    <CandTable
      v-else-if="hasResult && task"
      ref="candTableRef"
      :task="task"
      :plugin-id="pluginId"
      @download="onDownload"
    />

    <EmptyState v-else text="输入番号或关键词后点「搜索站点」" />
  </div>
</template>

<style scoped>
.avh-sitesearch__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.avh-sitesearch__input {
  min-width: 280px;
  flex: 0 1 360px;
}

.avh-sitesearch__spacer {
  flex: 1;
}

.avh-sitesearch__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 老实现是 `.fld > label + .chips`；这里只回显一行文本（站点不平铺成可点 chips）。 */
.avh-sitesearch__range {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-sitesearch__label {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-sitesearch__scope {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 46rem;
  padding: 5px 10px;
  font-size: 12.5px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
