"""
RAG Service - Gestion des documents et recherche sémantique

Supporte deux backends :
- PostgreSQL/pgvector (fallback, toujours disponible)
- Qdrant (recommandé pour recherche hybride haute performance)

Le backend est sélectionné via la config RAG_USE_QDRANT.
"""

import os
import uuid
from typing import List, Dict, Optional, Tuple
from flask import current_app
import psycopg2
from psycopg2.extras import RealDictCursor


# Variable globale pour le pool de connexions
_db_initialized = False


def use_qdrant() -> bool:
    """Vérifie si Qdrant doit être utilisé comme backend."""
    if not current_app.config.get("RAG_USE_QDRANT", True):
        return False
    
    try:
        from .qdrant_service import is_qdrant_available
        return is_qdrant_available()
    except Exception:
        return False


def get_db_connection(register_vec=True):
    """
    Crée une connexion à PostgreSQL.
    
    Args:
        register_vec: Si True, enregistre le type vector (nécessite extension)
    """
    conn = psycopg2.connect(current_app.config["POSTGRES_URL"])
    if register_vec:
        try:
            from pgvector.psycopg2 import register_vector
            register_vector(conn)
        except Exception as e:
            current_app.logger.warning(f"Could not register vector type: {e}")
    return conn


def init_db():
    """
    Initialise la base de données avec les tables et extensions nécessaires.
    À appeler au démarrage de l'application.
    """
    global _db_initialized
    
    if _db_initialized:
        return
    
    try:
        # Première connexion SANS register_vector pour créer l'extension
        conn = get_db_connection(register_vec=False)
        cur = conn.cursor()
        
        # Extension pgvector - DOIT être créée en premier
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        
        current_app.logger.info("pgvector extension created/verified")
        
        cur.close()
        conn.close()
        
        # Deuxième connexion AVEC register_vector maintenant que l'extension existe
        conn = get_db_connection(register_vec=True)
        cur = conn.cursor()
        
        # Table documents - stocke les métadonnées des PDFs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rag_documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT NOW(),
                chunk_count INTEGER DEFAULT 0,
                embedding_model VARCHAR(255),
                embedding_dimensions INTEGER,
                status VARCHAR(50) DEFAULT 'completed',
                error_message TEXT
            );
        """)

        # Migration automatique : Ajout des colonnes si elles manquent
        cur.execute("ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'completed';")
        cur.execute("ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS error_message TEXT;")
        
        # Index sur session_id pour les lookups rapides
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_documents_session 
            ON rag_documents(session_id);
        """)
        
        # Table chunks - stocke les morceaux de texte avec leurs embeddings
        # On utilise vector(2048) pour supporter différentes dimensions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES rag_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector(2048),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Index sur document_id
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_chunks_document 
            ON rag_chunks(document_id);
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        _db_initialized = True
        current_app.logger.info("RAG database initialized successfully")
        
    except Exception as e:
        current_app.logger.error(f"Error initializing RAG database: {e}")
        raise


def store_document(
    session_id: str,
    filename: str,
    file_path: str,
    chunks: List[Dict] = None,
    embeddings: List[List[float]] = None,
    embedding_model: str = None,
    embedding_dimensions: int = None,
    status: str = 'completed'
) -> str:
    """
    Stocke un document avec ses chunks et embeddings.
    
    Utilise Qdrant si disponible, sinon PostgreSQL.
    
    Args:
        session_id: ID de la session chat
        filename: Nom du fichier
        file_path: Chemin vers le fichier stocké
        chunks: Liste de dicts avec 'index' et 'content'
        embeddings: Liste d'embeddings (même ordre que chunks)
        embedding_model: Nom du modèle utilisé
        embedding_dimensions: Dimensions des embeddings
        
    Returns:
        ID du document créé
    """
    doc_id = str(uuid.uuid4())
    
    # Toujours stocker les métadonnées dans PostgreSQL
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Insérer le document dans PostgreSQL (métadonnées)
        cur.execute("""
            INSERT INTO rag_documents 
            (id, session_id, filename, file_path, chunk_count, embedding_model, embedding_dimensions, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (doc_id, session_id, filename, file_path, len(chunks) if chunks else 0, embedding_model, embedding_dimensions, status))
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error storing document metadata: {e}")
        raise
    finally:
        cur.close()
        conn.close()
    
    
    # Si pas de chunks (initialisation pending), on s'arrête là
    if not chunks:
        return doc_id

    # Stocker les chunks dans Qdrant ou PostgreSQL
    if use_qdrant():
        try:
            from .qdrant_service import store_chunks
            store_chunks(
                session_id=session_id,
                document_id=doc_id,
                filename=filename,
                chunks=chunks,
                embeddings=embeddings
            )
            current_app.logger.info(f"Document {doc_id} stored in Qdrant")
        except Exception as e:
            current_app.logger.warning(f"Qdrant storage failed, falling back to PostgreSQL: {e}")
            _store_chunks_postgres(doc_id, chunks, embeddings)
    else:
        _store_chunks_postgres(doc_id, chunks, embeddings)
    
    return doc_id


def _store_chunks_postgres(doc_id: str, chunks: List[Dict], embeddings: List[List[float]]):
    """Stocke les chunks dans PostgreSQL (fallback)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        for chunk, embedding in zip(chunks, embeddings):
            if embedding:
                padded_embedding = pad_embedding(embedding, 2048)
                cur.execute("""
                    INSERT INTO rag_chunks (document_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s)
                """, (doc_id, chunk['index'], chunk['content'], padded_embedding))
        
        conn.commit()
        current_app.logger.info(f"Document {doc_id} chunks stored in PostgreSQL")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error storing chunks in PostgreSQL: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def pad_embedding(embedding: List[float], target_dim: int) -> List[float]:
    """Pad ou truncate un embedding à la dimension cible."""
    if len(embedding) >= target_dim:
        return embedding[:target_dim]
    return embedding + [0.0] * (target_dim - len(embedding))


def search_similar(
    session_id: str,
    query_embedding: List[float],
    top_k: int = 5,
    embedding_dimensions: Optional[int] = None,
    document_id: Optional[str] = None
) -> List[Dict]:
    """
    Recherche les chunks les plus similaires à la query.
    
    Utilise Qdrant si disponible, sinon PostgreSQL.
    
    Args:
        session_id: ID de la session
        query_embedding: Embedding de la query
        top_k: Nombre de résultats
        embedding_dimensions: Dimensions de l'embedding (pour le padding)
        document_id: ID du document optionnel pour filtrer
        
    Returns:
        Liste de dicts avec 'content', 'filename', 'score'
    """
    # Essayer Qdrant d'abord
    if use_qdrant():
        try:
            from .qdrant_service import search_similar as qdrant_search
            results = qdrant_search(
                session_id=session_id,
                query_embedding=query_embedding,
                top_k=top_k,
                document_id=document_id
            )
            if results:
                return results
        except Exception as e:
            current_app.logger.warning(f"Qdrant search failed, falling back to PostgreSQL: {e}")
    
    # Fallback PostgreSQL
    return _search_similar_postgres(session_id, query_embedding, top_k, document_id)


def _search_similar_postgres(
    session_id: str,
    query_embedding: List[float],
    top_k: int = 5,
    document_id: Optional[str] = None
) -> List[Dict]:
    """Recherche dans PostgreSQL (fallback)."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Pad l'embedding de la query
        padded_query = pad_embedding(query_embedding, 2048)
        
        # Construction de la requête
        query_sql = """
            SELECT 
                c.content,
                c.chunk_index,
                d.filename,
                1 - (c.embedding <=> %s::vector) as similarity
            FROM rag_chunks c
            JOIN rag_documents d ON c.document_id = d.id
            WHERE d.session_id = %s
        """
        params = [padded_query, session_id]
        
        if document_id:
            query_sql += " AND c.document_id = %s"
            params.append(document_id)
            
        query_sql += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
        params.extend([padded_query, top_k])
        
        cur.execute(query_sql, tuple(params))
        
        results = []
        for row in cur.fetchall():
            results.append({
                'content': row['content'],
                'filename': row['filename'],
                'chunk_index': row['chunk_index'],
                'score': float(row['similarity']) if row['similarity'] else 0
            })
        
        return results
        
    except Exception as e:
        current_app.logger.error(f"Error searching similar chunks: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_context_for_query(session_id: str, query: str) -> Tuple[str, List[Dict]]:
    """
    Génère le contexte RAG pour une query.
    
    Args:
        session_id: ID de la session
        query: Question de l'utilisateur
        
    Returns:
        Tuple (contexte formaté, sources utilisées)
    """
    from .embedding_service import generate_embedding, get_embedding_model
    
    # Vérifier si un modèle d'embedding est configuré
    embedding_model = get_embedding_model()
    if not embedding_model:
        return "", []
    
    # Vérifier si la session a des documents
    if not has_documents(session_id):
        return "", []
    
    # Générer l'embedding de la query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return "", []
    
    # Rechercher les chunks similaires
    top_k = current_app.config.get("RAG_TOP_K", 5)
    similar_chunks = search_similar(session_id, query_embedding, top_k)
    
    if not similar_chunks:
        return "", []
    
    # Formater le contexte
    context_parts = ["### Contexte documentaire pertinent:\n"]
    for i, chunk in enumerate(similar_chunks, 1):
        context_parts.append(f"[Source {i}: {chunk['filename']}]\n{chunk['content']}\n")
    
    context = "\n".join(context_parts)
    
    return context, similar_chunks


def has_documents(session_id: str) -> bool:
    """Vérifie si une session a des documents attachés."""
    try:
        conn = get_db_connection(register_vec=False)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT COUNT(*) FROM rag_documents WHERE session_id = %s",
            (session_id,)
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count > 0
    except Exception:
        return False


def list_documents(session_id: str) -> List[Dict]:
    """
    Liste les documents attachés à une session.
    
    Returns:
        Liste de dicts avec info sur les documents
    """
    try:
        conn = get_db_connection(register_vec=False)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, filename, created_at, chunk_count, embedding_model, status, error_message
            FROM rag_documents
            WHERE session_id = %s
            ORDER BY created_at DESC
        """, (session_id,))
        
        result = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return result
        
    except Exception as e:
        current_app.logger.error(f"Error listing documents: {e}")
        return []


def delete_document(document_id: str) -> bool:
    """
    Supprime un document et ses chunks (cascade).
    Supprime aussi le fichier physique.
    
    Returns:
        True si succès
    """
    conn = get_db_connection(register_vec=False)
    cur = conn.cursor()
    
    try:
        # Récupérer le chemin du fichier avant suppression
        cur.execute(
            "SELECT file_path FROM rag_documents WHERE id = %s",
            (document_id,)
        )
        result = cur.fetchone()
        
        if result and result[0]:
            file_path = result[0]
            # Supprimer le fichier physique
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Supprimer le document (cascade supprime les chunks)
        cur.execute("DELETE FROM rag_documents WHERE id = %s", (document_id,))
        conn.commit()
        
        return True
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting document: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def delete_session_documents(session_id: str) -> bool:
    """
    Supprime tous les documents d'une session.
    
    Returns:
        True si succès
    """
    conn = get_db_connection(register_vec=False)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer les chemins des fichiers
        cur.execute(
            "SELECT file_path FROM rag_documents WHERE session_id = %s",
            (session_id,)
        )
        
        for row in cur.fetchall():
            if row['file_path'] and os.path.exists(row['file_path']):
                os.remove(row['file_path'])
        
        # Supprimer les documents
        cur.execute(
            "DELETE FROM rag_documents WHERE session_id = %s",
            (session_id,)
        )
        conn.commit()
        
        return True
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting session documents: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_document_chunks(document_id: str) -> List[Dict]:
    """
    Récupère tous les chunks d'un document.
    Utilise Qdrant si disponible, sinon PostgreSQL.
    
    Returns:
        Liste de dicts avec 'id', 'chunk_index', 'content', 'size'
    """
    # Essayer Qdrant d'abord
    if use_qdrant():
        try:
            from .qdrant_service import get_document_chunks as qdrant_get_chunks
            chunks = qdrant_get_chunks(document_id)
            if chunks:
                return chunks
        except Exception as e:
            current_app.logger.warning(f"Qdrant get_document_chunks failed: {e}")
    
    # Fallback PostgreSQL
    conn = get_db_connection(register_vec=False)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT id, chunk_index, content, length(content) as size
            FROM rag_chunks
            WHERE document_id = %s
            ORDER BY chunk_index ASC
        """, (document_id,))
        
        return [dict(row) for row in cur.fetchall()]
        
    except Exception as e:
        current_app.logger.error(f"Error getting document chunks: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def delete_chunk(chunk_id: str) -> bool:
    """
    Supprime un chunk spécifique.
    """
    conn = get_db_connection(register_vec=False)
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM rag_chunks WHERE id = %s", (chunk_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting chunk: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_document_stats(document_id: str) -> Dict:
    """
    Récupère les statistiques d'un document.
    Fonctionne avec Qdrant ou PostgreSQL.
    """
    stats = {
        "total_chunks": 0,
        "avg_chunk_size": 0,
        "total_size": 0,
        "estimated_tokens": 0
    }
    
    try:
        # Utilise get_document_chunks qui gère Qdrant/PG
        chunks = get_document_chunks(document_id)
        
        if chunks:
            sizes = [c.get("size", len(c.get("content", ""))) for c in chunks]
            stats["total_chunks"] = len(chunks)
            stats["total_size"] = sum(sizes)
            stats["avg_chunk_size"] = round(stats["total_size"] / len(chunks), 2) if chunks else 0
            # Estimate tokens: ~1 token per 4 characters for most languages
            stats["estimated_tokens"] = round(stats["total_size"] / 4)
            
    except Exception as e:
        current_app.logger.error(f"Error getting document stats: {e}")
    
    return stats


def get_document_metadata(document_id: str) -> Optional[Dict]:
    """Récupère les métadonnées d'un document."""
    conn = get_db_connection(register_vec=False)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT id, session_id, filename, chunk_count, embedding_model
            FROM rag_documents
            WHERE id = %s
        """, (document_id,))
        
        row = cur.fetchone()
        return dict(row) if row else None
        
    except Exception as e:
        current_app.logger.error(f"Error getting document metadata: {e}")
        return None
    finally:
        cur.close()
        conn.close()
