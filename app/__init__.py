from flask import Flask
from .config import Config
from .extensions import cache, init_redis_rq


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    # Extensions
    try:
        cache.init_app(app)
    except Exception as e:
        app.logger.warning(f"Cache initialization failed, falling back to SimpleCache: {str(e)}")
        # Fallback to SimpleCache if Redis is not available
        app.config["CACHE_TYPE"] = "SimpleCache"
        cache.init_app(app)

    init_redis_rq(app)

    # Blueprints
    from .blueprints.core.routes import core_bp
    from .blueprints.api.routes_models import api_models_bp
    from .blueprints.api.routes_remote import api_remote_bp
    from .blueprints.api.routes_huggingface import api_huggingface_bp
    from .blueprints.api.sse import sse_bp
    from .blueprints.api.routes_settings import api_settings_bp
    from .blueprints.api.routes_chat import api_chat_bp
    from .blueprints.api.routes_texts import api_texts_bp
    from .blueprints.api.routes_audio import api_audio_bp
    from .blueprints.api.routes_specialists import specialists_bp
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(api_models_bp, url_prefix="/api")
    app.register_blueprint(api_remote_bp, url_prefix="/api")
    app.register_blueprint(api_huggingface_bp, url_prefix="/api")
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
    
    # Ensure admin exists
    with app.app_context():
        user_service.ensure_admin_exists()
        
        # Ensure local audio providers exist
        from .services.provider_manager import ensure_local_audio_providers
        ensure_local_audio_providers()

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


    # Template globals
    from .utils import get_effective_ollama_base_url

    @app.context_processor
    def inject_globals():
        return {"ollama_base_url": get_effective_ollama_base_url()}

    return app
