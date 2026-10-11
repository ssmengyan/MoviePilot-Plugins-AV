/**
 * 限流政策固定值（按用户明确要求定的）：订阅检查每天 ≤6 次、间隔 ≥240 分钟。
 *
 * 界面只读展示、不提供放宽入口；这里放常量是为了让「草稿兜底」「只读展示」
 * 「运行概况」三处引用同一个数，避免哪天出现两个不同的 240。
 */
export const POLICY_MIN_INTERVAL_MIN = 240
export const POLICY_MAX_PER_DAY = 6
