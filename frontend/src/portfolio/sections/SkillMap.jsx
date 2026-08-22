import { useState } from "react";
import { SKILL_TREE_DATA } from "../data/portfolioData";
import { Network, Database, Code, BarChart3, Binary, CheckCircle2, ChevronRight } from "lucide-react";
import "./SkillMap.css";

function SkillMap() {
  const [selectedBranch, setSelectedBranch] = useState(SKILL_TREE_DATA.children[0]); // default to SQL

  return (
    <section id="skills" className="skill-map-section">
      <div className="section-container">
        {/* Section Header */}
        <div className="section-header-tag">
          <Network size={14} className="section-icon text-cyan" />
          <span>05 // HIERARCHICAL SKILL ARCHITECTURE</span>
        </div>
        <h2 className="section-title">SKILL MAP</h2>
        <p className="section-lead">
          An interactive technical topology showing how SQL, Python, Business Intelligence, and Statistical Modeling interconnect in my daily analytical workflow.
        </p>

        {/* Interactive Tree & Inspector Split */}
        <div className="skill-map-grid">
          {/* Left: Interactive Tree Nodes */}
          <div className="skill-tree-container">
            <div className="tree-root-card">
              <div className="root-indicator">
                <Database size={16} className="text-cyan" />
                <span>ROOT NODE: {SKILL_TREE_DATA.name}</span>
              </div>
              <span className="root-sub">{SKILL_TREE_DATA.level}</span>
            </div>

            {/* 4 Child Branches */}
            <div className="tree-branches-stack">
              {SKILL_TREE_DATA.children.map((branch) => {
                const isSelected = selectedBranch?.id === branch.id;
                return (
                  <div
                    key={branch.id}
                    className={`tree-branch-card ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedBranch(branch)}
                    data-cursor="pointer"
                  >
                    <div className="branch-meta-left">
                      <div className="branch-icon-box">
                        {branch.id.includes("sql") && <Database size={18} />}
                        {branch.id.includes("python") && <Code size={18} />}
                        {branch.id.includes("bi") && <BarChart3 size={18} />}
                        {branch.id.includes("stats") && <Binary size={18} />}
                      </div>
                      <div>
                        <h4 className="branch-title">{branch.name}</h4>
                        <span className="branch-level-tag">{branch.level}</span>
                      </div>
                    </div>

                    <ChevronRight size={18} className="branch-arrow" />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Selected Branch Deep Dive Panel */}
          <div className="skill-inspector-col">
            {selectedBranch && (
              <div className="skill-inspector-card">
                <div className="si-header">
                  <div className="si-tag">
                    <span>INSPECTING NODE // {selectedBranch.name}</span>
                  </div>
                  <span className="si-level-badge">{selectedBranch.level}</span>
                </div>

                <h3 className="si-title">{selectedBranch.name}</h3>

                {/* Practical Production Use Case */}
                <div className="si-use-case-box">
                  <span className="si-box-label">PRACTICAL PRODUCTION APPLICATION:</span>
                  <p className="si-use-case-desc">{selectedBranch.useCase}</p>
                </div>

                {/* Sub-Techniques / Artifacts */}
                <div className="si-sub-items-box">
                  <span className="si-box-label">CORE METHODS & TECHNOLOGIES:</span>
                  <div className="si-pills-wrap">
                    {selectedBranch.subItems.map((sub, i) => (
                      <span key={i} className="si-sub-pill">
                        <CheckCircle2 size={12} className="text-cyan" />
                        <span>{sub}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Connected Real-World Projects */}
                <div className="si-projects-box">
                  <span className="si-box-label">EMPLOYED IN REAL-WORLD PROJECTS:</span>
                  <div className="si-project-tags-wrap">
                    {selectedBranch.projects.map((proj, i) => (
                      <span key={i} className="si-proj-tag">
                        {proj}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default SkillMap;
