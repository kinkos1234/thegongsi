-- pgvector 확장 초기화 (PostgreSQL).
-- 실행:  psql $DATABASE_URL -f scripts/init_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- embeddings 테이블이 SQLAlchemy로 create_all 되었다 가정 → HNSW 인덱스만 수동 생성.
-- 3072차원은 기본 HNSW 지원 외 — halfvec 또는 파티셔닝 고려 (Phase 2).
-- 현재는 단순 btree만.

CREATE INDEX IF NOT EXISTS ix_embeddings_source
    ON embeddings (source_type, source_id, chunk_idx);

-- 벡터 유사도 인덱스 (1536 이하 차원에서만 HNSW 기본 지원).
-- text-embedding-3-large(3072)는 Phase 2에서 halfvec 마이그레이션.
