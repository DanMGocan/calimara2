import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HelmetProvider } from "react-helmet-async";
import { ToastProvider } from "@/components/ui/toast";
import { Layout } from "@/components/layout/Layout";
import { ErrorBoundary } from "@/components/layout/ErrorBoundary";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useSubdomain } from "@/hooks/useSubdomain";

// Pages - lazy loaded
import { lazy, Suspense } from "react";
import { PageLoader } from "@/components/layout/LoadingSpinner";

const LandingPage = lazy(() => import("@/pages/LandingPage"));
const CategoryPage = lazy(() => import("@/pages/CategoryPage"));
const RegisterPage = lazy(() => import("@/pages/RegisterPage"));
const AuthCallbackPage = lazy(() => import("@/pages/AuthCallbackPage"));
const AuthSetupPage = lazy(() => import("@/pages/AuthSetupPage"));
const BlogHomePage = lazy(() => import("@/pages/BlogHomePage"));
const PostDetailPage = lazy(() => import("@/pages/PostDetailPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const CreatePostPage = lazy(() => import("@/pages/CreatePostPage"));
const EditPostPage = lazy(() => import("@/pages/EditPostPage"));
const MessagesPage = lazy(() => import("@/pages/MessagesPage"));
const ConversationPage = lazy(() => import("@/pages/ConversationPage"));
const ModerationPage = lazy(() => import("@/pages/ModerationPage"));
const CollectionDetailPage = lazy(() => import("@/pages/CollectionDetailPage"));
const ClubsListPage = lazy(() => import("@/pages/ClubsListPage"));
const ClubCreatePage = lazy(() => import("@/pages/ClubCreatePage"));
const ClubDetailPage = lazy(() => import("@/pages/ClubDetailPage"));
const PremiumPage = lazy(() => import("@/pages/PremiumPage"));
const PremiumSuccessPage = lazy(() => import("@/pages/PremiumSuccessPage"));
const PremiumCancelPage = lazy(() => import("@/pages/PremiumCancelPage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function AppRoutes() {
  const { isSubdomain } = useSubdomain();

  if (isSubdomain) {
    return (
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<BlogHomePage />} />
          <Route path="dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="create-post" element={<ProtectedRoute><CreatePostPage /></ProtectedRoute>} />
          <Route path="edit-post/:postId" element={<ProtectedRoute><EditPostPage /></ProtectedRoute>} />
          <Route path="messages" element={<ProtectedRoute><MessagesPage /></ProtectedRoute>} />
          <Route path="messages/:conversationId" element={<ProtectedRoute><ConversationPage /></ProtectedRoute>} />
          <Route path="colectii/:slug" element={<CollectionDetailPage />} />
          <Route path=":slug" element={<PostDetailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="category/:categoryKey" element={<CategoryPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="auth/callback" element={<AuthCallbackPage />} />
        <Route path="auth/setup" element={<AuthSetupPage />} />
        <Route path="admin/moderation" element={<ProtectedRoute requireModerator><ModerationPage /></ProtectedRoute>} />
        <Route path="cluburi" element={<ClubsListPage />} />
        <Route path="cluburi/nou" element={<ProtectedRoute><ClubCreatePage /></ProtectedRoute>} />
        <Route path="cluburi/:slug" element={<ClubDetailPage />} />
        <Route path="premium" element={<PremiumPage />} />
        <Route path="premium/success" element={<PremiumSuccessPage />} />
        <Route path="premium/cancel" element={<PremiumCancelPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <BrowserRouter>
            <ErrorBoundary>
              <Suspense fallback={<PageLoader />}>
                <AppRoutes />
              </Suspense>
            </ErrorBoundary>
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </HelmetProvider>
  );
}
