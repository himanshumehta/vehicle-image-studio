/** One original image in storage, as returned by GET /api/images. */
export interface StoredImage {
  key: string;
  size: number;
  last_modified: string;
  url: string;
  has_nobg?: boolean;
  nobg_key?: string | null;
}

export interface ImageMetadata extends StoredImage {
  content_type: string;
  nobg_variant?: { key: string; exists: boolean; url: string | null };
}

export interface ImagesResponse {
  images: StoredImage[];
  count: number;
  next_token: string;
}

/** Response of the import and save endpoints. */
export interface SavedImage {
  key: string;
  url: string;
  size: number;
}

export type ProcessingState =
  | "original"
  | "replaced"
  | "removing-bg"
  | "bg-removed"
  | "compositing"
  | "studio-ready"
  | "upscaling"
  | "upscaled"
  | "mirroring"
  | "mirrored"
  | "enhancing"
  | "enhanced"
  | "cropping"
  | "cropped"
  | "watermarking"
  | "watermarked"
  | "llm-editing"
  | "llm-edited"
  | "uploading"
  | "uploaded";

/** States in which a request is in flight. */
export const BUSY_STATES: ReadonlySet<ProcessingState> = new Set<ProcessingState>([
  "removing-bg",
  "compositing",
  "upscaling",
  "mirroring",
  "enhancing",
  "cropping",
  "watermarking",
  "llm-editing",
  "uploading",
]);

/** A collection is a folder directly below `vehicles/` in storage. */
export interface Brand {
  slug: string;
  name: string;
  prefix: string;
  image_count: number;
}

export interface BrandsResponse {
  brands: Brand[];
  total_brands: number;
  total_images: number;
}
