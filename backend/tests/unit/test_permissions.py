"""Unit tests for encryption utilities."""

import pytest
from app.core.security import (
    decrypt_value,
    encrypt_value,
    get_fernet,
)


def test_encrypt_decrypt():
    """Test that encryption and decryption are inverse operations."""
    import os
    import base64
    from unittest.mock import patch

    # Create a valid 32-byte key
    test_key = base64.b64encode(os.urandom(32)).decode()

    with patch("app.core.security.get_settings") as mock_settings:
        mock_settings.return_value.ENCRYPTION_KEY = test_key

        original = "sensitive_data_12345"
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)

        assert decrypted == original
        assert encrypted != original


def test_encrypt_different_ciphertexts():
    """Test that encrypting the same value twice produces different ciphertexts (Fernet uses random IV)."""
    import os
    import base64
    from unittest.mock import patch

    test_key = base64.b64encode(os.urandom(32)).decode()

    with patch("app.core.security.get_settings") as mock_settings:
        mock_settings.return_value.ENCRYPTION_KEY = test_key

        value = "same_value"
        cipher1 = encrypt_value(value)
        cipher2 = encrypt_value(value)

        # Fernet uses random IV, so ciphertexts should differ
        assert cipher1 != cipher2


def test_decrypt_invalid_data():
    """Test that decrypting invalid data raises an exception."""
    import os
    import base64
    from unittest.mock import patch

    test_key = base64.b64encode(os.urandom(32)).decode()

    with patch("app.core.security.get_settings") as mock_settings:
        mock_settings.return_value.ENCRYPTION_KEY = test_key

        with pytest.raises(Exception):
            decrypt_value("not_valid_encrypted_data")
