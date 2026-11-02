"use client";
import { BUSY_STATES, type ProcessingState } from "@/lib/types";

const labels: Record<ProcessingState, string> = {
  original: "Original",
  replaced: "Image replaced",
  "removing-bg": "Removing background...",
  "bg-removed": "Background removed",
  compositing: "Applying studio background...",
  "studio-ready": "Studio composite ready",
  upscaling: "Upscaling (Real-ESRGAN)...",
  upscaled: "Upscaled",
  mirroring: "Mirroring...",
  mirrored: "Mirrored",
  enhancing: "Enhancing...",
  enhanced: "Enhanced",
  cropping: "Cropping...",
  cropped: "Cropped",
  watermarking: "Adding watermark...",
  watermarked: "Watermark added",
  "llm-editing": "AI editing image...",
  "llm-edited": "AI edit complete",
  uploading: "Saving...",
  uploaded: "Saved",
};

const isProcessing = (state: ProcessingState) => BUSY_STATES.has(state);

export function ProcessingStatus({ state }: { state: ProcessingState }) {
  return (
    <div className="flex items-center gap-2" role="status" aria-live="polite" aria-busy={isProcessing(state)}>
      {isProcessing(state) && (
        <div className="animate-spin rounded-full h-4 w-4 border-2 border-strong border-t-blue-400" />
      )}
      {state === "uploaded" && (
        <span className="text-green-400">&#10003;</span>
      )}
      <span
        className={`text-sm ${
          state === "uploaded"
            ? "text-green-400"
            : isProcessing(state)
            ? "text-blue-400"
            : "text-th-secondary"
        }`}
      >
        {labels[state]}
      </span>
    </div>
  );
}
