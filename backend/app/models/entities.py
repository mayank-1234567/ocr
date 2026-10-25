from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    file_hash: str = Field(index=True)
    file_path: str
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    import_status: str = Field(default="queued", index=True)
    extraction_progress: float = Field(default=0)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Page(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True)
    page_index: int
    printed_page_number: str | None = None
    extracted_text: str = ""
    ocr_text: str = ""
    layout_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Puzzle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True)
    page_id: int | None = Field(default=None, index=True)
    chapter: str | None = Field(default=None, index=True)
    puzzle_number: str | None = Field(default=None, index=True)
    fen: str | None = None
    side_to_move: str | None = None
    source_solution_text: str | None = None
    parsed_solution_san: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    accepted_alternatives_san: list[list[str]] = Field(default_factory=list, sa_column=Column(JSON))
    extraction_confidence: float = 0
    status: str = Field(default="needs_review", index=True)
    estimated_difficulty: int | None = None
    objective: str | None = None
    duplicate_of: int | None = None
    source_type: str = Field(default="book")
    source_debug_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    puzzle_id: int = Field(index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    moves_played_san: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    correctness: bool
    hints_used: int = 0
    duration_seconds: float = 0
    training_mode: str = Field(index=True)
    cycle_id: int | None = Field(default=None, index=True)
    first_attempt: bool = False


class Cycle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True)
    selected_puzzle_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    cycle_number: int = 1
    start_time: datetime = Field(default_factory=datetime.utcnow)
    completion_time: datetime | None = None
    attempted: int = 0
    solved_first_try: int = 0
    total_attempts: int = 0
    hints_used: int = 0
    total_seconds: float = 0


class ImportJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True)
    status: str = Field(default="queued", index=True)
    stage: str = "queued"
    message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
