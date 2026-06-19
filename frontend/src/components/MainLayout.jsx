import { useState, useEffect } from "react";
import { useNavigate, Outlet } from "react-router-dom";

function MainLayout() {
  const navigate = useNavigate();

  const [isModalOpen, setIsModalOpen] = useState(false);

  const [passwords, setPasswords] = useState({
    current: "",
    new: "",
    confirm: "",
  });

  const [currentTime, setCurrentTime] = useState("");

  const user = JSON.parse(localStorage.getItem("user") || "{}");

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
    localStorage.removeItem("user");
    navigate("/login");
  };

  const handleChangePasswordSubmit = (e) => {
    e.preventDefault();

    if (passwords.new !== passwords.confirm) {
      alert("New password and Confirm Password do not match!");
      return;
    }

    alert("Password changed successfully!");

    setPasswords({
      current: "",
      new: "",
      confirm: "",
    });

    setIsModalOpen(false);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "#f4f6f9",
      }}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 20px",
          background: "#ffffff",
          borderBottom: "1px solid #e9ecef",
          boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        {/* Logo */}
        <div
          onClick={() => navigate("/dashboard")}
          style={{
            cursor: "pointer",
            fontWeight: "700",
            fontSize: "20px",
            color: "#0d6efd",
            border: "2px solid #0d6efd",
            borderRadius: "10px",
            padding: "8px 18px",
          }}
        >
          Life OS
        </div>

        {/* Right Section */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "15px",
          }}
        >
          {/* Time */}
          <div
            style={{
              fontSize: "17px",
              fontWeight: "600",
              color: "#495057",
              minWidth: "110px",
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
              background: "#f8f9fa",
              border: "1px solid #dee2e6",
              borderRadius: "25px",
              padding: "6px 12px",
            }}
          >
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "50%",
                background: "#0d6efd",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: "bold",
                fontSize: "15px",
              }}
            >
              {(user?.username || "User").charAt(0).toUpperCase()}
            </div>

            <div>
              <div
                style={{
                  fontWeight: "600",
                  fontSize: "14px",
                  color: "#212529",
                }}
              >
                {user?.username || "User"}
              </div>

              <div
                style={{
                  fontSize: "12px",
                  color: "#6c757d",
                }}
              >
                Logged In
              </div>
            </div>
          </div>

          {/* Change Password */}
          <button
            onClick={() => setIsModalOpen(true)}
            style={{
              padding: "10px 16px",
              border: "1px solid #ced4da",
              borderRadius: "6px",
              background: "#ffffff",
              cursor: "pointer",
              fontWeight: "500",
            }}
          >
            Change Password
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            style={{
              padding: "10px 16px",
              background: "#dc3545",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: "600",
            }}
          >
            ⏻ Logout
          </button>
        </div>
      </header>

      {/* Page Content */}
      <main
        style={{
          flex: 1,
          padding: "24px",
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
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 9999,
          }}
        >
          <div
            style={{
              background: "#ffffff",
              padding: "24px",
              borderRadius: "10px",
              width: "400px",
              boxShadow: "0 5px 20px rgba(0,0,0,0.2)",
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: "20px" }}>
              Change Password
            </h3>

            <form onSubmit={handleChangePasswordSubmit}>
              <div style={{ marginBottom: "12px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "5px",
                    fontWeight: "600",
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
                    padding: "10px",
                    border: "1px solid #ced4da",
                    borderRadius: "6px",
                  }}
                />
              </div>

              <div style={{ marginBottom: "12px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "5px",
                    fontWeight: "600",
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
                    padding: "10px",
                    border: "1px solid #ced4da",
                    borderRadius: "6px",
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "5px",
                    fontWeight: "600",
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
                    padding: "10px",
                    border: "1px solid #ced4da",
                    borderRadius: "6px",
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
                    padding: "10px 15px",
                    border: "1px solid #ced4da",
                    borderRadius: "6px",
                    background: "#fff",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  style={{
                    padding: "10px 15px",
                    background: "#0d6efd",
                    color: "#fff",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
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