"use client";
import { useState, useRef, useEffect } from "react";
import { BUSY_STATES, type ProcessingState } from "@/lib/types";
import type { UpscaleFactor } from "@/lib/api";
import type { WatermarkOptions } from "@/hooks/useProcessing";

const UPSCALE_FACTORS: UpscaleFactor[] = [2, 4, 8];

interface EditorToolbarProps {
  state: ProcessingState;
  onRemoveBg: () => void;
  onReplace: (file: File) => void;
  onApplyBackground: (background?: File) => void;
  onUpscale: (scale: UpscaleFactor) => void;
  onAiEnhance: () => void;
  onMirror: () => void;
  onWatermark: (options: WatermarkOptions) => void;
  onCrop: () => void;
  cropMode: boolean;
  onUpload: () => void;
  onReset: () => void;
  onUndo: () => void;
  canUndo: boolean;
}

// --- Icon components (16x16 inline SVGs) ---

function IconScissors({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="4" cy="4" r="2" />
      <circle cx="4" cy="12" r="2" />
      <path d="M5.5 5.5L12 12M5.5 10.5L12 4" />
    </svg>
  );
}

function IconImage({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="12" height="12" rx="2" />
      <circle cx="5.5" cy="5.5" r="1" />
      <path d="M14 10l-3-3-7 7" />
    </svg>
  );
}

function IconSparkles({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1v2M8 13v2M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M1 8h2M13 8h2M3.5 12.5l1.4-1.4M11.1 4.9l1.4-1.4" />
    </svg>
  );
}

function IconWand({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 14L10 6M12 2l2 2-2 2-2-2 2-2z" />
      <path d="M6 2v1M3 5h1M13 9v1M11 12h1" strokeWidth="1" />
    </svg>
  );
}

function IconFlipHorizontal({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1v14" strokeDasharray="2 2" />
      <path d="M5 4H3l2 8H3" />
      <path d="M11 4h2l-2 8h2" />
    </svg>
  );
}

function IconCrop({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 1v11h11" />
      <path d="M1 4h11v11" />
    </svg>
  );
}

function IconUpload({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 10V2" />
      <path d="M5 5l3-3 3 3" />
      <path d="M2 10v3a1 1 0 001 1h10a1 1 0 001-1v-3" />
    </svg>
  );
}

function IconUndo({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7h7a3 3 0 010 6H8" />
      <path d="M6 4L3 7l3 3" />
    </svg>
  );
}

function IconRotateCcw({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4v4h4" />
      <path d="M2 8a6 6 0 1011-3" />
    </svg>
  );
}

function IconChevronDown({ className = "w-3 h-3" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

function IconWatermark({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12h12" />
      <path d="M4 8l2-4 2 4" />
      <path d="M4.5 7h3" />
      <path d="M10 4v4" />
      <path d="M10 4h2.5" />
    </svg>
  );
}

function IconReplace({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2l2 2-2 2" />
      <path d="M2 7V6a3 3 0 013-3h9" />
      <path d="M4 14l-2-2 2-2" />
      <path d="M14 9v1a3 3 0 01-3 3H2" />
    </svg>
  );
}

// --- Toolbar button helper ---

const btnBase =
  "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all text-th-secondary hover:text-th-primary hover:bg-white/[0.06] disabled:opacity-30 disabled:pointer-events-none";

const btnActive =
  "bg-white/[0.08] text-th-primary ring-1 ring-white/10";

const btnUpload =
  "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all disabled:opacity-30 disabled:pointer-events-none text-green-400 hover:bg-green-500/10";

const divider = "w-px h-5 bg-white/[0.06]";

export function EditorToolbar({
  state,
  onRemoveBg,
  onReplace,
  onApplyBackground,
  onUpscale,
  onAiEnhance,
  onMirror,
  onWatermark,
  onCrop,
  cropMode,
  onUpload,
  onReset,
  onUndo,
  canUndo,
}: EditorToolbarProps) {
  const replaceFileInputRef = useRef<HTMLInputElement>(null);

  const [showPicker, setShowPicker] = useState(false);
  const [showUpscalePicker, setShowUpscalePicker] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);
  const upscalePickerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Watermark state
  const [showWatermarkPanel, setShowWatermarkPanel] = useState(false);
  const [wmText, setWmText] = useState("example.com");
  const [wmPosition, setWmPosition] = useState("bottom-right");
  const [wmOpacity, setWmOpacity] = useState(0.4);
  const [wmFontSize, setWmFontSize] = useState(32);
  const [wmColor, setWmColor] = useState("#FFFFFF");
  const [wmRepeat, setWmRepeat] = useState(false);
  const wmPanelRef = useRef<HTMLDivElement>(null);

  const isProcessing = BUSY_STATES.has(state);
  const canEnhance = !isProcessing;
  const canUpload = state !== "original" && state !== "uploaded" && !isProcessing;
  const canApplyTemplate = state === "bg-removed" && !isProcessing;

  // Close pickers on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowPicker(false);
      }
      if (upscalePickerRef.current && !upscalePickerRef.current.contains(e.target as Node)) {
        setShowUpscalePicker(false);
      }
      if (wmPanelRef.current && !wmPanelRef.current.contains(e.target as Node)) {
        setShowWatermarkPanel(false);
      }
    }
    if (showPicker || showUpscalePicker || showWatermarkPanel) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [showPicker, showUpscalePicker, showWatermarkPanel]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setShowPicker(false);
      onApplyBackground(file);
    }
    // Reset input so same file can be selected again
    e.target.value = "";
  }

  return (
    <div className="flex items-center gap-1" role="toolbar" aria-label="Image editing tools">

      {/* ── Process group ── */}

      {/* Replace with a local file */}
      <button
        onClick={() => replaceFileInputRef.current?.click()}
        disabled={isProcessing}
        className={btnBase}
        title="Replace image with a local file"
      >
        <IconReplace />
        <span>Replace</span>
      </button>
      <input
        ref={replaceFileInputRef}
        type="file"
        accept="image/*"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onReplace(file);
          e.target.value = "";
        }}
        className="hidden"
      />

      <button
        onClick={onRemoveBg}
        disabled={state !== "original" || isProcessing}
        className={`${btnBase} ${state === "removing-bg" ? "animate-pulse" : ""}`}
        aria-label="Remove background"
        title="Remove Background (R)"
      >
        <IconScissors />
        <span>Remove BG</span>
      </button>

      {/* Template picker */}
      <div className="relative" ref={pickerRef}>
        <button
          onClick={() => setShowPicker(!showPicker)}
          disabled={!canApplyTemplate}
          className={`${btnBase} ${showPicker ? btnActive : ""} ${state === "compositing" ? "animate-pulse" : ""}`}
        >
          <IconImage />
          <span>Background</span>
          <IconChevronDown />
        </button>

        {showPicker && canApplyTemplate && (
          <div className="absolute top-full left-0 mt-2 w-64 bg-surface-tertiary border border-strong rounded-xl shadow-2xl z-50 p-3">
            <div className="flex flex-col gap-2">
              <button
                onClick={() => {
                  setShowPicker(false);
                  onApplyBackground();
                }}
                className="w-full px-3 py-2 bg-interactive-hover text-th-primary rounded-lg hover:bg-surface-elevated transition-colors text-sm text-left"
              >
                White studio backdrop
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full px-3 py-2 bg-interactive-hover text-th-primary rounded-lg hover:bg-surface-elevated transition-colors text-sm text-left"
              >
                Upload custom background...
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
          </div>
        )}
      </div>

      {/* Upscale picker */}
      <div className="relative" ref={upscalePickerRef}>
        <button
          onClick={() => setShowUpscalePicker(!showUpscalePicker)}
          disabled={isProcessing}
          className={`${btnBase} ${showUpscalePicker ? btnActive : ""} ${state === "upscaling" ? "animate-pulse" : ""}`}
          aria-label="Upscale"
          title="Upscale with Real-ESRGAN (U)"
        >
          <IconSparkles />
          <span>{state === "upscaling" ? "Upscaling..." : "Upscale"}</span>
          <IconChevronDown />
        </button>

        {showUpscalePicker && !isProcessing && (
          <div className="absolute top-full left-0 mt-2 w-44 bg-surface-tertiary border border-strong rounded-xl shadow-2xl z-50 p-2 flex flex-col gap-1">
            {UPSCALE_FACTORS.map((f) => (
              <button
                key={f}
                onClick={() => {
                  setShowUpscalePicker(false);
                  onUpscale(f);
                }}
                className="w-full px-3 py-1.5 rounded-lg text-sm text-left text-th-primary hover:bg-interactive-hover"
              >
                {f}x {f === 8 ? "(two passes)" : ""}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={onAiEnhance}
        disabled={!canEnhance}
        className={`${btnBase} ${state === "enhancing" ? "animate-pulse" : ""}`}
        aria-label="AI enhance"
        title="AI Enhance (E)"
      >
        <IconWand />
        <span>Enhance</span>
      </button>

      {/* ── Divider ── */}
      <div className={divider} />

      {/* ── Edit group ── */}

      <button
        onClick={onMirror}
        disabled={!canEnhance}
        className={`${btnBase} ${state === "mirroring" ? "animate-pulse" : ""}`}
        aria-label="Mirror image"
        title="Mirror (M)"
      >
        <IconFlipHorizontal />
        <span>Mirror</span>
      </button>

      <button
        onClick={onCrop}
        disabled={isProcessing}
        className={`${btnBase} ${cropMode ? btnActive : ""}`}
        aria-label="Toggle crop mode"
        title="Crop (C)"
      >
        <IconCrop />
        <span>Crop</span>
      </button>

      {/* Watermark */}
      <div className="relative" ref={wmPanelRef}>
        <button
          onClick={() => setShowWatermarkPanel(!showWatermarkPanel)}
          disabled={isProcessing}
          className={`${btnBase} ${showWatermarkPanel ? btnActive : ""} ${state === "watermarking" ? "animate-pulse" : ""}`}
          title="Add watermark (W)"
        >
          <IconWatermark />
          <span>Watermark</span>
          <IconChevronDown />
        </button>

        {showWatermarkPanel && !isProcessing && (
          <div className="absolute top-full left-0 mt-2 w-72 bg-surface-tertiary border border-strong rounded-xl shadow-2xl z-50 p-3">
            <p className="text-xs text-th-secondary mb-2 px-1">Add text watermark</p>

            {/* Text input */}
            <input
              type="text"
              value={wmText}
              onChange={(e) => setWmText(e.target.value)}
              placeholder="Watermark text..."
              className="w-full px-3 py-1.5 bg-surface-secondary border border-strong rounded-lg text-sm text-th-primary focus:outline-none focus:border-purple-500 mb-2"
              autoFocus
            />

            {/* Position */}
            <div className="mb-2">
              <label className="text-[10px] text-th-tertiary uppercase tracking-wider">Position</label>
              <div className="grid grid-cols-3 gap-1 mt-1">
                {[
                  { v: "top-left", l: "TL" },
                  { v: "top-center", l: "TC" },
                  { v: "top-right", l: "TR" },
                  { v: "center", l: "C" },
                  { v: "bottom-left", l: "BL" },
                  { v: "bottom-center", l: "BC" },
                  { v: "bottom-right", l: "BR" },
                ].map((p) => (
                  <button
                    key={p.v}
                    onClick={() => { setWmPosition(p.v); setWmRepeat(false); }}
                    className={`px-2 py-1 text-[10px] rounded ${
                      wmPosition === p.v && !wmRepeat
                        ? "bg-purple-600 text-white"
                        : "bg-surface-secondary text-th-secondary hover:text-th-primary"
                    }`}
                  >
                    {p.l}
                  </button>
                ))}
                <button
                  onClick={() => setWmRepeat(!wmRepeat)}
                  className={`px-2 py-1 text-[10px] rounded col-span-2 ${
                    wmRepeat
                      ? "bg-purple-600 text-white"
                      : "bg-surface-secondary text-th-secondary hover:text-th-primary"
                  }`}
                >
                  Tiled
                </button>
              </div>
            </div>

            {/* Opacity slider */}
            <div className="mb-2">
              <div className="flex justify-between">
                <label className="text-[10px] text-th-tertiary uppercase tracking-wider">Opacity</label>
                <span className="text-[10px] text-th-secondary">{Math.round(wmOpacity * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="1"
                step="0.05"
                value={wmOpacity}
                onChange={(e) => setWmOpacity(parseFloat(e.target.value))}
                className="w-full h-1 mt-1 accent-purple-500"
              />
            </div>

            {/* Font size slider */}
            <div className="mb-2">
              <div className="flex justify-between">
                <label className="text-[10px] text-th-tertiary uppercase tracking-wider">Size</label>
                <span className="text-[10px] text-th-secondary">{wmFontSize}px</span>
              </div>
              <input
                type="range"
                min="12"
                max="120"
                step="2"
                value={wmFontSize}
                onChange={(e) => setWmFontSize(parseInt(e.target.value))}
                className="w-full h-1 mt-1 accent-purple-500"
              />
            </div>

            {/* Color */}
            <div className="flex items-center gap-2 mb-3">
              <label className="text-[10px] text-th-tertiary uppercase tracking-wider">Color</label>
              <div className="flex gap-1">
                {["#FFFFFF", "#000000", "#FF0000", "#CCCCCC"].map((c) => (
                  <button
                    key={c}
                    onClick={() => setWmColor(c)}
                    className={`w-5 h-5 rounded-full border-2 ${
                      wmColor === c ? "border-purple-500" : "border-strong"
                    }`}
                    style={{ backgroundColor: c }}
                  />
                ))}
                <input
                  type="color"
                  value={wmColor}
                  onChange={(e) => setWmColor(e.target.value)}
                  className="w-5 h-5 rounded cursor-pointer border-0 p-0"
                />
              </div>
            </div>

            {/* Apply button */}
            <button
              onClick={() => {
                if (wmText.trim()) {
                  setShowWatermarkPanel(false);
                  onWatermark({
                    text: wmText.trim(),
                    position: wmRepeat ? undefined : wmPosition,
                    opacity: wmOpacity,
                    fontSize: wmFontSize,
                    color: wmColor,
                    repeat: wmRepeat,
                  });
                }
              }}
              disabled={!wmText.trim()}
              className="w-full px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-500 disabled:opacity-40 text-sm font-medium"
            >
              Apply Watermark
            </button>
          </div>
        )}
      </div>

      {/* ── Divider ── */}
      <div className={divider} />

      <button
        onClick={onUpload}
        disabled={!canUpload}
        className={`${btnUpload} ${state === "uploading" ? "animate-pulse" : ""}`}
        aria-label="Save processed image"
        title="Save to storage"
      >
        <IconUpload />
        <span>Save</span>
      </button>

      {/* ── Divider ── */}
      <div className={divider} />

      {/* ── History group ── */}

      {canUndo && (
        <button
          onClick={onUndo}
          disabled={isProcessing}
          className={btnBase}
          aria-label="Undo last action"
          title="Undo (Cmd+Z)"
        >
          <IconUndo />
          <span>Undo</span>
        </button>
      )}

      <button
        onClick={onReset}
        disabled={state === "original" || isProcessing}
        className={btnBase}
        aria-label="Reset to original"
        title="Reset"
      >
        <IconRotateCcw />
        <span>Reset</span>
      </button>
    </div>
  );
}
