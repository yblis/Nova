import json
from typing import List, Dict, Any

from flask import current_app
from psycopg2.extras import RealDictCursor

from .database import get_db_connection, init_db


def create_session(specialist_id: str, user_id: str, title: str = None) -> Dict[str, Any]:
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
    init_db()
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
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
