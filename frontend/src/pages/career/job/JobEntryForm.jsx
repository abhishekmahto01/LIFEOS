import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Briefcase,
  Building2,
  Globe,
  MapPin,
  Calendar,
  DollarSign,
  FileText,
  UserCheck,
  CheckCircle2,
  ArrowLeft,
  History,
  Sparkles,
  Link as LinkIcon,
  Tag,
  Laptop,
  Check,
  AlertCircle,
} from "lucide-react";
import { jobService } from "../../../services/jobService";
import "./JobEntryForm.css";

const ROLE_SUGGESTIONS = [
  "Data Analyst",
  "Senior Data Analyst",
  "Business Analyst",
  "BI Developer / Power BI Specialist",
  "Data Engineer",
  "Product Analyst",
  "Analytics Engineer",
  "Data Scientist",
  "Junior Data Analyst",
];

const PORTAL_SUGGESTIONS = [
  "LinkedIn",
  "Naukri",
  "Indeed",
  "Company Careers Page",
  "Glassdoor",
  "Wellfound (AngelList)",
  "Referral",
  "Instahyre",
  "Internshala",
];

const SKILL_SUGGESTIONS = [
  "SQL",
  "Python",
  "Power BI",
  "Tableau",
  "Advanced Excel",
  "Pandas / NumPy",
  "BigQuery",
  "Snowflake",
  "ETL Pipelines",
  "Statistical Analysis",
  "Data Modeling",
  "PostgreSQL",
];

function JobEntryForm() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    post_name: "Data Analyst",
    organization_name: "",
    job_portal: "LinkedIn",
    official_url: "",
    location: "Bangalore",
    work_mode: "Remote",
    salary_range: "",
    application_start_date: new Date().toISOString().split("T")[0],
    status: "Applied",
    resume_version: "Data_Analyst_Resume.pdf",
    skills: "SQL, Python, Power BI, Excel",
    hr_contact: "",
    remarks: "",
  });

  const [selectedSkills, setSelectedSkills] = useState([
    "SQL",
    "Python",
    "Power BI",
    "Advanced Excel",
  ]);

  const [customSkillInput, setCustomSkillInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleRoleSelect = (role) => {
    setFormData((prev) => ({ ...prev, post_name: role }));
  };

  const handlePortalSelect = (portal) => {
    setFormData((prev) => ({ ...prev, job_portal: portal }));
  };

  const toggleSkill = (skill) => {
    let updated;
    if (selectedSkills.includes(skill)) {
      updated = selectedSkills.filter((s) => s !== skill);
    } else {
      updated = [...selectedSkills, skill];
    }
    setSelectedSkills(updated);
    setFormData((prev) => ({ ...prev, skills: updated.join(", ") }));
  };

  const addCustomSkill = (e) => {
    e.preventDefault();
    if (!customSkillInput.trim()) return;
    const skill = customSkillInput.trim();
    if (!selectedSkills.includes(skill)) {
      const updated = [...selectedSkills, skill];
      setSelectedSkills(updated);
      setFormData((prev) => ({ ...prev, skills: updated.join(", ") }));
    }
    setCustomSkillInput("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!formData.organization_name.trim()) {
      setErrorMessage("Company / Organization Name is required.");
      return;
    }
    if (!formData.post_name.trim()) {
      setErrorMessage("Job Role / Position is required.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await jobService.createJob({
        ...formData,
        skills: selectedSkills.join(", "),
      });

      if (res.success) {
        setSuccessMessage(
          `Application for "${formData.post_name}" at "${formData.organization_name}" saved successfully!`
        );
        // Reset primary fields
        setFormData((prev) => ({
          ...prev,
          organization_name: "",
          official_url: "",
          salary_range: "",
          remarks: "",
          hr_contact: "",
        }));
      } else {
        setErrorMessage(res.error || "Failed to save job application.");
      }
    } catch (err) {
      console.error("Submission error:", err);
      setErrorMessage(
        err.response?.data?.error || "Error connecting to backend server."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="job-entry-container">
      {/* Top Header Card */}
      <div className="entry-header-card">
        <div className="entry-header-left">
          <button
            className="btn-back-link"
            onClick={() => navigate("/career")}
          >
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </button>
          <div>
            <h1 className="entry-main-title">Log New Job Application</h1>
            <p className="entry-subtitle">
              Record details of your Data Analytics and tech job applications
            </p>
          </div>
        </div>

        <div className="entry-header-actions">
          <button
            className="btn-entry-history"
            onClick={() => navigate("/career/job-history")}
          >
            <History size={16} />
            <span>View Apply History</span>
          </button>
        </div>
      </div>

      {/* Success Alert */}
      {successMessage && (
        <div className="alert-box success">
          <div className="alert-content">
            <CheckCircle2 size={20} />
            <span>{successMessage}</span>
          </div>
          <div className="alert-actions">
            <button
              className="btn-alert-link"
              onClick={() => navigate("/career/job-history")}
            >
              Go to History →
            </button>
          </div>
        </div>
      )}

      {/* Error Alert */}
      {errorMessage && (
        <div className="alert-box error">
          <div className="alert-content">
            <AlertCircle size={20} />
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      {/* Form Form Card */}
      <form className="job-entry-form" onSubmit={handleSubmit}>
        {/* Section 1: Role & Company */}
        <div className="form-section">
          <div className="section-title-row">
            <Briefcase size={18} className="section-icon" />
            <h3 className="section-title">Position & Organization</h3>
          </div>

          {/* Quick Role Suggestions */}
          <div className="suggestions-block">
            <span className="suggestions-label">
              <Sparkles size={13} /> Quick Select Data Roles:
            </span>
            <div className="suggestion-chips">
              {ROLE_SUGGESTIONS.map((role) => (
                <button
                  type="button"
                  key={role}
                  className={`chip-btn ${
                    formData.post_name === role ? "active" : ""
                  }`}
                  onClick={() => handleRoleSelect(role)}
                >
                  {role}
                </button>
              ))}
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label required">Job Role / Title</label>
              <input
                type="text"
                name="post_name"
                required
                placeholder="e.g. Senior Data Analyst"
                value={formData.post_name}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label required">Company / Organization</label>
              <input
                type="text"
                name="organization_name"
                required
                placeholder="e.g. Swiggy, Amazon, Deloitte, Start-up"
                value={formData.organization_name}
                onChange={handleChange}
                className="form-input"
              />
            </div>
          </div>

          {/* Quick Portal Suggestions */}
          <div className="suggestions-block" style={{ marginTop: "16px" }}>
            <span className="suggestions-label">
              <Globe size={13} /> Applied Via Platform:
            </span>
            <div className="suggestion-chips">
              {PORTAL_SUGGESTIONS.map((portal) => (
                <button
                  type="button"
                  key={portal}
                  className={`chip-btn ${
                    formData.job_portal === portal ? "active" : ""
                  }`}
                  onClick={() => handlePortalSelect(portal)}
                >
                  {portal}
                </button>
              ))}
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Job Portal / Source</label>
              <input
                type="text"
                name="job_portal"
                placeholder="e.g. LinkedIn, Naukri, Referral"
                value={formData.job_portal}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Job Posting / Application Link</label>
              <div className="input-with-icon">
                <input
                  type="url"
                  name="official_url"
                  placeholder="https://linkedin.com/jobs/view/..."
                  value={formData.official_url}
                  onChange={handleChange}
                  className="form-input"
                />
                {formData.official_url && (
                  <a
                    href={formData.official_url}
                    target="_blank"
                    rel="noreferrer"
                    className="input-action-btn"
                    title="Open Link"
                  >
                    <LinkIcon size={15} />
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Location, Mode & Compensation */}
        <div className="form-section">
          <div className="section-title-row">
            <MapPin size={18} className="section-icon" />
            <h3 className="section-title">Location, Work Mode & Status</h3>
          </div>

          <div className="form-grid-3">
            <div className="form-group">
              <label className="form-label">Location / City</label>
              <input
                type="text"
                name="location"
                placeholder="e.g. Bangalore, Mumbai, Remote"
                value={formData.location}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Work Mode</label>
              <select
                name="work_mode"
                value={formData.work_mode}
                onChange={handleChange}
                className="form-select"
              >
                <option value="Remote">🌐 Remote</option>
                <option value="Hybrid">🏢 Hybrid</option>
                <option value="On-site">📍 On-site / In-Office</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Offered / Expected CTC</label>
              <input
                type="text"
                name="salary_range"
                placeholder="e.g. 12-16 LPA / ₹90,000/mo"
                value={formData.salary_range}
                onChange={handleChange}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-grid-2" style={{ marginTop: "14px" }}>
            <div className="form-group">
              <label className="form-label">Application Date</label>
              <input
                type="date"
                name="application_start_date"
                value={formData.application_start_date}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Application Status</label>
              <select
                name="status"
                value={formData.status}
                onChange={handleChange}
                className="form-select"
              >
                <option value="Applied">📝 Applied (Submitted)</option>
                <option value="Screening">⏳ Screening / HR Review</option>
                <option value="Technical Round">💻 Technical / Case Study</option>
                <option value="Interview">🤝 Interview Scheduled</option>
                <option value="Offer">🎉 Offer Received</option>
                <option value="Rejected">❌ Rejected</option>
                <option value="Ghosted">👻 Ghosted / No Response</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 3: Skills & Resume Tracking */}
        <div className="form-section">
          <div className="section-title-row">
            <Tag size={18} className="section-icon" />
            <h3 className="section-title">Key Skills & Resume Profile Used</h3>
          </div>

          <div className="skills-picker-block">
            <label className="form-label">Target Skills Matched</label>
            <div className="skills-badge-grid">
              {SKILL_SUGGESTIONS.map((skill) => {
                const isSelected = selectedSkills.includes(skill);
                return (
                  <button
                    type="button"
                    key={skill}
                    className={`skill-tag-btn ${isSelected ? "selected" : ""}`}
                    onClick={() => toggleSkill(skill)}
                  >
                    {isSelected && <Check size={12} />}
                    <span>{skill}</span>
                  </button>
                );
              })}
            </div>

            {/* Custom Skill Input */}
            <div className="custom-skill-row">
              <input
                type="text"
                placeholder="Add custom skill (e.g., Alteryx, Looker)..."
                value={customSkillInput}
                onChange={(e) => setCustomSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustomSkill(e);
                  }
                }}
                className="form-input-sm"
              />
              <button
                type="button"
                className="btn-add-skill"
                onClick={addCustomSkill}
              >
                + Add
              </button>
            </div>
          </div>

          <div className="form-grid-2" style={{ marginTop: "16px" }}>
            <div className="form-group">
              <label className="form-label">Resume / CV Version Used</label>
              <input
                type="text"
                name="resume_version"
                placeholder="e.g. Data_Analyst_Resume_v3.pdf"
                value={formData.resume_version}
                onChange={handleChange}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label className="form-label">HR / Contact / Referral Info</label>
              <input
                type="text"
                name="hr_contact"
                placeholder="e.g. Priya Sharma (HR LinkedIn) / Referred by Rahul"
                value={formData.hr_contact}
                onChange={handleChange}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-group" style={{ marginTop: "14px" }}>
            <label className="form-label">Job Notes / Interview Points</label>
            <textarea
              name="remarks"
              rows={3}
              placeholder="Enter key requirements, why you applied, project highlights, or interview preparation notes..."
              value={formData.remarks}
              onChange={handleChange}
              className="form-textarea"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="form-actions-footer">
          <button
            type="button"
            className="btn-form-reset"
            onClick={() => {
              setFormData({
                post_name: "Data Analyst",
                organization_name: "",
                job_portal: "LinkedIn",
                official_url: "",
                location: "Bangalore",
                work_mode: "Remote",
                salary_range: "",
                application_start_date: new Date().toISOString().split("T")[0],
                status: "Applied",
                resume_version: "Data_Analyst_Resume.pdf",
                skills: "SQL, Python, Power BI, Excel",
                hr_contact: "",
                remarks: "",
              });
              setSelectedSkills(["SQL", "Python", "Power BI", "Advanced Excel"]);
              setSuccessMessage(null);
              setErrorMessage(null);
            }}
          >
            Reset Fields
          </button>

          <button
            type="submit"
            className="btn-form-submit"
            disabled={submitting}
          >
            {submitting ? (
              <span>Saving Application...</span>
            ) : (
              <>
                <CheckCircle2 size={16} />
                <span>Save Job Application</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default JobEntryForm;