"""
Client pour AllTalk TTS.

AllTalk utilise une API REST propriétaire (pas OpenAI-compatible pour le TTS).
"""

from typing import List, Dict, Any, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class AllTalkClient:
    """Client pour le service AllTalk TTS."""
    
    def __init__(self, base_url: str):
        """
        Initialise le client AllTalk.
        
        Args:
            base_url: URL de base du serveur AllTalk (ex: http://nova-alltalk:7851)
        """
        # Nettoyer l'URL (enlever /v1 si présent car AllTalk n'utilise pas ça)
        self._base_url = base_url.rstrip('/')
        if self._base_url.endswith('/v1'):
            self._base_url = self._base_url[:-3]
    
    def list_voices(self) -> List[str]:
        """Liste les voix disponibles."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self._base_url}/api/voices")
                response.raise_for_status()
                data = response.json()
                return data.get("voices", [])
        except Exception as e:
            logger.error(f"Failed to list AllTalk voices: {e}")
            return ["female_01.wav", "male_01.wav"]  # Fallback
    
    def generate_speech(
        self,
        text: str,
        voice: str = "female_01.wav",
        language: str = "fr",
        speed: float = 1.0
    ) -> bytes:
        """
        Génère de l'audio depuis du texte.
        
        Args:
            text: Texte à lire
            voice: Nom de la voix (fichier .wav)
            language: Code langue (fr, en, etc.)
            speed: Vitesse de lecture (non supporté par AllTalk directement)
            
        Returns:
            Contenu audio en bytes (WAV)
        """
        # S'assurer que le nom de voix a l'extension .wav
        if not voice.endswith('.wav'):
            voice = f"{voice}.wav"
        
        # Générer un nom de fichier unique pour éviter les conflits
        import time
        output_filename = f"output_{int(time.time() * 1000)}"
        
        payload = {
            "text_input": text,
            "text_filtering": "standard",  # Utiliser standard pour filtrer les caractères spéciaux
            "character_voice_gen": voice,
            "narrator_enabled": "false",
            "narrator_voice_gen": voice,
            "text_not_inside": "character",
            "language": language,
            "output_file_name": output_filename,
            "output_file_timestamp": "false",
            "autoplay": "false",
            "autoplay_volume": "0.8"
        }
        
        logger.info(f"AllTalk TTS request - voice: {voice}, lang: {language}, text length: {len(text)} chars")
        
        try:
            with httpx.Client(timeout=120.0) as client:
                # AllTalk retourne un JSON avec le chemin du fichier généré
                # Forcer l'encodage UTF-8 pour les caractères accentués
                response = client.post(
                    f"{self._base_url}/api/tts-generate",
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
                )
                response.raise_for_status()
                result = response.json()
                
                # Récupérer le fichier audio généré
                output_file_path = result.get("output_file_path")
                output_file_url = result.get("output_file_url")
                
                if output_file_url:
                    # AllTalk retourne une URL avec 127.0.0.1, extraire juste le path
                    # Ex: "http://127.0.0.1:7851/audio/test.wav" -> "/audio/test.wav"
                    from urllib.parse import urlparse
                    parsed = urlparse(output_file_url)
                    audio_path = parsed.path  # /audio/test.wav
                    
                    # Télécharger le fichier audio depuis notre base_url
                    audio_url = f"{self._base_url}{audio_path}"
                    logger.info(f"Fetching audio from: {audio_url}")
                    audio_response = client.get(audio_url)
                    audio_response.raise_for_status()
                    return audio_response.content
                else:
                    raise ValueError("AllTalk did not return an audio file URL")
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"AllTalk HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"AllTalk TTS error: {e}")
            raise
    
    def test_connection(self) -> tuple[bool, str]:
        """Teste la connexion au serveur AllTalk."""
        try:
            voices = self.list_voices()
            return True, f"Connecté - {len(voices)} voix disponibles"
        except Exception as e:
            return False, f"Erreur: {str(e)}"
