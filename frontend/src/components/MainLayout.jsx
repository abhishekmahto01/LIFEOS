import { useState, useEffect } from "react";
import { useNavigate, Outlet } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";
import { useAuth } from "../context/AuthContext";
import authService from "../services/authService";

function MainLayout() {
  const navigate = useNavigate();
  const { user: authUser, logout } = useAuth();

  const [isModalOpen, setIsModalOpen] = useState(false);

  const [passwords, setPasswords] = useState({
    current: "",
    new: "",
    confirm: "",
  });

  const [currentTime, setCurrentTime] = useState("");

  const user = authUser || JSON.parse(localStorage.getItem("user") || "{}");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();

      setCurrentTime(
        now.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };

    updateTime();

    const timer = setInterval(updateTime, 1000);

    return () => clearInterval(timer);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleChangePasswordSubmit = async (e) => {
    e.preventDefault();

    if (passwords.new !== passwords.confirm) {
      alert("New password and Confirm Password do not match!");
      return;
    }

    try {
      const res = await authService.changePassword(passwords.current, passwords.new);
      if (res.success) {
        alert("Password changed successfully!");
        setPasswords({
          current: "",
          new: "",
          confirm: "",
        });
        setIsModalOpen(false);
      } else {
        alert(res.message || "Failed to change password.");
      }
    } catch (err) {
      alert(err.response?.data?.message || "Error changing password.");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "var(--bg-app, #090d16)",
        color: "var(--text-primary, #f8fafc)",
        transition: "background-color 0.25s ease, color 0.25s ease",
      }}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 24px",
          background: "var(--header-bg, #0b1120)",
          borderBottom: "1px solid var(--header-border, #1e293b)",
          boxShadow: "var(--shadow-card, 0 2px 10px rgba(0,0,0,0.2))",
          position: "sticky",
          top: 0,
          zIndex: 100,
          transition: "background-color 0.25s ease, border-color 0.25s ease",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        {/* Logo & Portfolio Shortcut */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            onClick={() => navigate("/dashboard")}
            style={{
              cursor: "pointer",
              fontWeight: "800",
              fontSize: "20px",
              color: "var(--accent-blue, #3b82f6)",
              border: "2px solid var(--accent-blue, #3b82f6)",
              borderRadius: "10px",
              padding: "6px 16px",
              letterSpacing: "-0.02em",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span>Life OS</span>
          </div>

          <button
            onClick={() => navigate("/portfolio")}
            style={{
              cursor: "pointer",
              fontWeight: "700",
              fontSize: "12px",
              color: "#38bdf8",
              background: "rgba(56, 189, 248, 0.12)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              borderRadius: "8px",
              padding: "7px 12px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title="Open Abhishek's Data Science Portfolio"
          >
            <span>PORTFOLIO ↗</span>
          </button>
        </div>

        {/* Right Section */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "14px",
            flexWrap: "wrap",
          }}
        >
          {/* Global Theme Toggle */}
          <ThemeToggle />

          {/* Time */}
          <div
            style={{
              fontSize: "15px",
              fontWeight: "600",
              color: "var(--text-secondary, #94a3b8)",
              minWidth: "90px",
              textAlign: "center",
            }}
          >
            {currentTime}
          </div>

          {/* User Profile */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background: "var(--bg-surface-elevated, #1e293b)",
              border: "1px solid var(--border-color, #334155)",
              borderRadius: "25px",
              padding: "4px 12px 4px 6px",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                background: "var(--accent-blue, #3b82f6)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: "bold",
                fontSize: "14px",
              }}
            >
              {(user?.username || "User").charAt(0).toUpperCase()}
            </div>

            <div>
              <div
                style={{
                  fontWeight: "700",
                  fontSize: "13px",
                  color: "var(--text-primary, #f8fafc)",
                  lineHeight: "1.2",
                }}
              >
                {user?.username || "User"}
              </div>

              <div
                style={{
                  fontSize: "11px",
                  color: "var(--text-muted, #64748b)",
                }}
              >
                Active
              </div>
            </div>
          </div>

          {/* Change Password */}
          <button
            onClick={() => setIsModalOpen(true)}
            style={{
              padding: "8px 14px",
              border: "1px solid var(--border-input, #334155)",
              borderRadius: "8px",
              background: "var(--bg-surface-elevated, #1e293b)",
              color: "var(--text-primary, #f8fafc)",
              cursor: "pointer",
              fontWeight: "600",
              fontSize: "13px",
              transition: "all 0.2s ease",
            }}
          >
            Password
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            style={{
              padding: "8px 14px",
              background: "#dc2626",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              fontWeight: "700",
              fontSize: "13px",
              transition: "opacity 0.2s ease",
            }}
          >
            Logout
          </button>
        </div>
      </header>

      {/* Page Content */}
      <main
        style={{
          flex: 1,
          padding: "24px",
          maxWidth: "100%",
        }}
      >
        <Outlet />
      </main>

      {/* Change Password Modal */}
      {isModalOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 9999,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #0f172a)",
              color: "var(--text-primary, #f8fafc)",
              padding: "26px",
              borderRadius: "16px",
              width: "100%",
              maxWidth: "420px",
              boxShadow: "var(--shadow-popover, 0 10px 40px rgba(0,0,0,0.5))",
              border: "1px solid var(--border-card, #334155)",
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: "20px", fontSize: "18px", fontWeight: "800" }}>
              Change Password
            </h3>

            <form onSubmit={handleChangePasswordSubmit}>
              <div style={{ marginBottom: "14px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "6px",
                    fontWeight: "600",
                    fontSize: "13px",
                    color: "var(--text-secondary, #cbd5e1)",
                  }}
                >
                  Current Password
                </label>

                <input
                  type="password"
                  required
                  value={passwords.current}
                  onChange={(e) =>
                    setPasswords({
                      ...passwords,
                      current: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: "1px solid var(--border-input, #334155)",
                    borderRadius: "8px",
                    background: "var(--bg-input, #0b1120)",
                    color: "var(--text-primary, #f8fafc)",
                    outline: "none",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div style={{ marginBottom: "14px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "6px",
                    fontWeight: "600",
                    fontSize: "13px",
                    color: "var(--text-secondary, #cbd5e1)",
                  }}
                >
                  New Password
                </label>

                <input
                  type="password"
                  required
                  value={passwords.new}
                  onChange={(e) =>
                    setPasswords({
                      ...passwords,
                      new: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: "1px solid var(--border-input, #334155)",
                    borderRadius: "8px",
                    background: "var(--bg-input, #0b1120)",
                    color: "var(--text-primary, #f8fafc)",
                    outline: "none",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "6px",
                    fontWeight: "600",
                    fontSize: "13px",
                    color: "var(--text-secondary, #cbd5e1)",
                  }}
                >
                  Confirm Password
                </label>

                <input
                  type="password"
                  required
                  value={passwords.confirm}
                  onChange={(e) =>
                    setPasswords({
                      ...passwords,
                      confirm: e.target.value,
                    })
                  }
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: "1px solid var(--border-input, #334155)",
                    borderRadius: "8px",
                    background: "var(--bg-input, #0b1120)",
                    color: "var(--text-primary, #f8fafc)",
                    outline: "none",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: "10px",
                }}
              >
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  style={{
                    padding: "9px 16px",
                    border: "1px solid var(--border-input, #334155)",
                    borderRadius: "8px",
                    background: "transparent",
                    color: "var(--text-secondary, #94a3b8)",
                    cursor: "pointer",
                    fontWeight: "600",
                    fontSize: "13px",
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  style={{
                    padding: "9px 18px",
                    background: "var(--accent-blue, #2563eb)",
                    color: "#fff",
                    border: "none",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontWeight: "700",
                    fontSize: "13px",
                  }}
                >
                  Update
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default MainLayout;