export const KIND_TO_CATEGORY = {
  poem: "poezie",
  story: "proza_scurta"
};

export const CATEGORY_LABELS = {
  poezie: "Poezie",
  proza_scurta: "Proză scurtă"
};

export const TITLE_CHARACTER_LIMIT = 120;
export const POETRY_CHARACTER_LIMIT = 10000;
export const SHORT_STORY_CHARACTER_LIMIT = 50000;
export const COMMENT_CHARACTER_LIMIT = 2500;
export const EXPLANATORY_NOTE_CHARACTER_LIMIT = 300;
export const PROFILE_DESCRIPTION_CHARACTER_LIMIT = 400;
export const PRIVATE_MESSAGE_CHARACTER_LIMIT = 2000;

export const POST_CATEGORIES = [
  { key: "poezie", label: CATEGORY_LABELS.poezie, limit: POETRY_CHARACTER_LIMIT },
  { key: "proza_scurta", label: CATEGORY_LABELS.proza_scurta, limit: SHORT_STORY_CHARACTER_LIMIT }
];

export const POST_CONTENT_LIMITS = Object.fromEntries(POST_CATEGORIES.map((item) => [item.key, item.limit]));

export const FORUM_SECTIONS = [
  { key: "anunturi", label: "Anunțuri", featured: true },
  { key: "general", label: "Discuții generale" },
  { key: "poezie", label: "Poezie" },
  { key: "proza_scurta", label: "Proză scurtă" }
];

export const PROFILE_TIER_BADGES = {
  free: { label: "Utilizator", className: "tier-free", tone: "negru" },
  trubadur: { label: "Trubadur", className: "tier-bronze", tone: "bronz" },
  cronicar: { label: "Cronicar", className: "tier-silver", tone: "argint" },
  rapsod: { label: "Rapsod", className: "tier-gold", tone: "aur" }
};

export const AUTH_AVATAR_OPTIONS = [
  { key: "shapes", label: "Forme", seed: "calimara-avatar-shapes" },
  { key: "ink", label: "Cerneală", seed: "calimara-avatar-ink" },
  { key: "page", label: "Pagină", seed: "calimara-avatar-page" },
  { key: "stars", label: "Stele", seed: "calimara-avatar-stars" },
  { key: "garden", label: "Grădină", seed: "calimara-avatar-garden" },
  { key: "arcade", label: "Arcadă", seed: "calimara-avatar-arcade" }
];

export const AUTH_COVER_OPTIONS = [
  { key: "sky", label: "Cer", seed: "calimara-cover-sky" },
  { key: "ink", label: "Cerneală", seed: "calimara-cover-ink" },
  { key: "paper", label: "Pagină", seed: "calimara-cover-paper" },
  { key: "stars", label: "Stele", seed: "calimara-cover-stars" },
  { key: "garden", label: "Grădină", seed: "calimara-cover-garden" },
  { key: "forest", label: "Pădure", seed: "calimara-cover-forest" }
];

export const SHOP_SLOT_LABELS = {
  profile_badge: "Insignă profil",
  costume: "Costum",
  frame: "Ramă",
  background: "Fundal",
  title: "Titlu"
};

export const CONTENT_TYPE_LABELS = {
  post: "Text",
  comment: "Comentariu",
  audio: "Audio",
  forum_thread: "Discuție",
  forum_reply: "Răspuns",
  theatre_entry: "Teatru",
  stafeta_segment: "Ștafeta"
};

export const PROTECTED_ROUTES = new Set(["dashboard", "profileSettings", "create", "messages", "friends", "usersDirectory", "clubs", "club", "forum", "forumCreate", "forumThread", "forumSection", "theatreCreate", "stafeta", "stafetaCreate", "stafetaWork", "shop", "inventory", "playlists", "referrals", "admin", "docs"]);
export const AUTHOR_SUBDOMAIN_ROUTES = new Set(["dashboard", "profileSettings", "create", "messages"]);
export const AD_SUPPORTED_ROUTES = new Set(["landing", "clubs", "club", "theatre", "theatrePlay", "blog", "post", "series"]);
export const ADS_ENABLED = import.meta.env.VITE_ADS_ENABLED === "true";
export const ADSENSE_CLIENT_ID = (import.meta.env.VITE_ADSENSE_CLIENT_ID || "").trim();
export const ADSENSE_SLOTS = {
  rail: (import.meta.env.VITE_ADSENSE_SLOT_RAIL || "").trim(),
  inline: (import.meta.env.VITE_ADSENSE_SLOT_INLINE || "").trim(),
  postFooter: (import.meta.env.VITE_ADSENSE_SLOT_POST_FOOTER || "").trim()
};
export const TEXT_MODERATION_MESSAGE = "Textul a fost trimis în Franța, la Mistral, pentru moderare. Dar se întoarce imediat și va apărea pe platformă! Dacă Mistral zice nu, atunci va fi moderat de către un moderator uman.";
export const MODERATING_STATUSES = new Set(["pending", "flagged"]);
export const POST_DRAFT_AUTOSAVE_MS = 15000;
export const MODERATION_LABELS = {
  pending: "în moderare",
  flagged: "în revizie",
  rejected: "respins"
};

export const PROFILE_LINK_MISSING_MESSAGE = "Acest utilizator nu a setat încă un link pentru această platformă";

export const ALL_WORKS_SORT_OPTIONS = [
  { key: "newest", label: "Cele mai noi" },
  { key: "comments", label: "Comentarii" },
  { key: "likes", label: "Aprecieri" },
  { key: "super_likes", label: "Super-aprecieri" }
];
