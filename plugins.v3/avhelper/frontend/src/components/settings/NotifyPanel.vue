<script setup lang="ts">
/**
 * 设置台 · 通知（0.9.1 重做，2026-10-27 用户反馈）。
 *
 * 用户三条原话：
 * 1. 「当前设置-通知菜单中，缺少选择哪些信息发送至 Telegram 的配置项」；
 * 2. 「需要列出所有可用的通知渠道供我选取」；
 * 3. 「通知设置中需包含时间频率配置，使用 CRON 表达式，默认值固定写入即可」。
 *
 * 所以这一栏从"只看收件箱"变成三件事（顺序就是用户说的顺序）：
 *
 * | 区块 | 存哪 | 键 |
 * | --- | --- | --- |
 * | ① 推送渠道（13 个，逐个勾选 + 每个一颗「测试」） | `POST /rule` 那份 kv | `notifyChannels` |
 * | ② 推哪些通知（4 类） | 同上 | `notifyKinds` |
 * | ③ 时间频率（标准 5 段 CRON，默认值写死） | 同上 | `notifyCron` |
 * | ④ 收件箱（通知列表 / 清空） | 后端通知表 | `GET/DELETE /notices` |
 *
 * 三条口径写死在代码里，改之前先读 `panels.ts` 的 `NOTIFY_DEFAULTS` 与后端 `notify.py`：
 * 1. **本栏只 `emit('patch')`，不发任何写请求**：补丁由壳（`Console.vue`）合并进
 *    `POST /rule` —— 与「下载规则」「刮削」「演员」完全同一条保存路径，顶条「保存修改」。
 * 2. **渠道清单以 `GET /notify` 下发的为准**（后端 `notify.CHANNELS` 是唯一真值），
 *    拿不到时才用内置镜像表先画（`NOTIFY_CHANNEL_FALLBACK`）；**不发清单外的名字**。
 * 3. **空选择 = 不过滤**：一个渠道都不勾 = 推给你在 MoviePilot「设置 → 通知」里配过的
 *    全部渠道（老口径）；一类通知都不勾 = 业务通知全推（限流/界面提示永远只进收件箱）。
 *    界面上这两句要写出来，否则用户会以为"不勾 = 都不发"。
 *
 * **已读位点与顶栏铃铛共用同一个键**（S6-8 统一）：
 * `avhnext.settings.noticesSeen` —— 唯一实现在 `composables/noticesSeen.ts`。
 * 打开这一栏即算已读（与老 `openNotify()` 点铃铛同一条语义）：`markNoticesSeen()`。
 */
import { computed, ref, watch } from 'vue'
import type { NoticeItem } from '../../composables/settingsModel'
import { markNoticesSeen, seenAt } from '../../composables/noticesSeen'
import {
  NOTIFY_CHANNEL_FALLBACK,
  NOTIFY_DEFAULTS,
  NOTIFY_KIND_FALLBACK,
  type NotifySettings,
} from './panels'

const props = withDefaults(
  defineProps<{
    /** 通知设置草稿（壳持有：`GET /notify` 的 conf + 本栏还没提交的补丁）。 */
    settings?: NotifySettings
    /** 可选渠道（`GET /notify` 的 `channels[]`；拿不到时壳传内置镜像表）。 */
    channels?: Array<{ name: string; label: string }>
    /** 推送分类（`GET /notify` 的 `kinds[]`）。 */
    kinds?: Array<{ name: string; label: string }>
    /** 实际生效的宿主 cron（`GET /notify` 的 `cron{}` 摊平，**只读回显**）。 */
    cronText?: string
    /** 读设置失败的原因（空 = 没问题）。 */
    loadError?: string
    notices?: NoticeItem[]
    loading?: boolean
    /** 「清空通知」请求是否在跑。 */
    clearing?: boolean
  }>(),
  {
    settings: () => ({ ...NOTIFY_DEFAULTS }),
    channels: () => NOTIFY_CHANNEL_FALLBACK,
    kinds: () => NOTIFY_KIND_FALLBACK,
    cronText: '',
    loadError: '',
    notices: () => [],
    loading: false,
    clearing: false,
  },
)

/** ⚠️ 必须是字符串数组（AGENTS.md §5：函数式写法编译出 `emits: <函数>`，事件静默失效）。 */
const emit = defineEmits(['patch', 'test-channel', 'clear', 'reload'])

const view = computed<NotifySettings>(() => props.settings || { ...NOTIFY_DEFAULTS })

/** 打补丁到通知草稿（只传改动的字段，保存时由壳合并提交）。 */
function patch(patchValue: Partial<NotifySettings>): void {
  emit('patch', patchValue)
}

// ---------- ① 推送渠道 ----------

/** 渠道 → 是否被勾选（空数组 = 不过滤，界面上一个都不显示为勾选）。 */
function channelOn(name: string): boolean {
  return (view.value.notifyChannels || []).includes(name)
}

function toggleChannel(name: string, on: boolean): void {
  const current = (view.value.notifyChannels || []).filter(item => item !== name)
  const next = on ? [...current, name] : current
  // 勾选顺序按渠道清单走一遍，避免"先勾 App X 再勾 Telegram"导致保存后的顺序很随机
  const order = props.channels.map(item => item.name)
  next.sort((a, b) => order.indexOf(a) - order.indexOf(b))
  patch({ notifyChannels: next })
}

/** 「全部渠道 / 不指定」：一键清空 = 回"推给 MoviePilot 配过的全部渠道"。 */
function selectAllChannels(): void {
  patch({ notifyChannels: props.channels.map(item => item.name) })
}

function clearChannels(): void {
  patch({ notifyChannels: [] })
}

/** 正在测的渠道（每颗「测试」各转各的圈；同一时刻只测一个，够用了）。 */
const testing = ref('')

function testChannel(name: string): void {
  if (testing.value) return
  testing.value = name
  emit('test-channel', name)
  // 结论由壳用宿主 toast 给；这里 3 秒后收掉转圈（宿主 toast 无法回传成败）
  window.setTimeout(() => {
    if (testing.value === name) testing.value = ''
  }, 3000)
}

// ---------- ② 推哪些通知 ----------

function kindOn(name: string): boolean {
  const kinds = view.value.notifyKinds || []
  return kinds.includes('*') || kinds.includes(name)
}

function toggleKind(name: string, on: boolean): void {
  const current = (view.value.notifyKinds || []).filter(item => item !== name && item !== '*')
  patch({ notifyKinds: on ? [...current, name] : current })
}

// ---------- ③ 时间频率（CRON） ----------

/** 输入框的本地文本（允许用户打到一半的非法值；保存时后端 `pick_cron()` 兜底）。 */
const cronText = ref(view.value.notifyCron)

watch(
  () => view.value.notifyCron,
  (value) => {
    if (value !== cronText.value) cronText.value = value
  },
)

const CRON_HELP = '5 段：分 时 日 月 周（标准 cron，支持 * 5 9-17 1-5, 逗号与 */n）'

const cronValid = computed(() => cronText.value.trim().split(/\s+/).filter(Boolean).length === 5)

function onCronInput(value: string): void {
  cronText.value = String(value ?? '')
  const text = cronText.value.trim().split(/\s+/).filter(Boolean).join(' ')
  patch({ notifyCron: text || NOTIFY_DEFAULTS.notifyCron })
}

function resetCron(): void {
  cronText.value = NOTIFY_DEFAULTS.notifyCron
  patch({ notifyCron: NOTIFY_DEFAULTS.notifyCron })
}

/** 常用几档（点一下就填进输入框，用户还能再改）。 */
const CRON_PRESETS: Array<{ label: string; value: string }> = [
  { label: '每天 3 次（默认）', value: '30 9,14,21 * * *' },
  { label: '每天 09:30', value: '30 9 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每 2 小时', value: '0 */2 * * *' },
  { label: '每天 03:00', value: '0 3 * * *' },
]

// ---------- ④ 收件箱 ----------

const total = computed(() => (props.notices || []).length)

/**
 * 未读 = 时间戳晚于共享已读位点的条数（与顶栏角标、老 `noticeUnread()` 同一套口径）。
 *
 * `seenAt` 是模块级 ref：`markSeen()` 一改，这个 computed 与顶栏角标**同时**重算，
 * 屏幕上不会出现"设置台说 3 条未读、铃铛已经清零"这种自相矛盾的画面。
 */
const unread = computed(() =>
  (props.notices || []).filter(item => String(item.time || '') > seenAt.value).length,
)

/** 打开这一栏即算已读：先把未读数读出来（`unread` 已缓存），再上移位点。 */
watch(
  () => props.notices,
  () => markNoticesSeen(props.notices || []),
  { immediate: true },
)

/** 渠道分组：把 13 个塞两列，窄屏自然折成一列。 */
const groupedChannels = computed(() => props.channels)
</script>

<template>
  <div class="avh-notify">
    <v-card variant="tonal" class="avh-panel">
      <v-card-item>
        <template #prepend>
          <v-icon icon="mdi-bell" color="primary" />
        </template>
        <v-card-title>推送渠道</v-card-title>
        <v-card-subtitle>发给哪几个渠道 · 走 MoviePilot 原生通知（POST /rule 的 notifyChannels）</v-card-subtitle>
      </v-card-item>

      <v-card-text>
        <v-alert
          v-if="props.loadError"
          type="warning"
          variant="tonal"
          density="compact"
          class="text-caption mb-2"
        >通知设置读取失败（下面显示的是默认值）：{{ props.loadError }}</v-alert>

        <v-switch
          :model-value="view.notifyPush"
          color="primary"
          hide-details
          inset
          label="推送开关（关掉 = 通知只进插件收件箱，一个渠道都不发）"
          class="mb-2"
          @update:model-value="(value: any) => patch({ notifyPush: value === true })"
        />

        <div class="avh-row mb-2">
          <span class="text-caption text-medium-emphasis">渠道</span>
          <v-btn variant="text" size="x-small" prepend-icon="mdi-check-all" @click="selectAllChannels">全选</v-btn>
          <v-btn variant="text" size="x-small" prepend-icon="mdi-close-circle-outline" @click="clearChannels">不指定</v-btn>
          <span class="text-caption text-medium-emphasis">
            勾了 = 只发这几个；一个都不勾 = 发给你在 MoviePilot「设置 → 通知」里配过的全部渠道
          </span>
        </div>

        <div class="avh-channels">
          <div v-for="item in groupedChannels" :key="item.name" class="avh-channel">
            <v-checkbox
              :model-value="channelOn(item.name)"
              color="primary"
              density="compact"
              hide-details
              :label="item.label"
              class="avh-channel__box"
              @update:model-value="(value: any) => toggleChannel(item.name, value === true)"
            />
            <v-btn
              variant="text"
              size="x-small"
              :loading="testing === item.name"
              title="给这个渠道发一条测试消息（只发它一个）"
              @click="testChannel(item.name)"
            >测试</v-btn>
          </div>
        </div>

        <p class="text-caption text-medium-emphasis mb-0 mt-2">
          清单就是 MoviePilot 当前版本支持的全部通知渠道（后端 <code>notify.CHANNELS</code> 下发）。
          勾了但宿主那边没配好该渠道（比如没填 Telegram 的 token/chat_id），宿主会自己跳过 ——
          这时候用旁边那颗「测试」就能看出来。
        </p>
      </v-card-text>
    </v-card>

    <v-card variant="tonal" class="avh-panel">
      <v-card-item>
        <template #prepend>
          <v-icon icon="mdi-filter-variant" color="primary" />
        </template>
        <v-card-title>推哪些通知</v-card-title>
        <v-card-subtitle>分类过滤 · 限流提示与界面内提示永远只进收件箱（POST /rule 的 notifyKinds）</v-card-subtitle>
      </v-card-item>

      <v-card-text>
        <v-switch
          v-for="item in props.kinds"
          :key="item.name"
          :model-value="kindOn(item.name)"
          color="primary"
          hide-details
          inset
          :label="item.label"
          class="mb-1"
          @update:model-value="(value: any) => toggleKind(item.name, value === true)"
        />
        <p class="text-caption text-medium-emphasis mb-0">
          一个都不勾 = 业务通知全推（与勾满一样）；「检查被限流」「检查完成」这类界面提示永远不推送到渠道。
        </p>
      </v-card-text>
    </v-card>

    <v-card variant="tonal" class="avh-panel">
      <v-card-item>
        <template #prepend>
          <v-icon icon="mdi-clock-outline" color="primary" />
        </template>
        <v-card-title>时间频率（CRON）</v-card-title>
        <v-card-subtitle>订阅检查什么时候跑 · 默认值 {{ NOTIFY_DEFAULTS.notifyCron }}（POST /rule 的 notifyCron）</v-card-subtitle>
      </v-card-item>

      <v-card-text>
        <v-text-field
          :model-value="cronText"
          label="订阅检查时间表"
          :hint="CRON_HELP"
          persistent-hint
          variant="outlined"
          density="comfortable"
          clearable
          class="mb-2"
          :error="!cronValid"
          :error-messages="cronValid ? [] : ['需要 5 段：分 时 日 月 周（例：30 9,14,21 * * *）']"
          @update:model-value="(value: any) => onCronInput(String(value ?? ''))"
        />
        <div class="avh-row mb-2">
          <v-btn
            v-for="item in CRON_PRESETS"
            :key="item.value"
            variant="outlined"
            size="x-small"
            @click="resetCron(); onCronInput(item.value)"
          >{{ item.label }}</v-btn>
          <v-spacer />
          <v-btn variant="text" size="x-small" prepend-icon="mdi-restore" @click="resetCron">恢复默认</v-btn>
        </div>
        <p class="text-caption text-medium-emphasis mb-0">
          默认 <code>{{ NOTIFY_DEFAULTS.notifyCron }}</code> = 每天 09:30 / 14:30 / 21:30（与 0.9.0 之前一致）。
          <template v-if="props.cronText">
            实际生效：<code>{{ props.cronText }}</code>。
          </template>
          写错的值保存时会被夹回默认值；<b>改完要重载插件</b>宿主才会按新时间表调度。
          另外还有一层限流不受时间表影响：每天最多检查 6 次、两次之间至少 240 分钟。
        </p>
      </v-card-text>
    </v-card>

    <v-card variant="tonal" class="avh-panel">
      <v-card-item>
        <template #prepend>
          <v-icon icon="mdi-inbox" color="primary" />
        </template>
        <v-card-title>收件箱</v-card-title>
        <v-card-subtitle>插件自己的通知列表（不发渠道的那几条也只在这里）</v-card-subtitle>
      </v-card-item>

      <v-card-text>
        <div class="avh-counts mb-3">
          <v-chip color="primary" variant="tonal" size="small">
            未读 {{ unread }} / 共 {{ total }}
          </v-chip>
          <v-chip v-if="seenAt" variant="text" size="small" class="text-caption">
            已读到 {{ seenAt }}
          </v-chip>
        </div>

        <v-list v-if="total" density="compact" class="avh-notices mb-2">
          <v-list-item v-for="(item, index) in props.notices.slice(0, 20)" :key="index">
            <template #prepend>
              <v-icon
                :icon="item.kind === 'ok' ? 'mdi-check-circle-outline' : item.kind === 'warn' ? 'mdi-alert-outline' : 'mdi-robot-outline'"
                :color="item.kind === 'ok' ? 'success' : item.kind === 'warn' ? 'warning' : 'primary'"
                size="small"
              />
            </template>
            <v-list-item-title class="text-body-2">
              {{ item.title || item.body || '（无标题）' }}
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ item.type || '系统消息' }} · {{ item.time || '—' }}
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item v-if="total > 20">
            <v-list-item-title class="text-caption text-medium-emphasis">
              只显示最近 20 条，其余 {{ total - 20 }} 条在数据台的铃铛里。
            </v-list-item-title>
          </v-list-item>
        </v-list>
        <v-alert v-else type="info" variant="tonal" density="compact" class="text-caption mb-0">
          暂无通知。
        </v-alert>

        <p class="text-caption text-medium-emphasis mb-0 mt-2">
          打开本栏即算已读；这里的「未读」与数据台顶栏铃铛上的角标是同一个位点。
        </p>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="text" prepend-icon="mdi-refresh" :loading="props.loading" @click="emit('reload')">刷新</v-btn>
        <v-spacer />
        <v-btn
          color="error"
          variant="tonal"
          prepend-icon="mdi-bell-off-outline"
          :disabled="!total"
          :loading="props.clearing"
          @click="emit('clear')"
        >清空通知</v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<style scoped>
.avh-panel {
  margin-bottom: 12px;
}

.avh-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 渠道两列（窄屏自然折成一列）：13 个排一列太占高度 */
.avh-channels {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0 12px;
}

.avh-channel {
  display: flex;
  align-items: center;
  gap: 4px;
}

.avh-channel__box {
  flex: 1;
  min-width: 0;
}

.avh-counts {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.avh-notices {
  max-height: 40vh;
  overflow-y: auto;
  background: transparent;
}
</style>
