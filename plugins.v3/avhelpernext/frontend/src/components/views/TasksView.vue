<script setup lang="ts">
/**
 * 视图：任务（S6 第三个原生化视图）。
 *
 * 对照老实现 `ui/views/tasks.js`（`renderTasks` / `startDownload` / `loadTasks` /
 * `startTaskPolling`）与它的调用方 `ui/app.js`（`bindUi` 的 nav 点击分支），逐条对齐的是
 * **行为与文案**，DOM 换成 Vuetify 组件；候选表本体（列、行样式、下载按钮）在
 * `common/CandTable.vue` 里逐列对齐 `candTable(t, idx)`，本视图只负责"画哪些任务"。
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | `renderTasks`：`pend = S.tasks.filter(t => t.state === 'await')`，**只画待确认**，下载进度在「下载」页 | `pending` 同款过滤；本视图不画任何队列行 |
 * | `dling = S.queue.filter(q => q.state !== 'done').length`，非 0 时左侧 `<span class="hint">⏬ {n} 个已提交，进度看「下载」页</span>` | 同一个 `store.downloading` 派生值、同一句文案（0 时同样不渲染） |
 * | 右侧 `↻ 刷新任务` → `loadTasks(true)`（**非静默**：失败 toast「任务读取失败」）+ `toast('任务','正在刷新…')` | `store.refreshTasks(false)` + `t.info('正在刷新…')`；失败 `t.warning('任务读取失败：{原因}')`（写法照 S6-2 下载页对同一条 toast 的处理） |
 * | `'<div class="secttl">待确认（' + pend.length + '）</div>'` | 同一句文案的小标题（`.avh-tasks__secttl` 对齐 `app.css` 的 `.secttl`） |
 * | 每个待确认任务一块 `candTable(t, i)`；`bindDownloadButtons(m)` 事件委托 | `common/CandTable.vue`（`v-for`）+ `@download`；行内 loading 由它自持，动作结束后用 `defineExpose({ clearPending })` 清掉 |
 * | `startDownload` 失败 `toast('下载失败', r.message || '请稍后重试', 'warn')`，并把按钮 `disabled = false` | `t.warning(res.message || '下载失败，请稍后重试')`（写法照 S6-1 站点搜索对同一条 toast 的处理）+ 清转圈 |
 * | `startDownload` 成功 `toast('已提交下载', site + ' · 进度见「下载」页', 'ok')` + `loadTasks(true)` | `t.success('已提交下载')` + `t.info('{site} · 进度见「下载」页')` + 静默 `refreshTasks`（store 已把该任务标成 `pushed`，那一行立刻从待确认里消失） |
 * | 空态 `'<div class="empty">没有待确认的任务</div>'` | `EmptyState`，文案逐字一致 |
 * | `queueMissingThumbs(pend)`（每轮最多补 3 个、补过的番号不再排队） | `common.queueMissingThumbs(api, pending)`，列表每次变化补一轮（补到的图由 `CandTable` 读共享的 `filledThumbs`） |
 * | 轮询：`startTaskPolling()` 每 5 秒 `loadTasks(false)`，靠 `S.view` 是 tasks 或 downloads 判断"只在任务/下载页" | 本视图挂载且 `document.visibilityState === 'visible'` 时每 5 秒 `store.refreshTasks(true)`；**卸载或不可见即停**（与 S6-2 下载页同一套规则） |
 * | 老 `bindUi` 的 nav 点击分支：切到任务/下载栏目立刻 `loadTasks(false)`（静默） | 挂载时补一次静默 `store.refreshTasks(true)`（下载页没补、靠 5 秒轮询兜住；任务页补上是因为待确认列表变化最快，见下面"与 S6-2 的一处不同"） |
 *
 * 与 S6-2 的一处不同（刻意，可回退）：挂载时多发一次静默 `GET plugin/tasks`，对齐老实现
 * 「点左栏立刻 `loadTasks(false)`」那一行；它**不是**右栏概况刷新（见下），失败也不 toast。
 *
 * 刻意**不做**（老实现也没有，别顺手加）：
 * - 不画下载队列：老任务页自从拆出「下载」页以后只剩待确认候选（`renderTasks` 只读 `S.tasks`）；
 * - 不放「🔎 搜索 PT 站」（`ptSearch`）：那颗按钮长在**详情抽屉**里（`ui/views/detail.js`），
 *   任务页从来没有搜种入口；它连带的 `renderPills()` + `loadTasks(true)` 等详情视图迁移时再处理；
 * - 不加错误态组件：老实现读任务失败只有 toast（列表照旧显示，空就是空态），与 S6-2 下载页同一取舍；
 * - 不在动作/轮询里刷右栏「运行概况」：老 `renderPills()` 是**本地计数、不发请求**，右栏本来就由壳的
 *   `/bootstrap` 15 秒轮询负责；这里的角标全由 store 派生（`store.downloading` / `store.tasks`）；
 * - 不按 `auto` / `source` / `state` 二次过滤或排序：老实现按 `S.tasks` 原样顺序画（`pushed` 等非
 *   `await` 任务只是被过滤掉，不另画一行）。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import CandTable from '../common/CandTable.vue'
import EmptyState from '../common/EmptyState.vue'
import { queueMissingThumbs } from '../common/common'
import { hostToast, type PluginApi } from '../../composables/usePluginApi'
import type { PluginStore } from '../../composables/usePluginStore'
import type { SearchTask } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）。 */
    store: PluginStore
    /** 本插件实例 id：给候选表里的封面拼图片代理地址用。 */
    pluginId?: string
    /**
     * 用请求器补封面（`plugin/detail`，经 `common.queueMissingThumbs` 串行发）。
     * 不传时本轮不补图，列表照常显示占位。
     */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null, toast: null },
)

const t = hostToast(props.toast as any)

/** 轮询间隔：与老 `startTaskPolling()` 的 5000ms 一致（后端搜种/下载状态本身就变得慢）。 */
const POLL_MS = 5000

/** 每张候选表的实例：`clearPending(site?)` 由 `CandTable` 通过 `defineExpose` 暴露。 */
const tables = ref<Array<InstanceType<typeof CandTable> | null>>([])

/**
 * 待确认的候选：老 `S.tasks.filter(t => t.state === 'await')`。
 * **只认 `'await'`**（`pushed` / 其它状态一律不画），顺序照 store 原样。
 */
const pending = computed<SearchTask[]>(() => {
  const all = Array.isArray(props.store.tasks.value) ? props.store.tasks.value : []
  return all.filter(item => item.state === 'await')
})

/** 已提交未完成的数量：老 `dling` 的同一条表达式（store 里已有同款派生值，不再自己算一遍）。 */
const submitted = computed(() => Number(props.store.downloading.value) || 0)

/** 行 key：老实现按数组顺序画、没有 key 概念；这里优先用任务 id，保证刷新时行不被重建。 */
function rowKey(task: SearchTask, index: number): string {
  return String(task.id ?? `${task.number || ''}#${index}`)
}

/** 清掉所有候选表的行内 loading（老实现是整块重绘，所有按钮都回到初始态）。 */
function clearAllPending(): void {
  tables.value.forEach(table => table?.clearPending())
}

/**
 * 只清被点的那一行（表内 key 是 `任务id|站点`，每张表按自己的 id 匹配，不会误伤别的行）。
 * 成功失败都要清，否则那一行的按钮永远转圈。
 */
function clearSitePending(site: string): void {
  tables.value.forEach(table => table?.clearPending(site))
}

/**
 * 手动刷新（老 `#btnRefreshTasks`）：先起请求**再**提示，顺序与老实现一致。
 *
 * 这一条走非静默（老实现传的就是 `loadTasks(true)`），失败时给 toast；
 * 后台轮询一律静默，不把界面打成错误态。
 */
async function refreshTasks(): Promise<void> {
  const inflight = props.store.refreshTasks(false)
  t.info('正在刷新…')
  if (!(await inflight)) {
    t.warning(`任务读取失败：${props.store.error.value || '请稍后重试'}`)
  }
  clearAllPending()
}

/** 行内「下载 / 仍要下载」：老 `bindDownloadButtons` → `startDownload(id, site, btn, force)`。 */
async function onDownload(payload: { taskId: string; site: string; force: boolean }): Promise<void> {
  const res = await props.store.startDownload(payload.taskId, payload.site, payload.force)
  if (!res.ok) {
    t.warning(res.message || '下载失败，请稍后重试')
  } else {
    t.success('已提交下载')
    t.info(`${payload.site} · 进度见「下载」页`)
    // 老实现在这里 `loadTasks(true)`：store 已就地标成 `pushed`（那一行消失），再静默对齐一次服务端。
    void props.store.refreshTasks(false)
  }
  clearSitePending(payload.site)
}

/** 每轮列表变化补一轮缺图：老实现是在 `renderTasks` 末尾调一次 `queueMissingThumbs(pend)`。 */
watch(
  pending,
  (items) => {
    if (props.api) queueMissingThumbs(props.api, items)
  },
  { immediate: true },
)

// ---------- 5 秒轮询（只在"本视图挂载 ＋ 页面可见"时跑） ----------

/** `setInterval` 句柄；`null` = 当前没有轮询。 */
let timer: number | null = null

function startPolling(): void {
  if (timer !== null) return
  timer = window.setInterval(() => {
    void props.store.refreshTasks(true)
  }, POLL_MS)
}

function stopPolling(): void {
  if (timer === null) return
  window.clearInterval(timer)
  timer = null
}

/** 切到别的标签页/最小化：立刻停（老实现靠浏览器节流，这里显式停，回来看时 5 秒内自会刷新）。 */
function onVisibilityChange(): void {
  if (document.visibilityState === 'visible') startPolling()
  else stopPolling()
}

onMounted(() => {
  // 老 `bindUi`：点左栏切到任务页时紧跟一次 `loadTasks(false)`（静默，失败不打扰）。
  void props.store.refreshTasks(true)
  if (document.visibilityState === 'visible') startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  // 卸载即停：切到别的栏目（原生视图或 iframe）都不该再打 `/tasks`。
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="avh-tasks">
    <div class="avh-tasks__toolbar">
      <span v-if="submitted" class="avh-tasks__hint">
        ⏬ {{ submitted }} 个已提交，进度看「下载」页
      </span>
      <div class="avh-tasks__spacer" />
      <v-btn variant="outlined" size="small" @click="refreshTasks">↻ 刷新任务</v-btn>
    </div>

    <template v-if="pending.length">
      <div class="avh-tasks__secttl">待确认（{{ pending.length }}）</div>
      <CandTable
        v-for="(task, index) in pending"
        :key="rowKey(task, index)"
        ref="tables"
        :task="task"
        :plugin-id="pluginId"
        @download="onDownload"
      />
    </template>

    <EmptyState v-else text="没有待确认的任务" />
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.toolbar` / `.hint` / `.spacer` */
.avh-tasks__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-tasks__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-tasks__spacer {
  flex: 1;
}

/* 对齐 `.secttl`：12px、弱化色、字距 .4px（`margin-top` 与工具条的 margin-bottom 相叠） */
.avh-tasks__secttl {
  margin: 20px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
</style>
