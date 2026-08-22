import { useState } from "react";
import { PORTFOLIO_CONFIG } from "../data/portfolioData";
import { Mail, FileText, Send, CheckCircle2, MessageSquare, Sparkles, Globe, ExternalLink } from "lucide-react";
import "./ContactSection.css";

function ContactSection() {
  const [formSent, setFormSent] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    problemStatement: "",
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.email || !formData.problemStatement) return;

    setFormSent(true);
    setTimeout(() => {
      setFormData({ name: "", email: "", problemStatement: "" });
      setFormSent(false);
    }, 4000);
  };

  return (
    <section id="contact" className="contact-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <MessageSquare size={14} className="section-icon text-cyan" />
          <span>11 // DIRECT COMMUNICATIONS</span>
        </div>

        <div className="contact-header-block">
          <h2 className="section-title">HAVE A DATA PROBLEM?</h2>
          <p className="contact-manifesto">
            &ldquo;Let’s turn it into a question worth answering.&rdquo;
          </p>
        </div>

        <div className="contact-channels-grid">
          {/* Left: Direct Channel Buttons & Resume */}
          <div className="contact-buttons-col">
            <span className="col-subheading">ESTABLISH DIRECT CHANNEL:</span>

            <a
              href={`mailto:${PORTFOLIO_CONFIG.email}`}
              className="btn-channel email"
              data-cursor="pointer"
            >
              <div className="channel-icon-wrap">
                <Mail size={20} />
              </div>
              <div className="channel-text">
                <span className="channel-lbl">EMAIL INBOX</span>
                <span className="channel-val">{PORTFOLIO_CONFIG.email}</span>
              </div>
            </a>

            <a
              href={PORTFOLIO_CONFIG.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-channel github"
              data-cursor="pointer"
            >
              <div className="channel-icon-wrap">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
              </div>
              <div className="channel-text">
                <span className="channel-lbl">GITHUB CODE REPOSITORIES</span>
                <span className="channel-val">abhishekmahto01</span>
              </div>
            </a>

            <a
              href={PORTFOLIO_CONFIG.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-channel linkedin"
              data-cursor="pointer"
            >
              <div className="channel-icon-wrap">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                </svg>
              </div>
              <div className="channel-text">
                <span className="channel-lbl">LINKEDIN PROFESSIONAL</span>
                <span className="channel-val">Connect on LinkedIn</span>
              </div>
            </a>

            <button
              className="btn-channel resume"
              onClick={() => alert("Resume document ready for review! Contact via email for direct PDF copy.")}
              data-cursor="pointer"
            >
              <div className="channel-icon-wrap">
                <FileText size={20} />
              </div>
              <div className="channel-text">
                <span className="channel-lbl">CURRICULUM VITAE</span>
                <span className="channel-val">Download / Request Resume</span>
              </div>
            </button>
          </div>

          {/* Right: Quick Data Problem Dispatcher Form */}
          <div className="contact-form-col">
            <div className="problem-dispatcher-card">
              <div className="dispatcher-header">
                <Sparkles size={16} className="text-cyan" />
                <span>DATA PROBLEM DISPATCHER</span>
              </div>

              {formSent ? (
                <div className="form-success-state">
                  <CheckCircle2 size={36} className="text-emerald" />
                  <h4>Transmission Received!</h4>
                  <p>Thank you for reaching out. I will review your data problem statement and follow up shortly.</p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="dispatcher-form">
                  <div className="form-group">
                    <label className="form-lbl">YOUR NAME / ORGANIZATION</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. Lead Analytics Recruiter / Data Team"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-lbl">CONTACT EMAIL *</label>
                    <input
                      type="email"
                      required
                      className="form-input"
                      placeholder="e.g. team@company.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-lbl">THE DATA PROBLEM OR INQUIRY *</label>
                    <textarea
                      required
                      rows={4}
                      className="form-textarea"
                      placeholder="Describe the decision, metric bottleneck, or role requirement..."
                      value={formData.problemStatement}
                      onChange={(e) => setFormData({ ...formData, problemStatement: e.target.value })}
                    ></textarea>
                  </div>

                  <button type="submit" className="btn-dispatch-message" data-cursor="pointer">
                    <Send size={16} />
                    <span>DISPATCH DATA INQUIRY</span>
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default ContactSection;
