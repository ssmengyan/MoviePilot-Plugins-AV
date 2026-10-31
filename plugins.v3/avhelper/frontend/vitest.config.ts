import { defineConfig } from 'vitest/config'

/**
 * 前端单测（0.9.3 D2）。
 *
 * 只测**纯函数与状态逻辑**（`normKey`、`settingsModel` 的归一化、A4 的序号闸、`safeUrl`）——
 * 这些是不跑浏览器也能锁住的口径。真实宿主里的回归仍走 `_tmp/fe-host/` 的迷你宿主 +
 * Playwright（见 `docs/agent/testing.md`）。
 *
 * 不需要 `@vitejs/plugin-vue`：这一层不挂载组件，跑的是 `.ts` 模块。
 */
export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
  },
})
