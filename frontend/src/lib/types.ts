export interface StoredImage {
  key: string;
  size: number;
  last_modified: string;
  url?: string;
  has_nobg?: boolean;
}

export interface ImageMetadata extends StoredImage {
  content_type: string;
  url: string;
}

export interface ImagesResponse {
  images: StoredImage[];
  count: number;
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
