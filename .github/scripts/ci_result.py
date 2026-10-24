"""Fail closed unless every selected workflow and every required child job passed."""

import json
import os

from ci_scope import COMPONENTS


def verify_component(name: str, selected: bool, result: dict) -> None:
    if not selected:
        if result["result"] != "skipped":
            raise ValueError(f"{name}: unexpected execution outside the selected scope")
        return
    if result["result"] != "success":
        raise ValueError(f"{name}: {result['result']}")
    jobs = json.loads(result["outputs"]["jobs"])
    if set(jobs) != set(COMPONENTS[name]["jobs"]):
        raise ValueError(f"{name}: missing or unexpected verification jobs")
    for job, details in jobs.items():
        if details["result"] != "success":
            raise ValueError(f"{name}/{job}: {details['result']}")


def verify(needs: dict) -> None:
    if set(needs) != {"scope", *COMPONENTS}:
        raise ValueError("Missing or unexpected component workflows")
    if needs["scope"]["result"] != "success":
        raise ValueError("CI scope selection or policy tests did not pass")
    selected = json.loads(needs["scope"]["outputs"]["selected"])
    if set(selected) != set(COMPONENTS):
        raise ValueError("Incomplete component selection")
    for name, enabled in selected.items():
        if type(enabled) is not bool:
            raise ValueError(f"{name}: invalid scope flag")
        verify_component(name, enabled, needs[name])


if __name__ == "__main__":
    verify(json.loads(os.environ["CI_NEEDS"]))
    print("All selected CI checks passed; unselected components were skipped.")
