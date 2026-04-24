#!/bin/bash
# Script to run the android_coder agent on a DemoApp task

set -e

REPO_ROOT="${REPO_ROOT:-/Users/aj/workspace_ai/the-smelters}"
cd "$REPO_ROOT"

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

# Prompt for task selection
read -p "Enter task number to run (e.g., 6, 7, 8) or 'q' to quit: " SELECTION

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

# Ensure opencode server is running
if ! curl -s http://localhost:4096/health > /dev/null 2>&1; then
    echo "Starting opencode server..."
    opencode serve --port 4096 &
    sleep 3
fi

# Create worktree if needed
WORKTREE_DIR="$REPO_ROOT/worktrees/DemoApp/task-$task_num"
if [ ! -d "$WORKTREE_DIR" ]; then
    echo "Creating worktree..."
    mkdir -p "$WORKTREE_DIR"
    git worktree add "$WORKTREE_DIR" origin/main -q 2>/dev/null || true
fi

# Run the agent
echo "Running android_coder agent..."
echo ""

TRACKER_DB="$DB_PATH" \
REPO_ROOT="$REPO_ROOT" \
TASKS_ROOT="$REPO_ROOT/tasks" \
PYTHONPATH="$REPO_ROOT" \
$PYTHON -m agents.android_coder "$task_id"

echo ""
echo "============================================"
echo "Agent finished."
echo "============================================"