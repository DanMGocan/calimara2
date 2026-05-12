import re
import unicodedata


def generate_slug(title: str, fallback: str = "postare") -> str:
    normalized_title = unicodedata.normalize("NFKD", title or "")
    ascii_title = normalized_title.encode("ascii", "ignore").decode("ascii")
    slug = ascii_title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or fallback
