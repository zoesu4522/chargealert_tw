FROM python:3.13-slim

WORKDIR /app

# 先裝套件,讓 Docker 快取這層(之後改程式不用每次重裝)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製 webhook 程式
COPY . .

EXPOSE 8000

# 容器內跑 uvicorn。這裡是 main:app(不是 webhook.main:app),
# 因為 build context 是 ./webhook,main.py 就在容器的 /app 底下。
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
