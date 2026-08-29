import api from "./api";

/**
 * Authentication Service for LifeOS
 * Manages JWT tokens, user credentials, login sessions, and password updates.
 */
export const authService = {
  // Login with username & password, returns JWT token & user payload
  login: async (username, password) => {
    const response = await api.post("/api/auth/login", { username, password });
    if (response.data.success && response.data.token) {
      localStorage.setItem("token", response.data.token);
      localStorage.setItem("user", JSON.stringify(response.data.user));
    }
    return response.data;
  },

  // Logout: clears all authentication tokens and state
  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },

  // Get current stored user object
  getCurrentUser: () => {
    try {
      const user = localStorage.getItem("user");
      return user ? JSON.parse(user) : null;
    } catch {
      return null;
    }
  },

  // Get current stored JWT access token
  getToken: () => {
    return localStorage.getItem("token");
  },

  // Check if active authenticated session exists
  isAuthenticated: () => {
    const token = localStorage.getItem("token");
    const user = localStorage.getItem("user");
    return Boolean(token && user);
  },

  // Get authenticated user profile from verified JWT token
  getProfile: async () => {
    const response = await api.get("/api/auth/me");
    return response.data;
  },

  // Change password for currently authenticated user
  changePassword: async (oldPassword, newPassword) => {
    const response = await api.post("/api/auth/change-password", {
      old_password: oldPassword,
      new_password: newPassword,
    });
    return response.data;
  },
};

export default authService;
