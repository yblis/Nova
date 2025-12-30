"""
RAG Background Tasks - Traitement asynchrone des documents PDF
Ce module est exécuté par le worker RQ, SANS contexte Flask.
"""

import os
import traceback
import psycopg2

# Configuration depuis les variables d'environnement (pas de Flask context)
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@ollamanager-postgres:5432/ollamanager")
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))


def get_standalone_db_connection():
    """Connexion DB standalone (sans Flask context)."""
    return psycopg2.connect(POSTGRES_URL)


def update_document_status(doc_id: str, status: str, error_message: str = None, 
                           chunk_count: int = 0, embedding_model: str = None, 
                           embedding_dimensions: int = None):
    """Met à jour le statut d'un document en base (standalone)."""
    conn = get_standalone_db_connection()
    cur = conn.cursor()
    try:
        sql = "UPDATE rag_documents SET status = %s"
        params = [status]
        
        if error_message:
            sql += ", error_message = %s"
            params.append(error_message)
            
        if chunk_count > 0:
            sql += ", chunk_count = %s"
            params.append(chunk_count)
            
        if embedding_model:
            sql += ", embedding_model = %s"
            params.append(embedding_model)
            
        if embedding_dimensions:
            sql += ", embedding_dimensions = %s"
            params.append(embedding_dimensions)
            
        sql += " WHERE id = %s"
        params.append(doc_id)
        
        cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error updating document status: {e}")
    finally:
        cur.close()
        conn.close()


def process_document_background(doc_id: str, session_id: str, filename: str, file_path: str):
    """
    Tâche d'arrière-plan pour traiter un document PDF (OCR + Embedding).
    Exécuté par le worker RQ, SANS contexte Flask.
    """
    print(f"Starting background processing for document {doc_id} ({filename})")
    update_document_status(doc_id, "processing")
    
    try:
        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        
        # Import des services (ils utilisent current_app, donc on doit créer un context)
        # On va créer une mini-app Flask juste pour le context
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from app.services.ocr_service import process_pdf_intelligent
            from app.services.embedding_service import generate_embeddings_batch, get_embedding_model
            from app.services.rag_service import use_qdrant, _store_chunks_postgres
            from app.services.rag_config_service import get_setting
            
            chunk_size = get_setting("chunk_size", RAG_CHUNK_SIZE)
            chunk_overlap = get_setting("chunk_overlap", RAG_CHUNK_OVERLAP)
            
            ocr_provider_setting = get_setting("ocr_provider", "")
            ocr_model = get_setting("ocr_model", "")
            
            if ocr_provider_setting and ":" in ocr_provider_setting:
                ocr_provider = ocr_provider_setting.split(":")[0]
            else:
                ocr_provider = "auto"

            embedding_model = get_embedding_model()
            if not embedding_model:
                raise ValueError("No embedding model configured")

            # OCR / Extraction
            print(f"Extracting text from {filename}...")
            result = process_pdf_intelligent(
                pdf_bytes=pdf_bytes,
                filename=filename,
                ocr_provider=ocr_provider,
                ocr_model=ocr_model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            chunks = result.get("chunks", [])
            if not chunks:
                msg = f"No text extracted. Type: {result.get('pdf_type', 'unknown')}"
                update_document_status(doc_id, "failed", error_message=msg)
                print(f"Document {doc_id} failed: {msg}")
                return

            print(f"Extracted {len(chunks)} chunks. Generating embeddings...")
            
            # Embeddings
            chunk_texts = [c['content'] for c in chunks]
            embeddings = generate_embeddings_batch(chunk_texts, embedding_model)
            
            if not embeddings or len(embeddings) != len(chunks):
                raise ValueError("Failed to generate embeddings")
                
            # Dimensions
            embedding_dimensions = len(embeddings[0]) if embeddings else 0
            
            # Stockage des chunks
            if use_qdrant():
                try:
                    from app.services.qdrant_service import store_chunks
                    store_chunks(
                        session_id=session_id,
                        document_id=doc_id,
                        filename=filename,
                        chunks=chunks,
                        embeddings=embeddings
                    )
                    print(f"Chunks stored in Qdrant for doc {doc_id}")
                except Exception as e:
                    print(f"Qdrant failed, fallback to PG: {e}")
                    _store_chunks_postgres(doc_id, chunks, embeddings)
            else:
                _store_chunks_postgres(doc_id, chunks, embeddings)

            # Mise à jour finale
            update_document_status(
                doc_id, 
                "completed", 
                chunk_count=len(chunks),
                embedding_model=embedding_model,
                embedding_dimensions=embedding_dimensions
            )
            print(f"Document {doc_id} processed successfully with {len(chunks)} chunks.")

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        update_document_status(doc_id, "failed", error_message=str(e))
