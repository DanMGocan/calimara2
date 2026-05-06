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
export const PROFILE_DESCRIPTION_CHARACTER_LIMIT = 1000;

export const POST_CATEGORIES = [
  { key: "poezie", label: CATEGORY_LABELS.poezie, limit: POETRY_CHARACTER_LIMIT },
  { key: "proza_scurta", label: CATEGORY_LABELS.proza_scurta, limit: SHORT_STORY_CHARACTER_LIMIT }
];

export const POST_CONTENT_LIMITS = Object.fromEntries(POST_CATEGORIES.map((item) => [item.key, item.limit]));

export const FORUM_SECTIONS = [
  { key: "general", label: "General" },
  { key: "poezie", label: "Poezie" },
  { key: "proza_scurta", label: "Proză scurtă" },
  { key: "feedback", label: "Impresii" },
  { key: "anunturi", label: "Anunțuri" }
];

export const PROFILE_TIER_BADGES = {
  free: { label: "Utilizator", className: "tier-free", tone: "negru" },
  trubadur: { label: "Trubadur", className: "tier-bronze", tone: "bronz" },
  cronicar: { label: "Cronicar", className: "tier-silver", tone: "argint" },
  rapsod: { label: "Rapsod", className: "tier-gold", tone: "aur" }
};

export const AUTH_AVATAR_OPTIONS = [
  { key: "shapes", label: "Forme" },
  { key: "ink", label: "Cerneală" },
  { key: "page", label: "Pagină" },
  { key: "stars", label: "Stele" },
  { key: "garden", label: "Grădină" },
  { key: "arcade", label: "Arcadă" }
];

export const AUTH_COVER_OPTIONS = [
  { key: "sky", label: "Cer" },
  { key: "ink", label: "Cerneală" },
  { key: "paper", label: "Pagină" },
  { key: "stars", label: "Stele" },
  { key: "garden", label: "Grădină" },
  { key: "forest", label: "Pădure" }
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
  forum_reply: "Răspuns"
};

export const PROTECTED_ROUTES = new Set(["dashboard", "profileSettings", "create", "messages", "forum", "forumCreate", "forumThread", "shop", "inventory", "admin"]);
export const AUTHOR_SUBDOMAIN_ROUTES = new Set(["dashboard", "profileSettings", "create", "messages"]);
export const AD_SUPPORTED_ROUTES = new Set(["landing", "category", "clubs", "club", "blog", "post", "series"]);
export const ADS_ENABLED = import.meta.env.VITE_ADS_ENABLED === "true";
export const ADSENSE_CLIENT_ID = (import.meta.env.VITE_ADSENSE_CLIENT_ID || "").trim();
export const ADSENSE_SLOTS = {
  rail: (import.meta.env.VITE_ADSENSE_SLOT_RAIL || "").trim(),
  inline: (import.meta.env.VITE_ADSENSE_SLOT_INLINE || "").trim(),
  postFooter: (import.meta.env.VITE_ADSENSE_SLOT_POST_FOOTER || "").trim()
};
export const TEXT_MODERATION_MESSAGE = "Textul este în curs de moderare și va fi disponibil pe site în câteva secunde, cu voia Robotului.";
export const COMMENT_MODERATION_MESSAGE = "Comentariul este în curs de moderare și va fi disponibil în câteva secunde, cu voia Robotului.";
export const FORUM_MODERATION_MESSAGE = "Mesajul este în curs de moderare și va fi disponibil în câteva secunde, cu voia Robotului.";
export const POST_DRAFT_AUTOSAVE_MS = 15000;
export const MODERATION_LABELS = {
  pending: "în moderare",
  flagged: "în revizie",
  rejected: "respins"
};

export const PROFILE_LINK_MISSING_MESSAGE = "Acest utilizator nu a setat inca un link pentru aceasta platforma";

export const ALL_WORKS_SORT_OPTIONS = [
  { key: "newest", label: "Cele mai noi" },
  { key: "comments", label: "Comentarii" },
  { key: "likes", label: "Aprecieri" },
  { key: "super_likes", label: "Super-aprecieri" }
];
