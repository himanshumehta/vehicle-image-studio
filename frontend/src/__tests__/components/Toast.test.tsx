import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Toast } from "@/components/ui/Toast";

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders success toast", () => {
    render(<Toast id="1" message="Success!" type="success" onDismiss={() => {}} />);
    expect(screen.getByText("Success!")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("renders error toast", () => {
    render(<Toast id="1" message="Error!" type="error" onDismiss={() => {}} />);
    expect(screen.getByText("Error!")).toBeInTheDocument();
  });

  it("renders info toast", () => {
    render(<Toast id="1" message="Info!" type="info" onDismiss={() => {}} />);
    expect(screen.getByText("Info!")).toBeInTheDocument();
  });

  it("auto-dismisses after 4 seconds", () => {
    const onDismiss = vi.fn();
    render(<Toast id="test-1" message="Auto" type="info" onDismiss={onDismiss} />);
    expect(onDismiss).not.toHaveBeenCalled();
    vi.advanceTimersByTime(4000);
    expect(onDismiss).toHaveBeenCalledWith("test-1");
  });

  it("has aria-live attribute", () => {
    render(<Toast id="1" message="A11y" type="info" onDismiss={() => {}} />);
    expect(screen.getByRole("alert")).toHaveAttribute("aria-live", "assertive");
  });
});
