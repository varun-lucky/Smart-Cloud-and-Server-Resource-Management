-- SmartCloud Platform — MySQL 8+ schema
-- Run this script in MySQL Workbench (or another GUI MySQL client) before starting app.py.
CREATE DATABASE IF NOT EXISTS smartcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smartcloud;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(190) NULL UNIQUE,
    role VARCHAR(24) NOT NULL DEFAULT 'USER',
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT chk_users_role CHECK (role IN ('USER','ADMIN'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS workers (
    worker_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    capabilities_json JSON NOT NULL,
    metrics_json JSON NOT NULL,
    last_seen TIMESTAMP(6) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_workers_last_seen (last_seen)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS servers (
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
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS jobs (
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
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS allocations (
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
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resource_usage_logs (
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
) ENGINE=InnoDB;
