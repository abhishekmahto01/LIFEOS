import { useState, useEffect } from "react";
import {
  Link2,
  ShieldCheck,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Lock,
  Radio,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

export function ConnectedAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    try {
      setLoading(true);
      const res = await socialMediaService.getAccounts();
      if (res.success) {
        setAccounts(res.accounts || []);
      }
    } catch (e) {
      console.error("Error fetching accounts:", e);
    } finally {
      setLoading(false);
    }
  };

  const isPlatformConnected = (platformKey) => {
    return accounts.some(
      (a) => a.platform?.toLowerCase() === platformKey.toLowerCase() && a.connection_status === "ACTIVE"
    );
  };

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="accounts" />

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
            LifeOS connects exclusively through official Google OAuth 2.0 and Meta Graph APIs. All OAuth tokens are encrypted at rest using AES-256. Passwords are never requested or stored.
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
                isPlatformConnected("youtube") ? "connected" : "not-connected"
              }`}
            >
              {isPlatformConnected("youtube") ? "Connected" : "Not Configured"}
            </span>
          </div>

          <div className="sm-platform-card-body">
            <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
              <strong>Scope:</strong> YouTube Data API v3 (Upload Video, Shorts, Read Analytics)
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
              {isPlatformConnected("youtube")
                ? "Active channel connection ready for video uploads."
                : "Configure Google Client ID & Secret in .env to initiate official OAuth connection."}
            </div>
          </div>

          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-primary"
              style={{ fontSize: "12px", padding: "8px 16px" }}
              onClick={() =>
                alert("Google OAuth 2.0 will connect via backend /api/social-media/connect/youtube in Phase 3.")
              }
            >
              {isPlatformConnected("youtube") ? "Reconnect Channel" : "+ Connect YouTube"}
            </button>
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
            <span
              className={`sm-status-pill ${
                isPlatformConnected("instagram") ? "connected" : "not-connected"
              }`}
            >
              {isPlatformConnected("instagram") ? "Connected" : "Not Configured"}
            </span>
          </div>

          <div className="sm-platform-card-body">
            <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
              <strong>Scope:</strong> instagram_basic, instagram_content_publish, instagram_manage_insights
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
              {isPlatformConnected("instagram")
                ? "Active Instagram professional account ready for Reels."
                : "Requires an Instagram Business/Creator account linked to a Meta App."}
            </div>
          </div>

          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-primary"
              style={{ fontSize: "12px", padding: "8px 16px" }}
              onClick={() =>
                alert("Meta OAuth will connect via backend /api/social-media/connect/meta in Phase 5.")
              }
            >
              {isPlatformConnected("instagram") ? "Reconnect Account" : "+ Connect Instagram"}
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
            <span
              className={`sm-status-pill ${
                isPlatformConnected("facebook") ? "connected" : "not-connected"
              }`}
            >
              {isPlatformConnected("facebook") ? "Connected" : "Not Configured"}
            </span>
          </div>

          <div className="sm-platform-card-body">
            <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginBottom: "6px" }}>
              <strong>Scope:</strong> pages_show_list, pages_read_engagement, pages_manage_posts
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary, #334155)" }}>
              {isPlatformConnected("facebook")
                ? "Active Facebook page ready for Video Reels publishing."
                : "Connect your official Facebook creator/business page."}
            </div>
          </div>

          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-primary"
              style={{ fontSize: "12px", padding: "8px 16px" }}
              onClick={() =>
                alert("Meta OAuth will connect via backend /api/social-media/connect/meta in Phase 5.")
              }
            >
              {isPlatformConnected("facebook") ? "Reconnect Page" : "+ Connect Facebook"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ConnectedAccounts;
