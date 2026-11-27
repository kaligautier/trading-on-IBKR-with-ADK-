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


@pytest.fixture
def sources(tmp_path):
    """Copy every file validate_sources reads, so a test can mutate one safely."""
    import shutil

    shutil.copytree(ROOT.parent / "infra", tmp_path / "infra")
    for component in ("market-scanner-adk", "market-scanner-api", "momentum-api"):
        relative = f"apps/backend/{component}/src/app/config/settings.py"
        (tmp_path / relative).parent.mkdir(parents=True)
        shutil.copyfile(ROOT.parent / relative, tmp_path / relative)
    (tmp_path / "database").mkdir()
    shutil.copyfile(ROOT / "domains.json", tmp_path / "database/domains.json")
    return tmp_path


def _rewrite(path, old, new):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def test_copied_sources_match_budget(budget, sources):
    capacity.validate_sources(budget, sources)


def test_scaling_out_a_pooled_service_is_rejected(budget, sources):
    _rewrite(
        sources / "infra/reader/main.tf",
        "max_instance_count = 1",
        "max_instance_count = 3",
    )
    with pytest.raises(ValueError, match="scaling differs"):
        capacity.validate_sources(budget, sources)


def test_job_parallelism_is_pinned(budget, sources):
    _rewrite(sources / "infra/momentum/main.tf", "parallelism = 1", "parallelism = 2")
    with pytest.raises(ValueError, match="scaling differs"):
        capacity.validate_sources(budget, sources)


def test_non_literal_scaling_is_rejected(budget, sources):
    _rewrite(
        sources / "infra/momentum-api/main.tf",
        "max_instance_count = 1",
        "max_instance_count = var.max_instances",
    )
    with pytest.raises(ValueError, match="literal integer"):
        capacity.validate_sources(budget, sources)


def test_undeclared_database_client_is_rejected(budget, sources):
    (sources / "infra/reader/extra.tf").write_text(
        'resource "google_cloud_run_v2_job" "backfill" {\n'
        '  template { parallelism = 1\n    env { name = "DATABASE_URL" } }\n}\n'
    )
    with pytest.raises(ValueError, match="missing from the budget"):
        capacity.validate_sources(budget, sources)


def test_litellm_workers_multiply_its_pool(budget, sources):
    _rewrite(
        sources / "infra/litellm/gateway.tf",
        '"--num_workers", "1"',
        '"--num_workers", "2"',
    )
    with pytest.raises(ValueError, match="workers"):
        capacity.validate_sources(budget, sources)


def test_declared_instances_cannot_exceed_pooled_allocation(budget):
    reader = next(r for r in budget["runtimes"] if r["consumer"] == "scanner_reader")
    reader["instances"] = 2
    with pytest.raises(ValueError, match="exceed the consumer allocation"):
        capacity.validate(budget)


def test_admission_only_covers_one_waiting_process(budget):
    job = next(r for r in budget["runtimes"] if r["consumer"] == "momentum")
    job["instances"] = 3
    with pytest.raises(ValueError, match="admission allocation"):
        capacity.validate(budget)


def test_admitted_process_cannot_exceed_active_slots(budget):
    scanner = next(r for r in budget["runtimes"] if r["consumer"] == "scanner")
    scanner["connections"] = 3
    with pytest.raises(ValueError, match="Admitted runtime"):
        capacity.validate(budget)


def test_every_consumer_declares_its_runtimes(budget):
    budget["runtimes"] = [
        r for r in budget["runtimes"] if r["consumer"] != "momentum_reader"
    ]
    with pytest.raises(ValueError, match="declare the runtimes"):
        capacity.validate(budget)


def test_migration_runtimes_fit_the_migration_allowance(budget):
    migration = next(r for r in budget["runtimes"] if r["consumer"] == "migration")
    migration["connections"] = 2
    with pytest.raises(ValueError, match="migration allowance"):
        capacity.validate(budget)
