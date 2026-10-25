# SmartCloud Platform — MySQL Edition

SmartCloud is a BTech CSE OS + DBMS project for a **simulated** cloud/server resource pool. It combines a Flask controller, worker agents, approved demo jobs, OS scheduling algorithms, Banker's safety checking, logical resource allocation, and an advanced dashboard UI.

## What is included

- **MySQL 8+ persistence:** workers, jobs, logical servers, allocations and resource-usage events are stored in MySQL. There is no SQLite runtime or fallback.
- **Advanced dashboard:** KPI cards, server capacity gauges, worker health/telemetry, searchable job queue, CPU scheduling Gantt chart, Banker safe-state output, allocation ledger and resource-event table.
- **Job management:** create and track the approved `system_info`, `cpu_demo`, and `disk_info` job types.
- **OS algorithms:** FCFS, non-preemptive Priority (lower number is higher priority), Round Robin, process timing metrics, and Banker’s algorithm.
- **Resource safety:** synchronized MySQL transactions with row locks, capacity validation, duplicate active-owner protection, allocation/release audit events, and three seeded logical servers.
- **Worker agent:** reports machine metrics and only runs the three allowlisted demo tasks. It never accepts arbitrary shell commands.
- **Graphical VS Code workflow:** launch configurations are included under `.vscode/launch.json` for the controller and worker.

The logical server pool remains an academic simulation, not a production cloud, hypervisor, or auto-provisioner. The controller and allowlisted worker can run as a real LAN client–server application; see `PHASE2_AUDIT_AND_RUNBOOK.md` for the full audit and PC 1/PC 2 setup.

## Real client–server workflow

- Set `FLASK_HOST=0.0.0.0` in the server `.env` to listen on the LAN. Do not configure public port forwarding.
- Set a distinct `CLIENT_TOKENS_JSON` mapping on the controller, for example `{"pc2":"a-long-random-token"}`. The client token is separate from dashboard admin and worker tokens.
- Start the controller on PC 1, then start the worker agent on PC 1 with `CONTROLLER_URL=http://127.0.0.1:5000`. One worker processes one job at a time.
- On PC 2, set `SMARTCLOUD_SERVER_URL=http://<PC1-private-IP>:5000` and `SMARTCLOUD_CLIENT_TOKEN`, then run `python client.py`.
- The client API currently accepts the bounded allowlisted `text_analysis` task. Use the returned job ID with `python client.py status <JOB_ID>` and `python client.py result <JOB_ID>`.
- MySQL remains on PC 1. PC 2 talks only to Flask; do not expose the MySQL port.

LAN HTTP traffic is unencrypted. Use a trusted private network and do not expose this development server to the public internet.

## Setup with graphical tools only

### 1. Open the project

Extract the ZIP, open Visual Studio Code, and choose **File → Open Folder…**. Select the extracted `SmartCloudPlatform_Phase2_MySQL` folder. Install the Microsoft **Python** extension and **Python Debugger** extension if VS Code prompts for them.

### 2. Prepare MySQL in MySQL Workbench

1. Start the local MySQL Server service using your system's graphical Services panel or MySQL Installer.
2. Open MySQL Workbench and connect to your local server.
3. Open `schema_mysql.sql` from the project in Workbench, then use the lightning-bolt **Execute** control to run the script. Confirm the `smartcloud` schema and its six tables appear in the SCHEMAS navigator.
4. In VS Code Explorer, make a copy of `.env.example` named `.env`.
5. Edit `.env` and set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`. The defaults expect a local MySQL server, database `smartcloud`, and user `root`; replace the example password with the password for your own MySQL account.
6. Replace both placeholder tokens with different, long random values. The admin token is entered in the dashboard; the worker token is used by the worker agent.

The application also creates missing Phase 2 tables and seeds the three logical servers when it first connects. Running the schema script first is recommended so the database is visible in Workbench and its target name is explicit.

### 3. Select a Python environment in VS Code

1. Open the Command Palette from **View → Command Palette…**.
2. Select **Python: Create Environment**, choose **Venv**, and select a Python interpreter.
3. When VS Code asks for a dependency file, select the project's `requirements.txt`. Let the Python extension create the environment and install the listed packages through its GUI workflow.
4. Confirm the created environment is selected in the bottom status bar.

### 4. Run the controller with Run and Debug

1. Open the **Run and Debug** view in VS Code.
2. Choose **SmartCloud Controller (MySQL)** from the configuration list.
3. Press the green **Start Debugging** button. The app does not need a terminal window; VS Code's internal Debug Console shows logs.
4. Open `http://127.0.0.1:5000` in your browser. Enter the `ADMIN_TOKEN` from `.env` in the access panel and choose **Connect dashboard**.
5. Confirm that the MySQL badge shows **Connected** and the three logical simulation servers appear. Use **Refresh data** after operations.

If MySQL is stopped or the credentials are incorrect, the dashboard reports the connection problem. Fix the MySQL service or `.env` values and retry; the application does not silently create or switch to a SQLite file.

### 5. Run a worker agent (optional)

To run the worker on the same computer, make a copy of `worker.env.example` as `worker/.env`, then set `CONTROLLER_URL`, `WORKER_SHARED_TOKEN` (same value as the controller), and a descriptive `WORKER_NAME`. In VS Code, select **SmartCloud Worker Agent** from **Run and Debug** and start it. For a second computer, copy the project and configure the worker's own `worker/.env`; use a controller URL reachable over a trusted network. Do not expose the Flask development server directly to the public internet.

## Dashboard guide

- **Overview:** counts, CPU capacity remaining, simulated server capacity bars and shortcuts.
- **Job queue:** submit an allowlisted worker task and search recent jobs by name, ID, worker or status.
- **Workers:** inspect heartbeat age, CPU load, available RAM, free disk and platform.
- **CPU scheduler lab:** run FCFS, Priority or Round Robin on process JSON and inspect Gantt segments plus waiting, turnaround and response times.
- **Banker’s safety check:** supply available, allocation and maximum vectors/matrices; inspect the Need matrix and safe sequence or unfinished processes.
- **Allocation ledger:** reserve logical CPU/RAM/storage or release an owner's active reservation. Updates use MySQL transactions and row locks.

## Database tables

`users`, `workers`, `servers`, `jobs`, `allocations`, and `resource_usage_logs`. The current dashboard uses token-based admin/worker protection; a user-account management interface is not part of this build.

## Troubleshooting

- **“MySQL is not ready”**: make sure the MySQL Server service is running, `schema_mysql.sql` ran successfully, and `.env` points to the right host/port/database/user/password.
- **HTTP 401**: check that the exact admin token from `.env` was pasted into the dashboard. Worker token and admin token are intentionally different.
- **No worker online**: the dashboard and logical server pool work without workers, but worker inventory stays empty until a worker agent starts and sends heartbeats.
- **Worker cannot connect**: confirm `CONTROLLER_URL` points to the controller's reachable address and the worker shared token matches. Devices on different networks need a trusted private route/VPN and suitable network rules.
- **Dependency/environment issue**: use the VS Code Python environment picker and create the environment from `requirements.txt` again if needed.

## Scope boundaries

Included: database persistence, CRUD-like job operations, resource allocation/release, locking/transactions, CPU scheduling, Banker’s algorithm, worker telemetry, and a dashboard that surfaces those Phase 2 modules.

Not included: AI/ML, Kubernetes, Docker infrastructure, public cloud provisioning, production authentication/TLS, or arbitrary remote command execution.
