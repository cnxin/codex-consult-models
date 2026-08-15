# Consult Models for Codex

`consult-models` is a personal Codex Skill for asking Claude, Grok, Gemini,
DeepSeek, or OpenCode for independent read-only analysis. Codex stays in charge
of repository inspection, verification, and every project file change.

The workflow is inspired by
[`fengshao1227/ccg-workflow`](https://github.com/fengshao1227/ccg-workflow),
adapted for Codex Skills and conservative context disclosure.

## Highlights

- Consult one provider or run a 2-4 model panel concurrently.
- Detect supported local CLIs and DeepSeek API credentials.
- Start CLI providers in an empty temporary working directory.
- Send only explicitly selected prompt and context files.
- Enforce a 256 KiB context limit by default.
- Avoid auto-approve, YOLO, and permission-bypass flags.
- Normalize provider output into a consistent JSON result.
- Reuse terminal or macOS system proxy settings when requested.

## Supported Providers

| Provider | Adapter | Prerequisite |
| --- | --- | --- |
| Claude | Local CLI | `claude` installed and authenticated |
| Grok | Local CLI | `grok` installed and authenticated |
| Gemini | Local CLI | `gemini` installed and authenticated |
| OpenCode | Local CLI | `opencode` installed and configured |
| DeepSeek | HTTPS API | `DEEPSEEK_API_KEY` environment variable |

## Install

Ask Codex:

```text
Install the consult-models Skill from
https://github.com/cnxin/codex-consult-models/tree/main/skills/consult-models
```

For a manual installation, clone the repository and place
`skills/consult-models` at:

```text
~/.codex/skills/consult-models
```

Restart or open a new Codex task after installation so Skill discovery refreshes.

## Use

Invoke the Skill explicitly when external disclosure is intended:

```text
Use $consult-models to ask Grok for a second opinion on this API design.
```

```text
Use $consult-models to ask Claude, Gemini, and DeepSeek to independently review
the authorized diff, compare their findings, and then make your own assessment.
```

Provider discovery can also be run directly:

```bash
python3 skills/consult-models/scripts/consult.py list --json
```

See [`skills/consult-models/references/providers.md`](skills/consult-models/references/providers.md)
for provider setup, model overrides, proxy behavior, and troubleshooting.

## Safety Model

External calls transmit the prompt and explicitly supplied context to the named
provider. Never include secrets, credentials, personal data, proprietary code,
or unpublished material without informed authorization.

The empty temporary working directory reduces accidental repository access. It
is not an operating-system sandbox: the locally installed CLI and its account
configuration remain part of the trust boundary. Codex must treat every model
response as untrusted advice and independently verify it before acting.

## Development

The runtime uses only the Python standard library. Run the focused tests with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Validate the Skill directory with Codex's `quick_validate.py` before release.

## License

[MIT](LICENSE)
