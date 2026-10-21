from app.config.storage import MomentumStorage


def test_fresh_workspace_uses_momentum_home(tmp_path, monkeypatch):
    monkeypatch.delenv("MOMENTUM_CACHE_DIR", raising=False)
    monkeypatch.delenv("TRADINGAGENTS_CACHE_DIR", raising=False)

    storage = MomentumStorage.from_environment(tmp_path)

    assert storage.cache_directory == tmp_path / ".momentum" / "cache"


def test_existing_legacy_workspace_is_reused(tmp_path, monkeypatch):
    monkeypatch.delenv("MOMENTUM_MEMORY_LOG_PATH", raising=False)
    monkeypatch.delenv("TRADINGAGENTS_MEMORY_LOG_PATH", raising=False)
    legacy_directory = tmp_path / ".tradingagents"
    legacy_directory.mkdir()

    storage = MomentumStorage.from_environment(tmp_path)

    assert storage.memory_log_path == legacy_directory / "memory" / "trading_memory.md"


def test_momentum_environment_name_has_priority_over_legacy_alias(
    tmp_path, monkeypatch
):
    primary = tmp_path / "primary"
    legacy = tmp_path / "legacy"
    monkeypatch.setenv("MOMENTUM_RESULTS_DIR", str(primary))
    monkeypatch.setenv("TRADINGAGENTS_RESULTS_DIR", str(legacy))

    storage = MomentumStorage.from_environment(tmp_path)

    assert storage.results_directory == primary


def test_legacy_environment_name_remains_supported(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy-cache"
    monkeypatch.delenv("MOMENTUM_CACHE_DIR", raising=False)
    monkeypatch.setenv("TRADINGAGENTS_CACHE_DIR", str(legacy))

    storage = MomentumStorage.from_environment(tmp_path)

    assert storage.cache_directory == legacy
