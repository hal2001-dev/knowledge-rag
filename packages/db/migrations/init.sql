CREATE TABLE IF NOT EXISTS documents (
    doc_id               TEXT PRIMARY KEY,
    title                TEXT NOT NULL,
    source               TEXT DEFAULT '',
    file_type            TEXT DEFAULT 'pdf',
    content_hash         VARCHAR(64) UNIQUE,
    chunk_count          INTEGER DEFAULT 0,
    has_tables           BOOLEAN DEFAULT FALSE,
    has_images           BOOLEAN DEFAULT FALSE,
    indexed_at           TIMESTAMPTZ DEFAULT NOW(),
    status               TEXT DEFAULT 'done',
    summary              JSONB,
    summary_model        TEXT,
    summary_generated_at TIMESTAMPTZ,
    doc_type             VARCHAR(16) NOT NULL DEFAULT 'book'
        CHECK (doc_type IN ('book','article','paper','note','report','web','other')),
    category             VARCHAR(64),
    category_confidence  REAL,
    tags                 JSONB DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS ix_documents_doc_type     ON documents(doc_type);
CREATE INDEX IF NOT EXISTS ix_documents_category     ON documents(category);
