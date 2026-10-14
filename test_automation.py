
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CAPABILITY_FILE = PROJECT_ROOT / "capabilities" / "customer_lookup_v1.json"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"


class AutomationArtifactTests(unittest.TestCase):

    def test_capability_file_exists(self):
        self.assertTrue(CAPABILITY_FILE.is_file())

    def test_capability_is_valid_json(self):
        with CAPABILITY_FILE.open(encoding="utf-8") as file:
            capability = json.load(file)
        self.assertIsInstance(capability, dict)

    def test_capability_has_version(self):
        with CAPABILITY_FILE.open(encoding="utf-8") as file:
            capability = json.load(file)
        self.assertEqual(capability.get("version"), 1)

    def test_capability_is_parameterized(self):
        content = CAPABILITY_FILE.read_text(encoding="utf-8")
        self.assertIn("{{customer_id}}", content)

    def test_capability_contains_replay_steps(self):
        with CAPABILITY_FILE.open(encoding="utf-8") as file:
            capability = json.load(file)
        self.assertIn("steps", capability)
        self.assertGreaterEqual(len(capability["steps"]), 3)

    def test_evidence_directory_exists(self):
        self.assertTrue(EVIDENCE_DIR.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
