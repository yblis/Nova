"""
Chat History Service - PostgreSQL Backend
Stockage de l'historique des conversations dans PostgreSQL pour des performances optimales.
"""

import os
import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from flask import current_app
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2 import pool

# Global connection pool
_connection_pool = None
_chat_db_initialized = False


def _get_pool():
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=current_app.config["POSTGRES_URL"]
            )
        except Exception as e:
            current_app.logger.warning(f"Could not create connection pool: {e}")
            return None
    return _connection_pool


def get_db_connection():
    """Get a connection from the pool or create a new one."""
    p = _get_pool()
    if p:
        try:
            return p.getconn()
        except Exception:
            pass
    # Fallback to direct connection
    return psycopg2.connect(current_app.config["POSTGRES_URL"])


def release_db_connection(conn):
    """Release a connection back to the pool."""
    p = _get_pool()
    if p and conn:
        try:
            p.putconn(conn)
            return
        except Exception:
            pass
    # Fallback: close connection
    if conn:
        try:
            conn.close()
        except Exception:
            pass


def init_chat_db():
    """
    Initialise les tables pour l'historique des conversations.
    Optimized: Only runs once per process.
    """
    global _chat_db_initialized
    
    if _chat_db_initialized:
        return
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if tables already exist (fast check)
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'chat_sessions'
            );
        """)
        tables_exist = cur.fetchone()[0]
        
        if not tables_exist:
            # Table des sessions de chat
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
                    model VARCHAR(255) NOT NULL,
                    system_prompt TEXT DEFAULT '',
                    model_config JSONB DEFAULT '{}',
                    is_pinned BOOLEAN DEFAULT FALSE,
                    latest_context JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Index pour les performances
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated 
                ON chat_sessions(updated_at DESC);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_pinned 
                ON chat_sessions(is_pinned);
            """)
            
            # Table des messages
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    thinking TEXT,
                    images TEXT[],
                    extra_data JSONB,
                    timestamp TIMESTAMP DEFAULT NOW()
                );
            """)
            
            # Index sur session_id
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session 
                ON chat_messages(session_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp 
                ON chat_messages(session_id, timestamp);
            """)
            
            conn.commit()
            current_app.logger.info("Chat history database tables created")
        
        cur.close()
        _chat_db_initialized = True
        current_app.logger.info("Chat history database initialized")
        
        # Migration: ajouter colonne extra_data si elle n'existe pas
        try:
            cur2 = conn.cursor()
            cur2.execute("""
                ALTER TABLE chat_messages 
                ADD COLUMN IF NOT EXISTS extra_data JSONB
            """)
            conn.commit()
            cur2.close()
        except Exception:
            pass  # Colonne existe déjà ou erreur ignorée
        
        # Tenter la migration depuis JSON si nécessaire
        migrate_from_json()
        
    except Exception as e:
        current_app.logger.error(f"Error initializing chat history database: {e}")
        raise
    finally:
        if conn:
            release_db_connection(conn)


def migrate_from_json():
    """
    Migre les données depuis l'ancien fichier JSON vers PostgreSQL.
    """
    data_dir = os.path.join(current_app.root_path, "..", "data")
    json_file = os.path.join(data_dir, "chat_history.json")
    backup_file = os.path.join(data_dir, "chat_history.json.backup")
    
    # Vérifier si le fichier JSON existe
    if not os.path.exists(json_file):
        return
    
    # Vérifier si la migration a déjà été faite
    if os.path.exists(backup_file):
        current_app.logger.info("JSON migration already completed (backup exists)")
        return
    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        sessions = data.get("sessions", [])
        if not sessions:
            current_app.logger.info("No sessions to migrate from JSON")
            return
        
        current_app.logger.info(f"Migrating {len(sessions)} sessions from JSON to PostgreSQL...")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        for session in sessions:
            session_id = session.get("id", str(uuid.uuid4()))
            
            # Vérifier si la session existe déjà
            cur.execute("SELECT id FROM chat_sessions WHERE id = %s", (session_id,))
            if cur.fetchone():
                continue
            
            # Insérer la session
            cur.execute("""
                INSERT INTO chat_sessions 
                (id, title, model, system_prompt, model_config, is_pinned, latest_context, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s))
            """, (
                session_id,
                session.get("title", "New Chat"),
                session.get("model", "unknown"),
                session.get("system_prompt", ""),
                Json(session.get("model_config", {})),
                session.get("is_pinned", False),
                Json(session.get("latest_context")) if session.get("latest_context") else None,
                session.get("created_at", datetime.now().timestamp()),
                session.get("updated_at", datetime.now().timestamp())
            ))
            
            # Insérer les messages
            for msg in session.get("messages", []):
                cur.execute("""
                    INSERT INTO chat_messages 
                    (session_id, role, content, thinking, images, timestamp)
                    VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                """, (
                    session_id,
                    msg.get("role", "user"),
                    msg.get("content", ""),
                    msg.get("thinking"),
                    msg.get("images"),
                    msg.get("timestamp", datetime.now().timestamp())
                ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Renommer le fichier JSON en backup
        os.rename(json_file, backup_file)
        current_app.logger.info(f"Migration completed. JSON file backed up to {backup_file}")
        
    except Exception as e:
        current_app.logger.error(f"Error migrating from JSON: {e}")
        # Ne pas bloquer l'application si la migration échoue


class ChatHistoryService:
    """Service pour gérer l'historique des conversations avec PostgreSQL."""
    
    def __init__(self, data_dir: str = None):
        """
        Initialise le service.
        data_dir est ignoré (conservé pour compatibilité).
        """
        init_chat_db()
    
    def list_sessions(self) -> List[Dict]:
        """
        Liste toutes les sessions (métadonnées uniquement).
        Triées par: épinglées d'abord, puis par date de mise à jour.
        """
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("""
                SELECT 
                    id, title, model, is_pinned, 
                    EXTRACT(EPOCH FROM created_at) as created_at,
                    EXTRACT(EPOCH FROM updated_at) as updated_at
                FROM chat_sessions
                ORDER BY is_pinned DESC, updated_at DESC
            """)
            
            sessions = []
            for row in cur.fetchall():
                sessions.append({
                    "id": str(row["id"]),
                    "title": row["title"],
                    "model": row["model"],
                    "is_pinned": row["is_pinned"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
            
            return sessions
            
        except Exception as e:
            current_app.logger.error(f"Error listing sessions: {e}")
            return []
        finally:
            cur.close()
            release_db_connection(conn)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Récupère une session complète avec ses messages."""
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Récupérer la session
            cur.execute("""
                SELECT 
                    id, title, model, system_prompt, model_config, is_pinned, latest_context,
                    EXTRACT(EPOCH FROM created_at) as created_at,
                    EXTRACT(EPOCH FROM updated_at) as updated_at
                FROM chat_sessions
                WHERE id = %s
            """, (session_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            session = {
                "id": str(row["id"]),
                "title": row["title"],
                "model": row["model"],
                "system_prompt": row["system_prompt"] or "",
                "model_config": row["model_config"] or {},
                "is_pinned": row["is_pinned"],
                "latest_context": row["latest_context"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "messages": []
            }
            
            # Récupérer les messages
            cur.execute("""
                SELECT 
                    role, content, thinking, images, extra_data,
                    EXTRACT(EPOCH FROM timestamp) as timestamp
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY timestamp ASC
            """, (session_id,))
            
            for msg_row in cur.fetchall():
                message = {
                    "role": msg_row["role"],
                    "content": msg_row["content"],
                    "timestamp": msg_row["timestamp"]
                }
                if msg_row["thinking"]:
                    message["thinking"] = msg_row["thinking"]
                if msg_row["images"]:
                    message["images"] = msg_row["images"]
                if msg_row["extra_data"]:
                    message["extra_data"] = msg_row["extra_data"]
                session["messages"].append(message)
            
            return session
            
        except Exception as e:
            current_app.logger.error(f"Error getting session {session_id}: {e}")
            return None
        finally:
            cur.close()
            release_db_connection(conn)
    
    def create_session(self, model: str, title: str = "New Chat") -> str:
        """Crée une nouvelle session et retourne son ID."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            session_id = str(uuid.uuid4())
            default_config = {
                "temperature": 0.7,
                "num_ctx": 4096,
                "top_p": 0.9,
                "top_k": 40
            }
            
            cur.execute("""
                INSERT INTO chat_sessions (id, title, model, model_config)
                VALUES (%s, %s, %s, %s)
            """, (session_id, title, model, Json(default_config)))
            
            conn.commit()
            return session_id
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error creating session: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def add_message(self, session_id: str, role: str, content: str, 
                    thinking: str = None, images: list = None, extra_data: dict = None):
        """Ajoute un message à une session."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO chat_messages (session_id, role, content, thinking, images, extra_data)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session_id, role, content, thinking, images, json.dumps(extra_data) if extra_data else None))
            
            # Mettre à jour updated_at de la session
            cur.execute("""
                UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s
            """, (session_id,))
            
            # Auto-update title si premier message utilisateur et titre par défaut
            if role == "user":
                cur.execute("""
                    SELECT title, (SELECT COUNT(*) FROM chat_messages WHERE session_id = %s AND role = 'user') as user_count
                    FROM chat_sessions WHERE id = %s
                """, (session_id, session_id))
                row = cur.fetchone()
                if row and row[0] == "New Chat" and row[1] <= 1:
                    # Générer un titre basé sur le début du message
                    try:
                        from .llm_config_service import is_auto_title_enabled
                        if not is_auto_title_enabled():
                            new_title = content[:30] + "..." if len(content) > 30 else content
                            cur.execute("""
                                UPDATE chat_sessions SET title = %s WHERE id = %s
                            """, (new_title, session_id))
                    except Exception:
                        new_title = content[:30] + "..." if len(content) > 30 else content
                        cur.execute("""
                            UPDATE chat_sessions SET title = %s WHERE id = %s
                        """, (new_title, session_id))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error adding message: {e}")
            raise ValueError(f"Session not found or error: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_message_extra_data(self, session_id: str, message_index: int, extra_data: dict) -> bool:
        """
        Met à jour le extra_data d'un message spécifique.
        
        Args:
            session_id: ID de la session
            message_index: Index du message (0-based)
            extra_data: Nouveau extra_data
            
        Returns:
            True si mis à jour avec succès
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Récupérer l'ID du message par son index
            cur.execute("""
                SELECT id FROM chat_messages
                WHERE session_id = %s
                ORDER BY timestamp ASC
                LIMIT 1 OFFSET %s
            """, (session_id, message_index))
            
            result = cur.fetchone()
            if not result:
                return False
            
            message_id = result[0]
            
            # Mettre à jour extra_data
            cur.execute("""
                UPDATE chat_messages
                SET extra_data = %s
                WHERE id = %s
            """, (Json(extra_data) if extra_data else None, message_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error updating message extra_data: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    
    def delete_session(self, session_id: str):
        """Supprime une session (les messages sont supprimés en cascade)."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error deleting session: {e}")
        finally:
            cur.close()
            conn.close()
    
    def update_session_context(self, session_id: str, context: List[int]):
        """Met à jour le contexte de la session."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE chat_sessions SET latest_context = %s WHERE id = %s
            """, (Json(context), session_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error updating context: {e}")
            raise ValueError("Session not found")
        finally:
            cur.close()
            conn.close()
    
    def update_session_settings(self, session_id: str, system_prompt: str = None,
                                model_config: Dict = None, title: str = None) -> Dict:
        """Met à jour les paramètres d'une session."""
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            updates = []
            params = []
            
            if system_prompt is not None:
                updates.append("system_prompt = %s")
                params.append(system_prompt)
            
            if model_config is not None:
                # Fusionner avec la config existante
                cur.execute("SELECT model_config FROM chat_sessions WHERE id = %s", (session_id,))
                row = cur.fetchone()
                if row:
                    existing = row["model_config"] or {}
                    existing.update(model_config)
                    updates.append("model_config = %s")
                    params.append(Json(existing))
            
            if title is not None:
                updates.append("title = %s")
                params.append(title)
            
            if updates:
                updates.append("updated_at = NOW()")
                params.append(session_id)
                
                cur.execute(f"""
                    UPDATE chat_sessions SET {', '.join(updates)} WHERE id = %s
                """, tuple(params))
                conn.commit()
            
            # Retourner la session mise à jour
            return self.get_session(session_id)
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error updating session settings: {e}")
            raise ValueError("Session not found")
        finally:
            cur.close()
            conn.close()
    
    def toggle_session_pin(self, session_id: str) -> bool:
        """Toggle l'état épinglé d'une session. Retourne le nouvel état."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE chat_sessions 
                SET is_pinned = NOT is_pinned 
                WHERE id = %s
                RETURNING is_pinned
            """, (session_id,))
            
            row = cur.fetchone()
            if not row:
                raise ValueError("Session not found")
            
            conn.commit()
            return row[0]
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error toggling pin: {e}")
            raise ValueError("Session not found")
        finally:
            cur.close()
            conn.close()
    
    def delete_sessions(self, session_ids: List[str]) -> int:
        """Supprime plusieurs sessions. Retourne le nombre supprimé."""
        if not session_ids:
            return 0
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Use the same pattern as delete_session (single) - loop through each ID
            deleted_count = 0
            for session_id in session_ids:
                cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
                deleted_count += cur.rowcount
            
            conn.commit()
            return deleted_count
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error deleting sessions: {e}")
            return 0
        finally:
            cur.close()
            conn.close()
    
    def delete_all_sessions(self) -> int:
        """Supprime toutes les sessions. Retourne le nombre supprimé."""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT COUNT(*) FROM chat_sessions")
            count = cur.fetchone()[0]
            
            cur.execute("DELETE FROM chat_sessions")
            conn.commit()
            return count
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error deleting all sessions: {e}")
            return 0
        finally:
            cur.close()
            conn.close()
