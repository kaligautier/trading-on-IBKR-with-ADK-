# Shared 15-slot PostgreSQL budget. Every function returns a list of error messages;
# an empty list means the budget (and, when given, the live inventory) is safe.

def available:
  .server.max_connections - .server.superuser_reserved_connections - .server.reserved_connections;

def total:
  ([(.roles | add), .migration_allowance] | max) + .operator_allowance + .provider_allowance;

def numbers:
  [.server[], .operator_allowance, .migration_allowance, .provider_allowance, .roles[],
   (.consumers[] | .active, .admission)];

def budget_errors:
  . as $b
  | [ if .release_mode != "drain-before-replace" then "Overlapping release mode is outside the reviewed capacity" else empty end,
      if .migration_mode != "offline" then "Migrations require an offline maintenance phase" else empty end,
      if any(numbers[]; type != "number" or . < 0 or . != floor) then "Connection limits must be nonnegative integers" else empty end,
      if (.roles | map(.) | min) < 1 or .operator_allowance < 1 then "Each runtime and the operator require an allowance" else empty end,
      if total > available then "Global connection budget exceeds ordinary server capacity" else empty end,
      (.consumers[] | select(.active + .admission > ([.roles[] | $b.roles[.] // 0] | add))
        | "Consumer exceeds its role allocation"),
      if ([.consumers[].roles[]] | sort) != (.roles | keys) then "Every runtime role must be counted exactly once" else empty end ];

# $inventory is the JSON row of snapshot.sql; $release lists the logins being replaced.
def inventory_errors($inventory; $release; $phase):
  . as $b
  | ({} + .roles + {database_migrator: .migration_allowance}) as $expected
  | [ if $phase != "runtime" and $phase != "migration" then "Phase must be runtime or migration" else empty end,
      if $inventory.full_visibility != true then "Provider/client visibility is incomplete; rollout blocked" else empty end,
      if $inventory.server != .server then "Observed server settings differ from the reviewed budget" else empty end,
      ($inventory.unallocated_client_connections // -1) as $other
      | if $other < 0 or $other > (available - total + .provider_allowance) then "Unallocated provider/client connections consume headroom" else empty end,
      ($expected | to_entries[] | . as $role | $inventory.roles[$role.key] as $seen
        | if $seen == null or $seen.superuser != false or $seen.connection_limit != $role.value then "Runtime role protection differs from the reviewed budget"
          elif $seen.connections > $role.value then "Existing sessions exceed the new limit; drain first"
          else empty end),
      if $phase == "runtime" and ($inventory.roles.database_migrator.connections // 0) > 0 then "Migration connections must drain before runtime" else empty end,
      if $phase == "migration" and $inventory.ingress_and_dispatch_paused != true then "Pause every application before offline migration" else empty end,
      if $phase == "migration" and any($b.roles | keys[]; ($inventory.roles[.].connections // 0) > 0) then "All application connections must drain before migration" else empty end,
      ($release[] | . as $r | select(($expected | has($r) | not) or ($inventory.roles[$r].connections // 1) != 0) | "Release target has not drained"),
      if ($release | length) > 0 and $inventory.ingress_and_dispatch_paused != true then "Pause ingress and dispatch before the release gate" else empty end ]
  | unique;

# Consumers' versioned settings must match the budget they are counted against.
def pool_limit: capture("DATABASE_POOL_SIZE: int = Field\\((?<args>[^)]*)\\)").args
  | [scan("\\b(default|le)=(\\d+)") | {(.[0]): (.[1] | tonumber)}] | add;

def source_errors($domains; $settings; $litellm):
  . as $b
  | [ ($domains.market_scanner.runtime_roles, $domains.momentum.runtime_roles | to_entries[]
        | select($b.roles[.key] != .value) | "Domain role limits differ from the capacity budget"),
      ($settings[] | select(([try pool_limit catch null] | .[0]) != {default: 1, le: 1}) | "Configured pool exceeds the shared allocation"),
      if ([$litellm | scan("database_connection_pool_limit\\s*=\\s*(\\d+)")[0]] != ["1"]) or .roles.litellm != 2
        then "LiteLLM pools differ from the shared allocation" else empty end ]
  | unique;

def summary:
  {application_peak: (.roles | add), ordinary_slots: available, operator: .operator_allowance,
   migration: .migration_allowance, provider: .provider_allowance, migration_mode};
