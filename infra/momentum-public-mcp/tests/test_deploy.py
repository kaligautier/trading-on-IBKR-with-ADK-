"""Exercise the deployment gate without cloud credentials or infrastructure writes."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "mcp_deploy", Path(__file__).resolve().parents[1] / "deploy.py"
)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)
IMAGE = (
    "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/"
    "momentum-public-mcp@sha256:" + "a" * 64
)


class DeploymentGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.variables = Path(self.directory.name) / "release.tfvars"
        self.original = '# Cloud Build previous.\nimage = "old-digest"\n'
        self.variables.write_text(self.original)
        self.evidence = Path(self.directory.name) / "evidence.json"

    def invoke(self, **kwargs):
        deploy.deploy(IMAGE, self.variables, self.evidence, **kwargs)

    def test_invalid_release_inputs_fail_before_any_cloud_command(self):
        with patch.object(deploy, "run") as run:
            with self.assertRaises(ValueError):
                deploy.deploy("mutable:latest", self.variables, self.evidence)
            self.variables.write_text('project_id = "example"\n')
            with self.assertRaises(ValueError):
                self.invoke()
        run.assert_not_called()

    def test_plan_only_does_not_apply_verify_or_change_the_release(self):
        with patch.object(deploy, "run") as run:
            self.invoke(plan_only=True)
        self.assertEqual(
            [call.args[0][1] for call in run.call_args_list], ["init", "plan"]
        )
        self.assertEqual(self.variables.read_text(), self.original)
        self.assertFalse(self.evidence.exists())

    def test_failed_verification_does_not_record_a_successful_release(self):
        failure = subprocess.CalledProcessError(1, ["verifier"])
        with patch.object(
            deploy,
            "run",
            side_effect=[None, None, None, "https://mcp.example", failure],
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                self.invoke()
        self.assertEqual(self.variables.read_text(), self.original)
        self.assertFalse(self.evidence.exists())

    def test_success_applies_then_verifies_read_only_before_recording_digest(self):
        def command(arguments, *, capture=False):
            if arguments[:2] == ["terraform", "output"]:
                return "https://mcp.example\n"
            if arguments[0] == deploy.sys.executable:
                self.assertEqual(self.variables.read_text(), self.original)
                self.assertEqual(
                    arguments,
                    [
                        deploy.sys.executable,
                        str(deploy.VERIFIER),
                        "https://mcp.example",
                    ],
                )
                return '{"tools": ["list_analyses"], "correlation_headers": true}'
            return ""

        with patch.object(deploy, "run", side_effect=command) as run:
            self.invoke()
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            [item[1] for item in commands[:4]], ["init", "plan", "apply", "output"]
        )
        self.assertIn(IMAGE, self.variables.read_text())
        self.assertNotIn("Cloud Build previous", self.variables.read_text())
        self.assertEqual(json.loads(self.evidence.read_text())["image"], IMAGE)


if __name__ == "__main__":
    unittest.main()
