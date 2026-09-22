FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    librdkafka-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/
COPY dashboard/ /app/dashboard/

ENV PYTHONPATH=/app/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

WORKDIR /app/app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
