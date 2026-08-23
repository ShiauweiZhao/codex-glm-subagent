import json
import os
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(str(REPO), "src"))

from codex_glm53_subagent import startup_catalog  # noqa: E402


def model(slug, **overrides):
    payload = {
        "slug": slug,
        "display_name": slug,
        "visibility": "list",
        "priority": 0,
    }
    payload.update(overrides)
    return payload


class StartupCatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="glm53-startup-catalog-test-"))
        self.codex = self.tmp / "codex"
        self.codex.mkdir()
        self.runtime = self.codex / "zai-glm53-subagent"
        self.runtime.mkdir()
        self.original_config = (
            'model = "gpt-5.6-sol"\n'
            'model_reasoning_effort = "high"\n'
            "\n"
            "[features]\n"
            "multi_agent = true\n"
        ).encode()
        (self.codex / "config.toml").write_bytes(self.original_config)
        self.auth = b'{"sentinel":"do-not-touch"}\n'
        (self.codex / "auth.json").write_bytes(self.auth)
        self._write_cache(
            [
                model("gpt-5.6-sol", auto_review_model_override=None),
                model("codex-auto-review", visibility="hide"),
            ]
        )
        (self.runtime / "glm-5.3-models.json").write_text(
            json.dumps(
                {
                    "models": [
                        model(
                            "glm-5.3",
                            auto_review_model_override="glm-5.3",
                            context_window=1048576,
                        )
                    ]
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_cache(self, models):
        (self.codex / "models_cache.json").write_text(
            json.dumps(
                {
                    "fetched_at": "2026-08-23T00:00:00Z",
                    "client_version": "0.148.0-alpha.21",
                    "models": models,
                }
            ),
            encoding="utf-8",
        )

    def test_activate_builds_hidden_glm_catalog_and_restores_config_exactly(self):
        report = startup_catalog.activate(self.codex)

        startup_path = self.runtime / "startup-models.json"
        backup_path = self.runtime / "config-before-startup-catalog.toml"
        config = tomllib.loads((self.codex / "config.toml").read_text())
        catalog = json.loads(startup_path.read_text())
        by_slug = {entry["slug"]: entry for entry in catalog["models"]}

        self.assertEqual(report["status"], "activated")
        self.assertEqual(config["model"], "gpt-5.6-sol")
        self.assertEqual(config["model_reasoning_effort"], "high")
        self.assertTrue(config["features"]["multi_agent"])
        self.assertEqual(config["model_catalog_json"], str(startup_path))
        self.assertEqual(
            [entry["slug"] for entry in catalog["models"]],
            ["gpt-5.6-sol", "codex-auto-review", "glm-5.3"],
        )
        self.assertEqual(by_slug["glm-5.3"]["visibility"], "hide")
        self.assertEqual(
            by_slug["glm-5.3"]["auto_review_model_override"], "glm-5.3"
        )
        self.assertEqual(backup_path.read_bytes(), self.original_config)
        self.assertEqual((self.codex / "auth.json").read_bytes(), self.auth)

        deactivated = startup_catalog.deactivate(self.codex)
        self.assertEqual(deactivated["status"], "deactivated")
        self.assertEqual((self.codex / "config.toml").read_bytes(), self.original_config)
        self.assertEqual((self.codex / "auth.json").read_bytes(), self.auth)

    def test_activate_is_idempotent_and_refreshes_the_combined_catalog(self):
        first = startup_catalog.activate(self.codex)
        first_config = (self.codex / "config.toml").read_bytes()

        self._write_cache(
            [
                model("gpt-5.6-sol"),
                model("gpt-5.6-terra"),
                model("codex-auto-review", visibility="hide"),
            ]
        )
        second = startup_catalog.activate(self.codex)
        slugs = [
            entry["slug"]
            for entry in json.loads(
                (self.runtime / "startup-models.json").read_text()
            )["models"]
        ]

        self.assertEqual(first["status"], "activated")
        self.assertEqual(second["status"], "already_activated")
        self.assertEqual((self.codex / "config.toml").read_bytes(), first_config)
        self.assertEqual(
            slugs,
            ["gpt-5.6-sol", "gpt-5.6-terra", "codex-auto-review", "glm-5.3"],
        )
        self.assertEqual(
            (self.runtime / "config-before-startup-catalog.toml").read_bytes(),
            self.original_config,
        )

    def test_activate_refuses_an_unmanaged_global_catalog_before_writing(self):
        config_path = self.codex / "config.toml"
        config_path.write_text(
            'model_catalog_json = "/tmp/user-models.json"\nmodel = "gpt-5.6-sol"\n',
            encoding="utf-8",
        )
        before = config_path.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "unmanaged model_catalog_json"):
            startup_catalog.activate(self.codex)

        self.assertEqual(config_path.read_bytes(), before)
        self.assertFalse((self.runtime / "startup-models.json").exists())
        self.assertFalse(
            (self.runtime / "config-before-startup-catalog.toml").exists()
        )

    def test_activate_fails_closed_without_parent_guardian_metadata(self):
        self._write_cache([model("gpt-5.6-sol")])

        with self.assertRaisesRegex(RuntimeError, "codex-auto-review"):
            startup_catalog.activate(self.codex)

        self.assertEqual(
            (self.codex / "config.toml").read_bytes(), self.original_config
        )
        self.assertFalse((self.runtime / "startup-models.json").exists())

    def test_deactivate_preserves_unrelated_changes_made_after_activation(self):
        startup_catalog.activate(self.codex)
        config_path = self.codex / "config.toml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8") + "\n[tui]\nanimations = false\n",
            encoding="utf-8",
        )

        startup_catalog.deactivate(self.codex)
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(parsed["model"], "gpt-5.6-sol")
        self.assertFalse(parsed["tui"]["animations"])
        self.assertNotIn("model_catalog_json", parsed)

    def test_status_reports_restart_requirement_without_exposing_config(self):
        inactive = startup_catalog.status(self.codex)
        startup_catalog.activate(self.codex)
        active = startup_catalog.status(self.codex)

        self.assertEqual(inactive, {"status": "inactive", "restart_required": False})
        self.assertEqual(active["status"], "active")
        self.assertTrue(active["restart_required"])
        self.assertEqual(active["model"], "glm-5.3")
        self.assertNotIn("config", active)


if __name__ == "__main__":
    unittest.main()
