<script setup lang="ts">
/**
 * 番号缩略图（本次新增的通用件）。
 *
 * 与老实现的对应关系：
 * - 普通番号缩略图 = `ui/ui/image.js` 的 `imgWithPlaceholder(url, alt)`
 *   ＋ `ui/app.css` 的 `.thumb/.tposter/.mini/.av` 系列规则（`.noimg` 占位）；
 * - 「失败才回落代理」的完整链 = 老实现**只在长缩略图那一处**做过
 *   （`views/detail.js` 的 `paintLong()`：直连失败 → `apiUrl('/img',{url})` → 仍失败才提示），
 *   本次把它抽成所有图片统一的纪律，并按设计文档 §6.1 的硬要求补上
 *   `referrerpolicy="no-referrer"`（projectjav 图床校验 Referer，带上本站地址一律 403）。
 *
 * 行为：
 * 1. 先按传入地址**直连**加载，且始终带 `referrerpolicy="no-referrer"`；
 * 2. 直连失败 → 换成插件图片代理 `/api/v1/plugin/<id>/img?url=...`（**只回落一次**）；
 * 3. 代理也失败 → 显示老实现同款占位文案（默认「无图」）。
 *
 * 后端给列表/详情里的图片字段时，通常已经是代理地址（`plugin.image_url()`），
 * 这种情况下第 2 步自然不发生（地址本身就是代理，见 `PROXY_MARK`）。
 */
import { computed, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 图片地址：可以是图床原地址，也可以是插件图片代理地址。 */
    src?: string
    /** 占位文案（老实现 `imgWithPlaceholder(url, alt)` 的 alt，默认「无图」）。 */
    alt?: string
    /** 本插件实例 id，用于拼图片代理地址（分身也为实例 id）。 */
    pluginId?: string
    /** 容器形态：`.thumb` 卡片封面 / `.tposter` 任务小图 / `.mini` 搜索行小图 / `.av` 演员头像 / `.film` 作品史封面。 */
    variant?: 'thumb' | 'tposter' | 'mini' | 'av' | 'film' | 'plain'
    /** 是否懒加载（老实现固定 `loading="lazy"`，首屏大图可关掉）。 */
    lazy?: boolean
    /** 兜底占位强制显示（父组件已知没有图时）。 */
    forcePlaceholder?: boolean
  }>(),
  {
    src: '',
    alt: '无图',
    pluginId: '',
    variant: 'plain',
    lazy: true,
    forcePlaceholder: false,
  },
)

const emit = defineEmits<{
  /** 直连与代理都失败（载荷 = 当时用的地址），父组件可据此整块换成占位。 */
  (event: 'failed', src: string): void
}>()

/** 宿主/后端生成的代理地址标记：命中就不再套一层代理（该标记就是后端 `image_url()` 的写法）。 */
const PROXY_MARK = '/img?url='

/** 直连阶段失败、已切到代理地址。 */
const useProxy = ref(false)
/** 代理也失败了。 */
const failed = ref(false)

watch(
  () => props.src,
  () => {
    useProxy.value = false
    failed.value = false
  },
)

/** 插件图片代理地址；`pluginId` 缺失时不拼（宁可不显示，也不去猜实例 id）。 */
const proxySrc = computed(() => {
  const raw = String(props.src || '')
  if (!raw) return ''
  if (raw.includes(PROXY_MARK)) return raw
  if (!props.pluginId) return ''
  return `/api/v1/plugin/${props.pluginId}/img?url=${encodeURIComponent(raw)}`
})

const currentSrc = computed(() => {
  const raw = String(props.src || '')
  if (!raw) return ''
  if (!useProxy.value) return raw
  return proxySrc.value
})

const showPlaceholder = computed(
  () => props.forcePlaceholder || !String(props.src || '') || failed.value || !currentSrc.value,
)

function onError(): void {
  const raw = String(props.src || '')
  // 地址本身就是代理，或没有可用的代理地址：没有第二跳，直接进占位态。
  if (!useProxy.value && proxySrc.value && proxySrc.value !== raw) {
    useProxy.value = true
    return
  }
  failed.value = true
  emit('failed', raw)
}
</script>

<template>
  <div class="avh-thumb" :class="`avh-thumb--${variant}`">
    <img
      v-if="!showPlaceholder"
      :src="currentSrc"
      :alt="alt"
      referrerpolicy="no-referrer"
      :loading="lazy ? 'lazy' : 'eager'"
      decoding="async"
      @error="onError"
    />
    <div v-else class="avh-thumb__noimg">{{ alt || '无图' }}</div>
  </div>
</template>

<style scoped>
/* 占位与外层尺寸都由使用方决定：这里只保证"图铺满 + 占位居中"两条老规则。 */
.avh-thumb {
  position: relative;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.avh-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* `.film .pic`：作品史封面是竖版标准封面，必须 contain，否则会被裁掉大半。 */
.avh-thumb--film img {
  object-fit: contain;
}

/*
 * 卡片封面（`--thumb`）的横向裁切位置：**贴右**，不是居中。
 *
 * javdb 的 `covers/` 大图（800×538 那档）是**封套展开图**：左半边是封底（截图墙、条形码、
 * 规格文字），右半边才是封面 —— 也就是老实现那张 147×200 竖图的画面。3:4 盒子配
 * `object-fit: cover` 默认居中，正好切在封底与封面的接缝上，看到的是"半张封底 + 半张封面"。
 *
 * 为什么右锚定（2026-10-13 实测，61 张封面逐张滑窗比对竖图模板）：
 * 59/61（96.8%）的最佳窗口就是最右那一条，误差 34.4 只有居中时 74.9 的一半；
 * 剩下 3 张右锚定也不比居中差。锚到右边 ≈ 把老实现那张竖图原样放大 2.7 倍取回来。
 *
 * 对竖图图源无副作用：「已入库的番号」栏的行只有 `thumb`（147×200），比例比盒子更窄，
 * 缩放由宽度决定、横向本就不溢出，这一条对它等于没写。
 */
.avh-thumb--thumb img {
  object-position: 100% 50%;
}

.avh-thumb--av img {
  border-radius: 50%;
}

.avh-thumb__noimg {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  text-align: center;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* 任务/下载队列的小封面（`.tposter .noimg`）：字号更小 */
.avh-thumb--tposter .avh-thumb__noimg {
  font-size: 11px;
}
</style>
