#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

cd "$ROOT_DIR"

WORKER_PIDS=()

cleanup() {
  if [ -n "${API_PID:-}" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
  for pid in "${WORKER_PIDS[@]}"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

echo "Starting API server..."
python server.py &
API_PID=$!

# OBJC_DISABLE_INITIALIZE_FORK_SAFETY: suppress macOS Objective-C runtime fork-safety
# check. Belt-and-suspenders alongside SimpleWorker — guards any edge cases where
# Python itself or a library triggers ObjC init before forking.
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Dedicated resume parsing worker
echo "Starting resume parsing worker..."
QUEUES=resume_parsing python -m workers.worker &
WORKER_PIDS+=($!)

# Dedicated resume scoring worker (avoids scoring stuck when general worker is busy)
echo "Starting resume scoring worker..."
QUEUES=resume_scoring python -m workers.worker &
WORKER_PIDS+=($!)

# General worker for jd_extraction, candidate_extraction
echo "Starting general worker..."
QUEUES=jd_extraction,candidate_extraction python -m workers.worker &
WORKER_PIDS+=($!)


# Async Woker for reminders and assessments
echo "Starting Assessment Worker..."
QUEUES=default python -m arq workers_async.worker.WorkerSettings &
WORKER_PIDS+=($!)

echo "API pid=$API_PID | Worker pids=${WORKER_PIDS[*]}"
echo "Press Ctrl+C to stop all."

wait "$API_PID" "${WORKER_PIDS[@]}"

