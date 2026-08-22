import { CURRENTLY_BUILDING } from "../data/portfolioData";
import { Radio, Sparkles, ArrowUpRight, Activity } from "lucide-react";
import "./CurrentlyBuilding.css";

function CurrentlyBuilding({ onOpenLifeOS, onExploreWork }) {
  return (
    <section className="currently-building-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Radio size={14} className="section-icon text-emerald" />
          <span>07 // REAL-TIME ACTIVE INITIATIVES</span>
        </div>
        <div className="building-header-row">
          <h2 className="section-title">CURRENTLY BUILDING</h2>
          <div className="live-building-indicator">
            <span className="live-pulse-dot"></span>
            <span>● LIVE EXECUTION RADAR</span>
          </div>
        </div>
        <p className="section-lead">
          Continuous iterative growth: daily algorithmic training, quantitative habit systems, and production analytical prototypes.
        </p>

        {/* 3 Active Radar Cards */}
        <div className="currently-building-grid">
          {CURRENTLY_BUILDING.map((item) => (
            <div
              key={item.id}
              className="building-card"
              onClick={() => {
                if (item.id === "lifeos-prod") onOpenLifeOS();
                if (item.id === "data-lab") onExploreWork();
              }}
              data-cursor="pointer"
            >
              <div className="building-card-top">
                <span className="building-tag-pill" style={{ color: item.color, borderColor: `${item.color}44`, backgroundColor: `${item.color}15` }}>
                  {item.tag}
                </span>
                <span className="building-badge-status">{item.badge}</span>
              </div>

              <h3 className="building-title">{item.title}</h3>
              <span className="building-subtitle">{item.subtitle}</span>

              <p className="building-desc">{item.desc}</p>

              <div className="building-card-footer">
                <span className="card-action-link" style={{ color: item.color }}>
                  <span>INSPECT INITIATIVE</span>
                  <ArrowUpRight size={14} />
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default CurrentlyBuilding;
