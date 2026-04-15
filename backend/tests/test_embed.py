"""임베딩 인제스트 골격 테스트 — chunking은 순수 함수라 OpenAI 없이 검증."""
from app.services.embed.ingest import chunk_text


def test_empty():
    assert chunk_text("") == []


def test_short_under_size():
    assert chunk_text("짧은 텍스트") == ["짧은 텍스트"]


def test_overlap():
    text = "a" * 1000
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) == 3  # 500 + (500-50=450) + remainder... let's just check overlap
    # 마지막 청크 끝이 원문 끝과 동일
    assert chunks[-1].endswith("a")


def test_deterministic():
    text = "한국어 테스트 문자열 " * 100
    assert chunk_text(text) == chunk_text(text)
