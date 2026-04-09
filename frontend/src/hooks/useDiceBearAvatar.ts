import { useMemo } from "react";
import { getAvatarUrl } from "@/lib/utils";

export function useDiceBearAvatar(seed: string, size = 64) {
  return useMemo(() => getAvatarUrl(seed, size), [seed, size]);
}

export function generateAvatarSeeds(count = 6): string[] {
  return Array.from({ length: count }, () =>
    Math.random().toString(36).substring(2, 10),
  );
}
