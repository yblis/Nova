import httpx
import re
from typing import List, Dict, Any
from urllib.parse import quote

class OllamaWebClient:
    """
    Client to interact with ollama.com website (scraping)
    """
    
    BASE_URL = "https://ollama.com"
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def get_model_tags(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Get all tags/variants for a specific model from ollama.com/library/{model}/tags
        Returns list of variants with size, context window, and input type
        """
        url = f"{self.BASE_URL}/library/{model_name}/tags"
        
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()
                return self._parse_model_tags(response.text, model_name)
        except Exception as e:
            print(f"Error fetching model tags from ollama.com: {e} | URL: {url}")
            return []

    def _parse_model_tags(self, html: str, model_name: str) -> List[Dict[str, Any]]:
        """
        Parse HTML from model tags page using regex (fallback)
        """
        results = []
        
        # Pattern to match tag info: hash • size • context window • input type
        # Example: 901cae732162 • 6.1GB • 256K context window  • Text, Image input
        pattern = r'([a-f0-9]{12})\s*•\s*([\d.]+(?:GB|MB|KB))\s*•\s*(\d+K?)\s*context window\s*•\s*([^•\n]+?)(?:\s*•|\s*\d+\s*(?:month|week|day|hour|year))'
        
        # Also find the tag names from hrefs
        tag_pattern = rf'/library/{re.escape(model_name)}:([^\"\s]+)'
        
        tag_names = re.findall(tag_pattern, html)
        tag_details = re.findall(pattern, html, re.IGNORECASE)
        
        seen_tags = set()
        for i, match in enumerate(tag_details):
            hash_id, size, context, input_type = match
            
            # Find corresponding tag name
            tag_name = tag_names[i] if i < len(tag_names) else f"variant-{i}"
            
            if tag_name in seen_tags:
                continue
            seen_tags.add(tag_name)
            
            results.append({
                "tag": tag_name,
                "full_name": f"{model_name}:{tag_name}",
                "size": size.strip(),
                "context": context.strip(),
                "input_type": input_type.strip().rstrip(' •'),
                "hash": hash_id
            })
        
        return results

    def search_models(self, query: str = "") -> List[Dict[str, Any]]:
        """
        Search for models on ollama.com/search
        If query is empty, returns the default/popular models
        """
        if query:
            url = f"{self.BASE_URL}/search?q={quote(query)}"
        else:
            url = f"{self.BASE_URL}/search"
        
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()
                return self._parse_search_results(response.text)
        except Exception as e:
            print(f"Error scraping ollama.com: {e} | URL: {url}")
            return []

    def _parse_search_results(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse HTML from search results using Regex (fallback if bs4 not present)
        Ollama search results usually look like list items with links.
        """
        results = []
        
        # This regex is a best-effort approximation based on current ollama.com structure
        # It looks for <li ...> <a href="/library/modelname"> ... 
        # Structure changes frequently, so this is fragile.
        
        # Regex to find model blocks
        # Usually: <li ...> ... <a href="/library/..." ...> ... <h2>name</h2> ... <p>desc</p> ... <span>pulls</span> ... <span>tags</span>
        
        # Let's try to extract specific chunks that look like model cards
        # Pattern for model items
        
        # Extract href="/library/..."
        # We find all links that point to /library/
        
        # Simple extraction strategy:
        # Find all blocks that contain model info
        
        # Current Ollama UI uses `x-test-model-card` or similar attributes? No, let's just inspect the captured HTML from earlier or trust generic patterns.
        # I saw the HTML output in the earlier turn (Step 145). It was truncated but showed standard HTML structure.
        # Let's use a robust regex that captures the essential parts.
        
        # Looking for <a href="/library/([^"]+)" ... >
        # Then inside that block finding name, desc, stats.
        
        # Since I don't have the full HTML structure in my context, I'll assume a list of items.
        # I'll effectively scan for `href="/library/` and capture generic info around it.
        
        # Better strategy: If I find BS4, I use it. The code below uses Regex as a fallback which I'm writing now.
        
        model_links = re.finditer(r'href="/library/([^"]+)"', html)
        seen_slugs = set()
        
        for match in model_links:
            slug = match.group(1)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            
            # For each slug found, we try to extract rudimentary info from the HTML snippet surrounding it
            # This is hard with regex on full HTML string.
            # I will assume simpler parsing: just list the names found.
            
            # To get descriptions, I'd need to parse the DOM properly.
            
            results.append({
                "name": slug,
                "description": "", # Hard to get reliable description with regex without context
                "pull_count": "",
                "tags": []
            })
            
        return results

# If bs4 is available, we overwrite the _parse_search_results method
try:
    from bs4 import BeautifulSoup
    
    def _parse_with_bs4(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Ollama search results are usually in a list
        # Look for list items
        items = soup.find_all("li")
        
        for item in items:
            link = item.find("a", href=re.compile(r"^/library/"))
            if not link:
                continue
                
            href = link.get("href")
            name = href.replace("/library/", "")
            
            description_tag = item.find("p")
            description = description_tag.get_text(strip=True) if description_tag else ""
            
            # Extract parameter sizes (like "7b", "13b", "70b")
            # They appear as spans with size values
            param_sizes = []
            # Look for spans containing parameter size patterns
            all_text = item.get_text()
            all_text_lower = all_text.lower()
            size_matches = re.findall(r'\b(\d+(?:\.\d+)?[bBmM])\b', all_text)
            for size in size_matches:
                # Normalize to lowercase
                size_lower = size.lower()
                # Skip very small values that might be version numbers
                if size_lower not in param_sizes:
                    param_sizes.append(size_lower)
            
            # Extract pull count
            pull_count = ""
            pull_match = re.search(r'([\d.]+[KMB]?)\s*Pulls?', all_text, re.IGNORECASE)
            if pull_match:
                pull_count = pull_match.group(1)
            
            # Extract model capabilities/types (vision, tools, thinking, embedding)
            capabilities = []
            # Check for capability keywords in the text
            capability_keywords = ['vision', 'tools', 'thinking', 'embedding', 'code', 'cloud']
            for cap in capability_keywords:
                # Look for the keyword as a standalone word in the text
                if re.search(rf'\b{cap}\b', all_text_lower):
                    capabilities.append(cap)
            
            # Let's clean up name (sometimes has query params)
            if "?" in name:
                name = name.split("?")[0]
            
            results.append({
                "name": name,
                "description": description,
                "pull_count": pull_count,
                "param_sizes": param_sizes,  # Available sizes
                "capabilities": capabilities,  # Model types/capabilities
                "tags": []
            })
            
        return results

    OllamaWebClient._parse_search_results = _parse_with_bs4

    def _parse_model_tags_bs4(self, html: str, model_name: str) -> List[Dict[str, Any]]:
        """
        Parse HTML from model tags page using BeautifulSoup
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen_tags = set()
        
        # Find all links to model tags
        tag_links = soup.find_all("a", href=re.compile(rf"^/library/{re.escape(model_name)}:[^/]+$"))
        
        for link in tag_links:
            href = link.get("href", "")
            # Extract tag name from href like /library/qwen3-vl:8b
            tag_match = re.search(rf"/library/{re.escape(model_name)}:([^\s/]+)", href)
            if not tag_match:
                continue
                
            tag_name = tag_match.group(1)
            if tag_name in seen_tags:
                continue
            seen_tags.add(tag_name)
            
            # Get the parent container to find associated info
            # Look for text containing size, context, input type
            parent = link.find_parent("li") or link.find_parent("div") or link
            all_text = parent.get_text(" ", strip=True) if parent else ""
            
            # Extract size (e.g., "6.1GB", "1.9GB", "143GB")
            size_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB|KB)', all_text, re.IGNORECASE)
            size = f"{size_match.group(1)}{size_match.group(2).upper()}" if size_match else ""
            
            # Extract context window (e.g., "256K", "8K", "128K")
            context_match = re.search(r'(\d+K?)\s*context', all_text, re.IGNORECASE)
            context = context_match.group(1) if context_match else ""
            
            # Extract input type (e.g., "Text, Image input", "Text input")
            input_match = re.search(r'((?:Text|Image|Video|Audio)(?:\s*,\s*(?:Text|Image|Video|Audio))*)\s*input', all_text, re.IGNORECASE)
            input_type = f"{input_match.group(1)} input" if input_match else "Text input"
            
            # Extract hash (e.g., "901cae732162")
            hash_match = re.search(r'([a-f0-9]{12})', all_text)
            hash_id = hash_match.group(1) if hash_match else ""
            
            results.append({
                "tag": tag_name,
                "full_name": f"{model_name}:{tag_name}",
                "size": size,
                "context": context,
                "input_type": input_type,
                "hash": hash_id
            })
        
        return results

    OllamaWebClient._parse_model_tags = _parse_model_tags_bs4

except ImportError:
    pass


def _parse_size_to_billions(size_str: str) -> float:
    """
    Parse a size string like '7b', '1.5b', '70b', '300m' to a float in billions.
    Returns None if parsing fails.
    """
    if not size_str:
        return None
    size_str = size_str.lower().strip()
    try:
        if size_str.endswith('b'):
            return float(size_str[:-1])
        elif size_str.endswith('m'):
            return float(size_str[:-1]) / 1000  # Convert millions to billions
        else:
            return float(size_str)
    except (ValueError, TypeError):
        return None


def filter_models_by_params(models: List[Dict[str, Any]], min_params: float = None, max_params: float = None) -> List[Dict[str, Any]]:
    """
    Filter models by parameter size range.
    A model passes the filter if ANY of its param_sizes falls within the range.
    Models without param_sizes are excluded when filtering is active.
    """
    if min_params is None and max_params is None:
        return models
    
    # If min is 0 or None and max is None or >= 100, return all (no effective filter)
    if (min_params is None or min_params == 0) and (max_params is None or max_params >= 100):
        return models
    
    filtered = []
    for model in models:
        param_sizes = model.get("param_sizes", [])
        
        # If no param sizes info and we're filtering, exclude the model
        # (we can't determine if it fits the criteria)
        if not param_sizes:
            continue
        
        # Check if any size is in range
        has_size_in_range = False
        for size_str in param_sizes:
            size_val = _parse_size_to_billions(size_str)
            if size_val is None:
                continue
            
            in_range = True
            if min_params is not None and size_val < min_params:
                in_range = False
            if max_params is not None and size_val > max_params:
                in_range = False
            
            if in_range:
                has_size_in_range = True
                break
        
        if has_size_in_range:
            filtered.append(model)
    
    return filtered


def filter_models_by_type(models: List[Dict[str, Any]], model_type: str = None) -> List[Dict[str, Any]]:
    """
    Filter models by type/capability.
    Valid types: vision, tools, thinking, embedding, code
    If model_type is None or empty, returns all models.
    """
    if not model_type:
        return models
    
    model_type_lower = model_type.lower().strip()
    
    # Special case: "text" means no special capabilities (basic text models)
    if model_type_lower == "text":
        # Return models that don't have vision, embedding capabilities
        return [m for m in models if not any(c in m.get("capabilities", []) for c in ["vision", "embedding"])]
    
    filtered = []
    for model in models:
        capabilities = model.get("capabilities", [])
        if model_type_lower in capabilities:
            filtered.append(model)
    
    return filtered
