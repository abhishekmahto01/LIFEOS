import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./components/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import ModuleRoute from "./components/ModuleRoute";

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

        {/* LifeOS Public System Access */}
        <Route path="/login" element={<Login />} />

        {/* LifeOS Protected System Modules */}
        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          {/* Main Dashboard - Available to all authenticated users */}
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Discipline Module */}
          <Route
            path="/discipline"
            element={
              <ModuleRoute moduleCode="discipline">
                <DisciplineDashboard />
              </ModuleRoute>
            }
          />

          {/* Career Module */}
          <Route
            path="/career"
            element={
              <ModuleRoute moduleCode="career">
                <CareerModule />
              </ModuleRoute>
            }
          />
          <Route
            path="/career/job-entry"
            element={
              <ModuleRoute moduleCode="career">
                <JobEntryForm />
              </ModuleRoute>
            }
          />
          <Route
            path="/career/job-history"
            element={
              <ModuleRoute moduleCode="career">
                <JobApplyHistory />
              </ModuleRoute>
            }
          />

          {/* Admin Panel — Strictly for System Admin */}
          <Route
            path="/admin"
            element={
              <ModuleRoute moduleCode="admin">
                <AdminModule />
              </ModuleRoute>
            }
          />

          {/* Social Media Hub — Omnichannel Creator Engine */}
          <Route
            path="/social-media"
            element={
              <ModuleRoute moduleCode="social_media">
                <SocialMediaDashboard />
              </ModuleRoute>
            }
          />
          <Route
            path="/social-media/create"
            element={
              <ModuleRoute moduleCode="social_media">
                <CreatePost />
              </ModuleRoute>
            }
          />
          <Route
            path="/social-media/calendar"
            element={
              <ModuleRoute moduleCode="social_media">
                <ContentCalendar />
              </ModuleRoute>
            }
          />
          <Route
            path="/social-media/accounts"
            element={
              <ModuleRoute moduleCode="social_media">
                <ConnectedAccounts />
              </ModuleRoute>
            }
          />
          <Route
            path="/social-media/history"
            element={
              <ModuleRoute moduleCode="social_media">
                <PostHistory />
              </ModuleRoute>
            }
          />
          <Route
            path="/social-media/analytics"
            element={
              <ModuleRoute moduleCode="social_media">
                <SocialAnalytics />
              </ModuleRoute>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;