"""
LifeOS — YouTube OAuth 2.0 Connection & Token Lifecycle Service
Implements official Google OAuth 2.0 Authorization Code flow,
YouTube Data API v3 channel retrieval, Fernet authenticated token encryption at rest,
automatic access token refreshing with refresh-token rotation support,
and idempotent account disconnection with POST-body token revocation.

Stage 5 Scope: Strictly read-only ('https://www.googleapis.com/auth/youtube.readonly').
"""

import json
import secrets
import hashlib
import datetime
import urllib.parse
import requests

from config import Config
from database.db import get_connection
from utils.crypto import encrypt_token, decrypt_token

YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
YOUTUBE_CHANNELS_API = "https://www.googleapis.com/youtube/v3/channels"

def get_youtube_authorization_url(user_id: int) -> dict:
    """
    Generate official Google OAuth 2.0 authorization URL.
    - Creates cryptographically secure random state token.
    - Stores SHA-256 hash in oauth_states table with 10-minute TTL.
    - Requests read-only scope for Stage 5.
    - Never logs or exposes raw secrets.
    """
    if not Config.GOOGLE_CLIENT_ID or not Config.GOOGLE_CLIENT_SECRET:
        raise ValueError("Google OAuth credentials are not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env.")

    raw_state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO oauth_states (state_hash, user_id, platform, redirect_uri, expires_at)
            VALUES (%s, %s, 'YOUTUBE', %s, %s);
        """, (state_hash, user_id, Config.GOOGLE_REDIRECT_URI, expires_at))
        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    params = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": Config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_READONLY_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": raw_state,
        "prompt": "consent"
    }

    auth_url = f"{GOOGLE_AUTH_BASE}?{urllib.parse.urlencode(params)}"
    return {
        "authorization_url": auth_url,
        "state": raw_state
    }

def handle_youtube_oauth_callback(raw_state: str, code: str = None, error: str = None) -> tuple[str, dict | None]:
    """
    Process Google OAuth 2.0 redirect callback.
    - Returns (result_code, data_or_none) where result_code is a safe fixed error/success code.
    - Safe error codes:
        'oauth_denied', 'invalid_state', 'state_expired', 'state_already_used',
        'redirect_uri_mismatch', 'token_exchange_failed', 'scope_not_granted',
        'channel_not_found', 'oauth_failed'
    - On success: returns ('success', {'channel_title': ..., 'channel_id': ..., 'account_id': ...})
    """
    if error or not raw_state or not isinstance(raw_state, str):
        if error:
            return "oauth_denied", None
        return "invalid_state", None

    state_hash = hashlib.sha256(raw_state.strip().encode("utf-8")).hexdigest()

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Validate and atomically consume single-use state
        cur.execute("""
            SELECT id, user_id, redirect_uri, expires_at, consumed_at
            FROM oauth_states
            WHERE state_hash = %s AND platform = 'YOUTUBE'
            FOR UPDATE;
        """, (state_hash,))
        state_row = cur.fetchone()

        if not state_row:
            return "invalid_state", None

        state_id, user_id, stored_redirect_uri, expires_at, consumed_at = state_row

        if consumed_at is not None:
            return "state_already_used", None

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at < now_utc:
            return "state_expired", None

        # Validate stored redirect URI matches configured GOOGLE_REDIRECT_URI
        if stored_redirect_uri != Config.GOOGLE_REDIRECT_URI:
            return "redirect_uri_mismatch", None

        # Atomically mark state as consumed
        cur.execute("UPDATE oauth_states SET consumed_at = CURRENT_TIMESTAMP WHERE id = %s;", (state_id,))
        conn.commit()

        if not code or not code.strip():
            return "oauth_denied", None

        # 2. Exchange authorization code for tokens
        token_payload = {
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "code": code.strip(),
            "grant_type": "authorization_code",
            "redirect_uri": Config.GOOGLE_REDIRECT_URI
        }

        try:
            token_resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data=token_payload, timeout=15)
        except Exception:
            return "token_exchange_failed", None

        if token_resp.status_code != 200:
            return "token_exchange_failed", None

        try:
            tokens = token_resp.json()
        except Exception:
            return "token_exchange_failed", None

        raw_access_token = tokens.get("access_token")
        raw_refresh_token = tokens.get("refresh_token")
        expires_in = int(tokens.get("expires_in", 3600))
        granted_scopes = tokens.get("scope", "")

        if not raw_access_token or not raw_access_token.strip():
            return "token_exchange_failed", None

        # Verify required YouTube scope was granted
        if YOUTUBE_READONLY_SCOPE not in granted_scopes:
            return "scope_not_granted", None

        token_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)

        # 3. Retrieve YouTube Channel details
        headers = {"Authorization": f"Bearer {raw_access_token}"}
        params = {"part": "snippet,contentDetails", "mine": "true"}

        try:
            yt_resp = requests.get(YOUTUBE_CHANNELS_API, headers=headers, params=params, timeout=15)
        except Exception:
            return "channel_not_found", None

        if yt_resp.status_code != 200:
            return "channel_not_found", None

        try:
            yt_data = yt_resp.json()
        except Exception:
            return "channel_not_found", None

        items = yt_data.get("items", [])
        if not items:
            return "channel_not_found", None

        channel_item = items[0]
        channel_id = channel_item.get("id")
        if not channel_id or not channel_id.strip():
            return "channel_not_found", None

        snippet = channel_item.get("snippet", {})
        channel_title = snippet.get("title", "YouTube Channel")
        channel_username = snippet.get("customUrl", "")
        thumbnails = snippet.get("thumbnails", {})
        profile_img = thumbnails.get("default", {}).get("url") or thumbnails.get("medium", {}).get("url", "")

        # 4. Encrypt tokens at rest
        encrypted_access = encrypt_token(raw_access_token)
        encrypted_refresh = encrypt_token(raw_refresh_token) if raw_refresh_token else None

        # 5. Upsert into social_accounts (preserving existing refresh token if not returned)
        metadata_json = json.dumps({
            "custom_url": channel_username,
            "connected_at_utc": str(now_utc)
        })

        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                profile_image_url, encrypted_access_token, encrypted_refresh_token,
                token_expires_at, raw_scopes, connection_status, metadata, updated_at
            )
            VALUES (
                %s, 'YOUTUBE', %s, %s, %s,
                %s, %s, %s,
                %s, %s, 'ACTIVE', %s::jsonb, CURRENT_TIMESTAMP
            )
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                account_name = EXCLUDED.account_name,
                account_username = EXCLUDED.account_username,
                profile_image_url = EXCLUDED.profile_image_url,
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                encrypted_refresh_token = COALESCE(EXCLUDED.encrypted_refresh_token, social_accounts.encrypted_refresh_token),
                token_expires_at = EXCLUDED.token_expires_at,
                raw_scopes = EXCLUDED.raw_scopes,
                connection_status = 'ACTIVE',
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
        """, (
            user_id, channel_id, channel_title, channel_username,
            profile_img, encrypted_access, encrypted_refresh,
            token_expires_at, granted_scopes, metadata_json
        ))

        account_id = cur.fetchone()[0]
        conn.commit()

        return "success", {
            "account_id": account_id,
            "channel_title": channel_title,
            "channel_id": channel_id,
            "user_id": user_id
        }
    except Exception:
        if conn:
            conn.rollback()
        return "oauth_failed", None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def get_user_social_accounts(user_id: int) -> list:
    """
    Fetch all connected social accounts for the authenticated user.
    Returns ONLY safe public metadata (IDs, names, status, expires_at).
    NEVER exposes encrypted tokens or secret fields.
    """
    if not user_id:
        return []

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                id, platform, platform_account_id, account_name, account_username,
                profile_image_url, connection_status, token_expires_at, created_at, updated_at
            FROM social_accounts
            WHERE user_id = %s
            ORDER BY id ASC;
        """, (user_id,))
        rows = cur.fetchall()

        accounts = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for r in rows:
            aid, plat, paid, aname, auser, pimg, status, expires_at, created_at, updated_at = r

            computed_status = status
            if status == "ACTIVE" and expires_at and expires_at < now_utc:
                computed_status = "EXPIRED"

            accounts.append({
                "id": aid,
                "platform": plat,
                "platform_account_id": paid,
                "account_name": aname,
                "account_username": auser,
                "profile_image_url": pimg,
                "connection_status": computed_status,
                "token_expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None
            })
        return accounts
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def disconnect_social_account(account_id: int, user_id: int) -> dict:
    """
    Disconnect a social account:
    - Verifies user ownership strictly.
    - Sends token revocation in POST body to Google revoke endpoint.
    - Scrubs stored tokens and marks connection_status = 'DISCONNECTED'.
    - Idempotent: repeated disconnect calls return success.
    - Prevents cross-user disconnection.
    """
    if not user_id:
        return {"success": False, "message": "User ID is required.", "status_code": 401}

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, platform, encrypted_access_token, encrypted_refresh_token, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s;
        """, (account_id, user_id))
        row = cur.fetchone()

        if not row:
            return {"success": False, "message": "Social account not found or access denied.", "status_code": 404}

        aid, platform, enc_access, enc_refresh, current_status = row

        # If already disconnected, return idempotent success
        if current_status == "DISCONNECTED" and not enc_access and not enc_refresh:
            return {"success": True, "message": "Account is already disconnected.", "status_code": 200}

        # Attempt Google token revocation using POST body
        token_to_revoke = None
        if enc_refresh:
            try:
                token_to_revoke = decrypt_token(enc_refresh)
            except Exception:
                pass
        elif enc_access:
            try:
                token_to_revoke = decrypt_token(enc_access)
            except Exception:
                pass

        if token_to_revoke and platform == "YOUTUBE":
            try:
                requests.post(
                    GOOGLE_REVOKE_ENDPOINT,
                    data={"token": token_to_revoke},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=5
                )
            except Exception:
                pass  # Suppress network exceptions and proceed with local scrub

        # Scrub database record
        cur.execute("""
            UPDATE social_accounts
            SET connection_status = 'DISCONNECTED',
                encrypted_access_token = NULL,
                encrypted_refresh_token = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s;
        """, (account_id, user_id))

        conn.commit()
        return {"success": True, "message": "Account disconnected successfully.", "status_code": 200}
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def get_valid_youtube_access_token(account_id: int, user_id: int) -> str:
    """
    Retrieve or automatically refresh active YouTube access token for API publishing.
    - user_id is MANDATORY; enforces ownership check.
    - Decrypts refresh token if access token is expired or token_expires_at is missing.
    - Updates encrypted access token in social_accounts.
    - Handles refresh-token rotation if Google returns a new refresh token.
    - Marks EXPIRED only for permanent invalid_grant errors; preserves ACTIVE on transient 5xx errors.
    - Never logs or exposes decrypted tokens.
    """
    if not user_id:
        raise ValueError("User ID is required to retrieve YouTube access token.")

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT encrypted_access_token, encrypted_refresh_token, token_expires_at, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s AND platform = 'YOUTUBE';
        """, (account_id, user_id))
        row = cur.fetchone()

        if not row:
            raise ValueError("YouTube account not found or access denied.")

        enc_access, enc_refresh, expires_at, status = row

        if status != "ACTIVE":
            raise ValueError(f"YouTube account connection is {status}. Please reconnect.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        # Treat missing token_expires_at as requiring refresh
        needs_refresh = (not enc_access) or (expires_at is None) or (expires_at - now_utc < datetime.timedelta(minutes=5))

        if not needs_refresh and enc_access:
            return decrypt_token(enc_access)

        # Perform token refresh
        if not enc_refresh:
            raise ValueError("No refresh token available. Please reconnect your YouTube account.")

        refresh_token = decrypt_token(enc_refresh)
        refresh_payload = {
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        try:
            resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data=refresh_payload, timeout=15)
        except Exception:
            raise ValueError("Temporary error connecting to Google token endpoint. Please try again.")

        if resp.status_code != 200:
            err_data = {}
            try:
                err_data = resp.json()
            except Exception:
                pass
            err_code = err_data.get("error", "")

            # Permanent invalid_grant marks account EXPIRED
            if resp.status_code in (400, 401) and err_code in ("invalid_grant", "unauthorized_client"):
                cur.execute("""
                    UPDATE social_accounts
                    SET connection_status = 'EXPIRED',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s;
                """, (account_id, user_id))
                conn.commit()
                raise ValueError("YouTube authorization has expired or been revoked. Account marked EXPIRED. Please reconnect.")

            # Transient 5xx or unknown errors do NOT mark expired
            raise ValueError(f"Temporary failure refreshing YouTube token (HTTP {resp.status_code}).")

        data = resp.json()
        new_access = data.get("access_token")
        if not new_access or not new_access.strip():
            raise ValueError("Google token refresh response missing access token.")

        new_expires_in = int(data.get("expires_in", 3600))
        new_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=new_expires_in)
        new_enc_access = encrypt_token(new_access)

        # Handle refresh-token rotation if Google returns a new refresh token
        new_refresh = data.get("refresh_token")
        if new_refresh and new_refresh.strip():
            new_enc_refresh = encrypt_token(new_refresh)
            cur.execute("""
                UPDATE social_accounts
                SET encrypted_access_token = %s,
                    encrypted_refresh_token = %s,
                    token_expires_at = %s,
                    connection_status = 'ACTIVE',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s;
            """, (new_enc_access, new_enc_refresh, new_expires_at, account_id, user_id))
        else:
            cur.execute("""
                UPDATE social_accounts
                SET encrypted_access_token = %s,
                    token_expires_at = %s,
                    connection_status = 'ACTIVE',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s;
            """, (new_enc_access, new_expires_at, account_id, user_id))

        conn.commit()
        return new_access
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
