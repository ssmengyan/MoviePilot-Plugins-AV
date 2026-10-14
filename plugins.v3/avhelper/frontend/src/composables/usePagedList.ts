/**
 * 纯前端「分段渲染」列表（滚到底翻页）：**数据一次取回，只画前 N 条，滚到底自动追加下一批**。
 *
 * 为什么有它（2026-10-15，方案 §2.4 P4）：用户明确抱怨过列表没有翻页
 * （原话要义：「这个列表没有翻页功能，库里很多内容都没有这种翻页」）。
 * 落点：已入库列表（本轮）、收藏演员与下载历史（后续同样接这个件）。
 *
 * | 项 | 口径 |
 * | --- | --- |
 * | 数据来源 | **不动后端**：调用方照旧一次拿到全量数组（`GET /library` 之类），本件只决定"画多少" |
 * | 渲染 | `rows` = 源数组**前 `shown` 条**；`shown` 初始 `pageSize`（默认 60），`loadMore()` 追加一批 |
 * | 触发 | **列表尾部**进入可见底边 `gap` px 以内就自动追加一批（滚到底自然满足；一批没铺满视口时也续追）；`sentinel` 哨兵既当"尾部标尺"，也用来定位滚动层 |
 * | 筛选 / 排序 / 搜索 | **完全不参与**：源数组是调用方过滤+排好序的那一份，本件只做"前缀切片"，顺序与内容原样 |
 * | 换结果 | 源数组**换了身份**（换筛选词 / 重新拉回一份数据）= 换了一套结果 → 自动回到第一批 |
 *
 * **为什么先不做虚拟滚动**：卡片墙是网格布局（`repeat(auto-fill,minmax(172px,1fr))`），
 * 一屏几十张、DOM 量级还在几百条 —— 分段渲染已经能把首屏成本压到与总条数无关（只画 60 张），
 * 而虚拟滚动要接管测量 / 定位 / 高度占位，与"卡片高度随封面比例变"的现有样式天然打架，
 * 收益要到几千条才出现。量级到几千时再上**服务端分页 + 虚拟滚动**（方案 §2.4）；
 * 那时这套接口仍然适用，只是"取下一批"从内存切片换成一次请求（`loadMore()` 变成 async）。
 *
 * **滚动层判定照抄 `components/common/BackToTop.vue`**（本仓库唯一一处滚动监听实现，
 * 2026-10-13 那版已经把这些坑踩过一遍，别自创第二套）：
 * 1. **不自己找滚动容器**：壳的内容区（`Console.vue` 的 `.avh-content`，`overflow: auto`）才是滚的那层，
 *    本件从哨兵往上找**最近一个 `overflow-y: auto|scroll` 的祖先**（跳过 `overflow: hidden` 的中间层），
 *    找不到就退回 `window`（宿主没给内容区限高、整页滚动的布局）；
 * 2. **候选容器未必真的能滚**：`scrollHeight > clientHeight` 才算，否则用整页 —— 两边都动过时以
 *    **已经动了的那个**为准，这样真机与本地工装走同一套判定，不会出现"本地测不出、只有真机才动"的假绿；
 * 3. **rAF 节流**：scroll 事件很密，一帧只算一次；
 * 4. **窗口尺寸变化重新找一次滚动层**（宿主弹窗改布局会换滚动层）。
 *
 * 用法（调用方只做三件事）：
 * ```ts
 * const { rows: pagedRows, shown, total, hasMore, sentinel } = usePagedList(rowsRef, { pageSize: 60 })
 * ```
 * 1. 渲染 `pagedRows`（不是全量源数组）；
 * 2. 列表末尾挂哨兵：`<div ref="sentinel">…进度提示…</div>`（**必须在滚动层内部**，否则找不到容器）；
 * 3. 想在换筛选词时立刻回到第一批可以主动调 `reset()`（不调也会在源数组换身份时自动重置）。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, toValue, watch } from 'vue'
import type { ComputedRef, MaybeRefOrGetter, Ref } from 'vue'

/** 每批条数（默认 60；`options.pageSize` 可覆盖）。 */
export const PAGE_SIZE = 60

/**
 * 触发下一批的容差（px）：**列表尾部**离可见底边不足这么多就追加 —— 提前一批备好，
 * 用户滑到尾部时新卡片已经在位（不会先看到空白再等）。
 */
export const NEAR_BOTTOM = 200

export interface PagedListOptions {
  /** 每批条数（默认 `PAGE_SIZE` = 60）。 */
  pageSize?: number
  /** 触发下一批的阈值：**列表尾部**离可见底边不足这么多 px 就追加（默认 `NEAR_BOTTOM` = 200）。 */
  gap?: number
}

/** `usePagedList()` 的返回值（`rows` / `sentinel` 直接给模板用，其余给进度提示用）。 */
export interface PagedList<T> {
  /** 当前已渲染的那一段 = 源数组前 `shown` 条（顺序内容都由源决定）。 */
  rows: ComputedRef<T[]>
  /** 已渲染条数（进度提示用；不会超过 `total`）。 */
  shown: Ref<number>
  /** 源数组条数（= 调用方过滤后的那份）。 */
  total: ComputedRef<number>
  /** 还有没渲染完的。 */
  hasMore: ComputedRef<boolean>
  /** 生效的每批条数（进度提示文案里要写它）。 */
  pageSize: number
  /** 追加一批；已经到底时返回 `false`（空操作）。 */
  loadMore(): boolean
  /** 一次显示全部（"加载全部"这类显式动作才用；滚动不会走到这里）。 */
  loadAll(): void
  /** 回到第一批（源数组换身份时会自动调用）。 */
  reset(): void
  /** 末尾哨兵：模板里 `ref="sentinel"` 挂在列表最后一项之后。 */
  sentinel: Ref<HTMLElement | null>
}

/**
 * 把一个（可能是 ref / computed / 取值函数的）数组变成"分段渲染 + 滚到底自动追加"的列表。
 *
 * 源数组**只读**：本件不 push / 不 splice / 不重排，`rows` 永远是它的前缀切片 ——
 * 所以筛选、排序、搜索的语义不会被这一层改动。
 */
export function usePagedList<T>(
  source: MaybeRefOrGetter<readonly T[] | null | undefined>,
  options: PagedListOptions = {},
): PagedList<T> {
  // 至少 1：传 0 / 负数会退化成"每批 0 条"，列表永远加载不出来
  const pageSize = Math.max(1, Math.floor(Number(options.pageSize) || PAGE_SIZE))
  // 0 / 负数 / 非数一律当"没配"用默认值：0 会让每次 scroll 都追加一批，没有意义
  const gapValue = Number(options.gap)
  const gap = Number.isFinite(gapValue) && gapValue > 0 ? gapValue : NEAR_BOTTOM

  /** 源数组（ref / computed / 取值函数都认）。非数组一律当空列（缺字段的老后端不会炸）。 */
  const all = computed<T[]>(() => {
    const value = toValue(source)
    return Array.isArray(value) ? (value as T[]) : []
  })

  const shown = ref(pageSize)
  const total = computed(() => all.value.length)
  const rows = computed<T[]>(() => all.value.slice(0, shown.value))
  const hasMore = computed(() => shown.value < total.value)

  function loadMore(): boolean {
    if (!hasMore.value) return false
    shown.value = Math.min(total.value, shown.value + pageSize)
    return true
  }

  function loadAll(): void {
    shown.value = total.value
  }

  function reset(): void {
    shown.value = pageSize
  }

  /*
   * 源数组换了身份 = 换了一套结果 → 回到第一批。
   * 用**数组身份**而不是长度：长度没变但内容全换了（刷新回来的新列表）也要从头发，
   * 否则用户会看到"筛出来的前 300 条"这种莫名其妙的初始渲染量。
   */
  watch(all, () => reset())

  // ---------- 滚到底自动追加（滚动层判定照抄 BackToTop.vue，见文件头） ----------

  /** 末尾哨兵：模板 `ref="sentinel"`；只用来定位滚动层，自己不画东西。 */
  const sentinel = ref<HTMLElement | null>(null)
  /** 候选滚动层：哨兵往上最近一个 `overflow-y: auto|scroll` 的祖先（`null` = 没有）。 */
  let scroller: HTMLElement | null = null
  /** rAF 节流用的句柄（滚动事件很密，只保留最后一帧）。 */
  let frame = 0

  /** 往上找最近一个「自己滚」的祖先；`overflow: hidden` 的中间层直接跳过。 */
  function findScroller(start: HTMLElement | null): HTMLElement | null {
    let el: HTMLElement | null = start
    while (el && el !== document.body && el !== document.documentElement) {
      const overflowY = window.getComputedStyle(el).overflowY
      if (overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') return el
      el = el.parentElement
    }
    return null
  }

  /**
   * 此刻真正在滚的那一层：内层容器真的在滚就返回它，**整页在滚时返回 `null`**（= 用 `window`）。
   *
   * 候选容器（`.avh-content`）天生带 `overflow: auto`，但它**未必真的能滚** ——
   * 宿主没给它限高、或者内容还不够长的时候，滚的是整页。所以规则是
   * 「候选容器真的能滚（`scrollHeight > clientHeight`）就用它；否则用整页」，
   * 两边都动过时以**已经动了的那个**为准。
   *
   * 它只决定「拿谁的下边缘当可见底边」，**不决定要不要追加**（那个看哨兵的位置，见 `gapToBottom()`）。
   */
  function activeScroller(): HTMLElement | null {
    const winTop = window.scrollY || document.documentElement.scrollTop || 0
    const inner = scroller
    if (inner && inner.scrollHeight - inner.clientHeight > 1) {
      if (inner.scrollTop > 0 || winTop <= 0) return inner
    }
    return null
  }

  /**
   * 列表尾部离「可见底边」还有多远（px）；`<= gap` 就该追加下一批。
   *
   * 为什么量**哨兵的位置**而不是滚动容器的 `scrollHeight - scrollTop`：
   * 容器**未必真的能滚** —— 一批 60 条没铺满视口时它就不滚（宽屏上 60 张可能只占三四行），
   * 这时既没有滚动条、也永远等不到 scroll 事件，只按"滚动到底"判会卡死在第一批。
   * 量哨兵天然覆盖这种情况：「尾部进了视口就补下一批」，补到尾部出视口为止。
   */
  function gapToBottom(): number {
    const el = sentinel.value
    if (!el) return Number.POSITIVE_INFINITY
    const rect = el.getBoundingClientRect()
    // 不在布局里（还没挂载 / 空态里整块没渲染）→ 不自动追加
    if (!rect.height && !rect.width) return Number.POSITIVE_INFINITY
    const inner = activeScroller()
    // 可见底边**不能超出视口**：容器比视口高又滚不动时，别把"屏幕外的尾部"也算进来
    const visibleBottom = inner
      ? Math.min(inner.getBoundingClientRect().bottom, window.innerHeight)
      : window.innerHeight
    return rect.bottom - visibleBottom
  }

  /**
   * 追一批：列表尾部已经进了可见区才追；追完等这一批画进 DOM 再量一次 ——
   * 一批 60 条还没铺满视口时（宽屏 + 筛出来只剩几十条）没有滚动条、也不会有 scroll 事件，
   * 靠 `nextTick` 递归补齐。每追一批就消耗掉一批，源数组有限，所以这个递归一定收敛。
   */
  function pump(): void {
    if (!hasMore.value) return
    if (gapToBottom() > gap) return
    if (!loadMore()) return
    void nextTick(pump)
  }

  function onScroll(): void {
    if (frame) return
    frame = window.requestAnimationFrame(() => {
      frame = 0
      pump()
    })
  }

  /** 窗口尺寸变化可能换掉滚动层（宿主弹窗改布局），重新找一次。 */
  function onResize(): void {
    detach()
    attach()
  }

  function detach(): void {
    if (scroller) scroller.removeEventListener('scroll', onScroll)
    window.removeEventListener('scroll', onScroll)
    window.removeEventListener('resize', onResize)
  }

  function attach(): void {
    detach()
    scroller = findScroller(sentinel.value ? sentinel.value.parentElement : null)
    // 两个都挂：内层容器与整页（哪一层真的在滚由 `activeScroller()` 现算，见它）
    if (scroller) scroller.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onResize, { passive: true })
    // 挂载先量一次：切栏目回来时容器可能已经停在底部（这时不会再触发 scroll 事件）
    void nextTick(pump)
  }

  /*
   * 哨兵随数据出现/消失（空态、错误态时列表整个不渲染）→ 重新找滚动层。
   * `flush: 'post'`：等 DOM 落定再找，否则量到的还是旧结构。`attach()` 先 `detach()`，重复挂也安全。
   */
  watch(sentinel, () => attach(), { flush: 'post' })

  onMounted(() => {
    if (sentinel.value) attach()
  })

  onBeforeUnmount(() => {
    detach()
    if (frame) {
      window.cancelAnimationFrame(frame)
      frame = 0
    }
  })

  return {
    rows,
    shown,
    total,
    hasMore,
    pageSize,
    loadMore,
    loadAll,
    reset,
    sentinel,
  }
}
