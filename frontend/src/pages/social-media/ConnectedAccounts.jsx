import { useState, useEffect } from "react";
import {
  Lock,
  CheckCircle2,
  AlertCircle,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

const OAUTH_ERROR_MESSAGES = {
  oauth_denied: "Google OAuth authorization was cancelled or denied.",
  invalid_state: "Invalid or unrecognized authorization session.",
  state_expired: "Authorization session expired. Please click Connect to try again.",
  state_already_used: "This authorization session has already been used.",
  redirect_uri_mismatch: "OAuth redirect URI configuration mismatch.",
  token_exchange_failed: "Failed to exchange authorization code with Google.",
  scope_not_granted: "Required YouTube read-only permission was not granted.",
  channel_not_found: "No YouTube channel found for this Google account. Please create a YouTube channel on youtube.com first.",
  oauth_failed: "An unexpected error occurred while connecting your YouTube channel.",
};

export function ConnectedAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState(null); // { type: 'success' | 'error', message: string }
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    // 1. Process OAuth callback query parameters from URL
    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    const platform = params.get("platform");
    const channel = params.get("channel");
    const errorCode = params.get("code");

    if (status === "success") {
      const channelDisplay = channel ? `: ${channel}` : "";
      setBanner({
        type: "success",
        message: `Successfully connected ${platform ? platform.toUpperCase() : "YouTube"} channel${channelDisplay}!`,
      });
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (status === "error") {
      const errorMsg = OAUTH_ERROR_MESSAGES[errorCode] || "Failed to complete YouTube OAuth connection.";
      setBanner({
        type: "error",
        message: errorMsg,
      });
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    try {
      setLoading(true);
      const res = await socialMediaService.getAccounts();
      if (res.success) {
        setAccounts(res.accounts || []);
      } else {
        setBanner({
          type: "error",
          message: res.error || "Failed to retrieve connected social accounts.",
        });
      }
    } catch (e) {
      console.error("Error fetching accounts:", e);
      setBanner({
        type: "error",
        message: "Failed to connect to backend server to load accounts.",
      });
    } finally {
      setLoading(false);
    }
  };

  const ytAccount = accounts.find(
    (a) => a.platform?.toUpperCase() === "YOUTUBE"
  );

  const handleConnectYouTube = async () => {
    try {
      setActionLoading(true);
      setBanner(null);
      const res = await socialMediaService.getYouTubeConnectUrl();
      if (res.success && res.authorization_url) {
        window.location.href = res.authorization_url;
      } else {
        setBanner({
          type: "error",
          message: res.error || "Failed to generate Google OAuth authorization URL.",
        });
      }
    } catch (err) {
      const errMsg = err.response?.data?.error || "Failed to initialize Google OAuth connection.";
      setBanner({ type: "error", message: errMsg });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisconnect = async (accountId, platformName) => {
    if (!window.confirm(`Are you sure you want to disconnect ${platformName}? This will revoke official API access.`)) {
      return;
    }
    try {
      setActionLoading(true);
      const res = await socialMediaService.disconnectAccount(accountId);
      if (res.success) {
        setBanner({ type: "success", message: `${platformName} disconnected successfully.` });
        await fetchAccounts();
      } else {
        setBanner({ type: "error", message: res.message || res.error || "Failed to disconnect account." });
      }
    } catch (err) {
      const errMsg = err.response?.data?.error || err.response?.data?.message || "Failed to disconnect account.";
      setBanner({ type: "error", message: errMsg });
    } finally {
      setActionLoading(false);
    }
  };

  const isYtActive = ytAccount?.connection_status === "ACTIVE";
  const isYtExpired = ytAccount?.connection_status === "EXPIRED" || ytAccount?.connection_status === "ERROR";

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="accounts" />

      {/* Notification Banner */}
      {banner && (
        <div
          style={{
            padding: "14px 18px",
            borderRadius: "12px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            background: banner.type === "success" ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
            border: `1px solid ${banner.type === "success" ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
            color: banner.type === "success" ? "#065f46" : "#991b1b",
          }}
        >
          {banner.type === "success" ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
          <div style={{ fontSize: "13px", fontWeight: "600", flex: 1 }}>{banner.message}</div>
          <button
            onClick={() => setBanner(null)}
            style={{ background: "none", border: "none", cursor: "pointer", fontWeight: "bold", color: "inherit" }}
          >
            ×
          </button>
        </div>
      )}

      {/* Security & Privacy Banner */}
      <div
        style={{
          background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(168, 85, 247, 0.08))",
          border: "1px solid rgba(59, 130, 246, 0.25)",
          borderRadius: "14px",
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: "14px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "10px",
            background: "rgba(37, 99, 235, 0.15)",
            color: "var(--accent-blue, #2563eb)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Lock size={20} />
        </div>
        <div>
          <div style={{ fontSize: "13.5px", fontWeight: "700", color: "var(--text-primary, #0f172a)" }}>
            Zero-Password Enterprise Security & Token Encryption
          </div>
          <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
            LifeOS connects exclusively through official Google OAuth 2.0. All OAuth tokens are encrypted at rest using Fernet authenticated encryption. Passwords are never requested or stored.
          </div>
        </div>
      </div>

      {/* 3 Platforms Grid */}
      <div className="sm-platforms-grid">
        {/* 1. YouTube */}
        <div className="sm-platform-card">
          <div className="sm-platform-card-header">
            <div className="sm-platform-brand">
              <div className="sm-platform-logo-badge youtube">
                <Youtube size={22} />
              </div>
              <div>
                <div className="sm-platform-name">YouTube Channel</div>
                <div className="sm-platform-type">Google OAuth 2.0 API</div>
              </div>
            </div>
            <span
              className={`sm-status-pill ${
                isYtActive ? "connected" : isYtExpired ? "expired" : "not-connected"
              }`}
            >
              {isYtActive ? "Connected" : isYtExpired ? "Token Expired" : "Not Connected"}
            </span>
          </div>

          <div className="sm-platform-card-body">
            {ytAccount && (isYtActive || isYtExpired) ? (
              <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "10px 0" }}>
                {ytAccount.profile_image_url && (
                  <img
                    src={ytAccount.profile_image_url}
                    alt={ytAccount.account_name}
                    style={{ width: "42px", height: "42px", borderRadius: "50%", objectFit: "cover" }}
                  />
                )}
                <div>
                  <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary, #0f172a)" }}>
                    {ytAccount.account_name || "YouTube Channel"}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
                    {ytAccount.account_username ? `@${ytAccount.account_username}` : `Channel ID: ${ytAccount.platform_account_id}`}
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
                  <strong>Scope:</strong> YouTube Data API v3 (Read-Only Channel Verification)
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
                  Connect your official YouTube channel using secure Google OAuth 2.0 authorization.
                </div>
              </>
            )}
          </div>

          <div className="sm-platform-card-footer" style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
            {ytAccount && (isYtActive || isYtExpired) ? (
              <>
                <button
                  className="sm-btn-secondary"
                  style={{ fontSize: "12px", padding: "8px 14px" }}
                  onClick={handleConnectYouTube}
                  disabled={actionLoading}
                >
                  <RefreshCw size={13} style={{ marginRight: "6px" }} /> Reconnect
                </button>
                <button
                  className="sm-btn-secondary"
                  style={{ fontSize: "12px", padding: "8px 14px", color: "#dc2626", borderColor: "rgba(220, 38, 38, 0.3)" }}
                  onClick={() => handleDisconnect(ytAccount.id, "YouTube Channel")}
                  disabled={actionLoading}
                >
                  <Trash2 size={13} style={{ marginRight: "6px" }} /> Disconnect
                </button>
              </>
            ) : (
              <button
                className="sm-btn-primary"
                style={{ fontSize: "12px", padding: "8px 16px" }}
                onClick={handleConnectYouTube}
                disabled={actionLoading}
              >
                + Connect YouTube
              </button>
            )}
          </div>
        </div>

        {/* 2. Instagram Professional */}
        <div className="sm-platform-card">
          <div className="sm-platform-card-header">
            <div className="sm-platform-brand">
              <div className="sm-platform-logo-badge instagram">
                <Instagram size={22} />
              </div>
              <div>
                <div className="sm-platform-name">Instagram Creator / Pro</div>
                <div className="sm-platform-type">Meta Graph API</div>
              </div>
            </div>
            <span className="sm-status-pill not-connected">Not Configured</span>
          </div>

          <div className="sm-platform-card-body">
            <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
              <strong>Scope:</strong> instagram_basic, instagram_content_publish
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
              Requires an Instagram Business or Creator account connected to a Facebook Page (Stage 7).
            </div>
          </div>

          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-primary"
              style={{ fontSize: "12px", padding: "8px 16px", opacity: 0.5, cursor: "not-allowed" }}
              disabled={true}
            >
              + Connect Instagram (Phase 7)
            </button>
          </div>
        </div>

        {/* 3. Facebook Page */}
        <div className="sm-platform-card">
          <div className="sm-platform-card-header">
            <div className="sm-platform-brand">
              <div className="sm-platform-logo-badge facebook">
                <Facebook size={22} />
              </div>
              <div>
                <div className="sm-platform-name">Facebook Page</div>
                <div className="sm-platform-type">Meta Page Video API</div>
              </div>
            </div>
            <span className="sm-status-pill not-connected">Not Configured</span>
          </div>

          <div className="sm-platform-card-body">
            <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
              <strong>Scope:</strong> pages_show_list, pages_manage_posts
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
              Connect your official Facebook creator or business page (Stage 7).
            </div>
          </div>

          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-primary"
              style={{ fontSize: "12px", padding: "8px 16px", opacity: 0.5, cursor: "not-allowed" }}
              disabled={true}
            >
              + Connect Facebook (Phase 7)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ConnectedAccounts;
