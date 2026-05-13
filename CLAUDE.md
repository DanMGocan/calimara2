# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Calimara is a Romanian microblogging platform for writers and poets. Each writer gets their own subdomain (e.g., `username.calimara.ro`) where they can post poems, short texts, and interact with readers. The main domain (`calimara.ro`) serves as a discovery hub showing random posts and blogs.

## Key Architecture

### Subdomain-Based Multi-Tenancy
- **Single FastAPI application** serves all subdomains dynamically
- **SubdomainMiddleware** (in `app/main.py`) detects subdomains via Host header and sets `request.state.is_subdomain` and `request.state.username`
- **Single PostgreSQL database** with user-scoped data (no separate databases per user)
- **Session sharing** across subdomains using `domain=SUBDOMAIN_SUFFIX` in SessionMiddleware

### Core Components
- **FastAPI app** with Jinja2 templates and session-based auth (no JWT)
- **Google OAuth 2.0** authentication using Authlib for secure user login
- **SQLAlchemy ORM** with modern `Mapped` annotations
- **Category system** with two categories: "Poezie" and "Proză scurtă", auto-classified by AI via `app/category_classifier.py`
- **Environment-based configuration** via `.env` file with domain variables
- **Bootstrap + custom CSS** with Inter font

### Database Architecture
- **Users Table**: `username` (unique, lowercase), `email`, `google_id` (OAuth unique identifier), `subtitle`, `avatar_seed`, social media URLs (facebook_url, tiktok_url, instagram_url, x_url, bluesky_url), donation URLs (patreon_url, paypal_url, buymeacoffee_url)
- **Posts Table**: `user_id`, `title`, `slug` (SEO-friendly URLs), `content`, `category` (AI-classified: "poezie" or "proza_scurta"), `view_count`
- **Comments Table**: Supports both authenticated and anonymous comments with approval system
- **Likes Table**: Supports both user-based and IP-based likes
- **Key Relationship**: Post model has `@property likes_count` that auto-calculates from relationship

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (rebuilds DB from schema.sql by default, starts uvicorn)
python run.py

# Preserve the existing database while starting
CALIMARA_RESET_DATABASE=false python run.py
```

### PostgreSQL Setup
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt install postgresql

# Create a database user
sudo -u postgres createuser --createdb calimara_user
sudo -u postgres psql -c "ALTER USER calimara_user PASSWORD 'calimara_pass';"

# The database itself is created automatically by run.py
```

### Test Data
The seed script creates sample data with 2 users and 10 posts:
- **gocandan / gocandan@gmail.com**: 5 Ion Creangă prose entries (admin + moderator, Rapsod tier)
- **dangocan / dangocan@outlook.com**: 5 Mihai Eminescu poems

## Critical Configuration

### Environment Variables (.env)
- **DB_USER**: PostgreSQL username
- **DB_PASSWORD**: PostgreSQL password
- **DB_HOST**: Database host (default: `localhost`)
- **DB_PORT**: Database port (default: `5432`)
- **DB_NAME**: Database name (default: `calimara_db`)
- **SESSION_SECRET_KEY**: Session encryption key (required, no default)
- **HTTPS_ONLY**: Set to `False` for local development (HTTP), `True` for production (HTTPS). Controls the Secure flag on session cookies.
- **MAIN_DOMAIN**: Main domain (e.g., `calimara.ro` or `localhost`)
- **SUBDOMAIN_SUFFIX**: Subdomain pattern (e.g., `.calimara.ro` or `.localhost`)
- **GOOGLE_CLIENT_ID**: Google OAuth client ID from Google Cloud Console
- **GOOGLE_CLIENT_SECRET**: Google OAuth client secret from Google Cloud Console
- **GOOGLE_REDIRECT_URI**: OAuth callback URL
- **GEMINI_API_KEY**: Google Gemini API key for content moderation
- **GOD_ADMIN_EMAIL**: Admin email address
- **STRIPE_ENABLED**: `True` to enable the Premium subscription feature (Stripe Checkout + webhook). `False` disables all premium endpoints.
- **STRIPE_SECRET_KEY**: Stripe secret API key (`sk_test_...` for test mode, `sk_live_...` for production). Required when `STRIPE_ENABLED=True`.
- **STRIPE_PUBLISHABLE_KEY**: Stripe publishable key (`pk_test_...`). Reserved for future client-side use; required when `STRIPE_ENABLED=True`.
- **STRIPE_WEBHOOK_SECRET**: Stripe webhook signing secret (`whsec_...`). The webhook endpoint at `/api/stripe/webhook` verifies every incoming event against this.
- **STRIPE_PRICE_ID_TRUBADUR_MONTHLY**: Stripe Price ID for the Trubadur monthly plan. Create the Price (EUR, recurring monthly) in the Stripe dashboard and paste the resulting `price_...` ID here.
- **STRIPE_PRICE_ID_CRONICAR_MONTHLY**: Stripe Price ID for the Cronicar monthly plan.
- **STRIPE_PRICE_ID_RAPSOD_MONTHLY**: Stripe Price ID for the Rapsod monthly plan.
- **STRIPE_SUCCESS_URL**: Full URL users are redirected to after successful Checkout. Include the literal placeholder `?session_id={CHECKOUT_SESSION_ID}`, e.g. `https://calimara.ro/premium/success?session_id={CHECKOUT_SESSION_ID}`.
- **STRIPE_CANCEL_URL**: Full URL users are redirected to if they cancel Checkout, e.g. `https://calimara.ro/premium/cancel`.
- **STRIPE_CUSTOMER_PORTAL_RETURN_URL**: Return URL from the Stripe Billing Portal (where users manage their subscription), e.g. `https://calimara.ro/dashboard`.
- **ADSENSE_PUBLISHER_ID**: AdSense `pub-...` publisher ID used by `/ads.txt`.
- **VITE_ADS_ENABLED**: `true` to enable frontend ad rendering; defaults to `false`.
- **VITE_ADSENSE_CLIENT_ID**: AdSense client ID in `ca-pub-...` format for the frontend script and ad units.
- **VITE_ADSENSE_SLOT_RAIL**: AdSense display ad slot ID for the landing-page side rail.
- **VITE_ADSENSE_SLOT_INLINE**: AdSense display ad slot ID for inline list ads.
- **VITE_ADSENSE_SLOT_POST_FOOTER**: AdSense display ad slot ID for post-detail footer ads.

### Template Context Helper
Use `get_common_context(request, current_user)` for consistent template variables including domain configuration that's passed to JavaScript via `window.CALIMARA_CONFIG`.

## Development Philosophy

### Server-Side Processing Preference
**IMPORTANT: Minimize JavaScript usage and prefer server-side processing whenever possible.**
- Use FastAPI endpoints and server-side redirects over client-side routing
- Prefer Jinja2 template rendering over dynamic JavaScript DOM manipulation  
- Keep JavaScript limited to essential interactions (form submissions, modals, UI enhancements)
- Use HTML forms with server-side processing rather than complex client-side logic
- When JavaScript is necessary, keep it simple and progressively enhanced

## Important Implementation Details

### Authentication Flow (Google OAuth)
- **Login**: GET `/auth/google` initiates OAuth flow, redirects to Google
- **Callback**: GET `/auth/google/callback` handles OAuth response
- **New Users**: Redirected to `/auth/setup` for username/avatar selection
- **Existing Users**: Logged in automatically and redirected to their subdomain
- **Complete Setup**: POST `/api/auth/complete-setup` finalizes new user registration
- **Logout**: GET `/api/logout` clears session and redirects to main domain via server-side redirect
- **Session detection**: `auth.get_current_user()` checks `request.session["user_id"]`

### Routing Logic
- **Main domain**: Shows landing page with random posts/users
- **Subdomains**: Shows specific user's blog with their latest posts
- **Admin pages**: Redirect to subdomain if accessed from main domain
- **Categories**: Two categories (Poezie, Proză scurtă) auto-classified by Mistral AI

### Database Initialization
- **schema.sql**: PostgreSQL schema with sample data
- **No migration scripts**: Do not add SQL migration scripts or runtime incremental schema patches. Put the complete current schema directly in `schema.sql`.
- **Database Initialization**: `run.py` drops and recreates the database from `schema.sql` by default. Set `CALIMARA_RESET_DATABASE=false` only when intentionally preserving the current database; no migrations are run.

## Code Patterns

### Never assign to `post.likes_count`
The Post model has a `@property likes_count` that auto-calculates. Always use the property, never assign to it.

### Domain references
Use environment variables (`MAIN_DOMAIN`, `SUBDOMAIN_SUFFIX`) instead of hardcoding `calimara.ro`. JavaScript gets these via `window.CALIMARA_CONFIG`.

### Template responses
Use `get_common_context()` helper and update with specific data rather than manually building context dictionaries.

### Subdomain detection
Check `request.state.is_subdomain` and `request.state.username` (set by SubdomainMiddleware) rather than parsing Host header manually.

## Development Notes
- do not try to use git, I will do that
- do not have css or js in the html files, all should be put in the appropriate files, in the static folder
- use only the latest libraries and APIs
- do not create database migration scripts; keep the whole PostgreSQL schema in `schema.sql` and let `run.py` rebuild from it when the DB is destroyed/reset
