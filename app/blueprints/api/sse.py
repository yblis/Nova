from __future__ import annotations

from flask import Blueprint, Response, request, current_app
from ...services.progress_bus import ProgressBus


sse_bp = Blueprint("sse", __name__)


@sse_bp.get("/progress")
def progress_stream() -> Response:
    job_id = request.args.get("job_id")
    if not job_id:
        return Response("missing job_id", status=400)
    
    # Check if we have a pending synchronous pull for this job_id
    sync_pulls = getattr(current_app, '_sync_pulls', {})
    print(f"DEBUG SSE: job_id={job_id}, sync_pulls keys={list(sync_pulls.keys())}, has_redis={bool(getattr(current_app, 'redis', None))}")
    
    if job_id in sync_pulls and not getattr(current_app, "redis", None):
        pull_info = sync_pulls[job_id]
        print(f"DEBUG SSE: Found pending pull for {job_id}: {pull_info}")
        
        # Capture all config values BEFORE the generator (while still in app context)
        name = pull_info['name']
        base_url = pull_info.get('base_url')
        ollama_url = base_url or current_app.config.get("OLLAMA_BASE_URL")
        connect_timeout = current_app.config.get("HTTP_CONNECT_TIMEOUT", 10)
        read_timeout = current_app.config.get("HTTP_READ_TIMEOUT", 600)
        
        def sync_pull_stream():
            import json
            from ...services.ollama_client import OllamaClient
            
            try:
                print(f"DEBUG SSE: Starting pull stream for {name}", flush=True)
                msg = f"data: {json.dumps({'status': f'Démarrage pull {name}...', 'progress': 0})}\n\n"
                print(f"DEBUG SSE: Yielding initial message", flush=True)
                yield msg.encode('utf-8')
                
                # Create Ollama client with pre-captured config
                print(f"DEBUG SSE: Creating client with URL: {ollama_url}", flush=True)
                client = OllamaClient(
                    base_url=ollama_url,
                    connect_timeout=connect_timeout,
                    read_timeout=read_timeout,
                )
                
                # Stream the pull
                total = None
                completed = 0
                chunk_count = 0
                print(f"DEBUG SSE: Starting client.pull_stream({name})", flush=True)
                
                for chunk in client.pull_stream(name):
                    chunk_count += 1
                    status = chunk.get("status", "")
                    total = chunk.get("total", total)
                    completed = chunk.get("completed", completed)
                    progress = (completed / total) if total and total > 0 else 0
                    
                    payload = {"progress": max(0, min(1, progress))}
                    if status:
                        payload["status"] = status
                    
                    if chunk_count <= 5 or chunk_count % 50 == 0:
                        print(f"DEBUG SSE: Chunk #{chunk_count}: {payload}", flush=True)
                    
                    yield f"data: {json.dumps(payload)}\n\n".encode('utf-8')
                
                # Done
                print(f"DEBUG SSE: Pull complete after {chunk_count} chunks", flush=True)
                yield f"data: {json.dumps({'status': 'Terminé', 'progress': 1.0, 'done': True})}\n\n".encode('utf-8')
                
                # Cleanup
                if job_id in sync_pulls:
                    del sync_pulls[job_id]
                    
            except Exception as e:
                print(f"DEBUG SSE: Exception during pull: {e}", flush=True)
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'error': str(e)})}\n\n".encode('utf-8')
        
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
        return Response(sync_pull_stream(), headers=headers)
    
    # Original fallback for dev mode without Redis (no pending pull)
    if not getattr(current_app, "redis", None):
        def mock_stream():
             import time
             import json
             try:
                 yield f"data: {json.dumps({'status': 'Aucun téléchargement en cours', 'progress': 0})}\n\n"
                 yield f"data: {json.dumps({'error': 'Redis non configuré - téléchargement non possible'})}\n\n"
             except: pass
        
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        return Response(mock_stream(), headers=headers)

    try:
        bus = ProgressBus(current_app.redis)  # type: ignore[attr-defined]
    except Exception:
         # Double check connection failure fallback
         return Response("Erreur de connexion Redis", status=503)

    def event_stream():
        import json
        import time
        
        last_status_hash = None
        max_wait_seconds = 300  # 5 minutes max
        poll_interval = 0.5  # Check every 500ms
        start_time = time.time()
        
        try:
            while time.time() - start_time < max_wait_seconds:
                # Get current status from Redis
                current = bus.get_last_status(job_id)
                
                if current:
                    # Create a hash to detect changes
                    current_hash = json.dumps(current, sort_keys=True)
                    
                    # Only yield if status changed
                    if current_hash != last_status_hash:
                        last_status_hash = current_hash
                        yield f"data: {json.dumps(current)}\n\n"
                        
                        # If done or error, we're finished
                        if current.get("done") or current.get("error"):
                            return
                
                # Small sleep to avoid hammering Redis
                time.sleep(poll_interval)
            
            # Timeout reached
            yield f"data: {{\"error\": \"Timeout: le job n'a pas répondu dans le délai imparti\"}}\n\n"
            
        except Exception as e:
            # If Redis connection fails during streaming, send an error message
            yield f"data: {{\"error\": \"Erreur de connexion Redis: {str(e)}\"}}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # for nginx
        "Connection": "keep-alive",
    }
    return Response(event_stream(), headers=headers)
