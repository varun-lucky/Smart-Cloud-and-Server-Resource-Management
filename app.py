import os
import threading
from dotenv import load_dotenv

# Load environment configuration before any module reads it.
load_dotenv()

from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
import psutil
from cloud.db import (
    init_db, upsert_worker, heartbeat_worker, list_workers, create_job,
    list_jobs, get_job, assign_next_job, update_job_result,
)
from cloud.scheduler import choose_worker
from cloud.security import admin_required, worker_required
from cloud.client_security import client_required
from cloud.util import now, as_int
from cloud.os_engine import fcfs, priority_nonpreemptive, round_robin, bankers_safety
from cloud import resource_store

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = as_int(os.getenv("MAX_REQUEST_BYTES", "65536"), 65536)
DB_READY = False
DB_INIT_LOCK = threading.Lock()
DB_FREE_ENDPOINTS = {"home", "health", "phase2_schedule_api", "phase2_banker_api"}
TIMEOUT = as_int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "45"), 45)


@app.before_request
def ensure_mysql_ready():
    """Initialise tables lazily, keeping the UI and pure OS algorithms usable if MySQL is down."""
    global DB_READY
    if request.endpoint in DB_FREE_ENDPOINTS or request.endpoint == "static" or DB_READY:
        return None
    try:
        with DB_INIT_LOCK:
            if not DB_READY:
                init_db()
                DB_READY = True
    except Exception as exc:
        app.logger.exception("MySQL initialisation failed")
        message = (
            "MySQL is not ready. Start MySQL Server, run schema_mysql.sql in MySQL Workbench, "
            "and verify MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE in .env."
        )
        if request.path.startswith("/api/"):
            return jsonify({"error": message, "database": "disconnected"}), 503
        return render_template("index.html", database_error=message), 503
    return None


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    app.logger.exception("Unhandled application error")
    message = "The request could not be completed. Check the server log and MySQL connection settings."
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), 500
    return render_template("index.html", database_error=message), 500


@app.get("/")
def home():
    return render_template("index.html", database_error=None)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "SmartCloud Controller", "time": now(), "database": "not checked" if not DB_READY else "connected"})


@app.get("/api/overview")
@admin_required
def overview_api():
    workers = list_workers(TIMEOUT)
    jobs = list_jobs()
    resources = resource_store.snapshot()
    online = sum(1 for worker in workers if worker["online"])
    queued = sum(1 for job in jobs if job["status"] == "QUEUED")
    running = sum(1 for job in jobs if job["status"] in ("DISPATCHED", "RUNNING"))
    completed = sum(1 for job in jobs if job["status"] == "COMPLETED")
    total_cpu = sum(server["cpu_total"] for server in resources["servers"])
    available_cpu = sum(server["cpu_available"] for server in resources["servers"])
    return jsonify({
        "workers": workers,
        "jobs": jobs,
        "resources": resources,
        "summary": {
            "online_workers": online,
            "total_workers": len(workers),
            "total_jobs": len(jobs),
            "queued_jobs": queued,
            "running_jobs": running,
            "completed_jobs": completed,
            "total_cpu": total_cpu,
            "available_cpu": available_cpu,
            "active_allocations": len(resources["allocations"]),
        },
        "generated_at": now(),
    })


@app.get("/api/server/status")
@admin_required
def server_status_api():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    return jsonify({
        "host": {"cpu_logical_cores": psutil.cpu_count(logical=True),
                 "cpu_percent": psutil.cpu_percent(interval=0.1),
                 "ram_total_mb": round(memory.total / 1048576),
                 "ram_available_mb": round(memory.available / 1048576),
                 "disk_total_mb": round(disk.total / 1048576),
                 "disk_free_mb": round(disk.free / 1048576)},
        "application_limits": {"max_request_bytes": app.config["MAX_CONTENT_LENGTH"],
                                "max_task_input_bytes": as_int(os.getenv("MAX_TASK_INPUT_BYTES", "32768"), 32768),
                                "max_queued_jobs": as_int(os.getenv("MAX_QUEUED_JOBS", "10"), 10),
                                "workers": [{"worker_id": w["worker_id"], "online": w["online"],
                                             "max_job_runtime_seconds": (w.get("capabilities") or {}).get("max_job_runtime_seconds"),
                                             "max_concurrent_jobs": (w.get("capabilities") or {}).get("max_concurrent_jobs", 1)}
                                            for w in list_workers(TIMEOUT)]},
        "memory_limit_enforcement": "estimated admission reservation; no OS process memory cap",
    })


@app.get("/api/workers")
@admin_required
def workers_api():
    return jsonify({"workers": list_workers(TIMEOUT)})


@app.get("/api/jobs")
@admin_required
def jobs_api():
    return jsonify({"jobs": list_jobs()})


@app.get("/api/jobs/<job_id>")
@admin_required
def job_api(job_id):
    job = get_job(job_id)
    return (jsonify({"job": job}), 200) if job else (jsonify({"error": "not found"}), 404)


@app.post("/api/client/jobs")
@client_required
def client_submit_job():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400
    kind = data.get("task_type")
    if kind != "text_analysis":
        return jsonify({"error": "task_type must be text_analysis"}), 400
    params = data.get("parameters")
    text = params.get("text") if isinstance(params, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "parameters.text must be a non-empty string"}), 400
    if len(text.encode("utf-8")) > as_int(os.getenv("MAX_TASK_INPUT_BYTES", "32768"), 32768):
        return jsonify({"error": "text input exceeds configured task limit"}), 413
    queued_limit = as_int(os.getenv("MAX_QUEUED_JOBS", "10"), 10)
    queued = sum(1 for job in list_jobs() if job.get("status") in ("QUEUED", "ASSIGNED", "DISPATCHED"))
    if queued >= max(1, queued_limit):
        return jsonify({"error": "server job queue is full"}), 503
    name = str(data.get("name", "Text analysis")).strip()[:120] or "Text analysis"
    workers = list_workers(TIMEOUT)
    worker = choose_worker(workers, 1, 128, 0)
    job = create_job(name, kind, 1, 128, 0, worker["worker_id"] if worker else None,
                     client_id=g.client_id, input_data={"text": text})
    return jsonify({"job_id": job["job_id"], "status": job["status"],
                    "message": "accepted" if worker else "queued: start an authorized worker"}), 202


@app.get("/api/client/jobs/<job_id>")
@client_required
def client_job_status(job_id):
    job = get_job(job_id, client_id=g.client_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify({"job_id": job["job_id"], "status": job["status"],
                    "created_at": job["created_at"], "updated_at": job["updated_at"],
                    "error": "task failed; contact the server administrator with this job ID"
                    if job["status"] == "FAILED" else None})


@app.get("/api/client/jobs/<job_id>/result")
@client_required
def client_job_result(job_id):
    job = get_job(job_id, client_id=g.client_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    if job["status"] != "COMPLETED":
        return jsonify({"error": "result is not ready", "status": job["status"]}), 409
    return jsonify({"job_id": job["job_id"], "result": job.get("result")})


@app.post("/api/jobs")
@admin_required
def submit_job():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    kind = str(data.get("job_type", "")).strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if len(name) > 120:
        return jsonify({"error": "name must be 120 characters or fewer"}), 400
    if kind not in ("system_info", "cpu_demo", "disk_info"):
        return jsonify({"error": "job_type must be system_info, cpu_demo or disk_info"}), 400
    cpu = as_int(data.get("cpu_cores", 1), 1)
    ram = as_int(data.get("ram_mb", 128), 128)
    disk = as_int(data.get("disk_mb", 100), 100)
    if not (1 <= cpu <= 64 and 32 <= ram <= 262144 and 0 <= disk <= 1048576):
        return jsonify({"error": "resource request outside demo limits"}), 400
    worker = choose_worker(list_workers(TIMEOUT), cpu, ram, disk)
    job = create_job(name, kind, cpu, ram, disk, worker["worker_id"] if worker else None)
    return jsonify({"job": job, "message": "assigned" if worker else "queued: no eligible worker"}), 201


@app.post("/api/worker/register")
@worker_required
def register():
    data = request.get_json(silent=True) or {}
    if not data.get("worker_id") or not data.get("name"):
        return jsonify({"error": "worker_id and name required"}), 400
    upsert_worker(str(data["worker_id"]), str(data["name"]), data.get("capabilities", {}), data.get("metrics", {}))
    return jsonify({"ok": True})


@app.post("/api/worker/heartbeat")
@worker_required
def heartbeat():
    data = request.get_json(silent=True) or {}
    if not data.get("worker_id"):
        return jsonify({"error": "worker_id required"}), 400
    heartbeat_worker(str(data["worker_id"]), data.get("metrics", {}), data.get("capabilities", {}))
    return jsonify({"ok": True, "time": now()})


@app.post("/api/worker/next-job")
@worker_required
def next_job():
    data = request.get_json(silent=True) or {}
    if not data.get("worker_id"):
        return jsonify({"error": "worker_id required"}), 400
    return jsonify({"job": assign_next_job(str(data["worker_id"]))})


@app.post("/api/worker/job-result")
@worker_required
def job_result():
    data = request.get_json(silent=True) or {}
    if not all(data.get(key) for key in ("job_id", "worker_id", "status")):
        return jsonify({"error": "job_id, worker_id and status required"}), 400
    if data["status"] not in ("RUNNING", "COMPLETED", "FAILED"):
        return jsonify({"error": "invalid status"}), 400
    updated = update_job_result(str(data["job_id"]), str(data["worker_id"]), data)
    if not updated:
        return jsonify({"error": "job not found, worker mismatch, or invalid state transition"}), 404
    return jsonify({"ok": True})


@app.post("/api/phase2/schedule")
@admin_required
def phase2_schedule_api():
    data = request.get_json(silent=True) or {}
    processes = data.get("processes", [])
    algorithm = str(data.get("algorithm", "fcfs")).lower()
    if not isinstance(processes, list) or not processes:
        return jsonify({"error": "processes must be a non-empty list"}), 400
    try:
        if algorithm == "fcfs":
            result = fcfs(processes)
        elif algorithm == "priority":
            result = priority_nonpreemptive(processes)
        elif algorithm == "round_robin":
            result = round_robin(processes, data.get("quantum", 2))
        else:
            return jsonify({"error": "algorithm must be fcfs, priority or round_robin"}), 400
        return jsonify({"algorithm": algorithm, "result": result})
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/phase2/banker")
@admin_required
def phase2_banker_api():
    data = request.get_json(silent=True) or {}
    try:
        result = bankers_safety(data["available"], data["allocation"], data["maximum"])
        return jsonify(result)
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/api/phase2/resources")
@admin_required
def phase2_resource_snapshot():
    return jsonify(resource_store.snapshot())


@app.post("/api/phase2/resources/allocate")
@admin_required
def phase2_allocate():
    data = request.get_json(silent=True) or {}
    if not data.get("owner") or not isinstance(data.get("request"), dict):
        return jsonify({"error": "owner and request object are required"}), 400
    try:
        result = resource_store.allocate(str(data["owner"]), data["request"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), (200 if result.get("allocated") else 409)


@app.post("/api/phase2/resources/release")
@admin_required
def phase2_release():
    data = request.get_json(silent=True) or {}
    if not data.get("owner"):
        return jsonify({"error": "owner is required"}), 400
    try:
        result = resource_store.release(str(data["owner"]))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), (200 if result.get("released") else 404)


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=as_int(os.getenv("FLASK_PORT", "5000"), 5000),
        debug=False,
    )
