import { useState, useEffect } from "react";
import {
  TrendingUp,
  Eye,
  Heart,
  MessageSquare,
  Share2,
  Users,
  BarChart3,
  Sparkles,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

export function SocialAnalytics() {
  const [analytics, setAnalytics] = useState(null);
  const [platformTab, setPlatformTab] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const res = await socialMediaService.getAnalytics();
      if (res.success) {
        setAnalytics(res.analytics);
      }
    } catch (e) {
      console.error("Error loading analytics:", e);
    } finally {
      setLoading(false);
    }
  };

  const a = analytics || {
    totalViews: 0,
    totalLikes: 0,
    totalComments: 0,
    totalShares: 0,
    followersGained: 0,
    engagementRate: 0,
  };

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="analytics" onRefresh={loadAnalytics} loading={loading} />

      {/* Analytics KPI Metrics */}
      <div className="sm-metrics-grid">
        <div className="sm-metric-card">
          <div className="sm-metric-icon published">
            <Eye size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Total Views</span>
            <span className="sm-metric-value">{a.totalViews.toLocaleString()}</span>
          </div>
        </div>

        <div className="sm-metric-card">
          <div className="sm-metric-icon scheduled">
            <Heart size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Total Likes</span>
            <span className="sm-metric-value">{a.totalLikes.toLocaleString()}</span>
          </div>
        </div>

        <div className="sm-metric-card">
          <div className="sm-metric-icon platforms">
            <MessageSquare size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Comments & Shares</span>
            <span className="sm-metric-value">{(a.totalComments + a.totalShares).toLocaleString()}</span>
          </div>
        </div>

        <div className="sm-metric-card">
          <div className="sm-metric-icon failed">
            <Users size={22} />
          </div>
          <div className="sm-metric-info">
            <span className="sm-metric-label">Followers Gained</span>
            <span className="sm-metric-value">+{a.followersGained}</span>
          </div>
        </div>
      </div>

      {/* Platform Breakdown Panel */}
      <div className="sm-panel-card">
        <div className="sm-panel-header">
          <h3 className="sm-panel-title">
            <BarChart3 size={18} />
            <span>Cross-Platform Audience Engagement & Retention</span>
          </h3>

          <div style={{ display: "flex", gap: "6px" }}>
            <button
              className={`sm-tab-btn ${platformTab === "all" ? "active" : ""}`}
              onClick={() => setPlatformTab("all")}
            >
              Omnichannel
            </button>
            <button
              className={`sm-tab-btn ${platformTab === "youtube" ? "active" : ""}`}
              onClick={() => setPlatformTab("youtube")}
            >
              <Youtube size={15} color="#ff0000" /> YouTube
            </button>
            <button
              className={`sm-tab-btn ${platformTab === "instagram" ? "active" : ""}`}
              onClick={() => setPlatformTab("instagram")}
            >
              <Instagram size={15} color="#e1306c" /> Instagram
            </button>
            <button
              className={`sm-tab-btn ${platformTab === "facebook" ? "active" : ""}`}
              onClick={() => setPlatformTab("facebook")}
            >
              <Facebook size={15} color="#1877f2" /> Facebook
            </button>
          </div>
        </div>

        {/* Telemetry Visual Graph Area */}
        <div className="sm-empty-state">
          <div className="sm-empty-icon-wrap">
            <TrendingUp size={24} />
          </div>
          <h4 className="sm-empty-title">Real-time Analytics Engine Active</h4>
          <p className="sm-empty-desc">
            Connect your YouTube channel and Meta accounts to view automatic graph telemetry, retention curves, click-through rates, and audience demographics.
          </p>
        </div>
      </div>
    </div>
  );
}

export default SocialAnalytics;
