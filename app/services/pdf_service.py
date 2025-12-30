"""
PDF Service - Extraction et chunking de documents PDF
"""

import io
from typing import List, Dict, Tuple


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extrait le texte d'un fichier PDF.
    
    Args:
        pdf_bytes: Contenu binaire du PDF
        
    Returns:
        Texte extrait du PDF
    """
    import fitz  # PyMuPDF
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if text.strip():
            text_parts.append(text)
    
    doc.close()
    return "\n\n".join(text_parts)


def chunk_text(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[Dict[str, any]]:
    """
    Découpe le texte en chunks avec chevauchement.
    
    Args:
        text: Texte à découper
        chunk_size: Taille maximale de chaque chunk (en caractères)
        overlap: Nombre de caractères de chevauchement entre chunks
        
    Returns:
        Liste de dicts avec 'index' et 'content'
    """
    if not text:
        return []
    
    # Nettoyer le texte
    text = text.strip()
    
    # Simple chunking par caractères avec respect des phrases
    chunks = []
    start = 0
    chunk_index = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Si on n'est pas à la fin, essayer de couper sur une phrase
        if end < len(text):
            # Chercher le dernier point, point d'interrogation ou exclamation
            last_sentence_end = max(
                text.rfind('. ', start, end),
                text.rfind('? ', start, end),
                text.rfind('! ', start, end),
                text.rfind('\n', start, end)
            )
            
            if last_sentence_end > start + chunk_size // 2:
                end = last_sentence_end + 1
        
        chunk_content = text[start:end].strip()
        
        if chunk_content:
            chunks.append({
                'index': chunk_index,
                'content': chunk_content
            })
            chunk_index += 1
        
        # Prochain chunk avec overlap
        start = end - overlap if end < len(text) else end
    
    return chunks


def process_pdf(
    pdf_bytes: bytes, 
    filename: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> Tuple[str, List[Dict[str, any]]]:
    """
    Pipeline complet: extraction + chunking d'un PDF.
    
    Args:
        pdf_bytes: Contenu binaire du PDF
        filename: Nom du fichier
        chunk_size: Taille des chunks
        overlap: Chevauchement
        
    Returns:
        Tuple (texte complet, liste de chunks)
    """
    text = extract_text_from_pdf(pdf_bytes)
    chunks = chunk_text(text, chunk_size, overlap)
    
    return text, chunks


def get_pdf_info(pdf_bytes: bytes) -> Dict[str, any]:
    """
    Récupère les métadonnées d'un PDF.
    
    Returns:
        Dict avec pages, title, author, etc.
    """
    import fitz
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    metadata = doc.metadata
    
    info = {
        'pages': len(doc),
        'title': metadata.get('title', ''),
        'author': metadata.get('author', ''),
        'subject': metadata.get('subject', ''),
        'keywords': metadata.get('keywords', ''),
    }
    
    doc.close()
    return info
