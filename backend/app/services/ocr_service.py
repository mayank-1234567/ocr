from __future__ import annotations

import pytesseract


class OCRService:
    def extract_text(self, image_bytes: bytes) -> str:
        try:
            return pytesseract.image_to_string(image_bytes)
        except Exception:
            return ""
