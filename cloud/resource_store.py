"""MySQL-backed logical resource pool with row-lock transaction safety."""
import json
from typing import Any

from cloud.db import connect
from cloud.util import now

_RESOURCE_KEYS = {"cpu_cores", "ram_mb", "disk_mb"}


def _validated_request(request: Any) -> dict[str, int]:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    unknown = set(request) - _RESOURCE_KEYS
    if unknown:
        raise ValueError("unknown resource keys: " + ", ".join(sorted(unknown)))
    result: dict[str, int] = {}
    for key in _RESOURCE_KEYS:
        value = request.get(key, 0)
        if isinstance(value, bool):
            raise ValueError(f"{key} must be a non-negative integer")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a non-negative integer")
        if str(value).strip() not in (str(number), f"+{number}") or number < 0:
            raise ValueError(f"{key} must be a non-negative integer")
        result[key] = number
    if not any(result.values()):
        raise ValueError("at least one resource must be requested")
    return result


def _server_dict(row: dict[str, Any]) -> dict[str, Any]:
    server = dict(row)
    server["cpu_available"] = server["cpu_total"] - server["cpu_used"]
    server["ram_available_mb"] = server["ram_total_mb"] - server["ram_used_mb"]
    server["disk_available_mb"] = server["disk_total_mb"] - server["disk_used_mb"]
    return server


def snapshot() -> dict[str, Any]:
    with connect() as connection:
        servers = [_server_dict(row) for row in connection.execute(
            "SELECT * FROM servers ORDER BY server_id"
        ).fetchall()]
        allocations = [dict(row) for row in connection.execute(
            "SELECT * FROM allocations WHERE status='ACTIVE' ORDER BY allocated_at, allocation_id"
        ).fetchall()]
        logs = [dict(row) for row in connection.execute(
            """SELECT log_id,server_id,owner,event_type,cpu_cores,ram_mb,disk_mb,details,created_at
               FROM resource_usage_logs ORDER BY log_id DESC LIMIT 30"""
        ).fetchall()]
    for row in logs:
        details = row.pop("details", None)
        if isinstance(details, (dict, list)):
            row["details"] = details
        else:
            try:
                row["details"] = json.loads(details) if details else None
            except (TypeError, ValueError):
                row["details"] = None
    return {"servers": servers, "allocations": allocations, "recent_logs": logs}


def allocate(owner: str, request: Any) -> dict[str, Any]:
    owner = str(owner or "").strip()
    if not owner or len(owner) > 120:
        raise ValueError("owner must contain 1 to 120 characters")
    requested = _validated_request(request)

    with connect() as connection:
        connection.start_transaction()
        # Lock the shared capacity rows first. This serializes allocators and also
        # ensures a second request re-checks whether the owner already has a reservation.
        servers = connection.execute(
            "SELECT * FROM servers WHERE status='ONLINE' ORDER BY server_id FOR UPDATE"
        ).fetchall()
        active = connection.execute(
            "SELECT allocation_id FROM allocations WHERE owner=%s AND status='ACTIVE' FOR UPDATE",
            (owner,),
        ).fetchone()
        if active:
            return {"allocated": False, "reason": "owner already has an active allocation"}

        eligible = []
        for server in servers:
            cpu_free = server["cpu_total"] - server["cpu_used"]
            ram_free = server["ram_total_mb"] - server["ram_used_mb"]
            disk_free = server["disk_total_mb"] - server["disk_used_mb"]
            if cpu_free < requested["cpu_cores"] or ram_free < requested["ram_mb"] or disk_free < requested["disk_mb"]:
                continue
            load_score = (
                (server["cpu_used"] + requested["cpu_cores"]) / max(server["cpu_total"], 1)
                + (server["ram_used_mb"] + requested["ram_mb"]) / max(server["ram_total_mb"], 1)
                + (server["disk_used_mb"] + requested["disk_mb"]) / max(server["disk_total_mb"], 1)
            )
            eligible.append((load_score, server))
        if not eligible:
            return {"allocated": False, "reason": "insufficient resources"}

        _, chosen = min(eligible, key=lambda item: (item[0], item[1]["server_id"]))
        timestamp = now()
        connection.execute(
            """UPDATE servers SET cpu_used=cpu_used+%s, ram_used_mb=ram_used_mb+%s,
               disk_used_mb=disk_used_mb+%s WHERE server_id=%s""",
            (requested["cpu_cores"], requested["ram_mb"], requested["disk_mb"], chosen["server_id"]),
        )
        allocation_cursor = connection.execute(
            """INSERT INTO allocations(owner,server_id,cpu_cores,ram_mb,disk_mb,status,allocated_at)
               VALUES(%s,%s,%s,%s,%s,'ACTIVE',%s)""",
            (owner, chosen["server_id"], requested["cpu_cores"], requested["ram_mb"], requested["disk_mb"], timestamp),
        )
        connection.execute(
            """INSERT INTO resource_usage_logs
               (server_id,owner,event_type,cpu_cores,ram_mb,disk_mb,details,created_at)
               VALUES(%s,%s,'ALLOCATED',%s,%s,%s,%s,%s)""",
            (chosen["server_id"], owner, requested["cpu_cores"], requested["ram_mb"], requested["disk_mb"],
             json.dumps({"allocation_id": allocation_cursor.lastrowid}), timestamp),
        )
        updated = connection.execute(
            "SELECT * FROM servers WHERE server_id=%s", (chosen["server_id"],)
        ).fetchone()
        return {
            "allocated": True,
            "owner": owner,
            "allocation_id": allocation_cursor.lastrowid,
            "server": _server_dict(updated),
            "allocation": requested,
        }


def release(owner: str) -> dict[str, Any]:
    owner = str(owner or "").strip()
    if not owner:
        raise ValueError("owner is required")
    with connect() as connection:
        connection.start_transaction()
        # Read the likely server without a lock, then lock resources before allocations.
        # This matches allocate()'s lock order and reduces deadlock risk under concurrency.
        candidate = connection.execute(
            """SELECT allocation_id, server_id FROM allocations WHERE owner=%s AND status='ACTIVE'
               ORDER BY allocation_id LIMIT 1""",
            (owner,),
        ).fetchone()
        if not candidate:
            return {"released": False, "reason": "no active allocation for owner"}
        connection.execute(
            "SELECT server_id FROM servers WHERE server_id=%s FOR UPDATE", (candidate["server_id"],)
        ).fetchone()
        allocation = connection.execute(
            """SELECT * FROM allocations WHERE allocation_id=%s AND owner=%s AND status='ACTIVE' FOR UPDATE""",
            (candidate["allocation_id"], owner),
        ).fetchone()
        if not allocation:
            return {"released": False, "reason": "no active allocation for owner"}
        timestamp = now()
        restored = connection.execute(
            """UPDATE servers SET cpu_used=cpu_used-%s, ram_used_mb=ram_used_mb-%s,
               disk_used_mb=disk_used_mb-%s
               WHERE server_id=%s AND cpu_used >= %s AND ram_used_mb >= %s AND disk_used_mb >= %s""",
            (allocation["cpu_cores"], allocation["ram_mb"], allocation["disk_mb"], allocation["server_id"],
             allocation["cpu_cores"], allocation["ram_mb"], allocation["disk_mb"]),
        )
        if restored.rowcount != 1:
            raise RuntimeError("Resource counters are inconsistent; release was rolled back")
        connection.execute(
            "UPDATE allocations SET status='RELEASED',released_at=%s WHERE allocation_id=%s AND status='ACTIVE'",
            (timestamp, allocation["allocation_id"]),
        )
        connection.execute(
            """INSERT INTO resource_usage_logs
               (server_id,owner,event_type,cpu_cores,ram_mb,disk_mb,details,created_at)
               VALUES(%s,%s,'RELEASED',%s,%s,%s,%s,%s)""",
            (allocation["server_id"], owner, allocation["cpu_cores"], allocation["ram_mb"], allocation["disk_mb"],
             json.dumps({"allocation_id": allocation["allocation_id"]}), timestamp),
        )
        return {
            "released": True,
            "owner": owner,
            "released_resources": {
                "cpu_cores": allocation["cpu_cores"],
                "ram_mb": allocation["ram_mb"],
                "disk_mb": allocation["disk_mb"],
            },
        }
