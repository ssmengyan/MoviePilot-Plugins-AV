<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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

/** 壳只有两种模式：`data` = 数据台（iframe），`settings` = 设置台（逐栏做实）。 */
type ConsoleMode = 'data' | 'settings'

interface SectionItem {
  key: string
  title: string
  icon: string
  /** 设置台占位卡片里的一句「本栏后续会做什么」。 */
  hint?: string
}

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

const SETTINGS_SECTIONS: SectionItem[] = [
  {
    key: 'sites',
    title: '搜索站点',
    icon: 'mdi-web',
    hint: '搜索范围站点与优先站点（优先站点命中即停）。按用户要求按钮化：主界面只显示已选站点 chips ＋「选择站点」「优先站点」两个按钮，勾选与排序都在弹窗里做，不再把十几个站点平铺在界面上。数据走 POST /rule 的 sites / prefSites。',
  },
  {
    key: 'rule',
    title: '下载规则',
    icon: 'mdi-filter-cog',
    hint: '分辨率策略、必须中文字幕、破解优先、允许 4K 择优、做种下限、BT 兜底、命中后自动下载还是仅通知、每日检查上限。数据走 POST /rule。',
  },
  {
    key: 'notify',
    title: '通知',
    icon: 'mdi-bell',
    hint: '通知渠道沿用 MoviePilot 原生通知（本插件不另建渠道）；本栏管已读位点与清空，数据走 GET / DELETE /notices。',
  },
  {
    key: 'library',
    title: '媒体库',
    icon: 'mdi-server',
    hint: 'Emby 地址与 API 密钥；两栏都留空 = 自动复用 MoviePilot「设置 → 媒体服务器」里已配置的 Emby。本栏的改动属于宿主配置，走 emit(save) 交给宿主 PUT。',
  },
  {
    key: 'runtime',
    title: '运行与缓存',
    icon: 'mdi-database-cog',
    hint: '缓存占用与清理、javdb 二进制状态，以及限流参数只读展示（订阅检查每天 ≤6 次、间隔 ≥240 分钟，参数不放宽）。',
  },
  {
    key: 'about',
    title: '关于',
    icon: 'mdi-information-outline',
    hint: '版本号、仓库地址、文档链接。',
  },
]

const pluginId = computed(() => props.pluginId || props.sourcePluginId || '')

/** iframe 必须用实例 id（普通插件 = pluginId；分身共享同一份联邦产物）。 */
const framePluginId = computed(() => props.pluginId || props.sourcePluginId || '')

const section = ref<string>(props.mode === 'settings' ? SETTINGS_SECTIONS[0]!.key : DATA_SECTIONS[0]!.key)
const running = ref(false)
const version = ref('')

const activeSection = computed<SectionItem>(
  () => SETTINGS_SECTIONS.find(item => item.key === section.value) || SETTINGS_SECTIONS[0]!,
)

/** 宿主要求复用的统一 toast（官方指南 §5.8）；拿不到时静默降级，不自建 Toast。 */
const injectedToast = inject<any>('moviepilot:toast', null)
const toast = hostToast(injectedToast)

/** 拉不到宿主 api 时的兜底实现：请求立刻失败，走错误分支。 */
const FALLBACK_API: PluginApi = {
  get: () => Promise.reject(new Error('宿主 api 不可用')),
  post: () => Promise.reject(new Error('宿主 api 不可用')),
}

function currentApi(): PluginApi {
  return props.api && typeof props.api.get === 'function' ? props.api : FALLBACK_API
}

const runtime = useRuntimeInfo(currentApi())
const { overview, updatedAt, error: runtimeError, loading: runtimeLoading, refresh: refreshRuntime } = runtime

const activeNavKey = computed(() =>
  props.mode === 'settings' ? section.value : `data:${section.value}`,
)

function pick(item: SectionItem): void {
  section.value = item.key
}

async function loadVersion(): Promise<void> {
  if (!framePluginId.value) return
  try {
    const res: any = await currentApi().get(`plugin/page/${framePluginId.value}`)
    const payload = res && typeof res === 'object' && 'data' in res ? res.data : res
    const value = payload?.plugin_version
    if (typeof value === 'string' && value) version.value = value
  } catch {
    // 版本号拿不到就不显示，不影响界面其余部分。
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

/** 顶条「保存修改」（仅设置台）：把宿主配置交回宿主保存。 */
function saveConfig(): void {
  if (props.mode !== 'settings') return
  emit('save', { ...(props.initialConfig || {}) } as PluginConfig)
}

function closePanel(): void {
  emit('close')
}

watch(
  () => props.mode,
  (mode) => {
    section.value = mode === 'settings' ? SETTINGS_SECTIONS[0]!.key : DATA_SECTIONS[0]!.key
  },
)

onMounted(() => {
  // 设计文档 §3：弹窗宽度由 `layout` 事件声明（宿主默认 80rem）。
  emit('layout', { maxWidth: DEFAULT_MAX_WIDTH })
  runtime.start()
  void loadVersion()
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

      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-play"
        :loading="running"
        class="me-2"
        @click="runCheck"
      >运行一次</v-btn>

      <v-btn
        v-if="props.mode === 'settings'"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-content-save"
        class="me-2"
        @click="saveConfig"
      >保存修改</v-btn>

      <v-btn variant="text" prepend-icon="mdi-close" class="me-2" @click="closePanel">关闭</v-btn>
    </v-toolbar>

    <v-divider />

    <div class="avh-body">
      <!-- 左栏：栏目导航 -->
      <nav class="avh-nav">
        <v-list density="compact" nav :selected="[activeNavKey]" mandatory>
          <template v-if="props.mode === 'data'">
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
            />
          </template>
        </v-list>

        <!-- 数据台 ⇄ 设置台：宿主合同里的 `switch`（两个弹窗互换）。 -->
        <v-btn
          block
          size="small"
          variant="text"
          :prepend-icon="props.mode === 'settings' ? 'mdi-view-dashboard-outline' : 'mdi-cog-outline'"
          class="mt-2"
          @click="emit('switch')"
        >{{ props.mode === 'settings' ? '打开数据台' : '打开设置台' }}</v-btn>
      </nav>

      <v-divider vertical />

      <!-- 内容区 -->
      <section class="avh-content">
        <template v-if="props.mode === 'data'">
          <AppFrame
            v-if="framePluginId"
            :plugin-id="framePluginId"
            :section-key="section"
            :version="version"
          />
          <v-alert v-else type="warning" variant="tonal">
            宿主没有传入 pluginId，无法定位内嵌应用。
          </v-alert>
        </template>

        <template v-else>
          <v-card variant="tonal" class="avh-placeholder">
            <v-card-item>
              <template #prepend>
                <v-icon :icon="activeSection.icon" color="primary" />
              </template>
              <v-card-title>{{ activeSection.title }}</v-card-title>
              <v-card-subtitle>设置台骨架 · S5 阶段做实</v-card-subtitle>
            </v-card-item>
            <v-card-text>
              <p class="mb-3">{{ activeSection.hint }}</p>
              <v-divider class="my-4" />
              <p class="text-caption text-medium-emphasis mb-2">
                保存语义（设计文档 §5）：先提交插件自管数据（<code>POST /rule</code>），再 <code>emit('save', config)</code>
                交给宿主保存插件配置；第一步失败就不提交第二步，弹窗不关。
              </p>
              <p class="text-caption text-medium-emphasis mb-0">
                未保存标记：任一字段变脏就在顶条显示「● 未保存」。
              </p>
            </v-card-text>
          </v-card>
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
