"use client";
import { useBrands } from "@/hooks/useBrands";

interface BrandGridProps {
  onSelectBrand: (slug: string, prefix: string) => void;
}

export function BrandGrid({ onSelectBrand }: BrandGridProps) {
  const { brands, totalBrands, totalImages, isLoading, error } = useBrands();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-strong border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-4 py-3 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-sm">
        Failed to load collections: {error.message}
      </div>
    );
  }

  if (brands.length === 0) {
    return (
      <div className="text-center py-20 text-th-tertiary">
        No collections yet. Import an image to get started.
      </div>
    );
  }

  return (
    <div>
      <p className="text-sm text-th-tertiary mb-4">
        {totalBrands} collections &middot; {totalImages.toLocaleString()} images
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {brands.map((brand) => (
          <button
            key={brand.slug}
            onClick={() => onSelectBrand(brand.slug, brand.prefix)}
            className="flex flex-col items-center gap-3 p-5 bg-surface-secondary border border-theme rounded-xl hover:border-strong hover:bg-surface-tertiary/50 transition-all group"
          >
            <div className="w-14 h-14 rounded-full bg-surface-tertiary group-hover:bg-interactive-hover flex items-center justify-center text-xl font-bold text-th-primary transition-colors">
              {brand.name.charAt(0).toUpperCase()}
            </div>
            <div className="text-center">
              <div className="text-sm font-medium text-th-primary group-hover:text-th-primary transition-colors">
                {brand.name}
              </div>
              <div className="text-xs text-th-tertiary mt-0.5">
                {brand.image_count} {brand.image_count === 1 ? "image" : "images"}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
