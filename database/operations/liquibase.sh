#!/usr/bin/env bash
# Run one Liquibase CLI command on one domain database as database_migrator.
#   liquibase.sh DOMAIN COMMAND [ARGS...]
# DATABASE_ENV_FILE: a private (0600) docker env file with LIQUIBASE_COMMAND_URL
#   (jdbc:postgresql://HOST:PORT/DOMAIN?sslmode=verify-full&sslrootcert=/run/database-ca.pem),
#   LIQUIBASE_COMMAND_USERNAME=database_migrator and LIQUIBASE_COMMAND_PASSWORD.
# DATABASE_CA_FILE: the server CA, mounted read-only at /run/database-ca.pem.
# DATABASE_NETWORK: optional docker network, for example container:<name> in CI.
set -euo pipefail
domain=${1:?market_scanner or momentum} command=${2:?Liquibase command}
shift 2
root=$(cd "$(dirname "$0")/.." && pwd)
env_file=${DATABASE_ENV_FILE:?Set DATABASE_ENV_FILE to a private env file}
fail() { echo "$*" >&2; exit 2; }
[[ $domain == market_scanner || $domain == momentum ]] || fail "Unknown domain $domain"
case $command in
  validate|status|history|update-sql|update|update-to-tag|changelog-sync-to-tag) ;;
  *) fail "Unsupported Liquibase command $command" ;;
esac
[[ -f $env_file && ! -L $env_file ]] || fail "DATABASE_ENV_FILE must be a regular file"
[[ $(stat -c %a "$env_file" 2>/dev/null || stat -f %Lp "$env_file") == 600 ]] \
  || fail "DATABASE_ENV_FILE must have permissions 0600"
grep -qx 'LIQUIBASE_COMMAND_USERNAME=database_migrator' "$env_file" \
  || fail "Migrations require the database_migrator identity"
url=$(grep '^LIQUIBASE_COMMAND_URL=' "$env_file" | cut -d= -f2-)
[[ $url =~ ^jdbc:postgresql://[^/?]+/${domain}(\?|$) ]] || fail "The URL must name the $domain database"
[[ $url != *[Pp]assword=* ]] || fail "Keep the password out of the URL"
if [[ ! $url =~ ^jdbc:postgresql://(localhost|127\.0\.0\.1|\[::1\])[:/] ]]; then
  [[ $url == *sslmode=verify-full* ]] || fail "Remote connections require sslmode=verify-full"
fi
options=(--rm --env-file "$env_file" -v "$root:/liquibase/changelog:ro"
  -e LIQUIBASE_COMMAND_CHANGELOG_FILE="domains/$domain/changelog.yaml"
  -e LIQUIBASE_LIQUIBASE_SCHEMA_NAME=liquibase -e LIQUIBASE_SHOW_BANNER=false)
[[ -z ${DATABASE_CA_FILE:-} ]] || options+=(-v "$(cd "$(dirname "$DATABASE_CA_FILE")" && pwd)/$(basename "$DATABASE_CA_FILE"):/run/database-ca.pem:ro")
[[ -z ${DATABASE_NETWORK:-} ]] || options+=(--network "$DATABASE_NETWORK")
docker build --quiet --tag local/deepcopy-database:5.0.4 "$root" >/dev/null
exec docker run "${options[@]}" local/deepcopy-database:5.0.4 "$command" "$@"
