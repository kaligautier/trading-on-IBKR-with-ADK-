from app.infrastructure.memory.log import MemoryLogConfiguration, TradingMemoryLog


def memory_log(tmp_path):
    return TradingMemoryLog(MemoryLogConfiguration(path=tmp_path / "memory.md"))


def test_decision_storage_is_idempotent(tmp_path):
    log = memory_log(tmp_path)

    log.store_decision("NVDA", "2026-08-02", "Rating: Buy")
    log.store_decision("NVDA", "2026-08-02", "Rating: Buy")

    assert len(log.load_entries()) == 1
    assert log.get_pending_entries()[0]["rating"] == "Buy"


def test_outcome_update_exposes_reflection_as_future_context(tmp_path):
    log = memory_log(tmp_path)
    log.store_decision("NVDA", "2026-07-01", "Rating: Buy")

    log.batch_update_with_outcomes(
        [
            {
                "ticker": "NVDA",
                "trade_date": "2026-07-01",
                "raw_return": 0.08,
                "alpha_return": 0.03,
                "holding_days": 5,
                "reflection": "Momentum persisted and the thesis held.",
            }
        ]
    )

    log.store_decision("NVDA", "2026-07-01", "Rating: Buy")
    assert len(log.load_entries()) == 1
    context = log.get_past_context("NVDA")
    assert "Momentum persisted" in context
    assert log.get_pending_entries() == []


def test_cross_ticker_lessons_are_injected(tmp_path):
    log = memory_log(tmp_path)
    log.store_decision("ASML", "2026-07-01", "Rating: Hold")
    log.update_with_outcome(
        "ASML",
        "2026-07-01",
        0.02,
        0.01,
        5,
        "Wait for confirmation before sizing.",
    )

    assert "Recent cross-ticker lessons" in log.get_past_context("NVDA")
