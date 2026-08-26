import { useState } from "react";
import { ArrowRight, CheckCircle2, ChevronDown, Sparkles, RefreshCw, Mail } from "lucide-react";
import "./ConsultationMatrixSection.css";

export default function ConsultationMatrixSection() {
  const [formData, setFormData] = useState({
    email: "",
    businessDuration: "0–1 year",
    scalingChallenge: "Data Infrastructure & Pipelines",
    marketingSpend: "$5,000 - $15,000 / month",
    annualRevenue: "$0 - $100k",
    runningAds: "No",
    notes: ""
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const durationOptions = ["0–1 year", "1–3 years", "3–5 years", "5+ years", "Stealth / New Project"];
  const challengeOptions = [
    "Data Infrastructure & Pipelines",
    "Predictive ML & Analytics Systems",
    "Executive BI & Real-Time Dashboards",
    "Brand & Full-Stack Application",
    "What's scale up / Strategy Discovery"
  ];
  const spendOptions = ["Select monthly spend", "< $5,000 / mo", "$5,000 - $15,000 / mo", "$15,000 - $50,000 / mo", "$50,000+ / mo"];
  const revenueOptions = ["$0 - $100k", "$100k - $500k", "$500k - $2M", "$2M - $10M", "$10M+"];
  const adsOptions = ["No", "Yes — Active Multi-channel", "Planning to launch soon", "Algorithmic Inbound Only"];

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.email || !formData.email.includes("@")) {
      alert("Please provide a valid email address.");
      return;
    }

    setIsSubmitting(true);

    setTimeout(() => {
      setIsSubmitting(false);
      setIsSuccess(true);
    }, 1000);
  };

  return (
    <section id="consultation" className="consultation-matrix-section">
      <div className="consultation-content-container">
        
        {/* Header Block */}
        <div className="consultation-header-block">
          <div className="consultation-badge">
            <Sparkles size={14} className="text-orange" />
            <span>INTERACTIVE CONSULTATION MATRIX</span>
          </div>
          <h2 className="consultation-title">
            Let&apos;s Architect Your Growth &amp; Data Systems
          </h2>
          <p className="consultation-sub">
            Fill out your project coordinates below to schedule a direct strategic deep-dive with Abhishek.
          </p>
        </div>

        {/* 6-Field Inquiry Matrix Form (Matching Reference Image 2) */}
        {!isSuccess ? (
          <form className="consultation-form-grid" onSubmit={handleSubmit}>
            
            {/* COLUMN 1 */}
            <div className="form-column">
              {/* Field 1: YOUR EMAIL* */}
              <div className="matrix-form-group">
                <label className="matrix-label">YOUR EMAIL*</label>
                <input 
                  type="email" 
                  className="matrix-input-field" 
                  placeholder="john@example.com"
                  value={formData.email}
                  onChange={(e) => handleChange("email", e.target.value)}
                  required
                />
              </div>

              {/* Field 2: WHAT'S YOUR BIGGEST CHALLENGE IN SCALING RIGHT NOW? */}
              <div className="matrix-form-group">
                <label className="matrix-label">
                  WHAT&apos;S YOUR BIGGEST CHALLENGE IN SCALING RIGHT NOW?
                </label>
                <div className="matrix-select-wrapper">
                  <select 
                    className="matrix-select-field"
                    value={formData.scalingChallenge}
                    onChange={(e) => handleChange("scalingChallenge", e.target.value)}
                  >
                    {challengeOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <ChevronDown size={18} className="select-chevron-icon" />
                </div>
              </div>

              {/* Field 3: WHAT'S YOUR ESTIMATED ANNUAL REVENUE? */}
              <div className="matrix-form-group">
                <label className="matrix-label">
                  WHAT&apos;S YOUR ESTIMATED ANNUAL REVENUE?
                </label>
                <div className="matrix-select-wrapper">
                  <select 
                    className="matrix-select-field"
                    value={formData.annualRevenue}
                    onChange={(e) => handleChange("annualRevenue", e.target.value)}
                  >
                    {revenueOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <ChevronDown size={18} className="select-chevron-icon" />
                </div>
              </div>
            </div>

            {/* COLUMN 2 */}
            <div className="form-column">
              {/* Field 4: HOW LONG HAVE YOU BEEN IN BUSINESS? */}
              <div className="matrix-form-group">
                <label className="matrix-label">
                  HOW LONG HAVE YOU BEEN IN BUSINESS?
                </label>
                <div className="matrix-select-wrapper">
                  <select 
                    className="matrix-select-field"
                    value={formData.businessDuration}
                    onChange={(e) => handleChange("businessDuration", e.target.value)}
                  >
                    {durationOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <ChevronDown size={18} className="select-chevron-icon" />
                </div>
              </div>

              {/* Field 5: HOW MUCH DO YOU SPEND ON MARKETING EACH MONTH? */}
              <div className="matrix-form-group">
                <label className="matrix-label">
                  HOW MUCH DO YOU SPEND ON MARKETING EACH MONTH?
                </label>
                <div className="matrix-select-wrapper">
                  <select 
                    className="matrix-select-field"
                    value={formData.marketingSpend}
                    onChange={(e) => handleChange("marketingSpend", e.target.value)}
                  >
                    {spendOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <ChevronDown size={18} className="select-chevron-icon" />
                </div>
              </div>

              {/* Field 6: ARE YOU RUNNING PAID ADS RIGHT NOW? */}
              <div className="matrix-form-group">
                <label className="matrix-label">
                  ARE YOU RUNNING PAID ADS RIGHT NOW?
                </label>
                <div className="matrix-select-wrapper">
                  <select 
                    className="matrix-select-field"
                    value={formData.runningAds}
                    onChange={(e) => handleChange("runningAds", e.target.value)}
                  >
                    {adsOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <ChevronDown size={18} className="select-chevron-icon" />
                </div>
              </div>
            </div>

            {/* Bottom Form Action Strip Matching Reference Image 2 */}
            <div className="consultation-action-row">
              <button 
                type="submit" 
                className="btn-submit-consultation"
                disabled={isSubmitting}
                data-cursor="pointer"
              >
                <span>{isSubmitting ? "Routing Telemetry..." : "Submit Consultation Request"}</span>
                <span className="submit-arrow-circle">
                  {isSubmitting ? <RefreshCw size={16} className="spin-icon" /> : <ArrowRight size={16} />}
                </span>
              </button>

              <div className="consultation-direct-contact">
                <Mail size={16} className="text-orange" />
                <span>Direct Dispatch: <a href="mailto:mahtoabhi07@gmail.com">mahtoabhi07@gmail.com</a></span>
              </div>
            </div>

          </form>
        ) : (
          /* Submission Success Card */
          <div className="consultation-success-card">
            <CheckCircle2 size={54} className="success-icon" />
            <h3 className="success-title">Consultation Request Dispatched!</h3>
            <p className="success-msg">
              Thank you for providing your project coordinates. Abhishek has received your parameters (<strong>{formData.scalingChallenge}</strong> for <strong>{formData.email}</strong>) and will follow up with an architectural roadmap within 24 hours.
            </p>
            <div className="success-meta-pills">
              <span className="success-pill">⚡ PRIORITY DISPATCH</span>
              <span className="success-pill">📍 INDIA / GLOBAL REMOTE</span>
              <span className="success-pill">🎯 TAILORED PROPOSAL</span>
            </div>
            <button 
              className="btn-reset-form"
              onClick={() => setIsSuccess(false)}
            >
              Submit Another Inquiry
            </button>
          </div>
        )}

      </div>
    </section>
  );
}
