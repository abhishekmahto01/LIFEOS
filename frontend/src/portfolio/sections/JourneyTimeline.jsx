import { useState } from "react";
import { JOURNEY_MILESTONES } from "../data/portfolioData";
import { GitBranch, Calendar, CheckCircle2, Clock, Sparkles, ChevronRight } from "lucide-react";
import "./JourneyTimeline.css";

function JourneyTimeline() {
  const [selectedMilestone, setSelectedMilestone] = useState(JOURNEY_MILESTONES[JOURNEY_MILESTONES.length - 2]); // default to 2026

  return (
    <section id="journey" className="journey-timeline-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <GitBranch size={14} className="section-icon text-cyan" />
          <span>02 // CHRONOLOGICAL MILESTONES</span>
        </div>
        <h2 className="section-title">THE JOURNEY</h2>
        <p className="section-lead">
          From relational database querying and enterprise reporting to deep statistical learning and predictive data products.
        </p>

        {/* Timeline Layout Grid */}
        <div className="timeline-interactive-grid">
          {/* Left Branching Tree */}
          <div className="timeline-branch-col">
            {JOURNEY_MILESTONES.map((m, idx) => {
              const isSelected = selectedMilestone?.title === m.title;
              return (
                <div
                  key={idx}
                  className={`timeline-node-card ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedMilestone(m)}
                  data-cursor="pointer"
                >
                  <div className="node-marker-stem">
                    <div className="node-dot"></div>
                    {idx !== JOURNEY_MILESTONES.length - 1 && <div className="node-stem-line"></div>}
                  </div>

                  <div className="node-body">
                    <div className="node-year-badge">
                      <Calendar size={12} />
                      <span>{m.year} • {m.quarter}</span>
                      <span className={`node-status-pill ${m.status.toLowerCase().replace(" ", "-")}`}>
                        {m.status}
                      </span>
                    </div>

                    <h3 className="node-title">{m.title}</h3>
                    <span className="node-subtitle">{m.subtitle}</span>
                  </div>

                  <ChevronRight size={18} className="node-chevron" />
                </div>
              );
            })}
          </div>

          {/* Right Expanded Telemetry Detail Card */}
          <div className="timeline-detail-col">
            {selectedMilestone && (
              <div className="milestone-inspector-card">
                <div className="inspector-header">
                  <div className="inspector-time-tag">
                    <Clock size={14} />
                    <span>TIMELINE TELEMETRY • {selectedMilestone.year} ({selectedMilestone.quarter})</span>
                  </div>
                  <span className="inspector-status">{selectedMilestone.status}</span>
                </div>

                <h3 className="inspector-title">{selectedMilestone.title}</h3>
                <span className="inspector-sub">{selectedMilestone.subtitle}</span>

                <div className="inspector-desc-box">
                  <p>{selectedMilestone.description}</p>
                </div>

                {/* Key Highlight */}
                <div className="inspector-highlight-card">
                  <Sparkles size={16} className="text-amber" />
                  <div>
                    <span className="highlight-tag">KEY OUTCOME / IMPACT</span>
                    <p className="highlight-text">{selectedMilestone.highlight}</p>
                  </div>
                </div>

                {/* Associated Technologies */}
                <div className="inspector-skills-group">
                  <span className="skills-group-lbl">ASSOCIATED COMPETENCIES:</span>
                  <div className="skills-pills-wrap">
                    {selectedMilestone.skills.map((s, i) => (
                      <span key={i} className="inspector-skill-pill">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default JourneyTimeline;
