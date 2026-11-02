import useSWR from "swr";
import { listImages } from "@/lib/api";

export function useImages(prefix = "", maxKeys = 50, continuationToken = "") {
  const { data, error, isLoading, mutate } = useSWR(
    ["images", prefix, maxKeys, continuationToken],
    () => listImages(prefix, maxKeys, continuationToken)
  );

  return {
    images: data?.images ?? [],
    count: data?.count ?? 0,
    nextToken: data?.next_token ?? "",
    isLoading,
    error,
    refresh: mutate,
  };
}
