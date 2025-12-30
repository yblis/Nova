from __future__ import annotations

import os
import re
import hashlib
import httpx
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import current_app

from .ollama_client import OllamaClient, BlobUploadedWithoutPath
from .huggingface_client import HuggingFaceClient
from .progress_bus import ProgressBus


def _client(base_url: str | None = None) -> OllamaClient:
    return OllamaClient(
        base_url=base_url or current_app.config["OLLAMA_BASE_URL"],
        connect_timeout=current_app.config["HTTP_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["HTTP_READ_TIMEOUT"],
    )


def _hf_client() -> HuggingFaceClient:
    return HuggingFaceClient(
        hf_token=current_app.config.get("HF_TOKEN"),
        connect_timeout=current_app.config["HTTP_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["HTTP_READ_TIMEOUT"],
    )


def enqueue_pull_model(name: str, base_url: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    
    # If RQ is not configured, do synchronous pull
    if getattr(current_app, "rq", None) is None:
        # Try to do synchronous pull directly
        try:
            client = _client(base_url)
            # Just trigger the pull - we'll track via SSE mock or direct response
            # Store the pull generator in app context for SSE to consume
            if not hasattr(current_app, '_sync_pulls'):
                current_app._sync_pulls = {}
            current_app._sync_pulls[job_id] = {
                'name': name,
                'base_url': base_url,
                'status': 'pending'
            }
        except Exception as e:
            print(f"DEBUG: Sync pull setup error: {e}")
        return job_id
        
    try:
        current_app.rq.enqueue(pull_model_job, job_id, name, base_url, job_timeout=current_app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600))  # type: ignore[attr-defined]
        
        # Track job in history
        if getattr(current_app, "redis", None):
            try:
                # Add to history list (limited to 50 items)
                current_app.redis.lpush("downloads:history", job_id)
                current_app.redis.ltrim("downloads:history", 0, 49)
                # Store initial metadata for the job so we can list it even if progress hasn't started
                import json
                initial_meta = {
                    "name": name,
                    "type": "pull",
                    "status": "pending",
                    "created_at": __import__("time").time()
                }
                current_app.redis.setex(f"job_meta:{job_id}", 86400, json.dumps(initial_meta))
            except Exception:
                pass
    except Exception as e:
        # Handle Redis connection errors
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": f"Erreur Redis: {str(e)}"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
    return job_id


def enqueue_check_update(name: str, base_url: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    if getattr(current_app, "rq", None) is None:  # type: ignore[attr-defined]
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": "RQ non configuré"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
        return job_id
    try:
        current_app.rq.enqueue(check_update_job, job_id, name, base_url, job_timeout=current_app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600))  # type: ignore[attr-defined]
    except Exception as e:
        # Handle Redis connection errors
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": f"Erreur Redis: {str(e)}"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
    return job_id


def enqueue_eject_force(base_url: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    if getattr(current_app, "rq", None) is None:  # type: ignore[attr-defined]
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": "RQ non configuré"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
        return job_id
    try:
        current_app.rq.enqueue(eject_force_job, job_id, base_url, job_timeout=current_app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600))  # type: ignore[attr-defined]
    except Exception as e:
        # Handle Redis connection errors
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": f"Erreur Redis: {str(e)}"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
    return job_id


def pull_model_job(job_id: str, name: str, base_url: str | None = None) -> None:
    
    # Import here to avoid circular imports
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            bus = ProgressBus(current_app.redis)
            bus.publish(job_id, {"status": f"Démarrage pull {name}"})
        except Exception:
            # If Redis is not available, we can't publish progress
            return
            
        try:
            total = None
            completed = 0
            for chunk in _client(base_url).pull_stream(name):
                status = chunk.get("status")
                error = chunk.get("error")
                if error:
                    try:
                        bus.publish(job_id, {"error": error})
                    except Exception:
                        pass
                    return

                total = chunk.get("total", total)
                completed = chunk.get("completed", completed)
                progress = (completed / total) if total else None
                payload: Dict[str, Any] = {}
                if status:
                    payload["status"] = status
                if progress is not None:
                    payload["progress"] = max(0.0, min(1.0, float(progress)))
                if payload:
                    try:
                        bus.publish(job_id, payload)
                    except Exception:
                        pass  # Ignore Redis errors
            
            # Pull terminé - mettre à jour les métadonnées du modèle
            try:
                bus.publish(job_id, {"status": "Mise à jour des métadonnées..."})
                from .model_metadata_service import refresh_model_metadata
                refresh_model_metadata(name)
            except Exception as meta_error:
                print(f"[PullModel] Failed to refresh metadata for {name}: {meta_error}")
            
            try:
                bus.publish(job_id, {"done": True, "status": "Terminé"})
            except Exception:
                pass  # Ignore Redis errors
        except Exception as e:
            try:
                bus.publish(job_id, {"error": str(e)})
            except Exception:
                pass  # Ignore Redis errors


def check_update_job(job_id: str, name: str, base_url: str | None = None) -> None:
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            bus = ProgressBus(current_app.redis)
        except Exception:
            # If Redis is not available, we can't publish progress
            return
            
        try:
            for chunk in _client(base_url).pull_stream(name):
                status = (chunk.get("status") or "").lower()
                if "up to date" in status:
                    try:
                        bus.publish(job_id, {"status": "À jour", "done": True})
                    except Exception:
                        pass  # Ignore Redis errors
                    return
                if any(k in status for k in ["downloading", "verifying", "extracting"]):
                    try:
                        bus.publish(job_id, {"status": "Mise à jour dispo", "done": True})
                    except Exception:
                        pass  # Ignore Redis errors
                    return
            try:
                bus.publish(job_id, {"status": "Inconnu", "done": True})
            except Exception:
                pass  # Ignore Redis errors
        except Exception as e:
            try:
                bus.publish(job_id, {"error": str(e)})
            except Exception:
                pass  # Ignore Redis errors


def eject_force_job(job_id: str, base_url: str | None = None) -> None:
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            bus = ProgressBus(current_app.redis)
            bus.publish(job_id, {"status": "Éjection forcée…"})
        except Exception:
            # If Redis is not available, we can't publish progress
            return
            
        try:
            # naive loop: call ps until empty
            for _ in range(10):
                procs = _client(base_url).ps().get("models", [])
                if not procs:
                    try:
                        bus.publish(job_id, {"done": True, "status": "Aucun modèle en cours"})
                    except Exception:
                        pass  # Ignore Redis errors
                    return
            try:
                bus.publish(job_id, {"done": True, "status": "Toujours en cours"})
            except Exception:
                pass  # Ignore Redis errors
        except Exception as e:
            try:
                bus.publish(job_id, {"error": str(e)})
            except Exception:
                pass  # Ignore Redis errors


def enqueue_pull_gguf(
    model_id: str,
    filename: str,
    output_dir: str | None = None,
    base_url: str | None = None,
) -> str:
    """
    Enqueue a job to download a GGUF model from HuggingFace

    Args:
        model_id: HuggingFace model ID (e.g., "TheBloke/Llama-2-7B-GGUF")
        filename: GGUF filename to download
        output_dir: Optional output directory (defaults to /tmp/gguf_models)

    Returns:
        Job ID for progress tracking
    """
    job_id = uuid.uuid4().hex
    if getattr(current_app, "rq", None) is None:  # type: ignore[attr-defined]
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": "RQ non configuré"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
        return job_id
    try:
        current_app.rq.enqueue(pull_gguf_job, job_id, model_id, filename, output_dir, base_url, job_timeout=current_app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600))  # type: ignore[attr-defined]
        
        # Track job in history
        if getattr(current_app, "redis", None):
            try:
                # Add to history list (limited to 50 items)
                current_app.redis.lpush("downloads:history", job_id)
                current_app.redis.ltrim("downloads:history", 0, 49)
                # Store initial metadata
                import json
                initial_meta = {
                    "name": filename,  # Using filename as name for GGUF
                    "type": "pull_gguf",
                    "status": "pending",
                    "created_at": __import__("time").time(),
                    "details": {"model_id": model_id, "output_dir": output_dir}
                }
                current_app.redis.setex(f"job_meta:{job_id}", 86400, json.dumps(initial_meta))
            except Exception:
                pass
    except Exception as e:
        # Handle Redis connection errors
        if getattr(current_app, "redis", None):  # type: ignore[attr-defined]
            try:
                ProgressBus(current_app.redis).publish(job_id, {"error": f"Erreur Redis: {str(e)}"})  # type: ignore[arg-type]
            except Exception:
                pass  # Ignore Redis errors
    return job_id


def pull_gguf_job(
    job_id: str,
    model_id: str,
    filename: str,
    output_dir: str | None = None,
    base_url: str | None = None,
) -> None:
    """
    Worker job to download a GGUF model from HuggingFace

    Args:
        job_id: Job ID for progress tracking
        model_id: HuggingFace model ID
        filename: GGUF filename to download
        output_dir: Output directory for downloaded file
    """
    print(f"DEBUG: pull_gguf_job called with job_id={job_id}, model_id={model_id}, filename={filename}, output_dir={output_dir}")
    
    # Import here to avoid circular imports
    from app import create_app
    
    # Create application context
    app = create_app()
    
    with app.app_context():
        try:
            print(f"DEBUG: Creating ProgressBus with Redis...")
            bus = ProgressBus(app.redis)  # Use app.redis instead of current_app.redis
            print(f"DEBUG: Publishing initial status message...")
            bus.publish(job_id, {"status": f"Démarrage téléchargement {filename}"})
            print(f"DEBUG: Initial status published successfully")
        except Exception as e:
            # If Redis is not available, we can't publish progress
            print(f"DEBUG: Exception in ProgressBus setup: {e}")
            return

        try:
            print(f"DEBUG: Starting download process...")
            
            # Determine output path
            if output_dir is None:
                # Use the Docker volume path instead of /tmp
                output_dir = os.path.join("/app", "models")
                print(f"DEBUG: Using default output_dir: {output_dir}")
            else:
                print(f"DEBUG: Using provided output_dir: {output_dir}")
                
            output_path = Path(output_dir) / filename
            print(f"DEBUG: Full output path: {output_path}")
            
            # Ensure the output directory exists
            print(f"DEBUG: Creating directory {output_path.parent}...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"DEBUG: Directory created successfully")
            print(f"DEBUG: Output directory: {output_path.parent}")
            print(f"DEBUG: Output file path: {output_path}")

            # Download with progress tracking
            print(f"DEBUG: Creating HuggingFace client...")
            hf_client = _hf_client()
            print(f"DEBUG: HuggingFace client created: {hf_client}")
            
            print(f"DEBUG: Starting download stream for model_id={model_id}, filename={filename}")
            total = None
            completed = 0
            chunk_count = 0
            
            for chunk in hf_client.download_gguf_stream(model_id, filename, output_path):
                chunk_count += 1
                print(f"DEBUG: Received chunk #{chunk_count}: {chunk}")
                status = chunk.get("status")
                total = chunk.get("total", total)
                completed = chunk.get("completed", completed)
                progress = (completed / total) if total else None

                payload: Dict[str, Any] = {}
                if status:
                    payload["status"] = status
                if progress is not None:
                    payload["progress"] = max(0.0, min(1.0, float(progress)))
                if payload:
                    try:
                        bus.publish(job_id, payload)
                    except Exception:
                        pass  # Ignore Redis errors

            print(f"DEBUG: Download loop completed. Total chunks processed: {chunk_count}")
            
            try:
                completion_msg = {
                    "status": f"Téléchargement terminé: {output_path}",
                    "file_path": str(output_path)
                }
                print(f"DEBUG: Publishing completion message (no done yet): {completion_msg}")
                bus.publish(job_id, completion_msg)
                print(f"DEBUG: Download completion message published; proceeding to model creation")
            except Exception as e:
                print(f"DEBUG: Exception publishing completion: {e}")
                pass  # Ignore Redis errors

            # Post-download: upload the GGUF file to Ollama via blob API and create model
            # Since the Ollama server is remote, we need to upload the file content via the API
            try:
                bus.publish(job_id, {"status": "Préparation création modèle Ollama (calcul SHA256…)"})
            except Exception:
                pass

            # Compute digest for blob identification
            digest = None
            try:
                sha = hashlib.sha256()
                with open(output_path, "rb") as f:
                    for blk in iter(lambda: f.read(1024 * 1024), b""):
                        sha.update(blk)
                digest = "sha256:" + sha.hexdigest()
                print(f"DEBUG: Computed digest: {digest}")
                try:
                    bus.publish(job_id, {"status": f"Empreinte calculée: {digest[:18]}…"})
                except Exception:
                    pass
            except Exception as e:
                print(f"DEBUG: Failed to compute sha256: {e}")
                try:
                    bus.publish(job_id, {"error": f"Impossible de calculer l'empreinte SHA256: {e}"})
                except Exception:
                    pass
                return

            # Connect to Ollama at the effective endpoint (if provided)
            try:
                oc = _client(base_url)
            except Exception as e:
                print(f"DEBUG: Failed to init OllamaClient: {e}")
                try:
                    bus.publish(job_id, {"error": f"Impossible de se connecter à Ollama: {e}"})
                except Exception:
                    pass
                return

            # Upload the blob to Ollama server
            try:
                try:
                    bus.publish(job_id, {"status": "Téléversement du fichier GGUF vers Ollama…"})
                except Exception:
                    pass

                # Define progress callback for blob upload
                last_progress = [0]  # Use list to allow modification in closure

                def upload_progress_callback(bytes_uploaded, total_bytes):
                    progress = bytes_uploaded / total_bytes if total_bytes > 0 else 0
                    # Only publish every 5% to avoid flooding Redis
                    if progress - last_progress[0] >= 0.05:
                        last_progress[0] = progress
                        try:
                            bus.publish(job_id, {
                                "status": f"Upload vers Ollama: {bytes_uploaded / 1024 / 1024:.1f} / {total_bytes / 1024 / 1024:.1f} MB",
                                "progress": progress
                            })
                        except Exception:
                            pass

                # Upload the blob - this will transfer the file to the Ollama server
                oc.create_blob(digest, str(output_path), progress_callback=upload_progress_callback)
                print(f"DEBUG: Blob uploaded successfully with digest: {digest}")

                try:
                    bus.publish(job_id, {"status": f"Fichier GGUF téléversé sur le serveur Ollama"})
                except Exception:
                    pass
            except BlobUploadedWithoutPath as e:
                # L'upload a réussi même si le chemin n'a pas été retourné
                print(f"DEBUG: Blob uploaded but no path returned: {e}")
                try:
                    bus.publish(job_id, {"status": f"Fichier GGUF téléversé (HTTP {e.status_code})"})
                except Exception:
                    pass
            except Exception as e:
                print(f"DEBUG: create_blob error: {e}")
                try:
                    bus.publish(job_id, {"error": f"Erreur lors du téléversement: {e}"})
                except Exception:
                    pass
                return

            # Create the model using the uploaded blob
            # When using uploaded blobs, we must use the 'files' parameter instead of a Modelfile
            model_name = Path(filename).stem

            # Use the files parameter to reference the uploaded blob by filename and digest
            # This is the correct API format for creating models from uploaded GGUF blobs
            files = {filename: digest}

            created = False
            last_error = None

            try:
                modelfile_content = f"FROM {filename}"
                bus.publish(job_id, {"status": f"Création modèle '{model_name}' à partir du blob uploadé..."})
                print(f"DEBUG: Création avec files parameter: {files} et Modelfile: {modelfile_content}")
            except Exception:
                pass

            try:
                for evt in oc.create_stream(model_name, modelfile=modelfile_content, files=files):
                    st = evt.get("status")
                    if st:
                        print(f"DEBUG: create_stream event: {st}")
                        try:
                            bus.publish(job_id, {"status": st})
                        except Exception:
                            pass
                created = True
            except httpx.HTTPStatusError as e:
                status_code = getattr(e.response, "status_code", None)
                body = ""
                try:
                    body = e.response.text
                except Exception:
                    body = str(e)
                last_error = f"HTTP {status_code}: {body}"
                print(f"DEBUG: create_stream HTTP error: {last_error}")
                print(f"DEBUG: Response body: {body}")
                print(f"DEBUG: Used files parameter: {files}")
            except Exception as e:
                last_error = str(e)
                print(f"DEBUG: create_stream exception: {e}")

            if not created:
                try:
                    msg = f"Impossible de créer le modèle"
                    if last_error:
                        msg += f": {last_error}"
                    bus.publish(job_id, {"error": msg})
                except Exception:
                    pass
            else:
                # Succès: publier le message de finalisation
                try:
                    bus.publish(job_id, {"done": True, "status": f"Modèle '{model_name}' créé avec succès"})
                except Exception:
                    pass

        except Exception as e:
            print(f"DEBUG: Exception in download process: {e}")
            try:
                error_msg = {"error": str(e)}
                print(f"DEBUG: Publishing error message: {error_msg}")
                bus.publish(job_id, error_msg)
                print(f"DEBUG: Error message published successfully")
            except Exception as e2:
                print(f"DEBUG: Exception publishing error: {e2}")
                pass  # Ignore Redis errors
