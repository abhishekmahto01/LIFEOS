import { useState } from "react";
import { PROBLEM_SOLVING_STEPS } from "../data/portfolioData";
import { Brain, ArrowDown, CheckCircle, Wrench, Sparkles } from "lucide-react";
import "./HowIThink.css";

function HowIThink() {
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const activeStep = PROBLEM_SOLVING_STEPS[activeStepIndex];

  return (
    <section id="how-i-think" className="how-i-think-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Brain size={14} className="section-icon text-cyan" />
          <span>04 // METHODOLOGY & PROBLEM-SOLVING</span>
        </div>
        <h2 className="section-title">HOW I THINK</h2>
        <p className="section-lead">
          A structured analytical mindset: translating ambiguity into quantifiable hypotheses, verifying data lineage, and extracting decisions that move metrics.
        </p>

        {/* Interactive Pipeline Stepper */}
        <div className="thinking-pipeline-container">
          {/* Top Horizontal Flow Sequence */}
          <div className="pipeline-steps-scroller">
            {PROBLEM_SOLVING_STEPS.map((step, idx) => {
              const isActive = activeStepIndex === idx;
              return (
                <button
                  key={step.step}
                  className={`pipeline-step-node ${isActive ? "active" : ""}`}
                  onClick={() => setActiveStepIndex(idx)}
                >
                  <span className="step-num">{step.step}</span>
                  <span className="step-phase-name">{step.phase}</span>
                  {idx !== PROBLEM_SOLVING_STEPS.length - 1 && <span className="step-connector">→</span>}
                </button>
              );
            })}
          </div>

          {/* Active Step Deep-Dive Card */}
          <div className="thinking-inspector-card">
            <div className="think-header-strip">
              <span className="think-phase-pill">PHASE {activeStep.step} // {activeStep.phase}</span>
              <span className="think-nav-hint">CLICK ANY STEP TO INSPECT APPROACH</span>
            </div>

            <h3 className="think-main-title">{activeStep.title}</h3>
            <p className="think-description">{activeStep.description}</p>

            <div className="think-tools-box">
              <div className="think-tools-header">
                <Wrench size={14} className="text-cyan" />
                <span>ANALYTICAL ARTIFACTS & TOOLS EMPLOYED:</span>
              </div>
              <div className="think-tools-pills">
                {activeStep.tools.map((tool, i) => (
                  <span key={i} className="think-tool-badge">
                    <CheckCircle size={12} className="text-emerald" />
                    <span>{tool}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default HowIThink;
