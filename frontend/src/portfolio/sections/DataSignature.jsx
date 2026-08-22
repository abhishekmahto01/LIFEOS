import { DATA_SIGNATURE_METRICS, SKILL_PROGRESS_METERS } from "../data/portfolioData";
import { Database, Activity, Sparkles, TrendingUp, Layers } from "lucide-react";
import "./DataSignature.css";

function DataSignature() {
  return (
    <section id="my-data" className="data-signature-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Database size={14} className="section-icon text-cyan" />
          <span>01 // PERSONAL DATA SIGNATURE</span>
        </div>
        <h2 className="section-title">MY DATA</h2>
        <p className="section-lead">
          I don’t just memorize tools. I use data to understand real problems, discover hidden patterns, and construct defensible decisions.
        </p>

        {/* 4 Live Metric Cards */}
        <div className="signature-metrics-grid">
          {DATA_SIGNATURE_METRICS.map((metric, i) => (
            <div key={i} className="sig-metric-card">
              <div className="sig-metric-top">
                <span className="sig-metric-lbl">{metric.label}</span>
                <span className="sig-metric-tag">{metric.change}</span>
              </div>
              <div className="sig-metric-main">
                <span className="sig-metric-val">{metric.value}</span>
                <span className="sig-metric-unit">{metric.unit}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Skill Progress & Proficiency Matrix */}
        <div className="signature-meters-box">
          <div className="meters-box-header">
            <div className="meters-title-group">
              <Layers size={16} className="text-cyan" />
              <span>CORE TECHNICAL COMPETENCY & EXECUTION DEPTH</span>
            </div>
            <span className="meters-audit-tag">VERIFIED BY CASE STUDIES</span>
          </div>

          <div className="meters-grid">
            {SKILL_PROGRESS_METERS.map((meter, i) => (
              <div key={i} className="meter-row-item">
                <div className="meter-info-line">
                  <div className="meter-name-wrap">
                    <span className="meter-name">{meter.name}</span>
                    <span className="meter-tier-badge">{meter.tier}</span>
                  </div>
                  <span className="meter-percent-val">{meter.percent}%</span>
                </div>

                {/* Visual Block Meter */}
                <div className="meter-track">
                  <div
                    className="meter-fill"
                    style={{ width: `${meter.percent}%` }}
                  ></div>
                </div>

                <span className="meter-desc">{meter.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default DataSignature;
