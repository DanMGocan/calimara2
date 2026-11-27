import { useEffect } from "react";
import { PROTECTED_ROUTES } from "./constants.js";
import { categoryLabel, htmlToText, usernameHandle } from "./format.js";
import { blogUrl, mainPath, profileAvatarUrl, profileCoverUrl } from "./paths.js";

const SITE_NAME = "călimara.ro";
const DEFAULT_TITLE = "călimara.ro, platformă modernă de poezie și proză";
const DEFAULT_DESCRIPTION = "Călimara este o platformă literară pentru poezie, proză scurtă, profiluri de autori, teatru colaborativ și discuții.";
const DEFAULT_IMAGE = "/og-image.jpg";

const PRIVATE_ROUTE_NAMES = new Set([
  ...PROTECTED_ROUTES,
  "authLogin",
  "authSetup",
  "authCallback",
  "invite",
  "forumCreate",
  "theatreCreate",
  "notFound",
  "followers",
  "following",
  "publicInventory"
]);

const DATA_DRIVEN_ROUTE_NAMES = new Set([
  "blog",
  "allWorks",
  "post",
  "series",
  "theatrePlay"
]);

const STATIC_ROUTE_SEO = {
  landing: {
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
    canonicalUrl: mainPath("/")
  },
  about: {
    title: `Ce este Călimara | ${SITE_NAME}`,
    description: "Călimara este un spațiu pentru publicarea și descoperirea textelor literare românești.",
    canonicalUrl: mainPath("/ce-este-calimara")
  },
  privacy: {
    title: `Confidențialitate | ${SITE_NAME}`,
    description: "Politica de confidențialitate pentru conturi, conținut, emailuri, cookies și reclame pe Călimara.",
    canonicalUrl: mainPath("/confidentialitate")
  },
  terms: {
    title: `Termeni | ${SITE_NAME}`,
    description: "Termenii de utilizare pentru publicare, moderare, conținut și conturi pe Călimara.",
    canonicalUrl: mainPath("/termeni")
  },
  premium: {
    title: `Premium | ${SITE_NAME}`,
    description: "Planurile Premium Călimara pentru autori, ascultare audio, Super-apreciez și instrumente literare.",
    canonicalUrl: mainPath("/premium")
  },
  theatre: {
    title: `Teatru colaborativ | ${SITE_NAME}`,
    description: "Piese scrise pe rând, cu personaje, scene și autori care colaborează pe Călimara.",
    canonicalUrl: mainPath("/teatru")
  }
};

function currentCanonicalUrl() {
  if (typeof window === "undefined") return "https://calimara.ro/";
  const url = new URL(window.location.href);
  url.hash = "";
  url.search = "";
  return url.toString();
}

function absoluteUrl(value) {
  if (typeof window === "undefined") return value || "https://calimara.ro/og-image.jpg";
  if (!value) return new URL(DEFAULT_IMAGE, window.location.origin).toString();
  if (String(value).startsWith("//")) return `${window.location.protocol}${value}`;
  return new URL(value, window.location.origin).toString();
}

function shortDescription(value, fallback = DEFAULT_DESCRIPTION, limit = 165) {
  const text = (htmlToText(value) || fallback).replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1).replace(/\s+\S*$/, "").replace(/[ .,;:]+$/, "")}…`;
}

function routeSeo(route) {
  if (!route || PRIVATE_ROUTE_NAMES.has(route.name)) {
    return {
      title: `Pagină privată | ${SITE_NAME}`,
      description: "Această pagină nu este destinată indexării publice.",
      canonicalUrl: currentCanonicalUrl(),
      robots: "noindex, nofollow"
    };
  }
  if (STATIC_ROUTE_SEO[route.name]) return STATIC_ROUTE_SEO[route.name];
  return {
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
    canonicalUrl: currentCanonicalUrl()
  };
}

function normalizedSeo(meta = {}) {
  const canonicalUrl = meta.canonicalUrl || currentCanonicalUrl();
  const title = meta.title || DEFAULT_TITLE;
  const description = meta.description || DEFAULT_DESCRIPTION;
  const imageUrl = absoluteUrl(meta.imageUrl || DEFAULT_IMAGE);
  return {
    title,
    description,
    canonicalUrl,
    imageUrl,
    robots: meta.robots || "index, follow",
    ogType: meta.ogType || "website",
    jsonLd: Array.isArray(meta.jsonLd) ? meta.jsonLd : []
  };
}

function upsertMeta(selector, createAttributes, content) {
  let element = document.head.querySelector(selector);
  if (!element) {
    element = document.createElement("meta");
    Object.entries(createAttributes).forEach(([key, value]) => element.setAttribute(key, value));
    document.head.appendChild(element);
  }
  element.setAttribute("content", content);
  element.setAttribute("data-seo", createAttributes.name || createAttributes.property);
}

function upsertCanonical(href) {
  let element = document.head.querySelector('link[rel="canonical"]');
  if (!element) {
    element = document.createElement("link");
    element.setAttribute("rel", "canonical");
    document.head.appendChild(element);
  }
  element.setAttribute("href", href);
  element.setAttribute("data-seo", "canonical");
}

export function setDocumentSeo(meta = {}) {
  if (typeof document === "undefined") return;
  const seo = normalizedSeo(meta);
  document.title = seo.title;
  upsertMeta('meta[name="description"]', { name: "description" }, seo.description);
  upsertMeta('meta[name="robots"]', { name: "robots" }, seo.robots);
  upsertCanonical(seo.canonicalUrl);
  upsertMeta('meta[property="og:site_name"]', { property: "og:site_name" }, SITE_NAME);
  upsertMeta('meta[property="og:locale"]', { property: "og:locale" }, "ro_RO");
  upsertMeta('meta[property="og:type"]', { property: "og:type" }, seo.ogType);
  upsertMeta('meta[property="og:title"]', { property: "og:title" }, seo.title);
  upsertMeta('meta[property="og:description"]', { property: "og:description" }, seo.description);
  upsertMeta('meta[property="og:url"]', { property: "og:url" }, seo.canonicalUrl);
  upsertMeta('meta[property="og:image"]', { property: "og:image" }, seo.imageUrl);
  upsertMeta('meta[name="twitter:card"]', { name: "twitter:card" }, "summary_large_image");
  upsertMeta('meta[name="twitter:title"]', { name: "twitter:title" }, seo.title);
  upsertMeta('meta[name="twitter:description"]', { name: "twitter:description" }, seo.description);
  upsertMeta('meta[name="twitter:image"]', { name: "twitter:image" }, seo.imageUrl);

  document.head.querySelectorAll('script[data-seo^="jsonld-"]').forEach((element) => element.remove());
  seo.jsonLd.forEach((payload, index) => {
    const script = document.createElement("script");
    script.type = "application/ld+json";
    script.setAttribute("data-seo", `jsonld-${index}`);
    script.textContent = JSON.stringify(payload);
    document.head.appendChild(script);
  });
}

export function useRouteSeo(route) {
  useEffect(() => {
    if (DATA_DRIVEN_ROUTE_NAMES.has(route?.name)) return;
    setDocumentSeo(routeSeo(route));
  }, [route?.name, route?.slug, route?.username]);
}

export function usePageSeo(meta, deps = []) {
  useEffect(() => {
    if (!meta) return;
    setDocumentSeo(meta);
  }, deps);
}

export function postSeo(post, owner) {
  if (!post || !owner?.username) return null;
  const canonicalUrl = `${blogUrl(owner.username)}/${post.slug}`;
  const description = shortDescription(post.content, `${categoryLabel(post.category)} de ${usernameHandle(owner.username)} pe Călimara.`);
  const robots = post.moderation_status && post.moderation_status !== "approved" ? "noindex, nofollow" : "index, follow";
  return {
    title: `${post.title} de ${usernameHandle(owner.username)} | ${SITE_NAME}`,
    description,
    canonicalUrl,
    imageUrl: profileCoverUrl(owner),
    ogType: "article",
    robots,
    jsonLd: [{
      "@context": "https://schema.org",
      "@type": "CreativeWork",
      name: post.title,
      headline: post.title,
      text: shortDescription(post.content, "", 600),
      url: canonicalUrl,
      inLanguage: "ro",
      genre: categoryLabel(post.category),
      datePublished: post.created_at,
      dateModified: post.updated_at,
      author: {
        "@type": "Person",
        name: owner.username,
        url: blogUrl(owner.username)
      }
    }]
  };
}

export function profileSeo(owner, { allWorks = false, postCount = 0 } = {}) {
  if (!owner?.username) return null;
  const handle = usernameHandle(owner.username);
  const canonicalUrl = allWorks ? `${blogUrl(owner.username)}/toate-operele` : blogUrl(owner.username);
  const description = shortDescription(
    owner.subtitle,
    allWorks ? `${postCount} texte publicate de ${handle} pe Călimara.` : `Profilul public al autorului ${handle} pe Călimara.`
  );
  return {
    title: allWorks ? `Toate operele lui ${handle} | ${SITE_NAME}` : `${handle} | ${SITE_NAME}`,
    description,
    canonicalUrl,
    imageUrl: profileCoverUrl(owner),
    ogType: "profile",
    jsonLd: [{
      "@context": "https://schema.org",
      "@type": "ProfilePage",
      url: canonicalUrl,
      name: allWorks ? `Toate operele lui ${handle}` : handle,
      description,
      inLanguage: "ro",
      mainEntity: {
        "@type": "Person",
        name: owner.username,
        alternateName: handle,
        url: blogUrl(owner.username),
        image: absoluteUrl(profileAvatarUrl(owner, 512))
      }
    }]
  };
}

export function seriesSeo(series) {
  if (!series?.slug) return null;
  const ownerLabel = series.owner?.username ? ` de ${usernameHandle(series.owner.username)}` : "";
  const postCount = series.posts?.length || series.post_count || 0;
  const description = shortDescription(series.description, `Serie literară${ownerLabel} cu ${postCount} texte publice pe Călimara.`);
  return {
    title: `${series.title}${ownerLabel} | ${SITE_NAME}`,
    description,
    canonicalUrl: mainPath(`/serii/${series.slug}`),
    imageUrl: series.owner ? profileCoverUrl(series.owner) : DEFAULT_IMAGE,
    ogType: "book",
    jsonLd: [{
      "@context": "https://schema.org",
      "@type": "CreativeWorkSeries",
      name: series.title,
      description,
      url: mainPath(`/serii/${series.slug}`),
      inLanguage: "ro",
      numberOfItems: postCount
    }]
  };
}

export function theatrePlaySeo(play) {
  if (!play?.slug) return null;
  const creatorLabel = play.creator?.username ? ` creată de ${usernameHandle(play.creator.username)}` : "";
  const description = shortDescription(play.description, `Piesă de teatru colaborativ pe Călimara${creatorLabel}.`);
  return {
    title: `${play.title} | Teatru colaborativ | ${SITE_NAME}`,
    description,
    canonicalUrl: mainPath(`/teatru/${play.slug}`),
    imageUrl: play.creator ? profileCoverUrl(play.creator) : DEFAULT_IMAGE,
    ogType: "article",
    jsonLd: [{
      "@context": "https://schema.org",
      "@type": "CreativeWork",
      name: play.title,
      description,
      url: mainPath(`/teatru/${play.slug}`),
      inLanguage: "ro",
      creator: play.creator?.username ? {
        "@type": "Person",
        name: play.creator.username,
        url: blogUrl(play.creator.username)
      } : undefined
    }]
  };
}

