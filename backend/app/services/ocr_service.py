from __future__ import annotations

import cv2
import numpy as np
import pytesseract


class OCRService:
    def extract_text(self, image: np.ndarray) -> str:
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            return pytesseract.image_to_string(gray)
        except Exception:
            return ""
