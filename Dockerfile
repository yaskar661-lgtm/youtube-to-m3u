FROM python:3.11-slim

# Streamlink'in kararlı çalışması için gerekli sistem paketlerini kuruyoruz
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render'ın portu dışarı açabilmesi için çevre değişkenini Docker'a geçiriyoruz
ENV PYTHONUNBUFFERED=1

CMD ["python", "proxy_server.py"]
