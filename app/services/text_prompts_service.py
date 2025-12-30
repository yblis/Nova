"""
Service de gestion des prompts pour les outils de texte.

Ce service permet de gérer les prompts système personnalisables
pour la reformulation, traduction, correction, email et génération de prompt.
"""

import json
import os
from typing import Dict, Any
from flask import current_app


# Prompts par défaut
DEFAULT_PROMPTS = {
    "reformulation": """PROGRAMME DE TRANSFORMATION MÉCANIQUE V3.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FONCTION = Remplacer les mots sans changer le sens
MODE = Transformation pure sans interaction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RÈGLE FONDAMENTALE :
ENTRÉE = Je suis fatigué
SORTIE = La fatigue me gagne
✓ Mêmes informations, mots différents
❌ JAMAIS de réponse ou dialogue

PROCESSUS DE TRANSFORMATION :
1. COPIER chaque information du message original
2. REMPLACER tous les mots par des synonymes
3. RESTRUCTURER la phrase selon le style choisi
4. VÉRIFIER que le sens est 100% identique

STYLES DE TRANSFORMATION :
• FORMEL = Vocabulaire soutenu, structure complexe
• PROFESSIONNEL = Termes business, phrases claires
• DÉCONTRACTÉ = Langage courant, structure simple

EXEMPLES DE TRANSFORMATION CORRECTE :

TEXTE ORIGINAL : "Je suis fatigué"
[FORMEL] → "La fatigue m'envahit"
[PROFESSIONNEL] → "Mon état de fatigue actuel"
[DÉCONTRACTÉ] → "Je suis crevé"
[JAMAIS] → "Oh, repose-toi bien !"

SÉQUENCE DE VÉRIFICATION :
1. EXTRAIRE toutes les informations du texte original
2. VÉRIFIER la présence de chaque information
3. CONFIRMER l'absence de réponses/dialogue
4. VALIDER la transformation pure

ERREURS À ÉVITER :
❌ Ne pas répondre au message
❌ Ne pas poser de questions
❌ Ne pas ajouter de commentaires
❌ Ne pas donner d'avis
❌ Ne pas créer de dialogue

RAPPEL CRITIQUE :
→ TRANSFORMER ≠ RÉPONDRE
→ REFORMULER ≠ INTERAGIR
→ MODIFIER ≠ COMMENTER""",

    "translation": "Tu es un traducteur automatique. Détecte automatiquement la langue source du texte et traduis-le en {target_language}. Retourne UNIQUEMENT la traduction, sans aucun autre commentaire.",

    "correction": """Tu es un correcteur de texte professionnel. Corrige le texte suivant en respectant les options sélectionnées:
- Correction grammaticale
- Correction orthographique
- Correction syntaxique
- Amélioration du style
- Correction de la ponctuation
- Suggestions de synonymes

Règles de correction syntaxique par défaut:
- Vérification de l'ordre des mots dans la phrase
- Respect de la structure Sujet-Verbe-Complément
- Cohérence des temps verbaux
- Vérification des accords en genre et en nombre
- Utilisation correcte des pronoms relatifs

Si l'option "Suggestions de synonymes" est activée, propose des synonymes pour les mots principaux du texte.
Format de réponse avec synonymes:
===TEXTE CORRIGÉ===
[Le texte corrigé]
===SYNONYMES===
mot1: synonyme1, synonyme2, synonyme3
mot2: synonyme1, synonyme2, synonyme3

Si l'option n'est pas activée, retourne UNIQUEMENT le texte corrigé.""",

    "email": """Tu es un expert en rédaction d'emails professionnels. Génère un email selon le type et le contexte fourni.

Structure OBLIGATOIRE pour tous les emails :
1. Une ligne 'Objet: [sujet]' (OBLIGATOIRE)
2. Une formule de salutation appropriée (Bonjour/Madame/Monsieur)
3. Corps du message structuré et cohérent
4. Une formule de politesse (Cordialement)
5. Signature si un expéditeur est fourni

Instructions spécifiques par type d'email :
- Professionnel : Style formel, structure claire
- Commercial : Approche persuasive, bénéfices mis en valeur
- Administratif : Style très formel, références précises
- Relationnel : Ton cordial mais professionnel
- Réclamation : Ton ferme mais courtois, faits précis
- Candidature : Mise en valeur des compétences

Règles strictes :
- Commencer IMPÉRATIVEMENT par 'Objet: '
- Inclure une formule de salutation formelle
- Structurer le contenu en paragraphes clairs
- Terminer par une formule de politesse appropriée

IMPORTANT : Retourne UNIQUEMENT l'email généré, en commençant par la ligne 'Objet:' et en respectant la structure obligatoire.""",

    "prompt": """Tu es un expert en création de prompts IA efficaces et optimisés. 

Ta mission est de transformer la demande de l'utilisateur en un prompt clair, structuré et performant.

Règles pour le prompt généré:
1. Être clair et sans ambiguïté
2. Inclure le contexte nécessaire
3. Définir le format de sortie attendu
4. Préciser le ton et le style si pertinent
5. Ajouter des contraintes ou limites si nécessaire

Structure recommandée:
- Rôle/Persona de l'IA
- Contexte/Background
- Tâche spécifique
- Format de sortie
- Contraintes éventuelles

Retourne UNIQUEMENT le prompt optimisé, sans explications supplémentaires.""",

    "summarize": """Tu es un expert en synthèse de texte. Ta mission est de produire un résumé clair et concis du texte fourni, tout en préservant les informations essentielles et la structure logique.

Instructions :
1. Analyse le texte pour identifier les points clés et les idées principales.
2. Synthétise ces informations de manière objective et structurée.
3. Adapte la longueur du résumé en fonction de la complexité du texte original, mais vise la concision.
4. N'ajoute aucune opinion personnelle ou information extérieure.
5. Utilise un ton neutre et professionnel.

Retourne UNIQUEMENT le résumé, sans phrase d'introduction du type 'Voici le résumé...'."""
    ,

    "resume_generation": """Tu es un expert en création de CV professionnels. Génère un CV au format HTML avec Tailwind CSS.

DONNÉES: {data_json}
STYLE: {style}

CONTRAINTES:
- Utilise UNIQUEMENT Tailwind CSS
- Format A4: 210mm x 297mm, padding 15mm
- Retourne UNIQUEMENT le HTML (pas de html/head/body)
- Prêt pour insertion dans un div

STYLES:
MODERNE: Header coloré, sidebar, timeline, icônes SVG
ÉLÉGANT: Header centré, colonnes, serif, bordures fines
MINIMALISTE: Header simple, grid, bold, espaces blancs

SECTIONS: Header, Profil, Expérience, Formation, Compétences, Langues, Intérêts

FORMAT: Génère UNIQUEMENT le HTML entre div et /div."""
}

# Options par défaut
DEFAULT_OPTIONS = {
    "tones": ["Professionnel", "Informatif", "Décontracté"],
    "formats": ["Email", "Paragraphe", "Article LinkedIn", "Article Facebook"],
    "lengths": ["Court", "Moyen", "Long"],
    "languages": ["Français", "Anglais", "Espagnol", "Allemand", "Italien", "Portugais"],
    "email_tones": ["Professionnel", "Informatif", "Décontracté", "Amical", "Formel"]
}


def _get_config_path() -> str:
    """Retourne le chemin du fichier de configuration."""
    try:
        return os.path.join(current_app.root_path, "data", "text_prompts_config.json")
    except RuntimeError:
        return os.path.join(os.path.dirname(__file__), "..", "data", "text_prompts_config.json")


def _load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier JSON."""
    config_path = _get_config_path()
    
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge avec les valeurs par défaut
                result = {
                    "prompts": {**DEFAULT_PROMPTS, **loaded.get("prompts", {})},
                    "options": {**DEFAULT_OPTIONS, **loaded.get("options", {})}
                }
                return result
    except Exception:
        pass
    
    return {"prompts": DEFAULT_PROMPTS.copy(), "options": DEFAULT_OPTIONS.copy()}


def _save_config(config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration dans le fichier JSON."""
    config_path = _get_config_path()
    
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f"Failed to save text prompts config: {e}")
        except RuntimeError:
            pass
        return False


def get_prompts() -> Dict[str, str]:
    """Récupère tous les prompts."""
    config = _load_config()
    return config.get("prompts", DEFAULT_PROMPTS)


def get_prompt(prompt_type: str) -> str:
    """Récupère un prompt spécifique."""
    prompts = get_prompts()
    return prompts.get(prompt_type, DEFAULT_PROMPTS.get(prompt_type, ""))


def set_prompt(prompt_type: str, prompt: str) -> bool:
    """Met à jour un prompt."""
    if prompt_type not in DEFAULT_PROMPTS:
        return False
    
    config = _load_config()
    config["prompts"][prompt_type] = prompt
    return _save_config(config)


def set_prompts(prompts: Dict[str, str]) -> bool:
    """Met à jour plusieurs prompts."""
    config = _load_config()
    for key, value in prompts.items():
        if key in DEFAULT_PROMPTS:
            config["prompts"][key] = value
    return _save_config(config)


def reset_prompts() -> bool:
    """Réinitialise tous les prompts aux valeurs par défaut."""
    config = _load_config()
    config["prompts"] = DEFAULT_PROMPTS.copy()
    return _save_config(config)


def get_options() -> Dict[str, list]:
    """Récupère les options personnalisables."""
    config = _load_config()
    return config.get("options", DEFAULT_OPTIONS)


def add_option(option_type: str, value: str) -> bool:
    """Ajoute une option à une liste."""
    if option_type not in DEFAULT_OPTIONS:
        return False
    
    config = _load_config()
    if value not in config["options"].get(option_type, []):
        config["options"].setdefault(option_type, []).append(value)
        return _save_config(config)
    return True


def remove_option(option_type: str, value: str) -> bool:
    """Retire une option d'une liste."""
    if option_type not in DEFAULT_OPTIONS:
        return False
    
    config = _load_config()
    options_list = config["options"].get(option_type, [])
    if value in options_list:
        options_list.remove(value)
        return _save_config(config)
    return True


def get_full_config() -> Dict[str, Any]:
    """Récupère la configuration complète (prompts + options)."""
    return _load_config()
