import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  History,
  Filter,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Film,
  Loader2,
} from "lucide-react";
import { Youtube } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

const STATUS_FILTERS = [
  "ALL",
  "PUBLISHED",
  "PROCESSING",
  "DRAFT",
  "FAILED",
];

export function PostHistory() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [pageBanner, setPageBanner] = useState(null);

  const pollTimeoutRef = useRef(null);
  const isMountedRef = useRef(true);
  const scheduleAutoRefreshRef = useRef(null);

  const scheduleAutoRefresh = useCallback(() => {
    if (!isMountedRef.current) return;
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);

    pollTimeoutRef.current = setTimeout(async () => {
      if (!isMountedRef.current) return;
      try {
        const res = await socialMediaService.getContentList({
          status: activeFilter === "ALL" ? undefined : activeFilter,
        });
        if (res.success && isMountedRef.current) {
          const fetchedPosts = res.content || [];
          setPosts(fetchedPosts);
          const stillProcessing = fetchedPosts.some(
            (p) => p.overall_status === "PROCESSING" || p.overall_status === "PENDING"
          );
          if (stillProcessing && scheduleAutoRefreshRef.current) {
            scheduleAutoRefreshRef.current();
          }
        }
      } catch {
        // Silently tolerate background poll error
      }
    }, 4000);
  }, [activeFilter]);

  useEffect(() => {
    scheduleAutoRefreshRef.current = scheduleAutoRefresh;
  }, [scheduleAutoRefresh]);

  const fetchPosts = useCallback(() => {
    setLoading(true);
    return socialMediaService
      .getContentList({
        status: activeFilter === "ALL" ? undefined : activeFilter,
      })
      .then((res) => {
        if (res.success && isMountedRef.current) {
          const fetchedPosts = res.content || [];
          setPosts(fetchedPosts);

          // Check if any post is currently processing; if so, schedule next poll
          const hasProcessing = fetchedPosts.some(
            (p) => p.overall_status === "PROCESSING" || p.overall_status === "PENDING"
          );
          if (hasProcessing && scheduleAutoRefreshRef.current) {
            scheduleAutoRefreshRef.current();
          }
        }
      })
      .catch(() => {
        if (isMountedRef.current) {
          setPageBanner({ type: "error", message: "Failed to load post history." });
        }
      })
      .finally(() => {
        if (isMountedRef.current) {
          setLoading(false);
        }
      });
  }, [activeFilter]);

  useEffect(() => {
    isMountedRef.current = true;
    let ignore = false;

    socialMediaService
      .getContentList({
        status: activeFilter === "ALL" ? undefined : activeFilter,
      })
      .then((res) => {
        if (!ignore) {
          if (res.success) {
            const fetchedPosts = res.content || [];
            setPosts(fetchedPosts);

            const hasProcessing = fetchedPosts.some(
              (p) => p.overall_status === "PROCESSING" || p.overall_status === "PENDING"
            );
            if (hasProcessing && scheduleAutoRefreshRef.current) {
              scheduleAutoRefreshRef.current();
            }
          }
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setPageBanner({ type: "error", message: "Failed to load post history." });
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
      isMountedRef.current = false;
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, [activeFilter]);

  const handleRetry = async (post) => {
    try {
      setActionLoadingId(post.id);
      setPageBanner(null);
      const res = await socialMediaService.retryYouTubePublish(post.id);
      if (res.success) {
        setPageBanner({
          type: "success",
          message: `Retry initiated for "${post.title}". Progress will update automatically.`,
        });
        await fetchPosts();
      } else {
        setPageBanner({
          type: "error",
          message: res.message || res.error || "Failed to retry publishing.",
        });
      }
    } catch (err) {
      const errMsg = err.response?.data?.message || err.response?.data?.error || "Error retrying post.";
      setPageBanner({ type: "error", message: errMsg });
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="history" onRefresh={fetchPosts} loading={loading} />

      {/* In-page Notification Banner */}
      {pageBanner && (
        <div className={`sm-alert ${pageBanner.type}`} style={{ marginBottom: "16px" }}>
          {pageBanner.type === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <div style={{ fontSize: "13px" }}>{pageBanner.message}</div>
          <button
            style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontSize: "14px", color: "inherit" }}
            onClick={() => setPageBanner(null)}
          >
            &times;
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          overflowX: "auto",
          paddingBottom: "4px",
          marginBottom: "16px",
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
      {posts.length === 0 && !loading ? (
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
                <th>Video / Title</th>
                <th>Description</th>
                <th>Platforms & Status</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {posts.map((post) => {
                const ytPlat = (post.platforms || []).find((p) => p.platform === "YOUTUBE");
                const hasPostUrl = ytPlat?.platform_post_url;
                const isProcessing = post.overall_status === "PROCESSING" || ytPlat?.processing_status === "PROCESSING" || ytPlat?.processing_status === "UPLOADING";

                return (
                  <tr key={post.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "rgba(37, 99, 235, 0.1)", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Film size={16} />
                        </div>
                        <div>
                          <div style={{ fontWeight: "700", color: "var(--text-primary, #0f172a)" }}>
                            {post.title || "Untitled Post"}
                          </div>
                          <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                            ID: #{post.id} • {post.media_type || "VIDEO"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={{ maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {post.common_caption || "—"}
                    </td>
                    <td>
                      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <Youtube size={16} />
                          <span className={`sm-badge ${post.overall_status}`}>
                            {post.overall_status}
                          </span>
                        </div>
                        {isProcessing && ytPlat?.progress_percent !== undefined && (
                          <div style={{ fontSize: "10.5px", color: "var(--text-muted, #64748b)", display: "flex", alignItems: "center", gap: "4px" }}>
                            <Loader2 size={10} className="sm-spin" /> Uploading: {ytPlat.progress_percent}%
                          </div>
                        )}
                        {ytPlat?.error_message && (
                          <div style={{ fontSize: "10.5px", color: "#dc2626", maxWidth: "200px" }}>
                            {ytPlat.error_message}
                          </div>
                        )}
                      </div>
                    </td>
                    <td style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
                      {post.created_at ? new Date(post.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {hasPostUrl && (
                          <a
                            href={ytPlat.platform_post_url}
                            target="_blank"
                            rel="noreferrer"
                            className="sm-btn-secondary"
                            style={{ padding: "4px 8px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", textDecoration: "none" }}
                          >
                            <ExternalLink size={12} /> Watch
                          </a>
                        )}
                        {post.retry_eligible && (
                          <button
                            className="sm-btn-secondary"
                            style={{ padding: "4px 8px", fontSize: "11px", color: "#dc2626", borderColor: "rgba(220, 38, 38, 0.3)" }}
                            onClick={() => handleRetry(post)}
                            disabled={actionLoadingId === post.id}
                          >
                            {actionLoadingId === post.id ? (
                              <Loader2 size={12} className="sm-spin" />
                            ) : (
                              <RefreshCw size={12} style={{ marginRight: "4px" }} />
                            )}
                            {post.retry_type === "THUMBNAIL_ONLY" ? "Retry Thumbnail" : "Retry"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default PostHistory;
