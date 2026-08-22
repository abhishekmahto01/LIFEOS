import { useEffect, useState } from "react";
import "./CustomCursor.css";

function CustomCursor() {
  const [pos, setPos] = useState({ x: -100, y: -100 });
  const [hoverState, setHoverState] = useState("default"); // 'default', 'pointer', 'view', 'lifeos'
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Disable on touch devices or reduced motion preference
    if (window.matchMedia("(pointer: coarse)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const onMouseMove = (e) => {
      setPos({ x: e.clientX, y: e.clientY });
      if (!isVisible) setIsVisible(true);

      const target = e.target;
      if (!target) return;

      const projectCard = target.closest("[data-cursor='view']");
      const lifeosBtn = target.closest("[data-cursor='lifeos']");
      const interactive = target.closest("button, a, input, [role='button'], .interactive-node");

      if (projectCard) {
        setHoverState("view");
      } else if (lifeosBtn) {
        setHoverState("lifeos");
      } else if (interactive) {
        setHoverState("pointer");
      } else {
        setHoverState("default");
      }
    };

    const onMouseLeave = () => setIsVisible(false);
    const onMouseEnter = () => setIsVisible(true);

    window.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseleave", onMouseLeave);
    document.addEventListener("mouseenter", onMouseEnter);

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseleave", onMouseLeave);
      document.removeEventListener("mouseenter", onMouseEnter);
    };
  }, [isVisible]);

  if (!isVisible) return null;

  return (
    <div
      className={`custom-cursor-wrap state-${hoverState}`}
      style={{
        transform: `translate3d(${pos.x}px, ${pos.y}px, 0)`,
      }}
    >
      <div className="cursor-dot"></div>
      <div className="cursor-ring">
        {hoverState === "view" && <span className="cursor-tag">VIEW</span>}
        {hoverState === "lifeos" && <span className="cursor-tag">WARP</span>}
      </div>
    </div>
  );
}

export default CustomCursor;
