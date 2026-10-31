/**
 * 快照序号闸（0.9.3 A4）：只接受最新一次读取的响应，用户动作写入会让在飞的读取作废。
 *
 * 这里锁的是**顺序语义**，不是实现细节：
 * 1. 先发后到的旧响应必须被丢弃（否则界面会从「已取消」倒回「下载中」）；
 * 2. 用户动作写入后，之前发出的读取一律作废；
 * 3. 动作之后**新发起**的读取仍然生效（不然界面就永远不更新了）。
 */
import { describe, expect, it } from 'vitest'

import { createLatestGate } from '../src/composables/latestGate'

describe('createLatestGate', () => {
  it('只接受最近一次发起的读取', () => {
    const gate = createLatestGate()
    const older = gate.start()
    const newer = gate.start()
    expect(gate.accept(newer)).toBe(true)
    expect(gate.accept(older)).toBe(false)
  })

  it('旧响应先到也不能落（由发起顺序决定，不由到达顺序）', () => {
    const gate = createLatestGate()
    const older = gate.start()
    const newer = gate.start()
    // 旧的先回来：它已经不是最新那次发起，整份丢弃
    expect(gate.accept(older)).toBe(false)
    expect(gate.accept(newer)).toBe(true)
  })

  it('用户动作写入后，在飞的全部作废', () => {
    const gate = createLatestGate()
    const inflight = gate.start()
    gate.invalidate()
    expect(gate.accept(inflight)).toBe(false)
  })

  it('动作之后新发起的读取仍然生效', () => {
    const gate = createLatestGate()
    gate.start()
    gate.invalidate()
    const after = gate.start()
    expect(gate.accept(after)).toBe(true)
  })

  it('连续两次动作只留最后一份（中间那份读取也不会翻回来）', () => {
    const gate = createLatestGate()
    const read = gate.start()
    gate.invalidate()
    gate.invalidate()
    expect(gate.accept(read)).toBe(false)
    const fresh = gate.start()
    expect(gate.accept(fresh)).toBe(true)
  })
})
