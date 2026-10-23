FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY wifi_sonar ./wifi_sonar
COPY web ./web

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "wifi_sonar"]
