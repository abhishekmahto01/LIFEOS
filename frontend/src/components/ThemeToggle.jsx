import { Moon, Sun } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import "./ThemeToggle.css";

export function ThemeToggle({ showLabel = true, className = "" }) {
  const { theme, toggleTheme, isDark } = useTheme();

  return (
    <button
      className={`theme-toggle-btn ${isDark ? "is-dark" : "is-light"} ${className}`}
      onClick={toggleTheme}
      type="button"
      title={`Switch to ${isDark ? "Light Mode (White)" : "Dark Mode (Black)"}`}
      aria-label="Toggle theme"
    >
      <div className="theme-toggle-thumb">
        {isDark ? (
          <Sun size={15} className="theme-icon sun" />
        ) : (
          <Moon size={15} className="theme-icon moon" />
        )}
      </div>
      {showLabel && (
        <span className="theme-toggle-label">
          {isDark ? "Light" : "Dark"}
        </span>
      )}
    </button>
  );
}

export default ThemeToggle;
