FROM python:3.11-slim

# System deps for OCR + PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate Prisma client
RUN prisma generate

RUN mkdir -p /app/storage/uploads

# Default: run API server (override for worker)
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
