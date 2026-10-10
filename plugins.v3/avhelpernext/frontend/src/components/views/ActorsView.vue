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
 * | 点卡片 → `openActor(name)`：`S.actor = name; S.view='actors'`，**重置** `S.actorYear` / `S.actorAll`，`#main` 滚回顶部 | 同一顺序：设 `actor` → 清年份/展开态 → `loadPage()` → 根元素 `scrollIntoView({block:'start'})`（`#main` 就是壳的内容区） |
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
 * | `FILM_FOLD = 12`：`fold = !S.actorAll && list.length > 12`，只铺前 12 部；超过 12 部才有 `.morebar`（`展开其余 n 部`／`收起`），收起后 `.secttl` `scrollIntoView({block:'start'})` | 同一条算式、同一句按钮文案、同一个回滚位置（`nextTick` 后滚标题） |
 * | 年份收敛：`years.length > 1` 才画 `.filmyears`，按钮 `全部 n` + 每年 `2025 6`（`opacity:.65` 的数字）；点击 `S.actorYear=y; S.actorAll=false` | 同（保留 `全部 ` 后面那个空格与弱化数字）；切年份同样把展开态重置回折叠 |
 * | 作品史接口 `apiGet('/actor', {name})`（**不带 limit** → 后端 `limit=0` 走 `--all` 全量） | `api.get('plugin/actor', { params: { name, limit: ACTOR_LIMIT } })`，`ACTOR_LIMIT = 0` 与老实现同一条路径（契约 `GET /actor?name=&limit=`） |
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
 * 3. 未搬：`preload()` / `prefetchCards()` / `prefetchDetail()` 三条预热（图片与详情缓存的网络预热，
 *    属于 discover/detail 的机器）；`actorAvatarOf` 里 `cached('actor:'+name)` 那一档来自搜索弹窗
 *    —— 搜索弹窗已原生化（`detail/SearchDialog.vue`），但那份缓存键属于老 `CACHE`，未搬。
 *
 * **S6-7 收口**：`openFilm()` 已从"一句 t.info"换成 `emit('openMovie', {number, id})`
 * （壳接详情抽屉），并新增 `focusActor` prop 承接"详情/搜索里点演员 → 打开作品史"。
 */
import { computed, nextTick, reactive, ref, watch } from 'vue'
import ActorRow from '../common/ActorRow.vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import Thumb from '../common/Thumb.vue'
import { errorText, hostToast, type PluginApi } from '../../composables/usePluginApi'
import { cssUrl } from '../../composables/cssUrl'
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

/** 作品史默认只铺 12 部，多的折起来（老 `FILM_FOLD`，逐字同一个数）。 */
const FILM_FOLD = 12

/**
 * 一次要多少部作品：老实现 `apiGet('/actor', {name:name})` **不带 limit**，
 * 后端 `api_actor(name, limit=0)` 就走 `--all` 全量（`client.py` 的 `actor()`），
 * 再由页面折前 12 部。这里显式写 `limit: 0`，保持同一条路径。
 */
const ACTOR_LIMIT = 0

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
/** 老 `S.actorAll`：`true` = 作品史整段铺开（不折 12 部）。 */
const actorAll = ref(false)
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

/** 折叠判定：老 `const fold = !S.actorAll && list.length > FILM_FOLD`。 */
const fold = computed(() => !actorAll.value && list.value.length > FILM_FOLD)

/** 实际铺出来的作品：折叠时只铺前 12 部。 */
const shown = computed<ActorMovie[]>(() =>
  fold.value ? list.value.slice(0, FILM_FOLD) : list.value,
)

/** 展开/收起按钮文案（老实现那两句，一个字都不改）。 */
const moreLabel = computed(() =>
  fold.value ? `展开其余 ${list.value.length - FILM_FOLD} 部` : '收起',
)

/** 「作品史」标题：老实现把总条数与当前年份条数拼在同一行里。 */
const filmsTitle = computed(() => {
  const total = `作品史（按发行时间倒序，共 ${movies.value.length} 部`
  const scope = year.value ? `，${year.value} 年 ${list.value.length} 部` : ''
  return `${total}${scope}）`
})

/** 该年份没作品 / 这位演员没作品，两句不同的空态（老实现的三元）。 */
const filmsEmptyText = computed(() =>
  year.value ? '该年份没有作品记录。' : '这位演员暂无作品数据。',
)

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
  const res = await apiGet('actor', { name, limit: ACTOR_LIMIT })
  if (!res.ok) {
    pageCache.set(key, { error: res.message || '抓取失败，请稍后重试', data: {} })
    t.warning('演员抓取失败')
    t.info(res.message || '抓取失败，请稍后重试')
    return
  }
  pageCache.set(key, { error: '', data: (res.payload || {}) as ActorPageData })
}

/** 点演员卡片：老 `openActor(name)`（重置年份与展开态，页面滚回顶部）。 */
function openActor(name: string): void {
  const target = String(name || '')
  if (!target) return
  actor.value = target
  actorYear.value = ''
  actorAll.value = false
  void loadPage(target)
  // 老实现 `const m = $('#main'); if (m) m.scrollTop = 0;` —— 壳的内容区就是滚动容器。
  void nextTick(() => rootEl.value?.scrollIntoView({ block: 'start' }))
}

/** `← 返回`：老 `S.actor = null; render()`（**不**重置年份/展开态，下次进别的演员才重置）。 */
function backToList(): void {
  actor.value = ''
}

/** 错误态「重试」：老 `actor-retry` → `delete CACHE['page:actor:'+S.actor]; render()`。 */
async function retryPage(): Promise<void> {
  const name = actor.value
  if (!name) return
  pageRetrying.value = true
  try {
    pageCache.delete(`page:actor:${name}`)
    await loadPage(name, true)
  } finally {
    pageRetrying.value = false
  }
}

/** 年份 tab：老 `S.actorYear = b.dataset.y; S.actorAll = false; render()`。 */
function pickYear(value: string): void {
  actorYear.value = value
  actorAll.value = false
}

/** 展开/收起：老 `#btnMoreFilms`（收起后把「作品史」标题滚回视口顶部）。 */
async function toggleAll(): Promise<void> {
  const expanding = !actorAll.value
  actorAll.value = expanding
  if (expanding) return
  await nextTick()
  const title = rootEl.value?.querySelector('.avh-secttl')
  if (title instanceof HTMLElement) title.scrollIntoView({ block: 'start' })
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
          <!-- 文案与老实现逐字一致：`全部 18`（注意「全部」后面那个空格），年按钮是 `2025 6` -->
          <button
            type="button"
            :class="{ 'avh-filmyears__on': !year }"
            @click="pickYear('')"
          >全部 {{ movies.length }}</button>
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
              v-for="(mv, index) in shown"
              :key="filmKey(mv, index)"
              class="avh-film"
              :title="mv.title || mv.number || ''"
              @click="openFilm(mv)"
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

          <div v-if="list.length > FILM_FOLD" class="avh-morebar">
            <v-btn variant="outlined" size="small" @click="toggleAll">{{ moreLabel }}</v-btn>
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

/* 对齐 `.morebar` */
.avh-morebar {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
