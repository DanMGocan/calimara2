import subprocess
import sys
import os
from dotenv import load_dotenv

# Define the application directory on the VM
APP_DIR = "/home/dangocan_1/calimara2"
VENV_PYTHON = os.path.join(APP_DIR, "venv", "bin", "python3")
INITDB_SCRIPT = os.path.join(APP_DIR, "scripts", "initdb.py")
GUNICORN_SERVICE = "calimara" # Name of the systemd service

def run_command(command, cwd=None, shell=True):
    """Runs a shell command and prints its output."""
    print(f"Executing: {command}")
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        print("STDOUT:\n", result.stdout)
        if result.stderr:
            print("STDERR:\n", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

def check_environment_and_dependencies():
    """Check environment variables and critical dependencies"""
    print("\n" + "="*60)
    print("ENVIRONMENT AND DEPENDENCY CHECKS")
    print("="*60)
    
    # Load environment variables
    env_file = os.path.join(APP_DIR, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ .env file found at: {env_file}")
    else:
        print(f"❌ .env file not found at: {env_file}")
        return False
    
    # Check critical environment variables
    critical_vars = {
        "GEMINI_API_KEY": "AI Moderation",
        "GOOGLE_CLIENT_ID": "Google OAuth",
        "GOOGLE_CLIENT_SECRET": "Google OAuth",
        "MYSQL_USER": "Database Connection",
        "MYSQL_PASSWORD": "Database Connection",
        "SESSION_SECRET_KEY": "Session Security"
    }
    
    print("\n--- Environment Variables ---")
    all_vars_ok = True
    for var, purpose in critical_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "SECRET" in var or "PASSWORD" in var or "KEY" in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value[:20] + "..." if len(value) > 20 else value
            print(f"✅ {var}: {display_value} ({purpose})")
        else:
            print(f"❌ {var}: NOT SET ({purpose})")
            all_vars_ok = False
    
    # Check Python dependencies
    print("\n--- Python Dependencies ---")
    dependencies = [
        ("fastapi", "Web Framework"),
        ("google.generativeai", "AI Moderation"),
        ("sqlalchemy", "Database ORM"),
        ("authlib", "OAuth Authentication"),
        ("jinja2", "Template Engine")
    ]
    
    for module, purpose in dependencies:
        try:
            __import__(module)
            print(f"✅ {module}: Available ({purpose})")
        except ImportError:
            print(f"❌ {module}: NOT AVAILABLE ({purpose})")
            all_vars_ok = False
    
    # Test AI Moderation Configuration
    print("\n--- AI Moderation Test ---")
    try:
        # Test import with environment loaded
        from app import moderation
        
        # Check configuration
        gemini_key = os.getenv("GEMINI_API_KEY")
        moderation_enabled = os.getenv("MODERATION_ENABLED", "True").lower() == "true"
        
        if gemini_key and moderation_enabled:
            print("✅ AI Moderation: Properly configured")
        elif not gemini_key:
            print("❌ AI Moderation: Missing GEMINI_API_KEY")
            all_vars_ok = False
        elif not moderation_enabled:
            print("⚠️  AI Moderation: Disabled in configuration")
        
    except Exception as e:
        print(f"❌ AI Moderation: Import failed - {e}")
        all_vars_ok = False
    
    # Test Database Connection
    print("\n--- Database Connection Test ---")
    try:
        from app.database import engine
        with engine.connect() as conn:
            result = conn.execute("SELECT 1").fetchone()
            if result:
                print("✅ Database: Connection successful")
            else:
                print("❌ Database: Connection failed")
                all_vars_ok = False
    except Exception as e:
        print(f"❌ Database: Connection failed - {e}")
        all_vars_ok = False
    
    print("\n" + "="*60)
    if all_vars_ok:
        print("✅ ALL CHECKS PASSED - System ready for deployment")
    else:
        print("❌ SOME CHECKS FAILED - Review issues above")
    print("="*60)
    
    return all_vars_ok

def deploy_vm():
    """Performs VM-side deployment operations."""
    print("Starting VM deployment automation...")

    # 0. Run comprehensive diagnostics BEFORE deployment
    print("\n--- Pre-deployment diagnostics ---")
    print("Running comprehensive system diagnostics...")
    if not run_command(f'{VENV_PYTHON} scripts/diagnostic.py', cwd=APP_DIR):
        print("❌ Diagnostic script failed. Please check the issues above.")
        response = input("Continue deployment anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    else:
        print("✅ Pre-deployment diagnostics completed.")

    # 1. Git pull latest changes
    print("\n--- Performing git pull ---")
    if not run_command('git pull', cwd=APP_DIR):
        print("Failed to pull latest changes. Aborting VM deployment.")
        sys.exit(1)

    # 2. Restart Gunicorn service
    print("\n--- Restarting Gunicorn service ---")
    # Use sudo for systemctl commands
    if not run_command(f'sudo systemctl restart {GUNICORN_SERVICE}', shell=True):
        print(f"Failed to restart {GUNICORN_SERVICE} service. Aborting VM deployment.")
        sys.exit(1)
    print(f"{GUNICORN_SERVICE} service restarted.")

    # 3. Reload Systemd daemon and restart Nginx
    print("\n--- Reloading Systemd daemon and restarting Nginx ---")
    if not run_command('sudo systemctl daemon-reload', shell=True):
        print("Failed to reload Systemd daemon. Continuing, but may need manual intervention.")
    if not run_command('sudo systemctl restart nginx', shell=True):
        print("Failed to restart Nginx. Aborting VM deployment.")
        sys.exit(1)
    print("Nginx restarted.")

    # 3. Run initdb.py script
    # IMPORTANT: The user has explicitly requested initdb.py to be run on each deploy.
    # This means the database will be wiped and recreated on every deployment,
    # resulting in loss of all existing data (users, posts, comments, likes).
    # This is suitable for testing environments where a fresh database is desired.
    # For production, consider using database migration tools (e.g., Alembic).
    print("\n--- Running initdb.py (as per user request - WARNING: Data will be wiped!) ---")
    # Ensure the script is run with the correct Python interpreter from the venv
    if not run_command(f'{VENV_PYTHON} {INITDB_SCRIPT}', cwd=APP_DIR, shell=True):
        print("Failed to run initdb.py. Aborting VM deployment.")
        sys.exit(1)
    print("initdb.py executed successfully.")

    # 4. Post-deployment diagnostics
    print("\n--- Post-deployment diagnostics ---")
    print("Running post-deployment system diagnostics...")
    if not run_command(f'{VENV_PYTHON} scripts/diagnostic.py', cwd=APP_DIR):
        print("⚠️  Post-deployment diagnostics failed. Service may not work properly.")
    else:
        print("✅ Post-deployment diagnostics completed.")

    # 5. Check service status
    print("\n--- Service Status Check ---")
    run_command(f'sudo systemctl status {GUNICORN_SERVICE} --no-pager -l')

    print("\nVM deployment automation completed successfully.")

if __name__ == "__main__":
    deploy_vm()
