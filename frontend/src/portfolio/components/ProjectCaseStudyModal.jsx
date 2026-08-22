import { useEffect, useState } from "react";
import { X, Code, CheckCircle, Database, Search, Target, Award, Copy, Check } from "lucide-react";
import "./ProjectCaseStudyModal.css";

function ProjectCaseStudyModal({ project, isOpen, onClose }) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState("all");

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "auto";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !project) return null;

  const handleCopyCode = () => {
    if (project.codeSnippet) {
      navigator.clipboard.writeText(project.codeSnippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const stages = [
    { num: "01", key: "problem", title: "THE PROBLEM", icon: Target, content: project.caseStudy?.problem },
    { num: "02", key: "data", title: "THE DATA", icon: Database, content: project.caseStudy?.data },
    { num: "03", key: "approach", title: "THE APPROACH", icon: Code, content: project.caseStudy?.approach },
    { num: "04", key: "analysis", title: "THE ANALYSIS", icon: Search, content: project.caseStudy?.analysis },
    { num: "05", key: "insight", title: "THE INSIGHT", icon: CheckCircle, content: project.caseStudy?.insight },
    { num: "06", key: "result", title: "THE RESULT & IMPACT", icon: Award, content: project.caseStudy?.result },
  ];

  return (
    <div className="case-study-backdrop" onClick={onClose}>
      <div className="case-study-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header Bar */}
        <div className="case-study-header">
          <div className="cs-header-meta">
            <div className="cs-category-badge">{project.category}</div>
            <h2 className="cs-title">{project.title}</h2>
          </div>
          <button className="btn-cs-close" onClick={onClose} aria-label="Close case study">
            <X size={20} />
          </button>
        </div>

        {/* Quick KPI Cards */}
        <div className="cs-kpis-grid">
          {project.kpis?.map((kpi, idx) => (
            <div key={idx} className="cs-kpi-card">
              <span className="cs-kpi-lbl">{kpi.label}</span>
              <span className="cs-kpi-val">{kpi.value}</span>
            </div>
          ))}
        </div>

        {/* Tech Stack Pills */}
        <div className="cs-stack-row">
          <span className="cs-stack-tag">TECH STACK:</span>
          {project.tags?.map((t, i) => (
            <span key={i} className="cs-tech-pill">
              {t}
            </span>
          ))}
        </div>

        {/* 6-Stage Narrative Framework */}
        <div className="cs-stages-timeline">
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <div key={stage.num} className="cs-stage-card">
                <div className="cs-stage-left">
                  <span className="cs-stage-num">{stage.num}</span>
                  <div className="cs-stage-icon-wrap">
                    <Icon size={16} />
                  </div>
                </div>
                <div className="cs-stage-content">
                  <h4 className="cs-stage-title">{stage.title}</h4>
                  <p className="cs-stage-desc">{stage.content}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Production Code Snippet Preview */}
        {project.codeSnippet && (
          <div className="cs-code-section">
            <div className="cs-code-header">
              <div className="cs-code-title">
                <Code size={14} />
                <span>CORE QUERY & ALGORITHM IMPLEMENTATION</span>
              </div>
              <button className="btn-copy-code" onClick={handleCopyCode}>
                {copied ? <Check size={14} className="text-emerald" /> : <Copy size={14} />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <pre className="cs-code-block">
              <code>{project.codeSnippet}</code>
            </pre>
          </div>
        )}

        {/* Footer */}
        <div className="cs-footer">
          <span className="cs-note">PROJECT EXPERIMENT LAB • ABHISHEK DATA PORTFOLIO</span>
          <button className="btn-cs-done" onClick={onClose}>
            Close Case Study
          </button>
        </div>
      </div>
    </div>
  );
}

export default ProjectCaseStudyModal;
