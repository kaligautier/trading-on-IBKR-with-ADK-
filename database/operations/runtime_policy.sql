-- Fail unless every runtime login of this domain keeps its isolated access policy: an
-- identical schema is not enough if a runtime login could own or create objects.
-- psql variable `roles`: the domain's runtime_roles from database/domains.json, as JSON.
\set ON_ERROR_STOP on
\set QUIET on
BEGIN READ ONLY;
SELECT set_config('deepcopy.runtime_roles', :'roles', true);
DO $$
DECLARE
    expected record;
    state record;
BEGIN
    FOR expected IN
        SELECT key AS role, value::int AS limit_
        FROM jsonb_each_text(current_setting('deepcopy.runtime_roles')::jsonb)
    LOOP
        SELECT r.rolconnlimit = expected.limit_ AND r.rolcanlogin
          AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls
                   OR r.rolreplication OR r.rolinherit)
          AND NOT EXISTS (SELECT FROM pg_auth_members WHERE member = r.oid)
          AND has_database_privilege(r.oid, current_database(), 'CONNECT')
          AND NOT has_database_privilege(r.oid, current_database(), 'CREATE,TEMP')
          AND NOT EXISTS (SELECT FROM pg_database d WHERE d.datallowconn AND NOT d.datistemplate
                          AND d.datname <> current_database()
                          AND has_database_privilege(r.oid, d.oid, 'CONNECT'))
          AND NOT has_schema_privilege(r.oid, 'public', 'CREATE') AS isolated
        INTO state FROM pg_roles r WHERE r.rolname = expected.role;
        IF NOT coalesce(state.isolated, false) THEN
            RAISE EXCEPTION 'Runtime role % differs from the isolated Aiven access policy', expected.role;
        END IF;
    END LOOP;
END $$;
COMMIT;
