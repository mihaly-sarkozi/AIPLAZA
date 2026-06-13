FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        tesseract-ocr \
        tesseract-ocr-hun \
        tesseract-ocr-eng \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install --upgrade pip && pip install -r requirements-dev.txt

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/pytest.ini ./pytest.ini
COPY backend/admin ./admin
COPY backend/apps ./apps
COPY backend/core ./core
COPY backend/infra ./infra
COPY backend/lang ./lang
COPY backend/main.py ./main.py
COPY backend/scripts ./scripts
COPY backend/scaffolding ./scaffolding
COPY backend/shared ./shared
COPY backend/storage ./storage
COPY backend/tests ./tests

EXPOSE 8001

CMD ["sh", "-c", "python3 scripts/init_db.py && uvicorn main:app --reload --host 0.0.0.0 --port 8001"]
