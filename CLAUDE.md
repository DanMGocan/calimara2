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
- **Google OAuth 2.0** authentication using Authlib for secure user login
- **SQLAlchemy ORM** with modern `Mapped` annotations
- **Category system** in `app/categories.py` with hierarchical structure (main categories → subcategories → genres)
- **Environment-based configuration** via `.env` file with domain variables
- **Bootstrap + custom CSS** with Inter font

### Database Architecture
- **Users Table**: `username` (unique, lowercase), `email`, `google_id` (OAuth unique identifier), `subtitle`, `avatar_seed`, social media URLs (facebook_url, tiktok_url, instagram_url, x_url, bluesky_url), donation URLs (patreon_url, paypal_url, buymeacoffee_url)
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
# Test user information on Azure VM
# Email: sad@sad.sad, Username: gandurisilimbrici
# Authentication: Google OAuth (no local password)
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
- **GOOGLE_CLIENT_ID**: Google OAuth client ID from Google Cloud Console
- **GOOGLE_CLIENT_SECRET**: Google OAuth client secret from Google Cloud Console
- **GOOGLE_REDIRECT_URI**: OAuth callback URL (e.g., `https://calimara.ro/auth/google/callback`)

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
- **Categories**: Hierarchical system with main categories, subcategories, and genres

### Database Initialization
- **schema.sql**: Contains full database schema with sample data (uses google_id instead of password_hash)
- **initdb.py**: Executes schema.sql (no password hashing needed for OAuth)
- **Test user**: gandurisilimbrici/sad@sad.sad with test Google ID for testing
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

### Google OAuth Authentication (Latest)
- **Complete Authentication Overhaul**: Replaced local email/password authentication with Google OAuth 2.0
- **OAuth Flow**: Users authenticate via Google, then customize username and avatar in setup page
- **Database Changes**: Replaced `password_hash` with `google_id` in Users table
- **New Templates**: 
  - `auth_setup.html`: User customization page after Google authentication
  - Updated `register.html`: Simplified to only show Google OAuth option
  - Updated `base.html`: Replaced login modal with "Conectează-te cu Google" button
- **Security**: All authentication now handled by Google's secure OAuth system
- **User Experience**: Streamlined registration process with no local passwords to remember
- **Backend Implementation**: 
  - `app/google_oauth.py`: Complete OAuth handling module
  - New endpoints: `/auth/google`, `/auth/google/callback`, `/auth/setup`, `/api/auth/complete-setup`
  - Updated schemas for Google authentication in `app/schemas.py`

### Security Improvements
- **Cross-User Data Protection**: Fixed vulnerability where users could see other users' unread message counts when visiting different subdomains
- **Subdomain Verification**: Added proper authentication checks in JavaScript to prevent unauthorized data access
- **Session Security**: Enhanced session validation for subdomain-specific features

### UI/UX Improvements
- **Visual Consistency**: Improved button styling and link behavior across the platform
- **AJAX Category Filtering**: Replaced page reloads with smooth AJAX transitions on landing page
- **Background Opacity**: Adjusted background images for better readability
- **Clean Registration**: Simplified registration page to focus only on Google OAuth

### Gemini 1.5 Flash Content Moderation System (Latest)
- **AI-Powered Moderation**: Advanced content analysis using Google Gemini 1.5 Flash instead of Perspective API
- **Romanian Language Support**: Specialized prompts and cultural context awareness for Romanian content
- **Literary Context**: Understands artistic expression vs. harmful content in poetry, prose, and theater
- **Multi-Category Analysis**: Toxicity, harassment, hate speech, explicit content, dangerous content, Romanian profanity
- **Enhanced Detection**: Combines AI analysis with Romanian-specific pattern matching
- **Automated Decisions**: Auto-approve safe content, auto-reject harmful content, flag ambiguous content for review
- **Admin Control Panel**: God admin can review, approve, reject, or delete flagged content
- **Cultural Sensitivity**: Recognizes Romanian idioms, sarcasm, humor, and cultural references
- **Fail-Safe Design**: Defaults to approval if API fails to ensure content flow
- **Environment Variables**: `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-1.5-flash`, `ROMANIAN_CONTEXT_AWARE=True`

### God Admin and Moderation System
- **God Admin Account**: Dedicated admin account (`gocandan@gmail.com`) with full moderation control
- **Email-Based Access**: Admin access determined by email address matching `GOD_ADMIN_EMAIL`
- **Moderation Control Panel**: Complete interface at `/admin/moderation` for content review
- **Real-Time Statistics**: Dashboard showing pending, flagged, suspended counts and daily actions
- **Content Review**: Tabbed interface for pending content, flagged content, user management, analytics
- **User Management**: Search, suspend, and unsuspend user accounts with reasons
- **Navigation Integration**: Admin link appears in navigation only for god admin users

### Social Media and Donation Buttons
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

## Development Notes
- do not try to use git, I will do that
- do not have css or js in the html files, all should be put in the appropriate files, in the static folder
- use only the latest libraries and APIS