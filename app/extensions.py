from __future__ import annotations

from flask import Flask
from flask_caching import Cache


from flask_caching import Cache
from flask_login import LoginManager


cache = Cache()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"



def init_redis_rq(app: Flask) -> None:
    try:
        from redis import Redis
        from rq import Queue
    except Exception:
        # Optional during local dev/tests without Redis/RQ
        app.redis = None  # type: ignore[attr-defined]
        app.rq = None  # type: ignore[attr-defined]
        return

    try:
        redis_url = app.config["REDIS_URL"]
        app.redis = Redis.from_url(redis_url)  # type: ignore[attr-defined]
        # Test the connection
        app.redis.ping()  # type: ignore[attr-defined]
        app.rq = Queue("ollama", connection=app.redis, default_timeout=app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600))  # type: ignore[attr-defined]
    except Exception as e:
        # Redis connection failed - continue without Redis/RQ
        app.logger.warning(f"Redis connection failed: {str(e)}")
        app.redis = None  # type: ignore[attr-defined]
        app.rq = None  # type: ignore[attr-defined]
