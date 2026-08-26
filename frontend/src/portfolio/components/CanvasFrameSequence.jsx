import { useEffect, useRef, useState } from "react";
import "./CanvasFrameSequence.css";

/**
 * CanvasFrameSequence: High-Performance 240-Frame 3D Motion Engine
 * Loads and scrubs 240 sequential frames on scroll
 */
export default function CanvasFrameSequence({
  scrollProgress = 0,
  totalFrames = 240,
  faceTranslateX = 0, // in vw
  faceScale = 1,
  faceOpacity = 0.88,
  mousePos = { x: 0, y: 0 },
}) {
  const canvasRef = useRef(null);
  const imagesRef = useRef([]);
  const [loadedCount, setLoadedCount] = useState(0);
  const currentFrameRef = useRef(0);
  const targetFrameRef = useRef(0);

  // Preload all 240 frames
  useEffect(() => {
    const images = [];
    let isMounted = true;
    let successfulLoads = 0;

    for (let i = 1; i <= totalFrames; i++) {
      const paddedNum = String(i).padStart(3, "0");
      const img = new Image();
      img.src = `/portfolio/frames/ezgif-frame-${paddedNum}.jpg`;

      img.onload = () => {
        successfulLoads++;
        if (
          isMounted &&
          (successfulLoads === 1 ||
            successfulLoads % 20 === 0 ||
            successfulLoads === totalFrames)
        ) {
          setLoadedCount(successfulLoads);
        }
      };

      images.push(img);
    }

    imagesRef.current = images;

    return () => {
      isMounted = false;
    };
  }, [totalFrames]);

  // Update target frame when scroll changes
  useEffect(() => {
    const maxIdx = totalFrames - 1;
    const nextTarget = Math.min(Math.max(Math.floor(scrollProgress * maxIdx), 0), maxIdx);
    targetFrameRef.current = nextTarget;
  }, [scrollProgress, totalFrames]);

  // Render loop with smooth frame interpolation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    let animationFrameId;

    const render = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = window.innerWidth;
      const height = window.innerHeight;

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);

      // Smooth lerp between current frame and target frame for buttery motion
      const diff = targetFrameRef.current - currentFrameRef.current;
      if (Math.abs(diff) > 0.05) {
        currentFrameRef.current += diff * 0.25; // responsive spring lerp
      } else {
        currentFrameRef.current = targetFrameRef.current;
      }

      const activeIndex = Math.min(
        Math.max(Math.round(currentFrameRef.current), 0),
        totalFrames - 1
      );

      const frameList = imagesRef.current;
      let targetImg = frameList[activeIndex];

      // If the current target frame is still downloading, find the nearest loaded frame
      if (!targetImg || !targetImg.complete || targetImg.naturalWidth === 0) {
        for (let offset = 1; offset < 30; offset++) {
          const prev = frameList[Math.max(0, activeIndex - offset)];
          if (prev && prev.complete && prev.naturalWidth > 0) {
            targetImg = prev;
            break;
          }
          const next = frameList[Math.min(totalFrames - 1, activeIndex + offset)];
          if (next && next.complete && next.naturalWidth > 0) {
            targetImg = next;
            break;
          }
        }
      }

      // Draw active frame with cover math, translation, scale, and opacity
      if (targetImg && targetImg.complete && targetImg.naturalWidth > 0) {
        const imgW = targetImg.naturalWidth;
        const imgH = targetImg.naturalHeight;
        const imgAspect = imgW / imgH;
        const screenAspect = width / height;

        let drawW, drawH, drawX, drawY;

        if (screenAspect > imgAspect) {
          drawW = width;
          drawH = width / imgAspect;
        } else {
          drawH = height;
          drawW = height * imgAspect;
        }

        // Horizontal translation (left-to-right) + subtle mouse parallax
        const offsetX = (faceTranslateX / 100) * width + mousePos.x * 0.4;
        const offsetY = mousePos.y * 0.3;

        drawX = (width - drawW) / 2 + offsetX;
        drawY = (height - drawH) / 2 + offsetY;

        // Apply scale from center
        ctx.translate(width / 2 + offsetX, height / 2 + offsetY);
        ctx.scale(faceScale, faceScale);
        ctx.translate(-(width / 2 + offsetX), -(height / 2 + offsetY));

        ctx.globalAlpha = faceOpacity;
        ctx.drawImage(targetImg, drawX, drawY, drawW, drawH);
      }

      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [loadedCount, totalFrames, faceTranslateX, faceScale, faceOpacity, mousePos]);

  return (
    <div className="canvas-frame-sequence-wrapper">
      <canvas ref={canvasRef} className="frame-sequence-canvas" />
    </div>
  );
}
