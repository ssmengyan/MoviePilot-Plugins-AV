import { computed, ref, type Ref } from 'vue'
import { errorText, type PluginApi } from './usePluginApi'
import {
  formatBytes,
  formatCheckTime,
  toCheckInfo,
  type BootstrapLike,
  type CheckInfo,
} from './settingsModel'

/** `/bootstrap` 里用得到的字段（其余原样透传，不做假设）。 */
export interface BootstrapData extends BootstrapLike {
  favs?: any[]
  subs?: any[]
  known?: any[]
  tasks?: any[]
  queue?: any[]
}

/** 右栏「运行概况」能显示的几行。取不到的行显示 `—`，不编造数据。 */
export interface RuntimeOverview {
  enabled: boolean | null
  subs: number | null
  awaitTasks: number | null
  downloading: number | null
  favorites: number | null
  notices: number | null
  /** 缓存占用：`/bootstrap.cacheSizeText` 优先，没有就用 `cacheSize` 换算，都没有 = `—`。 */
  cacheSize: string
  /** 下次可检查时间：`/bootstrap.check.nextAt`（epoch 秒，`0` = 现在可检查），没上线 = `—`。 */
  nextCheck: string
  /** 限流只读展示用的归一结果（字段没上线 = `null`）。 */
  check: CheckInfo | null
}

export const POLL_INTERVAL_MS = 15_000

function len(value: any): number | null {
  return Array.isArray(value) ? value.length : null
}

/**
 * 拉 `/bootstrap` 并算出右栏概况；每 15s 轮询，页面不可见时跳过
 * （`document.hidden` 时既不轮询也不发请求），回到可见时立刻补一次。
 */
export function useRuntimeInfo(api: PluginApi) {
  const data: Ref<BootstrapData | null> = ref(null)
  const error: Ref<string> = ref('')
  const loading: Ref<boolean> = ref(false)
  const updatedAt: Ref<string> = ref('')
  let timer: ReturnType<typeof setInterval> | null = null

  const overview = computed<RuntimeOverview>(() => {
    const d = data.value
    const queue = Array.isArray(d?.queue) ? d?.queue : null
    const tasks = Array.isArray(d?.tasks) ? d?.tasks : null
    const check = toCheckInfo(d?.check)
    const cacheText = typeof d?.cacheSizeText === 'string' ? d.cacheSizeText.trim() : ''
    const cacheBytes = Number.isFinite(Number(d?.cacheSize)) ? Number(d?.cacheSize) : null

    return {
      enabled: typeof d?.enabled === 'boolean' ? d.enabled : null,
      subs: len(d?.subs),
      awaitTasks: tasks ? tasks.filter((item: any) => item?.state === 'await').length : null,
      downloading: queue ? queue.filter((item: any) => item?.state !== 'done').length : null,
      favorites: len(d?.favs),
      notices: len(d?.notices),
      // 两个字段都是后端本轮在补的：取不到就 `—`，不编造。
      cacheSize: cacheText || formatBytes(cacheBytes) || '—',
      nextCheck: formatCheckTime(check?.nextAt, 'next'),
      check,
    }
  })

  const recovery = computed(() => ({
    subs: Array.isArray(data.value?.subs) ? data.value?.subs ?? [] : [],
    tasks: Array.isArray(data.value?.tasks) ? data.value?.tasks ?? [] : [],
    queue: Array.isArray(data.value?.queue) ? data.value?.queue ?? [] : [],
  }))

  /**
   * 拉一次 `/bootstrap`。
   *
   * `fresh = true` 是**手动刷新**（右栏「刷新」、各视图的 `refresh-side`、运行与缓存栏的刷新）：
   * 带上 `?fresh=1` 让后端同步问一次下载器，下载进度立刻是新的（代价约 0.6 秒）。
   * 15 秒轮询与首屏**不带**它：后端回本地快照 + 后台补刷，首屏不被下载器拖慢
   * （`TaskEngine.queue()` 里的两档年龄说明）。
   */
  async function refresh(fresh = false): Promise<void> {
    if (loading.value) return
    loading.value = true
    try {
      const res: any = await api.get(
        'plugin/bootstrap',
        fresh ? { params: { fresh: 1 } } : undefined,
      )
      // 兼容两种返回：完整信封 / 已拆包的裸数据。
      const payload: BootstrapData =
        res && typeof res === 'object' && 'data' in res && 'success' in res
          ? (res.data ?? {})
          : (res ?? {})
      data.value = payload
      error.value = ''
      const now = new Date()
      updatedAt.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
    } catch (err) {
      error.value = errorText(err)
    } finally {
      loading.value = false
    }
  }

  function onVisibility(): void {
    if (!document.hidden) void refresh()
  }

  function start(): void {
    void refresh()
    if (timer !== null) return
    timer = setInterval(() => {
      if (document.hidden) return
      void refresh()
    }, POLL_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisibility)
  }

  function stop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    document.removeEventListener('visibilitychange', onVisibility)
  }

  return { data, error, loading, updatedAt, overview, recovery, refresh, start, stop }
}
