#!/bin/bash
# Script to run the android_coder agent on a DemoApp task

set -e

REPO_ROOT="${REPO_ROOT:-/Users/aj/workspace_ai/the-smelters}"
cd "$REPO_ROOT"
PROJECT_DIR="$REPO_ROOT/projects/DemoApp"
OPENCODE_SERVER_PID=""
EVENT_MONITOR_PID=""

# Ensure venv python is available
PYTHON="$REPO_ROOT/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    echo "Error: Python venv not found at $PYTHON"
    echo "Creating venv..."
    cd "$REPO_ROOT"
    uv venv --python python3.13
    uv pip install claude-agent-sdk anthropic google-genai pyyaml pytest pytest-asyncio
    PYTHON="$REPO_ROOT/.venv/bin/python"
fi

# Database path
DB_PATH="$REPO_ROOT/database/DemoApp/tasks.db"
EVENTS_PATH="$REPO_ROOT/database/DemoApp/events.jsonl"
OPENCODE_SERVER_LOG="$REPO_ROOT/database/DemoApp/opencode-serve.log"

if [ ! -f "$DB_PATH" ]; then
    echo "No tasks database found. Seeding tasks..."
    $PYTHON seed.py --project DemoApp --db "$DB_PATH" --root "$REPO_ROOT"
fi

echo "============================================"
echo "  Android Coder - Task Selector"
echo "============================================"
echo ""

# Get task list (using task_number for display)
TASKS=$($PYTHON -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
cursor = conn.execute(
    'SELECT id, task_number, title, status FROM tasks WHERE status IN (\"ready\", \"failed\") ORDER BY task_number'
)
for row in cursor.fetchall():
    print(f'{row[0]}|{row[1]}|{row[2]}|{row[3]}')
conn.close()
")

if [ -z "$TASKS" ]; then
    echo "No available tasks found."
    exit 1
fi

echo "Available tasks:"
echo ""
while IFS='|' read -r id task_num title status; do
    echo "  [#$task_num] $title (status: $status)"
done <<< "$TASKS"
echo ""
echo "============================================"

SELECTION="${1:-${TASK_NUMBER:-}}"
if [ -z "$SELECTION" ]; then
    # Prompt for task selection only when task number wasn't passed via arg/env.
    read -r -p "Enter task number to run (e.g., 6, 7, 8) or 'q' to quit: " SELECTION
fi

if [ "$SELECTION" = "q" ] || [ -z "$SELECTION" ]; then
    echo "Cancelled."
    exit 0
fi

# Validate selection - match by task_number
if ! echo "$TASKS" | grep -q "|$SELECTION|"; then
    echo "Error: Invalid task number: $SELECTION"
    exit 1
fi

# Get task ID from task_number
TASK_INFO=$($PYTHON -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
row = conn.execute('SELECT id, task_number, title, spec_path FROM tasks WHERE task_number = $SELECTION').fetchone()
print(f'{row[0]}|{row[1]}|{row[2]}|{row[3]}')
conn.close()
")

IFS='|' read -r task_id task_num title spec_path <<< "$TASK_INFO"

echo ""
echo "Selected: Task #$task_num - $title"
echo "============================================"
echo ""

# Restart opencode server to ensure it uses current network route (VPN, etc.)
echo "Restarting opencode server..."
if PIDS=$(pgrep -f "opencode serve --port 4096"); then
    echo "Stopping existing opencode server process(es): $PIDS"
    # shellcheck disable=SC2086
    kill $PIDS 2>/dev/null || true
fi

# Wait for graceful shutdown, then force kill if needed.
for _ in {1..10}; do
    if ! pgrep -f "opencode serve --port 4096" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done
if FORCE_PIDS=$(pgrep -f "opencode serve --port 4096"); then
    echo "Force-stopping stuck opencode process(es): $FORCE_PIDS"
    # shellcheck disable=SC2086
    kill -9 $FORCE_PIDS 2>/dev/null || true
    sleep 1
fi

SERVER_READY=0
mkdir -p "$(dirname "$OPENCODE_SERVER_LOG")"
for ATTEMPT in 1 2 3; do
    echo "Starting opencode server (attempt $ATTEMPT/3)..."
    opencode serve --port 4096 >> "$OPENCODE_SERVER_LOG" 2>&1 &
    OPENCODE_SERVER_PID=$!

    for _ in {1..20}; do
        if curl -s http://localhost:4096/health > /dev/null 2>&1; then
            SERVER_READY=1
            break
        fi
        # If process crashed before health check succeeded, retry.
        if ! kill -0 "$OPENCODE_SERVER_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done

    if [ "$SERVER_READY" -eq 1 ]; then
        break
    fi

    kill "$OPENCODE_SERVER_PID" 2>/dev/null || true
    wait "$OPENCODE_SERVER_PID" 2>/dev/null || true
done

if [ "$SERVER_READY" -ne 1 ]; then
    echo "Error: opencode server failed to start on port 4096 after 3 attempts"
    echo "Check latest log under ~/.local/share/opencode/log/"
    exit 1
fi

# Run the agent
echo "Running android_coder agent..."
echo "Canonical DemoApp copy (template only; agent does not edit here): $PROJECT_DIR"
echo "Task edits go under: $REPO_ROOT/worktrees/DemoApp/task-<task_number> (see tasks.worktree in $DB_PATH)"
echo "Event log: $EVENTS_PATH"
echo "Opencode server log: $OPENCODE_SERVER_LOG"
echo ""

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: DemoApp project directory not found at $PROJECT_DIR"
    exit 1
fi

touch "$EVENTS_PATH"

echo "Listening to event log for task $task_id..."
$PYTHON -u - "$EVENTS_PATH" "$task_id" <<'PY' &
import json
import os
import sys
import time

events_path = sys.argv[1]
task_id = int(sys.argv[2])

with open(events_path, "r", encoding="utf-8") as f:
    f.seek(0, os.SEEK_END)
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.2)
            continue
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("task_id") != task_id:
            continue
        ts = event.get("ts", "?")
        actor = event.get("actor", "?")
        kind = event.get("type", "?")
        if kind == "agent_output":
            provider = event.get("provider", "?")
            output = str(event.get("output", "")).strip()
            preview = output[:240]
            if output and len(output) > 240:
                preview += "...(truncated)"
            print(f"[event:{ts}] [{actor}] {kind}/{provider}: {preview}", flush=True)
        elif kind == "agent_output_line":
            provider = event.get("provider", "?")
            line = str(event.get("line", ""))
            print(f"[event:{ts}] [{actor}] {kind}/{provider}: {line}", flush=True)
        else:
            extra = {k: v for k, v in event.items() if k not in {"ts", "task_id", "actor", "type"}}
            print(f"[event:{ts}] [{actor}] {kind}: {json.dumps(extra, ensure_ascii=False)}", flush=True)
PY
EVENT_MONITOR_PID=$!

cleanup_background_processes() {
    if [ -n "$EVENT_MONITOR_PID" ] && kill -0 "$EVENT_MONITOR_PID" 2>/dev/null; then
        kill "$EVENT_MONITOR_PID" 2>/dev/null || true
        wait "$EVENT_MONITOR_PID" 2>/dev/null || true
    fi
    if [ -n "$OPENCODE_SERVER_PID" ] && kill -0 "$OPENCODE_SERVER_PID" 2>/dev/null; then
        kill "$OPENCODE_SERVER_PID" 2>/dev/null || true
        wait "$OPENCODE_SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup_background_processes EXIT

(
    cd "$REPO_ROOT"
    export PYTHONUNBUFFERED=1
    TRACKER_DB="$DB_PATH" \
    REPO_ROOT="$REPO_ROOT" \
    TASKS_ROOT="$REPO_ROOT/tasks" \
    PYTHONPATH="$REPO_ROOT" \
    $PYTHON -u -m agents.android_coder "$task_id"
)

cleanup_background_processes
trap - EXIT

echo ""
echo "============================================"
echo "Agent finished."
echo "============================================"