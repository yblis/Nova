import json
import os
import tempfile
import pytest
from unittest.mock import patch


@pytest.fixture
def provider_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "providers.json")


@pytest.fixture
def manager(provider_data_dir):
    os.environ["LLM_ENCRYPTION_KEY"] = ""
    from cryptography.fernet import Fernet
    os.environ["LLM_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    from app.services.provider_manager import ProviderManager
    return ProviderManager(data_path=provider_data_dir)


class TestProviderManagerInit:

    def test_creates_data_file_with_default_ollama(self, manager, provider_data_dir):
        assert os.path.exists(provider_data_dir)
        providers = manager.get_providers()
        assert len(providers) >= 1
        ollama_providers = [p for p in providers if p.get("type") == "ollama"]
        assert len(ollama_providers) >= 1

    def test_default_ollama_exists(self, manager):
        providers = manager.get_providers()
        ollama_types = [p["type"] for p in providers]
        assert "ollama" in ollama_types


class TestProviderCRUD:

    def test_add_provider(self, manager):
        result = manager.add_provider(
            name="Test OpenAI",
            provider_type="openai",
            api_key="sk-test-key-12345"
        )
        assert result is not None
        assert result["name"] == "Test OpenAI"
        assert result["type"] == "openai"
        assert "api_key_encrypted" not in result or result.get("api_key_encrypted") == ""

    def test_get_provider_without_key(self, manager):
        added = manager.add_provider(
            name="Test Anthropic",
            provider_type="anthropic",
            api_key="sk-ant-test-key"
        )
        provider = manager.get_provider(added["id"], include_api_key=False)
        assert provider is not None
        assert provider["name"] == "Test Anthropic"

    def test_get_provider_with_key(self, manager):
        added = manager.add_provider(
            name="Test Gemini",
            provider_type="gemini",
            api_key="AIza-test-key"
        )
        provider = manager.get_provider(added["id"], include_api_key=True)
        assert provider is not None
        assert provider.get("api_key") == "AIza-test-key"

    def test_update_provider_name(self, manager):
        added = manager.add_provider(
            name="Original Name",
            provider_type="openai",
            api_key="sk-test"
        )
        manager.update_provider(added["id"], name="Updated Name")
        provider = manager.get_provider(added["id"])
        assert provider["name"] == "Updated Name"

    def test_delete_provider(self, manager):
        added = manager.add_provider(
            name="To Delete",
            provider_type="openai",
            api_key="sk-delete"
        )
        result = manager.delete_provider(added["id"])
        assert result is True
        assert manager.get_provider(added["id"]) is None

    def test_delete_nonexistent_provider(self, manager):
        result = manager.delete_provider("nonexistent-id")
        assert result is False


class TestProviderPersistence:

    def test_data_persists_across_instances(self, provider_data_dir):
        os.environ["LLM_ENCRYPTION_KEY"] = ""
        from cryptography.fernet import Fernet
        os.environ["LLM_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        from app.services.provider_manager import ProviderManager

        manager1 = ProviderManager(data_path=provider_data_dir)
        manager1.add_provider(
            name="Persistent Provider",
            provider_type="openai",
            api_key="sk-persist"
        )

        manager2 = ProviderManager(data_path=provider_data_dir)
        providers = manager2.get_providers()
        names = [p["name"] for p in providers]
        assert "Persistent Provider" in names

    def test_data_file_exists_after_save(self, manager, provider_data_dir):
        manager.add_provider(
            name="Trigger Save",
            provider_type="openai",
            api_key="sk-save"
        )
        assert os.path.exists(provider_data_dir)


class TestActiveProvider:

    def test_set_active_provider(self, manager):
        added = manager.add_provider(
            name="New Active",
            provider_type="openai",
            api_key="sk-active"
        )
        result = manager.set_active_provider(added["id"])
        assert result is True

    def test_set_nonexistent_active_provider(self, manager):
        result = manager.set_active_provider("nonexistent-id")
        assert result is False
