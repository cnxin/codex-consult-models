# Consult Models

[English](README.md) | 简体中文

`consult-models` 是一个给 Codex 和 Claude Code 用的 Skill：让主控 Agent 去问其他
AI 模型要独立意见（Codex、Claude、Grok、Antigravity/Gemini、DeepSeek、OpenCode），
或者把一个边界清楚的编码任务直接派给它们去做。主控 Agent 始终说了算：发什么内容
出去由它决定，每一处改动由它审 diff，测试也由它亲自跑。

工作流参考了 [`fengshao1227/ccg-workflow`](https://github.com/fengshao1227/ccg-workflow)，
并按 Skill 的形式和「最小化披露上下文」的原则做了改造。

## 亮点

- 可以只问一个模型，也可以让 2–4 个模型组成评审团并发作答。
- **干活模式（`work`）**：在一个 git 仓库里授予文件编辑权限把任务派出去，结束后
  准确告诉你这次改了哪些文件。
- Antigravity 无头模式下的权限拒绝会被识别并说明原因，不会再被当成「空回复的成功」。
- 用 `--resume SESSION_ID` 接着上一次的 Antigravity / Claude 对话追问或返工。
- 保存常用的「模型组合」任务配置，一条命令调用。
- 咨询模式在空的临时目录里启动，只发送你明确指定的提示词和上下文文件
  （默认总上限 256 KiB）。
- 从不传自动批准、YOLO 或跳过权限之类的参数；即使在 `work` 模式下，shell 命令也不放行。
- 各家输出统一整理成一致的 JSON 结果。
- 按需复用终端或 macOS 系统代理设置。

## 支持的模型

| 提供方 | 接入方式 | 前置条件 | 支持 `work` |
| --- | --- | --- | --- |
| Codex | 本地 CLI | 已安装并登录 `codex` | 是 |
| Claude | 本地 CLI | 已安装并登录 `claude` | 是 |
| Antigravity | 本地 CLI | 已安装并登录 `agy` | 是 |
| Gemini | 本地 CLI | 已安装 `gemini`（多数账号已停服，请改用 Antigravity） | 是 |
| Grok | 本地 CLI | 已安装并登录 `grok` | 否 |
| OpenCode | 本地 CLI | 已安装并配置 `opencode` | 否 |
| DeepSeek | HTTPS API | 设置环境变量 `DEEPSEEK_API_KEY` | 否 |

Gemini 系列模型通过 Antigravity 调用（`--provider agy`）。适配器使用无头 JSON 模式并带
`--sandbox`，只有 `work` 才会加 `--mode accept-edits`，并且从不传
`--dangerously-skip-permissions`。

## 安装

### Claude Code

```bash
git clone https://github.com/cnxin/codex-consult-models
mkdir -p ~/.claude/skills
cp -R codex-consult-models/skills/consult-models ~/.claude/skills/
```

新开一个 Claude Code 会话，Skill 就会被识别。如果不想每次调用都弹权限确认，可以在设置里放行这个脚本：

```json
{ "permissions": { "allow": ["Bash(python3 ~/.claude/skills/consult-models/scripts/consult.py:*)"] } }
```

### Codex

对 Codex 说：

```text
Install the consult-models Skill from
https://github.com/cnxin/codex-consult-models/tree/main/skills/consult-models
```

或者手动把 `skills/consult-models` 复制到 `~/.codex/skills/consult-models`。
安装后重启 Codex 或新开一个任务，让它重新发现 Skill。

## 使用

需要把内容发给外部模型时，明确点名这个 Skill：

```text
用 consult-models 让 Grok 对这个 API 设计给个第二意见。
```

```text
用 consult-models 让 Antigravity（Gemini 3.8 Flash）修好 src/date.ts 里出错的日期解析，
然后你审一下它的 diff 并跑测试。
```

也可以直接运行脚本：

```bash
python3 skills/consult-models/scripts/consult.py list --json      # 检查各家是否可用
python3 skills/consult-models/scripts/consult.py models           # 列出 Antigravity 可用模型名

# 只读咨询
python3 skills/consult-models/scripts/consult.py run --provider agy \
  --model gemini-3.8-flash-high --prompt "评审这个设计。" --json

# 派活：允许它在仓库里改文件
python3 skills/consult-models/scripts/consult.py work --provider agy \
  --workdir /path/to/repo --prompt "修好 calc.py 里的 add()，别的不要动。" --json

# 接着同一个会话返工
python3 skills/consult-models/scripts/consult.py work --provider agy \
  --workdir /path/to/repo --resume SESSION_ID --prompt "测试报错：……请修复。"
```

### `work` 的结果怎么看

| 字段 | 含义 |
| --- | --- |
| `ok` | 模型跑完了，并且给出了回复或改了文件 |
| `changed_files` | 本次调用里内容发生变化的文件（运行前就有的未提交改动不算），用 `git diff` 审查 |
| `warning` | 有操作被拒或结果可疑，但结果仍可用（例如改完文件后想跑测试被拒） |
| `metadata.denied_actions` | 模型申请过但被拒的权限（`write_file`、`command` 等） |
| `session_id` | 传给 `--resume` 继续对话（agy、claude） |
| `head_changed` | 模型擅自提交了，需要检查 `git log` |

`work` 要求 `--workdir` 在 git 仓库里（且不能是 `/` 或家目录），默认超时 900 秒。被派活的模型不能跑命令，
测试由主控 Agent 自己跑；失败了就带着报错用 `--resume` 让它返工。

### 保存任务配置

在交互式终端面板里创建或编辑配置：

```bash
python3 skills/consult-models/scripts/consult.py configure --profile review
```

面板里选择提供方和可选的模型覆盖。配置不包含任何凭据，保存在
`~/.config/codex-consult-models/config.json`，文件权限为 `0600`。

```bash
python3 skills/consult-models/scripts/consult.py profiles

python3 skills/consult-models/scripts/consult.py task \
  --profile review \
  --prompt "从正确性和安全性角度评审这个 API 设计。" \
  --json
```

提供方安装、派活细节、模型覆盖、Codex 的 provider 覆盖、代理和故障排查，见
[`skills/consult-models/references/providers.md`](skills/consult-models/references/providers.md)（英文）。

## 常见问题

- **Antigravity 回复为空 / 什么都没做**：agy 无头模式不会弹确认，凡是没授权的操作都会被自动拒绝，
  而且退出码仍是 0。本工具会把它报成 `ok: false` 并说明被拒的是什么。需要改文件请用 `work`；
  需要跑命令请自己跑，或在 `~/.gemini/antigravity-cli/settings.json` 的 `permissions.allow`
  里加一条范围很窄的规则（例如 `command(npm test)`）。
- **提示模型不存在**：Antigravity 的模型名会随版本变化（例如 3.7 → 3.8），先运行 `models` 再选。
  也记得检查 `~/.gemini/antigravity-cli/settings.json` 里的默认模型是否还有效。
- **找不到 `gemini`**：Gemini CLI 对多数账号已停服，改用 `--provider agy`。
- **Codex 提示 `Model provider ... not found`**：`--codex-config model_provider=` 传的名字没有在
  `~/.codex/config.toml` 里定义。

## 安全模型

外部调用会把提示词和你明确提供的上下文发送给对应的提供方。未经知情授权，不要包含密钥、凭据、
个人数据、私有代码或未公开的材料。

空的临时工作目录能减少意外读取仓库，但它不是操作系统级沙箱：本地安装的 CLI 及其账号配置仍在信任边界内。
`work` 只授予一个 git 仓库内的文件编辑权限，其他一概不给；主控 Agent 必须自己审 diff、跑验证。
任何模型的回复都只当作不可信的建议。

## 开发

运行时只依赖 Python 标准库。运行测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

发布前用 Codex 的 `quick_validate.py` 校验 Skill 目录。

## 许可证

[MIT](LICENSE)
