"""
Service d'orchestration pour le mode débat multi-LLM.

Ce service gère les appels parallèles ou séquentiels à plusieurs fournisseurs LLM
et orchestre le streaming des réponses.
"""

import asyncio
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Generator, Iterator
from dataclasses import dataclass, field
from flask import current_app

from .llm_clients import get_client_for_provider
from .provider_manager import get_provider_manager, PROVIDER_TYPES

DEBATE_CONFIG_FILE = "app/data/debate_config.json"

@dataclass
class Participant:
    """Représente un participant au débat."""
    id: str
    provider_id: str
    model: str
    name: str
    color: str
    system_prompt: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Participant":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            provider_id=data["provider_id"],
            model=data["model"],
            name=data.get("name", data["model"]),
            color=data.get("color", "zinc"),
            system_prompt=data.get("system_prompt", "")
        )
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "model": self.model,
            "name": self.name,
            "color": self.color,
            "system_prompt": self.system_prompt
        }


@dataclass
class DebateMessage:
    """Message dans un débat."""
    role: str
    content: str
    participant_id: Optional[str] = None
    participant_name: Optional[str] = None
    color: Optional[str] = None
    timestamp: float = 0


class DebateService:
    """Orchestre les réponses de plusieurs LLM."""
    
    # Couleurs par type de provider
    PROVIDER_COLORS = {
        "ollama": "blue",
        "gemini": "purple",
        "groq": "cyan",
        "openai": "emerald",
        "anthropic": "amber",
        "mistral": "orange",
        "openrouter": "pink",
        "deepseek": "indigo",
        "qwen": "rose",
        "lmstudio": "teal",
        "openai_compatible": "slate"
    }
    
    def __init__(self):
        self.provider_manager = get_provider_manager()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def get_available_providers(self) -> List[Dict]:
        """Retourne la liste des providers disponibles avec leurs modèles."""
        providers = self.provider_manager.get_providers()
        result = []
        
        for p in providers:
            provider_name = p.get("name", "")
            
            # Exclure les providers audio (TTS/STT)
            if "(TTS)" in provider_name or "(STT)" in provider_name:
                continue
                
            provider_type = p.get("type", "")
            result.append({
                "id": p["id"],
                "name": provider_name,
                "type": provider_type,
                "color": self.PROVIDER_COLORS.get(provider_type, "zinc"),
                "default_model": p.get("default_model", "")
            })
        
        return result
    
    def get_provider_color(self, provider_type: str) -> str:
        """Retourne la couleur associée à un type de provider."""
        return self.PROVIDER_COLORS.get(provider_type, "zinc")
    
    def _get_client_and_stream(
        self,
        participant: Participant,
        messages: List[Dict],
        options: Optional[Dict] = None
    ) -> Iterator[Dict]:
        """
        Génère un stream de réponses pour un participant.
        
        Yields:
            Dict avec: participant_id, name, content, thinking, done
        """
        try:
            # Récupérer le provider
            provider = self.provider_manager.get_provider(
                participant.provider_id, 
                include_api_key=True
            )
            
            if not provider:
                yield {
                    "participant_id": participant.id,
                    "name": participant.name,
                    "color": participant.color,
                    "error": f"Provider {participant.provider_id} non trouvé",
                    "done": True
                }
                return
            
            # Obtenir le client
            client = get_client_for_provider(provider)
            
            # Préparer les messages avec le system prompt du participant
            chat_messages = []
            if participant.system_prompt:
                chat_messages.append({
                    "role": "system",
                    "content": participant.system_prompt
                })
            chat_messages.extend(messages)
            
            # Stream la réponse
            for chunk in client.chat_stream(
                messages=chat_messages,
                model=participant.model,
                options=options
            ):
                msg = chunk.get("message", {})
                yield {
                    "participant_id": participant.id,
                    "name": participant.name,
                    "color": participant.color,
                    "content": msg.get("content", ""),
                    "thinking": msg.get("thinking", ""),
                    "done": chunk.get("done", False)
                }
                
        except Exception as e:
            current_app.logger.error(f"Debate stream error for {participant.name}: {e}")
            yield {
                "participant_id": participant.id,
                "name": participant.name,
                "color": participant.color,
                "error": str(e),
                "done": True
            }
    
    def parallel_generate(
        self,
        participants: List[Participant],
        messages: List[Dict],
        options: Optional[Dict] = None
    ) -> Generator[Dict, None, None]:
        """
        Génère les réponses de tous les participants en parallèle.
        
        Les réponses sont entrelacées au fur et à mesure qu'elles arrivent.
        
        Yields:
            Dict avec les chunks de chaque participant
        """
        import queue
        
        result_queue = queue.Queue()
        active_threads = []
        
        def stream_participant(participant: Participant):
            """Thread worker pour un participant."""
            try:
                for chunk in self._get_client_and_stream(participant, messages, options):
                    result_queue.put(chunk)
            except Exception as e:
                result_queue.put({
                    "participant_id": participant.id,
                    "name": participant.name,
                    "color": participant.color,
                    "error": str(e),
                    "done": True
                })
        
        # Démarrer un thread par participant
        for participant in participants:
            thread = threading.Thread(target=stream_participant, args=(participant,))
            thread.start()
            active_threads.append(thread)
        
        # Collecter les résultats
        done_count = 0
        while done_count < len(participants):
            try:
                chunk = result_queue.get(timeout=0.1)
                yield chunk
                if chunk.get("done") or chunk.get("error"):
                    done_count += 1
            except queue.Empty:
                # Vérifier si tous les threads sont terminés
                if all(not t.is_alive() for t in active_threads):
                    break
        
        # Attendre la fin de tous les threads
        for thread in active_threads:
            thread.join(timeout=1.0)
    
    def sequential_generate(
        self,
        participants: List[Participant],
        user_message: str,
        conversation_history: List[Dict],
        rounds: int = 1,
        options: Optional[Dict] = None
    ) -> Generator[Dict, None, None]:
        """
        Génère les réponses séquentiellement avec contexte croisé.
        
        Chaque participant voit les réponses précédentes des autres.
        
        Args:
            participants: Liste des participants
            user_message: Message de l'utilisateur
            conversation_history: Historique de la conversation
            rounds: Nombre de tours de débat
            options: Options LLM
            
        Yields:
            Dict avec les chunks de chaque participant
        """
        current_round_responses = {}
        
        for round_num in range(rounds):
            for participant in participants:
                # Construire le contexte avec les réponses des autres
                context_messages = list(conversation_history)
                
                # Ajouter le message utilisateur
                context_messages.append({
                    "role": "user",
                    "content": user_message
                })
                
                # Ajouter les réponses des autres participants de ce tour
                for other_id, response in current_round_responses.items():
                    if other_id != participant.id:
                        other_participant = next(
                            (p for p in participants if p.id == other_id), 
                            None
                        )
                        if other_participant:
                            # Indiquer que c'est la réponse d'un autre LLM
                            context_messages.append({
                                "role": "assistant",
                                "content": f"[{other_participant.name}]: {response}"
                            })
                            context_messages.append({
                                "role": "user",
                                "content": f"Réagissez à la réponse de {other_participant.name} ci-dessus."
                            })
                
                # Collecter la réponse complète pour le contexte
                full_response = ""
                
                # Signaler le début de la réponse de ce participant
                yield {
                    "participant_id": participant.id,
                    "name": participant.name,
                    "color": participant.color,
                    "round": round_num + 1,
                    "start": True,
                    "done": False
                }
                
                for chunk in self._get_client_and_stream(participant, context_messages, options):
                    full_response += chunk.get("content", "")
                    chunk["round"] = round_num + 1
                    yield chunk
                
                # Stocker la réponse pour le contexte des suivants
                current_round_responses[participant.id] = full_response
    
    def build_debate_system_prompt(
        self, 
        participant: Participant, 
        other_participants: List[Participant],
        debate_topic: Optional[str] = None
    ) -> str:
        """
        Construit un system prompt pour un débat.
        
        Args:
            participant: Le participant actuel
            other_participants: Les autres participants
            debate_topic: Sujet du débat (optionnel)
        """
        if participant.system_prompt:
            return participant.system_prompt
        
        other_names = [p.name for p in other_participants if p.id != participant.id]
        
        prompt = f"""Tu es {participant.name}, un assistant IA participant à une discussion.

Tu participes à un débat/discussion avec d'autres IA : {', '.join(other_names)}.

Règles du débat :
1. Exprime tes opinions de manière claire et argumentée
2. Réagis aux arguments des autres participants quand pertinent
3. Sois respectueux mais n'hésite pas à défendre ton point de vue
4. Apporte des perspectives uniques basées sur tes connaissances
5. Reste concis et pertinent

{f"Sujet du débat : {debate_topic}" if debate_topic else ""}
"""
        return prompt


    def get_debate_defaults(self) -> List[Dict]:
        """Récupère la configuration par défaut du débat."""
        import os
        import json
        
        # Chemin absolu par rapport à la racine de l'application
        config_path = os.path.join(current_app.root_path, "..", DEBATE_CONFIG_FILE)
        
        if not os.path.exists(config_path):
            return []
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            current_app.logger.error(f"Error loading debate defaults: {e}")
            return []

    def save_debate_defaults(self, participants: List[Dict]) -> bool:
        """Sauvegarde la configuration actuelle comme défaut."""
        import os
        import json
        
        config_path = os.path.join(current_app.root_path, "..", DEBATE_CONFIG_FILE)
        
        try:
            # Assurer que le dossier existe
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(participants, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            current_app.logger.error(f"Error saving debate defaults: {e}")
            return False


def get_debate_service() -> DebateService:
    """Factory pour obtenir une instance du DebateService."""
    return DebateService()
