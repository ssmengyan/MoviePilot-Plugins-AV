/**
 * 联邦构建入口：只做两个暴露名的再导出。
 *
 * 宿主 `federationLoader` 用 `loadRemoteComponent(pluginId, 'Page' | 'Config')`
 * 拿 `./Page` / `./Config`，取到模块后走 `default`（`u()` 里的 `__esModule` /
 * `Symbol.toStringTag === 'Module'` 判定），所以这里必须是**具名导出**，
 * 名字与 vite.config.ts 的 `exposes` 键一致。
 */
export { default as Page } from './components/Page.vue'
export { default as Config } from './components/Config.vue'
