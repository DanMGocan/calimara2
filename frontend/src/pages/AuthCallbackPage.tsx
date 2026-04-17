import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getBlogUrl } from "@/lib/utils";

export default function AuthCallbackPage() {
  const [params] = useSearchParams();
  const status = params.get("status");
  const { user, isAuthenticated, isLoading, refetch } = useAuth();
  const hasRefetchedRef = useRef(false);

  useEffect(() => {
    if (status === "setup") {
      window.location.href = "/auth/setup";
      return;
    }
    if (!hasRefetchedRef.current) {
      hasRefetchedRef.current = true;
      refetch();
      return;
    }
    if (!isLoading && isAuthenticated && user) {
      window.location.href = getBlogUrl(user.username);
    }
  }, [status, refetch, isLoading, isAuthenticated, user]);

  return <PageLoader />;
}
