"""Exercise the real Terraform provider against a local mock or pinned proxy."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


class TerraformPolicy:
    def __init__(self, directory, base_url, master, models):
        self.path = Path(directory) / "terraform"
        self.path.mkdir()
        source = json.dumps(str(ROOT / "governance/policy"))
        (self.path / "main.tf").write_text(
            """terraform {
  required_providers { litellm = { source = "BerriAI/litellm", version = "= 1.106.0" } }
}
variable "master" {\n type = string\n sensitive = true\n ephemeral = true\n}
variable "keys" {\n type = map(string)\n sensitive = true\n ephemeral = true\n}
variable "agents" { type = any }
variable "base_url" { type = string }
variable "import_team" { default = false }
provider "litellm" {
  api_base = var.base_url
  api_key = var.master
}
module "policy" {
  source = """
            + source
            + """
  models = """
            + json.dumps(models)
            + """
  agents = var.agents
  client_keys = var.keys
}
import {
  for_each = var.import_team ? toset(["agents"]) : toset([])
  to = module.policy.litellm_team.agents
  id = each.value
}
import {
  for_each = { for name, agent in var.agents : name => agent.existing_token_id if try(agent.existing_token_id, null) != null }
  to = module.policy.litellm_key.agent[each.key]
  id = each.value
}
"""
        )
        moved = ROOT / "governance/moved.tf"
        if moved.exists():
            (self.path / "moved.tf").write_text(moved.read_text())
        self.env = {
            **os.environ,
            "TF_VAR_master": master,
            "TF_VAR_base_url": base_url,
            "TF_IN_AUTOMATION": "1",
        }
        self.run("init", "-backend=false", "-input=false")

    def run(self, *args):
        result = subprocess.run(
            ["terraform", f"-chdir={self.path}", *args, "-no-color"],
            env=self.env,
            capture_output=True,
            text=True,
        )
        assert result.returncode in (0, 2), result.stdout + result.stderr
        return result

    def apply(self, agents, keys, import_team=False):
        self.env.update(
            TF_VAR_agents=json.dumps(agents),
            TF_VAR_keys=json.dumps(keys),
            TF_VAR_import_team=json.dumps(import_team),
        )
        self.run("apply", "-auto-approve", "-input=false")
        state = (self.path / "terraform.tfstate").read_text()
        assert all(
            secret not in state
            for secret in [self.env["TF_VAR_master"], *keys.values()]
        )
        assert (
            self.run(
                "plan", "-detailed-exitcode", "-input=false", "-out=checked.tfplan"
            ).returncode
            == 0
        ), "Rerun is not a no-op"
        plan = self.run("show", "-json", "checked.tfplan").stdout
        assert all(
            secret not in plan for secret in [self.env["TF_VAR_master"], *keys.values()]
        )


def main():
    import httpx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    keys = {"scanner": "sk-offline-scanner", "weekly": "sk-offline-weekly"}
    agents = {"scanner": {}, "weekly": {"max_budget": 4, "budget_duration": "7d"}}
    with httpx.Client(
        base_url=args.base_url, headers={"Authorization": "Bearer offline-only-master"}
    ) as client:
        client.post("__reset").raise_for_status()
        with tempfile.TemporaryDirectory() as directory:
            policy = TerraformPolicy(
                directory, args.base_url, "offline-only-master", ["offline-model"]
            )
            policy.env["TF_CLI_ARGS_apply"] = (
                "-parallelism=1"  # The mock stores a shared snapshot.
            )
            policy.apply(agents, keys)
            state = client.get("__state").raise_for_status().json()
            assert (
                state["keys"][hashlib.sha256(keys["scanner"].encode()).hexdigest()][
                    "max_budget"
                ]
                == 3
            )
            assert (
                state["keys"][hashlib.sha256(keys["weekly"].encode()).hexdigest()][
                    "budget_duration"
                ]
                == "7d"
            )
            policy.run(
                "state",
                "mv",
                "module.policy.litellm_team.agents",
                "litellm_team.agents",
            )
            policy.run(
                "state",
                "mv",
                'module.policy.litellm_key.agent["scanner"]',
                'litellm_key.agent["scanner"]',
            )
            policy.run(
                "state",
                "mv",
                'module.policy.litellm_key.agent["weekly"]',
                'litellm_key.agent["weekly"]',
            )
            policy.run("plan", "-input=false", "-out=moved.tfplan")
            moved_plan = json.loads(policy.run("show", "-json", "moved.tfplan").stdout)
            assert all(
                r["change"]["actions"] == ["no-op"]
                for r in moved_plan["resource_changes"]
            )
            policy.apply(agents, keys)
            rotated = "sk-offline-rotated"
            policy.env["TF_VAR_keys"] = json.dumps({**keys, "scanner": rotated})
            policy.env["TF_VAR_agents"] = json.dumps(
                {
                    **agents,
                    "scanner": {
                        "existing_token_id": hashlib.sha256(
                            rotated.encode()
                        ).hexdigest()
                    },
                }
            )
            mismatch = subprocess.run(
                [
                    "terraform",
                    f"-chdir={policy.path}",
                    "plan",
                    "-no-color",
                    "-input=false",
                ],
                env=policy.env,
                capture_output=True,
                text=True,
            )
            assert (
                mismatch.returncode == 1
                and "Terraform key ID differs" in mismatch.stderr
            )
            policy.env["TF_VAR_keys"] = json.dumps(keys)
            policy.env["TF_VAR_agents"] = json.dumps(agents)
            client.post("__fail").raise_for_status()
            failure = subprocess.run(
                [
                    "terraform",
                    f"-chdir={policy.path}",
                    "plan",
                    "-no-color",
                    "-input=false",
                ],
                env=policy.env,
                capture_output=True,
                text=True,
            )
            assert failure.returncode == 1, "Failed refresh was ignored"
    print(
        "PASS: actual Terraform/provider create, daily/weekly budgets, no-op, no raw secrets in state and failed-refresh rejection"
    )


if __name__ == "__main__":
    main()
