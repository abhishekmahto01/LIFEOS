import api from "./api";

export const jobService = {
  // Create a new job application
  createJob: async (jobData) => {
    const response = await api.post("/api/jobs", jobData);
    return response.data;
  },

  // Get job applications history with optional filters
  getHistory: async (params = {}) => {
    const response = await api.get("/api/jobs/history", { params });
    return response.data;
  },

  // Get aggregated statistics for Career Dashboard
  getStats: async () => {
    const response = await api.get("/api/jobs/stats");
    return response.data;
  },

  // Get single job details and its timeline activities
  getJobById: async (jobId) => {
    const response = await api.get(`/api/jobs/${jobId}`);
    return response.data;
  },

  // Update existing job application
  updateJob: async (jobId, jobData) => {
    const response = await api.put(`/api/jobs/${jobId}`, jobData);
    return response.data;
  },

  // Delete job application
  deleteJob: async (jobId) => {
    const response = await api.delete(`/api/jobs/${jobId}`);
    return response.data;
  },

  // Add activity log to timeline
  addActivity: async (jobId, activityData) => {
    const response = await api.post(`/api/jobs/${jobId}/activity`, activityData);
    return response.data;
  },
};

export default jobService;
