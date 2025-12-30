# Nova

> Modern and complete web interface to manage your LLM models via Ollama and other providers

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey?logo=flask)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Made by AI](https://img.shields.io/badge/Made%20by-AI-blueviolet?logo=openai)](https://github.com/)

> **🤖 100% AI-Generated Project**  
> This project was entirely designed and developed by artificial intelligence (Claude Opus 4.5/Gemini 3 Pro), from A to Z.  
> Human intervention was limited to debugging, minor fixes, and project direction.

---

## ✨ Features

### 💬 Chat & Conversations
- Modern chat interface with Markdown support
- Persistent conversation history
- Streaming mode for real-time responses
- Multi-agent debate mode with multiple LLMs

### 🌐 Multi-Provider LLM Support
- **Ollama** (local)
- **OpenAI** (GPT-4, GPT-3.5)
- **Anthropic** (Claude)
- **Google** (Gemini)
- **Mistral AI**
- **Groq**
- **Qwen/DashScope**

### 📚 RAG (Retrieval Augmented Generation)
- PDF document upload and indexing
- PostgreSQL vector database (pgvector) + Qdrant
- Hybrid search for contextual responses

### 🎙️ Audio
- **Speech-to-Text (STT)**: Transcription via Whisper
- **Text-to-Speech (TTS)**: Voice synthesis via AllTalk

### 🛠️ Model Management
- Download models from the Ollama library
- Real-time progress tracking
- Delete and manage installed models

### 🌍 Interface
- Dark/light theme
- Multilingual support (FR/EN)
- Responsive design (mobile-first)

---

## 🚀 Installation

### Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- [Ollama](https://ollama.ai/) (optional, for local models)
- NVIDIA GPU + CUDA (optional, for accelerated STT/TTS)

### Quick Deployment

1. **Clone the repository**
   ```bash
   git clone https://github.com/yblis/Nova
   cd Nova
   ```

2. **Configure the environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Launch the application**
   ```bash
   docker compose up -d --build
   ```

4. **Access the interface**
   
   Open your browser at `http://localhost:5000`

---

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | `change-me` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `REDIS_URL` | Redis URL | `redis://redis:6379/0` |
| `POSTGRES_URL` | PostgreSQL URL | See `.env.example` |
| `QDRANT_URL` | Qdrant URL | `http://qdrant:6333` |
| `LLM_ENCRYPTION_KEY` | API encryption key | Auto-generated |

### LLM Providers

To use cloud providers, add your API keys via the admin interface.

---

## 🏗️ Architecture

```
Nova/
├── app/                    # Flask source code
│   ├── blueprints/         # Modules (chat, admin, rag...)
│   ├── services/           # Business logic
│   ├── static/             # CSS, JS, images
│   └── templates/          # Jinja2 templates
├── _Documentation/         # Technical documentation
├── data/                   # Persistent data
├── logs/                   # Log files
├── docker-compose.yml      # Docker configuration
├── Dockerfile              # Application image
└── requirements.txt        # Python dependencies
```

### Docker Services

| Service | Description | Port |
|---------|-------------|------|
| `nova` | Main Flask application | 5000 |
| `nova-worker` | RQ worker for async tasks | - |
| `redis` | Cache and message broker | 6379 |
| `postgres` | Database + pgvector | 5432 |
| `qdrant` | Vector database | 6333 |
| `whisper` | Speech-to-Text | 8000 |
| `alltalk` | Text-to-Speech | 7851 |

---

## 🔧 Development

### Run in Development Mode

```bash
# Without audio (GPU)
docker compose up redis postgres qdrant nova -d

# With real-time logs
docker compose logs -f nova
```

### Rebuild After Changes

```bash
docker compose up -d --build nova
```

---

## 📝 License

This project is licensed under MIT. See the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai/) - For the local LLM API
- [Flask](https://flask.palletsprojects.com/) - Python web framework
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) - Fast STT
- [AllTalk TTS](https://github.com/erew123/alltalk_tts) - Voice synthesis

---

<p align="center">
  Made with ❤️ for the open-source community
</p>
