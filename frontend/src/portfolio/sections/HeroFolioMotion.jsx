import { useState } from "react";
import { ArrowRight, ChevronRight } from "lucide-react";
import "./HeroFolioMotion.css";

export default function HeroFolioMotion({ onOpenLifeOS, onExploreWork }) {
  const [activeRoleIndex, setActiveRoleIndex] = useState(0);

  const roles = [
    { 
      title: "Creative Director", 
      sub: "Brand, Systems & Design", 
      quote: "Great design should feel invisible.", 
      desc: "From logo to language, I build brands that connect and convert." 
    },
    { 
      title: "Data Scientist", 
      sub: "Predictive AI & Algorithms", 
      quote: "Great data should feel invisible.", 
      desc: "From raw signals to intelligent systems, I build architectures that connect and scale." 
    },
    { 
      title: "Full-Stack Architect", 
      sub: "React, Python & PostgreSQL", 
      quote: "Great engineering feels invisible.", 
      desc: "Building high-performance platforms that translate complex computations into instant user delight." 
    }
  ];

  const pillars = [
    { num: "#01", title: "Brand Strategy" },
    { num: "#02", title: "Brand Identity Design" },
    { num: "#03", title: "Packaging Design" },
    { num: "#04", title: "Creative Direction" }
  ];

  const currentRole = roles[activeRoleIndex];

  return (
    <section id="hero" className="hero-folio-section">
      <div className="hero-folio-container">
        
        {/* MAIN HERO CONTENT ROW (Folioblox Exact Layout - Reference Image 1) */}
        <div className="hero-folio-content-grid">
          
          {/* LEFT SIDE: "Hey, I'm a" + Large Bold Title */}
          <div className="hero-left-column">
            <div className="hero-greeting-tag">
              <span className="greeting-text">Hey, I&apos;m a</span>
              <div className="role-switch-pills">
                {roles.map((r, idx) => (
                  <button
                    key={r.title}
                    className={`role-mini-pill ${activeRoleIndex === idx ? "active" : ""}`}
                    onClick={() => setActiveRoleIndex(idx)}
                    data-cursor="pointer"
                  >
                    {idx === 0 ? "Creative" : idx === 1 ? "Data Science" : "FullStack"}
                  </button>
                ))}
              </div>
            </div>

            <h1 className="hero-main-title">
              {currentRole.title}
            </h1>

            <p className="hero-sub-statement">
              {currentRole.sub}
            </p>

            <div className="hero-cta-button-group">
              <a 
                href="#consultation" 
                className="btn-hero-orange-pill"
                onClick={(e) => {
                  e.preventDefault();
                  const target = document.getElementById("consultation");
                  if (target) target.scrollIntoView({ behavior: "smooth" });
                }}
                data-cursor="pointer"
              >
                <span>Get in touch</span>
                <span className="orange-arrow-circle">
                  <ArrowRight size={15} />
                </span>
              </a>

              <button 
                className="btn-hero-glass-link"
                onClick={onExploreWork}
                data-cursor="pointer"
              >
                <span>Explore Work</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {/* RIGHT SIDE: Bold Statement Quote Matching Reference Image 1 */}
          <div className="hero-right-column">
            <div className="hero-quote-block">
              <h2 className="hero-philosophy-quote">
                &ldquo;{currentRole.quote}&rdquo;
              </h2>
              <p className="hero-philosophy-sub">
                {currentRole.desc}
              </p>
            </div>
          </div>

        </div>

        {/* BOTTOM PILLAR BAR (Folioblox #01, #02, #03, #04 Strip) */}
        <div className="hero-bottom-pillars-bar">
          {pillars.map((p) => (
            <div key={p.num} className="pillar-item">
              <span className="pillar-number">{p.num}</span>
              <span className="pillar-title">{p.title}</span>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
}
