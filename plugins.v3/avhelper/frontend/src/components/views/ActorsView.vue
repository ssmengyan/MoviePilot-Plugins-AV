<script setup lang="ts">
/**
 * 视图：我的演员（S6 第五个原生化视图）。
 *
 * 对照老实现 `ui/views/actors.js`（`renderActors` / `openActorPicker` / `addFav` /
 * `delFav` / `toggleFav` / `refreshFavButtons` / `openActor` / `filmRow` /
 * `renderActorDetail`）与它的调用方 `ui/app.js`（`render()` 的
 * `if (S.actor && S.view === 'actors')` 分支、`bindUi` 的 `actor-retry` /
 * `picker-retry` / `modal-close` 事件委托、`renderPills`），逐条对齐的是**行为与文案**，
 * DOM 换成 Vuetify 组件：
 *
 * | 老实现 | 这里 |
 * | --- | --- |
 * | **演员详情不是抽屉**：`S.actor` 非空时 `render()` 走 `renderActorDetail(m)`，同一个视图里换内容 | 同一个行为：`actor` 非空 → 本组件画作品史（**没有**改成弹窗/抽屉），顶部仍是 `← 返回` |
 * | `renderActors`：空态 `还没有收藏演员<br><br>` ＋ `➕ 从演员榜挑选` | `EmptyState` 文案逐字一致 + 默认插槽里同一颗按钮 |
 * | 非空：工具条 `共 n 位` ＋ 右侧 `➕ 添加演员`；`.actors` 网格的 `⭐` 卡片 | 同一句话、同一个按钮、同一个网格（卡片本体是 `common/ActorRow.vue`） |
 * | 点卡片 → `openActor(name)`：`S.actor = name; S.view='actors'`，**重置** `S.actorYear`，`#main` 滚回顶部 | 同一顺序：设 `actor` → 清年份 → `loadPage()` → 根元素 `scrollIntoView({block:'start'})`（`#main` 就是壳的内容区） |
 * | `openActorPicker()`：弹窗标题 `从演员榜挑选`、右下 `关闭`；正文按缓存画：加载 `正在抓取演员榜…`／错误 `errHtml(msg,'picker-retry')`／全已收藏 `演员榜里的人都已收藏。`／否则提示 `点 ➕ 加入收藏` + 卡片网格 | `v-dialog`（`attach="body"`，写法照设置台 `SitesPanel`）：标题、关闭按钮、四种正文状态与文案逐字一致 |
 * | `avail = ent.data.filter(a => !findFav(a.name))`：**paint 时过滤一次**，之后加的收藏只把这卡就地改成 `✓ 已收藏`（`tag.className='tag on'`、`cursor:default`、解绑 onclick） | 同一语义：打开弹窗时把过滤后的名单存成**快照** `pickerRows`，加成功后只往 `pickerAdded` 里记名字 → 卡片就地翻成 `✓ 已收藏`（`ActorRow` 的 `favorited`），不整块重建 |
 * | 抓榜失败：正文 `errHtml(r.message \|\| '演员榜抓取失败，请稍后重试')` ＋ `toast('演员榜抓取失败', r.message \|\| '请稍后重试','warn')` | 同一句话进 `ErrorState`；toast 拆成 `t.warning('演员榜抓取失败')` + `t.info(原因)`（宿主 toast 只有单行正文，写法照 S6-4 订阅页） |
 * | `picker-retry` → `delete CACHE['actors']; openActorPicker()`（弹窗不关，就地把正文换成加载态） | `retryRank()`：清掉榜单缓存重抓，弹窗保持打开 |
 * | `addFav(name, zh, avatar)`：已收藏不发请求；成功 `toast('已收藏', name + ' 会出现在「我的演员」里','ok')`；失败 `toast('收藏失败', msg \|\| '请稍后重试','warn')` | 文案逐字一致（拆 `t.success` + `t.info`）；请求本身在 `usePluginStore.addFav` 里（本视图唯一碰的 composable，理由见下） |
 * | `delFav` / `toggleFav`：成功 `已取消收藏`，失败 `取消收藏失败`；`refreshFavButtons()`（详情抽屉里的按钮）不适用 | `usePluginStore.delFav` + 本视图的 `toggleFav`；**抽屉里的那颗按钮属于未迁移的 detail 视图**，不在这里补 |
 * | 加/取消收藏后 `renderPills()`（右栏「收藏演员」计数是本地计数） | `emit('refreshSide')` → 壳重拉 `/bootstrap`（写 S6-4 订阅页同一套）；角标口径仍是 `store.favs` |
 * | `renderActorDetail`：加载态 `正在抓取演员档案与作品史…`；错误 `errHtml(entry.error,'actor-retry')`；两种状态下 `← 返回` 都在 | 同顺序、同文案；重试 = 清 `page:actor:<name>` 缓存后重抓 |
 * | 档案卡：`.profile` 头像 132×132 + `h2`（`名字 / 中文名`）+ `.kv`（`作品/年龄/生日/身高cm/罩杯/出身/IG` + 无条件 `本次返回作品 n 部`）+ `.acts` 三颗按钮 | 同一结构、同一字段顺序；按钮文案 `★ 已收藏`／`☆ 收藏该演员`、`✓ 已订阅新片`(禁用)／`📌 订阅该演员的新片`、`⚡ 检查她的新片` 逐字一致 |
 * | 订阅判定 `S.subs.filter(s => s.type==='actor' && s.name===name)[0]` | `store.subs` 同一条过滤 |
 * | `subActorDialog(name, zh, avatar)`：**弹出规则编辑器** → `POST /subs` → 成功顺手收藏该演员 + `toast('订阅已创建', name,'ok')` + 切到订阅页 | 按 S6-4 订阅页的先例**不做规则编辑器**（规则唯一归属设置台「下载规则」栏）：直接 `store.subscribeNumber(name,'actor')`，先提示一句规则从哪来，成功后仍**顺手收藏**该演员、`t.success('订阅已创建')` + `t.info(name)`；**不切页**（宿主合同里没有"切到数据台某栏"的事件，见下） |
 * | `runCheck(name)`：订阅检查那条 toast 链（正在检查 / 限流 / 完成 / 失败） | 与 S6-4 订阅页**同一段实现**（先提示再请求；限流是业务结果，不是失败），文案一字不改 |
 * | `filmRow(mv,i)`：`.pic`（`--bg` 模糊底 + 竖版 `contain` 封面）+ `.fn` 番号 + `.ftt` 标题（有才画）+ `.fd`（日期 ／ `中字`\|`无中字` ／ `🧲 n` ／ 有 `lib` 才画 `已入库`） | 同一字段、同一顺序；`Thumb variant="film"` 负责 `contain`，模糊底用本地 `--bg` + `::before`（`--bg` 的 URL 转义照抄 `cssUrl`） |
 * | **作品史服务端分页**（老 `#btnMoreFilms`）：首屏 `page=1&limit=30`，`.morebar` 里一颗「加载更多（已显示 n / 共 m 部）」，续拉下一页按 `id|番号` 去重后追加；`hasMore` 为假且不止一页时显示 `已加载全部 n 部` | `loadMoreFilms()` 同一套（页码存进页内缓存，切走只更新缓存不重绘），按钮 `:loading` 转圈 |
 * | 年份收敛：`years.length > 1` 才画 `.filmyears`，按钮 `全部 n`（还有下一页时带 `+`）+ 每年 `2025 6`（`opacity:.65` 的数字）；点击 `S.actorYear=y` | 同（保留 `全部 ` 后面那个空格与弱化数字）；筛选只作用于**已加载**的那几页，`hasMore` 时年份空态会提示「继续加载试试」 |
 * | 作品史接口 `apiGet('/actor', {name, page, limit:30})`（服务端分页；后端 `ACTOR_PAGE=30`、单页硬上限 50） | `api.get('plugin/actor', { params: { name, page, limit: FILM_PAGE } })`（契约 `GET /actor?name=&page=&limit=`，回 `page/limit/total/hasMore`） |
 * | ——（老实现**没有**，2026-10-13 加）「加载全部」 | `loadAllFilms()`：50/页（站点单页上限）、最多连拉 20 页 = 1000 部（对齐 javdb-cli `--all` 的口径）；每拉完一页就写回缓存、列表**当场**变长；在飞时同一颗按钮变「⏸ 停止」。翻页口径与偏移实测见 `ALL_LIMIT` / `ALL_MAX_PAGES` 的注释 |
 * | ——（老实现**没有**，2026-10-13 加）「回到顶部」 | 作品史里挂 `common/BackToTop.vue`：往下滑过 260px 才浮出（不默认显示），点一下平滑回顶；榜单栏挂同一颗 |
 * | 演员榜接口 `apiGet('/actors')` → `r.data.actors` | `api.get('plugin/actors')`，同样认 `{success, actors}` 与 `{success,data:{actors}}` 两种信封 |
 * | 页内缓存 `CACHE['page:actor:'+name]` / `CACHE['actors']`（跨栏目切换仍在，来回看演员不重抓） | 同名的模块级缓存（`Map` + `reactive`），组件卸载/重挂不掉 |
 *
 * 刻意**不做**（老实现也没有，或属于别的视图）：
 * - 不改抽屉/弹窗：老实现就是"同一视图内切换"，这里照做（设计文档 §6.1「番号/演员的跳转与抽屉行为一致」）；
 * - 不做规则编辑器（见上表 `subActorDialog` 一行）；
 * - 不画 `⭐` 之外的收藏态花样：收藏卡片的星标由 `ActorRow` 画（老实现 `.actor .star`）；
 * - 不加轮询：老演员页没有任何定时器。
 *
 * 与老实现的行为差异（都在下面各自位置有注释）：
 * 1. **订阅演员成功后不跳页**：老实现 `S.view='subs'; render()`。宿主合同（`switch` / `close` / `save` /
 *    `layout` / `action`）里没有"把数据台切到某一栏"的事件，要跳页得给壳加一个新事件 —— 本轮不扩合同，
 *    改为 `t.info` 指路「在「订阅」栏里可以看到它」；
 * 2. 老实现"弹窗开着时下面那层先不重绘"是 innerHTML 重建的权宜：Vue 里底层列表是响应式的，
 *    收藏成功会立刻反映到弹窗背后的「我的演员」网格（弹窗盖着，不打架）；
 * 3. **预热（S6-8 补齐）**：老实现里有三条"抢跑"，本视图的处理是 ——
 *    - **作品史详情抢跑**（搬）：老 `renderActorDetail` 末尾的 `prefetchCards(m, PREFETCH_N)`
 *      （前 6 部）与每行 `el.onmouseenter = () => prefetchDetail(num, id)` → 本文件用
 *      共用的 `composables/prefetchDetail.ts` 的预热器（串行 1 条 / 限量 6 / 命中
 *      `detailCache` 跳过），换演员或卸载即 `flush()`（队里没跑的丢掉、在飞的那条作废不落地）；
 *    - **头像预热**（搬）：老 `preload(S.favs.map(a => a.avatar))` → 同名手法的
 *      `warmImage()`，按老语义跳过空地址（见下面那条 watch 的注释）；
 *    - **封面预热**（故意不搬）：老 `preload(list.map(x => x.thumb))`，理由见下面那段注释。
 * 4. 未搬：`actorAvatarOf` 里 `cached('actor:'+name)` 那一档来自搜索弹窗
 *    —— 搜索弹窗已原生化（`detail/SearchDialog.vue`），但那份缓存键属于老 `CACHE`，未搬。
 *
 * **S6-7 收口**：`openFilm()` 已从"一句 t.info"换成 `emit('openMovie', {number, id})`
 * （壳接详情抽屉），并新增 `focusActor` prop 承接"详情/搜索里点演员 → 打开作品史"。
 */
import { computed, nextTick, onUnmounted, reactive, ref, watch } from 'vue'
import ActorRow from '../common/ActorRow.vue'
import BackToTop from '../common/BackToTop.vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import Thumb from '../common/Thumb.vue'
import { errorText, hostToast, type PluginApi } from '../../composables/usePluginApi'
import { cssUrl } from '../../composables/cssUrl'
import { PREFETCH_N, createDetailPrefetcher, warmImage } from '../../composables/prefetchDetail'
import type { PluginStore } from '../../composables/usePluginStore'
import type { FavActor } from '../../composables/storeTypes'

const props = withDefaults(
  defineProps<{
    /** 数据台单一数据源（`Console.vue` 建好后传进来）。 */
    store: PluginStore
    /** 本插件实例 id：给 `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /**
     * 宿主请求器：演员榜（`plugin/actors`）与演员作品史（`plugin/actor`）走它。
     * store 只暴露动作、不暴露底层请求器，而这两条是"页面级缓存 + 直接读形状"的读接口，
     * 与 S6-2/S6-3 用 `api` 补封面同一个理由。
     */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
    /**
     * 从别处（详情抽屉的演员行 / 搜索结果）指定要打开的作品史。
     *
     * 老实现 `openActor(name)`（`ui/views/actors.js`）由 `views/detail.js` 与 `views/search.js`
     * 直接调用，会顺手把 `S.view = 'actors'`、重置年份与展开态，再 `render()`。
     * 壳（`Console.vue`）负责前一半（切栏目 + 每次递增 `:key` 重挂本组件），
     * 后一半在这里：`watch(focusActor, …, {immediate:true})` → `openActor(name)`。
     *
     * 用"每次重挂"而不是"只改 prop"：`focusActor` 相同时（已经在看 A，再点一次 A）prop 不变，
     * watch 不会触发，而老实现会重新画一遍。
     */
    focusActor?: string
  }>(),
  { pluginId: '', api: null, toast: null, focusActor: '' },
)

const emit = defineEmits<{
  /** 收藏 / 取消收藏 / 订阅成功：请壳刷新右栏「运行概况」（收藏演员计数只有 `/bootstrap` 读得到）。 */
  (event: 'refreshSide'): void
  /**
   * 点作品卡片：老 `openMovie(num, id)` 打开「影片详情」抽屉（S6-7 已原生化）。
   * 与发现榜单同一个事件名与载荷，壳统一接成 `DetailDrawer`。
   */
  (event: 'openMovie', payload: { number: string; id: string }): void
}>()

const t = hostToast(props.toast as any)

/**
 * 作品史按需加载（服务端分页）：首屏只抓一页（30 部），点「加载更多」再续拉下一页。
 *
 * 老实现曾是 `apiGet('/actor', {name})` 不带 limit → 后端 `--all` 全量：最多连抓 50 页
 * （20/页）≈ 35 秒，上千部的大牌演员还只能拿到 1000 部。现在与后端 `ACTOR_PAGE` 对齐，
 * 一页一付钱，翻页键即缓存键（`actor:<name>:p<page>:l<limit>`）。
 */
const FILM_PAGE = 30

// ---------- 接口 ----------

/** `GET plugin/actor` 返回的作品（后端 `_movie()`）。`filmRow` 用到的字段一个不少。 */
interface ActorMovie {
  number?: string
  thumb?: string
  title?: string
  date?: string
  cnsub?: boolean
  /** 磁力条数（0 也照画 `🧲 0`）。 */
  magnets?: number
  /** 已入库（Emby 库里命中）时存在；`filmRow` 只判真假。 */
  lib?: unknown
  /** javdb 内部 id（打开详情时回传）。 */
  id?: string
}

/** `GET plugin/actor` 返回的档案（后端 `api_actor` 的 `entity`）。 */
interface ActorEntity {
  name?: string
  zh?: string
  avatar?: string
  videos_count?: number | string
  age?: number | string
  birthday?: string
  height?: number | string
  cup?: string
  birthplace?: string
  instagram?: string
}

interface ActorPageData {
  entity?: ActorEntity
  movies?: ActorMovie[]
  /** 已拉到的页码（后端 `api_actor` 回传；续拉时 +1）。 */
  page?: number
  /** 每页条数（与后端 `ACTOR_PAGE` 一致）。 */
  limit?: number
  /** 站点记录总数（`entity.videos_count`）。 */
  total?: number
  /** 还有下一页。 */
  hasMore?: boolean
}

/** 页内缓存条目（老 `put(key, {data})` / `put(key, {error})` 的同形状）。 */
interface Cached<T> {
  error: string
  data: T
}

/**
 * 演员页缓存：`page:actor:<name>`（老 `CACHE['page:actor:'+name]`）。
 *
 * 放模块级、用 `reactive(new Map())`：老 `CACHE` 是全局对象，切栏目/重挂组件都不掉，
 * 来回看同一个演员不重抓；`reactive` 保证晚到的响应能触发重绘（老实现靠再次 `render()`）。
 */
const pageCache = reactive(new Map<string, Cached<ActorPageData>>())

/** 演员榜缓存（老 `CACHE['actors']`）；`error` 非空表示上次抓失败过。 */
const rankCache: Cached<FavActor[] | null> = { error: '', data: null }

/** 老 `apiGet` 的等价：宿主 axios 抛错与业务 `success:false` 都折成一句话。 */
async function apiGet(
  path: string,
  params?: Record<string, string | number>,
): Promise<{ ok: true; payload: any } | { ok: false; message: string }> {
  const api = props.api
  if (!api || typeof api.get !== 'function') return { ok: false, message: '宿主请求器不可用' }
  try {
    const raw: any = await api.get(`plugin/${path}`, params ? { params } : undefined)
    const payload = raw && typeof raw === 'object' && 'success' in raw && 'data' in raw ? raw.data : raw
    if (payload && typeof payload === 'object' && payload.success === false) {
      return { ok: false, message: String(payload.message || payload.detail || '接口返回失败') }
    }
    return { ok: true, payload }
  } catch (err) {
    return { ok: false, message: errorText(err) }
  }
}

// ---------- 状态 ----------

const rootEl = ref<HTMLElement | null>(null)
/** 老 `S.actor`：非空 = 正在看这个演员的作品史（**同一个视图内切换**，不是抽屉）。 */
const actor = ref('')
/** 老 `S.actorYear`：`''` = 全部年份。 */
const actorYear = ref('')
/** 「加载更多」在飞（老实现只把按钮置灰改字，没有单独状态）。 */
const loadingMore = ref(false)
/** 「重试」转圈（老实现整块重绘，没有单独的 loading 态）。 */
const pageRetrying = ref(false)

/** 筛选栏当前年份（老 `const year = S.actorYear \|\| ''`）。 */
const year = computed(() => actorYear.value)

/** 收藏列表原样取（老实现直接 `S.favs.map(...)`，不过滤、不排序）。 */
const favs = computed<FavActor[]>(() =>
  Array.isArray(props.store.favs.value) ? props.store.favs.value : [],
)

/** 空数组也不画工具条（老实现 `.length ? 列表 : 空态`，两者互斥）。 */
const hasFavs = computed(() => favs.value.length > 0)

/** 老 `findFav(name)`：`S.favs.filter(f => f.name === name)[0] || null`。 */
function findFav(name: string): FavActor | null {
  return favs.value.filter(item => item.name === name)[0] || null
}

/**
 * 老 `actorAvatarOf(name)`：收藏里没有头像时逐个缓存在找。
 * 老实现还有一档 `cached('actor:'+name)`（搜索弹窗的缓存，`views/search.js`，本轮未迁移，见文件头）。
 */
function actorAvatarOf(name: string): string {
  const fav = findFav(name)
  if (fav && fav.avatar) return fav.avatar
  const rank = rankCache.data
  if (rank) {
    const hit = rank.filter(item => item.name === name)[0]
    if (hit && hit.avatar) return hit.avatar
  }
  const page = pageCache.get(`page:actor:${name}`)
  if (page && page.data && page.data.entity && page.data.entity.avatar) return page.data.entity.avatar
  return ''
}

/** 收藏卡片的头像：老实现 `a.avatar || actorAvatarOf(a.name)`。 */
function favAvatar(item: FavActor): string {
  return String(item.avatar || actorAvatarOf(String(item.name || '')))
}

// ---------- 收藏列表 / 作品史：数据 ----------

/** 当前演员页的缓存条目；`null` = 还在抓（老实现 `if (!entry)` 那一支）。 */
const pageEntry = computed<Cached<ActorPageData> | null>(() =>
  actor.value ? pageCache.get(`page:actor:${actor.value}`) || null : null,
)

/** 加载态：有演员名、缓存里还没这条。 */
const pageLoading = computed(() => !!actor.value && !pageEntry.value)

/** 错误态文案（老 `errHtml(entry.error, 'data-act="actor-retry"')`）。 */
const pageError = computed(() => (pageEntry.value ? pageEntry.value.error : ''))

const pageData = computed<ActorPageData>(() => (pageEntry.value ? pageEntry.value.data : {}))
const entity = computed<ActorEntity>(() => pageData.value.entity || {})
const movies = computed<ActorMovie[]>(() =>
  Array.isArray(pageData.value.movies) ? (pageData.value.movies as ActorMovie[]) : [],
)

/** 是否已收藏（作品史里那颗按钮的文案与样式都看它）。 */
const faved = computed(() => !!findFav(actor.value))

/** 该演员的订阅（老 `S.subs.filter(s => s.type==='actor' && s.name===name)[0] || null`）。 */
const sub = computed(
  () =>
    (Array.isArray(props.store.subs.value) ? props.store.subs.value : []).filter(
      item => item.type === 'actor' && item.name === actor.value,
    )[0] || null,
)

/** 年份清单与各年计数：老实现按作品出现顺序收集（**只认 4 位数字前缀**）。 */
const yearInfo = computed(() => {
  const years: string[] = []
  const yearCount: Record<string, number> = {}
  movies.value.forEach(mv => {
    const value = String(mv.date || '').slice(0, 4)
    if (/^\d{4}$/.test(value)) {
      if (!yearCount[value]) {
        yearCount[value] = 0
        years.push(value)
      }
      yearCount[value] += 1
    }
  })
  return { years, yearCount }
})

/** 年份筛选后的作品（老 `movies.filter(mv => String(mv.date||'').slice(0,4) === year)`）。 */
const list = computed<ActorMovie[]>(() =>
  year.value
    ? movies.value.filter(mv => String(mv.date || '').slice(0, 4) === year.value)
    : movies.value,
)

/** 站点还有下一页（后端 `hasMore`）。 */
const hasMore = computed(() => !!pageData.value.hasMore)

/** 站点记录总数：后端没给就退回已加载条数（老 `Number(d.total || 0) || movies.length`）。 */
const totalCount = computed(() => Number(pageData.value.total || 0) || movies.value.length)

/** 「作品史」标题：老实现把已加载数、站点总数与当前年份条数拼在同一行里。 */
const filmsTitle = computed(() => {
  const loaded = `作品史（按发行时间倒序，已加载 ${movies.value.length} 部`
  const site = totalCount.value > movies.value.length ? ` / 站点记录 ${totalCount.value} 部` : ''
  const scope = year.value ? `，${year.value} 年 ${list.value.length} 部` : ''
  return `${loaded}${site}${scope}）`
})

/** 「加载更多」按钮文案（老实现按有没有选年份分两句）。 */
const moreLabel = computed(() =>
  year.value
    ? `继续加载 ${FILM_PAGE} 部（往更早的年份找）`
    : `加载更多（已显示 ${movies.value.length} / 共 ${totalCount.value} 部）`,
)

/** 该年份没作品 / 这位演员没作品 / 已加载的部分里没有（还有下一页，老实现的三元四支）。 */
const filmsEmptyText = computed(() => {
  if (!year.value) return '这位演员暂无作品数据。'
  if (hasMore.value) {
    return `已加载的 ${movies.value.length} 部里没有 ${year.value} 年的作品，继续加载试试。`
  }
  return '该年份没有作品记录。'
})

// ---------- 演员页：加载 / 导航 ----------

/**
 * 抓演员档案与作品史（老 `renderActorDetail` 里那次 `apiGet('/actor')`）。
 *
 * 失败：缓存里写 `{error}`（老 `put(key, {error})`）+ 两条 toast；
 * 成功：写 `{data}`。晚到的响应只影响缓存，界面按 `actor` 是否还停在这个人上自动决定画不画。
 */
async function loadPage(name: string, force = false): Promise<void> {
  const key = `page:actor:${name}`
  if (!force && pageCache.has(key)) return
  const res = await apiGet('actor', { name, page: 1, limit: FILM_PAGE })
  if (!res.ok) {
    pageCache.set(key, { error: res.message || '抓取失败，请稍后重试', data: {} })
    t.warning('演员抓取失败')
    t.info(res.message || '抓取失败，请稍后重试')
    return
  }
  pageCache.set(key, { error: '', data: (res.payload || {}) as ActorPageData })
}

/** 点演员卡片：老 `openActor(name)`（重置年份，页面滚回顶部）。 */
function openActor(name: string): void {
  const target = String(name || '')
  if (!target) return
  actor.value = target
  actorYear.value = ''
  allCapped.value = false        // 换了人，"一次拉满上限"那句提示是上一位的，收掉
  void loadPage(target)
  // 老实现 `const m = $('#main'); if (m) m.scrollTop = 0;` —— 壳的内容区就是滚动容器。
  void nextTick(() => rootEl.value?.scrollIntoView({ block: 'start' }))
}

/** `← 返回`：老 `S.actor = null; render()`（**不**重置年份，下次进别的演员才重置）。 */
function backToList(): void {
  actor.value = ''
}

/** 错误态「重试」：老 `actor-retry` → `delete CACHE['page:actor:'+S.actor]; render()`。 */
async function retryPage(): Promise<void> {
  const name = actor.value
  if (!name) return
  pageRetrying.value = true
  allCapped.value = false        // 重抓回第 1 页，「一次拉满上限」那句提示作废
  try {
    pageCache.delete(`page:actor:${name}`)
    await loadPage(name, true)
  } finally {
    pageRetrying.value = false
  }
}

/** 年份 tab：老 `S.actorYear = b.dataset.y; render()`。 */
function pickYear(value: string): void {
  actorYear.value = value
}

/** 某年份在已加载作品里的条数（老 `yearCountOf`）。 */
function yearCountOf(items: ActorMovie[], target: string): number {
  return items.filter(mv => String(mv.date || '').slice(0, 4) === target).length
}

/**
 * 续拉下一页作品史（老 `#btnMoreFilms`）：追加到已加载列表后面。
 *
 * 按 `id|番号` 去重——翻页期间站点新增作品会让整体位移，不去重就会看到重复卡片。
 * 整块由 Vue 重画，年份筛选跟着已加载的部分走；这一批里没有当前年份的作品时给个提示，
 * 免得看起来像没反应（老实现同样两条 toast）。
 */
async function loadMoreFilms(): Promise<void> {
  const name = actor.value
  const entry = pageEntry.value
  if (!name || !entry || loadingMore.value || allLoading.value) return
  const data = entry.data || {}
  // 页号必须配**同一页尺寸**（服务端偏移分页）：全量拉过之后 limit 是 50，接着就得用 50 翻
  const limit = Number(data.limit) || FILM_PAGE
  const page = (Number(data.page) || 1) + 1
  const before = year.value ? yearCountOf(movies.value, year.value) : 0
  loadingMore.value = true
  try {
    const res = await apiGet('actor', { name, page, limit })
    if (!res.ok) {
      t.warning('加载更多失败')
      t.info(res.message || '请稍后重试')
      return
    }
    const next = (res.payload || {}) as ActorPageData
    // 基准取缓存里那份列表（不是 `movies.value`）：请求在飞时用户可能已经换了演员或返回列表，
    // 那时 `movies.value` 已经是别人的列表，concat 会把两个人的作品混进同一条缓存。
    const base: ActorMovie[] = Array.isArray(data.movies) ? (data.movies as ActorMovie[]) : []
    const seen: Record<string, boolean> = {}
    base.forEach((x: ActorMovie) => {
      seen[`${x.id || ''}|${x.number || ''}`] = true
    })
    const add = (next.movies || []).filter(x => !seen[`${x.id || ''}|${x.number || ''}`])
    data.movies = base.concat(add)
    data.page = page
    data.hasMore = !!next.hasMore
    data.total = next.total || data.total
    data.entity = next.entity || data.entity
    // 换了续拉方式（手动一页页来），"一次拉满上限"那句提示就该收了
    allCapped.value = false
    if (actor.value !== name) return      // 已经切走了：只更新缓存
    if (year.value && yearCountOf(data.movies, year.value) === before) {
      t.warning('继续加载')
      t.info(`这一批没有 ${year.value} 年的作品，已加载 ${data.movies.length} 部`)
    }
  } finally {
    loadingMore.value = false
  }
}

// ---------- 「加载全部」：从最新一部一路拉到最旧一部（2026-10-13 加） ----------

/**
 * 全量模式每页条数 = 站点单页硬上限（后端 `ACTOR_PAGE_MAX = 50`，实测 50 条）。
 *
 * 为什么不沿用首屏那 30：站点是**服务端偏移分页**，`page` 与 `limit` 一起决定取哪一段。
 * 2026-10-13 实测（三上悠亜，站点记录 323 部）：`p1 l30` 正好是 `p1 l50` 的前 30 条，
 * 而 `p2 l50` 从第 51 条开始 —— 拿 `p1 l30` 去接 `p2 l50` 会**丢掉第 31–50 条**。
 * 所以全量一律 50/页、并且从第 1 页重来（首屏那 30 条本来就是它的前 30 条，等于原地加长）。
 */
const ALL_LIMIT = 50

/**
 * 一次「加载全部」最多连拉多少页 = 1000 部。
 *
 * 对齐 javdb-cli 自己 `--all` 的口径（`AllEntityMovies`：上限 50 页 × 20/页，官方注释写明
 * "上千部的大牌演员只能拿到 1000 部"）。不设上限的话，4000+ 部的演员会变成几分钟不停的请求。
 * 触顶不是失败：已拉到的留在界面上，给一句话，再点一次接着拉。
 */
const ALL_MAX_PAGES = 20

/** 「加载全部」在飞 / 用户按了停止（当前这一页回来就收工）。 */
const allLoading = ref(false)
const allStop = ref(false)
/** 本次连拉了第几页（只用于触顶判定）。 */
const allPages = ref(0)
/** 触到一次连拉的上限停下来了（界面补一句"再点一次继续"）。 */
const allCapped = ref(false)

/** 「加载全部」按钮文案：在飞时是进度 + 停止（`⏸` 是实测能画出来的那个，`⏹` 在本机是空白方块）。 */
const allLabel = computed(() => {
  const loaded = movies.value.length
  const total = totalCount.value
  if (allLoading.value) {
    return total > loaded ? `⏸ 停止（已加载 ${loaded} / ${total} 部）` : `⏸ 停止（已加载 ${loaded} 部）`
  }
  if (total > loaded) return `⏬ 加载全部（还有 ${total - loaded} 部）`
  return '⏬ 加载全部'
})

/**
 * 「加载全部」：从第 1 页（或上次停下的下一页）一页页拉到站点说没有为止。
 *
 * 与「加载更多」共用同一份页内缓存（`page:actor:<name>`），于是：
 * - 拉到第几页、每页多少条都记在缓存条目里，切走再回来接着拉，不重头再来；
 * - 每拉完一页就写回缓存 → 列表当场变长（不是等全部拉完才画）；
 * - 切走这位演员就停（`actor.value !== name`），已拉的留在他的缓存条目里，不污染别人的。
 */
async function loadAllFilms(): Promise<void> {
  const name = actor.value
  const entry = pageEntry.value
  if (!name || !entry || loadingMore.value) return
  if (allLoading.value) {
    allStop.value = true                 // 在飞时再点一次 = 停止
    return
  }
  const data = entry.data || {}
  const loadedLimit = Number(data.limit) || FILM_PAGE
  const loadedPage = Number(data.page) || 1
  // 上次已经是全量口径（50/页）就接着下一页拉；否则从第 1 页重来（理由见 ALL_LIMIT）
  const resume = loadedLimit === ALL_LIMIT && loadedPage >= 1 && movies.value.length > 0
  let page = resume ? loadedPage + 1 : 1
  // 基准一律取"现在画出来的那一份"（重来时也一样）：新拉的页与它按 `id|番号` 求并集，
  // 于是**重来的那一瞬间列表不会变短**（先用 30/页拉到 60 部再点全量，头 50 部落地时仍是 60 部）。
  const acc: ActorMovie[] = movies.value.slice()
  const seen: Record<string, boolean> = {}
  acc.forEach(mv => {
    seen[`${mv.id || ''}|${mv.number || ''}`] = true
  })

  let stopped = false
  allLoading.value = true
  allStop.value = false
  allCapped.value = false
  allPages.value = 0
  try {
    for (let i = 0; i < ALL_MAX_PAGES; i++) {
      const res = await apiGet('actor', { name, page, limit: ALL_LIMIT })
      if (!res.ok) {
        t.warning(allPages.value ? '「加载全部」中断' : '「加载全部」失败')
        t.info(res.message || '请稍后重试')
        break
      }
      const next = (res.payload || {}) as ActorPageData
      const items = Array.isArray(next.movies) ? next.movies : []
      items.forEach(mv => {
        const key = `${mv.id || ''}|${mv.number || ''}`
        if (!seen[key]) {
          seen[key] = true
          acc.push(mv)
        }
      })
      // 每页都写回缓存（写的是**这位演员自己**的条目，与此刻在看谁无关）
      data.movies = acc.slice()
      data.limit = ALL_LIMIT
      data.page = page
      data.total = Number(next.total || 0) || data.total
      data.entity = next.entity || data.entity
      data.hasMore = !!next.hasMore
      allPages.value = i + 1
      if (!items.length || !next.hasMore) break     // 站点说没有了：到底了
      if (allStop.value) { stopped = true; break }  // 用户按了停止
      if (actor.value !== name) break               // 切走演员 / 返回列表
      if (allPages.value >= ALL_MAX_PAGES) {
        allCapped.value = true
        break
      }
      page += 1
    }
  } finally {
    allLoading.value = false
    allStop.value = false
  }
  if (actor.value !== name) return
  if (stopped) t.info(`已停止，共加载 ${acc.length} 部`)
  if (allCapped.value) {
    t.info(`已一次拉满 ${ALL_MAX_PAGES * ALL_LIMIT} 部（与 javdb-cli 的 --all 同口径），再点「加载全部」可以继续`)
  }
}

// ---------- 收藏动作 ----------

/** 收藏/取消收藏的 toast 文案（老 `addFav` / `delFav` 那两句 title + 正文）。 */
async function setFav(name: string, zh: string, avatar: string, next: boolean): Promise<boolean> {
  if (next) {
    const res = await props.store.addFav(name, zh, avatar)
    if (!res.ok) {
      t.warning('收藏失败')
      t.info(res.message || '请稍后重试')
      return false
    }
    t.success('已收藏')
    t.info(`${name} 会出现在「我的演员」里`)
    emit('refreshSide')
    return true
  }
  const res = await props.store.delFav(name)
  if (!res.ok) {
    t.warning('取消收藏失败')
    t.info(res.message || '请稍后重试')
    return false
  }
  t.warning('已取消收藏')
  t.info(name)
  emit('refreshSide')
  return true
}

/** 作品史里那颗 `☆/★`：老 `toggleFav(name, e.avatar || '')`。 */
async function toggleFav(): Promise<void> {
  const name = actor.value
  if (!name) return
  const wasFav = !!findFav(name)
  const avatar = String(entity.value.avatar || '') || actorAvatarOf(name)
  await setFav(name, String(entity.value.zh || ''), avatar, !wasFav)
}

/** 订阅该演员的新片（老 `subActorDialog` 剥掉规则编辑器后的那一半）。 */
const subscribing = ref(false)

async function subscribeActor(): Promise<void> {
  const name = actor.value
  if (!name || sub.value || subscribing.value) return
  subscribing.value = true
  // 老实现这里弹的是规则编辑器；规则现在唯一归属设置台「下载规则」栏（S6-4 的先例），先说明一句。
  t.info('按「设置台 → 下载规则」的默认规则订阅该演员的新片')
  try {
    const res = await props.store.subscribeNumber(name, 'actor')
    if (!res.ok) {
      t.warning('订阅失败')
      t.info(res.message || '请稍后重试')
      return
    }
    // 老实现：订阅成功顺手把演员加进收藏（`if (!findFav(name)) addFav(name, zh, avatar)`）。
    if (!findFav(name)) {
      await props.store.addFav(name, String(entity.value.zh || ''), String(entity.value.avatar || ''))
    }
    t.success('订阅已创建')
    t.info(`${name} · 在「订阅」栏里可以看到它`)
    emit('refreshSide')
  } finally {
    subscribing.value = false
  }
}

// ---------- 「检查她的新片」：与 S6-4 订阅页同一段 `runCheck` ----------

/** 请求在飞（按钮转圈并禁用）。 */
const checking = ref(false)

/** 老 `runCheck(name)`：**先**提示正在检查，**再**发请求；限流是业务结果不是失败。 */
async function checkActor(): Promise<void> {
  const name = actor.value
  if (!name || checking.value) return
  checking.value = true
  t.info(`正在检查 ${name}`)
  try {
    const res = await props.store.runCheck(name)
    if (!res.ok) {
      t.warning(`检查失败：${res.message || '请稍后重试'}`)
      return
    }
    if (res.kind === 'limited') {
      t.warning(res.message || '距上次检查不足间隔，已跳过')
    } else {
      t.success('检查完成')
      t.info(res.message || '检查完成')
    }
    emit('refreshSide')
  } finally {
    checking.value = false
  }
}

// ---------- 作品卡片 ----------

/** `.pic` 的内联 `--bg`（有封面才给，与老实现 `mv.thumb ? ' style="--bg:url(...)"' : ''` 一致）。 */
function picStyle(mv: ActorMovie): Record<string, string> | undefined {
  if (!mv.thumb) return undefined
  return { '--bg': `url('${cssUrl(mv.thumb)}')` }
}

/** 行 key：老实现按数组顺序画（`data-i`）；这里用番号 + 下标，避免刷新时行被重建。 */
function filmKey(mv: ActorMovie, index: number): string {
  return `${mv.number || ''}#${index}`
}

/**
 * 点作品卡片：老 `openMovie(num, id)` 打开「影片详情」抽屉。
 * S6-7 之前抽屉还没原生化，这里只给一句 `t.info`；现在把番号与 javdb id 交给壳
 * （事件名与载荷和 `DiscoverView` 完全一致，壳只接一处）。
 */
function openFilm(mv: ActorMovie): void {
  const num = String(mv.number || '')
  if (!num) return
  emit('openMovie', { number: num, id: String(mv.id || '') })
}

// ---------- 详情抢跑 / 头像预热（老 `renderActorDetail` 末尾那三行） ----------

/**
 * 作品史详情的后台抢跑（老 `prefetchCards(m, PREFETCH_N)` ＋ 每行
 * `el.onmouseenter = () => prefetchDetail(num, id)`）。
 *
 * 队列纪律全在 `composables/prefetchDetail.ts`（与发现榜单**同一套**）：
 * 串行 1 条 / 限量 `PREFETCH_N` / 命中 `detailCache` 跳过 / 已在飞不重复发；
 * 这里只负责"什么时候排"和"什么时候取消"。
 *
 * **一份队列一个组件实例**（`createDetailPrefetcher()` 在 `setup` 里建）：
 * 壳用 `:key="actors:${actorNonce}"` 挂本视图（详情抽屉里点演员会 `actorNonce++`），
 * 换演员时是"旧实例卸载 + 新实例挂载"。队列若放模块级，旧实例卸载时的 `flush()`
 * 会把新实例刚排进去的作品史任务一起清掉。
 */
const prefetcher = createDetailPrefetcher(() => props.api)

/** 鼠标进入某一行作品：老 `onmouseenter` 抢跑（点下去时多半已经在路上）。 */
function prefetchFilm(mv: ActorMovie): void {
  prefetcher.enqueue(mv.number, mv.id)
}

/**
 * 作品史列表变化时补一轮抢跑：老实现每次 `renderActorDetail` 末尾都跑一次
 * `prefetchCards(m, PREFETCH_N)`（前 6 部）。这里的 `list` 就是当时铺出来的那批
 * （年份筛选后的全部，抢跑仍只取前 6 部）；切年份 / 续拉下一页会重算 → 重新排一轮，
 * 已在缓存里的那些会被 `enqueue` 静默跳过。
 *
 * 老实现预热的是**全部**铺出来的卡片，这里同样把 `list` 交出去（`enqueueMany` 自己截前 N）。
 */
watch(
  list,
  items => prefetcher.enqueueMany(items, PREFETCH_N),
  { immediate: true },
)

/**
 * 换演员 / 离开视图：把在途与排队的抢跑**作废**。
 *
 * 老实现没有这一步（它靠"缓存按番号存、旧响应落地也无所谓"），但作品史的抢跑是
 * "为当前这个人准备的"：换人之后旧任务既占串行位、又会白起 javdb 子进程。
 * `flush()` 之后队里没跑的丢掉；正在飞的那条回来时会被代数闸门拦下、**不写进 `detailCache`**。
 *
 * 为什么不在 `openActor` / `backToList` 里先调一次：`actor` 的 watch 是 `pre` 刷新的，
 * 这两个函数同步设完 `actor` 就立刻 `loadPage()`（异步），flush 与 `pageCache` 的写入
 * 不在同一时刻，放在 watch 里才和"界面真的换了人"同一拍。
 */
watch(actor, () => prefetcher.flush())
onUnmounted(() => prefetcher.flush())

/**
 * 封面预热：老 `preload(list.map(x => x.thumb))` —— **故意不搬**（任务里允许，理由如下，实测过）。
 *
 * 1. **老实现确实有事可做，但新实现的事已经由 `<Thumb lazy>` 干了**：真机实测
 *    （`?mode=real`，1440×960，某位演员 12 部作品）首屏只看得到前 6 张，后 6 张要滚下去；
 *    老实现把它们全拉一遍，图确实"滚到就有"。新实现每张封面都是 `<Thumb lazy>`，
 *    滚到那一刻才开始取 —— 用户看到的差别是"滚过去会不会白一下"，不是"能不能看"。
 * 2. **会跟详情抢跑抢连接位（这条是决定性的）**：详情预热是**串行 1 条**、每条要起一个
 *    javdb 子进程（老实现注释：不并发压多个子进程），抢跑的全部价值就是"点开详情秒开"；
 *    封面预热会把浏览器对同站的连接位分走。不该为了"滚过去不白一下"去挤"点开要等几秒"。
 * 3. **预热的是原始地址、真正用的可能是代理**：`Thumb` 直连失败会回落到插件 `/img` 代理；
 *    老地址多半带 `images.projectjav.com`（该图床对 Referer 挑剔），直连 403 时预热等于白发一次请求。
 *
 * 真要恢复，就该连"代理地址"一起预热（那需要把 `Thumb` 的回落链也抽成小件），不是照抄一行。
 */

/**
 * 头像预热：老 `renderActors` 末尾的 `preload(S.favs.map(a => a.avatar))`。
 *
 * **与老实现的差异（有意）**：老实现预热的是 `S.favs` 里的原字段；这里预热的是
 * `favAvatar(item)` —— 即画在卡片上的那个地址（老实现要先 `actorAvatarOf` 回落，
 * 收藏里 `avatar` 为空时它画的和预热的根本不是同一个 URL）。空地址照样跳过（老 `preload` 的 `if (u)`）。
 *
 * `watch(…, {immediate:true})` 而不是只在新收藏进来时预热：落回链（收藏 → 演员榜 → 档案页）
 * 是"晚一步才有地址"的，`favAvatar` 变了再补一次，才对得上老实现"每次 `renderActors` 都跑一遍"。
 *
 * 实测备注（`?mode=real`，2026-10-10）：真机 8 位收藏的 `favs[].avatar` **都非空**
 * （各 ~97–98 字符的代理地址），所以这一条在真机上是真的有事可做：
 * 8 条 `new Image()`、8 个头像地址各被请求 1 次（与 `<Thumb>` 的取图去重，没有重复请求）。
 */
watch(
  () => favs.value.map(item => favAvatar(item)).join('\n'),
  () => favs.value.forEach(item => warmImage(favAvatar(item))),
  { immediate: true },
)

// ---------- 演员榜挑选弹窗 ----------

const pickerOpen = ref(false)
const pickerLoading = ref(false)
/** 弹窗正文的错误态（老 `errHtml(ent.error, 'data-act="picker-retry"')`）。 */
const pickerError = ref('')
/**
 * 弹窗里那份**名单快照**：老实现只在 paint 时按 `!findFav()` 过滤一次，
 * 之后加的收藏只把那张卡就地改成 `✓ 已收藏`（不会从弹窗里消失）。
 */
const pickerRows = ref<FavActor[]>([])
/** 本次弹窗里加成功的名字（老实现就地改 DOM；Vue 里改成这份记录驱动 `favorited`）。 */
const pickerAdded = ref<string[]>([])
/** 正在加收藏的名字（防重复点击）。 */
const addingName = ref('')

/** 卡片是否已是收藏态：快照里加过的，或当前收藏列表里已有的（老 `findFav` 判定）。 */
function pickerFaved(name: string): boolean {
  return pickerAdded.value.indexOf(name) >= 0 || !!findFav(name)
}

/** 抓演员榜（老 `openActorPicker` 里那次 `apiGet('/actors')` + `put('actors', …)`）。 */
async function loadRank(force: boolean): Promise<void> {
  if (!force && rankCache.data) {
    pickerRows.value = rankCache.data.slice()
    return
  }
  pickerLoading.value = true
  pickerError.value = ''
  const res = await apiGet('actors')
  pickerLoading.value = false
  if (!res.ok) {
    const message = res.message || '演员榜抓取失败，请稍后重试'
    rankCache.data = null
    rankCache.error = message
    pickerError.value = message
    t.warning('演员榜抓取失败')
    t.info(res.message || '请稍后重试')
    return
  }
  const payload = (res.payload || {}) as Record<string, any>
  const rawList = Array.isArray(payload.actors)
    ? payload.actors
    : Array.isArray(payload.data && payload.data.actors)
      ? payload.data.actors
      : []
  const rankList: FavActor[] = rawList
    .filter((item: any) => item && typeof item === 'object')
    .map((item: any) => ({
      name: String(item.name || ''),
      zh: String(item.zh || ''),
      avatar: String(item.avatar || ''),
    }))
    .filter((item: FavActor) => !!item.name)
  rankCache.error = ''
  rankCache.data = rankList
  // paint 时过滤一次（老 `avail`），把结果当快照用。
  pickerRows.value = rankList.filter(item => !findFav(item.name))
}

/** `➕ 添加演员` / 空态里的 `➕ 从演员榜挑选`：老 `openActorPicker()`。 */
async function openPicker(): Promise<void> {
  pickerOpen.value = true
  pickerAdded.value = []
  await loadRank(false)
}

/** 弹窗里的「重试」：老 `delete CACHE['actors']; openActorPicker()`（弹窗不关，就地把正文换成加载态）。 */
async function retryRank(): Promise<void> {
  rankCache.data = null
  rankCache.error = ''
  pickerAdded.value = []
  await loadRank(true)
}

/** 点挑选卡：老 `addFav(card.dataset.n, zh, av)` + 就地改成 `✓ 已收藏`。 */
async function pickAdd(row: FavActor): Promise<void> {
  const name = String(row.name || '')
  if (!name || pickerFaved(name) || addingName.value) return
  addingName.value = name
  try {
    const ok = await setFav(name, String(row.zh || ''), String(row.avatar || ''), true)
    if (ok) pickerAdded.value = [...pickerAdded.value, name]
  } finally {
    addingName.value = ''
  }
}

// ---------- 外部指定演员（详情抽屉 / 搜索结果 → 壳下传） ----------

/**
 * 老实现 `openActor(name)` 由 `views/detail.js` 与 `views/search.js` 直接调用：重置年份与
 * 展开态、抓作品史、页面滚回顶部。壳负责"切到「我的演员」栏"，这里负责余下的同一段行为。
 *
 * `immediate: true`：壳每次都用新的 `:key` 重挂本组件，`focusActor` 在挂载那一刻就已经有值，
 * 不带 immediate 的话那次 watch 根本不会跑。
 */
watch(
  () => props.focusActor,
  name => {
    if (name) openActor(name)
  },
  { immediate: true },
)
</script>

<template>
  <div ref="rootEl" class="avh-actors-view">
    <!-- 演员作品史：**同一个视图内切换**（老 `S.actor` 非空 → `renderActorDetail`），不是抽屉/弹窗 -->
    <template v-if="actor">
      <div class="avh-actors__toolbar">
        <v-btn variant="outlined" size="small" @click="backToList">← 返回</v-btn>
      </div>

      <div v-if="pageLoading" class="avh-loading">正在抓取演员档案与作品史…</div>

      <ErrorState
        v-else-if="pageError"
        :message="pageError"
        :retrying="pageRetrying"
        @retry="retryPage"
      />

      <template v-else>
        <div class="avh-profile">
          <div class="avh-profile__av">
            <Thumb :src="entity.avatar" :alt="actor" :plugin-id="pluginId" />
          </div>
          <div class="avh-profile__main">
            <h2 class="avh-profile__name">
              {{ entity.name || actor }}
              <span v-if="entity.zh" class="avh-profile__zh">/ {{ entity.zh }}</span>
            </h2>
            <div class="avh-kv">
              <span v-if="entity.videos_count"><b>作品</b> {{ entity.videos_count }}</span>
              <span v-if="entity.age"><b>年龄</b> {{ entity.age }}</span>
              <span v-if="entity.birthday"><b>生日</b> {{ entity.birthday }}</span>
              <span v-if="entity.height"><b>身高</b> {{ entity.height }}cm</span>
              <span v-if="entity.cup"><b>罩杯</b> {{ entity.cup }}</span>
              <span v-if="entity.birthplace"><b>出身</b> {{ entity.birthplace }}</span>
              <span v-if="entity.instagram"><b>IG</b> {{ entity.instagram }}</span>
              <span><b>本次返回作品</b> {{ movies.length }} 部</span>
            </div>
            <div class="avh-acts">
              <v-btn
                :color="faved ? undefined : 'primary'"
                :variant="faved ? 'outlined' : 'flat'"
                size="small"
                @click="toggleFav"
              >{{ faved ? '★ 已收藏' : '☆ 收藏该演员' }}</v-btn>
              <v-btn
                :color="sub ? undefined : 'primary'"
                :variant="sub ? 'outlined' : 'flat'"
                size="small"
                :loading="subscribing"
                :disabled="!!sub || subscribing"
                @click="subscribeActor"
              >{{ sub ? '✓ 已订阅新片' : '📌 订阅该演员的新片' }}</v-btn>
              <v-btn variant="outlined" size="small" :loading="checking" @click="checkActor">
                ⚡ 检查她的新片
              </v-btn>
            </div>
          </div>
        </div>

        <div class="avh-secttl">{{ filmsTitle }}</div>

        <!-- 年份收敛：只有多于一个年份才画（老 `years.length > 1`） -->
        <div v-if="yearInfo.years.length > 1" class="avh-filmyears">
          <!-- 文案与老实现逐字一致：`全部 18`（还有下一页时带一个 `+`），年按钮是 `2025 6` -->
          <button
            type="button"
            :class="{ 'avh-filmyears__on': !year }"
            @click="pickYear('')"
          >全部 {{ movies.length }}{{ hasMore ? '+' : '' }}</button>
          <button
            v-for="y in yearInfo.years"
            :key="y"
            type="button"
            :class="{ 'avh-filmyears__on': year === y }"
            @click="pickYear(y)"
          >{{ y }}<span class="avh-filmyears__n">{{ ' ' + yearInfo.yearCount[y] }}</span></button>
        </div>

        <template v-if="list.length">
          <div class="avh-films">
            <div
              v-for="(mv, index) in list"
              :key="filmKey(mv, index)"
              class="avh-film"
              :title="mv.title || mv.number || ''"
              @click="openFilm(mv)"
              @mouseenter="prefetchFilm(mv)"
            >
              <div class="avh-film__pic" :style="picStyle(mv)">
                <Thumb
                  variant="film"
                  :src="mv.thumb"
                  :alt="mv.number || ''"
                  :plugin-id="pluginId"
                />
              </div>
              <div class="avh-film__ft">
                <div class="avh-film__fn">{{ mv.number || '' }}</div>
                <div v-if="mv.title" class="avh-film__ftt">{{ mv.title }}</div>
                <div class="avh-film__fd">
                  <span>{{ mv.date || '' }}</span>
                  <span class="avh-tag" :class="{ 'avh-tag--on': !!mv.cnsub }">
                    {{ mv.cnsub ? '中字' : '无中字' }}
                  </span>
                  <span>🧲 {{ mv.magnets || 0 }}</span>
                  <span v-if="mv.lib" class="avh-tag avh-tag--lib">已入库</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 加载更多（老 `.morebar`）+ 加载全部（2026-10-13 加）：还有下一页才画 -->
          <div v-if="hasMore" class="avh-morebar">
            <v-btn
              variant="outlined"
              size="small"
              :loading="loadingMore"
              :disabled="allLoading"
              @click="loadMoreFilms"
            >
              {{ moreLabel }}
            </v-btn>
            <!-- 全量拉：一次 50/页、最多 20 页（1000 部）；在飞时这颗按钮就是「停止」 -->
            <v-btn
              :variant="allLoading ? 'outlined' : 'tonal'"
              :color="allLoading ? 'warning' : 'primary'"
              size="small"
              :disabled="loadingMore"
              @click="loadAllFilms"
            >
              {{ allLabel }}
            </v-btn>
          </div>
          <div v-if="allCapped" class="avh-morebar">
            <span class="avh-hint avh-morebar__tip">
              已一次拉满 {{ ALL_MAX_PAGES * ALL_LIMIT }} 部（与 javdb-cli 的 --all 同口径），
              再点一次「加载全部」可以接着往下拉。
            </span>
          </div>
          <div v-else-if="!hasMore && movies.length > FILM_PAGE" class="avh-morebar">
            <span class="avh-hint">已加载全部 {{ movies.length }} 部</span>
          </div>
        </template>

        <EmptyState v-else :text="filmsEmptyText" />
      </template>
    </template>

    <!-- 我的演员：**只显示收藏的**（老 `renderActors`） -->
    <template v-else>
      <template v-if="hasFavs">
        <div class="avh-actors__toolbar">
          <span class="avh-hint">共 {{ favs.length }} 位</span>
          <div class="avh-actors__spacer" />
          <v-btn variant="outlined" size="small" @click="openPicker">➕ 添加演员</v-btn>
        </div>
        <div class="avh-actors">
          <ActorRow
            v-for="item in favs"
            :key="item.name"
            favorited
            :name="String(item.name || '')"
            :zh="item.zh || ''"
            :avatar="favAvatar(item)"
            :plugin-id="pluginId"
            @select="openActor"
          />
        </div>
      </template>

      <EmptyState v-else text="还没有收藏演员">
        <v-btn color="primary" variant="flat" @click="openPicker">➕ 从演员榜挑选</v-btn>
      </EmptyState>
    </template>

    <!-- 从演员榜挑选（老 `openActorPicker` 的弹窗） -->
    <v-dialog v-model="pickerOpen" max-width="880" scrollable attach="body">
      <v-card>
        <v-card-title class="d-flex align-center">从演员榜挑选</v-card-title>
        <v-card-text>
          <div v-if="pickerLoading" class="avh-loading">正在抓取演员榜…</div>

          <ErrorState
            v-else-if="pickerError"
            :message="pickerError"
            :retrying="pickerLoading"
            @retry="retryRank"
          />

          <div v-else-if="!pickerRows.length" class="avh-hint">演员榜里的人都已收藏。</div>

          <template v-else>
            <div class="avh-actorpick__tip avh-hint">点 ➕ 加入收藏</div>
            <div class="avh-actors avh-actors--pick">
              <ActorRow
                v-for="row in pickerRows"
                :key="row.name"
                picker
                :name="String(row.name || '')"
                :zh="row.zh || ''"
                :avatar="row.avatar || ''"
                :plugin-id="pluginId"
                :favorited="pickerFaved(String(row.name || ''))"
                :adding="addingName === String(row.name || '')"
                @add="pickAdd(row)"
              />
            </div>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="error" variant="outlined" @click="pickerOpen = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 回到顶部：只在作品史（长列表）里出现，滚下去才浮出来（见 common/BackToTop.vue） -->
    <BackToTop v-if="actor" />
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.toolbar` / `.hint` / `.spacer` */
.avh-actors__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.avh-hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-actors__spacer {
  flex: 1;
}

/* 对齐 `.loading`：弱化色、居中、上下留白 */
.avh-loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 对齐 `.actors`（挑选弹窗那份按老实现收窄到 120px） */
.avh-actors {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(136px, 1fr));
}

.avh-actors--pick {
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
}

/* 老实现的内联 `margin-bottom:12px` */
.avh-actorpick__tip {
  margin-bottom: 12px;
}

/* 对齐 `.profile`：横向卡片，头像 132×132（12px 圆角，不是圆形） */
.avh-profile {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.avh-profile__av {
  width: 132px;
  height: 132px;
  flex: none;
  overflow: hidden;
  border-radius: 12px;
}

.avh-profile__main {
  flex: 1;
  min-width: 240px;
}

.avh-profile__name {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
}

.avh-profile__zh {
  font-size: 14px;
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 对齐 `.kv`：`作品 12` 这种键值对，键比正文更淡 */
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

/* 对齐 `.acts` */
.avh-acts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

/* 对齐 `.secttl`：12px、弱化色、字距 .4px */
.avh-secttl {
  margin: 20px 0 8px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 对齐 `.filmyears`：胶囊按钮，选中的那颗走主色 */
.avh-filmyears {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 0 0 12px;
}

.avh-filmyears button {
  padding: 3px 11px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  background: rgba(var(--v-theme-on-surface), 0.06);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 999px;
  cursor: pointer;
}

.avh-filmyears__on {
  color: rgb(var(--v-theme-on-primary)) !important;
  background: rgb(var(--v-theme-primary)) !important;
  border-color: rgb(var(--v-theme-primary)) !important;
}

.avh-filmyears__n {
  opacity: 0.65;
}

/* 对齐 `.films` */
.avh-films {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(216px, 1fr));
}

/* 对齐 `.film` */
.avh-film {
  overflow: hidden;
  cursor: pointer;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  transition: 0.15s;
}

.avh-film:hover {
  border-color: rgb(var(--v-theme-primary));
  transform: translateY(-2px);
}

/* 对齐 `.film .pic` + `.pic::before`（同图模糊底，横竖混排也不裁切） */
.avh-film__pic {
  position: relative;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.12);
}

.avh-film__pic::before {
  content: '';
  position: absolute;
  inset: -10px;
  background-image: var(--bg, none);
  background-size: cover;
  background-position: center;
  filter: blur(16px);
  opacity: 0.5;
}

/* 封面本体压在模糊底之上；`variant="film"` 已把 `object-fit` 定成 contain */
.avh-film__pic :deep(.avh-thumb) {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: transparent;
}

.avh-film__ft {
  padding: 8px 10px 10px;
}

.avh-film__fn {
  font-size: 13px;
  font-weight: 700;
}

/* 对齐 `.ftt`：两行截断 */
.avh-film__ftt {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.35;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.avh-film__fd {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* `.tag` / `.tag.on` / `.tag.lib` 的等价样式（老 `app.css` 同名规则；
   `ActorRow` 里那份是 scoped，作用不到作品史的标签上，所以这里再写一份） */
.avh-tag {
  display: inline-block;
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

.avh-tag--lib {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: rgba(var(--v-theme-primary), 0.22);
  color: rgb(var(--v-theme-on-surface));
}

/* 对齐 `.morebar`（现在是两颗按钮：加载更多 / 加载全部） */
.avh-morebar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}

/* 触到一次连拉上限那句提示：独占一行、居中，别把两颗按钮挤变形 */
.avh-morebar__tip {
  flex: 1 1 100%;
  text-align: center;
  line-height: 1.7;
}
</style>
