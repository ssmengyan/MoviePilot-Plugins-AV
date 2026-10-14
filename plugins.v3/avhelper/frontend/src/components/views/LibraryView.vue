<script setup lang="ts">
/**
 * 视图：已入库的番号（2026-10-12 新增，用户诉求见 `docs/AVHelper-已入库列表设计.md`）。
 *
 * 一句话：**把 Emby 库里此刻所有的番号，按「发现榜单」那套卡片墙列出来**。
 *
 * | 项 | 口径 |
 * | --- | --- |
 * | 位置 | 左侧数据台独立一栏「已入库的番号」（排在「下载」之后） |
 * | 内容 | 当前库中已有的番号视频，**不包含已删除的**（后端 `/library` 直读 Emby 索引，文件删了下一轮就不在其中） |
 * | 交互 | 点卡片 = 打开在线详情（与发现榜单同一个抽屉：简介 / 资料 / 预览图 / 磁力 / 长图）； |
 * |      | 卡片上的「▶ 观看」= 直达 Emby（MB）观看地址（`lib.url`，新标签页）； |
 * |      | 已入库的片子进详情页本来就有「在 Emby 中打开 ↗」（0.2.3 就有，本轮不动它） |
 * | 翻页 | 只渲染**前 60 条**，滚到底自动追加下一批（`composables/usePagedList.ts`：纯前端分段渲染，数据仍一次取回） |
 *
 * 与「下载历史」的分工（用户 2026-10-12 重新定义过，别混）：
 * - 这一栏 = **库里现在有什么**（实时，删了就没有）；
 * - 「下载历史」= **本插件下载过什么**（台账，文件删了也还在）。
 * 所以库里那些"本来就有、不是插件下的"片子只出现在这里，不会出现在下载历史里。
 *
 * 数据只有一个来源：`GET plugin/library`（契约 §4）。**不碰 store**：`/bootstrap` 那份快照
 * 里没有库列表，也不该为这一页去给它加字段（`/bootstrap` 有"首屏 0.03 秒"的纪律，
 * 往里塞一次 Emby 全库抓取就破了）。
 *
 * 三条既有纪律（与历史页同一套，别在这里破例）：
 * 1. `api` 是壳（`Console.vue` 的 `bindPluginApi`）已经补好实例 id 的请求器，这里只写
 *    `plugin/library`；再补一次 id 会变成 `plugin/<id>/<id>/library`；
 * 2. 颜色全走 `rgb(var(--v-theme-…))`，不写死深色值；
 * 3. 封面**不发额外网络请求**：`thumb` 由后端从本地「番号 → 封面」索引与 7 天详情缓存里捞，
 *    没有就是没有（卡片画番号占位）。这一页只按发现榜单同一条纪律预热**前 6 张**详情
 *    （`createDetailPrefetcher` 的串行 + 限量），预热回来的详情会顺手把封面写进后端索引，
 *    所以第二趟进来能多出几张图 —— 但绝不为了铺满封面去逐个番号起 javdb 子进程。
 *
 * 列表**翻页**（2026-10-15 加，方案 §2.4 P4）：用户口径是「这个列表没有翻页功能，库里很多内容
 * 都没有这种翻页」—— 早先那句"本机 109 条，一次画完比翻页好用"**已被用户否决**，别再改回去。
 * 现在的口径：数据仍然一次取回（`GET /library` 不动），但**只渲染前 60 条**，滚到底自动追加下一批
 * （`composables/usePagedList.ts`，纯前端分段渲染；末尾哨兵那行同时兼作进度提示）。
 * 先不上虚拟滚动 / 服务端分页的理由见 `usePagedList.ts` 的文件头：卡片墙一屏几十张、量级还在几百，
 * 分段渲染就够；等库里到几千条再上服务端分页 + 虚拟滚动。**筛选 / 排序 / 搜索的语义不受影响**：
 * 这一层只做"前缀切片"，源头数组仍是下面那份**全量过滤结果**。
 *
 * 刻意**不做**：
 * - 不在卡片上做「移除/删除」：这一栏是 Emby 的实时投影，要删片得去 Emby 里删，
 *   插件里给一个"看起来能删"的按钮只会误导（台账那边的「移除记录」是另一回事）；
 * - 不显示磁力/发行日/时长：库索引里没有这些（要抓一遍 javdb 才有），
 *   `NumCard` 的库模式按"有什么画什么"处理（见 `NumCard.vue` 的差异 3）。
 *
 * v4 刮削线（0.7.0）加的**版本角标**（v4.1 §9.2 第 6 条）：同番号多版本时在卡片**右上角**画
 * `中字` / `流出` / `中字流出` / `4K` / `2版本`。`NumCard` 是六栏共用的通用件、不认识
 * `version_tags` / `badge`，所以这里包一层定位盒子（`.avh-library__cell`）把徽标画在卡片角落，
 * **不动通用件**。数据缺字段（老后端）时 `versionBadgeOf()` 返回空串、整颗不渲染。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import EmptyState from '../common/EmptyState.vue'
import ErrorState from '../common/ErrorState.vue'
import NumCard from '../common/NumCard.vue'
import type { CardMovie } from '../common/NumCard.vue'
import { createDetailPrefetcher } from '../../composables/prefetchDetail'
import { usePagedList } from '../../composables/usePagedList'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'

const props = withDefaults(
  defineProps<{
    /** 本插件实例 id：给 `NumCard` → `Thumb` 拼图片代理地址用。 */
    pluginId?: string
    /** 宿主请求器（已补插件 id）：`plugin/library` 与详情预热走它。 */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { pluginId: '', api: null, toast: null },
)

const emit = defineEmits<{
  /** 点卡片：把番号交出去，由壳打开「影片详情」抽屉（与发现榜单同一个事件名与形状）。 */
  (event: 'openMovie', payload: { number: string; id: string }): void
}>()

const t = hostToast(props.toast as any)

/** 端点：契约 §4 的 `GET /library`。 */
const ENDPOINT = 'plugin/library'

/**
 * 每批渲染多少张（用户口径 **60**，与 `usePagedList` 的默认值同数；这里显式写出来，
 * 以后这一栏想调批次只改这一处，别去动通用件的默认值）。
 */
const LIBRARY_PAGE_SIZE = 60

/** 库列表（后端已按入库时间新→旧给好，前端不再排序）。 */
const items = ref<CardMovie[]>([])
/** 后端给的库里总数（过滤只改显示行数，计数仍按全量）。 */
const total = ref(0)
/**
 * 媒体库连上了没有。
 *
 * 后端只在**列表为空**时才带这个字段：空列表可能是"库里真没片"，也可能是"Emby 没连上"
 * （`emby().index()` 静默降级成空索引）。两者给用户的下一步完全不同（一个去看片、
 * 一个去查设置），所以必须分开说，不能让用户对着"库里没有片子"去翻 Emby。
 */
const libraryReady = ref(true)
/** 加载中（首屏与手动刷新都会置上；刷新时列表保留，只把按钮转起来）。 */
const loading = ref(false)
/** 读失败的原因（进 `ErrorState`）。 */
const error = ref('')
/** 是否已经成功读过一次。 */
const loaded = ref(false)

/** 搜索词：番号 / 片名 / 演员，本地过滤。 */
const query = ref('')

/** 过滤后的行。 */
const rows = computed<CardMovie[]>(() => {
  const keyword = String(query.value || '').trim().toLowerCase()
  if (!keyword) return items.value
  return items.value.filter((item) => {
    const haystack = [item.number, item.title, item.actor]
      .map(value => String(value || '').toLowerCase())
      .join(' ')
    return haystack.includes(keyword)
  })
})

/** 是否带过滤条件 —— 决定空态说"库里没有片子"还是"没匹配到"。 */
const filtered = computed(() => !!String(query.value || '').trim())

/**
 * 卡片墙**分段渲染**（2026-10-15 加）：源数组仍是上面那份**全量过滤结果**（`rows`），
 * 这一层只决定"画多少" —— 首屏 60 张，滚到底自动追加下一批（见 `usePagedList.ts`）。
 *
 * 三条边界：
 * 1. **不给后端加 `page`/`limit`**：库列表本来就一次取回，服务端分页留给"到几千条"那一版；
 * 2. **不改筛选/排序/搜索语义**：`rows`（计数、空态判定、详情预热都还用它）一字未动，
 *    这里只拿它的前缀；
 * 3. **换筛选词 = 源数组换身份** → `usePagedList` 自动回到第一批（`shown` 重置为 60），
 *    不会出现"筛出 300 张一口气全画"。
 */
const {
  rows: pagedRows,
  shown: shownRows,
  total: pagedTotal,
  hasMore,
  sentinel,
} = usePagedList(rows, { pageSize: LIBRARY_PAGE_SIZE })

/** 末尾哨兵那行文案：还有下一批就报进度，到底了就说加载完了。 */
const pagedHint = computed(() => (
  hasMore.value
    ? `已显示 ${shownRows.value} / ${pagedTotal.value} 部 · 继续下滑自动加载`
    : `已全部加载（${pagedTotal.value} 部）`
))

/** 工具条那句计数：`共 N 部`；有过滤时补一句「已筛出 M 部」。 */
const summary = computed(() => {
  const all = total.value || items.value.length
  return filtered.value ? `共 ${all} 部 · 筛出 ${rows.value.length} 部` : `共 ${all} 部`
})

/** 详情预热器：本视图一份队列（串行、限量、卸载即 flush，见 `prefetchDetail.ts`）。 */
const prefetcher = createDetailPrefetcher(() => props.api)

/**
 * 读一次库列表。
 *
 * - `fresh` = 手动刷新：多带一个 `fresh=1`，让后端**丢掉 Emby 索引那 5 分钟缓存**重抓
 *   （"我刚在 Emby 里删了这部片，怎么还在"就靠它）；
 * - `notify` = 手动刷新时给一句 toast；首屏与失败重试都是静默的（失败已落在 `ErrorState` 里）；
 * - 失败**不清空**已有列表：网络抖一下不该把用户正在看的墙清成空白。
 */
async function load(fresh = false, notify = false): Promise<void> {
  if (loading.value) return
  loading.value = true
  error.value = ''
  if (notify) t.info('正在读取媒体库…')
  try {
    const client = props.api
    if (!client || typeof client.get !== 'function') throw new Error('宿主 api 不可用')
    const response = await client.get(ENDPOINT, { params: fresh ? { fresh: 1 } : {} })
    const payload: any = unwrap<any>(response)
    if (payload && typeof payload === 'object' && payload.success === false) {
      throw new Error(String(payload.message || '已入库列表读取失败'))
    }
    const list = Array.isArray(payload?.items) ? payload.items : []
    items.value = list as CardMovie[]
    total.value = Number(payload?.total || list.length) || list.length
    // 字段缺省（老后端）时按"连上了"处理：宁可显示"库里没有片子"，也别乱指路去查设置
    libraryReady.value = payload?.libraryReady === undefined ? true : !!payload.libraryReady
    loaded.value = true
    if (notify) t.success(`共 ${total.value} 部`)
  } catch (err) {
    error.value = errorText(err)
    if (notify) t.warning(`已入库列表读取失败：${error.value}`)
  } finally {
    loading.value = false
  }
}

/** 点卡片：交给壳开详情抽屉（在线详情：简介 / 资料 / 预览图 / 磁力 / 长图）。 */
function openCard(movie: CardMovie): void {
  emit('openMovie', { number: String(movie.number || ''), id: String(movie.id || '') })
}

/** 鼠标进入卡片：抢跑一次详情（点下去时多半已经在路上）。 */
function hoverCard(movie: CardMovie): void {
  prefetcher.enqueue(movie.number, movie.id)
}

/** 卡片 key：番号 + 下标（同一番号理论上不会重复，防后端异常数据把 key 撞了）。 */
function cardKey(movie: CardMovie, index: number): string {
  return `${movie.number || ''}#${index}`
}

/**
 * 版本角标（v4.1 §9.2 第 6 条：同番号多版本时在卡片**右上角**画版本徽标，
 * 如 `中字` / `流出` / `中字流出` / `4K` / `2版本`）。
 *
 * 数据三处都认，**缺字段一律什么都不画**（老后端没有这些字段时卡片与以前一模一样）：
 * 1. `badge`（后端算好的成品串，优先）；
 * 2. `version_tags` 数组（`["中字","流出"]` → `中字/流出`）；
 * 3. `version_tags` 字典（契约 §3.1 的键：`is_zh_sub` / `is_uncensored_leak` / `resolution` /
 *    `is_iso` / `is_vr`）。
 * 同一番号有多个实例时（`version_count` / `versions` > 1）追加 `N版本`。
 */
function versionBadgeOf(movie: CardMovie): string {
  const row = movie as Record<string, any>
  const direct = String(row.badge ?? '').trim()
  const labels: string[] = []
  const push = (value: unknown) => {
    const label = String(value ?? '').trim()
    if (label && !labels.includes(label)) labels.push(label)
  }
  if (!direct) {
    const tags = row.version_tags
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

// 列表一变就预热前 6 张（与发现榜单同一个 `PREFETCH_N`）；挂载即读一次。
watch(rows, list => prefetcher.enqueueMany(list), { immediate: true })

onBeforeUnmount(() => {
  // 卸载即作废在途的预热（在飞的那条回来也不会写缓存）
  prefetcher.flush()
})

// 首屏就读：这一栏没有轮询（库只在 Emby 侧变动，没有秒级需求），
// 每次切到本栏壳都会重挂组件（`:key="section"`），所以"进来就是最新的"。
void load(false, false)
</script>

<template>
  <div class="avh-library">
    <div class="avh-library__toolbar">
      <span class="avh-library__hint">媒体库里现在的番号，点卡片看详情、点「▶ 观看」直接播放</span>

      <div class="avh-library__spacer" />

      <v-text-field
        v-model="query"
        class="avh-library__q"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        single-line
        prepend-inner-icon="mdi-magnify"
        placeholder="番号 / 片名 / 演员"
        aria-label="按番号、片名或演员过滤已入库的番号"
      />

      <v-btn variant="outlined" size="small" :loading="loading" @click="load(true, true)">↻ 刷新</v-btn>
    </div>

    <!-- 计数：过滤只改下面的**行数**，总数仍是库里全部 -->
    <div v-if="!error && (loaded || items.length)" class="avh-library__stats">
      <v-chip size="x-small" variant="flat" color="success" label>已入库</v-chip>
      <span class="avh-library__hint">{{ summary }}</span>
    </div>

    <ErrorState
      v-if="error"
      :message="`已入库列表读取失败：${error}`"
      :retrying="loading"
      @retry="load(false, false)"
    />

    <div v-else-if="loading && !items.length" class="avh-library__loading">正在读取媒体库…</div>

    <!-- 媒体库没连上：与"库里真没片"分开说，下一步动作不一样 -->
    <EmptyState
      v-else-if="!libraryReady && !items.length"
      text="没有连上 Emby 媒体库"
      hint="插件默认复用 MoviePilot「设置 → 媒体服务器」里已启用的 Emby；也可以在「设置 → 媒体库」里单独填 host 与 api_key"
    />

    <EmptyState
      v-else-if="!items.length"
      text="媒体库里还没有片子<br>下载并整理入库后，这里会按入库时间列出全部番号"
    />

    <EmptyState
      v-else-if="filtered && !rows.length"
      text="没有匹配的番号"
      hint="试试清空搜索词，或者换个番号 / 演员名"
    />

    <template v-else>
      <div class="avh-library__grid">
        <!--
          卡片右上角的版本角标（v4.1 §9.2-6）：`NumCard` 自己不认识 `version_tags` / `badge`，
          所以包一层定位盒子把徽标画在卡片右上角 —— 不动 `NumCard`（它是六栏共用的通用件）。
          `versionBadgeOf()` 缺字段时返回空串，那颗 `<span>` 整个不渲染（老后端行为不变）。
          列表源是 `pagedRows`（`usePagedList` 的已渲染段，首屏 60 张），**不是**全量的 `rows`。
        -->
        <div
          v-for="(movie, index) in pagedRows"
          :key="cardKey(movie, index)"
          class="avh-library__cell"
        >
          <NumCard
            :movie="movie"
            :plugin-id="pluginId"
            mode="library"
            @select="openCard(movie)"
            @hover="hoverCard(movie)"
          />
          <span v-if="versionBadgeOf(movie)" class="avh-vbadge">{{ versionBadgeOf(movie) }}</span>
        </div>
      </div>

      <!--
        末尾哨兵（`usePagedList` 的 `sentinel`，2026-10-15 加）：
        滚到底自动追加下一批就靠它往上找**真正在滚的那一层**（判定照抄 `common/BackToTop.vue`），
        所以它**必须待在滚动层内部**，不能挪到视图外面去。顺带兼作进度提示。
      -->
      <div ref="sentinel" class="avh-library__more">
        <span class="avh-library__hint">{{ pagedHint }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 工具条：与下载页 / 历史页同款（`.toolbar` + `.hint` + `.spacer`） */
.avh-library__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.avh-library__hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-library__spacer {
  flex: 1;
}

/* 搜索框宽度固定：不跟着输入内容长短伸缩，工具条高度就不会跳（照历史页） */
.avh-library__q {
  width: 220px;
  flex: none;
}

.avh-library__stats {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

/* 与发现榜单同一句「正在抓取…」的位置与字号 */
.avh-library__loading {
  padding: 44px 20px;
  text-align: center;
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 对齐 `.grid`：`repeat(auto-fill,minmax(172px,1fr))`，卡片本体是 `NumCard`（库模式） */
.avh-library__grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(172px, 1fr));
}

/* 卡片定位盒子（版本角标要贴在卡片右上角）：`flex` 列让卡片撑满同一行的高度，观感与原来一致 */
.avh-library__cell {
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 末尾哨兵（`usePagedList` 的 `sentinel`）：只画一行进度提示；滚动到底自动追加靠它定位滚动层 */
.avh-library__more {
  padding: 14px 4px 2px;
  text-align: center;
}

.avh-library__cell :deep(.avh-card) {
  flex: 1 1 auto;
}

/* 版本角标（v4.1 §9.2-6）：右上角、小而不抢眼；没有 version_tags / badge 时整个不渲染 */
.avh-vbadge {
  position: absolute;
  top: 6px;
  right: 6px;
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
</style>
