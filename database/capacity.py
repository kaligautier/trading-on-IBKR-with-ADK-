"""Validate the shared 15-slot budget; live/release checks require full visibility."""

import argparse
import ast
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(budget, inventory=None, release_roles=()):
    if budget["release_mode"] != "drain-before-replace":
        raise ValueError("Overlapping release mode is outside the reviewed capacity")
    server = budget["server"]
    values = [
        *server.values(),
        budget["operator_allowance"],
        budget["migration_allowance"],
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
    total = application + budget["operator_allowance"] + budget["migration_allowance"]
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
    if inventory is not None:
        validate_inventory(budget, inventory, available - total, release_roles)
    elif release_roles:
        raise ValueError("A release requires a current full-visibility inventory")
    return {
        "application_peak": application,
        "ordinary_slots": available,
        "operator": budget["operator_allowance"],
        "migration": budget["migration_allowance"],
    }


def validate_inventory(budget, inventory, spare, release_roles):
    if inventory.get("full_visibility") is not True:
        raise ValueError("Provider/client visibility is incomplete; rollout blocked")
    if inventory["server"] != budget["server"]:
        raise ValueError("Observed server settings differ from the reviewed budget")
    if inventory.get("unallocated_client_connections", -1) not in range(spare + 1):
        raise ValueError("Unallocated provider/client connections consume headroom")
    expected = {**budget["roles"], "database_migrator": budget["migration_allowance"]}
    for role, limit in expected.items():
        observed = inventory["roles"][role]
        if observed["superuser"] or observed["connection_limit"] != limit:
            raise ValueError("Runtime role protection differs from the reviewed budget")
        if observed["connections"] > limit:
            raise ValueError("Existing sessions exceed the new limit; drain first")
    for role in release_roles:
        if role not in expected or inventory["roles"][role]["connections"] != 0:
            raise ValueError("Release target has not drained")
    if release_roles and inventory.get("ingress_and_dispatch_paused") is not True:
        raise ValueError("Pause ingress and dispatch before the release gate")


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--release-role", action="append", default=[])
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
        )
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Capacity validation failed: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
