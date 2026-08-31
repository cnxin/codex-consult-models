#!/usr/bin/env python3
"""Focused tests for consult.py."""

from __future__ import annotations

import importlib.util
import json
import os
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
                "agy", "task", "Gemini 3.7 Flash (High)"
            )
        self.assertIn("--sandbox", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertEqual(command[-2:], ["--model", "Gemini 3.7 Flash (High)"])


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
                "models": {"agy": "Gemini 3.7 Flash (High)"},
            }
            consult.write_config(config_path, config)
            providers, models = consult.profile_settings(
                "review", str(config_path), ["claude=sonnet"]
            )
        self.assertEqual(providers, ["claude", "agy"])
        self.assertEqual(models["claude"], "sonnet")
        self.assertEqual(models["agy"], "Gemini 3.7 Flash (High)")

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


class ExecutionTests(unittest.TestCase):
    def test_grok_json_is_normalized(self) -> None:
        output, metadata = consult.normalize_cli_output(
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

    def test_agy_json_is_normalized(self) -> None:
        output, metadata = consult.normalize_cli_output(
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

    def test_deepseek_requires_key_without_leaking_value(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = consult.run_deepseek("task", None, 10, None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "DEEPSEEK_API_KEY is not set")


if __name__ == "__main__":
    unittest.main()
