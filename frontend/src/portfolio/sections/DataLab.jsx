import { useState } from "react";
import { DATA_LAB_PROJECTS } from "../data/portfolioData";
import { FlaskConical, Filter, ArrowUpRight, Code, Database, Sparkles, Activity, Layers } from "lucide-react";
import "./DataLab.css";

function DataLab({ onSelectProject }) {
  const [activeFilter, setActiveFilter] = useState("ALL");

  const filters = ["ALL", "SQL", "Python", "Power BI", "PostgreSQL", "Machine Learning"];

  const filteredProjects = DATA_LAB_PROJECTS.filter((p) => {
    if (activeFilter === "ALL") return true;
    return p.tags.some((t) => t.toLowerCase().includes(activeFilter.toLowerCase()));
  });

  return (
    <section id="data-lab" className="data-lab-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-row">
          <div>
            <div className="section-header-tag">
              <FlaskConical size={14} className="section-icon text-cyan" />
              <span>03 // PROJECT LABORATORY</span>
            </div>
            <h2 className="section-title">DATA LAB</h2>
            <p className="section-lead">
              Practical analytical experiments addressing real-world bottlenecks: urban logistics, customer churn mitigation, credit risk stratification, and quantified-self behavioral intelligence.
            </p>
          </div>

          {/* Filter Pills */}
          <div className="lab-filter-row">
            <Filter size={14} className="text-muted" />
            {filters.map((f) => (
              <button
                key={f}
                className={`btn-lab-filter ${activeFilter === f ? "active" : ""}`}
                onClick={() => setActiveFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Project Experiment Grid */}
        <div className="data-lab-grid">
          {filteredProjects.map((project) => (
            <div
              key={project.id}
              className="lab-project-card"
              onClick={() => onSelectProject(project)}
              data-cursor="view"
            >
              {/* Card Top Strip */}
              <div className="lab-card-top">
                <span className="lab-category-tag">{project.category}</span>
                <div className="lab-action-trigger">
                  <span>CASE STUDY</span>
                  <ArrowUpRight size={14} />
                </div>
              </div>

              {/* Title & Summary */}
              <h3 className="lab-project-title">{project.title}</h3>
              <p className="lab-project-summary">{project.summary}</p>

              {/* Interactive Visual Preview (Chart Simulation) */}
              <div className="lab-chart-preview-box">
                {project.chartType === "timeSeriesDemand" && (
                  <div className="mini-chart time-series">
                    <div className="chart-label-strip">
                      <span>HOURLY PICKUP DEMAND CURVE</span>
                      <span className="peak-tag">PEAK 20:00</span>
                    </div>
                    <svg viewBox="0 0 300 80" className="svg-curve">
                      <path
                        d="M 0,65 Q 40,60 80,45 T 160,20 T 220,10 T 300,50"
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth="3"
                      />
                      <path
                        d="M 0,65 Q 40,60 80,45 T 160,20 T 220,10 T 300,50 L 300,80 L 0,80 Z"
                        fill="url(#cyanGrad)"
                        opacity="0.25"
                      />
                      <defs>
                        <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#38bdf8" />
                          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                )}

                {project.chartType === "retentionWaterfall" && (
                  <div className="mini-chart retention-bars">
                    <div className="chart-label-strip">
                      <span>30-DAY COHORT DECAY VELOCITY</span>
                      <span className="metric-tag">ROC 0.87</span>
                    </div>
                    <div className="retention-bar-stack">
                      <div className="r-bar" style={{ height: "95%" }}><span>Day 0</span></div>
                      <div className="r-bar" style={{ height: "78%" }}><span>Day 7</span></div>
                      <div className="r-bar" style={{ height: "64%" }}><span>Day 14</span></div>
                      <div className="r-bar warning" style={{ height: "42%" }}><span>Day 30</span></div>
                      <div className="r-bar danger" style={{ height: "26%" }}><span>Churn</span></div>
                    </div>
                  </div>
                )}

                {project.chartType === "riskDistribution" && (
                  <div className="mini-chart risk-curve">
                    <div className="chart-label-strip">
                      <span>BORROWER DEFAULT PROBABILITY DENSITY</span>
                      <span className="metric-tag">GINI 0.74</span>
                    </div>
                    <svg viewBox="0 0 300 80" className="svg-curve">
                      <path
                        d="M 0,75 C 60,70 100,10 150,15 C 200,20 240,65 300,75"
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="3"
                      />
                      <path
                        d="M 0,75 C 60,70 100,10 150,15 C 200,20 240,65 300,75 L 300,80 L 0,80 Z"
                        fill="url(#redGrad)"
                        opacity="0.25"
                      />
                      <defs>
                        <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#ef4444" />
                          <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                )}

                {project.chartType === "habitCorrelation" && (
                  <div className="mini-chart habit-matrix">
                    <div className="chart-label-strip">
                      <span>365-DAY DISCIPLINE SCORING ENGINE</span>
                      <span className="metric-tag">r = +0.78</span>
                    </div>
                    <div className="matrix-dot-preview">
                      {Array.from({ length: 35 }).map((_, i) => (
                        <span
                          key={i}
                          className={`m-dot lvl-${(i % 4) + 1}`}
                        ></span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 4 KPIs Strip */}
              <div className="lab-kpi-row">
                {project.kpis.slice(0, 3).map((kpi, idx) => (
                  <div key={idx} className="lab-kpi-item">
                    <span className="lab-kpi-lbl">{kpi.label}</span>
                    <span className="lab-kpi-val">{kpi.value}</span>
                  </div>
                ))}
              </div>

              {/* Tech Stack Pills */}
              <div className="lab-tags-row">
                {project.tags.map((tag, idx) => (
                  <span key={idx} className="lab-tag-pill">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default DataLab;
