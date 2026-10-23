# Shared PostgreSQL capacity: 15 total connections

The observed server has 15 connections, 3 superuser-reserved slots and no other
reserved slots. Ordinary consumers therefore share **12** slots. The executable
contract is `database/connection-budget.json`; validate with
`python3 database/capacity.py`. The application allocation includes idle pools and
admission attempts, not just active SQL statements.

| Consumer / login | Maximum | Normal use |
| --- | ---: | --- |
| Scanner writer | 3 | One admitted HTTP/job workflow: result + session; one admission probe |
| Scanner reader | 1 | One reader pool |
| Momentum results writer | 2 | One admitted workflow/result/memory connection; one admission probe |
| Momentum sessions writer | 1 | One admitted workflow's ADK sessions |
| Momentum reader | 1 | One reader pool |
| LiteLLM | 2 | Admin and inference gateway, one connection each |
| database_migrator | 1 | Serial domain migration |
| Operator | 1 | Inventory/diagnostic connection |
| PostgreSQL superuser reserve | 3 | Unavailable to application logins |
| **Total** | **15** | No additional ordinary provider client fits |

The Scanner HTTP and scheduled entry points share one database advisory lock.
Momentum has its own lock. Admission holds the existing result connection outside
any transaction; result writes reuse it. A competing normal execution receives a
bounded busy outcome before model calls. Cancellation/crash closes that connection
and releases the session lock. Runtime-role limits are an additional hard boundary
across old/new revisions and transient Cloud Run excess instances. A database
connection refusal is a capacity fault, not a successful admission rejection.

## Rollout gate

This is an implementation target, **not a claim that live role limits or secrets
have already changed**. The earlier reader-only inventory could not see all server
sessions. It is insufficient to establish provider headroom. A full-visibility
operator must run `database/operations/capacity_snapshot.sql`, save only its JSON
row, and run `python3 database/capacity.py --inventory snapshot.json`. This rejects
hidden statistics, different server settings, elevated/wrong-limit runtime roles,
or any unallocated ordinary client. If provider clients consume ordinary slots,
stop: revise the allocation; do not consume the operator slot or increase the tier.

Use a maintenance replacement, not an overlapping rolling release:

1. Pause scheduled/manual dispatch and ingress to the affected service. Let active
   work finish, then stop its old revisions and connection pools. Keep the operator
   connection available. Do not terminate in-flight writes to force this gate.
2. Apply the reviewed role bootstrap and the one-connection LiteLLM secret/config
   changes only after their old pools drain. Existing sessions are not evicted by
   lowering role limits. Apply the memory migration before the new Momentum worker.
3. Export a fresh full-visibility snapshot. Set `ingress_and_dispatch_paused=true`
   only after verifying the external controls; this is an explicit operator
   attestation, not a database-discoverable fact. Invoke the gate with every target
   login, for example `--release-role litellm`. Any remaining target connections
   reject replacement. Keep dispatch paused until the gate and rollout finish.
4. Run migrations serially. LiteLLM's own Prisma migration uses its existing role
   allocation **while both LiteLLM services are stopped**; never overlap it with
   their two live pools. Domain Liquibase uses the separate migrator allowance.
5. Start one replacement per service, verify pools/roles and runtime behavior,
   then restore ingress/dispatch. Re-run the inventory gate. Roll back application
   images without removing retained memory or rewriting Liquibase history.

Readers and LiteLLM retain bounded pools and need the drain gate during replacement.
Unexpected old/new overlap can produce bounded database failures because role caps
remain global. This protects headroom; it does not promise uninterrupted service
under unsupported overlap or arbitrary launch floods. No paid tier, pooler or queue
is added. Deployment is not automated by this read-only validator.

PostgreSQL [reserved-slot rules](https://www.postgresql.org/docs/18/runtime-config-connection.html),
[role limits](https://www.postgresql.org/docs/18/sql-createrole.html) and
[session advisory locks](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS)
are the underlying boundaries. Cloud Run instance/task settings alone do not bound
independent job executions or deployment overlap.
