# Use official Python image matching pyproject.toml
FROM python:3.13-slim

# Prevent Python from writing .pyc files and make stdout/stderr unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS-level build and document-processing dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       git \
       curl \
       poppler-utils \
       libopenblas-dev \
       libomp-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest and install Python requirements
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the app port
EXPOSE 8080

# Start the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
