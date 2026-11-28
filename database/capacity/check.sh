#!/usr/bin/env bash
# Validate the shared 15-slot PostgreSQL connection budget (see
# docs/database-connection-capacity.md). Run from anywhere; needs only jq.
#   check.sh                               static budget and consumer settings
#   check.sh --test                        the policy's own test cases
#   check.sh SNAPSHOT [runtime|migration] [LOGIN...]
#                                          rollout gate on a snapshot.sql row; each
#                                          LOGIN is a role being replaced
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
inputs=(-L "$root/database/capacity"
  --slurpfile budget "$root/database/capacity/budget.json"
  --slurpfile domains "$root/database/domains.json"
  --rawfile scanner "$root/apps/backend/market-scanner-adk/src/app/config/settings.py"
  --rawfile reader "$root/apps/backend/market-scanner-api/src/app/config/settings.py"
  --rawfile momentum_api "$root/apps/backend/momentum-api/src/app/config/settings.py"
  --rawfile litellm "$root/infra/litellm/foundation.tf")
if [[ ${1:-} == --test ]]; then
  exec jq -n -r "${inputs[@]}" -f "$root/database/capacity/tests.jq"
fi
if [[ $# -eq 0 ]]; then
  inventory=(--argjson inventory null)
else
  inventory=(--slurpfile inventory "$1")
  shift
fi
phase=${1:-runtime}
shift || true
exec jq -n "${inputs[@]}" "${inventory[@]}" --arg phase "$phase" \
  --argjson release "$(jq -n '$ARGS.positional' --args "$@")" \
  -f "$root/database/capacity/check.jq"
