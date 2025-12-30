from __future__ import annotations

import re
from typing import List, Dict, Optional

import httpx


BASE = "https://ollama.com"


def _get(path: str, params: dict | None = None, timeout: float = 10.0) -> str:
    url = f"{BASE}{path}"
    headers = {"User-Agent": "OllamaMgr/1.0 (+https://example.local)"}
    with httpx.Client(timeout=timeout, headers=headers) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.text


def search_models(q: str) -> List[Dict[str, str]]:
    if not q:
        return []
    try:
        html = _get("/search", params={"q": q})
    except Exception:
        return []
    # Extract unique model names from links like /library/name or /library/name:tag
    names = set()
    for m in re.finditer(r"/library/([a-zA-Z0-9_.-]+)(?::[a-zA-Z0-9_.-]+)?\b", html):
        names.add(m.group(1))
    results = sorted(names)
    return [{"name": n} for n in results]


def model_variants(model: str) -> List[str]:
    try:
        html = _get(f"/library/{model}")
    except Exception:
        return []
    # Find tags like /library/model:tag
    tags = set()
    pattern = re.compile(rf"/library/{re.escape(model)}:([a-zA-Z0-9_.-]+)\b")
    for m in pattern.finditer(html):
        tags.add(m.group(1))
    return sorted(tags)


def model_details(model: str) -> Dict[str, Optional[str] | List[str]]:
    """Best-effort: fetch model page and extract simple details.
    Returns keys: title, description, link, variants.
    """
    try:
        html = _get(f"/library/{model}", timeout=10.0)
    except Exception:
        return {"title": model, "description": None, "link": f"{BASE}/library/{model}", "variants": []}

    # Title from <title> or <h1>
    title = None
    m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        # remove site suffix if present
        title = re.sub(r"\s*[\-\|].*", "", title)
    if not title:
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
        if m:
            title = m.group(1).strip()

    # Description from og:description or meta description or first paragraph
    desc = None
    for pattern in [
        r"<meta\s+property=\"og:description\"\s+content=\"([^\"]+)\"",
        r"<meta\s+name=\"description\"\s+content=\"([^\"]+)\"",
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            break
    if not desc:
        m = re.search(r"<p>([^<]{40,300})</p>", html, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()

    variants = model_variants(model)
    return {
        "title": title or model,
        "description": desc,
        "link": f"{BASE}/library/{model}",
        "variants": variants,
    }
