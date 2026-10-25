from __future__ import annotations

import hashlib
from pathlib import Path

import fitz


class PDFService:
    @staticmethod
    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def read_pages(path: Path) -> list[dict]:
        pages: list[dict] = []
        with fitz.open(path) as doc:
            for i, page in enumerate(doc):
                blocks = page.get_text("blocks")
                text = page.get_text("text")
                pages.append(
                    {
                        "index": i,
                        "text": text,
                        "blocks": [
                            {
                                "x0": b[0],
                                "y0": b[1],
                                "x1": b[2],
                                "y1": b[3],
                                "text": b[4],
                            }
                            for b in blocks
                        ],
                        "pixmap": page.get_pixmap(dpi=220, alpha=False),
                    }
                )
        return pages
