# SmartCloud Platform — Phase 2 status

**Project:** Smart Cloud and Server Resource Management  
**Team:** OSDBMS-V-2026-T162  
**Database runtime:** MySQL 8+  
**Interface:** Flask API with responsive dashboard

## Phase 2 modules

- The controller uses MySQL persistence for workers, jobs, logical servers, allocations and resource-usage logs. `schema_mysql.sql` contains the relational schema and the runtime adapter is implemented in `cloud/db.py`.
- CPU scheduling supports FCFS, non-preemptive Priority (lower numeric priority wins) and Round Robin. The algorithms report execution segments and waiting, turnaround and response times.
- Banker’s safety checking calculates the Need matrix and returns a safe sequence or unfinished process indexes.
- Resource allocation validates CPU, RAM and disk requests, selects a fitting logical server, updates capacity counters and records audit events in the same MySQL transaction. Row locks coordinate shared resource updates.
- Job submission, worker heartbeats, dispatch and result updates are implemented through Flask endpoints. The worker runs only the fixed `system_info`, `cpu_demo`, and `disk_info` tasks.
- The dashboard presents summary metrics, simulated-server capacity, job search/status, worker telemetry, a visual scheduling Gantt chart, Banker results and an allocation/event ledger.

## Verification status

The project includes algorithm unit tests and opt-in MySQL integration tests in `tests/`. MySQL-dependent checks require a configured MySQL Server and a dedicated test schema; they must not be described as passed until run against that server. The supplied code package has been inspected and syntax-checked, but this environment did not have a configured MySQL Server to verify live database connectivity.

## Boundaries and limitations

The three server entries are logical simulation servers, not physical cloud hosts. Worker-reported machine telemetry is separate from logical resource reservations. The system is an academic prototype and does not include production authentication, TLS termination, cloud provisioning, container isolation, Kubernetes or AI/ML optimization.
