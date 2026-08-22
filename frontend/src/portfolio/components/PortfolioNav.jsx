import { useState, useEffect } from "react";
import { Zap, Menu, X, ArrowUpRight, Activity } from "lucide-react";
import "./PortfolioNav.css";

function PortfolioNav({ onOpenLifeOS }) {
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState("hero");
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLinks = [
    { id: "hero", label: "CONTROL ROOM" },
    { id: "my-data", label: "MY DATA" },
    { id: "journey", label: "JOURNEY" },
    { id: "data-lab", label: "DATA LAB" },
    { id: "how-i-think", label: "HOW I THINK" },
    { id: "skills", label: "SKILLS" },
    { id: "lifeos", label: "LIFEOS" },
    { id: "contact", label: "CONTACT" },
  ];

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 40);

      // Scroll spy
      const sections = navLinks.map((l) => document.getElementById(l.id)).filter(Boolean);
      const scrollPos = window.scrollY + 200;

      for (let i = sections.length - 1; i >= 0; i--) {
        if (sections[i].offsetTop <= scrollPos) {
          setActiveSection(navLinks[i].id);
          break;
        }
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id) => {
    setMobileOpen(false);
    const element = document.getElementById(id);
    if (element) {
      const offset = 80;
      const bodyRect = document.body.getBoundingClientRect().top;
      const elementRect = element.getBoundingClientRect().top;
      const elementPosition = elementRect - bodyRect;
      const offsetPosition = elementPosition - offset;

      window.scrollTo({
        top: offsetPosition,
        behavior: "smooth",
      });
    }
  };

  return (
    <header className={`portfolio-nav-bar ${scrolled ? "nav-scrolled" : ""}`}>
      <div className="nav-container">
        {/* Brand / Telemetry Identity */}
        <div className="nav-brand-group" onClick={() => scrollToSection("hero")}>
          <div className="brand-logo-hex">
            <span>A</span>
          </div>
          <div className="brand-meta">
            <span className="brand-name">ABHISHEK</span>
            <div className="brand-telemetry-status">
              <span className="pulse-beacon"></span>
              <span className="status-label">DATA ANALYST → DATA SCIENTIST</span>
            </div>
          </div>
        </div>

        {/* Desktop Nav Links */}
        <nav className="desktop-nav-menu">
          {navLinks.map((item) => (
            <button
              key={item.id}
              className={`nav-menu-link ${activeSection === item.id ? "active" : ""}`}
              onClick={() => scrollToSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {/* Action Button: Enter LifeOS */}
        <div className="nav-actions">
          <button
            className="btn-nav-lifeos"
            data-cursor="lifeos"
            onClick={onOpenLifeOS}
            title="Launch Personal Operating System"
          >
            <Zap size={14} className="nav-bolt" />
            <span>ENTER LIFEOS</span>
            <ArrowUpRight size={14} />
          </button>

          {/* Mobile Menu Toggle */}
          <button
            className="btn-mobile-nav-toggle"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle Navigation Menu"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="mobile-nav-drawer">
          <div className="mobile-nav-links">
            {navLinks.map((item) => (
              <button
                key={item.id}
                className={`mobile-nav-link ${activeSection === item.id ? "active" : ""}`}
                onClick={() => scrollToSection(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="mobile-nav-footer">
            <button className="btn-mobile-lifeos" onClick={onOpenLifeOS}>
              <Zap size={16} />
              <span>ENTER LIFEOS PLATFORM</span>
              <ArrowUpRight size={16} />
            </button>
          </div>
        </div>
      )}
    </header>
  );
}

export default PortfolioNav;
