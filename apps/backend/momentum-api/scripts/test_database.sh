#!/usr/bin/env bash
# Only a labelled disposable database. Never accepts an arbitrary database URL.
set -euo pipefail
name=momentum-current-api-test-db
label=org.deepcopy.momentum-api-test
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
script="$root/apps/backend/momentum-api/scripts/test_database.sh"
image=postgres:18@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336

verify_container() {
  test "$(docker inspect --format '{{index .Config.Labels "org.deepcopy.momentum-api-test"}}' "$name")" = true
  test "$(docker port "$name" 5432/tcp)" = 127.0.0.1:55473
}

migrate() {
  verify_container
  docker exec -i "$name" psql -v ON_ERROR_STOP=1 -U postgres <<'SQL'
CREATE ROLE database_migrator LOGIN PASSWORD 'local-only';
CREATE ROLE momentum_results_writer LOGIN PASSWORD 'local-only';
CREATE ROLE momentum_sessions_writer LOGIN PASSWORD 'local-only';
CREATE ROLE momentum_results_reader LOGIN PASSWORD 'local-only';
CREATE DATABASE momentum;
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
SQL
  docker exec -i "$name" psql -v ON_ERROR_STOP=1 -U postgres -d momentum < "$root/database/domains/momentum/bootstrap.sql"
  docker exec -i "$name" psql -v ON_ERROR_STOP=1 -U database_migrator -d momentum < "$root/database/operations/prepare.sql"
  docker build --tag local/deepcopy-database:5.0.4 "$root/database"
  for command in validate update update; do
    docker run --rm --network "container:$name" \
      --volume "$root/database:/liquibase/changelog:ro" \
      --env LIQUIBASE_COMMAND_URL=jdbc:postgresql://127.0.0.1:5432/momentum \
      --env LIQUIBASE_COMMAND_USERNAME=database_migrator \
      --env LIQUIBASE_COMMAND_PASSWORD=local-only \
      --env LIQUIBASE_COMMAND_CHANGELOG_FILE=domains/momentum/changelog.yaml \
      --env LIQUIBASE_LIQUIBASE_SCHEMA_NAME=liquibase \
      local/deepcopy-database:5.0.4 "$command"
  done
}

case "${1:-}" in
  verify)
    MOMENTUM_API_FIXTURE_OWNER=$(python3 -c 'from uuid import uuid4; print(uuid4().hex)')
    export MOMENTUM_API_FIXTURE_OWNER
    cleanup_verify() {
      if test "$(docker inspect --format '{{index .Config.Labels "org.deepcopy.momentum-api-test-owner"}}' "$name" 2>/dev/null)" = "$MOMENTUM_API_FIXTURE_OWNER"; then
        bash "$script" stop
      fi
    }
    trap cleanup_verify EXIT
    bash "$script" start
    cd "$root/apps/backend/momentum-api"
    MOMENTUM_API_TEST_DATABASE=1 uv run --frozen pytest src/test "${@:2}"
    ;;
  start)
    if docker container inspect "$name" >/dev/null 2>&1; then
      echo 'Container exists; inspect it and stop it explicitly before restarting.' >&2
      exit 1
    fi
    docker run --detach --rm --name "$name" --label "$label=true" \
      --label "org.deepcopy.momentum-api-test-owner=${MOMENTUM_API_FIXTURE_OWNER:-manual}" \
      --publish 127.0.0.1:55473:5432 --publish 127.0.0.1:55474:8080 \
      --env POSTGRES_PASSWORD=local-only "$image"
    for ((attempt=0; attempt<60; attempt++)); do
      if docker exec "$name" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; then
        migrate
        exit 0
      fi
      sleep 1
    done
    echo 'Database not ready; inspect the labelled container.' >&2
    exit 1
    ;;
  stop) verify_container; docker stop "$name" ;;
  *) echo 'Usage: bash scripts/test_database.sh start|stop|verify' >&2; exit 2 ;;
esac
