# Chess Tactics Trainer — Render Docker deployment

This app combines a chess tactics trainer with automatic position extraction from PDF books. It uses the actual `AndrewSpano/2d-chess-ocr` repository and its published YOLO weights; it does not replace the OCR model with a generic OCR service.

## Upload to GitHub from a phone

1. Download and extract the ZIP.
2. Open the GitHub repository and tap **Add file → Upload files**.
3. Upload these files to the repository root (not the ZIP, and not a nested folder): `Dockerfile`, `app.py`, `requirements.txt`, `render.yaml`, `README.md`, `.dockerignore`.
4. Commit the changes. In the repository's main file list, `Dockerfile` must be visible alongside `app.py`.

The filename is exactly `Dockerfile` with a capital D and no extension. If GitHub turns it into `Dockerfile.txt`, rename it.

## Deploy on Render

Recommended: in Render, choose **New + → Blueprint**, connect the GitHub repository, and let Render read `render.yaml`. Or create a **Web Service** with runtime **Docker**. If the files are in the repository root, leave **Root Directory** empty. If you put them in a subfolder, set Root Directory to that folder.

The Dockerfile installs Stockfish and CPU-only PyTorch, installs the Python packages, clones the original OCR repository, and downloads its published model weights during build. The first build may take several minutes and the image is large. This app needs enough RAM to load PyTorch and the OCR model; Render's free instance may run out of memory during inference or while processing large PDFs.

## What the app does

- Accepts a PDF upload, renders each page with PyMuPDF, and passes page images to `Chess2DOCRInference` from the original OCR project.
- Filters invalid chess positions and passes recognized positions directly to the trainer.
- Uses Stockfish to evaluate moves and provide hints.
- Uses a self-contained click-to-move board; no external chessboard JavaScript/CDN is needed.
- Does not require a database or login.

## Limits

Defaults: 25 MB maximum PDF, 100 pages, PDF scale 1.35. CPU inference is slow for large books, and OCR can miss or misread diagrams. The extracted list is stored in the current browser's local storage; uploaded PDFs and in-progress processing jobs are not persistent across restarts. The model infers the side to move heuristically from highlighted last-move tiles, so review uncertain diagrams carefully.

## If the deployment fails

Open the Render service → **Events** or **Logs** and copy the first error lines. Build errors usually mention package installation, model download, or missing files; runtime errors appear after the service starts. Do not send secret keys or tokens.
