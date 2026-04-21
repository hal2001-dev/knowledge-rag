CREATE TABLE IF NOT EXISTS documents (
    doc_id      TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    source      TEXT DEFAULT '',
    file_type   TEXT DEFAULT 'pdf',
    chunk_count INTEGER DEFAULT 0,
    has_tables  BOOLEAN DEFAULT FALSE,
    has_images  BOOLEAN DEFAULT FALSE,
    indexed_at  TIMESTAMPTZ DEFAULT NOW(),
    status      TEXT DEFAULT 'done'
);
