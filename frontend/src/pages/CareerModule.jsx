import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Briefcase,
  PlusCircle,
  History,
  TrendingUp,
  Clock,
  Award,
  CheckCircle2,
  XCircle,
  Building2,
  ExternalLink,
  RefreshCw,
  BarChart3,
  Globe,
  MapPin,
  Laptop,
  ArrowRight,
  Database,
  Sparkles,
} from "lucide-react";
import { jobService } from "../services/jobService";
import "./CareerModule.css";

function CareerModule() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await jobService.getStats();
      if (data.success) {
        setStats(data);
      } else {
        setError(data.error || "Failed to load career metrics");
      }
    } catch (err) {
      console.error("Error fetching stats:", err);
      setError("Unable to connect to backend server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const getStatusBadgeClass = (status) => {
    switch (status?.toLowerCase()) {
      case "offer":
        return "status-badge status-offer";
      case "interview":
      case "technical round":
      case "hr round":
        return "status-badge status-interview";
      case "screening":
      case "shortlisted":
        return "status-badge status-screening";
      case "rejected":
        return "status-badge status-rejected";
      case "ghosted":
        return "status-badge status-ghosted";
      default:
        return "status-badge status-applied";
    }
  };

  return (
    <div className="career-dashboard-container">
      {/* Top Header Navigation & Action Bar */}
      <div className="career-header-card">
        <div className="career-header-info">
          <div className="career-title-row">
            <div className="career-icon-wrapper">
              <Database size={24} />
            </div>
            <div>
              <h1 className="career-main-title">Career & Job Tracker</h1>
              <p className="career-subtitle">
                Data Analytics & Tech Application Pipeline Dashboard
              </p>
            </div>
          </div>
        </div>

        <div className="career-header-actions">
          <button
            className="btn-header-refresh"
            onClick={fetchStats}
            title="Refresh Data"
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            <span>Refresh</span>
          </button>
          <button
            className="btn-header-secondary"
            onClick={() => navigate("/career/job-history")}
          >
            <History size={16} />
            <span>Job Apply History</span>
          </button>
          <button
            className="btn-header-primary"
            onClick={() => navigate("/career/job-entry")}
          >
            <PlusCircle size={16} />
            <span>+ New Job Application</span>
          </button>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="career-nav-tabs">
        <button className="career-tab-btn active">
          <BarChart3 size={16} />
          <span>Dashboard Overview</span>
        </button>
        <button
          className="career-tab-btn"
          onClick={() => navigate("/career/job-entry")}
        >
          <PlusCircle size={16} />
          <span>Job Entry Form</span>
        </button>
        <button
          className="career-tab-btn"
          onClick={() => navigate("/career/job-history")}
        >
          <History size={16} />
          <span>Apply History & Tracker</span>
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="career-alert-banner">
          <span>⚠️ {error}</span>
          <button onClick={fetchStats} className="btn-alert-retry">
            Retry
          </button>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <div className="kpi-card kpi-total">
          <div className="kpi-icon-box blue">
            <Briefcase size={22} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Total Applied</span>
            <h2 className="kpi-value">{loading ? "--" : stats?.total || 0}</h2>
            <span className="kpi-hint">Applications tracked</span>
          </div>
        </div>

        <div className="kpi-card kpi-screening">
          <div className="kpi-icon-box amber">
            <Clock size={22} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Screening / Review</span>
            <h2 className="kpi-value">
              {loading ? "--" : stats?.status_breakdown?.Screening || 0}
            </h2>
            <span className="kpi-hint">Resume / HR review</span>
          </div>
        </div>

        <div className="kpi-card kpi-interview">
          <div className="kpi-icon-box indigo">
            <TrendingUp size={22} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Interviews</span>
            <h2 className="kpi-value">
              {loading ? "--" : stats?.status_breakdown?.Interview || 0}
            </h2>
            <span className="kpi-hint">Technical / HR rounds</span>
          </div>
        </div>

        <div className="kpi-card kpi-offer">
          <div className="kpi-icon-box emerald">
            <Award size={22} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Offers Received</span>
            <h2 className="kpi-value">
              {loading ? "--" : stats?.status_breakdown?.Offer || 0}
            </h2>
            <span className="kpi-hint">Celebration milestone!</span>
          </div>
        </div>

        <div className="kpi-card kpi-rate">
          <div className="kpi-icon-box purple">
            <Sparkles size={22} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Interview Rate</span>
            <h2 className="kpi-value">
              {loading ? "--" : `${stats?.interview_rate || 0}%`}
            </h2>
            <span className="kpi-hint">Interviews / Total</span>
          </div>
        </div>

        <div className="kpi-card kpi-rejected">
          <div className="kpi-icon-box gray">
            <XCircle size={22} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Rejected / Closed</span>
            <h2 className="kpi-value">
              {loading ? "--" : stats?.status_breakdown?.Rejected || 0}
            </h2>
            <span className="kpi-hint">Keep momentum high</span>
          </div>
        </div>
      </div>

      {/* Main Insights Section */}
      <div className="career-insights-grid">
        {/* Left: Role & Platform Breakdown */}
        <div className="insights-card">
          <div className="card-header-with-badge">
            <div className="card-header-title">
              <BarChart3 size={18} className="text-primary" />
              <h3>Target Roles Breakdown</h3>
            </div>
            <span className="badge-count">
              {stats?.top_roles?.length || 0} Roles
            </span>
          </div>

          <div className="role-breakdown-list">
            {loading ? (
              <div className="skeleton-placeholder">Loading insights...</div>
            ) : stats?.top_roles && stats.top_roles.length > 0 ? (
              stats.top_roles.map((item, idx) => {
                const percentage = stats.total
                  ? Math.round((item.count / stats.total) * 100)
                  : 0;
                return (
                  <div key={idx} className="breakdown-row">
                    <div className="breakdown-info">
                      <span className="breakdown-name">{item.role}</span>
                      <span className="breakdown-stat">
                        {item.count} ({percentage}%)
                      </span>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${Math.max(percentage, 8)}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="empty-insights-box">
                <p>No job applications logged yet.</p>
                <button
                  className="btn-mini-primary"
                  onClick={() => navigate("/career/job-entry")}
                >
                  Log Your First Role
                </button>
              </div>
            )}
          </div>

          {/* Work Mode Breakdown */}
          <div className="work-mode-section">
            <h4 className="section-subheading">Work Environment</h4>
            <div className="work-mode-chips">
              <div className="work-chip">
                <Laptop size={14} />
                <span>
                  Remote: {stats?.work_mode_breakdown?.Remote || 0}
                </span>
              </div>
              <div className="work-chip">
                <Building2 size={14} />
                <span>
                  Hybrid: {stats?.work_mode_breakdown?.Hybrid || 0}
                </span>
              </div>
              <div className="work-chip">
                <MapPin size={14} />
                <span>
                  On-site: {stats?.work_mode_breakdown?.["On-site"] || 0}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Job Portals & Quick Data Strategy */}
        <div className="insights-card">
          <div className="card-header-with-badge">
            <div className="card-header-title">
              <Globe size={18} className="text-secondary" />
              <h3>Top Job Portals & Sources</h3>
            </div>
            <span className="badge-count">
              {stats?.top_portals?.length || 0} Portals
            </span>
          </div>

          <div className="portal-grid">
            {loading ? (
              <div className="skeleton-placeholder">Loading portals...</div>
            ) : stats?.top_portals && stats.top_portals.length > 0 ? (
              stats.top_portals.map((p, idx) => (
                <div key={idx} className="portal-item-card">
                  <span className="portal-name">{p.portal}</span>
                  <span className="portal-number">{p.count} applications</span>
                </div>
              ))
            ) : (
              <div className="empty-insights-box">
                <p>LinkedIn, Indeed, Naukri, Referrals will show here.</p>
              </div>
            )}
          </div>

          {/* Data Analytics Track Banner */}
          <div className="da-track-banner">
            <div className="da-track-header">
              <Sparkles size={16} className="da-sparkle" />
              <span>Data Analytics Optimization Tip</span>
            </div>
            <p className="da-track-text">
              Highlight projects with SQL transformations, Power BI/Tableau
              interactive dashboards, and business KPI impacts in your
              applications for higher interview conversion.
            </p>
          </div>
        </div>
      </div>

      {/* Recent Applications Feed */}
      <div className="recent-apps-card">
        <div className="recent-apps-header">
          <div className="recent-title-group">
            <Clock size={18} className="text-primary" />
            <h3>Recent Job Applications</h3>
          </div>
          <button
            className="btn-view-all"
            onClick={() => navigate("/career/job-history")}
          >
            <span>View All History</span>
            <ArrowRight size={15} />
          </button>
        </div>

        {loading ? (
          <div className="recent-loading-state">Loading recent applications...</div>
        ) : stats?.recent_jobs && stats.recent_jobs.length > 0 ? (
          <div className="recent-table-wrapper">
            <table className="recent-table">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Role</th>
                  <th>Portal</th>
                  <th>Work Mode</th>
                  <th>Date Applied</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <div className="company-cell">
                        <div className="company-avatar">
                          {job.organization_name?.charAt(0)?.toUpperCase()}
                        </div>
                        <span className="company-name">
                          {job.organization_name}
                        </span>
                      </div>
                    </td>
                    <td className="role-cell">{job.post_name}</td>
                    <td>
                      <span className="portal-tag">{job.job_portal}</span>
                    </td>
                    <td>
                      <span className="mode-tag">{job.work_mode}</span>
                    </td>
                    <td className="date-cell">{job.application_start_date}</td>
                    <td>
                      <span className={getStatusBadgeClass(job.status)}>
                        {job.status}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn-row-action"
                        onClick={() => navigate("/career/job-history")}
                        title="View details in history"
                      >
                        View <ExternalLink size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="recent-empty-state">
            <Building2 size={36} className="empty-icon" />
            <p className="empty-text">No job applications logged yet.</p>
            <p className="empty-subtext">
              Click below to record your first Data Analytics job application.
            </p>
            <button
              className="btn-header-primary"
              style={{ marginTop: "14px" }}
              onClick={() => navigate("/career/job-entry")}
            >
              <PlusCircle size={16} />
              <span>Add Job Application</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default CareerModule;