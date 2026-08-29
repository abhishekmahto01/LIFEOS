import api from "./api";

/**
 * Social Media Hub - API Service
 * Centralized client service for Social Media Dashboard, Post Creation, Calendar, Accounts, History & Analytics.
 */
export const socialMediaService = {
  // 1. Get Social Media Hub Dashboard Summary (Metrics, Platform health, upcoming posts)
  getDashboardSummary: async () => {
    try {
      const response = await api.get("/api/social-media/dashboard");
      return response.data;
    } catch (err) {
      // Phase 1 Safe Fallback (clean zero/empty initial state)
      return {
        success: true,
        metrics: {
          totalPublished: 0,
          scheduledPosts: 0,
          failedPosts: 0,
          connectedPlatforms: 0,
        },
        platforms: {
          youtube: { connected: false, channelName: null, status: "Not Connected" },
          instagram: { connected: false, accountName: null, status: "Not Connected" },
          facebook: { connected: false, pageName: null, status: "Not Connected" },
        },
        recentPosts: [],
        upcomingSchedule: [],
        bestPerforming: [],
      };
    }
  },

  // 2. Get Connected Social Accounts
  getAccounts: async () => {
    const response = await api.get("/api/social-media/accounts");
    return response.data;
  },

  // 3. Connect Account OAuth Start URLs
  getYouTubeConnectUrl: async () => {
    const response = await api.get("/api/social-media/connect/youtube");
    return response.data;
  },

  getMetaConnectUrl: async () => {
    const response = await api.get("/api/social-media/connect/meta");
    return response.data;
  },

  // 4. Disconnect Account
  disconnectAccount: async (accountId) => {
    const response = await api.delete(`/api/social-media/accounts/${accountId}`);
    return response.data;
  },

  // 5. Content Management
  getContentList: async (params = {}) => {
    try {
      const response = await api.get("/api/social-media/content", { params });
      return response.data;
    } catch (err) {
      return {
        success: true,
        content: [],
      };
    }
  },

  getContentById: async (contentId) => {
    const response = await api.get(`/api/social-media/content/${contentId}`);
    return response.data;
  },

  createContent: async (formData) => {
    const response = await api.post("/api/social-media/content", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  publishContent: async (contentId) => {
    const response = await api.post(`/api/social-media/content/${contentId}/publish`);
    return response.data;
  },

  scheduleContent: async (contentId, scheduleData) => {
    const response = await api.post(`/api/social-media/content/${contentId}/schedule`, scheduleData);
    return response.data;
  },

  retryPost: async (postId) => {
    const response = await api.post(`/api/social-media/posts/${postId}/retry`);
    return response.data;
  },

  // 6. Analytics
  getAnalytics: async () => {
    try {
      const response = await api.get("/api/social-media/analytics");
      return response.data;
    } catch (err) {
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
};

export default socialMediaService;
