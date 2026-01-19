"""
Memory Graph Service - Graphe de connaissances sémantique pour recherche web.

Ce service crée et maintient un graphe de connaissances personnel qui enrichit
les recherches SearXNG avec une mémoire contextuelle persistante.
"""

import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from flask import current_app
import psycopg2
from psycopg2.extras import RealDictCursor, Json

from .chat_history_pg import get_db_connection, release_db_connection


# ══════════════════════════════════════════════════════════════════════════════
# INITIALISATION DES TABLES
# ══════════════════════════════════════════════════════════════════════════════

_memory_graph_initialized = False


def init_memory_graph_db():
    """
    Initialise les tables pour le Memory Graph.
    """
    global _memory_graph_initialized
    
    if _memory_graph_initialized:
        return
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Vérifier si les tables existent déjà
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'memory_nodes'
            );
        """)
        tables_exist = cur.fetchone()[0]
        
        if not tables_exist:
            # Extension pgvector pour les embeddings (si pas déjà installée)
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            except Exception:
                current_app.logger.warning("pgvector extension not available, using JSON for embeddings")
            
            # Table des concepts/entités découverts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_nodes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    concept TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    first_seen TIMESTAMP DEFAULT NOW(),
                    last_seen TIMESTAMP DEFAULT NOW(),
                    search_count INTEGER DEFAULT 1,
                    importance_score FLOAT DEFAULT 0.5,
                    embedding JSONB,
                    metadata JSONB DEFAULT '{}',
                    UNIQUE(user_id, concept)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_nodes_user ON memory_nodes(user_id);
                CREATE INDEX IF NOT EXISTS idx_memory_nodes_concept ON memory_nodes(concept);
                CREATE INDEX IF NOT EXISTS idx_memory_nodes_last_seen ON memory_nodes(last_seen DESC);
            """)
            
            # Table des relations entre concepts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_edges (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    source_node_id INTEGER REFERENCES memory_nodes(id) ON DELETE CASCADE,
                    target_node_id INTEGER REFERENCES memory_nodes(id) ON DELETE CASCADE,
                    relation_type TEXT DEFAULT 'related_to',
                    strength FLOAT DEFAULT 0.5,
                    co_occurrence_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, source_node_id, target_node_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_edges_source ON memory_edges(source_node_id);
                CREATE INDEX IF NOT EXISTS idx_memory_edges_target ON memory_edges(target_node_id);
            """)
            
            # Table des sources web associées
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_sources (
                    id SERIAL PRIMARY KEY,
                    node_id INTEGER REFERENCES memory_nodes(id) ON DELETE CASCADE,
                    url TEXT NOT NULL,
                    title TEXT,
                    snippet TEXT,
                    discovered_at TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_memory_sources_node ON memory_sources(node_id);
            """)
            
            # Table historique des recherches
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_searches (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    session_id TEXT,
                    searched_at TIMESTAMP DEFAULT NOW(),
                    result_count INTEGER DEFAULT 0,
                    nodes_extracted INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_memory_searches_user ON memory_searches(user_id, searched_at DESC);
            """)
            
            conn.commit()
            current_app.logger.info("Memory Graph tables created successfully")
        
        _memory_graph_initialized = True
        
    except Exception as e:
        current_app.logger.error(f"Error initializing Memory Graph: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_connection(conn)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION D'ENTITÉS VIA LLM
# ══════════════════════════════════════════════════════════════════════════════

def extract_entities_from_snippets(snippets: List[Dict[str, str]], query: str) -> List[Dict[str, Any]]:
    """
    Extrait les entités/concepts des snippets de recherche via le LLM.
    
    Args:
        snippets: Liste de dicts avec 'title', 'snippet'
        query: La requête originale
        
    Returns:
        Liste de dicts avec 'concept', 'category', 'relation_to_query'
    """
    if not snippets:
        return []
    
    # Construire le texte à analyser
    text_content = f"Requête: {query}\n\n"
    for i, s in enumerate(snippets[:5], 1):  # Limiter à 5 pour éviter trop de tokens
        text_content += f"[{i}] {s.get('title', '')}\n{s.get('snippet', '')}\n\n"
    
    # Prompt pour extraction d'entités
    extraction_prompt = f"""Analyse le texte suivant et extrait les concepts clés, entités, et sujets importants.

{text_content}

Retourne un JSON avec une liste d'entités extraites. Format:
{{
  "entities": [
    {{"concept": "nom du concept", "category": "science|tech|santé|économie|culture|général", "importance": 0.1-1.0}},
    ...
  ]
}}

Règles:
- Extrait 3 à 8 concepts maximum
- Privilégie les noms propres, termes techniques, concepts clés
- Évite les mots trop génériques
- Retourne UNIQUEMENT le JSON, rien d'autre"""

    try:
        from .llm_clients import get_active_client
        
        client = get_active_client()
        if not client:
            return _fallback_entity_extraction(snippets, query)
        
        # Appel au LLM
        response = client.chat(
            model=None,  # Utilise le modèle par défaut du provider actif
            messages=[{"role": "user", "content": extraction_prompt}],
            options={"temperature": 0.3}
        )
        
        content = response.get('content', '') if isinstance(response, dict) else str(response)
        
        # Parser le JSON
        try:
            # Chercher le JSON dans la réponse
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('entities', [])
        except json.JSONDecodeError:
            pass
            
    except Exception as e:
        current_app.logger.warning(f"LLM entity extraction failed: {e}")
    
    return _fallback_entity_extraction(snippets, query)


def _fallback_entity_extraction(snippets: List[Dict[str, str]], query: str) -> List[Dict[str, Any]]:
    """
    Extraction basique d'entités sans LLM (fallback).
    Utilise des heuristiques simples.
    """
    import re
    from collections import Counter
    
    # Mots à ignorer
    stopwords = {'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'à', 'en',
                 'est', 'sont', 'a', 'ont', 'pour', 'par', 'sur', 'avec', 'dans', 'que',
                 'qui', 'ce', 'cette', 'ces', 'son', 'sa', 'ses', 'the', 'a', 'an', 'is',
                 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
                 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can'}
    
    # Collecter tous les mots
    all_text = query + " " + " ".join(s.get('title', '') + " " + s.get('snippet', '') for s in snippets)
    
    # Extraire les mots significatifs (majuscules = noms propres potentiels)
    words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', all_text)  # Mots commençant par majuscule
    words += re.findall(r'\b[a-z]{4,15}\b', all_text.lower())  # Mots de 4-15 lettres
    
    # Filtrer et compter
    filtered = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    counter = Counter(filtered)
    
    # Top concepts
    entities = []
    for concept, count in counter.most_common(6):
        if count >= 1:
            entities.append({
                'concept': concept,
                'category': 'general',
                'importance': min(0.9, 0.3 + (count * 0.1))
            })
    
    return entities


# ══════════════════════════════════════════════════════════════════════════════
# GESTION DU GRAPHE
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_node(user_id: int, concept: str, category: str = 'general') -> Optional[int]:
    """
    Récupère ou crée un nœud dans le graphe.
    
    Returns:
        ID du nœud
    """
    init_memory_graph_db()
    conn = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Essayer de mettre à jour si existe
        cur.execute("""
            UPDATE memory_nodes 
            SET last_seen = NOW(), search_count = search_count + 1
            WHERE user_id = %s AND LOWER(concept) = LOWER(%s)
            RETURNING id
        """, (user_id, concept))
        
        result = cur.fetchone()
        if result:
            conn.commit()
            return result[0]
        
        # Sinon créer
        cur.execute("""
            INSERT INTO memory_nodes (user_id, concept, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, concept) DO UPDATE SET
                last_seen = NOW(),
                search_count = memory_nodes.search_count + 1
            RETURNING id
        """, (user_id, concept, category))
        
        node_id = cur.fetchone()[0]
        conn.commit()
        return node_id
        
    except Exception as e:
        current_app.logger.error(f"Error creating node: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            release_db_connection(conn)


def create_or_strengthen_edge(user_id: int, source_id: int, target_id: int, 
                               relation_type: str = 'related_to'):
    """
    Crée ou renforce un lien entre deux concepts.
    """
    if source_id == target_id:
        return
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO memory_edges (user_id, source_node_id, target_node_id, relation_type)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, source_node_id, target_node_id) DO UPDATE SET
                co_occurrence_count = memory_edges.co_occurrence_count + 1,
                strength = LEAST(1.0, memory_edges.strength + 0.1),
                updated_at = NOW()
        """, (user_id, source_id, target_id, relation_type))
        
        conn.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error creating edge: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_connection(conn)


def add_source_to_node(node_id: int, url: str, title: str, snippet: str):
    """
    Ajoute une source web à un nœud.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Éviter les doublons
        cur.execute("""
            INSERT INTO memory_sources (node_id, url, title, snippet)
            SELECT %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM memory_sources WHERE node_id = %s AND url = %s
            )
        """, (node_id, url, title, snippet[:1000] if snippet else '', node_id, url))
        
        conn.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error adding source: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_connection(conn)


def log_search(user_id: int, query: str, session_id: str, result_count: int, nodes_extracted: int):
    """
    Enregistre une recherche dans l'historique.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO memory_searches (user_id, query, session_id, result_count, nodes_extracted)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, query, session_id, result_count, nodes_extracted))
        
        conn.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error logging search: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_connection(conn)


# ══════════════════════════════════════════════════════════════════════════════
# RÉCUPÉRATION DU CONTEXTE
# ══════════════════════════════════════════════════════════════════════════════

def get_related_context(user_id: int, query: str, limit: int = 5) -> Tuple[str, List[Dict]]:
    """
    Récupère le contexte lié à une requête depuis le graphe de mémoire.
    
    Args:
        user_id: ID de l'utilisateur
        query: Requête de recherche
        limit: Nombre max de concepts liés à retourner
        
    Returns:
        Tuple (contexte_textuel, liste_de_concepts_liés)
    """
    init_memory_graph_db()
    conn = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Chercher des concepts liés à la requête (recherche textuelle simple)
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        
        if not query_words:
            return "", []
        
        # Construire la condition de recherche
        like_conditions = " OR ".join(["LOWER(concept) LIKE %s" for _ in query_words])
        like_params = [f"%{w}%" for w in query_words]
        
        # Récupérer les concepts liés
        cur.execute(f"""
            SELECT n.id, n.concept, n.category, n.search_count, n.last_seen,
                   COALESCE(
                       (SELECT json_agg(json_build_object('title', s.title, 'url', s.url))
                        FROM memory_sources s WHERE s.node_id = n.id LIMIT 3),
                       '[]'
                   ) as sources
            FROM memory_nodes n
            WHERE n.user_id = %s AND ({like_conditions})
            ORDER BY n.search_count DESC, n.last_seen DESC
            LIMIT %s
        """, [user_id] + like_params + [limit])
        
        related_concepts = cur.fetchall()
        
        if not related_concepts:
            return "", []
        
        # Construire le contexte textuel
        context_parts = ["=== MÉMOIRE CONTEXTUELLE ==="]
        context_parts.append("Concepts liés à ta recherche que tu as déjà explorés:")
        
        for concept in related_concepts:
            last_seen = concept['last_seen']
            if isinstance(last_seen, str):
                last_seen = datetime.fromisoformat(last_seen)
            
            days_ago = (datetime.now() - last_seen).days if last_seen else 0
            time_str = "aujourd'hui" if days_ago == 0 else f"il y a {days_ago} jour(s)"
            
            context_parts.append(
                f"• {concept['concept']} ({concept['category']}) - "
                f"consulté {concept['search_count']}x, dernière fois {time_str}"
            )
        
        context_parts.append("=== FIN MÉMOIRE ===\n")
        
        return "\n".join(context_parts), [dict(c) for c in related_concepts]
        
    except Exception as e:
        current_app.logger.error(f"Error getting related context: {e}")
        return "", []
    finally:
        if conn:
            release_db_connection(conn)


def get_user_knowledge_graph(user_id: int, limit: int = 50) -> Dict[str, Any]:
    """
    Récupère le graphe de connaissances complet d'un utilisateur.
    
    Returns:
        Dict avec 'nodes' et 'edges' pour visualisation
    """
    init_memory_graph_db()
    conn = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Récupérer les nœuds
        cur.execute("""
            SELECT id, concept, category, search_count, importance_score, last_seen
            FROM memory_nodes
            WHERE user_id = %s
            ORDER BY search_count DESC, last_seen DESC
            LIMIT %s
        """, (user_id, limit))
        
        nodes = [dict(n) for n in cur.fetchall()]
        node_ids = [n['id'] for n in nodes]
        
        if not node_ids:
            return {'nodes': [], 'edges': [], 'stats': {'total_concepts': 0, 'total_connections': 0}}
        
        # Récupérer les arêtes
        cur.execute("""
            SELECT source_node_id, target_node_id, relation_type, strength, co_occurrence_count
            FROM memory_edges
            WHERE user_id = %s 
              AND source_node_id = ANY(%s) 
              AND target_node_id = ANY(%s)
        """, (user_id, node_ids, node_ids))
        
        edges = [dict(e) for e in cur.fetchall()]
        
        # Stats
        cur.execute("""
            SELECT COUNT(*) as total_concepts FROM memory_nodes WHERE user_id = %s
        """, (user_id,))
        total_concepts = cur.fetchone()['total_concepts']
        
        cur.execute("""
            SELECT COUNT(*) as total_edges FROM memory_edges WHERE user_id = %s
        """, (user_id,))
        total_edges = cur.fetchone()['total_edges']
        
        return {
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'total_concepts': total_concepts,
                'total_connections': total_edges
            }
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting knowledge graph: {e}")
        return {'nodes': [], 'edges': [], 'stats': {'total_concepts': 0, 'total_connections': 0}}
    finally:
        if conn:
            release_db_connection(conn)


# ══════════════════════════════════════════════════════════════════════════════
# API PRINCIPALE - PROCESSUS COMPLET
# ══════════════════════════════════════════════════════════════════════════════

def process_search_results(user_id: int, query: str, search_results: List[Dict[str, str]], 
                           session_id: str = None) -> Tuple[str, List[Dict]]:
    """
    Traite les résultats d'une recherche SearXNG et met à jour le graphe.
    
    Args:
        user_id: ID de l'utilisateur
        query: Requête de recherche
        search_results: Résultats de SearXNG (liste de dicts avec title, url, snippet)
        session_id: ID de la session chat
        
    Returns:
        Tuple (contexte_mémoire, concepts_trouvés)
    """
    init_memory_graph_db()
    
    # 1. Récupérer le contexte existant lié à cette recherche
    memory_context, related = get_related_context(user_id, query)
    
    # 2. Extraire les entités des nouveaux résultats
    entities = extract_entities_from_snippets(search_results, query)
    
    if not entities:
        # Fallback: utiliser les mots de la requête comme concepts
        for word in query.split():
            if len(word) > 3:
                entities.append({'concept': word, 'category': 'general', 'importance': 0.5})
    
    # 3. Créer/mettre à jour les nœuds
    node_ids = []
    for entity in entities:
        node_id = get_or_create_node(
            user_id, 
            entity.get('concept', ''), 
            entity.get('category', 'general')
        )
        if node_id:
            node_ids.append(node_id)
            
            # Ajouter les sources à ce nœud
            for result in search_results[:3]:  # Top 3 sources
                add_source_to_node(
                    node_id,
                    result.get('url', ''),
                    result.get('title', ''),
                    result.get('snippet', '')
                )
    
    # 4. Créer les liens entre tous les concepts trouvés ensemble
    for i, source_id in enumerate(node_ids):
        for target_id in node_ids[i+1:]:
            create_or_strengthen_edge(user_id, source_id, target_id)
    
    # 5. Log de la recherche
    log_search(user_id, query, session_id or '', len(search_results), len(entities))
    
    return memory_context, entities


def clear_user_memory(user_id: int) -> bool:
    """
    Efface la mémoire d'un utilisateur.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Supprimer dans l'ordre (contraintes FK)
        cur.execute("DELETE FROM memory_searches WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM memory_edges WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM memory_sources WHERE node_id IN (SELECT id FROM memory_nodes WHERE user_id = %s)", (user_id,))
        cur.execute("DELETE FROM memory_nodes WHERE user_id = %s", (user_id,))
        
        conn.commit()
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error clearing memory: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_db_connection(conn)


def delete_node_by_concept(user_id: int, concept: str) -> bool:
    """
    Supprime un concept spécifique du graphe mémoire.
    
    Args:
        user_id: ID de l'utilisateur
        concept: Nom du concept à supprimer
        
    Returns:
        True si supprimé avec succès
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Trouver l'ID du nœud
        cur.execute("""
            SELECT id FROM memory_nodes 
            WHERE user_id = %s AND LOWER(concept) = LOWER(%s)
        """, (user_id, concept))
        
        result = cur.fetchone()
        if not result:
            return False
        
        node_id = result[0]
        
        # Supprimer les sources liées
        cur.execute("DELETE FROM memory_sources WHERE node_id = %s", (node_id,))
        
        # Supprimer les arêtes liées
        cur.execute("""
            DELETE FROM memory_edges 
            WHERE source_node_id = %s OR target_node_id = %s
        """, (node_id, node_id))
        
        # Supprimer le nœud
        cur.execute("DELETE FROM memory_nodes WHERE id = %s", (node_id,))
        
        conn.commit()
        current_app.logger.info(f"Deleted memory node '{concept}' for user {user_id}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error deleting node: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_db_connection(conn)
