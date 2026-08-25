import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./components/MainLayout";

import PortfolioPage from "./portfolio/PortfolioPage";
import Dashboard from "./pages/Dashboard";
import CareerModule from "./pages/CareerModule";
import AdminModule from "./pages/admin/AdminModule";
import DisciplineDashboard from "./pages/DisciplineDashboard";
import Login from "./pages/Login";

import JobEntryForm from "./pages/career/job/JobEntryForm.jsx";
import JobApplyHistory from "./pages/career/job/JobApplyHistory.jsx";

import SocialMediaDashboard from "./pages/social-media/SocialMediaDashboard.jsx";
import CreatePost from "./pages/social-media/CreatePost.jsx";
import ContentCalendar from "./pages/social-media/ContentCalendar.jsx";
import ConnectedAccounts from "./pages/social-media/ConnectedAccounts.jsx";
import PostHistory from "./pages/social-media/PostHistory.jsx";
import SocialAnalytics from "./pages/social-media/SocialAnalytics.jsx";

function App() {
  return (
    <Router>
      <Routes>
        {/* Abhishek — Interactive Data Science Portfolio Landing */}
        <Route path="/" element={<PortfolioPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />

        {/* LifeOS System Access & Modules */}
        <Route path="/login" element={<Login />} />

        <Route element={<MainLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/discipline" element={<DisciplineDashboard />} />
          <Route path="/career" element={<CareerModule />} />
          <Route path="/career/job-entry" element={<JobEntryForm />} />
          <Route path="/career/job-history" element={<JobApplyHistory />} />
          <Route path="/admin" element={<AdminModule />} />

          {/* Social Media Hub — Omnichannel Creator Engine */}
          <Route path="/social-media" element={<SocialMediaDashboard />} />
          <Route path="/social-media/create" element={<CreatePost />} />
          <Route path="/social-media/calendar" element={<ContentCalendar />} />
          <Route path="/social-media/accounts" element={<ConnectedAccounts />} />
          <Route path="/social-media/history" element={<PostHistory />} />
          <Route path="/social-media/analytics" element={<SocialAnalytics />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;