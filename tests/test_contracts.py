import json
import os
import tomllib
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as f:
        return f.read()


def parse_simple_yaml(text):
    result = {}
    path = [(0, result)]
    block_buf = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while path and indent < path[-1][0]:
            path.pop()
        if block_buf is not None:
            if indent <= block_buf[0]:
                block_buf[2][block_buf[1]] = "\n".join(block_buf[3]).strip()
                block_buf = None
            else:
                block_buf[3].append(line)
                continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        parent = path[-1][1]
        if value == "":
            child = {}
            parent[key] = child
            path.append((indent, child))
        elif value.startswith("|") or value.startswith(">"):
            block_buf = [indent, key, parent, []]
        else:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            parent[key] = value
    if block_buf is not None:
        block_buf[2][block_buf[1]] = "\n".join(block_buf[3]).strip()
    return result


class Glm53ContractsTest(unittest.TestCase):
    def test_toml_top_level_schema(self):
        data = tomllib.loads(read("agents", "zai-glm53-worker.toml"))
        self.assertEqual(data["name"], "zai_glm53_worker")
        self.assertIsInstance(data["description"], str)
        self.assertIsInstance(data["developer_instructions"], str)
        self.assertEqual(data["model_provider"], "zai_glm53")
        self.assertEqual(data["model"], "glm-5.3")
        self.assertEqual(data["model_context_window"], 1048576)
        self.assertNotIn("model_catalog_json", data)

    def test_toml_provider_schema(self):
        data = tomllib.loads(read("agents", "zai-glm53-worker.toml"))
        self.assertEqual(list(data["model_providers"].keys()), ["zai_glm53"])
        prov = data["model_providers"]["zai_glm53"]
        self.assertEqual(prov["name"], "Z.AI GLM-5.3 Responses")
        self.assertEqual(prov["base_url"], "https://open.bigmodel.cn/api/v1")
        self.assertEqual(prov["wire_api"], "responses")
        self.assertEqual(prov["request_max_retries"], 1)
        self.assertEqual(prov["stream_max_retries"], 1)
        self.assertEqual(prov["stream_idle_timeout_ms"], 300000)
        self.assertEqual(prov["placeholder"], "__CODEX_GLM53_AUTH_BODY__")

    def test_developer_instructions_boundaries(self):
        inst = tomllib.loads(read("agents", "zai-glm53-worker.toml"))[
            "developer_instructions"
        ].lower()
        for marker in (
            "worker",
            "gpt",
            "writable scope",
            "validation",
            "escalate_to_gpt",
            "no git",
            "no credentials",
            "no fallback",
            "external mutation",
            "approval",
            "permission",
        ):
            self.assertIn(marker, inst)

    def test_developer_instructions_require_plaintext_handoff(self):
        inst = tomllib.loads(read("agents", "zai-glm53-worker.toml"))[
            "developer_instructions"
        ]
        self.assertIn("trusted plaintext handoff", inst)
        self.assertIn("MISSING_PLAINTEXT_HANDOFF", inst)

    def test_catalog_json_schema(self):
        data = json.loads(read("agents", "glm-5.3-models.json"))
        self.assertEqual(list(data.keys()), ["models"])
        self.assertEqual(len(data["models"]), 1)
        m = data["models"][0]
        self.assertEqual(m["slug"], "glm-5.3")
        self.assertEqual(m["display_name"], "glm-5.3")
        self.assertEqual(m["description"], "Z.ai's latest flagship model")
        self.assertEqual(m["default_reasoning_level"], "max")
        self.assertEqual(
            m["supported_reasoning_levels"],
            [
                {"effort": "low", "description": "Light reasoning"},
                {"effort": "high", "description": "Enhanced reasoning"},
                {"effort": "max", "description": "Deep reasoning"},
            ],
        )
        self.assertEqual(m["shell_type"], "shell_command")
        self.assertEqual(m["visibility"], "list")
        self.assertTrue(m["supported_in_api"])
        self.assertEqual(m["priority"], 0)
        self.assertEqual(m["base_instructions"], "")
        self.assertTrue(m["supports_reasoning_summaries"])
        self.assertEqual(m["default_reasoning_summary"], "none")
        self.assertFalse(m["support_verbosity"])
        self.assertEqual(m["apply_patch_tool_type"], "freeform")
        self.assertEqual(m["auto_review_model_override"], "glm-5.3")
        self.assertEqual(m["truncation_policy"], {"mode": "bytes", "limit": 10000})
        self.assertEqual(m["context_window"], 1048576)
        self.assertEqual(m["max_context_window"], 1048576)
        self.assertEqual(m["effective_context_window_percent"], 95)
        self.assertTrue(m["supports_parallel_tool_calls"])
        self.assertEqual(m["experimental_supported_tools"], [])
        self.assertEqual(m["input_modalities"], ["text"])

    def test_skill_frontmatter(self):
        text = read("skills", "use-zai-glm53-worker", "SKILL.md")
        self.assertTrue(text.startswith("---\n"))
        parts = text.split("---\n", 2)
        self.assertGreaterEqual(len(parts), 3)
        frontmatter = parse_simple_yaml(parts[1])
        self.assertEqual(frontmatter.get("name"), "use-zai-glm53-worker")
        self.assertIsInstance(frontmatter.get("description"), str)
        self.assertIn("GLM-5.3", frontmatter["description"])
        self.assertIn("worker", frontmatter["description"].lower())
        body = parts[2]
        for marker in ("writable scope", "validation", "ESCALATE_TO_GPT", "stop condition"):
            self.assertIn(marker, body)
        for marker in (
            "SubagentStart",
            "plaintext_handoff.py --mode stage",
            'agent type `zai_glm53_worker`',
            '`fork_turns="none"`',
            "Never spawn after a failed stage",
        ):
            self.assertIn(marker, body)
        self.assertIn("No bridge", body)

    def test_skill_parent_routing_and_luna_reroute_contract(self):
        body = read("skills", "use-zai-glm53-worker", "SKILL.md")
        lowered = body.lower()
        normalized = " ".join(lowered.split())
        for marker in (
            "requirements",
            "planning",
            "design",
            "architecture",
            "task decomposition",
            "review",
            "final verification",
            "git",
        ):
            self.assertIn(marker, normalized)
        self.assertIn("standing authorization", normalized)
        self.assertIn("do not ask again", normalized)
        self.assertIn("private source", normalized)
        self.assertIn("quota", normalized)
        self.assertIn("token", normalized)
        self.assertIn("rate-limit", normalized)
        self.assertIn('agent_type="worker"', body)
        self.assertIn('model="gpt-5.6-luna"', body)
        self.assertIn('reasoning_effort="max"', body)
        self.assertIn('fork_turns="none"', body)
        self.assertIn("not a runtime provider fallback", normalized)
        self.assertIn("no paid recovery probe", normalized)
        for marker in (
            "hook trust",
            "authentication",
            "permission",
            "data-boundary",
            "model/account compatibility",
            "missing callback",
            "escalate_to_gpt",
        ):
            self.assertIn(marker, normalized)

    def test_skill_fails_closed_on_runtime_specific_provider_error(self):
        body = read("skills", "use-zai-glm53-worker", "SKILL.md")
        normalized = " ".join(body.lower().split())
        self.assertIn("runtime-specific provider failure", normalized)
        self.assertIn("do not block staging from a version string alone", normalized)
        self.assertIn("codex-glm53-runtime", body)
        self.assertIn("restart codex desktop", normalized)
        self.assertIn("must not spawn", normalized)
        self.assertIn("must not select luna", normalized)
        self.assertNotIn(
            "do not stage a fresh assignment until a released bundled codex runtime",
            normalized,
        )
        self.assertNotIn("codex-glm53-runtime install --activate", body)

    def test_skill_classifies_guardian_model_unavailability(self):
        body = read("skills", "use-zai-glm53-worker", "SKILL.md")
        normalized = " ".join(body.lower().split())
        self.assertIn("guardian_model_unavailable", normalized)
        self.assertIn("modelcode", normalized)
        self.assertIn("non-capacity", normalized)
        self.assertIn("must not select luna", normalized)

    def test_skill_requires_active_startup_catalog_before_write_assignments(self):
        body = read("skills", "use-zai-glm53-worker", "SKILL.md")
        normalized = " ".join(body.lower().split())
        self.assertIn("codex-glm53-startup-catalog status", body)
        self.assertIn("startup catalog", normalized)
        self.assertIn("write assignment", normalized)
        self.assertIn("restart codex desktop", normalized)
        self.assertIn("must not stage", normalized)

    def test_skill_recovers_sandbox_denied_staging_without_changing_transport(self):
        body = read("skills", "use-zai-glm53-worker", "SKILL.md")
        normalized = " ".join(body.lower().split())
        self.assertIn("operation not permitted", normalized)
        self.assertIn("exactly one sandbox approval", normalized)
        self.assertIn("retry the same staging command once", normalized)
        self.assertIn("must not spawn until that retry succeeds", normalized)
        self.assertIn("does not authorize a provider", normalized)
        self.assertIn("assignment itself is stdin", normalized)

    def test_agent_yaml_schema(self):
        raw = read("skills", "use-zai-glm53-worker", "agents", "openai.yaml")
        data = parse_simple_yaml(raw)
        self.assertEqual(list(data.keys()), ["interface"])
        interface = data["interface"]
        self.assertEqual(interface["display_name"], "Use Z.AI GLM-5.3 Worker")
        self.assertIsInstance(interface["short_description"], str)
        self.assertIsInstance(interface["default_prompt"], str)
        self.assertIn("$use-zai-glm53-worker", interface["default_prompt"])
        self.assertEqual(list(interface.keys()), ["display_name", "short_description", "default_prompt"])


if __name__ == "__main__":
    unittest.main()
