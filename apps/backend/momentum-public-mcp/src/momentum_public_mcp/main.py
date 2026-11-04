"""Cloud Run entrypoint."""

from momentum_public_mcp.application import MomentumPublicApplication
from momentum_public_mcp.config.config import Settings
from momentum_public_mcp.observability.logger import config_logger
from momentum_public_mcp.observability.telemetry import init_telemetry

settings = Settings()

# Initialize OpenTelemetry before logging so trace context is available.
telemetry_provider = init_telemetry(settings)

# Configure JSON logging with trace correlation.
config_logger(settings)

application = MomentumPublicApplication(settings)
mcp = application.mcp


def main() -> None:
    try:
        application.run()
    finally:
        if telemetry_provider is not None:
            telemetry_provider.shutdown()


if __name__ == "__main__":
    main()
