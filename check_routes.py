#!/usr/bin/env python3
"""
Check which routes are registered in the FastAPI app
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

print("=" * 60)
print("REGISTERED ROUTES IN FASTAPI APP")
print("=" * 60)

# Get all routes
routes = []
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        routes.append((route.path, list(route.methods)))

# Sort by path
routes.sort(key=lambda x: x[0])

# Print moderation routes
print("\nMODERATION ROUTES:")
print("-" * 40)
moderation_count = 0
for path, methods in routes:
    if 'moderation' in path:
        print(f"{', '.join(methods):6} {path}")
        moderation_count += 1

if moderation_count == 0:
    print("❌ NO MODERATION ROUTES FOUND!")
else:
    print(f"\n✅ Found {moderation_count} moderation routes")

# Print all API routes
print("\n\nALL API ROUTES:")
print("-" * 40)
api_count = 0
for path, methods in routes:
    if path.startswith('/api/'):
        print(f"{', '.join(methods):6} {path}")
        api_count += 1

print(f"\n✅ Total API routes: {api_count}")
print("=" * 60)