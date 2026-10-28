FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHESS_OCR_REPO=/opt/2d-chess-ocr \
    CHESS_OCR_MODEL=/opt/2d-chess-ocr/finetuned-models/yolo26m-finetuned.pt \
    MAX_PDF_MB=25 \
    MAX_PDF_PAGES=160

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates stockfish libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Clone the actual detector code and download its published pretrained weights.
RUN git clone --depth 1 https://github.com/AndrewSpano/2d-chess-ocr.git /opt/2d-chess-ocr \
    && cd /opt/2d-chess-ocr \
    && python download_models.py \
    && test -f /opt/2d-chess-ocr/finetuned-models/yolo26m-finetuned.pt

COPY app.py /app/app.py
EXPOSE 10000
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 600"]
