/**
 * `safeUrl()`（0.9.3 B3）：界面上的动态链接只放行绝对 http(s)。
 *
 * 这条是「临时加固」不是「已发生的漏洞」：目前这些字段都来自后端/站点，理论可控；
 * 但组件是公共的，写死一个判据比每次靠人眼看调用方可靠。
 */
import { describe, expect, it } from 'vitest'

import { safeUrl } from '../src/composables/safeUrl'

describe('safeUrl', () => {
  it('放行 http / https 绝对地址', () => {
    expect(safeUrl('http://192.0.2.50:8096/web/index.html')).toBe('http://192.0.2.50:8096/web/index.html')
    expect(safeUrl('https://javdb.com/v/abc')).toBe('https://javdb.com/v/abc')
  })

  it('挡住脚本与非 http 协议', () => {
    for (const value of ['javascript:alert(1)', 'data:text/html,x', 'vbscript:x', 'file:///etc/passwd']) {
      expect(safeUrl(value)).toBe('')
    }
  })

  it('相对地址一律不认（点了会指到 MoviePilot 自己的页面）', () => {
    expect(safeUrl('/detail/123')).toBe('')
    expect(safeUrl('../x')).toBe('')
  })

  it('空值与非字符串给空串', () => {
    expect(safeUrl('')).toBe('')
    expect(safeUrl('   ')).toBe('')
    expect(safeUrl(null)).toBe('')
    expect(safeUrl(undefined)).toBe('')
  })

  it('大小写不敏感，且不改写原地址', () => {
    expect(safeUrl('HTTPS://Example.com/a?b=1')).toBe('HTTPS://Example.com/a?b=1')
  })
})
