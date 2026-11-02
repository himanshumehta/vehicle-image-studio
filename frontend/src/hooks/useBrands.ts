import useSWR from "swr";
import { listBrands } from "@/lib/api";

export function useBrands() {
  const { data, error, isLoading } = useSWR("brands", listBrands, {
    dedupingInterval: 60000,
  });

  return {
    brands: data?.brands ?? [],
    totalBrands: data?.total_brands ?? 0,
    totalImages: data?.total_images ?? 0,
    isLoading,
    error,
  };
}
