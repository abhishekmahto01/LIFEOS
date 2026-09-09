import { useEffect, useState } from "react";
import { Navigate, useNavigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import authService from "../services/authService";
import permissionService from "../services/permissionService";
import { ShieldAlert, ArrowLeft, Home, Lock } from "lucide-react";

export function ModuleRoute({ moduleCode, children }) {
  const { user: authUser, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const user = authUser || authService.getCurrentUser();
  const hasValidSession = isAuthenticated || authService.isAuthenticated();

  const [hasAccess, setHasAccess] = useState(null); // null = checking, true = allowed, false = denied
  const [loading, setLoading] = useState(true);

  const isAdmin = user && (user.username?.toLowerCase() === "admin" || user.user_id === 1);

  useEffect(() => {
    let isMounted = true;

    async function checkPermission() {
      if (!hasValidSession || !user) {
        if (isMounted) {
          setHasAccess(false);
          setLoading(false);
        }
        return;
      }

      // Root Admin user automatically has full access to all modules and admin panel
      if (isAdmin) {
        if (isMounted) {
          setHasAccess(true);
          setLoading(false);
        }
        return;
      }

      // Normal users are strictly blocked from the Admin module
      if (moduleCode === "admin") {
        if (isMounted) {
          setHasAccess(false);
          setLoading(false);
        }
        return;
      }

      // Check user permissions via /api/me/modules
      try {
        const res = await permissionService.getMyModules();
        const allowedModules = res.modules || [];
        const normalizedTarget = (moduleCode || "").toLowerCase().replace(/[\s-]/g, "_");

        const allowed = allowedModules.some((m) => {
          const code = (m.module_code || "").toLowerCase().replace(/[\s-]/g, "_");
          const name = (m.module_name || "").toLowerCase().replace(/[\s-]/g, "_");
          const route = (m.route || "").toLowerCase().replace(/[\s-]/g, "_");
          return (
            code === normalizedTarget ||
            name === normalizedTarget ||
            route === `/${normalizedTarget}` ||
            route === normalizedTarget
          );
        });

        if (isMounted) {
          setHasAccess(allowed);
          setLoading(false);
        }
      } catch (err) {
        console.error("Permission check failed:", err);
        if (isMounted) {
          setHasAccess(false);
          setLoading(false);
        }
      }
    }

    checkPermission();

    return () => {
      isMounted = false;
    };
  }, [moduleCode, user?.user_id, hasValidSession, isAdmin]);

  if (!hasValidSession) {
    return <Navigate to="/login" replace />;
  }

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "50vh" }}>
        <div style={{ textAlign: "center", color: "#6b7280", fontSize: "14px" }}>
          <div className="dash-loading-spinner" style={{ margin: "0 auto 12px" }}></div>
          <span>Verifying Module Security Clearance...</span>
        </div>
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "65vh",
          padding: "24px",
        }}
      >
        <div
          style={{
            maxWidth: "480px",
            width: "100%",
            background: "var(--bg-surface-elevated, #111827)",
            border: "1px solid #ef444440",
            borderRadius: "16px",
            padding: "36px 28px",
            textAlign: "center",
            boxShadow: "0 10px 30px rgba(239, 68, 68, 0.1)",
          }}
        >
          <div
            style={{
              width: "64px",
              height: "64px",
              borderRadius: "50%",
              background: "rgba(239, 68, 68, 0.15)",
              color: "#ef4444",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 18px",
            }}
          >
            <Lock size={32} />
          </div>

          <h2
            style={{
              fontSize: "20px",
              fontWeight: "800",
              color: "var(--text-primary, #ffffff)",
              marginBottom: "10px",
            }}
          >
            403 &bull; Access Denied
          </h2>

          <p
            style={{
              fontSize: "14px",
              color: "var(--text-secondary, #9ca3af)",
              lineHeight: "1.5",
              marginBottom: "24px",
            }}
          >
            You do not have permission to access the{" "}
            <strong style={{ color: "#f87171", textTransform: "capitalize" }}>
              {moduleCode?.replace("_", " ")}
            </strong>{" "}
            module. Please contact an administrator to request access.
          </p>

          <div style={{ display: "flex", justifyContent: "center", gap: "12px" }}>
            <button
              onClick={() => navigate("/dashboard")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 20px",
                background: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontWeight: "700",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              <Home size={15} />
              <span>Return to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return children ? children : <Outlet />;
}

export default ModuleRoute;
