import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Briefcase,
  Search,
  Filter,
  Download,
  PlusCircle,
  Clock,
  ExternalLink,
  Edit2,
  Trash2,
  List,
  Columns,
  RefreshCw,
  ArrowLeft,
  Calendar,
  Building2,
  MapPin,
  Laptop,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Award,
  Activity,
  X,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { jobService } from "../../../services/jobService";
import "./JobApplyHistory.css";

const STATUS_OPTIONS = [
  "Applied",
  "Screening",
  "Technical Round",
  "Interview",
  "Offer",
  "Rejected",
  "Ghosted",
];

function JobApplyHistory() {
  const navigate = useNavigate();

  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters & Search
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [selectedWorkMode, setSelectedWorkMode] = useState("All");
  const [selectedPortal, setSelectedPortal] = useState("All");
  const [viewMode, setViewMode] = useState("table"); // 'table' or 'kanban'

  // Modals state
  const [selectedJob, setSelectedJob] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isActivityModalOpen, setIsActivityModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Form states for modals
  const [editFormData, setEditFormData] = useState({});
  const [newActivityData, setNewActivityData] = useState({
    activity_name: "",
    activity_status: "Interview",
    activity_date: new Date().toISOString().split("T")[0],
    remarks: "",
  });
  const [modalLoading, setModalLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const fetchJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {};
      if (searchTerm.trim()) params.search = searchTerm.trim();
      if (selectedStatus !== "All") params.status = selectedStatus;
      if (selectedWorkMode !== "All") params.work_mode = selectedWorkMode;
      if (selectedPortal !== "All") params.job_portal = selectedPortal;

      const data = await jobService.getHistory(params);
      if (data.success) {
        setJobs(data.jobs || []);
      } else {
        setError(data.error || "Failed to fetch job history.");
      }
    } catch (err) {
      console.error("Error fetching jobs:", err);
      setError("Unable to connect to backend server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [selectedStatus, selectedWorkMode, selectedPortal]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchJobs();
  };

  // Quick inline status change
  const handleQuickStatusChange = async (jobId, newStatus) => {
    try {
      const currentJob = jobs.find((j) => j.id === jobId);
      if (!currentJob) return;

      const updated = {
        ...currentJob,
        status: newStatus,
        log_activity: true,
        activity_name: `Status updated to ${newStatus}`,
      };

      const res = await jobService.updateJob(jobId, updated);
      if (res.success) {
        setJobs((prev) =>
          prev.map((j) => (j.id === jobId ? { ...j, status: newStatus } : j))
        );
        showToast(`Status updated to "${newStatus}"!`);
      }
    } catch (err) {
      console.error("Status update error:", err);
      alert("Failed to update status.");
    }
  };

  // Open Activity / Timeline Modal
  const openActivityModal = async (job) => {
    try {
      setModalLoading(true);
      setSelectedJob(job);
      setIsActivityModalOpen(true);
      const res = await jobService.getJobById(job.id);
      if (res.success && res.job) {
        setSelectedJob(res.job);
        setNewActivityData({
          activity_name: "",
          activity_status: res.job.status || "Interview",
          activity_date: new Date().toISOString().split("T")[0],
          remarks: "",
        });
      }
    } catch (err) {
      console.error("Error loading activities:", err);
    } finally {
      setModalLoading(false);
    }
  };

  const handleAddActivity = async (e) => {
    e.preventDefault();
    if (!newActivityData.activity_name.trim()) return;

    try {
      setModalLoading(true);
      const res = await jobService.addActivity(selectedJob.id, newActivityData);
      if (res.success) {
        // Refresh single job
        const updatedJobRes = await jobService.getJobById(selectedJob.id);
        if (updatedJobRes.success) {
          setSelectedJob(updatedJobRes.job);
        }
        // Update in main list
        setJobs((prev) =>
          prev.map((j) =>
            j.id === selectedJob.id
              ? {
                  ...j,
                  status: newActivityData.activity_status || j.status,
                }
              : j
          )
        );
        setNewActivityData({
          activity_name: "",
          activity_status: selectedJob.status || "Interview",
          activity_date: new Date().toISOString().split("T")[0],
          remarks: "",
        });
        showToast("Activity logged to timeline successfully!");
      }
    } catch (err) {
      console.error("Add activity error:", err);
      alert("Failed to log activity.");
    } finally {
      setModalLoading(false);
    }
  };

  // Open Edit Modal
  const openEditModal = (job) => {
    setSelectedJob(job);
    setEditFormData({ ...job });
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      setModalLoading(true);
      const res = await jobService.updateJob(selectedJob.id, editFormData);
      if (res.success) {
        setJobs((prev) =>
          prev.map((j) => (j.id === selectedJob.id ? { ...editFormData } : j))
        );
        setIsEditModalOpen(false);
        showToast("Job application updated successfully!");
      }
    } catch (err) {
      console.error("Edit update error:", err);
      alert("Failed to update job application.");
    } finally {
      setModalLoading(false);
    }
  };

  // Delete Job
  const openDeleteModal = (job) => {
    setSelectedJob(job);
    setIsDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    try {
      setModalLoading(true);
      const res = await jobService.deleteJob(selectedJob.id);
      if (res.success) {
        setJobs((prev) => prev.filter((j) => j.id !== selectedJob.id));
        setIsDeleteModalOpen(false);
        showToast("Job application deleted.");
      }
    } catch (err) {
      console.error("Delete error:", err);
      alert("Failed to delete application.");
    } finally {
      setModalLoading(false);
    }
  };

  // Export to CSV
  const handleExportCSV = () => {
    if (jobs.length === 0) {
      alert("No application data to export.");
      return;
    }

    const headers = [
      "ID",
      "Company",
      "Role",
      "Portal",
      "Work Mode",
      "Location",
      "Salary",
      "Status",
      "Skills",
      "Resume Version",
      "HR Contact",
      "Date Applied",
      "Official Link",
      "Remarks",
    ];

    const csvRows = [headers.join(",")];

    jobs.forEach((j) => {
      const row = [
        j.id,
        `"${(j.organization_name || "").replace(/"/g, '""')}"`,
        `"${(j.post_name || "").replace(/"/g, '""')}"`,
        `"${(j.job_portal || "").replace(/"/g, '""')}"`,
        `"${(j.work_mode || "").replace(/"/g, '""')}"`,
        `"${(j.location || "").replace(/"/g, '""')}"`,
        `"${(j.salary_range || "").replace(/"/g, '""')}"`,
        `"${(j.status || "").replace(/"/g, '""')}"`,
        `"${(j.skills || "").replace(/"/g, '""')}"`,
        `"${(j.resume_version || "").replace(/"/g, '""')}"`,
        `"${(j.hr_contact || "").replace(/"/g, '""')}"`,
        `"${j.application_start_date || ""}"`,
        `"${(j.official_url || "").replace(/"/g, '""')}"`,
        `"${(j.remarks || "").replace(/"/g, '""')}"`,
      ];
      csvRows.push(row.join(","));
    });

    const csvContent =
      "data:text/csv;charset=utf-8," + encodeURIComponent(csvRows.join("\n"));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", csvContent);
    downloadAnchor.setAttribute(
      "download",
      `LifeOS_Data_Analytics_Applications_${new Date().toISOString().split("T")[0]}.csv`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

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

  // Group jobs for Kanban
  const kanbanColumns = [
    {
      title: "📝 Applied",
      statuses: ["Applied"],
      color: "blue",
    },
    {
      title: "⏳ Screening / Review",
      statuses: ["Screening", "Shortlisted"],
      color: "amber",
    },
    {
      title: "💻 Interview / Rounds",
      statuses: ["Interview", "Technical Round", "HR Round"],
      color: "indigo",
    },
    {
      title: "🎉 Offer Received",
      statuses: ["Offer"],
      color: "emerald",
    },
    {
      title: "❌ Rejected / Closed",
      statuses: ["Rejected", "Ghosted"],
      color: "gray",
    },
  ];

  return (
    <div className="job-history-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="history-toast-banner">
          <CheckCircle2 size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="history-header-card">
        <div className="history-header-left">
          <button
            className="btn-back-link"
            onClick={() => navigate("/career")}
          >
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </button>
          <div>
            <h1 className="history-main-title">Job Application Tracker</h1>
            <p className="history-subtitle">
              Manage, search, and track the full lifecycle of your Data
              Analytics applications
            </p>
          </div>
        </div>

        <div className="history-header-actions">
          <button
            className="btn-history-secondary"
            onClick={fetchJobs}
            title="Refresh list"
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? "spin" : ""} />
            <span>Refresh</span>
          </button>

          <button
            className="btn-history-secondary"
            onClick={handleExportCSV}
            title="Export CSV for Excel/Google Sheets"
          >
            <Download size={15} />
            <span>Export CSV</span>
          </button>

          <button
            className="btn-history-primary"
            onClick={() => navigate("/career/job-entry")}
          >
            <PlusCircle size={16} />
            <span>+ Log Application</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="history-toolbar-card">
        <form className="search-form" onSubmit={handleSearchSubmit}>
          <div className="search-input-wrapper">
            <Search size={16} className="search-icon-input" />
            <input
              type="text"
              placeholder="Search company, role, skills, location..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input-field"
            />
            {searchTerm && (
              <button
                type="button"
                className="btn-clear-search"
                onClick={() => {
                  setSearchTerm("");
                  fetchJobs();
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>
          <button type="submit" className="btn-search-submit">
            Search
          </button>
        </form>

        <div className="filters-group">
          {/* Status Filter */}
          <div className="filter-item">
            <label>Status:</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="filter-select"
            >
              <option value="All">All Statuses</option>
              {STATUS_OPTIONS.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>

          {/* Work Mode Filter */}
          <div className="filter-item">
            <label>Mode:</label>
            <select
              value={selectedWorkMode}
              onChange={(e) => setSelectedWorkMode(e.target.value)}
              className="filter-select"
            >
              <option value="All">All Modes</option>
              <option value="Remote">Remote</option>
              <option value="Hybrid">Hybrid</option>
              <option value="On-site">On-site</option>
            </select>
          </div>

          {/* View Mode Toggle */}
          <div className="view-mode-toggle">
            <button
              className={`btn-view-toggle ${
                viewMode === "table" ? "active" : ""
              }`}
              onClick={() => setViewMode("table")}
              title="Table View"
            >
              <List size={16} />
              <span>Table</span>
            </button>
            <button
              className={`btn-view-toggle ${
                viewMode === "kanban" ? "active" : ""
              }`}
              onClick={() => setViewMode("kanban")}
              title="Kanban Board View"
            >
              <Columns size={16} />
              <span>Kanban</span>
            </button>
          </div>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="history-error-banner">
          <span>⚠️ {error}</span>
          <button onClick={fetchJobs} className="btn-retry">
            Retry
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {loading ? (
        <div className="history-loading-box">
          <RefreshCw size={28} className="spin text-primary" />
          <p>Loading application history...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="history-empty-card">
          <Building2 size={44} className="empty-icon" />
          <h3>No Job Applications Found</h3>
          <p>
            {searchTerm || selectedStatus !== "All"
              ? "No applications matched your search or filters. Try clearing them."
              : "You haven't logged any job applications yet."}
          </p>
          <button
            className="btn-history-primary"
            onClick={() => {
              if (searchTerm || selectedStatus !== "All") {
                setSearchTerm("");
                setSelectedStatus("All");
                setSelectedWorkMode("All");
              } else {
                navigate("/career/job-entry");
              }
            }}
          >
            {searchTerm || selectedStatus !== "All"
              ? "Clear All Filters"
              : "+ Log Your First Job"}
          </button>
        </div>
      ) : viewMode === "table" ? (
        /* TABLE VIEW */
        <div className="history-table-card">
          <div className="table-header-meta">
            <span>Showing {jobs.length} applications</span>
          </div>
          <div className="table-responsive">
            <table className="history-data-table">
              <thead>
                <tr>
                  <th>Company & Position</th>
                  <th>Portal</th>
                  <th>Work Mode</th>
                  <th>Location</th>
                  <th>Salary / CTC</th>
                  <th>Date Applied</th>
                  <th>Current Stage</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <div className="job-meta-cell">
                        <div className="company-avatar-box">
                          {job.organization_name?.charAt(0)?.toUpperCase()}
                        </div>
                        <div>
                          <div className="company-title">
                            {job.organization_name}
                            {job.official_url && (
                              <a
                                href={job.official_url}
                                target="_blank"
                                rel="noreferrer"
                                className="link-ext-icon"
                                title="Open Job Link"
                              >
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                          <div className="role-subtitle">{job.post_name}</div>
                          {job.skills && (
                            <div className="skills-mini-pills">
                              {job.skills
                                .split(",")
                                .slice(0, 3)
                                .map((s, i) => (
                                  <span key={i} className="skill-mini-badge">
                                    {s.trim()}
                                  </span>
                                ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="source-tag">{job.job_portal}</span>
                    </td>

                    <td>
                      <span className="mode-badge-tag">{job.work_mode}</span>
                    </td>

                    <td className="location-text">
                      {job.location || "Not specified"}
                    </td>

                    <td className="salary-text">
                      {job.salary_range || "--"}
                    </td>

                    <td className="date-text">
                      {job.application_start_date || "--"}
                    </td>

                    <td>
                      <select
                        value={job.status}
                        onChange={(e) =>
                          handleQuickStatusChange(job.id, e.target.value)
                        }
                        className={`status-select-dropdown ${getStatusBadgeClass(
                          job.status
                        )}`}
                      >
                        {STATUS_OPTIONS.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                    </td>

                    <td style={{ textAlign: "right" }}>
                      <div className="actions-btn-group">
                        <button
                          className="btn-action-icon timeline"
                          onClick={() => openActivityModal(job)}
                          title="View & Add Timeline / Activities"
                        >
                          <Activity size={15} />
                        </button>
                        <button
                          className="btn-action-icon edit"
                          onClick={() => openEditModal(job)}
                          title="Edit Details"
                        >
                          <Edit2 size={15} />
                        </button>
                        <button
                          className="btn-action-icon delete"
                          onClick={() => openDeleteModal(job)}
                          title="Delete Application"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* KANBAN BOARD VIEW */
        <div className="kanban-board-grid">
          {kanbanColumns.map((col, idx) => {
            const columnJobs = jobs.filter((j) =>
              col.statuses.includes(j.status)
            );
            return (
              <div key={idx} className={`kanban-column column-${col.color}`}>
                <div className="kanban-column-header">
                  <h4>{col.title}</h4>
                  <span className="kanban-counter">{columnJobs.length}</span>
                </div>

                <div className="kanban-cards-stack">
                  {columnJobs.map((job) => (
                    <div key={job.id} className="kanban-card">
                      <div className="kanban-card-top">
                        <span className="kanban-company">
                          {job.organization_name}
                        </span>
                        <span className="kanban-portal">{job.job_portal}</span>
                      </div>

                      <h5 className="kanban-role">{job.post_name}</h5>

                      <div className="kanban-meta-row">
                        <span className="kanban-info-pill">
                          <MapPin size={11} /> {job.location || job.work_mode}
                        </span>
                        {job.salary_range && (
                          <span className="kanban-info-pill">
                            ₹ {job.salary_range}
                          </span>
                        )}
                      </div>

                      {job.skills && (
                        <div className="kanban-skills">
                          {job.skills
                            .split(",")
                            .slice(0, 2)
                            .map((s, i) => (
                              <span key={i} className="kanban-skill-badge">
                                {s.trim()}
                              </span>
                            ))}
                        </div>
                      )}

                      <div className="kanban-card-bottom">
                        <span className="kanban-date">
                          <Calendar size={11} /> {job.application_start_date}
                        </span>

                        <div className="kanban-actions">
                          <button
                            className="btn-kanban-action"
                            onClick={() => openActivityModal(job)}
                            title="Timeline / Rounds"
                          >
                            <Activity size={13} />
                          </button>
                          <button
                            className="btn-kanban-action"
                            onClick={() => openEditModal(job)}
                            title="Edit"
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            className="btn-kanban-action delete"
                            onClick={() => openDeleteModal(job)}
                            title="Delete"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}

                  {columnJobs.length === 0 && (
                    <div className="kanban-empty-column">
                      <span>No jobs in this stage</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ACTIVITY & TIMELINE MODAL */}
      {isActivityModalOpen && selectedJob && (
        <div className="modal-overlay">
          <div className="modal-box activity-modal">
            <div className="modal-header">
              <div className="modal-title-group">
                <Activity size={20} className="text-primary" />
                <div>
                  <h3 className="modal-heading">
                    Application Timeline & Activities
                  </h3>
                  <span className="modal-subheading">
                    {selectedJob.post_name} at {selectedJob.organization_name}
                  </span>
                </div>
              </div>
              <button
                className="btn-modal-close"
                onClick={() => setIsActivityModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body-scrollable">
              {/* Add New Activity Log Form */}
              <form onSubmit={handleAddActivity} className="new-activity-form">
                <h4 className="section-mini-title">+ Log New Round / Note</h4>
                <div className="activity-form-grid">
                  <div className="form-group">
                    <label className="form-label required">
                      Activity / Round Name
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Technical Round 1, Take-home Task, HR Call"
                      value={newActivityData.activity_name}
                      onChange={(e) =>
                        setNewActivityData({
                          ...newActivityData,
                          activity_name: e.target.value,
                        })
                      }
                      className="form-input"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Update Status To</label>
                    <select
                      value={newActivityData.activity_status}
                      onChange={(e) =>
                        setNewActivityData({
                          ...newActivityData,
                          activity_status: e.target.value,
                        })
                      }
                      className="form-select"
                    >
                      {STATUS_OPTIONS.map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-group" style={{ marginTop: "10px" }}>
                  <label className="form-label">Activity Date</label>
                  <input
                    type="date"
                    value={newActivityData.activity_date}
                    onChange={(e) =>
                      setNewActivityData({
                        ...newActivityData,
                        activity_date: e.target.value,
                      })
                    }
                    className="form-input"
                  />
                </div>

                <div className="form-group" style={{ marginTop: "10px" }}>
                  <label className="form-label">Remarks / Interview Questions</label>
                  <textarea
                    rows={2}
                    placeholder="Enter what went well, questions asked (SQL, Python, etc.), or next steps..."
                    value={newActivityData.remarks}
                    onChange={(e) =>
                      setNewActivityData({
                        ...newActivityData,
                        remarks: e.target.value,
                      })
                    }
                    className="form-textarea"
                  />
                </div>

                <button
                  type="submit"
                  className="btn-add-activity-submit"
                  disabled={modalLoading}
                >
                  {modalLoading ? "Saving..." : "Add to Timeline"}
                </button>
              </form>

              {/* Timeline list */}
              <div className="timeline-history-list">
                <h4 className="section-mini-title">Timeline History</h4>
                {selectedJob.activities && selectedJob.activities.length > 0 ? (
                  <div className="timeline-stack">
                    {selectedJob.activities.map((act) => (
                      <div key={act.id} className="timeline-item">
                        <div className="timeline-dot"></div>
                        <div className="timeline-card">
                          <div className="timeline-top">
                            <span className="timeline-name">
                              {act.activity_name}
                            </span>
                            <span className="timeline-date">
                              {act.activity_date}
                            </span>
                          </div>
                          {act.activity_status && (
                            <span
                              className={`timeline-status-tag ${getStatusBadgeClass(
                                act.activity_status
                              )}`}
                            >
                              {act.activity_status}
                            </span>
                          )}
                          {act.remarks && (
                            <p className="timeline-remarks">{act.remarks}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-timeline-note">
                    No activity recorded yet.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* EDIT MODAL */}
      {isEditModalOpen && selectedJob && (
        <div className="modal-overlay">
          <div className="modal-box edit-modal">
            <div className="modal-header">
              <div className="modal-title-group">
                <Edit2 size={18} className="text-primary" />
                <h3 className="modal-heading">Edit Job Application</h3>
              </div>
              <button
                className="btn-modal-close"
                onClick={() => setIsEditModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="modal-form">
              <div className="form-grid-2">
                <div className="form-group">
                  <label className="form-label required">Role / Title</label>
                  <input
                    type="text"
                    required
                    value={editFormData.post_name || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        post_name: e.target.value,
                      })
                    }
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label required">Company</label>
                  <input
                    type="text"
                    required
                    value={editFormData.organization_name || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        organization_name: e.target.value,
                      })
                    }
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-grid-3" style={{ marginTop: "12px" }}>
                <div className="form-group">
                  <label className="form-label">Portal</label>
                  <input
                    type="text"
                    value={editFormData.job_portal || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        job_portal: e.target.value,
                      })
                    }
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Work Mode</label>
                  <select
                    value={editFormData.work_mode || "Remote"}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        work_mode: e.target.value,
                      })
                    }
                    className="form-select"
                  >
                    <option value="Remote">Remote</option>
                    <option value="Hybrid">Hybrid</option>
                    <option value="On-site">On-site</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Status</label>
                  <select
                    value={editFormData.status || "Applied"}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        status: e.target.value,
                      })
                    }
                    className="form-select"
                  >
                    {STATUS_OPTIONS.map((st) => (
                      <option key={st} value={st}>
                        {st}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-grid-2" style={{ marginTop: "12px" }}>
                <div className="form-group">
                  <label className="form-label">Location</label>
                  <input
                    type="text"
                    value={editFormData.location || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        location: e.target.value,
                      })
                    }
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Salary Range</label>
                  <input
                    type="text"
                    value={editFormData.salary_range || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        salary_range: e.target.value,
                      })
                    }
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-group" style={{ marginTop: "12px" }}>
                <label className="form-label">Job Link URL</label>
                <input
                  type="url"
                  value={editFormData.official_url || ""}
                  onChange={(e) =>
                    setEditFormData({
                      ...editFormData,
                      official_url: e.target.value,
                    })
                  }
                  className="form-input"
                />
              </div>

              <div className="form-group" style={{ marginTop: "12px" }}>
                <label className="form-label">Skills Matched</label>
                <input
                  type="text"
                  value={editFormData.skills || ""}
                  onChange={(e) =>
                    setEditFormData({
                      ...editFormData,
                      skills: e.target.value,
                    })
                  }
                  className="form-input"
                />
              </div>

              <div className="form-group" style={{ marginTop: "12px" }}>
                <label className="form-label">Remarks</label>
                <textarea
                  rows={2}
                  value={editFormData.remarks || ""}
                  onChange={(e) =>
                    setEditFormData({
                      ...editFormData,
                      remarks: e.target.value,
                    })
                  }
                  className="form-textarea"
                />
              </div>

              <div className="modal-actions-footer">
                <button
                  type="button"
                  className="btn-modal-cancel"
                  onClick={() => setIsEditModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-modal-save"
                  disabled={modalLoading}
                >
                  {modalLoading ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {isDeleteModalOpen && selectedJob && (
        <div className="modal-overlay">
          <div className="modal-box delete-confirm-box">
            <div className="delete-icon-wrap">
              <Trash2 size={24} />
            </div>
            <h3 className="delete-title">Delete Application?</h3>
            <p className="delete-desc">
              Are you sure you want to delete the application for{" "}
              <strong>{selectedJob.post_name}</strong> at{" "}
              <strong>{selectedJob.organization_name}</strong>? This will also
              remove all recorded interview timeline logs.
            </p>
            <div className="delete-actions">
              <button
                className="btn-modal-cancel"
                onClick={() => setIsDeleteModalOpen(false)}
              >
                Cancel
              </button>
              <button
                className="btn-confirm-delete"
                onClick={handleDeleteConfirm}
                disabled={modalLoading}
              >
                {modalLoading ? "Deleting..." : "Yes, Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default JobApplyHistory;