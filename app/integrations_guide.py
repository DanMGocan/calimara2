"""Setup guide and configuration status for Calimara's external integrations.

Powers the admin "Integrări" tab. Only reports whether each environment
variable is set; never returns the values themselves.
"""

import os
from typing import Any

RESTART_COMMAND = "sudo systemctl restart calimara"
ENV_FILE_PATH = "/home/dan/calimara2/.env"

TRUE_VALUES = ("true", "1", "yes", "on")

# Each integration:
#   key, name, purpose
#   env: list of {name, required, secret, hint}
#   flags: feature flags (env vars) that switch the integration on; empty
#          list means the integration is active as soon as required vars are set
#   steps: ordered instructions
#   notes: extra warnings
INTEGRATIONS: list[dict[str, Any]] = [
    {
        "key": "google_oauth",
        "name": "Google – autentificare",
        "purpose": "Butonul „Continuă cu Google” la autentificare și înregistrare.",
        "env": [
            {"name": "GOOGLE_CLIENT_ID", "required": True, "secret": False, "hint": "se termină în .apps.googleusercontent.com"},
            {"name": "GOOGLE_CLIENT_SECRET", "required": True, "secret": True, "hint": "începe cu GOCSPX-"},
            {"name": "GOOGLE_REDIRECT_URI", "required": True, "secret": False, "hint": "https://calimara.ro/auth/google/callback (deja completat)"},
        ],
        "flags": [],
        "steps": [
            "Deschide https://console.cloud.google.com și creează un proiect nou (ex. „calimara”), sau alege unul existent.",
            "APIs & Services → OAuth consent screen: tip „External”, nume aplicație „Călimara”, email de suport, domeniu autorizat calimara.ro, link-uri către https://calimara.ro/confidentialitate și https://calimara.ro/termeni.",
            "APIs & Services → Credentials → Create credentials → OAuth client ID → tip „Web application”.",
            "La „Authorized JavaScript origins” adaugă https://calimara.ro.",
            "La „Authorized redirect URIs” adaugă exact: https://calimara.ro/auth/google/callback",
            "Copiază Client ID în GOOGLE_CLIENT_ID și Client secret în GOOGLE_CLIENT_SECRET.",
            "Înapoi la OAuth consent screen apasă „Publish app”, altfel doar utilizatorii de test se pot autentifica.",
        ],
        "notes": [],
    },
    {
        "key": "facebook_oauth",
        "name": "Facebook – autentificare",
        "purpose": "Butonul „Continuă cu Facebook” la autentificare.",
        "env": [
            {"name": "FACEBOOK_CLIENT_ID", "required": True, "secret": False, "hint": "App ID (doar cifre)"},
            {"name": "FACEBOOK_CLIENT_SECRET", "required": True, "secret": True, "hint": "App Secret"},
            {"name": "FACEBOOK_REDIRECT_URI", "required": True, "secret": False, "hint": "https://calimara.ro/auth/facebook/callback (deja completat)"},
        ],
        "flags": [],
        "steps": [
            "Deschide https://developers.facebook.com → My Apps → Create App → cazul de utilizare „Authenticate and request data from users with Facebook Login”.",
            "În aplicație: Facebook Login → Settings → „Valid OAuth Redirect URIs”: https://calimara.ro/auth/facebook/callback",
            "App settings → Basic: App Domains = calimara.ro, Privacy Policy URL = https://calimara.ro/confidentialitate, Terms of Service URL = https://calimara.ro/termeni.",
            "Tot în App settings → Basic copiază App ID în FACEBOOK_CLIENT_ID și App Secret (butonul „Show”) în FACEBOOK_CLIENT_SECRET.",
            "Comută aplicația din „Development” în „Live”, altfel doar administratorii aplicației se pot autentifica.",
        ],
        "notes": [],
    },
    {
        "key": "mistral",
        "name": "Mistral AI",
        "purpose": "Moderare automată, corectare diacritice, formatare AI și critica AI pentru utilizatorii gratuiți.",
        "env": [
            {"name": "MISTRAL_API_KEY", "required": True, "secret": True, "hint": "cheie API din consola Mistral"},
        ],
        "flags": ["MODERATION_ENABLED", "DIACRITICS_ENABLED", "AI_FORMATTING_ENABLED"],
        "steps": [
            "Creează un cont pe https://console.mistral.ai.",
            "Workspace → Billing: alege un plan (planul gratuit „Experiment” funcționează, dar are limite mici de trafic; pentru producție activează plata).",
            "API Keys → Create new key. Copiază cheia imediat (nu mai poate fi afișată ulterior) în MISTRAL_API_KEY.",
            "Pornește funcțiile dorite: MODERATION_ENABLED=True, DIACRITICS_ENABLED=True, AI_FORMATTING_ENABLED=True.",
        ],
        "notes": [
            "Cu MODERATION_ENABLED=True, textele noi trec prin moderarea AI înainte de publicare. Fără moderare, tot ce se publică apare direct.",
        ],
    },
    {
        "key": "anthropic",
        "name": "Anthropic (Claude)",
        "purpose": "Critica AI pentru utilizatorii premium.",
        "env": [
            {"name": "ANTHROPIC_API_KEY", "required": True, "secret": True, "hint": "începe cu sk-ant-"},
        ],
        "flags": ["AI_CRITIC_ENABLED"],
        "steps": [
            "Creează un cont pe https://console.anthropic.com.",
            "Settings → Billing: adaugă credit (API-ul este plătit per utilizare).",
            "Settings → API Keys → Create Key. Copiază cheia în ANTHROPIC_API_KEY.",
            "Setează AI_CRITIC_ENABLED=True.",
        ],
        "notes": [
            "Critica pentru utilizatorii gratuiți folosește Mistral, deci AI_CRITIC_ENABLED are nevoie și de MISTRAL_API_KEY.",
            "Modelul folosit pentru premium se poate schimba cu PREMIUM_USERS_MODEL.",
        ],
    },
    {
        "key": "brevo",
        "name": "Brevo – email",
        "purpose": "Emailuri tranzacționale: coduri de verificare, resetare parolă, notificări, campanii din tabul Email.",
        "env": [
            {"name": "BREVO_API_KEY", "required": True, "secret": True, "hint": "începe cu xkeysib-"},
            {"name": "BREVO_SENDER_EMAIL", "required": True, "secret": False, "hint": "contact@calimara.ro (deja completat)"},
            {"name": "BREVO_SENDER_NAME", "required": False, "secret": False, "hint": "Călimara (deja completat)"},
            {"name": "SYSTEM_ALERT_EMAIL", "required": False, "secret": False, "hint": "unde primești alertele de sistem"},
        ],
        "flags": ["EMAILS_ENABLED"],
        "steps": [
            "Creează un cont pe https://app.brevo.com.",
            "Settings → Senders, Domains & Dedicated IPs → Domains → Add a domain → calimara.ro.",
            "Brevo îți afișează înregistrările DNS (cod Brevo TXT, DKIM, DMARC). Adaugă-le în Cloudflare → DNS și apasă „Verify” în Brevo.",
            "Senders → Add a sender: contact@calimara.ro (aceeași adresă ca BREVO_SENDER_EMAIL).",
            "Settings → SMTP & API → API Keys → Generate a new API key. Copiază cheia în BREVO_API_KEY.",
            "Setează EMAILS_ENABLED=True.",
        ],
        "notes": [
            "Fără email, utilizatorii noi care se înregistrează cu parolă nu primesc codul de activare, iar invitațiile din tabul Acces nu ajung la destinatari. Autentificarea cu Google sau Facebook funcționează și fără email.",
        ],
    },
    {
        "key": "stripe",
        "name": "Stripe – abonamente premium",
        "purpose": "Plata abonamentelor Trubadur, Cronicar și Rapsod și portalul de gestionare a abonamentului.",
        "env": [
            {"name": "STRIPE_SECRET_KEY", "required": True, "secret": True, "hint": "sk_live_... (sau sk_test_... pentru teste)"},
            {"name": "STRIPE_WEBHOOK_SECRET", "required": True, "secret": True, "hint": "whsec_..."},
            {"name": "STRIPE_PRICE_ID_TRUBADUR_MONTHLY", "required": True, "secret": False, "hint": "price_..."},
            {"name": "STRIPE_PRICE_ID_CRONICAR_MONTHLY", "required": False, "secret": False, "hint": "price_..."},
            {"name": "STRIPE_PRICE_ID_RAPSOD_MONTHLY", "required": False, "secret": False, "hint": "price_..."},
            {"name": "STRIPE_SUCCESS_URL", "required": True, "secret": False, "hint": "deja completat"},
            {"name": "STRIPE_CANCEL_URL", "required": True, "secret": False, "hint": "deja completat"},
            {"name": "STRIPE_CUSTOMER_PORTAL_RETURN_URL", "required": True, "secret": False, "hint": "deja completat"},
        ],
        "flags": ["STRIPE_ENABLED"],
        "steps": [
            "Creează sau deschide contul pe https://dashboard.stripe.com și finalizează activarea (date firmă, cont bancar).",
            "Product catalog → Add product, de trei ori: Trubadur, Cronicar, Rapsod. Fiecare cu un preț recurent lunar în RON.",
            "Deschide fiecare preț și copiază ID-ul (price_...) în STRIPE_PRICE_ID_TRUBADUR_MONTHLY, STRIPE_PRICE_ID_CRONICAR_MONTHLY și STRIPE_PRICE_ID_RAPSOD_MONTHLY.",
            "Developers → API keys → Secret key → copiază în STRIPE_SECRET_KEY.",
            "Developers → Webhooks → Add endpoint: URL https://calimara.ro/api/stripe/notificare, cu evenimentele customer.subscription.created, customer.subscription.updated, customer.subscription.deleted și invoice.payment_failed.",
            "Deschide webhook-ul creat → „Signing secret” → copiază (whsec_...) în STRIPE_WEBHOOK_SECRET.",
            "Settings → Billing → Customer portal → activează portalul (permite anularea și schimbarea cardului).",
            "Setează STRIPE_ENABLED=True.",
        ],
        "notes": [
            "Atenție: cu STRIPE_ENABLED=True, dacă lipsește oricare variabilă obligatorie, aplicația nu mai pornește. Verifică jurnalul după repornire: journalctl -u calimara -n 50",
            "Cheile de test (sk_test_) și cele live (sk_live_) au produse, prețuri și webhook-uri separate. Nu le amesteca.",
        ],
    },
    {
        "key": "hetzner_s3",
        "name": "Hetzner Object Storage (S3)",
        "purpose": "Stocarea fișierelor audio și a imaginilor de profil în afara serverului. Opțional: implicit se folosește discul acestui server.",
        "env": [
            {"name": "HETZNER_S3_ENDPOINT_URL", "required": True, "secret": False, "hint": "ex. https://fsn1.your-objectstorage.com"},
            {"name": "HETZNER_S3_REGION", "required": True, "secret": False, "hint": "fsn1, nbg1 sau hel1"},
            {"name": "HETZNER_S3_BUCKET", "required": True, "secret": False, "hint": "numele bucket-ului"},
            {"name": "HETZNER_S3_ACCESS_KEY_ID", "required": True, "secret": True, "hint": "Access key"},
            {"name": "HETZNER_S3_SECRET_ACCESS_KEY", "required": True, "secret": True, "hint": "Secret key"},
        ],
        "flags": [],
        "backend_vars": ["AUDIO_STORAGE_BACKEND", "PROFILE_MEDIA_STORAGE_BACKEND"],
        "steps": [
            "Deschide https://console.hetzner.com → proiectul tău → Object Storage → Create Bucket (locație ex. Falkenstein / fsn1, vizibilitate privată).",
            "Object Storage → Security → S3 credentials → Generate credentials. Copiază Access key și Secret key (secretul este afișat o singură dată).",
            "Completează HETZNER_S3_ENDPOINT_URL (ex. https://fsn1.your-objectstorage.com), HETZNER_S3_REGION, HETZNER_S3_BUCKET și cele două chei.",
            "Comută stocarea: AUDIO_STORAGE_BACKEND=s3 și PROFILE_MEDIA_STORAGE_BACKEND=s3.",
        ],
        "notes": [
            "Fișierele încărcate deja pe disc nu sunt mutate automat în bucket.",
        ],
    },
    {
        "key": "google_cloud_audio",
        "name": "Google Cloud – audio (TTS/STT)",
        "purpose": "Generarea variantei audio a textelor (text-to-speech) și transcrierea înregistrărilor (speech-to-text).",
        "env": [
            {"name": "GOOGLE_CLOUD_PROJECT", "required": True, "secret": False, "hint": "ID-ul proiectului Google Cloud"},
            {"name": "GOOGLE_APPLICATION_CREDENTIALS", "required": True, "secret": False, "hint": "/home/dan/calimara2/keys/google-cloud.json (deja completat)"},
        ],
        "flags": ["AUDIO_ENABLED"],
        "credentials_file_var": "GOOGLE_APPLICATION_CREDENTIALS",
        "steps": [
            "În https://console.cloud.google.com (poate fi același proiect ca la autentificarea Google) activează facturarea: Billing → Link a billing account.",
            "APIs & Services → Library: activează „Cloud Text-to-Speech API” și „Cloud Speech-to-Text API”.",
            "IAM & Admin → Service Accounts → Create service account (ex. „calimara-audio”), cu rolul „Cloud Speech Client”.",
            "Deschide contul de serviciu → Keys → Add key → Create new key → JSON. Se descarcă un fișier .json.",
            "Copiază fișierul pe server în /home/dan/calimara2/keys/google-cloud.json (mkdir -p keys, apoi chmod 600 keys/google-cloud.json). Folderul keys/ este exclus din git.",
            "Completează GOOGLE_CLOUD_PROJECT cu ID-ul proiectului (nu numele) și setează AUDIO_ENABLED=True.",
        ],
        "notes": [],
    },
    {
        "key": "adsense",
        "name": "Google AdSense – reclame",
        "purpose": "Reclame afișate vizitatorilor fără abonament și fișierul /ads.txt.",
        "env": [
            {"name": "ADSENSE_PUBLISHER_ID", "required": True, "secret": False, "hint": "pub-XXXXXXXXXXXXXXXX"},
            {"name": "VITE_ADSENSE_CLIENT_ID", "required": True, "secret": False, "hint": "ca-pub-XXXXXXXXXXXXXXXX"},
            {"name": "VITE_ADSENSE_SLOT_RAIL", "required": True, "secret": False, "hint": "ID unitate (doar cifre)"},
            {"name": "VITE_ADSENSE_SLOT_INLINE", "required": True, "secret": False, "hint": "ID unitate (doar cifre)"},
            {"name": "VITE_ADSENSE_SLOT_POST_FOOTER", "required": True, "secret": False, "hint": "ID unitate (doar cifre)"},
        ],
        "flags": ["VITE_ADS_ENABLED"],
        "steps": [
            "Pe https://adsense.google.com → Sites → Add site → calimara.ro. Urmează pașii de verificare și așteaptă aprobarea.",
            "Account → Account information: copiază Publisher ID. Pune pub-... în ADSENSE_PUBLISHER_ID și ca-pub-... (același număr) în VITE_ADSENSE_CLIENT_ID.",
            "Ads → By ad unit → Display ads: creează trei unități (bară laterală, în text, sub articol). Copiază valoarea data-ad-slot a fiecăreia în VITE_ADSENSE_SLOT_RAIL, VITE_ADSENSE_SLOT_INLINE și VITE_ADSENSE_SLOT_POST_FOOTER.",
            "Setează VITE_ADS_ENABLED=true.",
        ],
        "notes": [
            "Variabilele VITE_ sunt incluse în frontend la build. Repornirea serviciului reface build-ul automat, așa că durează ~1 minut.",
        ],
    },
]


def _is_set(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _is_true(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in TRUE_VALUES


def _integration_status(item: dict[str, Any]) -> dict[str, Any]:
    env = [
        {
            "name": var["name"],
            "required": var["required"],
            "secret": var["secret"],
            "hint": var["hint"],
            "is_set": _is_set(var["name"]),
        }
        for var in item["env"]
    ]
    flags = [{"name": name, "enabled": _is_true(name)} for name in item["flags"]]
    backends = []
    for name in item.get("backend_vars", []):
        value = (os.getenv(name) or "local").strip().lower()
        backends.append({"name": name, "value": value if value in ("local", "s3") else "invalid"})

    required_ok = all(var["is_set"] for var in env if var["required"])
    if flags:
        switched_on = any(flag["enabled"] for flag in flags)
    elif backends:
        switched_on = any(backend["value"] == "s3" for backend in backends)
    else:
        switched_on = required_ok

    credentials_file = None
    file_var = item.get("credentials_file_var")
    if file_var:
        path = (os.getenv(file_var) or "").strip()
        credentials_file = {"name": file_var, "exists": bool(path) and os.path.isfile(path)}
        if switched_on and not credentials_file["exists"]:
            required_ok = False

    if switched_on and required_ok:
        status = "active"
    elif switched_on:
        status = "incomplete"
    elif required_ok:
        status = "ready"
    else:
        status = "not_configured"

    return {
        "key": item["key"],
        "name": item["name"],
        "purpose": item["purpose"],
        "status": status,
        "env": env,
        "flags": flags,
        "backends": backends,
        "credentials_file": credentials_file,
        "steps": list(item["steps"]),
        "notes": list(item["notes"]),
    }


def integrations_status() -> dict[str, Any]:
    """Return setup instructions plus set/missing status. Never includes values."""
    items = [_integration_status(item) for item in INTEGRATIONS]
    return {
        "env_file": ENV_FILE_PATH,
        "restart_command": RESTART_COMMAND,
        "summary": {
            status: sum(1 for item in items if item["status"] == status)
            for status in ("active", "ready", "incomplete", "not_configured")
        },
        "integrations": items,
    }
