# Tasks: Domain databases and durable sessions

Completed and verified locally and remotely on 2026-10-21 under the user's
implementation and remote-apply instructions. [Specification](../../specs/database-per-application.md),
[plan](plan.md), [local evidence](local-evidence.md),
[remote audit](evidence.md).

The implementation paths below replace the originally proposed shell scripts and
`rebuild_domains.py`; the acceptance scope is unchanged. Remote Momentum already
had the final layout and was preserved, rather than reset over ongoing work.
No copy, compatibility layer, destructive automatic retry, or remote CI success
is implied by these checkboxes.

| Task | Completed deliverable and verification |
| --- | --- |
| [x] T01 Inventory | Aiven host matched to deployed credentials; exact consumers, legacy objects, histories and role limits inventoried. See release map and remote evidence. |
| [x] T02 Disposable harness | `database/scripts/local_domains.py` uses labeled loopback fixtures; `database/tests/test_harness.py` rejects remote Docker, foreign containers and wrong domains. |
| [x] T03 Scanner chains | `db.changelog-scanner.yaml`, `market-scanner/001-analysis.sql`, `common/001-adk-sessions.sql`; real fresh application, pinned SDK schema checks and no-op second update. |
| [x] T04 Momentum chains | `db.changelog-momentum.yaml` includes current unchanged `momentum-unified/sessions.sql` and `results.sql`; twelve implemented result tables, independent history. |
| [x] T05 Guarded operations | `local_domains.py` local reset; `scanner_cutover.py` explicit inspect/bootstrap/migrate/publish/cleanup, private credentials, host/consumer/object checks, no CASCADE or automatic reset. Eleven local guard tests pass; the original live cleanup evidence is retained. |
| [x] T06 Grants/budgets | Domain bootstrap plus separate administrator/migrator Scanner SQL; defaultdb retirement preserves operators. Local non-superuser SQL test, runtime permission tests and live CONNECT matrix passed. Writer=4, reader=2, bounded pools and serialized jobs. |
| [x] T07 Scanner adapter | `src/app/services/session_database.py`: PostgreSQL schema preflight, no DDL/memory fallback, bounded pool and close. Unit/integration and image restart tests passed. |
| [x] T08 Scheduled sessions | `src/app/jobs/daily_scan.py` uses durable backend; explicit duplicate-ID rejection; error/partial persistence tests; live failed and successful executions leave sessions. |
| [x] T09 Interactive sessions | `src/app/application.py` registers the same backend and lifecycle; local authenticated restart test and live HTTP creation/read with direct DB confirmation passed. |
| [x] T10 Analyses/correlation | Typed report-v3 storage in `_analysis`; local transaction/deletion tests; live execution marker joins session to successful report, assets and horizons. |
| [x] T11 Reader | `_analysis` only, unchanged report-v3/auth/pagination; local integration, mypy and image smoke passed; live latest/detail exactly equal stored JSON, sessions denied. |
| [x] T12 Momentum adapter | Authoritative `momentum-cloud-run` runtime selects `_sessions`/`_analysis`; 133 unit and seven current persistence tests in rehearsal, plus remote actual SDK reopen round trip. |
| [x] T13 Scanner releases | Tested immutable images, numeric DB secret versions 2, final schemas. Reviewed saved Terraform plans applied; final plans return 0/no changes. |
| [x] T14 Momentum release | Exact deployed job/secret mapping in `release-map.md`; already on dedicated DB. Existing deployment specification and migration history verified unchanged; no redundant Terraform mutation. |
| [x] T15 Rehearsal | `database/scripts/rehearse_domains.py --momentum-root ../momentum-cloud-run`: 559 tests, actual adapters, separate processes and real PostgreSQL/Liquibase, no skipped required integration. Separate image tests exercise actual container restart. |
| [x] T16 CI/runbook | `.github/workflows/domain-database.yml` invokes the reproducible rehearsal; explicit domain Compose entry points; `operations.md` gives actual remote commands/targets. Local workflow command passed; GitHub CI was not invoked. |
| [x] T17 Legacy removal | Runtime migration commands use explicit domain roots. The historical shared master and bootstrap are retained only for Momentum migration-history regression tests. All production defaults select `_analysis`; local rehearsal passed with historical SQL used only as fixtures. |
| [x] T18 Remote apply | Fresh Scanner DB/migrations, secret versions, images and consumers deployed; exact old Scanner tables/history removed; defaultdb table inventory empty; cross-domain/defaultdb access denied. |
| [x] T19 Live completion | `market-scanner-daily-v7ll2` succeeded: 12 events, 25 assets, 191 horizons, correlated report; session/report readable after worker exit. Momentum round trip passed, scheduler enabled, LiteLLM and Momentum deployment specs preserved. |

## Reproducible checks

```sh
python3 database/scripts/rehearse_domains.py --momentum-root ../momentum-cloud-run
python3 database/scripts/test_scanner_bootstrap.py
uv run --project apps/backend/market-scanner-adk --frozen pytest -q database/tests/test_scanner_cutover.py
python3 scripts/scanner_image_smoke.py local/scanner-domain:amd64
uv run --project apps/backend/market-scanner-api --frozen python apps/backend/market-scanner-api/scripts/container_smoke.py local/scanner-reader-domain:amd64
git diff --check
```

The [runbook](operations.md) separates inspection,
fresh creation, migrations, publication, Terraform rollout, live verification and
cleanup. Its one-time bootstrap/migrate/cleanup actions must not be blindly replayed
against the completed deployment. The final audit maps DB-01 through DB-12 to
actual evidence and records the first provider timeout separately from the successful run.
