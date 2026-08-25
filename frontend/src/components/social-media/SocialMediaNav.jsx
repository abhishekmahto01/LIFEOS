import { NavLink, useNavigate } from "react-router-dom";
import {
  Share2,
  PlusCircle,
  Calendar,
  Link2,
  History,
  TrendingUp,
  LayoutDashboard,
  ArrowLeft,
} from "lucide-react";
import "./SocialMediaNav.css";

export function SocialMediaNav({ activeTab = "overview", onRefresh, loading = false }) {
  const navigate = useNavigate();

  const navItems = [
    { key: "overview", label: "Dashboard Overview", path: "/social-media", icon: LayoutDashboard },
    { key: "create", label: "Create Post", path: "/social-media/create", icon: PlusCircle },
    { key: "calendar", label: "Content Calendar", path: "/social-media/calendar", icon: Calendar },
    { key: "accounts", label: "Connected Accounts", path: "/social-media/accounts", icon: Link2 },
    { key: "history", label: "Post History", path: "/social-media/history", icon: History },
    { key: "analytics", label: "Social Analytics", path: "/social-media/analytics", icon: TrendingUp },
  ];

  return (
    <div className="sm-nav-header-wrapper">
      {/* Top Header Information & Actions */}
      <div className="sm-header-card">
        <div className="sm-header-info">
          <button
            className="sm-back-btn"
            onClick={() => navigate("/dashboard")}
            title="Back to LifeOS Dashboard"
          >
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </button>
          
          <div className="sm-title-row">
            <div className="sm-icon-badge">
              <Share2 size={24} />
            </div>
            <div>
              <div className="sm-kicker">CREATOR • OMNICHANNEL ENGINE</div>
              <h1 className="sm-main-title">Social Media Hub</h1>
              <p className="sm-subtitle">Create once, publish everywhere — YouTube, Instagram & Facebook</p>
            </div>
          </div>
        </div>

        <div className="sm-header-actions">
          <button
            className="sm-btn-create-post"
            onClick={() => navigate("/social-media/create")}
          >
            <PlusCircle size={16} />
            <span>+ Create New Post</span>
          </button>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="sm-tabs-bar">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.key}
              to={item.path}
              end={item.path === "/social-media"}
              className={({ isActive }) =>
                `sm-tab-btn ${isActive ? "active" : ""}`
              }
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </div>
    </div>
  );
}

export default SocialMediaNav;
