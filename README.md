# AVHelper · MoviePilot v3 插件仓库

<div align="center">

**AV 资源助手** —— 番号发现、订阅、选种下载与入库标记的一体化界面

[![MoviePilot](https://img.shields.io/badge/MoviePilot-v3.x-4c6ef5?style=flat-square)](https://github.com/jxxghp/MoviePilot)
[![Plugin Version](https://img.shields.io/badge/plugin-0.4.0-7048e8?style=flat-square)](package.v3.json)
[![License](https://img.shields.io/badge/license-非商业学习许可-ff8a4c?style=flat-square)](LICENSE)

</div>

---

## ⚠️ 声明与免责（请先读这一段）

> **本项目仅供学习、研究与技术交流使用，严禁任何形式的商业使用。**

- 本项目是一个**技术演示与学习项目**：演示「从公开元数据站点读取影片资料 → 在你自己已配置的
  PT/BT 站点搜索 → 调用你自己部署的 MoviePilot 完成选种下载与媒体库联动」这一类通用自动化流程。
- 本项目**不包含、不提供、不分发、不托管、不索引任何影音内容**，也**不内置**任何资源站的账号、
  密钥、订阅源或下载链接。所有数据都来自使用者自行配置的第三方服务。
- 本项目与任何元数据站点、PT/BT 站点、媒体服务器软件、MoviePilot 及其相关组织**没有任何隶属、
  合作、赞助或背书关系**。
- 使用者应自行确认其所在国家或地区的法律法规，并**自行承担**因安装、配置、使用本项目（包括
  抓取、搜索、下载、刮削等行为）而产生的一切后果与法律责任。**请勿用于任何违法用途。**
- 本项目仅面向达到其所在司法辖区法定成年年龄的使用者。**请遵守你所使用的每一个第三方服务的
  服务条款与使用限制。**
- 软件按「现状」提供，不附带任何担保。详见 [LICENSE](LICENSE)。

**如果你不接受上述任何一条，请不要安装或使用本项目。**

---

## 目录

- [它是什么](#它是什么)
- [功能一览](#功能一览)
- [安装](#安装)
- [配置项](#配置项)
- [使用](#使用)
- [目录结构](#目录结构)
- [常见问题](#常见问题)
- [二次开发](#二次开发)
- [开源声明与许可](#开源声明与许可)
- [致谢](#致谢)

---

## 它是什么

一个 **MoviePilot v3 本地插件**（插件 ID `AVHelper`）。它把三件事串成一条链：

| 环节 | 由谁负责 |
| --- | --- |
| 「有什么新片」的发现层 | [javdb-cli](https://github.com/FlanChanXwO/javdb-cli) 只读二进制（本插件自动下载或由你指定） |
| 「记住要什么、挑哪个种、发什么通知」 | **本插件**（自带 SQLite 台账 + Vue 联邦界面） |
| 「搜索与下载」 | MoviePilot 原生 `search_torrents` / `filter_torrents` / `download` |
| 「入库与刮削」 | Emby + MetaTube（保持你自己的现有配置，插件不改动） |

插件**不修改 MoviePilot 核心代码**，全部功能落在一个插件目录里；界面上除了插件自己的数据台，
还会给 MoviePilot 的「媒体数据源」补一个 `JAVDB` 源，并劫持该来源的番号识别。

## 功能一览

- **发现**：日/周/月 × 有码/无码/FC2 榜单、演员榜、番号/关键词搜索、影片详情抽屉（预览图灯箱、
  长缩略图、磁力列表、一键下载）。
- **我的演员**：收藏演员、演员主页与作品史（服务端分页，首屏 30 部 + 加载更多）。
- **订阅**：番号订阅与演员订阅；演员订阅按作品史与「已知番号」差集判断新片。命中后按规则搜种。
- **任务**：搜种候选表（站点、规格、做种、体积、标记），可手动挑选下载，也可按规则自动下载；
  未确认的任务可一键取消。
- **下载**：下载队列（进度、状态、封面）；同栏的「下载历史」页签是**本插件下载过**的台账
  （封面/番号/标题/演员/大小/完成时间/库状态表格，可搜索、可只看不在库、可移除记录）。
  台账按**归一化番号**记账，文件删掉了也仍然认账。
- **已入库的番号**：Emby 库里**此刻**的片子，按入库时间倒序的卡片墙（已删除的不在其中）。
  点卡片看在线详情（与榜单同一个抽屉），卡片上的「▶ 观看」直达 Emby 观看地址。
- **站点搜索**：直接在你已配置的 PT 站点里按番号检索（含成人区适配），不依赖 MoviePilot 原生索引器。
- **通知**：站内通知抽屉 + 可选推送到 MoviePilot 已配置的通知渠道（如 Telegram）。
- **入库标记**：番号若已在 Emby 库中，卡片/详情会显示「已入库」并可跳转 Emby。
- **缓存治理**：数据与图片统一落在数据根下，带 TTL、容量上限与按旧淘汰，内置每日清理任务。
- **限流保护**：订阅检查每天 ≤ 6 次、两次之间 ≥ 240 分钟，站点之间随机间隔，站点命中即停。

## 安装

### 0. 前置条件

| 项 | 要求 |
| --- | --- |
| MoviePilot | **v3.x**（插件声明 `system_version: ">=3.1.0"`）；需要 Vue 联邦前端（v3 默认具备） |
| 网络 | 能访问你使用的元数据站点与你自己的 PT 站点；内地网络通常需要一个 HTTP 代理（插件里可配） |
| 下载器 | MoviePilot 里已配置好至少一个下载器（qBittorrent / Transmission 等） |
| 媒体服务器（可选） | MoviePilot 里已配置 Emby，用于「已入库」标记与「已入库的番号」栏 |
| javdb-cli | **无需手工准备**：插件启动后若找不到 javdb 二进制，会自动从官方 Release 下载对应平台的一份 |

> 关于 javdb-cli：它是本插件唯一的额外依赖，是上游（[FlanChanXwO/javdb-cli](https://github.com/FlanChanXwO/javdb-cli)）
> 提供的 Go 单文件二进制。插件默认自动下载 **linux / macOS / windows × amd64 / arm64** 对应包，
> 并锁定在实际测试过的版本（见 `plugins.v3/avhelper/paths.py` 的 `JAVDB_VERSION`）。
> 如果你的环境不能直连 GitHub，可以自己下载一份放进容器，然后在插件设置里填写路径。

### 1. 安装插件

**方式 A：在 MoviePilot 里添加本插件仓库（推荐）**

1. 打开 MoviePilot → **设置 → 插件**（或插件市场的设置入口）；
2. 在「插件市场地址 / 第三方插件仓库」里**追加**下面这一行（多个仓库用换行或逗号分隔）：

   ```text
   https://github.com/ssmengyan/MoviePilot-Plugins-AV
   ```

3. 保存后刷新插件市场，搜索 **「AV 资源助手」**（或插件 ID `AVHelper`）；
4. 点击安装。安装完成后**启用插件**。

**方式 B：手动放置（本地插件仓库）**

1. 把 `package.v3.json` 与 `plugins.v3/avhelper/` 放到你的本地插件仓库目录下，
   保持 `<本地插件仓库>/package.v3.json` 与 `<本地插件仓库>/plugins.v3/avhelper/` 的结构；
2. 在 MoviePilot 的 `PLUGIN_LOCAL_REPO_PATHS` 里指向该目录，或直接把 `plugins.v3/avhelper/`
   拷到 MoviePilot 的插件运行目录；
3. 重启 MoviePilot 或重载插件。

### 2. 首次配置

安装启用后，进入插件详情页 → 右下角「打开设置」→ **常规**栏：

1. **代理地址**：内地网络填写你的 HTTP 代理（如 `http://192.0.2.2:7890`），否则留空；
2. **javdb 路径**：留空即可（插件会自动下载）。若自动下载失败，手工放一份再填绝对路径；
3. **数据目录**：留空即可（默认落在 MoviePilot 的插件数据目录下）；
4. **Emby 地址 / API 密钥**：留空即可（默认复用 MoviePilot「设置 → 媒体服务器」里的 Emby）；
5. 保存。

然后切到 **规则** 栏确认默认下载规则（分辨率策略、是否必须中字、做种数下限、保存路径、
下载器与分类），再到 **站点** 栏勾选参与搜种的站点。

> **保存路径与下载器留空**表示交给 MoviePilot 的下载器默认值。分类默认 `avi`，配合 qBittorrent
> 的 `auto_tmm`（分类即目录）就能自动落到分类目录里。

## 配置项

| 配置项 | 说明 | 默认 |
| --- | --- | --- |
| `enabled` | 是否启用插件。关闭后定时订阅检查不执行，界面仍可浏览 | 关 |
| `proxy` | javdb 子进程与部分站点请求使用的 HTTP 代理；留空 = 直连 | 空 |
| `javdb_bin` | javdb 可执行文件路径；留空 = 自动下载 / 自动查找 | 空 |
| `data_root` | 数据根（SQLite 台账、JSON 缓存、图片缓存同根）；留空 = 插件数据目录下的 `cache` | 空 |
| `emby_host` / `emby_apikey` | 单独指定 Emby；两项都留空 = 复用 MoviePilot 的媒体服务器配置 | 空 |

**路径解析顺序**（见 `plugins.v3/avhelper/paths.py`）：

- 数据根：`data_root` 配置 → 存在 `/avhelper` 挂载卷时用 `/avhelper/cache` → MoviePilot 插件数据目录；
- javdb：`javdb_bin` 配置 → `/avhelper/bin/javdb` → `PATH` 上的 `javdb` → `<数据根>/bin/javdb`。

## 使用

界面分「**数据台**」与「**设置台**」两块，都在插件详情页内。

**数据台七个栏目**

| 栏目 | 内容 |
| --- | --- |
| 发现榜单 | 三周期 × 三分类榜单、详情抽屉、灯箱、长缩略图、磁力下载 |
| 我的演员 | 收藏演员、演员主页与作品史 |
| 订阅 | 番号/演员订阅列表，新建、编辑规则、删除 |
| 任务 | 待确认候选（搜种结果打分表），可挑选下载或取消 |
| 下载 | 两个页签：「下载中」= 下载队列与进度；「下载历史」= 本插件下载过的番号台账（可搜索、只看不在库、移除记录） |
| 已入库的番号 | Emby 库里此刻的片子（卡片墙，按入库时间倒序）；点卡片看在线详情，「▶ 观看」直达 Emby |
| 站点搜索 | 直接在 PT 站点按番号检索 |

> 「下载历史」与「已入库的番号」是两件事：前者答「本插件下载过什么」（台账，文件删了也留着），
> 后者答「库里现在有什么」（实时，Emby 里删了就不在了）。

顶栏有全局搜索与通知铃铛（角标为未读数）。

**设置台栏目**：常规（开关/代理/路径）、规则（默认下载规则）、站点（参与搜种的站点）、
通知（推送开关与渠道）、媒体库（Emby）、运行与缓存（缓存占用、清理、限流只读展示）、关于。

## 目录结构

```text
MoviePilot-Plugins-AV/
├── package.v3.json              # MoviePilot v3 插件索引（市场元数据）
├── plugins.v3/
│   └── avhelper/                # 插件本体（目录名 = 插件类名小写）
│       ├── __init__.py          # 插件主类 AVHelper（宿主扩展点、API、界面路由）
│       ├── paths.py             # 数据根 / javdb 二进制解析与自动下载
│       ├── client.py            # javdb-cli 子进程封装
│       ├── store.py             # 插件自管 SQLite（订阅/任务/通知/台账）
│       ├── tasks.py             # 订阅检查 → 搜种 → 打分 → 下载 编排
│       ├── sitesearch.py        # PT 站点检索适配（含成人区适配）
│       ├── scoring.py           # 候选打分
│       ├── ratelimit.py         # 限流
│       ├── emby.py              # Emby 库索引与番号归一化
│       ├── imgproxy.py          # 图片代理（XOR 解包 + 防盗链 Referer）
│       ├── longshot.py          # 长缩略图解析
│       ├── notify.py            # 通知模板
│       ├── frontend/            # Vue 联邦前端工程（dist 为构建产物，必须入库）
│       └── ui/                  # 旧宿主/联邦加载失败时的回退界面
├── tests/v3/avhelper/           # 单元测试（pytest，无需宿主环境）
├── icons/avhelper.png           # 插件图标
├── README.md
└── LICENSE
```

## 常见问题

**Q：装了插件但界面一片空白 / 右栏概况全是 `—`？**
A：先确认 MoviePilot 是 v3.1.0 以上；再看浏览器控制台是否有远程组件加载失败。多数情况是
`plugins.v3/avhelper/frontend/dist/` 没随插件一起装进去（该目录**必须**入库并随插件分发）。

**Q：榜单一直转圈、搜索没有结果？**
A：绝大多数是网络问题。到「设置台 → 常规」把 **代理地址** 填上（内地通常必须），保存后重试。
插件启动时会往 MoviePilot 日志里写 javdb 的就绪情况，可以先看日志确认。

**Q：日志里出现 `javdb 未就绪`？**
A：自动下载需要能访问 GitHub。要么给插件配上代理，要么自己下载
[javdb-cli](https://github.com/FlanChanXwO/javdb-cli/releases) 对应平台的压缩包，解出 `javdb`
放进容器（例如放到数据目录下的 `bin/`），再在设置里填绝对路径。

**Q：搜不到番号的种子？**
A：检查「设置台 → 站点」里有没有勾选站点；部分站点需要先在 MoviePilot 里配好 Cookie / API Key。
分类为成人内容的站点，MoviePilot 原生索引器不一定支持，插件对常见站点（如馒头、肉丝）做了专门适配。

**Q：订阅检查为什么不是实时的？**
A：这是刻意的限流保护（每天 ≤ 6 次、间隔 ≥ 240 分钟、站点之间随机间隔、优先站点命中即停），
避免把站点打到风控。需要立刻检查时，可以在订阅栏点「检查一次」。

**Q：卸载插件会删掉我的订阅和台账吗？**
A：不会自动删。数据都在数据根目录下（默认是 MoviePilot 插件数据目录里的 `AVHelper/cache`），
卸载插件不会清空该目录，需要你自己删。

## 二次开发

欢迎 fork、改代码、提 PR —— 只要符合 [LICENSE](LICENSE) 的**非商业**条件。

**前端（Vue 联邦）**

```bash
cd plugins.v3/avhelper/frontend
npm install
npm run build      # 产物写到 frontend/dist/assets，必须随插件一起提交
```

开发时可用 `npm run dev`（`vite build --watch`）配合 MoviePilot 的本地插件仓库热加载。

**后端（插件本体）**

插件主类 `AVHelper` 定义在 `plugins.v3/avhelper/__init__.py`，通过宿主扩展点接入：
`init_plugin` / `get_form` / `get_page` / `get_render_mode` / `get_api` / `get_service` /
`get_media_source` / `get_module` / `stop_service`。宿主 Plugin 契约见
[MoviePilot](https://github.com/jxxghp/MoviePilot) 与官方
[MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins) 的 `docs/Plugin_Development.md`。

约定：**所有函数与方法都要写中文 docstring**；版本号在 `__init__.py` 的 `plugin_version` 与
`package.v3.json` 的 `version` **两处必须一致**，并在 `history` 里加一条用户可读的变更说明。

**测试**

```bash
cd <本仓库根目录>
python -m pytest tests -q       # 单元测试不依赖 MoviePilot 宿主环境
python -m compileall plugins.v3/avhelper
```

## 开源声明与许可

- 本项目**欢迎任何人学习、使用、修改与二次开发**，也欢迎 fork 与提交 PR。
- 但**严禁任何形式的商业使用**：不得出售、出租、付费分发，不得作为付费产品或付费服务的一部分
  （含代部署、代配置、付费教程社群等），不得与硬件/软件/镜像/云服务捆绑销售，不得以本项目为
  卖点投放广告或引流牟利。
- 分发（含修改版）时请**保留署名与本仓库地址**，并以**相同方式共享**（继续采用同样禁止商用的许可）。
- 完整条款见 [LICENSE](LICENSE)。注意：由于禁止商用，本许可属于「源码公开（source-available）」
  许可，按 OSI 定义**不是**严格意义的开源许可。

## 致谢

- [MoviePilot](https://github.com/jxxghp/MoviePilot) —— 本插件运行所依赖的宿主
- [javdb-cli](https://github.com/FlanChanXwO/javdb-cli) —— 发现层的只读 CLI 与 Go SDK
- [MetaTube](https://github.com/metatube-community) —— 刮削层（由使用者自行部署）

---

<div align="center">
<sub>仅供学习研究 · 禁止商用 · 请遵守当地法律法规与你所使用服务的条款</sub>
</div>
