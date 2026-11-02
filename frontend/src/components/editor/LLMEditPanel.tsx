"use client";
import { useState, useEffect, useCallback, useRef } from "react";

/** One-click clean-up presets; prompts live in the backend (CLEANUP_PRESETS). */
const CLEANUP_PRESETS = [
  { id: "remove_plate", label: "Remove number plate" },
  { id: "remove_watermark", label: "Remove watermark" },
  { id: "remove_plate_and_watermark", label: "Plate + watermark" },
] as const;

const QUICK_PROMPTS = [
  "Clean up background distractions",
  "Replace background with clean studio backdrop",
  "Enhance lighting and contrast",
  "Remove unwanted shadows on the ground",
  "Sharpen vehicle details and chrome reflections",
  "Color correct for accurate paint representation",
  "Remove scratches and blemishes from the vehicle",
  "Add subtle ambient lighting around the vehicle",
] as const;

const HISTORY_KEY = "vehicle-image-studio:llm-edit-history";
const MAX_HISTORY = 20;

interface LLMEditPanelProps {
  onSubmit: (instruction: { prompt?: string; preset?: string }, provider?: string, quality?: string) => void;
  isProcessing: boolean;
  onClose: () => void;
  providers: Array<{ name: string; available: boolean }>;
}

export function LLMEditPanel({
  onSubmit,
  isProcessing,
  onClose,
  providers,
}: LLMEditPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState(
    providers.find((p) => p.available)?.name || "openai"
  );
  const [quality, setQuality] = useState<"low" | "medium" | "high">("medium");
  const [history, setHistory] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(HISTORY_KEY);
      return stored ? (JSON.parse(stored) as string[]) : [];
    } catch {
      return [];
    }
  });
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const saveToHistory = useCallback((p: string) => {
    setHistory((prev) => {
      const updated = [p, ...prev.filter((h) => h !== p)].slice(0, MAX_HISTORY);
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
  }, []);

  const handleSubmit = useCallback(() => {
    if (!prompt.trim() || isProcessing) return;
    saveToHistory(prompt.trim());
    onSubmit({ prompt: prompt.trim() }, provider, quality);
  }, [prompt, isProcessing, provider, quality, onSubmit, saveToHistory]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSubmit();
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    },
    [handleSubmit, onClose]
  );

  const costEstimate =
    provider === "openai"
      ? quality === "low"
        ? 0.009
        : quality === "high"
          ? 0.133
          : 0.034
      : 0.039;

  return (
    <div className="border-t border-theme bg-surface-secondary/80 backdrop-blur">
      <div className="max-w-3xl mx-auto px-4 py-3">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-th-primary">AI Edit</span>
          <button
            onClick={onClose}
            className="text-th-tertiary hover:text-th-primary text-sm"
          >
            Close
          </button>
        </div>

        {/* Prompt */}
        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your edit... (e.g., 'Remove the dealer logo from the windscreen')"
          className="w-full px-3 py-2 bg-surface border border-strong rounded-lg text-sm text-th-primary placeholder:text-th-tertiary focus:outline-none focus:border-input-focus resize-none"
          rows={2}
          disabled={isProcessing}
        />

        {/* Controls row */}
        <div className="flex items-center gap-4 mt-2">
          {/* Provider */}
          {providers.length > 1 && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-th-tertiary">Provider:</span>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={isProcessing}
                className="px-2 py-1 bg-surface border border-strong rounded text-xs text-th-primary focus:outline-none"
              >
                {providers
                  .filter((p) => p.available)
                  .map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name === "openai" ? "OpenAI" : "Gemini"}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {/* Quality */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-th-tertiary">Quality:</span>
            <div className="flex gap-1">
              {(["low", "medium", "high"] as const).map((q) => (
                <button
                  key={q}
                  onClick={() => setQuality(q)}
                  disabled={isProcessing}
                  className={`px-2 py-0.5 text-xs rounded transition-colors ${
                    quality === q
                      ? "bg-blue-600 text-white"
                      : "bg-surface text-th-secondary hover:bg-interactive-hover"
                  }`}
                >
                  {q.charAt(0).toUpperCase() + q.slice(1)}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1" />

          {/* Cost estimate */}
          <span className="text-xs text-th-tertiary">
            ~${costEstimate.toFixed(3)}
          </span>

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={!prompt.trim() || isProcessing}
            className="px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium transition-colors"
          >
            {isProcessing ? "Editing..." : "Apply Edit"}
          </button>
        </div>

        {/* Clean-up presets */}
        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          <span className="text-xs text-th-tertiary">Clean up:</span>
          {CLEANUP_PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => onSubmit({ preset: p.id }, provider, quality)}
              disabled={isProcessing}
              className="px-2.5 py-1 bg-blue-600/90 text-white rounded text-xs font-medium hover:bg-blue-500 disabled:opacity-40 transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Quick prompts */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {QUICK_PROMPTS.map((qp) => (
            <button
              key={qp}
              onClick={() => setPrompt(qp)}
              disabled={isProcessing}
              className="px-2 py-0.5 bg-surface border border-strong rounded text-xs text-th-secondary hover:text-th-primary hover:bg-interactive-hover transition-colors"
            >
              {qp}
            </button>
          ))}
        </div>

        {/* Recent history */}
        {history.length > 0 && (
          <div className="mt-2 max-h-20 overflow-y-auto">
            <span className="text-xs text-th-tertiary">Recent:</span>
            {history.slice(0, 5).map((h, i) => (
              <button
                key={i}
                onClick={() => setPrompt(h)}
                disabled={isProcessing}
                className="block w-full text-left px-2 py-0.5 text-xs text-th-secondary hover:text-th-primary hover:bg-interactive truncate"
              >
                {h}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
