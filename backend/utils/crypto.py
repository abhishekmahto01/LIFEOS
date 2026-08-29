from cryptography.fernet import Fernet, InvalidToken
from config import Config

def _get_fernet_cipher(override_key: str = None) -> Fernet:
    """
    Validate and return a Fernet cipher instance using the dedicated ENCRYPTION_KEY.
    Requires a valid 32-byte url-safe base64 key.
    Never derives keys from SECRET_KEY or arbitrary strings.
    Never logs or exposes the key.
    """
    key_str = override_key if override_key is not None else Config.ENCRYPTION_KEY
    
    if not key_str or not isinstance(key_str, str) or len(key_str.strip()) == 0:
        raise ValueError(
            "ENCRYPTION_KEY is missing. Please configure a valid Fernet encryption key in your .env configuration."
        )
    
    try:
        key_bytes = key_str.strip().encode("utf-8")
        return Fernet(key_bytes)
    except Exception:
        raise ValueError(
            "ENCRYPTION_KEY is invalid. Expected a 32-byte url-safe base64 Fernet key."
        )

def encrypt_token(token: str, key: str = None) -> str:
    """
    Encrypt an OAuth access or refresh token using Fernet authenticated encryption.
    Never stores or logs raw OAuth tokens.
    """
    if not token or not isinstance(token, str):
        return ""
    
    f = _get_fernet_cipher(override_key=key)
    encrypted_bytes = f.encrypt(token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")

def decrypt_token(encrypted_token: str, key: str = None) -> str:
    """
    Decrypt an encrypted OAuth token back into plaintext for official API calls.
    Never logs decrypted tokens or keys.
    """
    if not encrypted_token or not isinstance(encrypted_token, str):
        return ""
    
    f = _get_fernet_cipher(override_key=key)
    try:
        decrypted_bytes = f.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        raise ValueError("Failed to decrypt OAuth token. Invalid encryption key or corrupted data.")
