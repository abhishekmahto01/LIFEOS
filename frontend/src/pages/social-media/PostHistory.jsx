import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  History,
  Filter,
  PlusCircle,
  RotateCw,
  Eye,
  Trash2,
  Edit,
  Sparkles,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

const STATUS_FILTERS = [
  "ALL",
  "DRAFT",
  "SCHEDULED",
  "PUBLISHING",
  "PUBLISHED",
  "PARTIALLY_PUBLISHED",
  "FAILED",
];

export function PostHistory() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPosts();
  }, [activeFilter]);

  const fetchPosts = async () => {
    try {
      setLoading(true);
      const res = await socialMediaService.getContentList({
        status: activeFilter === "ALL" ? undefined : activeFilter,
      });
      if (res.success) {
        setPosts(res.content || []);
      }
    } catch (e) {
      console.error("Error fetching post history:", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="history" onRefresh={fetchPosts} loading={loading} />

      {/* Filter Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          overflowX: "auto",
          paddingBottom: "4px",
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-muted, #64748b)", display: "flex", alignItems: "center", gap: "4px" }}>
          <Filter size={14} /> FILTER:
        </span>
        {STATUS_FILTERS.map((st) => (
          <button
            key={st}
            className={`sm-tab-btn ${activeFilter === st ? "active" : ""}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
            onClick={() => setActiveFilter(st)}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Posts Table or Empty State */}
      {posts.length === 0 ? (
        <div className="sm-panel-card">
          <div className="sm-empty-state">
            <div className="sm-empty-icon-wrap">
              <History size={24} />
            </div>
            <h3 className="sm-empty-title">No post history found</h3>
            <p className="sm-empty-desc">
              {activeFilter === "ALL"
                ? "You have not created any social media posts yet."
                : `No posts with status '${activeFilter}' found.`}
            </p>
            <button
              className="sm-empty-btn"
              onClick={() => navigate("/social-media/create")}
            >
              + Create New Post
            </button>
          </div>
        </div>
      ) : (
        <div className="sm-table-container">
          <table className="sm-table">
            <thead>
              <tr>
                <th>Video / Content</th>
                <th>Master Caption</th>
                <th>Platforms & Status</th>
                <th>Date / Schedule</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {posts.map((post) => (
                <tr key={post.id}>
                  <td>
                    <div style={{ fontWeight: "700" }}>{post.title || "Omnichannel Reel"}</div>
                  </td>
                  <td>{post.common_caption || "—"}</td>
                  <td>
                    <span className={`sm-badge ${post.content_status}`}>
                      {post.content_status}
                    </span>
                  </td>
                  <td>{post.created_at || "—"}</td>
                  <td>
                    <button
                      className="sm-btn-secondary"
                      style={{ padding: "4px 8px", fontSize: "11px" }}
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default PostHistory;
