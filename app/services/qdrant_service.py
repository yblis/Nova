"""
Qdrant Service - Gestion de la base vectorielle hybride pour RAG avancé

Ce service gère :
- Connexion et initialisation de Qdrant
- Création/gestion des collections
- Indexation des documents avec vecteurs denses
- Recherche hybride (dense + filtres)
- Fallback vers PostgreSQL/pgvector si Qdrant indisponible
"""

from typing import List, Dict, Optional, Any
import uuid
from flask import current_app


# Dimensions des modèles d'embedding courants
EMBEDDING_DIMENSIONS = {
    'nomic-embed-text': 768,
    'all-minilm': 384,
    'mxbai-embed-large': 1024,
    'snowflake-arctic-embed': 1024,
    'bge-m3': 1024,
    'bge-large': 1024,
    'text-embedding-3-small': 1536,
    'text-embedding-3-large': 3072,
    'text-embedding-ada-002': 1536,
}


def get_qdrant_client():
    """
    Crée et retourne un client Qdrant.
    
    Returns:
        QdrantClient instance
        
    Raises:
        Exception si Qdrant n'est pas disponible
    """
    from qdrant_client import QdrantClient
    
    url = current_app.config.get("QDRANT_URL", "http://localhost:6333")
    
    client = QdrantClient(url=url)
    
    # Vérifier la connexion
    client.get_collections()
    
    return client


def is_qdrant_available() -> bool:
    """Vérifie si Qdrant est disponible."""
    try:
        get_qdrant_client()
        return True
    except Exception as e:
        current_app.logger.warning(f"Qdrant not available: {e}")
        return False


def init_collection(
    collection_name: Optional[str] = None,
    vector_size: int = 768,
    recreate: bool = False
) -> bool:
    """
    Initialise une collection Qdrant pour le RAG.
    
    Args:
        collection_name: Nom de la collection (défaut depuis config)
        vector_size: Dimension des vecteurs
        recreate: Si True, recrée la collection si elle existe
        
    Returns:
        True si succès
    """
    from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Vérifier si la collection existe
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)
    
    if exists and not recreate:
        current_app.logger.info(f"Collection '{collection_name}' already exists")
        return True
    
    if exists and recreate:
        client.delete_collection(collection_name)
        current_app.logger.info(f"Deleted existing collection '{collection_name}'")
    
    # Créer la collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE
        )
    )
    
    # Créer les index pour les payloads
    client.create_payload_index(
        collection_name=collection_name,
        field_name="session_id",
        field_schema=PayloadSchemaType.KEYWORD
    )
    
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_id",
        field_schema=PayloadSchemaType.KEYWORD
    )
    
    current_app.logger.info(f"Created collection '{collection_name}' with vector size {vector_size}")
    return True


def store_chunks(
    session_id: str,
    document_id: str,
    filename: str,
    chunks: List[Dict],
    embeddings: List[List[float]],
    collection_name: Optional[str] = None
) -> int:
    """
    Stocke des chunks avec leurs embeddings dans Qdrant.
    
    Args:
        session_id: ID de la session
        document_id: ID du document
        filename: Nom du fichier
        chunks: Liste de dicts avec 'index' et 'content'
        embeddings: Liste d'embeddings correspondants
        collection_name: Nom de la collection
        
    Returns:
        Nombre de chunks stockés
    """
    from qdrant_client.models import PointStruct
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Vérifier que la collection existe
    try:
        client.get_collection(collection_name)
    except Exception:
        # Déterminer la dimension des vecteurs
        vector_size = len(embeddings[0]) if embeddings and embeddings[0] else 768
        init_collection(collection_name, vector_size)
    
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        if not embedding:
            continue
        
        point_id = str(uuid.uuid4())
        
        points.append(PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "session_id": session_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": chunk.get("index", 0),
                "content": chunk.get("content", ""),
                "page": chunk.get("page"),
            }
        ))
    
    if points:
        client.upsert(
            collection_name=collection_name,
            points=points
        )
    
    current_app.logger.info(f"Stored {len(points)} chunks in Qdrant for document {document_id}")
    return len(points)


def search_similar(
    session_id: str,
    query_embedding: List[float],
    top_k: int = 5,
    document_id: Optional[str] = None,
    score_threshold: float = 0.0,
    collection_name: Optional[str] = None
) -> List[Dict]:
    """
    Recherche les chunks les plus similaires à une query.
    
    Args:
        session_id: ID de la session pour filtrer
        query_embedding: Vecteur de la query
        top_k: Nombre de résultats
        document_id: Filtrer par document (optionnel)
        score_threshold: Score minimum (0-1)
        collection_name: Nom de la collection
        
    Returns:
        Liste de dicts avec 'content', 'filename', 'score', 'chunk_index'
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Construire le filtre
    conditions = [
        FieldCondition(key="session_id", match=MatchValue(value=session_id))
    ]
    
    if document_id:
        conditions.append(
            FieldCondition(key="document_id", match=MatchValue(value=document_id))
        )
    
    query_filter = Filter(must=conditions)
    
    # Recherche (API Qdrant >= 1.16)
    results = client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        query_filter=query_filter,
        limit=top_k,
        score_threshold=score_threshold
    )
    
    return [
        {
            "content": hit.payload.get("content", ""),
            "filename": hit.payload.get("filename", ""),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "page": hit.payload.get("page"),
            "document_id": hit.payload.get("document_id"),
            "score": hit.score
        }
        for hit in results.points
    ]


def delete_document_chunks(
    document_id: str,
    collection_name: Optional[str] = None
) -> int:
    """
    Supprime tous les chunks d'un document.
    
    Returns:
        Nombre de points supprimés
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Compter les points avant suppression
    count_before = client.count(
        collection_name=collection_name,
        count_filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        )
    ).count
    
    # Supprimer
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        )
    )
    
    current_app.logger.info(f"Deleted {count_before} chunks for document {document_id}")
    return count_before


def delete_session_chunks(
    session_id: str,
    collection_name: Optional[str] = None
) -> int:
    """
    Supprime tous les chunks d'une session.
    
    Returns:
        Nombre de points supprimés
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Compter les points avant suppression
    count_before = client.count(
        collection_name=collection_name,
        count_filter=Filter(
            must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
        )
    ).count
    
    # Supprimer
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
        )
    )
    
    current_app.logger.info(f"Deleted {count_before} chunks for session {session_id}")
    return count_before


def get_document_chunks(
    document_id: str,
    collection_name: Optional[str] = None
) -> List[Dict]:
    """
    Récupère tous les chunks d'un document depuis Qdrant.
    
    Args:
        document_id: ID du document
        collection_name: Nom de la collection
        
    Returns:
        Liste de dicts avec 'id', 'chunk_index', 'content', 'size'
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Récupérer tous les points du document avec scroll
    results, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
        limit=1000,  # Max chunks par document
        with_payload=True,
        with_vectors=False
    )
    
    chunks = []
    for point in results:
        content = point.payload.get("content", "")
        chunks.append({
            "id": str(point.id),
            "chunk_index": point.payload.get("chunk_index", 0),
            "content": content,
            "size": len(content)
        })
    
    # Trier par index
    chunks.sort(key=lambda x: x["chunk_index"])
    
    return chunks


def get_collection_stats(collection_name: Optional[str] = None) -> Dict:
    """
    Récupère les statistiques de la collection.
    
    Returns:
        Dict avec points_count, segments_count, etc.
    """
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    try:
        info = client.get_collection(collection_name)
        return {
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "segments_count": len(info.segments) if info.segments else 0,
            "status": info.status.value if info.status else "unknown"
        }
    except Exception as e:
        return {"error": str(e)}


def list_session_documents(
    session_id: str,
    collection_name: Optional[str] = None
) -> List[Dict]:
    """
    Liste les documents uniques d'une session.
    
    Returns:
        Liste de dicts avec document_id, filename, chunk_count
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    client = get_qdrant_client()
    collection_name = collection_name or current_app.config.get("QDRANT_COLLECTION", "rag_documents")
    
    # Scroll tous les points de la session
    documents = {}
    
    offset = None
    while True:
        results, offset = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
            ),
            limit=100,
            offset=offset,
            with_payload=["document_id", "filename"]
        )
        
        for point in results:
            doc_id = point.payload.get("document_id")
            if doc_id not in documents:
                documents[doc_id] = {
                    "document_id": doc_id,
                    "filename": point.payload.get("filename", ""),
                    "chunk_count": 0
                }
            documents[doc_id]["chunk_count"] += 1
        
        if offset is None:
            break
    
    return list(documents.values())


def migrate_from_postgres(session_id: Optional[str] = None) -> Dict:
    """
    Migre les données de PostgreSQL vers Qdrant.
    
    Args:
        session_id: Migrer seulement cette session (ou toutes si None)
        
    Returns:
        Dict avec stats de migration
    """
    from .rag_service import get_db_connection
    from .embedding_service import generate_embedding
    from psycopg2.extras import RealDictCursor
    
    stats = {
        "documents_migrated": 0,
        "chunks_migrated": 0,
        "errors": []
    }
    
    conn = get_db_connection(register_vec=True)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer les documents
        if session_id:
            cur.execute(
                "SELECT * FROM rag_documents WHERE session_id = %s",
                (session_id,)
            )
        else:
            cur.execute("SELECT * FROM rag_documents")
        
        documents = cur.fetchall()
        
        for doc in documents:
            doc_id = str(doc["id"])
            
            # Récupérer les chunks avec embeddings
            cur.execute("""
                SELECT chunk_index, content, embedding
                FROM rag_chunks
                WHERE document_id = %s
                ORDER BY chunk_index
            """, (doc_id,))
            
            chunks = []
            embeddings = []
            
            for row in cur.fetchall():
                chunks.append({
                    "index": row["chunk_index"],
                    "content": row["content"]
                })
                embeddings.append(list(row["embedding"]) if row["embedding"] else None)
            
            if chunks and embeddings:
                try:
                    store_chunks(
                        session_id=doc["session_id"],
                        document_id=doc_id,
                        filename=doc["filename"],
                        chunks=chunks,
                        embeddings=[e for e in embeddings if e]
                    )
                    stats["documents_migrated"] += 1
                    stats["chunks_migrated"] += len([e for e in embeddings if e])
                except Exception as e:
                    stats["errors"].append(f"Document {doc_id}: {str(e)}")
        
    finally:
        cur.close()
        conn.close()
    
    current_app.logger.info(f"Migration completed: {stats}")
    return stats
