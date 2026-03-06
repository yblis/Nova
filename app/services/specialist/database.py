import psycopg2
from psycopg2.extras import RealDictCursor
from flask import current_app


_db_initialized = False


def get_db_connection():
    return psycopg2.connect(current_app.config["POSTGRES_URL"])


def pad_embedding(embedding: list, target_dim: int = 2048) -> list:
    if len(embedding) >= target_dim:
        return embedding[:target_dim]
    return embedding + [0.0] * (target_dim - len(embedding))


def init_db():
    global _db_initialized
    if _db_initialized:
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS specialists (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    system_prompt TEXT NOT NULL,
                    model VARCHAR(255),
                    avatar_url TEXT,
                    color VARCHAR(20) DEFAULT '#6366f1',
                    provider_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS specialist_knowledge (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    specialist_id UUID REFERENCES specialists(id) ON DELETE CASCADE,
                    type VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    content TEXT,
                    file_path TEXT,
                    metadata JSONB DEFAULT '{}',
                    embedding_model VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS specialist_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    knowledge_id UUID REFERENCES specialist_knowledge(id) ON DELETE CASCADE,
                    specialist_id UUID REFERENCES specialists(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(2048),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            try:
                cur.execute("""
                    ALTER TABLE specialist_chunks
                    ALTER COLUMN embedding TYPE vector(2048)
                """)
            except Exception:
                pass

            cur.execute("""
                CREATE TABLE IF NOT EXISTS specialist_tools (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    specialist_id UUID REFERENCES specialists(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    config JSONB NOT NULL DEFAULT '{}',
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS specialist_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    specialist_id UUID REFERENCES specialists(id) ON DELETE CASCADE,
                    user_id VARCHAR(255) NOT NULL,
                    title VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS specialist_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES specialist_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    sources JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_specialists_user_id ON specialists(user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_specialist_knowledge_specialist_id
                ON specialist_knowledge(specialist_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_specialist_chunks_specialist_id
                ON specialist_chunks(specialist_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_specialist_sessions_specialist_id
                ON specialist_sessions(specialist_id)
            """)

            try:
                cur.execute("""
                    ALTER TABLE specialists
                    ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT 'computer'
                """)
            except Exception:
                pass

            try:
                cur.execute("""
                    ALTER TABLE specialists
                    ADD COLUMN IF NOT EXISTS provider_id VARCHAR(255)
                """)
            except Exception:
                pass

            conn.commit()
            _db_initialized = True
            current_app.logger.info("Specialist tables initialized")

    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error initializing specialist tables: {e}")
        raise
    finally:
        conn.close()
