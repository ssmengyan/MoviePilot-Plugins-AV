<script setup lang="ts">
/**
 * 设置台 · 刮削（v4 刮削线 S9 新增）。
 *
 * 这一栏是 `docs/AVHelper-最终方案-v4.1.md` §10.1 与 `docs/AVHelper-刮削v4-模块契约.md` §3.8
 * 要求的「刮削」设置栏：**刮削模式 / 简介源开关 / 翻译模型 + 模型自检 / 封面裁切锚点 /
 * 预告片模式 / 定时重刮**。观感与写法照 `RulePanel.vue`（同一套 `v-card` + `v-btn-toggle` +
 * `v-switch` + 「说明一句在控件下面」的排布），数据进 `ScrapeSettings`（`./panels.ts`）。
 *
 * 三处口径写死在代码里，改之前先读契约：
 * 1. **预告片默认 `off`**（契约 D9 的产品口径）：`local` 会往媒体目录写 `<片名>-trailer.mp4`，
 *    触发 Emby 实时扫描；`remote`（写 `RemoteTrailers`）实测**写不进去**，留在界面上只为将来能修好。
 * 2. **「模型自检」走 `POST /scrape/selfcheck`**（契约 §3.7，入参 `{model?}`，
 *    出参 `{ok, model, latency_ms, error}`，后端转 `translator.selfcheck()`）。
 *    ⚠️ 主统筹 2026-10-14 明确：**模型自检只用这个端点，不要退回 `/scrape/status` 的 `sources`**
 *    （那是"各数据源自检"，不是模型自检）。端点失败（404/网关不通）时**不白屏**：只显示原因。
 * 3. **保存走顶条「保存修改」**：本栏只 `emit('patch')`，壳把补丁合并进 `POST /rule`
 *    （与「下载规则」同一份 kv；后端 `merge_rule()` 保留未知键），本栏不发任何写请求。
 */
import { computed, ref } from 'vue'
import { errorText, hostToast, unwrap, type PluginApi } from '../../composables/usePluginApi'
import type { CropAnchor, ScrapeMode, ScrapeSettings, TrailerMode } from './panels'

const props = withDefaults(
  defineProps<{
    /** 刮削设置草稿（壳持有：`GET /rule` 的刮削键 + 本栏还没提交的补丁）。 */
    settings: ScrapeSettings
    /** 宿主请求器（壳已补插件 id）：只有「模型自检」用它。 */
    api?: PluginApi | null
    /** 宿主 toast（`moviepilot:toast` 注入），拿不到时静默降级。 */
    toast?: unknown
  }>(),
  { api: null, toast: null },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5：函数式写法编译出 `emits: <函数>`，事件静默失效）。 */
const emit = defineEmits(['patch'])

const t = hostToast(props.toast as any)

/** 打补丁到刮削草稿（只传改动的字段，保存时由壳合并提交）。 */
function patch(key: keyof ScrapeSettings, value: unknown): void {
  emit('patch', { [key]: value })
}

const MODES: { value: ScrapeMode; label: string; hint: string }[] = [
  { value: 'off', label: '关闭', hint: '不启用自建刮削层：Emby 侧维持现状。' },
  { value: 'fill', label: '只补空缺', hint: '只写 Emby 里为空的字段，已有值不覆盖。' },
  { value: 'hybrid', label: '混合', hint: '自建层优先，它拿不到的字段回落 MetaTube。' },
  { value: 'own', label: '仅自建', hint: '只用自建层的结果；拿不到就留空，不回落 MetaTube。' },
]

const modeHint = computed(
  () => MODES.find(item => item.value === props.settings.scrapeMode)?.hint || '',
)

const ANCHORS: { value: CropAnchor; label: string; hint: string }[] = [
  { value: 'auto', label: '自动', hint: '按图源判断：封套展开图贴右取封面，FC2 / VR / 素人取中间。' },
  { value: 'right', label: '贴右', hint: '永远取最右那一段（javdb 封套展开图的封面就在右边）。' },
  { value: 'center', label: '居中', hint: '永远取中间窗口（适合横版剧照改的封面）。' },
  { value: 'left', label: '贴左', hint: '永远取最左那一段。' },
  { value: 'raw', label: '不裁切', hint: '原图直传，比例由 Emby 自己处理。' },
]

const anchorHint = computed(
  () => ANCHORS.find(item => item.value === props.settings.cropAnchor)?.hint || '',
)

const TRAILERS: { value: TrailerMode; label: string; hint: string }[] = [
  { value: 'off', label: '关闭', hint: '默认关闭：不下载、不写入任何预告片信息。' },
  { value: 'remote', label: '远端地址', hint: '写 Emby 的 RemoteTrailers —— 实测写不进去（204 但读回为空），留着给以后。' },
  { value: 'local', label: '本地文件', hint: '把预告片下成 <片名>-trailer.mp4 放在影片同目录，靠 Emby 实时扫描认领。' },
]

const trailerHint = computed(
  () => TRAILERS.find(item => item.value === props.settings.trailerMode)?.hint || '',
)

// ---------- 模型自检（`POST /scrape/selfcheck`） ----------

/** 自检结论（`null` = 还没点过）。 */
const check = ref<{ ok: boolean; text: string } | null>(null)
const checking = ref(false)

/**
 * 「模型自检」：`POST /scrape/selfcheck {model}`。
 *
 * 三种失败都要能看：① 宿主 api 不可用；② 端点 404（后端还没落地）；③ 网关/模型报错
 * （后端回 `{ok:false, error}` 也是 HTTP 200，所以**必须看 `ok` 而不是只看状态码**）。
 */
async function runSelfcheck(): Promise<void> {
  if (checking.value) return
  checking.value = true
  check.value = null
  t.info(`正在自检模型 ${props.settings.translateModel} …`)
  try {
    const api = props.api
    if (!api || typeof api.post !== 'function') throw new Error('宿主 api 不可用')
    const payload: any = unwrap<any>(
      await api.post('plugin/scrape/selfcheck', { model: props.settings.translateModel }),
    )
    if (payload && typeof payload === 'object' && payload.success === false) {
      throw new Error(String(payload.message || '模型自检失败'))
    }
    const ok = payload?.ok === undefined ? true : !!payload.ok
    const latency = payload?.latency_ms ?? payload?.latencyMs
    const text = [
      `模型 ${String(payload?.model || props.settings.translateModel)}`,
      latency === undefined || latency === null ? '' : `${latency} ms`,
      ok ? '可用' : String(payload?.error || '不可用'),
    ].filter(Boolean).join(' · ')
    check.value = { ok, text }
    if (ok) t.success('模型自检通过')
    else t.warning(`模型自检未通过：${String(payload?.error || '原因未知')}`)
  } catch (err) {
    // 端点还没上线（404）或网关不通：只显示原因（**不再退回落读 /scrape/status**）。
    check.value = { ok: false, text: `自检失败：${errorText(err)}` }
    t.warning(`模型自检失败：${errorText(err)}`)
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <v-card variant="tonal" class="avh-panel">
    <v-card-item>
      <template #prepend>
        <v-icon icon="mdi-auto-fix" color="primary" />
      </template>
      <v-card-title>刮削</v-card-title>
      <v-card-subtitle>自建刮削层 · 简介 / 翻译 / 裁切 / 预告片 · 与「下载规则」同一份插件设置（POST /rule）</v-card-subtitle>
    </v-card-item>

    <v-card-text>
      <!-- ===== 刮削模式 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">刮削模式</div>
      <v-btn-toggle
        :model-value="props.settings.scrapeMode"
        mandatory
        density="comfortable"
        variant="outlined"
        color="primary"
        class="mb-1"
        @update:model-value="(value: any) => value && patch('scrapeMode', value)"
      >
        <v-btn v-for="item in MODES" :key="item.value" :value="item.value">{{ item.label }}</v-btn>
      </v-btn-toggle>
      <p class="text-caption text-medium-emphasis mb-4">
        {{ modeHint }}
        具体字段路由由后端按这一档执行；本栏只负责选择与保存。
      </p>

      <!-- ===== 简介源 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">简介来源</div>
      <v-switch
        :model-value="props.settings.plotJavtxt"
        color="primary"
        hide-details
        inset
        label="Javtxt（中文直出）"
        class="mb-1"
        @update:model-value="(value: any) => patch('plotJavtxt', value === true)"
      />
      <v-switch
        :model-value="props.settings.plotMetatube"
        color="primary"
        hide-details
        inset
        label="MetaTube（日文 + 翻译）"
        class="mb-1"
        @update:model-value="(value: any) => patch('plotMetatube', value === true)"
      />
      <p class="text-caption text-medium-emphasis mb-4">
        javdb 侧不给简介（实测 12/12 <code>summary</code> 为 null），所以简介只能来自这两个源；
        两个都关掉时这一档等于「只写核心字段」。
      </p>

      <!-- ===== 翻译模型 + 自检 ===== -->
      <div class="avh-grid mb-2">
        <v-text-field
          :model-value="props.settings.translateModel"
          label="翻译模型"
          hint="默认 hy3（同一网关；hy3 会把 token 烧在推理上，后端已给足 max_tokens）"
          persistent-hint
          variant="outlined"
          density="comfortable"
          clearable
          @update:model-value="(value: any) => patch('translateModel', String(value ?? '').trim() || 'hy3')"
        />
        <v-text-field
          :model-value="props.settings.translateModelFallback"
          label="备用模型"
          hint="主模型失败/超时后降级用它（默认 deepseek-v4.1-flash）"
          persistent-hint
          variant="outlined"
          density="comfortable"
          clearable
          @update:model-value="(value: any) => patch('translateModelFallback', String(value ?? '').trim())"
        />
      </div>

      <div class="avh-row mb-2">
        <v-btn
          variant="outlined"
          size="small"
          prepend-icon="mdi-connection"
          :loading="checking"
          @click="runSelfcheck"
        >模型自检</v-btn>
        <span class="text-caption text-medium-emphasis">POST /scrape/selfcheck（后端转 translator.selfcheck）</span>
      </div>

      <v-alert
        v-if="check"
        :type="check.ok ? 'success' : 'warning'"
        variant="tonal"
        density="compact"
        class="text-caption mb-3"
      >{{ check.text }}</v-alert>

      <!-- ===== 封面裁切锚点 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">封面裁切锚点</div>
      <v-btn-toggle
        :model-value="props.settings.cropAnchor"
        mandatory
        density="comfortable"
        variant="outlined"
        color="primary"
        class="mb-1"
        @update:model-value="(value: any) => value && patch('cropAnchor', value)"
      >
        <v-btn v-for="item in ANCHORS" :key="item.value" :value="item.value">{{ item.label }}</v-btn>
      </v-btn-toggle>
      <p class="text-caption text-medium-emphasis mb-4">{{ anchorHint }}</p>

      <!-- ===== 预告片模式 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">预告片</div>
      <v-btn-toggle
        :model-value="props.settings.trailerMode"
        mandatory
        density="comfortable"
        variant="outlined"
        color="primary"
        class="mb-1"
        @update:model-value="(value: any) => value && patch('trailerMode', value)"
      >
        <v-btn v-for="item in TRAILERS" :key="item.value" :value="item.value">{{ item.label }}</v-btn>
      </v-btn-toggle>
      <p class="text-caption text-medium-emphasis mb-4">
        {{ trailerHint }}
        产品口径：写媒体目录（本地文件那档）会让 Emby 立刻扫一遍库，所以这里默认停在「关闭」。
      </p>

      <!-- ===== 定时重刮 ===== -->
      <div class="text-caption text-medium-emphasis mb-1">定时重刮</div>
      <v-switch
        :model-value="props.settings.autoScrapeTier1"
        color="primary"
        hide-details
        inset
        label="Tier 1：新片与残缺片（指数退避 6h→24h→72h→7d→14d）"
        class="mb-1"
        @update:model-value="(value: any) => patch('autoScrapeTier1', value === true)"
      />
      <v-switch
        :model-value="props.settings.autoScrapeTier2"
        color="primary"
        hide-details
        inset
        label="Tier 2：全库冷数据滚动（每轮取最久未更新的 5 条）"
        class="mb-1"
        @update:model-value="(value: any) => patch('autoScrapeTier2', value === true)"
      />
      <p class="text-caption text-medium-emphasis mb-0">
        两档默认都关：打开后由后端调度器按退避节奏跑，队列长度在数据台「刮削」栏顶部看。
      </p>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

/* 与 `RulePanel` 同一套「自动铺列」网格（窄屏自然折成一列） */
.avh-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px 16px;
}

.avh-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
