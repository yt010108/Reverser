FROM node:22-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv docker.io ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN npm ci --omit=dev

COPY pyproject.toml README.md ./
COPY code ./code
RUN python3 -m venv /opt/reverser-venv \
 && /opt/reverser-venv/bin/pip install --no-cache-dir '.[web]'

COPY .pi ./.pi
COPY config.toml ./
COPY memory ./memory
COPY web ./web
ENV PATH="/opt/reverser-venv/bin:/app/node_modules/.bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
CMD ["uvicorn", "reverser_harness.web:app", "--host", "0.0.0.0", "--port", "8080"]
