# Listing dynamique des modèles LLM

## Architecture

Le listing des modèles LLM est **exclusivement dynamique** : chaque client interroge l'API de son fournisseur pour récupérer la liste des modèles disponibles. Aucune liste statique n'est maintenue dans le code.

## Interface publique

Tous les clients LLM implémentent `BaseLLMClient.list_models()` qui retourne :

```python
List[Dict[str, Any]]
```

Chaque dictionnaire contient au minimum :
- `id` : identifiant du modèle (utilisé pour les appels API)
- `name` : nom d'affichage
- `description` : description optionnelle

## Comportement par fournisseur

| Fournisseur | Méthode de listing | Fallback en cas d'échec |
|---|---|---|
| **Ollama** | `GET /api/tags` | `[]` + log warning |
| **OpenAI / Groq / Mistral / DeepSeek / Cerebras** | SDK OpenAI `client.models.list()` | `[]` + log warning |
| **LM Studio** | API native v1 `/api/v1/models` (fallback v0) | SDK OpenAI puis `[]` |
| **Hugging Face** | API Hub `/api/models` + filtres | `[]` + log warning |
| **OpenRouter / OpenRouter Free** | SDK OpenAI `client.models.list()` | `[]` + log warning |
| **Google Gemini** | SDK google-genai `client.models.list()` | `[]` + log warning |
| **Anthropic** | SDK anthropic `client.models.list()` | `[]` + log warning |
| **Qwen (DashScope)** | API OpenAI-compatible `GET /models` | `[]` + log warning |
| **Cohere** | `GET /v1/models` via httpx | `[]` + exception LLMError |

## Modèle par défaut

`get_default_model()` retourne `None` pour les fournisseurs cloud (Gemini, Anthropic, Qwen). Le modèle par défaut est géré par `ProviderManager.get_default_model(provider_id)` qui persiste le choix utilisateur en base de données.

Pour les fournisseurs compatibles OpenAI, un `default_model` est défini dans `PROVIDER_CONFIGS` mais sert uniquement de suggestion initiale.

## Test de connexion

Chaque client implémente `test_connection()` qui valide la connectivité en listant les modèles disponibles (et non en envoyant un message à un modèle hardcodé). Cela garantit que :
1. La clé API est valide
2. Le service est joignable
3. Aucun modèle n'est consommé ou facturé pendant le test

## Dépendances

- `google-genai` : SDK Google GenAI pour Gemini
- `anthropic` : SDK Anthropic pour Claude
- `httpx` : Client HTTP pour Qwen/DashScope (API compatible OpenAI)
- `openai` : SDK OpenAI pour les providers compatibles

## Effets de bord

`list_models()` effectue un appel réseau à l'API du fournisseur. Si l'API est indisponible ou la clé invalide, la méthode retourne une liste vide et logge un warning.

## Considérations de sécurité

- Les clés API sont transmises aux SDK via leurs mécanismes natifs (headers Authorization ou paramètres de constructeur)
- Les appels de listing ne consomment pas de tokens et ne transmettent aucune donnée utilisateur
- Les erreurs ne sont jamais remontées telles quelles à l'utilisateur (pas de fuite de clé dans les traces)
