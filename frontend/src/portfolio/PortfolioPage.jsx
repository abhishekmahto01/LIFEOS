import { useState, useEffect, useRef } from "react";
import PortfolioNav from "./components/PortfolioNav";
import CustomCursor from "./components/CustomCursor";
import LifeOSTransitionModal from "./components/LifeOSTransitionModal";
import ProjectCaseStudyModal from "./components/ProjectCaseStudyModal";

import HeroFolioMotion from "./sections/HeroFolioMotion";
import ConsultationMatrixSection from "./sections/ConsultationMatrixSection";
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
  
  // Whole-Page Scroll-Driven Face Motion State
  const [globalScrollProgress, setGlobalScrollProgress] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    let ticking = false;

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const scrollTop = window.scrollY || document.documentElement.scrollTop;
          const docHeight = document.documentElement.scrollHeight - window.innerHeight;
          const progress = docHeight > 0 ? Math.min(Math.max(scrollTop / docHeight, 0), 1) : 0;
          setGlobalScrollProgress(progress);
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleMouseMove = (e) => {
    const { clientX, clientY } = e;
    const { innerWidth, innerHeight } = window;
    const x = (clientX / innerWidth - 0.5) * 16;
    const y = (clientY / innerHeight - 0.5) * 16;
    setMousePos({ x, y });
  };

  const handleOpenLifeOS = () => {
    setIsLifeOSWarpOpen(true);
  };

  const handleExploreWork = () => {
    const el = document.getElementById("data-lab");
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  // --------------------------------------------------------------------------
  // WHOLE-PAGE LEFT-TO-RIGHT PHOTO MOTION MATHEMATICS:
  // Sequence based on user pictures:
  // 1. Hero (0% - 15% scroll): Face is at LEFT (offset -18vw to -8vw), sharp, prominent (Reference 1)
  // 2. About / Data (15% - 30% scroll): Face glides through center (-8vw to +8vw)
  // 3. Consultation (30% - 50% scroll): Face settles at RIGHT (+18vw to +26vw), glowing behind form (Reference 2)
  // 4. Projects / Skills / Journey (50% - 85% scroll): Face pans with subtle depth parallax (+12vw to -5vw)
  // 5. Contact / Footer (85% - 100% scroll): Face returns to balanced right posture (+16vw)
  // --------------------------------------------------------------------------
  let faceTranslateX = 0; // in vw
  let faceOpacity = 0.85;
  let faceScale = 1;

  if (globalScrollProgress < 0.15) {
    // Stage 1: Hero — Face on the LEFT
    const localP = globalScrollProgress / 0.15;
    faceTranslateX = -18 + localP * 10; // -18vw -> -8vw
    faceOpacity = 0.95 - localP * 0.15;
    faceScale = 1.05;
  } else if (globalScrollProgress < 0.35) {
    // Stage 2: Transition into Consultation — Glides from center to RIGHT
    const localP = (globalScrollProgress - 0.15) / 0.20;
    faceTranslateX = -8 + localP * 28; // -8vw -> +20vw
    faceOpacity = 0.8 - localP * 0.15;
    faceScale = 1.05 + localP * 0.05;
  } else if (globalScrollProgress < 0.55) {
    // Stage 3: Consultation Matrix — Settled at RIGHT (Reference Image 2)
    const localP = (globalScrollProgress - 0.35) / 0.20;
    faceTranslateX = 20 + localP * 6; // +20vw -> +26vw
    faceOpacity = 0.65;
    faceScale = 1.1;
  } else if (globalScrollProgress < 0.80) {
    // Stage 4: Data Lab & Skills — Gentle cinematic depth parallax
    const localP = (globalScrollProgress - 0.55) / 0.25;
    faceTranslateX = 26 - localP * 24; // +26vw -> +2vw
    faceOpacity = 0.45;
    faceScale = 1.05;
  } else {
    // Stage 5: Timeline & Contact — Smooth final sweep
    const localP = (globalScrollProgress - 0.80) / 0.20;
    faceTranslateX = 2 + localP * 16; // +2vw -> +18vw
    faceOpacity = 0.55;
    faceScale = 1.08;
  }

  return (
    <div className="portfolio-master-root" onMouseMove={handleMouseMove}>
      {/* Minimal Desktop Cursor */}
      <CustomCursor />

      {/* ========================================================================= */}
      {/* PERSISTENT WHOLE-PAGE CINEMATIC PHOTO & DUAL NEON AMBIENCE LAYER          */}
      {/* ========================================================================= */}
      <div className="global-photo-motion-stage">
        
        {/* Left Studio Magenta Ambient Glow */}
        <div 
          className="global-ambient-glow global-ambient-magenta"
          style={{
            transform: `translate(${mousePos.x * -0.5}px, ${mousePos.y * -0.5 + globalScrollProgress * 100}px)`
          }}
        />

        {/* Right Studio Crimson Ambient Glow */}
        <div 
          className="global-ambient-glow global-ambient-crimson"
          style={{
            transform: `translate(${mousePos.x * 0.5}px, ${mousePos.y * 0.5 - globalScrollProgress * 100}px)`
          }}
        />

        {/* The Continuous Motion Portrait Photo (Glides Left to Right as you scroll) */}
        <div 
          className="global-photo-actor"
          style={{
            transform: `translate3d(calc(${faceTranslateX}vw + ${mousePos.x * 0.4}px), ${mousePos.y * 0.3}px, 0) scale(${faceScale})`,
            opacity: faceOpacity,
          }}
        >
          <img 
            src="/portfolio/user_portrait.jpg" 
            alt="Abhishek - Portrait Background"
            className="global-portrait-image"
          />
          <div className="global-photo-vignette" />
        </div>

        {/* Global Dark Grid Mesh */}
        <div className="global-mesh-overlay" />
      </div>

      {/* Floating Telemetry Navigation Bar */}
      <PortfolioNav onOpenLifeOS={handleOpenLifeOS} />

      {/* Main Content Sections */}
      <main className="portfolio-main-content">
        {/* 01. Folio Hero Section (Typography & Actions with Left-Aligned Subject) */}
        <HeroFolioMotion
          onOpenLifeOS={handleOpenLifeOS}
          onExploreWork={handleExploreWork}
          scrollProgress={globalScrollProgress}
        />

        {/* 02. Personal Data Signature ("MY DATA / ABOUT") */}
        <DataSignature />

        {/* 03. Interactive Consultation & Strategic Scoping Matrix (Reference Image 2) */}
        <ConsultationMatrixSection />

        {/* 04. Data Lab & 6-Stage Project Case Studies */}
        <DataLab onSelectProject={(p) => setSelectedCaseStudyProject(p)} />

        {/* 05. "How I Think" Data Science & Creative Problem Solving Flow */}
        <HowIThink />

        {/* 06. Hierarchical Skill Architecture Topology */}
        <SkillMap />

        {/* 07. "If My Career Were A Dataset" Analytics */}
        <CareerDatasetAnalytics />

        {/* 08. Chronological Career & Learning Journey */}
        <JourneyTimeline />

        {/* 09. Currently Building Live Radar */}
        <CurrentlyBuilding
          onOpenLifeOS={handleOpenLifeOS}
          onExploreWork={handleExploreWork}
        />

        {/* 10. "Behind The Analyst" LifeOS Secret Portal */}
        <LifeOSPortalSection onOpenLifeOS={handleOpenLifeOS} />

        {/* 11. The Goal & Motivation */}
        <GoalMotivation />

        {/* 12. Practical Experience & Education */}
        <ExperienceResume />

        {/* 13. Direct Communications Contact Form */}
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
