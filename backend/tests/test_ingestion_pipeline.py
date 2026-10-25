from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Book, Puzzle
from app.services.ingestion_service import IngestionService


def make_pdf(path: Path):
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, "Chapter 1: Warmup")
    c.drawString(72, 700, "Puzzle 1")
    c.drawString(72, 680, "FEN r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq")
    c.drawString(72, 660, "1. Bxf7+ Kxf7 2. Nxe5+")
    c.save()


def test_ingestion_extracts_puzzle(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        book = Book(title="sample", file_hash="x", file_path=str(pdf))
        session.add(book)
        session.commit()
        session.refresh(book)

        IngestionService().process_book(session, book.id)
        puzzles = session.exec(select(Puzzle)).all()

        assert puzzles
        assert puzzles[0].fen is not None
        assert puzzles[0].status in {"verified", "engine_generated", "needs_review"}
