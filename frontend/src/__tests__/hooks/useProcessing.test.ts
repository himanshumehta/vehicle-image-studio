import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useProcessing } from "@/hooks/useProcessing";

vi.mock("@/lib/api", () => ({
  removeBackground: vi.fn(),
  compositeWithTemplate: vi.fn(),
  compositeWithCustomFile: vi.fn(),
  uploadProcessedImage: vi.fn(),
  enhanceImageBlob: vi.fn(),
  enhanceImageKey: vi.fn(),
  upscaleImageBlob: vi.fn(),
  upscaleImageKey: vi.fn(),
  mirrorImageBlob: vi.fn(),
  mirrorImageKey: vi.fn(),
  cropImageBlob: vi.fn(),
  cropImageKey: vi.fn(),
  llmEditImage: vi.fn(),
  watermarkImage: vi.fn(),
  watermarkImageKey: vi.fn(),
}));

const api = await import("@/lib/api");

describe("useProcessing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock URL.createObjectURL
    vi.stubGlobal("URL", {
      ...globalThis.URL,
      createObjectURL: vi.fn(() => "blob:mock-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("initializes with original state", () => {
    const { result } = renderHook(() => useProcessing("test-key"));
    expect(result.current.state).toBe("original");
    expect(result.current.bgRemovedUrl).toBeNull();
    expect(result.current.canUndo).toBe(false);
  });

  it("transitions through removeBg states", async () => {
    (api.removeBackground as any).mockResolvedValue("blob:bg-removed");
    const { result } = renderHook(() => useProcessing("test-key"));

    await act(async () => {
      await result.current.removeBg();
    });

    expect(result.current.state).toBe("bg-removed");
    expect(result.current.bgRemovedUrl).toBe("blob:bg-removed");
    expect(result.current.canUndo).toBe(true);
  });

  it("rolls back state on removeBg error", async () => {
    (api.removeBackground as any).mockRejectedValue(new Error("fail"));
    const { result } = renderHook(() => useProcessing("test-key"));

    await act(async () => {
      await result.current.removeBg();
    });

    expect(result.current.state).toBe("original");
    expect(result.current.error).toBe("fail");
    expect(result.current.canUndo).toBe(false);
  });

  it("undo restores previous state", async () => {
    (api.removeBackground as any).mockResolvedValue("blob:bg-removed");
    const { result } = renderHook(() => useProcessing("test-key"));

    await act(async () => {
      await result.current.removeBg();
    });
    expect(result.current.state).toBe("bg-removed");

    act(() => {
      result.current.undo();
    });
    expect(result.current.state).toBe("original");
    expect(result.current.bgRemovedUrl).toBeNull();
  });

  it("reset clears all state", async () => {
    (api.removeBackground as any).mockResolvedValue("blob:bg-removed");
    const { result } = renderHook(() => useProcessing("test-key"));

    await act(async () => {
      await result.current.removeBg();
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.state).toBe("original");
    expect(result.current.bgRemovedUrl).toBeNull();
    expect(result.current.canUndo).toBe(false);
  });

  it("upscales the stored image by key before any edit", async () => {
    (api.upscaleImageKey as any).mockResolvedValue("blob:upscaled");
    const { result } = renderHook(() => useProcessing("vehicles/samples/a.png"));

    await act(async () => {
      await result.current.upscale("/api/files/vehicles/samples/a.png", 8);
    });

    expect(api.upscaleImageKey).toHaveBeenCalledWith("vehicles/samples/a.png", 8);
    expect(result.current.state).toBe("upscaled");
    expect(result.current.enhancedUrl).toBe("blob:upscaled");
  });
});
