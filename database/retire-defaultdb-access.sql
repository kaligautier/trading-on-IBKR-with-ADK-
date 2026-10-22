-- Run as administrator only after the domain cutover and legacy table cleanup.
-- Preserve existing login access for service operators and unrelated consumers.
BEGIN;
DO $$
DECLARE principal RECORD;
DECLARE domains TEXT[] := ARRAY['market_scanner_writer', 'market_scanner_reader',
                               'momentum_sessions_writer', 'momentum_results_writer'];
BEGIN
    IF current_database() <> 'defaultdb' OR EXISTS (
        SELECT FROM pg_namespace WHERE nspname IN ('market_scanner', 'momentum', '_sessions', '_analysis')
    ) THEN
        RAISE EXCEPTION 'Legacy application schemas must be removed first';
    END IF;
    FOR principal IN SELECT rolname FROM pg_roles
        WHERE rolcanlogin AND NOT rolname = ANY(domains)
          AND has_database_privilege(oid, current_database(), 'CONNECT')
    LOOP
        EXECUTE format('GRANT CONNECT ON DATABASE defaultdb TO %I', principal.rolname);
    END LOOP;
    REVOKE CONNECT ON DATABASE defaultdb FROM PUBLIC;
    REVOKE ALL ON DATABASE defaultdb FROM market_scanner_writer, market_scanner_reader,
        momentum_sessions_writer, momentum_results_writer;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = ANY(domains)
               AND has_database_privilege(oid, current_database(), 'CONNECT')) THEN
        RAISE EXCEPTION 'Domain roles still inherit access to defaultdb';
    END IF;
END $$;
COMMIT;
