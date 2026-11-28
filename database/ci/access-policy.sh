#!/usr/bin/env bash
# Prove on a disposable server migrated by .github/actions/domain-database that each
# runtime login of domains.json is confined to its domain, and that a bootstrap refuses
# an unusable or replication-capable runtime login. Test-only; never point it at Aiven.
# Usage: NAME=<container> PASSWORD=<test password> database/ci/access-policy.sh
set -euo pipefail
: "${NAME:?container name}" "${PASSWORD:?test password}"
cd "$(dirname "$0")/.."
SESSION_WRITERS=" market_scanner_writer momentum_sessions_writer "
failures=0

psql_as() { # ROLE DATABASE, SQL on stdin
  docker exec -i -e PGPASSWORD="$PASSWORD" "$NAME" \
    psql -X -q -At -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$1" -d "$2"
}
fail() { echo "::error::$*"; failures=$((failures + 1)); }
allowed() { # ROLE DATABASE SQL
  local output
  output=$(psql_as "$1" "$2" <<< "$3" 2>&1) || fail "$1 on $2 was refused: $3: $output"
}
denied() { # ROLE DATABASE SQL
  local output
  if output=$(psql_as "$1" "$2" <<< "$3" 2>&1); then
    fail "$1 on $2 was allowed: $3"
  elif [[ ! "$output" =~ "permission denied"|"read-only transaction" ]]; then
    fail "$1 on $2 failed for another reason: $3: $output"
  fi
}

domains=$(jq -r 'to_entries[] | select(.value.runtime_roles) | .key' domains.json)
while read -r domain role; do
  allowed "$role" "$domain" "SELECT 1"
  for other in $domains; do
    [[ "$other" == "$domain" ]] || denied "$role" "$other" "SELECT 1"
  done
  denied "$role" "$domain" "CREATE TABLE _analysis.forbidden(id int)"
  denied "$role" "$domain" "SELECT count(*) FROM liquibase.databasechangelog"
  if [[ "$SESSION_WRITERS" == *" $role "* ]]; then
    allowed "$role" "$domain" "SELECT count(*) FROM _sessions.sessions"
    denied "$role" "$domain" "CREATE TABLE _sessions.forbidden(id int)"
    denied "$role" "$domain" "UPDATE _sessions.adk_internal_metadata SET value = '0'"
  else
    denied "$role" "$domain" "SELECT count(*) FROM _sessions.sessions"
  fi
done < <(jq -r 'to_entries[] | .key as $d | .value.runtime_roles // {} | keys[] | "\($d) \(.)"' domains.json)
allowed market_scanner_reader market_scanner "SELECT count(*) FROM _analysis.market_scans"

while read -r domain role; do
  for attribute in NOLOGIN REPLICATION; do
    psql_as postgres postgres <<< "ALTER ROLE $role $attribute"
    if output=$(psql_as postgres "$domain" < "domains/$domain/bootstrap.sql" 2>&1); then
      fail "$domain bootstrap accepted $role with $attribute"
    elif [[ ! "$output" =~ "Runtime roles must exist"|"non-administrative" ]]; then
      fail "$domain bootstrap failed for another reason with $role $attribute: $output"
    fi
    psql_as postgres postgres <<< "ALTER ROLE $role LOGIN NOREPLICATION"
  done
done < <(jq -r 'to_entries[] | .key as $d | .value.runtime_roles // {} | keys[] | "\($d) \(.)"' domains.json)
for domain in $domains; do
  psql_as postgres "$domain" < "domains/$domain/bootstrap.sql" >/dev/null \
    || fail "$domain bootstrap does not accept the restored runtime logins"
done

if (( failures )); then exit 1; fi
echo "PASS: runtime logins are confined to their domain; bootstraps refuse unsafe logins"
