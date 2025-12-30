from flask import Blueprint, request, jsonify, Response, current_app
from app.services.audio_config_service import audio_config_service
from app.services.provider_manager import get_provider_manager
from app.services.llm_clients import get_client_for_provider
from app.services.llm_error_handler import LLMError
import logging
import subprocess
import tempfile
import os
import io

api_audio_bp = Blueprint('api_audio', __name__, url_prefix='/api/chat/audio')
logger = logging.getLogger(__name__)


def convert_audio_to_wav(input_file, input_filename: str) -> io.BytesIO:
    """
    Convertit un fichier audio (webm, etc.) en WAV pour compatibilité Whisper.
    Utilise ffmpeg si disponible, sinon retourne le fichier original.
    """
    # Vérifier si c'est un format qui nécessite conversion
    needs_conversion = input_filename.lower().endswith(('.webm', '.m4a', '.ogg', '.opus'))
    
    if not needs_conversion:
        # Retourner le fichier tel quel
        input_file.seek(0)
        return input_file
    
    try:
        # Sauvegarder le fichier temporairement
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(input_filename)[1], delete=False) as tmp_in:
            input_file.save(tmp_in)
            tmp_in_path = tmp_in.name
        
        # Créer le fichier de sortie WAV
        tmp_out_path = tmp_in_path + '.wav'
        
        # Convertir avec ffmpeg
        result = subprocess.run([
            'ffmpeg', '-y', '-i', tmp_in_path,
            '-ar', '16000',  # Sample rate 16kHz (optimal pour Whisper)
            '-ac', '1',       # Mono
            '-c:a', 'pcm_s16le',  # Format PCM 16-bit
            tmp_out_path
        ], capture_output=True, timeout=30)
        
        if result.returncode != 0:
            logger.warning(f"ffmpeg conversion failed: {result.stderr.decode()}")
            # Fallback: retourner le fichier original
            input_file.seek(0)
            os.unlink(tmp_in_path)
            return input_file
        
        # Lire le fichier converti
        with open(tmp_out_path, 'rb') as f:
            wav_data = io.BytesIO(f.read())
            wav_data.name = 'audio.wav'
        
        # Nettoyer les fichiers temporaires
        os.unlink(tmp_in_path)
        os.unlink(tmp_out_path)
        
        logger.info(f"Audio converted from {input_filename} to WAV")
        return wav_data
        
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg conversion timed out")
        input_file.seek(0)
        return input_file
    except FileNotFoundError:
        logger.warning("ffmpeg not found, using original file")
        input_file.seek(0)
        return input_file
    except Exception as e:
        logger.error(f"Audio conversion error: {str(e)}")
        input_file.seek(0)
        return input_file


@api_audio_bp.route('/transcribe', methods=['POST'])
def transcribe_audio():
    """
    Transcrit un fichier audio (Speech-to-Text).
    Reçoit un fichier 'file' dans le FormData.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Récupérer la config
        config = audio_config_service.get_config()
        provider_id = config.get('stt_provider_id')
        model = config.get('stt_model')
        
        if not provider_id or not model:
            return jsonify({'error': 'STT backend not configured'}), 400

        # Obtenir le client pour ce provider
        try:
            mgr = get_provider_manager()
            provider = mgr.get_provider(provider_id, include_api_key=True)
            if not provider:
                return jsonify({'error': f'Provider not found: {provider_id}'}), 400
            client = get_client_for_provider(provider)
        except ValueError as e:
             return jsonify({'error': f'Invalid provider: {str(e)}'}), 400
        
        # Convertir l'audio si nécessaire (webm -> wav)
        audio_file = convert_audio_to_wav(file, file.filename)
        
        # Transcrire
        text = client.transcribe(
            file=audio_file,
            model=model
        )
        
        return jsonify({'text': text})
        
    except LLMError as e:
        return jsonify({'error': e.get_user_message()}), 500
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_audio_bp.route('/speak', methods=['POST'])
def generate_speech():
    """
    Génère de l'audio depuis du texte (Text-to-Speech).
    Reçoit JSON: { text, voice, speed (opt) }
    """
    data = request.get_json()
    text = data.get('text')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        # Récupérer la config (le frontend peut overrider voice/speed si besoin)
        config = audio_config_service.get_config()
        provider_id = config.get('tts_provider_id')
        model = config.get('tts_model')
        voice = data.get('voice') or config.get('tts_voice') or "alloy"
        speed = float(data.get('speed') or config.get('tts_speed') or 1.0)
        
        if not provider_id:
            return jsonify({'error': 'TTS backend not configured'}), 400

        # Obtenir le provider
        mgr = get_provider_manager()
        provider = mgr.get_provider(provider_id, include_api_key=True)
        if not provider:
            return jsonify({'error': f'Provider not found: {provider_id}'}), 400
        
        provider_url = provider.get('url', '')
        provider_name = provider.get('name', '')
        
        # Détecter si c'est AllTalk (API propriétaire, pas OpenAI-compatible)
        if 'alltalk' in provider_url.lower() or 'alltalk' in provider_name.lower():
            from app.services.llm_clients.alltalk_client import AllTalkClient
            
            alltalk_client = AllTalkClient(provider_url)
            audio_content = alltalk_client.generate_speech(
                text=text,
                voice=voice,
                language="fr",
                speed=speed
            )
            
            return Response(
                audio_content, 
                mimetype="audio/wav",
                headers={"Content-Disposition": "attachment; filename=speech.wav"}
            )
        else:
            # Provider OpenAI-compatible standard
            client = get_client_for_provider(provider)
            audio_content = client.generate_speech(
                text=text,
                model=model or "tts-1",
                voice=voice,
                speed=speed
            )
            
            return Response(
                audio_content, 
                mimetype="audio/mpeg",
                headers={"Content-Disposition": "attachment; filename=speech.mp3"}
            )
        
    except LLMError as e:
        return jsonify({'error': e.get_user_message()}), 500
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        return jsonify({'error': str(e)}), 500
