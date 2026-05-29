CREATE DATABASE IF NOT EXISTS chargealert
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE chargealert;

CREATE TABLE IF NOT EXISTS connector_status (
    connector_id      VARCHAR(100) PRIMARY KEY,
    station_id        VARCHAR(100),
    charging_point_id VARCHAR(100),
    connector_type    INT,
    current_status    INT,
    last_update_time  DATETIME,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_station (station_id),
    INDEX idx_status (current_status)
);

CREATE TABLE IF NOT EXISTS status_history (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    connector_id VARCHAR(100),
    station_id   VARCHAR(100),
    old_status   INT,
    new_status   INT,
    changed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified     TINYINT(1) DEFAULT 0,
    INDEX idx_connector_time (connector_id, changed_at),
    INDEX idx_notified (notified)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at     TIMESTAMP NULL,
    connectors_count INT,
    changes_count   INT DEFAULT 0,
    status          VARCHAR(20),
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS station_info (
    station_id     VARCHAR(100) PRIMARY KEY,
    station_name   VARCHAR(255),
    description    TEXT,
    operator_id    VARCHAR(100),
    latitude       DECIMAL(10, 7),
    longitude      DECIMAL(10, 7),
    address        VARCHAR(500),
    charging_rate  TEXT,
    parking_rate   TEXT,
    service_time   VARCHAR(255),
    telephone      VARCHAR(50),
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (station_name)
);