/**
 * `normKey()` 与**后端 `emby.norm_key()` 共用一份用例表**（0.9.3 D2）。
 *
 * 用例表在 `tests/normkey-cases.json`，Python 侧 `test_normkey_shared_table.py` 读同一份文件。
 * 两边算法一旦漂开（比如后端抹了数字段前导零、前端忘了），这里和后端单测会一起红 ——
 * 台账行 key、演员匹配、Emby 索引全靠这条口径对齐。
 */
import { describe, expect, it } from 'vitest'

import { normKey } from '../src/composables/downloadHistory'
import table from './normkey-cases.json'

describe('normKey（与后端 emby.norm_key 共用用例表）', () => {
  for (const item of table.cases) {
    it(`${JSON.stringify(item.input)} → ${JSON.stringify(item.key)}（${item.why}）`, () => {
      expect(normKey(item.input)).toBe(item.key)
    })
  }
})
