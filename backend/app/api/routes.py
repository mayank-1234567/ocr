from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.db.database import engine, get_session
from app.models import Attempt, Book, Cycle, Page, Puzzle
from app.schemas.api import AttemptCreate, CycleClose, CycleCreate, PuzzleRead, PuzzleUpdate, TrainerSessionRequest
from app.services.ingestion_service import IngestionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api")
ingestion = IngestionService()
pdf_service = PDFService()


def _process_book_in_background(book_id: int) -> None:
    with Session(engine) as bg_session:
        ingestion.process_book(bg_session, book_id)


def _book_or_404(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/books/upload")
def upload_book(background: BackgroundTasks, file: UploadFile = File(...), session: Session = Depends(get_session)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = settings.uploads_dir / file.filename
    with file_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    file_hash = pdf_service.file_hash(file_path)
    title = Path(file.filename).stem
    book = Book(title=title, file_hash=file_hash, file_path=str(file_path), import_status="queued")
    session.add(book)
    session.commit()
    session.refresh(book)

    background.add_task(_process_book_in_background, book.id)
    return {"book_id": book.id}


@router.get("/books")
def list_books(session: Session = Depends(get_session)):
    books = session.exec(select(Book).order_by(Book.created_at.desc())).all()
    return books


@router.get("/books/{book_id}")
def get_book(book_id: int, session: Session = Depends(get_session)):
    book = _book_or_404(session, book_id)
    pages = session.exec(select(Page).where(Page.book_id == book_id)).all()
    puzzles = session.exec(select(Puzzle).where(Puzzle.book_id == book_id)).all()
    return {"book": book, "pages": pages, "puzzles": puzzles}


@router.post("/books/{book_id}/reprocess")
def reprocess_book(book_id: int, background: BackgroundTasks, session: Session = Depends(get_session)):
    book = _book_or_404(session, book_id)
    for p in session.exec(select(Puzzle).where(Puzzle.book_id == book_id)).all():
        session.delete(p)
    for p in session.exec(select(Page).where(Page.book_id == book_id)).all():
        session.delete(p)
    session.commit()

    book.import_status = "queued"
    book.extraction_progress = 0
    book.error_message = None
    book.updated_at = datetime.utcnow()
    session.add(book)
    session.commit()

    background.add_task(_process_book_in_background, book.id)
    return {"ok": True}


@router.delete("/books/{book_id}")
def delete_book(book_id: int, session: Session = Depends(get_session)):
    book = _book_or_404(session, book_id)
    for p in session.exec(select(Puzzle).where(Puzzle.book_id == book_id)).all():
        session.delete(p)
    for p in session.exec(select(Page).where(Page.book_id == book_id)).all():
        session.delete(p)
    session.delete(book)
    session.commit()
    try:
        Path(book.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}


@router.get("/puzzles", response_model=list[PuzzleRead])
def list_puzzles(
    book_id: int | None = None,
    chapter: str | None = None,
    status: str | None = None,
    limit: int = Query(200, le=1000),
    session: Session = Depends(get_session),
):
    q = select(Puzzle)
    if book_id is not None:
        q = q.where(Puzzle.book_id == book_id)
    if chapter:
        q = q.where(Puzzle.chapter == chapter)
    if status:
        q = q.where(Puzzle.status == status)
    return session.exec(q.limit(limit)).all()


@router.patch("/puzzles/{puzzle_id}", response_model=PuzzleRead)
def update_puzzle(puzzle_id: int, payload: PuzzleUpdate, session: Session = Depends(get_session)):
    puzzle = session.get(Puzzle, puzzle_id)
    if not puzzle:
        raise HTTPException(404, "Puzzle not found")

    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(puzzle, k, v)
    session.add(puzzle)
    session.commit()
    session.refresh(puzzle)
    return puzzle


@router.post("/trainer/session")
def create_trainer_session(payload: TrainerSessionRequest, session: Session = Depends(get_session)):
    q = select(Puzzle).where(Puzzle.book_id == payload.book_id)
    if payload.chapter:
        q = q.where(Puzzle.chapter == payload.chapter)
    if payload.include_statuses:
        q = q.where(col(Puzzle.status).in_(payload.include_statuses))

    puzzles = session.exec(q).all()
    if payload.mode == "random":
        import random

        random.shuffle(puzzles)
    else:
        puzzles.sort(key=lambda p: ((p.chapter or ""), (p.puzzle_number or ""), p.id or 0))
    return {"puzzle_ids": [p.id for p in puzzles if p.id], "count": len(puzzles)}


@router.post("/attempts")
def log_attempt(payload: AttemptCreate, session: Session = Depends(get_session)):
    attempt = Attempt(**payload.model_dump())
    session.add(attempt)

    if payload.cycle_id:
        cycle = session.get(Cycle, payload.cycle_id)
        if cycle:
            cycle.total_attempts += 1
            cycle.attempted += 1
            cycle.hints_used += payload.hints_used
            cycle.total_seconds += payload.duration_seconds
            if payload.correctness and payload.first_attempt:
                cycle.solved_first_try += 1
            session.add(cycle)

    session.commit()
    return {"ok": True}


@router.post("/cycles")
def create_cycle(payload: CycleCreate, session: Session = Depends(get_session)):
    cycle = Cycle(**payload.model_dump())
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    return cycle


@router.post("/cycles/close")
def close_cycle(payload: CycleClose, session: Session = Depends(get_session)):
    cycle = session.get(Cycle, payload.cycle_id)
    if not cycle:
        raise HTTPException(404, "Cycle not found")
    cycle.completion_time = datetime.utcnow()
    session.add(cycle)
    session.commit()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    puzzles = session.exec(select(Puzzle)).all()
    total_puzzles = len(puzzles)
    verified_puzzles = len([p for p in puzzles if p.status == "verified"])
    attempts_rows = session.exec(select(Attempt)).all()
    total_attempts = len(attempts_rows)
    correct_attempts = len([a for a in attempts_rows if a.correctness])
    avg_seconds = (sum(a.duration_seconds for a in attempts_rows) / total_attempts) if total_attempts else 0
    by_book = session.exec(
        select(Book.title, func.count(Puzzle.id), func.avg(Puzzle.extraction_confidence))
        .join(Puzzle, Puzzle.book_id == Book.id)
        .group_by(Book.title)
    ).all()

    return {
        "total_puzzles": total_puzzles,
        "verified_puzzles": verified_puzzles,
        "attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "avg_seconds": avg_seconds,
        "books": [{"title": b[0], "puzzles": b[1], "avg_confidence": b[2]} for b in by_book],
    }
