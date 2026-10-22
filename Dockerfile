FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY wifi_sonar ./wifi_sonar
COPY web ./web

RUN pip install --no-cache-dir . \
    && mkdir -p /data

ENV WIFI_SONAR_HOST=0.0.0.0 \
    WIFI_SONAR_SOURCE=sim \
    WIFI_SONAR_WEB=/app/web \
    WIFI_SONAR_DB=/data/wifi_sonar.sqlite \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "wifi_sonar"]
