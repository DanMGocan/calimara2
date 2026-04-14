CATEGORIES = {
    "poezie": "Poezie",
    "proza_scurta": "Proză scurtă",
}

def get_all_categories():
    """Get all categories with their display names"""
    return [(key, name) for key, name in CATEGORIES.items()]

def get_category_name(category_key):
    """Get display name for a category"""
    return CATEGORIES.get(category_key, "")

def is_valid_category(category_key):
    """Check if a category key is valid"""
    return category_key in CATEGORIES
