import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_URL", "postgresql://test:test@localhost:5432/test_db")
os.environ.setdefault("LLM_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODk=")
os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword123")


@pytest.fixture
def app():
    with patch("app.extensions.init_redis_rq"):
        from app import create_app
        test_app = create_app()
        test_app.config["TESTING"] = True
        yield test_app


@pytest.fixture
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def app_context(app):
    with app.app_context():
        yield app
