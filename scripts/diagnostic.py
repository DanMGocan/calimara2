#!/usr/bin/env python3
"""
Calimara System Diagnostic Script
Run this to check if all systems are working properly
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Run comprehensive system diagnostics"""
    print("=" * 60)
    print("CALIMARA SYSTEM DIAGNOSTICS")
    print("=" * 60)
    
    # Load environment variables
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ Environment file loaded: {env_file}")
    else:
        print(f"❌ Environment file not found: {env_file}")
        return False
    
    # Check critical environment variables
    critical_vars = {
        "GEMINI_API_KEY": "AI Moderation",
        "GOOGLE_CLIENT_ID": "Google OAuth",
        "GOOGLE_CLIENT_SECRET": "Google OAuth", 
        "MYSQL_USER": "Database",
        "MYSQL_PASSWORD": "Database",
        "SESSION_SECRET_KEY": "Sessions"
    }
    
    print("\n--- Environment Variables ---")
    for var, purpose in critical_vars.items():
        value = os.getenv(var)
        if value:
            if "SECRET" in var or "PASSWORD" in var or "KEY" in var:
                display = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display = value[:20] + "..." if len(value) > 20 else value
            print(f"✅ {var}: {display} ({purpose})")
        else:
            print(f"❌ {var}: NOT SET ({purpose})")
    
    # Test AI Moderation
    print("\n--- AI Moderation Test ---")
    try:
        from app import moderation
        import asyncio
        
        # Run AI test
        async def test_ai():
            result = await moderation.test_ai_moderation()
            return result
        
        result = asyncio.run(test_ai())
        
        if result.get("ai_working"):
            print("✅ AI Moderation: Working correctly")
            print(f"   - Toxic content detection: {result['toxic_content']['status']}")
            print(f"   - Normal content detection: {result['normal_content']['status']}")
        else:
            print(f"❌ AI Moderation: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ AI Moderation: Failed to test - {e}")
    
    # Test Database
    print("\n--- Database Test ---")
    try:
        from app.database import engine
        with engine.connect() as conn:
            result = conn.execute("SELECT 1").fetchone()
            if result:
                print("✅ Database: Connection successful")
                
                # Test if moderation_logs table exists
                try:
                    conn.execute("SELECT COUNT(*) FROM moderation_logs").fetchone()
                    print("✅ Database: moderation_logs table exists")
                except:
                    print("⚠️  Database: moderation_logs table missing (run initdb.py)")
            
    except Exception as e:
        print(f"❌ Database: Connection failed - {e}")
    
    print("\n" + "=" * 60)
    print("Diagnostic complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()