import asyncio
import time

from app.config.llm import create_model
from app.config.rate_limit import ModelRequestGate
from app.config.settings import Settings


async def test_shared_gate_bounds_concurrency_and_spaces_starts():
    gate = ModelRequestGate(concurrency=2, minimum_interval=0.02)
    active = maximum = 0
    starts = []

    async def request():
        nonlocal active, maximum
        async with gate.acquire():
            starts.append(time.monotonic())
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0.06)
            finally:
                active -= 1

    await asyncio.gather(*(request() for _ in range(5)))
    assert maximum == 2
    assert all(b - a >= 0.019 for a, b in zip(starts, starts[1:], strict=False))


def test_quick_and_deep_models_share_one_gate_without_sdk_retries():
    config = Settings(
        LITELLM_API_BASE="https://gateway.example", LITELLM_API_KEY="test"
    )
    gate = ModelRequestGate()
    models = [create_model(config, name, gate) for name in ("quick", "deep")]
    assert all(model._gate is gate for model in models)
    assert all(
        model.client_kwargs["http_options"].retry_options.attempts == 1
        for model in models
    )
