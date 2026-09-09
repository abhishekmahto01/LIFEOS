import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { permissionService } from "../services/permissionService";
import {
  Zap,
  Flame,
  Target,
  ArrowRight,
  Briefcase,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Award,
  Users,
  Key,
  Layers,
  BarChart3,
  FilePlus2,
  Kanban,
  Clock,
  Share2,
  Globe,
  PlusCircle,
  Calendar,
  Lock,
} from "lucide-react";
import { disciplineService } from "../services/disciplineService";
import { socialMediaService } from "../services/socialMediaService";
import "./Dashboard.css";

function Dashboard() {
  const navigate = useNavigate();

  const [modules, setModules] = useState([]);
  const [disciplineSummary, setDisciplineSummary] = useState(null);
  const [socialSummary, setSocialSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const user = JSON.parse(localStorage.getItem("user") || "{}");

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      if (!user || !user.user_id) {
        navigate("/login");
        return;
      }

      // Fetch user allowed modules via permissionService (/api/me/modules)
      const res = await permissionService.getMyModules();
      const fetchedModules = res.modules || [];
      setModules(fetchedModules);

      const hasDiscipline = fetchedModules.some(
        (m) =>
          m.module_code === "discipline" ||
          m.module_name?.toLowerCase() === "discipline" ||
          m.route === "/discipline"
      );

      const hasSocial = fetchedModules.some(
        (m) =>
          m.module_code === "social_media" ||
          m.module_name?.toLowerCase().includes("social") ||
          m.route === "/social-media"
      );

      // Fetch live discipline summary only if user has access to discipline
      if (hasDiscipline) {
        try {
          const discRes = await disciplineService.getTodaySummary(user.user_id);
          if (discRes.success) {
            setDisciplineSummary(discRes);
          }
        } catch (e) {
          console.error("Discipline summary fetch error:", e);
        }
      }

      // Fetch live social media summary only if user has access to social media
      if (hasSocial) {
        try {
          const smRes = await socialMediaService.getDashboardSummary();
          if (smRes.success) {
            setSocialSummary(smRes);
          }
        } catch (e) {
          console.error("Social media summary fetch error:", e);
        }
      }
    } catch (error) {
      console.error("Error loading dashboard modules:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dash-loading-screen">
        <div className="dash-loading-spinner"></div>
        <p>Initializing LifeOS Workspace...</p>
      </div>
    );
  }

  return (
    <div className="main-dashboard-wrapper">
      {/* Top Welcome Banner */}
      <div className="dash-welcome-banner">
        <div className="dash-welcome-content">
          <div className="dash-badge-row">
            <span className="dash-tag-pill">
              <Sparkles size={12} className="inline-icon" /> LIFEOS V2.0
            </span>
            <span className="dash-date-pill">
              {new Date().toLocaleDateString("en-US", {
                weekday: "long",
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          </div>
          <h1 className="dash-headline">
            Welcome Back, {user?.username || "Commander"} 👋
          </h1>
          <p className="dash-subheadline">
            Execute your 2026 goals, track daily discipline, and manage career pipelines.
          </p>
        </div>
      </div>

      {/* Sleek Minimalist Modules Grid */}
      <div className="modules-dashboard-grid">
        {modules.length === 0 ? (
          <div
            style={{
              gridColumn: "1 / -1",
              background: "rgba(255, 255, 255, 0.02)",
              border: "1px dashed rgba(255, 255, 255, 0.12)",
              borderRadius: "16px",
              padding: "48px 24px",
              textAlign: "center",
              color: "#94a3b8",
            }}
          >
            <Lock size={32} style={{ color: "#64748b", marginBottom: "16px" }} />
            <h3 style={{ color: "#e2e8f0", fontSize: "1.15rem", marginBottom: "8px" }}>
              No Module Access Assigned
            </h3>
            <p style={{ maxWidth: "420px", margin: "0 auto", fontSize: "0.9rem", lineHeight: 1.6 }}>
              You do not currently have access to any LIFEOS modules. Please contact an administrator to assign module permissions to your account.
            </p>
          </div>
        ) : (
          modules.map((mod) => {
          const isDiscipline =
            mod.module_code === "discipline" ||
            mod.module_name?.toLowerCase() === "discipline" ||
            mod.route === "/discipline";
          const isCareer =
            mod.module_code === "career" ||
            mod.module_name?.toLowerCase() === "career" ||
            mod.route === "/career";
          const isAdmin =
            mod.module_code === "admin" ||
            mod.module_name?.toLowerCase() === "admin" ||
            mod.route === "/admin";
          const isSocialMedia =
            mod.module_code === "social_media" ||
            mod.module_name?.toLowerCase().includes("social") ||
            mod.route === "/social-media";

          if (isSocialMedia) {
            return (
              <div
                key={mod.id}
                className="featured-module-card social-module-card"
                onClick={() => navigate(mod.route)}
              >
                <div className="card-top-shine"></div>

                {/* Header */}
                <div className="disc-card-header">
                  <div className="module-icon-badge social">
                    <Share2 size={18} />
                  </div>
                  <div className="disc-title-group">
                    <span className="module-kicker social">CREATOR &bull; OMNICHANNEL</span>
                    <h3 className="disc-card-title">SOCIAL MEDIA HUB</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={13} />
                  </div>
                </div>

                {/* Streamlined Live Stats */}
                <div className="disc-compact-stats-row">
                  <div className="compact-stat-chip">
                    <span className="chip-lbl">ACCOUNTS</span>
                    <span className="chip-val magenta">
                      {socialSummary?.metrics?.connectedPlatforms || 0}/3
                    </span>
                  </div>

                  <div className="compact-stat-chip">
                    <span className="chip-lbl">SCHEDULED</span>
                    <span className="chip-val cyan">
                      {socialSummary?.metrics?.scheduledPosts || 0}
                    </span>
                  </div>

                  <div className="compact-stat-chip">
                    <span className="chip-lbl">PUBLISHED</span>
                    <span className="chip-val emerald">
                      {socialSummary?.metrics?.totalPublished || 0}
                    </span>
                  </div>
                </div>

                {/* Quick Action Chips */}
                <div className="compact-features-grid">
                  <div
                    className="c-feature-chip"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate("/social-media/create");
                    }}
                  >
                    <PlusCircle size={12} />
                    <span>Create Post</span>
                  </div>
                  <div
                    className="c-feature-chip"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate("/social-media/calendar");
                    }}
                  >
                    <Calendar size={12} />
                    <span>Calendar</span>
                  </div>
                  <div
                    className="c-feature-chip"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate("/social-media/accounts");
                    }}
                  >
                    <Globe size={12} />
                    <span>Accounts</span>
                  </div>
                  <div
                    className="c-feature-chip"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate("/social-media/analytics");
                    }}
                  >
                    <TrendingUp size={12} />
                    <span>Analytics</span>
                  </div>
                </div>

                {/* Card Footer */}
                <div className="disc-card-footer">
                  <span className="social-cta-link">Open Creator Hub &rarr;</span>
                </div>
              </div>
            );
          }

          if (isDiscipline) {
            return (
              <div
                key={mod.id}
                className="featured-module-card discipline-card"
                onClick={() => navigate(mod.route)}
              >
                <div className="card-top-shine"></div>

                {/* Header */}
                <div className="disc-card-header">
                  <div className="module-icon-badge disc">
                    <Zap size={18} />
                  </div>
                  <div className="disc-title-group">
                    <span className="module-kicker disc">HABITS &bull; 2026</span>
                    <h3 className="disc-card-title">DISCIPLINE</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={13} />
                  </div>
                </div>

                {/* Streamlined Live Stats */}
                <div className="disc-compact-stats-row">
                  <div className="compact-stat-chip">
                    <span className="chip-lbl">STREAK</span>
                    <span className="chip-val flame">
                      🔥 {disciplineSummary?.current_streak || 0}d
                    </span>
                  </div>

                  <div className="compact-stat-chip">
                    <span className="chip-lbl">TODAY</span>
                    <span className="chip-val cyan">
                      {disciplineSummary?.today_completion || 0}%
                    </span>
                  </div>

                  <div className="compact-stat-chip">
                    <span className="chip-lbl">MONTH</span>
                    <span className="chip-val emerald">
                      {disciplineSummary?.monthly_completion || 0}%
                    </span>
                  </div>
                </div>

                {/* Clean Progress Meter */}
                <div className="disc-card-progress-bar">
                  <div className="d-bar-header">
                    <span>2026 MISSION</span>
                    <span className="d-pct">
                      {disciplineSummary?.year_2026_progress?.yearly_score || 0}%
                    </span>
                  </div>
                  <div className="d-track">
                    <div
                      className="d-fill"
                      style={{
                        width: `${Math.max(disciplineSummary?.year_2026_progress?.yearly_score || 0, 4)}%`,
                      }}
                    ></div>
                  </div>
                </div>

                {/* Card Footer */}
                <div className="disc-card-footer">
                  <span className="disc-cta-link">Open Matrix Tracker &rarr;</span>
                </div>
              </div>
            );
          }

          if (isCareer) {
            return (
              <div
                key={mod.id}
                className="featured-module-card career-module-card"
                onClick={() => navigate(mod.route)}
              >
                <div className="card-top-shine"></div>

                {/* Header */}
                <div className="disc-card-header">
                  <div className="module-icon-badge career">
                    <Briefcase size={18} />
                  </div>
                  <div className="disc-title-group">
                    <span className="module-kicker career">TECH PIPELINE</span>
                    <h3 className="disc-card-title">CAREER</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={13} />
                  </div>
                </div>

                {/* Quick Action Chips */}
                <div className="compact-features-grid">
                  <div className="c-feature-chip">
                    <BarChart3 size={12} />
                    <span>Analytics</span>
                  </div>
                  <div className="c-feature-chip">
                    <FilePlus2 size={12} />
                    <span>Job Entry</span>
                  </div>
                  <div className="c-feature-chip">
                    <Kanban size={12} />
                    <span>Pipeline</span>
                  </div>
                  <div className="c-feature-chip">
                    <Clock size={12} />
                    <span>Timeline</span>
                  </div>
                </div>

                {/* Card Footer */}
                <div className="disc-card-footer">
                  <span className="career-cta-link">Open Career Hub &rarr;</span>
                </div>
              </div>
            );
          }

          if (isAdmin) {
            return (
              <div
                key={mod.id}
                className="featured-module-card admin-module-card"
                onClick={() => navigate(mod.route)}
              >
                <div className="card-top-shine"></div>

                {/* Header */}
                <div className="disc-card-header">
                  <div className="module-icon-badge admin">
                    <ShieldAlert size={18} />
                  </div>
                  <div className="disc-title-group">
                    <span className="module-kicker admin">ACCESS &bull; SYSTEM</span>
                    <h3 className="disc-card-title">ADMIN</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={13} />
                  </div>
                </div>

                {/* Quick Action Chips */}
                <div className="compact-features-grid">
                  <div className="c-feature-chip">
                    <Users size={13} />
                    <span>Users</span>
                  </div>
                  <div className="c-feature-chip">
                    <Key size={13} />
                    <span>Permissions</span>
                  </div>
                  <div className="c-feature-chip">
                    <Layers size={13} />
                    <span>Modules</span>
                  </div>
                </div>

                {/* Card Footer */}
                <div className="disc-card-footer">
                  <span className="admin-cta-link">System Console &rarr;</span>
                </div>
              </div>
            );
          }

          return (
            <div
              key={mod.id}
              className="featured-module-card generic-module-card"
              onClick={() => navigate(mod.route)}
            >
              <div className="card-top-shine"></div>
              <div className="disc-card-header">
                <h3 className="disc-card-title">{mod.module_name}</h3>
                <div className="disc-arrow-btn">
                  <ArrowRight size={15} />
                </div>
              </div>
            </div>
          );
        })
      )}
      </div>
    </div>
  );
}

export default Dashboard;