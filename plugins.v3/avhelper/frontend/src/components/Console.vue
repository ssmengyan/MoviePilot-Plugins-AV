<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import AppFrame from './AppFrame.vue'
import { DEFAULT_MAX_WIDTH, type ConfigProps } from './contract'
import { CONSOLE_EMIT_NAMES } from './emitContract'
import {
  bindPluginApi,
  hostToast,
  type PluginApi,
  type PluginConfig,
} from '../composables/usePluginApi'
import { useRuntimeInfo } from '../composables/useRuntimeInfo'
import { useSettingsDraft, type RuleState } from '../composables/useSettingsDraft'
import { useHostConfirm } from '../composables/useHostDialogs'
import { SETTINGS_SECTIONS, type SectionItem } from './settings/panels'
import GeneralPanel from './settings/GeneralPanel.vue'
import SitesPanel from './settings/SitesPanel.vue'
import RulePanel from './settings/RulePanel.vue'
import NotifyPanel from './settings/NotifyPanel.vue'
import LibraryPanel from './settings/LibraryPanel.vue'
import RuntimePanel from './settings/RuntimePanel.vue'
import AboutPanel from './settings/AboutPanel.vue'
import SiteSearchView from './views/SiteSearchView.vue'
import DownloadsView from './views/DownloadsView.vue'
import TasksView from './views/TasksView.vue'
import SubsView from './views/SubsView.vue'
import ActorsView from './views/ActorsView.vue'
import DiscoverView from './views/DiscoverView.vue'
import DetailDrawer from './detail/DetailDrawer.vue'
import NotifyDrawer from './detail/NotifyDrawer.vue'
import SearchDialog from './detail/SearchDialog.vue'
import { usePluginStore } from '../composables/usePluginStore'
import { countUnread } from '../composables/noticesSeen'
import { takePendingSettingsSection } from '../composables/settingsJump'

/**
 * 壳只有两种**入口模式**，决定设置窗口的初始开合：
 * - `data`     = 插件详情弹窗（`./Page`）：先看数据台，设置窗口默认关着；
 * - `settings` = 插件配置弹窗（`./Config`）：一进来就把设置窗口打开，数据台仍画在它后面
 *   —— 关掉设置窗口就露出数据台，不再有"关掉设置就整个界面消失"的第三条路。
 */
type ConsoleMode = 'data' | 'settings'

/**
 * props 默认值必须自包含（`defineProps()` 会被提升到 setup 之外，不能引用本地变量）：
 * `api` 的默认值就是一个必然失败的兜底请求器，宿主没传时界面照样画得出来。
 */
const props = withDefaults(defineProps<ConfigProps & { mode?: ConsoleMode }>(), {
  api: () => ({
    get: () => Promise.reject(new Error('宿主 api 不可用')),
    post: () => Promise.reject(new Error('宿主 api 不可用')),
  }),
  pluginId: '',
  sourcePluginId: '',
  nativeSubscribe: null,
  show_switch: true,
  initialConfig: () => ({}),
  mode: 'data',
})

/**
 * 事件必须用**字符串数组**声明（见 `emitContract.ts` 里记的真机根因）：
 * 写成 `defineEmits(consoleEmits())` 会编译出 `emits: <函数>`，Vue 认不出来，
 * 五个事件退化成 fallthrough attrs 后一次点击双发 —— 那正是"设置弹窗叠两层、
 * 关一次关不掉、再关整个界面消失"的来源。
 */
const emit = defineEmits(CONSOLE_EMIT_NAMES)

const DATA_SECTIONS: SectionItem[] = [
  { key: 'discover', title: '发现榜单', icon: 'mdi-chart-line' },
  { key: 'actors', title: '我的演员', icon: 'mdi-account-star' },
  { key: 'subs', title: '订阅', icon: 'mdi-rss' },
  { key: 'tasks', title: '任务', icon: 'mdi-clipboard-list' },
  { key: 'downloads', title: '下载', icon: 'mdi-download' },
  { key: 'sitesearch', title: '站点搜索', icon: 'mdi-magnify' },
]

const pluginId = computed(() => props.pluginId || props.sourcePluginId || '')

/**
 * 数据台**已原生化**的栏目 → 视图组件（S6 增量替换，设计文档 §6.1）。
 *
 * **六栏到这里全部原生化**（2026-10-10，`discover` 是最后一栏）：这张表里没有的栏目
 * 仍由 `AppFrame` 承载被嵌应用（`ui/`），`AppFrame` 从此只作为"设置台之外的回退"保留
 * ——真机上它只在两种情况下出现：这张表被回退式删掉一行，或宿主不认识 `vue` 渲染模式
 * （那时整个联邦组件根本不会加载，`get_page()` 的 iframe 才是退路）。
 *
 * 所有原生视图共用同一组 props（`store` / `pluginId` / `api` / `toast`）；
 * `@switch` / `@refresh-side` / `@open-movie` 也统一绑在 `<component>` 上——没有声明这些
 * 事件的视图只是收不到回调（它们本来就不发），不影响行为。
 */
const NATIVE_VIEWS: Record<string, Component> = {
  discover: DiscoverView,
  sitesearch: SiteSearchView,
  downloads: DownloadsView,
  tasks: TasksView,
  subs: SubsView,
  actors: ActorsView,
}

/** iframe 必须用实例 id（普通插件 = pluginId；分身共享同一份联邦产物）。 */
const framePluginId = computed(() => props.pluginId || props.sourcePluginId || '')

/**
 * 数据台与设置窗口**各存一份栏目**：设置是盖在数据台之上的独立窗口，
 * 关掉它数据台的栏目不该被改动（老实现两个 Console 实例本来就是各存一份）。
 */
const section = ref<string>(DATA_SECTIONS[0]!.key)
const settingsSection = ref<string>(SETTINGS_SECTIONS[0]!.key)
/**
 * 设置窗口开合。
 *
 * 2026-10-11 起设置是**本组件内的独立窗口**（`<v-dialog>`），不再走宿主的
 * Page ⇄ Config 互换 —— 那条路只有一个结局：宿主换弹窗时把数据台一起关掉，
 * 于是"关掉设置"要么停在设置页（叠了两层时），要么整个界面消失（最后一层也关了）。
 */
const settingsOpen = ref(props.mode === 'settings')
const version = ref('')
/** 「清空通知」请求在跑（确认框关闭后到请求结束之间的按钮态）。 */
const noticeClearing = ref(false)

/**
 * 详情抽屉（S6-7）与顶栏搜索（同批）：两者都是**跨栏目**的弹层，所以由壳持有状态，
 * 视图只发事件（`@open-movie` / `@open-actor`）。
 * - `drawerOpen` / `drawerNumber` / `drawerId`：老 `#drawer` 的开关与 `CURSOR.number` / `CURSOR.id`；
 * - `searchOpen` / `query` / `searchDialog`：老 `#qInput` / `#qBtn` 与 `doSearch` 的弹窗；
 * - `actorFocus` / `actorNonce`：老 `openActor(name)` 的落点（切到「我的演员」栏并打开 ta）。
 */
const drawerOpen = ref(false)
/** 抽屉当前番号（老 `CURSOR.number`）：声明式下传，抽屉内部再走 `openMovie` 那套守卫。 */
const drawerNumber = ref('')
/** 抽屉当前 javdb id（老 `CURSOR.id`）：同一部片重开时复用，换片才清。 */
const drawerId = ref('')
const searchOpen = ref(false)
const searchDialog = ref<InstanceType<typeof SearchDialog> | null>(null)
const query = ref('')
const actorFocus = ref('')
const actorNonce = ref(0)

/**
 * 通知抽屉（老 `ui/index.html` 的 `#bellBtn` / `#ndrawer` + `ui/views/notify.js`）：
 * 与详情抽屉、搜索弹窗一样是**跨栏目**的浮层，所以状态同样由壳持有。
 *
 * - 数据源就是数据台的 store（`store.notices`）；`/bootstrap` 每 15s 轮询已经在拉它
 *   （`useRuntimeInfo`），所以这里**不新开轮询、也不额外打 `/notices`**；
 * - 未读角标与设置台「通知」栏共用同一个已读位点
 *   （**键 = `avhnext.settings.noticesSeen`**，见 `composables/noticesSeen.ts`）；
 * - 打开抽屉即 `markNoticesSeen()`（抽屉内部做），角标随位点响应式归零。
 */
const notifyOpen = ref(false)

/**
 * 未读条数（`time` 晚于已读位点的条数）。
 *
 * 数据来源与抽屉一致，都是数据台 store 的 `store.notices`（`/bootstrap` 轮询那份）；
 * 兜底再读一次设置台草稿的 `notices`（设置台挂载时自己 `GET /notices` 拉的同一份数据）
 * ——在 `?dedupe=1` 之前的老宿主行为、或 `/bootstrap` 某轮没带 `notices` 时，
 * 草稿那份更可信。**取两者的较大值**：同一条通知不会被数两次，角标只会少不会多。
 *
 * 写成函数而不是 `computed`：它要读设置台草稿的 `notices`，而那份解构在本行**之后**才发生
 * （模块顶层的 TDZ 会直接抛错）。模板里每次渲染都会重新求值，响应式照样跟得上。
 */
function notifyUnread(): number {
  return Math.max(countUnread(store.notices.value), countUnread(notices.value))
}

/** 打开通知抽屉：老 `openNotify()` 第一件事就是关掉详情抽屉与弹窗（同一时刻只开一层）。 */
function openNotify(): void {
  drawerOpen.value = false
  searchOpen.value = false
  notifyOpen.value = true
}

/**
 * 「清空通知」（通知抽屉那一侧）。抽屉自己已经过了宿主确认，这里直接发请求。
 *
 * 数据源是 store，所以清空走 `store.clearNotices()`；设置台草稿（`draft.notices`）是同一份
 * 数据的另一个副本，清完顺手同步一把，免得切到设置台还看见已经删掉的条目。
 */
async function clearNoticesFromDrawer(): Promise<void> {
  noticeClearing.value = true
  try {
    const result = await store.clearNotices()
    if (!result.ok) {
      toast.warning(result.message || '清空通知失败')
      return
    }
    notices.value = []
    toast.success(result.message || '通知已清空')
    await refreshRuntime()
  } finally {
    noticeClearing.value = false
  }
}

/**
 * 这个 Console 是不是宿主「插件配置」弹窗里那一个（`./Config`，`mode === 'settings'`）。
 *
 * 只影响一件事：宿主配置（`enabled` / `proxy` / …）该由谁 PUT ——
 * 宿主的 `PluginConfigDialog` 自己接了 `save` 事件，而 `PluginDataDialog` 没接（见 `saveHostConfig`）。
 */
const settingsEntry = computed(() => props.mode === 'settings')

/** 设置窗口当前栏目（`settingsSection` 的归一结果；key 不认识时回落第一栏）。 */
const activeSetting = computed<SectionItem>(
  () => SETTINGS_SECTIONS.find(item => item.key === settingsSection.value) || SETTINGS_SECTIONS[0]!,
)

/** 当前栏目有没有原生视图：`null` → 内容区走 iframe（设置台栏目的 key 不在 `NATIVE_VIEWS` 里）。 */
const nativeView = computed<Component | null>(() => NATIVE_VIEWS[section.value] || null)

/** 宿主要求复用的统一 toast（官方指南 §5.8）；拿不到时静默降级，不自建 Toast。 */
const injectedToast = inject<any>('moviepilot:toast', null)
const toast = hostToast(injectedToast)
/** 宿主要求复用的确认弹窗（官方指南 §5.10）；拿不到时降级 `window.confirm`。 */
const confirm = useHostConfirm()

/** 拉不到宿主 api 时的兜底实现：请求立刻失败，走错误分支。 */
const FALLBACK_API: PluginApi = {
  get: () => Promise.reject(new Error('宿主 api 不可用')),
  post: () => Promise.reject(new Error('宿主 api 不可用')),
}

/**
 * 宿主**原始**请求器：只给宿主自己的路由用（`plugin/page/<id>`、`plugin/remotes`、
 * `plugin/form/<id>`）——那些路径不能补插件 id，否则会被当成插件端点而 404/空。
 */
function rawApi(): PluginApi {
  return props.api && typeof props.api.get === 'function' ? props.api : FALLBACK_API
}

/**
 * 插件自身端点的请求器：`bindPluginApi` 给每条 `plugin/<端点>` 补上实例 id。
 *
 * 宿主**不会**替组件补（普通安装下 `source_plugin_id` 为 `null`，垫片原样转发），
 * 少了这一步所有数据接口都会落到 `/api/v1/plugin/<端点>` 的兜底路由上、静默返回空
 * —— 真机症状就是"完全加载不出来数据"（详见 `bindPluginApi` 的说明）。
 *
 * 用 `computed` 是为了**对象标识稳定**：模板里 `:api="currentApi()"` 每次重渲染都会
 * 求值，直接新建对象会让子组件的 props 每次都变、把 `watch(api)` 一类的逻辑反复触发。
 */
const boundApi = computed<PluginApi>(() => bindPluginApi(rawApi(), pluginId.value))

function currentApi(): PluginApi {
  return boundApi.value
}

const runtime = useRuntimeInfo(currentApi())
const { data: bootstrap, overview, updatedAt, error: runtimeError, loading: runtimeLoading, refresh: refreshRuntime } = runtime

/**
 * 数据台 store：原生视图共用一份状态（S6 逐个把 iframe 里的视图搬过来）。
 * 用壳已经拉到的 `/bootstrap` 灌一次（`hydrate` 不发请求），避免和右栏概况重复拉同一个端点。
 */
const store = usePluginStore(currentApi())
watch(
  bootstrap,
  (payload) => {
    if (payload) store.hydrate(payload as Record<string, unknown>)
  },
  { immediate: true },
)

/**
 * 数据台左栏的**数量角标**（老 `ui/index.html` 的 `#pillFavs` / `#pillSubs` /
 * `#pillTasks` / `#pillQueue` 四颗，口径逐条照抄老 `ui/app.js` 的 `renderPills()`）：
 *
 * | 栏目 | 老 id | 老口径 | 这里取的 store 字段 |
 * | --- | --- | --- | --- |
 * | 我的演员 | `#pillFavs` | `S.favs.length` | `favs` |
 * | 订阅 | `#pillSubs` | `S.subs.length` | `subs` |
 * | 任务 | `#pillTasks` | `S.tasks` 里 `state === 'await'` 的条数 | `awaitTasks` |
 * | 下载 | `#pillQueue` | `S.queue` 里 `state !== 'done'` 的条数 | `downloading` |
 *
 * 数据全部来自数据台 store，也就是壳已经在轮询的 `/bootstrap`（`useRuntimeInfo`，15 秒一轮，
 * 页面不可见时暂停）灌进来的那一份 —— **不新增请求、也不新增轮询**。
 * 「发现榜单」「站点搜索」照老实现**没有**角标（`badge` 为 `null`，模板里不渲染）。
 *
 * 计数为 0 时**照样显示 `0`**：老实现就是 `$('#pillX').textContent = n`，没有隐藏分支
 * （只有顶栏 `#bellCount` 有 `.zero{display:none}`），所以这里只在 0 时加 `avh-pill--zero`
 * 做视觉弱化，角标本身仍然画出来。
 */
interface NavBadge {
  /** 角标文本（老实现是 `textContent = n`，非数字不参与格式化）。 */
  count: number
  /** `true` = 老 `.pill.warn` 配色（老实现只有「任务」栏是 warn）。 */
  warn: boolean
}

const navBadges = computed<Record<string, NavBadge>>(() => ({
  actors: { count: store.favs.value.length, warn: false },
  subs: { count: store.subs.value.length, warn: false },
  tasks: { count: store.awaitTasks.value, warn: true },
  downloads: { count: store.downloading.value, warn: false },
}))

/** 数据台左栏条目 = 栏目 + 角标（`badge === null` = 这一栏不画角标）。 */
const dataSections = computed<(SectionItem & { badge: NavBadge | null })[]>(() =>
  DATA_SECTIONS.map(item => ({ ...item, badge: navBadges.value[item.key] ?? null })),
)

/** 设置草稿：脏标记与保存顺序都在这里（设计文档 §5）。 */
const draft = useSettingsDraft({
  api: currentApi(),
  initialConfig: props.initialConfig,
  toast: injectedToast,
  // 第 2 步（宿主配置）由 `saveHostConfig` 按入口选路：宿主接 save 就交给宿主，不接就自己 PUT。
  onSaveHost: saveHostConfig,
})

/**
 * 解构出来给模板用：`draft` 是普通对象，模板里 `draft.rule` 拿到的是 ref 本身
 * 而不是值（只有 `setup()` 返回值与顶层 ref 才会自动解包），所以显式取出。
 */
const {
  rule: ruleDraft,
  hostConfig,
  sites,
  sitesLoaded,
  notices,
  cacheText,
  checkInfo,
  dirty,
  enabledKnown,
  hostLoaded,
  saveButtonLabel,
  validation,
  loading: draftLoading,
  saving: draftSaving,
  noticeLoading,
  cacheCleaning,
  error: draftError,
  sectionDirty,
  load: loadDraft,
  applyBootstrap,
  hydrateHost,
  save: saveDraft,
  loadNotices,
  cleanCache: cleanCacheDraft,
} = draft

/** `/bootstrap` 轮询结果灌进草稿：站点清单、缓存占用、限流信息只有它有。 */
watch(bootstrap, value => applyBootstrap(value), { immediate: true })

const activeNavKey = computed(() => `data:${section.value}`)

/** 草稿还没就绪时（`/rule` 在飞）为 null，面板按需隐藏/回显空值。 */
const ruleView = computed<RuleState | null>(() => ruleDraft.value)

function patchRule(patch: Partial<RuleState>): void {
  const current = ruleDraft.value
  if (!current) return
  ruleDraft.value = { ...current, ...patch }
}

function pick(item: SectionItem): void {
  section.value = item.key
}

function pickSetting(item: SectionItem): void {
  settingsSection.value = item.key
}

/**
 * 「发现榜单」点卡片：老实现 `openMovie(number, id)` 打开「影片详情」抽屉
 * （`ui/views/detail.js`：预览图 + 磁力 + 长图补图 + 灯箱）。
 *
 * S6-7 之前这里是一句临时提示；现在换成真实调用：番号与 id 由壳声明式下传，
 * 抽屉内部的 watch 照着老 `openMovie` 的四步走（换片清 `CURSOR.id` → 写 id →
 * 标记「刚打开」→ `paintDetail`）。
 */
function onOpenMovie(payload: { number?: string; id?: string }): void {
  const number = String(payload?.number || '')
  if (!number) return
  drawerNumber.value = number
  drawerId.value = String(payload?.id || '')
  drawerOpen.value = true
}

/**
 * 详情抽屉 / 搜索结果里点了演员：老实现 `closeAll(); openActor(name)`。
 *
 * 壳这边做三件事：关掉抽屉与搜索弹窗、切到「我的演员」栏、把演员名交给 `ActorsView`。
 * `actorNonce` 每次自增并参与 `ActorsView` 的 `:key`：老 `openActor` 无论当前在哪一栏
 * 都会重新画一遍作品史；而"已经在看 A、再点一次 A"这种同值场景，只靠 prop 变化
 * 是触发不了的（Vue 不会为同一个值再跑一次 watch），换 key 重挂才真的等价。
 */
function openActorFromOverlay(name: string): void {
  const target = String(name || '')
  if (!target) return
  drawerOpen.value = false
  searchOpen.value = false
  actorFocus.value = target
  actorNonce.value += 1
  section.value = 'actors'
}

/** 顶栏搜索：老 `#qBtn.onclick` / `#qInput` 的 Enter（`doSearch($('#qInput').value)`）。 */
function runSearch(): void {
  const kw = String(query.value || '').trim()
  if (!kw) return
  searchOpen.value = true
  searchDialog.value?.search(kw)
}

/** 搜索结果里点影片：老 `closeAll(); openMovie(el.dataset.num, el.dataset.id || '')`。 */
function onSearchPickMovie(payload: { number?: string; id?: string }): void {
  searchOpen.value = false
  onOpenMovie(payload)
}

async function loadVersion(): Promise<void> {
  if (!framePluginId.value) return
  try {
    // 宿主自己的路由（`/api/v1/plugin/page/<id>`），走原始请求器、不补插件 id。
    const res: any = await rawApi().get(`plugin/page/${framePluginId.value}`)
    const payload = res && typeof res === 'object' && 'data' in res ? res.data : res
    const value = payload?.plugin_version
    if (typeof value === 'string' && value) {
      version.value = value
      return
    }
  } catch {
    // 拿不到就走下面的兜底；都不行就不显示版本号，不影响界面其余部分。
  }
  // 兜底：宿主 `plugin/page` 只返回 {render_mode, page}，不带插件版本；
  // 而 `plugin/remotes` 的入口 URL 上挂着 `?v=<plugin_version>`（宿主自己拼的），从那里取。
  try {
    const remotes: any = await rawApi().get('plugin/remotes?token=moviepilot')
    const list = Array.isArray(remotes) ? remotes : (remotes?.data ?? [])
    const mine = (Array.isArray(list) ? list : []).find(
      (item: any) => String(item?.id || '').toLowerCase() === framePluginId.value.toLowerCase(),
    )
    const matched = /[?&]v=([^&]+)/.exec(String(mine?.url || ''))
    if (matched) version.value = decodeURIComponent(matched[1])
  } catch {
    // 静默：版本号只是装饰。
  }
}

/** 从信封或裸对象里取一句提示文案。 */
function messageOf(res: any): string {
  if (!res || typeof res !== 'object') return ''
  for (const key of ['message', 'detail', 'msg']) {
    const value = (res as Record<string, any>)[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

/**
 * 顶条「保存修改」（仅设置台）：严格按设计文档 §5 —— 草稿层先 `POST /rule`，
 * 失败就 toast 报错并**不**把宿主配置交出去（弹窗不关）；成功后才 `emit('save')`。
 */
async function saveAll(): Promise<void> {
  if (draftSaving.value) return
  const ok = await saveDraft()
  if (!ok) return
  emit('action')
  await refreshRuntime()
}

/** 「清理缓存」：破坏性操作，先过宿主确认（拿不到注入就降级 `window.confirm`）。 */
async function cleanCache(): Promise<void> {
  const ok = await confirm({
    type: 'warn',
    title: '清理缓存',
    content: '将删除插件缓存目录里的图片与 JSON 缓存（不影响已下载的媒体、不删数据库）。确认继续？',
    confirmText: '清理',
    cancelText: '取消',
  })
  if (!ok) return
  const done = await cleanCacheDraft()
  if (!done) return
  await refreshRuntime()
}

/** 「清空通知」：不可恢复，同样先确认。 */
async function clearNotices(): Promise<void> {
  const ok = await confirm({
    type: 'warn',
    title: '清空通知',
    content: `将清空全部 ${notices.value.length} 条通知，且无法恢复。确认继续？`,
    confirmText: '清空',
    cancelText: '取消',
  })
  if (!ok) return
  noticeClearing.value = true
  try {
    // 走 store 这条实现（与通知抽屉同一条）：清空后 store 的 notices 归零 → 顶栏角标**即时**消失。
    // 只清设置台那份草稿的话，角标要等 ≤15s 的下一次 `/bootstrap` 才归零（缺口 G7）。
    const result = await store.clearNotices()
    if (!result.ok) {
      toast.warning(result.message || '清空通知失败')
      return
    }
    notices.value = []          // 设置台「通知」栏显示的就是这个 ref，顺手清掉，免得还列着旧条目
    await refreshRuntime()
  } finally {
    noticeClearing.value = false
  }
}

function closePanel(): void {
  emit('close')
}

/**
 * 打开设置窗口（左栏底部那颗「⚙ 打开设置台」，以及「站点搜索 → 改范围」「订阅 → 改规则」）。
 *
 * 设置是**本组件内的独立窗口**：打开只是把数据台之上的那一层盖上来，数据台本身不卸载、
 * 不换弹窗，所以关掉它必然回到数据台 —— 这正是用户要的"关掉设置就回主界面"。
 *
 * 顺带办两件事：① 读一次「落到哪一栏」的一次性便签（`settingsJump.ts`）；
 * ② 首次打开时把设置草稿拉起来（`/rule` + `/notices`，都在本机、很快）。
 */
function openSettings(): void {
  applyPendingSection()
  ensureDraft()
  settingsOpen.value = true
}

/**
 * 设置草稿只在**第一次打开设置窗口**时拉一次（`/rule` + `/notices`）：
 * 数据台弹窗里的用户可能根本不进设置，那两次请求就不该发。
 *
 * 顺带补一次**宿主配置真实值**：宿主 `./Page`（数据台弹窗）**不传** `initialConfig`，
 * 而宿主配置是整份覆盖的 `PUT plugin/<id>` —— 拿空草稿去 PUT 会把 `enabled` / `proxy`
 * 一起写没。2026-10-11 真机就是这么把插件关掉、代理也清空的（详见 `hostLoaded` 的说明）。
 * `./Config` 入口（宿主传了 `initialConfig`）不需要这一步：`hostLoaded` 一开始就是 true。
 */
let draftLoaded = false
function ensureDraft(): void {
  if (draftLoaded) return
  draftLoaded = true
  void loadHostConfig()
  void loadDraft()
}

/** 读一次宿主保存的插件配置（宿主路由 `GET plugin/<实例id>`），给草稿补上基准值。 */
async function loadHostConfig(): Promise<void> {
  if (hostLoaded.value) return
  const api = rawApi()
  if (!api.get || !pluginId.value) return
  try {
    const res: any = await api.get(`plugin/${pluginId.value}`, { feedback: 'silent' })
    const payload = res && typeof res === 'object' && 'data' in res ? res.data : res
    hydrateHost(payload)
  } catch {
    // 拿不到就保持 hostLoaded=false：保存时第 2 步会被挡下（宁可报错，也不写空配置）。
  }
}

function closeSettings(): void {
  settingsOpen.value = false
}

/**
 * 保存宿主配置（`enabled` / `proxy` / `emby_host` / `emby_apikey`）：按入口分两条路。
 *
 * - **配置弹窗侧**（`mode === 'settings'`，用户从插件卡片的「设置」菜单进来）：
 *   交给宿主 —— 宿主的 `PluginConfigDialog` 接了 `save`，它自己 `PUT plugin/<id>`，
 *   并顺带刷新插件卡与侧栏导航；
 * - **数据台侧**（`mode === 'data'`，用户点开插件详情后在里面进设置）：
 *   宿主**没接** `save` —— MP v3.1.4 前端产物实测，`PluginDataDialog` 的 vue 分支只绑了
 *   `action` / `layout` / `switch` / `close`，所以这一步得我们按同一条宿主路由自己 PUT。
 *   路径固定 `plugin/<实例id>`：宿主只在**分身**场景才重写 `plugin/<源id>`，
 *   而我们这里写的就是实例 id，普通安装与分身都对得上（详见 `api/pluginInstance.ts`）。
 *
 * **前置条件**：必须已经读到过宿主配置（`hostLoaded`）。`PUT plugin/<id>` 是整份覆盖，
 * 草稿里那四个字段就是配置的全部内容；基准没读到就提交等于把配置清空 —— 直接抛错，
 * 让草稿层的 catch 提示「保存失败」，脏标记留着，用户重开设置窗口再试。
 */
async function saveHostConfig(config: PluginConfig): Promise<void> {
  if (settingsEntry.value) {
    emit('save', config)
    return
  }
  if (!hostLoaded.value) {
    throw new Error('尚未读到插件配置，本次未提交宿主配置（请关掉设置窗口重开一次再保存）')
  }
  const api = rawApi()
  if (!api.put || !pluginId.value) {
    throw new Error('宿主不支持保存插件配置（缺少 PUT 能力）')
  }
  const res: any = await api.put(`plugin/${pluginId.value}`, config, { feedback: 'silent' })
  const payload = res && typeof res === 'object' && 'data' in res ? res.data : res
  if (payload?.success === false) {
    throw new Error(messageOf(payload) || '插件配置保存失败')
  }
}

watch(
  () => props.mode,
  (mode) => {
    // 同一个实例被宿主复用、mode 从 data 变到 settings（或反过来）时，跟着把设置窗口开合一次。
    if (mode === 'settings') openSettings()
    else closeSettings()
  },
)

/**
 * 设置窗口落点：数据台里点「改范围 / 改规则」时，视图先写一张一次性便签
 * （`settingsJump.ts` 的 `requestSettingsSection`）再发 `switch`，这里在**打开窗口前**取走它。
 *
 * 便签机制保留原样：它本来就是"跨实例传一次落点"的办法，现在虽然同一个 Console 就能定位，
 * 但视图那侧不必改（少动一处就少一处回归面）；读后即删，便签为空或栏目名不认识就停在当前栏。
 */
function applyPendingSection(): void {
  const pending = takePendingSettingsSection()
  if (pending && SETTINGS_SECTIONS.some(item => item.key === pending)) settingsSection.value = pending
}

onMounted(() => {
  // 设计文档 §3：弹窗宽度由 `layout` 事件声明（宿主默认 80rem）。
  emit('layout', { maxWidth: DEFAULT_MAX_WIDTH })
  runtime.start()
  void loadVersion()
  if (props.mode === 'settings') {
    // 配置弹窗入口：一进来就把设置窗口打开（便签在这时也再取一次，覆盖 setup 后才写入的情况）。
    openSettings()
  }
})

onBeforeUnmount(() => {
  runtime.stop()
})
</script>

<template>
  <div class="avh-console">
    <v-toolbar density="comfortable" color="surface" class="avh-topbar">
      <!--
        顶栏 = **三段式**：左块（图标 + 标题 + 版本 + 「已停用」chip）/ 中间搜索框 / 右块（🔔 + 关闭）。
        为什么改：原来是「标题 + `<v-spacer>` + 搜索框 + 一串按钮」，右侧按钮越多，搜索框就被推得越靠右
        —— 真机实测它与工具条的几何中心差 53~177px。现在左右两块都是 `flex: 1 1 0`
        （flex-basis 为 0、grow 相同 → 严格等宽），搜索框是固定基准宽的第三段，
        于是它必然落在工具条几何中心，与右块有几颗按钮无关。
      -->
      <div class="avh-topbar__left">
        <v-icon icon="mdi-movie-open-star" color="primary" class="ms-2" />
        <v-toolbar-title class="avh-title">
          <span class="text-h6">AV 资源助手</span>
          <span v-if="version" class="text-caption text-medium-emphasis">v{{ version }}</span>
          <v-chip
            v-if="overview.enabled === false"
            size="x-small"
            color="warning"
            variant="tonal"
          >已停用</v-chip>
        </v-toolbar-title>
      </div>

      <!-- 顶栏搜索（老 `ui/index.html` 的 `#qInput` / `#qBtn`）：占位符与按钮文案逐字照抄 -->
      <div class="avh-searchbox">
        <v-text-field
          v-model="query"
          density="compact"
          variant="outlined"
          hide-details
          single-line
          autocomplete="off"
          placeholder="搜索番号 / 演员（如 SSIS-001）…"
          class="avh-searchbox__input"
          @keydown.enter="runSearch"
        />
        <v-btn color="primary" variant="flat" size="small" @click="runSearch">搜索</v-btn>
      </div>

      <!-- 右块：与左块严格等宽的第三段，内容右对齐 —— 两块等宽才是搜索框居中的前提。 -->
      <div class="avh-topbar__right">
        <!--
          🔔 通知（老 `ui/index.html` 顶条最右那颗 `#bellBtn`：`<button class="ghost" id="bellBtn">🔔 通知
          <span class="bellbadge zero" id="bellCount">0</span></button>`）。
          位置与老实现一致：搜索框右侧、破坏性/主操作按钮之前。
          角标：未读为 0 时**整颗不画**（等价老 `.bellbadge.zero{display:none}`），
          计数逻辑与老 `noticeUnread()` 一致（`time` 晚于已读位点的条数）。
        -->
        <v-btn
          variant="text"
          class="avh-bell"
          title="通知"
          @click="openNotify"
        >
          🔔 通知
          <span v-if="notifyUnread() > 0" class="avh-bellbadge">{{ notifyUnread() }}</span>
        </v-btn>

        <!-- 顶栏**没有**「运行一次」：用户明确要求删掉 —— 功能冗余（「订阅」栏自带「检查一次」、
             「我的演员」栏自带「检查她」，都在各自视图里，未受影响），而且它占着顶栏右端、
             把搜索框挤离几何中心。随它一起删掉的还有 `runCheck()` 与 `running` ref。 -->

        <!-- 「保存修改」也不在这里：它跟着设置窗口走（见下面那个 v-dialog 的顶条），
             数据台本身没有可保存的东西。 -->

        <v-btn variant="text" prepend-icon="mdi-close" class="me-2" @click="closePanel">关闭</v-btn>
      </div>
    </v-toolbar>

    <v-divider />

    <div class="avh-body">
      <!--
        左栏：上 = 滚动区（栏目列表 + 运行概况），下 = 钉底的设置入口。
        运行概况原本是内容区右侧独立的一栏（`<aside class="avh-side">`，白占 264px、还把内容区挤窄），
        现在搬进这里：窄栏里它照样完整可读，内容区则拿到整宽。
      -->
      <nav class="avh-nav">
        <div class="avh-nav__scroll">
          <v-list density="compact" nav :selected="[activeNavKey]" mandatory>
            <v-list-subheader>数据台</v-list-subheader>
            <!--
              数量角标（老 `nav .pill`）：`#append` 插槽画在标题右侧，与老 `<button>文字<span class="pill">`
              的位置一致。「发现榜单」「站点搜索」的 `badge` 为 `null` → 不画，照老实现。
            -->
            <v-list-item
              v-for="item in dataSections"
              :key="item.key"
              :value="`data:${item.key}`"
              :prepend-icon="item.icon"
              :title="item.title"
              @click="pick(item)"
            >
              <template #append>
                <span
                  v-if="item.badge"
                  class="avh-pill"
                  :class="{ 'avh-pill--warn': item.badge.warn, 'avh-pill--zero': item.badge.count === 0 }"
                >{{ item.badge.count }}</span>
              </template>
            </v-list-item>
          </v-list>

          <!-- 运行概况（挂载后取 /bootstrap，每 15s 轮询，页面不可见时暂停）。
               卡片本身没变，只按 216px 窄栏收紧了内边距与标题档位，见 `.avh-overview` 样式。 -->
          <v-card variant="outlined" class="avh-overview mt-2">
            <v-card-item>
              <template #prepend>
                <v-icon icon="mdi-gauge" color="primary" />
              </template>
              <v-card-title class="text-body-2 font-weight-medium">运行概况</v-card-title>
              <v-card-subtitle v-if="updatedAt" class="text-caption">更新于 {{ updatedAt }}</v-card-subtitle>
            </v-card-item>

            <v-card-text>
              <v-list density="compact" class="pa-0">
                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">订阅</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 font-weight-medium">{{ overview.subs === null ? '—' : overview.subs }}</span>
                  </template>
                </v-list-item>
                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">待确认任务</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 font-weight-medium">{{ overview.awaitTasks === null ? '—' : overview.awaitTasks }}</span>
                  </template>
                </v-list-item>
                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">下载中</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 font-weight-medium">{{ overview.downloading === null ? '—' : overview.downloading }}</span>
                  </template>
                </v-list-item>
                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">收藏演员</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 font-weight-medium">{{ overview.favorites === null ? '—' : overview.favorites }}</span>
                  </template>
                </v-list-item>
                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">通知</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 font-weight-medium">{{ overview.notices === null ? '—' : overview.notices }}</span>
                  </template>
                </v-list-item>

                <v-divider class="my-2" />

                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">缓存</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 text-medium-emphasis">{{ overview.cacheSize }}</span>
                  </template>
                </v-list-item>
                <v-list-item class="px-0">
                  <v-list-item-title class="text-body-2">下次检查</v-list-item-title>
                  <template #append>
                    <span class="text-body-2 text-medium-emphasis">{{ overview.nextCheck }}</span>
                  </template>
                </v-list-item>
              </v-list>

              <v-btn
                block
                size="small"
                variant="text"
                prepend-icon="mdi-refresh"
                :loading="runtimeLoading"
                class="mt-2"
                @click="refreshRuntime(true)"
              >刷新</v-btn>

              <v-alert
                v-if="runtimeError"
                type="warning"
                variant="tonal"
                density="compact"
                class="mt-2 text-caption"
              >{{ runtimeError }}</v-alert>
            </v-card-text>
          </v-card>
        </div>

        <!-- 设置唯一入口：打开本组件内的设置窗口（不是宿主弹窗互换）。
             设置窗口里**没有**「打开数据台」那颗按钮 —— 关掉窗口本来就回到这里。
             它钉在左栏最底部（`.avh-nav__switch` 的 `margin-top: auto`）：滚动区怎么滚都不动它。 -->
        <v-btn
          block
          size="small"
          variant="text"
          prepend-icon="mdi-cog-outline"
          class="avh-nav__switch"
          @click="openSettings"
        >打开设置</v-btn>
      </nav>

      <v-divider vertical />

      <!-- 内容区 -->
      <section class="avh-content">
        <!-- S6 增量替换：已原生化的栏目走 Vue 组件（见 NATIVE_VIEWS），六栏现在全在这里。 -->
        <component
          :is="nativeView"
          v-if="nativeView && framePluginId"
          :key="section === 'actors' ? `actors:${actorNonce}` : section"
          :store="store"
          :plugin-id="framePluginId"
          :api="currentApi()"
          :toast="injectedToast"
          :focus-actor="section === 'actors' ? actorFocus : ''"
          @switch="openSettings"
          @refresh-side="refreshRuntime(true)"
          @open-movie="onOpenMovie"
          @open-actor="openActorFromOverlay"
        />
        <AppFrame
          v-else-if="framePluginId"
            :plugin-id="framePluginId"
            :section-key="section"
            :version="version"
          />
          <v-alert v-else type="warning" variant="tonal">
            宿主没有传入 pluginId，无法定位内嵌应用。
          </v-alert>
      </section>
    </div>

    <!--
      设置窗口（2026-10-11 重构）：**本组件内的独立弹窗**，盖在数据台之上。

      为什么不再走宿主的 Page ⇄ Config 互换：
      - 宿主换弹窗时会把数据台那个弹窗一起关掉（`PluginDataDialog` 的 `closeOn` 含 `switch`），
        于是"关掉设置"只能要么停在设置页、要么整个界面消失 —— 用户实测的两个症状都出自这里；
      - 弹窗层次由宿主栈决定，一旦同名事件被转发两次（`defineEmits` 写法踩过的坑，见
        `emitContract.ts`）就会叠出两层一模一样的设置弹窗，第一下"关闭"看起来毫无反应。

      现在这一层的开合完全由本组件掌握：**任何**关闭方式（右上 ×、ESC、点遮罩）
      都只是 `settingsOpen = false`，数据台一直在下面，必然回到主界面。
      窗口里也**没有**「打开数据台」按钮 —— 关掉就是数据台。
    -->
    <v-dialog v-model="settingsOpen" max-width="1120" scrollable>
      <v-card class="avh-settings">
        <v-toolbar density="comfortable" color="surface" class="avh-settings__bar">
          <v-icon icon="mdi-cog-outline" color="primary" class="ms-2" />
          <v-toolbar-title class="text-h6">设置</v-toolbar-title>

          <v-spacer />

          <!-- 保存按钮跟着设置窗口走：数据台没有可保存的东西 -->
          <v-btn
            :color="dirty ? 'warning' : 'primary'"
            :variant="dirty ? 'flat' : 'tonal'"
            prepend-icon="mdi-content-save"
            :loading="draftSaving"
            class="me-2"
            @click="saveAll"
          >{{ saveButtonLabel }}</v-btn>

          <v-btn
            variant="text"
            icon="mdi-close"
            title="关闭设置（回到数据台）"
            class="me-2"
            @click="closeSettings"
          />
        </v-toolbar>

        <v-divider />

        <div class="avh-settings__body">
          <!-- 左栏：设置七栏 -->
          <nav class="avh-settings__nav">
            <v-list density="compact" nav :selected="[settingsSection]" mandatory>
              <v-list-item
                v-for="item in SETTINGS_SECTIONS"
                :key="item.key"
                :value="item.key"
                :prepend-icon="item.icon"
                :title="item.title"
                @click="pickSetting(item)"
              >
                <template #append>
                  <v-icon
                    v-if="sectionDirty(item.key)"
                    icon="mdi-circle"
                    size="8"
                    color="warning"
                    title="本栏有未保存改动"
                  />
                </template>
              </v-list-item>
            </v-list>
          </nav>

          <v-divider vertical />

          <!-- 右栏：当前设置栏 -->
          <section class="avh-settings__content">
            <v-alert
              v-if="draftError"
              type="warning"
              variant="tonal"
              density="compact"
              class="text-caption mb-3"
            >{{ draftError }}</v-alert>

            <!-- 规则草稿还没到位时才出骨架（`/rule` 在飞）。它是独立的，不参与下面的
                 v-if/v-else-if 链：否则「常规」「通知」这些不依赖规则的栏目会被一起挡住。 -->
            <v-skeleton-loader v-if="draftLoading && !ruleView" type="article" class="mb-3" />

            <GeneralPanel
              v-if="settingsSection === 'general'"
              :config="hostConfig"
              :enabled-known="enabledKnown"
              @patch="(patch: any) => Object.assign(hostConfig, patch)"
            />

            <SitesPanel
              v-else-if="settingsSection === 'sites'"
              :sites="ruleView?.sites || []"
              :pref-sites="ruleView?.prefSites || []"
              :options="sites"
              :loaded="sitesLoaded"
              @update:sites="(value: string[]) => patchRule({ sites: value })"
              @update:pref-sites="(value: string[]) => patchRule({ prefSites: value })"
            />

            <RulePanel
              v-else-if="settingsSection === 'rule' && ruleView"
              :rule="ruleView"
              :policy-min-interval="checkInfo?.minIntervalMin || 0"
              :site-scope-count="ruleView.sites.length"
              @patch="patchRule"
            />

            <NotifyPanel
              v-else-if="settingsSection === 'notify'"
              :notices="notices"
              :loading="noticeLoading"
              :clearing="noticeClearing"
              @clear="clearNotices"
              @reload="loadNotices"
            />

            <LibraryPanel
              v-else-if="settingsSection === 'library'"
              :config="hostConfig"
              :validation="validation"
              @patch="(patch: any) => Object.assign(hostConfig, patch)"
            />

            <RuntimePanel
              v-else-if="settingsSection === 'runtime'"
              :cache-text="cacheText"
              :check="checkInfo"
              :cleaning="cacheCleaning"
              :loading="runtimeLoading"
              @clean="cleanCache"
              @refresh="refreshRuntime(true)"
            />

            <AboutPanel
              v-else-if="settingsSection === 'about'"
              :version="version"
              :plugin-id="props.pluginId"
              :source-plugin-id="props.sourcePluginId"
            />

            <v-alert v-else type="info" variant="tonal">
              未知栏目：{{ activeSetting.title }}
            </v-alert>
          </section>
        </div>
      </v-card>
    </v-dialog>

    <!--
      跨栏目的三个弹层（S6-7 详情/搜索，S6-8 通知）：挂在壳的根节点上，切栏目不会把已经打开的
      浮层弄丢（老实现里 `#drawer` / `#ndrawer` / `#modal` / `#lb` 就在 `ui/index.html` 的根层级上）。
    -->
    <DetailDrawer
      v-if="framePluginId"
      :open="drawerOpen"
      :number="drawerNumber"
      :id="drawerId"
      :store="store"
      :plugin-id="framePluginId"
      :api="currentApi()"
      :toast="injectedToast"
      @close="drawerOpen = false"
      @open-actor="openActorFromOverlay"
      @refresh-side="refreshRuntime(true)"
    />

    <SearchDialog
      v-if="framePluginId"
      ref="searchDialog"
      :open="searchOpen"
      :plugin-id="framePluginId"
      :api="currentApi()"
      @close="searchOpen = false"
      @open-movie="onSearchPickMovie"
      @open-actor="openActorFromOverlay"
    />

    <!--
      通知抽屉（S6-8）：列表就是 `store.notices`（`/bootstrap` 轮询那份），
      「清空」走 `store.clearNotices()`；已读位点由抽屉内部上移（打开即已读）。
    -->
    <NotifyDrawer
      :open="notifyOpen"
      :notices="store.notices.value"
      :plugin-id="framePluginId"
      :clearing="noticeClearing"
      @close="notifyOpen = false"
      @clear="clearNoticesFromDrawer"
    />
  </div>
</template>

<style scoped>
.avh-console {
  display: flex;
  flex-direction: column;
  /*
   * 固定高度：宿主弹窗是**按内容量尺寸**的，根盒子不定高时「发现榜单」能长到 5562px、
   * 其它栏目只有 501~645px，于是切栏目弹窗忽大忽小。78vh 是本项目既有口径
   * （`AppFrame.vue` 里 iframe 的高度），**不用** `calc(100vh - …)`（改它需要真机调，设计文档 §7）。
   * `min-height` 兜住矮视口，`overflow: hidden` 让多出来的内容由内部滚动消化（内容区本来就
   * 是 `overflow: auto`），根盒子从此不再长高 —— 任何栏目下弹窗外框都一样大。
   */
  height: 78vh;
  min-height: 520px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
}

.avh-topbar {
  flex: 0 0 auto;
  padding-inline: 0;
}

/* 三段式顶栏的左块：与右块等宽（flex-basis 0）、内容左对齐。
   `min-width: 0` + `overflow: hidden` 让它在窄弹窗里先被压缩，把宽度让给中间的搜索框。 */
.avh-topbar__left {
  flex: 1 1 0;
  min-width: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 右块：与左块严格等宽 + 内容右对齐 —— 两块等宽，夹在中间的搜索框才落在工具条几何中心。 */
.avh-topbar__right {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.avh-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 顶栏搜索（老 `.searchbox`：输入框 + 紧贴的「搜索」按钮，占位符同款）。
   三段式里的中段：grow 0 / basis 420px → 固定基准宽，被两侧等宽块顶到几何中心；
   窄弹窗里可一路缩到 200px（工具条本身是 nowrap 的 flex，始终单行不换行）。 */
.avh-searchbox {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 1 420px;
  min-width: 200px;
  margin-right: 0;
}

.avh-searchbox__input {
  flex: 1 1 auto;
  min-width: 120px;
}

/* 顶栏「🔔 通知」那颗按钮：老实现是 `.ghost`（`white-space:nowrap` + 12px 字号），
   不换行才不会在窄弹窗里折成两行。 */
.avh-bell {
  white-space: nowrap;
}

/* 未读角标：照抄老 `.bellbadge`（圆角胶囊、11px、左侧 6px 间距、最小宽 16px）。
   老实现用 `.zero{display:none}` 在 0 时隐藏，这里等价地 `v-if="notifyUnread() > 0"` 不渲染。 */
.avh-bellbadge {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  min-width: 16px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 16px;
  text-align: center;
  color: #fff;
  background: rgb(var(--v-theme-error));
}

/* 左栏数量角标：几何值照抄老 `nav .pill`（`ui/app.css`）——
   圆角 999px、字号 11px、内边距 `0 6px`、行高 16px、最小宽 16px、文字居中。
   配色不搬老界面的写死值（`--acc2:#2f6fd0` / `--warn:#d29922` / `#fff` / `#2b2100`），
   改走 Vuetify 主题变量：普通态 = 老那颗蓝（`primary`），warn 态 = 老那颗琥珀（`warning`）。 */
.avh-pill {
  display: inline-block;
  min-width: 16px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 16px;
  text-align: center;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}

/* 老 `.pill.warn`：只有「任务」栏那一颗。 */
.avh-pill--warn {
  background: rgb(var(--v-theme-warning));
  color: rgb(var(--v-theme-on-warning));
}

/* 计数为 0 也照画（老实现 `textContent = n`，不留空），只是弱化到不抢眼。 */
.avh-pill--zero {
  opacity: 0.55;
}

.avh-body {
  display: flex;
  align-items: stretch;
  /* 根盒子定高后，这一层必须自己吃掉剩余高度：原来是 `flex: 0 1 auto`，
     内容一多它就把根盒子撑高、再被根盒子的 `overflow: hidden` 裁掉一节。 */
  flex: 1 1 auto;
  min-height: 0;
  padding: 12px;
  gap: 4px;
}

/* 左栏：上 = 滚动区（栏目列表 + 运行概况），下 = 钉底的设置入口。
   216px = 原右栏 264px 的收窄版：概况整块搬进来后，内容区反而拿到了整宽。 */
.avh-nav {
  flex: 0 0 216px;
  max-width: 216px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

/* 左栏滚动区：`min-height: 0` 不能省 —— flex 子项默认 `min-height: auto` 会拒绝收缩，
   内容一多就把左栏顶出根盒子。滚动条只出现在这里，底部那颗按钮永远留在栏底。 */
.avh-nav__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

/* 栏目行高收到 34px（Vuetify 默认 40）：左栏多装了「运行概况」整张卡片，
   6 行栏目 + 卡片 + 底部按钮要在 78vh 减去工具栏的高度里全部装下 ——
   实测 34px 正好让左栏在 1440×900 下不需要滚动（更矮的窗口仍由 `__scroll` 兜底）。 */
.avh-nav__scroll > .v-list .v-list-item {
  min-height: 34px;
}

/* 「打开设置」：`margin-top: auto` 把它钉在左栏最底部，`flex: 0 0 auto` 保证它不被滚动区挤压。
   位置/样式是本轮唯一改动 —— 它的 `@click="openSettings"` 与文案一字未改。 */
.avh-nav__switch {
  margin-top: auto;
  flex: 0 0 auto;
}

.avh-content {
  flex: 1 1 auto;
  min-width: 0;
  overflow: auto;
  padding-inline: 12px;
}

/*
 * 运行概况（原右栏卡片，现挂左栏列表下方）：卡片内边距收紧、标题降一档，
 * 让 7 行信息（订阅 / 待确认任务 / 下载中 / 收藏演员 / 通知 / 缓存 / 下次检查）
 * + 分割线 + 「刷新」在 216px 窄栏里也完整显示。
 * 这里**没有** `position: sticky`（右栏那版有）：卡片现在是滚动区里的最后一项，
 * sticky 只会让它在滚动时浮到顶部盖住栏目列表（outlined 卡片还是透明底，会糊在一起）。
 */
.avh-overview :deep(.v-card-item) {
  padding: 8px 10px 4px;
}

/* 标题图标与文字之间默认 8px，窄栏里收到 6px */
.avh-overview :deep(.v-card-item__prepend) {
  padding-inline-end: 6px;
}

.avh-overview :deep(.v-card-text) {
  padding: 4px 10px 8px;
}

/* 行高从 40px 收到 ~25px：7 行 + 分割线才装得进窄栏。
   只压 `padding-block` 没用（内容行高仍撑着），所以 `min-height` 也归零，
   由「标题行 21px + 上下各 2px」决定行高 —— 216px 窄栏里 7 行刚好排满。 */
.avh-overview :deep(.v-list-item) {
  min-height: 0;
  padding-block: 2px;
}

.avh-overview :deep(.v-list-item-title) {
  line-height: 1.3;
}

/* 标题列（1fr，长标题仍是 ellipsis）与数值列之间留一点缝，别贴在一起 */
.avh-overview :deep(.v-list-item__content) {
  padding-inline-end: 6px;
}

/* 数值一律不换行：「待确认任务 12」这类行一折行，7 行就把窄栏撑散了 */
.avh-overview :deep(.v-list-item__append) {
  white-space: nowrap;
}

/*
 * 设置窗口：窗口自身占满 `v-dialog` 的 `max-width`（1120px），
 * 左栏固定 190px、右栏自适应并各自滚动 —— 与数据台同一套排布，只是换成了独立窗口。
 */
.avh-settings {
  display: flex;
  flex-direction: column;
  min-height: 0;
  /* 与数据台同一口径的固定高度：设置窗口的尺寸也不再随栏目跳。
     这里**只加高度、不动结构**，内部两栏（`__nav` / `__content` 本来就是 `overflow: auto`）
     照旧各自滚动。

     ⚠️ 必须写 `min-height`，**不能写 `height`**（2026-10-11 实测）：`v-dialog scrollable` 会给
     卡片加一条 `max-height: 100%`，而外层 `.v-overlay__content` 的高度是"按内容算"的 ——
     卡片上写死的 `height: 78vh` 会被那条 `max-height:100%`（解析成卡片自己的内容高）夹回去，
     实测 7 栏里只有内容最高的两栏超过 520px，其余全停在内容高度（405/460/520）。
     `min-height` 的优先级高于 `max-height`，内容被撑到 78vh，那条 `100%` 也跟着变成 78vh。 */
  min-height: 78vh;
}

.avh-settings__bar {
  flex: 0 0 auto;
  padding-inline: 0;
}

.avh-settings__body {
  display: flex;
  align-items: stretch;
  min-height: 0;
  padding: 12px;
  gap: 4px;
}

.avh-settings__nav {
  flex: 0 0 190px;
  max-width: 190px;
  overflow-y: auto;
}

.avh-settings__content {
  flex: 1 1 auto;
  min-width: 0;
  overflow: auto;
  padding-inline: 12px;
  max-height: 68vh;
}

@media (max-width: 1100px) {
  .avh-body {
    flex-wrap: wrap;
  }

  /* 窄屏降级：左栏不再钉 216px，交给 flex 分配（`.avh-side` 已随右栏一起删除） */
  .avh-nav {
    flex: 1 1 auto;
    max-width: none;
  }

  .avh-settings__body {
    flex-wrap: wrap;
  }

  .avh-settings__nav {
    flex: 1 1 auto;
    max-width: none;
  }
}
</style>
