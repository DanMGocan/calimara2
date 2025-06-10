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
- **Users Table**: `username` (unique, lowercase), `email`, `password_hash`, `subtitle`
- **Posts Table**: `user_id`, `title`, `content`, `category`, `genre`
- **Comments Table**: Supports both authenticated and anonymous comments with approval system
- **Likes Table**: Supports both user-based and IP-based likes
- **Key Relationship**: Post model has `@property likes_count` that auto-calculates from relationship

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize/reset database (WARNING: wipes all data)
python scripts/initdb.py
```

### Local Development
```bash
# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test specific user credentials
# Email: sad@sad.sad, Password: 123, Username: gandurisilimbrici
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