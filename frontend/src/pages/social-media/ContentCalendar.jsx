import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  PlusCircle,
  Clock,
  Filter,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import "./SocialMedia.css";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function ContentCalendar() {
  const navigate = useNavigate();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [platformFilter, setPlatformFilter] = useState("all");

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayIndex = new Date(year, month, 1).getDay();

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const days = [];
  for (let i = 0; i < firstDayIndex; i++) {
    days.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    days.push(d);
  }

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="calendar" />

      {/* Calendar Header Card */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          border: "1px solid var(--border-card, #e2e8f0)",
          borderRadius: "16px",
          padding: "20px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          boxShadow: "var(--shadow-card, 0 4px 14px rgba(15, 23, 42, 0.03))",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <button
            onClick={prevMonth}
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              border: "1px solid var(--border-card, #e2e8f0)",
              background: "var(--bg-surface-elevated, #f8fafc)",
              color: "var(--text-primary, #0f172a)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <ChevronLeft size={18} />
          </button>

          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: "800", color: "var(--text-primary, #0f172a)" }}>
            {MONTHS[month]} {year}
          </h2>

          <button
            onClick={nextMonth}
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              border: "1px solid var(--border-card, #e2e8f0)",
              background: "var(--bg-surface-elevated, #f8fafc)",
              color: "var(--text-primary, #0f172a)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* Platform Filters */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            className={`sm-tab-btn ${platformFilter === "all" ? "active" : ""}`}
            onClick={() => setPlatformFilter("all")}
          >
            All Platforms
          </button>
          <button
            className={`sm-tab-btn ${platformFilter === "youtube" ? "active" : ""}`}
            onClick={() => setPlatformFilter("youtube")}
          >
            <Youtube size={15} color="#ff0000" /> YouTube
          </button>
          <button
            className={`sm-tab-btn ${platformFilter === "instagram" ? "active" : ""}`}
            onClick={() => setPlatformFilter("instagram")}
          >
            <Instagram size={15} color="#e1306c" /> Instagram
          </button>
          <button
            className={`sm-tab-btn ${platformFilter === "facebook" ? "active" : ""}`}
            onClick={() => setPlatformFilter("facebook")}
          >
            <Facebook size={15} color="#1877f2" /> Facebook
          </button>
        </div>
      </div>

      {/* Calendar Month Grid */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          border: "1px solid var(--border-card, #e2e8f0)",
          borderRadius: "16px",
          padding: "20px",
          boxShadow: "var(--shadow-card, 0 4px 14px rgba(15, 23, 42, 0.03))",
        }}
      >
        {/* Day Name Headers */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 1fr)",
            gap: "8px",
            textAlign: "center",
            fontWeight: "700",
            fontSize: "12px",
            color: "var(--text-muted, #64748b)",
            marginBottom: "12px",
          }}
        >
          <span>SUN</span>
          <span>MON</span>
          <span>TUE</span>
          <span>WED</span>
          <span>THU</span>
          <span>FRI</span>
          <span>SAT</span>
        </div>

        {/* Day Cells Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 1fr)",
            gap: "8px",
          }}
        >
          {days.map((day, idx) => {
            if (!day) {
              return (
                <div
                  key={`empty-${idx}`}
                  style={{
                    minHeight: "90px",
                    borderRadius: "10px",
                    background: "var(--bg-surface-elevated, #f8fafc)",
                    opacity: 0.3,
                  }}
                />
              );
            }

            const isToday =
              day === new Date().getDate() &&
              month === new Date().getMonth() &&
              year === new Date().getFullYear();

            return (
              <div
                key={`day-${day}`}
                style={{
                  minHeight: "90px",
                  borderRadius: "10px",
                  border: isToday
                    ? "2px solid var(--accent-blue, #2563eb)"
                    : "1px solid var(--border-card, #e2e8f0)",
                  background: isToday
                    ? "var(--accent-blue-soft, rgba(37, 99, 235, 0.05))"
                    : "var(--bg-surface, #ffffff)",
                  padding: "8px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  transition: "all 0.2s ease",
                  cursor: "pointer",
                }}
                onClick={() => navigate("/social-media/create")}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: isToday ? "800" : "600",
                      color: isToday ? "var(--accent-blue, #2563eb)" : "var(--text-primary, #0f172a)",
                    }}
                  >
                    {day}
                  </span>
                  {isToday && (
                    <span
                      style={{
                        fontSize: "9px",
                        fontWeight: "800",
                        color: "var(--accent-blue, #2563eb)",
                        background: "rgba(37, 99, 235, 0.1)",
                        padding: "1px 5px",
                        borderRadius: "4px",
                      }}
                    >
                      TODAY
                    </span>
                  )}
                </div>

                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--text-muted, #94a3b8)",
                    textAlign: "center",
                    padding: "4px",
                  }}
                >
                  + Add Post
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default ContentCalendar;
