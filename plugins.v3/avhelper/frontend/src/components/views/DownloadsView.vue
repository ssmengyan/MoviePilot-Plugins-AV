<script setup lang="ts">
/**
 * 视图：下载队列（S6 第二个原生化视图）。
 *
 * 对照老实现 `ui/views/downloads.js`（`renderQueue` / `queueRow` / `queueThumb` /
 * `pumpThumbFill` / `applyThumb` / `queueMissingThumbs`）与它的调用方
 * `ui/views/tasks.js`（`loadTasks` / `startTaskPolling`），逐条对齐的是**行为与文案**，
 * DOM 换成 Vuetify 组件：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | 工具条 `<span class="hint">进度取自下载器，每 5 秒自动刷新</span>` + 右侧 `↻ 刷新进度` | 同一句话、同一个按钮（`variant="outlined"` ≈ 老 `.ghost` 描边） |
 * | `#btnRefreshQueue` → `loadTasks(true)`（**非静默**：失败 toast「任务读取失败」） + `toast('下载队列','正在刷新进度…')` | `store.refreshTasks(false)` + `t.info('正在刷新进度…')`；失败 `t.warning('任务读取失败：{原因}')` |
 * | 行 `queueRow(q)`：`.q > .qhd > (.tposter ＋ 番号/元信息/保存路径) ＋ .right(百分比/状态)` + `.bar` | 同一结构、同一顺序（`.avh-q` / `.avh-q__hd` / `.avh-bar`） |
 * | 元信息 `[site, spec, size].filter(Boolean).join(' · ')`，全空 → `—` | 同 |
 * | 保存路径行 `savePath` ＋（有 `added` 时）` · added`，无条件渲染 | 同（空串也保留那一行） |
 * | 进度 `Math.max(0, Math.min(100, Number(progress) || 0))` → `width:{pct}%` | 同 |
 * | 状态文案 `q.state === 'done' ? '已下载' : '下载中…'`；进度条 `bar.done` 换绿 | 老实现那两句现在只剩「下载中…」（只画在下载中那一节）；完成条目按 §5.3 不再画百分比/状态/进度条，所以 `.bar.done` 那条绿色规则已随之下线 |
 * | 空态 `下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看` | `EmptyState`，文案逐字一致（含 `<br>`；**队列整体为空**时才是它，某一节为空只画一行小字提示） |
 * | 封面 `imgWithPlaceholder(q.thumb,'无图')`；`applyThumb` 补到就地换图 | `common/Thumb.vue`（`variant="tposter"`）＋ `common.queueThumb`／`queueMissingThumbs` 串行补图，**只回填不重绘**（`filledThumbs` 变了只换 `<img>` 的 src） |
 * | `queueMissingThumbs(S.queue)`（每轮最多 3 个、补过的番号不再排队） | 同（`common.queueMissingThumbs`），队列每次变化补一轮 |
 * | 轮询：`startTaskPolling()` 每 5 秒 `loadTasks(false)`，靠 `S.view` 是 tasks 或 downloads 判断"只在任务/下载页" | 本视图挂载且 `document.visibilityState === 'visible'` 时每 5 秒 `store.refreshTasks(true)`；**卸载或不可见即停**（不会在别的栏目里偷偷轮询） |
 *
 * **按 `state` 拆节（下载历史契约 §5.3）**：
 * 队列只剩两类要画的 —— 「下载中」（`state !== 'done' && state !== 'failed'`：封面/进度/百分比）
 * 与「下载失败」（`state === 'failed'`：红色徽标 + 失败原因，没有进度条）。
 *
 * **2026-10-15 起「已完成」整节删除**（用户明确要求）：条目一变 `done` 后端就把它写进台账
 * 并**从队列摘掉**，所以那一节按设计就该是空的；以前留着它只为兼容旧快照与刷新间隙，
 * 结果是一屏里同一件事说两遍（页签 + 小节标题 + 一节永远为空的列表）。完成清单的权威位置
 * 就是同一栏的「下载历史」页签。
 *
 * **2026-10-12 起本栏分两个页签（用户要求的"下载历史与下载界面融合"）**：
 * 「下载中」= 上面这套（队列 + 旧快照的完成节），「下载历史」= 原第七栏 `HistoryView`
 * （插件下载过的番号台账，见 `docs/AVHelper-下载历史设计.md`）。两件事本来就同源
 * （历史 = 队列里完成的那些），合成一栏后左栏省下一格给新的「已入库的番号」。
 * 两条与之配套的规矩：
 * - **历史页签一旦打开就留在 DOM 里**（`v-show` 而不是 `v-if`）：用户可能在那里搜索/看
 *   「只看不在库」，切回下载中再切回来不该把筛选和滚动位置清掉；
 * - **只在「下载中」页签里轮询**：5 秒一次的进度轮询是为进度条服务的，看历史时白打
 *   `/tasks` 没有意义（`syncPolling()`）。
 *
 * **v4 刮削线（0.7.0）在本栏加的两样**（都在「下载中」页签里，`QueueItem` 之外的字段全部可选读）：
 * - **「下载失败」独立一节**（v4.1 §9.2-1，主统筹点名要画）：`state === 'failed'` 的行
 *   既不是"下载中"（画 0% 进度条会让人以为还在下）也不是"已完成"，所以单开一节：
 *   红色描边 + `下载失败` 徽标 + `失败原因：{failed_reason}`（悬浮也给全文），**没有进度条**；
 * - **版本角标**（v4.1 §9.2-6）：行卡片右上角画 `中字` / `流出` / `4K` / `2版本`
 *   （数据来自 `badge` 或 `version_tags`，与 `LibraryView` 同一口径；**缺字段整颗不渲染**）。
 *
 * 刻意**不做**（老实现也没有，别顺手加）：
 * - 没有行内动作（取消下载 / 重试 / 打开目录）：老下载页只有 `↻ 刷新进度` 一个按钮；
 * - 不渲染 `item.category` / `item.hash` / `item.downloader` / `item.id`：老 `queueRow` 没用它们；
 * - 不在节内重排：两节各自的顺序仍是 `S.queue` 的原样顺序（老实现不过滤，这里只按 `state` 一刀切）；
 * - 不在轮询里刷右栏「运行概况」：老 `loadTasks` 只重画自己（`renderPills` 是本地计数、不发请求），
 *   右栏本来就由壳的 `/bootstrap` 15 秒轮询负责。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import Thumb from '../common/Thumb.vue'
import HistoryView from './HistoryView.vue'
import { filledThumbs, queueMissingThumbs } from '../common/common'
import { pushBottomToast } from '../../composables/bottomToast'
import { useHostConfirm } from '../../composables/useHostDialogs'
import { hostToast, type PluginApi } from '../../composables/usePluginApi'
import type { PluginStore } from '../../composables/usePluginStore'
import type { QueueItem } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）。 */
    store: PluginStore
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /**
     * 用请求器补封面（`plugin/detail`，经 `common.queueThumb` 串行发）。
     * 不传时本轮不补图，列表照常显示占位。
     */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null },
)

const t = hostToast(props.toast as any)

/**
 * 宿主要求复用的确认弹窗；拿不到注入时 `useHostConfirm` 内部降级 `window.confirm`。
 *
 * 取消下载会**连磁盘上已下载的部分文件一起删**，属破坏性动作，必须过这道闸
 * （与历史页「移除记录」、订阅页「取消」同一道闸）。
 */
const confirm = useHostConfirm()

/**
 * 行内动作的 in-flight（按行 id 记）。
 *
 * 纪律与 0.6.2 的任务页下载按钮**完全一致**（见 `AGENTS.md` §5 那条硬口径）：
 * 1. 连点几行的按钮互不阻塞（各自等各自的结论），只有同一行重复触发才合并；
 * 2. 行内转圈**只由这一行自己的结论结束** —— 成功就随行消失/变形，失败才由这里解下来；
 * 3. 兜底看门狗：超过 `WATCHDOG_MS` 还没有结论（宿主那条请求挂了又没超时）只解这一行。
 * `key` = `<动作>:<行id>`，动作有 `cancel` / `return` / `discard` / `drop`。
 */
const pending = ref<Record<string, boolean>>({})
/** 看门狗窗口：与 `CandTable` 同一口径（3 分钟）。 */
const WATCHDOG_MS = 180_000

function pendingKey(action: string, item: QueueItem): string {
  return `${action}:${String(item.id || item.hash || item.number || '')}`
}

function isPending(action: string, item: QueueItem): boolean {
  return !!pending.value[pendingKey(action, item)]
}

/** 起一个行内动作：置转圈 + 看门狗；`run` 返回后按需自动解下来（成功由数据变化带走）。 */
function withRowPending(action: string, item: QueueItem, run: () => Promise<boolean>): void {
  const key = pendingKey(action, item)
  if (pending.value[key]) return
  pending.value = { ...pending.value, [key]: true }
  const clear = () => {
    if (!pending.value[key]) return
    const next = { ...pending.value }
    delete next[key]
    pending.value = next
  }
  window.setTimeout(clear, WATCHDOG_MS)
  void run().finally(clear)
}

/** 这一行是不是「已经取消」（后端 `state='canceled'`，行留在原位等用户选出口）。 */
function isCanceled(item: QueueItem): boolean {
  return item.state === 'canceled'
}

/** 轮询间隔：与老 `startTaskPolling()` 的 5000ms 一致（下载器进度本身就更新得慢）。 */
const POLL_MS = 5000

/**
 * 页签（2026-10-12 融合）：`active` = 下载中（老下载页那套），`history` = 下载历史台账。
 *
 * 两个页签的**数据源完全不同**：前者是 store 里的 `/tasks` 队列（5 秒轮询），
 * 后者自己调 `GET plugin/downloads`（`HistoryView` 内部负责，挂载时读一次）。
 */
type TabKey = 'active' | 'history'
/** 页签文案（顺序固定：「下载中」在前，用户进这一栏首先是看进度）。 */
const TABS: { key: TabKey; name: string }[] = [
  { key: 'active', name: '下载中' },
  { key: 'history', name: '下载历史' },
]
const tab = ref<TabKey>('active')
/**
 * 历史页签挂载过没有。
 *
 * 用"挂载过就一直留着（`v-show` 隐藏）"而不是每次切回去都重建：用户在历史页里可能已经
 * 搜了番号、开了「只看不在库」，切走再切回来把筛选清掉属于无谓的打扰。代价只是历史页的
 * DOM 留着不销毁（一张表，可忽略）。
 */
const historyMounted = ref(false)

function pickTab(key: TabKey): void {
  tab.value = key
  if (key === 'history') historyMounted.value = true
}

/** 队列原样取（老实现直接 `S.queue.map(queueRow)`，不过滤、不排序）。 */
const rows = computed<QueueItem[]>(() =>
  Array.isArray(props.store.queue.value) ? props.store.queue.value : [],
)

/**
 * 队列项之外**可选读**的字段（后端 `_film_extra()` / `_merge_queue()` 什么时候给了就能用）。
 *
 * 队列条目的必给键只有
 * `id/number/thumb/site/spec/size/hash/downloader/category/savePath/state/progress/added`；
 * 所以这里一律按可选读：拿不到就**不画那一行**，绝不编造结论（例如"不在库"）。
 *
 * 「已完成」那一节 2026-10-15 已按用户要求整节删除（条目一变 `done` 就被后端写进台账并摘队列，
 * 留着只是同一件事在两处说），所以这个类型现在只服务**失败行**。
 */
type RowExtra = QueueItem & {
  /** 片名（读侧统一投影给的 `title`；队列行拿不到时不画）。 */
  title?: string
  /** 下载速度（`12.3 MB` 这类可读串，后端从下载器读数里抄的）。 */
  speed?: string
  /** 剩余时间（`8m` 这类可读串）。 */
  eta?: string
  /** 取消时间与那一步的说明（`state === 'canceled'` 时后端记的）。 */
  canceled_at?: string
  canceled_detail?: string
  /** 失败原因（`state === 'failed'` 时后端记的那个字段）。 */
  failed_reason?: string
  failedReason?: string
  /** 版本角标数据（后端没有这两个字段时什么都不画）。 */
  version_tags?: unknown
  versionTags?: unknown
  badge?: string
  version_count?: number
}

/** 完成判定就是 `state === 'done'`（老实现同款，不认别的字符串）。 */
function isDone(item: QueueItem): boolean {
  return item.state === 'done'
}

/**
 * 失败判定：`state === 'failed'`（v4.1 §9.2-1 要求后端把 qB 的 error/missingFiles/unknown
 * 落成这个状态并记 `failed_reason`；主统筹 2026-10-14 明确"必须画出来"）。
 *
 * 为什么单开一节：它既不是"下载中"（画进度条会给 0% 的假象），也不是"已完成"
 * —— 混进任一边都会让用户误判这一条到底成没成。
 */
function isFailed(item: QueueItem): boolean {
  return item.state === 'failed'
}

/**
 * 「下载中」：还没完成、也还没失败、**也还没被取消**。
 *
 * `canceled` 单独成节（见 `canceledRows`）：它的种子已经被删掉了，画进度条与百分比是假的；
 * 但**行不消失**（用户要求"保留在原位置"），所以它必须有自己的一节来承载那三个出口。
 */
const activeRows = computed<QueueItem[]>(() =>
  rows.value.filter(item => !isDone(item) && !isFailed(item) && !isCanceled(item)),
)

/** 「已取消」：行留在原位，等用户选「换资源」或「不要了」。 */
const canceledRows = computed<RowExtra[]>(() =>
  rows.value.filter(item => isCanceled(item)) as RowExtra[],
)

/** 「失败」：`state === 'failed'`，红色徽标 + 悬浮/正文给出 `failed_reason`。 */
const failedRows = computed<RowExtra[]>(() => rows.value.filter(item => isFailed(item)) as RowExtra[])

/** 失败原因（两种写法都认；都没有就写「原因未知」，不编造）。 */
function failReasonOf(item: RowExtra): string {
  return String(item.failed_reason || item.failedReason || '').trim() || '原因未知'
}

/**
 * 速度与剩余时间那一段：`12.3 MB/s · 剩余 8m`（两段各自可有可无；都没有返回空串）。
 *
 * 数据来自后端 `_merge_queue()` 从下载器读数里抄下来的 `speed` / `eta`
 * （宿主的 `DownloaderTorrent.dlspeed` / `left_time`，已经是可读串）。
 * **没有就不画** —— 宁可退回「下载中…」，也不编一个"0 B/s"出来。
 */
function speedOf(item: RowExtra): string {
  const row = item as unknown as Record<string, any>
  const speed = String(row.speed || '').trim()
  const eta = String(row.eta || '').trim()
  const parts: string[] = []
  if (speed && speed !== '0 B') parts.push(/\/s$/i.test(speed) ? speed : `${speed}/s`)
  if (eta) parts.push(`剩余 ${eta}`)
  return parts.join(' · ')
}

/** 是否画版本角标（`badge` / `version_tags` 任一有值；老后端两个都没有 → false）。 */
function hasBadge(item: QueueItem): boolean {
  return !!versionBadgeOf(item)
}

/**
 * 版本角标（v4.1 §9.2 第 6 条）：与 `LibraryView` 同一口径（那份在卡片网格里，这份在行卡片上）。
 * 数据来自 `badge`（优先）或 `version_tags`（数组 / 字典）；**缺字段时返回空串、什么都不画**。
 */
function versionBadgeOf(item: QueueItem): string {
  const row = item as unknown as Record<string, any>
  const direct = String(row.badge ?? '').trim()
  const labels: string[] = []
  const push = (value: unknown) => {
    const label = String(value ?? '').trim()
    if (label && !labels.includes(label)) labels.push(label)
  }
  if (!direct) {
    const tags = row.version_tags ?? row.versionTags
    if (Array.isArray(tags)) tags.forEach(push)
    else if (tags && typeof tags === 'object') {
      const dict = tags as Record<string, any>
      if (dict.is_zh_sub) push('中字')
      if (dict.is_uncensored_leak) push('流出')
      const resolution = String(dict.resolution ?? '').trim()
      if (resolution) push(/2160|4k/i.test(resolution) ? '4K' : resolution.toUpperCase())
      if (dict.is_iso) push('ISO')
      if (dict.is_vr) push('VR')
      if (dict.part_no) push(String(dict.part_no))
      if (dict.edition) push(String(dict.edition))
    }
  }
  const merged = [direct, labels.join('/')].filter(Boolean).join(' ')
  const count = Number(row.version_count ?? row.versions ?? 0)
  if (count > 1) return merged ? `${merged} ${count}版本` : `${count}版本`
  return merged
}

/** 进度百分比：老实现 `Math.max(0, Math.min(100, Number(q.progress) || 0))`（NaN 也归 0）。 */
function progressOf(item: QueueItem): number {
  return Math.max(0, Math.min(100, Number(item.progress) || 0))
}

/** `站点 · 规格 · 大小`，全缺省时显示 `—`（老实现 `meta || '—'`）。 */
function metaOf(item: QueueItem): string {
  return [item.site, item.spec, item.size].filter(Boolean).join(' · ') || '—'
}

/** 保存路径 ＋（有 `added` 时）` · 加入时间`；老实现无条件渲染这一行，空串也占位。 */
function pathOf(item: QueueItem): string {
  return String(item.savePath || '') + (item.added ? ` · ${item.added}` : '')
}

/** 行 key：老实现按数组顺序画、没有 key 概念；这里优先用队列里唯一的 hash / id。 */
function rowKey(item: QueueItem, index: number): string {
  return String(item.hash || item.id || `${item.number || ''}#${index}`)
}

/**
 * 封面地址：优先队列项自带（后端 `image_url()` 通常给的是插件代理地址），
 * 其次是 `common.queueThumb` 补回来的结果——两者都改 `:src`，**不重建整块列表**，
 * 免得用户正看着的进度条/滚动位置被打回去（老 `applyThumb` 的同一纪律）。
 */
function thumbOf(item: QueueItem): string {
  return String(item.thumb || filledThumbs.value[String(item.number || '')] || '')
}

/** 这一行的显示名（番号优先，其次片名/种子站点，最后兜底）。 */
function labelOf(item: QueueItem): string {
  return String(item.number || (item as RowExtra).title || item.site || '这条下载')
}

/**
 * 「取消下载」：删下载器里的种子（**含已下载的部分文件**）→ 行变「已取消」留在原位。
 *
 * 三件事按顺序：
 * 1. 宿主确认弹窗写清"会删掉已经下好的部分"，别让用户在不知情的情况下丢文件；
 * 2. `store.cancelDownload(id)`（闸门 `qcancel:<id>`，按行并发）；
 * 3. **成功不摘行**：后端把这一行标成 `canceled` 并回一份新队列，界面自会把它挪到
 *    「已取消」那一节 —— 前端不自己动手，免得与后端那份快照打架。
 */
async function cancelDownload(item: QueueItem): Promise<void> {
  const label = labelOf(item)
  const ok = await confirm({
    type: 'warn',
    title: '取消下载',
    content: `将从下载器删除「${label}」的下载任务，并删除已下载的部分文件。`
      + `条目会留在原位，之后可以「换资源」重新挑一个，或者「不要了」彻底取消。`,
    confirmText: '取消下载',
    cancelText: '先留着',
  })
  if (!ok) return
  withRowPending('cancel', item, async () => {
    const res = await props.store.cancelDownload(String(item.id || ''))
    if (res.ok) {
      pushBottomToast('success', res.message || `已取消 ${label}`)
      return true
    }
    pushBottomToast('warning', `取消失败：${res.message || '请稍后重试'}`)
    return false
  })
}

/**
 * 「换资源」：把这条下载摘掉，并让它对应的任务回到「任务」页待确认。
 *
 * 后端的口径是"任务置回 await、候选原样保留"，所以点完去任务页就能挑别的种子，
 * 不必重搜站点（重搜要走限流、还慢）。
 */
async function returnDownload(item: QueueItem): Promise<void> {
  const label = labelOf(item)
  withRowPending('return', item, async () => {
    const res = await props.store.returnDownload(String(item.id || ''))
    if (res.ok) {
      pushBottomToast('success', res.message || `已把 ${label} 放回任务列表`)
      return true
    }
    pushBottomToast('warning', `操作失败：${res.message || '请稍后重试'}`)
    return false
  })
}

/**
 * 「不要了」：彻底取消 —— 摘行 + 台账墓碑 + 任务取消 +（默认）取消该番号的订阅。
 *
 * 勾选框默认**勾上**：不取消订阅的话，下一次订阅检查还会把同一个番号重新搜出来落成任务，
 * "不要了"就成了假话（后端 `cancel_all` 会给 `known` 写一条忽略记录兜底）。
 */
async function discardDownload(item: QueueItem): Promise<void> {
  const label = labelOf(item)
  const ok = await confirm({
    type: 'warn',
    title: '不要了',
    content: `「${label}」会从下载列表移除，下载历史里也不再保留这条记录。`
      + `如果它有番号订阅，会一并取消，以后不会再自动下载。`,
    confirmText: '不要了',
    cancelText: '先留着',
  })
  if (!ok) return
  withRowPending('discard', item, async () => {
    const res = await props.store.discardDownload(String(item.id || ''), true)
    if (res.ok) {
      pushBottomToast('success', res.message || `已彻底取消 ${label}`)
      return true
    }
    pushBottomToast('warning', `取消失败：${res.message || '请稍后重试'}`)
    return false
  })
}

/** 「移除」：只把这条已经取消的灰行从列表去掉（不动下载器、不动台账）。 */
async function dropCanceledRow(item: QueueItem): Promise<void> {
  withRowPending('drop', item, async () => {
    const res = await props.store.dropDownloadRow(String(item.id || ''))
    if (res.ok) return true
    pushBottomToast('warning', `移除失败：${res.message || '请稍后重试'}`)
    return false
  })
}

/**
 * 手动刷新（老 `#btnRefreshQueue`）：先起请求**再**提示，顺序与老实现一致。
 *
 * 这一条走非静默（老实现传的就是 `loadTasks(true)`），失败时给 toast；
 * 后台轮询则一律静默，不把界面打成错误态。
 */
async function refreshQueue(): Promise<void> {
  const inflight = props.store.refreshTasks(false)
  t.info('正在刷新进度…')
  if (!(await inflight)) {
    t.warning(`任务读取失败：${props.store.error.value || '请稍后重试'}`)
  }
}

/** 每轮列表变化补一轮缺图：老实现是在 `renderQueue` 末尾调一次 `queueMissingThumbs(S.queue)`。 */
watch(
  rows,
  (items) => {
    if (props.api) queueMissingThumbs(props.api, items)
  },
  { immediate: true },
)

// ---------- 5 秒轮询（只在"下载中页签 ＋ 本视图挂载 ＋ 页面可见"时跑） ----------

/** `setInterval` 句柄；`null` = 当前没有轮询。 */
let timer: number | null = null

/** 该不该轮询：进度条只在「下载中」页签里，看历史时不必白打 `/tasks`。 */
function shouldPoll(): boolean {
  return tab.value === 'active' && document.visibilityState === 'visible'
}

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

/** 按当前页签 + 可见性起停轮询（挂载、切页签、切前后台都走它）。 */
function syncPolling(): void {
  if (shouldPoll()) startPolling()
  else stopPolling()
}

/** 切到别的标签页/最小化：立刻停（老实现靠浏览器节流，这里显式停，回来看时 5 秒内自会刷新）。 */
function onVisibilityChange(): void {
  syncPolling()
}

/** 切页签：进「下载中」补一次最新进度（可能已经在历史页停了几分钟），再同步起停。 */
watch(tab, (key) => {
  if (key === 'active') void props.store.refreshTasks(true)
  syncPolling()
})

onMounted(() => {
  syncPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  // 卸载即停：切到别的栏目（原生视图或 iframe）都不该再打 `/tasks`。
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="avh-downloads">
    <div class="avh-downloads__toolbar">
      <!--
        两个页签（2026-10-12）：胶囊样式与发现榜单那组 tabs 同一套（`.avh-tabs`），
        选中那颗走主色。括号里是计数：「下载中」拿队列现成数，「下载历史」不画数字
        —— 台账由 `HistoryView` 自己读，这一层不去替它猜（猜错比不画更糟）。
      -->
      <div class="avh-tabs">
        <button
          v-for="item in TABS"
          :key="item.key"
          :class="{ 'avh-tabs__on': item.key === tab }"
          @click="pickTab(item.key)"
        >{{ item.name }}<template v-if="item.key === 'active'">（{{ activeRows.length }}）</template></button>
      </div>

      <!--
        顶部**不画任何说明句**（用户 2026-10-15 明确要求）：「进度取自下载器，每 5 秒自动刷新」
        这类话既不专业也占位置，工具条只留"数据 + 操作"。同理历史页与库页的那两句也一并删了。
      -->
      <div class="avh-downloads__spacer" />

      <v-btn v-if="tab === 'active'" variant="outlined" size="small" @click="refreshQueue">↻ 刷新进度</v-btn>
    </div>

    <!--
      ===== 下载中（老下载页那套） =====
    -->
    <template v-if="tab === 'active'">
      <template v-if="rows.length">
        <!--
          「下载中」直接开画，**不再画小节标题**（用户 2026-10-15）：
          页签那颗胶囊里已经有 `下载中（N）`，下面再来一行"下载中（N）"是同一屏同一份计数说两遍。
        -->
        <template v-if="activeRows.length">
          <div
            v-for="(item, index) in activeRows"
            :key="rowKey(item, index)"
            class="avh-q"
            :class="{ 'avh-q--vtag': hasBadge(item) }"
          >
            <!-- 版本角标（v4.1 §9.2-6）：卡片右上角；没有 version_tags / badge 就整颗不渲染 -->
            <span v-if="hasBadge(item)" class="avh-vbadge">{{ versionBadgeOf(item) }}</span>
            <div class="avh-q__hd">
              <Thumb
                class="avh-q__poster"
                variant="tposter"
                :src="thumbOf(item)"
                alt="无图"
                :plugin-id="pluginId"
              />
              <div class="avh-q__main">
                <div class="avh-q__no">{{ item.number || '' }}</div>
                <!--
                  影片标题（读侧统一投影给的 `title`，2026-10-15 加）：同一部片在榜单/历史/
                  库页显示的都是它，下载页以前只有番号 —— 那正是"四个界面五花八门"的一处。
                  拿不到（投影里没这部片）就整行不画，不拿种子名顶上。
                -->
                <div v-if="item.title" class="avh-q__ttl">{{ item.title }}</div>
                <div class="avh-q__hint avh-q__meta">{{ metaOf(item) }}</div>
                <div class="avh-q__hint avh-q__path">{{ pathOf(item) }}</div>
              </div>
              <div class="avh-q__right">
                <div class="avh-q__no">{{ progressOf(item) }}%</div>
                <!-- 速度与剩余时间（后端从下载器读的 `dlspeed`/`left_time`；没有就退回状态文案） -->
                <div v-if="speedOf(item)" class="avh-q__hint">{{ speedOf(item) }}</div>
                <div v-else class="avh-q__hint">下载中…</div>
                <!-- 行内「取消下载」（2026-10-15）：删种子（含已下载的部分文件）→ 行留在原位变灰 -->
                <v-btn
                  class="avh-q__act"
                  variant="text"
                  size="x-small"
                  color="error"
                  :loading="isPending('cancel', item)"
                  @click="cancelDownload(item)"
                >取消下载</v-btn>
              </div>
            </div>
            <div class="avh-bar">
              <i :style="{ width: `${progressOf(item)}%` }" />
            </div>
          </div>
        </template>
        <!-- 一节为空只给一行小字（整体为空的 `EmptyState` 在下面），别把一个空态画两遍 -->
        <div v-else class="avh-downloads__hint">没有下载中的任务</div>

        <!--
          ===== 下载失败（v4.1 §9.2-1，2026-10-14 主统筹点名要画）=====
          `state === 'failed'`（qB 的 error / missingFiles / unknown 被后端如实落成这个状态）：
          **没有进度条、没有百分比**（画 0% 会让人以为还在下），红色徽标 + `failed_reason`。
        -->
        <div v-if="failedRows.length" class="avh-downloads__secttl">
          <span>下载失败（{{ failedRows.length }}）</span>
          <span class="avh-downloads__secttl-note">在「任务」页可重新挑种下载</span>
        </div>

        <template v-if="failedRows.length">
          <div
            v-for="(item, index) in failedRows"
            :key="rowKey(item, index)"
            class="avh-q avh-q--failed"
            :class="{ 'avh-q--vtag': hasBadge(item) }"
          >
            <span v-if="hasBadge(item)" class="avh-vbadge">{{ versionBadgeOf(item) }}</span>
            <div class="avh-q__hd">
              <Thumb
                class="avh-q__poster"
                variant="tposter"
                :src="thumbOf(item)"
                alt="无图"
                :plugin-id="pluginId"
              />
              <div class="avh-q__main">
                <div class="avh-q__no">
                  {{ item.number || '' }}
                  <v-chip size="x-small" color="error" variant="tonal" class="ms-1">下载失败</v-chip>
                </div>
                <div v-if="item.title" class="avh-q__ttl">{{ item.title }}</div>
                <div class="avh-q__hint avh-q__meta">{{ metaOf(item) }}</div>
                <div class="avh-q__hint avh-q__path" :title="failReasonOf(item)">
                  失败原因：{{ failReasonOf(item) }}
                </div>
              </div>
            </div>
          </div>
        </template>

        <!--
          ===== 已取消（2026-10-15 新增，用户明确要求）=====
          用户点「取消下载」之后，种子已经从下载器删掉，但**行不消失**（"条目不要立即消失，
          应保留在原位置"）—— 留在这里等用户选出口，避免"点错了只能重来"：

          - 换资源：摘掉这一行 + 把任务放回「任务」页待确认（候选原样保留，挑别的种子）
          - 不要了：彻底取消（摘行 + 台账墓碑 + 任务取消 + 默认连番号订阅一起取消）
          - 移除：只把这条灰行从列表去掉（不动下载器、不改台账）

          没有进度条也没有百分比：种子已经不在下载器里了，画 0% 是骗人。
        -->
        <template v-if="canceledRows.length">
          <div class="avh-downloads__secttl">
            <span>已取消（{{ canceledRows.length }}）</span>
            <span class="avh-downloads__secttl-note">选「换资源」重新挑，或「不要了」彻底取消</span>
          </div>

          <div
            v-for="(item, index) in canceledRows"
            :key="rowKey(item, index)"
            class="avh-q avh-q--canceled"
            :class="{ 'avh-q--vtag': hasBadge(item) }"
          >
            <span v-if="hasBadge(item)" class="avh-vbadge">{{ versionBadgeOf(item) }}</span>
            <div class="avh-q__hd">
              <Thumb
                class="avh-q__poster"
                variant="tposter"
                :src="thumbOf(item)"
                alt="无图"
                :plugin-id="pluginId"
              />
              <div class="avh-q__main">
                <div class="avh-q__no">
                  {{ item.number || '' }}
                  <v-chip size="x-small" variant="tonal" class="ms-1">已取消</v-chip>
                </div>
                <div v-if="item.title" class="avh-q__ttl">{{ item.title }}</div>
                <div class="avh-q__hint avh-q__meta">{{ metaOf(item) }}</div>
                <div class="avh-q__hint avh-q__path" :title="String(item.canceled_detail || '')">
                  {{ item.canceled_detail || pathOf(item) }}
                </div>
              </div>
            </div>
            <div class="avh-q__exits">
              <v-btn
                variant="tonal"
                size="small"
                :loading="isPending('return', item)"
                @click="returnDownload(item)"
              >换资源</v-btn>
              <v-btn
                variant="text"
                size="small"
                color="error"
                :loading="isPending('discard', item)"
                @click="discardDownload(item)"
              >不要了</v-btn>
              <v-btn
                variant="text"
                size="small"
                :loading="isPending('drop', item)"
                @click="dropCanceledRow(item)"
              >移除</v-btn>
            </div>
          </div>
        </template>
      </template>

      <!--
        队列整体为空时的空态：**只留指路**（2026-10-15 精简）。
        完成条目会被后端写进台账并**从队列摘掉**，所以"没有任何下载在进行"时这一页永远是空的
        —— 不告诉用户"完成的在下载历史里"，那个页签就等于藏起来了，所以第三句保留。
      -->
      <EmptyState v-else text="下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看<br>完成的下载在「下载历史」页签" />
    </template>

    <!--
      ===== 下载历史（原数据台第七栏，2026-10-12 并进本栏） =====
      `historyMounted` 之后一直留着（`v-show` 隐藏），切回来筛选与滚动位置都还在。
    -->
    <HistoryView
      v-if="historyMounted"
      v-show="tab === 'history'"
      :api="props.api"
      :plugin-id="props.pluginId"
      :toast="props.toast"
    />
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.toolbar` / `.hint` / `.spacer` */
.avh-downloads__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-downloads__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-downloads__spacer {
  flex: 1;
}

/* 页签：与发现榜单那组 tabs 同一套几何（胶囊容器 + 选中那颗走主色，写法照 `DiscoverView`）。
   两份 scoped CSS 各有各的作用域，抄这一小段比抽公共件划算（本项目的既有做法）。 */
.avh-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-tabs button {
  padding: 4px 12px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  background: none;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.avh-tabs__on {
  color: rgb(var(--v-theme-on-primary)) !important;
  background: rgb(var(--v-theme-primary)) !important;
}

/* 对齐 `app.css` 的 `.secttl`：12px、弱化色、字距 .4px（与 `TasksView` 的小标题同一套口径） */
.avh-downloads__secttl {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 20px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 小节标题右侧那句指路（契约 §5.3）：靠右、不参与标题的字距，免得挤成标题的一部分 */
.avh-downloads__secttl-note {
  margin-left: auto;
  letter-spacing: 0;
}

/* 对齐 `.q`：卡片底色 + 描边 + 10px 圆角。
   `position: relative` 是给右上角的版本角标（v4.1 §9.2-6）做定位锚点。 */
.avh-q {
  position: relative;
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

/* 失败行：描边与底色走 error 通道（与"下载中""已完成"一眼分得开） */
.avh-q--failed {
  border-color: rgba(var(--v-theme-error), 0.4);
  background: rgba(var(--v-theme-error), 0.08);
}

/* 版本角标（v4.1 §9.2-6）：贴在卡片右上角；没有 version_tags / badge 时整颗不渲染 */
.avh-vbadge {
  position: absolute;
  top: 8px;
  right: 10px;
  z-index: 1;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.6;
  border-radius: 4px;
  color: #fff;
  background: rgba(var(--v-theme-secondary), 0.9);
  border: 1px solid rgba(255, 255, 255, 0.14);
  pointer-events: none;
}

/* 有角标时把右侧那一列（百分比 / 「下载中…」）压下一行，两者不叠在一起 */
.avh-q--vtag .avh-q__right {
  padding-top: 20px;
}

/*
 * 已取消行（2026-10-15）：整行压暗一档，与「下载中」一眼分得开。
 * 不用禁用态灰（那看着像坏掉了），只把底色与描边收淡 —— 它仍然是一张"可操作"的卡
 * （下面那三个出口等着用户点）。
 */
.avh-q--canceled {
  background: rgba(var(--v-theme-on-surface), 0.02);
  border-style: dashed;
}

/* 行内动作按钮（「取消下载」）：贴着百分比右下，不与进度条抢注意力 */
.avh-q__act {
  margin-top: 2px;
  padding: 0 4px;
  min-width: 0;
  font-size: 11.5px;
}

/* 已取消行的三个出口：左对齐一排，右留一点空隙免得贴着卡片边 */
.avh-q__exits {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding-left: 60px;      /* 与封面右侧的正文对齐（48px 封面 + 12px gap） */
}

/* 对齐 `.qhd` */
.avh-q__hd {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

/* 对齐 `.tposter`：48×64 小封面 */
.avh-q__poster {
  width: 48px;
  height: 64px;
  flex: none;
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

/* 老实现的内联 `flex:1;min-width:0` */
.avh-q__main {
  flex: 1;
  min-width: 0;
}

/* 对齐 `.qhd .qn` */
.avh-q__no {
  font-size: 14px;
  font-weight: 600;
}

.avh-q__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-q__meta {
  margin-top: 3px;
}

.avh-q__path {
  margin-top: 2px;
}

/* 完成行的片名（台账可选字段，见 `DoneRow` 注释）：比 `.hint` 稍亮一档，读起来像"一行记录" */
.avh-q__ttl {
  margin-top: 3px;
  font-size: 12.5px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

/* 对齐 `.qhd .right` */
.avh-q__right {
  margin-left: auto;
  text-align: right;
  white-space: nowrap;
}

/* 对齐 `.bar` / `.bar i`（老实现是 --acc2 → --acc 的渐变）
   只有「下载中」那一节画进度条：完成行是静态历史行，契约 §5.3 明确要去掉进度，
   所以老实现的 `.bar.done i` 换绿那条规则已随之下线（没有使用者了）。 */
.avh-bar {
  height: 7px;
  border-radius: 99px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.12);
}

.avh-bar i {
  display: block;
  width: 0;
  height: 100%;
  transition: width 0.3s;
  background: linear-gradient(
    90deg,
    rgba(var(--v-theme-primary), 0.6),
    rgb(var(--v-theme-primary))
  );
}
</style>
