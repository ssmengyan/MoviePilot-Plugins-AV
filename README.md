# AVHelper · MoviePilot v3 AV 资源助手

<div align="center">

番号发现、订阅、选种下载与入库刮削的一体化插件

[![MoviePilot](https://img.shields.io/badge/MoviePilot-v3.x-4c6ef5?style=flat-square)](https://github.com/jxxghp/MoviePilot)
[![Plugin Version](https://img.shields.io/badge/plugin-0.7.0-7048e8?style=flat-square)](package.v3.json)
[![License](https://img.shields.io/badge/license-GPL--3.0-3da639?style=flat-square)](LICENSE)

</div>

## 这是什么

一个 **MoviePilot v3 插件**（插件 ID `AVHelper`），把 JAV 资源的「发现 → 订阅 → 选种 → 下载 → 刮削入库」串成一条链，全部在一个自带界面里完成：

| 环节 | 由谁负责 |
| --- | --- |
| 发现新片 | [javdb-cli](https://github.com/FlanChanXwO/javdb-cli)（插件自动下载该二进制，无需手工准备） |
| 记住要什么、挑哪个种、发通知 | **AVHelper 插件**（自带 SQLite 台账 + Vue 界面） |
| 搜索与下载 | MoviePilot 原生能力（复用你已配置的站点与下载器） |
| 刮削与入库 | **插件自建刮削层**（番号解析、中文标题/简介、翻译、封面、Emby 元数据写入） |

插件**不修改 MoviePilot 核心代码**，内置限流保护（订阅检查每天 ≤ 6 次、站点间随机间隔），不会把站点打到风控。

## 功能

- **发现榜单**：日 / 周 / 月 × 有码 / 无码 / FC2，番号与关键词搜索，详情抽屉（预览图、长缩略图、磁力列表、一键下载）
- **订阅**：按番号或按演员订阅新片，命中后按规则自动搜种
- **选种下载**：PT/BT 候选种子打分表（站点、规格、做种数、体积），手动挑选或按规则自动下载，队列进度实时可见
- **我的演员**：收藏演员、演员主页与作品史，支持自定义备注名
- **自建刮削**：中文标题与简介、日文人名锁定译名、LLM 翻译（可选）、封面按 Emby 比例裁切、元数据安全写入 Emby（写前整份快照，可一键回滚）
- **入库联动**：Emby 库「已入库」标记、已入库番号卡片墙、下载历史台账（文件删了也认账）
- **站点搜索**：直接在你已配置的 PT 站点按番号检索（含成人区适配）
- **通知**：站内通知 + 推送到 MoviePilot 已配置的通知渠道（如 Telegram）

## 安装

前置条件：**MoviePilot v3.1.0+**；已在 MoviePilot 里配置好下载器（qBittorrent / Transmission 等）；Emby 可选（入库标记与刮削写入需要）。

**方式 A：插件市场（推荐）**

在 MoviePilot「设置 → 插件」的第三方插件仓库里追加：

```text
https://github.com/ssmengyan/MoviePilot-Plugins-AV
```

保存后刷新插件市场，搜索 **「AV 资源助手」** 安装并启用。

**方式 B：本地插件仓库**

把 `package.v3.json` 与 `plugins.v3/avhelper/` 放到本地插件仓库目录，并在 MoviePilot 的 `PLUGIN_LOCAL_REPO_PATHS` 里指向它。

## 配置

安装后进入插件 →「打开设置」：

1. **常规**：内地网络请填 HTTP 代理（榜单拉不出来基本都是代理没配）；其余全部留空即可——javdb 二进制自动下载，数据默认存在 MoviePilot 插件数据目录，Emby 默认复用宿主配置；
2. **下载规则**：确认默认下载规则（分辨率、中字、做种数下限、保存路径、下载器与分类）；
3. **搜索站点**：勾选参与搜种的 PT 站点；
4. **刮削**（可选）：简介翻译需要一个 OpenAI 兼容的 LLM 接口，在宿主运行时配置里填 `LLM_API_KEY`（可选 `LLM_BASE_URL` / `LLM_TRANSLATE_MODEL`）；不配置也能用，只是不翻译，不会编造中文。

## 许可与免责声明

- 本项目以 **GPL-3.0** 发布（完整条款见 [LICENSE](LICENSE)），可自由学习、使用、修改与再分发；分发修改版时请保留署名并以相同许可开源。
- 内置的演员/标签映射表取自社区项目 [sqzw-x/amane](https://github.com/sqzw-x/amane)（GPL-3.0），出处见 [NOTICE.md](plugins.v3/avhelper/resources/NOTICE.md)。
- 本项目仅供学习、研究与技术交流，不包含、不提供、不托管任何影音内容；请遵守所在地区的法律法规及你所使用的每一个站点的服务条款，后果自负。仅面向达到法定成年年龄的使用者。

## 致谢

[MoviePilot](https://github.com/jxxghp/MoviePilot) · [javdb-cli](https://github.com/FlanChanXwO/javdb-cli) · [amane](https://github.com/sqzw-x/amane)（映射表数据）
