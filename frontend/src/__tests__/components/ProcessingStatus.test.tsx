import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProcessingStatus } from "@/components/editor/ProcessingStatus";

describe("ProcessingStatus", () => {
  it("shows 'Original' for original state", () => {
    render(<ProcessingStatus state="original" />);
    expect(screen.getByText("Original")).toBeInTheDocument();
  });

  it("shows spinner during processing states", () => {
    const { container } = render(<ProcessingStatus state="removing-bg" />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("shows checkmark for uploaded state", () => {
    render(<ProcessingStatus state="uploaded" />);
    expect(screen.getByText("✓")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("has aria-live attribute", () => {
    render(<ProcessingStatus state="original" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });

  it("has aria-busy during processing", () => {
    render(<ProcessingStatus state="enhancing" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  it("has aria-busy false when not processing", () => {
    render(<ProcessingStatus state="enhanced" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "false");
  });
});
