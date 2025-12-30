"""
Specialist Service - Gestion des assistants IA spécialisés

Ce service gère :
- CRUD des spécialistes
- Gestion des connaissances (fichiers, URLs, texte)
- Gestion des outils/intégrations API
- Recherche RAG dans les connaissances du spécialiste
"""

import os
import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from flask import current_app
import psycopg2
from psycopg2.extras import RealDictCursor

from .embedding_service import generate_embedding, generate_embeddings_batch, get_embedding_model, get_embedding_dimensions
from .pdf_service import process_pdf, chunk_text


# Variable globale pour le pool de connexions
_db_initialized = False


def get_db_connection():
    """Crée une connexion à PostgreSQL."""
    return psycopg2.connect(current_app.config["POSTGRES_URL"])


def pad_embedding(embedding: list, target_dim: int = 2048) -> list:
    """Pad ou truncate un embedding à la dimension cible."""
    if len(embedding) >= target_dim:
        return embedding[:target_dim]
    return embedding + [0.0] * (target_dim - len(embedding))


def init_db():
    """
    Initialise les tables PostgreSQL pour les spécialistes.
    À appeler au démarrage de l'application.
    """
    global _db_initialized
    if _db_initialized:
        return
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Table des spécialistes
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
            
            # Table des connaissances
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
            
            # Table des chunks pour le RAG
            # On utilise vector(2048) pour supporter différentes dimensions d'embedding
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
            
            # Migration: modifier la colonne embedding si elle existe avec une dimension différente
            try:
                cur.execute("""
                    ALTER TABLE specialist_chunks 
                    ALTER COLUMN embedding TYPE vector(2048)
                """)
            except Exception:
                pass  # Ignorer l'erreur si la colonne a déjà la bonne dimension
            
            # Table des outils/intégrations
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
            
            # Table des sessions de chat
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
            
            # Table des messages
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
            
            # Index pour les recherches
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
            
            # Migration: ajouter la colonne icon si elle n'existe pas
            try:
                cur.execute("""
                    ALTER TABLE specialists 
                    ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT 'computer'
                """)
            except Exception:
                pass  # Column might already exist in older PostgreSQL versions
            
            # Migration: ajouter la colonne provider_id si elle n'existe pas
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


# ============== CRUD Spécialistes ==============

def create_specialist(
    user_id: str,
    name: str,
    system_prompt: str,
    description: str = None,
    model: str = None,
    avatar_url: str = None,
    color: str = "#6366f1",
    icon: str = "computer",
    provider_id: str = None
) -> Dict[str, Any]:
    """
    Crée un nouveau spécialiste.
    
    Returns:
        Dict avec les infos du spécialiste créé
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO specialists (user_id, name, description, system_prompt, model, avatar_url, color, icon, provider_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (user_id, name, description, system_prompt, model, avatar_url, color, icon, provider_id))
            
            result = dict(cur.fetchone())
            conn.commit()
            
            # Convertir les dates en ISO
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            if result.get('updated_at'):
                result['updated_at'] = result['updated_at'].isoformat()
            result['id'] = str(result['id'])
            
            return result
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error creating specialist: {e}")
        raise
    finally:
        conn.close()


def list_specialists(user_id: str) -> List[Dict[str, Any]]:
    """
    Liste tous les spécialistes d'un utilisateur.
    
    Returns:
        Liste de dicts avec les infos des spécialistes
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT s.*, 
                       COUNT(DISTINCT k.id) as knowledge_count,
                       COUNT(DISTINCT t.id) as tools_count
                FROM specialists s
                LEFT JOIN specialist_knowledge k ON s.id = k.specialist_id
                LEFT JOIN specialist_tools t ON s.id = t.specialist_id
                WHERE s.user_id = %s
                GROUP BY s.id
                ORDER BY s.updated_at DESC
            """, (user_id,))
            
            results = []
            for row in cur.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                if item.get('updated_at'):
                    item['updated_at'] = item['updated_at'].isoformat()
                results.append(item)
            
            return results
            
    finally:
        conn.close()


def get_specialist(specialist_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Récupère un spécialiste par son ID.
    
    Args:
        specialist_id: ID du spécialiste
        user_id: Si fourni, vérifie que le spécialiste appartient à cet utilisateur
        
    Returns:
        Dict avec les infos du spécialiste ou None
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM specialists WHERE id = %s"
            params = [specialist_id]
            
            if user_id:
                query += " AND user_id = %s"
                params.append(user_id)
            
            cur.execute(query, params)
            row = cur.fetchone()
            
            if not row:
                return None
            
            result = dict(row)
            result['id'] = str(result['id'])
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            if result.get('updated_at'):
                result['updated_at'] = result['updated_at'].isoformat()
            
            # Récupérer les connaissances AVEC le comptage des chunks
            cur.execute("""
                SELECT k.id, k.type, k.name, k.metadata, k.created_at,
                       COUNT(c.id) as chunk_count
                FROM specialist_knowledge k
                LEFT JOIN specialist_chunks c ON k.id = c.knowledge_id
                WHERE k.specialist_id = %s
                GROUP BY k.id
                ORDER BY k.created_at DESC
            """, (specialist_id,))
            
            knowledge = []
            for k in cur.fetchall():
                item = dict(k)
                item['id'] = str(item['id'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                knowledge.append(item)
            
            result['knowledge'] = knowledge
            
            # Récupérer les outils
            cur.execute("""
                SELECT id, name, type, config, enabled, created_at 
                FROM specialist_tools 
                WHERE specialist_id = %s
                ORDER BY created_at DESC
            """, (specialist_id,))
            
            tools = []
            for t in cur.fetchall():
                item = dict(t)
                item['id'] = str(item['id'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                tools.append(item)
            
            result['tools'] = tools
            
            return result
            
    finally:
        conn.close()


def update_specialist(
    specialist_id: str,
    user_id: str,
    name: str = None,
    description: str = None,
    system_prompt: str = None,
    model: str = None,
    avatar_url: str = None,
    color: str = None,
    icon: str = None,
    provider_id: str = None
) -> Optional[Dict[str, Any]]:
    """
    Met à jour un spécialiste.
    
    Returns:
        Dict avec les infos mises à jour ou None si non trouvé
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Construire la requête dynamiquement
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if description is not None:
                updates.append("description = %s")
                params.append(description)
            if system_prompt is not None:
                updates.append("system_prompt = %s")
                params.append(system_prompt)
            if model is not None:
                updates.append("model = %s")
                params.append(model)
            if avatar_url is not None:
                updates.append("avatar_url = %s")
                params.append(avatar_url)
            if color is not None:
                updates.append("color = %s")
                params.append(color)
            if icon is not None:
                updates.append("icon = %s")
                params.append(icon)
            if provider_id is not None:
                updates.append("provider_id = %s")
                params.append(provider_id)
            
            if not updates:
                return get_specialist(specialist_id, user_id)
            
            updates.append("updated_at = NOW()")
            params.extend([specialist_id, user_id])
            
            cur.execute(f"""
                UPDATE specialists 
                SET {', '.join(updates)}
                WHERE id = %s AND user_id = %s
                RETURNING *
            """, params)
            
            row = cur.fetchone()
            conn.commit()
            
            if not row:
                return None
            
            result = dict(row)
            result['id'] = str(result['id'])
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            if result.get('updated_at'):
                result['updated_at'] = result['updated_at'].isoformat()
            
            return result
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error updating specialist: {e}")
        raise
    finally:
        conn.close()


def delete_specialist(specialist_id: str, user_id: str) -> bool:
    """
    Supprime un spécialiste et toutes ses données associées.
    
    Returns:
        True si supprimé, False si non trouvé
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # Récupérer les fichiers à supprimer
            cur.execute("""
                SELECT file_path FROM specialist_knowledge 
                WHERE specialist_id = %s AND file_path IS NOT NULL
            """, (specialist_id,))
            
            file_paths = [row[0] for row in cur.fetchall()]
            
            # Supprimer le spécialiste (cascade supprime knowledge, tools, sessions)
            cur.execute("""
                DELETE FROM specialists 
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (specialist_id, user_id))
            
            deleted = cur.fetchone() is not None
            conn.commit()
            
            # Supprimer les fichiers physiques
            if deleted:
                for file_path in file_paths:
                    try:
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        current_app.logger.warning(f"Error deleting file {file_path}: {e}")
            
            return deleted
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting specialist: {e}")
        raise
    finally:
        conn.close()


# ============== Gestion des Connaissances ==============

def add_knowledge_text(
    specialist_id: str,
    name: str,
    content: str,
    knowledge_type: str = "text"
) -> Dict[str, Any]:
    """
    Ajoute une connaissance textuelle et génère les embeddings.
    
    Args:
        specialist_id: ID du spécialiste
        name: Nom de la connaissance
        content: Contenu textuel
        knowledge_type: Type ('text', 'web_url')
        
    Returns:
        Dict avec les infos de la connaissance créée
    """
    init_db()
    conn = get_db_connection()
    
    # Nettoyer les caractères NUL qui ne sont pas acceptés par PostgreSQL
    content = content.replace('\x00', '') if content else ''
    name = name.replace('\x00', '') if name else ''
    
    try:
        knowledge_id = str(uuid.uuid4())
        embedding_model = get_embedding_model()
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Créer la connaissance
            cur.execute("""
                INSERT INTO specialist_knowledge 
                    (id, specialist_id, type, name, content, embedding_model, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                knowledge_id, specialist_id, knowledge_type, name, content,
                embedding_model, json.dumps({"char_count": len(content)})
            ))
            
            knowledge = dict(cur.fetchone())
            
            # Chunker le texte
            chunks = chunk_text(content, chunk_size=500, overlap=50)
            
            if chunks and embedding_model:
                # Générer les embeddings
                texts = [c['content'] for c in chunks]
                current_app.logger.info(f"Generating embeddings for {len(texts)} chunks")
                embeddings = generate_embeddings_batch(texts)
                
                # Stocker les chunks avec padding de l'embedding
                inserted_count = 0
                for chunk, embedding in zip(chunks, embeddings):
                    if embedding:
                        padded_embedding = pad_embedding(embedding, 2048)
                        cur.execute("""
                            INSERT INTO specialist_chunks 
                                (knowledge_id, specialist_id, chunk_index, content, embedding)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            knowledge_id, specialist_id, chunk['index'],
                            chunk['content'], padded_embedding
                        ))
                        inserted_count += 1
                
                current_app.logger.info(f"Inserted {inserted_count} chunks into DB")
            
            conn.commit()
            
            # VERIFICATION IMMEDIATE
            with conn.cursor() as check_cur:
                check_cur.execute("SELECT COUNT(*) FROM specialist_chunks WHERE knowledge_id = %s", (knowledge_id,))
                count_in_db = check_cur.fetchone()[0]
                current_app.logger.info(f"VERIFICATION POST-COMMIT: Found {count_in_db} chunks in DB for knowledge {knowledge_id}")
                if count_in_db == 0 and len(chunks) > 0:
                    current_app.logger.error("CRITICAL: Chunks were committed but NOT found in DB immediately after!")

            knowledge['id'] = str(knowledge['id'])
            knowledge['specialist_id'] = str(knowledge['specialist_id'])
            knowledge['chunk_count'] = len(chunks) if chunks else 0
            if knowledge.get('created_at'):
                knowledge['created_at'] = knowledge['created_at'].isoformat()
            
            return knowledge
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error adding knowledge: {e}")
        raise
    finally:
        conn.close()


def add_knowledge_file(
    specialist_id: str,
    filename: str,
    file_bytes: bytes,
    file_type: str
) -> Dict[str, Any]:
    """
    Ajoute un fichier comme connaissance.
    
    Args:
        specialist_id: ID du spécialiste
        filename: Nom du fichier
        file_bytes: Contenu binaire du fichier
        file_type: Type MIME ou extension
        
    Returns:
        Dict avec les infos de la connaissance créée
    """
    init_db()
    
    # Déterminer le type de connaissance
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.pdf':
        # Traiter le PDF
        text, chunks = process_pdf(file_bytes, filename)
        knowledge_type = 'pdf'
    elif ext in ['.txt', '.md', '.py', '.js', '.json', '.csv', '.html', '.css', '.yaml', '.yml']:
        # Fichier texte
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('latin-1')
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        knowledge_type = 'text_file'
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
        # Image - stocker sans chunking
        knowledge_type = 'image'
        text = None
        chunks = []
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    # Sauvegarder le fichier
    upload_dir = os.path.join(current_app.root_path, "data", "specialists", specialist_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}{ext}")
    
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    
    conn = get_db_connection()
    
    try:
        knowledge_id = str(uuid.uuid4())
        embedding_model = get_embedding_model()
        
        metadata = {
            "original_filename": filename,
            "size": len(file_bytes),
            "extension": ext
        }
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Créer la connaissance
            cur.execute("""
                INSERT INTO specialist_knowledge 
                    (id, specialist_id, type, name, content, file_path, embedding_model, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                knowledge_id, specialist_id, knowledge_type, filename,
                text[:10000] if text else None,  # Stocker un extrait
                file_path, embedding_model, json.dumps(metadata)
            ))
            
            knowledge = dict(cur.fetchone())
            
            # Stocker les chunks avec embeddings
            if chunks and embedding_model:
                texts = [c['content'] for c in chunks]
                embeddings = generate_embeddings_batch(texts)
                
                for chunk, embedding in zip(chunks, embeddings):
                    if embedding:
                        padded_embedding = pad_embedding(embedding, 2048)
                        cur.execute("""
                            INSERT INTO specialist_chunks 
                                (knowledge_id, specialist_id, chunk_index, content, embedding)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            knowledge_id, specialist_id, chunk['index'],
                            chunk['content'], padded_embedding
                        ))
            
            conn.commit()
            
            knowledge['id'] = str(knowledge['id'])
            knowledge['specialist_id'] = str(knowledge['specialist_id'])
            knowledge['chunk_count'] = len(chunks) if chunks else 0
            if knowledge.get('created_at'):
                knowledge['created_at'] = knowledge['created_at'].isoformat()
            
            return knowledge
            
    except Exception as e:
        conn.rollback()
        # Nettoyer le fichier en cas d'erreur
        if os.path.exists(file_path):
            os.remove(file_path)
        current_app.logger.error(f"Error adding file knowledge: {e}")
        raise
    finally:
        conn.close()


def add_knowledge_web(specialist_id: str, url: str) -> Dict[str, Any]:
    """
    Ajoute une URL comme connaissance.
    
    Essaie d'abord un fetch direct, puis utilise SearXNG comme fallback
    si le site bloque les requêtes automatiques.
    
    Args:
        specialist_id: ID du spécialiste
        url: URL à indexer
        
    Returns:
        Dict avec les infos de la connaissance créée
    """
    from .web_search_service import get_searxng_url, is_searxng_available
    import httpx
    import re
    from html.parser import HTMLParser
    
    content = None
    title = url
    method_used = "direct"
    
    # Classe pour extraire le texte du HTML
    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.in_script = False
            self.in_style = False
            
        def handle_starttag(self, tag, attrs):
            if tag in ['script', 'style', 'noscript', 'header', 'footer', 'nav']:
                self.in_script = True
                
        def handle_endtag(self, tag):
            if tag in ['script', 'style', 'noscript', 'header', 'footer', 'nav']:
                self.in_script = False
                
        def handle_data(self, data):
            if not self.in_script:
                text = data.strip()
                if text and len(text) > 2:  # Ignorer les textes trop courts
                    self.text_parts.append(text)
    
    # 1. Essayer le fetch direct avec un User-Agent réaliste
    direct_error = None
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br', # Accepter la compression
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        with httpx.Client(timeout=30.0, follow_redirects=True, http2=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            # Gestion robuste de l'encodage
            encoding = response.encoding or 'utf-8'
            try:
                html_content = response.content.decode(encoding)
            except UnicodeDecodeError:
                # Fallback: essayer de détecter ou utiliser latin-1/replace
                try:
                    import chardet
                    detected = chardet.detect(response.content)
                    if detected['encoding']:
                        html_content = response.content.decode(detected['encoding'])
                    else:
                        raise ValueError("Encoding unknown")
                except Exception:
                    html_content = response.content.decode('utf-8', errors='replace')

            parser = TextExtractor()
            parser.feed(html_content)
            content = ' '.join(parser.text_parts)
            
            # Nettoyage supplémentaire du contenu: retirer les séquences de caractères étranges
            # Si le contenu contient trop de caractères de contrôle ou non-imprimables, c'est suspect
            # On ne garde que les caractères imprimables unicode et les espaces courants
            content = "".join(ch for ch in content if ch.isprintable() or ch in '\n\r\t ')
            
            # Extraire le titre
            title_match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else url
            
    except httpx.HTTPStatusError as e:
        direct_error = e
        status_code = e.response.status_code
        current_app.logger.warning(f"Direct fetch failed for {url}: HTTP {status_code}")
    except Exception as e:
        direct_error = e
        current_app.logger.warning(f"Direct fetch failed for {url}: {e}")
    
    # 2. Si le fetch direct a échoué, essayer avec SearXNG
    if content is None or len(content.strip()) < 100:
        if is_searxng_available():
            try:
                searxng_url = get_searxng_url()
                
                # Utiliser SearXNG pour chercher cette URL spécifique
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(
                        f"{searxng_url}/search",
                        params={
                            "q": f"site:{url}",
                            "format": "json",
                            "language": "fr-FR"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        
                        if results:
                            method_used = "searxng"
                            # Récupérer le premier résultat qui correspond à l'URL
                            for result in results:
                                result_url = result.get("url", "")
                                if url in result_url or result_url in url:
                                    title = result.get("title", url)
                                    content = result.get("content", result.get("snippet", ""))
                                    break
                            
                            # Si aucun résultat exact, prendre le premier
                            if not content and results:
                                title = results[0].get("title", url)
                                content = results[0].get("content", results[0].get("snippet", ""))
                                
                        if content:
                            current_app.logger.info(f"Retrieved content via SearXNG for {url}")
                            
            except Exception as e:
                current_app.logger.warning(f"SearXNG fallback failed for {url}: {e}")
    
    # 3. Si toujours pas de contenu, retourner une erreur claire
    if not content or len(content.strip()) < 50:
        if direct_error:
            if isinstance(direct_error, httpx.HTTPStatusError):
                status_code = direct_error.response.status_code
                if status_code == 403:
                    raise ValueError(f"Accès refusé (403): Ce site bloque les requêtes automatiques. Essayez de copier-coller le contenu manuellement.")
                elif status_code == 404:
                    raise ValueError(f"Page non trouvée (404): L'URL n'existe pas.")
                else:
                    raise ValueError(f"Erreur HTTP {status_code}: Impossible d'accéder à cette URL.")
            elif isinstance(direct_error, httpx.TimeoutException):
                raise ValueError("Timeout: Le site met trop de temps à répondre.")
            else:
                raise ValueError(f"Impossible de récupérer l'URL: {str(direct_error)}")
        else:
            raise ValueError("Contenu insuffisant récupéré depuis cette URL.")
    
    # Nettoyer le contenu des caractères NUL et autres caractères invalides pour PostgreSQL
    content = content.replace('\x00', '').replace('\u0000', '')
    title = title.replace('\x00', '').replace('\u0000', '')
    
    # Ajouter comme connaissance textuelle
    current_app.logger.info(f"Adding web knowledge from {url} (method: {method_used}, content length: {len(content)})")
    return add_knowledge_text(
        specialist_id=specialist_id,
        name=title[:200],  # Limiter la longueur du titre
        content=content[:50000],  # Limiter la taille
        knowledge_type="web_url"
    )


def delete_knowledge(knowledge_id: str, specialist_id: str) -> bool:
    """
    Supprime une connaissance et ses chunks associés.
    
    Returns:
        True si supprimé, False si non trouvé
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # Récupérer le fichier à supprimer
            cur.execute("""
                SELECT file_path FROM specialist_knowledge 
                WHERE id = %s AND specialist_id = %s
            """, (knowledge_id, specialist_id))
            
            row = cur.fetchone()
            if not row:
                return False
            
            file_path = row[0]
            
            # Supprimer la connaissance (cascade supprime les chunks)
            cur.execute("""
                DELETE FROM specialist_knowledge 
                WHERE id = %s AND specialist_id = %s
                RETURNING id
            """, (knowledge_id, specialist_id))
            
            deleted = cur.fetchone() is not None
            conn.commit()
            
            # Supprimer le fichier physique
            if deleted and file_path and os.path.exists(file_path):
                os.remove(file_path)
            
            return deleted
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting knowledge: {e}")
        raise
    finally:
        conn.close()


def get_knowledge_chunks(knowledge_id: str, specialist_id: str) -> Dict[str, Any]:
    """
    Récupère les chunks d'une connaissance avec ses statistiques.
    
    Args:
        knowledge_id: ID de la connaissance
        specialist_id: ID du spécialiste (pour vérifier l'accès)
        
    Returns:
        Dict avec 'chunks' et 'stats'
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Vérifier que la connaissance appartient au spécialiste
            cur.execute("""
                SELECT id, name, type FROM specialist_knowledge 
                WHERE id = %s AND specialist_id = %s
            """, (knowledge_id, specialist_id))
            
            knowledge = cur.fetchone()
            if not knowledge:
                return {"chunks": [], "stats": {}}
            
            # Récupérer les chunks
            cur.execute("""
                SELECT id, chunk_index, content, length(content) as size
                FROM specialist_chunks
                WHERE knowledge_id = %s
                ORDER BY chunk_index ASC
            """, (knowledge_id,))
            
            chunks = []
            total_size = 0
            for row in cur.fetchall():
                chunk = dict(row)
                chunk['id'] = str(chunk['id'])
                total_size += chunk.get('size', 0)
                chunks.append(chunk)
            
            # Stats
            stats = {
                "total_chunks": len(chunks),
                "total_size": total_size,
                "avg_chunk_size": round(total_size / len(chunks), 2) if chunks else 0,
                "estimated_tokens": round(total_size / 4),
                "knowledge_name": knowledge['name'],
                "knowledge_type": knowledge['type']
            }
            
            return {"chunks": chunks, "stats": stats}
            
    except Exception as e:
        current_app.logger.error(f"Error getting knowledge chunks: {e}")
        return {"chunks": [], "stats": {}}
    finally:
        conn.close()


def list_knowledge(specialist_id: str) -> List[Dict[str, Any]]:
    """Liste les connaissances d'un spécialiste."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT k.*, 
                       COUNT(c.id) as chunk_count
                FROM specialist_knowledge k
                LEFT JOIN specialist_chunks c ON k.id = c.knowledge_id
                WHERE k.specialist_id = %s
                GROUP BY k.id
                ORDER BY k.created_at DESC
            """, (specialist_id,))
            
            results = []
            current_app.logger.info(f"Listing knowledge for specialist {specialist_id}")
            for row in cur.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])
                current_app.logger.info(f"Found knowledge {item['id']} ({item['name']}): {item['chunk_count']} chunks")
                item['specialist_id'] = str(item['specialist_id'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                # Ne pas retourner le contenu complet
                if item.get('content'):
                    item['content_preview'] = item['content'][:200] + '...' if len(item['content']) > 200 else item['content']
                    del item['content']
                results.append(item)
            
            return results
            
    finally:
        conn.close()


# ============== Recherche RAG ==============

def search_knowledge(
    specialist_id: str,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Recherche sémantique dans les connaissances d'un spécialiste.
    
    Args:
        specialist_id: ID du spécialiste
        query: Question/requête de l'utilisateur
        top_k: Nombre de résultats
        
    Returns:
        Liste de chunks pertinents avec score
    """
    init_db()
    
    # Générer l'embedding de la query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []
    
    # Padder l'embedding pour correspondre à la dimension de la table
    padded_query = pad_embedding(query_embedding, 2048)
    
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Recherche par similarité cosinus
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
    """
    Génère le contexte RAG pour une query.
    
    Returns:
        Tuple (contexte formaté, sources utilisées)
    """
    results = search_knowledge(specialist_id, query, top_k=5)
    
    if not results:
        return "", []
    
    # Formater le contexte
    context_parts = ["=== CONNAISSANCES DU SPÉCIALISTE ===\n"]
    sources = []
    
    for i, result in enumerate(results, 1):
        if result.get('score', 0) > 0.3:  # Seuil de pertinence
            context_parts.append(f"[{i}] Source: {result['source_name']}")
            context_parts.append(f"Contenu: {result['content']}\n")
            sources.append({
                'name': result['source_name'],
                'type': result['source_type'],
                'score': result['score']
            })
    
    context_parts.append("=== FIN DES CONNAISSANCES ===\n")
    
    return "\n".join(context_parts), sources


# ============== Gestion des Outils ==============

def add_tool(
    specialist_id: str,
    name: str,
    tool_type: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ajoute un outil/intégration au spécialiste.
    
    Args:
        specialist_id: ID du spécialiste
        name: Nom de l'outil
        tool_type: Type ('bookstack', 'api', 'custom')
        config: Configuration de l'outil
        
    Returns:
        Dict avec les infos de l'outil créé
    """
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO specialist_tools (specialist_id, name, type, config)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            """, (specialist_id, name, tool_type, json.dumps(config)))
            
            result = dict(cur.fetchone())
            conn.commit()
            
            result['id'] = str(result['id'])
            result['specialist_id'] = str(result['specialist_id'])
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            
            return result
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error adding tool: {e}")
        raise
    finally:
        conn.close()


def update_tool(
    tool_id: str,
    specialist_id: str,
    name: str = None,
    config: Dict[str, Any] = None,
    enabled: bool = None
) -> Optional[Dict[str, Any]]:
    """Met à jour un outil."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if config is not None:
                updates.append("config = %s")
                params.append(json.dumps(config))
            if enabled is not None:
                updates.append("enabled = %s")
                params.append(enabled)
            
            if not updates:
                return None
            
            params.extend([tool_id, specialist_id])
            
            cur.execute(f"""
                UPDATE specialist_tools 
                SET {', '.join(updates)}
                WHERE id = %s AND specialist_id = %s
                RETURNING *
            """, params)
            
            row = cur.fetchone()
            conn.commit()
            
            if not row:
                return None
            
            result = dict(row)
            result['id'] = str(result['id'])
            result['specialist_id'] = str(result['specialist_id'])
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            
            return result
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error updating tool: {e}")
        raise
    finally:
        conn.close()


def delete_tool(tool_id: str, specialist_id: str) -> bool:
    """Supprime un outil."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM specialist_tools 
                WHERE id = %s AND specialist_id = %s
                RETURNING id
            """, (tool_id, specialist_id))
            
            deleted = cur.fetchone() is not None
            conn.commit()
            return deleted
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting tool: {e}")
        raise
    finally:
        conn.close()


def list_tools(specialist_id: str) -> List[Dict[str, Any]]:
    """Liste les outils d'un spécialiste."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM specialist_tools 
                WHERE specialist_id = %s
                ORDER BY created_at DESC
            """, (specialist_id,))
            
            results = []
            for row in cur.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])
                item['specialist_id'] = str(item['specialist_id'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                results.append(item)
            
            return results
            
    finally:
        conn.close()


# ============== Sessions de Chat ==============

def create_session(specialist_id: str, user_id: str, title: str = None) -> Dict[str, Any]:
    """Crée une nouvelle session de chat."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO specialist_sessions (specialist_id, user_id, title)
                VALUES (%s, %s, %s)
                RETURNING *
            """, (specialist_id, user_id, title or "Nouvelle conversation"))
            
            result = dict(cur.fetchone())
            conn.commit()
            
            result['id'] = str(result['id'])
            result['specialist_id'] = str(result['specialist_id'])
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            if result.get('updated_at'):
                result['updated_at'] = result['updated_at'].isoformat()
            
            return result
            
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_sessions(specialist_id: str, user_id: str) -> List[Dict[str, Any]]:
    """Liste les sessions de chat d'un spécialiste."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT s.*, 
                       COUNT(m.id) as message_count,
                       MAX(m.created_at) as last_message_at
                FROM specialist_sessions s
                LEFT JOIN specialist_messages m ON s.id = m.session_id
                WHERE s.specialist_id = %s AND s.user_id = %s
                GROUP BY s.id
                ORDER BY COALESCE(MAX(m.created_at), s.created_at) DESC
            """, (specialist_id, user_id))
            
            results = []
            for row in cur.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])
                item['specialist_id'] = str(item['specialist_id'])
                for dt_field in ['created_at', 'updated_at', 'last_message_at']:
                    if item.get(dt_field):
                        item[dt_field] = item[dt_field].isoformat()
                results.append(item)
            
            return results
            
    finally:
        conn.close()


def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """Récupère les messages d'une session."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM specialist_messages 
                WHERE session_id = %s
                ORDER BY created_at ASC
            """, (session_id,))
            
            results = []
            for row in cur.fetchall():
                item = dict(row)
                item['id'] = str(item['id'])
                item['session_id'] = str(item['session_id'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                results.append(item)
            
            return results
            
    finally:
        conn.close()


def add_message(
    session_id: str,
    role: str,
    content: str,
    sources: List[Dict] = None
) -> Dict[str, Any]:
    """Ajoute un message à une session."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO specialist_messages (session_id, role, content, sources)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            """, (session_id, role, content, json.dumps(sources) if sources else None))
            
            result = dict(cur.fetchone())
            
            # Mettre à jour updated_at de la session
            cur.execute("""
                UPDATE specialist_sessions SET updated_at = NOW() WHERE id = %s
            """, (session_id,))
            
            conn.commit()
            
            result['id'] = str(result['id'])
            result['session_id'] = str(result['session_id'])
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            
            return result
            
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_session(session_id: str, specialist_id: str, user_id: str) -> bool:
    """Supprime une session et ses messages."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM specialist_sessions 
                WHERE id = %s AND specialist_id = %s AND user_id = %s
                RETURNING id
            """, (session_id, specialist_id, user_id))
            
            deleted = cur.fetchone() is not None
            conn.commit()
            return deleted
            
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_sessions(session_ids: List[str], specialist_id: str, user_id: str) -> int:
    """Supprime plusieurs sessions."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # PostgreSQL nécessite un tuple pour IN, mais avec un seul élément ça peut poser pb
            # On utilise ANY(array) qui est plus robuste
            cur.execute("""
                DELETE FROM specialist_sessions 
                WHERE id = ANY(%s::uuid[]) AND specialist_id = %s AND user_id = %s
                RETURNING id
            """, (session_ids, specialist_id, user_id))
            
            deleted_count = cur.rowcount
            conn.commit()
            return deleted_count
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting sessions bulk: {e}")
        raise
    finally:
        conn.close()


def delete_all_sessions(specialist_id: str, user_id: str) -> int:
    """Supprime toutes les sessions d'un spécialiste pour un utilisateur."""
    init_db()
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM specialist_sessions 
                WHERE specialist_id = %s AND user_id = %s
                RETURNING id
            """, (specialist_id, user_id))
            
            deleted_count = cur.rowcount
            conn.commit()
            return deleted_count
            
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting all sessions: {e}")
        raise
    finally:
        conn.close()
