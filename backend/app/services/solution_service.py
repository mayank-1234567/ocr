from __future__ import annotations

import re

import chess

SAN_RE = re.compile(
    r"(?:\d+\.{1,3})?\s*([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O|[a-h]x[a-h][1-8](?:=[QRBN])?[+#]?)"
)


class SolutionService:
    def extract_san_candidates(self, text: str) -> list[str]:
        return [m.group(1).strip() for m in SAN_RE.finditer(text)]

    def validate_san_line(self, fen: str, san_moves: list[str]) -> tuple[bool, list[str]]:
        board = chess.Board(fen)
        normalized: list[str] = []
        try:
            for san in san_moves:
                move = board.parse_san(san)
                normalized.append(board.san(move))
                board.push(move)
            return True, normalized
        except Exception:
            return False, normalized
