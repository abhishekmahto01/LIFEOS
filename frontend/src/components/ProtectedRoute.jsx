import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import authService from "../services/authService";

export function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const hasValidSession = isAuthenticated || authService.isAuthenticated();

  if (!hasValidSession) {
    return <Navigate to="/login" replace />;
  }

  return children ? children : <Outlet />;
}

export default ProtectedRoute;
