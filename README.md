# Universal Chess Tactics Book Trainer

Local full-stack app that ingests chess tactics PDFs and turns extracted puzzles into an interactive trainer.

## What is implemented

- **Frontend**: React + TypeScript + Vite UI with:
  - Library upload page
  - Book/puzzle browsing with extraction confidence + status filters
  - Manual correction for FEN and solution line
  - Interactive chess trainer (drag/drop, undo, restart, hints, reveal, auto-next)
  - Progress dashboard
- **Backend**: FastAPI + SQLite with:
  - PDF upload and persistent local storage
  - Ingestion pipeline (text extraction + OCR fallback + diagram detection hooks)
  - Puzzle extraction records with confidence, status, source type, debug payload
  - Duplicate detection
  - Attempt and cycle tracking APIs
  - Stockfish integration hook (optional via environment variable)
- **Testing**:
  - Unit test for SAN extraction/validation
  - Integration test for PDF ingestion
  - API health test

## Architecture and extraction design

Pipeline components are separated so book layouts can be handled incrementally:

1. `PDFService` (PyMuPDF): page text + render data
2. `OCRService` (pytesseract): fallback on low-text pages
3. `DiagramService` (OpenCV): candidate diagram bbox detection (supports multiple page candidates)
4. `SolutionService` (python-chess): SAN extraction + legal-line validation
5. `ChessEngineService` (python-chess UCI): optional Stockfish analysis/candidate lines
6. `IngestionService`: orchestrates matching, confidence scoring, statusing, duplicate marking

Status values distinguish extraction quality:

- `verified`
- `needs_review`
- `engine_generated`
- `duplicate`
- `failed` (book-level)

## Pretrained/model strategy (current)

This build uses a **conservative baseline recognizer** (OpenCV + parsing heuristics) and ships a pluggable service structure for integrating pretrained chess OCR models without rewriting the app.

- Included OCR backend: `pytesseract` (Apache-2.0)
- Included CV backend: `opencv-python-headless` (Apache-2.0)
- Included rule/engine tooling: `python-chess` (GPL-3.0-or-later)

A stronger pretrained piece recognizer is not bundled yet; low-confidence puzzles are automatically marked for manual review/correction.

## Data storage

All runtime data is local under `/home/runner/work/ocr/ocr/backend/storage` (on Windows: `backend\\storage`):

- `trainer.db` — SQLite database
- `uploads/` — uploaded PDFs
- `artifacts/` — processing artifacts (reserved)

## Windows setup and run

### 1) Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Optional Stockfish setup:

```powershell
$env:UCT_STOCKFISH_PATH="C:\\path\\to\\stockfish.exe"
```

### 2) Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Usage flow

1. Open Library tab.
2. Upload a PDF.
3. Wait for status to move to `ready`.
4. Inspect extracted puzzles; correct uncertain FEN/lines using `Edit FEN` / `Edit line`.
5. Start training in sequential or random mode.
6. Solve on board; use hint/restart/reveal/next controls.
7. View aggregated progress in Dashboard.

## Test commands

Backend:

```bash
cd backend
PYTHONPATH=/home/runner/work/ocr/ocr/backend pytest -q
```

Frontend:

```bash
cd frontend
npm run build
npm run lint
```

## Known limitations

- Baseline diagram recognition does not yet provide high-accuracy piece-by-piece extraction for all scanned books.
- OCR quality depends on local Tesseract availability and scan quality.
- Solution matching currently supports SAN-style extraction best; prose/descriptive notation support is partial.
- Trainer validation currently checks against parsed line(s); broader objective-aware acceptance logic is still incremental.
- No dedicated visual review pane showing diagram crop beside editable board yet.
- Chapter inference and puzzle-number matching are heuristic and may require manual review.
