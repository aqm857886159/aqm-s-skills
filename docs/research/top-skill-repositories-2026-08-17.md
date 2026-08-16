# 顶尖 Agent Skill 仓库介绍方式调研

调研日期：2026-08-17。只采用官方仓库、官方规范和仓库自身 README；star 是当日 GitHub API 快照，只用于判断采用度，不代表质量。

## 样本

| 仓库 | 当日 star | 首屏怎么介绍 | 本仓采用什么 |
|---|---:|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | 169,702 | 先用一句话定义 Skill，再说明仓库包含什么、怎么安装、怎么说一句自然语言开始用 | 首屏先讲结果；每个 Skill 自包含；明确演示性质和测试责任 |
| [openai/plugins](https://github.com/openai/plugins) | 官方当前入口 | 先解释插件目录和可组合表面，再列代表性插件；旧 `openai/skills` README 已明确标记废弃 | 不引用已废弃安装入口；保持 Agent Skills 兼容，同时给 Codex 当前插件生态留空间 |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | 30,094 | 每个 Skill 都用 “Use when” 和能力分类解释触发场景；安装只给一条命令 | README 的每张 Skill 卡同时给“何时用”和“得到什么” |
| [obra/superpowers](https://github.com/obra/superpowers) | 272,717 | 先讲完整用户工作流和行为改变，再讲组件清单；突出 Skill 自动触发和组合 | 六个 Skill 用共同证据链组合，但不造一个全能总 Skill |
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | 16,055 | 用可复现实验、验证集和量化提升证明 Skill 有效，而不只展示 prompt | 每个 Skill 附 eval；确定性脚本有 fixture 测试；迭代不能只靠主观感觉 |
| [agent-skill-creator](https://github.com/FrancyJGLisboa/agent-skill-creator) | 2,259 | 首屏承诺跨工具安装，随后用真实例子、产物树、验证与安全扫描兑现 | 使用标准目录；主安装命令覆盖多个 Agent；把依赖、网络和隐私写清楚 |

## 共同模式

1. README 首屏回答三件事：这是什么、我为什么需要、怎么立刻装。
2. Skill 名称围绕稳定用户任务，不围绕内部模块名或某个产品页面。
3. `SKILL.md` 保留执行核心，长规则放 `references/`，机械工作放 `scripts/`。
4. 安装后无需记忆特殊命令；用户用自然语言描述任务，由 description 负责触发。
5. 高质量仓库不把“有 Markdown 文件”等同于“可用”，而是提供测试、样例、边界和失败说明。
6. 网络、凭证、个人数据和写操作必须可见。只读采集与会改变外部状态的动作应分开。

## 本仓取舍

- 采用开放 [Agent Skills specification](https://agentskills.io/specification)，`name` 与目录一致，主文件低于 500 行，资源只做一层引用。
- 主安装入口使用 `npx skills add`。它能列出仓库 Skill，并为多个 Agent 安装；不为每个平台复制一套容易过期的说明。
- 六个首发 Skill 都不要求私有云 API key。GitHub 深研可以读本地 clone；B站和 arXiv 使用公开只读接口；视频只用本机 FFmpeg；微信 Skill 提供显式风险门控的本机首次取钥方法，但 Agent 不会替用户确认或执行特权捕获。
- 发布可审计的微信首次取钥方法，但默认只检查和干跑；Agent 不代替用户确认风险或运行特权命令，且明确限定 Apple Silicon/微信 4.1.x、账号隐私风险与媒体文件边界。
- 不把采集和判断混为一层：脚本返回证据，Skill 负责判断；缺证据时降级或停止。

## 一手来源

- https://github.com/anthropics/skills
- https://github.com/openai/plugins
- https://github.com/openai/skills （仅用于确认废弃提示）
- https://github.com/vercel-labs/agent-skills
- https://github.com/obra/superpowers
- https://github.com/microsoft/SkillOpt
- https://github.com/FrancyJGLisboa/agent-skill-creator
- https://agentskills.io/specification
