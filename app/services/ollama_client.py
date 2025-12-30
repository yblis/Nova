from __future__ import annotations

import httpx
from typing import Any, Dict, Iterable, Optional


class BlobUploadedWithoutPath(Exception):
    """
    Exception levée quand l'upload d'un blob réussit (HTTP 200/201) 
    mais qu'Ollama ne retourne pas le chemin du blob.
    """
    def __init__(self, message: str, digest: str, status_code: int):
        super().__init__(message)
        self.digest = digest
        self.status_code = status_code


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        connect_timeout: float = 10.0,
        read_timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # httpx requires either a default timeout or all four values
        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout,
        )

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def _post(self, path: str, json: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        with self._client() as c:
            r = c.post(url, json=json)
            r.raise_for_status()
            return r.json()

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        with self._client() as c:
            r = c.get(url)
            r.raise_for_status()
            return r.json()

    def _delete(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        import json as json_module
        with self._client() as c:
            # Use request() method since delete() doesn't support json body directly
            r = c.request("DELETE", url, content=json_module.dumps(json) if json else None, 
                         headers={"Content-Type": "application/json"} if json else None)
            r.raise_for_status()
            return r.json() if r.content else {}

    # API wrappers

    def tags(self) -> Dict[str, Any]:
        return self._get("/api/tags")

    def show(self, name: str) -> Dict[str, Any]:
        try:
            return self._post("/api/show", {"name": name})
        except httpx.HTTPStatusError as e:
            # If model not found and no tag provided, try with default tag provided by Ollama
            if e.response.status_code == 404 and ":" not in name:
                try:
                    return self._post("/api/show", {"name": f"{name}:latest"})
                except Exception:
                    # If this also fails, raise the original error
                    pass
            raise

    def pull_stream(self, name: str) -> Iterable[Dict[str, Any]]:
        url = f"{self.base_url}/api/pull"
        with httpx.Client(timeout=self.timeout) as c:
            with c.stream("POST", url, json={"name": name}, headers={"Accept": "application/json"}) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        yield httpx.Response(200, content=line).json()
                    except Exception:
                        # Ignore malformed lines
                        continue

    def delete(self, name: str) -> bool:
        self._delete("/api/delete", json={"name": name})
        return True

    def copy(self, source: str, dest: str) -> bool:
        self._post("/api/copy", {"source": source, "destination": dest})
        return True

    def ps(self) -> Dict[str, Any]:
        return self._get("/api/ps")

    def generate(self, prompt: str, keep_alive: int = 0, stream: bool = False, model: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"prompt": prompt, "keep_alive": keep_alive, "stream": stream}
        if model:
            payload["model"] = model
        return self._post("/api/generate", payload)


    def generate_stream(self, prompt: str, model: str, context: list = []) -> Iterable[Dict[str, Any]]:
        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "context": context, "stream": True}
        with httpx.Client(timeout=self.timeout) as c:
            with c.stream("POST", url, json=payload) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line: continue
                    try:
                        yield httpx.Response(200, content=line).json()
                    except: continue

    def chat_stream(self, messages: list, model: str, images: list = None, options: dict = None) -> Iterable[Dict[str, Any]]:
        """
        Stream chat response from Ollama.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            images: Optional list of base64-encoded images (for vision models)
            options: Optional dict of model parameters (temperature, num_ctx, top_p, top_k, etc.)
        """
        url = f"{self.base_url}/api/chat"
        
        # If images provided, attach to the last user message
        if images and messages:
            # Find the last user message and add images to it
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i]["images"] = images
                    break
        
        payload = {"model": model, "messages": messages, "stream": True}
        
        # Add options if provided
        if options:
            payload["options"] = options
        
        with httpx.Client(timeout=self.timeout) as c:
            with c.stream("POST", url, json=payload) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line: continue
                    try:
                        yield httpx.Response(200, content=line).json()
                    except: continue

    def chat(self, messages: list, model: str, images: list = None, options: dict = None, stream: bool = False) -> Dict[str, Any]:
        """
        Non-streaming chat request to Ollama.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            images: Optional list of base64-encoded images (for vision models)
            options: Optional dict of model parameters
            stream: Must be False for this method (ignored, always non-streaming)
        
        Returns:
            Dict with the complete response including 'message' key
        """
        url = f"{self.base_url}/api/chat"
        
        # If images provided, attach to the last user message
        if images and messages:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i]["images"] = images
                    break
        
        payload = {"model": model, "messages": messages, "stream": False}
        
        if options:
            payload["options"] = options
        
        with self._client() as c:
            r = c.post(url, json=payload)
            r.raise_for_status()
            return r.json()


    # ---- New methods for remote model creation ----

    def create_stream(self, name: str, modelfile: str | None = None, files: Dict[str, str] | None = None) -> Iterable[Dict[str, Any]]:
        """
        Stream creation of a model from a Modelfile or from uploaded blobs.

        Usage example with Modelfile:
        for evt in client.create_stream("my-model", modelfile="FROM /path/to/blob\n"):
            print(evt)

        Usage example with uploaded blobs:
        for evt in client.create_stream("my-model", files={"model.gguf": "sha256:abc123..."}):
            print(evt)
        """
        url = f"{self.base_url}/api/create"
        payload: Dict[str, Any] = {"name": name}

        if modelfile:
            payload["modelfile"] = modelfile
        if files:
            payload["files"] = files

        with httpx.Client(timeout=self.timeout) as c:
            with c.stream("POST", url, json=payload, headers={"Accept": "application/json"}) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        yield httpx.Response(200, content=line).json()
                    except Exception:
                        # Ignore malformed lines
                        continue

    def create_model(
        self,
        name: str,
        from_model: str,
        system: str | None = None,
        template: str | None = None,
        parameters: Dict[str, Any] | None = None,
        stream: bool = True
    ) -> Iterable[Dict[str, Any]]:
        """
        Create a custom model based on an existing model with modified parameters.
        
        This uses the Ollama /api/create endpoint with the new API format.
        
        Args:
            name: Name for the new custom model
            from_model: Source model to base the new model on
            system: Optional system prompt for the model
            template: Optional prompt template
            parameters: Optional dict of model parameters (temperature, num_ctx, top_p, etc.)
            stream: Whether to stream the response (default True)
            
        Returns:
            Iterable of status dicts showing creation progress
        """
        # Reverting to component fields as 'modelfile' string approach failed on this server
        url = f"{self.base_url}/api/create"
        payload: Dict[str, Any] = {
            "model": name,
            "from": from_model,
            "stream": stream
        }
        
        if system:
            payload["system"] = system
        if template:
            payload["template"] = template
        if parameters:
            payload["parameters"] = parameters
            
        print(f"[DEBUG] Creating model with payload: {payload}")
        
        with httpx.Client(timeout=self.timeout) as c:
            with c.stream("POST", url, json=payload, headers={"Accept": "application/json"}) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = httpx.Response(200, content=line).json()
                        if "error" in data:
                            print(f"[DEBUG] Ollama creation error: {data['error']}")
                        yield data
                    except Exception as e:
                        print(f"[ERROR] Failed to parse line: {line} - {e}")
                        # Ignore malformed lines
                        continue

    def head_blob_exists(self, digest: str) -> bool:
        """
        Check if a blob exists on the server by digest, e.g. 'sha256:...'
        Returns True if the server responds 200 OK, False otherwise.
        """
        url = f"{self.base_url}/api/blobs/{digest}"
        with self._client() as c:
            r = c.head(url)
            return r.status_code == 200

    def get_blob_info(self, digest: str) -> Dict[str, Any]:
        """
        Get information about a blob from the server.
        Returns a dict with blob metadata if available.
        """
        url = f"{self.base_url}/api/blobs/{digest}"
        with self._client() as c:
            r = c.get(url)
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    return {"status": "exists", "text": r.text}
            else:
                return {"status": "not_found", "status_code": r.status_code}

    def list_blobs(self) -> Dict[str, Any]:
        """
        Try to list all blobs from the server.
        This is not a standard Ollama API endpoint but some installations might support it.
        """
        url = f"{self.base_url}/api/blobs"
        with self._client() as c:
            try:
                r = c.get(url)
                if r.status_code == 200:
                    return r.json()
                else:
                    return {"error": f"HTTP {r.status_code}", "supported": False}
            except Exception as e:
                return {"error": str(e), "supported": False}

    def create_blob(self, digest: str, file_path: str, progress_callback=None) -> str:
        """
        Create a blob from a local file on the server, returns server file path.
        Uses streaming upload to handle large files efficiently with progress tracking.

        Notes:
        - 'digest' must include the 'sha256:' prefix.
        - Returns the server path indicated by the response (header or body). Raises on missing path.
        - progress_callback: Optional callback function(bytes_uploaded, total_bytes) for progress tracking
        """
        import os
        import requests

        url = f"{self.base_url}/api/blobs/{digest}"
        file_size = os.path.getsize(file_path)

        print(f"DEBUG: Starting blob upload. File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")

        # Use requests library for better streaming support with progress tracking
        class ProgressFileWrapper:
            def __init__(self, file_path, callback=None):
                self.file = open(file_path, 'rb')
                self.file_size = os.path.getsize(file_path)
                self.bytes_read = 0
                self.callback = callback
                self.last_log_mb = 0

            def read(self, size=-1):
                chunk = self.file.read(size)
                if chunk:
                    self.bytes_read += len(chunk)

                    # Log every 50 MB
                    current_mb = self.bytes_read / (1024 * 1024)
                    if current_mb - self.last_log_mb >= 50:
                        print(f"DEBUG: Upload progress: {current_mb:.2f} MB / {self.file_size / 1024 / 1024:.2f} MB ({self.bytes_read * 100 / self.file_size:.1f}%)")
                        self.last_log_mb = current_mb

                    # Call progress callback
                    if self.callback:
                        try:
                            self.callback(self.bytes_read, self.file_size)
                        except Exception:
                            pass

                return chunk

            def __len__(self):
                return self.file_size

            def close(self):
                self.file.close()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        print(f"DEBUG: Starting POST request to {url}")

        # Use requests with streaming upload
        with ProgressFileWrapper(file_path, progress_callback) as file_wrapper:
            r = requests.post(
                url,
                data=file_wrapper,
                headers={'Content-Length': str(file_size)},
                timeout=(self.timeout.connect, 3600)  # connect timeout, read timeout
            )

        print(f"DEBUG: Upload completed. Status: {r.status_code}, Total uploaded: {file_wrapper.bytes_read / 1024 / 1024:.2f} MB")

        # Accept 200/201; include error body for diagnostics otherwise
        if r.status_code not in (200, 201):
            # Use requests.HTTPError instead of httpx.HTTPStatusError
            error = requests.HTTPError(f"Blob create failed {r.status_code}: {r.text}")
            error.response = r
            raise error
        # Prefer path from headers if present
        path = r.headers.get("Location") or r.headers.get("X-Ollama-Path")
        if path:
            return str(path)
        # Try to parse JSON body with 'path' or similar
        try:
            data = r.json()
            if isinstance(data, dict):
                p = data.get("path") or data.get("blob_path")
                if p:
                    return str(p)
        except Exception:
            pass
        # Fallback to raw text if provided
        t = (r.text or "").strip()
        if t and not t.startswith('<!') and not t.startswith('{'):  # Éviter HTML et JSON vides
            return t

        # Si on arrive ici, l'upload semble avoir réussi (HTTP 200/201) mais sans chemin retourné.
        # Certaines versions d'Ollama ou configurations peuvent ne pas retourner le chemin.
        # Dans ce cas, on va lever une exception spéciale qui indique le succès de l'upload
        # mais l'absence de chemin, permettant au code appelant de gérer ce cas.

        # Collect a small subset of response headers for visibility
        interesting_headers = {}
        for k in ("Location", "X-Ollama-Path", "Content-Type", "Server", "Date"):
            if k in r.headers:
                interesting_headers[k] = r.headers.get(k)
        body_snippet = ((r.text or "").strip()[:512]) if r.text is not None else ""

        error_msg = (
            "Ollama /api/blobs did not return a path. "
            f"BaseURL={self.base_url}, HTTP={r.status_code}, digest={digest}. "
            f"Headers={interesting_headers}. Body[0..512]={body_snippet}"
        )
        raise BlobUploadedWithoutPath(error_msg, digest, r.status_code)
