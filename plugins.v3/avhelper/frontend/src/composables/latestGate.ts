/**
 * 「只接受最新一次响应」的序号闸（0.9.3 A4）。
 *
 * 场景：任务页首屏、5 秒轮询、手动刷新、下载/取消动作都会写同一份任务与队列快照。
 * 先发出的请求更慢、后发的先回来时，旧响应最后到达会把新状态覆盖回去 —— 用户看到
 * 「取消的又变回下载中」「刚下的又回到待确认」。给每次读取发一个递增令牌，
 * 响应回来时令牌已经过期就整份丢弃（错误刷新仍然保留屏幕上最后一份成功数据）。
 *
 * 用户动作（下载/取消/换资源/检查）返回的是**更新的**快照，它不排队：写之前
 * `invalidate()` 把所有在飞的读取作废，所以轮询不会把动作的结果盖回去。
 */
export interface LatestGate {
  /** 开始一次读取，拿到这次读取的令牌。 */
  start(): number
  /** 这次读取的响应还能不能落（只有令牌仍是最新的才可以）。 */
  accept(token: number): boolean
  /** 刚写入了一份更新的快照（用户动作）：让所有在飞的读取作废。 */
  invalidate(): void
}

export function createLatestGate(): LatestGate {
  let seq = 0
  return {
    start(): number {
      seq += 1
      return seq
    },
    accept(token: number): boolean {
      return token === seq
    },
    invalidate(): void {
      seq += 1
    },
  }
}
