import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useZoom } from "@/hooks/useZoom";

describe("useZoom", () => {
  it("initializes with default zoom of 1", () => {
    const { result } = renderHook(() => useZoom());
    expect(result.current.zoom).toBe(1);
  });

  it("initializes with custom zoom", () => {
    const { result } = renderHook(() => useZoom(2));
    expect(result.current.zoom).toBe(2);
  });

  it("zooms in by 0.25 step", () => {
    const { result } = renderHook(() => useZoom());
    act(() => result.current.zoomIn());
    expect(result.current.zoom).toBe(1.25);
  });

  it("zooms out by 0.25 step", () => {
    const { result } = renderHook(() => useZoom());
    act(() => result.current.zoomOut());
    expect(result.current.zoom).toBe(0.75);
  });

  it("resets zoom to 1", () => {
    const { result } = renderHook(() => useZoom(2));
    act(() => result.current.resetZoom());
    expect(result.current.zoom).toBe(1);
  });

  it("clamps zoom at max (4)", () => {
    const { result } = renderHook(() => useZoom(4));
    act(() => result.current.zoomIn());
    expect(result.current.zoom).toBe(4);
  });

  it("clamps zoom at min (0.25)", () => {
    const { result } = renderHook(() => useZoom(0.25));
    act(() => result.current.zoomOut());
    expect(result.current.zoom).toBe(0.25);
  });

  it("zoomToFit calculates correct zoom for landscape image", () => {
    const { result } = renderHook(() => useZoom());
    act(() => result.current.zoomToFit(800, 600, 1600, 900));
    // (800 - 64) / 1600 = 0.46, (600 - 64) / 900 = 0.595 => min = 0.46
    expect(result.current.zoom).toBeCloseTo(0.46, 1);
  });

  it("zoomToFit calculates correct zoom for portrait image", () => {
    const { result } = renderHook(() => useZoom());
    act(() => result.current.zoomToFit(800, 600, 400, 800));
    // (800-64)/400=1.84, (600-64)/800=0.67 => min = 0.67
    expect(result.current.zoom).toBeCloseTo(0.67, 1);
  });

  it("handles wheel event with deltaY > 0 (zoom out)", () => {
    const { result } = renderHook(() => useZoom());
    act(() => {
      result.current.onWheel({
        deltaY: 100,
        preventDefault: () => {},
      } as any);
    });
    expect(result.current.zoom).toBe(0.75);
  });

  it("handles wheel event with deltaY < 0 (zoom in)", () => {
    const { result } = renderHook(() => useZoom());
    act(() => {
      result.current.onWheel({
        deltaY: -100,
        preventDefault: () => {},
      } as any);
    });
    expect(result.current.zoom).toBe(1.25);
  });
});
