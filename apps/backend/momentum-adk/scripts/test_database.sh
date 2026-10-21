#!/usr/bin/env bash
set -euo pipefail

name=momentum-test-db
image=postgres:17@sha256:d74eeac9a635390a49bc21bd49fccd973de707e2a53a76ac49b552b8712ec46f
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
label=org.deepcopy.momentum-test

case "${1:-}" in
  start)
    if docker container inspect "$name" >/dev/null 2>&1; then
      echo "Test container already exists; inspect/stop it explicitly." >&2
      exit 1
    fi
    docker build --tag local/deep-copy-liquibase:5.0.4 "$root/database"
    docker run --detach --rm --name "$name" --label "$label=true" \
      --publish 127.0.0.1:55449:5432 \
      --env POSTGRES_PASSWORD=local-test-only "$image"
    for ((attempt=0; attempt<60; attempt++)); do
      if docker exec "$name" pg_isready --username postgres >/dev/null 2>&1; then
        echo "Disposable PostgreSQL ready on 127.0.0.1:55449"
        exit 0
      fi
      sleep 1
    done
    echo "PostgreSQL did not become ready; inspect the labeled container." >&2
    exit 1
    ;;
  stop)
    test "$(docker inspect --format '{{index .Config.Labels "org.deepcopy.momentum-test"}}' "$name")" = true
    docker stop "$name"
    ;;
  *)
    echo "Usage: bash scripts/test_database.sh start|stop" >&2
    exit 2
    ;;
esac
