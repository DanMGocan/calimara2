#!/usr/bin/env python3
"""
Simple script to clear browser sessions by restarting the application.
This helps when you have persistent login sessions that need to be cleared.
"""

import os
import sys

def clear_sessions():
    """Clear all session data by removing session files if they exist."""
    print("🔄 Clearing session data...")
    
    # Session data is typically stored in memory for FastAPI SessionMiddleware
    # But we can clear any temporary files that might exist
    temp_dirs = [
        os.path.join(os.getcwd(), "sessions"),
        os.path.join(os.getcwd(), "tmp"),
        "/tmp/calimara_sessions"
    ]
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                print(f"✅ Cleared session directory: {temp_dir}")
            except Exception as e:
                print(f"⚠️  Could not clear {temp_dir}: {e}")
    
    print("✅ Session clearing complete!")
    print("💡 To fully clear sessions:")
    print("   1. Restart your FastAPI application")
    print("   2. Clear your browser cookies for calimara.ro")
    print("   3. Use browser's incognito/private mode for testing")

if __name__ == "__main__":
    clear_sessions()
