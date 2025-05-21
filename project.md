# Project: Microblogging Platform for Romanian Writers

## Overview

We are building a lightweight microblogging platform for Romanian writers and poets. Each writer has a personalized blog hosted on a subdomain (e.g. `dangocan.calimara.ro`) where they can post poems, short texts, and interact with readers.
The platform will be developed using **FastAPI** and deployed on a **single Azure virtual machine** (Ubuntu-based). The application will use a **single centralized SQL database**, in MySQL, and **not separate SQLite files per user**.

---

## Key Features

### ✅ Subdomain-Based Writer Spaces
- Each writer has a subdomain like `username.calimara.ro`.
- All content is served dynamically based on the subdomain.
- The backend should detect and handle routing based on the `Host` header or similar.
- An unregistered user can visit all subdomains and the main domain. 
- There should be a Login button at the top where users that already have a blog can login. 
- Once they are logged in, they should be taken to their own blog.
- Every blog owner will have an Admin dashboard, where the owner can approve comments, edit or delete posts and see statistics (like number of visitors per blog and per post)
- Every post should have a Like button and social media icons where you can share it 

### 📝 Writer Accounts & Posts
- Writers can register and create their space.
- Each writer can:
  - Post poems or texts
  - Edit and delete their posts
  - View analytics (e.g. likes, views)
- Readers can:
  - Like poems
  - Comment on poems


### 🌍 Discover & Explore
- Main domain (`calimara.ro`) should act as a hub:
  - Have a button where visitors can apply to open their own space
  - Have a panel on the right with 10 random posts and 10 random blogs

---

## Technical Requirements

### Backend
- Built with **FastAPI**
- Subdomain detection using FastAPI middleware
- Centralized database (MySQL preferred)

### Database Schema (Simplified)
- create this as you see fit
- make sure there is a initdb.py script that restarts the database

### Hosting
- Single **Azure VM (Ubuntu)**, hosting:
  - FastAPI app (via Uvicorn + Gunicorn)
  - MySQL server
  - Nginx (for reverse proxy + TLS via Let's Encrypt)
  - I have a domain already, calimara.ro

### DNS & SSL
- Wildcard DNS configured for `*.calimara.ro`
- Nginx handles SSL termination and routes subdomain traffic to FastAPI

---

## MVP Goals

1. Subdomain routing working
2. User registration and login
3. Posting poems
4. Public viewing at subdomain
5. Main domain feed showing recent or trending posts

---

## Notes

- This is not a content-heavy platform (yet), so early stages can run fine on a single VM.
- The goal is simplicity and creative expression, not a full social network.
- Make sure there is a requirements.txt file

## User flow 

-- a user can land on my landing page at calimara.ro, where they will see a presentation of the product and have the ability to open their own instance. There is also a button for Login, where a blog owner can log in and this will lead them to their blog's Admin Dashboard.

-- after someone logs in, they should be redirected towards their own blog. In the Navbar they should see the Create Post, Admin buttons and a button to send them to calimara.ro

-- a user can land on someone's blog, for example dangocan.calimara.ro where they will see that user's last posts, 10 random post and 10 random blogs in side bar containers from all around the platform. On every blog, visible for unlogged users, there will be a button, "Deschide-ti si tu o calimara" that will allow these users to open their own microblog

## User Interface 

- the UI should feel lightweight, modern, and use a white and grey theme. It should also heavily use Bootstrap buttons. 