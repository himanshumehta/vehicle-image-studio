"use client";
import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ImageGrid } from "@/components/gallery/ImageGrid";
import { BrandGrid } from "@/components/gallery/BrandGrid";
import { fetchPageTokens, importImage } from "@/lib/api";

function GalleryPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const brand = searchParams.get("brand");
  const initialPage = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
  const [tokenHistory, setTokenHistory] = useState<string[]>([""]);
  const [pageIndex, setPageIndex] = useState(0);
  const [goToInput, setGoToInput] = useState("");
  // A deep link (?page=N) starts by walking the pagination tokens up to page N.
  const [isSkipping, setIsSkipping] = useState(() => Boolean(brand) && initialPage > 1);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deepLinkHandled = useRef(false);

  const prefix = brand ? `vehicles/${brand}/` : "";
  const currentToken = tokenHistory[pageIndex];

  const syncUrl = useCallback(
    (page: number) => {
      const params = new URLSearchParams(searchParams.toString());
      if (page <= 1) {
        params.delete("page");
      } else {
        params.set("page", String(page));
      }
      const qs = params.toString();
      router.replace(`/gallery${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [router, searchParams]
  );

  // On mount, jump to the page from the URL if needed.
  useEffect(() => {
    if (!brand || deepLinkHandled.current || initialPage <= 1) return;
    deepLinkHandled.current = true;
    const targetIndex = initialPage - 1;
    fetchPageTokens(prefix, 50, "", targetIndex)
      .then((newTokens) => {
        if (newTokens.length === 0) return;
        const updatedHistory = ["", ...newTokens];
        setTokenHistory(updatedHistory);
        setPageIndex(Math.min(targetIndex, updatedHistory.length - 1));
      })
      .finally(() => setIsSkipping(false));
  }, [initialPage, prefix, brand]);

  const handleNextPage = (nextToken: string) => {
    const newHistory = tokenHistory.slice(0, pageIndex + 1);
    newHistory.push(nextToken);
    setTokenHistory(newHistory);
    const newIndex = pageIndex + 1;
    setPageIndex(newIndex);
    syncUrl(newIndex + 1);
  };

  const handlePrevPage = () => {
    if (pageIndex > 0) {
      const newIndex = pageIndex - 1;
      setPageIndex(newIndex);
      syncUrl(newIndex + 1);
    }
  };

  const handleGoToPage = async () => {
    const target = parseInt(goToInput, 10);
    if (isNaN(target) || target < 1) return;

    const targetIndex = target - 1;

    if (targetIndex < tokenHistory.length) {
      setPageIndex(targetIndex);
      setGoToInput("");
      syncUrl(target);
      return;
    }

    setIsSkipping(true);
    try {
      const lastKnownIndex = tokenHistory.length - 1;
      const pagesNeeded = targetIndex - lastKnownIndex;
      const lastToken = tokenHistory[lastKnownIndex];
      const newTokens = await fetchPageTokens(prefix, 50, lastToken, pagesNeeded);

      if (newTokens.length === 0) {
        setIsSkipping(false);
        return;
      }

      const updatedHistory = [...tokenHistory, ...newTokens];
      setTokenHistory(updatedHistory);
      const finalIndex = Math.min(targetIndex, updatedHistory.length - 1);
      setPageIndex(finalIndex);
      setGoToInput("");
      syncUrl(finalIndex + 1);
    } finally {
      setIsSkipping(false);
    }
  };

  const handleSelectBrand = (slug: string) => {
    router.push(`/gallery?brand=${encodeURIComponent(slug)}`);
  };

  const brandDisplayName = brand
    ? brand.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "";

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Vehicle Image Studio</h1>
          <p className="text-th-secondary mt-1">
            {brand
              ? "Open an image to remove its background, upscale it or clean up plates and watermarks"
              : "Pick a collection, or import a vehicle photo"}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="px-4 py-2 bg-surface-secondary border border-strong rounded-lg text-sm text-th-primary hover:border-input-focus transition-colors disabled:opacity-50"
          >
            {importing ? "Importing..." : "Import image"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              setImporting(true);
              setImportError(null);
              try {
                const res = await importImage(file, brand || "uploads");
                router.push(`/edit/${encodeURIComponent(res.key)}`);
              } catch (err) {
                setImportError(err instanceof Error ? err.message : "Import failed");
              } finally {
                setImporting(false);
              }
            }}
          />
          {importError && <span className="text-xs text-red-400">{importError}</span>}
        </div>
      </header>

      {brand ? (
        <>
          <nav className="flex items-center gap-2 mb-6 text-sm">
            <button
              onClick={() => router.push("/gallery")}
              className="text-th-secondary hover:text-th-primary transition-colors"
            >
              All collections
            </button>
            <span className="text-th-muted">/</span>
            <span className="text-th-primary font-medium">{brandDisplayName}</span>
          </nav>

          <ImageGrid
            prefix={prefix}
            continuationToken={currentToken}
            onNextToken={handleNextPage}
            pageIndex={pageIndex}
            onPrevPage={handlePrevPage}
            goToInput={goToInput}
            onGoToInputChange={setGoToInput}
            onGoToPage={handleGoToPage}
            isSkipping={isSkipping}
          />
        </>
      ) : (
        <BrandGrid onSelectBrand={handleSelectBrand} />
      )}
    </div>
  );
}

/** Keyed by collection, so switching collections starts with fresh pagination state. */
function GalleryForCollection() {
  const brand = useSearchParams().get("brand") ?? "";
  return <GalleryPageInner key={brand} />;
}

export default function GalleryPage() {
  return (
    <Suspense>
      <GalleryForCollection />
    </Suspense>
  );
}
