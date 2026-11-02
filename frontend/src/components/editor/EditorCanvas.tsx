"use client";
import { useRef, useState, useCallback, useEffect, type WheelEvent } from "react";
import { CropOverlay } from "./CropOverlay";

const MIN_ZOOM = 0.1;
const MAX_ZOOM = 8;

function clamp(val: number, min: number, max: number) {
  return Math.max(min, Math.min(max, val));
}

interface EditorCanvasProps {
  imageUrl: string;
  zoom: number;
  onZoomChange?: (zoom: number) => void;
  onWheel: (e: WheelEvent) => void;
  previewOffsetX?: number;
  previewOffsetY?: number;
  previewScale?: number;
  cropMode?: boolean;
  onApplyCrop?: (x: number, y: number, w: number, h: number) => void;
  onCancelCrop?: () => void;
  onZoomToFit?: () => void;
}

export function EditorCanvas({
  imageUrl,
  zoom,
  onZoomChange,
  onWheel,
  previewOffsetX = 0,
  previewOffsetY = 0,
  previewScale = 1,
  cropMode = false,
  onApplyCrop,
  onCancelCrop,
  onZoomToFit,
}: EditorCanvasProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [spaceHeld, setSpaceHeld] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  // Space key tracking for pan mode
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !cropMode) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        e.preventDefault();
        setSpaceHeld(true);
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") setSpaceHeld(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [cropMode]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Middle-click or Space+left-click to pan
      if (e.button === 1 || (spaceHeld && e.button === 0)) {
        e.preventDefault();
        setIsPanning(true);
        panStart.current = { x: e.clientX, y: e.clientY, panX: panOffset.x, panY: panOffset.y };
      }
    },
    [spaceHeld, panOffset]
  );

  useEffect(() => {
    if (!isPanning) return;
    const onMove = (e: MouseEvent) => {
      setPanOffset({
        x: panStart.current.panX + (e.clientX - panStart.current.x),
        y: panStart.current.panY + (e.clientY - panStart.current.y),
      });
    };
    const onUp = () => setIsPanning(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isPanning]);

  // Cursor-centered zoom
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      if (!onZoomChange || !containerRef.current) {
        onWheel(e);
        return;
      }
      e.preventDefault();
      const rect = containerRef.current.getBoundingClientRect();
      const cursorX = e.clientX - rect.left - rect.width / 2;
      const cursorY = e.clientY - rect.top - rect.height / 2;

      const prevZoom = zoom;
      const step = prevZoom < 1 ? 0.1 : prevZoom < 2 ? 0.25 : 0.5;
      const direction = e.deltaY > 0 ? -1 : 1;
      const newZoom = clamp(zoom + direction * step, MIN_ZOOM, MAX_ZOOM);
      const factor = newZoom / prevZoom;

      setPanOffset({
        x: cursorX - factor * (cursorX - panOffset.x),
        y: cursorY - factor * (cursorY - panOffset.y),
      });
      onZoomChange(newZoom);
    },
    [zoom, panOffset, onZoomChange, onWheel]
  );

  // Double-click to toggle fit/1x
  const handleDoubleClick = useCallback(() => {
    if (onZoomToFit) {
      if (Math.abs(zoom - 1) < 0.01) {
        onZoomToFit();
      } else {
        onZoomChange?.(1);
        setPanOffset({ x: 0, y: 0 });
      }
    }
  }, [zoom, onZoomToFit, onZoomChange]);

  if (!imageUrl) {
    return (
      <div className="flex items-center justify-center h-full text-th-tertiary">
        Loading image...
      </div>
    );
  }

  const hasPreview = previewOffsetX !== 0 || previewOffsetY !== 0 || previewScale !== 1;
  // Always show a checkerboard so transparent cut-outs are visible.
  const showCheckerboard = true;
  const displayUrl = imageUrl;

  return (
    <div
      ref={containerRef}
      className={`h-full overflow-hidden bg-surface rounded-lg border border-theme relative ${
        showCheckerboard ? "checkerboard-bg" : ""
      }`}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      style={{ cursor: spaceHeld || isPanning ? "grab" : undefined }}
    >
      {onZoomToFit && (
        <button
          onClick={() => {
            onZoomToFit();
            setPanOffset({ x: 0, y: 0 });
          }}
          className="absolute top-2 right-2 z-10 px-2 py-1 bg-surface-tertiary/80 text-th-secondary hover:text-th-primary rounded text-xs"
          aria-label="Zoom to fit"
          title="Fit image to view (F)"
        >
          Fit
        </button>
      )}
      <div
        className="w-full h-full flex items-center justify-center"
        style={{
          transform: `translate(${panOffset.x}px, ${panOffset.y}px)`,
        }}
      >
        <div
          className="relative"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          <img
            ref={imgRef}
            src={displayUrl}
            alt="Editor preview"
            className="block transition-transform duration-150"
            // Fit inside the canvas at zoom 1 (header + toolbar + padding ~ 230px).
            style={{
              maxWidth: "calc(100vw - 64px)",
              maxHeight: "calc(100vh - 230px)",
              ...(hasPreview
                ? { transform: `translate(${previewOffsetX}px, ${previewOffsetY}px) scale(${previewScale})` }
                : {}),
            }}
            draggable={false}
          />
          {cropMode && onApplyCrop && onCancelCrop && (
            <CropOverlay
              imageRef={imgRef}
              onApply={onApplyCrop}
              onCancel={onCancelCrop}
            />
          )}
        </div>
      </div>

      {/* Checkerboard CSS */}
      <style jsx>{`
        .checkerboard-bg {
          background-image:
            linear-gradient(45deg, #404040 25%, transparent 25%),
            linear-gradient(-45deg, #404040 25%, transparent 25%),
            linear-gradient(45deg, transparent 75%, #404040 75%),
            linear-gradient(-45deg, transparent 75%, #404040 75%);
          background-size: 20px 20px;
          background-position: 0 0, 0 10px, 10px -10px, -10px 0;
        }
      `}</style>
    </div>
  );
}
