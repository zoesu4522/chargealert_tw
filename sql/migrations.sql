-- =====================================================================
-- ChargeAlert TW — Schema Migration 記錄
-- =====================================================================
-- 用途:記錄 init.sql 首次建立後、額外手動套用的 schema 變更。
--
-- 為什麼需要這個檔:
--   init.sql 只在「DB volume 第一次建立」時由 MySQL 容器自動執行。
--   volume 已存在的環境(本機 / EC2 既有 DB),改了 init.sql 也不會重跑,
--   必須手動套用變更。這個檔就是那些變更的單一記錄,
--   每筆都用 IF NOT EXISTS / 防呆寫法,可安全重複執行。
--
-- 套用方式(任一環境,缺欄位時執行):
--   docker compose exec db mysql -u root -p<密碼> chargealert < sql/migrations.sql
--   或逐段貼進 MySQL Workbench / mysql CLI。
--
-- 未來正規做法:導入 migration 工具(Alembic / Flyway)做版本化管理。
--   目前專案規模小,以本檔人工記錄即可。
-- =====================================================================

USE chargealert;

-- ---------------------------------------------------------------------
-- 2026-06-01  多縣市架構:station_info 增加 city / district
-- ---------------------------------------------------------------------
-- 背景:原本系統只服務桃園,city 寫死在程式。多縣市改造後,
--       station_info 需記錄每站所屬縣市(city,英文 code)與行政區
--       (district,中文,從 TDX 地址 Town 取得)。
-- 套用環境:本機(2026-06-01 手動 ALTER)、EC2(2026-06-01 手動 ALTER)。
--
-- 注意:MySQL 8.0 的 ALTER TABLE ADD COLUMN 不支援 IF NOT EXISTS,
--       若欄位已存在會報 1060 錯誤(可忽略),或先用下方查詢確認。
--
-- 確認欄位是否已存在:
--   SELECT COLUMN_NAME FROM information_schema.COLUMNS
--   WHERE TABLE_SCHEMA='chargealert' AND TABLE_NAME='station_info'
--     AND COLUMN_NAME IN ('city','district');

ALTER TABLE station_info
    ADD COLUMN city     VARCHAR(50) NULL AFTER station_name,
    ADD COLUMN district VARCHAR(50) NULL AFTER city,
    ADD INDEX idx_city (city),
    ADD INDEX idx_city_district (city, district);

-- Backfill:既有資料(多縣市改造前抓的)全屬桃園。
UPDATE station_info SET city = 'Taoyuan' WHERE city IS NULL;

-- 從地址抽行政區(桃園地址格式「桃園市XX區」)。
-- 先用「市」切右半去掉縣市名,再用「區」切左半得到區名。盡力而為,非 100%。
UPDATE station_info
SET district = SUBSTRING_INDEX(SUBSTRING_INDEX(address, '區', 1), '市', -1)
WHERE city = 'Taoyuan' AND address LIKE '%區%' AND district IS NULL;

-- ---------------------------------------------------------------------
-- 2026-06-01  availability_snapshot(趨勢圖快照表)
-- ---------------------------------------------------------------------
-- 背景:此表是 init.sql 早期版本沒有的(趨勢圖功能後加)。
--       新版 init.sql 已含此表;舊 volume 需手動補建。
-- 用 IF NOT EXISTS,已存在則略過,可安全重跑。

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

-- =====================================================================
-- 變更記錄結束。新增變更請往下追加,並標註日期 + 套用環境。
-- =====================================================================
