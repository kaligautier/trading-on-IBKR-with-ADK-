-- Run with full pg_stat_activity visibility, in a read-only transaction.
-- A low-privilege reader's hidden rows are not evidence of free connections.
BEGIN READ ONLY;
SELECT jsonb_build_object(
  'full_visibility', (SELECT rolsuper OR pg_has_role(current_user, 'pg_read_all_stats', 'MEMBER')
                     FROM pg_roles WHERE rolname=current_user),
  'server', jsonb_build_object(
    'max_connections', current_setting('max_connections')::int,
    'superuser_reserved_connections', current_setting('superuser_reserved_connections')::int,
    'reserved_connections', current_setting('reserved_connections')::int),
  'roles', (SELECT jsonb_object_agg(r.rolname, jsonb_build_object(
       'connection_limit', r.rolconnlimit, 'superuser', r.rolsuper,
       'connections', (SELECT count(*) FROM pg_stat_activity a
                       WHERE a.usename=r.rolname AND a.backend_type='client backend')))
    FROM pg_roles r WHERE r.rolname IN (
      'market_scanner_writer', 'market_scanner_reader', 'momentum_sessions_writer',
      'momentum_results_writer', 'momentum_results_reader', 'litellm', 'database_migrator')),
  'unallocated_client_connections', (SELECT count(*) FROM pg_stat_activity
    WHERE backend_type='client backend' AND pid<>pg_backend_pid()
      AND usename NOT IN ('market_scanner_writer', 'market_scanner_reader',
        'momentum_sessions_writer', 'momentum_results_writer',
        'momentum_results_reader', 'litellm', 'database_migrator')),
  'ingress_and_dispatch_paused', false
);
COMMIT;
