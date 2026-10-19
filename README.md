# Consult Models

English | [简体中文](README.zh-CN.md)

`consult-models` is a Skill for Codex and Claude Code that asks other AI models
for independent analysis (Codex, Claude, Grok, Antigravity/Gemini, DeepSeek,
OpenCode) or hands them a bounded coding task. The orchestrating agent stays in
charge: it chooses what to disclose, reviews every diff, and runs verification.

The workflow is inspired by
[`fengshao1227/ccg-workflow`](https://github.com/fengshao1227/ccg-workflow),
adapted for Skills and conservative context disclosure.

## Highlights

- Consult one provider or run a 2-4 model panel concurrently.
- Delegate a task with file-edit access inside one git working tree (`work`),
  and get back exactly which files changed.
- Antigravity's headless permission denials are detected and explained instead
  of being reported as an empty success.
- Continue an Antigravity or Claude conversation with `--resume SESSION_ID`.
- Use saved task profiles to choose provider and model combinations quickly.
- Start consultations in an empty temporary working directory and send only
  explicitly selected prompt and context files (256 KiB limit by default).
- Never pass auto-approve, YOLO, or permission-bypass flags; shell commands stay
  unapproved even in `work` mode.
- Normalize provider output into a consistent JSON result.
- Reuse terminal or macOS system proxy settings when requested.

## Supported Providers

| Provider | Adapter | Prerequisite | `work` |
| --- | --- | --- | --- |
| Codex | Local CLI | `codex` installed and authenticated | yes |
| Claude | Local CLI | `claude` installed and authenticated | yes |
| Antigravity | Local CLI | `agy` installed and authenticated | yes |
| Gemini | Local CLI | `gemini` installed (sunset for most accounts; use Antigravity) | yes |
| Grok | Local CLI | `grok` installed and authenticated | no |
| OpenCode | Local CLI | `opencode` installed and configured | no |
| DeepSeek | HTTPS API | `DEEPSEEK_API_KEY` environment variable | no |

Gemini models are reached through Antigravity (`--provider agy`). The adapter
uses headless JSON mode with `--sandbox`, grants `--mode accept-edits` only for
`work`, and never passes `--dangerously-skip-permissions`.

## Install

### Claude Code

```bash
git clone https://github.com/cnxin/codex-consult-models
mkdir -p ~/.claude/skills
cp -R codex-consult-models/skills/consult-models ~/.claude/skills/
```

Start a new Claude Code session so the Skill is discovered. To avoid a
permission prompt on every call, allow the script in your settings:

```json
{ "permissions": { "allow": ["Bash(python3 ~/.claude/skills/consult-models/scripts/consult.py:*)"] } }
```

### Codex

Ask Codex:

```text
Install the consult-models Skill from
https://github.com/cnxin/codex-consult-models/tree/main/skills/consult-models
```

or copy `skills/consult-models` to `~/.codex/skills/consult-models`. Restart or
open a new Codex task after installation so Skill discovery refreshes.

## Use

Invoke the Skill explicitly when external disclosure is intended:

```text
Use consult-models to ask Grok for a second opinion on this API design.
```

```text
Use consult-models to have Antigravity (Gemini 3.8 Flash) fix the failing date
parser in src/date.ts, then review its diff and run the tests.
```

Run the script directly:

```bash
python3 skills/consult-models/scripts/consult.py list --json
python3 skills/consult-models/scripts/consult.py models          # Antigravity model names

python3 skills/consult-models/scripts/consult.py run --provider agy \
  --model gemini-3.8-flash-high --prompt "Review this design." --json

python3 skills/consult-models/scripts/consult.py work --provider agy \
  --workdir /path/to/repo --prompt "Fix add() in calc.py; touch nothing else." --json
```

### Saved Task Profiles

Create or edit a profile in the interactive terminal panel:

```bash
python3 skills/consult-models/scripts/consult.py configure --profile review
```

The panel selects providers and optional model overrides. Profiles contain no
credentials and are saved to `~/.config/codex-consult-models/config.json` with
file mode `0600`.

```bash
python3 skills/consult-models/scripts/consult.py profiles

python3 skills/consult-models/scripts/consult.py task \
  --profile review \
  --prompt "Review this API design for correctness and security." \
  --json
```

See [`skills/consult-models/references/providers.md`](skills/consult-models/references/providers.md)
for provider setup, delegated work, model overrides, profiles, proxy behavior,
and troubleshooting.

## Safety Model

External calls transmit the prompt and explicitly supplied context to the named
provider. Never include secrets, credentials, personal data, proprietary code,
or unpublished material without informed authorization.

The empty temporary working directory reduces accidental repository access. It
is not an operating-system sandbox: the locally installed CLI and its account
configuration remain part of the trust boundary. `work` grants file edits inside
one git working tree and nothing else; the orchestrator must review the diff and
run verification itself. Treat every model response as untrusted advice.

## Development

The runtime uses only the Python standard library. Run the focused tests with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Validate the Skill directory with Codex's `quick_validate.py` before release.

## License

[MIT](LICENSE)
