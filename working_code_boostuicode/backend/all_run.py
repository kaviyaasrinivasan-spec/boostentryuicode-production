#!/usr/bin/env python3
"""
all_run.py
Start Flask (backend) and React (frontend) together, stream logs, and cleanly stop on Ctrl+C.

Place this in the project root (the same folder that contains app.py and package.json for the React app).
"""

import os
import sys
import subprocess
import threading
import shutil
import signal
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# If your React app lives in the same folder, keep as ROOT_DIR; change if it's different.
API_DIR = ROOT_DIR
REACT_DIR = ROOT_DIR

# Determine python executable (use current interpreter so venv is honored)
PYTHON_EXE = sys.executable  # typically venv\Scripts\python.exe when venv is active

# Find npm executable (handles npm.cmd on Windows)
def find_npm():
    # try typical names
    for name in ("npm", "npm.cmd"):
        p = shutil.which(name)
        if p:
            return p
    return None

NPM_EXE = find_npm()

# Commands
FLASK_CMD = [PYTHON_EXE, "app.py"]
REACT_CMD = [NPM_EXE, "run", "dev"] if NPM_EXE else None

# Windows process flags (so we can send CTRL_BREAK_EVENT)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

def start_process(cmd, cwd, env=None, name="PROC"):
    if cmd is None:
        raise RuntimeError(f"Command for {name} is None")
    print(f"▶ Starting {name}:")
    print("  Command:", " ".join(cmd))
    print("  Working dir:", cwd)
    try:
        # On Windows, create new process group to allow CTRL_BREAK_EVENT
        creationflags = CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        return proc
    except FileNotFoundError as e:
        print(f"❌ Failed to start {name}: {e}")
        return None

def stream_output(prefix, stream):
    """Read lines from stream and print them with prefix."""
    try:
        for line in iter(stream.readline, ""):
            if line:
                sys.stdout.write(f"{prefix} {line}")
        stream.close()
    except Exception as e:
        print(f"{prefix} Reader error: {e}")

def stop_process(proc, name="PROC"):
    if not proc:
        return
    try:
        if proc.poll() is None:
            print(f"🛑 Stopping {name} (pid {proc.pid})...")
            # Prefer sending CTRL_BREAK_EVENT on Windows for graceful stop if possible
            if os.name == "nt":
                try:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                    # give it a moment
                    time.sleep(1)
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        proc.kill()
            else:
                proc.terminate()
            # wait for it to exit
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"⚠️ {name} did not stop in time — killing.")
                proc.kill()
    except Exception as e:
        print(f"Error stopping {name}: {e}")

def main():
    if NPM_EXE is None:
        print("❌ npm executable not found on PATH. Please install Node/npm or ensure npm is on PATH.")
        print("   On Windows, ensure npm.cmd is available (Node.js install).")
        # We won't exit here — we still may want to run Flask only, but user asked to run both.
        # Return nonzero to indicate partial failure.
        # return 1

    print("🚀 Starting fullstack (Flask + React)")
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"API_DIR: {API_DIR}")
    print(f"REACT_DIR: {REACT_DIR}")
    print(f"PYTHON_EXE: {PYTHON_EXE}")
    print(f"NPM_EXE: {NPM_EXE}\n")

    # Optionally inherit environment, but ensure PATH is passed
    env = os.environ.copy()

    flask_proc = start_process(FLASK_CMD, API_DIR, env=env, name="FLASK")
    react_proc = None
    if NPM_EXE:
        react_proc = start_process(REACT_CMD, REACT_DIR, env=env, name="REACT")
    else:
        print("⚠️ React not started because npm was not found.")

    # Start threads to stream outputs
    threads = []
    if flask_proc and flask_proc.stdout:
        t = threading.Thread(target=stream_output, args=("🟢 [FLASK]", flask_proc.stdout), daemon=True)
        t.start()
        threads.append(t)
    if react_proc and react_proc.stdout:
        t = threading.Thread(target=stream_output, args=("🟣 [REACT]", react_proc.stdout), daemon=True)
        t.start()
        threads.append(t)

    try:
        # Wait until one of the processes exits, or until KeyboardInterrupt
        while True:
            # If both processes are None, nothing to do
            if not flask_proc and not react_proc:
                print("No processes started. Exiting.")
                break

            # If any process exited, break loop to stop the other and exit.
            if flask_proc and flask_proc.poll() is not None:
                print(f"🟢 [FLASK] exited with code {flask_proc.returncode}")
                break
            if react_proc and react_proc.poll() is not None:
                print(f"🟣 [REACT] exited with code {react_proc.returncode}")
                break

            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n⏹️ Ctrl+C received — shutting down...")

    finally:
        # Stop both
        stop_process(react_proc, name="REACT")
        stop_process(flask_proc, name="FLASK")

        # give threads a moment to flush
        time.sleep(0.3)
        print("✅ Both servers stopped. Goodbye.")

if __name__ == "__main__":
    main()
