# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Calimara is a Romanian microblogging platform for writers and poets. Each writer gets their own subdomain (e.g., `username.calimara.ro`) where they can post poems, short texts, and interact with readers. The main domain (`calimara.ro`) serves as a discovery hub showing random posts and blogs.

## Key Architecture

### Subdomain-Based Multi-Tenancy
- **Single FastAPI application** serves all subdomains dynamically
- **SubdomainMiddleware** (in `app/main.py`) detects subdomains via Host header and sets `request.state.is_subdomain` and `request.state.username`
- **Single MySQL database** with user-scoped data (no separate databases per user)
- **Session sharing** across subdomains using `domain=SUBDOMAIN_SUFFIX` in SessionMiddleware

### Core Components
- **FastAPI app** with Jinja2 templates and session-based auth (no JWT)
- **SQLAlchemy ORM** with modern `Mapped` annotations
- **Category system** in `app/categories.py` with hierarchical structure (main categories → subcategories → genres)
- **Environment-based configuration** via `.env` file with domain variables
- **Bootstrap + custom CSS** with Inter font

### Database Architecture
- **Users Table**: `username` (unique, lowercase), `email`, `password_hash`, `subtitle`, `avatar_seed`, social media URLs (facebook_url, tiktok_url, instagram_url, x_url, bluesky_url), donation URLs (patreon_url, paypal_url, buymeacoffee_url)
- **Posts Table**: `user_id`, `title`, `slug` (SEO-friendly URLs), `content`, `category`, `genre`, `view_count`
- **Comments Table**: Supports both authenticated and anonymous comments with approval system
- **Likes Table**: Supports both user-based and IP-based likes
- **Tags Table**: Post tagging system with autocomplete suggestions
- **Key Relationship**: Post model has `@property likes_count` that auto-calculates from relationship

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize/reset database (WARNING: wipes all data)
python scripts/initdb.py
```

### Testing Environment
**⚠️ IMPORTANT: Local testing is not available for this project.**
- All testing must be done on the Azure virtual machine
- Use `python deploy_vm.py` to deploy and test changes
- Local development server cannot properly test subdomain functionality

```bash
# Test specific user credentials on Azure VM
# Email: sad@sad.sad, Password: 123, Username: gandurisilimbrici
# Access via: https://gandurisilimbrici.calimara.ro
```

### VM Deployment
```bash
# Deploy to Azure VM (git pull + restart services + reset DB)
python deploy_vm.py

# Manual service operations on VM
sudo systemctl restart calimara
sudo systemctl status calimara
sudo journalctl -u calimara -f
```

## Critical Configuration

### Environment Variables (.env)
- **MAIN_DOMAIN**: Main domain (e.g., `calimara.ro`)
- **SUBDOMAIN_SUFFIX**: Subdomain pattern (e.g., `.calimara.ro`)
- **SESSION_SECRET_KEY**: Session encryption key
- **MYSQL_* variables**: Database connection details

### Template Context Helper
Use `get_common_context(request, current_user)` for consistent template variables including domain configuration that's passed to JavaScript via `window.CALIMARA_CONFIG`.

## Development Philosophy

### Server-Side Processing Preference
**⚠️ IMPORTANT: Minimize JavaScript usage and prefer server-side processing whenever possible.**
- Use FastAPI endpoints and server-side redirects over client-side routing
- Prefer Jinja2 template rendering over dynamic JavaScript DOM manipulation  
- Keep JavaScript limited to essential interactions (form submissions, modals, UI enhancements)
- Use HTML forms with server-side processing rather than complex client-side logic
- When JavaScript is necessary, keep it simple and progressively enhanced

## Important Implementation Details

### Authentication Flow
- **Login**: POST `/api/token` sets `request.session["user_id"]` and redirects to user's subdomain
- **Logout**: GET `/api/logout` clears session and redirects to main domain via server-side redirect
- **Session detection**: `auth.get_current_user()` checks `request.session["user_id"]`

### Routing Logic
- **Main domain**: Shows landing page with random posts/users
- **Subdomains**: Shows specific user's blog with their latest posts
- **Admin pages**: Redirect to subdomain if accessed from main domain
- **Categories**: Hierarchical system with main categories, subcategories, and genres

### Database Initialization
- **schema.sql**: Contains full database schema with sample data
- **initdb.py**: Executes schema.sql and replaces placeholder password with bcrypt hash
- **Test user**: gandurisilimbrici/sad@sad.sad/123 for testing
- **Database Reinitialization**: Database will be reinitalized after every update, no need to create migrations. It will use the schema.sql for the general layout of the DB and init_db.py to process the creation of the database.

### Deployment Architecture
- **Azure VM**: Single Ubuntu VM running FastAPI + MySQL + Nginx
- **Systemd service**: `calimara.service` runs gunicorn
- **Wildcard DNS**: `*.calimara.ro` points to same IP
- **deploy_vm.py**: Automated deployment script that wipes database on each deploy

## Code Patterns

### Never assign to `post.likes_count`
The Post model has a `@property likes_count` that auto-calculates. Always use the property, never assign to it.

### Domain references
Use environment variables (`MAIN_DOMAIN`, `SUBDOMAIN_SUFFIX`) instead of hardcoding `calimara.ro`. JavaScript gets these via `window.CALIMARA_CONFIG`.

### Template responses
Use `get_common_context()` helper and update with specific data rather than manually building context dictionaries.

### Subdomain detection
Check `request.state.is_subdomain` and `request.state.username` (set by SubdomainMiddleware) rather than parsing Host header manually.

## Recent Features

### Social Media and Donation Buttons (Latest)
- **User Profile Enhancement**: Added 8 new URL fields to User model for social media and donation links
- **Admin Management**: Complete interface in admin dashboard for managing social links
- **Frontend Display**: Social buttons appear on both blog.html and post_detail.html templates
- **Visual Design**: Platform-specific colors (Facebook blue, Instagram gradient, etc.) with disabled states
- **API Integration**: PUT `/api/user/me` endpoint handles social link updates
- **Template Structure**: 
  - Social section: "Urmărește-mă pe sociale:" (Facebook, TikTok, Instagram, X, BlueSky)
  - Donation section: "Sprijină-mă, de ce nu?" (Patreon, PayPal, Buy Me a Coffee)
- **Behavior**: Buttons only appear when URLs are set, all links open in new tabs

### SEO-Friendly URLs and Post Tracking
- **Slug Generation**: Automatic SEO-friendly URLs from post titles with Romanian character handling
- **View Tracking**: Post view count incrementation for analytics
- **Unique Slugs**: Automatic slug conflict resolution with counter suffixes