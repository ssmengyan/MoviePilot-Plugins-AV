/**
 * 通知「已读位点」——**全应用唯一一份**（S6-8 通知抽屉）。
 *
 * 位点键：`avhnext.settings.noticesSeen`
 * ---------------------------------------
 * 老实现（`ui/views/notify.js`）用的是 `avh.noticesSeen`，重构版的设置台
 * （`components/settings/NotifyPanel.vue`）先上线时另开了 `avhnext.settings.noticesSeen`。
 * 顶栏铃铛的「未读角标」与设置台「通知」栏的已读位点必须是**同一个位点**，否则
 * 两边角标各说各话（老重构版就是这个症状）。这里只保留一个键，并按任务约定
 * **沿用设置台那个**（设置台已上线，沿用它可以不动用户已有的"已读到哪"）：
 *
 *   - 顶栏 🔔 未读角标 = `notices` 里 `time > seenAt` 的条数；
 *   - 打开通知抽屉即 `markSeen()`（角标归零，列表照旧全留）——与老 `openNotify()` 一致；
 *   - 打开设置台「通知」栏同样 `markSeen()`（它以前就是"打开即已读"）。
 *
 * 老写法里还有个只读的 `legacySeen`（读 `avh.noticesSeen`，用来在设置台显示"内嵌应用已读到…"）：
 * 键统一之后它必然等于本位点（两边不可能再有分歧），所以整条只读展示一并去掉，不再读第二个键。
 *
 * 口径与老实现逐字一致：按**时间戳字符串**比较（后端的 `time` 是
 * `YYYY-MM-DD HH:MM:SS`，字典序即时间序），不做日期解析。
 */
import { ref, type Ref } from 'vue'

/** 已读位点用的 localStorage 键（顶栏角标与设置台共用；**不要再加第二个键**）。 */
export const NOTICES_SEEN_KEY = 'avhnext.settings.noticesSeen'

/** 当前已读位点（`''` = 没读过，全部算未读）。 */
export const seenAt: Ref<string> = ref(readSeen())

function readSeen(): string {
  try {
    return localStorage.getItem(NOTICES_SEEN_KEY) || ''
  } catch {
    // 隐私模式等取不到 localStorage：只用内存位点，界面照常。
    return ''
  }
}

/** 位点落盘（写不了就只留内存位点，与老实现同一套降级）。 */
export function saveSeen(): void {
  try {
    localStorage.setItem(NOTICES_SEEN_KEY, seenAt.value)
  } catch {
    /* 写不了就只保留内存位点 */
  }
}

/** 重新从 localStorage 读一次（另一个标签页改过位点、或宿主重新挂载组件时用）。 */
export function reloadSeen(): void {
  seenAt.value = readSeen()
}

/** 列表里最新的那条时间（空列表返回兜底值；老 `reduce` 的同一条算式）。 */
export function latestNoticeTime(
  notices: ReadonlyArray<{ time?: string }> | null | undefined,
  fallback = seenAt.value,
): string {
  return (notices || []).reduce(
    (acc, item) => (String(item?.time || '') > acc ? String(item?.time) : acc),
    fallback,
  )
}

/** 未读数：`time` 晚于已读位点的条数（老 `noticeUnread()`）。 */
export function countUnread(
  notices: ReadonlyArray<{ time?: string }> | null | undefined,
): number {
  return (notices || []).filter(item => String(item?.time || '') > seenAt.value).length
}

/**
 * 把位点上移到列表里最新的一条（老 `noticeMarkSeen()`）。
 *
 * 位点只会前进：列表为空、或全部早于当前位点时，一个字都不写
 * （所以"打开抽屉 → 清空 → 位点"这条链不会因为列表变空而丢掉已读位置）。
 */
export function markNoticesSeen(
  notices: ReadonlyArray<{ time?: string }> | null | undefined,
): void {
  const latest = latestNoticeTime(notices)
  if (latest === seenAt.value) return
  seenAt.value = latest
  saveSeen()
}
