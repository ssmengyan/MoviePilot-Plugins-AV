import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'

/**
 * 删掉模块联邦在 `generate:false` 下仍会抽取出来的 vuetify 共享 CSS。
 *
 * `vuetify/styles` 声明为 `{ generate: false }`（宿主已加载完整 Vuetify 样式表），
 * 但 @originjs/vite-plugin-federation 仍会把 `assets/__federation_shared_vuetify/styles-*.css`
 * 写进产物（约 330KB 废料）。范本插件 subscribeassistantenhanced 里也是这么清的，
 * 官方指南第 6 节明确写明「`__federation_shared_vuetify` 目录不需要上传」。
 */
function cleanFederationAssets(): Plugin {
  return {
    name: 'clean-federation-assets',
    enforce: 'post',
    generateBundle(_options, bundle) {
      for (const fileName of Object.keys(bundle)) {
        if (fileName.startsWith('assets/__federation_shared_vuetify/')) {
          delete bundle[fileName]
        }
      }

      // 顺手把 remoteEntry.js 的行尾空白规范化，保证重复构建字节稳定（便于入库 diff）。
      const remoteEntry = bundle['assets/remoteEntry.js']
      if (remoteEntry?.type === 'chunk') {
        remoteEntry.code = remoteEntry.code
          .split('\n')
          .map(line => line.trimEnd())
          .join('\n')
      }
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'AVHelper',
      filename: 'remoteEntry.js',
      exposes: {
        './Page': './src/components/Page.vue',
        './Config': './src/components/Config.vue',
      },
      shared: {
        vue: { requiredVersion: false, generate: false },
        vuetify: { requiredVersion: false, generate: false },
        'vuetify/styles': { requiredVersion: false, generate: false },
      },
      // 说明：设计要求 `format: 'esm'`。1.4.1 的产物本来就是 ESM（remoteEntry.js 末尾是
      // `export { dynamicLoadingCss, get, init }`），且该版本的类型定义里**没有** `format`
      // 选项（见 node_modules/@originjs/vite-plugin-federation/types/index.d.ts），
      // 写上会让 `tsc --noEmit` 报 TS2353。范本插件 subscribeassistantenhanced 也未写。
      // 因此这里不写、依赖默认行为 —— 产物已实测为 ESM。
    }),
    cleanFederationAssets(),
  ],
  build: {
    target: 'esnext', // 必须：联邦产物里用了顶层 await
    minify: false,
    cssCodeSplit: true,
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: { input: 'src/main.ts' },
  },
})
