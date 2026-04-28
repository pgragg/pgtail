"""End-to-end integration tests: real Postgres in Docker via testcontainers.

Skipped automatically when Docker is unavailable.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Iterator

import pytest

_EXTERNAL_DSN = os.environ.get("PGTAIL_TEST_DSN")

if not _EXTERNAL_DSN:
    # Skip the entire module if testcontainers/docker isn't usable.
    testcontainers = pytest.importorskip("testcontainers.postgres")
    docker = pytest.importorskip("docker")

    try:
        _client = docker.from_env()  # type: ignore[attr-defined]
        _client.ping()
    except Exception:  # pragma: no cover
        pytest.skip("docker daemon not available", allow_module_level=True)

import psycopg  # noqa: E402

from pgtail.events import ChangeEvent  # noqa: E402
from pgtail.options import Settings  # noqa: E402
from pgtail.replication import stream_changes  # noqa: E402

pytestmark = pytest.mark.integration


def _wait_ready(dsn: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"postgres did not become ready at {dsn}: {last_err!r}")


def _provision_test_schema(dsn: str) -> None:
    """Idempotently set up the schema needed by tests against an external DSN."""
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_setting('wal_level')")
        wal_level = cur.fetchone()[0]
        if wal_level != "logical":
            raise RuntimeError(
                f"PGTAIL_TEST_DSN points at a server with wal_level={wal_level!r}; need 'logical'"
            )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS users "
            "(id serial PRIMARY KEY, email text NOT NULL, name text)"
        )
        cur.execute("ALTER TABLE users REPLICA IDENTITY FULL")
        cur.execute("TRUNCATE users RESTART IDENTITY")
        # Drop any leftover slots / publications from prior aborted runs.
        cur.execute("SELECT slot_name FROM pg_replication_slots WHERE slot_name LIKE 'pgtail_%%'")
        for (name,) in cur.fetchall():
            with contextlib.suppress(Exception):
                cur.execute("SELECT pg_drop_replication_slot(%s)", (name,))
        cur.execute("SELECT pubname FROM pg_publication WHERE pubname LIKE 'pgtail_pub_%%'")
        for (name,) in cur.fetchall():
            cur.execute(f"DROP PUBLICATION IF EXISTS {name}")


@pytest.fixture(scope="module")
def pg_container() -> Iterator[str]:
    """Yield a DSN to a Postgres with wal_level=logical.

    If ``PGTAIL_TEST_DSN`` is set in the environment, we use that and only
    provision the schema. Otherwise we spin up a Postgres container via
    testcontainers.
    """
    if _EXTERNAL_DSN:
        _wait_ready(_EXTERNAL_DSN)
        _provision_test_schema(_EXTERNAL_DSN)
        yield _EXTERNAL_DSN
        return

    from testcontainers.core.waiting_utils import wait_for_logs
    from testcontainers.postgres import PostgresContainer

    img = "postgres:16-alpine"
    container = PostgresContainer(
        img, username="postgres", password="postgres", dbname="test"
    ).with_command(
        "postgres -c wal_level=logical -c max_replication_slots=10 -c max_wal_senders=10"
    )
    with container as pg:
        # Wait for the "ready to accept connections" log line — more reliable than
        # blind polling, especially on the second startup after the wal_level reload.
        wait_for_logs(pg, "database system is ready to accept connections", timeout=60)

        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        dsn = f"postgresql://postgres:postgres@{host}:{port}/test"

        _wait_ready(dsn, timeout=30)

        with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("ALTER ROLE postgres WITH REPLICATION")
            cur.execute(
                "CREATE TABLE users (id serial PRIMARY KEY, email text NOT NULL, name text)"
            )
            cur.execute("ALTER TABLE users REPLICA IDENTITY FULL")

        yield dsn


def _settings(dsn: str, **overrides: object) -> Settings:
    base = dict(
        dsn=dsn,
        schemas=("public",),
        tables=(),
        exclude=(),
        ops=("insert", "update", "delete", "truncate"),
        json_output=False,
        color=False,
        show_time=False,
        verbose=False,
        max_width=200,
        redact=(),
        slot=None,
        log_file=None,
        expand_all=False,
        collapse_threshold=10_000,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_stream_captures_insert_update_delete(pg_container: str) -> None:
    dsn = pg_container
    s = _settings(dsn, tables=("users",))

    events: list[ChangeEvent] = []
    stop_after = 3
    error: list[Exception] = []

    def runner() -> None:
        try:
            for ev in stream_changes(s):
                events.append(ev)
                if len(events) >= stop_after:
                    break
        except Exception as e:  # pragma: no cover
            error.append(e)

    t = threading.Thread(target=runner, daemon=True)
    t.start()

    # Give the publication/slot setup a moment.
    time.sleep(2.0)

    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, name) VALUES (%s, %s) RETURNING id",
            ("a@b.com", "Ana"),
        )
        new_id = cur.fetchone()[0]
        cur.execute("UPDATE users SET email = %s WHERE id = %s", ("ana@b.com", new_id))
        cur.execute("DELETE FROM users WHERE id = %s", (new_id,))

    t.join(timeout=15)
    assert not error, f"stream raised: {error[0]!r}"
    assert len(events) >= 3, f"expected 3+ events, got {len(events)}: {events}"

    ops = [e.op for e in events[:3]]
    assert ops == ["insert", "update", "delete"]

    insert_ev = events[0]
    assert insert_ev.qualified == "public.users"
    assert insert_ev.new_row is not None
    assert insert_ev.new_row["email"] == "a@b.com"

    update_ev = events[1]
    assert update_ev.changed_fields == ("email",)
    assert update_ev.old_row is not None
    assert update_ev.old_row["email"] == "a@b.com"
    assert update_ev.new_row is not None
    assert update_ev.new_row["email"] == "ana@b.com"

    delete_ev = events[2]
    assert delete_ev.old_row is not None
    assert delete_ev.old_row["email"] == "ana@b.com"
