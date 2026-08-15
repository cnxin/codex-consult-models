# Provider Reference

Read this file only for provider setup, authentication failures, model overrides, or adapter troubleshooting.

## Availability

`scripts/consult.py list --json` reports executable paths and whether API credentials are configured. The skill never installs a provider automatically.

| Provider | Local dependency | Authentication | Default invocation |
| --- | --- | --- | --- |
| Claude | `claude` CLI | Claude CLI login | `claude -p ... --output-format json` |
| Grok | `grok` CLI | `grok login --oauth` | `grok --output-format json --no-subagents --max-turns 1 -p ...` |
| Gemini | `gemini` CLI | Gemini CLI login or its supported API key | `gemini -o json -p ...` |
| OpenCode | `opencode` CLI | Provider configured in OpenCode | `opencode run --format json ...` |
| DeepSeek | No CLI required | `DEEPSEEK_API_KEY` | HTTPS request to the OpenAI-compatible chat completions endpoint |

The CLI adapters deliberately omit auto-approve, YOLO, and permission-bypass flags. They start in an empty temporary working directory and receive selected context only through the prompt. This reduces accidental repository access but is not an operating-system sandbox; trust the locally installed CLI itself and keep disclosure minimal.

## Model Overrides

Single-provider mode:

```bash
python3 scripts/consult.py run --provider grok --model MODEL --prompt "..."
```

Panel mode:

```bash
python3 scripts/consult.py panel \
  --provider grok --provider deepseek \
  --model grok=MODEL \
  --model deepseek=deepseek-reasoner \
  --prompt "..."
```

If no override is supplied, each CLI uses its configured default. DeepSeek uses `DEEPSEEK_MODEL` or `deepseek-chat`.

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
- Context rejected: reduce file size, convert binary data to a minimal textual description, or raise `--max-context-bytes` only after reviewing disclosure scope.
- OpenCode model not found: configure the provider in OpenCode and pass its exact `provider/model` identifier with `--model`.
