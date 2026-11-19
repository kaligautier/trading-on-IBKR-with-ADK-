"""Refuse a Terraform plan that does anything but update the image of Cloud Run workloads.

Usage: check_image_only_plan.py PLAN_JSON IMAGE_REPOSITORY

PLAN_JSON is `terraform show -json` output. The image of every changed container must be
IMAGE_REPOSITORY pinned by a sha256 digest. Prints resource addresses and actions only:
plan values never reach the (public) log. Exit 0 when the plan is acceptable, 1 otherwise.
"""

import json
import os
import re
import sys

WORKLOADS = {"google_cloud_run_v2_service", "google_cloud_run_v2_job"}
# Provider bookkeeping that disappears once Terraform owns the resource.
NOISE = {"client", "client_version"}
IMAGE_PATH = re.compile(r"^template\.0(\.template\.0)?\.containers\.\d+\.image$")
DIGEST = re.compile(r"^@sha256:[0-9a-f]{64}$")


def changed_paths(before, after, unknown, path=""):
    """Yield dotted paths whose value differs, ignoring values unknown until apply."""
    if unknown is True:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        unknown = unknown if isinstance(unknown, dict) else {}
        for key in sorted(set(before) | set(after)):
            yield from changed_paths(
                before.get(key),
                after.get(key),
                unknown.get(key),
                f"{path}.{key}" if path else key,
            )
    elif isinstance(before, list) and isinstance(after, list):
        unknown = unknown if isinstance(unknown, list) else []
        if len(before) != len(after):
            yield path
            return
        for index, (old, new) in enumerate(zip(before, after)):
            known = unknown[index] if index < len(unknown) else None
            yield from changed_paths(old, new, known, f"{path}.{index}")
    elif before != after:
        yield path


def value_at(document, path):
    for part in path.split("."):
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def check(plan, repository):
    """Return (problems, changes). Problems never contain plan values."""
    problems, changes = [], []
    for resource in plan.get("resource_changes", []):
        change = resource["change"]
        actions = change["actions"]
        if actions in (["no-op"], ["read"]):
            continue
        address = resource["address"]
        if actions != ["update"] or resource["type"] not in WORKLOADS:
            problems.append(
                f"{address}: {','.join(actions)} is not an in-place Cloud Run update"
            )
            continue
        images = 0
        for path in changed_paths(
            change["before"], change["after"], change.get("after_unknown")
        ):
            if path in NOISE:
                continue
            if not IMAGE_PATH.match(path):
                problems.append(f"{address}: `{path}` changes besides the image")
                continue
            images += 1
            image = value_at(change["after"], path)
            if not (
                isinstance(image, str)
                and image.startswith(repository)
                and DIGEST.match(image[len(repository) :])
            ):
                problems.append(
                    f"{address}: `{path}` is not {repository} pinned by a sha256 digest"
                )
        if images:
            changes.append(f"{address}: {images} image(s)")
        elif not any(p.startswith(address) for p in problems):
            problems.append(f"{address}: updated without an image change")
    return problems, changes


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    try:
        with open(argv[1]) as handle:
            plan = json.load(handle)
    except (OSError, ValueError):
        print("REFUSED: the plan is missing or is not valid JSON")
        return 1
    problems, changes = check(plan, argv[2])
    for line in changes:
        print(f"image update: {line}")
    for line in problems:
        print(f"REFUSED: {line}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output and not problems:
        with open(output, "a") as handle:
            handle.write(f"changed={len(changes)}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
