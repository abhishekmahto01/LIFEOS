import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  Film,
  Image as ImageIcon,
  CheckCircle2,
  Calendar,
  Clock,
  Sparkles,
  Save,
  Send,
  AlertCircle,
  Hash,
  Smartphone,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import "./SocialMedia.css";

export function CreatePost() {
  const navigate = useNavigate();

  const [selectedVideo, setSelectedVideo] = useState(null);
  const [selectedThumbnail, setSelectedThumbnail] = useState(null);
  const [commonCaption, setCommonCaption] = useState("");
  const [hashtags, setHashtags] = useState("#data #datascience #coding #analytics #lifeos");

  // Platform selections
  const [platforms, setPlatforms] = useState({
    youtube: true,
    instagram: true,
    facebook: false,
  });

  // Customization per platform
  const [activePlatformTab, setActivePlatformTab] = useState("youtube");
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeDesc, setYoutubeDesc] = useState("");
  const [instagramCaption, setInstagramCaption] = useState("");
  const [facebookCaption, setFacebookCaption] = useState("");

  // Publish mode: 'now', 'schedule', 'draft'
  const [publishMode, setPublishMode] = useState("now");
  const [scheduleDateTime, setScheduleDateTime] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  const handleVideoSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith("video/")) {
        setMessage({ type: "error", text: "Please select a valid video file (MP4, MOV, etc.)" });
        return;
      }
      setSelectedVideo(file);
      setMessage(null);
      if (!youtubeTitle) {
        setYoutubeTitle(file.name.replace(/\.[^/.]+$/, ""));
      }
    }
  };

  const handleThumbnailSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        setMessage({ type: "error", text: "Please select a valid image file (PNG, JPG, WebP)" });
        return;
      }
      setSelectedThumbnail(file);
    }
  };

  const togglePlatform = (plat) => {
    setPlatforms((prev) => ({ ...prev, [plat]: !prev[plat] }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedVideo && publishMode !== "draft") {
      setMessage({ type: "error", text: "Please select a video file before publishing." });
      return;
    }
    if (!platforms.youtube && !platforms.instagram && !platforms.facebook) {
      setMessage({ type: "error", text: "Please select at least one publishing platform." });
      return;
    }

    setIsSubmitting(true);
    // Phase 1 confirmation / UI validation feedback
    setTimeout(() => {
      setIsSubmitting(false);
      setMessage({
        type: "success",
        text: `Post successfully prepared in ${publishMode.toUpperCase()} mode! (Phase 1 UI validated; full backend pipeline active in Phase 2)`,
      });
    }, 600);
  };

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="create" />

      {message && (
        <div
          style={{
            padding: "12px 18px",
            borderRadius: "12px",
            fontSize: "13px",
            fontWeight: "600",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            background: message.type === "error" ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)",
            border: `1px solid ${message.type === "error" ? "rgba(239, 68, 68, 0.3)" : "rgba(16, 185, 129, 0.3)"}`,
            color: message.type === "error" ? "#ef4444" : "#10b981",
          }}
        >
          {message.type === "error" ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{message.text}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="sm-create-layout">
        {/* Left Column: Post Settings & Metadata */}
        <div className="sm-form-section">
          <div className="sm-form-group">
            <label className="sm-form-label">
              <span>01. Select Video Content (Short / Reel)</span>
              <span className="sm-form-hint">MP4, MOV up to 500MB</span>
            </label>
            <label className="sm-dropzone">
              <input
                type="file"
                accept="video/*"
                onChange={handleVideoSelect}
                style={{ display: "none" }}
              />
              <div className="sm-empty-icon-wrap">
                <UploadCloud size={24} />
              </div>
              {selectedVideo ? (
                <div>
                  <strong style={{ color: "var(--accent-blue, #2563eb)" }}>
                    {selectedVideo.name}
                  </strong>
                  <div style={{ fontSize: "11.5px", color: "var(--text-muted, #64748b)" }}>
                    {(selectedVideo.size / (1024 * 1024)).toFixed(2)} MB • Ready for Omnichannel Broadcast
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ fontWeight: "700", fontSize: "13.5px" }}>
                    Click or Drag & Drop Video here
                  </div>
                  <div style={{ fontSize: "11.5px", color: "var(--text-muted, #64748b)" }}>
                    Optimized for 9:16 Vertical Video (YouTube Shorts, IG Reels, FB Reels)
                  </div>
                </div>
              )}
            </label>
          </div>

          {/* Optional Custom Thumbnail */}
          <div className="sm-form-group">
            <label className="sm-form-label">
              <span>02. Custom Thumbnail (Optional)</span>
              <span className="sm-form-hint">JPG, PNG</span>
            </label>
            <input
              type="file"
              accept="image/*"
              onChange={handleThumbnailSelect}
              className="sm-input-text"
            />
            {selectedThumbnail && (
              <span style={{ fontSize: "12px", color: "#10b981", fontWeight: "600" }}>
                ✓ Selected: {selectedThumbnail.name}
              </span>
            )}
          </div>

          {/* Target Platforms */}
          <div className="sm-form-group">
            <label className="sm-form-label">
              <span>03. Target Publishing Platforms</span>
              <span className="sm-form-hint">Select all that apply</span>
            </label>
            <div className="sm-platforms-select-row">
              <button
                type="button"
                className={`sm-platform-checkbox-btn ${platforms.youtube ? "selected" : ""}`}
                onClick={() => togglePlatform("youtube")}
              >
                <Youtube size={17} color="#ff0000" />
                <span>YouTube</span>
              </button>

              <button
                type="button"
                className={`sm-platform-checkbox-btn ${platforms.instagram ? "selected" : ""}`}
                onClick={() => togglePlatform("instagram")}
              >
                <Instagram size={17} color="#e1306c" />
                <span>Instagram</span>
              </button>

              <button
                type="button"
                className={`sm-platform-checkbox-btn ${platforms.facebook ? "selected" : ""}`}
                onClick={() => togglePlatform("facebook")}
              >
                <Facebook size={17} color="#1877f2" />
                <span>Facebook</span>
              </button>
            </div>
          </div>

          {/* Common Caption & Hashtags */}
          <div className="sm-form-group">
            <label className="sm-form-label">
              <span>04. Master Caption</span>
              <span className="sm-form-hint">Auto-fills platform tabs</span>
            </label>
            <textarea
              className="sm-textarea"
              placeholder="Write your captivating video caption..."
              value={commonCaption}
              onChange={(e) => {
                setCommonCaption(e.target.value);
                if (!instagramCaption) setInstagramCaption(e.target.value);
                if (!facebookCaption) setFacebookCaption(e.target.value);
                if (!youtubeDesc) setYoutubeDesc(e.target.value);
              }}
            />
          </div>

          <div className="sm-form-group">
            <label className="sm-form-label">
              <span>05. Hashtags</span>
            </label>
            <input
              type="text"
              className="sm-input-text"
              value={hashtags}
              onChange={(e) => setHashtags(e.target.value)}
              placeholder="#shorts #reels #tech #ai"
            />
          </div>

          {/* Platform Specific Customization Tabs */}
          <div className="sm-form-group" style={{ marginTop: "6px" }}>
            <label className="sm-form-label">
              <span>06. Fine-Tune Platform Details</span>
            </label>
            <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
              {platforms.youtube && (
                <button
                  type="button"
                  className={`sm-tab-btn ${activePlatformTab === "youtube" ? "active" : ""}`}
                  onClick={() => setActivePlatformTab("youtube")}
                >
                  <Youtube size={15} /> YouTube Shorts
                </button>
              )}
              {platforms.instagram && (
                <button
                  type="button"
                  className={`sm-tab-btn ${activePlatformTab === "instagram" ? "active" : ""}`}
                  onClick={() => setActivePlatformTab("instagram")}
                >
                  <Instagram size={15} /> Instagram Reel
                </button>
              )}
              {platforms.facebook && (
                <button
                  type="button"
                  className={`sm-tab-btn ${activePlatformTab === "facebook" ? "active" : ""}`}
                  onClick={() => setActivePlatformTab("facebook")}
                >
                  <Facebook size={15} /> Facebook Reel
                </button>
              )}
            </div>

            {activePlatformTab === "youtube" && platforms.youtube && (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <input
                  type="text"
                  className="sm-input-text"
                  placeholder="YouTube Video Title (Max 100 chars)"
                  value={youtubeTitle}
                  onChange={(e) => setYoutubeTitle(e.target.value)}
                />
                <textarea
                  className="sm-textarea"
                  placeholder="YouTube Description & Links"
                  value={youtubeDesc || commonCaption}
                  onChange={(e) => setYoutubeDesc(e.target.value)}
                />
              </div>
            )}

            {activePlatformTab === "instagram" && platforms.instagram && (
              <textarea
                className="sm-textarea"
                placeholder="Instagram Reel Caption & Mentions"
                value={instagramCaption || commonCaption}
                onChange={(e) => setInstagramCaption(e.target.value)}
              />
            )}

            {activePlatformTab === "facebook" && platforms.facebook && (
              <textarea
                className="sm-textarea"
                placeholder="Facebook Page Reel Caption"
                value={facebookCaption || commonCaption}
                onChange={(e) => setFacebookCaption(e.target.value)}
              />
            )}
          </div>

          {/* Publishing Mode Selection */}
          <div className="sm-form-group" style={{ marginTop: "10px" }}>
            <label className="sm-form-label">
              <span>07. Publishing Timeline</span>
            </label>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <button
                type="button"
                className={`sm-platform-checkbox-btn ${publishMode === "now" ? "selected" : ""}`}
                onClick={() => setPublishMode("now")}
                style={{ flex: 1 }}
              >
                <Send size={15} />
                <span>Publish Now</span>
              </button>

              <button
                type="button"
                className={`sm-platform-checkbox-btn ${publishMode === "schedule" ? "selected" : ""}`}
                onClick={() => setPublishMode("schedule")}
                style={{ flex: 1 }}
              >
                <Clock size={15} />
                <span>Schedule Post</span>
              </button>

              <button
                type="button"
                className={`sm-platform-checkbox-btn ${publishMode === "draft" ? "selected" : ""}`}
                onClick={() => setPublishMode("draft")}
                style={{ flex: 1 }}
              >
                <Save size={15} />
                <span>Save Draft</span>
              </button>
            </div>

            {publishMode === "schedule" && (
              <div style={{ marginTop: "12px" }}>
                <label className="sm-form-label" style={{ fontSize: "12px", marginBottom: "4px" }}>
                  Select Target Date & Time
                </label>
                <input
                  type="datetime-local"
                  className="sm-input-text"
                  value={scheduleDateTime}
                  onChange={(e) => setScheduleDateTime(e.target.value)}
                  required
                />
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="sm-form-actions-row">
            <button
              type="button"
              className="sm-btn-secondary"
              onClick={() => navigate("/social-media")}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="sm-btn-primary"
              disabled={isSubmitting}
            >
              {publishMode === "now" && "🚀 Launch Omnichannel Broadcast"}
              {publishMode === "schedule" && "⏰ Schedule Omnichannel Post"}
              {publishMode === "draft" && "💾 Save as Draft"}
            </button>
          </div>
        </div>

        {/* Right Column: Live Mobile Reel/Short Preview */}
        <div className="sm-preview-sticky">
          <div className="sm-phone-mockup">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-muted, #64748b)" }}>
                <Smartphone size={14} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />
                Live Preview
              </span>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "#ec4899" }}>
                9:16 Vertical
              </span>
            </div>

            <div className="sm-phone-screen">
              <div className="sm-phone-overlay">
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "2px" }}>
                  <div
                    style={{
                      width: "24px",
                      height: "24px",
                      borderRadius: "50%",
                      background: "#ec4899",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "10px",
                      fontWeight: "bold",
                    }}
                  >
                    OS
                  </div>
                  <span style={{ fontSize: "12px", fontWeight: "700" }}>@abhishek.lifeos</span>
                </div>
                <div className="sm-phone-caption">
                  {commonCaption || "Your engaging caption and story will appear right here..."}
                </div>
                <div style={{ fontSize: "11px", color: "#38bdf8", fontWeight: "600" }}>
                  {hashtags}
                </div>
              </div>
            </div>

            <div style={{ fontSize: "11.5px", color: "var(--text-muted, #64748b)", textAlign: "center" }}>
              Selected: {Object.keys(platforms).filter((k) => platforms[k]).join(", ") || "None"}
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}

export default CreatePost;
