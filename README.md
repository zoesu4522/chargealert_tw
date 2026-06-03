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

## 📖 專案背景

剛踏入電動車生活的駕駛,卻發現「找充電站」比加油痛苦十倍 ——
明明地圖顯示有站,趕到卻被佔用;下雨天還得淋雨等待,或在多個互不相通的 App 間焦慮切換。

**ChargeAlert TW** 從「白跑一趟」的真實痛點出發,結合政府開放資料與雲端 AI 運算,
將駕駛從「主動刷 App」的焦慮中解放出來 —— 訂閱想去的充電站,**有空位時主動通知你**。

### 解決的痛點

| 痛點 | 解方 |
|------|------|
| 🏝️ **資訊孤島** — 各家業者 App 互不相通 | 串接 TDX 交通部開放資料,單一介面查全台充電站 |
| 🔄 **被動查詢** — 無法及時掌握動態 | 訂閱制 + 主動推播,空位釋出即時通知 |
| 🌧️ **多維缺失** — 難綜合天氣與位置 | 整合中央氣象署 CWA,天氣感知充電建議 |
| ⛽ **資源浪費** — 無效行駛與時間成本 | 即時可用數 + 通知,減少白跑一趟 |

---

## 🏗️ 系統架構

四代理人架構,部署於 AWS EC2,以 Docker Compose 編排:

```
外部資料來源              AWS Cloud (EC2 t3.micro)              使用者
                    ┌──────────────────────────────┐
TDX API ──擷取──▶   │  Python Scheduler (4 Agents)   │
                    │  ├ TDX Watcher    每15分抓取     │
中央氣象署 API ─查詢▶ │  ├ Push Notifier  狀態變化推播   │  ──▶  LINE
                    │  ├ ChargeChat     LLM 對話       │       使用者
LINE Messaging ─推播▶│  └ Weather Advisor 天氣建議      │
   ◀── Webhook       │                                │
                    │  MySQL 8.0 (連線資料/歷史/訂閱)   │
OpenAI/Bedrock ─prompt▶                                │
                    │  Parameter Store · CloudWatch   │
                    └──────────────────────────────┘
```

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

---

## 💡 開發亮點

開發過程記錄了多個工程決策與問題排查:

- **並發處理** — LINE 連點造成重複卡片,診斷出 race condition,將鎖機制從背景任務移至 webhook 同步段,並評估 Redis 分散式鎖的投入產出比後採記憶體冷卻鎖
- **資料一致性** — 釐清 KPI 與趨勢圖的資料來源,將指標聚焦於唯一持續即時監控的桃園,誠實標示資料範圍而非以混合數字撐場面
- **規則優先 + LLM 後備** — 核心功能用確定性規則保證可用性,LLM 作為增強層,系統不依賴外部配額
- **系統可觀測性** — 完整的 log 追蹤(抓取 → 快照 → 偵測變化 → 推播 → 冷卻)

---

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
