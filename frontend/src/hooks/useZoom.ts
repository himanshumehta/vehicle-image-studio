"use client";
import { useState, useCallback, type WheelEvent } from "react";

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

export function useZoom(initial = 1) {
  const [zoom, setZoom] = useState(initial);

  const zoomIn = useCallback(() => {
    setZoom((z) => Math.min(z + ZOOM_STEP, MAX_ZOOM));
  }, []);

  const zoomOut = useCallback(() => {
    setZoom((z) => Math.max(z - ZOOM_STEP, MIN_ZOOM));
  }, []);

  const resetZoom = useCallback(() => {
    setZoom(1);
  }, []);

  const zoomToFit = useCallback(
    (containerW: number, containerH: number, imgW: number, imgH: number) => {
      if (!imgW || !imgH) return;
      const padding = 32;
      const scaleX = (containerW - padding * 2) / imgW;
      const scaleY = (containerH - padding * 2) / imgH;
      const fitZoom = Math.min(scaleX, scaleY, MAX_ZOOM);
      setZoom(Math.max(fitZoom, MIN_ZOOM));
    },
    []
  );

  const onWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    setZoom((z) => {
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      return Math.min(Math.max(z + delta, MIN_ZOOM), MAX_ZOOM);
    });
  }, []);

  return { zoom, zoomIn, zoomOut, resetZoom, zoomToFit, onWheel, setZoom };
}
