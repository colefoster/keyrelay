import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from hooks import redact_secrets as hook
from secret_corpus import CASES, invented


ROOT = Path(__file__).resolve().parents[1]


class DetectionTest(unittest.TestCase):
    def test_corpus(self):
        for label, text, rule, value in CASES:
            with self.subTest(case=label):
                matches = hook.findings(text)
                self.assertEqual({kind for _, _, kind in matches}, {rule} if rule else set())
                safe, changed = hook.redact_text(text)
                self.assertEqual(changed, bool(rule))
                if rule:
                    self.assertNotIn(value, safe)
                    self.assertIn("KEYRELAY:", safe)
                    self.assertEqual(hook.redact_text(safe), (safe, False))
                else:
                    self.assertEqual(safe, text)

    def test_multiple_values_and_surrounding_text(self):
        secret = "ghp_" + invented(36)
        other = "sk-proj-" + invented(100)
        safe, changed = hook.redact_text("start " + secret + " mid " + other + " end " + secret)
        self.assertTrue(changed)
        self.assertNotIn(secret, safe)
        self.assertNotIn(other, safe)
        self.assertTrue(safe.startswith("start ") and " mid " in safe and " end " in safe)
        self.assertEqual(safe.count("KEYRELAY:"), 3)

    def test_generated_hash_and_uuid_negatives(self):
        for seed in range(100):
            for size in (32, 40, 64, 128):
                self.assertFalse(hook.findings("TOKEN=" + invented(size, "0123456789abcdef", seed)))

    def test_structured_negative_properties(self):
        for value in (invented(40, "0123456789abcdef"),
                      "550e8400-e29b-41d4-a716-446655440000",
                      "The token parser should handle escaped strings correctly.",
                      "${SERVICE_API_KEY}", "x" * 48):
            response = {"token": value}
            self.assertEqual(hook.redact_json(response), (response, False))

    def test_many_values_are_all_removed(self):
        secret = "ghp_" + invented(36)
        safe, changed = hook.redact_text((secret + "\n") * 1000)
        self.assertTrue(changed)
        self.assertNotIn(secret, safe)
        self.assertEqual(safe.count("KEYRELAY:"), 1000)


class ContractTest(unittest.TestCase):
    def invoke(self, event, payload=None, raw=None):
        if raw is None:
            raw = json.dumps(payload).encode()
        child = subprocess.run(
            [sys.executable, str(ROOT / "hooks/redact_secrets.py"), "--event", event],
            input=raw, capture_output=True, timeout=5,
        )
        self.assertEqual(child.returncode, 0)
        self.assertEqual(child.stderr, b"")
        return json.loads(child.stdout) if child.stdout else {}, child.stdout

    def test_every_positive_is_blocked_without_prompt_echo(self):
        for label, text, rule, value in CASES:
            if not rule:
                continue
            with self.subTest(case=label):
                output, raw = self.invoke("UserPromptSubmit", {
                    "hook_event_name": "UserPromptSubmit", "prompt": text,
                    "transcript_path": "/must/not/read", "session_id": "untrusted",
                })
                self.assertEqual(output["decision"], "block")
                self.assertTrue(output["hookSpecificOutput"]["suppressOriginalPrompt"])
                self.assertNotIn(value.encode(), raw)
                self.assertIn("Keyrelay", output["reason"])

    def test_clean_prompt_is_silent(self):
        output, raw = self.invoke("UserPromptSubmit", {
            "hook_event_name": "UserPromptSubmit", "prompt": "Fix the UUID parser",
        })
        self.assertEqual((output, raw), ({}, b""))

    def test_bash_replacement_preserves_shape_and_flags(self):
        secret = "ghp_" + invented(36)
        response = {"stdout": "before " + secret + " after", "stderr": secret,
                    "interrupted": False, "isImage": False, "exitCode": 3}
        output, raw = self.invoke("PostToolUse", {
            "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_response": response,
        })
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PostToolUse")
        self.assertNotIn("decision", output)
        safe = specific["updatedToolOutput"]
        self.assertEqual(safe.keys(), response.keys())
        self.assertEqual(safe["exitCode"], 3)
        self.assertIs(safe["interrupted"], False)
        self.assertIn("before ", safe["stdout"])
        self.assertIn(" after", safe["stdout"])
        self.assertNotIn(secret.encode(), raw)

    def test_nested_mcp_response_and_sensitive_property(self):
        value = invented(40)
        response = {"content": [{"type": "text", "text": "API_KEY=" + value}],
                    "structuredContent": {"api_key": value}, "isError": True}
        output, raw = self.invoke("PostToolUse", {
            "hook_event_name": "PostToolUse", "tool_name": "mcp__demo__lookup",
            "tool_response": response,
        })
        safe = output["hookSpecificOutput"]["updatedToolOutput"]
        self.assertEqual(safe["content"][0]["type"], "text")
        self.assertIs(safe["isError"], True)
        self.assertNotIn(value.encode(), raw)

    def test_all_positive_outputs_are_replaced(self):
        for label, text, rule, value in CASES:
            if not rule:
                continue
            with self.subTest(case=label):
                output = hook.process({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                       "tool_response": {"stdout": text}}, "PostToolUse")
                self.assertNotIn(value, json.dumps(output))
                self.assertIn("updatedToolOutput", output["hookSpecificOutput"])

    def test_clean_result_is_silent_and_ignores_metadata(self):
        secret = "ghp_" + invented(36)
        output, raw = self.invoke("PostToolUse", {
            "hook_event_name": "PostToolUse", "tool_name": secret,
            "tool_input": {"command": secret}, "tool_response": {"stdout": "safe"},
        })
        self.assertEqual((output, raw), ({}, b""))

    def test_arbitrary_mcp_keys_are_redacted(self):
        secret = "ghp_" + invented(36)
        safe, changed = hook.redact_json({secret: "safe"})
        self.assertTrue(changed)
        self.assertNotIn(secret, json.dumps(safe))

    def test_redacted_key_collision_stops_without_echo(self):
        secret = "ghp_" + invented(36)
        second = "ghp_" + invented(36, seed=55)
        output, raw = self.invoke("PostToolUse", {
            "hook_event_name": "PostToolUse", "tool_name": "mcp__demo__lookup",
            "tool_response": {secret: 1, second: 2},
        })
        self.assertIs(output["continue"], False)
        self.assertNotIn(secret.encode(), raw)
        self.assertNotIn(second.encode(), raw)

    def test_invalid_inputs_stop_without_echo(self):
        secret = "ghp_" + invented(36)
        invalid = [b"", ("broken " + secret).encode(), b"\xff", b"[]", b"null",
                   b'{"prompt":"first","prompt":"second"}', b'{"n":NaN}',
                   b'{"n":Infinity}', b'{"n":1e999}',
                   b'{"hook_event_name":"PostToolUse","tool_name":"Bash","tool_response":{"n":1e999}}',
                   b"[" * 2000 + b"]" * 2000,
                   b" " * (hook.MAX_INPUT_BYTES + 1)]
        for event in hook.EVENTS:
            for index, raw in enumerate(invalid):
                with self.subTest(event=event, case=index):
                    output, emitted = self.invoke(event, raw=raw)
                    self.assertEqual(output["decision"], "block")
                    self.assertNotIn(secret.encode(), emitted)
                    if event == "UserPromptSubmit":
                        self.assertTrue(output["hookSpecificOutput"]["suppressOriginalPrompt"])
                    else:
                        self.assertIs(output["continue"], False)

    def test_missing_fields_mismatched_event_and_deep_structure(self):
        bad = [{}, {"hook_event_name": "PostToolUse"},
               {"hook_event_name": "UserPromptSubmit", "prompt": 42}]
        for payload in bad:
            output, _ = self.invoke("UserPromptSubmit", payload)
            self.assertEqual(output["decision"], "block")
        nested = "safe"
        for _ in range(hook.MAX_DEPTH + 2):
            nested = [nested]
        output, _ = self.invoke("PostToolUse", {
            "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_response": nested,
        })
        self.assertIs(output["continue"], False)

    def test_no_file_or_network_access_in_processing(self):
        with patch("builtins.open", side_effect=AssertionError("file access")), \
                patch("socket.socket", side_effect=AssertionError("network access")):
            result = hook.process({"hook_event_name": "UserPromptSubmit", "prompt": "hello"},
                                  "UserPromptSubmit")
            self.assertEqual(result, {})

    def test_example_is_inert_synchronous_command_configuration(self):
        settings = json.loads((ROOT / "hooks/claude-settings.example.json").read_text())
        self.assertEqual(set(settings["hooks"]), set(hook.EVENTS))
        for event in hook.EVENTS:
            entry = settings["hooks"][event][0]
            command = entry["hooks"][0]
            self.assertEqual(command["type"], "command")
            self.assertEqual(command["onFailure"], "block")
            self.assertNotIn("async", command)
            self.assertIn("--event " + event, command["command"])


if __name__ == "__main__":
    unittest.main()
