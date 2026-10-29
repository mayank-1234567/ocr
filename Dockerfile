# The upstream 2d-chess-ocr project currently requires Python >= 3.14.2.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHESS_OCR_REPO=/opt/2d-chess-ocr \
    CHESS_OCR_MODEL=/opt/2d-chess-ocr/finetuned-models/yolo26m-finetuned.pt \
    MAX_PDF_MB=25 \
    MAX_PDF_PAGES=100 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates stockfish libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt

# Install CPU-only PyTorch. This avoids fetching the much larger CUDA runtime
# for a Render service that runs inference on CPU.
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && python -m pip install -r /app/requirements.txt

# Use the real detector and the published model weights from AndrewSpano/2d-chess-ocr.
RUN git clone --depth 1 https://github.com/AndrewSpano/2d-chess-ocr.git /opt/2d-chess-ocr \
    && cd /opt/2d-chess-ocr \
    && python download_models.py \
    && test -s /opt/2d-chess-ocr/finetuned-models/yolo26m-finetuned.pt

COPY app.py /app/app.py
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 600 --access-logfile - --error-logfile -"]
