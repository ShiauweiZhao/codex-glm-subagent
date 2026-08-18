import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "hooks" / "plaintext_handoff.py"


class PlaintextHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="glm53-handoff-test-")
        self.state = Path(self.temporary.name) / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def run_script(self, mode, stdin, *extra):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--mode",
                mode,
                "--state-directory",
                str(self.state),
                *extra,
            ],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )

    def stage(self, assignment="Objective: return the literal marker GLM53_SMOKE_OK"):
        result = self.run_script("stage", assignment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_stage_and_target_hook_deliver_assignment_exactly_once(self):
        assignment = "Objective: extract the repository basename\nStop after evidence."
        staged = self.stage(assignment)
        self.assertTrue(staged["staged"])
        self.assertEqual(staged["agent_type"], "zai_glm53_worker")
        pending = Path(staged["pending_path"])
        self.assertTrue(pending.is_file())
        self.assertEqual(stat.S_IMODE(os.stat(pending).st_mode), 0o600)

        hook_input = json.dumps(
            {
                "hook_event_name": "SubagentStart",
                "agent_type": "zai_glm53_worker",
                "agent_id": "child-1",
            }
        )
        delivered = self.run_script("hook", hook_input)
        self.assertEqual(delivered.returncode, 0, delivered.stderr)
        output = json.loads(delivered.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"], "SubagentStart"
        )
        self.assertIn("spawned zai_glm53_worker child", context)
        self.assertIn("BEGIN PARENT ASSIGNMENT", context)
        self.assertIn(assignment, context)
        self.assertIn("END PARENT ASSIGNMENT", context)
        self.assertFalse(pending.exists())

        replay = self.run_script("hook", hook_input)
        self.assertEqual(replay.returncode, 10)
        self.assertIn("No plaintext handoff", replay.stderr)

    def test_non_target_hook_does_not_consume_pending_assignment(self):
        staged = self.stage()
        pending = Path(staged["pending_path"])
        result = self.run_script(
            "hook",
            json.dumps(
                {
                    "hook_event_name": "SubagentStart",
                    "agent_type": "another_worker",
                    "agent_id": "other",
                }
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(pending.exists())

    def test_second_live_pending_assignment_is_rejected(self):
        self.stage("first assignment")
        second = self.run_script("stage", "second assignment")
        self.assertEqual(second.returncode, 3)
        self.assertIn("already pending", second.stderr)

    def test_empty_assignment_is_rejected(self):
        result = self.run_script("stage", "  \n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("empty", result.stderr.lower())

    def test_invalid_hook_input_fails_closed(self):
        result = self.run_script("hook", "not-json")
        self.assertEqual(result.returncode, 4)
        self.assertIn("invalid JSON", result.stderr)


if __name__ == "__main__":
    unittest.main()
