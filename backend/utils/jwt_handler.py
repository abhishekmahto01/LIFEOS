import datetime
import jwt
from config import Config

def generate_token(user_id: int, username: str, expires_in: int = None) -> str:
    """Generate a signed JWT access token for the given user."""
    if expires_in is None:
        expires_in = Config.JWT_ACCESS_TOKEN_EXPIRES

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=expires_in)
    }

    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")
    return token

def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.
    Returns payload dictionary or raises jwt.PyJWTError.
    """
    return jwt.decode(
        token,
        Config.JWT_SECRET_KEY,
        algorithms=["HS256"],
        options={"require": ["exp", "iat", "user_id"]}
    )
