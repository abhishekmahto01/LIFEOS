import { useEffect, useRef, useState } from "react";
import { Zap, Terminal, Activity, ArrowRight, ShieldCheck, Cpu, Database, Play } from "lucide-react";
import { PORTFOLIO_CONFIG, HERO_TELEMETRY } from "../data/portfolioData";
import "./HeroControlRoom.css";

function HeroControlRoom({ onOpenLifeOS, onExploreWork }) {
  const canvasRef = useRef(null);
  const [bootPhase, setBootPhase] = useState(0); // 0: init, 1: nodes, 2: telemetry, 3: ready

  // Boot sequence (< 1.4s total)
  useEffect(() => {
    const t1 = setTimeout(() => setBootPhase(1), 150);
    const t2 = setTimeout(() => setBootPhase(2), 500);
    const t3 = setTimeout(() => setBootPhase(3), 900);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  // Subtle Interactive Data Canvas Network
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animationFrameId;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    const pointCount = window.innerWidth < 768 ? 30 : 65;
    const points = Array.from({ length: pointCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      radius: Math.random() * 2 + 1,
    }));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw connecting lines
      for (let i = 0; i < points.length; i++) {
        for (let j = i + 1; j < points.length; j++) {
          const dx = points[i].x - points[j].x;
          const dy = points[i].y - points[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 130) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(56, 189, 248, ${0.18 * (1 - dist / 130)})`;
            ctx.lineWidth = 0.8;
            ctx.moveTo(points[i].x, points[i].y);
            ctx.lineTo(points[j].x, points[j].y);
            ctx.stroke();
          }
        }
      }

      // Draw points
      points.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(56, 189, 248, 0.6)";
        ctx.fill();

        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <section id="hero" className={`hero-control-room-section boot-phase-${bootPhase}`}>
      {/* Background Interactive Data Grid & Nodes Canvas */}
      <canvas ref={canvasRef} className="hero-data-canvas" />
      <div className="hero-grid-ambient-overlay"></div>

      <div className="hero-control-container">
        {/* Top Control Bar Indicator */}
        <div className="hero-telemetry-tag">
          <div className="telemetry-ping">
            <span className="ping-dot"></span>
            <span className="ping-text">{HERO_TELEMETRY.systemStatus}</span>
          </div>
          <span className="telemetry-divider">/</span>
          <span className="telemetry-focus">{HERO_TELEMETRY.activeFocus}</span>
        </div>

        {/* Hero Identity Centerpiece */}
        <div className="hero-identity-block">
          <span className="hero-command-prompt">&gt; initiate_analyst_profile --verbose</span>
          <h1 className="hero-name-heading">{PORTFOLIO_CONFIG.name.toUpperCase()}</h1>
          <div className="hero-role-badge-row">
            <span className="hero-role-current">DATA ANALYST</span>
            <span className="hero-role-arrow">→</span>
            <span className="hero-role-target">DATA SCIENTIST</span>
          </div>
          <p className="hero-core-manifesto">
            &ldquo;{PORTFOLIO_CONFIG.tagline}&rdquo;
          </p>
        </div>

        {/* The Live Data Control Room Telemetry Console */}
        <div className="hero-console-card">
          <div className="console-header-strip">
            <div className="console-title-group">
              <Terminal size={14} className="text-cyan" />
              <span>LIVE TELEMETRY MATRIX</span>
            </div>
            <div className="console-dots">
              <span className="c-dot red"></span>
              <span className="c-dot yellow"></span>
              <span className="c-dot green"></span>
            </div>
          </div>

          <div className="console-metrics-grid">
            <div className="c-metric-cell">
              <span className="cm-label">EXPERIENCE</span>
              <span className="cm-val text-cyan">{HERO_TELEMETRY.experienceYears} YRS</span>
              <span className="cm-sub">Active Learning & Work</span>
            </div>

            <div className="c-metric-cell">
              <span className="cm-label">PROJECTS BUILT</span>
              <span className="cm-val text-white">{HERO_TELEMETRY.projectsCount}</span>
              <span className="cm-sub">End-to-End Solutions</span>
            </div>

            <div className="c-metric-cell">
              <span className="cm-label">SQL PROFICIENCY</span>
              <span className="cm-val text-emerald">{HERO_TELEMETRY.sqlProficiency}</span>
              <span className="cm-sub">Advanced Queries & CTEs</span>
            </div>

            <div className="c-metric-cell">
              <span className="cm-label">PYTHON</span>
              <span className="cm-val text-amber">{HERO_TELEMETRY.pythonLevel}</span>
              <span className="cm-sub">Pandas • Scikit • ETL</span>
            </div>

            <div className="c-metric-cell">
              <span className="cm-label">POWER BI</span>
              <span className="cm-val text-cyan">{HERO_TELEMETRY.powerBiLevel}</span>
              <span className="cm-sub">DAX • Star Schema</span>
            </div>

            <div className="c-metric-cell">
              <span className="cm-label">POSTGRESQL</span>
              <span className="cm-val text-white">{HERO_TELEMETRY.postgresLevel}</span>
              <span className="cm-sub">Relational Architecture</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="hero-actions-row">
          <button
            className="btn-hero-primary"
            onClick={onExploreWork}
            data-cursor="pointer"
          >
            <span>EXPLORE DATA LAB</span>
            <ArrowRight size={16} />
          </button>

          <button
            className="btn-hero-secondary"
            onClick={onOpenLifeOS}
            data-cursor="lifeos"
          >
            <Zap size={16} className="btn-bolt-icon" />
            <span>ENTER LIFEOS PLATFORM</span>
          </button>
        </div>
      </div>
    </section>
  );
}

export default HeroControlRoom;
