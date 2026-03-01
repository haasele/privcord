FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask gunicorn

COPY federation_directory/ federation_directory/
COPY requirements.txt .

ENV PYTHONUNBUFFERED=1
ENV DIRECTORY_DATA_PATH=/data/servers.json

EXPOSE 8765

# Default: run with gunicorn; override with DIRECTORY_PORT if needed
CMD ["gunicorn", "-b", "0.0.0.0:8765", "-w", "1", "federation_directory.app:app"]
