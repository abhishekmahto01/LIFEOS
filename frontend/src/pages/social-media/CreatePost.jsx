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
  X,
  History,
  PlusCircle,
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
  const [showSuccessModal, setShowSuccessModal] = useState(false);

  // Meta publishing (Instagram Reels + Facebook Page videos) runs independently of
  // the YouTube polling pipeline. metaResults: { INSTAGRAM|FACEBOOK: {status, url, error} }
  // where status is 'PUBLISHING' | 'PUBLISHED' | 'FAILED'.
  const [selectedIgAccountId, setSelectedIgAccountId] = useState(null);
  const [selectedFbAccountId, setSelectedFbAccountId] = useState(null);
  const [metaResults, setMetaResults] = useState({});

  const videoInputRef = useRef(null);
  const thumbInputRef = useRef(null);
  const pollTimeoutRef = useRef(null);
  const pollAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);
  // What the last submit targeted, so Retry re-runs only the platforms that failed.
  const lastSubmitRef = useRef({ youtube: false, metaTargets: [] });

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

  // Handle modal keyboard navigation & body overflow lock
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && showSuccessModal) {
        setShowSuccessModal(false);
      }
    };
    if (showSuccessModal) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [showSuccessModal]);

  const handleResetForm = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
    }
    setSelectedVideo(null);
    setSelectedThumbnail(null);
    setPostTitle("");
    setCommonCaption("");
    setHashtags("#data #coding #analytics #lifeos");
    setPrivacyStatus("PRIVATE");
    setMadeForKids(false);
    setCategoryId("22");
    setUploadProgress(0);
    setYoutubeChunkProgress(0);
    setActiveContentId(null);
    setPublishedUrl(null);
    setErrorMessage(null);
    setPipelineState(null);
    setIsSubmitting(false);
    setShowSuccessModal(false);
    setMetaResults({});

    if (videoInputRef.current) {
      videoInputRef.current.value = "";
    }
    if (thumbInputRef.current) {
      thumbInputRef.current.value = "";
    }
  }, []);

  const youtubeAccounts = accounts.filter((a) => a.platform?.toUpperCase() === "YOUTUBE" && a.connection_status === "ACTIVE");
  const selectedAccount = youtubeAccounts.find((a) => String(a.id) === String(selectedAccountId)) || youtubeAccounts[0];
  const instagramAccounts = accounts.filter((a) => a.platform?.toUpperCase() === "INSTAGRAM" && a.connection_status === "ACTIVE");
  const selectedIgAccount =
    instagramAccounts.find((a) => String(a.id) === String(selectedIgAccountId)) || instagramAccounts[0];

  const facebookPages = accounts.filter((a) => a.platform?.toUpperCase() === "FACEBOOK" && a.connection_status === "ACTIVE");
  const selectedFbAccount =
    facebookPages.find((a) => String(a.id) === String(selectedFbAccountId)) || facebookPages[0];

  const META_PUBLISHERS = {
    INSTAGRAM: socialMediaService.publishInstagram,
    FACEBOOK: socialMediaService.publishFacebook,
  };
  const META_LABELS = { INSTAGRAM: "Instagram", FACEBOOK: "Facebook" };

  const selectedPlatformNames = [
    platforms.youtube && "YouTube",
    platforms.instagram && "Instagram",
    platforms.facebook && "Facebook",
  ].filter(Boolean);
  const targetLabel = selectedPlatformNames.join(" + ") || "Social Media";
  const youtubeBlocksSubmit = platforms.youtube && (!selectedAccount || !selectedAccount.can_upload);

  const setMetaResult = (platform, result) =>
    setMetaResults((prev) => ({ ...prev, [platform]: result }));

  // Publishes to each selected Meta target in parallel. When YouTube is not part of
  // the post, these results also drive the main pipeline state and success modal.
  const publishToMeta = async (contentId, targets, drivesPipeline) => {
    const outcomes = await Promise.all(
      targets.map(async ({ platform, accountId }) => {
        setMetaResult(platform, { status: "PUBLISHING" });
        try {
          const res = await META_PUBLISHERS[platform](contentId, accountId);
          if (!res.success) throw new Error(res.error || res.message || `${META_LABELS[platform]} publishing failed.`);
          const result = { status: "PUBLISHED", url: res.publish_url || null };
          if (isMountedRef.current) setMetaResult(platform, result);
          return { platform, ...result };
        } catch (err) {
          const error =
            err.response?.data?.error || err.response?.data?.message || err.message || `${META_LABELS[platform]} publishing failed.`;
          if (isMountedRef.current) setMetaResult(platform, { status: "FAILED", error });
          return { platform, status: "FAILED", error };
        }
      })
    );

    if (!drivesPipeline || !isMountedRef.current) return;
    const firstSuccess = outcomes.find((o) => o.status === "PUBLISHED");
    setIsSubmitting(false);
    if (firstSuccess) {
      setPipelineState("PUBLISHED");
      setPublishedUrl(firstSuccess.url);
      setShowSuccessModal(true);
    } else {
      setPipelineState("FAILED");
      setErrorMessage(outcomes.map((o) => `${META_LABELS[o.platform]}: ${o.error}`).join(" | "));
    }
  };

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
              setShowSuccessModal(true);
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

    const { youtube: hadYouTube, metaTargets } = lastSubmitRef.current;
    const failedMeta = metaTargets.filter((t) => metaResults[t.platform]?.status === "FAILED");

    if (!hadYouTube) {
      if (failedMeta.length === 0) return;
      setIsSubmitting(true);
      setShowSuccessModal(false);
      setErrorMessage(null);
      setPipelineState("QUEUED");
      publishToMeta(activeContentId, failedMeta, true);
      return;
    }

    if (failedMeta.length > 0) {
      publishToMeta(activeContentId, failedMeta, false);
    }

    try {
      setIsSubmitting(true);
      setShowSuccessModal(false);
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

    const toYouTube = platforms.youtube;
    const toInstagram = platforms.instagram;
    const toFacebook = platforms.facebook;

    if (!toYouTube && !toInstagram && !toFacebook) {
      setErrorMessage("Select at least one platform to publish to.");
      return;
    }

    if (toYouTube && !selectedAccount) {
      setErrorMessage("Please select a connected YouTube account.");
      return;
    }

    if (toYouTube && !selectedAccount.can_upload) {
      setErrorMessage("Your YouTube account requires reconnection to grant upload permissions.");
      return;
    }

    if (toInstagram && !selectedIgAccount) {
      setErrorMessage("Please connect an Instagram Professional account first.");
      return;
    }

    if (toFacebook && !selectedFbAccount) {
      setErrorMessage("Please connect a Facebook Page first.");
      return;
    }

    setIsSubmitting(true);
    setShowSuccessModal(false);
    setErrorMessage(null);
    setUploadProgress(0);
    setYoutubeChunkProgress(0);
    setPipelineState("UPLOADING_LOCAL");
    setPublishedUrl(null);
    setMetaResults({});

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

      const platformTargets = [];
      if (toYouTube) {
        platformTargets.push({
          platform: "YOUTUBE",
          account_id: selectedAccount.id,
          privacy_status: privacyStatus,
        });
      }
      if (toInstagram) {
        platformTargets.push({ platform: "INSTAGRAM", account_id: selectedIgAccount.id });
      }
      if (toFacebook) {
        platformTargets.push({ platform: "FACEBOOK", account_id: selectedFbAccount.id });
      }
      formData.append("platforms", JSON.stringify(platformTargets));

      const res = await socialMediaService.uploadAndCreatePost(formData, (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percent);
        }
      });

      if (res.success && res.data) {
        const contentId = res.data.content_id;
        setActiveContentId(contentId);
        setPipelineState("QUEUED");
        if (toYouTube) {
          startStatusPolling(contentId);
        }
        const metaTargets = [];
        if (toInstagram) metaTargets.push({ platform: "INSTAGRAM", accountId: selectedIgAccount.id });
        if (toFacebook) metaTargets.push({ platform: "FACEBOOK", accountId: selectedFbAccount.id });
        lastSubmitRef.current = { youtube: toYouTube, metaTargets };
        if (metaTargets.length > 0) {
          publishToMeta(contentId, metaTargets, !toYouTube);
        }
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
      {platforms.youtube && selectedAccount && !selectedAccount.can_upload && (
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
      {!accountsLoading && platforms.youtube && youtubeAccounts.length === 0 && (
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
                {pipelineState === "QUEUED" && `Queued for ${targetLabel} Publishing...`}
                {pipelineState === "UPLOADING_YOUTUBE" && `Streaming Chunks to YouTube (${youtubeChunkProgress}%)...`}
                {pipelineState === "PROCESSING_YOUTUBE" && "YouTube Processing & Finalizing..."}
                {pipelineState === "PUBLISHED" && `Successfully Published to ${targetLabel}!`}
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
                <ExternalLink size={14} /> View Published Post
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
              onClick={() => videoInputRef.current?.click()}
            >
              <input
                ref={videoInputRef}
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
                onClick={() => thumbInputRef.current?.click()}
              >
                <input
                  ref={thumbInputRef}
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
                  className={`sm-platform-select-btn ${platforms.instagram ? "active" : ""} ${instagramAccounts.length === 0 ? "disabled" : ""}`}
                  title={instagramAccounts.length === 0 ? "Connect an Instagram Professional account first" : "Publish as an Instagram Reel"}
                  disabled={instagramAccounts.length === 0}
                  onClick={() => setPlatforms({ ...platforms, instagram: !platforms.instagram })}
                >
                  <Instagram size={16} /> Instagram Reel
                </button>
                <button
                  type="button"
                  className={`sm-platform-select-btn ${platforms.facebook ? "active" : ""} ${facebookPages.length === 0 ? "disabled" : ""}`}
                  title={facebookPages.length === 0 ? "Connect a Facebook Page first" : "Post the video to your Facebook Page"}
                  disabled={facebookPages.length === 0}
                  onClick={() => setPlatforms({ ...platforms, facebook: !platforms.facebook })}
                >
                  <Facebook size={16} /> Facebook Page
                </button>
              </div>

              {/* Instagram Account Selection — choose which IG account this post goes to */}
              {platforms.instagram && instagramAccounts.length > 0 && (
                <div style={{ marginTop: "12px" }}>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                    Post to Instagram Account
                  </label>
                  <select
                    className="sm-form-input"
                    value={selectedIgAccount?.id || ""}
                    onChange={(e) => setSelectedIgAccountId(Number(e.target.value))}
                    disabled={instagramAccounts.length === 1}
                  >
                    {instagramAccounts.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        @{acc.account_username || acc.account_name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Facebook Page Selection */}
              {platforms.facebook && facebookPages.length > 0 && (
                <div style={{ marginTop: "12px" }}>
                  <label style={{ fontSize: "12px", fontWeight: "600", display: "block", marginBottom: "4px" }}>
                    Post to Facebook Page
                  </label>
                  <select
                    className="sm-form-input"
                    value={selectedFbAccount?.id || ""}
                    onChange={(e) => setSelectedFbAccountId(Number(e.target.value))}
                    disabled={facebookPages.length === 1}
                  >
                    {facebookPages.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {acc.account_name || `Page ${acc.platform_account_id}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {Object.entries(metaResults).map(([platform, result]) => {
                const PlatformIcon = platform === "FACEBOOK" ? Facebook : Instagram;
                const label = META_LABELS[platform];
                return (
                  <div
                    key={platform}
                    style={{
                      marginTop: "12px",
                      fontSize: "12px",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      background: result.status === "FAILED" ? "rgba(220, 38, 38, 0.1)" : result.status === "PUBLISHED" ? "rgba(16, 185, 129, 0.1)" : "rgba(59, 130, 246, 0.1)",
                      color: result.status === "FAILED" ? "#991b1b" : result.status === "PUBLISHED" ? "#065f46" : "#1e40af",
                    }}
                  >
                    <PlatformIcon size={14} />
                    {result.status === "PUBLISHING" && `Publishing to ${label} (this can take a minute)...`}
                    {result.status === "PUBLISHED" && (
                      <>
                        Published on {label}.
                        {result.url && (
                          <a href={result.url} target="_blank" rel="noopener noreferrer" style={{ color: "inherit", fontWeight: 700 }}>
                            View post
                          </a>
                        )}
                      </>
                    )}
                    {result.status === "FAILED" && `${label} failed: ${result.error}`}
                  </div>
                );
              })}

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
              disabled={isSubmitting || !selectedVideo || selectedPlatformNames.length === 0 || youtubeBlocksSubmit}
              style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: "700" }}
            >
              {isSubmitting ? (
                <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
                  <Loader2 size={16} className="sm-spin" /> Publishing to {targetLabel}...
                </span>
              ) : (
                `🚀 Publish Video to ${targetLabel}`
              )}
            </button>
          </div>
        </div>
      </form>

      {/* Publication Success Modal */}
      {showSuccessModal && (
        <div
          className="sm-modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowSuccessModal(false);
            }
          }}
        >
          <div
            className="sm-success-modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="sm-success-modal-title"
            aria-describedby="sm-success-modal-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="sm-modal-close-btn"
              onClick={() => setShowSuccessModal(false)}
              aria-label="Close published success modal"
            >
              <X size={20} />
            </button>

            <div className="sm-celebration-container">
              <div className="sm-celebration-pulse" />
              <div className="sm-confetti-particle sm-confetti-1" />
              <div className="sm-confetti-particle sm-confetti-2" />
              <div className="sm-confetti-particle sm-confetti-3" />
              <div className="sm-confetti-particle sm-confetti-4" />
              <div className="sm-confetti-particle sm-confetti-5" />
              <div className="sm-confetti-particle sm-confetti-6" />
              <div className="sm-success-icon-badge">
                <CheckCircle2 size={38} strokeWidth={2.5} />
              </div>
            </div>

            <h2 id="sm-success-modal-title" className="sm-success-modal-title">
              Video Published!
            </h2>
            <p id="sm-success-modal-desc" className="sm-success-modal-text">
              Your video was published to {targetLabel}. Check each platform's status on this page for links to every post.
            </p>

            {postTitle && (
              <div className="sm-success-video-card">
                <div className="sm-success-video-info">
                  <span className="sm-success-video-name">{postTitle}</span>
                  <div className="sm-success-video-meta">
                    <span className="sm-badge PUBLISHED">{targetLabel}</span>
                    <span>•</span>
                    <span>{privacyStatus}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="sm-modal-actions">
              {publishedUrl && (
                <a
                  href={publishedUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="sm-btn-modal-primary"
                >
                  <ExternalLink size={16} /> View Published Post
                </a>
              )}
              <div className="sm-modal-actions-secondary-row">
                <button
                  type="button"
                  className="sm-btn-modal-secondary"
                  onClick={() => {
                    setShowSuccessModal(false);
                    navigate("/social-media/history");
                  }}
                >
                  <History size={15} /> View Post History
                </button>
                <button
                  type="button"
                  className="sm-btn-modal-secondary"
                  onClick={handleResetForm}
                >
                  <PlusCircle size={15} /> Create Another Post
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CreatePost;
