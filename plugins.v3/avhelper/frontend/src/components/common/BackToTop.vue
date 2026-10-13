<script setup lang="ts">
/**
 * 通用件：回到顶部（悬浮小按钮，2026-10-13 加）。
 *
 * 为什么需要：榜单与演员作品史都是「一直往下滑」的长列表，滑到几百张卡之后想回顶部
 * 只能手工往上拨很久。这里给一个滚下去才浮出来的小按钮，点一下平滑回到顶部。
 *
 * 用法：把它放进**视图根元素的最后一行**（例如 `<BackToTop />`），其余什么都不用管：
 *
 * - **不自己找滚动容器**：宿主/壳的内容区（`Console.vue` 的 `.avh-content`，`overflow: auto`）
 *   才是滚动的那一层，本组件从挂载点往上找**最近一个 `overflow-y: auto|scroll` 的祖先**
 *   （跳过 `overflow: hidden` 的中间层），找不到就退回 `window`（整页滚动的那种宿主）。
 *   这样同一个组件在数据台各栏、以后的设置台里都能直接放，不需要各视图把容器传进来。
 * - **定位靠 `position: sticky`**：外层锚点 `height: 0` + `bottom: <offset>`，钉在滚动区右下角，
 *   但**不占布局高度、也不改变列表的滚动长度**（按钮画在锚点线之上，不会多出一截可滚区域）。
 *   不用 `position: fixed`：壳渲染在宿主的 `v-dialog` 里，`fixed` 会被祖先的 transform 拽成
 *   「相对弹窗」定位，弹窗一滚就跟着跑。
 * - **只有真的滚下去才出现**：阈值 `threshold`（默认 260px）之前完全不画（`visibility: hidden`，
 *   连焦点都拿不到），越过阈值才淡入 + 轻微上浮；回到阈值以内自动收回去。
 *   挂载时先量一次：切栏目时容器可能已经停在半中间，不先量一次要等用户再滚一下才出现。
 *
 * 刻意**不做**：不做进度环 / 不做滚动条美化 / 不监听键盘（老实现 `#main` 也没有这些）。
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 出现阈值（px）：往下滑超过这么多才浮出来。 */
    threshold?: number
    /** 距滚动区右下角的留白（px）。 */
    offset?: number
  }>(),
  { threshold: 260, offset: 18 },
)

const hostEl = ref<HTMLElement | null>(null)
/** 是否越过阈值（决定 `--on` 那个类）。 */
const show = ref(false)

/** 候选滚动层：挂载点往上最近一个 `overflow-y: auto|scroll` 的祖先（`null` = 没有）。 */
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
 * 此刻真正在滚的那一层。
 *
 * 为什么不能只看那个候选：壳的内容区（`.avh-content`）天生带 `overflow: auto`，但它**未必真的能滚**
 * —— 宿主没给它限高、或者内容还不够长的时候，滚的是整页（本地工装换个宿主布局就会变成这样）。
 * 所以规则是「候选容器真的能滚（`scrollHeight > clientHeight`）就用它；否则用整页」，
 * 两边都动过时以**已经动了的那个**为准 —— 真机与工装因此走同一套判定，不会出现"本地测不出来、
 * 只有真机才动"的假绿。
 */
function active(): { el: HTMLElement | Window; top: number } {
  const winTop = window.scrollY || document.documentElement.scrollTop || 0
  const inner = scroller
  if (inner && inner.scrollHeight - inner.clientHeight > 1) {
    if (inner.scrollTop > 0 || winTop <= 0) return { el: inner, top: inner.scrollTop }
  }
  return { el: window, top: winTop }
}

function measure(): void {
  show.value = active().top > props.threshold
}

function onScroll(): void {
  if (frame) return
  frame = window.requestAnimationFrame(() => {
    frame = 0
    measure()
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
  scroller = findScroller(hostEl.value ? hostEl.value.parentElement : null)
  // 两个都挂：内层容器与整页（哪一层真的在滚由 `active()` 现算，见它的注释）
  if (scroller) scroller.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onResize, { passive: true })
  measure()
}

/** 点一下：平滑回到顶部（阈值内的收回交给随后的 scroll 事件）。 */
function toTop(): void {
  active().el.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  attach()
  // 再量一次：挂载那一拍布局可能还没稳定（图片/字体回填会改 scrollHeight）
  void nextTick(measure)
})

onBeforeUnmount(() => {
  detach()
  if (frame) {
    window.cancelAnimationFrame(frame)
    frame = 0
  }
})
</script>

<template>
  <div
    ref="hostEl"
    class="avh-top"
    :class="{ 'avh-top--on': show }"
    :style="{ '--avh-top-bottom': `${offset}px` }"
  >
    <button
      type="button"
      class="avh-top__btn"
      title="回到顶部"
      aria-label="回到顶部"
      @click="toTop"
    >
      <span class="avh-top__ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="17" height="17">
          <path
            fill="currentColor"
            d="M12 4.4 4.6 11.8l1.5 1.5 4.9-4.9V19.6h2V8.4l4.9 4.9 1.5-1.5z"
          />
        </svg>
      </span>
      <span class="avh-top__txt">回到顶部</span>
    </button>
  </div>
</template>

<style scoped>
/* 锚点：sticky 钉在滚动区右下角，height:0 —— 不加布局高度、不加滚动长度。
   `align-items: flex-end` 不能省：容器高 0，靠它把按钮**往上**画（画在锚点线之上）；
   默认的 stretch/start 会把按钮画到线下面，等于给列表尾部多出一截可滚区域。 */
.avh-top {
  position: sticky;
  bottom: var(--avh-top-bottom, 18px);
  z-index: 6;
  height: 0;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  pointer-events: none;
}

/* 按钮本身：玻璃胶囊 + 主色图标圈，悬停时展开文字（"回到顶部"） */
.avh-top__btn {
  display: inline-flex;
  align-items: center;
  height: 44px;
  padding: 0 13px 0 8px;
  color: rgb(var(--v-theme-on-surface));
  cursor: pointer;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-on-surface), 0.1), rgba(var(--v-theme-on-surface), 0.015)),
    rgba(var(--v-theme-surface), 0.78);
  border: 1px solid rgba(var(--v-theme-primary), 0.28);
  border-radius: 999px;
  box-shadow:
    0 12px 26px rgba(0, 0, 0, 0.32),
    0 1px 0 rgba(255, 255, 255, 0.07) inset;
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  /* 隐藏态：收起 + 下沉 + 不可点（visibility 一起过渡，收起后连焦点也拿不到） */
  opacity: 0;
  visibility: hidden;
  transform: translateY(10px) scale(0.88);
  transform-origin: right bottom;
  transition:
    opacity 0.22s ease,
    transform 0.22s cubic-bezier(0.22, 1.2, 0.36, 1),
    visibility 0.22s,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.avh-top--on .avh-top__btn {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: none;
}

.avh-top__btn:hover {
  border-color: rgba(var(--v-theme-primary), 0.75);
  box-shadow:
    0 16px 30px rgba(0, 0, 0, 0.36),
    0 0 0 4px rgba(var(--v-theme-primary), 0.16);
  transform: translateY(-2px);
}

.avh-top__btn:active {
  transform: translateY(0) scale(0.97);
}

.avh-top__btn:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.7);
  outline-offset: 2px;
}

/* 图标圈：主色底 + 主色箭头，悬停稍亮、箭头轻轻抬一下 */
.avh-top__ico {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 28px;
  height: 28px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.2);
  border-radius: 50%;
  transition:
    background 0.2s ease,
    transform 0.22s cubic-bezier(0.22, 1.2, 0.36, 1);
}

.avh-top__btn:hover .avh-top__ico {
  background: rgba(var(--v-theme-primary), 0.3);
  transform: translateY(-1px);
}

/* 文字平时是 0 宽（只剩圆按钮），悬停/键盘聚焦时展开 */
.avh-top__txt {
  max-width: 0;
  margin-left: 0;
  overflow: hidden;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: 0.3px;
  white-space: nowrap;
  opacity: 0;
  transition:
    max-width 0.24s ease,
    margin-left 0.24s ease,
    opacity 0.18s ease;
}

.avh-top__btn:hover .avh-top__txt,
.avh-top__btn:focus-visible .avh-top__txt {
  max-width: 84px;
  margin-left: 7px;
  opacity: 0.92;
}

@media (prefers-reduced-motion: reduce) {
  .avh-top__btn,
  .avh-top__txt,
  .avh-top__ico {
    transition: none;
  }

  .avh-top__btn,
  .avh-top--on .avh-top__btn {
    transform: none;
  }
}
</style>
