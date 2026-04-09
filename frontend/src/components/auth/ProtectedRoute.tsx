import { type ReactNode } from "react";
import { useAuth } from "@/hooks/useAuth";
import { PageLoader } from "@/components/layout/LoadingSpinner";

interface ProtectedRouteProps {
  children: ReactNode;
  requireAdmin?: boolean;
  requireModerator?: boolean;
}

export function ProtectedRoute({ children, requireAdmin, requireModerator }: ProtectedRouteProps) {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <PageLoader />;

  if (!isAuthenticated || !user) {
    window.location.href = "/auth/google";
    return <PageLoader />;
  }

  if (requireAdmin && !user.is_admin) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-muted">Nu aveti acces la aceasta pagina.</p>
      </div>
    );
  }

  if (requireModerator && !user.is_moderator && !user.is_admin) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-muted">Nu aveti acces la aceasta pagina.</p>
      </div>
    );
  }

  return <>{children}</>;
}
