"""Cloud Run entrypoint."""

from momentum_public_mcp.application import MomentumPublicApplication
from momentum_public_mcp.config import Settings

application = MomentumPublicApplication(Settings())
mcp = application.mcp


def main() -> None:
    application.run()


if __name__ == "__main__":
    main()
