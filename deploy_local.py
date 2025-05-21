import subprocess
import sys

def run_command(command, cwd=None):
    """Runs a shell command and prints its output."""
    print(f"Executing: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
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

def deploy_local():
    """Performs local Git operations for deployment."""
    print("Starting local deployment automation...")

    # 1. Git add all changes
    if not run_command('git add .'):
        print("Failed to add files. Aborting.")
        sys.exit(1)

    # 2. Git commit
    commit_message = "Auto deployment"
    if not run_command(f'git commit -m "{commit_message}"'):
        print("Failed to commit changes. Aborting.")
        sys.exit(1)

    # 3. Git push
    if not run_command('git push origin main'):
        print("Failed to push changes to remote. Aborting.")
        sys.exit(1)

    print("Local deployment automation completed successfully.")

if __name__ == "__main__":
    deploy_local()
