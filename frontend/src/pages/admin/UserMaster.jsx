import { useState, useEffect } from "react";
import api from "../../services/api";

function UserMaster() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchUsers(); }, []);

  const fetchUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/api/admin/users");
      setUsers(res.data.users || []);
    } catch (err) {
      setError("Failed to load users. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUserName.trim()) { showMsg("error", "Username is required"); return; }
    setSaving(true);
    try {
      const res = await api.post("/api/admin/users", {
        user_name: newUserName.trim(),
        is_active: isActive,
      });
      showMsg("success", res.data.message);
      setNewUserName("");
      setIsActive(true);
      fetchUsers();
    } catch (err) {
      showMsg("error", err.response?.data?.message || "Error creating user");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (userId) => {
    try {
      const res = await api.patch(`/api/admin/users/${userId}/toggle`);
      setUsers((prev) => prev.map((u) => u.user_id === userId ? { ...u, is_active: res.data.is_active } : u));
      showMsg("success", "User status updated");
    } catch (err) {
      showMsg("error", "Failed to update status");
    }
  };

  const showMsg = (type, msg) => {
    if (type === "success") { setSuccess(msg); setError(""); }
    else { setError(msg); setSuccess(""); }
    setTimeout(() => { setSuccess(""); setError(""); }, 3000);
  };

  return (
    <div>
      {success && <div style={{ background: "#dcfce7", color: "#166534", padding: "10px 16px", borderRadius: 6, marginBottom: 12, fontSize: 13 }}>{success}</div>}
      {error && <div style={{ background: "#fee2e2", color: "#991b1b", padding: "10px 16px", borderRadius: 6, marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <div style={{ background: "#fff", border: "1px solid #e9ecef", borderRadius: 8, padding: "20px 24px", marginBottom: 20 }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "#1f2937", marginBottom: 4 }}>Add New User</div>
        <p style={{ fontSize: 12, color: "#6b7280", marginBottom: 16 }}>Default password will be same as username.</p>
        <div style={{ display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 180 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Username <span style={{ color: "red" }}>*</span></label>
            <input type="text" placeholder="e.g. rahul123" value={newUserName}
              onChange={(e) => setNewUserName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateUser()}
              style={{ padding: "9px 12px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 13, outline: "none" }} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>Status</label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", paddingBottom: 2 }}>
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)}
                style={{ accentColor: "#27ae60", width: 16, height: 16 }} />
              <span style={{ fontSize: 13 }}>Active</span>
            </label>
          </div>
          <button onClick={handleCreateUser} disabled={saving}
            style={{ padding: "9px 20px", background: "#27ae60", color: "#fff", border: "none", borderRadius: 6, fontWeight: 600, fontSize: 13, cursor: "pointer" }}>
            {saving ? "Saving..." : "Save User"}
          </button>
        </div>
      </div>

      <div style={{ background: "#fff", border: "1px solid #e9ecef", borderRadius: 8, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #e9ecef" }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1f2937" }}>All Users</span>
          <button onClick={fetchUsers} style={{ padding: "6px 14px", background: "#fff", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 12, cursor: "pointer" }}>↻ Refresh</button>
        </div>
        {loading ? (
          <div style={{ textAlign: "center", padding: 32, color: "#9ca3af" }}>Loading...</div>
        ) : users.length === 0 ? (
          <div style={{ textAlign: "center", padding: 32, color: "#9ca3af", fontSize: 13 }}>No users found. Add one above.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                {["Sr.", "User ID", "Username", "Default Password", "Status", "Created At", "Action"].map((h) => (
                  <th key={h} style={{ background: "#f3f4f6", color: "#374151", fontWeight: 600, padding: "10px 14px", textAlign: "left", borderBottom: "1px solid #e9ecef", fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u, idx) => (
                <tr key={u.user_id} style={{ background: idx % 2 === 0 ? "#fff" : "#fafafa" }}>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6" }}>{idx + 1}</td>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6" }}>{u.user_id}</td>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6", fontWeight: 500 }}>{u.user_name}</td>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6", color: "#888", fontStyle: "italic" }}>{u.user_name} (same as username)</td>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6" }}>
                    <span style={{ background: u.is_active ? "#dcfce7" : "#fee2e2", color: u.is_active ? "#166534" : "#991b1b", padding: "3px 10px", borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6", fontSize: 12, color: "#888" }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString("en-IN") : "—"}
                  </td>
                  <td style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6" }}>
                    <button onClick={() => handleToggle(u.user_id)}
                      style={{ padding: "5px 12px", background: u.is_active ? "#e74c3c" : "#27ae60", color: "#fff", border: "none", borderRadius: 5, fontSize: 12, cursor: "pointer" }}>
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default UserMaster;