import React, { useState } from "react";
import { useNavigate, Outlet } from "react-router-dom";

function MainLayout() {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [passwords, setPasswords] = useState({ current: "", new: "", confirm: "" });

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/login");
  };

  const handleChangePasswordSubmit = (e) => {
    e.preventDefault();
    if (passwords.new !== passwords.confirm) {
      alert("New password and Confirm password do not match!");
      return;
    }
    alert("Password changed successfully!");
    setPasswords({ current: "", new: "", confirm: "" });
    setIsModalOpen(false);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "#f4f6f9" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 20px", background: "#fff", borderBottom: "1px solid #e9ecef" }}>
        <div onClick={() => navigate("/dashboard")} style={{ cursor: "pointer", fontWeight: "bold", fontSize: "18px", color: "#007bff", border: "1.5px solid #007bff", borderRadius: 8, padding: "6px 14px" }}>
          Life OS
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button onClick={() => setIsModalOpen(true)} style={{ padding: "8px 15px", border: "1px solid #ced4da", borderRadius: "4px", background: "#fff", cursor: "pointer", fontSize: 14 }}>
            Change Password
          </button>
          <button onClick={handleLogout} style={{ padding: "8px 15px", background: "#dc3545", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: 14, fontWeight: 600 }}>
            ⏻ Logout
          </button>
        </div>
      </header>

      <div style={{ flex: 1, padding: "24px" }}>
        <Outlet />
      </div>

      {isModalOpen && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 1000 }}>
          <div style={{ background: "#fff", padding: "24px", borderRadius: "8px", width: "350px", boxShadow: "0 4px 15px rgba(0,0,0,0.2)" }}>
            <h3 style={{ marginTop: 0, marginBottom: "15px" }}>Change Password</h3>
            <form onSubmit={handleChangePasswordSubmit}>
              <div style={{ marginBottom: "12px", display: "flex", flexDirection: "column" }}>
                <label style={{ fontSize: "12px", fontWeight: "bold", marginBottom: "5px" }}>Current Password</label>
                <input type="password" required style={{ padding: "8px", border: "1px solid #ccc", borderRadius: "4px" }} value={passwords.current} onChange={(e) => setPasswords({...passwords, current: e.target.value})} />
              </div>
              <div style={{ marginBottom: "12px", display: "flex", flexDirection: "column" }}>
                <label style={{ fontSize: "12px", fontWeight: "bold", marginBottom: "5px" }}>New Password</label>
                <input type="password" required style={{ padding: "8px", border: "1px solid #ccc", borderRadius: "4px" }} value={passwords.new} onChange={(e) => setPasswords({...passwords, new: e.target.value})} />
              </div>
              <div style={{ marginBottom: "15px", display: "flex", flexDirection: "column" }}>
                <label style={{ fontSize: "12px", fontWeight: "bold", marginBottom: "5px" }}>Confirm New Password</label>
                <input type="password" required style={{ padding: "8px", border: "1px solid #ccc", borderRadius: "4px" }} value={passwords.confirm} onChange={(e) => setPasswords({...passwords, confirm: e.target.value})} />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button type="button" onClick={() => setIsModalOpen(false)} style={{ padding: "8px 12px", border: "1px solid #ccc", borderRadius: "4px", background: "#fff", cursor: "pointer" }}>Cancel</button>
                <button type="submit" style={{ padding: "8px 12px", background: "#007bff", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer" }}>Update</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default MainLayout;