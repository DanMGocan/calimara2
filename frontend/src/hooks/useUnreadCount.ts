import { useQuery } from "@tanstack/react-query";
import { fetchUnreadCount } from "@/api/messages";
import { UNREAD_POLL_INTERVAL } from "@/lib/constants";

export function useUnreadCount(enabled = true) {
  const { data } = useQuery({
    queryKey: ["messages", "unread"],
    queryFn: fetchUnreadCount,
    refetchInterval: UNREAD_POLL_INTERVAL,
    enabled,
  });

  return data?.unread_count ?? 0;
}
