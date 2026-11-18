"""Replace installed distributions with hash-verified wheels, offline.

Only wheels whose distribution is already installed are applied, so the proxy
and migrations images share one wheel set. Afterwards every installed
requirement on a replaced distribution must still be satisfied.
"""

import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name, parse_wheel_filename


def installed():
    return {
        canonicalize_name(d.metadata["Name"]): d.version
        for d in importlib.metadata.distributions()
    }


def main():
    pip, *wheels = sys.argv[1:]
    before = installed()
    targets = {}
    for wheel in map(Path, wheels):
        name, version, _, _ = parse_wheel_filename(wheel.name)
        if name in before:
            targets[name] = (str(version), wheel)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps"]
        + ["--force-reinstall", *(str(w) for _, w in targets.values())],
        env={**os.environ, "PYTHONPATH": pip},
        check=True,
    )
    after = installed()
    for name, (version, _) in targets.items():
        assert after[name] == version, f"{name} {after[name]} != {version}"
    environment = default_environment()
    for dist in importlib.metadata.distributions():
        for line in dist.requires or []:
            requirement = Requirement(line)
            name = canonicalize_name(requirement.name)
            if name not in targets:
                continue
            if requirement.marker and not requirement.marker.evaluate(
                environment | {"extra": ""}
            ):
                continue
            assert requirement.specifier.contains(after[name], prereleases=True), (
                f"{dist.metadata['Name']} requires {line}; installed {after[name]}"
            )
    for name, (version, _) in sorted(targets.items()):
        print(f"{name} {before[name]} -> {version}")


if __name__ == "__main__":
    main()
