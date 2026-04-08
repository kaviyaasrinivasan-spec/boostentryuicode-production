import subprocess
import os
import sys

# --- CONFIGURATION ---
container_id = "142b870088e8"
container_docs_path = "/app/uploaded_docs"
local_docs_path = r"/root/boostentryai/docs"
# ----------------------

def run_command(cmd):
    """Run a shell command and show output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error running: {cmd}")
            print(result.stderr)
            sys.exit(1)
        else:
            print(f"✅ {cmd}")
            if result.stdout.strip():
                print(result.stdout.strip())
    except Exception as e:
        print(f"⚠️ Exception: {e}")
        sys.exit(1)

def main():
    print("\n📁 Checking/creating local directory...")
    os.makedirs(local_docs_path, exist_ok=True)

    print("\n📦 Copying files from container to local system...")
    copy_command = f'docker cp {container_id}:{container_docs_path}/. "{local_docs_path}"'
    run_command(copy_command)

    print("\n🧹 Deleting only files inside container folder (keeping folder)...")
    delete_command = f'docker exec {container_id} sh -c "rm -rf {container_docs_path}/*"'
    run_command(delete_command)

    print("\n✅ Done! Files copied to local and deleted inside container (folder preserved).\n")

if __name__ == "__main__":
    main()
