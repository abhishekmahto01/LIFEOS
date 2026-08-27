import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Zap,
  Flame,
  Trophy,
  Star,
  CheckCircle2,
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
  Plus,
  Compass,
  Activity,
  Layers,
  PieChart,
} from "lucide-react";
import { disciplineService } from "../services/disciplineService";
import riderBg from "../assets/images/cinematic-rider.jpg";
import "./DisciplineDashboard.css";

const FULL_MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const DEFAULT_ROUTINES = [
  { key: "deep_work", label: "Deep Work", icon: "💼", category: "Productivity" },
  { key: "gym", label: "Gym / Workout", icon: "🏋️", category: "Fitness" },
  { key: "study", label: "Study / DS-365", icon: "🧠", category: "Learning" },
  { key: "job", label: "Job Applications", icon: "🎯", category: "Career" },
  { key: "reading", label: "Reading / Meditating", icon: "📖", category: "Mind" },
  { key: "wake_early", label: "Wake Up Early", icon: "⏰", category: "Routine" },
  { key: "budget", label: "Budget Tracking", icon: "💰", category: "Finance" },
  { key: "cold_shower", label: "Cold Shower", icon: "🚿", category: "Health" },
  { key: "clean_living", label: "Clean Living / No Alcohol", icon: "🚫", category: "Health" },
  { key: "reflection", label: "Time with Self / Reflection", icon: "🧘", category: "Mind" },
];

function DisciplineDashboard() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const userId = user.user_id || 1;

  const currentYear = 2026;
  const todayDate = new Date();
  const currentMonthIndex = todayDate.getFullYear() === currentYear ? todayDate.getMonth() + 1 : 8;

  // Selected Month State
  const [selectedMonth, setSelectedMonth] = useState(currentMonthIndex);
  const [matrixData, setMatrixData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeAnalyticsTab, setActiveAnalyticsTab] = useState("overview"); // overview, habits, weekday, bmw

  // Hovered day tooltip for Area Chart
  const [hoveredAreaPoint, setHoveredAreaPoint] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Load Month Matrix Data
  const loadMonthData = useCallback(async (monthNum) => {
    try {
      setLoading(true);
      setError(null);
      const res = await disciplineService.getMonthMatrix(currentYear, monthNum, userId);
      if (res && res.success) {
        setMatrixData(res);
      } else {
        setError("Failed to load discipline data for this month.");
      }
    } catch (err) {
      console.error("Error loading month matrix:", err);
      setError("Network or server error while loading matrix.");
    } finally {
      setLoading(false);
    }
  }, [userId, currentYear]);

  useEffect(() => {
    loadMonthData(selectedMonth);
  }, [selectedMonth, loadMonthData]);

  // Handle Checkbox Cell Toggle
  const handleCellToggle = async (dateStr, habitKey, currentVal) => {
    // Check if target date is in the future
    const targetDay = daysList.find((d) => d.date === dateStr);
    if (targetDay && targetDay.is_future) {
      showToast("Future dates are locked and cannot be marked in advance.");
      return;
    }

    const newVal = !currentVal;

    // Optimistic UI Update in local state
    setMatrixData((prev) => {
      if (!prev || !prev.days) return prev;
      const updatedDays = prev.days.map((d) => {
        if (d.date === dateStr) {
          const updatedHabits = { ...d.habits, [habitKey]: newVal };
          const doneCount = Object.values(updatedHabits).filter(Boolean).length;
          const goalCount = d.goal_count || DEFAULT_ROUTINES.length;
          const openCount = Math.max(goalCount - doneCount, 0);
          const scorePercent = Math.round((doneCount / goalCount) * 100);
          return {
            ...d,
            habits: updatedHabits,
            done_count: doneCount,
            open_count: openCount,
            score_percent: scorePercent,
          };
        }
        return d;
      });

      // Recalculate weeks summary
      const updatedWeeks = (prev.weeks_summary || []).map((w) => {
        const wDays = updatedDays.filter((d) => d.week_num === w.week_num);
        const wDone = wDays.reduce((acc, d) => acc + (d.done_count || 0), 0);
        const wGoal = wDays.reduce((acc, d) => acc + (d.goal_count || 0), 0);
        const wProg = wGoal > 0 ? Math.round((wDone / wGoal) * 100) : 0;
        return {
          ...w,
          total_done: wDone,
          total_goal: wGoal,
          progress_percent: wProg,
        };
      });

      return {
        ...prev,
        days: updatedDays,
        weeks_summary: updatedWeeks,
      };
    });

    try {
      await disciplineService.toggleHabitCell(dateStr, habitKey, newVal, userId);
    } catch (err) {
      console.error("Error persisting habit toggle:", err);
      showToast("Error saving change to server. Retrying...");
      loadMonthData(selectedMonth);
    }
  };

  const daysList = matrixData?.days || [];
  const weeksSummary = matrixData?.weeks_summary || [];
  const routinesList = matrixData?.routines_presets || DEFAULT_ROUTINES;

  // Compute SVG coordinates for the Electric Blue Area Line Chart
  const areaChartPoints = useMemo(() => {
    if (!daysList.length) return { pathD: "", areaD: "", points: [] };

    const svgWidth = 1000;
    const svgHeight = 160;
    const paddingX = 20;
    const paddingY = 20;
    const usableWidth = svgWidth - paddingX * 2;
    const usableHeight = svgHeight - paddingY * 2;

    const points = daysList.map((d, idx) => {
      const x = paddingX + (idx / Math.max(daysList.length - 1, 1)) * usableWidth;
      const score = Math.min(Math.max(d.score_percent || 0, 0), 100);
      const y = svgHeight - paddingY - (score / 100) * usableHeight;
      return { x, y, day: d.day, date: d.date, score, weekday: d.weekday, done: d.done_count, goal: d.goal_count };
    });

    // Build smooth cubic bezier or line path
    let pathD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cp1x = prev.x + (curr.x - prev.x) / 2;
      const cp1y = prev.y;
      const cp2x = prev.x + (curr.x - prev.x) / 2;
      const cp2y = curr.y;
      pathD += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${curr.x} ${curr.y}`;
    }

    const firstPt = points[0];
    const lastPt = points[points.length - 1];
    const areaD = `${pathD} L ${lastPt.x} ${svgHeight - paddingY} L ${firstPt.x} ${svgHeight - paddingY} Z`;

    return { pathD, areaD, points };
  }, [daysList]);

  // Overall Month Stats
  const monthDoneTotal = useMemo(() => {
    return daysList.reduce((acc, d) => acc + (d.done_count || 0), 0);
  }, [daysList]);

  const monthGoalTotal = useMemo(() => {
    return daysList.reduce((acc, d) => acc + (d.goal_count || 0), 0);
  }, [daysList]);

  const monthScoreAvg = useMemo(() => {
    if (!monthGoalTotal) return 0;
    return Math.round((monthDoneTotal / monthGoalTotal) * 100);
  }, [monthDoneTotal, monthGoalTotal]);

  return (
    <div className="disc-matrix-page-root">
      {/* Background Ambient Glows */}
      <div className="disc-ambient-glow top-cyan"></div>
      <div className="disc-ambient-glow bottom-magenta"></div>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="disc-floating-toast">
          <Sparkles size={14} className="toast-icon" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 01. TOP NAVIGATION & HEADER */}
      {/* ========================================================================= */}
      <header className="disc-top-header">
        <div className="header-left-col">
          <button
            className="btn-back-dash"
            onClick={() => navigate("/dashboard")}
            data-cursor="pointer"
          >
            <ChevronLeft size={16} />
            <span>Dashboard</span>
          </button>
          <div className="header-title-badge">
            <span className="live-pulse-radar"></span>
            <span className="title-txt">DISCIPLINE MATRIX &bull; {currentYear}</span>
          </div>
        </div>

        {/* Month Selector Pills */}
        <div className="month-selector-track">
          {FULL_MONTH_NAMES.map((name, idx) => {
            const mNum = idx + 1;
            const isSelected = selectedMonth === mNum;
            const isCurrent = currentMonthIndex === mNum;
            return (
              <button
                key={mNum}
                className={`month-tab-pill ${isSelected ? "active" : ""} ${isCurrent ? "current-month" : ""}`}
                onClick={() => setSelectedMonth(mNum)}
                data-cursor="pointer"
              >
                <span>{name.toUpperCase()}</span>
                {isCurrent && <span className="current-dot"></span>}
              </button>
            );
          })}
        </div>

        <div className="header-right-col">
          <div className="header-stat-pill">
            <Flame size={15} className="text-orange" />
            <span>{matrixData?.current_streak || 0} DAY STREAK</span>
          </div>
          <button
            className="btn-header-refresh"
            onClick={() => loadMonthData(selectedMonth)}
            title="Refresh Data"
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? "spin" : ""} />
          </button>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* 02. TOP AREA CHART: MONTHLY OVERVIEW (Electric Cyan/Blue Spline) */}
      {/* ========================================================================= */}
      <section className="disc-section-top-area">
        <div className="area-chart-container glass-card">
          <div className="area-chart-header">
            <div className="ach-left">
              <span className="ach-kicker">{FULL_MONTH_NAMES[selectedMonth - 1]?.toUpperCase()} OVERVIEW</span>
              <h2 className="ach-title">Daily Discipline Trajectory</h2>
            </div>
            <div className="ach-stats-row">
              <div className="ach-stat-item">
                <span className="stat-lbl">MONTH SCORE</span>
                <span className="stat-val cyan">{monthScoreAvg}%</span>
              </div>
              <div className="ach-stat-item">
                <span className="stat-lbl">TOTAL DONE</span>
                <span className="stat-val emerald">{monthDoneTotal}</span>
              </div>
              <div className="ach-stat-item">
                <span className="stat-lbl">TARGET GOAL</span>
                <span className="stat-val">{monthGoalTotal}</span>
              </div>
            </div>
          </div>

          {/* SVG Electric Area Chart */}
          <div className="area-svg-wrapper">
            {/* Y-Axis scale labels */}
            <div className="area-y-axis">
              <span>100%</span>
              <span>80%</span>
              <span>60%</span>
              <span>40%</span>
              <span>20%</span>
              <span>0%</span>
            </div>

            <svg
              viewBox="0 0 1000 160"
              preserveAspectRatio="none"
              className="electric-area-svg"
            >
              <defs>
                {/* Electric Cyan Neon Gradient */}
                <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#00f2fe" stopOpacity="0.55" />
                  <stop offset="40%" stopColor="#00b4d8" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#07090e" stopOpacity="0.0" />
                </linearGradient>
                {/* Line Glow Filter */}
                <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {/* Horizontal Grid lines */}
              <line x1="20" y1="20" x2="980" y2="20" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
              <line x1="20" y1="50" x2="980" y2="50" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
              <line x1="20" y1="80" x2="980" y2="80" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
              <line x1="20" y1="110" x2="980" y2="110" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />
              <line x1="20" y1="140" x2="980" y2="140" stroke="rgba(255,255,255,0.06)" strokeDasharray="4 4" />

              {/* Filled Area */}
              {areaChartPoints.areaD && (
                <path d={areaChartPoints.areaD} fill="url(#areaGradient)" />
              )}

              {/* Neon Spline Path */}
              {areaChartPoints.pathD && (
                <path
                  d={areaChartPoints.pathD}
                  fill="none"
                  stroke="#00f2fe"
                  strokeWidth="2.5"
                  filter="url(#neonGlow)"
                />
              )}

              {/* Interactive Data Points */}
              {areaChartPoints.points.map((pt, idx) => (
                <circle
                  key={idx}
                  cx={pt.x}
                  cy={pt.y}
                  r="3.5"
                  className={`area-point-dot ${hoveredAreaPoint?.day === pt.day ? "active" : ""}`}
                  onMouseEnter={() => setHoveredAreaPoint(pt)}
                  onMouseLeave={() => setHoveredAreaPoint(null)}
                />
              ))}
            </svg>

            {/* Hover Tooltip Card */}
            {hoveredAreaPoint && (
              <div
                className="area-hover-tooltip"
                style={{
                  left: `${(hoveredAreaPoint.x / 1000) * 100}%`,
                }}
              >
                <div className="tooltip-header">
                  <span>{hoveredAreaPoint.weekday} {hoveredAreaPoint.day} {FULL_MONTH_NAMES[selectedMonth - 1]}</span>
                </div>
                <div className="tooltip-body">
                  <div className="tooltip-score">
                    <span className="sc-lbl">Score</span>
                    <span className="sc-val">{hoveredAreaPoint.score}%</span>
                  </div>
                  <div className="tooltip-count">
                    <span>{hoveredAreaPoint.done} / {hoveredAreaPoint.goal} Habits</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 03. CENTER: SPREADSHEET HABIT CHECKBOX MATRIX */}
      {/* ========================================================================= */}
      <section className="disc-section-matrix">
        <div className="spreadsheet-card glass-card">
          <div className="spreadsheet-header-bar">
            <div className="sh-left">
              <span className="sh-badge">HABIT MATRIX</span>
              <h3 className="sh-title">Daily Execution Tracking</h3>
            </div>
            <div className="sh-legend">
              <span className="legend-tag w1"><span className="dot"></span>Week 1</span>
              <span className="legend-tag w2"><span className="dot"></span>Week 2</span>
              <span className="legend-tag w3"><span className="dot"></span>Week 3</span>
              <span className="legend-tag w4"><span className="dot"></span>Week 4</span>
              {weeksSummary.length > 4 && (
                <span className="legend-tag w5"><span className="dot"></span>Week 5</span>
              )}
            </div>
          </div>

          <div className="matrix-table-scroll-container">
            <table className="discipline-spreadsheet-table">
              <thead>
                {/* Top Header Row: Grouped by Weeks */}
                <tr className="row-weeks-banner">
                  <th className="col-sticky-routine" rowSpan={2}>
                    <div className="th-routine-box">DAILY ROUTINES</div>
                  </th>
                  <th className="col-sticky-goal" rowSpan={2}>
                    <div className="th-goal-box">GOALS</div>
                  </th>
                  {weeksSummary.map((w) => (
                    <th
                      key={w.week_num}
                      colSpan={w.days_count}
                      className={`th-week-header ${w.color_name}`}
                    >
                      <div className="week-header-inner">
                        <span>{w.label}</span>
                        <span className="week-badge">{w.progress_percent}%</span>
                      </div>
                    </th>
                  ))}
                </tr>

                {/* Second Header Row: Day Names and Dates */}
                <tr className="row-days-subheaders">
                  {daysList.map((d) => (
                    <th
                      key={d.date}
                      className={`th-day-col ${d.week_color} ${d.is_today ? "is-today" : ""} ${d.is_future ? "is-future" : ""}`}
                    >
                      <div className="day-col-header">
                        <span className="day-weekday">{d.weekday}</span>
                        <span className="day-number">{d.day}</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {/* Routine Rows with Interactive Checkboxes */}
                {routinesList.map((routine) => {
                  const completedDaysInMonth = daysList.filter(
                    (d) => d.habits && d.habits[routine.key]
                  ).length;

                  return (
                    <tr key={routine.key} className="routine-data-row">
                      {/* Fixed Routine Name Column */}
                      <td className="cell-routine-name col-sticky-routine">
                        <div className="routine-name-wrap">
                          <span className="routine-emoji">{routine.icon}</span>
                          <span className="routine-label">{routine.label}</span>
                        </div>
                      </td>

                      {/* Fixed Target Goal Column */}
                      <td className="cell-routine-goal col-sticky-goal">
                        <span className="goal-num">{daysList.length}</span>
                      </td>

                      {/* Day Checkbox Cells */}
                      {daysList.map((d) => {
                        const isChecked = Boolean(d.habits && d.habits[routine.key]);
                        return (
                          <td
                            key={d.date}
                            className={`cell-checkbox ${d.week_color} ${d.is_today ? "is-today" : ""} ${d.is_future ? "is-future-disabled" : ""}`}
                            onClick={() => {
                              if (d.is_future) {
                                showToast("Future dates are locked.");
                                return;
                              }
                              handleCellToggle(d.date, routine.key, isChecked);
                            }}
                            data-cursor={d.is_future ? "not-allowed" : "pointer"}
                            title={d.is_future ? "Future date locked" : undefined}
                          >
                            <div className={`matrix-checkbox-box ${isChecked ? "checked" : ""} ${d.is_future ? "disabled" : ""}`}>
                              {isChecked ? <Check size={12} strokeWidth={3.5} /> : null}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 04. BOTTOM: MULTI-COLOR WEEKLY BAR CHART & ANALYTICS OVERVIEW */}
      {/* ========================================================================= */}
      <section className="disc-section-bottom-bars">
        <div className="overview-analytics-card glass-card">
          <div className="overview-header-row">
            <div className="ov-left">
              <span className="ov-badge">OVERVIEW &bull; ANALYTICS</span>
              <h3 className="ov-title">Weekly Color-Coded Distribution</h3>
            </div>
            <div className="ov-nav-tabs">
              <button
                className={`ov-tab-btn ${activeAnalyticsTab === "overview" ? "active" : ""}`}
                onClick={() => setActiveAnalyticsTab("overview")}
              >
                Weekly Bars
              </button>
              <button
                className={`ov-tab-btn ${activeAnalyticsTab === "habits" ? "active" : ""}`}
                onClick={() => setActiveAnalyticsTab("habits")}
              >
                Habit Breakdown
              </button>
              <button
                className={`ov-tab-btn ${activeAnalyticsTab === "weekday" ? "active" : ""}`}
                onClick={() => setActiveAnalyticsTab("weekday")}
              >
                Day Heatmap
              </button>
            </div>
          </div>

          {activeAnalyticsTab === "overview" && (
            <div className="bottom-bars-view-container">
              {/* Daily Vertical Bars Grouped by Week */}
              <div className="daily-bars-track-container">
                <div className="bars-y-scale">
                  <span>10</span>
                  <span>7</span>
                  <span>5</span>
                  <span>2</span>
                  <span>0</span>
                </div>

                <div className="bars-columns-grid">
                  {daysList.map((d) => {
                    const doneCnt = d.done_count || 0;
                    const goalCnt = d.goal_count || 10;
                    const heightPct = Math.round((doneCnt / Math.max(goalCnt, 1)) * 100);

                    return (
                      <div
                        key={d.date}
                        className={`daily-bar-column ${d.week_color} ${d.is_today ? "is-today" : ""}`}
                        title={`${d.weekday} ${d.day}: ${doneCnt}/${goalCnt} habits (${heightPct}%)`}
                      >
                        <div className="bar-tube-slot">
                          <div
                            className="bar-tube-fill"
                            style={{ height: `${heightPct}%` }}
                          >
                            {doneCnt > 0 && <span className="bar-num-tag">{doneCnt}</span>}
                          </div>
                        </div>
                        <span className="bar-day-lbl">{d.day}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Data Table Rows beneath Bars: DONE, GOAL, OPEN, WEEKLY PROGRESS */}
              <div className="bottom-analytics-matrix-table">
                {/* DONE Row */}
                <div className="matrix-metric-row">
                  <div className="metric-header-cell">DONE</div>
                  <div className="metric-values-cells">
                    {daysList.map((d) => (
                      <div key={d.date} className={`val-cell ${d.week_color} done`}>
                        {d.done_count || 0}
                      </div>
                    ))}
                  </div>
                </div>

                {/* GOAL Row */}
                <div className="matrix-metric-row">
                  <div className="metric-header-cell">GOAL</div>
                  <div className="metric-values-cells">
                    {daysList.map((d) => (
                      <div key={d.date} className="val-cell goal">
                        {d.goal_count || 10}
                      </div>
                    ))}
                  </div>
                </div>

                {/* OPEN Row */}
                <div className="matrix-metric-row">
                  <div className="metric-header-cell">OPEN</div>
                  <div className="metric-values-cells">
                    {daysList.map((d) => (
                      <div key={d.date} className="val-cell open">
                        {d.open_count || 0}
                      </div>
                    ))}
                  </div>
                </div>

                {/* WEEKLY PROGRESS Row */}
                <div className="matrix-metric-row progress-row">
                  <div className="metric-header-cell">WEEKLY PROGRESS</div>
                  <div className="weekly-progress-spans-container">
                    {weeksSummary.map((w) => (
                      <div
                        key={w.week_num}
                        className={`week-progress-block ${w.color_name}`}
                        style={{ flex: w.days_count }}
                      >
                        <div className="prog-track">
                          <div
                            className="prog-fill"
                            style={{ width: `${w.progress_percent}%` }}
                          ></div>
                        </div>
                        <span className="prog-percent-text">{w.progress_percent}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* 05. SUGGESTED GRAPH: HABIT BREAKDOWN & CONSISTENCY */}
          {/* ========================================================================= */}
          {activeAnalyticsTab === "habits" && (
            <div className="analytics-tab-panel habit-adherence-panel">
              <div className="habit-breakdown-grid">
                {(matrixData?.habit_adherence || []).map((h) => (
                  <div key={h.key} className="habit-stat-card glass-card">
                    <div className="hsc-header">
                      <span className="hsc-icon">{h.icon}</span>
                      <div className="hsc-info">
                        <span className="hsc-label">{h.label}</span>
                        <span className="hsc-category">{h.category}</span>
                      </div>
                      <span className="hsc-pct cyan">{h.adherence_percent}%</span>
                    </div>

                    <div className="hsc-progress-bar">
                      <div
                        className="hsc-progress-fill"
                        style={{ width: `${h.adherence_percent}%` }}
                      ></div>
                    </div>

                    <div className="hsc-footer">
                      <span>{h.completed_count} Days Completed</span>
                      <span>Target: {h.goal_target} Days</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* 06. SUGGESTED GRAPH: DAY-OF-WEEK BEHAVIORAL VARIANCE */}
          {/* ========================================================================= */}
          {activeAnalyticsTab === "weekday" && (
            <div className="analytics-tab-panel weekday-heatmap-panel">
              <div className="weekday-cards-grid">
                {(matrixData?.day_of_week_distribution || []).map((day) => {
                  const isStrong = day.adherence_percent >= 80;
                  const isWeak = day.adherence_percent < 50;

                  return (
                    <div key={day.day_name} className="weekday-card glass-card">
                      <div className="wd-header">
                        <span className="wd-name">{day.day_name}</span>
                        <span className={`wd-badge ${isStrong ? "strong" : isWeak ? "weak" : "med"}`}>
                          {day.adherence_percent}%
                        </span>
                      </div>

                      <div className="wd-bar-wrapper">
                        <div
                          className={`wd-bar-fill ${isStrong ? "strong" : isWeak ? "weak" : "med"}`}
                          style={{ height: `${day.adherence_percent}%` }}
                        ></div>
                      </div>

                      <div className="wd-footer">
                        <span>{day.done} of {day.total} Routines</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default DisciplineDashboard;
