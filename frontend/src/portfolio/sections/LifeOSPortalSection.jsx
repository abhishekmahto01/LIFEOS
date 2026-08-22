import { Zap, Dumbbell, Briefcase, BookOpen, Code2, ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import "./LifeOSPortalSection.css";

function LifeOSPortalSection({ onOpenLifeOS }) {
  const modules = [
    {
      icon: Dumbbell,
      title: "FITNESS & HEALTH",
      desc: "Physical discipline tracking, workout adherence & energy output metrics.",
      tag: "25% Weight",
      color: "#3b82f6",
    },
    {
      icon: Briefcase,
      title: "JOB & CAREER PIPELINE",
      desc: "Application lifecycle management, status follow-ups & interview telemetry.",
      tag: "25% Weight",
      color: "#eab308",
    },
    {
      icon: BookOpen,
      title: "DS-365 & STUDY",
      desc: "Daily data science mastery curriculum, algorithmic exercises & research logs.",
      tag: "25% Weight",
      color: "#a855f7",
    },
    {
      icon: Code2,
      title: "PROJECTS & CODE",
      desc: "End-to-end data pipeline development, Git commits & case study delivery.",
      tag: "25% Weight",
      color: "#10b981",
    },
  ];

  return (
    <section id="lifeos" className="lifeos-portal-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Zap size={14} className="section-icon text-amber" />
          <span>08 // THE SECRET DOOR</span>
        </div>
        <h2 className="section-title">BEHIND THE ANALYST</h2>

        <div className="lifeos-manifesto-quote">
          <p className="quote-line-1">&ldquo;I analyze data professionally.&rdquo;</p>
          <p className="quote-line-2">&ldquo;I also analyze myself.&rdquo;</p>
        </div>

        {/* LifeOS Central Gateway Card */}
        <div className="lifeos-gateway-card">
          <div className="gateway-top-bar">
            <div className="gateway-brand">
              <div className="lifeos-bolt-box">
                <Zap size={20} className="text-amber" />
              </div>
              <div>
                <h3 className="lifeos-system-title">LIFEOS // PERSONAL OPERATING SYSTEM</h3>
                <span className="lifeos-system-sub">Discipline Analytics • Full-Stack PostgreSQL Engine • Mission 2026</span>
              </div>
            </div>
            <span className="gateway-live-pill">SYSTEM ONLINE</span>
          </div>

          {/* 4 Vector Modules */}
          <div className="lifeos-modules-grid">
            {modules.map((m, idx) => {
              const Icon = m.icon;
              return (
                <div key={idx} className="l-mod-card">
                  <div className="l-mod-top">
                    <div className="l-mod-icon-wrap" style={{ color: m.color, backgroundColor: `${m.color}15` }}>
                      <Icon size={20} />
                    </div>
                    <span className="l-mod-weight">{m.tag}</span>
                  </div>
                  <h4 className="l-mod-title">{m.title}</h4>
                  <p className="l-mod-desc">{m.desc}</p>
                </div>
              );
            })}
          </div>

          {/* Gateway Action Trigger */}
          <div className="gateway-action-bar">
            <div className="gateway-info-strip">
              <Sparkles size={16} className="text-cyan" />
              <span>Full-stack data tracking with automated scoring & interactive analytics.</span>
            </div>

            <button
              className="btn-launch-lifeos"
              data-cursor="lifeos"
              onClick={onOpenLifeOS}
            >
              <span>ENTER LIFEOS</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

export default LifeOSPortalSection;
