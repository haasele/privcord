FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker_autoscaler/ worker_autoscaler/
COPY config/ config/

ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "worker_autoscaler", "--config", "/app/config/example.yaml"]
