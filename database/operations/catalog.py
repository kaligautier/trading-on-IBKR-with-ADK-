"""Read managed PostgreSQL definitions and grants without reading business rows."""

import hashlib
import json

SCHEMAS = ["_analysis", "_sessions"]

QUERIES = {
    "schemas": """
        SELECT nspname AS name, pg_get_userbyid(nspowner) AS owner,
          ARRAY(SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
            || ':' || a.privilege_type || ':' || a.is_grantable::text
            FROM aclexplode(COALESCE(nspacl,acldefault('n',nspowner))) a ORDER BY 1) AS grants
        FROM pg_namespace WHERE nspname=ANY($1) ORDER BY 1
    """,
    "tables": """
        SELECT n.nspname AS schema,c.relname AS name,c.relkind::text AS kind,
          pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity AS row_security,
          c.relforcerowsecurity AS force_row_security,
          ARRAY(SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
            || ':' || a.privilege_type || ':' || a.is_grantable::text
            FROM aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a ORDER BY 1) AS grants
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=ANY($1) AND c.relkind IN ('r','p','v','m','S','f') ORDER BY 1,2
    """,
    "columns": """
        SELECT n.nspname AS schema,c.relname AS table,a.attname AS name,a.attnum AS position,
          format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS not_null,
          a.attidentity::text AS identity,a.attgenerated::text AS generated,
          pg_get_expr(d.adbin,d.adrelid) AS default_value
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname=ANY($1) AND c.relkind IN ('r','p','v','m','f')
          AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,a.attnum
    """,
    "constraints": """
        SELECT n.nspname AS schema,c.relname AS table,k.conname AS name,
          pg_get_constraintdef(k.oid) AS definition,k.convalidated AS validated
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=ANY($1) ORDER BY 1,2,3
    """,
    "indexes": """
        SELECT schemaname AS schema,tablename AS table,indexname AS name,indexdef AS definition
        FROM pg_indexes WHERE schemaname=ANY($1) ORDER BY 1,2,3
    """,
    "functions": """
        SELECT n.nspname AS schema,p.proname AS name,pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname=ANY($1) ORDER BY 1,2,3
    """,
    "triggers": """
        SELECT n.nspname AS schema,c.relname AS table,t.tgname AS name,
          pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=ANY($1) AND NOT t.tgisinternal ORDER BY 1,2,3
    """,
    "default_privileges": """
        SELECT n.nspname AS schema,pg_get_userbyid(d.defaclrole) AS owner,
          d.defaclobjtype::text AS type,d.defaclacl::text AS grants
        FROM pg_default_acl d JOIN pg_namespace n ON n.oid=d.defaclnamespace
        WHERE n.nspname=ANY($1) ORDER BY 1,2,3
    """,
}


async def snapshot(connection):
    """Keep every query in one consistent read-only snapshot."""
    async with connection.transaction(isolation="repeatable_read", readonly=True):
        await connection.execute("SET LOCAL search_path = pg_catalog")
        return {
            name: [dict(row) for row in await connection.fetch(query, SCHEMAS)]
            for name, query in QUERIES.items()
        }


def fingerprint(definitions):
    encoded = json.dumps(definitions, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_baseline(definitions, expected):
    if fingerprint(definitions) != expected:
        raise ValueError(
            "Schema differs from the verified Aiven baseline; adoption refused"
        )
