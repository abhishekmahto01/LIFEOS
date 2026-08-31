"""
LifeOS — Instagram & Meta Graph API OAuth Connection & Token Lifecycle Service
Implements official Meta OAuth 2.0 Authorization Code flow for Instagram Professional/Creator accounts,
Meta long-lived token exchange (60-day token lifetime), Facebook Page & linked Instagram account discovery,
Fernet authenticated token encryption at rest, and idempotent account upsert into social_accounts.

Stage 6B Scope: Connect Instagram -> OAuth -> Token exchange & encryption -> Stored in social_accounts.
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


def get_instagram_authorization_url(user_id: int) -> dict:
    """
    Generate official Meta OAuth 2.0 authorization URL for Instagram connection.
    - Creates cryptographically secure random state token.
    - Stores SHA-256 hash in oauth_states table with 10-minute TTL.
    - Requests Instagram publishing, pages discovery, and profile scopes.
    - Never logs or exposes raw secrets.
    """
    if not Config.INSTAGRAM_CLIENT_ID or not Config.INSTAGRAM_CLIENT_SECRET:
        raise ValueError(
            "Instagram/Meta OAuth credentials are not configured. "
            "Please set INSTAGRAM_CLIENT_ID and INSTAGRAM_CLIENT_SECRET in your .env."
        )

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
            VALUES (%s, %s, 'INSTAGRAM', %s, %s);
        """, (state_hash, user_id, Config.INSTAGRAM_REDIRECT_URI, expires_at))
        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Meta OAuth Dialog Base URL (dynamically versioned)
    meta_dialog_url = f"https://www.facebook.com/{Config.META_GRAPH_API_VERSION}/dialog/oauth"

    scopes_str = ",".join(Config.INSTAGRAM_SCOPES) if isinstance(Config.INSTAGRAM_SCOPES, list) else str(Config.INSTAGRAM_SCOPES)

    params = {
        "client_id": Config.INSTAGRAM_CLIENT_ID,
        "redirect_uri": Config.INSTAGRAM_REDIRECT_URI,
        "response_type": "code",
        "scope": scopes_str,
        "state": raw_state
    }

    auth_url = f"{meta_dialog_url}?{urllib.parse.urlencode(params)}"
    return {
        "authorization_url": auth_url,
        "state": raw_state
    }


def handle_instagram_oauth_callback(raw_state: str, code: str = None, error: str = None) -> tuple[str, dict | None]:
    """
    Process Meta OAuth 2.0 redirect callback for Instagram.
    - Returns (result_code, data_or_none) where result_code is a safe fixed error/success code.
    - Safe error codes:
        'oauth_denied', 'invalid_state', 'state_expired', 'state_already_used',
        'redirect_uri_mismatch', 'token_exchange_failed', 'instagram_account_not_found',
        'oauth_failed'
    - On success: returns ('success', {'account_id': ..., 'username': ..., 'name': ..., 'user_id': ...})
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
            WHERE state_hash = %s AND platform IN ('INSTAGRAM', 'META')
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

        # Validate stored redirect URI matches configured INSTAGRAM_REDIRECT_URI
        if stored_redirect_uri != Config.INSTAGRAM_REDIRECT_URI:
            return "redirect_uri_mismatch", None

        # Atomically mark state as consumed
        cur.execute("UPDATE oauth_states SET consumed_at = CURRENT_TIMESTAMP WHERE id = %s;", (state_id,))
        conn.commit()

        if not code or not code.strip():
            return "oauth_denied", None

        # 2. Exchange authorization code for short-lived access token
        token_endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/oauth/access_token"
        token_params = {
            "client_id": Config.INSTAGRAM_CLIENT_ID,
            "client_secret": Config.INSTAGRAM_CLIENT_SECRET,
            "redirect_uri": Config.INSTAGRAM_REDIRECT_URI,
            "code": code.strip()
        }

        try:
            token_resp = requests.get(token_endpoint, params=token_params, timeout=15)
        except Exception:
            return "token_exchange_failed", None

        if token_resp.status_code != 200:
            return "token_exchange_failed", None

        try:
            tokens = token_resp.json()
        except Exception:
            return "token_exchange_failed", None

        short_lived_access_token = tokens.get("access_token")
        if not short_lived_access_token or not short_lived_access_token.strip():
            return "token_exchange_failed", None

        # Default short-lived expiry (~1-2 hours)
        expires_in = int(tokens.get("expires_in", 7200))
        final_access_token = short_lived_access_token

        # 3. Exchange for 60-day Long-Lived Token (Meta Best Practice)
        long_lived_params = {
            "grant_type": "fb_exchange_token",
            "client_id": Config.INSTAGRAM_CLIENT_ID,
            "client_secret": Config.INSTAGRAM_CLIENT_SECRET,
            "fb_exchange_token": short_lived_access_token
        }
        try:
            long_resp = requests.get(token_endpoint, params=long_lived_params, timeout=15)
            if long_resp.status_code == 200:
                long_data = long_resp.json()
                if long_data.get("access_token"):
                    final_access_token = long_data["access_token"]
                    expires_in = int(long_data.get("expires_in", 5184000))  # 60 days default
        except Exception:
            pass  # Non-fatal: keep short-lived token if exchange endpoint fails

        token_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)

        # 4. Discover connected Facebook Pages and linked Instagram Professional Account
        headers = {"Authorization": f"Bearer {final_access_token}"}
        accounts_endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/me/accounts"
        accounts_params = {
            "fields": "id,name,access_token,instagram_business_account{id,username,name,profile_picture_url}"
        }

        instagram_account = None
        fb_page_metadata = {}

        try:
            accounts_resp = requests.get(accounts_endpoint, headers=headers, params=accounts_params, timeout=15)
            if accounts_resp.status_code == 200:
                accounts_data = accounts_resp.json()
                pages = accounts_data.get("data", [])

                for page in pages:
                    ig_biz = page.get("instagram_business_account")
                    if ig_biz and ig_biz.get("id"):
                        instagram_account = {
                            "id": ig_biz.get("id"),
                            "username": ig_biz.get("username", ""),
                            "name": ig_biz.get("name") or page.get("name", "Instagram Account"),
                            "profile_picture_url": ig_biz.get("profile_picture_url", "")
                        }
                        fb_page_metadata = {
                            "facebook_page_id": page.get("id"),
                            "facebook_page_name": page.get("name", "")
                        }
                        break
        except Exception:
            pass

        # Fallback: Check direct /me endpoint if user connected via direct Instagram endpoint
        if not instagram_account:
            try:
                me_endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/me"
                me_params = {"fields": "id,username,name,profile_picture_url,account_type"}
                me_resp = requests.get(me_endpoint, headers=headers, params=me_params, timeout=15)
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    if me_data.get("username") or me_data.get("id"):
                        instagram_account = {
                            "id": me_data.get("id"),
                            "username": me_data.get("username", ""),
                            "name": me_data.get("name", me_data.get("username", "Instagram Account")),
                            "profile_picture_url": me_data.get("profile_picture_url", "")
                        }
            except Exception:
                pass

        if not instagram_account or not instagram_account.get("id"):
            return "instagram_account_not_found", None

        ig_account_id = str(instagram_account["id"])
        ig_username = instagram_account.get("username") or ig_account_id
        ig_name = instagram_account.get("name") or ig_username
        profile_img = instagram_account.get("profile_picture_url") or ""

        # 5. Encrypt access token at rest
        encrypted_access = encrypt_token(final_access_token)

        # 6. Upsert into social_accounts table
        granted_scopes = ",".join(Config.INSTAGRAM_SCOPES) if isinstance(Config.INSTAGRAM_SCOPES, list) else str(Config.INSTAGRAM_SCOPES)
        metadata = {
            "instagram_user_id": ig_account_id,
            "connected_at_utc": str(now_utc),
            **fb_page_metadata
        }
        metadata_json = json.dumps(metadata)

        cur.execute("""
            INSERT INTO social_accounts (
                user_id, platform, platform_account_id, account_name, account_username,
                profile_image_url, encrypted_access_token, encrypted_refresh_token,
                token_expires_at, raw_scopes, connection_status, metadata, updated_at
            )
            VALUES (
                %s, 'INSTAGRAM', %s, %s, %s,
                %s, %s, NULL,
                %s, %s, 'ACTIVE', %s::jsonb, CURRENT_TIMESTAMP
            )
            ON CONFLICT (user_id, platform, platform_account_id) DO UPDATE SET
                account_name = EXCLUDED.account_name,
                account_username = EXCLUDED.account_username,
                profile_image_url = EXCLUDED.profile_image_url,
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                token_expires_at = EXCLUDED.token_expires_at,
                raw_scopes = EXCLUDED.raw_scopes,
                connection_status = 'ACTIVE',
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
        """, (
            user_id, ig_account_id, ig_name, ig_username,
            profile_img, encrypted_access,
            token_expires_at, granted_scopes, metadata_json
        ))

        account_id = cur.fetchone()[0]
        conn.commit()

        return "success", {
            "account_id": account_id,
            "username": ig_username,
            "name": ig_name,
            "account_id_str": ig_account_id,
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


def is_instagram_token_expired(expires_at: datetime.datetime | None, threshold_minutes: int = 5) -> bool:
    """
    Check if a token expiry timestamp is expired or within the given threshold buffer.
    If expires_at is None, returns True (missing expiry requires validation/renewal).
    """
    if expires_at is None:
        return True
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    return expires_at <= (now_utc + datetime.timedelta(minutes=threshold_minutes))


def mark_instagram_account_status(account_id: int, user_id: int, status: str, error_msg: str | None = None) -> bool:
    """
    Safely update connection_status for a user's Instagram account.
    Allowed statuses: 'ACTIVE', 'EXPIRED', 'REVOKED', 'DISCONNECTED', 'ERROR'.
    """
    valid_statuses = {"ACTIVE", "EXPIRED", "REVOKED", "DISCONNECTED", "ERROR"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid connection_status '{status}'. Allowed: {valid_statuses}")

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        if error_msg:
            cur.execute("""
                UPDATE social_accounts
                SET connection_status = %s,
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{last_error}',
                        %s::jsonb
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s AND platform = 'INSTAGRAM';
            """, (status, json.dumps(error_msg), account_id, user_id))
        else:
            cur.execute("""
                UPDATE social_accounts
                SET connection_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s AND platform = 'INSTAGRAM';
            """, (status, account_id, user_id))
        updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def mark_instagram_account_expired(account_id: int, user_id: int) -> bool:
    """Mark an Instagram account as EXPIRED requiring reconnect."""
    return mark_instagram_account_status(account_id=account_id, user_id=user_id, status="EXPIRED")


def mark_instagram_account_error(account_id: int, user_id: int, error_message: str | None = None) -> bool:
    """Mark an Instagram account as ERROR requiring attention or reconnect."""
    return mark_instagram_account_status(account_id=account_id, user_id=user_id, status="ERROR", error_msg=error_message)


def mark_instagram_account_revoked(account_id: int, user_id: int, error_message: str | None = None) -> bool:
    """Mark an Instagram account as REVOKED requiring reconnect."""
    return mark_instagram_account_status(account_id=account_id, user_id=user_id, status="REVOKED", error_msg=error_message)


def refresh_instagram_access_token(account_id: int, user_id: int) -> tuple[bool, str | None, str | None]:
    """
    Renew a Meta/Instagram Long-Lived User Access Token using Meta Graph API (grant_type=fb_exchange_token).
    - Enforces strict user ownership.
    - Decrypts current token internally.
    - Encrypts newly renewed token with Fernet before database storage.
    - Updates token_expires_at (60 days default) and sets connection_status = 'ACTIVE'.
    - Marks EXPIRED or ERROR only on permanent OAuth rejection (code 190 / invalid grant).
    - Preserves existing database state on transient network / 5xx server failures.
    - Never logs or exposes raw tokens.
    Returns (success, decrypted_new_token_or_none, error_or_none).
    """
    if not user_id or not account_id:
        return False, None, "User ID and Account ID are required for token renewal."

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, encrypted_access_token, token_expires_at, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s AND platform = 'INSTAGRAM';
        """, (account_id, user_id))
        row = cur.fetchone()

        if not row:
            return False, None, "Instagram account not found or access denied."

        aid, enc_access, expires_at, status = row

        if status == "DISCONNECTED":
            return False, None, "Instagram account is disconnected. Please reconnect."

        if not enc_access:
            mark_instagram_account_error(account_id, user_id, "No access token found for account")
            return False, None, "No access token stored for this account. Please reconnect."

        try:
            current_access_token = decrypt_token(enc_access)
        except Exception:
            mark_instagram_account_error(account_id, user_id, "Corrupt encrypted access token")
            return False, None, "Corrupt or malformed access token. Please reconnect your Instagram account."

        # Exchange current long-lived token for a refreshed long-lived token
        token_endpoint = f"{Config.META_GRAPH_API_BASE_URL}/{Config.META_GRAPH_API_VERSION}/oauth/access_token"
        refresh_params = {
            "grant_type": "fb_exchange_token",
            "client_id": Config.INSTAGRAM_CLIENT_ID,
            "client_secret": Config.INSTAGRAM_CLIENT_SECRET,
            "fb_exchange_token": current_access_token
        }

        try:
            resp = requests.get(token_endpoint, params=refresh_params, timeout=15)
        except Exception:
            # Transient network/connection error — do NOT corrupt or expire database status
            return False, None, "Temporary failure connecting to Meta Graph API. Please try again."

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                return False, None, "Invalid JSON response received from Meta Graph API."

            new_access_token = data.get("access_token")
            if not new_access_token or not new_access_token.strip():
                mark_instagram_account_error(account_id, user_id, "Meta response missing access token")
                return False, None, "Meta token renewal response missing access token."

            expires_in = int(data.get("expires_in", 5184000))  # Default 60 days
            new_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
            new_enc_access = encrypt_token(new_access_token)

            cur.execute("""
                UPDATE social_accounts
                SET encrypted_access_token = %s,
                    token_expires_at = %s,
                    connection_status = 'ACTIVE',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s;
            """, (new_enc_access, new_expires_at, account_id, user_id))
            conn.commit()

            return True, new_access_token, None

        # Handle non-200 responses
        if resp.status_code >= 500:
            # Transient 5xx server error on Meta's side — preserve active connection
            return False, None, f"Temporary Meta server error (HTTP {resp.status_code}). Please try again."

        # Parse client/OAuth error (HTTP 400/401)
        err_data = {}
        try:
            err_data = resp.json().get("error", {})
        except Exception:
            pass

        err_code = err_data.get("code")
        err_type = err_data.get("type", "")
        err_msg = err_data.get("message", "OAuth error")

        # Code 190 is Meta's canonical Invalid OAuth Access Token (expired, revoked, password changed)
        if err_code == 190 or "OAuthException" in err_type or "expired" in err_msg.lower() or "revoked" in err_msg.lower() or resp.status_code in (400, 401):
            mark_instagram_account_expired(account_id, user_id)
            return False, None, "Instagram authorization has expired or been revoked. Please reconnect."

        mark_instagram_account_error(account_id, user_id, f"Meta token renewal failed (HTTP {resp.status_code})")
        return False, None, "Failed to renew Instagram authorization. Please reconnect."

    except Exception as e:
        if conn:
            conn.rollback()
        return False, None, f"Unexpected error renewing Instagram token: {str(e)}"
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_valid_instagram_access_token(account_id: int, user_id: int, auto_refresh: bool = True) -> tuple[bool, str | None, str | None]:
    """
    Retrieve and decrypt active Instagram access token for the given account.
    - Enforces strict user ownership check.
    - Inspects token_expires_at and automatically renews long-lived token when expired or near expiry.
    - Handles malformed/corrupted encrypted tokens safely by setting ERROR state.
    - Returns (success, decrypted_access_token_or_none, error_or_none).
    """
    if not user_id or not account_id:
        return False, None, "User ID and Account ID are required."

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, encrypted_access_token, token_expires_at, connection_status
            FROM social_accounts
            WHERE id = %s AND user_id = %s AND platform = 'INSTAGRAM';
        """, (account_id, user_id))
        row = cur.fetchone()

        if not row:
            return False, None, "Instagram account not found or access denied."

        aid, enc_access, expires_at, status = row

        if status == "DISCONNECTED":
            return False, None, "Instagram account is disconnected. Please reconnect."

        if not enc_access:
            mark_instagram_account_error(account_id, user_id, "Missing encrypted token")
            return False, None, "No access token found for this account. Please reconnect."

        try:
            raw_token = decrypt_token(enc_access)
        except Exception:
            mark_instagram_account_error(account_id, user_id, "Corrupt encrypted token")
            return False, None, "Corrupt or malformed token. Please reconnect your Instagram account."

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

        is_expired = (expires_at is not None) and (expires_at < now_utc)
        # Check if nearing expiration (within 2 days)
        is_near_expiry = (expires_at is not None) and (expires_at - now_utc < datetime.timedelta(days=2))

        if not is_expired and not is_near_expiry:
            if status != "ACTIVE":
                mark_instagram_account_status(account_id, user_id, "ACTIVE")
            return True, raw_token, None

        # Token is expired or nearing expiry
        if auto_refresh:
            success, refreshed_token, err = refresh_instagram_access_token(account_id=aid, user_id=user_id)
            if success and refreshed_token:
                return True, refreshed_token, None

            # If renewal failed, check if token is still strictly in its valid window
            if not is_expired and raw_token:
                return True, raw_token, None

            # Token has expired and could not be renewed
            return False, None, err or "Instagram access token has expired. Please reconnect."
        else:
            if is_expired:
                mark_instagram_account_expired(account_id, user_id)
                return False, None, "Instagram access token has expired. Please reconnect."
            return True, raw_token, None

    except Exception as e:
        return False, None, f"Failed to retrieve Instagram access token: {str(e)}"
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
