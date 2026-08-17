import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
MAKEFILE = REPO / "Makefile"


class GitHubActionsContractTest(unittest.TestCase):
    def test_ci_workflow_contract(self):
        self.assertTrue(WORKFLOW.is_file())
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("actions/checkout@v7", text)
        self.assertIn("actions/setup-python@v7", text)
        self.assertIn("ubuntu-latest", text)
        self.assertIn("macos-latest", text)
        self.assertIn('"3.11"', text)
        self.assertIn('"3.14"', text)
        self.assertIn("python -m unittest discover -s tests -v", text)
        self.assertIn("python -m compileall -q src tests", text)
        self.assertIn("python -m json.tool agents/glm-5.3-models.json", text)
        self.assertIn('PYTHONDONTWRITEBYTECODE: "1"', text)
        self.assertIn("PYTHONPATH: src", text)
        self.assertNotIn("ZAI_API_KEY", text)
        self.assertNotIn("experimental_bearer_token", text)
        self.assertNotIn("docker", text.lower())

    def test_makefile_uses_full_local_validation(self):
        text = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("-m unittest discover -s tests -v", text)
        self.assertIn("-m compileall -q src tests", text)
        self.assertNotIn("-p 'test_installer.py'", text)


if __name__ == "__main__":
    unittest.main()
