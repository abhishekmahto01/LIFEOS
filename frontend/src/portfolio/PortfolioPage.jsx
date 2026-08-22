import { useState } from "react";
import PortfolioNav from "./components/PortfolioNav";
import CustomCursor from "./components/CustomCursor";
import LifeOSTransitionModal from "./components/LifeOSTransitionModal";
import ProjectCaseStudyModal from "./components/ProjectCaseStudyModal";

import HeroControlRoom from "./sections/HeroControlRoom";
import DataSignature from "./sections/DataSignature";
import JourneyTimeline from "./sections/JourneyTimeline";
import DataLab from "./sections/DataLab";
import HowIThink from "./sections/HowIThink";
import SkillMap from "./sections/SkillMap";
import CareerDatasetAnalytics from "./sections/CareerDatasetAnalytics";
import CurrentlyBuilding from "./sections/CurrentlyBuilding";
import LifeOSPortalSection from "./sections/LifeOSPortalSection";
import GoalMotivation from "./sections/GoalMotivation";
import ExperienceResume from "./sections/ExperienceResume";
import ContactSection from "./sections/ContactSection";
import PortfolioFooter from "./sections/PortfolioFooter";

import "./PortfolioPage.css";

function PortfolioPage() {
  const [isLifeOSWarpOpen, setIsLifeOSWarpOpen] = useState(false);
  const [selectedCaseStudyProject, setSelectedCaseStudyProject] = useState(null);

  const handleOpenLifeOS = () => {
    setIsLifeOSWarpOpen(true);
  };

  const handleExploreWork = () => {
    const el = document.getElementById("data-lab");
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div className="portfolio-master-root">
      {/* Minimal Desktop Cursor */}
      <CustomCursor />

      {/* Floating Telemetry Navigation Bar */}
      <PortfolioNav onOpenLifeOS={handleOpenLifeOS} />

      {/* Main Content Sections */}
      <main className="portfolio-main-content">
        {/* 01. Hero Data Control Room */}
        <HeroControlRoom
          onOpenLifeOS={handleOpenLifeOS}
          onExploreWork={handleExploreWork}
        />

        {/* 02. Personal Data Signature ("MY DATA") */}
        <DataSignature />

        {/* 03. Chronological Career & Learning Journey */}
        <JourneyTimeline />

        {/* 04. Data Lab & Project Experiments */}
        <DataLab onSelectProject={(p) => setSelectedCaseStudyProject(p)} />

        {/* 05. "How I Think" Data Science Problem Solving Flow */}
        <HowIThink />

        {/* 06. Hierarchical Skill Architecture Topology */}
        <SkillMap />

        {/* 07. "If My Career Were A Dataset" Analytics */}
        <CareerDatasetAnalytics />

        {/* 08. Currently Building Live Radar */}
        <CurrentlyBuilding
          onOpenLifeOS={handleOpenLifeOS}
          onExploreWork={handleExploreWork}
        />

        {/* 09. "Behind The Analyst" LifeOS Secret Door */}
        <LifeOSPortalSection onOpenLifeOS={handleOpenLifeOS} />

        {/* 10. The Goal & Motivation */}
        <GoalMotivation />

        {/* 11. Practical Experience & Education */}
        <ExperienceResume />

        {/* 12. "Have A Data Problem?" Direct Communications */}
        <ContactSection />
      </main>

      {/* Minimal Footer */}
      <PortfolioFooter onOpenLifeOS={handleOpenLifeOS} />

      {/* 6-Stage Immersive Project Case Study Modal */}
      <ProjectCaseStudyModal
        project={selectedCaseStudyProject}
        isOpen={Boolean(selectedCaseStudyProject)}
        onClose={() => setSelectedCaseStudyProject(null)}
      />

      {/* Cinematic Motorcycle Headlight Warp Transition Modal */}
      <LifeOSTransitionModal
        isOpen={isLifeOSWarpOpen}
        onClose={() => setIsLifeOSWarpOpen(false)}
        destination="/login"
      />
    </div>
  );
}

export default PortfolioPage;
