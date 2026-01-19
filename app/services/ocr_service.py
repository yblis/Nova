"""
OCR Service - Extraction intelligente de documents PDF avec détection automatique

Ce service gère l'extraction de texte de PDF avec :
- Détection automatique PDF natif vs scanné
- Extraction directe via PyMuPDF pour PDF natifs
- Extraction via LLM Vision pour PDF scannés
- Conversion en Markdown structuré
"""

import io
import base64
from typing import List, Dict, Tuple, Optional, Literal
from flask import current_app


PDFType = Literal["native", "scanned", "hybrid"]


def detect_pdf_type(pdf_bytes: bytes, threshold: int = 50) -> Tuple[PDFType, Dict]:
    """
    Détecte si un PDF est natif (texte extractible) ou scanné (images).
    
    Args:
        pdf_bytes: Contenu binaire du PDF
        threshold: Nombre minimum de caractères par page pour considérer comme natif
        
    Returns:
        Tuple (type, stats) avec stats contenant les infos de détection
    """
    import fitz  # PyMuPDF
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    stats = {
        "total_pages": len(doc),
        "pages_with_text": 0,
        "pages_with_images": 0,
        "avg_chars_per_page": 0,
        "total_chars": 0,
        "total_images": 0
    }
    
    for page in doc:
        text = page.get_text().strip()
        char_count = len(text)
        stats["total_chars"] += char_count
        
        if char_count >= threshold:
            stats["pages_with_text"] += 1
        
        images = page.get_images()
        if images:
            stats["pages_with_images"] += 1
            stats["total_images"] += len(images)
    
    doc.close()
    
    if stats["total_pages"] > 0:
        stats["avg_chars_per_page"] = stats["total_chars"] / stats["total_pages"]
    
    # Déterminer le type
    text_ratio = stats["pages_with_text"] / stats["total_pages"] if stats["total_pages"] > 0 else 0
    
    if text_ratio >= 0.8:
        pdf_type = "native"
    elif text_ratio <= 0.2:
        pdf_type = "scanned"
    else:
        pdf_type = "hybrid"
    
    return pdf_type, stats


def extract_with_pymupdf(pdf_bytes: bytes) -> Tuple[str, List[Dict]]:
    """
    Extrait le texte d'un PDF natif avec PyMuPDF.
    Préserve la structure par pages.
    
    Returns:
        Tuple (texte_complet, liste_de_pages)
    """
    import fitz
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({
                "page": page_num + 1,
                "content": text.strip(),
                "type": "text"
            })
    
    doc.close()
    
    full_text = "\n\n---\n\n".join([p["content"] for p in pages])
    return full_text, pages


def extract_images_from_pdf(pdf_bytes: bytes) -> List[Dict]:
    """
    Extrait les images d'un PDF pour OCR Vision.
    
    Returns:
        Liste de dicts avec 'page', 'image_bytes', 'format'
    """
    import fitz
    from PIL import Image
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    
    for page_num, page in enumerate(doc):
        # Convertir la page en image (2.5x zoom - haute qualité pour OCR)
        # Plus haute résolution = meilleure reconnaissance des caractères
        mat = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(matrix=mat)
        
        # Convertir en bytes PNG
        img_bytes = pix.tobytes("png")
        
        images.append({
            "page": page_num + 1,
            "image_bytes": img_bytes,
            "format": "png",
            "width": pix.width,
            "height": pix.height
        })
    
    doc.close()
    return images


def image_to_base64(image_bytes: bytes) -> str:
    """Convertit des bytes d'image en base64."""
    return base64.b64encode(image_bytes).decode('utf-8')


def convert_to_markdown(raw_text: str, preserve_structure: bool = True) -> str:
    """
    Convertit du texte brut en Markdown structuré.
    Détecte les headers, listes, tableaux potentiels.
    
    Args:
        raw_text: Texte brut extrait
        preserve_structure: Si True, essaie de détecter la structure
        
    Returns:
        Texte formaté en Markdown
    """
    if not preserve_structure:
        return raw_text
    
    lines = raw_text.split('\n')
    markdown_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            markdown_lines.append('')
            continue
        
        # Détecter les headers potentiels (lignes courtes en majuscules ou avec numérotation)
        if len(stripped) < 80 and stripped.isupper():
            markdown_lines.append(f"## {stripped.title()}")
        elif stripped[0].isdigit() and '.' in stripped[:4]:
            # Numérotation type "1. xxx" ou "1.1 xxx"
            markdown_lines.append(stripped)
        elif stripped.startswith('-') or stripped.startswith('•') or stripped.startswith('*'):
            # Listes
            markdown_lines.append(f"- {stripped.lstrip('-•* ')}")
        else:
            markdown_lines.append(stripped)
    
    return '\n'.join(markdown_lines)


def process_pdf_intelligent(
    pdf_bytes: bytes,
    filename: str,
    ocr_provider: str = "auto",
    ocr_model: str = "",
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> Dict:
    """
    Pipeline complet d'extraction intelligente de PDF.
    
    Stratégie d'extraction:
    1. Tenter l'extraction directe PyMuPDF (PDFs natifs)
    2. Si échec et PDF scanné: utiliser LLM Vision si disponible (meilleure qualité)
    3. Fallback sur Tesseract avec pré-traitement si LLM Vision indisponible
    
    Args:
        pdf_bytes: Contenu binaire du PDF
        filename: Nom du fichier
        ocr_provider: Provider OCR (auto, vision, gemini, openai, anthropic, ollama, tesseract)
        ocr_model: Modèle spécifique à utiliser (ex: gemini-1.5-flash, llava:latest)
        chunk_size: Taille des chunks
        chunk_overlap: Chevauchement des chunks
        
    Returns:
        Dict avec texte, chunks, type_pdf, stats, ocr_used
    """
    from .pdf_service import chunk_text
    from .vision_ocr_service import (
        extract_text_with_ocr, 
        extract_text_with_vision_llm,
        is_vision_llm_available,
        get_best_ocr_method
    )
    import signal
    
    # Timeout handler pour éviter les blocages sur certains PDFs malformés
    def timeout_handler(signum, frame):
        raise TimeoutError(f"PDF processing timeout after 180 seconds for {filename}")
    
    # Configurer le timeout (180 secondes max pour le traitement complet)
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(180)  # 180 secondes timeout (plus long pour LLM Vision)
    
    try:
        # Déterminer le seuil depuis la config
        threshold = current_app.config.get("RAG_OCR_THRESHOLD", 50)
        
        # Détecter le type de PDF
        pdf_type, stats = detect_pdf_type(pdf_bytes, threshold)
        
        current_app.logger.info(f"PDF '{filename}' detected as: {pdf_type} (avg {stats['avg_chars_per_page']:.0f} chars/page)")
    
        result = {
            "filename": filename,
            "pdf_type": pdf_type,
            "stats": stats,
            "ocr_provider_used": None,
            "ocr_method": None,
            "full_text": "",
            "chunks": [],
            "pages": []
        }
        
        # ÉTAPE 1: Toujours essayer d'abord l'extraction directe PyMuPDF
        # Même sur les PDFs "scannés", certains (comme PDF24) ont du texte vectoriel extractible
        full_text, pages = extract_with_pymupdf(pdf_bytes)
        
        if full_text and len(full_text.strip()) > 100:
            # Extraction directe réussie
            result["full_text"] = full_text
            result["pages"] = pages
            result["ocr_provider_used"] = "pymupdf"
            result["ocr_method"] = "direct"
            current_app.logger.info(f"Direct extraction successful: {len(full_text)} chars")
            
        elif pdf_type in ("scanned", "hybrid"):
            # ÉTAPE 2: Pas assez de texte -> OCR nécessaire
            current_app.logger.info(f"Direct extraction failed ({len(full_text) if full_text else 0} chars), trying OCR...")
            
            # Extraire les images des pages pour OCR
            page_images = extract_images_from_pdf(pdf_bytes)
            
            # Déterminer la méthode OCR à utiliser
            use_vision_llm = False
            vision_provider = None
            
            if ocr_provider == "auto":
                # Auto: préférer LLM Vision si disponible
                if is_vision_llm_available():
                    use_vision_llm = True
                    vision_provider = "auto"
            elif ocr_provider == "vision":
                use_vision_llm = True
                vision_provider = "auto"
            elif ocr_provider in ["gemini", "openai", "anthropic", "ollama"]:
                use_vision_llm = True
                vision_provider = ocr_provider
            elif ocr_provider == "tesseract":
                use_vision_llm = False
            else:
                # Défaut: auto
                use_vision_llm = is_vision_llm_available()
            
            pages = []
            
            if use_vision_llm:
                # MÉTHODE 1: OCR via LLM Vision (haute qualité)
                current_app.logger.info(f"Using LLM Vision OCR (provider: {vision_provider or 'auto'})")
                
                for img_data in page_images:
                    try:
                        page_text = extract_text_with_vision_llm(
                            image_bytes=img_data["image_bytes"],
                            provider=vision_provider or "auto",
                            model=ocr_model
                        )
                        pages.append({
                            "page": img_data["page"],
                            "content": page_text,
                            "type": "ocr_vision"
                        })
                        result["ocr_provider_used"] = vision_provider or "vision"
                        result["ocr_method"] = "vision_llm"
                    except Exception as e:
                        current_app.logger.warning(f"Vision OCR failed for page {img_data['page']}: {e}")
                        # Fallback sur Tesseract pour cette page
                        try:
                            page_text = extract_text_with_ocr(
                                image_bytes=img_data["image_bytes"],
                                use_preprocessing=True
                            )
                            pages.append({
                                "page": img_data["page"],
                                "content": page_text,
                                "type": "ocr_tesseract_fallback"
                            })
                        except Exception as e2:
                            current_app.logger.error(f"Tesseract fallback also failed for page {img_data['page']}: {e2}")
                            pages.append({
                                "page": img_data["page"],
                                "content": "",
                                "type": "error",
                                "error": str(e)
                            })
            else:
                # MÉTHODE 2: OCR via Tesseract avec pré-traitement
                current_app.logger.info("Using Tesseract OCR with preprocessing")
                
                for img_data in page_images:
                    try:
                        page_text = extract_text_with_ocr(
                            image_bytes=img_data["image_bytes"],
                            use_preprocessing=True
                        )
                        pages.append({
                            "page": img_data["page"],
                            "content": page_text,
                            "type": "ocr_tesseract"
                        })
                    except Exception as e:
                        current_app.logger.warning(f"OCR failed for page {img_data['page']}: {e}")
                        pages.append({
                            "page": img_data["page"],
                            "content": "",
                            "type": "error",
                            "error": str(e)
                        })
                
                result["ocr_provider_used"] = "tesseract"
                result["ocr_method"] = "tesseract_preprocessed"
            
            result["pages"] = pages
            result["full_text"] = "\n\n---\n\n".join([p["content"] for p in pages if p["content"]])
        
        # Convertir en Markdown
        result["full_text"] = convert_to_markdown(result["full_text"])
        
        # Chunking
        if result["full_text"]:
            result["chunks"] = chunk_text(result["full_text"], chunk_size, chunk_overlap)
        
        # Log du résultat
        current_app.logger.info(
            f"PDF processing complete: {filename} | "
            f"Method: {result['ocr_method']} | "
            f"Provider: {result['ocr_provider_used']} | "
            f"Text: {len(result['full_text'])} chars | "
            f"Chunks: {len(result['chunks'])}"
        )
        
        return result
    
    finally:
        # Toujours désactiver l'alarme et restaurer le handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _get_best_ocr_provider() -> str:
    """
    Détermine le meilleur provider OCR disponible.
    Ordre de priorité : gemini > openai > ollama > tesseract
    """
    from .provider_manager import get_provider_manager
    
    try:
        pm = get_provider_manager()
        
        # Vérifier les providers cloud avec Vision
        if pm.is_provider_configured("gemini"):
            return "gemini"
        if pm.is_provider_configured("openai"):
            return "openai"
        if pm.is_provider_configured("anthropic"):
            return "anthropic"
        
        # Vérifier Ollama avec un modèle Vision
        if pm.is_provider_configured("ollama"):
            # TODO: Vérifier si un modèle vision est disponible
            return "ollama"
        
    except Exception as e:
        current_app.logger.warning(f"Could not determine best OCR provider: {e}")
    
    # Fallback
    return "tesseract"


def get_pdf_info_extended(pdf_bytes: bytes) -> Dict:
    """
    Récupère les métadonnées étendues d'un PDF.
    
    Returns:
        Dict avec pages, title, author, type, stats
    """
    import fitz
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    metadata = doc.metadata
    
    pdf_type, stats = detect_pdf_type(pdf_bytes)
    
    info = {
        'pages': len(doc),
        'title': metadata.get('title', ''),
        'author': metadata.get('author', ''),
        'subject': metadata.get('subject', ''),
        'keywords': metadata.get('keywords', ''),
        'pdf_type': pdf_type,
        'detection_stats': stats
    }
    
    doc.close()
    return info
