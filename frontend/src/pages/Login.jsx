import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import "./Login.css";
import logo from "../assets/images/lifeos-logo.png";

function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

        navigate("/dashboard");
      } else {
        setError(res.data.message || "Login failed");
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
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      handleSignIn();
    }
  };

  return (
    <div className="login-page">
      <div className="login-box">

        <div className="left-panel">
          <div className="brand-card">
            <img
              src={logo}
              alt="Life OS"
              className="logo"
            />
            <h2>Life OS</h2>
            <p>Organize • Simplify • Succeed</p>
          </div>
        </div>

        <div className="right-panel">
          <div className="login-form">
            <h1>Hello Again!</h1>
            <p>Welcome back, you've been missed.</p>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <input
              type="text"
              placeholder="Enter User ID"
              value={username}
              onChange={(e) =>
                setUsername(e.target.value)
              }
              onKeyDown={handleKeyDown}
            />

            <div className="password-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="Enter Password"
                value={password}
                onChange={(e) =>
                  setPassword(e.target.value)
                }
                onKeyDown={handleKeyDown}
              />

              <span
                className="eye-icon"
                onClick={() =>
                  setShowPassword(!showPassword)
                }
              >
                {showPassword ? "🙈" : "👁"}
              </span>
            </div>

            <div className="login-options">
              <label>
                <input type="checkbox" />
                Remember Me
              </label>

              <a href="#">
                Forgot Password?
              </a>
            </div>

            <button
              onClick={handleSignIn}
              disabled={loading}
            >
              {loading
                ? "Signing In..."
                : "Sign In"}
            </button>

            <div className="footer-text">
              Life OS v1.0
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

export default Login;