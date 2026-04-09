# Collaborative Drama (Piese de Teatru) — Design Spec

## Context

Calimara is a Romanian microblogging platform for writers. Users currently write individual posts (poems, short texts). This feature adds **collaborative drama writing** — users can co-author plays together in real time (async), each playing a character. This transforms Calimara from a solo writing platform into a collaborative creative space, adding a unique social dimension.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Location | Creator's subdomain | Dramas belong to the creator, consistent with posts |
| Collaboration model | Async turn-based | Any character posts anytime; simple, fits existing patterns |
| Visibility | Always public | Like a live performance — readers watch it being written |
| Audience interaction | Like + Comment | Consistent with post interactions |
| PDF export | Professional screenplay format | WeasyPrint HTML-to-PDF |
| Architecture | Dedicated module | Dramas are structurally different from posts |
| Notifications | New notification system | Bell icon + dropdown, reusable for future features |

---

## 1. Data Model

### 1.1 `dramas` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `user_id` | INTEGER | FK users(id) CASCADE, NOT NULL |
| `title` | VARCHAR(255) | NOT NULL |
| `slug` | VARCHAR(300) | UNIQUE, NOT NULL, indexed |
| `description` | TEXT | Setting/synopsis |
| `status` | VARCHAR(20) | CHECK ('in_progress', 'completed'), DEFAULT 'in_progress' |
| `is_open_for_applications` | BOOLEAN | DEFAULT TRUE |
| `view_count` | INTEGER | DEFAULT 0, indexed |
| `moderation_status` | VARCHAR(20) | CHECK ('approved', 'pending', 'rejected', 'flagged'), DEFAULT 'approved' |
| `moderation_reason` | TEXT | nullable |
| `toxicity_score` | DECIMAL(3,2) | nullable |
| `moderated_by` | INTEGER | FK users(id) SET NULL |
| `moderated_at` | TIMESTAMP | nullable |
| `created_at` | TIMESTAMP | DEFAULT NOW() |
| `updated_at` | TIMESTAMP | DEFAULT NOW(), trigger-updated |

Indexes: `slug`, `user_id`, `status`, `view_count`, `created_at`

### 1.2 `drama_characters` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `drama_id` | INTEGER | FK dramas(id) CASCADE, NOT NULL |
| `user_id` | INTEGER | FK users(id) CASCADE, NOT NULL |
| `character_name` | VARCHAR(100) | NOT NULL |
| `character_description` | TEXT | nullable |
| `is_creator` | BOOLEAN | DEFAULT FALSE |
| `joined_at` | TIMESTAMP | DEFAULT NOW() |

Unique constraints: `(drama_id, user_id)`, `(drama_id, character_name)`
Index: `drama_id`

### 1.3 `drama_acts` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `drama_id` | INTEGER | FK dramas(id) CASCADE, NOT NULL |
| `act_number` | INTEGER | NOT NULL |
| `title` | VARCHAR(255) | NOT NULL |
| `setting` | TEXT | Stage directions, environment |
| `status` | VARCHAR(20) | CHECK ('active', 'completed'), DEFAULT 'active' |
| `created_at` | TIMESTAMP | DEFAULT NOW() |

Unique constraint: `(drama_id, act_number)`
Index: `drama_id`
Business rule: only one `active` act per drama at a time (enforced in application layer)

### 1.4 `drama_replies` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `act_id` | INTEGER | FK drama_acts(id) CASCADE, NOT NULL |
| `character_id` | INTEGER | FK drama_characters(id) CASCADE, NOT NULL |
| `content` | TEXT | NOT NULL (the dialogue) |
| `stage_direction` | VARCHAR(500) | nullable, e.g. "(strigand)" |
| `position` | INTEGER | NOT NULL (ordering within act) |
| `created_at` | TIMESTAMP | DEFAULT NOW() |
| `updated_at` | TIMESTAMP | DEFAULT NOW(), trigger-updated |

Index: `(act_id, position)`

### 1.5 `drama_likes` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `drama_id` | INTEGER | FK dramas(id) CASCADE, NOT NULL |
| `user_id` | INTEGER | FK users(id) SET NULL, nullable |
| `ip_address` | VARCHAR(45) | nullable |
| `created_at` | TIMESTAMP | DEFAULT NOW() |

Unique constraints: `(drama_id, user_id)`, `(drama_id, ip_address)`

### 1.6 `drama_comments` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `drama_id` | INTEGER | FK dramas(id) CASCADE, NOT NULL |
| `user_id` | INTEGER | FK users(id) SET NULL, nullable |
| `author_name` | VARCHAR(255) | nullable (anonymous) |
| `content` | TEXT | NOT NULL |
| `moderation_status` | VARCHAR(20) | CHECK ('approved', 'pending', 'rejected', 'flagged'), DEFAULT 'approved' |
| `moderation_reason` | TEXT | nullable |
| `toxicity_score` | DECIMAL(3,2) | nullable |
| `moderated_by` | INTEGER | FK users(id) SET NULL |
| `moderated_at` | TIMESTAMP | nullable |
| `created_at` | TIMESTAMP | DEFAULT NOW() |

Index: `(drama_id, moderation_status)`

### 1.7 `drama_invitations` table

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `drama_id` | INTEGER | FK dramas(id) CASCADE, NOT NULL |
| `from_user_id` | INTEGER | FK users(id) CASCADE, NOT NULL |
| `to_user_id` | INTEGER | FK users(id) CASCADE, NOT NULL |
| `type` | VARCHAR(20) | CHECK ('invitation', 'application'), NOT NULL |
| `character_name` | VARCHAR(100) | nullable (proposed name) |
| `message` | TEXT | nullable |
| `status` | VARCHAR(20) | CHECK ('pending', 'accepted', 'rejected'), DEFAULT 'pending' |
| `created_at` | TIMESTAMP | DEFAULT NOW() |
| `responded_at` | TIMESTAMP | nullable |

Index: `(drama_id, to_user_id, status)`

### 1.8 `notifications` table (General Purpose)

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PK |
| `user_id` | INTEGER | FK users(id) CASCADE, NOT NULL |
| `type` | VARCHAR(50) | NOT NULL (e.g. 'drama_invitation', 'drama_application', 'drama_reply', 'new_message') |
| `title` | VARCHAR(255) | NOT NULL |
| `message` | TEXT | nullable |
| `link` | VARCHAR(500) | nullable (URL to navigate to) |
| `is_read` | BOOLEAN | DEFAULT FALSE |
| `metadata` | JSONB | DEFAULT '{}' |
| `created_at` | TIMESTAMP | DEFAULT NOW() |

Indexes: `(user_id, is_read, created_at)`, `user_id`

---

## 2. SQLAlchemy Models

New models in `app/models.py` following existing patterns (Mapped annotations, relationship with back_populates):

- **Drama**: relationships to User (owner), DramaCharacter, DramaAct, DramaLike, DramaComment, DramaInvitation. Hybrid property `likes_count`. Property `active_act`.
- **DramaCharacter**: relationships to Drama, User. Property `reply_count`.
- **DramaAct**: relationships to Drama, DramaReply. Property `replies_ordered` (sorted by position).
- **DramaReply**: relationships to DramaAct, DramaCharacter.
- **DramaLike**: relationships to Drama, User.
- **DramaComment**: relationships to Drama, User. Same moderation fields as Comment.
- **DramaInvitation**: relationships to Drama, from_user, to_user.
- **Notification**: relationship to User.

---

## 3. Pydantic Schemas

In `app/schemas.py`:

- `DramaCreate(title, description, character_name, character_description)`
- `DramaUpdate(title?, description?, is_open_for_applications?)` — status changes via dedicated endpoints
- `DramaResponse(id, title, slug, description, status, ..., characters, acts, likes_count)`
- `ActCreate(title, setting)`
- `ActUpdate(title?, setting?)`
- `ReplyCreate(content, stage_direction?)`
- `ReplyUpdate(content?, stage_direction?)`
- `ReplyReorder(reply_ids: list[int])` — ordered list of reply IDs
- `InvitationCreate(to_username, character_name?, message?)`
- `ApplicationCreate(character_name, character_description?, message?)`
- `InvitationRespond(status: 'accepted' | 'rejected')`
- `DramaCommentCreate(content, author_name?)`

---

## 4. Routes

### 4.1 API Routes — `app/routers/drama_routes.py`

**Drama CRUD:**
- `POST /api/dramas/` — Create drama (auth required)
- `GET /api/dramas/{slug}` — Get drama with acts, characters, replies
- `PUT /api/dramas/{slug}` — Update drama (owner only)
- `DELETE /api/dramas/{slug}` — Delete drama (owner only)

**Characters & Participation:**
- `POST /api/dramas/{slug}/invite` — Send invitation (owner only)
- `POST /api/dramas/{slug}/apply` — Apply to join (any auth user)
- `POST /api/dramas/{slug}/invitations/{id}/respond` — Accept/reject
- `DELETE /api/dramas/{slug}/characters/{id}` — Remove character (owner only)

**Acts:**
- `POST /api/dramas/{slug}/acts` — Create act (owner only)
- `PUT /api/dramas/{slug}/acts/{act_number}` — Update act (owner only)
- `POST /api/dramas/{slug}/acts/{act_number}/complete` — End act (owner only)

**Replies:**
- `POST /api/dramas/{slug}/acts/{act_number}/replies` — Add reply (participants only)
- `PUT /api/dramas/{slug}/replies/{id}` — Edit own reply
- `DELETE /api/dramas/{slug}/replies/{id}` — Delete reply (owner or author)
- `PUT /api/dramas/{slug}/replies/reorder` — Reorder (owner only)

**Audience:**
- `POST /api/dramas/{slug}/likes` — Like/unlike
- `POST /api/dramas/{slug}/comments` — Comment
- `GET /api/dramas/{slug}/export/pdf` — PDF export

### 4.2 API Routes — `app/routers/notification_routes.py`

- `GET /api/notifications` — Get notifications (paginated)
- `GET /api/notifications/unread-count` — Count for badge
- `PUT /api/notifications/{id}/read` — Mark read
- `PUT /api/notifications/read-all` — Mark all read

### 4.3 Page Routes — additions to `app/routers/pages.py`

- `GET /piese` — Drama listing (subdomain: user's dramas; main domain: discovery)
- `GET /piese/creeaza` — Create drama form
- `GET /piese/{slug}` — Drama reading page
- `GET /piese/{slug}/gestioneaza` — Drama management (owner only)
- `GET /notificari` — Notifications page

---

## 5. Templates

### 5.1 New Templates

- `templates/drama/list.html` — Grid of drama cards (title, creator, status badge, character count, like count)
- `templates/drama/detail.html` — The main reading/participation view:
  - Header: title, creator, description, character list
  - Acts as expandable sections
  - Replies formatted as screenplay dialogue
  - Reply form at bottom of active act (for participants)
  - Like/comment section below
- `templates/drama/create.html` — Form: title, description, own character name/description
- `templates/drama/manage.html` — Owner dashboard:
  - Act management (create, end current act)
  - Character list with remove buttons
  - Pending invitations/applications
  - Reply moderation (reorder, delete)
- `templates/drama/pdf_template.html` — HTML template for WeasyPrint:
  - Cover page with Calimara.ro branding
  - Character page
  - Act pages in screenplay format
- `templates/includes/notification_dropdown.html` — Bell icon partial for base.html navbar

### 5.2 Modified Templates

- `templates/base.html` — Add notification bell icon in navbar, add "Piese" nav link
- `templates/blog.html` — Add drama section showing user's dramas
- `templates/index.html` — Add featured/recent dramas section on main landing

---

## 6. Static Assets

- `static/js/drama.js` — Drama page interactions (reply submission, invitation handling, act management, reorder via drag-and-drop)
- `static/js/notifications.js` — Notification dropdown (fetch unread, mark read, polling for updates)
- `static/css/style.css` — New drama-specific styles (screenplay formatting, character cards, act sections, curtain animation)

---

## 7. Key Interaction Flows

### 7.1 Creating a Drama
1. User navigates to `/piese/creeaza` on their subdomain
2. Fills form: title, description (setting/synopsis), their character name + description
3. POST to `/api/dramas/` creates drama + first character (is_creator=true)
4. Redirected to `/piese/{slug}/gestioneaza` to create first act

### 7.2 Invitation Flow
1. Owner enters username on manage page, sends invitation
2. System creates `drama_invitations` row + `notifications` row for recipient
3. Recipient sees bell badge, clicks notification, sees invitation details
4. Accepts: `drama_characters` row created, notification sent to owner
5. Rejects: owner notified

### 7.3 Application Flow
1. User visits drama detail page, clicks "Aplica"
2. Modal: enter character name, description, optional message
3. System creates `drama_invitations` (type=application) + notification for owner
4. Owner reviews on manage page, accepts/rejects

### 7.4 Writing Replies
1. Participant visits drama detail page, scrolls to active act
2. Reply form: stage direction field (optional) + dialogue content field
3. POST creates reply with next position number
4. Reply appears at bottom of act
5. All other participants get notifications of new replies

### 7.5 Owner Controls
- **Reorder replies**: Drag-and-drop on manage page updates `position` values
- **Delete replies**: Owner clicks delete on any reply
- **End act**: Button marks current act as completed
- **New act**: Form to create next act with title + setting
- **Complete drama**: Marks entire drama as completed, triggers "Cortina" display

### 7.6 PDF Export
1. User clicks "Exporta PDF" on drama detail page
2. Server renders `pdf_template.html` with drama data
3. WeasyPrint converts HTML to PDF
4. PDF returned as download with filename: `{drama_slug}.pdf`

---

## 8. Fun Features

1. **Drama Stats**: Character count, total replies, acts count, view count, duration from first to last reply
2. **Character Profile Cards**: Each character shows player username (linked to their blog), character description, reply count within the drama
3. **"Cortina" (Curtain Call)**: CSS animation when a drama is completed — a red curtain draws closed, then reopens showing all participants with their characters. Visible on the detail page.
4. **Drama Discovery**: `calimara.ro/piese` shows featured and recent dramas across the platform with filters (in progress, completed, most liked)
5. **Theater Mask Badge**: Users who've participated in completed dramas get a small mask icon on their blog profile (visible on `blog.html`)

---

## 9. Authorization Rules

| Action | Who can do it |
|--------|---------------|
| Create drama | Any authenticated user |
| Edit drama details | Drama owner |
| Delete drama | Drama owner |
| Create/end acts | Drama owner |
| Send invitations | Drama owner |
| Apply to join | Any auth user (if open for applications) |
| Accept/reject invitations | Invitation recipient |
| Accept/reject applications | Drama owner |
| Add replies | Drama participants (characters) in active act only |
| Edit reply | Reply author |
| Delete reply | Drama owner or reply author |
| Reorder replies | Drama owner |
| Like/comment | Any user (including anonymous for likes) |
| Export PDF | Anyone |
| View drama | Anyone (always public) |

---

## 10. New Dependency

- **WeasyPrint** — HTML-to-PDF conversion for professional screenplay export. Add to `requirements.txt`. WeasyPrint requires system dependencies (`libpango`, `libcairo`) which should be documented.

---

## 11. Files to Create/Modify

### New Files
- `app/routers/drama_routes.py` — Drama API routes
- `app/routers/notification_routes.py` — Notification API routes
- `templates/drama/list.html`
- `templates/drama/detail.html`
- `templates/drama/create.html`
- `templates/drama/manage.html`
- `templates/drama/pdf_template.html`
- `templates/includes/notification_dropdown.html`
- `static/js/drama.js`
- `static/js/notifications.js`

### Modified Files
- `app/models.py` — Add Drama, DramaCharacter, DramaAct, DramaReply, DramaLike, DramaComment, DramaInvitation, Notification models
- `app/schemas.py` — Add drama and notification schemas
- `app/crud.py` — Add drama and notification CRUD functions
- `app/main.py` — Include new routers
- `schema.sql` — Add all new tables, indexes, triggers, sample data
- `scripts/initdb.py` — Update table drop order to include new tables
- `templates/base.html` — Add notification bell, "Piese" nav link
- `templates/blog.html` — Add drama section
- `templates/index.html` — Add drama discovery section
- `static/css/style.css` — Drama styles, screenplay formatting, curtain animation
- `requirements.txt` — Add WeasyPrint

---

## 12. Verification Plan

1. **Database**: Run `python scripts/initdb.py` — verify all new tables created with correct constraints
2. **Create drama**: Log in, create a drama with character — verify it appears on subdomain `/piese`
3. **Invitation flow**: Create second user, send invitation, verify notification appears, accept, verify character created
4. **Application flow**: With open applications, apply as third user, verify owner sees application, accept
5. **Writing flow**: Create act, add replies from multiple characters, verify ordering, test reorder
6. **Owner controls**: Delete a reply, end act, create new act, complete drama
7. **Audience**: Like and comment on a drama as non-participant
8. **PDF export**: Export a drama with multiple acts, verify formatting and Calimara branding
9. **Notifications**: Verify bell badge count updates, mark as read works
10. **Discovery**: Check main domain `/piese` shows dramas from across platform
11. **Curtain animation**: Complete a drama, verify the "Cortina" animation displays
