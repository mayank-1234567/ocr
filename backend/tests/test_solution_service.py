from app.services.solution_service import SolutionService


def test_extract_and_validate_san_line():
    svc = SolutionService()
    text = "1. Bxf7+ Kxf7 2. Nxe5+"
    moves = svc.extract_san_candidates(text)
    assert moves[:3] == ["Bxf7+", "Kxf7", "Nxe5+"]

    ok, normalized = svc.validate_san_line("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1", moves[:3])
    assert ok is True
    assert len(normalized) == 3
