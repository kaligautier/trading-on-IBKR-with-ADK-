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
        "unallocated_client_connections": 0,
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
        observed["unallocated_client_connections"] = 1
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
