"use client";
import { useState, useCallback, useRef } from "react";
import {
  removeBackground,
  compositeWithTemplate,
  compositeWithCustomFile,
  uploadProcessedImage,
  enhanceImageBlob,
  enhanceImageKey,
  upscaleImageBlob,
  upscaleImageKey,
  mirrorImageBlob,
  mirrorImageKey,
  cropImageBlob,
  cropImageKey,
  llmEditImage,
  watermarkImage,
  watermarkImageKey,
} from "@/lib/api";
import type { UpscaleFactor } from "@/lib/api";
import type { ProcessingState } from "@/lib/types";

interface HistoryEntry {
  bgRemovedUrl: string | null;
  studioUrl: string | null;
  enhancedUrl: string | null;
  state: ProcessingState;
}

/**
 * Processing state machine for the editor. Every operation pushes the previous
 * result onto an undo stack; the newest result is what the canvas shows.
 * Operations run on the current result (as a blob) or, before any edit, on the
 * stored image key.
 */
export function useProcessing(imageKey: string) {
  const [state, setState] = useState<ProcessingState>("original");
  const [bgRemovedUrl, setBgRemovedUrl] = useState<string | null>(null);
  const [studioUrl, setStudioUrl] = useState<string | null>(null);
  const [enhancedUrl, setEnhancedUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historyCount, setHistoryCount] = useState(0);
  const historyRef = useRef<HistoryEntry[]>([]);
  const blobUrls = useRef(new Set<string>());

  const trackBlob = useCallback((url: string) => {
    if (url.startsWith("blob:")) blobUrls.current.add(url);
  }, []);

  const pushHistory = useCallback(() => {
    historyRef.current.push({ bgRemovedUrl, studioUrl, enhancedUrl, state });
    setHistoryCount(historyRef.current.length);
  }, [bgRemovedUrl, studioUrl, enhancedUrl, state]);

  const popHistory = useCallback(() => {
    historyRef.current.pop();
    setHistoryCount(historyRef.current.length);
  }, []);

  /** Run an operation on the current image (blob if edited, otherwise by key). */
  const runOnCurrent = useCallback(
    async (
      currentDisplayUrl: string,
      busy: ProcessingState,
      done: ProcessingState,
      byBlob: (blob: Blob) => Promise<string>,
      byKey: (key: string) => Promise<string>,
      failMessage: string,
    ) => {
      const prevState = state;
      try {
        setError(null);
        pushHistory();
        setState(busy);
        let url: string;
        if (currentDisplayUrl.startsWith("blob:")) {
          const res = await fetch(currentDisplayUrl);
          url = await byBlob(await res.blob());
        } else {
          url = await byKey(imageKey);
        }
        trackBlob(url);
        setEnhancedUrl(url);
        setState(done);
      } catch (e) {
        popHistory();
        setError(e instanceof Error ? e.message : failMessage);
        setState(prevState);
      }
    },
    [imageKey, popHistory, pushHistory, state, trackBlob],
  );

  const removeBg = useCallback(async () => {
    try {
      setError(null);
      pushHistory();
      setState("removing-bg");
      const url = await removeBackground(imageKey);
      trackBlob(url);
      setBgRemovedUrl(url);
      setState("bg-removed");
    } catch (e) {
      popHistory();
      setError(e instanceof Error ? e.message : "Background removal failed");
      setState("original");
    }
  }, [imageKey, popHistory, pushHistory, trackBlob]);

  const applyTemplate = useCallback(
    async (options: { templateId?: string; file?: File }) => {
      try {
        setError(null);
        pushHistory();
        setState("compositing");
        const resultUrl = options.file
          ? await compositeWithCustomFile(imageKey, options.file)
          : await compositeWithTemplate(imageKey, options.templateId || "studio");
        trackBlob(resultUrl);
        setStudioUrl(resultUrl);
        setState("studio-ready");
      } catch (e) {
        popHistory();
        setError(e instanceof Error ? e.message : "Background composite failed");
        setState("bg-removed");
      }
    },
    [imageKey, popHistory, pushHistory, trackBlob],
  );

  const upscale = useCallback(
    (currentDisplayUrl: string, scale: UpscaleFactor) =>
      runOnCurrent(
        currentDisplayUrl,
        "upscaling",
        "upscaled",
        (b) => upscaleImageBlob(b, scale),
        (k) => upscaleImageKey(k, scale),
        "Upscale failed",
      ),
    [runOnCurrent],
  );

  const aiEnhance = useCallback(
    (currentDisplayUrl: string) =>
      runOnCurrent(currentDisplayUrl, "enhancing", "enhanced", enhanceImageBlob, enhanceImageKey, "Enhance failed"),
    [runOnCurrent],
  );

  const mirror = useCallback(
    (currentDisplayUrl: string) =>
      runOnCurrent(currentDisplayUrl, "mirroring", "mirrored", mirrorImageBlob, mirrorImageKey, "Mirror failed"),
    [runOnCurrent],
  );

  const crop = useCallback(
    (currentDisplayUrl: string, x: number, y: number, w: number, h: number) =>
      runOnCurrent(
        currentDisplayUrl,
        "cropping",
        "cropped",
        (b) => cropImageBlob(b, x, y, w, h),
        (k) => cropImageKey(k, x, y, w, h),
        "Crop failed",
      ),
    [runOnCurrent],
  );

  const addWatermark = useCallback(
    (
      currentDisplayUrl: string,
      options: { text: string; position?: string; opacity?: number; fontSize?: number; color?: string; repeat?: boolean },
    ) =>
      runOnCurrent(
        currentDisplayUrl,
        "watermarking",
        "watermarked",
        (b) => watermarkImage(b, options),
        (k) => watermarkImageKey(k, options),
        "Watermark failed",
      ),
    [runOnCurrent],
  );

  const llmEdit = useCallback(
    async (
      currentDisplayUrl: string,
      instruction: { prompt?: string; preset?: string },
      provider?: "openai" | "gemini",
      quality?: "low" | "medium" | "high",
    ) => {
      const prevState = state;
      try {
        setError(null);
        pushHistory();
        setState("llm-editing");
        const res = await fetch(currentDisplayUrl);
        const editedBlob = await llmEditImage(await res.blob(), instruction, { provider, quality });
        const url = URL.createObjectURL(editedBlob);
        trackBlob(url);
        setEnhancedUrl(url);
        setState("llm-edited");
      } catch (e) {
        popHistory();
        setError(e instanceof Error ? e.message : "AI edit failed");
        setState(prevState);
      }
    },
    [popHistory, pushHistory, state, trackBlob],
  );

  const replaceImage = useCallback(
    async (file: File) => {
      pushHistory();
      const objectUrl = URL.createObjectURL(file);
      trackBlob(objectUrl);
      setEnhancedUrl(objectUrl);
      setState("replaced");
    },
    [pushHistory, trackBlob],
  );

  const undo = useCallback(() => {
    const entry = historyRef.current.pop();
    if (!entry) return;
    setBgRemovedUrl(entry.bgRemovedUrl);
    setStudioUrl(entry.studioUrl);
    setEnhancedUrl(entry.enhancedUrl);
    setState(entry.state);
    setError(null);
    setHistoryCount(historyRef.current.length);
  }, []);

  const upload = useCallback(
    async (uploadKey: string) => {
      const urlToUpload = enhancedUrl || studioUrl || bgRemovedUrl;
      if (!urlToUpload) return;
      const prevState = state;
      try {
        setError(null);
        setState("uploading");
        const res = await fetch(urlToUpload);
        await uploadProcessedImage(uploadKey, await res.blob());
        setState("uploaded");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Save failed");
        setState(prevState);
      }
    },
    [bgRemovedUrl, enhancedUrl, state, studioUrl],
  );

  const reset = useCallback(() => {
    blobUrls.current.forEach((url) => URL.revokeObjectURL(url));
    blobUrls.current.clear();
    setState("original");
    setBgRemovedUrl(null);
    setStudioUrl(null);
    setEnhancedUrl(null);
    setError(null);
    historyRef.current = [];
    setHistoryCount(0);
  }, []);

  return {
    state,
    bgRemovedUrl,
    studioUrl,
    enhancedUrl,
    error,
    removeBg,
    applyTemplate,
    upscale,
    aiEnhance,
    mirror,
    crop,
    upload,
    replaceImage,
    addWatermark,
    reset,
    llmEdit,
    undo,
    canUndo: historyCount > 0,
  };
}
