import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./components/MainLayout";

import Dashboard from "./pages/Dashboard";
import CareerModule from "./pages/CareerModule";
import AdminModule from "./pages/admin/AdminModule";
import DisciplineDashboard from "./pages/DisciplineDashboard";
import Login from "./pages/Login";

import JobEntryForm from "./pages/career/job/JobEntryForm.jsx";
import JobApplyHistory from "./pages/career/job/JobApplyHistory.jsx";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route element={<MainLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/discipline" element={<DisciplineDashboard />} />
          <Route path="/career" element={<CareerModule />} />
          <Route path="/career/job-entry" element={<JobEntryForm />} />
          <Route path="/career/job-history" element={<JobApplyHistory />} />
          <Route path="/admin" element={<AdminModule />} />
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Router>
  );
}

export default App;