import os
import subprocess
import signal
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
WORKER_PROCS = []
API_PROC = None


def activate_venv():
    """Ensure Python runs from the project's virtual environment."""
    if sys.platform == "win32":
        venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


PYTHON_EXEC = activate_venv()


def start_process(cmd, env=None):
    """Start a subprocess and return the process object."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        env=env or os.environ.copy(),
    )
    return proc


def cleanup(signum=None, frame=None):
    print("\nStopping all processes...")

    if API_PROC and API_PROC.poll() is None:
        API_PROC.terminate()

    for proc in WORKER_PROCS:
        if proc.poll() is None:
            proc.terminate()

    sys.exit(0)


def main():
    global API_PROC

    os.chdir(ROOT_DIR)

    # macOS fork safety env
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    print("Starting API server...")
    API_PROC = start_process([PYTHON_EXEC, "server.py"])

    print("Starting resume parsing worker...")
    env = os.environ.copy()
    env["QUEUES"] = "resume_parsing"
    WORKER_PROCS.append(start_process([PYTHON_EXEC, "-m", "workers.worker"], env))

    print("Starting resume scoring worker...")
    env = os.environ.copy()
    env["QUEUES"] = "resume_scoring"
    WORKER_PROCS.append(start_process([PYTHON_EXEC, "-m", "workers.worker"], env))

    print("Starting general worker...")
    env = os.environ.copy()
    env["QUEUES"] = "jd_extraction,candidate_extraction"
    WORKER_PROCS.append(start_process([PYTHON_EXEC, "-m", "workers.worker"], env))

    print("Starting Assessment/Notification Worker (arq)...")
    WORKER_PROCS.append(start_process([PYTHON_EXEC, "-m", "arq", "workers_async.worker.WorkerSettings"]))
    
    print(
        f"API pid={API_PROC.pid} | Worker pids={[p.pid for p in WORKER_PROCS]}"
    )
    print("Press Ctrl+C to stop all.")

    # Wait for all
    try:
        API_PROC.wait()
        for p in WORKER_PROCS:
            p.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    main()

