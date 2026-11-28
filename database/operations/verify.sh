#!/usr/bin/env bash
# Read-only checks of one domain database before a Liquibase operation.
#   verify.sh baseline DOMAIN   schema and grants equal the adopted Aiven baseline
#                               (domains.json fingerprint); run before adoption
#   verify.sh current DOMAIN    schema equals the current release (current.json) and
#                               every release changeset is applied with its checksum
# Both also check the runtime logins' isolation (runtime_policy.sql).
# The connection comes from libpq: PGSERVICE (pg_service.conf with sslmode=verify-full
# and sslrootcert) plus ~/.pgpass, never a URL or password on the command line.
# PSQL overrides the client command, for example `docker exec -i <container> psql ...`.
set -euo pipefail
mode=${1:?baseline or current} domain=${2:?market_scanner or momentum}
here=$(cd "$(dirname "$0")" && pwd)
[[ $domain == market_scanner || $domain == momentum ]] || { echo "Unknown domain $domain" >&2; exit 2; }
read -r -a psql <<< "${PSQL:-psql}"
run() { "${psql[@]}" -X -At -v ON_ERROR_STOP=1 -d "$domain" "$@"; }

read -r database transport < <(run -F ' ' -c "SELECT current_database(),
  CASE WHEN inet_server_addr() IS NULL OR host(inet_server_addr()) IN ('127.0.0.1', '::1') THEN 'local'
       WHEN (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()) THEN 'tls' ELSE 'plain' END")
[[ $database == "$domain" ]] || { echo "Connected to $database, not $domain" >&2; exit 1; }
[[ $transport != plain ]] || { echo "Remote connections require TLS (sslmode=verify-full)" >&2; exit 1; }
run -v roles="$(jq -c --arg d "$domain" '.[$d].runtime_roles' "$here/../domains.json")" \
  -f - < "$here/runtime_policy.sql" >/dev/null

fingerprint() { jq -S -c . | tr -d '\n' | sha256sum | cut -c1-64; }
case $mode in
  baseline)
    expected=$(jq -r --arg d "$domain" '.[$d].fingerprint' "$here/../domains.json")
    actual=$(run -f - < "$here/catalog.sql" | fingerprint)
    [[ $actual == "$expected" ]] || { echo "$domain: schema differs from the verified Aiven baseline ($actual); adoption refused" >&2; exit 1; }
    echo "$domain: schema and runtime policy match the Aiven baseline" ;;
  current)
    manifest="$here/../domains/$domain/current.json"
    snapshot=$(run -v current=true -f - < "$here/catalog.sql")
    actual=$(sed -n 1p <<< "$snapshot" | fingerprint)
    [[ $actual == "$(jq -r .fingerprint "$manifest")" ]] \
      || { echo "$domain: schema differs from the current migrated release ($actual)" >&2; exit 1; }
    # Adoption keeps legacy rows; each release changeset must be applied with its checksum.
    sed -n 2p <<< "$snapshot" | jq -e --slurpfile manifest "$manifest" '
      map(select(.exectype == "EXECUTED" or .exectype == "RERAN" or .exectype == "MARK_RAN")
          | {id, author, filename, md5sum}) as $applied
      | all($manifest[0].changesets[]; . as $c | $applied | index([$c]) != null)' >/dev/null \
      || { echo "$domain: migration history is missing or differs from the current release" >&2; exit 1; }
    echo "$domain: schema, history and runtime policy match the current release" ;;
  *) echo "Unknown mode $mode" >&2; exit 2 ;;
esac
