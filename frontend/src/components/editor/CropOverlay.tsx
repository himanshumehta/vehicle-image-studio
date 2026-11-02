"use client";
import { useState, useCallback, useRef, useEffect, type MouseEvent, type TouchEvent } from "react";

interface CropOverlayProps {
  imageRef: React.RefObject<HTMLImageElement | null>;
  onApply: (x: number, y: number, w: number, h: number) => void;
  onCancel: () => void;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

type DragMode = "draw" | "move" | "n" | "s" | "e" | "w" | "nw" | "ne" | "sw" | "se" | null;

const ASPECT_RATIOS: { label: string; value: number | null }[] = [
  { label: "Free", value: null },
  { label: "16:9", value: 16 / 9 },
  { label: "4:3", value: 4 / 3 },
  { label: "1:1", value: 1 },
  { label: "3:2", value: 3 / 2 },
];

function clamp(val: number, min: number, max: number) {
  return Math.max(min, Math.min(max, val));
}

export function CropOverlay({ imageRef, onApply, onCancel }: CropOverlayProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const [selection, setSelection] = useState<Rect | null>(null);
  const [dragMode, setDragMode] = useState<DragMode>(null);
  const [aspectRatio, setAspectRatio] = useState<number | null>(null);
  // Display-pixel -> image-pixel factors, refreshed from event handlers (not during render).
  const [pxScale, setPxScale] = useState<{ x: number; y: number } | null>(null);
  const dragStart = useRef({ x: 0, y: 0 });
  const dragSelStart = useRef<Rect>({ x: 0, y: 0, w: 0, h: 0 });

  const getOverlayBounds = useCallback(() => {
    if (!overlayRef.current) return { left: 0, top: 0, width: 0, height: 0 };
    const rect = overlayRef.current.getBoundingClientRect();
    return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
  }, []);

  const toOverlayCoords = useCallback(
    (clientX: number, clientY: number) => {
      const bounds = getOverlayBounds();
      return {
        x: clamp(clientX - bounds.left, 0, bounds.width),
        y: clamp(clientY - bounds.top, 0, bounds.height),
      };
    },
    [getOverlayBounds]
  );

  const getHandleAtPoint = useCallback(
    (px: number, py: number, sel: Rect): DragMode => {
      const HANDLE = 10;
      const { x, y, w, h } = sel;
      const right = x + w;
      const bottom = y + h;

      if (Math.abs(px - x) < HANDLE && Math.abs(py - y) < HANDLE) return "nw";
      if (Math.abs(px - right) < HANDLE && Math.abs(py - y) < HANDLE) return "ne";
      if (Math.abs(px - x) < HANDLE && Math.abs(py - bottom) < HANDLE) return "sw";
      if (Math.abs(px - right) < HANDLE && Math.abs(py - bottom) < HANDLE) return "se";

      if (Math.abs(py - y) < HANDLE && px > x + HANDLE && px < right - HANDLE) return "n";
      if (Math.abs(py - bottom) < HANDLE && px > x + HANDLE && px < right - HANDLE) return "s";
      if (Math.abs(px - x) < HANDLE && py > y + HANDLE && py < bottom - HANDLE) return "w";
      if (Math.abs(px - right) < HANDLE && py > y + HANDLE && py < bottom - HANDLE) return "e";

      if (px > x && px < right && py > y && py < bottom) return "move";

      return null;
    },
    []
  );

  const handlePointerDown = useCallback(
    (clientX: number, clientY: number) => {
      const pt = toOverlayCoords(clientX, clientY);

      if (selection) {
        const handle = getHandleAtPoint(pt.x, pt.y, selection);
        if (handle) {
          setDragMode(handle);
          dragStart.current = pt;
          dragSelStart.current = { ...selection };
          return;
        }
      }

      setDragMode("draw");
      dragStart.current = pt;
      setSelection({ x: pt.x, y: pt.y, w: 0, h: 0 });
    },
    [selection, toOverlayCoords, getHandleAtPoint]
  );

  const handlePointerMove = useCallback(
    (clientX: number, clientY: number) => {
      if (!dragMode) return;
      const img = imageRef.current;
      const overlay = overlayRef.current;
      if (img && overlay && overlay.clientWidth > 0 && overlay.clientHeight > 0) {
        setPxScale({ x: img.naturalWidth / overlay.clientWidth, y: img.naturalHeight / overlay.clientHeight });
      }
      const pt = toOverlayCoords(clientX, clientY);
      const bounds = getOverlayBounds();
      const dx = pt.x - dragStart.current.x;
      const dy = pt.y - dragStart.current.y;
      const s = dragSelStart.current;

      setSelection((prev) => {
        if (!prev) return prev;

        if (dragMode === "draw") {
          const x = Math.min(dragStart.current.x, pt.x);
          let y = Math.min(dragStart.current.y, pt.y);
          const w = Math.abs(pt.x - dragStart.current.x);
          let h = Math.abs(pt.y - dragStart.current.y);
          if (aspectRatio) {
            h = w / aspectRatio;
            if (pt.y < dragStart.current.y) y = dragStart.current.y - h;
          }
          return { x, y, w, h };
        }

        if (dragMode === "move") {
          const nx = clamp(s.x + dx, 0, bounds.width - s.w);
          const ny = clamp(s.y + dy, 0, bounds.height - s.h);
          return { ...prev, x: nx, y: ny };
        }

        let { x, y, w, h } = { ...s };
        if (dragMode.includes("n")) {
          const newY = clamp(s.y + dy, 0, s.y + s.h - 10);
          h = s.h - (newY - s.y);
          y = newY;
          if (aspectRatio) w = h * aspectRatio;
        }
        if (dragMode.includes("s")) {
          h = clamp(s.h + dy, 10, bounds.height - s.y);
          if (aspectRatio) w = h * aspectRatio;
        }
        if (dragMode.includes("w")) {
          const newX = clamp(s.x + dx, 0, s.x + s.w - 10);
          w = s.w - (newX - s.x);
          x = newX;
          if (aspectRatio) h = w / aspectRatio;
        }
        if (dragMode.includes("e")) {
          w = clamp(s.w + dx, 10, bounds.width - s.x);
          if (aspectRatio) h = w / aspectRatio;
        }
        return { x, y, w, h };
      });
    },
    [dragMode, toOverlayCoords, getOverlayBounds, aspectRatio, imageRef]
  );

  const handlePointerUp = useCallback(() => {
    if (dragMode === "draw" && selection && selection.w < 5 && selection.h < 5) {
      setSelection(null);
    }
    setDragMode(null);
  }, [dragMode, selection]);

  const onMouseDown = useCallback(
    (e: MouseEvent) => {
      e.preventDefault();
      handlePointerDown(e.clientX, e.clientY);
    },
    [handlePointerDown]
  );

  const onTouchStart = useCallback(
    (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      e.preventDefault();
      const t = e.touches[0];
      handlePointerDown(t.clientX, t.clientY);
    },
    [handlePointerDown]
  );

  useEffect(() => {
    const onMove = (e: globalThis.MouseEvent) => handlePointerMove(e.clientX, e.clientY);
    const onUp = () => handlePointerUp();
    const onTouchMove = (e: globalThis.TouchEvent) => {
      if (e.touches.length !== 1) return;
      e.preventDefault();
      handlePointerMove(e.touches[0].clientX, e.touches[0].clientY);
    };
    const onTouchEnd = () => handlePointerUp();

    if (dragMode) {
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      window.addEventListener("touchmove", onTouchMove, { passive: false });
      window.addEventListener("touchend", onTouchEnd);
      return () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        window.removeEventListener("touchmove", onTouchMove);
        window.removeEventListener("touchend", onTouchEnd);
      };
    }
  }, [dragMode, handlePointerMove, handlePointerUp]);

  const handleApply = useCallback(() => {
    if (!selection || !imageRef.current || !overlayRef.current) return;
    const img = imageRef.current;
    const overlay = overlayRef.current;
    const displayW = overlay.clientWidth;
    const displayH = overlay.clientHeight;
    const naturalW = img.naturalWidth;
    const naturalH = img.naturalHeight;
    const scaleX = naturalW / displayW;
    const scaleY = naturalH / displayH;

    const x = Math.round(selection.x * scaleX);
    const y = Math.round(selection.y * scaleY);
    const w = Math.round(selection.w * scaleX);
    const h = Math.round(selection.h * scaleY);
    onApply(x, y, w, h);
  }, [selection, imageRef, onApply]);

  // Keyboard shortcuts: Escape=cancel, Enter=apply
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      } else if (e.key === "Enter" && selection && selection.w > 20 && selection.h > 20) {
        e.preventDefault();
        handleApply();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onCancel, selection, handleApply]);

  const dimLabel =
    selection && selection.w > 30 && selection.h > 20 && pxScale
      ? `${Math.round(selection.w * pxScale.x)} x ${Math.round(selection.h * pxScale.y)}`
      : "";

  const cursorForMode = (mode: DragMode): string => {
    switch (mode) {
      case "n":
      case "s":
        return "ns-resize";
      case "e":
      case "w":
        return "ew-resize";
      case "nw":
      case "se":
        return "nwse-resize";
      case "ne":
      case "sw":
        return "nesw-resize";
      case "move":
        return "move";
      default:
        return "crosshair";
    }
  };

  return (
    <div
      ref={overlayRef}
      className="absolute inset-0"
      style={{ cursor: dragMode ? cursorForMode(dragMode) : "crosshair" }}
      onMouseDown={onMouseDown}
      onTouchStart={onTouchStart}
    >
      {/* Aspect ratio buttons */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 flex gap-1 bg-[var(--surface-overlay)] rounded-lg px-2 py-1">
        {ASPECT_RATIOS.map((ar) => (
          <button
            key={ar.label}
            onClick={(e) => {
              e.stopPropagation();
              setAspectRatio(ar.value);
            }}
            className={`px-2 py-0.5 text-xs rounded ${
              aspectRatio === ar.value
                ? "bg-teal-500 text-white"
                : "text-th-primary hover:bg-interactive-hover"
            }`}
          >
            {ar.label}
          </button>
        ))}
      </div>

      {/* Dark mask outside selection */}
      {selection && selection.w > 0 && selection.h > 0 && (
        <>
          <div
            className="absolute bg-[var(--surface-overlay)] left-0 right-0 top-0"
            style={{ height: selection.y }}
          />
          <div
            className="absolute bg-[var(--surface-overlay)] left-0 right-0 bottom-0"
            style={{ top: selection.y + selection.h }}
          />
          <div
            className="absolute bg-[var(--surface-overlay)] left-0"
            style={{ top: selection.y, height: selection.h, width: selection.x }}
          />
          <div
            className="absolute bg-[var(--surface-overlay)] right-0"
            style={{ top: selection.y, height: selection.h, left: selection.x + selection.w }}
          />

          {/* Selection border */}
          <div
            className="absolute border-2 border-dashed border-white"
            style={{
              left: selection.x,
              top: selection.y,
              width: selection.w,
              height: selection.h,
              pointerEvents: "none",
            }}
          >
            {/* Rule-of-thirds grid */}
            {selection.w > 60 && selection.h > 60 && (
              <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: "none" }}>
                <line x1="33.33%" y1="0" x2="33.33%" y2="100%" stroke="white" strokeOpacity="0.3" strokeWidth="1" />
                <line x1="66.67%" y1="0" x2="66.67%" y2="100%" stroke="white" strokeOpacity="0.3" strokeWidth="1" />
                <line x1="0" y1="33.33%" x2="100%" y2="33.33%" stroke="white" strokeOpacity="0.3" strokeWidth="1" />
                <line x1="0" y1="66.67%" x2="100%" y2="66.67%" stroke="white" strokeOpacity="0.3" strokeWidth="1" />
              </svg>
            )}
          </div>

          {/* Resize handles */}
          {[
            { pos: "nw", left: selection.x, top: selection.y },
            { pos: "ne", left: selection.x + selection.w, top: selection.y },
            { pos: "sw", left: selection.x, top: selection.y + selection.h },
            { pos: "se", left: selection.x + selection.w, top: selection.y + selection.h },
            { pos: "n", left: selection.x + selection.w / 2, top: selection.y },
            { pos: "s", left: selection.x + selection.w / 2, top: selection.y + selection.h },
            { pos: "w", left: selection.x, top: selection.y + selection.h / 2 },
            { pos: "e", left: selection.x + selection.w, top: selection.y + selection.h / 2 },
          ].map(({ pos, left, top }) => (
            <div
              key={pos}
              className="absolute w-3 h-3 bg-white border border-strong rounded-sm"
              style={{
                left: left - 6,
                top: top - 6,
                cursor: cursorForMode(pos as DragMode),
                pointerEvents: "none",
              }}
            />
          ))}

          {/* Dimension label */}
          {dimLabel && (
            <div
              className="absolute bg-[var(--surface-overlay)] text-white text-xs px-2 py-1 rounded pointer-events-none"
              style={{
                left: selection.x + selection.w / 2,
                top: selection.y + selection.h + 8,
                transform: "translateX(-50%)",
              }}
            >
              {dimLabel}
            </div>
          )}

          {/* Action buttons */}
          {!dragMode && selection.w > 20 && selection.h > 20 && (
            <div
              className="absolute flex gap-2"
              style={{
                left: selection.x + selection.w / 2,
                top: selection.y + selection.h + 32,
                transform: "translateX(-50%)",
              }}
            >
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleApply();
                }}
                className="px-4 py-1.5 bg-teal-600 text-white rounded-lg hover:bg-teal-500 text-sm font-medium shadow-lg"
              >
                Apply Crop
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCancel();
                }}
                className="px-4 py-1.5 bg-interactive-hover text-th-primary rounded-lg hover:bg-surface-elevated text-sm font-medium shadow-lg"
              >
                Cancel
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
