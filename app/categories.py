# Predefined categories and genres for Calimara posts

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
    "dramaturgie": {
        "name": "Dramaturgie",
        "genres": {
            "teatru_clasic": "Teatru clasic",
            "monologuri": "Monologuri",
            "drama_contemporana": "Dramă contemporană"
        }
    },
    "eseu_critica": {
        "name": "Eseu și critică literară",
        "genres": {
            "eseuri_personale": "Eseuri personale",
            "critica_literara": "Critică literară",
            "recenzii_carte": "Recenzii de carte"
        }
    },
    "literatura_copii": {
        "name": "Literatură pentru copii și adolescenți",
        "genres": {
            "povesti_copii": "Povești pentru copii",
            "literatura_young_adult": "Literatură Young Adult",
            "basme_fabule": "Basme și fabule"
        }
    },
    "literatura_fantastica": {
        "name": "Literatură fantastică și speculativă",
        "genres": {
            "fantasy": "Fantasy",
            "science_fiction": "Science fiction",
            "distopie": "Distopie",
            "magie_realista": "Magie realistă"
        }
    },
    "literatura_realista": {
        "name": "Literatură realistă",
        "genres": {
            "realism_social": "Realism social",
            "fictiune_psihologica": "Ficțiune psihologică",
            "fictiune_istorica": "Ficțiune istorică"
        }
    },
    "literatura_experimentala": {
        "name": "Literatură experimentală",
        "genres": {
            "proza_poetica": "Proză poetică",
            "literatura_digitala": "Literatură digitală",
            "forme_hibride": "Forme hibride"
        }
    },
    "memorii_jurnal": {
        "name": "Memorii și jurnal personal",
        "genres": {
            "jurnale": "Jurnale",
            "scrisori": "Scrisori",
            "confesiuni": "Confesiuni"
        }
    },
    "literatura_populara": {
        "name": "Literatură populară și folclor",
        "genres": {
            "poezie_populara": "Poezie populară",
            "legende": "Legende",
            "mituri": "Mituri"
        }
    }
}

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