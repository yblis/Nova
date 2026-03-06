from typing import List, Dict, Tuple, Any

from flask import current_app
from psycopg2.extras import RealDictCursor

from .database import get_db_connection, init_db, pad_embedding
from ..embedding_service import generate_embedding


def search_knowledge(
    specialist_id: str,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    init_db()

    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []

    padded_query = pad_embedding(query_embedding, 2048)

    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.content,
                    c.chunk_index,
                    k.name as source_name,
                    k.type as source_type,
                    1 - (c.embedding <=> %s::vector) as similarity
                FROM specialist_chunks c
                JOIN specialist_knowledge k ON c.knowledge_id = k.id
                WHERE c.specialist_id = %s
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
            """, (padded_query, specialist_id, padded_query, top_k))

            results = []
            for row in cur.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])
                item['score'] = float(item['similarity'])
                del item['similarity']
                results.append(item)

            return results

    finally:
        conn.close()


def get_context_for_query(specialist_id: str, query: str) -> Tuple[str, List[Dict]]:
    results = search_knowledge(specialist_id, query, top_k=5)

    if not results:
        return "", []

    context_parts = ["=== CONNAISSANCES DU SPÉCIALISTE ===\n"]
    sources = []

    for i, result in enumerate(results, 1):
        if result.get('score', 0) > 0.3:
            context_parts.append(f"[{i}] Source: {result['source_name']}")
            context_parts.append(f"Contenu: {result['content']}\n")
            sources.append({
                'name': result['source_name'],
                'type': result['source_type'],
                'score': result['score']
            })

    context_parts.append("=== FIN DES CONNAISSANCES ===\n")

    return "\n".join(context_parts), sources
