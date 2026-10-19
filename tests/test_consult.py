#!/usr/bin/env python3
"""Focused tests for consult.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "consult-models"
    / "scripts"
    / "consult.py"
)
SPEC = importlib.util.spec_from_file_location("consult_models_script", SCRIPT_PATH)
assert SPEC and SPEC.loader
consult = importlib.util.module_from_spec(SPEC)
# dataclasses resolve annotations through sys.modules.
sys.modules[SPEC.name] = consult
SPEC.loader.exec_module(consult)


class CommandConstructionTests(unittest.TestCase):
    def test_claude_omits_permission_bypass(self) -> None:
        with mock.patch.object(consult, "executable_for", return_value="/cli/claude"):
            command = consult.command_for("claude", "task", None)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertEqual(command[-1], "task")

    def test_grok_disables_subagents_and_auto_approve(self) -> None:
        with mock.patch.object(consult, "executable_for", return_value="/cli/grok"):
            command = consult.command_for("grok", "task", "model-x")
        self.assertIn("--no-subagents", command)
        self.assertNotIn("--always-approve", command)
        self.assertIn("model-x", command)

    def test_gemini_omits_yolo_flag(self) -> None:
        with mock.patch.object(consult, "executable_for", return_value="/cli/gemini"):
            command = consult.command_for("gemini", "task", None)
        self.assertNotIn("-y", command)
        self.assertEqual(command[-1], "task")

    def test_agy_uses_sandbox_without_permission_bypass(self) -> None:
        with mock.patch.object(consult, "executable_for", return_value="/cli/agy"):
            command = consult.command_for(
                "agy", "task", "Gemini 3.8 Flash (High)"
            )
        self.assertIn("--sandbox", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertEqual(command[-2:], ["--model", "Gemini 3.8 Flash (High)"])

    def test_agy_read_mode_bounds_print_time_and_slash_commands(self) -> None:
        options = consult.CallOptions(timeout=120)
        with mock.patch.object(consult, "executable_for", return_value="/cli/agy"):
            command = consult.command_for("agy", "task", None, options)
        self.assertIn("--disable-slash-commands", command)
        self.assertEqual(command[command.index("--print-timeout") + 1], "115s")
        self.assertNotIn("--mode", command)

    def test_agy_edit_mode_accepts_edits_only(self) -> None:
        options = consult.CallOptions(
            access="edit", workdir="/repo", resume="conv-1", effort="high"
        )
        with mock.patch.object(consult, "executable_for", return_value="/cli/agy"):
            command = consult.command_for("agy", "task", None, options)
        self.assertEqual(command[command.index("--mode") + 1], "accept-edits")
        self.assertEqual(command[command.index("--add-dir") + 1], "/repo")
        self.assertEqual(command[command.index("--conversation") + 1], "conv-1")
        self.assertIn("--sandbox", command)
        self.assertNotIn("--dangerously-skip-permissions", command)

    def test_codex_sandbox_follows_access(self) -> None:
        with mock.patch.object(consult, "executable_for", return_value="/cli/codex"):
            read = consult.command_for("codex", "task", "m", consult.CallOptions())
            edit = consult.command_for(
                "codex", "task", None, consult.CallOptions(access="edit")
            )
        self.assertEqual(read[read.index("--sandbox") + 1], "read-only")
        self.assertIn("--ephemeral", read)
        self.assertEqual(edit[edit.index("--sandbox") + 1], "workspace-write")
        for command in (read, edit):
            self.assertFalse(any("dangerously" in part for part in command))
            self.assertEqual(command[-1], "task")

    def test_codex_config_cannot_loosen_sandbox(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                consult.codex_config_overrides(["model_provider=router"]),
                ("model_provider=router",),
            )
            for bad in ("sandbox_mode=danger-full-access", "approval_policy=never", "x"):
                with self.assertRaises(consult.ConsultError):
                    consult.codex_config_overrides([bad])

    def test_missing_gemini_points_to_agy(self) -> None:
        with mock.patch.object(consult, "executable_for", return_value=None):
            with self.assertRaisesRegex(consult.ConsultError, "--provider agy"):
                consult.command_for("gemini", "task", None)


class PromptTests(unittest.TestCase):
    def args_for(self, **overrides: object) -> Namespace:
        values: dict[str, object] = {
            "prompt": "analyze",
            "prompt_file": None,
            "context": [],
            "max_context_bytes": 1024,
        }
        values.update(overrides)
        return Namespace(**values)

    def test_context_is_delimited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context_path = Path(temp_dir, "context.txt")
            context_path.write_text("evidence", encoding="utf-8")
            prompt = consult.load_prompt(
                self.args_for(context=[str(context_path)])
            )
        self.assertIn("<TASK>\nanalyze\n</TASK>", prompt)
        self.assertIn("<CONTEXT", prompt)
        self.assertIn("evidence", prompt)

    def test_context_does_not_disclose_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context_path = Path(temp_dir, "context.txt")
            context_path.write_text("evidence", encoding="utf-8")
            prompt = consult.load_prompt(
                self.args_for(context=[str(context_path)])
            )
        self.assertIn('name="context.txt"', prompt)
        self.assertNotIn(temp_dir, prompt)

    def test_context_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context_path = Path(temp_dir, "large.txt")
            context_path.write_text("abcdef", encoding="utf-8")
            args = self.args_for(context=[str(context_path)], max_context_bytes=5)
            with self.assertRaises(consult.ConsultError):
                consult.load_prompt(args)


class ProfileTests(unittest.TestCase):
    def test_profile_round_trip_and_model_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir, "config.json")
            config = consult.empty_config()
            config["profiles"]["review"] = {
                "providers": ["claude", "agy"],
                "models": {"agy": "Gemini 3.8 Flash (High)"},
            }
            consult.write_config(config_path, config)
            providers, models = consult.profile_settings(
                "review", str(config_path), ["claude=sonnet"]
            )
        self.assertEqual(providers, ["claude", "agy"])
        self.assertEqual(models["claude"], "sonnet")
        self.assertEqual(models["agy"], "Gemini 3.8 Flash (High)")

    def test_config_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir, "config.json")
            consult.write_config(config_path, consult.empty_config())
            mode = config_path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_provider_selection_accepts_names_and_numbers(self) -> None:
        self.assertEqual(
            consult.parse_provider_selection("claude,4"), ["claude", "agy"]
        )

    def test_new_providers_do_not_renumber_existing_ones(self) -> None:
        self.assertEqual(consult.PROVIDERS[:6], (
            "claude", "grok", "gemini", "agy", "opencode", "deepseek"
        ))


class ExecutionTests(unittest.TestCase):
    def test_grok_json_is_normalized(self) -> None:
        output, metadata, error = consult.normalize_cli_output(
            "grok",
            json.dumps(
                {
                    "text": "answer",
                    "sessionId": "session-1",
                    "stopReason": "end_turn",
                    "thought": "do not expose this as the answer",
                }
            ),
        )
        self.assertEqual(output, "answer")
        self.assertEqual(metadata["session_id"], "session-1")
        self.assertNotIn("thought", output)
        self.assertEqual(error, "")

    def test_agy_json_is_normalized(self) -> None:
        output, metadata, _ = consult.normalize_cli_output(
            "agy", json.dumps({"response": "answer", "usage": {"total_tokens": 3}})
        )
        self.assertEqual(output, "answer")
        self.assertEqual(metadata["usage"]["total_tokens"], 3)

    def test_cli_runs_in_isolated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_cli = Path(temp_dir, "grok")
            fake_cli.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "print(json.dumps({'cwd': os.getcwd(), 'args': sys.argv[1:]}))\n",
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            with mock.patch.object(consult, "executable_for", return_value=str(fake_cli)):
                result = consult.run_cli("grok", "task", None, 10, dict(os.environ))
        self.assertTrue(result["ok"])
        payload = json.loads(result["output"])
        self.assertIn("codex-consult-grok-", payload["cwd"])
        self.assertIn("task", payload["args"])

    def fake_cli(self, directory: str, name: str, body: str) -> str:
        path = Path(directory, name)
        path.write_text("#!/usr/bin/env python3\nimport json, os, sys\n" + body, encoding="utf-8")
        path.chmod(0o755)
        return str(path)

    def test_agy_denied_actions_are_not_success(self) -> None:
        payload = {
            "conversation_id": "c1",
            "status": "SUCCESS",
            "response": "",
            "denied_actions": [{"action": "write_file", "display_name": "WriteToFile"}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = self.fake_cli(temp_dir, "agy", f"print(json.dumps({payload!r}))\n")
            with mock.patch.object(consult, "executable_for", return_value=cli):
                result = consult.run_cli("agy", "task", None, 10, dict(os.environ))
        self.assertFalse(result["ok"])
        self.assertIn("write_file", result["error"])
        self.assertIn("work", result["error"])
        self.assertEqual(result["output"], "")
        self.assertEqual(result["session_id"], "c1")

    def test_agy_error_status_is_failure(self) -> None:
        payload = {"status": "ERROR", "response": "", "error": "invalid model selection"}
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = self.fake_cli(temp_dir, "agy", f"print(json.dumps({payload!r}))\n")
            with mock.patch.object(consult, "executable_for", return_value=cli):
                result = consult.run_cli("agy", "task", None, 10, dict(os.environ))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid model selection")

    def test_codex_reads_last_message_file(self) -> None:
        body = (
            "out = sys.argv[sys.argv.index('-o') + 1]\n"
            "open(out, 'w').write('final answer')\n"
            "print('transcript noise')\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = self.fake_cli(temp_dir, "codex", body)
            with mock.patch.object(consult, "executable_for", return_value=cli):
                result = consult.run_cli("codex", "task", None, 10, dict(os.environ))
        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], "final answer")

    def test_deepseek_requires_key_without_leaking_value(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = consult.run_deepseek("task", None, 10, None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "DEEPSEEK_API_KEY is not set")



class WorkTests(unittest.TestCase):
    def git(self, repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
            check=True,
            capture_output=True,
        )

    def make_repo(self, root: str) -> Path:
        repo = Path(root, "repo")
        repo.mkdir()
        self.git(repo, "init", "-q")
        Path(repo, "calc.py").write_text("x = 1\n", encoding="utf-8")
        self.git(repo, "add", "calc.py")
        self.git(repo, "commit", "-qm", "init")
        Path(repo, "notes.txt").write_text("already dirty\n", encoding="utf-8")
        return repo

    def test_work_requires_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(consult.ConsultError, "git repository"):
                consult.resolve_workdir(temp_dir)

    def test_work_reports_only_new_changes_and_tolerates_late_denial(self) -> None:
        payload = {
            "status": "SUCCESS",
            "response": "",
            "denied_actions": [{"action": "command"}],
        }
        body = (
            "assert '--mode' in sys.argv and 'accept-edits' in sys.argv\n"
            "open('calc.py', 'w').write('x = 2\\n')\n"
            f"print(json.dumps({payload!r}))\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self.make_repo(temp_dir)
            cli = Path(temp_dir, "agy")
            cli.write_text("#!/usr/bin/env python3\nimport json, sys\n" + body, encoding="utf-8")
            cli.chmod(0o755)
            options = consult.CallOptions(workdir=str(repo), timeout=10)
            with mock.patch.object(consult, "executable_for", return_value=str(cli)):
                result = consult.run_work("agy", "task", options, "none")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["changed_files"], ["calc.py"])
        self.assertIn("command", result["warning"])
        self.assertEqual(result["access"], "edit")


if __name__ == "__main__":
    unittest.main()
