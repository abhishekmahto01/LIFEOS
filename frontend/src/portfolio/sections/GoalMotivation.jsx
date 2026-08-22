import { Compass, Flame, Shield, Award, Target, Sparkles } from "lucide-react";
import "./GoalMotivation.css";

function GoalMotivation() {
  const goalVectors = [
    { label: "CAREER VELOCITY", percent: 80, color: "#38bdf8" },
    { label: "TECHNICAL SKILLS", percent: 85, color: "#06b6d4" },
    { label: "DISCIPLINE ADHERENCE", percent: 78, color: "#10b981" },
    { label: "DAILY CONSISTENCY", percent: 85, color: "#eab308" },
  ];

  return (
    <section className="goal-motivation-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Target size={14} className="section-icon text-red" />
          <span>09 // PERSONAL GOAL & DRIVE</span>
        </div>
        <h2 className="section-title">THE GOAL</h2>

        <div className="goal-card-container">
          <div className="goal-card-left">
            <span className="goal-badge">MISSION 2026 // VISION</span>
            <h3 className="goal-quote">&ldquo;Dreams are goals with a deadline.&rdquo;</h3>
            <p className="goal-subtext">
              The superbike is not merely a machine; it is an engineering benchmark for relentless discipline, sharp precision, and continuous personal acceleration.
            </p>

            {/* Conceptual Progress Gauges */}
            <div className="goal-gauges-stack">
              {goalVectors.map((v, i) => (
                <div key={i} className="gauge-item">
                  <div className="gauge-info">
                    <span className="gauge-lbl">{v.label}</span>
                    <span className="gauge-pct">{v.percent}%</span>
                  </div>
                  <div className="gauge-track">
                    <div
                      className="gauge-fill"
                      style={{ width: `${v.percent}%`, backgroundColor: v.color }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Silhouette & Blueprint Wireframe */}
          <div className="goal-card-right">
            <div className="superbike-blueprint-visual">
              {/* Minimalist Vector Superbike Wireframe Silhouette */}
              <svg viewBox="0 0 400 220" className="superbike-svg">
                {/* Wheels */}
                <circle cx="80" cy="150" r="45" fill="none" stroke="#38bdf8" strokeWidth="3" opacity="0.8" />
                <circle cx="80" cy="150" r="32" fill="none" stroke="rgba(56, 189, 248, 0.3)" strokeWidth="2" strokeDasharray="4 4" />
                <circle cx="80" cy="150" r="10" fill="#38bdf8" />

                <circle cx="320" cy="150" r="45" fill="none" stroke="#38bdf8" strokeWidth="3" opacity="0.8" />
                <circle cx="320" cy="150" r="32" fill="none" stroke="rgba(56, 189, 248, 0.3)" strokeWidth="2" strokeDasharray="4 4" />
                <circle cx="320" cy="150" r="10" fill="#38bdf8" />

                {/* Chassis Frame & Aggressive Tank Lines */}
                <path
                  d="M 80,150 L 140,110 L 190,115 L 240,80 L 290,105 L 320,150"
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                />
                <path
                  d="M 190,115 L 210,55 L 260,60 L 300,75 L 320,100"
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                {/* Tail section */}
                <path
                  d="M 110,95 L 170,105 L 140,140 Z"
                  fill="rgba(239, 68, 68, 0.2)"
                  stroke="#ef4444"
                  strokeWidth="1.5"
                />
                {/* Front Fork & Headlight Angle */}
                <line x1="290" y1="65" x2="320" y2="150" stroke="#38bdf8" strokeWidth="3.5" />
                <polygon points="295,70 330,85 305,95" fill="rgba(56, 189, 248, 0.4)" stroke="#38bdf8" strokeWidth="1.5" />

                {/* Ground telemetry grid */}
                <line x1="20" y1="195" x2="380" y2="195" stroke="rgba(255, 255, 255, 0.15)" strokeWidth="1" strokeDasharray="6 6" />
              </svg>

              <div className="superbike-specs-tag">
                <span>1000cc MOTORCYCLE BENCHMARK • 205 HP PRECISION</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default GoalMotivation;
