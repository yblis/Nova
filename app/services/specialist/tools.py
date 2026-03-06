import json
from typing import List, Dict, Optional, Any

from flask import current_app
from psycopg2.extras import RealDictCursor

from .database import get_db_connection, init_db


def add_tool(
    specialist_id: str,
    name: str,
    tool_type: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
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
