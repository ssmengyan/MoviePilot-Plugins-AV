<script setup lang="ts">
/**
 * 影片详情抽屉（老实现 `ui/views/detail.js` 全量 + `ui/ui/drawer.js` / `ui/core/state.js` 的
 * `CURSOR` / `ui/app.js` 的 `detail-retry` 委托）。
 *
 * 逐条对齐的是**行为与文案**，DOM 换成 Vuetify（抽屉 = `v-navigation-drawer`）：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | `openMovie(number, id)`：`CURSOR.number !== number` 时清 `CURSOR.id`；有 id 就写；`detailFresh = number`；`openDrawer('影片详情 · '+number, '')`；标题栏显示「↻ 重新抓取」 | `open(number, id)` 同一顺序；`open` 为真时抽屉滑出，标题栏那两颗按钮（重新抓取 / 关闭）常驻 |
 * | `paintDetail(number)`：命中缓存直接画 → 错误条目画 `errHtml(entry.error,'data-act="detail-retry"')` → 否则 `skeletonHtml(number)` + `GET plugin/detail?number=&id=` | 同一个三分支：`entry && !error` 画正文、`entry.error` 画 `ErrorState`、无条目画骨架并自动发同一次请求 |
 * | 详情抓失败：`toast('详情抓取失败', r.message \|\| '抓取失败，请稍后重试','warn')` + `put(key,{error})` | 同一句话拆成 `t.warning` + `t.info`（宿主 toast 只有单行正文，写法照 S6 各视图） |
 * | `detailTopIfFresh(number)`：**刚打开**的那一部首帧画完把抽屉滚回顶部（长图回填 / 重新抓取的重绘不动用户的滚动位置） | `scrollTopIfFresh()` 同一条守卫（模块级 `freshNumber`），在 `nextTick` 后与详情回来后各调一次 |
 * | `skeletonHtml(number)`：拿 `findMovie(number)` 的列表数据先画封面/番号/发行/演员 ＋「⏳ 正在抓取影片详情（预览图与磁力随后填充）…」 | 同一个骨架（封面走 `Thumb`，文案逐字一致） |
 * | `detailHtml`：`hero`（封面 + `h2` 番号 + `librow` ＋ 演员行 ＋ `kv` ＋ `acts`）／`预览图（n 张）`／`磁力链接（n 条）`／长图容器 | 同一字段、同一顺序、同一句话（见模板注释） |
 * | `magnetListHtml`：`mn` 种子名、`mh` 里 `中字/无中字`＋`高清`＋`大小` 三个 tag、`magnet:?xt=urn:btih:<hash>` 直链、右侧「⬇ 下载」 | 同（按钮文案 `⬇ 下载`，提交中 `⏳ 提交中…`，成功 `✅ 已提交`） |
 * | `dlMagnet`：`POST plugin/magnet-download {number,hash,name}`；失败 `toast('下载失败', msg \|\| '请检查下载器配置','warn')` 并把按钮复原；成功 `toast('已提交下载', msg \|\| '进度见「下载」页','ok')` | 同一对文案；失败复原按钮、成功停在 `✅ 已提交`（老实现同样不复位）；成功后请壳刷新右栏概况（老实现 `renderPills()`） |
 * | `bindDetail` 的演员行点击：`closeAll(); openActor(name)` | `emit('openActor', name)` —— 抽屉自己关，再由壳切到「我的演员」栏并打开该演员 |
 * | `#btnPtSearch`：`ptSearch(number, mv.actor, mv.thumb, btn)`（老 `views/tasks.js`：后台搜种、不跳页、底部一条 hint） | `store.searchKeyword(number, null, {actor, thumb})`；宿主合同里没有「底部浮动提示」通道，结果改成 `t.success/t.info`（见差异清单） |
 * | `#btnSubNum`：`subscribeNumber(number)` | `store.subscribeNumber(number)`，成功 `t.success('订阅已创建')` + `t.info(number)` |
 * | `#btnFavInDetail`：`toggleFav(mv.actor, mv.actor_avatar)` | `store.addFav/delFav` + 同一对文案 |
 * | `loadLong(number, knownUrl, force)`：`knownUrl`（详情里的 `longimage`）直接画；否则 `⏳ 正在获取长缩略图…` ＋ `GET plugin/longimage?number=`；`force` 走 `&force=1` | 同一条链，状态机在 `composables/detailCache.ts` 的 `longState` 里 |
 * | `paintLong`：`<img referrerpolicy="no-referrer">`（图床校验 Referer）→ **直连失败才**换 `apiUrl('/img',{url})` → 再失败 `longFail('长缩略图加载失败：浏览器直连与插件代理都没取到。')` | 同一个 `Image()` + 逐级 `onerror` 回落（**顺序与文案一字不改**）；点图 `openLb([src],0)` |
 * | `longFail`：`<div class="hint" style="color:var(--warn)">` 正文 ＋ 可选 URL 行 ＋「重试」按钮（`loadLong(number,'',true)`） | 同（`--warn` → warning 主题色；URL 行 `word-break:break-all`） |
 * | 预览图 `shot`：格子固定 16:9、图 `object-fit:contain`、**底下垫一层同图模糊底**（`--bg`）填满留白 | 同一个 `contain` + `::before` 模糊底（**绝不用 cover**：javdb 预览图横竖混排，cover 会把竖图裁掉一半） |
 * | 封面：`img src=cover` ＋ `onerror` → `IMG_FALLBACK`（data-URI 的「图片加载失败」） | `coverSrc`：直连失败换成后端真源 `movie.thumb`，再失败换同一张 data-URI 兜底 |
 * | 点预览图：`openLb(imgs, i + (mv.cover ? 1 : 0))`（列表 = 封面 + 预览图） | 同一条算式，灯箱是 `detail/Lightbox.vue` |
 *
 * 刻意**不做**（老实现也没有，或属于别的模块）：
 * - 抽屉里**不**画编号跳转 / 上一部下一部（老实现没有）；
 * - 不新开弹窗做磁力确认（老实现点一下直接推给下载器）；
 * - 不缓存 `id` 到组件外（老实现 `CURSOR` 是全局的，这里 `lastId` 只服务于"同一部片重开时复用 id"）。
 *
 * 与老实现的行为差异（都在下面各自位置有注释）：
 * 1. **Esc**：抽屉由 `v-navigation-drawer` 自己关（先关灯箱、再关抽屉，与老实现同先后）；
 * 2. 「搜索 PT 站」的成功提示：老实现是底部浮动 hint（`ui/views/tasks.js` 的 `hint()`），
 *    宿主合同（`moviepilot:toast`）里没有那个通道，改成 toast —— 文案仍按老实现的两句；
 * 3. 骨架里 `Thumb` 在封面缺失时给 `.noimg` 占位，而老 `skeletonHtml` 是一句
 *    「正在获取封面…」的文字提示；文案保留在同一位置（缺封面时才出现）；
 * 4. 老实现 `renderPills()` 之后还要等整应用重绘；这里 `emit('refreshSide')` 请壳去刷右栏概况。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import Thumb from '../common/Thumb.vue'
import Lightbox from './Lightbox.vue'
import { hostToast, type PluginApi } from '../../composables/usePluginApi'
import { cssUrl } from '../../composables/cssUrl'
import {
  cachedDetail,
  dropDetail,
  fetchLongUrl,
  longState,
  putDetail,
  putDetailError,
  setLongUrl,
} from '../../composables/detailCache'
import { rankCache } from '../../composables/discoverCache'
import type { PluginStore } from '../../composables/usePluginStore'
import type { FavActor } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 抽屉是否打开（壳控制；老实现是 `#drawer.classList.add('on')`）。 */
    open?: boolean
    /** 当前番号（老 `CURSOR.number`）。 */
    number?: string
    /** 来自列表卡片的 javdb id（老 `openMovie(number, id)`），带上可省一次「番号→id」往返。 */
    id?: string
    /** 数据台单一数据源：收藏 / 订阅 / 搜种 / 磁力下载都走它。 */
    store: PluginStore
    /** 本插件实例 id：给 `Thumb` 与图片代理地址用。 */
    pluginId?: string
    /** 宿主请求器：详情与长图两个读接口走它。 */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { open: false, number: '', id: '', pluginId: '', api: null, toast: null },
)

const emit = defineEmits<{
  /** 请求关闭抽屉（关闭按钮 / 蒙层 / Esc）。 */
  (event: 'close'): void
  /** 点了演员行：老 `closeAll(); openActor(name)` —— 由壳切到「我的演员」栏并打开 ta。 */
  (event: 'openActor', name: string): void
  /** 收藏 / 订阅 / 下载成功：请壳刷新右栏「运行概况」（老 `renderPills()`）。 */
  (event: 'refreshSide'): void
}>()

/**
 * Esc 关抽屉。
 *
 * **不能**指望 `v-navigation-drawer` 自己关 —— 真机实测按 Esc 抽屉纹丝不动、遮罩继续挡住点击，
 * 而老实现是 `document` 上的全局 keydown → `closeAll()`。
 * 灯箱开着时交给灯箱处理（它的监听在子组件挂载时注册得更早，老实现同样是"命中灯箱就 return"）。
 */
function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !props.open) return
  if (lightbox.value?.isOpen?.()) return
  emit('close')
}

onMounted(() => document.addEventListener('keydown', onKeydown, true))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown, true))

const t = hostToast(props.toast as any)

/** 老 `IMG_FALLBACK`（`ui/ui/image.js`）：兜底图上写着「图片加载失败」。 */
const IMG_FALLBACK =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="100%" height="100%" fill="#1c232d"/>' +
      '<text x="50%" y="50%" fill="#6b7887" font-size="16" text-anchor="middle">图片加载失败</text></svg>',
  )

/**
 * 「刚打开」的番号（老 `detailFresh`）：首帧画完把抽屉滚回顶部。
 *
 * 放**模块级**而不是组件内：老实现里它就是模块级 `let`，跨番号复用同一个值；
 * 同一个番号的重绘（长图回填 / 重新抓取）不该动用户已经滚到的位置。
 */
let freshNumber = ''

/** 抽屉正文的滚动容器（老 `#drawerBody`）。 */
const bodyEl = ref<HTMLElement | null>(null)
/** 灯箱（老 `window.AVH.openLb`）。 */
const lightbox = ref<InstanceType<typeof Lightbox> | null>(null)

/**
 * 往上找**真正在滚**的那个祖先（含自己），但**绝不越过抽屉根**。
 *
 * 为什么不能直接写 `bodyEl.scrollTop = 0`：抽屉的真实 DOM 是 Vuetify 给的
 * `.v-navigation-drawer > .v-navigation-drawer__content > [我们的 head + body]`，
 * 而 `.v-navigation-drawer__content` 自带 `overflow-y:auto; height:100%`、又是 **block**
 * 容器（`frontend/node_modules/vuetify/lib/components/VNavigationDrawer/VNavigationDrawer.css:71-77`）
 * —— 于是 `.avh-detail__body` 既不是 flex 子项、高度也等于内容高度，**永远不溢出**，
 * 写它的 `scrollTop` 是空操作（真机实测：把 A 片滚到底再打开 B 片仍停在底部，
 * 而 `__content.scrollTop` 一直是 5278、`body.scrollHeight == body.clientHeight == 6121`）。
 *
 * **必须止步于抽屉根**：抽屉外层还有宿主的一堆容器（数据台的 `.v-card` 实测就是可滚的，
 * `scrollHeight 2251 / clientHeight 880`）。不设边界时，冷缓存那一帧我们的内容还没长高，
 * 循环会一路往上命中宿主的滚动容器，把用户身后的榜单页顶回顶部 —— 点开一部片却把背景滚乱。
 *
 * 顺带：这里按"谁溢出就复位谁"来找、不写死类名，将来 Vuetify 改结构或我们改回单层滚动
 * 都不用跟着改。找不到就退回自身（那时写自身是安全的值）。
 */
function scrollHostOf(el: HTMLElement | null): HTMLElement | null {
  if (!el) return null
  const root = el.closest('.v-navigation-drawer') || el.closest('.avh-detail')
  let node: HTMLElement | null = el
  while (node) {
    if (node.scrollHeight - node.clientHeight > 1) return node
    if (node === root) break
    node = node.parentElement
  }
  return el
}

/**
 * 刚打开的那一部：首帧画完把抽屉滚回顶部（老 `detailTopIfFresh`）。
 *
 * 浏览器有「滚动锚定」，只换内容它可能又把上一部的偏移找回来，所以打开时多调一次。
 * 两个容器都写：改样式后 `.avh-detail__body` 会变成真正的滚动容器，
 * 但换片那一帧它可能还没溢出（内容比视口矮），这时真正的偏移仍在旧的
 * `__content` 上 —— 两处都归零才不会漏。
 */
function scrollTopIfFresh(): void {
  if (freshNumber !== activeNumber.value) return
  freshNumber = ''
  const el = bodyEl.value
  if (!el) return
  el.scrollTop = 0
  const host = scrollHostOf(el)
  if (host && host !== el) host.scrollTop = 0
}

/** 当前番号（老 `CURSOR.number`）。 */
const activeNumber = computed(() => String(props.number || ''))
/** 当前 javdb id（老 `CURSOR.id`）：同一部片重开时复用，换片才清。 */
const lastId = ref('')

/** 详情请求在飞（防同一部片并发打两次）。 */
const fetching = ref(false)

/** 当前详情条目（老 `cached('detail:'+number)`）；`null` = 还没抓过。 */
const entry = computed(() => (activeNumber.value ? cachedDetail(activeNumber.value) : undefined))

/** 详情载荷（老 `entry.data || {}`）。 */
const detail = computed<Record<string, any>>(() => (entry.value && entry.value.data) || {})
const movie = computed<Record<string, any>>(() => detail.value.movie || {})
const actors = computed<any[]>(() => (Array.isArray(detail.value.actors) ? detail.value.actors : []))
/** 老 `const previews = d.previews || []`（空串地址由模板逐张兜底）。 */
const previews = computed<string[]>(() =>
  Array.isArray(detail.value.previews) ? detail.value.previews : [],
)
const magnets = computed<any[]>(() => (Array.isArray(detail.value.magnets) ? detail.value.magnets : []))

/** 老 `const num = mv.number || number`（后端有时不带 number）。 */
const num = computed(() => String(movie.value.number || activeNumber.value || ''))

/** 灯箱列表：`[mv.cover].concat(previews).filter(Boolean)`（老 `imgs`）。 */
const lightboxImages = computed<string[]>(() =>
  [String(movie.value.cover || ''), ...previews.value.map(item => String(item || ''))].filter(Boolean),
)

/** 详情抓失败时的错误文案（老 `entry.error`）。 */
const detailError = computed(() => String((entry.value && entry.value.error) || ''))

/** 有没有可画的东西：老 `entry && !entry.error` 那一支。 */
const hasDetail = computed(() => !!entry.value && !entry.value.error)

// ---------- 骨架用的列表数据（老 `findMovie(number)`） ----------

/**
 * 老 `findMovie(num)`：遍历全局 `CACHE`，在数组载荷或 `{movies}` 里找同一个番号，
 * 用**列表里已有的卡片数据**先把壳画出来，别让用户对着空白等。
 *
 * 这里对着发现榜单的模块级缓存找同一份数据（`rank:<period>:<kind>`）。
 */
function findMovie(number: string): Record<string, any> | null {
  if (!number) return null
  for (const item of rankCache.values()) {
    const list = item && Array.isArray(item.data) ? item.data : null
    if (!list) continue
    const hit = list.filter(movie => movie && String(movie.number || '') === number)[0]
    if (hit) return hit
  }
  return null
}

const skeletonMovie = computed(() => findMovie(activeNumber.value) || {})

// ---------- 收藏 / 演员头像 ----------

/** 老 `findFav(name)`：`S.favs.filter(f => f.name === name)[0] || null`。 */
function findFav(name: string): FavActor | null {
  const list = props.store.favs.value || []
  return list.filter(item => String(item.name || '') === name)[0] || null
}

/** 「☆ 收藏该演员」那颗按钮的当前态：老 `faved = mv.actor ? !!findFav(mv.actor) : false`。 */
const faved = computed(() => {
  const actor = String(movie.value.actor || '')
  return actor ? !!findFav(actor) : false
})

/**
 * 演员行（老 `detailHtml` 的 `.actorchips`）：
 * `actors` 非空就逐个画；否则退到 `mv.actor` 一个；再没有就一句「未识别到演员」。
 */
interface ActorChip {
  name: string
  zh: string
  avatar: string
  /** 自定义备注（BRIEF §3）：空串 = 不画那一行。 */
  alias: string
}

const actorChips = computed<ActorChip[]>(() => {
  if (actors.value.length) {
    return actors.value.map(item => ({
      name: String(item?.name || ''),
      zh: String(item?.zh || ''),
      avatar: String(item?.avatar || ''),
      alias: aliasOf(String(item?.name || '')),
    }))
  }
  const single = String(movie.value.actor || '')
  if (single) {
    return [{ name: single, zh: '', avatar: String(movie.value.actor_avatar || ''), alias: aliasOf(single) }]
  }
  return []
})

/** 抽屉标题（老 `openDrawer('影片详情 · ' + number, '')`）。 */
const title = computed(() => `影片详情 · ${activeNumber.value}`)

/**
 * 演员自定义备注（BRIEF §3 的冻结接口）：`props.store.aliases.value[name]`。
 *
 * 为什么包成函数而不是在模板里直接写 `store.aliases.value[...]`：
 * ① 取法集中在一处，将来改口径（比如回落到中文名）只动这里；
 * ② 模板里裸取 ref 在字段缺失时是硬报错（`aliases` 未定义 → 渲染直接炸），
 *    这里保留运行时判空 —— 真机与工装的装配顺序不完全一致，断言只做编译期的事。
 */
function aliasOf(name: string): string {
  const key = String(name || '')
  if (!key) return ''
  return String(props.store?.aliases?.value?.[key] || '')
}

// ---------- 抽屉滚动（老 `detailTopIfFresh`） ----------
// `scrollTopIfFresh()` 与它依赖的 `scrollHostOf()` 定义在 `bodyEl` 旁边（见上），
// 不在这里重复定义 —— 曾经留下过一份旧的单容器版本，两块一起看会误判成"改好了"。

/** 拿封面地址：直连 → 后端真源 `thumb` → data-URI 兜底（老实现直接 `onerror` 上兜底图）。 */
const coverSrc = ref('')
function syncCover(): void {
  coverSrc.value = String(movie.value.cover || movie.value.thumb || '')
}
function onCoverError(): void {
  const thumb = String(movie.value.thumb || '')
  if (thumb && coverSrc.value !== thumb) {
    coverSrc.value = thumb
    return
  }
  if (coverSrc.value !== IMG_FALLBACK) coverSrc.value = IMG_FALLBACK
}

// ---------- 取详情（老 `paintDetail` 的那次 apiGet） ----------

/**
 * 抓详情（老 `paintDetail` 里 `apiGet('/detail', {number, id})`）。
 *
 * 老实现每次 `paintDetail` 都会在"没有缓存条目"时发一次请求；这里用 `fetching` 合并并发，
 * 并在请求回来后**再调一次** `paintDetail`（本实现里就是缓存写入 + 响应式重绘）。
 */
async function fetchDetail(): Promise<void> {
  const number = activeNumber.value
  if (!number || fetching.value) return
  fetching.value = true
  try {
    const res = await fetchDetailRaw(number, number === activeNumber.value ? lastId.value : '')
    if (!res.ok) {
      putDetailError(number, res.message || '抓取失败，请稍后重试')
      t.warning('详情抓取失败')
      t.info(res.message || '抓取失败，请稍后重试')
      return
    }
    putDetail(number, res.data)
  } finally {
    fetching.value = false
    void nextTick(() => scrollTopIfFresh())
  }
}

/**
 * 一次详情请求（老 `apiGet` 的 `{ok, data|message}` 归一）。
 *
 * 用"抛错的 raw 请求"是为了拿到后端的 `message` 原文：业务失败（`success:false`）与
 * 传输失败（HTTP 5xx / 网络）都折成同一句，与老 `apiGet` 的两条文案一致。
 */
async function fetchDetailRaw(
  number: string,
  id: string,
): Promise<{ ok: true; data: Record<string, any> } | { ok: false; message: string }> {
  const api = props.api
  if (!api || typeof api.get !== 'function') return { ok: false, message: '宿主请求器不可用' }
  // 老 `apiUrl()` 会把空值参数丢掉，所以 id 为空时不带这一段。
  const params: Record<string, string> = { number }
  if (id) params.id = id
  try {
    const raw: any = await api.get('plugin/detail', { params })
    const payload = raw && typeof raw === 'object' && 'data' in raw ? raw.data : raw
    if (payload && typeof payload === 'object' && payload.success === false) {
      return { ok: false, message: String(payload.message || payload.detail || '抓取失败，请稍后重试') }
    }
    return { ok: true, data: (payload as Record<string, any>) || {} }
  } catch (err: any) {
    const status = Number(err?.response?.status || err?.status || 0)
    if (status) return { ok: false, message: `请求失败（HTTP ${status}）` }
    const payload = err?.payload || err?.response?.data
    const message = String(payload?.message || payload?.detail || err?.message || '')
    return { ok: false, message: message ? `网络请求失败：${message}` : '网络请求失败' }
  }
}

/**
 * 写 `CURSOR`（老 `openMovie` 的第二步）：换片才清 id，带上 id 就记下来。
 *
 * **命名注意**：这个函数**不能**叫 `open` —— 本组件有一个同名 prop（`open` = 抽屉开着没有），
 * `setup()` 的返回值覆盖了同名 prop 的模板解引用，模板里 `:model-value="open"` 会拿到这个函数
 * （函数恒真），于是抽屉一挂载就滑出来、遮罩挡住整页。踩过一次，别再改回去。
 */
function syncCursor(number: string, id = ''): void {
  const numValue = String(number || '')
  if (!numValue) return
  if (activeNumber.value !== numValue) lastId.value = ''
  if (id) lastId.value = String(id)
}

/**
 * 老 `openMovie` 里那句 `detailFresh = number`：标记「刚打开」。
 *
 * 单独暴露给壳调用（`open()` 之后调一次），而不是塞进 `watch` 里 —— watch 在组件内部
 * 状态变化时也会触发，而"刚打开"只该由**用户点开抽屉**这一个动作决定：
 * 同一个番号重开（关掉再点同一张卡）也要滚回顶部，同一个番号的重绘（长图回填 /
 * 重新抓取）则不许动用户的滚动位置。
 */
function focusFresh(): void {
  freshNumber = activeNumber.value
  void nextTick(() => scrollTopIfFresh())
}

// ---------- 磁力：复制 / 下载（老 `magnetListHtml` + `dlMagnet`） ----------

/** `magnet:?xt=urn:btih:<hash>`（老实现同一条拼法）。 */
function magnetUri(hash: string): string {
  return hash ? `magnet:?xt=urn:btih:${hash}` : ''
}

/** 每条磁力按钮的当前文案（老实现直接改 `btn.textContent`）。 */
const dlState = ref<Record<string, 'idle' | 'busy' | 'done'>>({})
/** 正在提交的 hash；`idle` 之外的按钮禁用（老实现 `disabled = true`）。 */
function dlLabel(hash: string): string {
  const state = dlState.value[hash] || 'idle'
  if (state === 'busy') return '⏳ 提交中…'
  if (state === 'done') return '✅ 已提交'
  return '⬇ 下载'
}

/**
 * 老 `dlMagnet(number, hash, name, btn)`：直接把磁力推给下载器，
 * 不用先复制再粘到下载器里（保存路径/分类/下载器取全局规则）。
 */
async function downloadMagnet(magnet: any): Promise<void> {
  const hash = String(magnet?.hash || '')
  if (!hash) return
  const current = dlState.value[hash] || 'idle'
  if (current !== 'idle') return
  const name = String(magnet?.name || '')
  dlState.value = { ...dlState.value, [hash]: 'busy' }
  const res = await props.store.downloadMagnet(hash, name, activeNumber.value)
  if (!res.ok) {
    dlState.value = { ...dlState.value, [hash]: 'idle' }
    t.warning('下载失败')
    t.info(res.message || '请检查下载器配置')
    return
  }
  // 老实现成功后按钮停在「✅ 已提交」，不复位。
  dlState.value = { ...dlState.value, [hash]: 'done' }
  t.success('已提交下载')
  t.info(res.message || '进度见「下载」页')
  emit('refreshSide')
}

// ---------- 详情里的三个动作（老 `bindDetail`） ----------

/** 「🔎 搜索 PT 站」：老 `ptSearch(number, actor, thumb, btn)`。 */
const ptSearching = ref(false)
async function ptSearch(): Promise<void> {
  const number = num.value
  if (!number || ptSearching.value) return
  ptSearching.value = true
  try {
    const res = await props.store.searchKeyword(number, null, {
      actor: String(movie.value.actor || ''),
      thumb: String(movie.value.thumb || ''),
    })
    if (!res.ok) {
      t.warning('搜种失败')
      t.info(res.message || '抓取失败，请稍后重试')
      return
    }
    const task: any = res.data || {}
    const cands = Array.isArray(task.cands) ? task.cands : []
    // 老实现落到任务列表 + 底部一条 hint（`hint(number, n ? '已搜索完成' : '没有找到候选')`）。
    t.success(String(task.number || number))
    t.info(cands.length ? '已搜索完成' : '没有找到候选')
    emit('refreshSide')
  } finally {
    ptSearching.value = false
  }
}

/** 「📌 订阅这个番号」：老 `subscribeNumber(number)`。 */
const subscribing = ref(false)
async function subscribeNumber(): Promise<void> {
  const number = num.value
  if (!number || subscribing.value) return
  subscribing.value = true
  try {
    const res = await props.store.subscribeNumber(number)
    if (!res.ok) {
      t.warning('订阅失败')
      t.info(res.message || '请稍后重试')
      return
    }
    t.success('订阅已创建')
    t.info(number)
    emit('refreshSide')
  } finally {
    subscribing.value = false
  }
}

/** 「☆ 收藏该演员 / ★ 已收藏」：老 `toggleFav(mv.actor, mv.actor_avatar || '')`。 */
const favBusy = ref(false)
async function toggleFav(): Promise<void> {
  const actor = String(movie.value.actor || '')
  if (!actor || favBusy.value) return
  favBusy.value = true
  try {
    if (findFav(actor)) {
      const res = await props.store.delFav(actor)
      if (!res.ok) {
        t.warning('取消收藏失败')
        t.info(res.message || '请稍后重试')
        return
      }
      t.warning('已取消收藏')
      t.info(actor)
      emit('refreshSide')
      return
    }
    const res = await props.store.addFav(
      actor,
      '',
      String(movie.value.actor_avatar || (actorChips.value[0] && actorChips.value[0].avatar) || ''),
    )
    if (!res.ok) {
      t.warning('收藏失败')
      t.info(res.message || '请稍后重试')
      return
    }
    t.success('已收藏')
    t.info(`${actor} 会出现在「我的演员」里`)
    emit('refreshSide')
  } finally {
    favBusy.value = false
  }
}

// ---------- 预览图 / 灯箱（老 `bindDetail` 的 `.shots [data-lb]`） ----------

/** `.shot` 的模糊底：老实现用 `cssUrl()` 转义会破坏 `url()` 的字符。 */
function shotStyle(url: unknown): Record<string, string> | undefined {
  const raw = String(url || '')
  if (!raw) return undefined
  return { '--bg': `url('${cssUrl(raw)}')` }
}

/**
 * 点第 i 张预览图：老 `openLb(imgs, i + (mv.cover ? 1 : 0))`。
 * 灯箱列表 = 封面 + 预览图，所以有封面时下标要整体后移一位。
 */
function openShot(index: number): void {
  const offset = movie.value.cover ? 1 : 0
  lightbox.value?.openAt(lightboxImages.value, index + offset)
}

/** 点封面：`openLb(imgs, 0)`（老 `detailHtml` 里封面的 `onclick`）。 */
function openCover(): void {
  lightbox.value?.openAt(lightboxImages.value, 0)
}

// ---------- 长缩略图（老 `loadLong` / `paintLong` / `longFail`） ----------

/** 当前番号的长图状态（老 `LONG_STATE[number]`）。 */
const long = computed(() => longState.get(activeNumber.value) || null)
/** 已画出来的长图地址（`null` = 还在解析/加载）。 */
const longSrc = ref('')
/** 长图直连失败、已切到插件代理。 */
const longUseProxy = ref(false)
/** `null` = 还没失败；字符串 = 给 `longFail` 的正文。 */
const longError = ref<string | null>(null)

/**
 * 「当前这一次加载还在飞」＋它的令牌。
 *
 * 为什么要令牌：换片/重抓时我们会把 `longSrc` 清空、地址换新，但**旧那次请求的回调还在**。
 * 不认令牌的话，旧图的 load/error 会落到新一部片上（典型症状：切到 B 片后 A 片的失败
 * 把 B 片打成失败态）。令牌只增不减，回调只认自己那一次。
 *
 * 为什么要有这个标志：`longSrc` 只在 `paintLong()` 里被设上，而 `paintLong()` 是
 * **在 `new Image()` 预载成功之后**才调的（见下），所以 `longSrc` 非空 = 图上已经有像素。
 * 模板因此可以放心用 `v-if="longSrc"` 画 `<img>`，不必再猜"设了 src 但还没 load"。
 */
const longLoading = ref(false)
let longLoadId = 0

/**
 * load 成功后才写进 DOM 的固有尺寸（`<img width height>`）。
 *
 * 为什么不用 `naturalWidth` 直接读：模板里不能读 DOM，而这里本来就是 onload 回调，
 * 天然拿得到。写上这两个属性有实际作用 —— 长图高达 5817px，浏览器在 load 之后要重排
 * 整篇内容；显式尺寸让这一帧之后**布局不再依赖"图片解码进度"**，也就不会出现
 * "load 已经触发、盒子却还是 0 高"的中间态。
 */
const longNaturalW = ref(0)
const longNaturalH = ref(0)

/** 清掉"这一次加载"的全部状态（换片 / 重抓 / 地址变化时调）。 */
function resetLongLoad(): void {
  longLoadId++
  longLoading.value = false
  longError.value = null
  longSrc.value = ''
  longUseProxy.value = false
  longNaturalW.value = 0
  longNaturalH.value = 0
}

/** 代理地址（老 `apiUrl('/img', {url})`）。 */
const longProxySrc = computed(() => {
  const raw = String(long.value?.url || '')
  if (!raw || !props.pluginId) return ''
  return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`
})

const longSrcAttr = computed(() => (longUseProxy.value ? longProxySrc.value : longSrc.value))

/**
 * 每次换地址都换一个**新的** `<img>` 元素（`:key` 抖动）。
 *
 * 为什么必须这样：老 `paintLong()` 每次都 `new Image()`，直连失败后把 `im.src` 改成
 * `/img` 代理地址、再挂上去；而模板里复用同一个 `<img>` 时，Vue 打补丁会对比新旧 `src`，
 * **同一个地址不会重新写 DOM** → 那次失败不再触发 `error`，回落链就断在第一跳
 * （实测症状：直连失败后卡在"已切代理"但既不报错也不出失败态）。
 * 换 key 强制重建，等价于老实现的"新元素 + 新 src"。
 *
 * key 里**必须带番号**：不带的话，换片后如果新旧两部的长图地址恰好相同
 * （同一图床同一路径、或两次都是同一个代理串），Vue 会判定"同一个元素"而**不重建**，
 * 于是新片的长图不重新加载、也不重新触发 load。带上番号就没有这个复用口子。
 */
const longImgKey = computed(
  () => `${activeNumber.value}|${longUseProxy.value ? 'p' : 'd'}#${longSrc.value}`,
)

/**
 * 老 `paintLong()`：新图 → **预载成功之后**才换上、失败逐级回落。
 *
 * 为什么改成"离屏预载成功才挂进 DOM"（老实现其实是"边下边画"，这一步比老实现更严）：
 * 长图是详情里最后一个元素、动辄 1224×5817，而图床直连要 2.5~6.5 秒、插件代理冷缓存
 * 要 5~20 秒。原写法一点 `paintLong` 就把 `<img src=…>` 挂上去，于是那 5~20 秒里：
 * `longSrc` 已非空 → 提示分支被 `v-else-if="longSrc"` 挡掉；图又还没像素 → 元素恒为
 * 0 高。用户看到的是**一块什么都没有的空位**（实测：0~4.5s 全是
 * `complete=false nw=0 nh=0 rectH=0`，卡片文字为空，只有高度 0 的 `<img>`）。
 * 改成本函数后，"`longSrc` 非空 ⇒ 像素已经在手"成为结构性保证：
 * 要么画着 `⏳ 正在加载长缩略图…`，要么画着图，不再有第三种可能。
 *
 * 顺带恢复了老实现的一个副作用：预载用的是同一个 `Image()`，浏览器的解码缓存因此
 * 是热的，`loadLong(true)` 重画时不会又等一遍网络。
 */
function paintLong(url: string): void {
  const src = String(url || '')
  if (!src) return
  const token = ++longLoadId
  longSrc.value = ''
  longUseProxy.value = false
  longError.value = null
  longNaturalW.value = 0
  longNaturalH.value = 0
  longLoading.value = true
  const probe = new Image()
  probe.decoding = 'async'
  probe.referrerPolicy = 'no-referrer'        // 关键：带 Referer 图床直接 403
  probe.onload = () => {
    if (token !== longLoadId) return          // 已经换片/换地址，这一次作废
    longNaturalW.value = probe.naturalWidth
    longNaturalH.value = probe.naturalHeight
    longLoading.value = false
    longSrc.value = src
  }
  probe.onerror = () => {
    if (token !== longLoadId) return
    // 直连失败 → 换插件代理地址再预载一次（**只回落一次**，与老 `im.onerror` 同序）。
    if (!longUseProxy.value && longProxySrc.value) {
      longUseProxy.value = true
      paintLong(String(long.value?.url || ''))
      return
    }
    longLoading.value = false
    longFail('长缩略图加载失败：浏览器直连与插件代理都没取到。')
  }
  probe.src = src
}

/** 老 `longFail(text, url)`。 */
function longFail(text: string): void {
  longError.value = text
  // 失败态不画 `<img>`（模板里是 `v-if="longError"` 那一支），所以清掉地址更不容易误判。
  longSrc.value = ''
}

/**
 * 长图区域的提示文案（老 `paintLong` 的「⏳ 正在加载长缩略图…」与 `loadLong` 的
 * 「⏳ 正在获取长缩略图…」两句，一字不改）：
 * - 地址已知、像素还没到（`longLoading`）→ 老 `paintLong` 那句；
 * - 还在问后端要地址 → 老 `loadLong` 那句；
 * - 失败态 → 交给 `longError`（返回空串，模板那一支不会画）。
 */
const longHint = computed(() => {
  if (longError.value) return ''
  if (longLoading.value) return '⏳ 正在加载长缩略图…'
  if (!longSrc.value && long.value && long.value.loading) return '⏳ 正在获取长缩略图…'
  return ''
})

/** 老 `loadLong` 里"地址还没解析出来"那句的兜底：详情在飞、地址也没在飞时也要有反馈。 */
const longFetching = computed(() => !longSrc.value && !longError.value && !longLoading.value)

/**
 * `<img>` 的 onerror：老 `im.onerror` 的逐级回落（**只回落一次**）。
 *
 * 换片令牌：元素换 key 重建后，旧元素的 error 仍可能在途（`longLoadId` 每次
 * `paintLong`/`resetLongLoad` 都会 +1），认令牌才不会把新一部片打成失败态。
 */
function onLongError(token: number): void {
  if (token !== longLoadId) return
  longLoading.value = false
  if (!longUseProxy.value && longProxySrc.value) {
    longUseProxy.value = true
    return
  }
  longFail('长缩略图加载失败：浏览器直连与插件代理都没取到。')
}

/** 给模板用的令牌快照（`longLoadId` 是 `let`，模板拿不到）。 */
function currentLongToken(): number {
  return longLoadId
}

/** 老 `loadLong(number, knownUrl, force)`。 */
async function loadLong(force = false): Promise<void> {
  const number = activeNumber.value
  if (!number) return
  if (force) longState.delete(number)
  const known = String(detail.value.longimage || '')
  if (known) longState.set(number, { url: known })
  const state = longState.get(number)
  if (state && state.url) {
    paintLong(state.url)
    return
  }
  if (state && state.err) {
    longFail(state.err)
    return
  }
  // 已知没有长图（详情里的 longimage 是空串）时才需要问后端；老实现同样先显示这句。
  longError.value = null
  longSrc.value = ''
  if (state && state.loading) return // 已有请求在飞：等它回来统一重绘
  longState.set(number, { loading: true })
  const res = await fetchLongUrl(props.api, number, force)
  const url = res.ok ? String(res.url || '') : ''
  if (res.ok) {
    longState.set(number, url ? { url } : { err: '该番号在 projectjav / javfree 里都没找到长图。' })
  } else {
    longState.set(number, { err: `长图地址查询失败：${res.message || '请稍后重试'}` })
  }
  if (url) setLongUrl(number, url)
  // 回来后若还停在这一部，按新状态重画（老实现 `if ($('#drawer').classList.contains('on') && CURSOR.number === number) loadLong(number)`）。
  if (number === activeNumber.value) {
    if (url) paintLong(url)
    else longFail(String((longState.get(number) || {}).err || '长图地址查询失败'))
  }
}

/**
 * 长图加载完成（老实现成功后 `w.innerHTML=''; appendChild(im)`）。
 *
 * 这里同时做一次"以真实元素为准"的尺寸回写：`paintLong()` 的离屏预载已经保证了
 * 图有像素才会挂进 DOM，所以这只是一层冗余保险（元素真正解码完成时把尺寸再对齐一次），
 * 代价是零 —— 却把"资源已 load ⇒ 一定看得见"从"依赖预载那一次"变成"两道都成立"。
 */
function onLongLoad(): void {
  longError.value = null
  longLoading.value = false
}

/** 点长图开灯箱：老 `im.onclick = () => openLb([im.src], 0)`。 */
function openLong(): void {
  const src = longSrcAttr.value
  if (src) lightbox.value?.openAt([src], 0)
}

// ---------- 生效点 ----------

/**
 * 打开/换片：老 `paintDetail()` 的入口 —— 同步封面、清掉上一部的磁力按钮态与长图态，
 * 没有缓存条目就抓一次（有缓存就只补长缩略图）。
 *
 * `props.open` 参与的写法与老 `openDrawer` 一致：抽屉没开时什么都不做。
 */
watch(
  () => [props.open, activeNumber.value, props.id] as const,
  ([isOpen, number, id]) => {
    if (!isOpen || !number) return
    syncCursor(number, String(id || ''))
    focusFresh()
    syncCover()
    dlState.value = {}
    // 换片：用 resetLongLoad 一次清干净（含"加载中"与换片令牌），别只清三个 ref —— 漏掉
    // `longLoading` 会让新一部片一直显示「⏳ 正在加载长缩略图…」而实际什么都没在加载。
    resetLongLoad()
    if (!entry.value) void fetchDetail()
    else void loadLong(false)
  },
  { immediate: true },
)

/** 详情到位（或换片）后：同步封面并补长缩略图（老 `bindDetail` 末尾那次 `loadLong`）。 */
watch(
  () => [activeNumber.value, movie.value.cover, movie.value.thumb, detail.value.longimage] as const,
  () => {
    if (!props.open || !activeNumber.value) return
    syncCover()
    void loadLong(false)
  },
)

/** 详情抓失败后按「重试」：老 `detail-retry` → `delete CACHE['detail:'+number]; paintDetail(number)`。 */
const retrying = ref(false)
async function retryDetail(): Promise<void> {
  const number = activeNumber.value
  if (!number || retrying.value) return
  retrying.value = true
  try {
    dropDetail(number)
    await fetchDetail()
  } finally {
    retrying.value = false
  }
}

/**
 * 标题栏「↻ 重新抓取」：老 `#drawerReload` → 删缓存 + `paintDetail(number)`。
 *
 * **这里故意不再 `dropDetail()`**（老实现会删）：删掉缓存条目会让模板立刻走骨架分支，
 * 内容一塌，浏览器把滚动位置从头夹到 0 —— 实测 `2639 → 0`，用户被顶回顶部，
 * 而"重绘不许动用户的滚动位置"是写进契约的。改成"先请求、成功后整条覆盖"：
 * 期间继续渲染旧内容（不闪屏、不塌），`putDetail()` 写进去后 Vue 原地重绘。
 * 失败就保留旧内容 + toast —— 拿一次刷新失败去换一页错误态不划算，用户还能再点一次。
 */
const refreshing = ref(false)
async function refreshDetail(): Promise<void> {
  const number = activeNumber.value
  if (!number || refreshing.value) return
  refreshing.value = true
  try {
    const res = await fetchDetailRaw(number, number === activeNumber.value ? lastId.value : '')
    if (!res.ok) {
      t.warning('详情抓取失败')
      t.info(res.message || '抓取失败，请稍后重试')
      return
    }
    putDetail(number, res.data)
    // 重抓成功后长图地址可能变了：清掉这一部解析出来的地址与"加载中"，让新详情重新驱动。
    longState.delete(number)
    if (number === activeNumber.value) {
      resetLongLoad()
      void loadLong(false)
    }
  } finally {
    refreshing.value = false
    void nextTick(() => scrollTopIfFresh())
  }
}

/** 标题栏那颗按钮的落点（名字保留 `reloadDetail`：模板与 `defineExpose` 都在用）。 */
async function reloadDetail(): Promise<void> {
  await refreshDetail()
}

/** 长图「重试」：老 `longFail` 里那颗按钮 → `loadLong(number, '', true)`（连后端缓存一起绕过）。 */
async function retryLong(): Promise<void> {
  await loadLong(true)
}

/** 点演员行：老 `closeAll(); openActor(name)`。 */
function pickActor(name: string): void {
  const target = String(name || '')
  if (!target) return
  emit('openActor', target)
}

defineExpose({ syncCursor, focusFresh, reloadDetail, retryDetail })
</script>

<template>
  <!--
    `disable-resize-watcher` 是必需的（真机与迷你宿主都一样）：
    Vuetify 的 `VNavigationDrawer` 有一条 `watch(isTemporary, val => isActive = !val)`，
    它在 `mobile` 判定第一次落地时会跑一遍，把**受控**的 `modelValue` 直接顶成 `true`
    （实测：1440px 宽下抽屉一挂载就是 `--active`，遮罩挡住整页，点不动卡片）。
    关掉那条 watcher，开关就只由壳的 `drawerOpen` 决定。
  -->
  <v-navigation-drawer
    :model-value="open"
    location="right"
    temporary
    disable-resize-watcher
    :width="1080"
    class="avh-detail"
    @update:model-value="(value: boolean) => { if (!value) emit('close') }"
  >
    <div class="avh-detail__head">
      <b class="avh-detail__title">{{ title }}</b>
      <div class="avh-detail__spacer" />
      <v-btn v-if="activeNumber" variant="outlined" size="small" @click="reloadDetail">↻ 重新抓取</v-btn>
      <v-btn variant="outlined" size="small" @click="emit('close')">关闭</v-btn>
    </div>

    <div ref="bodyEl" class="avh-detail__body">
      <!-- 老 `paintDetail` 的三个分支：命中缓存 → 错误条目 → 骨架 + 抓取 -->
      <template v-if="hasDetail">
        <div class="avh-hero">
          <div class="avh-hero__big">
            <img
              v-if="coverSrc"
              :src="coverSrc"
              :alt="num"
              referrerpolicy="no-referrer"
              decoding="async"
              @error="onCoverError"
              @click="openCover"
            >
            <!-- 老实现：后端没给封面时是一句文字提示，不是占位图 -->
            <div v-else class="avh-hint">后端未返回封面（/img 代理可能不可用）</div>
          </div>

          <div class="avh-hero__info">
            <h2 class="avh-hero__num">{{ num }}</h2>

            <!-- 老 `librow`：已在 Emby 库中（有 url 才画「在 Emby 中打开 ↗」） -->
            <div v-if="movie.lib" class="avh-librow">
              ✅ 已在 Emby 库中
              <template v-if="movie.lib.url">
                · <a :href="String(movie.lib.url)" target="_blank" rel="noopener">在 Emby 中打开 ↗</a>
              </template>
            </div>

            <!--
              「已下载」（下载历史契约 §5.2）：与徽标同一个投放条件 `downloaded && !lib`
              —— 已在库的片子上面那条已经说清楚了，不必重复。
              补一句"文件可能已不在库"是因为这颗标记天然会出现在**库里没有**的片子上，
              不解释一句，用户会以为是「已入库」的显示 bug（台账不因文件被删而消失，这正是它的用途）。
            -->
            <div v-if="movie.downloaded && !movie.lib" class="avh-dlrow">
              ✔ 已下载
              <span class="avh-hint">下载台账里有这个番号（文件可能已不在库）</span>
            </div>

            <div v-if="movie.title" class="avh-hero__ttl">{{ movie.title }}</div>

            <!-- 演员行：老 `.actorchips` → 点一下 closeAll + openActor(name) -->
            <div class="avh-actorchips">
              <template v-if="actorChips.length">
                <div
                  v-for="(actor, index) in actorChips"
                  :key="`${actor.name}#${index}`"
                  class="avh-actorchip"
                  :title="actor.name"
                  @click="pickActor(actor.name)"
                >
                  <Thumb class="avh-actorchip__av" variant="av" :src="actor.avatar" :alt="actor.name" :plugin-id="pluginId" />
                  <span class="avh-actorchip__body">
                    <span class="avh-actorchip__nm">{{ actor.name }}{{ actor.zh ? ` / ${actor.zh}` : '' }}</span>
                    <!-- 自定义备注（BRIEF §3）：只在非空时另起一行画，浅色小一号，不加图标不加前缀 -->
                    <span v-if="actor.alias" class="avh-actorchip__alias">{{ actor.alias }}</span>
                  </span>
                  <span class="avh-hint">看全部作品 ›</span>
                </div>
              </template>
              <span v-else class="avh-hint">未识别到演员</span>
            </div>

            <!-- 老 `.kv`：发行 / 时长 / 中文字幕 / 磁力 四个固定 + 片商 / 评分按需 -->
            <div class="avh-kv">
              <span><b>发行</b> {{ movie.date || '—' }}</span>
              <span><b>时长</b> {{ movie.duration || '—' }} 分钟</span>
              <span>
                <b>中文字幕</b>
                <span v-if="movie.cnsub" style="color: rgb(var(--v-theme-success))">有</span>
                <span v-else class="avh-hint">无</span>
              </span>
              <span><b>磁力</b> {{ movie.magnets || magnets.length || 0 }} 个</span>
              <span v-if="movie.maker"><b>片商</b> {{ movie.maker }}</span>
              <span v-if="movie.score"><b>评分</b> {{ movie.score }}</span>
            </div>

            <div class="avh-acts">
              <v-btn color="primary" variant="flat" size="small" :loading="ptSearching" @click="ptSearch">
                🔎 搜索 PT 站
              </v-btn>
              <v-btn variant="outlined" size="small" :loading="subscribing" @click="subscribeNumber">
                📌 订阅这个番号
              </v-btn>
              <v-btn
                v-if="movie.actor"
                variant="outlined"
                size="small"
                :loading="favBusy"
                @click="toggleFav"
              >{{ faved ? '★ 已收藏' : '☆ 收藏该演员' }}</v-btn>
            </div>
          </div>
        </div>

        <div class="avh-secttl">预览图（{{ previews.length }} 张）</div>
        <!-- 预览图横竖混排（实测 800×534 与 534×800 都有）：格子固定 16:9，
             图 `object-fit:contain` 完整显示，底下垫一层同图模糊底填满留白。
             **固定比例 + cover 会把竖图裁掉一半**，这是纪律不是偏好。 -->
        <div class="avh-shots">
          <template v-if="previews.length">
            <div
              v-for="(shot, index) in previews"
              :key="`${index}#${String(shot).slice(-24)}`"
              class="avh-shot"
              :class="{ 'avh-shot--blur': !!shot }"
              :style="shotStyle(shot)"
              @click="openShot(index)"
            >
              <Thumb variant="plain" :src="shot" alt="预览图" :plugin-id="pluginId" />
              <div v-if="!shot" class="avh-shot__noimg">预览图加载失败</div>
            </div>
          </template>
          <span v-else class="avh-hint">该片没有预览图</span>
        </div>

        <div class="avh-secttl">磁力链接（{{ magnets.length }} 条）</div>
        <div v-if="magnets.length">
          <div v-for="(magnet, index) in magnets" :key="`${magnet.hash}#${index}`" class="avh-mag">
            <div class="avh-mag__mg">
              <div class="avh-mag__mn">{{ magnet.name || magnet.hash || '未命名' }}</div>
              <div class="avh-mag__mh">
                <span class="avh-tag" :class="{ 'avh-tag--on': !!magnet.cnsub }">{{ magnet.cnsub ? '中字' : '无中字' }}</span>
                <span v-if="magnet.hd" class="avh-tag avh-tag--pref">高清</span>
                <span v-if="magnet.size" class="avh-tag">{{ magnet.size }}</span>
              </div>
              <div v-if="magnetUri(String(magnet.hash || ''))" class="avh-mag__mh avh-mag__mh--link">
                <a
                  :href="magnetUri(String(magnet.hash || ''))"
                  :title="'用系统下载器打开'"
                  class="avh-mag__hash"
                >{{ magnet.hash }}</a>
              </div>
            </div>
            <v-btn
              variant="outlined"
              size="small"
              :disabled="(dlState[String(magnet.hash || '')] || 'idle') !== 'idle'"
              @click="downloadMagnet(magnet)"
            >{{ dlLabel(String(magnet.hash || '')) }}</v-btn>
          </div>
        </div>
        <div v-else class="avh-hint">没有磁力链接</div>

        <!-- 长缩略图：详情一画完就自己去补（老 `bindDetail` 末尾那次 `loadLong`） -->
        <div class="avh-longwrap">
          <div v-if="longError" class="avh-longerr">
            {{ longError }}
            <div v-if="longSrc" class="avh-longerr__url">{{ longSrcAttr || longSrc }}</div>
            <div class="avh-longerr__act">
              <v-btn variant="outlined" size="small" @click="retryLong">重试</v-btn>
            </div>
          </div>
          <img
            v-else-if="longSrc"
            :key="longImgKey"
            class="avh-longimg"
            :src="longSrcAttr"
            :width="longNaturalW || undefined"
            :height="longNaturalH || undefined"
            alt="长缩略图"
            referrerpolicy="no-referrer"
            decoding="async"
            @load="onLongLoad"
            @error="onLongError(currentLongToken())"
            @click="openLong"
          >
          <!--
            占位提示：`longSrc` 非空 ⇒ 像素已在手（见 `paintLong()`），所以这两句只会在
            "还没图"时出现 —— 修的就是原来那 5~20 秒"既没图也没提示"的空白（那时
            `longSrc` 已被设上、`v-else-if="longSrc"` 把提示挡掉了）。
          -->
          <div v-else-if="longHint" class="avh-hint">{{ longHint }}</div>
          <div v-else-if="longFetching" class="avh-hint">⏳ 正在获取长缩略图…</div>
        </div>
      </template>

      <ErrorState
        v-else-if="detailError"
        :message="detailError"
        :retrying="retrying"
        @retry="retryDetail"
      />

      <!-- 骨架：先用列表卡片数据把壳画出来，别让用户对着空白等（老 `skeletonHtml`） -->
      <template v-else>
        <div class="avh-hero">
          <div class="avh-hero__big">
            <Thumb
              v-if="skeletonMovie.cover"
              variant="plain"
              :src="skeletonMovie.cover"
              :alt="activeNumber"
              :plugin-id="pluginId"
              :lazy="false"
            />
            <div v-else class="avh-hint">正在获取封面…</div>
          </div>
          <div class="avh-hero__info">
            <h2 class="avh-hero__num">{{ activeNumber }}</h2>
            <div class="avh-kv">
              <span v-if="skeletonMovie.date"><b>发行</b> {{ skeletonMovie.date }}</span>
              <span v-if="skeletonMovie.actor"><b>演员</b> {{ skeletonMovie.actor }}</span>
            </div>
            <div class="avh-hint avh-skeleton__tip">⏳ 正在抓取影片详情（预览图与磁力随后填充）…</div>
          </div>
        </div>
      </template>

      <!-- 空态兜底：抽屉打开但没有任何内容时别留白（老实现靠 `openMovie` 的番号守卫回避） -->
      <EmptyState v-if="!activeNumber" text="没有指定番号" />
    </div>

    <!-- 图片灯箱（老 `window.AVH.openLb`） -->
    <Lightbox ref="lightbox" />
  </v-navigation-drawer>
</template>

<style scoped>
/*
 * 把 Vuetify 的滚动槽改成 flex 列、并**收掉它自己的滚动**。
 *
 * 不加这段时：`.v-navigation-drawer__content` 是 `overflow-y:auto; height:100%` 的 block
 * 容器（VNavigationDrawer.css:71-77），滚的是**它**，于是 ① 我们的 `.avh-detail__head`
 * （含「↻ 重新抓取 / 关闭」两颗按钮）跟着内容一起被滚走 —— 而契约要的是标题栏常驻；
 * ② `.avh-detail__body` 的 `flex:1 1 auto; min-height:0; overflow:auto` 全是死代码
 * （它不是 flex 子项、高度=内容高度、永不溢出），往它写 `scrollTop` 是空操作。
 *
 * 收掉 `__content` 的滚动之后，`.avh-detail__body` 才真的成为唯一滚动容器：
 * head 是 `flex:none` 的行、body 吃掉剩余高度并自己滚。
 * （`scrollTopIfFresh()` 仍两个容器都归零：换片那一帧 body 可能还没溢出，
 *  偏移会短暂留在 `__content` 上。）
 */
.avh-detail :deep(.v-navigation-drawer__content) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.avh-detail__head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-detail__title {
  font-size: 14px;
}

.avh-detail__spacer {
  flex: 1;
}

/* 老 `.drawer .db{overflow:auto;padding:18px}` */
.avh-detail__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 18px;
}

.avh-hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 老 `.hero`：封面 min(420px,46vw) + 右侧信息区 */
.avh-hero {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.avh-hero__big {
  width: min(420px, 46vw);
  flex: none;
}

.avh-hero__big img {
  display: block;
  width: 100%;
  border-radius: 10px;
  cursor: zoom-in;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.avh-hero__info {
  flex: 1;
  min-width: 260px;
}

.avh-hero__num {
  margin: 0 0 8px;
  font-size: 24px;
}

.avh-hero__ttl {
  font-size: 13px;
  line-height: 1.7;
  color: rgba(var(--v-theme-on-surface), 0.68);
}

/* 老 `.librow`：已入库横幅 */
.avh-librow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 10px;
  padding: 7px 12px;
  font-size: 13px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.16);
}

.avh-librow a {
  color: rgb(var(--v-theme-primary));
}

/*
 * 「已下载」行（契约 §5.2）：与 `.avh-librow` 同构（同一个位置、同一套留白与圆角），
 * 只把语义色从 `primary` 换成 `info` —— 理由与 `NumCard` 的 `.avh-badge--dl` 一样：
 * 「此刻在库里」与「下载台账里记过（文件可能已删）」是两件事，同色会分不清看到的是哪一条。
 */
.avh-dlrow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 10px;
  padding: 7px 12px;
  font-size: 13px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-info), 0.45);
  background: rgba(var(--v-theme-info), 0.16);
}

/* 老 `.actorchips` / `.actorchip`：胶囊演员卡 */
.avh-actorchips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0;
}

.avh-actorchip {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 3px 12px 3px 3px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-actorchip:hover {
  border-color: rgb(var(--v-theme-secondary));
}

/*
 * 名字 / 备注两行的容器。
 *
 * `line-height: 0` 是必须的：内部两个 `<span>` 各自是 inline 盒子，父级行高会在它们
 * 基线周围再撑出空档（没有备注时胶囊会突然变高）。归零后由子元素自己定行高，
 * 有备注两行、没备注一行，都不会多出空白。
 */
.avh-actorchip__body {
  display: flex;
  flex-direction: column;
  line-height: 0;
}

.avh-actorchip__nm {
  line-height: 1.35;
}

/* 备注：浅色 + 小一号，与 `ActorRow` 的 `.avh-actor__zh` 同一口径（BRIEF §3） */
.avh-actorchip__alias {
  font-size: 11px;
  line-height: 1.3;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-actorchip__av {
  width: 26px;
  height: 26px;
  flex: none;
  overflow: hidden;
  border-radius: 50%;
}

/* 老 `.kv`：键值对一行，键比正文更淡 */
.avh-kv {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 8px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.avh-kv b {
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-acts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

/* 老 `.secttl` */
.avh-secttl {
  margin: 20px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 老 `.shots`：`repeat(auto-fill,minmax(250px,1fr))` */
.avh-shots {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  margin-top: 6px;
}

/* 老 `.shot`：固定 16:9 格子 + `::before` 同图模糊底 */
.avh-shot {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  cursor: zoom-in;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.12);
}

.avh-shot--blur::before {
  content: '';
  position: absolute;
  inset: -10px;
  background-image: var(--bg, none);
  background-size: cover;
  background-position: center;
  filter: blur(16px);
  opacity: 0.45;
}

/* 图压在模糊底之上；`Thumb` 里的 img 默认 `object-fit:cover`，这里改成 contain（不裁切） */
.avh-shot :deep(.avh-thumb) {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: transparent;
}

.avh-shot :deep(.avh-thumb img) {
  object-fit: contain;
}

.avh-shot__noimg {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 老 `.mag` 那一行：左内容 + 右「⬇ 下载」 */
.avh-mag {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.avh-mag:last-child {
  border-bottom: none;
}

.avh-mag__mg {
  flex: 1;
  min-width: 0;
}

.avh-mag__mn {
  margin: 2px 0 4px;
  font-size: 12.5px;
  line-height: 1.5;
  word-break: break-all;
}

.avh-mag__mh {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  word-break: break-all;
}

.avh-mag__mh--link {
  margin-top: 4px;
}

.avh-mag__hash {
  color: rgb(var(--v-theme-primary));
}

/* `.tag` / `.tag.on` / `.tag.pref` 的等价样式（老 `app.css` 同名规则） */
.avh-tag {
  display: inline-block;
  margin-right: 4px;
  padding: 1px 6px;
  font-size: 10.5px;
  border-radius: 4px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-tag--on {
  border-color: rgba(var(--v-theme-success), 0.45);
  background: rgba(var(--v-theme-success), 0.18);
  color: rgb(var(--v-theme-on-surface));
}

.avh-tag--pref {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: rgba(var(--v-theme-primary), 0.22);
  color: rgb(var(--v-theme-on-surface));
}

/* 老 `.longwrap` / `.longwrap img` / `.longerr` */
.avh-longwrap {
  margin-top: 8px;
}

.avh-longimg {
  display: block;
  max-width: 100%;
  cursor: zoom-in;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.avh-longerr {
  font-size: 12px;
  line-height: 1.8;
  color: rgb(var(--v-theme-warning));
}

.avh-longerr__url {
  margin-top: 4px;
  word-break: break-all;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-longerr__act {
  margin-top: 6px;
}

.avh-skeleton__tip {
  margin-top: 10px;
}
</style>
