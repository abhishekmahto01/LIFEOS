import { useState, useEffect } from "react";
import permissionService from "../../services/permissionService";
import { ShieldCheck, UserCheck, RefreshCw, Save, CheckSquare, Square, AlertCircle, CheckCircle2 } from "lucide-react";

function UserPermissions() {
  const [users, setUsers] = useState([]);
  const [modules, setModules] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedUserObj, setSelectedUserObj] = useState(null);
  const [selectedModuleIds, setSelectedModuleIds] = useState(new Set());
  
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingModules, setLoadingModules] = useState(false);
  const [loadingPerms, setLoadingPerms] = useState(false);
  const [saving, setSaving] = useState(false);
  
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoadingUsers(true);
    setLoadingModules(true);
    setErrorMsg("");
    try {
      // 1. Fetch Users
      const usersRes = await permissionService.getAllUsers();
      const rawUsers = usersRes.users || [];
      // Filter out root admin user from list of assignable users if preferred or keep for reference
      const assignableUsers = rawUsers.filter((u) => u.user_name?.toLowerCase() !== "admin");
      setUsers(assignableUsers);

      // 2. Fetch Assignable Modules
      const modulesRes = await permissionService.getAdminModules();
      setModules(modulesRes.modules || []);

      // Auto-select first user if available
      if (assignableUsers.length > 0 && !selectedUserId) {
        const firstId = assignableUsers[0].user_id;
        setSelectedUserId(firstId);
        setSelectedUserObj(assignableUsers[0]);
        loadUserPermissions(firstId);
      }
    } catch (err) {
      setErrorMsg("Failed to initialize permissions data. Please check backend connection.");
    } finally {
      setLoadingUsers(false);
      setLoadingModules(false);
    }
  };

  const handleUserChange = (e) => {
    const uid = parseInt(e.target.value, 10);
    setSelectedUserId(uid || "");
    const userObj = users.find((u) => u.user_id === uid);
    setSelectedUserObj(userObj || null);
    if (uid) {
      loadUserPermissions(uid);
    } else {
      setSelectedModuleIds(new Set());
    }
  };

  const loadUserPermissions = async (userId) => {
    if (!userId) return;
    setLoadingPerms(true);
    setErrorMsg("");
    try {
      const res = await permissionService.getUserPermissions(userId);
      const assignedIds = new Set(res.assigned_module_ids || []);
      setSelectedModuleIds(assignedIds);
    } catch (err) {
      setErrorMsg(`Failed to load permissions for user.`);
    } finally {
      setLoadingPerms(false);
    }
  };

  const handleToggleModule = (moduleId) => {
    setSelectedModuleIds((prev) => {
      const next = new Set(prev);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedModuleIds.size === modules.length) {
      setSelectedModuleIds(new Set());
    } else {
      setSelectedModuleIds(new Set(modules.map((m) => m.id)));
    }
  };

  const handleSavePermissions = async () => {
    if (!selectedUserId) {
      setErrorMsg("Please select a user first.");
      return;
    }
    setSaving(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const payload = Array.from(selectedModuleIds);
      const res = await permissionService.saveUserPermissions(selectedUserId, payload);
      setSuccessMsg(res.message || `Permissions saved successfully!`);
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch (err) {
      setErrorMsg(err.response?.data?.message || err.response?.data?.error || "Failed to save permissions.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ fontFamily: "inherit" }}>
      {/* Notifications */}
      {successMsg && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#dcfce7", color: "#166534", padding: "12px 18px", borderRadius: 8, marginBottom: 16, fontSize: 13, border: "1px solid #bbf7d0" }}>
          <CheckCircle2 size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#fee2e2", color: "#991b1b", padding: "12px 18px", borderRadius: 8, marginBottom: 16, fontSize: 13, border: "1px solid #fecaca" }}>
          <AlertCircle size={16} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Top Filter & Action Bar */}
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 10, padding: "20px 24px", marginBottom: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, flex: 1, minWidth: 280 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Select User <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <select
                value={selectedUserId}
                onChange={handleUserChange}
                disabled={loadingUsers}
                style={{
                  padding: "10px 14px",
                  borderRadius: 8,
                  border: "1px solid #d1d5db",
                  background: "#f9fafb",
                  fontSize: 14,
                  fontWeight: 500,
                  color: "#111827",
                  outline: "none",
                  cursor: "pointer"
                }}
              >
                <option value="">-- Choose User --</option>
                {users.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.user_name} (ID: {u.user_id}) {u.is_active ? "" : " [Inactive]"}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => selectedUserId && loadUserPermissions(selectedUserId)}
              disabled={!selectedUserId || loadingPerms}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "10px 16px",
                marginTop: 22,
                borderRadius: 8,
                background: "#f3f4f6",
                color: "#374151",
                border: "1px solid #d1d5db",
                fontWeight: 600,
                fontSize: 13,
                cursor: selectedUserId ? "pointer" : "not-allowed"
              }}
            >
              <RefreshCw size={14} className={loadingPerms ? "spin-icon" : ""} />
              <span>Search / Load</span>
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 22 }}>
            <button
              onClick={handleSavePermissions}
              disabled={!selectedUserId || saving}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 22px",
                borderRadius: 8,
                background: "#2563eb",
                color: "#ffffff",
                border: "none",
                fontWeight: 700,
                fontSize: 13,
                cursor: selectedUserId && !saving ? "pointer" : "not-allowed",
                boxShadow: "0 2px 4px rgba(37,99,235,0.2)"
              }}
            >
              <Save size={15} />
              <span>{saving ? "Saving..." : "Save Permissions"}</span>
            </button>
          </div>
        </div>

        {selectedUserObj && (
          <div style={{ marginTop: 14, padding: "8px 12px", background: "#eff6ff", borderRadius: 6, display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12, color: "#1e40af" }}>
            <UserCheck size={14} />
            <span>Configuring module access for: <strong>{selectedUserObj.user_name}</strong></span>
          </div>
        )}
      </div>

      {/* Permission Table Section */}
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid #e5e7eb", background: "#fafafa" }}>
          <div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#111827" }}>Module Access Control</span>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "#6b7280" }}>
              Toggle Allow checkbox to grant or revoke full module access.
            </p>
          </div>

          {modules.length > 0 && selectedUserId && (
            <button
              onClick={handleSelectAll}
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#2563eb",
                background: "transparent",
                border: "1px solid #bfdbfe",
                padding: "5px 12px",
                borderRadius: 6,
                cursor: "pointer"
              }}
            >
              {selectedModuleIds.size === modules.length ? "Deselect All" : "Select All Active"}
            </button>
          )}
        </div>

        {loadingPerms || loadingModules ? (
          <div style={{ textAlign: "center", padding: "48px 20px", color: "#9ca3af" }}>
            <RefreshCw size={24} className="spin-icon" style={{ margin: "0 auto 12px" }} />
            <p style={{ margin: 0, fontSize: 13 }}>Loading permission matrix...</p>
          </div>
        ) : !selectedUserId ? (
          <div style={{ textAlign: "center", padding: "48px 20px", color: "#9ca3af", fontSize: 13 }}>
            <ShieldCheck size={28} style={{ margin: "0 auto 10px", opacity: 0.5 }} />
            Please select a user from the top dropdown to view and manage module access.
          </div>
        ) : modules.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 20px", color: "#9ca3af", fontSize: 13 }}>
            No assignable modules found in module_master.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f3f4f6", borderBottom: "1px solid #e5e7eb" }}>
                <th style={{ padding: "12px 18px", textAlign: "left", color: "#374151", fontWeight: 700, width: 60 }}>Sr.</th>
                <th style={{ padding: "12px 18px", textAlign: "left", color: "#374151", fontWeight: 700 }}>Module Name</th>
                <th style={{ padding: "12px 18px", textAlign: "left", color: "#374151", fontWeight: 700 }}>Module Route</th>
                <th style={{ padding: "12px 18px", textAlign: "center", color: "#374151", fontWeight: 700, width: 140 }}>Access</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((mod, idx) => {
                const isAllowed = selectedModuleIds.has(mod.id);
                return (
                  <tr
                    key={mod.id}
                    onClick={() => handleToggleModule(mod.id)}
                    style={{
                      background: isAllowed ? "#f0fdf4" : idx % 2 === 0 ? "#ffffff" : "#fafafa",
                      borderBottom: "1px solid #f3f4f6",
                      cursor: "pointer",
                      transition: "background 0.15s ease"
                    }}
                  >
                    <td style={{ padding: "14px 18px", color: "#6b7280", fontWeight: 600 }}>{idx + 1}</td>
                    <td style={{ padding: "14px 18px", fontWeight: 600, color: "#111827" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span>{mod.module_name}</span>
                        <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "#e5e7eb", color: "#4b5563" }}>
                          {mod.module_code}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: "14px 18px", color: "#6b7280", fontFamily: "monospace", fontSize: 12 }}>
                      {mod.route}
                    </td>
                    <td style={{ padding: "14px 18px", textAlign: "center" }}>
                      <label
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          cursor: "pointer",
                          userSelect: "none",
                          padding: "4px 10px",
                          borderRadius: 6,
                          background: isAllowed ? "#dcfce7" : "#f3f4f6",
                          color: isAllowed ? "#166534" : "#6b7280",
                          fontWeight: 600,
                          fontSize: 12
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isAllowed}
                          onChange={() => handleToggleModule(mod.id)}
                          style={{
                            width: 16,
                            height: 16,
                            accentColor: "#16a34a",
                            cursor: "pointer"
                          }}
                        />
                        <span>{isAllowed ? "Allowed" : "Allow"}</span>
                      </label>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default UserPermissions;
