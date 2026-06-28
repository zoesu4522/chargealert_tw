# ⚡ ChargeAlert TW · 充電有譜

> 基於多源開放資料與 LLM 的電動車充電站智慧通報系統

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![AWS](https://img.shields.io/badge/AWS-EC2-FF9900)

**🔗 線上展示:** [chargealert.zoesu.dev](https://chargealert.zoesu.dev) ｜ **📊 即時監控儀表板:** [/dashboard](https://chargealert.zoesu.dev/dashboard/)

---


## 📑 目錄
- [專案背景](#-專案背景)
- [系統架構](#️-系統架構)
- [技術棧](#️-技術棧)
- [主要功能](#-主要功能)
- [部署架構](#-部署架構)
- [可觀測性](#-可觀測性-observability)
- [開發亮點](#-開發亮點)
- [作者](#-作者-author)
- [授權](#-授權-license)


## 📖 專案背景

剛踏入電動車生活的駕駛,卻發現「找充電站」比加油痛苦十倍 ——
明明地圖顯示有站,趕到卻被佔用;下雨天還得淋雨等待,或在多個互不相通的 App 間焦慮切換。

**ChargeAlert TW** 從「白跑一趟」的真實痛點出發,結合政府開放資料與雲端 AI 運算,
將駕駛從「主動刷 App」的焦慮中解放出來 —— 訂閱想去的充電站,**有空位時主動通知你**。

### 解決的痛點

| 痛點 | 解方 |
|------|------|
| 🏝️ 資訊孤島 — 各家 App 互不相通 | 串接 TDX 開放資料,多縣市 On-Demand 查詢、桃園 24/7 持續監控 |
| 🔄 **被動查詢** — 無法及時掌握動態 | 訂閱制 + 主動推播,空位釋出即時通知 |
| 🌧️ **單一資訊** — 無天氣 / 位置綜合判斷 | 整合中央氣象署 CWA,天氣感知充電建議 |
| ⛽ **資源浪費** — 無效行駛與時間成本 | 即時可用數 + 通知,減少白跑一趟 |

---

## 🏗️ 系統架構

![系統架構圖](https://d1h66ke8evp6ux.cloudfront.net/docs/architecture.png)

四代理人架構,部署於 AWS EC2(t3.micro · 東京),以 Docker Compose 編排,
Caddy 提供自動 HTTPS,CloudWatch 負責 metrics / logs / alarms 觀測性。


### 📐 系統設計圖

| 使用者流程 | 功能模組 |
|:---:|:---:|
| ![使用者流程圖](https://d1h66ke8evp6ux.cloudfront.net/docs/user-flow.png) | ![功能模組圖](https://d1h66ke8evp6ux.cloudfront.net/docs/module-map.png) |


### LINE Bot 互動展示

| Rich Menu | 訂閱卡片 | 推播通知 |
|:---:|:---:|:---:|
| ![Rich Menu](https://d1h66ke8evp6ux.cloudfront.net/docs/rich_menu.png) | ![Sub Card](./docs/sub-card.png) | ![Push](./docs/push-notify.png) |


### 四代理人

- **TDX Watcher** — 每 15 分鐘輪詢 TDX API,抓取桃園市充電站即時狀態,寫入 MySQL 並偵測狀態變化
- **Push Notifier** — 偵測到訂閱站「使用中→空閒」時,依使用者設定(開關/時段/冷卻)主動推播
- **ChargeChat** — LINE 訊息的 LLM 意圖解析(規則優先 + LLM 後備),查詢即時站況
- **Weather-Aware Advisor** — 整合 CWA 天氣資料,提供結合天氣的充電建議

---

## 🛠️ 技術棧

| 分類 | 技術 |
|------|------|
| **後端** | Python 3.13, FastAPI, APScheduler |
| **資料庫** | MySQL 8.0 |
| **雲端 / 維運** | AWS EC2, Docker Compose, Caddy (自動 HTTPS), Parameter Store, CloudWatch |
| **外部 API** | TDX 運輸資料流通服務, 中央氣象署 CWA, LINE Messaging API, OpenAI / AWS Bedrock |
| **前端** | 原生 HTML/CSS/JS, Chart.js (零 build 靜態儀表板) |

---


## 📊 系統現況

| 指標 | 數字 |
|------|------|
| 監控充電樁 | **1577** 支(桃園範圍) |
| 監控充電站 | **354** 座 |
| 運作時間 | 24 / 7(自 2026 年 5 月起連續上線) |
| 月運行成本 | ~ **NT$0**(AWS Free Tier) |
| TDX 點數用量 | < 月免費額度的 **1.4%** |



## ✨ 主要功能

### LINE Bot
- 🔍 **查站** — 文字或選單查充電站即時可用狀態
- 🗺️ **多縣市查詢** — 7 大都會 On-Demand 抓取,選縣市/依區找站
- 🔔 **訂閱通知** — 訂閱充電站,空位釋出主動推播(完整生命週期:訂閱→即時回報→通知→暫停/恢復→退訂)
- ⏰ **通知時段** — 自訂接收通知的時段(避免清晨被打擾)
- 🌤️ **天氣查詢** — 各縣市天氣 + 充電建議
- 🎨 **視覺化卡片** — Flex Message 充電站卡、縣市地標圖、天氣卡

### 即時監控儀表板
- 📊 KPI 總覽(可切換桃園即時 / 全部累積)
- 🔌 充電槍狀態分布、AC/DC 可用概況
- 📈 可用量趨勢、變化活躍度
- 🌦️ 全台主要縣市天氣總覽
- 🌙 亮 / 暗主題、響應式設計

---

## 🚀 部署架構

- **容器化:** Docker Compose 編排 4 服務(db / app / webhook / caddy)
- **HTTPS:** Caddy + Let's Encrypt 自動憑證
- **密鑰管理:** AWS Parameter Store 集中管理 API keys / DB 密碼
- **持續部署:** Git-based workflow(本機驗證 → push → EC2 pull → rebuild)


## 🚀 Quick Start

### 本地開發

```bash
git clone https://github.com/zoesu4522/chargealert_tw.git
cd chargealert_tw
cp .env.example .env
docker compose up -d
```

### 部署到 AWS EC2

詳見 [`docs/deployment.md`](./docs/deployment.md)


## 📡 可觀測性 (Observability)

CloudWatch Agent 收集自訂指標,Docker 四容器日誌集中管理,並設置告警:

- **Metrics** — CPU / 記憶體 / **swap** 使用率(自訂 namespace `ChargeAlertTW`)
- **Logs** — 四容器日誌集中至 `/chargealert/docker-logs`
- **Alarms** — CPU > 80% 過載告警、5 分鐘內錯誤暴增(>10)告警
- **實測** — CPU idle ≈ 98.5%、記憶體 ≈ 45%、swap ≈ 22%(2GB RAM 靠 swap 撐 MySQL + Python 的實證)

> 監控是 production 系統的必備,不是奢侈品。
---

## 💡 開發亮點

開發過程記錄了多個工程決策與問題排查:

- **並發處理** — LINE 連點造成重複卡片,診斷出 race condition,將鎖機制從背景任務移至 webhook 同步段,並評估 Redis 分散式鎖的投入產出比後採記憶體冷卻鎖
- **資料一致性** — 釐清 KPI 與趨勢圖的資料來源,將指標聚焦於唯一持續即時監控的桃園,誠實標示資料範圍而非以混合數字撐場面
- **規則優先 + LLM 後備** — 核心功能用確定性規則保證可用性,LLM 作為增強層,系統不依賴外部配額
- **系統可觀測性** — 完整的 log 追蹤(抓取 → 快照 → 偵測變化 → 推播 → 冷卻)
- **抽象設計的價值** — Bedrock 配額受阻時,靠 `_invoke()` 抽象層零改動切換至 OpenAI
  > 「AI 可以失敗,但系統不能失去方向。」

---

## 🗺️ Roadmap

- [x] CloudWatch observability(已完成 2026/6)
- [ ] 全台縣市 Active 監控擴展
- [ ] ChargeChat 對話深度優化(RAG)
- [ ] 歷史熱門度分析 + 預測
- [ ] mysqldump → S3 自動備份


## 👤 作者 Author

**蘇品寧 (Zoe Su)**

- GitHub: [@zoesu4522](https://github.com/zoesu4522)
- 專案展示 (Live Demo): [chargealert.zoesu.dev](https://chargealert.zoesu.dev)
- 個人網站: [zoesu.dev](https://www.zoesu.dev)

本專案為個人獨立開發之作品,從系統架構設計、後端 API、資料庫、
雲端部署 (AWS EC2 / Docker) 到 LINE Bot 互動與前端儀表板皆由本人完成。
完整開發歷程記錄於 commit history。

## 📄 授權 License

本專案採 **MIT License** 釋出 — 歡迎參考、學習與延伸使用。

Copyright (c) 2026 Zoe Su (Su Pin-Ning)

使用、修改或散布本專案程式碼時,**請保留上述著作權聲明與原作者標示**。
詳見 [LICENSE](./LICENSE)。


