import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  Film,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { Youtube, Instagram, Facebook } from "../../components/social-media/PlatformIcons";
import SocialMediaNav from "../../components/social-media/SocialMediaNav";
import { socialMediaService } from "../../services/socialMediaService";
import "./SocialMedia.css";

export function CreatePost() {
  const navigate = useNavigate();

  const [accounts, setAccounts] = useState([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [accountsError, setAccountsError] = useState(null);

  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [selectedThumbnail, setSelectedThumbnail] = useState(null);
  const [postTitle, setPostTitle] = useState("");
  const [commonCaption, setCommonCaption] = useState("");
  const [hashtags, setHashtags] = useState("#data #coding #analytics #lifeos");
  const [privacyStatus, setPrivacyStatus] = useState("PRIVATE");
  const [madeForKids, setMadeForKids] = useState(false);
  const [categoryId, setCategoryId] = useState("22");

  // Platform selection (Phase 6: YouTube enabled)
  const [platforms, setPlatforms] = useState({
    youtube: true,
    instagram: false,
    facebook: false,
  });

  // Upload & Pipeline State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0); // 0-100% (Browser -> LifeOS)
  const [pipelineState, setPipelineState] = useState(null); // 'UPLOADING_LOCAL' | 'QUEUED' | 'UPLOADING_YOUTUBE' | 'PROCESSING_YOUTUBE' | 'PUBLISHED' | 'FAILED'
  const [activeContentId, setActiveContentId] = useState(null);
  const [publishedUrl, setPublishedUrl] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [youtubeChunkProgress, setYoutubeChunkProgress] = useState(0);

  const pollTimeoutRef = useRef(null);
  const pollAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);

  const fetchConnectedAccounts = useCallback(() => {
    setAccountsLoading(true);
    setAccountsError(null);
    socialMediaService
      .getAccounts()
      .then((res) => {
        if (res.success) {
          const accs = res.accounts || [];
          setAccounts(accs);
          const ytActive = accs.find(
            (a) => a.platform?.toUpperCase() === "YOUTUBE" && a.connection_status === "ACTIVE"
          );
          if (ytActive) {
            setSelectedAccountId(ytActive.id);
          }
        } else {
          setAccountsError(res.error || "Failed to load connected accounts.");
        }
      })
      .catch(() => {
        setAccountsError("Network error while loading connected accounts.");
      })
      .finally(() => {
        setAccountsLoading(false);
      });
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    let ignore = false;

    socialMediaService
      .getAccounts()
      .then((res) => {
        if (!ignore) {
          if (res.success) {
            const accs = res.accounts || [];
            setAccounts(accs);
            const ytActive = accs.find(
              (a) => a.platform?.toUpperCase() === "YOUTUBE" && a.connection_status === "ACTIVE"
            );
            if (ytActive) {
              setSelectedAccountId(ytActive.id);
            }
          } else {
            setAccountsError(res.error || "Failed to load connected accounts.");
          }
          setAccountsLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setAccountsError("Network error while loading connected accounts.");
          setAccountsLoading(false);
        }
      });

    return () => {
      ignore = true;
      isMountedRef.current = false;
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, []);

  const youtubeAccounts = accounts.filter((a) => a.platform?.toUpperCase() === "YOUTUBE" && a.connection_status === "ACTIVE");
  const selectedAccount = youtubeAccounts.find((a) => String(a.id) === String(selectedAccountId)) || youtubeAccounts[0];

  const handleVideoSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith("video/")) {
      setSelectedVideo(null);
      setErrorMessage("Please select a valid video file (MP4, MOV, WebM).");
      return;
    }
    setSelectedVideo(file);
    setErrorMessage(null);
    if (!postTitle) {
      const cleanName = file.name.replace(/\.[^/.]+$/, "").substring(0, 100);
      setPostTitle(cleanName);
    }
  };

  const handleThumbnailSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setSelectedThumbnail(null);
      setErrorMessage("Please select a valid image file (PNG, JPG).");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setSelectedThumbnail(null);
      setErrorMessage("Thumbnail must be smaller than 2 MB.");
      return;
    }
    setSelectedThumbnail(file);
    setErrorMessage(null);
  };

  const scheduleNextPoll = (contentId, delayMs = 2000) => {
    if (!isMountedRef.current) return;
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);

    pollTimeoutRef.current = setTimeout(async () => {
      if (!isMountedRef.current) return;
      pollAttemptsRef.current += 1;

      try {
        const res = await socialMediaService.getContentStatus(contentId);
        if (!isMountedRef.current) return;

        if (res.success) {
          const ytPlat = (res.platforms || []).find((p) => p.platform === "YOUTUBE");
          if (ytPlat) {
            setYoutubeChunkProgress(ytPlat.upload_progress_percent || 0);

            if (ytPlat.platform_status === "PUBLISHED") {
              setPipelineState("PUBLISHED");
              setPublishedUrl(ytPlat.platform_post_url);
              setIsSubmitting(false);
              return;
            } else if (ytPlat.platform_status === "FAILED") {
              setPipelineState("FAILED");
              setErrorMessage(ytPlat.error_message || "YouTube publishing encountered an error.");
              setIsSubmitting(false);
              return;
            } else if (ytPlat.processing_status === "PROCESSING") {
              setPipelineState("PROCESSING_YOUTUBE");
            } else if (ytPlat.processing_status === "UPLOADING") {
              setPipelineState("UPLOADING_YOUTUBE");
            } else {
              setPipelineState("QUEUED");
            }
          }
        }
      } catch {
        // Silently tolerate transient polling error
      }

      // Max 60 poll iterations (2 minutes)
      if (pollAttemptsRef.current < 60) {
        scheduleNextPoll(contentId, 2000);
      } else {
        setIsSubmitting(false);
      }
    }, delayMs);
  };

  const startStatusPolling = (contentId) => {
    setActiveContentId(contentId);
    pollAttemptsRef.current = 0;
    scheduleNextPoll(contentId, 1000);
  };

  const handleRetry = async () => {
    if (!activeContentId) return;

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      setPipelineState("QUEUED");

      const res = await socialMediaService.retryYouTubePublish(activeContentId);
      if (res.success) {
        startStatusPolling(activeContentId);
      } else {
        setErrorMessage(res.error || "Retry failed.");
        setPipelineState("FAILED");
        setIsSubmitting(false);
      }
    } catch (err) {
      setErrorMessage(err.response?.data?.error || "Failed to retry publishing.");
      setPipelineState("FAILED");
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedVideo) {
      setErrorMessage("Please select a video to upload.");
      return;
    }

    if (!selectedAccount) {
      setErrorMessage("Please select a connected YouTube account.");
      return;
    }

    if (!selectedAccount.can_upload) {
      setErrorMessage("Your YouTube account requires reconnection to grant upload permissions.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setUploadProgress(0);
    setYoutubeChunkProgress(0);
    setPipelineState("UPLOADING_LOCAL");
    setPublishedUrl(null);

    try {
      const formData = new FormData();
      formData.append("video", selectedVideo);
      if (selectedThumbnail) {
        formData.append("thumbnail", selectedThumbnail);
      }
      formData.append("title", postTitle);
      formData.append("common_caption", commonCaption);
      formData.append("hashtags", hashtags);
      formData.append("privacy_status", privacyStatus);
      formData.append("made_for_kids", madeForKids ? "true" : "false");
      formData.append("category_id", categoryId);
      formData.append("publish_now", "true");

      const platformTargets = [
        {
          platform: "YOUTUBE",
          account_id: selectedAccount.id,
          privacy_status: privacyStatus,
        },
      ];
      formData.append("platforms", JSON.stringify(platformTargets));

      const res = await socialMediaService.uploadAndCreatePost(formData, (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        }
      });

      if (res.success && res.data) {
        setPipelineState("QUEUED");
        startStatusPolling(res.data.content_id);
      } else {
        setErrorMessage(res.error || "Upload failed.");
        setPipelineState("FAILED");
        setIsSubmitting(false);
      }
    } catch (err) {
      setErrorMessage(err.response?.data?.error || "Failed to create post. Please try again.");
      setPipelineState("FAILED");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="sm-module-container">
      <SocialMediaNav activeTab="create" onRefresh={fetchConnectedAccounts} loading={accountsLoading} />

      {/* Error loading accounts */}
      {accountsError && (
        <div className="sm-alert error" style={{ marginBottom: "20px" }}>
          <AlertCircle size={18} />
          <div>
            <strong>Error Loading Accounts</strong>
            <p style={{ margin: "4px 0 0 0", fontSize: "13px" }}>{accountsError}</p>
          </div>
        </div>
      )}

      {/* Warning if YouTube account needs reconnecting */}
      {selectedAccount && !selectedAccount.can_upload && (
        <div className="sm-alert warning" style={{ marginBottom: "20px" }}>
          <AlertCircle size={18} />
          <div>
            <strong>Action Required: Permission Upgrade</strong>
            <p style={{ margin: "4px 0 0 0", fontSize: "13px" }}>
              Your YouTube account ({selectedAccount.account_name}) is connected with read-only permissions from Phase 5.
              Reconnect to grant upload permissions before publishing.
            </p>
          </div>
          <button
            className="sm-btn-primary"
            style={{ marginLeft: "auto", padding: "6px 12px", fontSize: "12px" }}
            onClick={() => navigate("/social-media/accounts")}
          >
            Reconnect Account
          </button>
        </div>
      )}

      {/* Warning if no accounts connected */}
      {!accountsLoading && youtubeAccounts.length === 0 && (
        <div className="sm-alert info" style={{ marginBottom: "20px" }}>
          <AlertCircle size={18} />
          <div>
            <strong>No Connected YouTube Accounts</strong>
            <p style={{ margin: "4px 0 0 0", fontSize: "13px" }}>
              Connect your YouTube channel in Connected Accounts to start publishing Shorts and Videos.
            </p>
          </div>
          <button
            className="sm-btn-primary"
            style={{ marginLeft: "auto", padding: "6px 12px", fontSize: "12px" }}
            onClick={() => navigate("/social-media/accounts")}
          >
            Connect YouTube
          </button>
        </div>
      )}

      {/* Pipeline Status Banner */}
      {pipelineState && (
        <div className={`sm-pipeline-banner ${pipelineState.toLowerCase()}`} style={{ marginBottom: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {pipelineState === "PUBLISHED" ? (
              <CheckCircle2 size={24} color="#16a34a" />
            ) : pipelineState === "FAILED" ? (
              <AlertCircle size={24} color="#dc2626" />
            ) : (
              <Loader2 size={24} className="sm-spin" color="#2563eb" />
            )}
            <div>
              <div style={{ fontWeight: "700", fontSize: "14px" }}>
                {pipelineState === "UPLOADING_LOCAL" && "Uploading to LifeOS Secure Storage..."}
                {pipelineState === "QUEUED" && "Queued for YouTube Publishing..."}
                {pipelineState === "UPLOADING_YOUTUBE" && `Streaming Chunks to YouTube (${youtubeChunkProgress}%)...`}
                {pipelineState === "PROCESSING_YOUTUBE" && "YouTube Processing & Finalizing..."}
                {pipelineState === "PUBLISHED" && "Successfully Published to YouTube!"}
                {pipelineState === "FAILED" && "Publishing Encountered an Error"}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginTop: "2px" }}>
                {pipelineState === "UPLOADING_LOCAL" && `Local progress: ${uploadProgress}%`}
                {pipelineState === "UPLOADING_YOUTUBE" && `Resumable chunked upload: ${youtubeChunkProgress}% server-confirmed`}
                {pipelineState === "PROCESSING_YOUTUBE" && "Awaiting YouTube processingDetails confirmation"}
                {pipelineState === "PUBLISHED" && "Temporary video files have been safely deleted from server storage."}
                {pipelineState === "FAILED" && (errorMessage || "Retry to resume from the last server-confirmed byte.")}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginLeft: "auto" }}>
            {pipelineState === "PUBLISHED" && publishedUrl && (
              <a
                href={publishedUrl}
                target="_blank"
                rel="noreferrer"
                className="sm-btn-primary"
                style={{ padding: "8px 14px", fontSize: "13px", display: "inline-flex", alignItems: "center", gap: "6px", textDecoration: "none" }}
              >
                <ExternalLink size={14} /> Watch on YouTube
              </a>
            )}
            {pipelineState === "FAILED" && (
              <button
                type="button"
                className="sm-btn-secondary"
                onClick={handleRetry}
                disabled={isSubmitting}
                style={{ padding: "8px 14px", fontSize: "13px" }}
              >
                <RefreshCw size={14} style={{ marginRight: "6px" }} /> Retry
              </button>
            )}
          </div>
        </div>
      )}

      {errorMessage && !pipelineState && (
        <div className="sm-alert error" style={{ marginBottom: "20px" }}>
          <AlertCircle size={18} />
          <div>{errorMessage}</div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="sm-create-split-grid">
          {/* Left Column: Media Upload */}
          <div className="sm-panel-card">
            <h3 className="sm-panel-title">
              <Film size={18} />
              <span>01. Media Asset</span>
            </h3>

            {/* Video File Picker */}
            <div
              className={`sm-dropzone ${selectedVideo ? "has-file" : ""}`}
              onClick={() => document.getElementById("video-file-input").click()}
            >
              <input
                id="video-file-input"
                type="file"
                accept="video/mp4,video/quicktime,video/webm"
                style={{ display: "none" }}
                onChange={handleVideoSelect}
              />
              <UploadCloud size={36} color={selectedVideo ? "#2563eb" : "#94a3b8"} />
              <div style={{ marginTop: "8px", fontWeight: "600", fontSize: "14px" }}>
                {selectedVideo ? selectedVideo.name : "Select or Drop Video (MP4, MOV, WebM)"}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", marginTop: "4px" }}>
                {selectedVideo ? `${(selectedVideo.size / (1024 * 1024)).toFixed(1)} MB` : "Max 500 MB"}
              </div>
            </div>

            {/* Optional Thumbnail Picker */}
            <div style={{ marginTop: "16px" }}>
              <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "6px" }}>
                Custom Thumbnail (Optional, Max 2 MB)
              </label>
              <div
                className={`sm-dropzone-thumb ${selectedThumbnail ? "has-file" : ""}`}
                onClick={() => document.getElementById("thumb-file-input").click()}
              >
                <input
                  id="thumb-file-input"
                  type="file"
                  accept="image/jpeg,image/png"
                  style={{ display: "none" }}
                  onChange={handleThumbnailSelect}
                />
                <ImageIcon size={20} color={selectedThumbnail ? "#2563eb" : "#94a3b8"} />
                <span style={{ fontSize: "12px", fontWeight: "500" }}>
                  {selectedThumbnail ? selectedThumbnail.name : "Upload JPEG / PNG Thumbnail"}
                </span>
              </div>
            </div>

            {/* Target Platform & Account Picker */}
            <div style={{ marginTop: "20px" }}>
              <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "8px" }}>
                Target Platforms
              </label>
              <div className="sm-platforms-select-row">
                <button
                  type="button"
                  className={`sm-platform-select-btn ${platforms.youtube ? "active" : ""}`}
                  onClick={() => setPlatforms({ ...platforms, youtube: !platforms.youtube })}
                >
                  <Youtube size={16} /> YouTube
                </button>
                <button
                  type="button"
                  className="sm-platform-select-btn disabled"
                  title="Phase 7 (Meta Integration)"
                  disabled
                >
                  <Instagram size={16} /> Instagram (Phase 7)
                </button>
                <button
                  type="button"
                  className="sm-platform-select-btn disabled"
                  title="Phase 7 (Meta Integration)"
                  disabled
                >
                  <Facebook size={16} /> Facebook (Phase 7)
                </button>
              </div>

              {/* YouTube Account Selection if multiple exist */}
              {youtubeAccounts.length > 1 && (
                <div style={{ marginTop: "12px" }}>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                    Select YouTube Account
                  </label>
                  <select
                    className="sm-form-input"
                    value={selectedAccountId || ""}
                    onChange={(e) => setSelectedAccountId(Number(e.target.value))}
                  >
                    {youtubeAccounts.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {acc.account_name} ({acc.can_upload ? "Upload Ready" : "Reconnect Required"})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Metadata & Settings */}
          <div className="sm-panel-card">
            <h3 className="sm-panel-title">
              <span>02. Video Details & Privacy</span>
            </h3>

            {/* Title */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Video Title <span style={{ color: "#dc2626" }}>*</span>
              </label>
              <input
                type="text"
                className="sm-form-input"
                placeholder="e.g. LifeOS Omnichannel Publishing Demo"
                value={postTitle}
                onChange={(e) => setPostTitle(e.target.value)}
                maxLength={100}
                required
              />
              <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)", textAlign: "right", marginTop: "2px" }}>
                {postTitle.length} / 100 characters
              </div>
            </div>

            {/* Description */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Description
              </label>
              <textarea
                className="sm-form-textarea"
                rows={4}
                placeholder="Write a description for your video..."
                value={commonCaption}
                onChange={(e) => setCommonCaption(e.target.value)}
                maxLength={5000}
              />
              <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)", textAlign: "right", marginTop: "2px" }}>
                {commonCaption.length} / 5000 characters
              </div>
            </div>

            {/* Tags */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                Tags / Hashtags
              </label>
              <input
                type="text"
                className="sm-form-input"
                placeholder="#coding #ai #productivity"
                value={hashtags}
                onChange={(e) => setHashtags(e.target.value)}
              />
            </div>

            {/* Privacy & Audience */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "14px" }}>
              <div>
                <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                  Privacy Status
                </label>
                <select
                  className="sm-form-input"
                  value={privacyStatus}
                  onChange={(e) => setPrivacyStatus(e.target.value)}
                >
                  <option value="PRIVATE">Private (Recommended for unverified APIs)</option>
                  <option value="UNLISTED">Unlisted</option>
                  <option value="PUBLIC">Public</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: "13px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                  Category ID
                </label>
                <select
                  className="sm-form-input"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                >
                  <option value="22">People & Blogs (22)</option>
                  <option value="28">Science & Technology (28)</option>
                  <option value="27">Education (27)</option>
                  <option value="24">Entertainment (24)</option>
                </select>
              </div>
            </div>

            {/* Made for Kids Checkbox */}
            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={madeForKids}
                  onChange={(e) => setMadeForKids(e.target.checked)}
                />
                <span>This content is made for kids (COPPA compliance)</span>
              </label>
            </div>

            {/* Submit Action */}
            <button
              type="submit"
              className="sm-btn-primary"
              disabled={isSubmitting || !selectedVideo || !selectedAccount || !selectedAccount.can_upload}
              style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: "700" }}
            >
              {isSubmitting ? (
                <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
                  <Loader2 size={16} className="sm-spin" /> Publishing to YouTube...
                </span>
              ) : (
                "🚀 Publish Video to YouTube"
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default CreatePost;
