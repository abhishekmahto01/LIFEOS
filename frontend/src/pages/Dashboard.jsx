import { useNavigate } from "react-router-dom";
import "./Dashboard.css";

const modules = [
  { name: "Career", icon: "🧑‍💼", path: "/career" },
  { name: "Admin", icon: "🛠️", path: "/admin" },
];

function Dashboard() {
  const navigate = useNavigate();

  return (
    <div>
      {/* Sirf Grid render hoga layout ke andar */}
      <div className="modules-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "20px" }}>
        {modules.map((mod) => (
          <div
            key={mod.name}
            className="module-card"
            onClick={() => navigate(mod.path)}
            style={{ background: "#fff", padding: "30px", borderRadius: "8px", boxShadow: "0 2px 5px rgba(0,0,0,0.05)", textAlign: "center", cursor: "pointer", transition: "transform 0.2s" }}
          >
            <div className="module-icon" style={{ fontSize: "40px", marginBottom: "10px" }}>{mod.icon}</div>
            <div className="module-name" style={{ fontWeight: "bold", fontSize: "16px", color: "#333" }}>{mod.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;