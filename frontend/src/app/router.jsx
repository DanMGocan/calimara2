import { lazy } from "react";
import { PROTECTED_ROUTES } from "./constants.js";
import { AuthRequired, PageShell } from "./layout.jsx";
import { subdomainUsername } from "./paths.js";

const ROUTE_COMPONENTS = {
  landing: lazy(() => import("../routes/landing.jsx")),
  clubs: lazy(() => import("../routes/clubs.jsx")),
  club: lazy(() => import("../routes/clubs.jsx")),
  theatre: lazy(() => import("../routes/theatre.jsx")),
  theatreCreate: lazy(() => import("../routes/theatre.jsx")),
  theatrePlay: lazy(() => import("../routes/theatre.jsx")),
  stafeta: lazy(() => import("../routes/stafeta.jsx")),
  stafetaCreate: lazy(() => import("../routes/stafeta.jsx")),
  stafetaWork: lazy(() => import("../routes/stafeta.jsx")),
  blog: lazy(() => import("../routes/profile.jsx")),
  allWorks: lazy(() => import("../routes/profile.jsx")),
  followers: lazy(() => import("../routes/profile.jsx")),
  following: lazy(() => import("../routes/profile.jsx")),
  publicInventory: lazy(() => import("../routes/economy.jsx")),
  post: lazy(() => import("../routes/post.jsx")),
  series: lazy(() => import("../routes/series.jsx")),
  dashboard: lazy(() => import("../routes/dashboard.jsx")),
  profileSettings: lazy(() => import("../routes/profile-settings.jsx")),
  admin: lazy(() => import("../routes/admin.jsx")),
  docs: lazy(() => import("../routes/docs.jsx")),
  create: lazy(() => import("../routes/create.jsx")),
  messages: lazy(() => import("../routes/messages.jsx")),
  friends: lazy(() => import("../routes/friends.jsx")),
  usersDirectory: lazy(() => import("../routes/users-directory.jsx")),
  forum: lazy(() => import("../routes/forum.jsx")),
  forumCreate: lazy(() => import("../routes/forum.jsx")),
  forumThread: lazy(() => import("../routes/forum.jsx")),
  shop: lazy(() => import("../routes/economy.jsx")),
  inventory: lazy(() => import("../routes/economy.jsx")),
  premium: lazy(() => import("../routes/premium.jsx")),
  playlists: lazy(() => import("../routes/playlists.jsx")),
  referrals: lazy(() => import("../routes/referrals.jsx")),
  about: lazy(() => import("../routes/legal.jsx")),
  privacy: lazy(() => import("../routes/legal.jsx")),
  terms: lazy(() => import("../routes/legal.jsx")),
  authLogin: lazy(() => import("../routes/auth.jsx")),
  authSetup: lazy(() => import("../routes/auth.jsx")),
  authCallback: lazy(() => import("../routes/auth.jsx")),
  invite: lazy(() => import("../routes/auth.jsx")),
  notFound: lazy(() => import("../routes/not-found.jsx"))
};

export function routeForLocation() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const userFromHost = subdomainUsername();

  if (userFromHost) {
    if (path === "/") return { name: "blog", username: userFromHost };
    if (path === "/toate-operele") return { name: "allWorks", username: userFromHost };
    if (path === "/urmaritori") return { name: "followers", username: userFromHost };
    if (path === "/urmariti") return { name: "following", username: userFromHost };
    if (path === "/inventar") return { name: "publicInventory", username: userFromHost };
    if (path === "/panou") return { name: "dashboard" };
    if (path === "/profil") return { name: "profileSettings" };
    if (path === "/scrie") return { name: "create" };
    if (path === "/mesaje") return { name: "messages" };
    if (path === "/prieteni") return { name: "friends" };
    if (path === "/utilizatori") return { name: "usersDirectory" };
    return { name: "post", username: userFromHost, slug: decodeURIComponent(path.slice(1)) };
  }

  if (path === "/") return { name: "landing" };
  if (path === "/panou") return { name: "dashboard" };
  if (path === "/profil") return { name: "profileSettings" };
  if (path === "/scrie") return { name: "create" };
  if (path === "/mesaje") return { name: "messages" };
  if (path === "/prieteni") return { name: "friends" };
  if (path === "/utilizatori") return { name: "usersDirectory" };
  if (path === "/moderare") return { name: "admin" };
  if (path === "/docs") return { name: "docs" };
  if (path.startsWith("/serii/")) return { name: "series", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/cluburi") return { name: "clubs" };
  if (path.startsWith("/cluburi/")) return { name: "club", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/teatru") return { name: "theatre" };
  if (path === "/teatru/nou") return { name: "theatreCreate" };
  if (path.startsWith("/teatru/")) return { name: "theatrePlay", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/stafeta") return { name: "stafeta" };
  if (path === "/stafeta/nou") return { name: "stafetaCreate" };
  if (path.startsWith("/stafeta/")) return { name: "stafetaWork", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/discutii") return { name: "forum" };
  if (path === "/discutii/nou") return { name: "forumCreate" };
  if (path.startsWith("/discutii/")) return { name: "forumThread", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/magazin") return { name: "shop" };
  if (path === "/inventar") return { name: "inventory" };
  if (path === "/premium") return { name: "premium" };
  if (path === "/playlisturi") return { name: "playlists" };
  if (path === "/invitatii") return { name: "referrals" };
  if (path === "/ce-este-calimara") return { name: "about" };
  if (path === "/confidentialitate") return { name: "privacy" };
  if (path === "/termeni") return { name: "terms" };
  if (path === "/autentificare") return { name: "authLogin" };
  if (path === "/autentificare/configurare") return { name: "authSetup" };
  if (path === "/autentificare/raspuns") return { name: "authCallback" };
  if (path.startsWith("/invitatie/")) return { name: "invite", token: decodeURIComponent(path.split("/")[2] || "") };
  return { name: "notFound" };
}

export function RouteView({ route, user, authLoaded, onUserUpdate, onUserRefresh, onMessagesRefresh, onAuthPostIdChange, onLandingStatsChange, onFooterPostActionsChange, onStartAuthorListening, onStartPlaylistListening }) {
  if (PROTECTED_ROUTES.has(route.name) && !authLoaded) {
    return <PageShell kicker="cont" title="Se verifică sesiunea" sub="Încărcăm starea contului tău." />;
  }

  if (PROTECTED_ROUTES.has(route.name) && authLoaded && !user) return <AuthRequired />;

  const Component = ROUTE_COMPONENTS[route.name] || ROUTE_COMPONENTS.notFound;
  return (
    <Component
      route={route}
      user={user}
      authLoaded={authLoaded}
      onUserUpdate={onUserUpdate}
      onUserRefresh={onUserRefresh}
      onMessagesRefresh={onMessagesRefresh}
      onAuthPostIdChange={onAuthPostIdChange}
      onLandingStatsChange={onLandingStatsChange}
      onFooterPostActionsChange={onFooterPostActionsChange}
      onStartAuthorListening={onStartAuthorListening}
      onStartPlaylistListening={onStartPlaylistListening}
    />
  );
}
