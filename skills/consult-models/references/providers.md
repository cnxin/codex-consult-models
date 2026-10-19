# Provider Reference

Read this file only for provider setup, authentication failures, model overrides, delegated work, or adapter troubleshooting.

## Availability

`scripts/consult.py list --json` reports executable paths and whether API credentials are configured. Besides `PATH`, the script looks in `~/.local/bin`, `/opt/homebrew/bin`, and `/usr/local/bin`, because agent shells often start without the login `PATH`. The skill never installs a provider automatically.

| Provider | Local dependency | Authentication | Consultation (`run`) | Delegated work (`work`) |
| --- | --- | --- | --- | --- |
| Codex | `codex` CLI | Codex login or configured provider | `codex exec --sandbox read-only --ephemeral -o FILE ...` | `--sandbox workspace-write` |
| Claude | `claude` CLI | Claude CLI login | `claude -p --output-format json ...` | `--permission-mode acceptEdits` |
| Antigravity | `agy` CLI | Antigravity login | `agy -p ... --output-format json --sandbox --disable-slash-commands --print-timeout Ns` | `--mode accept-edits --add-dir WORKDIR` |
| Gemini | `gemini` CLI | Gemini CLI login or API key | `gemini -o json -p ...` | `--approval-mode auto_edit` |
| Grok | `grok` CLI | `grok login --oauth` | `grok --output-format json --no-subagents --max-turns 1 -p ...` | not supported |
| OpenCode | `opencode` CLI | Provider configured in OpenCode | `opencode run --format json ...` | not supported |
| DeepSeek | No CLI required | `DEEPSEEK_API_KEY` | HTTPS chat completions request | not supported |

No adapter passes auto-approve, YOLO, or permission-bypass flags. Consultations start in an empty temporary directory and receive selected context only through the prompt. This reduces accidental repository access but is not an operating-system sandbox; trust the locally installed CLI itself and keep disclosure minimal.

## Delegated Work

`work` runs one provider with its working directory set to `--workdir`, which must be inside a git repository (not `/` or your home directory). It:

1. records the content digest of every dirty or untracked file and the current `HEAD`;
2. runs the provider with file-edit permission and no shell approval;
3. reports `changed_files` — paths whose content changed during the call — and `head_changed` if a commit happened.

Result fields to check:

| Field | Meaning |
| --- | --- |
| `ok` | The provider finished and either answered or changed files. |
| `changed_files` | Files to review with `git diff`. Empty with `ok: true` adds a warning. |
| `warning` | Something was refused or looks off but the result is usable. |
| `metadata.denied_actions` | Permissions the provider asked for and was refused (`write_file`, `command`, ...). |
| `session_id` | Pass to `--resume` for a follow-up turn (`agy`, `claude`). |

The worker cannot run tests. Run them yourself, then resume the session with the failure output if the worker should fix it.

## Model Overrides

Single provider:

```bash
python3 scripts/consult.py run --provider grok --model MODEL --prompt "..."
```

Panel:

```bash
python3 scripts/consult.py panel \
  --provider grok --provider deepseek \
  --model grok=MODEL \
  --model deepseek=deepseek-reasoner \
  --prompt "..."
```

If no override is supplied, each CLI uses its configured default. DeepSeek uses `DEEPSEEK_MODEL` or `deepseek-chat`.

## Antigravity (Gemini models)

Install and authenticate the official Antigravity CLI first; the installer places `agy` in `~/.local/bin` (see [Antigravity Installation & Auth](https://antigravity.google/docs/cli/install/)). Run `agy` interactively once if no cached session exists.

List the models your account can use. Pass either the slug or the display name:

```bash
python3 scripts/consult.py models
# gemini-3.8-flash-high   Gemini 3.8 Flash (High)
# ...
python3 scripts/consult.py run --provider agy --model gemini-3.8-flash-high --prompt "..."
```

Headless behaviour the adapter relies on:

- `agy -p` never prompts. Any tool not already allowed is **auto-denied**, the turn may end with an empty `response`, and the exit code stays 0. The only trace is `denied_actions` in the JSON output. consult-models turns that into `ok: false` with an explanation instead of reporting an empty success.
- `--mode accept-edits` allows file edits (`write_file`) but not shell commands (`command`).
- A stale model in `~/.gemini/antigravity-cli/settings.json` or `--model` fails with `status: "ERROR"` and a list of valid names.
- `--print-timeout` is set slightly below `--timeout` so agy stops cleanly before consult-models kills it.
- To let agy run a specific command during `work`, add a narrow rule such as `command(npm test)` under `permissions.allow` in `~/.gemini/antigravity-cli/settings.json`. Do not use `--dangerously-skip-permissions`.

## Gemini CLI

The standalone Gemini CLI is sunset for most non-enterprise accounts. When `gemini` is missing, the error suggests `--provider agy`, which serves the same Gemini model family. The `gemini` adapter remains for accounts that still have it.

## Codex

`codex` uses your `~/.codex/config.toml` defaults. To pick a different provider or profile without editing that file:

```bash
python3 scripts/consult.py run --provider codex \
  --codex-config model_provider=NAME --model MODEL --prompt "..."
export CONSULT_CODEX_PROFILE=consult            # passed as codex -p consult
export CONSULT_CODEX_CONFIG="model_provider=NAME;model_reasoning_effort=high"
```

Overrides for `sandbox*`, `approval*`, or `dangerously*` keys are rejected: the sandbox is always chosen by the command (`read-only` for consultations, `workspace-write` for `work`). The final answer comes from `codex exec -o FILE`, not from the transcript on stdout.

## Task Profiles

Task profiles save a reusable provider and model mix without storing credentials:

```bash
python3 scripts/consult.py configure --profile review
python3 scripts/consult.py profiles
python3 scripts/consult.py task --profile review --prompt "Review this diff."
```

Profiles live at `~/.config/codex-consult-models/config.json` with file mode `0600`. Set `CONSULT_MODELS_CONFIG` or pass `--config` to use a different path. An explicit `--model provider=MODEL` on `task` overrides the saved model for that run.

## DeepSeek

Required:

```bash
export DEEPSEEK_API_KEY="..."
```

Optional:

```bash
export DEEPSEEK_MODEL="deepseek-chat"
export DEEPSEEK_API_URL="https://api.deepseek.com/chat/completions"
```

The script reads the key from the environment and never prints it. Do not store it in the skill, a repository, a prompt, or a context file.

## Proxy Behavior

`--proxy auto` is the default. It uses existing `HTTPS_PROXY`/`HTTP_PROXY` variables, or on macOS reads the active system HTTPS proxy with `scutil --proxy`. This is useful for CLIs that do not inherit macOS system proxy settings.

Overrides:

```bash
python3 scripts/consult.py run --provider grok --proxy http://127.0.0.1:7897 --prompt "..."
python3 scripts/consult.py run --provider grok --proxy none --prompt "..."
```

Never include proxy credentials in logs or model prompts.

## Troubleshooting

- `missing executable`: install and authenticate the named provider outside this skill, then rerun `list`.
- OAuth or API timeout: test the provider endpoint through the configured proxy; do not disable TLS verification.
- Non-zero CLI exit: inspect the returned `error` field. The script truncates stderr and does not include the prompt or environment.
- `headless mode auto-denied`: the provider asked for a permission the mode does not grant. Use `work` for edits; run commands yourself.
- `work mode requires a git repository`: run `git init` or point `--workdir` at the repository.
- Context rejected: reduce file size, convert binary data to a minimal textual description, or raise `--max-context-bytes` only after reviewing disclosure scope.
- Antigravity authentication required: run `agy` interactively, complete login, then retry.
- Antigravity model not recognized: run `consult.py models` and pass an exact slug or display name.
- Codex `Model provider ... not found`: the name passed to `--codex-config model_provider=` is not defined in `~/.codex/config.toml`.
- OpenCode model not found: configure the provider in OpenCode and pass its exact `provider/model` identifier with `--model`.
