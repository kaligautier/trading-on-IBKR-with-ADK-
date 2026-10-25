"""Cloud Run entrypoint."""

from momentum_public_mcp.application import (
    MomentumPublicApplication,
    MomentumPublicSettings,
)

application = MomentumPublicApplication(MomentumPublicSettings.from_environment())
mcp = application.mcp


def main() -> None:
    application.run()


if __name__ == "__main__":
    main()
