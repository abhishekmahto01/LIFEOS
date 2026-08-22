import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, Sparkles, Terminal, Activity } from "lucide-react";
import "./LifeOSTransitionModal.css";

function LifeOSTransitionModal({ isOpen, onClose, destination = "/login" }) {
  const navigate = useNavigate();
  const [phase, setPhase] = useState(0); // 0: init, 1: road streams, 2: headlight beam, 3: warp

  useEffect(() => {
    if (!isOpen) {
      setPhase(0);
      return;
    }

    // Phase 1: Stream road acceleration (0ms)
    setPhase(1);

    // Phase 2: Dual motorcycle headlight beam ignition (350ms)
    const t2 = setTimeout(() => setPhase(2), 350);

    // Phase 3: Luminous hyperdrive warp flash (700ms)
    const t3 = setTimeout(() => setPhase(3), 700);

    // Phase 4: Route navigation (950ms)
    const t4 = setTimeout(() => {
      // Check if user is already logged in, route to /dashboard, else /login
      const user = localStorage.getItem("user");
      const targetRoute = user ? "/dashboard" : destination;
      navigate(targetRoute);
    }, 950);

    return () => {
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, [isOpen, navigate, destination]);

  if (!isOpen) return null;

  return (
    <div className={`lifeos-warp-portal phase-${phase}`}>
      {/* 1. Road Stream Lines */}
      <div className="road-stream-grid">
        {Array.from({ length: 18 }).map((_, i) => (
          <div
            key={i}
            className="road-line"
            style={{
              top: `${(i / 18) * 100}%`,
              animationDelay: `${(i % 5) * 0.08}s`,
            }}
          ></div>
        ))}
      </div>

      {/* 2. S1000 Dual Projector Headlight Beam */}
      <div className="s1000-headlight-lens-flare">
        <div className="lens-core"></div>
        <div className="lens-beam left"></div>
        <div className="lens-beam right"></div>
      </div>

      {/* 3. Telemetry HUD Overlay */}
      <div className="warp-hud-overlay">
        <div className="warp-brand-badge">
          <Zap size={18} className="warp-bolt" />
          <span>LIFEOS v2.0 • PROTOCOL ENGAGED</span>
        </div>
        <div className="warp-progress-text">
          <Terminal size={14} className="hud-icon" />
          <span>TRANSFERRING ANALYST CONTEXT → PERSONAL OPERATING SYSTEM</span>
        </div>
        <div className="warp-status-row">
          <span className="live-dot"></span>
          <span>S1000 RR MOTIVATION ENGINE • MISSION 2026</span>
        </div>
      </div>

      {/* 4. Whiteout Hyperdrive Flash */}
      <div className="hyperdrive-whiteout"></div>
    </div>
  );
}

export default LifeOSTransitionModal;
