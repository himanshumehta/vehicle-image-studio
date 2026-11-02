"use client";

interface ZoomControlsProps {
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFit?: () => void;
  label?: string;
}

export function ZoomControls({ zoom, onZoomIn, onZoomOut, onReset, onFit, label }: ZoomControlsProps) {
  const percent = Math.round(zoom * 100);

  return (
    <div className="flex items-center gap-2 bg-surface-secondary border border-strong rounded-lg px-2 py-1">
      {label && (
        <span className="text-xs text-th-tertiary uppercase tracking-wide pl-1">{label}</span>
      )}
      <button
        onClick={onZoomOut}
        className="w-8 h-8 flex items-center justify-center text-th-secondary hover:text-th-primary transition-colors"
        title={label ? `${label} down` : "Zoom out"}
        aria-label={label ? `Decrease ${label.toLowerCase()}` : "Zoom out"}
      >
        -
      </button>
      <button
        onClick={onReset}
        className="text-sm text-th-primary min-w-[3.5rem] text-center hover:text-th-primary transition-colors"
        title={label ? `Reset ${label.toLowerCase()}` : "Reset zoom"}
        aria-label={label ? `Reset ${label.toLowerCase()}` : "Reset zoom"}
      >
        {percent}%
      </button>
      <button
        onClick={onZoomIn}
        className="w-8 h-8 flex items-center justify-center text-th-secondary hover:text-th-primary transition-colors"
        title={label ? `${label} up` : "Zoom in"}
        aria-label={label ? `Increase ${label.toLowerCase()}` : "Zoom in"}
      >
        +
      </button>
      {onFit && (
        <button
          onClick={onFit}
          className="px-2 h-8 flex items-center justify-center text-th-secondary hover:text-th-primary transition-colors text-xs border-l border-strong"
          title="Fit to view (F)"
          aria-label="Fit to view"
        >
          Fit
        </button>
      )}
    </div>
  );
}
