# Phase 2 implementation notes — MySQL edition

## Runtime architecture

- **Controller and dashboard:** Flask app, browser UI in `templates/index.html` plus `static/style.css` and `static/app.js`.
- **Database:** MySQL 8+ through `mysql-connector-python`. SQLite is not used. `.env` controls the connection using `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`.
- **Tables:** `users`, `workers`, `servers`, `jobs`, `allocations`, `resource_usage_logs`.
- **OS simulator:** FCFS, non-preemptive Priority, Round Robin, process metrics and Banker safety analysis.
- **Resource pool:** three seeded logical servers. Capacity counters, active reservations, and audit events are committed transactionally; row locks protect shared server capacity while allocation/release runs.
- **Worker:** reports machine telemetry and runs only the fixed `system_info`, `cpu_demo`, and `disk_info` jobs.

## Current feature map

| Feature | Implementation location | Status |
|---|---|---|
| MySQL schema and connection adapter | `schema_mysql.sql`, `cloud/db.py` | Implemented; requires a reachable MySQL Server to verify live connectivity |
| Worker registration and heartbeats | `cloud/db.py`, `app.py`, `worker/agent.py` | Implemented |
| Job submission, retrieval and status updates | `app.py`, `cloud/db.py` | Implemented |
| FCFS, Priority, Round Robin | `cloud/os_engine.py` | Implemented |
| Waiting, turnaround and response metrics | `cloud/os_engine.py` | Implemented |
| Banker safe-state and sequence | `cloud/os_engine.py` | Implemented |
| Logical server capacity and allocation ledger | `cloud/resource_store.py` | Implemented with MySQL transactions and row locking |
| Capacity usage events | `cloud/resource_store.py` | Implemented |
| Advanced dashboard | `templates/index.html`, `static/style.css`, `static/app.js` | Implemented; data views require valid MySQL credentials and admin token |
| GUI launch configurations | `.vscode/launch.json` | Included |

## Important details

- Worker physical telemetry and the three logical Phase 2 servers are separate demonstrations; the logical server pool does not actually provision hardware or guarantee enforcement of real CPU/RAM limits.
- Admin/worker requests use bearer tokens. The dashboard keeps the admin token in the page rather than persisting it to local storage.
- Before claiming a successful end-to-end run, start MySQL, execute `schema_mysql.sql` in MySQL Workbench, configure `.env`, run the controller using VS Code Run and Debug, and verify rows in Workbench.
- MySQL integration testing cannot be claimed from a code-only inspection without access to a configured MySQL Server. The scheduling and Banker algorithms can be exercised independently from the dashboard.
