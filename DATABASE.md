# Calimara Database Schema

This document describes the database schema for the Calimara microblogging platform.

## Quick Setup

To initialize the database, run:

```bash
# From the project root
python3 scripts/initdb.py
```

Or from the scripts directory:

```bash
cd scripts
python3 initdb.py
```

## Schema Files

- **`schema.sql`** - Complete database schema with sample data
- **`scripts/initdb.py`** - Python script that loads and executes the schema

## Database Structure

### Tables

1. **`users`** - Writer accounts
   - Stores usernames, emails, password hashes
   - Each user gets a subdomain (e.g., `username.calimara.ro`)

2. **`posts`** - Literary works
   - Poems, prose, essays, journal entries
   - Categorized by type and genre
   - Belongs to a user

3. **`comments`** - Reader comments
   - Can be from registered users or anonymous
   - Requires approval from post owner
   - Moderation support

4. **`likes`** - Post likes/hearts
   - Supports both registered and anonymous users
   - Prevents duplicate likes per user/IP

### Categories

The platform supports several literary categories:

- **Poezie** (Poetry): poezie_lirica, poezie_epica, poezie_satirica, poezie_experimentala
- **Proză** (Prose): povestiri_scurte, nuvele, romane, flash_fiction
- **Teatru** (Theater): teatru_clasic, monologuri, drama_contemporana
- **Eseu** (Essay): eseuri_personale, eseuri_filosofice
- **Critică Literară**: critica_literara, recenzii_carte
- **Jurnal** (Journal): jurnale_personale, confesiuni
- **Scrisoare** (Letters): scrisori_personale, scrisori_deschise
- **Literatură Experimentală**: proza_poetica, literatura_digitala, forme_hibride

## Sample Data

The schema includes sample data for testing:

### Test User
- **Username**: `gandurisilimbrici`
- **Email**: `sad@sad.sad`
- **Password**: `123`
- **Blog URL**: `gandurisilimbrici.calimara.ro`

### Sample Posts
- Various literary works across different categories
- Sample comments and likes for testing

## Environment Variables

The database connection can be configured with environment variables:

```bash
MYSQL_USER=admin
MYSQL_PASSWORD=your_password
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=calimara_db
```

## Database Features

- **UTF-8 Support**: Full Unicode support for Romanian text
- **Foreign Key Constraints**: Data integrity enforcement
- **Indexes**: Optimized for common queries
- **Moderation**: Comment approval system
- **Anonymous Support**: Likes and comments from unregistered users

## Deployment Notes

- The `initdb.py` script is run automatically during VM deployment
- **WARNING**: This will wipe all existing data
- For production, consider using database migration tools instead

## Schema Modifications

To modify the database schema:

1. Edit `schema.sql`
2. Test with `python3 scripts/initdb.py`
3. Deploy changes with the deployment script

The schema file is version controlled and should reflect the current production structure.