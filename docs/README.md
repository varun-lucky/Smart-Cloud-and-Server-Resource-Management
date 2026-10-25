# Project Documentation

This folder holds the documentation and research material for **Smart Cloud and Server Resource Management**, a B.Tech CSE project that combines Operating Systems and DBMS concepts.

> **Status: work in progress.** Phase 1 (planning and design) is done. Phase 2 (working prototype) is built and still being tested. Phase 3 has not started.

## Contents

- **Project Phase 1 Report**: problem statement, objectives and design
- **System Architecture**: how the controller, workers, database and dashboard fit together
- **Research Papers**: reference material used for the project
- **Phase 2 Notes**: see the files in the project root
  - `PHASE2_REPORT.md`: what was built in Phase 2
  - `PHASE2_AUDIT_AND_RUNBOOK.md`: what is verified, what is not, and how to run it on two PCs
- **Future Project Documentation**: Phase 3 planning

## What the project does

A Flask controller keeps track of a simulated pool of servers. Worker programs report their CPU, RAM and disk usage and run a small set of safe, fixed tasks. All data is stored in MySQL, and a web dashboard shows everything in one place.

## Phase 2 features

- **MySQL storage** for workers, jobs, servers, allocations and resource logs
- **CPU scheduling** with FCFS, Priority and Round Robin, including a Gantt chart and waiting / turnaround / response times
- **Banker's algorithm** to check whether a resource state is safe
- **Resource allocation** of CPU, RAM and storage, using transactions and row locks so two requests don't clash
- **Worker agent** that sends heartbeats and runs only approved tasks (no arbitrary commands)
- **Client program** that lets a second PC on the same network submit a job and read its result
- **Dashboard** with job queue, worker health, capacity charts and an allocation ledger

## Tech stack

Python, Flask, MySQL 8, HTML / CSS / JavaScript, psutil, Git and GitHub

## Current status

| Area | Status |
|---|---|
| OS algorithms (scheduling, Banker's) | Done, unit tests pass |
| Client API and text analysis task | Done, local tests pass |
| MySQL storage and allocation | Written, not yet tested against a live database |
| Worker running over the network | Written, not yet tested end to end |
| Two-PC setup | Not yet tested |
| HTTPS, rate limiting, crash recovery of stuck jobs | Not done |

The server pool is a **simulation**. It does not control real cloud machines, and it is not meant for production use.

## Planned for Phase 3

- Distributed scheduling across several servers
- Smarter server selection
- Production-style deployment
- Better security (HTTPS, rate limits)

## Team

Team ID: OSDBMS-V-2026-T162
