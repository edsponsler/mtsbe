CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE pericopes (
    id VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'pericope',
    corpus VARCHAR(100),
    book VARCHAR(100),
    chapter_start INTEGER,
    verse_start INTEGER,
    chapter_end INTEGER,
    verse_end INTEGER,
    pericope_title TEXT,
    text TEXT,
    child_verse_ids TEXT[],
    external_links JSONB,
    embedding vector(768) -- Update dimensions based on embedding model used (e.g., 768 for text-embedding-004)
);

CREATE TABLE verses (
    id VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50) NOT NULL DEFAULT 'verse',
    corpus VARCHAR(100),
    book VARCHAR(100),
    chapter INTEGER,
    verse INTEGER,
    text TEXT,
    parent_pericope_id VARCHAR(255) REFERENCES pericopes(id),
    embedding vector(768)
);

-- HNSW index for fast similarity search
CREATE INDEX ON pericopes USING hnsw (embedding vector_l2_ops);
CREATE INDEX ON verses USING hnsw (embedding vector_l2_ops);
