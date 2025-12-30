Documentation Technique : Intégration des APIs LLM en PythonCe document détaille l'implémentation technique des principaux fournisseurs de modèles de langage (LLM) pour une application Python.1. Prérequis et InstallationInstallation des SDK officiels via pip.pip install openai anthropic google-generativeai mistralai groq dashscope
2. Architecture Standard (OpenAI & Compatible)La majorité des fournisseurs modernes (LM Studio, Groq, OpenRouter, DeepSeek) adoptent le format de l'API OpenAI. Il est recommandé d'utiliser la librairie openai en changeant simplement base_url et api_key.A. OpenAI (Officiel)Librairie : openaiModèles clés : gpt-4o, gpt-4o-minifrom openai import OpenAI

client = OpenAI(api_key="sk-...")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Tu es un assistant utile."},
        {"role": "user", "content": "Reformule ce texte."}
    ],
    temperature=0.7
)

print(response.choices[0].message.content)
B. LM Studio (Local)Librairie : openaiBase URL : http://localhost:1234/v1 (Port par défaut)API Key : "lm-studio" (ou n'importe quelle chaîne, non vérifiée en local)from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

response = client.chat.completions.create(
    model="model-identifier", # Optionnel sur LM Studio, il prend le modèle chargé
    messages=[
        {"role": "system", "content": "Tu es un expert en correction."},
        {"role": "user", "content": "Corrige ce texte."}
    ],
    temperature=0.7
)

print(response.choices[0].message.content)
C. Groq (Vitesse Extrême)Librairie : groq (ou openai compatible)Note : Utiliser le SDK officiel est recommandé pour la gestion spécifique des erreurs.Modèles clés : llama3-8b-8192, mixtral-8x7b-32768from groq import Groq

client = Groq(api_key="gsk_...")

response = client.chat.completions.create(
    model="llama3-70b-8192",
    messages=[
        {"role": "system", "content": "Réponds en français."},
        {"role": "user", "content": "Explique l'IA."}
    ]
)

print(response.choices[0].message.content)
D. OpenRouter (Agrégateur)Librairie : openaiBase URL : https://openrouter.ai/api/v1Modèles clés : anthropic/claude-3.5-sonnet, meta-llama/llama-3-70b-instructfrom openai import OpenAI

client = OpenAI(
    base_url="[https://openrouter.ai/api/v1](https://openrouter.ai/api/v1)",
    api_key="sk-or-...",
)

response = client.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    messages=[{"role": "user", "content": "Bonjour"}],
    extra_headers={
        "HTTP-Referer": "[https://monsite.com](https://monsite.com)", # Requis par OpenRouter
        "X-Title": "MonApp"
    }
)

print(response.choices[0].message.content)
E. DeepSeek (Compatible)Librairie : openaiBase URL : https://api.deepseek.comModèles clés : deepseek-chat (V3), deepseek-coderfrom openai import OpenAI

client = OpenAI(
    base_url="[https://api.deepseek.com](https://api.deepseek.com)",
    api_key="sk-..."
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Tu es un assistant utile."},
        {"role": "user", "content": "Bonjour"}
    ],
    stream=False
)

print(response.choices[0].message.content)
3. APIs Spécifiques (SDK Propriétaires)Ces fournisseurs nécessitent ou recommandent leurs propres librairies pour des fonctionnalités avancées.F. Anthropic (Claude)Librairie : anthropicModèles clés : claude-3-5-sonnet-20240620, claude-3-opus-20240229import anthropic

client = anthropic.Anthropic(api_key="sk-ant-...")

message = client.messages.create(
    model="claude-3-5-sonnet-20240620",
    max_tokens=1024,
    system="Tu es un expert en reformulation.",
    messages=[
        {"role": "user", "content": "Reformule ceci de manière formelle."}
    ]
)

print(message.content[0].text)
G. Google GeminiLibrairie : google-generativeaiModèles clés : gemini-1.5-pro, gemini-1.5-flashimport google.generativeai as genai
import os

genai.configure(api_key="AIzaSy...")

model = genai.GenerativeModel('gemini-1.5-flash')

response = model.generate_content(
    "Explique la physique quantique simplement.",
    generation_config=genai.types.GenerationConfig(
        temperature=0.7
    )
)

print(response.text)
H. Mistral AI (La Plateforme)Librairie : mistralaiModèles clés : mistral-large-latest, mistral-small-latestfrom mistralai import Mistral

client = Mistral(api_key="b_...")

response = client.chat.complete(
    model="mistral-large-latest",
    messages=[
        {"role": "user", "content": "Quelle est la capitale de la France ?"}
    ]
)

print(response.choices[0].message.content)
I. Qwen (Alibaba Cloud / DashScope)Librairie : dashscopeModèles clés : qwen-max, qwen-plusVariable d'env : DASHSCOPE_API_KEYfrom http import HTTPStatus
import dashscope

dashscope.api_key = "sk-..."

response = dashscope.Generation.call(
    model='qwen-max',
    messages=[
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'Explain API integration.'}
    ],
    result_format='message',  # Requis pour avoir un format compatible message
)

if response.status_code == HTTPStatus.OK:
    print(response.output.choices[0]['message']['content'])
else:
    print(f"Erreur: {response.code} - {response.message}")
Tableau Récapitulatif des Base URLs (Compatible OpenAI)Si vous souhaitez centraliser votre code autour de la librairie openai uniquement (sauf Gemini/Anthropic/Qwen natif), voici les endpoints à configurer :FournisseurBase URLModèle ExempleLM Studiohttp://localhost:1234/v1(Selon chargement)OpenAIhttps://api.openai.com/v1gpt-4oDeepSeekhttps://api.deepseek.comdeepseek-chatOpenRouterhttps://openrouter.ai/api/v1mistralai/mistral-largeGroqhttps://api.groq.com/openai/v1llama3-70b-8192Mistralhttps://api.mistral.ai/v1mistral-large-latest