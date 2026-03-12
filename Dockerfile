FROM node:22-bookworm-slim AS frontend-build

WORKDIR /frontend

COPY src/otomoto_parser/v2/frontend/package.json src/otomoto_parser/v2/frontend/package-lock.json ./
RUN npm ci

COPY src/otomoto_parser/v2/frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY README.md pyproject.toml ./
COPY src ./src
COPY --from=frontend-build /frontend/dist ./src/otomoto_parser/v2/frontend/dist

RUN python -m pip install --upgrade pip \
    && python -m pip install .

VOLUME ["/data"]
EXPOSE 8000

CMD ["parser-app", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/data"]
