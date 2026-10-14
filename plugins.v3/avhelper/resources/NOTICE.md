# NOTICE — 第三方映射数据来源与许可

本目录下的三份数据文件**原样取自上游开源项目，未做任何修改**（逐字节一致，见下表 `git blob sha`）。
它们不是 AVHelper 自有内容，版权与许可归上游作者所有。

## 1. 上游仓库

| 项 | 值 |
| --- | --- |
| 仓库 | <https://github.com/sqzw-x/amane> （Amane，「AI 时代的私人影库」） |
| 默认分支 | `main` |
| 采集时 `main` HEAD | `7468d8e201fbd2a633435c5e13432da1d017373f`（2026-10-13T12:13:13Z） |
| 三份文件最近一次改动 | `15503a3e3f074e18267d9ca8394f8dcd1e814a80`（Initial commit，2026-08-23T10:07:28Z；此后未再改动） |
| 下载日期 | 2026-10-14（本机时间），经代理 `http://192.0.2.11:7890` 走 `raw.githubusercontent.com` |
| 许可证 | **GNU GPL v3（GPL-3.0）**，见下文 §3 |

## 2. 本目录内的文件

| 文件 | 上游路径 | 字节数 | sha256 | 上游 git blob sha |
| --- | --- | ---: | --- | --- |
| `mapping_actor.xml` | `resources/mapping_table/mapping_actor.xml` | 863,920 | `7681b71c7d38c45c1b9c6323a4b709b9d97ec5393c60293bea3b08612cdead04` | `0f268ff24837b62b16d5ea77e2019a4a77eaf15e` |
| `mapping_info.xml` | `resources/mapping_table/mapping_info.xml` | 37,911 | `f8ae4e320e8f775ed821d44a9a27259a09356b8d583014b2e4311b207d593c4f` | `e47b2afd7bb62d7323d4c4b1442ada18cb76657d` |
| `zhcdict.json` | `resources/zhconv/zhcdict.json` | 650,238 | `602a997bb2f3741239bd9c863af1fb43e4cd0059ff1ddc006a5742e4ef6954f3` | `0726df4bcae04777cb893eb22126c8bb39922166` |

> 三个 `git blob sha` 与本目录内文件的 `git hash-object` 结果**逐一相同**，可据此证明未改写（换行、BOM 均保持上游原样：LF、无 BOM）。

### 用途

| 文件 | 在 AVHelper 中的用途 |
| --- | --- |
| `mapping_actor.xml` | 演员三语映射（日文原名 / 简体中文名 / 繁体中文名 + 别名串 + 主页）：`namemap.actor_lookup()` / `actor_display()` / `actor_glossary()`（演员感知翻译词表） |
| `mapping_info.xml` | 标签/导演/系列/制作/发行 的关键词映射；`zh_cn="删除"` 的词条是**删除规则**：`namemap.tag_lookup()` / `clean_tags()` |
| `zhcdict.json` | 简繁字形字典：`namemap.to_simplified()` 的**正向最大匹配**词表（取其中的 `zh2Hans` 段） |

结构、统计与解析口径的实测细节见 `_tmp/p0/REPORT-4.md`（开发报告，不随包发布）。

## 3. 许可证原文（关键段落）

上游仓库根目录 `LICENSE`（35,149 字节 / 674 行 / blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`）是**未经改动的 GNU GPL v3 标准全文**，未填写版权人，`README.md` 徽章为 `License-GPLv3`，GitHub 识别为 `GPL-3.0`。
原文开头：

```
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.
```

与再分发相关的核心条款（节选，全文见上游 `LICENSE`）：

```
  5. Conveying Modified Source Versions.
  ...
  The work must carry prominent notices stating that you modified it, and
giving the relevant date.
  ...
  6. Conveying Non-Source Forms.
  ...
  You may convey a covered work in object code form under the terms of
sections 4 and 5, provided that you also convey the machine-readable
Corresponding Source ...
  ...
  10. Automatic Licensing of Downstream Recipients.
  ...
  You may not impose any further restrictions on the exercise of the rights
granted or affirmed under this License. ...
```

**未发现任何附加条款**：仓库内没有 `COPYING` / `NOTICE` / `LICENCE` / `TRADEMARK` 等补充文件；`AI_POLICY.md` 只约束 Issue/PR 的 AI 使用流程，`AGENTS.md` 是开发约定，均不含许可条款。上游也**没有**写 "or any later version"，故按 GPL-3.0-only 理解。

## 4. 使用性质与合规提示（AVHelper 侧）

- 本目录的三份文件为**数据文件**，随 AVHelper 插件包一起分发时，须保留本 NOTICE 与上游出处，不得删除或篡改。
- **【2026-10-14 决议·已执行】许可冲突的处置：AVHelper 整体切换到 GPL-3.0。**
  原先 AVHelper 用的是自定义「非商业学习许可协议」（禁止商业使用，自述"不是 OSI 认可的开源许可"），与 GPL-3.0 第 10 条
  「不得对下游追加限制」直接冲突。经项目所有者明确决策，仓库根 `LICENSE` 已替换为 **GNU GPL v3.0 全文**，
  `README.md` 的许可段落与 `package.v3.json` 的描述同步更新，三份数据文件因此可以**继续随包分发**。
  （决策前评估的另外两条路 —— ① 不随包分发、由用户自行放置到插件数据目录的 `resources/`；② 向上游请求书面例外 ——
  记录在 `_tmp/p0/REPORT-4.md` §6；将来若要改回非商业许可，必须先走其中一条。）
- 本目录文件不构成对上游的背书；上游与 AVHelper 之间无任何隶属或合作关系。
