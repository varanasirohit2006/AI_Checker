FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY package.json package-lock.json ./
COPY requirements.txt* ./
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sqlalchemy \
    psycopg2-binary \
    redis \
    celery \
    python-multipart \
    pyjwt \
    torch --extra-index-url https://download.pytorch.org/whl/cpu \
    transformers \
    sentence-transformers \
    faiss-cpu \
    datasketch \
    pdfplumber \
    python-docx \
    confusable-homoglyphs \
    scipy \
    scikit-learn

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
