import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Admin
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")


    # Flask-Caching
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "60"))
    CACHE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Timeouts (seconds)
    HTTP_CONNECT_TIMEOUT = float(os.getenv("HTTP_CONNECT_TIMEOUT", "10"))
    HTTP_READ_TIMEOUT = float(os.getenv("HTTP_READ_TIMEOUT", "300"))

    # RQ job timeout for worker tasks (seconds)
    RQ_DEFAULT_JOB_TIMEOUT = int(os.getenv("RQ_DEFAULT_JOB_TIMEOUT", "3600"))

    # Fallback base dir for Ollama blobs when /api/blobs doesn't return a path
    OLLAMA_BLOBS_BASE_DIR = os.getenv("OLLAMA_BLOBS_BASE_DIR", "")

    # PostgreSQL for RAG
    POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://ollama:ollama_rag@localhost:5432/ollama_rag")

    # Qdrant for advanced RAG (hybrid search)
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_documents")

    # RAG Configuration
    RAG_UPLOADS_DIR = os.getenv("RAG_UPLOADS_DIR", "/app/rag_uploads")
    RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
    
    # RAG OCR Configuration
    RAG_OCR_PROVIDER = os.getenv("RAG_OCR_PROVIDER", "auto")  # auto, gemini, openai, ollama, tesseract
    RAG_OCR_THRESHOLD = int(os.getenv("RAG_OCR_THRESHOLD", "50"))  # Min chars/page to consider PDF native
    RAG_USE_QDRANT = os.getenv("RAG_USE_QDRANT", "true").lower() == "true"  # Use Qdrant instead of pgvector

