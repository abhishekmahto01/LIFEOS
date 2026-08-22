import api from "./api";

export const disciplineService = {
  // Get today's habit status & top widget summary
  getTodaySummary: async (userId = 1) => {
    const response = await api.get("/api/discipline/today", {
      params: { user_id: userId },
    });
    return response.data;
  },

  // Get data for a specific date
  getDayData: async (dateStr, userId = 1) => {
    const response = await api.get(`/api/discipline/day/${dateStr}`, {
      params: { user_id: userId },
    });
    return response.data;
  },

  // Save/Toggle activities for a specific date
  saveDayData: async (dateStr, data, userId = 1) => {
    const response = await api.post(`/api/discipline/day/${dateStr}`, {
      ...data,
      user_id: userId,
    });
    return response.data;
  },

  // Get month calendar day-by-day
  getMonthCalendar: async (year, month, userId = 1) => {
    const response = await api.get(`/api/discipline/month/${year}/${month}`, {
      params: { user_id: userId },
    });
    return response.data;
  },

  // Get full 365-day year heatmap
  getYearHeatmap: async (year, userId = 1) => {
    const response = await api.get(`/api/discipline/year/${year}`, {
      params: { user_id: userId },
    });
    return response.data;
  },

  // Get full analytics (quarterly, streaks, insights, BMW progress)
  getAnalytics: async (year, userId = 1) => {
    const response = await api.get(`/api/discipline/analytics/${year}`, {
      params: { user_id: userId },
    });
    return response.data;
  },
};

export default disciplineService;
