import { useState } from "react";
import UserMaster from "./UserMaster";

const menuItems = [
  { key: "user-master", label: "👤 User Master" },
];

function AdminModule() {
  const [activeMenu, setActiveMenu] = useState("user-master");

  return (
    <div style={{ display: "flex", background: "#fff", borderRadius: 10, border: "1px solid #e9ecef", overflow: "hidden", minHeight: 500 }}>
      <div style={{ width: 210, borderRight: "1px solid #e9ecef", padding: "16px 10px", background: "#fafafa" }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#9ca3af", padding: "4px 12px 10px", textTransform: "uppercase", letterSpacing: ".05em" }}>
          Admin Panel
        </div>
        {menuItems.map((item) => (
          <div key={item.key} onClick={() => setActiveMenu(item.key)}
            style={{ padding: "9px 14px", borderRadius: 7, fontSize: 13, cursor: "pointer", marginBottom: 2,
              fontWeight: activeMenu === item.key ? 600 : 400,
              background: activeMenu === item.key ? "#eff6ff" : "transparent",
              color: activeMenu === item.key ? "#1d4ed8" : "#374151" }}>
            {item.label}
          </div>
        ))}
      </div>
      <div style={{ flex: 1, padding: 24 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#1f2937", marginBottom: 20 }}>
          {menuItems.find((m) => m.key === activeMenu)?.label}
        </div>
        {activeMenu === "user-master" && <UserMaster />}
      </div>
    </div>
  );
}

export default AdminModule;