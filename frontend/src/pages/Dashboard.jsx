import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
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
} from "lucide-react";
import { disciplineService } from "../services/disciplineService";
import "./Dashboard.css";

function Dashboard() {
  const navigate = useNavigate();

  const [modules, setModules] = useState([]);
  const [disciplineSummary, setDisciplineSummary] = useState(null);
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

      // Fetch user allowed modules
      const res = await axios.get(
        `http://localhost:5000/api/dashboard/modules/${user.user_id}`
      );

      // Fetch live discipline summary
      try {
        const discRes = await disciplineService.getTodaySummary(user.user_id);
        if (discRes.success) {
          setDisciplineSummary(discRes);
        }
      } catch (e) {
        console.error("Discipline summary fetch error:", e);
      }

      setModules(res.data);
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
        {modules.map((mod) => {
          const isDiscipline =
            mod.module_name?.toLowerCase() === "discipline" ||
            mod.route === "/discipline";
          const isCareer =
            mod.module_name?.toLowerCase() === "career" ||
            mod.route === "/career";
          const isAdmin =
            mod.module_name?.toLowerCase() === "admin" ||
            mod.route === "/admin";

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
        })}
      </div>
    </div>
  );
}

export default Dashboard;