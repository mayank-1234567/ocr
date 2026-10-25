from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class BookRead(BaseModel):
    id: int
    title: str
    import_status: str
    extraction_progress: float
    created_at: datetime
    metadata_json: dict[str, Any]


class PuzzleRead(BaseModel):
    id: int
    book_id: int
    chapter: str | None
    puzzle_number: str | None
    fen: str | None
    side_to_move: str | None
    source_solution_text: str | None
    parsed_solution_san: list[str]
    accepted_alternatives_san: list[list[str]]
    extraction_confidence: float
    status: str
    estimated_difficulty: int | None
    objective: str | None
    source_type: str


class PuzzleUpdate(BaseModel):
    fen: str | None = None
    side_to_move: str | None = None
    source_solution_text: str | None = None
    parsed_solution_san: list[str] | None = None
    accepted_alternatives_san: list[list[str]] | None = None
    status: str | None = None
    objective: str | None = None


class AttemptCreate(BaseModel):
    puzzle_id: int
    moves_played_san: list[str]
    correctness: bool
    hints_used: int = 0
    duration_seconds: float = 0
    training_mode: str
    cycle_id: int | None = None
    first_attempt: bool = False


class CycleCreate(BaseModel):
    book_id: int
    selected_puzzle_ids: list[int]
    cycle_number: int


class CycleClose(BaseModel):
    cycle_id: int


class TrainerSessionRequest(BaseModel):
    book_id: int
    chapter: str | None = None
    mode: str = "sequential"
    include_statuses: list[str] = ["verified", "needs_review", "engine_generated"]
