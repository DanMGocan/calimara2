import os
import urllib.parse
from urllib.parse import parse_qs

from fastapi import Request

# Configuration from environment variables
MAIN_DOMAIN = os.getenv("MAIN_DOMAIN", "calimara.ro")
SUBDOMAIN_SUFFIX = os.getenv("SUBDOMAIN_SUFFIX", ".calimara.ro")
AVATAR_BACKGROUND_COLORS = "f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff"
COVER_BACKGROUND_COLORS = "f1f4f8,dbeafe,d1fae5,fce7f3,f3e8ff,fff7ed"


def get_avatar_url(user_or_seed, size=80):
    """Generate DiceBear avatar URL for user or seed"""
    if hasattr(user_or_seed, 'avatar_seed'):
        seed = user_or_seed.avatar_seed or f"{user_or_seed.username}-shapes"
    elif hasattr(user_or_seed, 'username'):
        seed = f"{user_or_seed.username}-shapes"
    else:
        seed = str(user_or_seed)

    query = urllib.parse.urlencode(
        {
            "seed": seed,
            "backgroundColor": AVATAR_BACKGROUND_COLORS,
            "size": str(size),
        },
        safe=",",
    )
    return f"https://api.dicebear.com/7.x/shapes/svg?{query}"


def default_cover_seed(user_or_username) -> str:
    """Return the deterministic cover seed used when a user has not picked one."""
    username = getattr(user_or_username, "username", None) or str(user_or_username or "calimara")
    return f"{username}-cover-sky"


def get_cover_url(user_or_seed, size=1600):
    """Generate a DiceBear cover URL for user or seed."""
    if hasattr(user_or_seed, "cover_seed"):
        seed = user_or_seed.cover_seed or default_cover_seed(user_or_seed)
    elif hasattr(user_or_seed, "username"):
        seed = default_cover_seed(user_or_seed)
    else:
        seed = str(user_or_seed)

    query = urllib.parse.urlencode(
        {
            "seed": seed,
            "backgroundColor": COVER_BACKGROUND_COLORS,
            "backgroundType": "gradientLinear",
            "size": str(size),
        }
    )
    return f"https://api.dicebear.com/7.x/shapes/svg?{query}"


def get_client_ip(request: Request):
    """Dependency to get client IP for anonymous likes"""
    return request.client.host


def normalize_external_url(url: str | None) -> str | None:
    """Trim an external URL and add https:// when users omit the scheme."""
    if url is None:
        return None
    value = url.strip()
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme:
        return value
    if parsed.netloc:
        return f"https:{value}" if value.startswith("//") else f"https://{value}"
    return f"https://{value}"


def validate_social_url(url: str, platform: str) -> bool:
    """Validate that URL matches the expected platform domain"""
    if not url or not url.strip():
        return True  # Empty URLs are valid (will be stored as None)

    try:
        normalized_url = normalize_external_url(url)
        parsed = urllib.parse.urlparse(normalized_url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False

        domain = parsed.netloc.lower()

        # Remove www. prefix for comparison
        if domain.startswith('www.'):
            domain = domain[4:]

        platform_domains = {
            'facebook': ['facebook.com', 'fb.com'],
            'instagram': ['instagram.com'],
            'tiktok': ['tiktok.com'],
            'x': ['x.com', 'twitter.com'],
            'bluesky': ['bsky.app'],
            'patreon': ['patreon.com'],
            'paypal': ['paypal.me', 'paypal.com'],
            'buymeacoffee': ['buymeacoffee.com']
        }

        if platform not in platform_domains:
            return False

        return any(
            domain == valid_domain or domain.endswith("." + valid_domain)
            for valid_domain in platform_domains[platform]
        )
    except (ValueError, AttributeError):
        return False


def validate_youtube_playlist_url(url: str) -> bool:
    """Validate YouTube playlist links without accepting arbitrary video URLs."""
    if not url or not url.strip():
        return True

    try:
        normalized_url = normalize_external_url(url)
        parsed = urllib.parse.urlparse(normalized_url or "")
        if parsed.scheme not in {"http", "https"}:
            return False

        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        valid_domains = {
            "youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
        }
        if domain not in valid_domains and not domain.endswith(".youtube.com"):
            return False

        playlist_ids = parse_qs(parsed.query).get("list") or []
        return any(playlist_id.strip() for playlist_id in playlist_ids)
    except (ValueError, AttributeError):
        return False
