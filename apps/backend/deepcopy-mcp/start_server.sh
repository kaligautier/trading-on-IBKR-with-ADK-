#!/bin/sh
set -eu
if [ "${MCP_TELEMETRY_ENABLED:-false}" = "true" ]; then
    if ! command -v opentelemetry-instrument >/dev/null 2>&1; then
        echo "Telemetry requires an image built with INSTALL_TELEMETRY=true" >&2
        exit 1
    fi
    exec opentelemetry-instrument python -m app.main "$@"
fi
exec python -m app.main "$@"
