import os
from typing import List, Dict, Optional, Any

from flask import current_app
from psycopg2.extras import RealDictCursor

from .database import get_db_connection, init_db


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
    init_db()
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
    init_db()
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT file_path FROM specialist_knowledge
                WHERE specialist_id = %s AND file_path IS NOT NULL
            """, (specialist_id,))

            file_paths = [row[0] for row in cur.fetchall()]

            cur.execute("""
                DELETE FROM specialists
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (specialist_id, user_id))

            deleted = cur.fetchone() is not None
            conn.commit()

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
