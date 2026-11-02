import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ImageCard } from "@/components/gallery/ImageCard";

vi.mock("@/lib/api", () => ({
  deleteImage: vi.fn().mockResolvedValue({ deleted: "test" }),
}));

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ children, href }: any) => <a href={href}>{children}</a>,
}));

describe("ImageCard", () => {
  it("renders filename and image", () => {
    render(<ImageCard imageKey="vehicles/test.png" url="https://example.com/test.png" />);
    expect(screen.getByText("test.png")).toBeInTheDocument();
    expect(screen.getByAltText("test.png")).toBeInTheDocument();
  });

  it("displays file size when provided", () => {
    render(<ImageCard imageKey="test.png" url="https://example.com/test.png" size={1536000} />);
    expect(screen.getByText("1.5 MB")).toBeInTheDocument();
  });

  it("shows confirm dialog before delete", async () => {
    render(<ImageCard imageKey="test.png" url="https://example.com/test.png" />);
    const deleteBtn = screen.getByTitle("Delete image");
    await userEvent.click(deleteBtn);
    expect(screen.getByText("Delete Image")).toBeInTheDocument();
  });

  it("calls onDeleted after confirming delete", async () => {
    const onDeleted = vi.fn();
    render(<ImageCard imageKey="test.png" url="https://example.com/test.png" onDeleted={onDeleted} />);

    await userEvent.click(screen.getByTitle("Delete image"));
    await userEvent.click(screen.getByText("Delete"));

    expect(onDeleted).toHaveBeenCalled();
  });
});
