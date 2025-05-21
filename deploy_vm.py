import subprocess
import sys
import os

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

def deploy_vm():
    """Performs VM-side deployment operations."""
    print("Starting VM deployment automation...")

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

    # Note: initdb.py is designed to reset the DB. It should only be run for initial setup.
    # For ongoing deployments, use database migration tools (like Alembic) to preserve data.
    # We are removing it from automated deployment to prevent data loss.
    print("\n--- Skipping initdb.py (run manually for initial setup) ---")

    print("\nVM deployment automation completed successfully.")

if __name__ == "__main__":
    deploy_vm()
