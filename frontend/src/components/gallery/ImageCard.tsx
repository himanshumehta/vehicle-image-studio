"use client";
import { memo, useState, useCallback } from "react";
import Link from "next/link";
import { deleteImage } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface ImageCardProps {
  imageKey: string;
  url: string;
  size?: number;
  hasNobg?: boolean;
  onDeleted?: () => void;
}

export const ImageCard = memo(function ImageCard({ imageKey, url, size, hasNobg, onDeleted }: ImageCardProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const filename = imageKey.split("/").pop() || imageKey;

  const handleDelete = useCallback(async () => {
    setShowConfirm(false);
    await deleteImage(imageKey);
    onDeleted?.();
  }, [imageKey, onDeleted]);

  return (
    <>
      <Link
        href={`/edit/${encodeURIComponent(imageKey)}`}
        className="group block rounded-xl border border-theme bg-surface-secondary overflow-hidden hover:border-strong transition-colors relative"
      >
        <div className="aspect-[4/3] relative bg-surface-tertiary overflow-hidden">
          <img
            src={url}
            alt={filename}
            className="absolute inset-0 w-full h-full object-contain group-hover:scale-105 transition-transform duration-300"
          />
          {/* NoBG badge */}
          {hasNobg !== undefined && (
            <span
              className={`absolute top-2 left-2 px-1.5 py-0.5 text-[10px] font-medium rounded ${
                hasNobg
                  ? "bg-green-900/70 text-green-400"
                  : "bg-amber-900/70 text-amber-400"
              }`}
            >
              {hasNobg ? "NB \u2713" : "No NB"}
            </span>
          )}
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowConfirm(true);
            }}
            className="absolute top-2 right-2 w-7 h-7 bg-red-600 hover:bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-white text-xs font-bold"
            title="Delete image"
            aria-label={`Delete ${filename}`}
          >
            ✕
          </button>
        </div>
        <div className="p-3 flex items-center justify-between">
          <p className="text-sm text-th-primary truncate" title={filename}>
            {filename}
          </p>
          {size != null && (
            <span className="text-xs text-th-tertiary ml-2 shrink-0">{formatFileSize(size)}</span>
          )}
        </div>
      </Link>
      <ConfirmDialog
        open={showConfirm}
        title="Delete Image"
        message={`Are you sure you want to delete "${filename}"? This cannot be undone.`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
});
