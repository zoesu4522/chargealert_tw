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

-- station_info:加入 city / district(多縣市架構)。
-- city  = 縣市英文 code(對應 config.CITY_NAME_MAP,例 Taoyuan)
-- district = 行政區中文名(從地址抽出,例 中壢),UI 進階篩選備用
CREATE TABLE IF NOT EXISTS station_info (
    station_id     VARCHAR(100) PRIMARY KEY,
    station_name   VARCHAR(255),
    city           VARCHAR(50),
    district       VARCHAR(50),
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
    INDEX idx_name (station_name),
    INDEX idx_city (city),
    INDEX idx_city_district (city, district)
);

-- availability_snapshot:每次爬蟲輪詢後寫一次彙總快照,趨勢圖的時間序列來源。
-- 一次寫 3 列(ALL / AC / DC)。狀態碼 1=空閒 2=使用中 3=離線。
CREATE TABLE IF NOT EXISTS availability_snapshot (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_at DATETIME NOT NULL,
    power_type  VARCHAR(10) NOT NULL,
    total       INT DEFAULT 0,
    available   INT DEFAULT 0,
    in_use      INT DEFAULT 0,
    offline     INT DEFAULT 0,
    INDEX idx_type_time (power_type, snapshot_at)
);
-- user_subscriptions:使用者訂閱的充電站(訂閱制推播)。
-- active 軟刪除(退訂設 0 保留記錄);last_notified_at 實作推播冷卻。
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          VARCHAR(100) NOT NULL,
    station_id       VARCHAR(100) NOT NULL,
    station_name     VARCHAR(255),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active           TINYINT(1) DEFAULT 1,
    last_notified_at TIMESTAMP NULL,
    UNIQUE KEY uniq_user_station (user_id, station_id),
    INDEX idx_station_active (station_id, active),
    INDEX idx_user_active (user_id, active)
);

-- user_settings:使用者層級設定(通知總開關等)。
CREATE TABLE IF NOT EXISTS user_settings (
    user_id        VARCHAR(100) PRIMARY KEY,
    notify_enabled TINYINT(1) DEFAULT 1,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
