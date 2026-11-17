"""Reject unsafe budgets and release snapshots before any deployment work."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capacity", ROOT / "capacity.py")
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)


@pytest.fixture
def budget():
    return json.loads((ROOT / "connection-budget.json").read_text())


def inventory(budget):
    return {
        "full_visibility": True,
        "server": copy.deepcopy(budget["server"]),
        "unallocated_client_connections": 1,
        "ingress_and_dispatch_paused": True,
        "roles": {
            role: {"connection_limit": limit, "superuser": False, "connections": 0}
            for role, limit in {**budget["roles"], "database_migrator": 1}.items()
        },
    }


def test_budget_retains_operator_and_migration_slots(budget):
    assert capacity.validate(budget) == {
        "application_peak": 10,
        "ordinary_slots": 12,
        "operator": 1,
        "migration": 1,
        "provider": 1,
        "migration_mode": "offline",
    }


@pytest.mark.parametrize(
    "role", ["litellm", "market_scanner_writer", "momentum_results_reader"]
)
def test_larger_pool_cannot_silently_exhaust_server(budget, role):
    budget["roles"][role] += 1
    with pytest.raises(ValueError, match="exceeds"):
        capacity.validate(budget)


@pytest.mark.parametrize(
    "mutation", ["hidden", "provider", "superuser", "role_limit", "server"]
)
def test_live_inventory_must_prove_capacity(budget, mutation):
    observed = inventory(budget)
    if mutation == "hidden":
        observed["full_visibility"] = False
    elif mutation == "provider":
        observed["unallocated_client_connections"] = 2
    elif mutation == "superuser":
        observed["roles"]["litellm"]["superuser"] = True
    elif mutation == "role_limit":
        observed["roles"]["litellm"]["connection_limit"] = 12
    else:
        observed["server"]["superuser_reserved_connections"] = 4
    with pytest.raises(ValueError):
        capacity.validate(budget, observed)


def test_release_rejects_overlap_until_target_drained(budget):
    observed = inventory(budget)
    observed["roles"]["litellm"]["connections"] = 2
    with pytest.raises(ValueError, match="drained"):
        capacity.validate(budget, observed, ["litellm"])
    observed["roles"]["litellm"]["connections"] = 0
    capacity.validate(budget, observed, ["litellm"])
    observed["ingress_and_dispatch_paused"] = False
    with pytest.raises(ValueError, match="Pause"):
        capacity.validate(budget, observed, ["litellm"])


def test_versioned_consumer_settings_match_budget(budget):
    capacity.validate_sources(budget)


def test_source_configuration_growth_is_rejected(budget, tmp_path):
    import ast
    import shutil

    for relative in (
        "database/domains.json",
        "apps/backend/market-scanner-adk/src/app/config/settings.py",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT.parent / relative, target)
    settings = tmp_path / "apps/backend/market-scanner-adk/src/app/config/settings.py"
    tree = ast.parse(settings.read_text())
    field = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "DATABASE_POOL_SIZE"
    )
    for keyword in field.keywords:
        if keyword.arg in {"default", "le"}:
            keyword.value = ast.Constant(2)
    settings.write_text(ast.unparse(tree))
    with pytest.raises(ValueError, match="pool exceeds"):
        capacity.validate_sources(budget, tmp_path)


def test_unsupported_release_overlap_is_rejected(budget):
    budget["release_mode"] = "rolling"
    with pytest.raises(ValueError, match="Overlapping"):
        capacity.validate(budget)


def test_negative_consumer_allocation_cannot_hide_capacity(budget):
    budget["consumers"]["scanner"]["admission"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        capacity.validate(budget)


def test_offline_migration_rejects_live_application(budget):
    observed = inventory(budget)
    observed["roles"]["litellm"]["connections"] = 1
    with pytest.raises(ValueError, match="All application"):
        capacity.validate(budget, observed, phase="migration")
    observed["roles"]["litellm"]["connections"] = 0
    observed["roles"]["database_migrator"]["connections"] = 1
    capacity.validate(budget, observed, phase="migration")
    with pytest.raises(ValueError, match="Migration connections"):
        capacity.validate(budget, observed)
    observed["ingress_and_dispatch_paused"] = False
    with pytest.raises(ValueError, match="Pause every"):
        capacity.validate(budget, observed, phase="migration")
