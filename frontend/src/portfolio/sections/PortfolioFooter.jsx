import { Zap, Terminal, Heart } from "lucide-react";
import { PORTFOLIO_CONFIG } from "../data/portfolioData";
import "./PortfolioFooter.css";

function PortfolioFooter({ onOpenLifeOS }) {
  return (
    <footer className="portfolio-footer-root">
      <div className="footer-container">
        <div className="footer-top-row">
          <div className="footer-identity">
            <span className="footer-name">{PORTFOLIO_CONFIG.name.toUpperCase()}</span>
            <span className="footer-role">Data Analyst → Data Scientist</span>
          </div>

          <button className="btn-footer-lifeos" onClick={onOpenLifeOS} data-cursor="lifeos">
            <Zap size={14} className="text-amber" />
            <span>OPEN LIFEOS</span>
          </button>
        </div>

        <div className="footer-bottom-row">
          <p className="footer-tagline">
            Built with curiosity, SQL, Python & data-driven discipline.
          </p>
          <span className="footer-copyright">
            &copy; {new Date().getFullYear()} {PORTFOLIO_CONFIG.name}. All systems operational.
          </span>
        </div>
      </div>
    </footer>
  );
}

export default PortfolioFooter;
