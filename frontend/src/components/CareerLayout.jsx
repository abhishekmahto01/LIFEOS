import { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  Menu,
  Search,
  Home,
  FilePlus,
  History,
  KeyRound,
  LogOut,
  ArrowLeft,
} from "lucide-react";
import "./CareerLayout.css";
import { useAuth } from "../context/AuthContext";
import authService from "../services/authService";

const menuItems = [
  { label: "Career Home", icon: Home, path: "/career" },
  { label: "Job Entry", icon: FilePlus, path: "/career/job-entry" },
  { label: "Job History", icon: History, path: "/career/job-history" },
];

function CareerLayout() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [passwords, setPasswords] = useState({ current: "", new: "", confirm: "" });

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleChangePasswordSubmit = async (e) => {
    e.preventDefault();
    if (passwords.new !== passwords.confirm) {
      alert("New password and Confirm password do not match!");
      return;
    }
    try {
      const res = await authService.changePassword(passwords.current, passwords.new);
      if (res.success) {
        alert("Password changed successfully!");
        setPasswords({ current: "", new: "", confirm: "" });
        setIsModalOpen(false);
      } else {
        alert(res.message || "Failed to change password.");
      }
    } catch (err) {
      alert(err.response?.data?.message || "Error changing password.");
    }
  };

  const filteredItems = menuItems.filter((item) =>
    item.label.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}>
        <div className="sidebar-header">
          <button
            className="icon-btn"
            onClick={() => setCollapsed(!collapsed)}
            aria-label="Toggle menu"
          >
            <Menu size={20} />
          </button>
          {!collapsed && <span className="brand">Career</span>}
        </div>

        <button className="back-link" onClick={() => navigate("/dashboard")}>
          <ArrowLeft size={15} />
          {!collapsed && <span>Dashboard</span>}
        </button>

        {!collapsed && (
          <div className="search-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search menu..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        )}

        <nav className="nav-list">
          {filteredItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
              >
                <Icon size={18} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <button className="nav-item" onClick={() => setIsModalOpen(true)}>
            <KeyRound size={18} />
            {!collapsed && <span>Change Password</span>}
          </button>
          <button className="nav-item logout-btn" onClick={handleLogout}>
            <LogOut size={18} />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>

      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h3 className="modal-title">Change Password</h3>
            <form onSubmit={handleChangePasswordSubmit}>
              <div className="modal-field">
                <label>Current Password</label>
                <input type="password" required value={passwords.current} onChange={(e) => setPasswords({ ...passwords, current: e.target.value })} />
              </div>
              <div className="modal-field">
                <label>New Password</label>
                <input type="password" required value={passwords.new} onChange={(e) => setPasswords({ ...passwords, new: e.target.value })} />
              </div>
              <div className="modal-field">
                <label>Confirm New Password</label>
                <input type="password" required value={passwords.confirm} onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })} />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn-primary">Update</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default CareerLayout;