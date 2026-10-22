"""Exercise administrator SQL as a non-superuser in an owned local container."""

import subprocess
import time
from pathlib import Path

import local_domains

ROOT = Path(__file__).resolve().parents[1]
NAME = "deepcopy-scanner-bootstrap-test"


def docker(*args, data=None):
    result = subprocess.run(
        ["docker", *args], input=data, text=True, capture_output=True, check=True
    )
    return result.stdout


def sql(user, database, statement):
    return docker(
        "exec",
        "-i",
        NAME,
        "psql",
        "-XAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        user,
        "-d",
        database,
        data=statement,
    )


def main():
    local_domains.inspect_container()
    if NAME in docker("ps", "-a", "--format", "{{.Names}}").splitlines():
        raise RuntimeError("Refusing to replace an existing test container")
    docker(
        "run",
        "--rm",
        "--detach",
        "--name",
        NAME,
        "--label",
        "org.deepcopy.scanner-bootstrap-test=true",
        "--env",
        "POSTGRES_PASSWORD=local-test-only",
        local_domains.IMAGE,
    )
    try:
        for _ in range(60):
            if (
                subprocess.run(
                    ["docker", "exec", NAME, "pg_isready", "-U", "postgres"],
                    capture_output=True,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Local PostgreSQL did not become ready")
        sql(
            "postgres",
            "postgres",
            "CREATE ROLE scanner_admin LOGIN CREATEDB CREATEROLE NOINHERIT; CREATE ROLE database_migrator LOGIN NOINHERIT;",
        )
        sql(
            "scanner_admin",
            "postgres",
            "CREATE ROLE market_scanner_writer LOGIN; CREATE ROLE market_scanner_reader LOGIN; CREATE DATABASE market_scanner;",
        )
        bootstrap = (ROOT / "scanner-bootstrap.sql").read_text()
        try:
            sql("scanner_admin", "postgres", bootstrap)
        except subprocess.CalledProcessError as error:
            assert "requires the market_scanner database" in error.stderr
        else:
            raise AssertionError("Wrong database accepted")
        sql("scanner_admin", "market_scanner", bootstrap)
        assert (
            sql(
                "postgres",
                "market_scanner",
                "SELECT rolconnlimit FROM pg_roles WHERE rolname='market_scanner_writer';",
            ).strip()
            == "4"
        )
        sql(
            "database_migrator",
            "market_scanner",
            (ROOT / "scanner-migrator-bootstrap.sql").read_text(),
        )
        assert (
            sql(
                "postgres",
                "market_scanner",
                "SELECT has_database_privilege('market_scanner_writer','market_scanner','CREATE'), has_database_privilege('market_scanner_reader','market_scanner','TEMP');",
            ).strip()
            == "f|f"
        )
        assert (
            sql(
                "postgres",
                "market_scanner",
                "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='liquibase';",
            ).strip()
            == "database_migrator"
        )
        sql(
            "postgres",
            "postgres",
            "CREATE DATABASE defaultdb OWNER scanner_admin; CREATE ROLE momentum_sessions_writer LOGIN; CREATE ROLE momentum_results_writer LOGIN;",
        )
        sql(
            "scanner_admin",
            "defaultdb",
            (ROOT / "retire-defaultdb-access.sql").read_text(),
        )
        assert (
            sql(
                "postgres",
                "defaultdb",
                "SELECT has_database_privilege('market_scanner_writer','defaultdb','CONNECT'), has_database_privilege('momentum_sessions_writer','defaultdb','CONNECT'), has_database_privilege('database_migrator','defaultdb','CONNECT');",
            ).strip()
            == "f|f|t"
        )
        print(
            "PASS: non-superuser bootstrap, wrong-target guard, runtime DDL denial, separate migration owner, isolated domain CONNECT and preserved operator access."
        )
    finally:
        docker("stop", NAME)


if __name__ == "__main__":
    main()
