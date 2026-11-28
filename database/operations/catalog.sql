-- Print the managed schemas' definitions and grants as one JSON line, never business
-- rows. verify.sh hashes it (jq -S -c | sha256) and compares the result with the
-- fingerprints recorded from Aiven in database/domains.json and current.json.
-- psql variable `current`: 'true' adds column grants and the _suggestions schema and
-- prints, on a second line, the Liquibase history read in the same snapshot.
\set ON_ERROR_STOP on
\set QUIET on
\if :{?current}
\else
\set current false
\endif
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL search_path = pg_catalog;
SELECT CASE WHEN :'current'::boolean THEN ARRAY['_analysis', '_sessions', '_suggestions']
            ELSE ARRAY['_analysis', '_sessions'] END AS schemas \gset
SELECT json_build_object(
  'schemas', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT nspname AS name, pg_get_userbyid(nspowner) AS owner,
      ARRAY(SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
        || ':' || a.privilege_type || ':' || a.is_grantable::text
        FROM aclexplode(COALESCE(nspacl,acldefault('n',nspowner))) a ORDER BY 1) AS grants
    FROM pg_namespace WHERE nspname=ANY(:'schemas') ORDER BY 1) q),
  'tables', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema,c.relname AS name,c.relkind::text AS kind,
      pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity AS row_security,
      c.relforcerowsecurity AS force_row_security,
      ARRAY(SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
        || ':' || a.privilege_type || ':' || a.is_grantable::text
        FROM aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a ORDER BY 1) AS grants
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname=ANY(:'schemas') AND c.relkind IN ('r','p','v','m','S','f') ORDER BY 1,2) q),
  'columns', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema,c.relname AS table,a.attname AS name,a.attnum AS position,
      format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS not_null,
      a.attidentity::text AS identity,a.attgenerated::text AS generated,
      pg_get_expr(d.adbin,d.adrelid) AS default_value
    FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
    WHERE n.nspname=ANY(:'schemas') AND c.relkind IN ('r','p','v','m','f')
      AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,a.attnum) q),
  'constraints', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema,c.relname AS table,k.conname AS name,
      pg_get_constraintdef(k.oid) AS definition,k.convalidated AS validated
    FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname=ANY(:'schemas') ORDER BY 1,2,3) q),
  'indexes', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT schemaname AS schema,tablename AS table,indexname AS name,indexdef AS definition
    FROM pg_indexes WHERE schemaname=ANY(:'schemas') ORDER BY 1,2,3) q),
  'functions', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema,p.proname AS name,pg_get_functiondef(p.oid) AS definition
    FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname=ANY(:'schemas') ORDER BY 1,2,3) q),
  'triggers', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema,c.relname AS table,t.tgname AS name,
      pg_get_triggerdef(t.oid) AS definition
    FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname=ANY(:'schemas') AND NOT t.tgisinternal ORDER BY 1,2,3) q),
  'default_privileges', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema,pg_get_userbyid(d.defaclrole) AS owner,
      d.defaclobjtype::text AS type,d.defaclacl::text AS grants
    FROM pg_default_acl d JOIN pg_namespace n ON n.oid=d.defaclnamespace
    WHERE n.nspname=ANY(:'schemas') ORDER BY 1,2,3) q)
) AS catalog \gset
\if :current
SELECT json_build_object('column_grants', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT n.nspname AS schema, c.relname AS table, a.attname AS column,
      CASE WHEN acl.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(acl.grantee) END AS grantee,
      acl.privilege_type AS privilege, acl.is_grantable AS grantable
    FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    CROSS JOIN LATERAL aclexplode(a.attacl) acl
    WHERE n.nspname=ANY(:'schemas') AND c.relkind IN ('r','p','v','m','f')
      AND a.attnum>0 AND NOT a.attisdropped
    ORDER BY 1,2,3,4,5,6) q),
  'history', (SELECT COALESCE(json_agg(q), '[]') FROM (
    SELECT id, author, filename, md5sum, exectype
    FROM liquibase.databasechangelog ORDER BY filename, id, author) q)
) AS extra \gset
SELECT (:'catalog'::jsonb || jsonb_build_object('column_grants', :'extra'::jsonb -> 'column_grants'))::text;
SELECT (:'extra'::jsonb -> 'history')::text;
\else
SELECT :'catalog' AS catalog;
\endif
COMMIT;
