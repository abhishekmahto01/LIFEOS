import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Zap, Lock, User, Eye, EyeOff, ArrowRight, Sparkles } from "lucide-react";
import "./Login.css";
import logo from "../assets/images/lifeos-logo.png";
import userRiderImg from "../assets/images/user-s1000-rider.jpg";
import ThemeToggle from "../components/ThemeToggle";

function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isAccelerating, setIsAccelerating] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);

  const canvasRef = useRef(null);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    // DEV ONLY AUTO LOGIN
    const userParam = searchParams.get("user");

    if (userParam) {
      const mockUser = {
        user_id: userParam.toLowerCase() === "admin" ? 1 : 2,
        username: userParam,
      };

      localStorage.setItem("user", JSON.stringify(mockUser));
      navigate("/dashboard");
    }
  }, [searchParams, navigate]);

  // Golden Sunset Dust, Gravel & Speed Warp Particle System
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animationFrameId;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Dust puffs behind rear wheel
    const dustCount = 45;
    const dustParticles = Array.from({ length: dustCount }, () => ({
      x: width * 0.32 + (Math.random() * 80 - 40),
      y: height * 0.76 + (Math.random() * 50 - 25),
      radius: Math.random() * 16 + 6,
      vx: -(Math.random() * 7 + 4),
      vy: -(Math.random() * 3 + 0.5),
      opacity: Math.random() * 0.45 + 0.2,
      color: Math.random() > 0.4 ? "rgba(217, 119, 6, 0.45)" : "rgba(180, 83, 9, 0.35)",
      grow: Math.random() * 0.4 + 0.2,
    }));

    // Flying gravel pebbles
    const pebbleCount = 20;
    const pebbles = Array.from({ length: pebbleCount }, () => ({
      x: width * 0.32 + (Math.random() * 40 - 20),
      y: height * 0.78 + (Math.random() * 30 - 15),
      radius: Math.random() * 3 + 1.5,
      vx: -(Math.random() * 9 + 6),
      vy: -(Math.random() * 5 + 1),
      gravity: 0.15,
      opacity: 0.8,
      color: "#78350f",
    }));

    // Wind / Warp speed streaks
    const streakCount = 40;
    const speedStreaks = Array.from({ length: streakCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      len: Math.random() * 140 + 60,
      speed: Math.random() * 16 + 10,
      opacity: Math.random() * 0.35 + 0.1,
      color: "rgba(254, 215, 170, 0.7)",
      width: Math.random() * 2.5 + 0.8,
    }));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const speedMultiplier = isLaunching ? 5.5 : isAccelerating ? 1.7 : 1;

      // 1. Draw Dust Puffs behind Rear Wheel
      dustParticles.forEach((d) => {
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.radius, 0, Math.PI * 2);
        ctx.fillStyle = d.color;
        ctx.globalAlpha = d.opacity;
        ctx.fill();

        d.x += d.vx * speedMultiplier;
        d.y += d.vy;
        d.radius += d.grow * (isLaunching ? 1.8 : 1);
        d.opacity -= isLaunching ? 0.015 : 0.007;

        if (d.opacity <= 0 || d.x < 0) {
          d.x = width * 0.32 + (Math.random() * 40 - 20);
          d.y = height * 0.76 + (Math.random() * 30 - 15);
          d.radius = Math.random() * 14 + 6;
          d.opacity = Math.random() * 0.45 + 0.2;
          d.vx = -(Math.random() * 7 + 4);
        }
      });

      // 2. Draw Flying Gravel Pebbles
      pebbles.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.opacity;
        ctx.fill();

        p.x += p.vx * speedMultiplier;
        p.y += p.vy;
        p.vy += p.gravity;

        if (p.y > height + 20 || p.x < 0) {
          p.x = width * 0.32 + (Math.random() * 30 - 15);
          p.y = height * 0.78 + (Math.random() * 20 - 10);
          p.vy = -(Math.random() * 5 + 1);
          p.vx = -(Math.random() * 9 + 6);
        }
      });

      // 3. Draw Sunset Warp Speed Streaks
      speedStreaks.forEach((s) => {
        ctx.beginPath();
        ctx.strokeStyle = s.color;
        ctx.globalAlpha = isLaunching ? Math.min(s.opacity * 2.2, 0.95) : s.opacity;
        ctx.lineWidth = isLaunching ? s.width * 2 : s.width;

        const currentLen = isLaunching ? s.len * 3.5 : s.len;
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - currentLen, s.y + currentLen * 0.05);
        ctx.stroke();

        s.x -= s.speed * speedMultiplier * 1.5;

        if (s.x < -currentLen) {
          s.x = width + Math.random() * 200;
          s.y = Math.random() * height;
        }
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isAccelerating, isLaunching]);

  const handleSignIn = async () => {
    setError("");

    if (!username || !password) {
      setError("Please enter both User ID and Password");
      return;
    }

    setLoading(true);

    try {
      const res = await axios.post("http://localhost:5000/api/login", {
        username,
        password,
      });

      if (res.data.success) {
        localStorage.setItem(
          "user",
          JSON.stringify(res.data.user)
        );

        // 🚀 TRIGGER CINEMATIC BIKE LAUNCH SEQUENCE
        setIsLaunching(true);

        // Smooth transition to Dashboard as the bike rockets across the screen
        setTimeout(() => {
          navigate("/dashboard");
        }, 1100);
      } else {
        setError(res.data.message || "Login failed");
        setLoading(false);
      }
    } catch (err) {
      if (
        err.response &&
        err.response.data &&
        err.response.data.message
      ) {
        setError(err.response.data.message);
      } else {
        setError("Server error, please try again later");
      }
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !loading && !isLaunching) {
      handleSignIn();
    }
  };

  return (
    <div
      className={`login-cinema-root ${isAccelerating ? "throttle-boost" : ""} ${isLaunching ? "launch-sequence-active" : ""}`}
      onMouseDown={() => !isLaunching && setIsAccelerating(true)}
      onMouseUp={() => !isLaunching && setIsAccelerating(false)}
      onTouchStart={() => !isLaunching && setIsAccelerating(true)}
      onTouchEnd={() => !isLaunching && setIsAccelerating(false)}
    >
      {/* 1. HILL CLIMB S1000 RIDER STAGE & DYNAMIC MOVEMENT */}
      <div className="hill-climb-stage">
        <div className={`s1000-vehicle-rig ${isLaunching ? "s1000-rocket-launch" : ""}`}>
          <div
            className="s1000-chassis-image"
            style={{ backgroundImage: `url(${userRiderImg})` }}
          >
            {/* Sunset solar flare pulse */}
            <div className="sunset-solar-flare"></div>
            {/* Dual LED Headlight glow */}
            <div className={`s1000-headlight-flare ${isLaunching ? "headlight-hyper-beam" : ""}`}></div>
            {/* Speed breeze stream */}
            <div className="sunset-speed-stream"></div>
          </div>
        </div>
      </div>

      {/* 2. DUST, GRAVEL & SPEED PARTICLE CANVAS */}
      <canvas ref={canvasRef} className="dust-particle-canvas" />

      {/* 3. DYNAMIC ATMOSPHERIC VIGNETTE */}
      <div className="cinema-stage-vignette"></div>

      {/* 4. WARP TRANSITION FLASH OVERLAY (Appears during launch sequence) */}
      <div className={`warp-transition-flash ${isLaunching ? "flash-active" : ""}`}>
        {isLaunching && (
          <div className="warp-hud-tag">
            <Sparkles size={20} className="warp-icon" />
            <span>MISSION 2026 ENGAGED • ENTERING SYSTEM...</span>
          </div>
        )}
      </div>

      {/* Top Floating Header */}
      <div className={`login-top-bar ${isLaunching ? "fade-out-ui" : ""}`}>
        <div className="cinema-brand-tag">
          <Zap size={16} className="text-bolt" />
          <span>MISSION 2026 • BMW S1000 RR</span>
        </div>
        <ThemeToggle />
      </div>

      {/* 5. CLEAN MINIMAL STAGE CONTENT */}
      <div className={`login-stage-container clean-layout ${isLaunching ? "fade-out-ui" : ""}`}>
        <div className="stage-spacer"></div>

        {/* Right Side: Themed Glassmorphic Login Card */}
        <div className="glass-login-box">
          <div className="login-card-header">
            <div className="login-card-logo">
              <img src={logo} alt="Life OS" className="card-logo-img" />
              <div>
                <h2 className="login-title">Life OS</h2>
                <span className="login-subtitle">System Access Portal</span>
              </div>
            </div>
          </div>

          {error && (
            <div className="login-alert-error">
              <span>{error}</span>
            </div>
          )}

          <div className="login-fields-stack">
            <div className="field-group">
              <label className="field-label">User ID / Username</label>
              <div className="input-icon-wrap">
                <User size={18} className="field-icon" />
                <input
                  type="text"
                  className="login-input"
                  placeholder="Enter User ID"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={loading || isLaunching}
                  autoComplete="username"
                />
              </div>
            </div>

            <div className="field-group">
              <label className="field-label">Access Password</label>
              <div className="input-icon-wrap">
                <Lock size={18} className="field-icon" />
                <input
                  type={showPassword ? "text" : "password"}
                  className="login-input"
                  placeholder="Enter Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={loading || isLaunching}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="btn-eye-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? "Hide password" : "Show password"}
                  disabled={loading || isLaunching}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="login-options-row">
              <label className="remember-label">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  disabled={loading || isLaunching}
                />
                <span>Remember Session</span>
              </label>

              <a
                href="#forgot"
                onClick={(e) => {
                  e.preventDefault();
                  alert("Contact administrator to reset password.");
                }}
                className="forgot-link"
              >
                Forgot Password?
              </a>
            </div>

            <button
              className="btn-login-ignite"
              onClick={handleSignIn}
              disabled={loading || isLaunching}
            >
              <span>{isLaunching ? "Launching Mission..." : loading ? "Authenticating..." : "Launch Mission"}</span>
              <ArrowRight size={18} className={isLaunching ? "arrow-launch-spin" : ""} />
            </button>
          </div>

          <div className="login-card-footer">
            <div className="system-status-indicator">
              <span className="status-blip"></span>
              <span>{isLaunching ? "S1000 RR 205HP Engaged" : "LifeOS Engine Online • v2.0"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;