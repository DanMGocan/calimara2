import { useQuery } from "@tanstack/react-query";
import { fetchCurrentUser, type CurrentUser } from "@/api/auth";

export function useAuth() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: fetchCurrentUser,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  return {
    user: data?.user ?? null,
    isAuthenticated: data?.authenticated ?? false,
    isLoading,
    error,
    refetch,
  };
}

export type { CurrentUser };
