# Predefined categories and genres for Calimara posts

# Main categories structure with subcategories
MAIN_CATEGORIES = {
    "poezie": {
        "name": "Poezie",
        "genres": {
            "poezie_lirica": "Poezie lirică",
            "poezie_epica": "Poezie epică", 
            "poezie_satirica": "Poezie satirică",
            "poezie_experimentala": "Poezie experimentală"
        }
    },
    "proza": {
        "name": "Proză",
        "genres": {
            "povestiri_scurte": "Povestiri scurte",
            "nuvele": "Nuvele",
            "romane": "Romane",
            "flash_fiction": "Flash fiction"
        }
    },
    "altele": {
        "name": "Altele",
        "subcategories": {
            "teatru": {
                "name": "Teatru",
                "genres": {
                    "teatru_clasic": "Teatru clasic",
                    "monologuri": "Monologuri",
                    "drama_contemporana": "Dramă contemporană"
                }
            },
            "eseu": {
                "name": "Eseu",
                "genres": {
                    "eseuri_personale": "Eseuri personale",
                    "eseuri_filosofice": "Eseuri filosofice"
                }
            },
            "critica_literara": {
                "name": "Critică Literară",
                "genres": {
                    "critica_literara": "Critică literară",
                    "recenzii_carte": "Recenzii de carte"
                }
            },
            "scrisoare": {
                "name": "Scrisoare",
                "genres": {
                    "scrisori_personale": "Scrisori personale",
                    "scrisori_deschise": "Scrisori deschise"
                }
            },
            "jurnal": {
                "name": "Jurnal",
                "genres": {
                    "jurnale_personale": "Jurnale personale",
                    "confesiuni": "Confesiuni"
                }
            },
            "literatura_experimentala": {
                "name": "Literatură Experimentală",
                "genres": {
                    "proza_poetica": "Proză poetică",
                    "literatura_digitala": "Literatură digitală",
                    "forme_hibride": "Forme hibride"
                }
            }
        }
    }
}

# Legacy categories structure for backward compatibility
CATEGORIES_AND_GENRES = {
    "poezie": {
        "name": "Poezie",
        "genres": {
            "poezie_lirica": "Poezie lirică",
            "poezie_epica": "Poezie epică", 
            "poezie_satirica": "Poezie satirică",
            "poezie_experimentala": "Poezie experimentală"
        }
    },
    "proza": {
        "name": "Proză",
        "genres": {
            "povestiri_scurte": "Povestiri scurte",
            "nuvele": "Nuvele",
            "romane": "Romane",
            "flash_fiction": "Flash fiction"
        }
    },
    "teatru": {
        "name": "Teatru",
        "genres": {
            "teatru_clasic": "Teatru clasic",
            "monologuri": "Monologuri",
            "drama_contemporana": "Dramă contemporană"
        }
    },
    "eseu": {
        "name": "Eseu",
        "genres": {
            "eseuri_personale": "Eseuri personale",
            "eseuri_filosofice": "Eseuri filosofice"
        }
    },
    "critica_literara": {
        "name": "Critică Literară",
        "genres": {
            "critica_literara": "Critică literară",
            "recenzii_carte": "Recenzii de carte"
        }
    },
    "scrisoare": {
        "name": "Scrisoare",
        "genres": {
            "scrisori_personale": "Scrisori personale",
            "scrisori_deschise": "Scrisori deschise"
        }
    },
    "jurnal": {
        "name": "Jurnal",
        "genres": {
            "jurnale_personale": "Jurnale personale",
            "confesiuni": "Confesiuni"
        }
    },
    "literatura_experimentala": {
        "name": "Literatură Experimentală",
        "genres": {
            "proza_poetica": "Proză poetică",
            "literatura_digitala": "Literatură digitală",
            "forme_hibride": "Forme hibride"
        }
    }
}

def get_main_categories():
    """Get the three main categories for navigation"""
    return MAIN_CATEGORIES

def get_all_categories():
    """Get all categories with their display names"""
    return [(key, value["name"]) for key, value in CATEGORIES_AND_GENRES.items()]

def get_genres_for_category(category_key):
    """Get all genres for a specific category"""
    if category_key in CATEGORIES_AND_GENRES:
        return [(key, value) for key, value in CATEGORIES_AND_GENRES[category_key]["genres"].items()]
    return []

def get_category_name(category_key):
    """Get display name for a category"""
    return CATEGORIES_AND_GENRES.get(category_key, {}).get("name", "")

def get_genre_name(category_key, genre_key):
    """Get display name for a specific genre"""
    if category_key in CATEGORIES_AND_GENRES:
        return CATEGORIES_AND_GENRES[category_key]["genres"].get(genre_key, "")
    return ""

def is_valid_category(category_key):
    """Check if a category key is valid"""
    return category_key in CATEGORIES_AND_GENRES

def is_valid_genre(category_key, genre_key):
    """Check if a genre key is valid for the given category"""
    if category_key in CATEGORIES_AND_GENRES:
        return genre_key in CATEGORIES_AND_GENRES[category_key]["genres"]
    return False