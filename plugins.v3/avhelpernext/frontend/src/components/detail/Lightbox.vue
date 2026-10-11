<script setup lang="ts">
/**
 * 图片灯箱（老实现 `ui/ui/lightbox.js`：`openLb` / `showLb` / `lbStep` + `ui/app.js` 的
 * `bindUi()` 里那几条 `#lb*` 绑定）。
 *
 * 老实现的 DOM 与交互：
 * ```
 * <div id="lb">
 *   <img id="lbImg">
 *   <div class="nav prev">‹</div><div class="nav next">›</div>
 *   <div class="ctr">i / n</div><div class="close">✕</div>
 * </div>
 * ```
 * · `openLb(list, idx)`：`list.filter(Boolean)`，空列表**直接不开**（老实现第一句就 return）；
 *   下标越界回 0；`idx < 0` 时取最后一张（`lbStep(-1)` 的环形语义）；
 * · `showLb()`：`#lbImg.src = list[idx]`、`#lbCtr.textContent = (idx+1) + ' / ' + n`；
 * · `lbStep(d)`：`(idx + d + n) % n` —— 首尾环形，不是到头禁用；
 * · 图片加载失败：`#lbImg.onerror` 把计数改成 `i / n（图片加载失败）`，**不关灯箱**；
 * · Esc / 方向键 / 点背景关闭（`app.js` 的 `keydown` 与 `#lb` 的 onclick 只在 `e.target.id==='lb'` 时关）。
 *
 * 这里逐条对齐，只有两处是"宿主化"的：
 * 1. 关闭方式换成 `v-overlay` 的 `v-model`（`@keydown.esc` 与点背景），语义与老实现一致
 *    —— 灯箱开着时 Esc **先关灯箱**，抽屉还留着，再按一次才关抽屉（老实现靠 `return` 实现同一先后）；
 * 2. 箭头切换在 `v-overlay` 吃掉方向键之前处理：capture 阶段的 document 监听 + `preventDefault`。
 *
 * `z-index: 3000` 是必要的：抽屉是 `v-navigation-drawer`（z-index 1004/1005），
 * 灯箱必须压在所有弹层之上，否则"点预览图开灯箱"会被抽屉盖住。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const open = ref(false)
/** 当前图片列表（老 `LB.list`）。 */
const list = ref<string[]>([])
/** 当前下标（老 `LB.idx`）。 */
const idx = ref(0)
/** 当前这张是否加载失败（老实现直接改写计数文案；Vue 里由模板拼同一句话）。 */
const failed = ref(false)

const emit = defineEmits<{
  /** 关闭（点背景 / Esc / ✕）。 */
  (event: 'closed'): void
}>()

/** 老 `showLb()`：换 src 时把失败标记清掉。 */
function show(index: number): void {
  idx.value = index
  failed.value = false
}

/**
 * 老 `openLb(list, idx)`。
 *
 * :param images: 图片地址列表（老实现会先 `filter(Boolean)`）。
 * :param index: 起始下标；`< 0` 取最后一张；越界回 0。
 */
function openAt(images: (string | undefined | null)[], index = 0): void {
  const items = (images || []).filter(Boolean).map(item => String(item))
  if (!items.length) return // 老实现：空列表不弹灯箱
  list.value = items
  let next = Number(index) || 0
  if (next < 0) next = items.length - 1
  if (next < 0 || next >= items.length) next = 0
  show(next)
  open.value = true
}

/** 老 `lbStep(d)`：`(idx + d + n) % n`（环形）。 */
function step(delta: number): void {
  const total = list.value.length
  if (!total) return
  show(((idx.value + delta + total) % total + total) % total)
}

function close(): void {
  open.value = false
  emit('closed')
}

/** 老 `$('#lbImg').onerror`：只改计数文案，不关灯箱。 */
function onImgError(): void {
  failed.value = true
}

/**
 * 老 `bindUi()` 的 keydown 分支：灯箱开着时 Esc 关灯箱、←/→ 切换，且**只处理灯箱**
 * （老实现命中就 `return`，不再冒泡去关抽屉）。
 */
function onKeydown(event: KeyboardEvent): void {
  if (!open.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    step(-1)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    step(1)
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown, true))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown, true))

/** 点背景关闭：老实现判的是 `e.target.id === 'lb'`，这里对应"点到的就是这层容器本身"。 */
function onBackdrop(event: MouseEvent): void {
  if (event.target === event.currentTarget) close()
}

/** 给外层抽屉用：灯箱开着时 Esc 归灯箱处理（老实现命中灯箱就 `return`，不再去关抽屉）。 */
const isOpen = (): boolean => open.value

defineExpose({ openAt, step, close, isOpen })
</script>

<template>
  <v-overlay
    v-model="open"
    :z-index="3000"
    class="avh-lb-overlay"
    @keydown.esc="close"
  >
    <!-- 点背景关闭；图片本身 `pointer-events:none`，所以点图不会误关（老实现同一条判定） -->
    <div v-if="open" class="avh-lb" @click="onBackdrop">
      <img class="avh-lb__img" :src="list[idx] || ''" alt="" @error="onImgError">

      <div class="avh-lb__nav avh-lb__prev" role="button" aria-label="上一张" @click="step(-1)">‹</div>
      <div class="avh-lb__nav avh-lb__next" role="button" aria-label="下一张" @click="step(1)">›</div>

      <!-- 计数文案与老实现逐字一致；加载失败时追加「（图片加载失败）」 -->
      <div class="avh-lb__ctr">{{ idx + 1 }} / {{ list.length }}{{ failed ? '（图片加载失败）' : '' }}</div>

      <div class="avh-lb__close" role="button" aria-label="关闭" @click="close">✕</div>
    </div>
  </v-overlay>
</template>

<style scoped>
/* 老 CSS 是 `#lb{position:fixed;inset:0;background:#000e}` + flex 居中；这里铺满 overlay 内容区 */
.avh-lb {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
}
</style>

<style>
/*
 * 灯箱固定在视口正中，且**不受** `v-overlay` 内容容器（`v-overlay__content` 默认
 * `position:absolute; top:0; left:0`）与父级布局影响 —— 用非 scoped 规则挂到 overlay 根上，
 * 这是老 CSS `#lb{position:fixed;inset:0}` 的等价写法。
 */
.avh-lb-overlay .v-overlay__content {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  max-width: none;
  max-height: none;
  margin: 0;
}

.avh-lb__img {
  max-width: 94vw;
  max-height: 92vh;
  object-fit: contain;
  border-radius: 6px;
  /* 点图不关灯箱（老实现只在 `e.target.id === 'lb'` 时关） */
  pointer-events: none;
}

.avh-lb__nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  padding: 16px;
  font-size: 34px;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  user-select: none;
}

.avh-lb__nav:hover {
  color: #fff;
}

.avh-lb__prev {
  left: 8px;
}

.avh-lb__next {
  right: 8px;
}

.avh-lb__ctr {
  position: absolute;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 14px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(0, 0, 0, 0.53);
  border-radius: 99px;
}

.avh-lb__close {
  position: absolute;
  top: 14px;
  right: 20px;
  font-size: 26px;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
}

.avh-lb__close:hover {
  color: #fff;
}
</style>
