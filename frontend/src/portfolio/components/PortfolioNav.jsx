import { useState, useEffect } from "react";
import { Zap, Menu, X, ArrowRight } from "lucide-react";
import "./PortfolioNav.css";

function PortfolioNav({ onOpenLifeOS }) {
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState("hero");
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLinks = [
    { id: "hero-motion-container", label: "Home" },
    { id: "my-data", label: "About" },
    { id: "data-lab", label: "Projects" },
    { id: "how-i-think", label: "Workflow" },
    { id: "consultation", label: "Consultation" },
    { id: "contact", label: "Contact" },
  ];

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 30);

      const sections = navLinks.map((l) => document.getElementById(l.id)).filter(Boolean);
      const scrollPos = window.scrollY + 220;

      for (let i = sections.length - 1; i >= 0; i--) {
        if (sections[i].offsetTop <= scrollPos) {
          setActiveSection(navLinks[i].id);
          break;
        }
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id) => {
    setMobileOpen(false);
    const element = document.getElementById(id);
    if (element) {
      const offset = 70;
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
        {/* Brand Mark Matching Reference Image 1 */}
        <div className="nav-brand-group" onClick={() => scrollToSection("hero-motion-container")}>
          <span className="brand-logo-text">Folioblox</span>
          <span className="brand-dot"></span>
          <span className="brand-sub-badge">Abhishek</span>
        </div>

        {/* Centered Desktop Nav Menu Matching Reference Image 1 */}
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

        {/* Right CTA Matching Reference Image 1: White Pill with Orange Arrow Circle */}
        <div className="nav-actions">
          <button
            className="btn-nav-touch-pill"
            onClick={() => scrollToSection("consultation")}
            title="Book a strategic consultation"
            data-cursor="pointer"
          >
            <span>Get in touch</span>
            <span className="nav-orange-arrow">
              <ArrowRight size={14} />
            </span>
          </button>

          <button
            className="btn-nav-lifeos-mini"
            onClick={onOpenLifeOS}
            title="Launch LifeOS Platform"
            data-cursor="lifeos"
          >
            <Zap size={14} className="text-orange" />
            <span className="lifeos-text">LifeOS</span>
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
            <button className="btn-mobile-touch" onClick={() => scrollToSection("consultation")}>
              <span>Get in touch</span>
              <ArrowRight size={16} />
            </button>
            <button className="btn-mobile-lifeos" onClick={onOpenLifeOS}>
              <Zap size={16} />
              <span>ENTER LIFEOS PLATFORM</span>
            </button>
          </div>
        </div>
      )}
    </header>
  );
}

export default PortfolioNav;

