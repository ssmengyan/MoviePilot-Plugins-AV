/**
 * `settingsModel.ts` 的归一化口径（0.9.3 D2）。
 *
 * 这些函数是「界面显示什么」的唯一入口：后端给什么形状都得归一成同一份 `RuleState` /
 * `CheckInfo`，界面上才不会出现「输入框写着 6、实际按 99 跑」。测的是**边界与回落**，
 * 不是实现细节。
 */
import { describe, expect, it } from 'vitest'

import {
  CACHE_MAX_GB_FALLBACK,
  CACHE_MAX_GB_MAX,
  CACHE_MAX_GB_MIN,
  RULE_FALLBACK,
  epochSecondsToMs,
  formatBytes,
  str,
  toCacheGb,
  toCacheGbText,
  toCheckInfo,
  toRuleState,
} from '../src/composables/settingsModel'

describe('str', () => {
  it('原样返回字符串，非字符串转 String，空值用兜底', () => {
    expect(str('abc')).toBe('abc')
    expect(str(12)).toBe('12')
    expect(str(null, 'x')).toBe('x')
    expect(str(undefined, 'x')).toBe('x')
  })
})

describe('缓存上限（与后端 paths.cache_limit_gb 同口径）', () => {
  it('空 / 非数字 / ≤0 一律回落 1G，不是「不限制」', () => {
    for (const value of ['', '   ', 'abc', 0, -3, null, undefined]) {
      expect(toCacheGbText(value)).toBe(String(CACHE_MAX_GB_FALLBACK))
    }
  })

  it('上下夹到 [0.1, 4096]', () => {
    expect(toCacheGbText(0.01)).toBe(String(CACHE_MAX_GB_MIN))
    expect(toCacheGbText(99999)).toBe(String(CACHE_MAX_GB_MAX))
  })

  it('保留最多三位小数，去掉浮点尾巴', () => {
    expect(toCacheGbText('2.5000')).toBe('2.5')
    expect(toCacheGbText(1 + 2 / 10)).toBe('1.2')
    expect(toCacheGb('4')).toBe(4)
  })
})

describe('toRuleState', () => {
  it('空对象补成默认规则', () => {
    expect(toRuleState(null)).toEqual(RULE_FALLBACK)
    expect(toRuleState({})).toEqual(RULE_FALLBACK)
  })

  it('分辨率只认三档，其余回落 1080p', () => {
    expect(toRuleState({ res: '2160p' }).res).toBe('2160p')
    expect(toRuleState({ res: '4k' }).res).toBe(RULE_FALLBACK.res)
  })

  it('trigger 只认 auto，其余都当 notify', () => {
    expect(toRuleState({ trigger: 'auto' }).trigger).toBe('auto')
    expect(toRuleState({ trigger: 'whatever' }).trigger).toBe('notify')
  })

  it('限流参数不许被界面放宽（每日上限封顶 6、间隔不少于政策值）', () => {
    const rule = toRuleState({ maxPerDay: 99, minIntervalMin: 1 })
    expect(rule.maxPerDay).toBe(6)
    expect(rule.minIntervalMin).toBe(240)
  })

  it('做种数下限取整且不许为负', () => {
    expect(toRuleState({ minSeeders: '3.9' }).minSeeders).toBe(3)
    expect(toRuleState({ minSeeders: -5 }).minSeeders).toBe(0)
  })

  it('站点清单只留非空字符串', () => {
    expect(toRuleState({ sites: ['馒头', '', null, 7] }).sites).toEqual(['馒头', '7'])
  })

  it('缺键回落默认优先站，但用户清空时保留空表', () => {
    // 后端 DEFAULT_RULE 的 prefSites 是 馒头/Rousi：界面缺键时必须显示同一份默认值
    expect(toRuleState({}).prefSites).toEqual(RULE_FALLBACK.prefSites)
    expect(toRuleState({ prefSites: [] }).prefSites).toEqual([])
  })
})

describe('epochSecondsToMs', () => {
  it('秒 → 毫秒；0 是合法哨兵值必须保留', () => {
    expect(epochSecondsToMs(1_700_000_000)).toBe(1_700_000_000_000)
    expect(epochSecondsToMs(0)).toBe(0)
  })

  it('已经是毫秒量级就不再乘 1000', () => {
    expect(epochSecondsToMs(1_700_000_000_000)).toBe(1_700_000_000_000)
  })

  it('非数字 / 负数 / 空 → undefined（界面显示 —）', () => {
    for (const value of ['', 'abc', -1, null, undefined]) {
      expect(epochSecondsToMs(value)).toBeUndefined()
    }
  })
})

describe('toCheckInfo', () => {
  it('拿不到对象就返回 null', () => {
    expect(toCheckInfo(null)).toBeNull()
    expect(toCheckInfo('x')).toBeNull()
    expect(toCheckInfo({})).toBeNull()
  })

  it('只要有一项可用就当拿到了，缺项留给界面显示 —', () => {
    expect(toCheckInfo({ allowed: true })).toEqual({ allowed: true })
    expect(toCheckInfo({ reason: '距上次不足' })?.reason).toBe('距上次不足')
  })
})

describe('formatBytes', () => {
  it('按 1024 进档，负数与非数字给空串', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(-1)).toBe('')
    expect(formatBytes('abc')).toBe('')
  })
})
