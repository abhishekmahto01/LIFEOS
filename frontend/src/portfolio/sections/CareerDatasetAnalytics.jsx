import { CAREER_DATASET } from "../data/portfolioData";
import { BarChart3, PieChart, Clock, Info, ShieldCheck } from "lucide-react";
import "./CareerDatasetAnalytics.css";

function CareerDatasetAnalytics() {
  return (
    <section className="career-dataset-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <BarChart3 size={14} className="section-icon text-cyan" />
          <span>06 // QUANTITATIVE PROFILE METRICS</span>
        </div>
        <h2 className="section-title">IF MY CAREER WERE A DATASET</h2>
        <p className="section-lead">
          A personal data visualization snapshot of analytical focus areas, competency weightings, and weekly deep work cadences.
        </p>

        {/* 3 Visual Analytics Panels */}
        <div className="career-analytics-grid">
          {/* Panel 1: Skill Distribution */}
          <div className="analytics-card">
            <div className="card-top-strip">
              <span className="card-top-title">SKILL COMPETENCY DISTRIBUTION</span>
              <span className="card-top-tag">WEIGHTED</span>
            </div>

            <div className="skill-distribution-stack">
              {CAREER_DATASET.skillDistribution.map((item, idx) => (
                <div key={idx} className="skill-dist-row">
                  <div className="skill-dist-info">
                    <span className="dist-name">{item.skill}</span>
                    <span className="dist-val">{item.percentage}%</span>
                  </div>
                  <div className="dist-track">
                    <div
                      className="dist-fill"
                      style={{
                        width: `${item.percentage}%`,
                        backgroundColor: item.color,
                        boxShadow: `0 0 10px ${item.color}66`,
                      }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Panel 2: Focus Distribution */}
          <div className="analytics-card">
            <div className="card-top-strip">
              <span className="card-top-title">ANALYTICAL TIME & FOCUS ALLOCATION</span>
              <span className="card-top-tag">PROPORTION</span>
            </div>

            <div className="focus-distribution-list">
              {CAREER_DATASET.focusDistribution.map((item, idx) => (
                <div key={idx} className="focus-item-row">
                  <div className="focus-left">
                    <span className="focus-color-dot" style={{ backgroundColor: item.color }}></span>
                    <span className="focus-name">{item.area}</span>
                  </div>
                  <span className="focus-pct-tag">{item.weight}%</span>
                </div>
              ))}
            </div>

            {/* Visual Proportional Bar */}
            <div className="proportional-multi-bar">
              {CAREER_DATASET.focusDistribution.map((item, idx) => (
                <div
                  key={idx}
                  className="multi-segment"
                  style={{
                    width: `${item.weight}%`,
                    backgroundColor: item.color,
                  }}
                  title={`${item.area}: ${item.weight}%`}
                ></div>
              ))}
            </div>
          </div>

          {/* Panel 3: Weekly Deep Work Cadence */}
          <div className="analytics-card">
            <div className="card-top-strip">
              <span className="card-top-title">WEEKLY DEEP WORK & QUERY CADENCE</span>
              <span className="card-top-tag">7-DAY MATRIX</span>
            </div>

            <div className="cadence-bars-container">
              {CAREER_DATASET.weeklyProductivityCadence.map((d, idx) => (
                <div key={idx} className="cadence-day-col">
                  <span className="cadence-hrs">{d.deepWorkHours}h</span>
                  <div className="cadence-track">
                    <div
                      className="cadence-fill"
                      style={{ height: `${(d.deepWorkHours / 10) * 100}%` }}
                    ></div>
                  </div>
                  <span className="cadence-day-lbl">{d.day}</span>
                </div>
              ))}
            </div>

            <div className="cadence-footer-stat">
              <Clock size={12} className="text-cyan" />
              <span>Average 7.5+ hours dedicated daily to data problem-solving and model engineering.</span>
            </div>
          </div>
        </div>

        {/* Truthful Disclaimer Note */}
        <div className="dataset-disclaimer-note">
          <Info size={14} className="text-cyan" />
          <span>Note: Visualizations represent personal portfolio self-quantification and practice telemetry, not external standardized rankings.</span>
        </div>
      </div>
    </section>
  );
}

export default CareerDatasetAnalytics;
