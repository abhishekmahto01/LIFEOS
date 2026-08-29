import api from "./api";

/**
 * Social Media Hub - API Service
 * Centralized client service for Social Media Dashboard, Post Creation, Accounts, History & Analytics.
 */
export const socialMediaService = {
  // 1. Get Social Media Hub Dashboard Summary
  getDashboardSummary: async () => {
    const response = await api.get("/api/social-media/dashboard");
    return response.data;
  },

  // 2. Get Connected Social Accounts
  getAccounts: async () => {
    const response = await api.get("/api/social-media/accounts");
    return response.data;
  },

  // 3. Connect Account OAuth Start URL
  getYouTubeConnectUrl: async () => {
    const response = await api.get("/api/social-media/connect/youtube");
    return response.data;
  },

  // 4. Disconnect Account
  disconnectAccount: async (accountId) => {
    const response = await api.delete(`/api/social-media/accounts/${accountId}`);
    return response.data;
  },

  // 5. Post Creation & Temporary Upload (Browser automatically adds multipart boundary)
  uploadAndCreatePost: async (formData, onUploadProgress) => {
    const response = await api.post("/api/social-media/upload", formData, {
      onUploadProgress,
    });
    return response.data;
  },

  // 6. Content Status Polling
  getContentStatus: async (contentId) => {
    const response = await api.get(`/api/social-media/content/${contentId}/status`);
    return response.data;
  },

  // 7. Publish to YouTube
  publishYouTube: async (contentId) => {
    const response = await api.post(`/api/social-media/content/${contentId}/publish/youtube`);
    return response.data;
  },

  // 8. Retry YouTube Publishing
  retryYouTubePublish: async (contentId) => {
    const response = await api.post(`/api/social-media/content/${contentId}/retry/youtube`);
    return response.data;
  },

  // 9. Post History
  getContentList: async (params = {}) => {
    const response = await api.get("/api/social-media/history", { params });
    return response.data;
  },

  // 10. Analytics Placeholder
  getAnalytics: async () => {
    try {
      const response = await api.get("/api/social-media/analytics");
      return response.data;
    } catch {
      return {
        success: true,
        analytics: {
          totalViews: 0,
          totalLikes: 0,
          totalComments: 0,
          totalShares: 0,
          followersGained: 0,
          engagementRate: 0,
          platforms: [],
        },
      };
    }
  },

  // Legacy/Helper aliases
  getContentById: async (contentId) => {
    const response = await api.get(`/api/social-media/content/${contentId}/status`);
    return response.data;
  },
  retryPost: async (contentId) => {
    const response = await api.post(`/api/social-media/content/${contentId}/retry/youtube`);
    return response.data;
  },
};

export default socialMediaService;
