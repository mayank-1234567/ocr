from __future__ import annotations

import cv2
import numpy as np


class DiagramService:
    def detect_diagrams(self, image_bgr: np.ndarray) -> list[dict]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = gray.shape
        page_area = h * w
        diagrams: list[dict] = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            ratio = cw / max(ch, 1)
            area = cw * ch
            if 0.8 <= ratio <= 1.2 and area > page_area * 0.015:
                diagrams.append(
                    {
                        "bbox": {"x": x, "y": y, "w": cw, "h": ch},
                        "confidence": min(0.95, area / page_area * 6),
                    }
                )
        diagrams.sort(key=lambda d: (d["bbox"]["y"], d["bbox"]["x"]))
        return diagrams[:8]
