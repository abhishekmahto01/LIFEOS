import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  Globe,
  PlusCircle,
  Calendar,
  Sparkles,
  ArrowRight,
  TrendingUp,
  ExternalLink,
  Layers,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

export function SocialMediaDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const summary = await socialMediaService.getDashboardSummary();
      setData(summary);
    } catch (e) {
      console.error("Error loading social media dashboard:", e);
    } finally {
      setLoading(false);
    }
  };

  const metrics = data?.metrics || {
    totalPublished: 0,
    scheduledPosts: 0,
    failedPosts: 0,
    connectedPlatforms: 0,
  };

  const platforms = data?.platforms || {
    youtube: { connected: false, channelName: null, status: "Not Connected" },
    instagram: { connected: false, accountName: null, status: "Not Connected" },
    facebook: { connected: false, pageName: null, status: "Not Connected" },
  };

  const recentPosts = data?.recentPosts || [];
  const upcomingSchedule = data?.upcomingSchedule || [];

  return (
    <div className="sm-module-container">
      {/* Navigation Header */}
      <SocialMediaNav activeTab="overview" onRefresh={loadDashboard} loading={loading} />

      {/* 01. 4 Metric KPI Cards */}
      <div className="sm-metrics-grid">
        <div className="sm-metric-card">
          <div className="sm-metric-icon published">
            <CheckCircle2 size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Published Posts</span>
            <span className="sm-metric-value">{metrics.totalPublished}</span>
          </div>
        </div>

        <div className="sm-metric-card">
          <div className="sm-metric-icon scheduled">
            <Clock size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Scheduled Posts</span>
            <span className="sm-metric-value">{metrics.scheduledPosts}</span>
          </div>
        </div>

        <div className="sm-metric-card">
          <div className="sm-metric-icon failed">
            <AlertTriangle size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Failed / Retries</span>
            <span className="sm-metric-value">{metrics.failedPosts}</span>
          </div>
        </div>

        <div className="sm-metric-card">
          <div className="sm-metric-icon platforms">
            <Globe size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Connected Platforms</span>
            <span className="sm-metric-value">{metrics.connectedPlatforms} / 3</span>
          </div>
        </div>
      </div>

      {/* 02. Connected Platform Summaries */}
      <div className="sm-section-title-row">
        <h2 className="sm-section-title">
          <Layers size={18} />
          <span>Platform Ecosystem Telemetry</span>
        </h2>
        <button
          className="sm-panel-action-link"
          onClick={() => navigate("/social-media/accounts")}
        >
          Manage Accounts &rarr;
        </button>
      </div>

      <div className="sm-platforms-grid">
        {/* YouTube */}
        <div className="sm-platform-card">
          <div className="sm-platform-card-header">
            <div className="sm-platform-brand">
              <div className="sm-platform-logo-badge youtube">
                <Youtube size={20} />
              </div>
              <div>
                <div className="sm-platform-name">YouTube</div>
                <div className="sm-platform-type">Shorts & Video API</div>
              </div>
            </div>
            <span
              className={`sm-status-pill ${
                platforms.youtube?.connected ? "connected" : "not-connected"
              }`}
            >
              {platforms.youtube?.connected ? "Connected" : "Not Configured"}
            </span>
          </div>
          <div className="sm-platform-card-body">
            {platforms.youtube?.connected ? (
              <div>
                <strong>Channel:</strong> {platforms.youtube.channelName || "Active"}
              </div>
            ) : (
              <div>No Google OAuth token linked. Connect to publish YouTube Shorts directly.</div>
            )}
          </div>
          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-connect-sm"
              onClick={() => navigate("/social-media/accounts")}
            >
              {platforms.youtube?.connected ? "Manage Channel" : "Connect YouTube"}
            </button>
          </div>
        </div>

        {/* Instagram */}
        <div className="sm-platform-card">
          <div className="sm-platform-card-header">
            <div className="sm-platform-brand">
              <div className="sm-platform-logo-badge instagram">
                <Instagram size={20} />
              </div>
              <div>
                <div className="sm-platform-name">Instagram</div>
                <div className="sm-platform-type">Professional Graph API</div>
              </div>
            </div>
            <span
              className={`sm-status-pill ${
                platforms.instagram?.connected ? "connected" : "not-connected"
              }`}
            >
              {platforms.instagram?.connected ? "Connected" : "Not Configured"}
            </span>
          </div>
          <div className="sm-platform-card-body">
            {platforms.instagram?.connected ? (
              <div>
                <strong>Account:</strong> {platforms.instagram.accountName || "Active"}
              </div>
            ) : (
              <div>No Meta OAuth link. Connect professional account to publish Reels.</div>
            )}
          </div>
          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-connect-sm"
              onClick={() => navigate("/social-media/accounts")}
            >
              {platforms.instagram?.connected ? "Manage Account" : "Connect Instagram"}
            </button>
          </div>
        </div>

        {/* Facebook */}
        <div className="sm-platform-card">
          <div className="sm-platform-card-header">
            <div className="sm-platform-brand">
              <div className="sm-platform-logo-badge facebook">
                <Facebook size={20} />
              </div>
              <div>
                <div className="sm-platform-name">Facebook</div>
                <div className="sm-platform-type">Pages & Reels API</div>
              </div>
            </div>
            <span
              className={`sm-status-pill ${
                platforms.facebook?.connected ? "connected" : "not-connected"
              }`}
            >
              {platforms.facebook?.connected ? "Connected" : "Not Configured"}
            </span>
          </div>
          <div className="sm-platform-card-body">
            {platforms.facebook?.connected ? (
              <div>
                <strong>Page:</strong> {platforms.facebook.pageName || "Active"}
              </div>
            ) : (
              <div>No Meta OAuth link. Connect Facebook Page to publish Video Reels.</div>
            )}
          </div>
          <div className="sm-platform-card-footer">
            <button
              className="sm-btn-connect-sm"
              onClick={() => navigate("/social-media/accounts")}
            >
              {platforms.facebook?.connected ? "Manage Page" : "Connect Facebook"}
            </button>
          </div>
        </div>
      </div>

      {/* 03. Two-Column Split (Recent Activity & Upcoming Schedule) */}
      <div className="sm-content-split-grid">
        {/* Recent Posts Panel */}
        <div className="sm-panel-card">
          <div className="sm-panel-header">
            <h3 className="sm-panel-title">
              <Sparkles size={17} />
              <span>Recent Content Activity</span>
            </h3>
            <span
              className="sm-panel-action-link"
              onClick={() => navigate("/social-media/history")}
            >
              View History &rarr;
            </span>
          </div>

          {recentPosts.length === 0 ? (
            <div className="sm-empty-state">
              <div className="sm-empty-icon-wrap">
                <PlusCircle size={22} />
              </div>
              <h4 className="sm-empty-title">No content created yet</h4>
              <p className="sm-empty-desc">
                Upload a video once, customize per-platform metadata, and broadcast across YouTube, Instagram, and Facebook.
              </p>
              <button
                className="sm-empty-btn"
                onClick={() => navigate("/social-media/create")}
              >
                + Create First Omnichannel Post
              </button>
            </div>
          ) : (
            <div>Recent post list items</div>
          )}
        </div>

        {/* Upcoming Schedule Panel */}
        <div className="sm-panel-card">
          <div className="sm-panel-header">
            <h3 className="sm-panel-title">
              <Calendar size={17} />
              <span>Upcoming Publishing Schedule</span>
            </h3>
            <span
              className="sm-panel-action-link"
              onClick={() => navigate("/social-media/calendar")}
            >
              Open Calendar &rarr;
            </span>
          </div>

          {upcomingSchedule.length === 0 ? (
            <div className="sm-empty-state">
              <div className="sm-empty-icon-wrap">
                <Clock size={22} />
              </div>
              <h4 className="sm-empty-title">No scheduled posts</h4>
              <p className="sm-empty-desc">
                Schedule your Reels and Shorts ahead of time. LifeOS background worker will publish them automatically.
              </p>
              <button
                className="sm-empty-btn"
                onClick={() => navigate("/social-media/create")}
              >
                Schedule Next Video
              </button>
            </div>
          ) : (
            <div>Upcoming schedule list items</div>
          )}
        </div>
      </div>

      {/* 04. Best Performing Content Banner */}
      <div className="sm-panel-card">
        <div className="sm-panel-header">
          <h3 className="sm-panel-title">
            <TrendingUp size={17} />
            <span>Best-Performing Omnichannel Content</span>
          </h3>
          <span
            className="sm-panel-action-link"
            onClick={() => navigate("/social-media/analytics")}
          >
            Detailed Analytics &rarr;
          </span>
        </div>

        <div className="sm-empty-state">
          <div className="sm-empty-icon-wrap">
            <TrendingUp size={22} />
          </div>
          <h4 className="sm-empty-title">Analytics telemetry ready</h4>
          <p className="sm-empty-desc">
            Performance metrics (views, likes, retention, engagement rate) will automatically populate once posts are published.
          </p>
        </div>
      </div>
    </div>
  );
}

export default SocialMediaDashboard;
