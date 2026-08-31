import { useState, useEffect, useCallback } from "react";
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
  oauth_denied: "OAuth authorization was cancelled or denied.",
  invalid_state: "Invalid or unrecognized authorization session.",
  state_expired: "Authorization session expired. Please click Connect to try again.",
  state_already_used: "This authorization session has already been used.",
  redirect_uri_mismatch: "OAuth redirect URI configuration mismatch.",
  token_exchange_failed: "Failed to exchange authorization code with provider.",
  scope_not_granted: "Required permission scopes were not granted.",
  channel_not_found: "No YouTube channel found for this Google account. Please create a YouTube channel on youtube.com first.",
  instagram_account_not_found: "No Instagram Professional account found. Please verify your Instagram Business/Creator account is linked to a Facebook Page.",
  oauth_failed: "An unexpected error occurred while completing the OAuth connection.",
};

export function ConnectedAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState(() => {
    if (typeof window === "undefined") return null;
    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    const platform = params.get("platform");
    const channel = params.get("channel");
    const errorCode = params.get("code");
    const igParam = params.get("instagram");

    if (status === "success" || igParam === "connected") {
      const platformName = platform ? platform.toUpperCase() : igParam === "connected" ? "INSTAGRAM" : "YOUTUBE";
      const channelDisplay = channel ? `: ${decodeURIComponent(channel)}` : "";
      return {
        type: "success",
        message: `Successfully connected ${platformName === "INSTAGRAM" ? "Instagram" : platformName} account${channelDisplay}!`,
      };
    } else if (status === "error" || igParam === "error") {
      const errorMsg = OAUTH_ERROR_MESSAGES[errorCode] || `Failed to complete ${platform ? platform.toUpperCase() : "social"} OAuth connection.`;
      return {
        type: "error",
        message: errorMsg,
      };
    }
    return null;
  });
  const [actionLoading, setActionLoading] = useState(false);

  const fetchAccounts = useCallback(() => {
    setLoading(true);
    socialMediaService
      .getAccounts()
      .then((res) => {
        if (res.success) {
          setAccounts(res.accounts || []);
        } else {
          setBanner({
            type: "error",
            message: res.error || "Failed to retrieve connected social accounts.",
          });
        }
      })
      .catch(() => {
        setBanner({
          type: "error",
          message: "Failed to connect to backend server to load accounts.",
        });
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("status") || params.get("instagram")) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    let ignore = false;
    socialMediaService
      .getAccounts()
      .then((res) => {
        if (!ignore) {
          if (res.success) {
            setAccounts(res.accounts || []);
          } else {
            setBanner({
              type: "error",
              message: res.error || "Failed to retrieve connected social accounts.",
            });
          }
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setBanner({
            type: "error",
            message: "Failed to connect to backend server to load accounts.",
          });
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const ytAccount = accounts.find(
    (a) => a.platform?.toUpperCase() === "YOUTUBE"
  );
  const isYtActive = ytAccount?.connection_status === "ACTIVE";
  const isYtExpired = ytAccount?.connection_status === "EXPIRED" || ytAccount?.connection_status === "ERROR";

  const igAccount = accounts.find(
    (a) => a.platform?.toUpperCase() === "INSTAGRAM"
  );
  const isIgActive = igAccount?.connection_status === "ACTIVE";
  const isIgExpired = igAccount?.connection_status === "EXPIRED";
  const isIgError = igAccount?.connection_status === "ERROR";
  const isIgRevoked = igAccount?.connection_status === "REVOKED";
  const hasIgAccount = igAccount && igAccount.connection_status !== "DISCONNECTED";

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

  const handleConnectInstagram = async () => {
    try {
      setActionLoading(true);
      setBanner(null);
      const res = await socialMediaService.getInstagramConnectUrl();
      if (res.success && res.authorization_url) {
        window.location.href = res.authorization_url;
      } else {
        setBanner({
          type: "error",
          message: res.error || "Failed to generate Meta OAuth authorization URL.",
        });
      }
    } catch (err) {
      const errMsg = err.response?.data?.error || "Failed to initialize Instagram OAuth connection.";
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
      setBanner(null);
      const res = await socialMediaService.disconnectAccount(accountId);
      if (res.success) {
        setBanner({ type: "success", message: `Successfully disconnected ${platformName}.` });
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

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="accounts" onRefresh={fetchAccounts} loading={loading} />

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
                isYtActive && ytAccount?.can_upload
                  ? "connected"
                  : isYtActive && !ytAccount?.can_upload
                  ? "expired"
                  : isYtExpired
                  ? "expired"
                  : "not-connected"
              }`}
            >
              {isYtActive && ytAccount?.can_upload
                ? "Connected (Upload Ready)"
                : isYtActive && !ytAccount?.can_upload
                ? "Reconnect for Uploads"
                : isYtExpired
                ? "Token Expired"
                : "Not Connected"}
            </span>
          </div>

          <div className="sm-platform-card-body">
            {ytAccount && (isYtActive || isYtExpired) ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "10px 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
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
                {isYtActive && !ytAccount?.can_upload && (
                  <div style={{ fontSize: "11.5px", color: "#d97706", background: "rgba(217, 119, 6, 0.1)", padding: "6px 10px", borderRadius: "8px" }}>
                    ⚠️ <strong>Permission update:</strong> Click Reconnect to approve video publishing permissions (<code style={{ fontSize: "11px" }}>youtube.upload</code>).
                  </div>
                )}
              </div>
            ) : (
              <>
                <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
                  <strong>Scopes:</strong> YouTube Data API v3 (<code style={{ fontSize: "11px" }}>youtube.readonly</code>, <code style={{ fontSize: "11px" }}>youtube.upload</code>)
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
                  Connect your official YouTube channel using secure Google OAuth 2.0 authorization to enable one-click publishing.
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
                <div className="sm-platform-name">Instagram Professional</div>
                <div className="sm-platform-type">Meta Graph API</div>
              </div>
            </div>
            <span
              className={`sm-status-pill ${
                isIgActive
                  ? "connected"
                  : isIgExpired
                  ? "expired"
                  : isIgError || isIgRevoked
                  ? "error"
                  : "not-connected"
              }`}
            >
              {isIgActive
                ? "Connected"
                : isIgExpired
                ? "Session Expired"
                : isIgError
                ? "Connection Error"
                : isIgRevoked
                ? "Access Revoked"
                : "Not Connected"}
            </span>
          </div>

          <div className="sm-platform-card-body">
            {hasIgAccount ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "10px 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  {igAccount.profile_image_url ? (
                    <img
                      src={igAccount.profile_image_url}
                      alt={igAccount.account_name}
                      style={{ width: "42px", height: "42px", borderRadius: "50%", objectFit: "cover" }}
                    />
                  ) : (
                    <div
                      style={{
                        width: "42px",
                        height: "42px",
                        borderRadius: "50%",
                        background: "linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#ffffff"
                      }}
                    >
                      <Instagram size={22} />
                    </div>
                  )}
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary, #0f172a)" }}>
                      {igAccount.account_name || igAccount.account_username || "Instagram Account"}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
                      {igAccount.account_username ? `@${igAccount.account_username}` : `ID: ${igAccount.platform_account_id}`}
                    </div>
                  </div>
                </div>
                {isIgExpired && (
                  <div style={{ fontSize: "11.5px", color: "#d97706", background: "rgba(245, 158, 11, 0.1)", padding: "6px 10px", borderRadius: "8px", border: "1px solid rgba(245, 158, 11, 0.25)" }}>
                    ⚠️ <strong>Session Expired:</strong> Your Meta authorization token has expired. Click <strong>Reconnect</strong> to restore API access.
                  </div>
                )}
                {isIgError && (
                  <div style={{ fontSize: "11.5px", color: "#dc2626", background: "rgba(220, 38, 38, 0.1)", padding: "6px 10px", borderRadius: "8px", border: "1px solid rgba(220, 38, 38, 0.25)" }}>
                    ⚠️ <strong>Connection Error:</strong> Meta Graph API reported an authentication error. Click <strong>Reconnect</strong> to restore access.
                  </div>
                )}
                {isIgRevoked && (
                  <div style={{ fontSize: "11.5px", color: "#dc2626", background: "rgba(220, 38, 38, 0.1)", padding: "6px 10px", borderRadius: "8px", border: "1px solid rgba(220, 38, 38, 0.25)" }}>
                    ⚠️ <strong>Access Revoked:</strong> Permissions were revoked on Meta/Instagram. Click <strong>Reconnect</strong> to restore access.
                  </div>
                )}
              </div>
            ) : (
              <>
                <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
                  <strong>Scopes:</strong> Meta Graph API (<code style={{ fontSize: "11px" }}>instagram_basic</code>, <code style={{ fontSize: "11px" }}>instagram_content_publish</code>)
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
                  Connect your official Instagram Creator or Business account linked to a Facebook Page to enable automated publishing.
                </div>
              </>
            )}
          </div>

          <div className="sm-platform-card-footer" style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
            {hasIgAccount ? (
              <>
                <button
                  className="sm-btn-secondary"
                  style={{ fontSize: "12px", padding: "8px 14px" }}
                  onClick={handleConnectInstagram}
                  disabled={actionLoading}
                >
                  <RefreshCw size={13} style={{ marginRight: "6px" }} /> Reconnect
                </button>
                <button
                  className="sm-btn-secondary"
                  style={{ fontSize: "12px", padding: "8px 14px", color: "#dc2626", borderColor: "rgba(220, 38, 38, 0.3)" }}
                  onClick={() => handleDisconnect(igAccount.id, "Instagram Account")}
                  disabled={actionLoading}
                >
                  <Trash2 size={13} style={{ marginRight: "6px" }} /> Disconnect
                </button>
              </>
            ) : (
              <button
                className="sm-btn-primary"
                style={{ fontSize: "12px", padding: "8px 16px" }}
                onClick={handleConnectInstagram}
                disabled={actionLoading}
              >
                + Connect Instagram
              </button>
            )}
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
