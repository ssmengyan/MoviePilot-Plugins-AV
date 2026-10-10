<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import AppFrame from './AppFrame.vue'
import { DEFAULT_MAX_WIDTH, type ConfigProps } from './contract'
import { consoleEmits } from './emitContract'
import {
  errorText,
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

/** 壳只有两种模式：`data` = 数据台（iframe），`settings` = 设置台（七个栏目）。 */
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

const emit = defineEmits(consoleEmits())

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

const section = ref<string>(props.mode === 'settings' ? SETTINGS_SECTIONS[0]!.key : DATA_SECTIONS[0]!.key)
const running = ref(false)
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

const isSettings = computed(() => props.mode === 'settings')

const activeSection = computed<SectionItem>(
  () => SETTINGS_SECTIONS.find(item => item.key === section.value) || SETTINGS_SECTIONS[0]!,
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

function currentApi(): PluginApi {
  return props.api && typeof props.api.get === 'function' ? props.api : FALLBACK_API
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

/** 设置台草稿：脏标记与保存顺序都在这里（设计文档 §5）。 */
const draft = useSettingsDraft({
  api: currentApi(),
  initialConfig: props.initialConfig,
  toast: injectedToast,
  onSaveHost: (config: PluginConfig) => emit('save', config),
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
  save: saveDraft,
  loadNotices,
  clearNotices: clearNoticesDraft,
  cleanCache: cleanCacheDraft,
} = draft

/** `/bootstrap` 轮询结果灌进草稿：站点清单、缓存占用、限流信息只有它有。 */
watch(bootstrap, value => applyBootstrap(value), { immediate: true })

const activeNavKey = computed(() =>
  isSettings.value ? section.value : `data:${section.value}`,
)

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
    const res: any = await currentApi().get(`plugin/page/${framePluginId.value}`)
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
    const remotes: any = await currentApi().get('plugin/remotes?token=moviepilot')
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

/** 顶条「运行一次」：`POST /check`（受限流，按钮转圈后 toast 结果）。 */
async function runCheck(): Promise<void> {
  if (running.value) return
  running.value = true
  try {
    const res: any = await currentApi().post(`plugin/check`, {})
    const payload = res && typeof res === 'object' && 'data' in res ? res.data : res
    const message = messageOf(res) || messageOf(payload)
    if (payload?.limited) {
      toast.warning(message || '已达限流上限，本次未执行检查')
    } else {
      const hits = Array.isArray(payload?.notices) ? payload.notices.length : null
      toast.success(message || (hits === null ? '检查完成' : `检查完成：新增 ${hits} 条通知`))
    }
    await refreshRuntime()
  } catch (err) {
    toast.error(errorText(err))
  } finally {
    running.value = false
  }
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
    await clearNoticesDraft()
  } finally {
    noticeClearing.value = false
  }
}

function closePanel(): void {
  emit('close')
}

/**
 * 左栏底部那颗「打开数据台 / 打开设置台」。
 *
 * 宿主的 `switch` 是**叠加**而不是替换：数据台里 `switch` 会开一个设置弹窗盖在主界面之上
 * （关掉它就回到主界面，这是期望行为）；但设置台里再 `switch` 会再叠一层主界面 ——
 * 用户实测的"主界面 + 设置 + 主界面"三层就是这么来的。
 * 所以设置台这一侧改成 `close`：关掉设置弹窗，自然露出下面那层数据台，层数封顶 2。
 */
function switchConsole(): void {
  if (isSettings.value) {
    emit('close')
    return
  }
  emit('switch')
}

watch(
  () => props.mode,
  (mode) => {
    section.value = mode === 'settings' ? SETTINGS_SECTIONS[0]!.key : DATA_SECTIONS[0]!.key
  },
)

/**
 * 设置台落点：数据台里点「改范围 / 改规则」时，先写一张一次性便签（`settingsJump.ts`），
 * 再 `emit('switch')`。宿主只互换 Page/Config 两个弹窗、**不带载荷**，两个 Console 实例
 * 又不共享 `section`，所以只能靠这张同源便签把设置台定位到对应栏目。
 *
 * 读后即删（一次有效）；便签为空或栏目名不认识时保持默认第一栏。
 */
function applyPendingSection(): void {
  if (props.mode !== 'settings') return
  const pending = takePendingSettingsSection()
  if (pending && SETTINGS_SECTIONS.some(item => item.key === pending)) section.value = pending
}
applyPendingSection()

onMounted(() => {
  // 设计文档 §3：弹窗宽度由 `layout` 事件声明（宿主默认 80rem）。
  emit('layout', { maxWidth: DEFAULT_MAX_WIDTH })
  runtime.start()
  void loadVersion()
  if (props.mode === 'settings') {
    // 再取一次：便签可能在 setup 之后才写入（同一实例被复用的情况）。
    applyPendingSection()
    void loadDraft()
  }
})

onBeforeUnmount(() => {
  runtime.stop()
})
</script>

<template>
  <div class="avh-console">
    <v-toolbar density="comfortable" color="surface" class="avh-topbar">
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

      <v-spacer />

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

      <!--
        🔔 通知（老 `ui/index.html` 顶条最右那颗 `#bellBtn`：`<button class="ghost" id="bellBtn">🔔 通知
        <span class="bellbadge zero" id="bellCount">0</span></button>`）。
        位置与老实现一致：搜索框右侧、破坏性/主操作按钮之前。
        角标：未读为 0 时**整颗不画**（等价老 `.bellbadge.zero{display:none}`），
        计数逻辑与老 `noticeUnread()` 一致（`time` 晚于已读位点的条数）。
      -->
      <v-btn
        variant="text"
        class="avh-bell me-2"
        title="通知"
        @click="openNotify"
      >
        🔔 通知
        <span v-if="notifyUnread() > 0" class="avh-bellbadge">{{ notifyUnread() }}</span>
      </v-btn>

      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-play"
        :loading="running"
        class="me-2"
        @click="runCheck"
      >运行一次</v-btn>

      <v-btn
        v-if="isSettings"
        :color="dirty ? 'warning' : 'primary'"
        :variant="dirty ? 'flat' : 'tonal'"
        prepend-icon="mdi-content-save"
        :loading="draftSaving"
        class="me-2"
        @click="saveAll"
      >{{ saveButtonLabel }}</v-btn>

      <v-btn variant="text" prepend-icon="mdi-close" class="me-2" @click="closePanel">关闭</v-btn>
    </v-toolbar>

    <v-divider />

    <div class="avh-body">
      <!-- 左栏：栏目导航 -->
      <nav class="avh-nav">
        <v-list density="compact" nav :selected="[activeNavKey]" mandatory>
          <template v-if="!isSettings">
            <v-list-subheader>数据台</v-list-subheader>
            <v-list-item
              v-for="item in DATA_SECTIONS"
              :key="item.key"
              :value="`data:${item.key}`"
              :prepend-icon="item.icon"
              :title="item.title"
              @click="pick(item)"
            />
          </template>

          <template v-else>
            <v-list-subheader>设置台</v-list-subheader>
            <v-list-item
              v-for="item in SETTINGS_SECTIONS"
              :key="item.key"
              :value="item.key"
              :prepend-icon="item.icon"
              :title="item.title"
              @click="pick(item)"
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
          </template>
        </v-list>

        <!-- 数据台 ⇄ 设置台。
             宿主的 `switch` **不是替换而是再叠一层**弹窗：数据台点「打开设置台」= 设置叠在主界面之上
             （关掉设置就回到主界面，符合预期）；但在设置台里再 `switch` 会叠出第三层主界面
             （用户实测：主界面 + 设置 + 主界面）。所以设置台这一侧改用 `close`，
             直接关掉设置弹窗、露出下面那层数据台 —— 层数永远不超过 2。 -->
        <v-btn
          block
          size="small"
          variant="text"
          :prepend-icon="isSettings ? 'mdi-view-dashboard-outline' : 'mdi-cog-outline'"
          class="mt-2"
          @click="switchConsole"
        >{{ isSettings ? '打开数据台' : '打开设置台' }}</v-btn>
      </nav>

      <v-divider vertical />

      <!-- 内容区 -->
      <section class="avh-content">
        <template v-if="!isSettings">
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
            @switch="emit('switch')"
            @refresh-side="refreshRuntime()"
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
        </template>

        <template v-else>
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
            v-if="section === 'general'"
            :config="hostConfig"
            :enabled-known="enabledKnown"
            @patch="(patch: any) => Object.assign(hostConfig, patch)"
          />

          <SitesPanel
            v-else-if="section === 'sites'"
            :sites="ruleView?.sites || []"
            :pref-sites="ruleView?.prefSites || []"
            :options="sites"
            :loaded="sitesLoaded"
            @update:sites="(value: string[]) => patchRule({ sites: value })"
            @update:pref-sites="(value: string[]) => patchRule({ prefSites: value })"
          />

          <RulePanel
            v-else-if="section === 'rule' && ruleView"
            :rule="ruleView"
            :policy-min-interval="checkInfo?.minIntervalMin || 0"
            :site-scope-count="ruleView.sites.length"
            @patch="patchRule"
          />

          <NotifyPanel
            v-else-if="section === 'notify'"
            :notices="notices"
            :loading="noticeLoading"
            :clearing="noticeClearing"
            @clear="clearNotices"
            @reload="loadNotices"
          />

          <LibraryPanel
            v-else-if="section === 'library'"
            :config="hostConfig"
            :validation="validation"
            @patch="(patch: any) => Object.assign(hostConfig, patch)"
          />

          <RuntimePanel
            v-else-if="section === 'runtime'"
            :cache-text="cacheText"
            :check="checkInfo"
            :cleaning="cacheCleaning"
            :loading="runtimeLoading"
            @clean="cleanCache"
            @refresh="refreshRuntime()"
          />

          <AboutPanel
            v-else-if="section === 'about'"
            :version="version"
            :plugin-id="props.pluginId"
            :source-plugin-id="props.sourcePluginId"
          />

          <v-alert v-else type="info" variant="tonal">
            未知栏目：{{ activeSection.title }}
          </v-alert>
        </template>
      </section>

      <v-divider vertical />

      <!-- 右栏：运行概况（挂载后取 /bootstrap，每 15s 轮询，页面不可见时暂停） -->
      <aside class="avh-side">
        <v-card variant="outlined" class="avh-overview">
          <v-card-item>
            <template #prepend>
              <v-icon icon="mdi-gauge" color="primary" />
            </template>
            <v-card-title class="text-subtitle-1">运行概况</v-card-title>
            <v-card-subtitle v-if="updatedAt">更新于 {{ updatedAt }}</v-card-subtitle>
          </v-card-item>

          <v-card-text class="pt-0">
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
              @click="refreshRuntime()"
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
      </aside>
    </div>

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
      @refresh-side="refreshRuntime()"
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
  min-height: 0;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
}

.avh-topbar {
  flex: 0 0 auto;
  padding-inline: 0;
}

.avh-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 顶栏搜索（老 `.searchbox`：输入框 + 紧贴的「搜索」按钮，占位符同款） */
.avh-searchbox {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 1 380px;
  min-width: 200px;
  margin-right: 12px;
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

.avh-body {
  display: flex;
  align-items: stretch;
  min-height: 0;
  padding: 12px;
  gap: 4px;
}

.avh-nav {
  flex: 0 0 200px;
  max-width: 200px;
  overflow-y: auto;
}

.avh-content {
  flex: 1 1 auto;
  min-width: 0;
  overflow: auto;
  padding-inline: 12px;
}

.avh-side {
  flex: 0 0 264px;
  max-width: 264px;
  overflow-y: auto;
}

.avh-overview {
  position: sticky;
  top: 0;
}

@media (max-width: 1100px) {
  .avh-body {
    flex-wrap: wrap;
  }

  .avh-nav,
  .avh-side {
    flex: 1 1 auto;
    max-width: none;
  }
}
</style>
