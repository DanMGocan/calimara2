import { FaFacebookF, FaInstagram, FaPatreon, FaPaypal, FaTiktok, FaXTwitter } from "react-icons/fa6";
import { SiBluesky, SiBuymeacoffee } from "react-icons/si";
import { PROFILE_TIER_BADGES } from "./constants.js";
import { safeExternalUrl } from "./urls.js";

export { safeExternalUrl } from "./urls.js";

export const SOCIAL_PROFILE_LINKS = [
  { field: "facebook_url", label: "Facebook", Icon: FaFacebookF, className: "facebook" },
  { field: "instagram_url", label: "Instagram", Icon: FaInstagram, className: "instagram" },
  { field: "tiktok_url", label: "TikTok", Icon: FaTiktok, className: "tiktok" },
  { field: "x_url", label: "X", Icon: FaXTwitter, className: "x-twitter" },
  { field: "bluesky_url", label: "Bluesky", Icon: SiBluesky, className: "bluesky" }
];

export const SUPPORT_PROFILE_LINKS = [
  { field: "paypal_url", label: "PayPal", Icon: FaPaypal, className: "paypal" },
  { field: "patreon_url", label: "Patreon", Icon: FaPatreon, className: "patreon" },
  { field: "buymeacoffee_url", label: "Cafea", Icon: SiBuymeacoffee, className: "coffee" }
];

export function profileLinks(user, definitions) {
  return definitions.map((definition) => ({ ...definition, url: safeExternalUrl(user?.[definition.field]) }));
}

export function profileTierBadge(user) {
  const tier = user?.is_premium ? user?.premium_tier || "trubadur" : "free";
  return PROFILE_TIER_BADGES[tier] || PROFILE_TIER_BADGES.trubadur;
}
