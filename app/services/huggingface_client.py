"""
Service client for HuggingFace Hub API
Handles searching and downloading GGUF models from HuggingFace
"""
from __future__ import annotations

import re
from typing import Dict, List, Any, Optional, Iterable
import httpx
from pathlib import Path


class HuggingFaceClient:
    """Client for interacting with HuggingFace Hub API"""

    def __init__(
        self,
        hf_token: Optional[str] = None,
        connect_timeout: int = 10,
        read_timeout: int = 600
    ):
        """
        Initialize HuggingFace client

        Args:
            hf_token: Optional HuggingFace API token for private models
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
        """
        self.base_url = "https://huggingface.co"
        self.api_url = "https://huggingface.co/api"
        self.hf_token = hf_token
        # httpx.Timeout requires all 4 parameters: connect, read, write, pool
        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=connect_timeout,
            pool=connect_timeout
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with optional authentication"""
        headers = {
            "User-Agent": "Ollamanager-Flask/1.0"
        }
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        return headers

    def search_gguf_models(
        self,
        query: str = "",
        limit: int = 50,
        sort: str = "downloads",
        filter_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for GGUF models on HuggingFace Hub

        Args:
            query: Search query string
            limit: Maximum number of results
            sort: Sort by ('downloads', 'likes', 'updated', 'created')
            filter_params: Additional filters (parameter_size, quantization, etc.)

        Returns:
            List of model information dictionaries
        """
        # Map user-friendly sort names to HuggingFace API names
        sort_mapping = {
            "downloads": "downloads",
            "likes": "likes",
            "updated": "lastModified",
            "created": "createdAt"
        }

        # Use mapped sort value or default to downloads
        api_sort = sort_mapping.get(sort, sort)

        # Build search URL with filters
        params = {
            "search": query,
            "filter": "gguf",  # Filter for GGUF models
            "sort": api_sort,
            "limit": limit,
            "full": "true"
        }

        # Apply additional filters if provided
        if filter_params:
            # For parameter size filters, we'll do client-side filtering only
            # since HuggingFace API doesn't reliably support range filters on parameter_size
            if filter_params.get("parameter_size"):
                # Only apply exact parameter_size filter to API
                params["filter"] = f"{params['filter']},parameter_size:{filter_params['parameter_size']}"
                print(f"DEBUG: Applied exact filter: {params['filter']}")
            # Note: min_params and max_params will be handled client-side only

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.api_url}/models",
                    params=params,
                    headers=self._get_headers(),
                    follow_redirects=True
                )
                response.raise_for_status()
                models = response.json()
                print(f"DEBUG: API returned {len(models)} models for query: {query}, filter: {params.get('filter', 'none')}")

                # Process and enrich model data
                results = []
                for model in models:
                    model_id = model.get("id", "")
                    
                    # Get accurate file info for this model if possible
                    file_info_map = {}
                    # Only fetch file info for top models to avoid too many API calls
                    if isinstance(results, list) and len(results) < 10:  # Limit to avoid excessive API calls
                        try:
                            file_info_map = self._get_file_info_from_tree(model_id)
                        except Exception as e:
                            print(f"WARNING: Could not get file info for {model_id}: {e}")
                    
                    processed = self._process_model_info(model, file_info_map)

                    # Apply client-side filters for more specific criteria
                    if filter_params:
                        if not self._matches_filters(processed, filter_params):
                            continue

                    results.append(processed)

                print(f"DEBUG: After filtering, returning {len(results)} models")
                return results[:limit]
        except Exception as e:
            raise Exception(f"Failed to search HuggingFace models: {str(e)}")

    def _process_model_info(self, model: Dict[str, Any], file_info_map: Dict[str, Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process and enrich model information

        Args:
            model: Raw model data from API
            file_info_map: Optional mapping of filename to file info with sizes

        Returns:
            Processed model information
        """
        model_id = model.get("id", "")
        author, name = model_id.split("/", 1) if "/" in model_id else ("", model_id)

        # Extract GGUF files information
        siblings = model.get("siblings", [])
        gguf_files = [
            f for f in siblings
            if f.get("rfilename", "").lower().endswith(".gguf")
        ]

        return {
            "id": model_id,
            "author": author,
            "name": name,
            "downloads": model.get("downloads", 0),
            "likes": model.get("likes", 0),
            "tags": model.get("tags", []),
            "created_at": model.get("createdAt"),
            "updated_at": model.get("lastModified"),
            "gguf_files": self._parse_gguf_files(gguf_files, file_info_map),
            "description": model.get("description", ""),
            "model_card": model.get("cardData", {}),
        }

    def _parse_gguf_files(self, gguf_files: List[Dict[str, Any]], file_info_map: Dict[str, Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Parse GGUF files and extract metadata from filenames

        Args:
            gguf_files: List of GGUF file information
            file_info_map: Optional mapping of filename to file info with accurate sizes

        Returns:
            List of parsed GGUF file information with metadata
        """
        parsed_files = []

        for file in gguf_files:
            filename = file.get("rfilename", "")

            # Extract quantization level from filename (e.g., Q4_K_M, Q5_0, etc.)
            quant_match = re.search(r'[._-](Q\d+_[KF]_[MSL]|Q\d+_\d+)[._-]', filename, re.IGNORECASE)
            quantization = quant_match.group(1).upper() if quant_match else None

            # Extract parameter size if present (e.g., 7B, 13B, 70B, 1.7B, 0.5B)
            # Try with decimal first (e.g., 1.7B, 0.5B)
            param_match = re.search(r'[._-](\d+\.?\d*)B[._-]', filename, re.IGNORECASE)
            if param_match:
                param_size = f"{param_match.group(1)}B"
            else:
                # Try without delimiters (e.g., "qwen1.5b", "phi2.7b")
                param_match_name = re.search(r'(\d+\.?\d*)b', filename, re.IGNORECASE)
                param_size = f"{param_match_name.group(1)}B" if param_match_name else None

            # Get accurate file size if file_info_map is available
            file_size = 0
            if file_info_map and filename in file_info_map:
                file_size = file_info_map[filename].get("size", 0)
                if file_size > 0:
                    print(f"DEBUG: Using accurate size for {filename}: {file_size} bytes")
            else:
                # Fallback to unreliable size from API (usually 0)
                file_size = file.get("size", 0)

            parsed_files.append({
                "filename": filename,
                "size": file_size,
                "quantization": quantization,
                "parameter_size": param_size,
                "download_url": f"{self.base_url}/{file.get('rfilename')}" if file.get('rfilename') else None,
            })

        # Sort by size (largest first) to show full model first
        parsed_files.sort(key=lambda x: x.get("size", 0), reverse=True)

        return parsed_files

    def _matches_filters(self, model: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Check if model matches the given filters

        Args:
            model: Processed model information
            filters: Filter criteria

        Returns:
            True if model matches all filters
        """
        # Filter by quantization
        if filters.get("quantization"):
            has_quant = any(
                f.get("quantization") == filters["quantization"]
                for f in model.get("gguf_files", [])
            )
            if not has_quant:
                return False

        # Filter by parameter size range (min_params / max_params) - priority over exact
        min_params = filters.get("min_params")
        max_params = filters.get("max_params")
        
        if min_params or max_params:
            def _to_float_b(s: Optional[str]) -> Optional[float]:
                if not s:
                    return None
                try:
                    su = s.upper()
                    if su.endswith("B"):
                        return float(su[:-1])
                    return float(su)
                except Exception:
                    return None

            min_v = _to_float_b(min_params) if min_params else None
            max_v = _to_float_b(max_params) if max_params else None

            def within_range(f: Dict[str, Any]) -> bool:
                v = _to_float_b(f.get("parameter_size"))
                if v is None:
                    return False
                if min_v is not None and v < min_v:
                    return False
                if max_v is not None and v > max_v:
                    return False
                return True

            gguf_files = model.get("gguf_files", [])
            file_params = [f.get("parameter_size") for f in gguf_files]
            has_in_range = any(within_range(f) for f in gguf_files)
            
            print(f"DEBUG: Model {model.get('id')}")
            print(f"  - Range filter: {min_params} to {max_params}")
            print(f"  - File parameter sizes: {file_params}")
            print(f"  - Has in range: {has_in_range}")
            
            if not has_in_range:
                return False
        # Only apply exact parameter_size if range is not specified
        elif filters.get("parameter_size"):
            gguf_files = model.get("gguf_files", [])
            has_param = any(
                f.get("parameter_size") == filters["parameter_size"]
                for f in gguf_files
            )
            print(f"DEBUG: Model {model.get('id')} - Exact filter: {filters['parameter_size']}, Files: {[f.get('parameter_size') for f in gguf_files]}, Has match: {has_param}")
            if not has_param:
                return False

        # Filter by minimum downloads
        if filters.get("min_downloads"):
            if model.get("downloads", 0) < filters["min_downloads"]:
                return False

        # Filter by tags
        if filters.get("tags"):
            model_tags = set(model.get("tags", []))
            required_tags = set(filters["tags"]) if isinstance(filters["tags"], list) else {filters["tags"]}
            if not required_tags.issubset(model_tags):
                return False

        return True

    def _get_file_info_from_tree(self, model_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed file information including sizes from the /tree/main endpoint
        
        Args:
            model_id: HuggingFace model ID
            
        Returns:
            Dictionary mapping filenames to file information including size
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.api_url}/models/{model_id}/tree/main",
                    headers=self._get_headers(),
                    follow_redirects=True
                )
                response.raise_for_status()
                tree_data = response.json()
                
                # Create a mapping of filename to file info
                file_info_map = {}
                for file_item in tree_data:
                    if file_item.get("type") == "file":
                        filename = file_item.get("path", "")
                        if filename:
                            file_info_map[filename] = {
                                "size": file_item.get("size", 0),
                                "oid": file_item.get("oid", ""),
                                "lfs": file_item.get("lfs"),
                                "type": file_item.get("type", "")
                            }
                return file_info_map
        except Exception as e:
            print(f"WARNING: Failed to get file tree for {model_id}: {e}")
            return {}

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific model

        Args:
            model_id: HuggingFace model ID (e.g., "TheBloke/Llama-2-7B-GGUF")

        Returns:
            Detailed model information
        """
        try:
            # Get file information from tree endpoint first for accurate sizes
            file_info_map = self._get_file_info_from_tree(model_id)
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.api_url}/models/{model_id}",
                    headers=self._get_headers(),
                    follow_redirects=True
                )
                response.raise_for_status()
                model = response.json()
                
                # Process model info and enrich with accurate file sizes
                processed_model = self._process_model_info(model, file_info_map)
                return processed_model
                
        except Exception as e:
            raise Exception(f"Failed to get model info: {str(e)}")

    def download_gguf_stream(
        self,
        model_id: str,
        filename: str,
        output_path: Path
    ) -> Iterable[Dict[str, Any]]:
        """
        Download a GGUF file with progress tracking

        Args:
            model_id: HuggingFace model ID
            filename: GGUF filename to download
            output_path: Local path to save the file

        Yields:
            Progress information dictionaries with 'status', 'total', 'completed'
        """
        download_url = f"{self.base_url}/{model_id}/resolve/main/{filename}"
        
        print(f"DEBUG: Starting download - URL: {download_url}")
        print(f"DEBUG: Output path: {output_path}")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                print(f"DEBUG: Making request to {download_url}")
                
                # Create output directory if it doesn't exist
                output_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"DEBUG: Created output directory: {output_path.parent}")

                with client.stream(
                    "GET",
                    download_url,
                    headers=self._get_headers(),
                    follow_redirects=True
                ) as response:
                    print(f"DEBUG: Response status: {response.status_code}")
                    response.raise_for_status()

                    total = int(response.headers.get("Content-Length", 0))
                    completed = 0

                    print(f"DEBUG: Total file size: {total} bytes")

                    yield {
                        "status": f"Démarrage téléchargement {filename}",
                        "total": total,
                        "completed": completed,
                    }

                    with open(output_path, "wb") as f:
                        chunk_count = 0
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                completed += len(chunk)
                                chunk_count += 1

                                if chunk_count % 100 == 0:  # Yield progress every 100 chunks
                                    yield {
                                        "status": f"Téléchargement {filename}",
                                        "total": total,
                                        "completed": completed,
                                    }

                    # Final yield for completion
                    yield {
                        "status": f"Téléchargement terminé: {filename}",
                        "total": total,
                        "completed": completed,
                        "done": True,
                    }
                    
                    print(f"DEBUG: Download completed successfully. File saved to: {output_path}")

        except httpx.ConnectError as e:
            error_msg = f"Erreur de connexion: Impossible de se connecter à HuggingFace. Vérifiez votre connexion internet. Détail: {str(e)}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            error_msg = f"Timeout: La connexion a expiré. Détail: {str(e)}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Erreur lors du téléchargement: {str(e)}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)

    def get_available_quantizations(self) -> List[str]:
        """
        Get list of common GGUF quantization levels

        Returns:
            List of quantization level strings
        """
        return [
            "Q2_K",
            "Q3_K_S",
            "Q3_K_M",
            "Q3_K_L",
            "Q4_0",
            "Q4_K_S",
            "Q4_K_M",
            "Q5_0",
            "Q5_K_S",
            "Q5_K_M",
            "Q6_K",
            "Q8_0",
            "F16",
            "F32",
        ]

    def get_available_parameter_sizes(self) -> List[str]:
        """
        Get list of common model parameter sizes

        Returns:
            List of parameter size strings (sorted)
        """
        return [
            "0.5B",
            "0.6B",
            "1B",
            "1.5B",
            "1.7B",
            "1.8B",
            "2B",
            "2.7B",
            "3B",
            "4B",
            "7B",
            "8B",
            "9B",
            "13B",
            "14B",
            "27B",
            "30B",
            "32B",
            "33B",
            "34B",
            "40B",
            "65B",
            "70B",
            "72B",
            "110B",
            "180B",
            "235B",
            "314B",
            "405B",
        ]
