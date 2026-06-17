import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, ChevronDown, FilePlus, History } from "lucide-react";
import "./CareerModule.css";

function CareerModule() {
  const navigate = useNavigate();
  const [jobOpen, setJobOpen] = useState(true);

  return (
    <div className="career-page">
      <h2 className="career-title">Career Module</h2>

      <div className="career-card">
        <div
          className="career-card-header"
          onClick={() => setJobOpen(!jobOpen)}
        >
          <span className="career-card-label">
            <Briefcase size={18} />
            Job
          </span>
          <ChevronDown
            size={18}
            className={`career-chevron ${jobOpen ? "open" : ""}`}
          />
        </div>

        {jobOpen && (
          <div className="career-card-body">
            <div
              className="career-card-item"
              onClick={() => navigate("/career/job-entry")}
            >
              <FilePlus size={16} />
              <span>Job Entry Form</span>
            </div>
            <div
              className="career-card-item"
              onClick={() => navigate("/career/job-history")}
            >
              <History size={16} />
              <span>Job Apply History</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CareerModule;