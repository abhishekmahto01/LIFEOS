import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Zap,
  Flame,
  Trophy,
  Star,
  CheckCircle2,
  Circle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  Award,
  BarChart3,
  Dumbbell,
  Briefcase,
  BookOpen,
  Code2,
  Sparkles,
  ArrowRight,
  RefreshCw,
  X,
  Target,
  ArrowUpRight,
  Check,
  AlertCircle,
  Clock,
  Gauge,
  Sliders,
} from "lucide-react";
import { disciplineService } from "../services/disciplineService";
import "./DisciplineDashboard.css";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

const FULL_MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const MOTIVATIONAL_QUOTES = [
  "“Small actions. Every day. One goal.”",
  "“You don't need motivation. You need consistency.”",
  "“Future you is watching what you do today.”",
  "“Discipline is choosing between what you want now and what you want most.”",
  "“The bike is the reward. Discipline is the price.”",
  "“Don't break the chain.”",
  "“One disciplined day closer to the goal.”",
  "“Your future self will thank today's you.”"
];

function DisciplineDashboard() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const userId = user.user_id || 1;

  const currentYear = 2026;
  const today = new Date();
  const currentMonthIndex = today.getFullYear() === currentYear ? today.getMonth() + 1 : 8;

  // Selected Month State for Calendar
  const [selectedMonth, setSelectedMonth] = useState(currentMonthIndex);

  // Data states
  const [todayData, setTodayData] = useState(null);
  const [monthData, setMonthData] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [yearHeatmap, setYearHeatmap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Daily Detail Modal State
  const [selectedDayObj, setSelectedDayObj] = useState(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [modalFormState, setModalFormState] = useState({
    gym_completed: false,
    job_completed: false,
    study_completed: false,
    project_completed: false,
    notes: "",
  });
  const [modalSaving, setModalSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [showConfetti, setShowConfetti] = useState(false);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Load all initial data
  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [todayRes, monthRes, analyticsRes, heatmapRes] = await Promise.all([
        disciplineService.getTodaySummary(userId),
        disciplineService.getMonthCalendar(currentYear, selectedMonth, userId),
        disciplineService.getAnalytics(currentYear, userId),
        disciplineService.getYearHeatmap(currentYear, userId),
      ]);

      if (todayRes.success) setTodayData(todayRes);
      if (monthRes.success) setMonthData(monthRes);
      if (analyticsRes.success) setAnalyticsData(analyticsRes);
      if (heatmapRes.success) setYearHeatmap(heatmapRes);
    } catch (err) {
      console.error("Error loading discipline data:", err);
      setError("Failed to connect to Discipline backend service.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  // When selected month changes, load that month's calendar
  useEffect(() => {
    const fetchMonth = async () => {
      try {
        const res = await disciplineService.getMonthCalendar(currentYear, selectedMonth, userId);
        if (res.success) {
          setMonthData(res);
        }
      } catch (err) {
        console.error("Error loading month calendar:", err);
      }
    };
    fetchMonth();
  }, [selectedMonth]);

  // Quick toggle on Today's 4 activities
  const handleToggleTodayHabit = async (habitKey) => {
    if (!todayData || !todayData.today) return;

    const currentHabitState = todayData.today[habitKey];
    const newHabitState = !currentHabitState;

    const updatedToday = {
      ...todayData.today,
      [habitKey]: newHabitState,
    };

    // Optimistic update
    const completedCount = [
      updatedToday.gym_completed,
      updatedToday.job_completed,
      updatedToday.study_completed,
      updatedToday.project_completed,
    ].filter(Boolean).length;
    const newScore = Math.round((completedCount / 4.0) * 100);

    setTodayData((prev) => ({
      ...prev,
      today: { ...updatedToday, daily_score: newScore },
      today_completion: newScore,
    }));

    if (newScore === 100) {
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 3000);
      showToast("🎉 PERFECT DAY! 100% Discipline Achieved!");
    }

    try {
      const todayStr = todayData.today.date;
      await disciplineService.saveDayData(todayStr, updatedToday, userId);

      // Refresh analytics and month data silently
      const [monthRes, analyticsRes, heatmapRes] = await Promise.all([
        disciplineService.getMonthCalendar(currentYear, selectedMonth, userId),
        disciplineService.getAnalytics(currentYear, userId),
        disciplineService.getYearHeatmap(currentYear, userId),
      ]);
      if (monthRes.success) setMonthData(monthRes);
      if (analyticsRes.success) setAnalyticsData(analyticsRes);
      if (heatmapRes.success) setYearHeatmap(heatmapRes);
    } catch (err) {
      console.error("Failed to save habit toggle:", err);
      showToast("⚠️ Failed to persist change. Reverting...");
      loadDashboardData();
    }
  };

  // Open modal for a specific day
  const handleOpenDayModal = (dayObj) => {
    setSelectedDayObj(dayObj);
    setModalFormState({
      gym_completed: dayObj.gym_completed || false,
      job_completed: dayObj.job_completed || false,
      study_completed: dayObj.study_completed || false,
      project_completed: dayObj.project_completed || false,
      notes: dayObj.notes || "",
    });
    setIsDetailModalOpen(true);
  };

  // Save changes from modal
  const handleSaveModalDay = async (e) => {
    e.preventDefault();
    if (!selectedDayObj) return;

    if (selectedDayObj.is_future) {
      alert("Cannot mark future dates as completed.");
      return;
    }

    try {
      setModalSaving(true);
      const res = await disciplineService.saveDayData(
        selectedDayObj.date,
        modalFormState,
        userId
      );

      if (res.success) {
        showToast(`Discipline record for ${selectedDayObj.date} updated!`);
        setIsDetailModalOpen(false);
        // Refresh all data
        loadDashboardData();
      }
    } catch (err) {
      console.error("Error saving day details:", err);
      alert(err.response?.data?.error || "Failed to save day data.");
    } finally {
      setModalSaving(false);
    }
  };

  // Dynamic Quote selection
  const quoteIndex = todayData?.today?.date
    ? todayData.today.date.charCodeAt(todayData.today.date.length - 1) % MOTIVATIONAL_QUOTES.length
    : 0;
  const currentQuote = MOTIVATIONAL_QUOTES[quoteIndex];

  // Helper for heatmap cell color
  const getHeatmapColorClass = (score, isFuture, isToday) => {
    if (isFuture) return "cell-future";
    if (score === 100) return "cell-perfect";
    if (score >= 75) return "cell-high";
    if (score >= 50) return "cell-medium";
    if (score >= 25) return "cell-low";
    return "cell-empty";
  };

  return (
    <div className="discipline-root">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="discipline-toast">
          <CheckCircle2 size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Confetti celebration overlay */}
      {showConfetti && <div className="celebration-burst"></div>}

      {/* ========================================================================= */}
      {/* 1. TOP BANNER & MISSION 2026 HEADER */}
      {/* ========================================================================= */}
      <div className="mission-header-card">
        <div className="mission-header-top">
          <div className="mission-branding">
            <div className="mission-icon-halo">
              <Zap size={24} className="mission-bolt-icon" />
            </div>
            <div>
              <div className="mission-tagline-badge">
                <Target size={13} />
                <span>MISSION 2026</span>
              </div>
              <h1 className="mission-main-title">Discipline Dashboard</h1>
              <p className="mission-subtitle">{currentQuote}</p>
            </div>
          </div>

          <div className="mission-actions">
            <button
              className="btn-mission-refresh"
              onClick={loadDashboardData}
              disabled={loading}
              title="Refresh Data"
            >
              <RefreshCw size={15} className={loading ? "spin" : ""} />
              <span>Sync</span>
            </button>
            <button
              className="btn-mission-back"
              onClick={() => navigate("/dashboard")}
            >
              <span>Main LifeOS</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>

        {/* 2026 Year Compounding Progress Bar */}
        <div className="mission-progress-block">
          <div className="mission-progress-labels">
            <span className="progress-title">
              <Sparkles size={14} className="text-accent" />
              2026 Annual Consistency Rate
            </span>
            <span className="progress-percentage">
              {analyticsData?.overall_year_discipline || todayData?.year_2026_progress?.yearly_score || 0}%
            </span>
          </div>
          <div className="mission-progress-track">
            <div
              className="mission-progress-fill"
              style={{
                width: `${Math.min(
                  analyticsData?.overall_year_discipline || todayData?.year_2026_progress?.yearly_score || 0,
                  100
                )}%`,
              }}
            ></div>
          </div>
          <div className="mission-progress-footer">
            <span>
              📅 {todayData?.year_2026_progress?.days_passed || 0} Days Passed
            </span>
            <span>
              ⏳ {todayData?.year_2026_progress?.days_remaining || 0} Days Remaining in 2026
            </span>
          </div>
        </div>

        {/* Top 4 Core Metrics Cards */}
        <div className="mission-metrics-grid">
          <div className="metric-box box-score">
            <div className="metric-icon-wrap blue">
              <Target size={20} />
            </div>
            <div className="metric-details">
              <span className="metric-label">Discipline Score</span>
              <h2 className="metric-val">
                {analyticsData?.overall_year_discipline || todayData?.year_2026_progress?.yearly_score || 0}%
              </h2>
              <span className="metric-hint">Overall 2026 Avg</span>
            </div>
          </div>

          <div className="metric-box box-streak">
            <div className="metric-icon-wrap flame">
              <Flame size={20} />
            </div>
            <div className="metric-details">
              <span className="metric-label">Current Streak</span>
              <h2 className="metric-val">
                {analyticsData?.streaks?.current_streak || todayData?.current_streak || 0}
                <span className="unit-day"> Days</span>
              </h2>
              <span className="metric-hint">Active Unbroken Chain</span>
            </div>
          </div>

          <div className="metric-box box-best">
            <div className="metric-icon-wrap gold">
              <Trophy size={20} />
            </div>
            <div className="metric-details">
              <span className="metric-label">Longest Streak</span>
              <h2 className="metric-val">
                {analyticsData?.streaks?.longest_streak || 0}
                <span className="unit-day"> Days</span>
              </h2>
              <span className="metric-hint">2026 Personal Best</span>
            </div>
          </div>

          <div className="metric-box box-perfect">
            <div className="metric-icon-wrap emerald">
              <Star size={20} />
            </div>
            <div className="metric-details">
              <span className="metric-label">Perfect Days</span>
              <h2 className="metric-val">
                {analyticsData?.streaks?.perfect_days || todayData?.year_2026_progress?.perfect_days || 0}
              </h2>
              <span className="metric-hint">100% Completed</span>
            </div>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="discipline-error-banner">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={loadDashboardData} className="btn-error-retry">
            Retry
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. SECTION A — TODAY'S DAILY DISCIPLINE TRACKER */}
      {/* ========================================================================= */}
      <div className="daily-tracker-card">
        <div className="daily-tracker-header">
          <div className="daily-date-group">
            <div className="today-badge">TODAY'S MISSION</div>
            <h2 className="daily-date-title">
              {today.toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </h2>
          </div>

          <div className="daily-score-badge-wrap">
            <div
              className={`score-ring ${
                todayData?.today?.daily_score === 100
                  ? "perfect"
                  : todayData?.today?.daily_score >= 75
                  ? "disciplined"
                  : "progress"
              }`}
            >
              <span className="score-num">
                {todayData?.today?.daily_score || 0}%
              </span>
            </div>
            <div className="score-text-info">
              <span className="score-title">Daily Score</span>
              <span className="score-status-desc">
                {todayData?.today?.daily_score === 100
                  ? "🎉 Perfect Day"
                  : todayData?.today?.daily_score >= 75
                  ? "💪 Disciplined Day"
                  : "⏳ In Progress"}
              </span>
            </div>
          </div>
        </div>

        {/* 4 Interactive Habit Checklist Cards */}
        <div className="habit-cards-grid">
          {/* Habit 1: Gym */}
          <div
            className={`habit-card ${
              todayData?.today?.gym_completed ? "completed" : "pending"
            }`}
            onClick={() => handleToggleTodayHabit("gym_completed")}
          >
            <div className="habit-card-left">
              <div className="habit-icon-avatar gym">
                <Dumbbell size={20} />
              </div>
              <div className="habit-info">
                <span className="habit-name">Gym</span>
                <span className="habit-subtext">Workout & Physical Fitness</span>
              </div>
            </div>
            <div className="habit-toggle-btn">
              {todayData?.today?.gym_completed ? (
                <CheckCircle2 size={24} className="check-done-icon" />
              ) : (
                <Circle size={24} className="check-pending-icon" />
              )}
            </div>
          </div>

          {/* Habit 2: Job */}
          <div
            className={`habit-card ${
              todayData?.today?.job_completed ? "completed" : "pending"
            }`}
            onClick={() => handleToggleTodayHabit("job_completed")}
          >
            <div className="habit-card-left">
              <div className="habit-icon-avatar job">
                <Briefcase size={20} />
              </div>
              <div className="habit-info">
                <span className="habit-name">Job</span>
                <span className="habit-subtext">Career, Deliverables & Tasks</span>
              </div>
            </div>
            <div className="habit-toggle-btn">
              {todayData?.today?.job_completed ? (
                <CheckCircle2 size={24} className="check-done-icon" />
              ) : (
                <Circle size={24} className="check-pending-icon" />
              )}
            </div>
          </div>

          {/* Habit 3: Study */}
          <div
            className={`habit-card ${
              todayData?.today?.study_completed ? "completed" : "pending"
            }`}
            onClick={() => handleToggleTodayHabit("study_completed")}
          >
            <div className="habit-card-left">
              <div className="habit-icon-avatar study">
                <BookOpen size={20} />
              </div>
              <div className="habit-info">
                <span className="habit-name">Study</span>
                <span className="habit-subtext">Data Analytics, SQL, Python</span>
              </div>
            </div>
            <div className="habit-toggle-btn">
              {todayData?.today?.study_completed ? (
                <CheckCircle2 size={24} className="check-done-icon" />
              ) : (
                <Circle size={24} className="check-pending-icon" />
              )}
            </div>
          </div>

          {/* Habit 4: Project */}
          <div
            className={`habit-card ${
              todayData?.today?.project_completed ? "completed" : "pending"
            }`}
            onClick={() => handleToggleTodayHabit("project_completed")}
          >
            <div className="habit-card-left">
              <div className="habit-icon-avatar project">
                <Code2 size={20} />
              </div>
              <div className="habit-info">
                <span className="habit-name">Project</span>
                <span className="habit-subtext">LifeOS & Portfolio Building</span>
              </div>
            </div>
            <div className="habit-toggle-btn">
              {todayData?.today?.project_completed ? (
                <CheckCircle2 size={24} className="check-done-icon" />
              ) : (
                <Circle size={24} className="check-pending-icon" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. SECTION B — YEAR 2026 MONTH-WISE CALENDAR & HEATMAP */}
      {/* ========================================================================= */}
      <div className="calendar-section-card">
        <div className="calendar-header-bar">
          <div className="calendar-title-group">
            <Calendar size={20} className="text-accent" />
            <div>
              <h3 className="calendar-heading">
                {FULL_MONTH_NAMES[selectedMonth - 1]} 2026 Discipline Grid
              </h3>
              <p className="calendar-subheading">
                Click any date to view details, notes, or record past activities
              </p>
            </div>
          </div>

          {/* Month summary pill */}
          <div className="month-summary-pills">
            <span className="summary-pill score">
              Score: <strong>{monthData?.summary?.monthly_score || 0}%</strong>
            </span>
            <span className="summary-pill perfect">
              ⭐ {monthData?.summary?.perfect_days || 0} Perfect
            </span>
            <span className="summary-pill disciplined">
              🔥 {monthData?.summary?.disciplined_days || 0} Disciplined
            </span>
          </div>
        </div>

        {/* 12 Months Selector Bar */}
        <div className="months-nav-bar">
          {MONTH_NAMES.map((mName, idx) => {
            const mIndex = idx + 1;
            const isSelected = selectedMonth === mIndex;
            const monthAnalyticsObj = analyticsData?.monthly_scores?.find(
              (m) => m.month_index === mIndex
            );
            return (
              <button
                key={mIndex}
                className={`month-tab-btn ${isSelected ? "active" : ""}`}
                onClick={() => setSelectedMonth(mIndex)}
              >
                <span className="month-tab-name">{mName}</span>
                {monthAnalyticsObj && monthAnalyticsObj.status !== "upcoming" && (
                  <span className="month-tab-score">
                    {Math.round(monthAnalyticsObj.score)}%
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Month Calendar Grid (Mon - Sun) */}
        <div className="calendar-grid-wrapper">
          {/* Weekday headers */}
          <div className="calendar-weekdays-row">
            {WEEKDAY_NAMES.map((w) => (
              <div key={w} className="weekday-header-cell">
                {w}
              </div>
            ))}
          </div>

          {/* Days Grid */}
          <div className="calendar-days-grid">
            {/* Empty offset padding cells before first day */}
            {monthData &&
              Array.from({ length: monthData.first_day_weekday }).map((_, i) => (
                <div key={`empty-${i}`} className="calendar-day-cell empty-offset"></div>
              ))}

            {/* Days in Month */}
            {monthData?.days?.map((day) => {
              const colorClass = getHeatmapColorClass(
                day.daily_score,
                day.is_future,
                day.is_today
              );
              return (
                <div
                  key={day.date}
                  className={`calendar-day-cell ${colorClass} ${
                    day.is_today ? "is-today-cell" : ""
                  }`}
                  onClick={() => handleOpenDayModal(day)}
                  title={`${day.date}: ${day.daily_score}%`}
                >
                  <div className="day-cell-top">
                    <span className="day-number">{day.day_number}</span>
                    {day.is_perfect && <Star size={10} className="star-perfect-icon" />}
                  </div>

                  {!day.is_future && (
                    <div className="day-habit-dots">
                      <span className={`h-dot ${day.gym_completed ? "done" : ""}`} title="Gym" />
                      <span className={`h-dot ${day.job_completed ? "done" : ""}`} title="Job" />
                      <span className={`h-dot ${day.study_completed ? "done" : ""}`} title="Study" />
                      <span className={`h-dot ${day.project_completed ? "done" : ""}`} title="Project" />
                    </div>
                  )}

                  {!day.is_future && (
                    <span className="day-score-tag">{Math.round(day.daily_score)}%</span>
                  )}
                  {day.is_future && <span className="day-future-label">Upcoming</span>}
                </div>
              );
            })}
          </div>
        </div>

        {/* Heatmap Legend */}
        <div className="heatmap-legend-row">
          <span className="legend-title">Discipline Heatmap Scale:</span>
          <div className="legend-items">
            <span className="legend-box cell-empty"></span>
            <span className="legend-text">0%</span>
            <span className="legend-box cell-low"></span>
            <span className="legend-text">25%</span>
            <span className="legend-box cell-medium"></span>
            <span className="legend-text">50%</span>
            <span className="legend-box cell-high"></span>
            <span className="legend-text">75%</span>
            <span className="legend-box cell-perfect"></span>
            <span className="legend-text">100% (Perfect Day)</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. SECTION C — 365-DAY YEAR CONTRIBUTION HEATMAP */}
      {/* ========================================================================= */}
      <div className="annual-heatmap-card">
        <div className="annual-heatmap-header">
          <div className="annual-title-group">
            <Flame size={18} className="text-accent" />
            <h3>2026 Annual Consistency Matrix (365 Days)</h3>
          </div>
          <span className="annual-badge">
            {todayData?.year_2026_progress?.disciplined_days || 0} Disciplined Days Logged
          </span>
        </div>

        <div className="annual-matrix-scroll">
          <div className="annual-matrix-grid">
            {yearHeatmap?.days?.map((d) => (
              <div
                key={d.date}
                className={`matrix-dot ${getHeatmapColorClass(
                  d.score,
                  d.is_future,
                  d.is_today
                )}`}
                onClick={() =>
                  handleOpenDayModal({
                    date: d.date,
                    daily_score: d.score,
                    is_future: d.is_future,
                    is_today: d.is_today,
                  })
                }
                title={`${d.date}: ${d.score}% completed (${d.completed_count}/4 habits)`}
              ></div>
            ))}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 5. SECTION D & E — BMW S1000 GOAL & QUARTERLY ANALYTICS */}
      {/* ========================================================================= */}
      <div className="analytics-motivation-split">
        {/* SECTION E: 🏍️ BMW S1000 MOTIVATION SYSTEM */}
        <div className="bmw-s1000-card">
          <div className="bmw-header">
            <div className="bmw-logo-group">
              <span className="bmw-badge-pill">LONG TERM MISSION</span>
              <h3 className="bmw-title">🏍️ BMW S1000 RR</h3>
            </div>
            <div className="bmw-tier-tag">
              {analyticsData?.bmw_motivation?.tier || "Performance Tier"}
            </div>
          </div>

          <p className="bmw-motto">“RIDE TOWARDS YOUR GOAL”</p>

          {/* Tachometer / Futuristic Gauge visual */}
          <div className="bmw-tachometer-box">
            <div className="bmw-progress-circle-wrap">
              <div className="bmw-glow-ring">
                <span className="bmw-percent-text">
                  {analyticsData?.bmw_motivation?.progress_percent || 0}%
                </span>
                <span className="bmw-percent-sub">Goal Unlocked</span>
              </div>
            </div>

            <div className="bmw-specs-list">
              <div className="spec-row">
                <span className="spec-name">Consistency Fuel:</span>
                <span className="spec-val">
                  {analyticsData?.overall_year_discipline || 0}%
                </span>
              </div>
              <div className="spec-row">
                <span className="spec-name">Streak Momentum:</span>
                <span className="spec-val">
                  {analyticsData?.streaks?.current_streak || 0} Days 🔥
                </span>
              </div>
              <div className="spec-row">
                <span className="spec-name">Perfect Pitstops:</span>
                <span className="spec-val">
                  {analyticsData?.streaks?.perfect_days || 0} Days ⭐
                </span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="bmw-bar-track">
            <div
              className="bmw-bar-fill"
              style={{
                width: `${Math.min(
                  analyticsData?.bmw_motivation?.progress_percent || 0,
                  100
                )}%`,
              }}
            ></div>
          </div>

          <div className="bmw-quote-card">
            <p className="bmw-quote-text">
              {analyticsData?.bmw_motivation?.quote ||
                "“The bike is the reward. Discipline is the price.”"}
            </p>
            <span className="bmw-quote-author">
              {analyticsData?.bmw_motivation?.tagline ||
                "“Every disciplined day takes you one step closer.”"}
            </span>
          </div>
        </div>

        {/* SECTION F: DYNAMIC SELF-IMPROVEMENT INSIGHTS */}
        <div className="self-improvement-card">
          <div className="improve-header">
            <div className="improve-title-group">
              <TrendingUp size={20} className="text-emerald" />
              <h3>Improve Yourself (AI Insights)</h3>
            </div>
            <span className="badge-live-ai">Live Data Analysis</span>
          </div>

          {/* 4 Pillars Habit Performance */}
          <div className="habit-meters-block">
            <h4 className="block-sub-title">Habit Consistency Breakdown</h4>
            {analyticsData?.habit_consistency && (
              <div className="habit-bars-stack">
                <div className="h-bar-item">
                  <div className="h-bar-info">
                    <span className="h-name">🏋️ Gym Consistency</span>
                    <span className="h-score">
                      {analyticsData.habit_consistency.Gym}%
                    </span>
                  </div>
                  <div className="h-track">
                    <div
                      className="h-fill gym"
                      style={{ width: `${analyticsData.habit_consistency.Gym}%` }}
                    ></div>
                  </div>
                </div>

                <div className="h-bar-item">
                  <div className="h-bar-info">
                    <span className="h-name">💼 Job Consistency</span>
                    <span className="h-score">
                      {analyticsData.habit_consistency.Job}%
                    </span>
                  </div>
                  <div className="h-track">
                    <div
                      className="h-fill job"
                      style={{ width: `${analyticsData.habit_consistency.Job}%` }}
                    ></div>
                  </div>
                </div>

                <div className="h-bar-item">
                  <div className="h-bar-info">
                    <span className="h-name">📚 Study Consistency</span>
                    <span className="h-score">
                      {analyticsData.habit_consistency.Study}%
                    </span>
                  </div>
                  <div className="h-track">
                    <div
                      className="h-fill study"
                      style={{ width: `${analyticsData.habit_consistency.Study}%` }}
                    ></div>
                  </div>
                </div>

                <div className="h-bar-item">
                  <div className="h-bar-info">
                    <span className="h-name">💻 Project Consistency</span>
                    <span className="h-score">
                      {analyticsData.habit_consistency.Project}%
                    </span>
                  </div>
                  <div className="h-track">
                    <div
                      className="h-fill project"
                      style={{
                        width: `${analyticsData.habit_consistency.Project}%`,
                      }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Highlight Insights Box */}
          <div className="insights-feed-box">
            <div className="strong-weak-grid">
              <div className="sw-pill strong">
                <span className="sw-tag">🟢 Strongest Habit</span>
                <span className="sw-val">
                  {analyticsData?.self_improvement?.strongest_habit?.name || "Gym"} (
                  {analyticsData?.self_improvement?.strongest_habit?.consistency || 0}%)
                </span>
              </div>
              <div className="sw-pill weak">
                <span className="sw-tag">🔴 Needs Focus</span>
                <span className="sw-val">
                  {analyticsData?.self_improvement?.weakest_habit?.name || "Project"} (
                  {analyticsData?.self_improvement?.weakest_habit?.consistency || 0}%)
                </span>
              </div>
            </div>

            <div className="focus-advice-card">
              <div className="focus-title">
                <Target size={15} />
                <span>Focus Recommendation For Next Month:</span>
              </div>
              <p className="focus-desc">
                {analyticsData?.self_improvement?.focus_recommendation ||
                  "Maintain study and project habits early in the morning."}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 6. SECTION D — QUARTERLY ANALYTICS & MONTHLY SCORE PROGRESSION */}
      {/* ========================================================================= */}
      <div className="quarterly-section-card">
        <div className="quarterly-header">
          <div className="quarterly-title-group">
            <BarChart3 size={20} className="text-accent" />
            <h3>2026 Quarterly Performance Breakdown</h3>
          </div>
        </div>

        <div className="quarters-grid">
          {analyticsData?.quarterly_analytics?.map((q) => (
            <div key={q.quarter} className={`quarter-card ${q.status}`}>
              <div className="quarter-card-top">
                <span className="quarter-id">{q.quarter}</span>
                <span className="quarter-period">{q.title}</span>
                <span className={`quarter-status-badge ${q.status}`}>
                  {q.status === "completed"
                    ? "Completed"
                    : q.status === "in_progress"
                    ? "Active"
                    : "Upcoming"}
                </span>
              </div>

              <div className="quarter-score-row">
                <span className="q-score-num">{q.avg_score}%</span>
                <span className="q-score-label">Avg Discipline</span>
              </div>

              <div className="quarter-stats-list">
                <div className="q-stat-row">
                  <span>🏋️ Gym:</span>
                  <strong>{q.gym_consistency}%</strong>
                </div>
                <div className="q-stat-row">
                  <span>💼 Job:</span>
                  <strong>{q.job_consistency}%</strong>
                </div>
                <div className="q-stat-row">
                  <span>📚 Study:</span>
                  <strong>{q.study_consistency}%</strong>
                </div>
                <div className="q-stat-row">
                  <span>💻 Project:</span>
                  <strong>{q.project_consistency}%</strong>
                </div>
                <div className="q-stat-row highlight">
                  <span>⭐ Perfect Days:</span>
                  <strong>{q.perfect_days}</strong>
                </div>
                <div className="q-stat-row highlight">
                  <span>🔥 Best Streak:</span>
                  <strong>{q.best_streak} Days</strong>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* 12-Month Discipline Bar Chart */}
        <div className="monthly-chart-block">
          <h4 className="chart-block-title">Monthly Discipline Score Trend (2026)</h4>
          <div className="monthly-bars-chart">
            {analyticsData?.monthly_scores?.map((m) => (
              <div key={m.month_index} className="month-chart-col">
                <div className="bar-track">
                  <div
                    className={`bar-fill ${m.status}`}
                    style={{ height: `${m.score}%` }}
                    title={`${m.full_month_name}: ${m.score}%`}
                  >
                    {m.status !== "upcoming" && (
                      <span className="bar-val-tooltip">{Math.round(m.score)}%</span>
                    )}
                  </div>
                </div>
                <span className="month-label-col">{m.month_name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 7. DAILY DETAIL MODAL / DRAWER */}
      {/* ========================================================================= */}
      {isDetailModalOpen && selectedDayObj && (
        <div className="modal-backdrop">
          <div className="discipline-modal-box">
            <div className="modal-header-row">
              <div className="modal-header-text">
                <div className="modal-pill-tag">DAILY DETAIL PANEL</div>
                <h3 className="modal-date-heading">
                  {selectedDayObj.date}
                </h3>
              </div>
              <button
                className="btn-modal-x"
                onClick={() => setIsDetailModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveModalDay} className="modal-form-body">
              <div className="modal-score-summary">
                <div className="modal-score-circle">
                  <span>{selectedDayObj.daily_score || 0}%</span>
                </div>
                <div>
                  <h4 className="modal-status-text">
                    {selectedDayObj.is_future
                      ? "Upcoming Day"
                      : selectedDayObj.daily_score === 100
                      ? "🎉 Perfect 100% Day"
                      : selectedDayObj.daily_score >= 75
                      ? "💪 Disciplined Day"
                      : "In Progress"}
                  </h4>
                  <p className="modal-quote-text">
                    “Discipline beats motivation. Every single day.”
                  </p>
                </div>
              </div>

              {/* 4 Habit Toggles inside Modal */}
              <div className="modal-habits-checklist">
                <div
                  className={`modal-habit-row ${
                    modalFormState.gym_completed ? "checked" : ""
                  }`}
                  onClick={() =>
                    !selectedDayObj.is_future &&
                    setModalFormState({
                      ...modalFormState,
                      gym_completed: !modalFormState.gym_completed,
                    })
                  }
                >
                  <div className="m-habit-left">
                    <Dumbbell size={18} className="text-blue" />
                    <span>🏋️ Gym</span>
                  </div>
                  <div className="m-habit-checkbox">
                    {modalFormState.gym_completed ? (
                      <CheckCircle2 size={22} className="check-done" />
                    ) : (
                      <Circle size={22} className="check-pending" />
                    )}
                  </div>
                </div>

                <div
                  className={`modal-habit-row ${
                    modalFormState.job_completed ? "checked" : ""
                  }`}
                  onClick={() =>
                    !selectedDayObj.is_future &&
                    setModalFormState({
                      ...modalFormState,
                      job_completed: !modalFormState.job_completed,
                    })
                  }
                >
                  <div className="m-habit-left">
                    <Briefcase size={18} className="text-amber" />
                    <span>💼 Job</span>
                  </div>
                  <div className="m-habit-checkbox">
                    {modalFormState.job_completed ? (
                      <CheckCircle2 size={22} className="check-done" />
                    ) : (
                      <Circle size={22} className="check-pending" />
                    )}
                  </div>
                </div>

                <div
                  className={`modal-habit-row ${
                    modalFormState.study_completed ? "checked" : ""
                  }`}
                  onClick={() =>
                    !selectedDayObj.is_future &&
                    setModalFormState({
                      ...modalFormState,
                      study_completed: !modalFormState.study_completed,
                    })
                  }
                >
                  <div className="m-habit-left">
                    <BookOpen size={18} className="text-purple" />
                    <span>📚 Study</span>
                  </div>
                  <div className="m-habit-checkbox">
                    {modalFormState.study_completed ? (
                      <CheckCircle2 size={22} className="check-done" />
                    ) : (
                      <Circle size={22} className="check-pending" />
                    )}
                  </div>
                </div>

                <div
                  className={`modal-habit-row ${
                    modalFormState.project_completed ? "checked" : ""
                  }`}
                  onClick={() =>
                    !selectedDayObj.is_future &&
                    setModalFormState({
                      ...modalFormState,
                      project_completed: !modalFormState.project_completed,
                    })
                  }
                >
                  <div className="m-habit-left">
                    <Code2 size={18} className="text-emerald" />
                    <span>💻 Project</span>
                  </div>
                  <div className="m-habit-checkbox">
                    {modalFormState.project_completed ? (
                      <CheckCircle2 size={22} className="check-done" />
                    ) : (
                      <Circle size={22} className="check-pending" />
                    )}
                  </div>
                </div>
              </div>

              {/* Notes input */}
              <div className="modal-notes-group">
                <label className="modal-label">Day Reflections / Notes</label>
                <textarea
                  rows={3}
                  placeholder="Record your achievements, learnings, or thoughts for this day..."
                  value={modalFormState.notes}
                  onChange={(e) =>
                    setModalFormState({ ...modalFormState, notes: e.target.value })
                  }
                  className="modal-textarea"
                  disabled={selectedDayObj.is_future}
                />
              </div>

              <div className="modal-actions-footer">
                <button
                  type="button"
                  className="btn-modal-cancel"
                  onClick={() => setIsDetailModalOpen(false)}
                >
                  Close
                </button>
                {!selectedDayObj.is_future && (
                  <button
                    type="submit"
                    className="btn-modal-save"
                    disabled={modalSaving}
                  >
                    {modalSaving ? "Saving..." : "Save Daily Discipline"}
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default DisciplineDashboard;
