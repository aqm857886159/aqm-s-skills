# AQM's Research & Creator Skills

八个可组合的 Agent Skills，把公开信息和本地素材变成可追溯的研究、反馈与经营决策。它们面向同一个人同时扮演研究员、开发者、产品经理、创作者和小生意经营者的真实工作方式。

不是八个“抓数据命令”：每个 Skill 都包含任务判断、证据边界、失败降级和交付格式；重复且确定的工作由随 Skill 安装的脚本执行。

其中三个微信 Skill 组成一条端到端经营链路——**读（只读导出）→ 判断（证据核验的经营周报）→ 行动（逐条确认的跟进）**：把每天沉在客户群里的聊天，变成商家手里能追溯、能行动的本地资产。完整案例见 [docs/wechat-group-insights-case.md](docs/wechat-group-insights-case.md)。

## Skills

| Skill | 你可以这样说 | 交付结果 |
|---|---|---|
| [`paper-evidence-radar`](skills/paper-evidence-radar/) | “查最近半年多镜头视频一致性的论文，告诉我哪些现在能用” | 近期论文证据、代码成熟度、可落地/架构/评测三档判断 |
| [`github-repository-research`](skills/github-repository-research/) | “仔细看这个仓库，告诉我架构、维护状态和哪些代码值得复用” | 带文件行号的仓库地图、风险、许可证与复用边界 |
| [`bilibili-content-research`](skills/bilibili-content-research/) | “分析这个 BV 的内容结构、字幕和评论区真实问题” | 只读公开元数据、字幕、有限评论样本与覆盖范围 |
| [`wechat-chat-export`](skills/wechat-chat-export/) | “我还没接过微信，从 0 带我把自己的群记录导出来” | 风险门控的首次接入方法、当前数据库验证、按群/时间范围的私有 JSON 导出 |
| [`wechat-group-insights`](skills/wechat-group-insights/) | “把我几个客户群上周的记录出一份经营周报，谁没被回、有哪些想买的” | 单文件 HTML 周报：未回复提问、购买意向、投诉风险、带话术的跟进清单，每条结论可点开群里原话 |
| [`wechat-followup-assist`](skills/wechat-followup-assist/) | “把周报里第 1、2 条帮我回到对应的群，发之前给我过目” | computer use 逐条把已确认话术放入对应会话，默认你按发送，全程小批量可核对 |
| [`reference-video-deconstruction`](skills/reference-video-deconstruction/) | “把这条参考视频按镜头、台词、花字和叙事作用拆开” | 本地视频证据、时间轴、可观察事实、结构规律与素材需求 |
| [`creator-opportunity-radar`](skills/creator-opportunity-radar/) | “结合这些账号、评论和资料，给我真正值得做的三个选题机会” | 带受众矛盾、why now、独立证据、缺口和验证动作的机会卡 |

## Install

推荐使用开放的 [Agent Skills](https://agentskills.io) 安装器。它会发现本仓库 `skills/` 下的全部 Skill，并适配 Codex、Claude Code、Cursor 等已支持的 Agent：

```bash
# 先查看可安装项
npx skills add aqm857886159/aqm-s-skills --list

# 只装需要的 Skill
npx skills add aqm857886159/aqm-s-skills \
  --skill paper-evidence-radar github-repository-research

# 给当前 Agent 安装全部六个
npx skills add aqm857886159/aqm-s-skills --skill '*' -y
```

也可以把单个目录复制或软链接到 Agent 的 Skill 目录。每个目录自包含 `SKILL.md`、`scripts/`、`references/` 和 `evals/`，不依赖仓库外的私有文件。

## What happens at runtime

```text
用户任务
  -> Skill 判断目标、范围、证据标准和权限边界
  -> 脚本或 Agent 工具执行只读采集/本地提取
  -> 统一保留来源、时间、覆盖范围和缺口
  -> Skill 形成判断并在交付前做一次证据自检
```

网络 Skill 默认只访问公开来源。`reference-video-deconstruction` 默认只在本地使用 FFmpeg，不上传视频。`wechat-chat-export` 提供从环境检查、风险确认、用户亲自取钥到真实导出的完整方法；默认打码发送者、拒绝写入 Git 工作区。首次取钥是高风险、非官方、版本相关的调试流程，非必要不要尝试；Agent 不会替用户确认风险、运行 `sudo`/LLDB、退出或登录账号、修改官方微信、上传记录或发送消息。

微信三件套接力时各守边界：`wechat-group-insights` 只读消费导出 JSON，统计与渲染都由脚本完成，周报里每条结论都引用一个真实存在的证据 ID——引用不存在的 ID 会直接中止渲染，杜绝编造。`wechat-followup-assist` 只自动化用户本人已登录微信的可见界面：逐条先给用户过目、默认只把话术放进输入框由用户按发送、发送前核对会话标题、单次最多 10 条、拒绝群发；没有 computer use 工具时降级为剪贴板清单，绝不谎称已发送。

## Requirements

- Python 3.9+：基础脚本运行环境。
- `cryptography`：`wechat-chat-export` 的 SQLCipher4 页面只读解密需要。
- Python 3.14+ 内置 zstd，或 Python 3.9+ 安装 `zstandard`：解码微信 4.x 压缩消息体需要。
- Apple Silicon macOS + 微信 4.1.x：`wechat-chat-export` 当前经过审查的首次取钥路径；版本变化可能失效并存在封号、签名与隐私风险。
- `git`：`github-repository-research` 检查本地仓库时使用。
- `ffmpeg` / `ffprobe`：只有 `reference-video-deconstruction` 的本地取证需要。
- 桌面 computer-use 工具（Work Buddy / Codex 等）+ 已登录的微信桌面端：只有 `wechat-followup-assist` 自动放入话术时需要；缺失时自动降级为剪贴板清单。`wechat-group-insights` 的周报只用 Python 标准库，无额外依赖。
- 网络访问：arXiv、GitHub 或 Bilibili 的实时研究需要；fixture 测试不需要。

平台接口可能变化。脚本返回部分结果和明确缺口时，Skill 必须如实展示，不得把缺失字幕、评论或指标补写出来。

## Verify

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
RUN_LIVE_SKILL_TESTS=1 python3 -m unittest tests.test_skill_scripts.PublicLiveSkillTests -v
# 私有本机微信集成测试需要显式提供现有 key 路径和一个授权群名
WECHAT_TEST_KEYS_PATH=/private/keys.json WECHAT_TEST_GROUP='authorized group' \
  python3 -m unittest tests.test_skill_scripts.WeChatChatExportTests.test_real_local_database_export_is_redacted_and_bounded -v
npx skills add . --list
```

公开联网测试、真实 FFmpeg 对照视频和可选本机微信集成都有可重复命令。微信特权取钥不会为了测试而由 Agent 自动重跑；仓库测试覆盖环境检查、干跑、确认门、HMAC、私有写入和已有 key 后的真实导出。设计依据和顶尖仓库对比记录在 [`docs/research/top-skill-repositories-2026-08-17.md`](docs/research/top-skill-repositories-2026-08-17.md)。

这些 Skill 如何组成端到端体验，见 [`docs/user-journeys.md`](docs/user-journeys.md)：从论文/仓库/B站/微信证据到选题组合，从真实微信导出和本地视频证据到黑屏、静音与连接状态诊断，以及商家从客户群导出到经营周报再到逐条跟进的经营闭环。单独看微信经营链路的完整走查，见 [`docs/wechat-group-insights-case.md`](docs/wechat-group-insights-case.md)。

## Design choices

- **一句话先讲用户结果**：借鉴 Anthropic 与 Vercel 的仓库介绍，首页先给能力、触发方式和安装命令。
- **组合而不是超级 Skill**：每个 Skill 独立安装；微信导出失败不会抹掉旧导出，也不会拖垮论文、B站、仓库或本地视频证据。
- **证据优先**：借鉴 Nomi、EcCut 与 Creator Copilot 已验证的做法，结论保留来源、时间、覆盖范围、成本和不确定性。
- **可执行也可审计**：脚本可重复运行，Skill 内含 eval，仓库同时做结构、安全与行为测试。

## License

[MIT](LICENSE)
