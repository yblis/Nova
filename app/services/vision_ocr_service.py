"""
OCR Service - Utilise Tesseract OCR pour l'extraction de texte des PDF scannés

Simple et fiable - pas de dépendance aux APIs LLM externes.
"""

import io
import os
from typing import Optional
from flask import current_app

# IMPORTANT: Désactiver le multi-threading OpenMP de Tesseract
# Cela évite les blocages/freezes dans les environnements Docker
os.environ['OMP_THREAD_LIMIT'] = '1'

# Configuration par défaut
DEFAULT_LANGUAGES = "fra+eng"  # Français + Anglais


def extract_text_with_ocr(image_bytes: bytes, languages: str = DEFAULT_LANGUAGES) -> str:
    """
    Extrait le texte d'une image en utilisant Tesseract OCR.
    
    Args:
        image_bytes: Données binaires de l'image
        languages: Langues pour l'OCR (format Tesseract: "fra+eng")
        
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
        
        # Réduire la taille si trop grande (pour éviter les blocages Tesseract)
        max_dimension = 2000  # pixels max
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            current_app.logger.info(f"Image resized for OCR: {image.size}")
        
        # Extraire le texte avec Tesseract (avec timeout de 30 secondes)
        text = pytesseract.image_to_string(
            image,
            lang=languages,
            config='--oem 3 --psm 3',  # PSM 3 = fully automatic page segmentation (plus rapide)
            timeout=30  # Timeout de 30 secondes par page
        )
        
        return text.strip()
        
    except ImportError as e:
        current_app.logger.error(f"pytesseract non installé: {e}")
        raise ValueError("pytesseract n'est pas installé")
    except Exception as e:
        current_app.logger.error(f"Erreur OCR Tesseract: {e}")
        raise ValueError(f"Erreur OCR: {e}")


def is_tesseract_available() -> bool:
    """Vérifie si Tesseract est disponible sur le système."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
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
    """Retourne la liste des providers OCR disponibles (pour compatibilité)."""
    providers = []
    
    if is_tesseract_available():
        providers.append({
            "name": "tesseract",
            "available": True,
            "description": "Tesseract OCR (local)"
        })
    
    return providers


# Fonction de compatibilité avec l'ancien système
def get_ocr_provider(provider: str = "tesseract"):
    """Retourne le provider OCR (Tesseract uniquement maintenant)."""
    return TesseractOCR()


class TesseractOCR:
    """Wrapper pour Tesseract OCR."""
    
    def __init__(self, languages: str = DEFAULT_LANGUAGES):
        self.languages = languages
    
    def extract_text(self, image_bytes: bytes) -> str:
        """Extrait le texte d'une image."""
        return extract_text_with_ocr(image_bytes, self.languages)
    
    def is_available(self) -> bool:
        """Vérifie si Tesseract est disponible."""
        return is_tesseract_available()
