from flask import Flask
from .config import Config, INSECURE_DEFAULTS, SECURITY_HEADERS
from .extensions import cache, csrf, db, init_redis_rq


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    secret = app.config.get('SECRET_KEY', '')
    is_production = app.config.get('FLASK_ENV') == 'production' or not app.debug
    if secret in INSECURE_DEFAULTS:
        if is_production:
            raise RuntimeError(
                "SECRET_KEY is set to an insecure default. "
                "Set a strong SECRET_KEY in your .env file before running in production."
            )
        app.logger.warning(
            "SECRET_KEY is set to an insecure default. "
            "Please set a strong SECRET_KEY in your .env file."
        )

    # Extensions
    try:
        cache.init_app(app)
    except Exception as e:
        app.logger.warning(f"Cache initialization failed, falling back to SimpleCache: {str(e)}")
        # Fallback to SimpleCache if Redis is not available
        app.config["CACHE_TYPE"] = "SimpleCache"
        cache.init_app(app)

    init_redis_rq(app)

    # SQLAlchemy ORM
    db.init_app(app)
    with app.app_context():
        try:
            from .models import provider, text_tool_history  # noqa: F401 — enregistre les modèles
            db.create_all()
            # Auto-migrate providers from JSON to DB on first boot
            _auto_migrate_providers_json_to_db(app)
        except Exception as e:
            app.logger.warning(f"SQLAlchemy table creation failed (will retry on next request): {e}")

    # CSRF Protection
    csrf.init_app(app)

    # Rate Limiting
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[],  # No global limit, apply per-route
        storage_uri=app.config.get('REDIS_URL', 'memory://'),
    )
    app.limiter = limiter  # Store for access in blueprints

    # Blueprints
    from .blueprints.core.routes import core_bp
    from .blueprints.api.routes_models import api_models_bp
    from .blueprints.api.routes_remote import api_remote_bp
    from .blueprints.api.routes_huggingface import api_huggingface_bp
    from .blueprints.api.routes_lmstudio import api_lmstudio_bp
    from .blueprints.api.sse import sse_bp
    from .blueprints.api.routes_settings import api_settings_bp
    from .blueprints.api.routes_chat import api_chat_bp
    from .blueprints.api.routes_texts import api_texts_bp
    from .blueprints.api.routes_audio import api_audio_bp
    from .blueprints.api.routes_specialists import specialists_bp
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp

    # Exempt API blueprints from CSRF (they use JSON, not form submissions)
    # NOTE: csrf.exempt() requires the Blueprint OBJECT to exempt an entire blueprint
    csrf.exempt(api_chat_bp)
    csrf.exempt(sse_bp)
    csrf.exempt(api_models_bp)
    csrf.exempt(api_remote_bp)
    csrf.exempt(api_huggingface_bp)
    csrf.exempt(api_lmstudio_bp)
    csrf.exempt(api_settings_bp)
    csrf.exempt(api_texts_bp)
    csrf.exempt(api_audio_bp)
    csrf.exempt(specialists_bp)

    app.register_blueprint(core_bp)
    app.register_blueprint(api_models_bp, url_prefix="/api")
    app.register_blueprint(api_remote_bp, url_prefix="/api")
    app.register_blueprint(api_huggingface_bp, url_prefix="/api")
    app.register_blueprint(api_lmstudio_bp, url_prefix="/api")
    app.register_blueprint(sse_bp, url_prefix="/api/stream")
    app.register_blueprint(api_settings_bp, url_prefix="/api/settings")
    app.register_blueprint(api_chat_bp, url_prefix="/api")
    app.register_blueprint(api_texts_bp, url_prefix="/api")
    app.register_blueprint(api_audio_bp) # url_prefix est déjà défini dans le blueprint
    app.register_blueprint(specialists_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Login Manager setup
    from .extensions import login_manager
    login_manager.init_app(app)

    from .services.user_service import user_service

    @login_manager.user_loader
    def load_user(user_id):
        return user_service.get_user(user_id)
    
    # Ensure admin exists and initialize databases
    with app.app_context():
        user_service.ensure_admin_exists()
        
        # Ensure local audio providers exist
        from .services.provider_manager import ensure_local_audio_providers
        ensure_local_audio_providers()
        
        # Initialize database tables at startup (instead of per-request)
        try:
            from .services.rag_service import init_db as init_rag_db
            init_rag_db()
        except Exception as e:
            app.logger.warning(f"RAG DB init failed (will retry on first use): {e}")
        
        try:
            from .services.specialist import init_db as init_specialist_db
            init_specialist_db()
        except Exception as e:
            app.logger.warning(f"Specialist DB init failed (will retry on first use): {e}")
        
        try:
            from .services.chat_history_pg import init_chat_db
            init_chat_db()
        except Exception as e:
            app.logger.warning(f"Chat DB init failed (will retry on first use): {e}")
        
        try:
            from .services.memory_graph_service import init_memory_graph_db
            init_memory_graph_db()
        except Exception as e:
            app.logger.warning(f"Memory Graph DB init failed (will retry on first use): {e}")

    # Global Login Requirement
    from flask import request, redirect, url_for
    from flask_login import current_user

    @app.before_request
    def require_login():
        if request.endpoint == 'static':
            return
            
        allowed_endpoints = ['auth.login', 'auth.logout', 'api_models.running', 'core.manifest', 'core.service_worker']
        if request.endpoint in allowed_endpoints or (request.endpoint and request.endpoint.endswith('.static')):
            return
            
        if not current_user.is_authenticated:
            # Check if it's an API request? 
            # If API, maybe return 401? For now, standard behavior.
            return login_manager.unauthorized()


    @app.after_request
    def set_security_headers(response):
        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers.setdefault(header_name, header_value)
        return response

    from .utils import get_effective_ollama_base_url

    @app.context_processor
    def inject_globals():
        return {"ollama_base_url": get_effective_ollama_base_url()}

    return app


def _auto_migrate_providers_json_to_db(app):
    """Importe les providers depuis providers.json si aucun provider LLM n'est en DB.
    
    Utilise un advisory lock PostgreSQL pour éviter les race conditions
    entre les workers gunicorn qui démarrent en parallèle.
    """
    import json
    import os
    import uuid as _uuid
    from .models.provider import Provider
    from .extensions import db as _db
    from sqlalchemy import text

    try:
        # Advisory lock pour éviter la race condition entre workers
        _db.session.execute(text("SELECT pg_advisory_lock(42)"))
    except Exception:
        # Si l'advisory lock échoue (SQLite, etc.), on continue sans
        pass

    try:
        # Vérifier s'il y a déjà des providers LLM (pas juste audio)
        llm_types = {'ollama', 'groq', 'openai', 'anthropic', 'gemini', 'mistral',
                     'huggingface', 'lmstudio', 'openrouter', 'deepseek', 'cerebras', 'sambanova'}
        existing_llm = Provider.query.filter(Provider.type.in_(llm_types)).count()
        if existing_llm > 0:
            return

        json_path = os.path.join(app.root_path, 'data', 'providers.json')
        if not os.path.exists(json_path):
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        active_id = data.get('active_provider_id')
        count = 0
        for p in data.get('providers', []):
            pid = p.get('id') or str(_uuid.uuid4())
            # Éviter les doublons
            if Provider.query.get(pid):
                continue
            provider = Provider(
                id=pid,
                name=p.get('name', 'Sans nom'),
                type=p.get('type', 'ollama'),
                url=p.get('url', ''),
                api_key_encrypted=p.get('api_key_encrypted', ''),
                is_active=(pid == active_id),
            )
            provider.set_extra_headers(p.get('extra_headers', {}))
            _db.session.add(provider)
            count += 1
        _db.session.commit()
        if count:
            app.logger.info(f'[ProviderManagerDB] Auto-migrated {count} providers from JSON')
            # Si aucun actif, activer le premier
            if not Provider.query.filter_by(is_active=True).first():
                first = Provider.query.first()
                if first:
                    first.is_active = True
                    _db.session.commit()
    except Exception as e:
        _db.session.rollback()
        app.logger.warning(f'[ProviderManagerDB] JSON migration failed: {e}')
    finally:
        try:
            _db.session.execute(text("SELECT pg_advisory_unlock(42)"))
            _db.session.commit()
        except Exception:
            pass

