"""
OCR Service - Extraction de texte avancée pour PDF scannés

Supporte :
- Tesseract OCR local (avec pré-traitement d'image avancé)
- LLM Vision (Gemini, OpenAI, Anthropic) pour meilleure qualité
"""

import io
import os
import base64
from typing import Optional, List, Tuple
from flask import current_app

# IMPORTANT: Désactiver le multi-threading OpenMP de Tesseract
# Cela évite les blocages/freezes dans les environnements Docker
os.environ['OMP_THREAD_LIMIT'] = '1'

# Configuration par défaut
DEFAULT_LANGUAGES = "fra+eng"  # Français + Anglais


def preprocess_image_for_ocr(image) -> 'Image':
    """
    Pré-traitement avancé de l'image pour améliorer l'OCR.
    
    Applique:
    1. Conversion en niveaux de gris
    2. Augmentation du contraste
    3. Binarisation adaptative
    4. Réduction du bruit
    5. Redressement (deskew) si possible
    
    Args:
        image: PIL Image object
        
    Returns:
        Image pré-traitée
    """
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    import numpy as np
    
    # 1. Convertir en niveaux de gris
    if image.mode != 'L':
        image = image.convert('L')
    
    # 2. Auto-contraste (normalise l'histogramme)
    image = ImageOps.autocontrast(image, cutoff=1)
    
    # 3. Augmenter le contraste
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.8)
    
    # 4. Augmenter la netteté
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.5)
    
    # 5. Binarisation adaptative (seuillage Otsu simulé)
    # Calculer le seuil optimal basé sur l'histogramme
    histogram = image.histogram()
    total_pixels = sum(histogram)
    
    # Seuil de Otsu simplifié
    sum_total = sum(i * histogram[i] for i in range(256))
    sum_bg = 0
    weight_bg = 0
    max_variance = 0
    threshold = 128  # Valeur par défaut
    
    for i in range(256):
        weight_bg += histogram[i]
        if weight_bg == 0:
            continue
        weight_fg = total_pixels - weight_bg
        if weight_fg == 0:
            break
        
        sum_bg += i * histogram[i]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        
        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > max_variance:
            max_variance = variance
            threshold = i
    
    # Appliquer le seuillage avec un offset pour favoriser le texte
    threshold = min(threshold + 10, 255)  # Légèrement plus clair
    image = image.point(lambda x: 255 if x > threshold else 0)
    
    # 6. Réduction du bruit (morphologie)
    # Ouverture morphologique pour supprimer les petits points
    image = image.filter(ImageFilter.MedianFilter(3))
    
    # 7. Dilatation légère pour renforcer les caractères fins
    # Utiliser un filtre de mode qui épaissit légèrement
    image = image.filter(ImageFilter.ModeFilter(3))
    
    return image


def extract_text_with_ocr(image_bytes: bytes, languages: str = DEFAULT_LANGUAGES, use_preprocessing: bool = True) -> str:
    """
    Extrait le texte d'une image en utilisant Tesseract OCR avec pré-traitement.
    
    Args:
        image_bytes: Données binaires de l'image
        languages: Langues pour l'OCR (format Tesseract: "fra+eng")
        use_preprocessing: Appliquer le pré-traitement avancé
        
    Returns:
        Texte extrait de l'image
    """
    try:
        import pytesseract
        from PIL import Image
        
        # Ouvrir l'image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convertir en RGB si nécessaire (pour les images RGBA ou autres)
        if image.mode not in ('L', 'RGB'):
            image = image.convert('RGB')
        
        # Redimensionner si nécessaire (qualité optimale pour OCR = 300 DPI)
        # Pour un document A4 à 300 DPI, la largeur devrait être ~2480 pixels
        min_dimension = 2000  # pixels min pour bonne qualité
        max_dimension = 4000  # pixels max pour éviter les problèmes mémoire
        
        current_max = max(image.size)
        
        if current_max < min_dimension:
            # Upscale pour améliorer la qualité OCR
            ratio = min_dimension / current_max
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            current_app.logger.info(f"Image upscaled for OCR: {image.size}")
        elif current_max > max_dimension:
            # Downscale pour éviter les problèmes
            ratio = max_dimension / current_max
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            current_app.logger.info(f"Image downscaled for OCR: {image.size}")
        
        # Appliquer le pré-traitement si demandé
        if use_preprocessing:
            try:
                image = preprocess_image_for_ocr(image)
                current_app.logger.debug("Image preprocessing applied successfully")
            except Exception as e:
                current_app.logger.warning(f"Preprocessing failed, using original image: {e}")
        
        # Configuration Tesseract optimisée pour documents scannés
        # PSM 6 = Assume a single uniform block of text
        # OEM 3 = Default, based on what is available (LSTM + Legacy)
        tesseract_config = '--oem 3 --psm 6 -c preserve_interword_spaces=1'
        
        # Extraire le texte avec Tesseract
        text = pytesseract.image_to_string(
            image,
            lang=languages,
            config=tesseract_config,
            timeout=60  # Timeout de 60 secondes par page
        )
        
        return text.strip()
        
    except ImportError as e:
        current_app.logger.error(f"pytesseract non installé: {e}")
        raise ValueError("pytesseract n'est pas installé")
    except Exception as e:
        current_app.logger.error(f"Erreur OCR Tesseract: {e}")
        raise ValueError(f"Erreur OCR: {e}")


def extract_text_with_vision_llm(
    image_bytes: bytes, 
    provider: str = "auto",
    model: str = ""
) -> str:
    """
    Extrait le texte d'une image en utilisant un LLM Vision ou un modèle OCR spécialisé.
    
    Supporte :
    - Modèles OCR spécialisés (Mistral OCR, DeepSeek OCR via Ollama)
    - LLMs Vision génériques (Gemini, OpenAI, Anthropic, Ollama)
    
    Args:
        image_bytes: Données binaires de l'image
        provider: Provider à utiliser (auto, mistral, gemini, openai, anthropic, ollama)
        model: Modèle spécifique (optionnel, ex: mistral-ocr-latest, gotocr, minicpm-v)
        
    Returns:
        Texte extrait de l'image
    """
    from .provider_manager import get_provider_manager
    
    pm = get_provider_manager()
    
    # Vérifier si c'est un modèle OCR spécialisé Mistral
    if provider == "mistral" or (model and "ocr" in model.lower() and provider in ["auto", "mistral"]):
        if pm.is_provider_configured("mistral"):
            provider = "mistral"
        else:
            current_app.logger.warning("Mistral OCR requested but Mistral not configured, falling back...")
    
    # Déterminer le provider à utiliser
    if provider == "auto":
        # Ordre de préférence : Mistral OCR > Gemini > OpenAI > Anthropic > Ollama
        for prov in ["mistral", "gemini", "openai", "anthropic", "ollama"]:
            if pm.is_provider_configured(prov):
                provider = prov
                break
        else:
            raise ValueError("Aucun provider Vision configuré (Mistral, Gemini, OpenAI, Anthropic, Ollama)")
    
    # Vérifier que le provider est configuré
    if not pm.is_provider_configured(provider):
        raise ValueError(f"Provider {provider} non configuré")
    
    # Obtenir les credentials du provider
    provider_config = pm.get_provider_by_type(provider, include_api_key=True)
    if not provider_config:
        raise ValueError(f"Impossible de récupérer la configuration du provider {provider}")
    
    # Encoder l'image en base64
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Prompt optimisé pour l'OCR (utilisé pour les LLMs génériques, pas Mistral OCR)
    ocr_prompt = """Extrais TOUT le texte visible dans cette image de document scanné.

Instructions:
- Retranscris le texte EXACTEMENT comme il apparaît
- Préserve la structure (paragraphes, listes, tableaux)
- Inclus les en-têtes, pieds de page, numéros
- Pour les tableaux, utilise le format Markdown
- N'ajoute AUCUNE interprétation ou commentaire
- Si du texte est illisible, indique [illisible]

Retourne UNIQUEMENT le texte extrait, rien d'autre."""
    
    current_app.logger.info(f"OCR via LLM Vision: {provider} (model: {model or 'default'})")
    
    try:
        if provider == "mistral":
            return _ocr_with_mistral_ocr(provider_config, image_bytes, model)
        elif provider == "gemini":
            return _ocr_with_gemini(provider_config, image_base64, ocr_prompt, model)
        elif provider == "openai":
            return _ocr_with_openai(provider_config, image_base64, ocr_prompt, model)
        elif provider == "anthropic":
            return _ocr_with_anthropic(provider_config, image_base64, ocr_prompt, model)
        elif provider == "ollama":
            return _ocr_with_ollama(provider_config, image_base64, ocr_prompt, model)
        else:
            raise ValueError(f"Provider Vision non supporté: {provider}")
    except Exception as e:
        current_app.logger.error(f"Erreur OCR Vision ({provider}): {e}")
        raise


def _ocr_with_mistral_ocr(config: dict, image_bytes: bytes, model: str = "") -> str:
    """
    OCR avec Mistral OCR API spécialisé.
    
    Mistral OCR est un modèle dédié à l'extraction de documents qui :
    - Préserve la structure (tableaux, formules mathématiques, mise en page)
    - Retourne du Markdown structuré
    - Est optimisé pour les documents professionnels
    
    Args:
        config: Configuration du provider Mistral
        image_bytes: Image brute (pas base64)
        model: Modèle OCR à utiliser (défaut: mistral-ocr-latest)
    """
    import requests
    import json
    
    api_key = config.get("api_key")
    if not api_key:
        raise ValueError("Clé API Mistral manquante")
    
    # Modèle par défaut pour OCR
    model_name = model or "mistral-ocr-latest"
    
    # Encoder l'image en base64 avec le bon format
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Détecter le type MIME
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        mime_type = "image/png"
    elif image_bytes[:2] == b'\xff\xd8':
        mime_type = "image/jpeg"
    else:
        mime_type = "image/png"  # Défaut
    
    # API Mistral OCR
    url = "https://api.mistral.ai/v1/ocr"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Payload pour l'API OCR
    payload = {
        "model": model_name,
        "document": {
            "type": "image_url",
            "image_url": f"data:{mime_type};base64,{image_base64}"
        },
        "include_image_base64": False  # On veut juste le texte
    }
    
    current_app.logger.info(f"Calling Mistral OCR API with model: {model_name}")
    
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120
    )
    
    if response.status_code != 200:
        error_detail = response.text[:500] if response.text else "No details"
        raise ValueError(f"Mistral OCR API error {response.status_code}: {error_detail}")
    
    result = response.json()
    
    # Extraire le texte Markdown du résultat
    # La réponse contient généralement {"pages": [{"markdown": "..."}]}
    pages = result.get("pages", [])
    if pages:
        # Combiner toutes les pages
        markdown_parts = []
        for page in pages:
            if isinstance(page, dict):
                md = page.get("markdown", "") or page.get("content", "") or page.get("text", "")
                if md:
                    markdown_parts.append(md)
            elif isinstance(page, str):
                markdown_parts.append(page)
        
        return "\n\n---\n\n".join(markdown_parts)
    
    # Fallback sur d'autres formats de réponse possibles
    if "markdown" in result:
        return result["markdown"]
    if "content" in result:
        return result["content"]
    if "text" in result:
        return result["text"]
    
    current_app.logger.warning(f"Unexpected Mistral OCR response format: {list(result.keys())}")
    return str(result)



def _ocr_with_gemini(config: dict, image_base64: str, prompt: str, model: str = "") -> str:
    """OCR avec Google Gemini Vision."""
    import google.generativeai as genai
    
    api_key = config.get("api_key")
    if not api_key:
        raise ValueError("Clé API Gemini manquante")
    
    genai.configure(api_key=api_key)
    
    # Modèle par défaut pour Vision
    model_name = model or "gemini-1.5-flash"
    
    model_instance = genai.GenerativeModel(model_name)
    
    # Créer le contenu avec l'image
    import base64
    image_data = base64.b64decode(image_base64)
    
    response = model_instance.generate_content([
        prompt,
        {"mime_type": "image/png", "data": image_data}
    ])
    
    return response.text.strip()


def _ocr_with_openai(config: dict, image_base64: str, prompt: str, model: str = "") -> str:
    """OCR avec OpenAI GPT-4 Vision."""
    import openai
    
    api_key = config.get("api_key")
    if not api_key:
        raise ValueError("Clé API OpenAI manquante")
    
    client = openai.OpenAI(api_key=api_key)
    
    # Modèle par défaut pour Vision
    model_name = model or "gpt-4o"
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=4096
    )
    
    return response.choices[0].message.content.strip()


def _ocr_with_anthropic(config: dict, image_base64: str, prompt: str, model: str = "") -> str:
    """OCR avec Anthropic Claude Vision."""
    import anthropic
    
    api_key = config.get("api_key")
    if not api_key:
        raise ValueError("Clé API Anthropic manquante")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Modèle par défaut pour Vision
    model_name = model or "claude-3-5-sonnet-latest"
    
    response = client.messages.create(
        model=model_name,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    )
    
    return response.content[0].text.strip()


def _ocr_with_ollama(config: dict, image_base64: str, prompt: str, model: str = "") -> str:
    """OCR avec Ollama (modèles Vision comme LLaVA, Bakllava)."""
    import requests
    
    base_url = config.get("url", "http://localhost:11434")
    
    # Modèle par défaut pour Vision
    model_name = model or "llava:latest"
    
    response = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Basse température pour plus de précision
                "num_predict": 4096
            }
        },
        timeout=120
    )
    response.raise_for_status()
    
    return response.json().get("response", "").strip()


def is_tesseract_available() -> bool:
    """Vérifie si Tesseract est disponible sur le système."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def is_vision_llm_available() -> bool:
    """Vérifie si au moins un LLM Vision ou OCR spécialisé est configuré."""
    try:
        from .provider_manager import get_provider_manager
        pm = get_provider_manager()
        
        # Mistral OCR en priorité, puis LLMs Vision génériques
        for provider in ["mistral", "gemini", "openai", "anthropic", "ollama"]:
            if pm.is_provider_configured(provider):
                return True
        return False
    except Exception:
        return False


def get_available_languages() -> list:
    """Retourne la liste des langues disponibles pour Tesseract."""
    try:
        import pytesseract
        languages = pytesseract.get_languages()
        return [lang for lang in languages if lang != 'osd']  # Exclure 'osd'
    except Exception:
        return ['eng', 'fra']  # Valeurs par défaut


def list_available_providers() -> list:
    """Retourne la liste des providers OCR disponibles."""
    providers = []
    
    # Tesseract (local)
    if is_tesseract_available():
        providers.append({
            "name": "tesseract",
            "available": True,
            "description": "Tesseract OCR (local, avec pré-traitement)"
        })
    
    # LLM Vision providers
    try:
        from .provider_manager import get_provider_manager
        pm = get_provider_manager()
        
        vision_providers = [
            ("mistral", "Mistral OCR (spécialisé documents, recommandé)"),
            ("gemini", "Google Gemini Vision"),
            ("openai", "OpenAI GPT-4 Vision"),
            ("anthropic", "Anthropic Claude Vision"),
            ("ollama", "Ollama Vision (LLaVA, MiniCPM-V, GOT-OCR, etc.)")
        ]
        
        for prov_type, description in vision_providers:
            if pm.is_provider_configured(prov_type):
                providers.append({
                    "name": prov_type,
                    "available": True,
                    "description": description
                })
    except Exception:
        pass
    
    return providers


def get_best_ocr_method() -> Tuple[str, str]:
    """
    Détermine la meilleure méthode OCR disponible.
    
    Returns:
        Tuple (method, description) où method est 'vision' ou 'tesseract'
    """
    # Préférer les LLM Vision si disponibles
    if is_vision_llm_available():
        return ("vision", "LLM Vision (haute qualité)")
    elif is_tesseract_available():
        return ("tesseract", "Tesseract OCR (local)")
    else:
        return (None, "Aucun OCR disponible")


# Classe de compatibilité
class TesseractOCR:
    """Wrapper pour Tesseract OCR avec pré-traitement."""
    
    def __init__(self, languages: str = DEFAULT_LANGUAGES, use_preprocessing: bool = True):
        self.languages = languages
        self.use_preprocessing = use_preprocessing
    
    def extract_text(self, image_bytes: bytes) -> str:
        """Extrait le texte d'une image."""
        return extract_text_with_ocr(image_bytes, self.languages, self.use_preprocessing)
    
    def is_available(self) -> bool:
        """Vérifie si Tesseract est disponible."""
        return is_tesseract_available()


class VisionLLMOCR:
    """Wrapper pour OCR via LLM Vision."""
    
    def __init__(self, provider: str = "auto", model: str = ""):
        self.provider = provider
        self.model = model
    
    def extract_text(self, image_bytes: bytes) -> str:
        """Extrait le texte d'une image via LLM Vision."""
        return extract_text_with_vision_llm(image_bytes, self.provider, self.model)
    
    def is_available(self) -> bool:
        """Vérifie si un LLM Vision est disponible."""
        return is_vision_llm_available()


def get_ocr_provider(provider: str = "auto"):
    """
    Retourne le meilleur provider OCR disponible.
    
    Args:
        provider: 'auto', 'vision', 'tesseract', ou un nom de provider spécifique
        
    Returns:
        Instance de TesseractOCR ou VisionLLMOCR
    """
    if provider == "auto":
        method, _ = get_best_ocr_method()
        if method == "vision":
            return VisionLLMOCR()
        else:
            return TesseractOCR()
    elif provider == "vision":
        return VisionLLMOCR()
    elif provider == "tesseract":
        return TesseractOCR()
    elif provider in ["gemini", "openai", "anthropic", "ollama"]:
        return VisionLLMOCR(provider=provider)
    else:
        return TesseractOCR()
