# Phase 2 audit and LAN runbook

## Audit of the supplied ZIP

The ZIP contains no Phase 1 report or presentation PDFs. This audit uses the source files in the ZIP only; the missing PDFs may affect whether the original academic scope matches the code.

Implementation-map categories: **completed and verified** — OS algorithm unit tests and new isolated client/task tests; **implemented but not verified** — MySQL persistence, worker registration/heartbeats, DB-backed resource transactions, and the updated API against a live DB; **partially implemented** — job dispatch, real task processing, host telemetry, and application resource controls; **missing** — HTTPS, centralized rate limiting/concurrency enforcement, process memory caps, stale-job recovery, and cross-PC verification; **broken or requiring correction** — original LAN bind default, lack of a client identity boundary, and archive packaging of populated `.env` files (corrected in this delivery); **deferred to Phase 3** — distributed scheduling, autoscaling, discovery, high availability, predictive resource allocation, and production deployment.

| Area | Status and evidence |
|---|---|
| Flask controller and dashboard | Implemented in `app.py`, `templates/`, and `static/`. The dashboard requires admin auth and MySQL-backed routes. |
| MySQL persistence | Implemented in `cloud/db.py` and `schema_mysql.sql`; real DB connectivity was not verified here. The supplied archive also contained populated `.env` files, which were excluded from the revised ZIP. |
| Worker network protocol | Implemented in `app.py` and `worker/agent.py`: registration, heartbeat, queue claim, status and result reporting. A worker can run on a different PC, but the original instructions did not provide a separate client job API. |
| Safe task execution | Existing worker uses fixed task names and invokes a fixed Python module, not client-provided commands. The preexisting `system_info`, `cpu_demo`, and `disk_info` tasks do real bounded work. |
| Client workflow | Added token-authenticated `POST /api/client/jobs`, status, and result routes plus `client.py`. The new `text_analysis` task is allowlisted and accepts bounded text. Client job reads are scoped to the client identity resolved from its token. |
| Job state and scheduling | MySQL job states include queue/assignment/dispatch/running/completed/failed flows. Worker queue claiming is oldest-first. The CPU scheduling APIs are algorithm demonstrations; Round Robin does not preempt actual worker processes. |
| Resource monitoring | Worker telemetry collects host CPU, RAM, and disk metrics in `worker/metrics.py`. Dashboard logical servers in `cloud/resource_store.py` are simulated capacity, not real host limits. |
| Resource enforcement | Input bytes, queue length, and task timeout have conservative configurable defaults. RAM reservation is an estimate; the Python subprocess has no OS-enforced memory cap. A single worker agent processes one task at a time. Rate limiting and strict concurrent-worker enforcement are not implemented. |
| Banker’s algorithm | Implemented in `cloud/os_engine.py` and exposed as an admin API. It checks the supplied abstract allocation model only; it does not control host processes. |
| Authentication | Admin and worker bearer tokens existed. Added distinct client token mapping via `CLIENT_TOKENS_JSON`. Use long unique secrets. HTTP on a LAN does not encrypt credentials or job data. |
| Fault handling | Worker task timeout and task error reporting exist. Generic server exceptions are logged and returned without stack traces; database initialization responses no longer include connector details. Stale `RUNNING` jobs are not automatically recovered after a worker crash. |
| Phase 3 | Multi-server distributed scheduling, autoscaling, discovery, high availability, prediction, production deployment and advanced analytics remain deferred. |

## Files changed

- `app.py`: LAN bind default, request body bound, generic DB error response, client submission/status/result API.
- `cloud/db.py`: additive columns for client ownership and task input; persists input JSON and scopes client reads.
- `cloud/client_security.py`: maps distinct client tokens to stable client IDs.
- `worker/agent.py` and `worker/tasks.py`: passes bounded JSON input to the allowlisted text-analysis task.
- `client.py`: minimal terminal client for submission, status and result retrieval.
- `schema_mysql.sql`, `.env.example`, `tests/test_client_api.py`: schema, configuration template and client workflow tests.

## Defaults and limits

The `.env.example` defaults bind Flask to `0.0.0.0:5000`, allow 65,536 request bytes, 32,768 UTF-8 task input bytes, and 10 active queued/dispatched jobs. `worker.env.example` sets a 30-second worker task timeout and one task at a time per worker process. The client workflow reserves an estimated 1 CPU core and 128 MB RAM per job when choosing a worker. These estimates are scheduling metadata, not operating-system CPU or memory enforcement. The sequential loop is the practical one-job-at-a-time limit when only one worker is configured.

The server PC’s actual hardware could not be read in this environment: Windows denied CIM and Service Control Manager access. No CPU/RAM/disk capacity or MySQL service state is claimed here.

## PC 1: configure and start the server

1. Extract the revised ZIP, open its folder in VS Code, and install Python from the project `requirements.txt` into a virtual environment.
2. In MySQL Workbench, connect to the server PC’s MySQL instance and run `schema_mysql.sql`. The configured account must be able to create and alter the project tables on first start. Keep MySQL bound to localhost; PC 2 does not need its port.
3. Copy `.env.example` to `.env`. Set the actual MySQL credentials. Replace `ADMIN_TOKEN`, `WORKER_SHARED_TOKEN`, and the value in `CLIENT_TOKENS_JSON` with three distinct, long random values. Keep `.env` private.
4. In VS Code, use the existing **SmartCloud Controller (MySQL)** launch profile or run `python app.py` from the project folder. Debug mode is disabled. The app listens on all interfaces by default; this does not itself change Windows Firewall.
5. From PC 1, open `http://127.0.0.1:5000/health`. A response with status `ok` verifies the local Flask process only. Open `http://127.0.0.1:5000/` for the dashboard; enter the admin token.
6. If another PC cannot connect, check Windows network profile and firewall policy. If a firewall exception is required, create a narrow private-network inbound rule for TCP 5000 only after reviewing/approving that system change. Do not configure router forwarding or expose this service publicly.
7. Stop the server with **Ctrl+C** in its terminal/VS Code session. Restart it by launching the same profile again. App logs are in that session; no automatic Windows service is installed.

## Run a worker on PC 1

1. Copy `worker.env.example` to `worker/.env`.
2. Set `CONTROLLER_URL=http://127.0.0.1:5000`, the same `WORKER_SHARED_TOKEN` as PC 1’s `.env`, a worker name, and `MAX_JOB_RUNTIME_SECONDS` to the timeout you want. The worker reports its configured timeout in its capabilities; a different worker PC can have a different value.
3. Run `python -m worker.agent` from the project root. Keep this worker running to execute submitted tasks. It processes tasks sequentially and terminates a task that exceeds `MAX_JOB_RUNTIME_SECONDS`.

## PC 2: submit and retrieve a task

1. Install Python and the project requirements on PC 2, or copy only `client.py` and install `requests`.
2. Find PC 1’s private IPv4 address with Windows Settings → Network & Internet → the active connection → Hardware properties, or `ipconfig` in Command Prompt. Use that address, not `127.0.0.1`.
3. In PC 2’s PowerShell session, set `SMARTCLOUD_SERVER_URL` to `http://<PC1-private-IP>:5000` and `SMARTCLOUD_CLIENT_TOKEN` to the token mapped to `pc2` in PC 1’s `CLIENT_TOKENS_JSON`.
4. Run `python client.py`; enter text. The returned job ID is accepted by `python client.py status <JOB_ID>` and `python client.py result <JOB_ID>`. A queued job stays queued until an authorized worker polls the controller.
5. In MySQL Workbench on PC 1, verify the matching row in `smartcloud.jobs`, including status, client ID, and bounded result. PC 2 needs neither MySQL credentials nor access to TCP 3306.

Without HTTPS, bearer tokens and job data travel unencrypted on the LAN. Use only a trusted private network and rotate tokens if exposed. The API is a student project, not a production cloud service.

## Verification performed and outstanding

- Python compile check: passed.
- Unit suite: 11 passed; 7 MySQL integration tests skipped because a dedicated configured MySQL database was unavailable.
- New local tests: valid client token submits, missing token is rejected, one client cannot fetch another client’s job, and text statistics are correct.
- Not verified: MySQL migration on a live DB, worker subprocess over HTTP, Windows Firewall behavior, PC 2 LAN reachability, database row updates, oversized HTTP request end-to-end, timeout cleanup under a real worker, or physical host limits. Do not describe these as passed until run on the two PCs.

## Suggested safe sequence

1. Review Phase 1 PDFs (not in the supplied ZIP) against this audit.
2. Create a dedicated MySQL schema/account and update `.env` on PC 1.
3. Start MySQL and the controller; verify the health route locally.
4. Start one worker and submit a local text-analysis task with `client.py`.
5. Confirm job transitions/results in the dashboard and MySQL Workbench.
6. Test from PC 2 on the private LAN. Only then consider a narrow Windows Firewall rule if Windows blocks the connection.
7. Check oversized and invalid inputs, worker timeout, and ordinary task failure before a demonstration.

No Windows firewall, router, network, service, or permission settings were changed by this work.
