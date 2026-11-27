"""Validate the shared 15-slot budget; live/release checks require full visibility."""

import argparse
import ast
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(budget, inventory=None, release_roles=(), phase="runtime"):
    if budget["release_mode"] != "drain-before-replace":
        raise ValueError("Overlapping release mode is outside the reviewed capacity")
    validate_phase_config(budget, phase)
    server = budget["server"]
    values = [
        *server.values(),
        budget["operator_allowance"],
        budget["migration_allowance"],
        budget["provider_allowance"],
        *budget["roles"].values(),
        *(
            consumer[key]
            for consumer in budget["consumers"].values()
            for key in ("active", "admission")
        ),
    ]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Connection limits must be nonnegative integers")
    if min(budget["roles"].values()) < 1 or budget["operator_allowance"] < 1:
        raise ValueError("Each runtime and the operator require an allowance")
    available = (
        server["max_connections"]
        - server["superuser_reserved_connections"]
        - server["reserved_connections"]
    )
    application = sum(budget["roles"].values())
    workload = max(application, budget["migration_allowance"])
    total = workload + budget["operator_allowance"] + budget["provider_allowance"]
    if total > available:
        raise ValueError("Global connection budget exceeds ordinary server capacity")
    allocated = []
    for consumer in budget["consumers"].values():
        roles = consumer["roles"]
        allocated.extend(roles)
        if consumer["active"] + consumer["admission"] > sum(
            budget["roles"][r] for r in roles
        ):
            raise ValueError("Consumer exceeds its role allocation")
    if sorted(allocated) != sorted(budget["roles"]):
        raise ValueError("Every runtime role must be counted exactly once")
    validate_runtimes(budget)
    if inventory is not None:
        validate_inventory(budget, inventory, available - total, release_roles, phase)
    elif release_roles or phase == "migration":
        raise ValueError("A release requires a current full-visibility inventory")
    return {
        "application_peak": application,
        "ordinary_slots": available,
        "operator": budget["operator_allowance"],
        "migration": budget["migration_allowance"],
        "provider": budget["provider_allowance"],
        "migration_mode": budget["migration_mode"],
    }


def validate_runtimes(budget):
    """Each Cloud Run instance opens its own pool: instances multiply connections."""
    runtimes = budget["runtimes"]
    by_consumer = {}
    for runtime in runtimes:
        instances, connections = runtime["instances"], runtime["connections"]
        if any(
            type(value) is not int or value < 1 for value in (instances, connections)
        ):
            raise ValueError(
                "Runtime instances and connections must be positive integers"
            )
        consumer = runtime["consumer"]
        if consumer != "migration" and consumer not in budget["consumers"]:
            raise ValueError("Runtime belongs to an unknown consumer")
        by_consumer.setdefault(consumer, []).append(runtime)
    if set(budget["consumers"]) - set(by_consumer):
        raise ValueError("Every consumer must declare the runtimes that open its pools")
    migration = by_consumer.pop("migration", [])
    if (
        sum(r["instances"] * r["connections"] for r in migration)
        > budget["migration_allowance"]
    ):
        raise ValueError("Migration runtimes exceed the migration allowance")
    for name, members in by_consumer.items():
        validate_consumer_runtimes(budget["consumers"][name], members)


def validate_consumer_runtimes(consumer, members):
    if consumer["admission"] == 0:
        # Without admission, every instance can hold its whole pool at once.
        peak = sum(r["instances"] * r["connections"] for r in members)
        if peak > consumer["active"]:
            raise ValueError("Runtime instances exceed the consumer allocation")
    else:
        # One admitted process holds its pool; every other one only probes.
        if max(r["connections"] for r in members) > consumer["active"]:
            raise ValueError("Admitted runtime exceeds the consumer allocation")
        if sum(r["instances"] for r in members) - 1 > consumer["admission"]:
            raise ValueError("Runtime instances exceed the admission allocation")


def _terraform_block(text, kind, name):
    match = re.search(rf'resource\s+"{kind}"\s+"{name}"\s*\{{', text)
    if match is None:
        return None
    depth, end = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[end], 0)
        end += 1
    return text[match.start() : end]


def _terraform_setting(block, key):
    values = re.findall(rf"^\s*{key}\s*=\s*(\S+)", block, re.MULTILINE)
    if len(values) != 1 or not values[0].isdigit():
        raise ValueError(f"Cloud Run {key} must be a single literal integer")
    return int(values[0])


def validate_runtime_sources(budget, root):
    """Pin Cloud Run scaling to the budget and reject undeclared database clients."""
    declared = set()
    for runtime in budget["runtimes"]:
        kind, name = runtime["resource"].split(".")
        block = _terraform_block((root / runtime["file"]).read_text(), kind, name)
        if block is None:
            raise ValueError("Declared Cloud Run runtime is missing from Terraform")
        key = (
            "parallelism" if kind == "google_cloud_run_v2_job" else "max_instance_count"
        )
        if _terraform_setting(block, key) != runtime["instances"]:
            raise ValueError("Cloud Run scaling differs from the capacity budget")
        declared.add((runtime["file"], runtime["resource"]))
    for path in sorted((root / "infra").rglob("*.tf")):
        text = path.read_text()
        for match in re.finditer(
            r'resource\s+"(google_cloud_run_v2_(?:service|job))"\s+"(\w+)"', text
        ):
            block = _terraform_block(text, *match.groups())
            source = (str(path.relative_to(root)), ".".join(match.groups()))
            if re.search("database", block, re.IGNORECASE) and source not in declared:
                raise ValueError("Cloud Run database client is missing from the budget")
    workers = re.findall(
        r'"--num_workers",\s*"(\d+)"',
        "".join(
            path.read_text() for path in sorted((root / "infra/litellm").glob("*.tf"))
        ),
    )
    if not workers or set(workers) != {"1"}:
        raise ValueError("LiteLLM workers multiply its pool beyond the allocation")


def validate_phase_config(budget, phase):
    if phase not in {"runtime", "migration"} or budget["migration_mode"] != "offline":
        raise ValueError("Migrations require an offline maintenance phase")


def validate_inventory(budget, inventory, spare, release_roles, phase):
    if inventory.get("full_visibility") is not True:
        raise ValueError("Provider/client visibility is incomplete; rollout blocked")
    if inventory["server"] != budget["server"]:
        raise ValueError("Observed server settings differ from the reviewed budget")
    if inventory.get("unallocated_client_connections", -1) not in range(
        spare + budget["provider_allowance"] + 1
    ):
        raise ValueError("Unallocated provider/client connections consume headroom")
    expected = {**budget["roles"], "database_migrator": budget["migration_allowance"]}
    for role, limit in expected.items():
        observed = inventory["roles"][role]
        if observed["superuser"] or observed["connection_limit"] != limit:
            raise ValueError("Runtime role protection differs from the reviewed budget")
        if observed["connections"] > limit:
            raise ValueError("Existing sessions exceed the new limit; drain first")
    validate_phase_inventory(budget, inventory, phase)
    for role in release_roles:
        if role not in expected or inventory["roles"][role]["connections"] != 0:
            raise ValueError("Release target has not drained")
    if release_roles and inventory.get("ingress_and_dispatch_paused") is not True:
        raise ValueError("Pause ingress and dispatch before the release gate")


def validate_phase_inventory(budget, inventory, phase):
    if phase == "runtime" and inventory["roles"]["database_migrator"]["connections"]:
        raise ValueError("Migration connections must drain before runtime")
    if phase == "migration":
        if inventory.get("ingress_and_dispatch_paused") is not True:
            raise ValueError("Pause every application before offline migration")
        if any(inventory["roles"][role]["connections"] for role in budget["roles"]):
            raise ValueError("All application connections must drain before migration")


def validate_sources(budget, root=ROOT.parent):
    """Reject pool settings that no longer match the reviewed fleet allocation."""
    domains = json.loads((root / "database/domains.json").read_text())
    for domain in ("market_scanner", "momentum"):
        for role, limit in domains[domain]["runtime_roles"].items():
            if budget["roles"][role] != limit:
                raise ValueError("Domain role limits differ from the capacity budget")
    for component, maximum in (
        ("market-scanner-adk", 1),
        ("market-scanner-api", 1),
        ("momentum-api", 1),
    ):
        path = root / "apps/backend" / component / "src/app/config/settings.py"
        tree = ast.parse(path.read_text())
        fields = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DATABASE_POOL_SIZE"
        ]
        if len(fields) != 1 or not isinstance(fields[0], ast.Call):
            raise ValueError("Missing bounded database pool setting")
        limits = {
            item.arg: ast.literal_eval(item.value)
            for item in fields[0].keywords
            if item.arg in {"default", "le"}
        }
        if limits != {"default": maximum, "le": maximum}:
            raise ValueError("Configured pool exceeds the shared allocation")
    foundation = (root / "infra/litellm/foundation.tf").read_text()
    pools = re.findall(r"database_connection_pool_limit\s*=\s*(\d+)", foundation)
    if pools != ["1"] or budget["roles"]["litellm"] != 2:
        raise ValueError("LiteLLM pools differ from the shared allocation")
    validate_runtime_sources(budget, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--release-role", action="append", default=[])
    parser.add_argument("--phase", choices=("runtime", "migration"), default="runtime")
    arguments = parser.parse_args()
    try:
        budget = json.loads((ROOT / "connection-budget.json").read_text())
        validate_sources(budget)
        result = validate(
            budget,
            json.loads(arguments.inventory.read_text())
            if arguments.inventory
            else None,
            arguments.release_role,
            arguments.phase,
        )
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Capacity validation failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
