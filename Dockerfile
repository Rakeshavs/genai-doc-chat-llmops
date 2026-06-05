# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build-time OS deps (compiler, BLAS for faiss-cpu)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential gcc git curl \
       poppler-utils libopenblas-dev libomp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a prefix we can copy
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Only runtime OS libs needed (poppler for PDF, OpenBLAS for faiss)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       poppler-utils libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
