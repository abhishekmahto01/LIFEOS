import { useState } from "react";
import { RESUME_EXPERIENCE, EDUCATION_DATA } from "../data/portfolioData";
import { Briefcase, GraduationCap, ChevronDown, CheckCircle2, Calendar, Award } from "lucide-react";
import "./ExperienceResume.css";

function ExperienceResume() {
  const [expandedId, setExpandedId] = useState(RESUME_EXPERIENCE[0]?.id);

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <section className="experience-resume-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Briefcase size={14} className="section-icon text-cyan" />
          <span>10 // BACKGROUND & EDUCATION</span>
        </div>
        <h2 className="section-title">EXPERIENCE & EDUCATION</h2>
        <p className="section-lead">
          Structured background in enterprise database querying, business intelligence pipelines, and continuous data science research.
        </p>

        <div className="experience-education-grid">
          {/* Left: Expandable Work Experience Cards */}
          <div className="exp-column">
            <h3 className="sub-column-title">
              <Briefcase size={18} className="text-cyan" />
              <span>PRACTICAL EXPERIENCE</span>
            </h3>

            <div className="exp-cards-stack">
              {RESUME_EXPERIENCE.map((exp) => {
                const isExpanded = expandedId === exp.id;
                return (
                  <div
                    key={exp.id}
                    className={`exp-card ${isExpanded ? "expanded" : ""}`}
                    onClick={() => toggleExpand(exp.id)}
                    data-cursor="pointer"
                  >
                    <div className="exp-card-header">
                      <div>
                        <div className="exp-time-badge">
                          <Calendar size={12} />
                          <span>{exp.period}</span>
                        </div>
                        <h4 className="exp-role-title">{exp.role}</h4>
                        <span className="exp-company-name">{exp.company}</span>
                      </div>

                      <button className="btn-exp-toggle" aria-label="Toggle details">
                        <ChevronDown size={18} className={`chevron-icon ${isExpanded ? "rot-180" : ""}`} />
                      </button>
                    </div>

                    <p className="exp-summary-text">{exp.summary}</p>

                    {/* Expandable Key Contributions */}
                    {isExpanded && (
                      <div className="exp-expanded-body">
                        <span className="exp-body-heading">MEASURABLE CONTRIBUTIONS & RESPONSIBILITIES:</span>
                        <ul className="exp-points-list">
                          {exp.keyPoints.map((pt, i) => (
                            <li key={i}>
                              <CheckCircle2 size={14} className="point-check text-cyan" />
                              <span>{pt}</span>
                            </li>
                          ))}
                        </ul>

                        <div className="exp-skills-pills-row">
                          {exp.skills.map((s, i) => (
                            <span key={i} className="exp-skill-pill">
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Formal Education & Specialization */}
          <div className="edu-column">
            <h3 className="sub-column-title">
              <GraduationCap size={18} className="text-cyan" />
              <span>EDUCATION & SPECIALIZATION</span>
            </h3>

            <div className="edu-cards-stack">
              {EDUCATION_DATA.map((edu, idx) => (
                <div key={idx} className="edu-card">
                  <div className="edu-status-pill">{edu.status}</div>
                  <h4 className="edu-degree-title">{edu.degree}</h4>
                  <span className="edu-field-text">{edu.field}</span>
                  <p className="edu-focus-desc">{edu.focus}</p>
                </div>
              ))}

              <div className="cert-commitment-box">
                <Award size={20} className="text-amber" />
                <div>
                  <span className="cert-title">CONTINUOUS PRACTICE COMMITMENT</span>
                  <p className="cert-desc">Committed to daily Kaggle problem solving, SQL query optimization, and statistical model evaluation.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default ExperienceResume;
