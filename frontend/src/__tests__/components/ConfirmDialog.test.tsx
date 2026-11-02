import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders nothing when closed", () => {
    render(
      <ConfirmDialog open={false} title="Test" message="msg" onConfirm={() => {}} onCancel={() => {}} />
    );
    expect(screen.queryByText("Test")).not.toBeInTheDocument();
  });

  it("renders title and message when open", () => {
    render(
      <ConfirmDialog open={true} title="Delete?" message="Are you sure?" onConfirm={() => {}} onCancel={() => {}} />
    );
    expect(screen.getByText("Delete?")).toBeInTheDocument();
    expect(screen.getByText("Are you sure?")).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open={true} title="Test" message="msg" onConfirm={onConfirm} onCancel={() => {}} />
    );
    await userEvent.click(screen.getByText("Confirm"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when cancel button clicked", async () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open={true} title="Test" message="msg" onConfirm={() => {}} onCancel={onCancel} />
    );
    await userEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("calls onCancel on Escape key", async () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open={true} title="Test" message="msg" onConfirm={() => {}} onCancel={onCancel} />
    );
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalled();
  });

  it("has correct aria attributes", () => {
    render(
      <ConfirmDialog open={true} title="Test" message="msg" onConfirm={() => {}} onCancel={() => {}} />
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "Test");
  });

  it("shows danger styling when danger prop is true", () => {
    render(
      <ConfirmDialog open={true} title="Delete Item" message="msg" danger confirmLabel="Delete" onConfirm={() => {}} onCancel={() => {}} />
    );
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("bg-red-600");
  });
});
