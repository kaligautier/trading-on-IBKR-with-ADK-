# Run with `database/capacity/check.sh --test`. Prints PASS or the failing cases.
include "capacity";

$budget[0] as $b
| ($b | {full_visibility: true, server, unallocated_client_connections: 1, ingress_and_dispatch_paused: true,
         roles: ({} + .roles + {database_migrator: 1} | map_values({connection_limit: ., superuser: false, connections: 0}))}) as $live
| def live($release; $phase): inventory_errors($live; $release; $phase);
  def sources: source_errors($domains[0]; [$scanner, $reader, $momentum_api]; $litellm);
  [ {name: "current budget keeps the operator and migration slots", got: ($b | budget_errors + sources), want: []},
    {name: "summary", got: ($b | summary),
     want: {application_peak: 10, ordinary_slots: 12, operator: 1, migration: 1, provider: 1, migration_mode: "offline"}},
    (("litellm", "market_scanner_writer", "momentum_results_reader") as $role
     | {name: "larger \($role) pool exhausts the server", got: ($b | .roles[$role] += 1 | budget_errors),
        want: ["Global connection budget exceeds ordinary server capacity"]}),
    {name: "rolling release", got: ($b | .release_mode = "rolling" | budget_errors),
     want: ["Overlapping release mode is outside the reviewed capacity"]},
    {name: "negative admission", got: ($b | .consumers.scanner.admission = -1 | budget_errors),
     want: ["Connection limits must be nonnegative integers"]},
    {name: "consumer above its roles", got: ($b | .consumers.scanner.active = 3 | budget_errors),
     want: ["Consumer exceeds its role allocation"]},
    {name: "uncounted role", got: ($b | .roles.extra = 1 | .server.max_connections = 16 | budget_errors),
     want: ["Every runtime role must be counted exactly once"]},
    {name: "clean runtime inventory", got: ($b | live([]; "runtime")), want: []},
    (({key: "hidden", value: {full_visibility: false}, want: "Provider/client visibility is incomplete; rollout blocked"},
     {key: "provider", value: {unallocated_client_connections: 2}, want: "Unallocated provider/client connections consume headroom"},
     {key: "server", value: {server: ($b.server | .superuser_reserved_connections = 4)}, want: "Observed server settings differ from the reviewed budget"})
    | . as $m | {name: "inventory \($m.key)", got: ($b | inventory_errors($live + $m.value; []; "runtime")), want: [$m.want]}),
    (({key: "superuser", value: {superuser: true}}, {key: "role_limit", value: {connection_limit: 12}})
    | . as $m | {name: "inventory \($m.key)", got: ($b | inventory_errors($live | .roles.litellm += $m.value; []; "runtime")),
                 want: ["Runtime role protection differs from the reviewed budget"]}),
    {name: "release before drain", got: ($b | inventory_errors($live | .roles.litellm.connections = 2; ["litellm"]; "runtime")),
     want: ["Release target has not drained"]},
    {name: "sessions above a lowered limit", got: ($b | inventory_errors($live | .roles.litellm.connections = 3; []; "runtime")),
     want: ["Existing sessions exceed the new limit; drain first"]},
    {name: "release after drain", got: ($b | live(["litellm"]; "runtime")), want: []},
    {name: "release without pause", got: ($b | inventory_errors($live | .ingress_and_dispatch_paused = false; ["litellm"]; "runtime")),
     want: ["Pause ingress and dispatch before the release gate"]},
    {name: "migration with live application", got: ($b | inventory_errors($live | .roles.litellm.connections = 1; []; "migration")),
     want: ["All application connections must drain before migration"]},
    (($live | .roles.database_migrator.connections = 1) as $migrating
     | {name: "migration phase", got: ($b | inventory_errors($migrating; []; "migration")), want: []},
      {name: "runtime with migrator", got: ($b | inventory_errors($migrating; []; "runtime")),
       want: ["Migration connections must drain before runtime"]},
      {name: "migration without pause", got: ($b | inventory_errors($migrating | .ingress_and_dispatch_paused = false; []; "migration")),
       want: ["Pause every application before offline migration"]}),
    {name: "scanner pool growth", got: ($b | source_errors($domains[0]; [$scanner | sub("default=1"; "default=2") | sub("le=1"; "le=2"), $reader, $momentum_api]; $litellm)),
     want: ["Configured pool exceeds the shared allocation"]},
    {name: "missing pool setting", got: ($b | source_errors($domains[0]; ["", $reader, $momentum_api]; $litellm)),
     want: ["Configured pool exceeds the shared allocation"]},
    {name: "domain role drift", got: ($b | source_errors($domains[0] | .momentum.runtime_roles.momentum_results_writer = 3; [$scanner, $reader, $momentum_api]; $litellm)),
     want: ["Domain role limits differ from the capacity budget"]},
    {name: "litellm pool growth", got: ($b | source_errors($domains[0]; [$scanner, $reader, $momentum_api]; $litellm | sub("database_connection_pool_limit(?<s>\\s*)=\\s*1"; "database_connection_pool_limit = 2"))),
     want: ["LiteLLM pools differ from the shared allocation"]} ] as $cases
| [$cases[] | select(.got != .want)]
| if length == 0 then "PASS: \($cases | length) capacity cases" else "\(tojson)\n" | halt_error(1) end
