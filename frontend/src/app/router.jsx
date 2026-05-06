import { lazy } from "react";
import { PROTECTED_ROUTES } from "./constants.js";
import { AuthRequired, PageShell } from "./layout.jsx";
import { subdomainUsername } from "./paths.js";

const ROUTE_COMPONENTS = {
  landing: lazy(() => import("../routes/landing.jsx")),
  category: lazy(() => import("../routes/category.jsx")),
  clubs: lazy(() => import("../routes/clubs.jsx")),
  club: lazy(() => import("../routes/clubs.jsx")),
  blog: lazy(() => import("../routes/profile.jsx")),
  allWorks: lazy(() => import("../routes/profile.jsx")),
  publicInventory: lazy(() => import("../routes/economy.jsx")),
  post: lazy(() => import("../routes/post.jsx")),
  series: lazy(() => import("../routes/series.jsx")),
  dashboard: lazy(() => import("../routes/dashboard.jsx")),
  profileSettings: lazy(() => import("../routes/profile-settings.jsx")),
  admin: lazy(() => import("../routes/admin.jsx")),
  create: lazy(() => import("../routes/create.jsx")),
  messages: lazy(() => import("../routes/messages.jsx")),
  forum: lazy(() => import("../routes/forum.jsx")),
  forumCreate: lazy(() => import("../routes/forum.jsx")),
  forumThread: lazy(() => import("../routes/forum.jsx")),
  shop: lazy(() => import("../routes/economy.jsx")),
  inventory: lazy(() => import("../routes/economy.jsx")),
  premium: lazy(() => import("../routes/premium.jsx")),
  privacy: lazy(() => import("../routes/legal.jsx")),
  terms: lazy(() => import("../routes/legal.jsx")),
  authSetup: lazy(() => import("../routes/auth.jsx")),
  authCallback: lazy(() => import("../routes/auth.jsx")),
  notFound: lazy(() => import("../routes/not-found.jsx"))
};

export function routeForLocation() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const userFromHost = subdomainUsername();

  if (userFromHost) {
    if (path === "/") return { name: "blog", username: userFromHost };
    if (path === "/toate-operele") return { name: "allWorks", username: userFromHost };
    if (path === "/inventar") return { name: "publicInventory", username: userFromHost };
    if (path === "/panou") return { name: "dashboard" };
    if (path === "/profil") return { name: "profileSettings" };
    if (path === "/scrie") return { name: "create" };
    if (path === "/mesaje") return { name: "messages" };
    return { name: "post", username: userFromHost, slug: decodeURIComponent(path.slice(1)) };
  }

  if (path === "/") return { name: "landing" };
  if (path === "/panou") return { name: "dashboard" };
  if (path === "/profil") return { name: "profileSettings" };
  if (path === "/scrie") return { name: "create" };
  if (path === "/mesaje") return { name: "messages" };
  if (path === "/moderare") return { name: "admin" };
  if (path.startsWith("/categorie/")) return { name: "category", categoryKey: decodeURIComponent(path.split("/")[2] || "poezie") };
  if (path.startsWith("/serii/")) return { name: "series", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/cluburi") return { name: "clubs" };
  if (path.startsWith("/cluburi/")) return { name: "club", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/discutii") return { name: "forum" };
  if (path === "/discutii/nou") return { name: "forumCreate" };
  if (path.startsWith("/discutii/")) return { name: "forumThread", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/magazin") return { name: "shop" };
  if (path === "/inventar") return { name: "inventory" };
  if (path === "/premium") return { name: "premium" };
  if (path === "/confidentialitate") return { name: "privacy" };
  if (path === "/termeni") return { name: "terms" };
  if (path === "/autentificare/configurare") return { name: "authSetup" };
  if (path === "/autentificare/raspuns") return { name: "authCallback" };
  return { name: "notFound" };
}

export function RouteView({ route, user, authLoaded, onUserUpdate }) {
  if (PROTECTED_ROUTES.has(route.name) && !authLoaded) {
    return <PageShell kicker="cont" title="Se verifică sesiunea" sub="Încărcăm starea contului tău." />;
  }

  if (PROTECTED_ROUTES.has(route.name) && authLoaded && !user) return <AuthRequired />;

  const Component = ROUTE_COMPONENTS[route.name] || ROUTE_COMPONENTS.notFound;
  return <Component route={route} user={user} onUserUpdate={onUserUpdate} />;
}
