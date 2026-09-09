import api from "./api";

/**
 * Service for Module Permissions and Current User Module Access
 */
export const permissionService = {
  // Get active modules accessible by the currently authenticated user
  getMyModules: async () => {
    const response = await api.get("/api/me/modules");
    return response.data;
  },

  // Admin: Get all active assignable modules
  getAdminModules: async () => {
    const response = await api.get("/api/admin/modules");
    return response.data;
  },

  // Admin: Get assigned module IDs for a user
  getUserPermissions: async (userId) => {
    const response = await api.get(`/api/admin/users/${userId}/modules`);
    return response.data;
  },

  // Admin: Save/update assigned module IDs for a user
  saveUserPermissions: async (userId, moduleIds) => {
    const response = await api.put(`/api/admin/users/${userId}/modules`, {
      module_ids: moduleIds,
    });
    return response.data;
  },

  // Admin: Get list of all users
  getAllUsers: async () => {
    const response = await api.get("/api/admin/users");
    return response.data;
  },
};

export default permissionService;
