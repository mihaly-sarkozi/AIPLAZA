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
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/apps ./apps
COPY backend/config ./config
COPY backend/core ./core
COPY backend/infra ./infra
COPY backend/lang ./lang
COPY backend/main.py ./main.py
COPY backend/scripts ./scripts
COPY backend/shared ./shared
COPY backend/storage ./storage

EXPOSE 8001

CMD ["sh", "-c", "python3 scripts/init_db.py && uvicorn main:app --host 0.0.0.0 --port 8001"]
