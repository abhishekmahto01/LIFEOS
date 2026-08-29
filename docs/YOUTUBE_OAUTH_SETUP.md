# LifeOS — YouTube OAuth 2.0 Setup Guide (Phase 5)

This guide documents how to configure official Google OAuth 2.0 credentials and the YouTube Data API v3 for the LifeOS Social Media Hub.

---

## 1. Google Cloud Console Configuration

### Step 1: Create or Select a Project
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Click on the project dropdown at the top of the page and select **New Project**.
3. Name your project (e.g., `LifeOS-Social-Hub`) and click **Create**.

### Step 2: Enable YouTube Data API v3
1. In the left navigation menu, go to **APIs & Services** > **Library**.
2. Search for **YouTube Data API v3**.
3. Click **Enable** on the YouTube Data API v3 page.

### Step 3: Configure the OAuth Consent Screen
1. In the left menu, navigate to **APIs & Services** > **OAuth consent screen**.
2. Select **External** as the User Type and click **Create**.
3. Fill in the required application details:
   - **App name**: `LifeOS`
   - **User support email**: Select your Google email address
   - **Developer contact information**: Enter your email address
4. Click **Save and Continue**.

### Step 4: Add Stage 5 Minimum Scope
1. On the **Scopes** page, click **Add or Remove Scopes**.
2. Filter or search for YouTube scopes and select **only**:
   ```text
   https://www.googleapis.com/auth/youtube.readonly
   ```
3. Click **Update** and then **Save and Continue**.

> [!IMPORTANT]
> **Stage 5 Scope Limitation**: Phase 5 connects and verifies your YouTube channel identity, title, handle, and thumbnail. It **cannot** upload or publish videos. The `https://www.googleapis.com/auth/youtube.upload` permission belongs strictly to Phase 6 and must not be requested in Phase 5.

### Step 5: Add Test Users
1. Under **Test users**, click **+ Add Users**.
2. Enter the Google email address of the account associated with your YouTube channel.
3. Click **Save and Continue**.

### Step 6: Create OAuth Client ID
1. Navigate to **APIs & Services** > **Credentials**.
2. Click **+ Create Credentials** at the top and choose **OAuth client ID**.
3. Set **Application type** to **Web application**.
4. Set **Name** to `LifeOS Web Client`.
5. Under **Authorized JavaScript origins**, add:
   - `http://localhost:5173`
   - `http://127.0.0.1:5173`
6. Under **Authorized redirect URIs**, add the exact backend callback URL:
   ```text
   http://localhost:5000/api/social-media/oauth/youtube/callback
   ```
7. Click **Create**.
8. Copy your **Client ID** and **Client Secret** into your local environment.

> [!WARNING]
> The redirect URI configured in Google Cloud Console must **exactly** match the `GOOGLE_REDIRECT_URI` setting in `backend/.env`. Any mismatch (including trailing slashes or differing ports) will cause Google to reject the request with a redirect URI mismatch error.

---

## 2. Local Environment Configuration

Add the following variables to your local `backend/.env` file using your real Google credentials:

```env
# ==============================================================================
# Google OAuth 2.0 & YouTube Data API v3 (Phase 5)
# ==============================================================================
GOOGLE_CLIENT_ID=your_google_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:5000/api/social-media/oauth/youtube/callback

# Frontend Base URL for OAuth Redirects
FRONTEND_URL=http://localhost:5173

# Database Configuration
DB_NAME=lifeos
TEST_DB_NAME=lifeos_test
```

> [!CAUTION]
> **Security Warning**: Real credentials and secret keys belong **exclusively** in your local, untracked `backend/.env` file.
> Never commit, push, or share:
> - `backend/.env`
> - Google Client Secret (`GOOGLE_CLIENT_SECRET`)
> - OAuth access tokens or refresh tokens
> - Fernet Encryption Key (`ENCRYPTION_KEY`)
> - Database passwords (`DB_PASSWORD`)
> - JWT signing secrets (`JWT_SECRET_KEY`)

---

## 3. Database Isolation

LifeOS enforces strict database isolation between development and automated testing:

* **Development Database (`lifeos`)**: Stores active application data, user accounts, and authenticated social connections.
* **Test Database (`lifeos_test`)**: Dedicated sandbox used exclusively by automated unit and integration tests.
* **Safety Rule**: The test suite validates that `TEST_DB_NAME` does not resolve to the development database (`lifeos`) and will immediately abort execution if a collision is detected.

To create the local test database in PostgreSQL:
```bash
createdb lifeos_test
```

---

## 4. Local Startup Instructions

### 1. Start the Flask Backend
```bash
# From workspace root
source venv/bin/activate
cd backend
python app.py
```
*Backend runs on `http://127.0.0.1:5000`.*

### 2. Start the React Frontend
```bash
# In a separate terminal tab from workspace root
cd frontend
npm run dev
```
*Frontend runs on `http://localhost:5173`.*

---

## 5. Manual Verification Workflow

Follow these steps to verify the end-to-end OAuth connection in your browser:

1. **Log in to LifeOS**:
   - Open `http://localhost:5173` in your browser and log in to your account.
2. **Open Connected Accounts**:
   - Navigate to the **Social Media Hub** module and select the **Connected Accounts** tab (`/social-media/accounts`).
3. **Initiate YouTube Connection**:
   - Locate the **YouTube Channel** card and click **+ Connect YouTube**.
   - You will be redirected to the official Google OAuth consent screen.
4. **Approve Read-Only Permission**:
   - Select your test Google account.
   - Review and approve the requested read-only scope (*"View your YouTube account"*).
5. **Confirm Channel Card**:
   - Upon completion, Google redirects back through the backend callback to `/social-media/accounts?status=success`.
   - The YouTube card displays:
     - **Status**: `Connected` (green badge)
     - **Channel Title**: Your YouTube channel name
     - **Handle / Channel ID**: Your channel custom URL or ID
     - **Thumbnail**: Profile image retrieved from YouTube Data API v3
6. **Test Disconnect & Reconnect**:
   - Click **Disconnect** on the YouTube card to verify that official token revocation succeeds, stored tokens are cleared, and the status changes to `Not Connected`.
   - Click **+ Connect YouTube** again to verify that reconnection safely upserts the existing record without duplicate entries.

---

## 6. Next Steps (Phase 6)

Phase 5 completes the channel authorization and token lifecycle foundation. Video uploading, resumable chunked upload pipelines, and the `https://www.googleapis.com/auth/youtube.upload` scope will be added in Phase 6.
