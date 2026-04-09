import os
import urllib.parse
from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import models

# Configuration from environment variables
MAIN_DOMAIN = os.getenv("MAIN_DOMAIN", "calimara.ro")
SUBDOMAIN_SUFFIX = os.getenv("SUBDOMAIN_SUFFIX", ".calimara.ro")

# Configure Jinja2Templates
templates = Jinja2Templates(directory="templates")


def get_avatar_url(user_or_seed, size=80):
    """Generate DiceBear avatar URL for user or seed"""
    if hasattr(user_or_seed, 'avatar_seed'):
        seed = user_or_seed.avatar_seed or f"{user_or_seed.username}-shapes"
    elif hasattr(user_or_seed, 'username'):
        seed = f"{user_or_seed.username}-shapes"
    else:
        seed = str(user_or_seed)

    return f"https://api.dicebear.com/7.x/shapes/svg?seed={seed}&backgroundColor=f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff&size={size}"


# Register template global
templates.env.globals["get_avatar_url"] = get_avatar_url


def get_common_context(request: Request, current_user: Optional[models.User] = None):
    """Helper function to get common template context.
    Note: 'request' is no longer included — pass it separately to TemplateResponse.
    """
    return {
        "current_user": current_user,
        "current_domain": request.url.hostname,
        "main_domain": MAIN_DOMAIN,
        "subdomain_suffix": SUBDOMAIN_SUFFIX
    }


def get_client_ip(request: Request):
    """Dependency to get client IP for anonymous likes"""
    return request.client.host


def validate_social_url(url: str, platform: str) -> bool:
    """Validate that URL matches the expected platform domain"""
    if not url or not url.strip():
        return True  # Empty URLs are valid (will be stored as None)

    try:
        parsed = urllib.parse.urlparse(url.lower())
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
