import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ZoomControls } from "@/components/editor/ZoomControls";

describe("ZoomControls", () => {
  it("displays zoom percentage", () => {
    render(
      <ZoomControls zoom={1.5} onZoomIn={() => {}} onZoomOut={() => {}} onReset={() => {}} />
    );
    expect(screen.getByText("150%")).toBeInTheDocument();
  });

  it("calls onZoomIn when + clicked", async () => {
    const onZoomIn = vi.fn();
    render(
      <ZoomControls zoom={1} onZoomIn={onZoomIn} onZoomOut={() => {}} onReset={() => {}} />
    );
    await userEvent.click(screen.getByLabelText("Zoom in"));
    expect(onZoomIn).toHaveBeenCalledOnce();
  });

  it("calls onZoomOut when - clicked", async () => {
    const onZoomOut = vi.fn();
    render(
      <ZoomControls zoom={1} onZoomIn={() => {}} onZoomOut={onZoomOut} onReset={() => {}} />
    );
    await userEvent.click(screen.getByLabelText("Zoom out"));
    expect(onZoomOut).toHaveBeenCalledOnce();
  });

  it("calls onReset when percentage clicked", async () => {
    const onReset = vi.fn();
    render(
      <ZoomControls zoom={1} onZoomIn={() => {}} onZoomOut={() => {}} onReset={onReset} />
    );
    await userEvent.click(screen.getByLabelText("Reset zoom"));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("shows custom label", () => {
    render(
      <ZoomControls zoom={1} onZoomIn={() => {}} onZoomOut={() => {}} onReset={() => {}} label="Scale" />
    );
    expect(screen.getByText("Scale")).toBeInTheDocument();
  });

  it("has correct aria labels with custom label", () => {
    render(
      <ZoomControls zoom={1} onZoomIn={() => {}} onZoomOut={() => {}} onReset={() => {}} label="Scale" />
    );
    expect(screen.getByLabelText("Decrease scale")).toBeInTheDocument();
    expect(screen.getByLabelText("Increase scale")).toBeInTheDocument();
  });
});
