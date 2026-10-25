from __future__ import annotations

from functools import lru_cache

import chess
import chess.engine

from app.core.config import settings


class ChessEngineService:
    @lru_cache(maxsize=1)
    def _engine_path(self) -> str | None:
        return settings.stockfish_path

    def available(self) -> bool:
        return bool(self._engine_path())

    def analyze(self, fen: str, depth: int | None = None) -> dict:
        depth = depth or settings.engine_depth
        board = chess.Board(fen)
        if not self.available():
            return {"available": False, "candidates": [], "reason": "Stockfish path not configured"}

        path = self._engine_path()
        assert path
        with chess.engine.SimpleEngine.popen_uci(path) as engine:
            info = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=3)

        rows = info if isinstance(info, list) else [info]
        candidates = []
        for row in rows:
            pv = row.get("pv", [])
            if not pv:
                continue
            san_line = []
            probe = chess.Board(fen)
            for move in pv[:6]:
                san_line.append(probe.san(move))
                probe.push(move)
            score = row["score"].pov(board.turn)
            candidates.append({"line": san_line, "score": score.score(mate_score=100000)})
        return {"available": True, "candidates": candidates}
