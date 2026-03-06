import os
import re
import uuid
import json
from typing import List, Dict, Any

from flask import current_app
from psycopg2.extras import RealDictCursor

from .database import get_db_connection, init_db, pad_embedding
from ..embedding_service import generate_embedding, generate_embeddings_batch, get_embedding_model
from ..pdf_service import process_pdf, chunk_text


def add_knowledge_text(
    specialist_id: str,
    name: str,
    content: str,
    knowledge_type: str = "text"
) -> Dict[str, Any]:
    init_db()
    conn = get_db_connection()

    content = content.replace('\x00', '') if content else ''
    name = name.replace('\x00', '') if name else ''

    try:
        knowledge_id = str(uuid.uuid4())
        embedding_model = get_embedding_model()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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

            chunks = chunk_text(content, chunk_size=500, overlap=50)

            if chunks and embedding_model:
                texts = [c['content'] for c in chunks]
                current_app.logger.info(f"Generating embeddings for {len(texts)} chunks")
                embeddings = generate_embeddings_batch(texts)

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
    init_db()

    ext = os.path.splitext(filename)[1].lower()

    if ext == '.pdf':
        text, chunks = process_pdf(file_bytes, filename)
        knowledge_type = 'pdf'
    elif ext in ['.txt', '.md', '.py', '.js', '.json', '.csv', '.html', '.css', '.yaml', '.yml']:
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('latin-1')
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        knowledge_type = 'text_file'
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
        knowledge_type = 'image'
        text = None
        chunks = []
    else:
        raise ValueError(f"Unsupported file type: {ext}")

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
            cur.execute("""
                INSERT INTO specialist_knowledge
                    (id, specialist_id, type, name, content, file_path, embedding_model, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                knowledge_id, specialist_id, knowledge_type, filename,
                text[:10000] if text else None,
                file_path, embedding_model, json.dumps(metadata)
            ))

            knowledge = dict(cur.fetchone())

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
        if os.path.exists(file_path):
            os.remove(file_path)
        current_app.logger.error(f"Error adding file knowledge: {e}")
        raise
    finally:
        conn.close()


def add_knowledge_web(specialist_id: str, url: str) -> Dict[str, Any]:
    from ..web_search_service import get_searxng_url, is_searxng_available
    import httpx
    from html.parser import HTMLParser

    content = None
    title = url
    method_used = "direct"

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
                if text and len(text) > 2:
                    self.text_parts.append(text)

    direct_error = None
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        with httpx.Client(timeout=30.0, follow_redirects=True, http2=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            encoding = response.encoding or 'utf-8'
            try:
                html_content = response.content.decode(encoding)
            except UnicodeDecodeError:
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

            content = "".join(ch for ch in content if ch.isprintable() or ch in '\n\r\t ')

            title_match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else url

    except Exception as e:
        direct_error = e
        current_app.logger.warning(f"Direct fetch failed for {url}: {e}")

    if content is None or len(content.strip()) < 100:
        if is_searxng_available():
            try:
                searxng_url = get_searxng_url()

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
                            for result in results:
                                result_url = result.get("url", "")
                                if url in result_url or result_url in url:
                                    title = result.get("title", url)
                                    content = result.get("content", result.get("snippet", ""))
                                    break

                            if not content and results:
                                title = results[0].get("title", url)
                                content = results[0].get("content", results[0].get("snippet", ""))

                        if content:
                            current_app.logger.info(f"Retrieved content via SearXNG for {url}")

            except Exception as e:
                current_app.logger.warning(f"SearXNG fallback failed for {url}: {e}")

    if not content or len(content.strip()) < 50:
        if direct_error:
            import httpx as httpx_mod
            if isinstance(direct_error, httpx_mod.HTTPStatusError):
                status_code = direct_error.response.status_code
                if status_code == 403:
                    raise ValueError(f"Accès refusé (403): Ce site bloque les requêtes automatiques. Essayez de copier-coller le contenu manuellement.")
                elif status_code == 404:
                    raise ValueError(f"Page non trouvée (404): L'URL n'existe pas.")
                else:
                    raise ValueError(f"Erreur HTTP {status_code}: Impossible d'accéder à cette URL.")
            elif isinstance(direct_error, httpx_mod.TimeoutException):
                raise ValueError("Timeout: Le site met trop de temps à répondre.")
            else:
                raise ValueError(f"Impossible de récupérer l'URL: {str(direct_error)}")
        else:
            raise ValueError("Contenu insuffisant récupéré depuis cette URL.")

    content = content.replace('\x00', '').replace('\u0000', '')
    title = title.replace('\x00', '').replace('\u0000', '')

    current_app.logger.info(f"Adding web knowledge from {url} (method: {method_used}, content length: {len(content)})")
    return add_knowledge_text(
        specialist_id=specialist_id,
        name=title[:200],
        content=content[:50000],
        knowledge_type="web_url"
    )


def delete_knowledge(knowledge_id: str, specialist_id: str) -> bool:
    init_db()
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT file_path FROM specialist_knowledge
                WHERE id = %s AND specialist_id = %s
            """, (knowledge_id, specialist_id))

            row = cur.fetchone()
            if not row:
                return False

            file_path = row[0]

            cur.execute("""
                DELETE FROM specialist_knowledge
                WHERE id = %s AND specialist_id = %s
                RETURNING id
            """, (knowledge_id, specialist_id))

            deleted = cur.fetchone() is not None
            conn.commit()

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
    init_db()
    conn = get_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, type FROM specialist_knowledge
                WHERE id = %s AND specialist_id = %s
            """, (knowledge_id, specialist_id))

            knowledge = cur.fetchone()
            if not knowledge:
                return {"chunks": [], "stats": {}}

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
                if item.get('content'):
                    item['content_preview'] = item['content'][:200] + '...' if len(item['content']) > 200 else item['content']
                    del item['content']
                results.append(item)

            return results

    finally:
        conn.close()
