import os
import pytest
from unittest.mock import patch

os.environ["LLM_ENCRYPTION_KEY"] = ""


class TestEncryptDecryptRoundtrip:

    def test_encrypt_then_decrypt_returns_original(self):
        os.environ["LLM_ENCRYPTION_KEY"] = ""
        from cryptography.fernet import Fernet
        os.environ["LLM_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        from app.services.crypto_service import encrypt_api_key, decrypt_api_key
        original = "sk-test-api-key-12345"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string_returns_empty(self):
        from app.services.crypto_service import encrypt_api_key
        assert encrypt_api_key("") == ""

    def test_decrypt_empty_string_returns_none(self):
        from app.services.crypto_service import decrypt_api_key
        assert decrypt_api_key("") is None

    def test_decrypt_invalid_token_returns_none(self):
        from app.services.crypto_service import decrypt_api_key
        result = decrypt_api_key("totally-invalid-encrypted-data")
        assert result is None

    def test_encrypt_produces_different_output_each_time(self):
        from app.services.crypto_service import encrypt_api_key
        original = "sk-test-api-key-12345"
        encrypted_1 = encrypt_api_key(original)
        encrypted_2 = encrypt_api_key(original)
        assert encrypted_1 != encrypted_2


class TestMaskApiKey:

    def test_mask_standard_key(self):
        from app.services.crypto_service import mask_api_key
        result = mask_api_key("sk-abcdef123456")
        assert result.endswith("3456")
        assert result.startswith("•")

    def test_mask_empty_key(self):
        from app.services.crypto_service import mask_api_key
        assert mask_api_key("") == ""

    def test_mask_short_key(self):
        from app.services.crypto_service import mask_api_key
        result = mask_api_key("abc")
        assert result == "•••"

    def test_mask_custom_visible_chars(self):
        from app.services.crypto_service import mask_api_key
        result = mask_api_key("sk-abcdef123456", visible_chars=6)
        assert result.endswith("123456")


class TestIsKeyValid:

    def test_valid_encrypted_key(self):
        from app.services.crypto_service import encrypt_api_key, is_key_valid
        encrypted = encrypt_api_key("valid-key")
        assert is_key_valid(encrypted) is True

    def test_invalid_encrypted_key(self):
        from app.services.crypto_service import is_key_valid
        assert is_key_valid("garbage") is False
