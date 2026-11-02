"use client";
import { useState, useRef, useCallback, memo } from "react";

interface BeforeAfterSliderProps {
  beforeUrl: string;
  afterUrl: string;
}

export const BeforeAfterSlider = memo(function BeforeAfterSlider({ beforeUrl, afterUrl }: BeforeAfterSliderProps) {
  const [position, setPosition] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const updatePosition = useCallback((clientX: number) => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const x = clientX - rect.left;
    const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setPosition(percent);
  }, []);

  const onMouseDown = useCallback(() => {
    isDragging.current = true;
  }, []);

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging.current) {
        updatePosition(e.clientX);
      }
    },
    [updatePosition]
  );

  const onMouseUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      updatePosition(e.touches[0].clientX);
    },
    [updatePosition]
  );

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden rounded-lg border border-theme select-none cursor-col-resize"
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onTouchMove={onTouchMove}
    >
      {/* After image (full) */}
      <img
        src={afterUrl}
        alt="After"
        className="absolute inset-0 w-full h-full object-contain"
        draggable={false}
      />

      {/* Before image (clipped) */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ width: `${position}%` }}
      >
        <img
          src={beforeUrl}
          alt="Before"
          className="absolute inset-0 w-full h-full object-contain"
          // The clip box is `position`% of the container; scale the image back to full width.
          style={{ width: `${(100 / Math.max(position, 0.1)) * 100}%`, maxWidth: "none" }}
          draggable={false}
        />
      </div>

      {/* Slider line */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg z-10"
        style={{ left: `${position}%` }}
        onMouseDown={onMouseDown}
        onTouchStart={onMouseDown}
      >
        {/* Handle */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center">
          <span className="text-zinc-800 text-xs font-bold">&harr;</span>
        </div>
      </div>

      {/* Labels */}
      <div className="absolute top-3 left-3 bg-[var(--surface-overlay)] text-white text-xs px-2 py-1 rounded">
        Before
      </div>
      <div className="absolute top-3 right-3 bg-[var(--surface-overlay)] text-white text-xs px-2 py-1 rounded">
        After
      </div>
    </div>
  );
});
