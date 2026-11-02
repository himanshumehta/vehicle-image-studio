import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

function fireKey(key: string, opts: Partial<KeyboardEventInit> = {}) {
  window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, ...opts }));
}

describe("useKeyboardShortcuts", () => {
  it("fires handler for matching key", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts({ r: handler }));
    fireKey("r");
    expect(handler).toHaveBeenCalledOnce();
  });

  it("fires handler for mod+key combo", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts({ "mod+z": handler }));
    fireKey("z", { metaKey: true });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("does not fire when disabled", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts({ r: handler }, false));
    fireKey("r");
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not fire when focus is on input", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts({ r: handler }));
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "r", bubbles: true }));
    expect(handler).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("handles space key", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts({ space: handler }));
    fireKey(" ");
    expect(handler).toHaveBeenCalledOnce();
  });

  it("handles escape key", () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcuts({ escape: handler }));
    fireKey("Escape");
    expect(handler).toHaveBeenCalledOnce();
  });
});
