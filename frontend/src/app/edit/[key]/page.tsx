"use client";
import { useEffect, useState, use } from "react";
import Link from "next/link";
import { getImageMetadata, getEditProviders } from "@/lib/api";
import { useProcessing } from "@/hooks/useProcessing";
import { useZoom } from "@/hooks/useZoom";
import { EditorCanvas } from "@/components/editor/EditorCanvas";
import { BeforeAfterSlider } from "@/components/editor/BeforeAfterSlider";
import { ZoomControls } from "@/components/editor/ZoomControls";
import { EditorToolbar } from "@/components/editor/EditorToolbar";
import { ProcessingStatus } from "@/components/editor/ProcessingStatus";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { LLMEditPanel } from "@/components/editor/LLMEditPanel";
import { BUSY_STATES } from "@/lib/types";

type EditProvider = { name: string; available: boolean; models: string[] };

function defaultSaveKey(key: string): string {
  const dot = key.lastIndexOf(".");
  const base = dot > key.lastIndexOf("/") ? key.slice(0, dot) : key;
  return `${base}-edited.png`;
}

export default function EditorPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params);
  const imageKey = decodeURIComponent(key);
  const [originalUrl, setOriginalUrl] = useState<string>("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [uploadKey, setUploadKey] = useState(defaultSaveKey(imageKey));
  const [cropMode, setCropMode] = useState(false);
  const [showLLMPanel, setShowLLMPanel] = useState(false);
  const [editProviders, setEditProviders] = useState<EditProvider[]>([]);

  const { zoom, zoomIn, zoomOut, resetZoom, onWheel, setZoom } = useZoom();
  const processing = useProcessing(imageKey);

  useEffect(() => {
    getImageMetadata(imageKey)
      .then((meta) => setOriginalUrl(meta.url))
      .catch(() => setLoadError(`Could not load "${imageKey}" from storage.`));
  }, [imageKey]);

  useEffect(() => {
    getEditProviders()
      .then((data) => setEditProviders(data.providers))
      .catch(() => setEditProviders([]));
  }, []);

  const resultUrl = processing.enhancedUrl || processing.studioUrl || processing.bgRemovedUrl;
  const displayUrl = resultUrl || originalUrl;
  const canCompare = Boolean(originalUrl && resultUrl);
  const isProcessing = BUSY_STATES.has(processing.state);
  const aiEditEnabled = editProviders.some((p) => p.available);

  useKeyboardShortcuts(
    {
      "mod+z": () => processing.canUndo && processing.undo(),
      r: () => processing.state === "original" && !isProcessing && processing.removeBg(),
      u: () => !isProcessing && processing.upscale(displayUrl, 4),
      m: () => !isProcessing && processing.mirror(displayUrl),
      c: () => !isProcessing && setCropMode((m) => !m),
      e: () => !isProcessing && processing.aiEnhance(displayUrl),
      a: () => !isProcessing && aiEditEnabled && setShowLLMPanel((s) => !s),
      f: () => resetZoom(),
      space: () => {
        if (canCompare) setShowCompare((s) => !s);
      },
      escape: () => {
        if (showLLMPanel) setShowLLMPanel(false);
        else if (cropMode) setCropMode(false);
        else if (showCompare) setShowCompare(false);
      },
    },
    !isProcessing || processing.state === "original",
  );

  // Warn about unsaved changes
  useEffect(() => {
    if (processing.state === "original" || processing.state === "uploaded") return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [processing.state]);

  const collection = imageKey.split("/")[0] === "vehicles" ? imageKey.split("/")[1] : undefined;

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="flex-none flex items-center justify-between px-6 py-3 border-b border-theme bg-surface-secondary/50">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            href={collection ? `/gallery?brand=${collection}` : "/gallery"}
            className="text-th-secondary hover:text-th-primary transition-colors shrink-0"
          >
            &larr; {collection ? collection.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Gallery"}
          </Link>
          <span className="text-sm text-th-tertiary truncate" title={imageKey}>
            {imageKey}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <ProcessingStatus state={processing.state} />
          <ZoomControls zoom={zoom} onZoomIn={zoomIn} onZoomOut={zoomOut} onReset={resetZoom} onFit={resetZoom} />
        </div>
      </header>

      <div className="flex-none flex items-center justify-between px-6 py-3 border-b border-theme">
        <EditorToolbar
          state={processing.state}
          onRemoveBg={processing.removeBg}
          onReplace={processing.replaceImage}
          onApplyTemplate={processing.applyTemplate}
          onUpscale={(scale) => processing.upscale(displayUrl, scale)}
          onAiEnhance={() => processing.aiEnhance(displayUrl)}
          onMirror={() => processing.mirror(displayUrl)}
          onWatermark={(opts) => processing.addWatermark(displayUrl, opts)}
          onCrop={() => setCropMode((m) => !m)}
          cropMode={cropMode && !isProcessing}
          onUpload={() => processing.upload(uploadKey)}
          onReset={processing.reset}
          onUndo={processing.undo}
          canUndo={processing.canUndo}
        />
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowLLMPanel(!showLLMPanel)}
            disabled={isProcessing || !aiEditEnabled}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors font-medium ${
              showLLMPanel
                ? "bg-blue-600 text-white"
                : "bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-500 hover:to-indigo-500 disabled:opacity-40"
            }`}
            title={
              aiEditEnabled
                ? "Plate / watermark removal and free-form AI edits (A)"
                : "Set OPENAI_API_KEY or GEMINI_API_KEY to enable AI edits"
            }
          >
            AI Clean-up
          </button>

          {canCompare && (
            <button
              onClick={() => setShowCompare(!showCompare)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                showCompare
                  ? "bg-interactive-hover text-th-primary"
                  : "bg-interactive text-th-secondary hover:text-th-primary"
              }`}
            >
              {showCompare ? "Hide before/after" : "Before/after"}
            </button>
          )}
        </div>
      </div>

      {(processing.error || loadError) && (
        <div className="mx-6 mt-3 px-4 py-2 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-sm">
          {processing.error || loadError}
        </div>
      )}

      <div className="flex-1 overflow-hidden flex">
        <div className="flex-1 p-6 overflow-hidden">
          {showCompare && canCompare && resultUrl ? (
            <BeforeAfterSlider beforeUrl={originalUrl} afterUrl={resultUrl} />
          ) : (
            <EditorCanvas
              imageUrl={displayUrl}
              zoom={zoom}
              onZoomChange={setZoom}
              onWheel={onWheel}
              cropMode={cropMode && !isProcessing}
              onApplyCrop={(x, y, w, h) => {
                setCropMode(false);
                processing.crop(displayUrl, x, y, w, h);
              }}
              onCancelCrop={() => setCropMode(false)}
              onZoomToFit={resetZoom}
            />
          )}
        </div>
      </div>

      {showLLMPanel && (
        <LLMEditPanel
          onSubmit={(instruction, provider, quality) => {
            processing.llmEdit(
              displayUrl,
              instruction,
              provider as "openai" | "gemini" | undefined,
              quality as "low" | "medium" | "high" | undefined,
            );
          }}
          isProcessing={processing.state === "llm-editing"}
          onClose={() => setShowLLMPanel(false)}
          providers={editProviders}
        />
      )}

      {processing.state !== "original" && (
        <div className="flex-none px-6 py-3 border-t border-theme flex items-center gap-3">
          <label htmlFor="save-key" className="text-sm text-th-secondary">
            Save as:
          </label>
          <input
            id="save-key"
            type="text"
            value={uploadKey}
            onChange={(e) => setUploadKey(e.target.value)}
            className="flex-1 max-w-lg px-3 py-1.5 bg-surface-secondary border border-strong rounded-lg text-sm text-th-primary focus:outline-none focus:border-input-focus"
          />
        </div>
      )}
    </div>
  );
}
