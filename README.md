# AQM's Research & Creator Skills

六个可组合的 Agent Skills，把公开信息和本地素材变成可追溯的研究、反馈与创作决策。它们面向同一个人同时扮演研究员、开发者、产品经理、创作者和剪辑师的真实工作方式。

不是六个“抓数据命令”：每个 Skill 都包含任务判断、证据边界、失败降级和交付格式；重复且确定的工作由随 Skill 安装的脚本执行。

## Skills

| Skill | 你可以这样说 | 交付结果 |
|---|---|---|
| [`paper-evidence-radar`](skills/paper-evidence-radar/) | “查最近半年多镜头视频一致性的论文，告诉我哪些现在能用” | 近期论文证据、代码成熟度、可落地/架构/评测三档判断 |
| [`github-repository-research`](skills/github-repository-research/) | “仔细看这个仓库，告诉我架构、维护状态和哪些代码值得复用” | 带文件行号的仓库地图、风险、许可证与复用边界 |
| [`bilibili-content-research`](skills/bilibili-content-research/) | “分析这个 BV 的内容结构、字幕和评论区真实问题” | 只读公开元数据、字幕、有限评论样本与覆盖范围 |
| [`community-feedback-radar`](skills/community-feedback-radar/) | “把 GitHub Issue、B站评论和这份聊天导出整理成反馈雷达” | 脱敏去重后的 bug/需求/答疑/夸奖/噪音分诊板 |
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

网络 Skill 默认只访问公开来源。`reference-video-deconstruction` 默认只在本地使用 FFmpeg，不上传视频。`community-feedback-radar` 默认打码作者，并且不会回复评论、发群消息、自动修代码或创建 Issue。

## Requirements

- Python 3.9+：六个 Skill 的确定性脚本均只用标准库。
- `git`：`github-repository-research` 检查本地仓库时使用。
- `ffmpeg` / `ffprobe`：只有 `reference-video-deconstruction` 的本地取证需要。
- 网络访问：arXiv、GitHub 或 Bilibili 的实时研究需要；fixture 测试不需要。

平台接口可能变化。脚本返回部分结果和明确缺口时，Skill 必须如实展示，不得把缺失字幕、评论或指标补写出来。

## Verify

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
npx skills add . --list
```

联网 smoke 和本地 FFmpeg 旅程见各 Skill 的 `evals/evals.json`。设计依据和顶尖仓库对比记录在 [`docs/research/top-skill-repositories-2026-08-17.md`](docs/research/top-skill-repositories-2026-08-17.md)。

六个 Skill 如何组成两条端到端体验，见 [`docs/user-journeys.md`](docs/user-journeys.md)：一条从论文/仓库/社区证据到选题组合，一条从历史反馈和本地视频证据到黑屏、静音与连接状态诊断。

## Design choices

- **一句话先讲用户结果**：借鉴 Anthropic 与 Vercel 的仓库介绍，首页先给能力、触发方式和安装命令。
- **组合而不是超级 Skill**：每个 Skill 独立安装；反馈雷达可以调用 B站/仓库 Skill，但连接器失效不会拖垮其他来源。
- **证据优先**：借鉴 Nomi、EcCut 与 Creator Copilot 已验证的做法，结论保留来源、时间、覆盖范围、成本和不确定性。
- **可执行也可审计**：脚本可重复运行，Skill 内含 eval，仓库同时做结构、安全与行为测试。

## License

[MIT](LICENSE)
