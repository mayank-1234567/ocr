from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import chess
from sqlmodel import Session, select

from app.models import Book, ImportJob, Page, Puzzle
from app.services.chess_engine_service import ChessEngineService
from app.services.diagram_service import DiagramService
from app.services.ocr_service import OCRService
from app.services.pdf_service import PDFService
from app.services.solution_service import SolutionService

FEN_RE = re.compile(r"(?:FEN[:\s]+)?([rnbqkpRNBQKP1-8/]{15,}\s+[wb]\s+[-KQkq]{1,4}|[rnbqkpRNBQKP1-8/]{15,}\s+[wb]\s+-\s+-\s+\d+\s+\d+)")
PUZZLE_NUM_RE = re.compile(r"(?:Puzzle|Diagram|#)\s*(\d+[A-Za-z]?)", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^\s*(Chapter\s+\d+[:\-]?.*)$", re.IGNORECASE | re.MULTILINE)


class IngestionService:
    def __init__(self):
        self.pdf = PDFService()
        self.diagram = DiagramService()
        self.solution = SolutionService()
        self.engine = ChessEngineService()
        self.ocr = OCRService()

    def _mark_book(self, session: Session, book: Book, status: str, progress: float, error: str | None = None) -> None:
        book.import_status = status
        book.extraction_progress = progress
        book.error_message = error
        book.updated_at = datetime.utcnow()
        session.add(book)
        session.commit()

    def process_book(self, session: Session, book_id: int) -> None:
        book = session.get(Book, book_id)
        if not book:
            return

        job = ImportJob(book_id=book_id, status="running", stage="loading")
        session.add(job)
        session.commit()

        try:
            self._mark_book(session, book, "processing", 0.02)
            pages = self.pdf.read_pages(Path(book.file_path))
            total = len(pages) or 1

            for p in pages:
                image = np.frombuffer(p["pixmap"].samples, dtype=np.uint8).reshape(p["pixmap"].height, p["pixmap"].width, p["pixmap"].n)
                if p["pixmap"].n == 4:
                    image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                elif p["pixmap"].n == 1:
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

                ocr_text = ""
                if len(p["text"].strip()) < 40:
                    ocr_text = self.ocr.extract_text(image)

                page_text = p["text"] or ocr_text
                page = Page(
                    book_id=book.id,
                    page_index=p["index"],
                    printed_page_number=str(p["index"] + 1),
                    extracted_text=page_text,
                    ocr_text=ocr_text,
                    layout_json={"blocks": p["blocks"]},
                )
                session.add(page)
                session.commit()
                session.refresh(page)

                chapter_match = CHAPTER_RE.search(page_text)
                chapter = chapter_match.group(1).strip() if chapter_match else None
                puzzle_num_match = PUZZLE_NUM_RE.search(page_text)
                puzzle_num = puzzle_num_match.group(1) if puzzle_num_match else None

                fen_text_matches = [m.group(1).strip() for m in FEN_RE.finditer(page_text)]
                diagrams = self.diagram.detect_diagrams(image)

                if not fen_text_matches and not diagrams:
                    self._mark_book(session, book, "processing", (p["index"] + 0.5) / total)
                    continue

                # Always create at least one puzzle candidate when diagram is detected.
                candidates = fen_text_matches or [None] * max(1, len(diagrams))
                san_candidates = self.solution.extract_san_candidates(page_text)

                for i, fen_candidate in enumerate(candidates):
                    debug = {"page_index": p["index"], "diagrams": diagrams, "candidate_index": i}
                    status = "needs_review"
                    confidence = 0.25
                    parsed_solution: list[str] = []
                    source_type = "book"

                    fen = None
                    side = None
                    side_hint = "b" if "black to move" in page_text.lower() else "w" if "white to move" in page_text.lower() else None
                    if fen_candidate:
                        chunks = fen_candidate.split()
                        if len(chunks) == 3:
                            fen = f"{chunks[0]} {chunks[1]} - - 0 1"
                            side = chunks[1]
                        else:
                            fen = fen_candidate
                            side = fen.split()[1] if len(fen.split()) > 1 else None

                        try:
                            board = chess.Board(fen)
                            if board.king(chess.WHITE) is not None and board.king(chess.BLACK) is not None:
                                status = "verified"
                                confidence = 0.9
                        except Exception:
                            status = "needs_review"

                    if fen and san_candidates:
                        ok, normalized = self.solution.validate_san_line(fen, san_candidates[:8])
                        if ok:
                            parsed_solution = normalized
                        elif normalized:
                            parsed_solution = normalized
                            status = "needs_review"

                    if fen and not parsed_solution:
                        analysis = self.engine.analyze(fen)
                        if analysis.get("available") and analysis.get("candidates"):
                            parsed_solution = analysis["candidates"][0]["line"]
                            source_type = "engine_generated"
                            if status == "verified":
                                status = "engine_generated"

                    if not fen:
                        # conservative placeholder for manual correction
                        fen = "8/8/8/8/8/8/8/8 w - - 0 1"
                        side = side_hint or "w"
                        confidence = min(confidence, 0.2)

                    puzzle = Puzzle(
                        book_id=book.id,
                        page_id=page.id,
                        chapter=chapter,
                        puzzle_number=(f"{puzzle_num}-{i+1}" if puzzle_num and len(candidates) > 1 else puzzle_num),
                        fen=fen,
                        side_to_move=side,
                        source_solution_text=" ".join(san_candidates) if san_candidates else None,
                        parsed_solution_san=parsed_solution,
                        extraction_confidence=confidence,
                        status=status,
                        source_type=source_type,
                        source_debug_json=debug,
                    )
                    session.add(puzzle)
                    session.commit()

                self._mark_book(session, book, "processing", (p["index"] + 1) / total)

            dedupe_count = self._mark_duplicates(session, book.id)
            book.metadata_json = {
                **book.metadata_json,
                "deduplicated": dedupe_count,
                "processed_pages": total,
            }
            self._mark_book(session, book, "ready", 1.0)

            job.status = "done"
            job.stage = "completed"
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()
        except Exception as exc:
            self._mark_book(session, book, "failed", book.extraction_progress, str(exc))
            job.status = "failed"
            job.stage = "error"
            job.message = str(exc)
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()

    def _mark_duplicates(self, session: Session, book_id: int) -> int:
        seen: dict[str, int] = {}
        updates = 0
        puzzles = session.exec(select(Puzzle).where(Puzzle.book_id == book_id)).all()
        for p in puzzles:
            key = f"{p.fen}|{json.dumps(p.parsed_solution_san)}"
            if key in seen:
                p.duplicate_of = seen[key]
                p.status = "duplicate"
                updates += 1
            else:
                seen[key] = p.id or 0
            session.add(p)
        session.commit()
        return updates
