"""임베딩 인제스트 골격.

플로우: 공시/뉴스 텍스트 → 청킹 → OpenAI text-embedding-3-large → pgvector 저장.
재인덱싱 방지 위해 (source_type, source_id, chunk_idx) 유니크.

현재 skeleton — 실제 OpenAI 호출은 API 키 확보 후 활성화.
"""
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500  # 글자 기준, 공시·뉴스 짧으므로 충분
CHUNK_OVERLAP = 50


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """문자열 단순 슬라이싱. 한국어 문장 경계 인식은 Phase 2."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


async def embed_batch(texts: list[str], model: str = "text-embedding-3-large") -> list[list[float]]:
    """OpenAI 배치 임베딩. 키 없으면 RuntimeError."""
    # TODO: openai 클라이언트 연결
    raise RuntimeError("Embedding 인제스트는 OpenAI 키 확보 후 활성화")


async def ingest_disclosure(rcept_no: str, text: str) -> dict:
    """공시 1건 → chunk + embed + store."""
    chunks = chunk_text(text)
    logger.info(f"Disclosure {rcept_no}: {len(chunks)} chunks")
    # TODO: 벡터 생성 + DB 저장
    return {"rcept_no": rcept_no, "chunks": len(chunks), "status": "stub"}
