import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getBlogUrl } from "@/lib/utils";

export default function AuthCallbackPage() {
  const [params] = useSearchParams();
  const status = params.get("status");
  const { user, isAuthenticated, isLoading, refetch } = useAuth();

  useEffect(() => {
    if (status === "setup") {
      window.location.href = "/auth/setup";
      return;
    }

    // Refetch auth state after OAuth callback
    refetch();
  }, [status, refetch]);

  useEffect(() => {
    if (!isLoading && isAuthenticated && user) {
      window.location.href = getBlogUrl(user.username);
    }
  }, [isLoading, isAuthenticated, user]);

  return <PageLoader />;
}
