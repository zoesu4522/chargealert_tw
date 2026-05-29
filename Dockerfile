# 基礎:Python 3.13(穩定版,跟你的 3.14 相容但更通用)
FROM python:3.13-slim

# 設定工作目錄
WORKDIR /app

# 環境變數:讓 Python 輸出不要被緩衝(才看得到即時 log)
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Taipei

# 先複製 requirements 並安裝(這層會被快取,改 code 時不用重裝套件)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案檔案
COPY src/ ./src/

# 工作目錄移到 src(因為你的程式從 src 跑)
WORKDIR /app/src

# 啟動指令:跑排程器
CMD ["python", "scheduler.py"]