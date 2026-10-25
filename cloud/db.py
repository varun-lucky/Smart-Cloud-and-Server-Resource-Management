"""MySQL persistence layer for the SmartCloud educational prototype.

The application intentionally has no SQLite fallback. Configure MySQL in .env and
create the target schema before running the controller.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError

from cloud.util import now


def _connection_config() -> dict[str, Any]:
    """Read MySQL settings at call time so dotenv/test configuration is respected."""
    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
        timeout = int(os.getenv("MYSQL_CONNECT_TIMEOUT_SECONDS", "5"))
    except ValueError as exc:
        raise ValueError("MYSQL_PORT and MYSQL_CONNECT_TIMEOUT_SECONDS must be integers") from exc
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": port,
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "smartcloud"),
        "connection_timeout": timeout,
        "autocommit": False,
    }


def _json_value(value: Any, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _normalise(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


class QueryResult:
    """Small, materialised query result so every MySQL cursor is promptly closed."""

    def __init__(self, cursor: Any) -> None:
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.lastrowid
        self._rows = [
            {key: _normalise(value) for key, value in row.items()}
            for row in (cursor.fetchall() if cursor.with_rows else [])
        ]
        self._offset = 0
        cursor.close()

    def fetchone(self) -> dict[str, Any] | None:
        if self._offset >= len(self._rows):
            return None
        row = self._rows[self._offset]
        self._offset += 1
        return row

    def fetchall(self) -> list[dict[str, Any]]:
        rows = self._rows[self._offset :]
        self._offset = len(self._rows)
        return rows


class MySQLConnection:
    """Context-managed MySQL connection with a compact execute API."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def __enter__(self) -> "MySQLConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        finally:
            self._raw.close()
        return False

    def execute(self, sql: str, params: tuple | list = ()) -> QueryResult:
        cursor = self._raw.cursor(dictionary=True, buffered=True)
        try:
            cursor.execute(sql, tuple(params))
            return QueryResult(cursor)
        except Exception:
            cursor.close()
            raise

    def executemany(self, sql: str, seq: list[tuple] | tuple[tuple, ...]) -> QueryResult:
        cursor = self._raw.cursor(dictionary=True, buffered=True)
        try:
            cursor.executemany(sql, seq)
            return QueryResult(cursor)
        except Exception:
            cursor.close()
            raise

    def start_transaction(self) -> None:
        self._raw.start_transaction()

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()


def connect() -> MySQLConnection:
    """Open a real MySQL connection; never silently switch database engines."""
    try:
        raw = mysql.connector.connect(**_connection_config())
        # TIMESTAMP values are stored and displayed consistently in UTC.
        cursor = raw.cursor()
        cursor.execute("SET time_zone = '+00:00'")
        cursor.close()
        return MySQLConnection(raw)
    except MySQLError as exc:
        database = os.getenv("MYSQL_DATABASE", "smartcloud")
        raise RuntimeError(
            f"Could not connect to MySQL database '{database}'. Check that MySQL Server is running, "
            "MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD are correct, and the database exists. "
            f"MySQL connector detail: {exc}"
        ) from exc


def init_db() -> None:
    """Create the Phase 2 tables if missing and seed the logical server pool once."""
    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(80) NOT NULL UNIQUE,
            email VARCHAR(190) NULL UNIQUE,
            role VARCHAR(24) NOT NULL DEFAULT 'USER',
            created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            CONSTRAINT chk_users_role CHECK (role IN ('USER','ADMIN'))
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS workers (
            worker_id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            capabilities_json JSON NOT NULL,
            metrics_json JSON NOT NULL,
            last_seen TIMESTAMP(6) NOT NULL,
            created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            INDEX idx_workers_last_seen (last_seen)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS servers (
            server_id VARCHAR(64) PRIMARY KEY,
            server_name VARCHAR(120) NOT NULL,
            cpu_total INT NOT NULL,
            ram_total_mb BIGINT NOT NULL,
            disk_total_mb BIGINT NOT NULL,
            cpu_used INT NOT NULL DEFAULT 0,
            ram_used_mb BIGINT NOT NULL DEFAULT 0,
            disk_used_mb BIGINT NOT NULL DEFAULT 0,
            status VARCHAR(24) NOT NULL DEFAULT 'ONLINE',
            created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            CONSTRAINT chk_servers_cpu CHECK (cpu_total >= 0 AND cpu_used >= 0 AND cpu_used <= cpu_total),
            CONSTRAINT chk_servers_ram CHECK (ram_total_mb >= 0 AND ram_used_mb >= 0 AND ram_used_mb <= ram_total_mb),
            CONSTRAINT chk_servers_disk CHECK (disk_total_mb >= 0 AND disk_used_mb >= 0 AND disk_used_mb <= disk_total_mb)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS jobs (
            job_id VARCHAR(32) PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            job_type VARCHAR(40) NOT NULL,
            cpu_cores INT NOT NULL,
            ram_mb BIGINT NOT NULL,
            disk_mb BIGINT NOT NULL,
            status VARCHAR(24) NOT NULL,
            worker_id VARCHAR(64) NULL,
            os_pid BIGINT NULL,
            result_json JSON NULL,
            error_text TEXT NULL,
            client_id VARCHAR(80) NULL,
            input_json JSON NULL,
            created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            INDEX idx_jobs_status (status),
            INDEX idx_jobs_worker (worker_id),
            CONSTRAINT fk_jobs_worker FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS allocations (
            allocation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            owner VARCHAR(120) NOT NULL,
            job_id VARCHAR(32) NULL,
            server_id VARCHAR(64) NOT NULL,
            cpu_cores INT NOT NULL,
            ram_mb BIGINT NOT NULL,
            disk_mb BIGINT NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'ACTIVE',
            allocated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            released_at TIMESTAMP(6) NULL,
            INDEX idx_allocations_status (status),
            INDEX idx_allocations_owner (owner, status),
            CONSTRAINT fk_allocations_job FOREIGN KEY (job_id) REFERENCES jobs(job_id),
            CONSTRAINT fk_allocations_server FOREIGN KEY (server_id) REFERENCES servers(server_id),
            CONSTRAINT chk_allocations_resources CHECK (cpu_cores >= 0 AND ram_mb >= 0 AND disk_mb >= 0)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS resource_usage_logs (
            log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            server_id VARCHAR(64) NOT NULL,
            job_id VARCHAR(32) NULL,
            owner VARCHAR(120) NULL,
            event_type VARCHAR(40) NOT NULL,
            cpu_cores INT NOT NULL DEFAULT 0,
            ram_mb BIGINT NOT NULL DEFAULT 0,
            disk_mb BIGINT NOT NULL DEFAULT 0,
            details JSON NULL,
            created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            INDEX idx_usage_server_time (server_id, created_at),
            CONSTRAINT fk_usage_server FOREIGN KEY (server_id) REFERENCES servers(server_id),
            CONSTRAINT fk_usage_job FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        ) ENGINE=InnoDB""",
    ]
    with connect() as connection:
        for statement in statements:
            connection.execute(statement)
        # Additive migration for databases created by the original ZIP.
        columns = {row["COLUMN_NAME"] for row in connection.execute(
            "SELECT COLUMN_NAME FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='jobs'"
        ).fetchall()}
        if "client_id" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN client_id VARCHAR(80) NULL")
        if "input_json" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN input_json JSON NULL")
        seeded = connection.execute("SELECT COUNT(*) AS total FROM servers").fetchone()
        if not seeded or int(seeded["total"]) == 0:
            timestamp = now()
            connection.executemany(
                """INSERT INTO servers
                   (server_id, server_name, cpu_total, ram_total_mb, disk_total_mb,
                    cpu_used, ram_used_mb, disk_used_mb, status, created_at)
                   VALUES (%s,%s,%s,%s,%s,0,0,0,'ONLINE',%s)""",
                [
                    ("sim-server-01", "Simulation Server 01", 8, 8192, 512000, timestamp),
                    ("sim-server-02", "Simulation Server 02", 4, 4096, 256000, timestamp),
                    ("sim-server-03", "Simulation Server 03", 2, 2048, 128000, timestamp),
                ],
            )


def upsert_worker(wid: str, name: str, caps: Any, metrics: Any) -> None:
    timestamp = now()
    with connect() as connection:
        connection.execute(
            """INSERT INTO workers
               (worker_id, name, capabilities_json, metrics_json, last_seen, created_at)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE name=VALUES(name), capabilities_json=VALUES(capabilities_json),
               metrics_json=VALUES(metrics_json), last_seen=VALUES(last_seen)""",
            (wid, name, json.dumps(caps), json.dumps(metrics), timestamp, timestamp),
        )


def heartbeat_worker(wid: str, metrics: Any, caps: Any) -> None:
    timestamp = now()
    with connect() as connection:
        connection.execute(
            """INSERT INTO workers
               (worker_id, name, capabilities_json, metrics_json, last_seen, created_at)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE metrics_json=VALUES(metrics_json),
               capabilities_json=VALUES(capabilities_json), last_seen=VALUES(last_seen)""",
            (wid, wid, json.dumps(caps), json.dumps(metrics), timestamp, timestamp),
        )


def list_workers(timeout: int = 45) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM workers ORDER BY name").fetchall()
    current = datetime.utcnow()
    output = []
    for row in rows:
        try:
            last_seen = datetime.fromisoformat(str(row["last_seen"]))
            if last_seen.tzinfo is not None:
                last_seen = last_seen.replace(tzinfo=None)
            online = (current - last_seen).total_seconds() <= timeout
        except (TypeError, ValueError):
            online = False
        output.append({
            "worker_id": row["worker_id"],
            "name": row["name"],
            "online": online,
            "capabilities": _json_value(row.get("capabilities_json"), {}),
            "metrics": _json_value(row.get("metrics_json"), {}),
            "last_seen": row["last_seen"],
        })
    return output


def create_job(name: str, kind: str, cpu: int, ram: int, disk: int, wid: str | None = None,
               client_id: str | None = None, input_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    job_id = "JOB-" + uuid.uuid4().hex[:12].upper()
    status = "ASSIGNED" if wid else "QUEUED"
    timestamp = now()
    with connect() as connection:
        connection.execute(
            """INSERT INTO jobs
               (job_id,name,job_type,cpu_cores,ram_mb,disk_mb,status,worker_id,os_pid,result_json,error_text,client_id,input_json,created_at,updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,NULL,%s,%s,%s,%s)""",
            (job_id, name, kind, cpu, ram, disk, status, wid, client_id,
             json.dumps(input_data) if input_data is not None else None, timestamp, timestamp),
        )
    return get_job(job_id)


def _unpack_job(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    job = dict(row)
    job["result"] = _json_value(job.pop("result_json", None))
    job["input"] = _json_value(job.pop("input_json", None), {})
    return job


def list_jobs() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT 200").fetchall()
    return [_unpack_job(row) for row in rows]


def get_job(job_id: str, client_id: str | None = None) -> dict[str, Any] | None:
    with connect() as connection:
        if client_id is None:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
        else:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=%s AND client_id=%s", (job_id, client_id)).fetchone()
    return _unpack_job(row)


def assign_next_job(wid: str) -> dict[str, Any] | None:
    """Lock and dispatch an assigned job, or claim the oldest queued job."""
    with connect() as connection:
        connection.start_transaction()
        row = connection.execute(
            """SELECT * FROM jobs WHERE status='ASSIGNED' AND worker_id=%s
               ORDER BY created_at, job_id LIMIT 1 FOR UPDATE""",
            (wid,),
        ).fetchone()
        if row:
            job_id = row["job_id"]
            connection.execute(
                "UPDATE jobs SET status='DISPATCHED', updated_at=%s WHERE job_id=%s AND status='ASSIGNED'",
                (now(), job_id),
            )
            updated = connection.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
            return _unpack_job(updated)

        row = connection.execute(
            """SELECT * FROM jobs WHERE status='QUEUED' AND worker_id IS NULL
               ORDER BY created_at, job_id LIMIT 1 FOR UPDATE"""
        ).fetchone()
        if not row:
            return None
        job_id = row["job_id"]
        cursor = connection.execute(
            """UPDATE jobs SET status='DISPATCHED', worker_id=%s, updated_at=%s
               WHERE job_id=%s AND status='QUEUED' AND worker_id IS NULL""",
            (wid, now(), job_id),
        )
        if cursor.rowcount != 1:
            return None
        updated = connection.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
        return _unpack_job(updated)


def update_job_result(job_id: str, wid: str, data: dict[str, Any]) -> bool:
    result = json.dumps(data.get("result")) if data.get("result") is not None else None
    with connect() as connection:
        cursor = connection.execute(
            """UPDATE jobs SET status=%s, os_pid=COALESCE(%s,os_pid),
               result_json=COALESCE(%s,result_json), error_text=COALESCE(%s,error_text), updated_at=%s
               WHERE job_id=%s AND worker_id=%s AND status IN ('ASSIGNED','DISPATCHED','RUNNING')""",
            (data["status"], data.get("os_pid"), result, data.get("error"), now(), job_id, wid),
        )
        return cursor.rowcount == 1
