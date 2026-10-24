CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pericopes (
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

CREATE TABLE IF NOT EXISTS verses (
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
CREATE INDEX IF NOT EXISTS idx_pericopes_embedding ON pericopes USING hnsw (embedding vector_l2_ops);
CREATE INDEX IF NOT EXISTS idx_verses_embedding ON verses USING hnsw (embedding vector_l2_ops);

-- Multi-Tradition Commentaries and Non-Biblical Historical Corpora
CREATE TABLE IF NOT EXISTS commentaries (
    id VARCHAR(255) PRIMARY KEY,
    tradition VARCHAR(50) NOT NULL, -- 'midrash', 'patristic', 'historical'
    author VARCHAR(100),            -- 'Genesis Rabbah', 'Flavius Josephus', 'John Chrysostom', 'Augustine'
    work VARCHAR(150),              -- 'Midrash Rabbah', 'Antiquities of the Jews', 'Homilies on Genesis'
    reference VARCHAR(150),         -- 'Genesis Rabbah 22:5', 'Antiquities 1.2.1', 'Homily 47'
    book VARCHAR(100),              -- 'Genesis'
    chapter_start INTEGER,
    verse_start INTEGER,
    chapter_end INTEGER,
    verse_end INTEGER,
    title TEXT,
    text TEXT NOT NULL,             -- English translation
    original_language_text TEXT,    -- Original Hebrew/Aramaic or Greek/Latin if available
    linked_pericope_ids TEXT[],     -- Associated pericope IDs (e.g. ['gen-4-1-16-pericope'])
    metadata JSONB,                 -- Extra attributes
    embedding vector(768)           -- dense vector representation via gemini-embedding-2
);

CREATE INDEX IF NOT EXISTS idx_commentaries_embedding ON commentaries USING hnsw (embedding vector_l2_ops);
CREATE INDEX IF NOT EXISTS idx_commentaries_tradition ON commentaries (tradition);
CREATE INDEX IF NOT EXISTS idx_commentaries_author ON commentaries (author);

