import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "./Dashboard.css";

function Dashboard() {
  const navigate = useNavigate();

  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadModules();
  }, []);

  const loadModules = async () => {
    try {
      const user = JSON.parse(localStorage.getItem("user"));

      if (!user) {
        navigate("/login");
        return;
      }

      const res = await axios.get(
        `http://localhost:5000/api/dashboard/modules/${user.user_id}`
      );

      const modulesWithIcons = res.data.map((module) => ({
        ...module,
        icon:
          module.module_name === "Admin"
            ? "🛠️"
            : module.module_name === "Career"
            ? "🧑‍💼"
            : "📁",
      }));

      setModules(modulesWithIcons);
    } catch (error) {
      console.error("Error loading modules:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Loading modules...</div>;
  }

  return (
    <div>
      <div
        className="modules-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: "20px",
        }}
      >
        {modules.map((mod) => (
          <div
            key={mod.id}
            className="module-card"
            onClick={() => navigate(mod.route)}
            style={{
              background: "#fff",
              padding: "30px",
              borderRadius: "8px",
              boxShadow: "0 2px 5px rgba(0,0,0,0.05)",
              textAlign: "center",
              cursor: "pointer",
              transition: "transform 0.2s",
            }}
          >
            <div
              className="module-icon"
              style={{
                fontSize: "40px",
                marginBottom: "10px",
              }}
            >
              {mod.icon}
            </div>

            <div
              className="module-name"
              style={{
                fontWeight: "bold",
                fontSize: "16px",
                color: "#333",
              }}
            >
              {mod.module_name}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;