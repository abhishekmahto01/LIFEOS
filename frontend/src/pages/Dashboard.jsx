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
        <p>Loading LifeOS workspace...</p>
      </div>
    );
  }

  return (
    <div className="main-dashboard-wrapper">
      {/* Welcome Banner */}
      <div className="dash-welcome-banner">
        <div className="dash-welcome-text">
          <div className="dash-badge-row">
            <span className="dash-tag-pill">🚀 LIFEOS V2.0</span>
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

      {/* Modules Grid */}
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
                <div className="disc-card-header">
                  <div className="disc-icon-badge">
                    <Zap size={22} className="text-yellow" />
                  </div>
                  <div className="disc-title-group">
                    <span className="disc-pill-tag">CORE HABIT ENGINE</span>
                    <h3 className="disc-card-title">DISCIPLINE</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={16} />
                  </div>
                </div>

                <p className="disc-motto-quote">
                  “Small actions. Every day. One goal.”
                </p>

                {/* Live Stats Grid */}
                <div className="disc-live-stats-row">
                  <div className="d-stat-box">
                    <span className="d-stat-label">Discipline Score</span>
                    <h4 className="d-stat-val">
                      {disciplineSummary?.year_2026_progress?.yearly_score || 0}%
                    </h4>
                    <span className="d-stat-sub">2026 Overall</span>
                  </div>

                  <div className="d-stat-box">
                    <span className="d-stat-label">Current Streak</span>
                    <h4 className="d-stat-val flame-text">
                      🔥 {disciplineSummary?.current_streak || 0}
                      <span className="d-unit"> Days</span>
                    </h4>
                    <span className="d-stat-sub">Unbroken Chain</span>
                  </div>

                  <div className="d-stat-box">
                    <span className="d-stat-label">Today's Progress</span>
                    <h4 className="d-stat-val">
                      {disciplineSummary?.today_completion || 0}%
                    </h4>
                    <span className="d-stat-sub">
                      {disciplineSummary?.today_completion === 100
                        ? "⭐ Perfect"
                        : "⏳ In Progress"}
                    </span>
                  </div>

                  <div className="d-stat-box">
                    <span className="d-stat-label">
                      {disciplineSummary?.current_month_name || "Monthly"}
                    </span>
                    <h4 className="d-stat-val">
                      {disciplineSummary?.monthly_completion || 0}%
                    </h4>
                    <span className="d-stat-sub">Month Avg</span>
                  </div>
                </div>

                {/* 2026 Progress Bar */}
                <div className="disc-card-progress-bar">
                  <div className="d-bar-header">
                    <span>2026 Year Mission</span>
                    <span>
                      {disciplineSummary?.year_2026_progress?.yearly_score || 0}%
                    </span>
                  </div>
                  <div className="d-track">
                    <div
                      className="d-fill"
                      style={{
                        width: `${disciplineSummary?.year_2026_progress?.yearly_score || 0}%`,
                      }}
                    ></div>
                  </div>
                </div>

                <div className="disc-card-footer">
                  <span className="disc-goal-hint">
                    🏍️ BMW S1000 Goal Unlocking
                  </span>
                  <span className="disc-cta-link">
                    Open Discipline Dashboard →
                  </span>
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
                <div className="disc-card-header">
                  <div className="career-icon-badge">
                    <Briefcase size={22} className="text-blue" />
                  </div>
                  <div className="disc-title-group">
                    <span className="career-pill-tag">OPPORTUNITIES</span>
                    <h3 className="disc-card-title">CAREER</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={16} />
                  </div>
                </div>

                <p className="career-motto-quote">
                  “Data Analytics & Tech Job Application Tracker”
                </p>

                <div className="career-preview-features">
                  <div className="c-feature-pill">📊 Analytics Dashboard</div>
                  <div className="c-feature-pill">📝 Job Entry Form</div>
                  <div className="c-feature-pill">📑 Pipeline & Kanban</div>
                  <div className="c-feature-pill">🕒 Timeline Logs</div>
                </div>

                <div className="disc-card-footer">
                  <span className="disc-goal-hint">Track Applications</span>
                  <span className="career-cta-link">Open Career Module →</span>
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
                <div className="disc-card-header">
                  <div className="admin-icon-badge">
                    <ShieldAlert size={22} className="text-purple" />
                  </div>
                  <div className="disc-title-group">
                    <span className="admin-pill-tag">SECURITY & USERS</span>
                    <h3 className="disc-card-title">ADMIN</h3>
                  </div>
                  <div className="disc-arrow-btn">
                    <ArrowRight size={16} />
                  </div>
                </div>

                <p className="career-motto-quote">
                  “Manage system modules, permissions and access controls.”
                </p>

                <div className="career-preview-features">
                  <div className="c-feature-pill">👥 User Master</div>
                  <div className="c-feature-pill">🔐 Permissions</div>
                  <div className="c-feature-pill">⚙️ System Modules</div>
                </div>

                <div className="disc-card-footer">
                  <span className="disc-goal-hint">Administration</span>
                  <span className="career-cta-link">Open Admin Module →</span>
                </div>
              </div>
            );
          }

          // Generic module fallback
          return (
            <div
              key={mod.id}
              className="featured-module-card generic-card"
              onClick={() => navigate(mod.route)}
            >
              <div className="disc-card-header">
                <h3 className="disc-card-title">{mod.module_name}</h3>
                <ArrowRight size={16} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default Dashboard;