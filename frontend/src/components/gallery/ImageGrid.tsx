"use client";
import { useState, useMemo } from "react";
import { useImages } from "@/hooks/useImages";
import { ImageCard } from "./ImageCard";

type SortKey = "name" | "date" | "size";

interface ImageGridProps {
  prefix?: string;
  continuationToken?: string;
  onNextToken?: (token: string) => void;
  pageIndex?: number;
  onPrevPage?: () => void;
  goToInput?: string;
  onGoToInputChange?: (value: string) => void;
  onGoToPage?: () => void;
  isSkipping?: boolean;
}

export function ImageGrid({
  prefix,
  continuationToken,
  onNextToken,
  pageIndex = 0,
  onPrevPage,
  goToInput = "",
  onGoToInputChange,
  onGoToPage,
  isSkipping = false,
}: ImageGridProps) {
  const { images, nextToken, isLoading, error, refresh } = useImages(prefix, 50, continuationToken);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("date");

  const filtered = useMemo(() => {
    let list = images;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((img) => img.key.toLowerCase().includes(q));
    }
    return [...list].sort((a, b) => {
      if (sortBy === "name") return a.key.localeCompare(b.key);
      if (sortBy === "size") return b.size - a.size;
      return new Date(b.last_modified).getTime() - new Date(a.last_modified).getTime();
    });
  }, [images, search, sortBy]);

  if (isLoading || isSkipping) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-strong border-t-th-primary" />
          {isSkipping && <span className="text-sm text-th-secondary">Jumping to page...</span>}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-4">Failed to load images</p>
        <button
          onClick={() => refresh()}
          className="px-4 py-2 bg-interactive rounded-lg hover:bg-interactive-hover transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-20 text-th-tertiary">
        No images found
      </div>
    );
  }

  const currentPage = pageIndex + 1;
  const hasNext = !!nextToken;
  const hasPrev = pageIndex > 0;

  return (
    <>
      {/* Search and Sort controls */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search images..."
          className="flex-1 max-w-xs px-3 py-2 bg-surface-secondary border border-strong rounded-lg text-sm text-th-primary placeholder:text-th-tertiary focus:outline-none focus:border-input-focus"
          aria-label="Search images"
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortKey)}
          className="px-3 py-2 bg-surface-secondary border border-strong rounded-lg text-sm text-th-primary focus:outline-none focus:border-input-focus"
          aria-label="Sort images by"
        >
          <option value="date">Sort: Date</option>
          <option value="name">Sort: Name</option>
          <option value="size">Sort: Size</option>
        </select>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {filtered.map((img) => (
          <ImageCard
            key={img.key}
            imageKey={img.key}
            url={img.url || ""}
            size={img.size}
            hasNobg={(img as Record<string, unknown>).has_nobg as boolean | undefined}
            onDeleted={() => refresh()}
          />
        ))}
      </div>

      {search && filtered.length === 0 && (
        <div className="text-center py-8 text-th-tertiary text-sm">
          No images match &ldquo;{search}&rdquo;
        </div>
      )}

      {/* Pagination bar */}
      <div className="flex items-center justify-center gap-3 mt-8">
        {hasPrev && (
          <button
            onClick={onPrevPage}
            className="px-4 py-2 bg-interactive text-th-primary rounded-lg hover:bg-interactive-hover transition-colors text-sm font-medium"
          >
            Previous
          </button>
        )}

        <span className="text-sm text-th-secondary min-w-[4rem] text-center">
          Page {currentPage}
        </span>

        {hasNext && onNextToken && (
          <button
            onClick={() => onNextToken(nextToken)}
            className="px-4 py-2 bg-interactive text-th-primary rounded-lg hover:bg-interactive-hover transition-colors text-sm font-medium"
          >
            Next
          </button>
        )}

        {onGoToPage && (
          <>
            <div className="w-px h-6 bg-surface-elevated mx-1" />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                onGoToPage();
              }}
              className="flex items-center gap-2"
            >
              <label className="text-sm text-th-tertiary">Go to</label>
              <input
                type="number"
                min={1}
                value={goToInput}
                onChange={(e) => onGoToInputChange?.(e.target.value)}
                placeholder="#"
                className="w-16 px-2 py-1.5 bg-surface-secondary border border-strong rounded-lg text-sm text-th-primary text-center focus:outline-none focus:border-input-focus transition-colors [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              />
              <button
                type="submit"
                disabled={!goToInput}
                className="px-3 py-1.5 bg-interactive text-th-primary rounded-lg hover:bg-interactive-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
              >
                Go
              </button>
            </form>
          </>
        )}
      </div>
    </>
  );
}
