#!/bin/bash
# scripts/backfill_recent.sh
# 批量回填最近一周的工程事件

# Ensure we rely on python in venv
PYTHON=".venv/bin/python"
CLI="src/dimcause/cli.py"

# 只允许从环境变量注入密钥，禁止在仓库中硬编码
: "${DEEPSEEK_API_KEY:?请先通过环境变量或 .env 提供 DEEPSEEK_API_KEY}"
export DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
export PYTHONPATH=src

echo "🚀 Starting Phase 2 Backfill..."

# 1. Backfill Logs (Jan 26 - Jan 31)
echo "---------------------------------------------------"
echo "📂 Processing Logs (2026-01-26 to 2026-01-31)..."
count_logs=0
for day in {26..31}; do
    date="2026-01-$day"
    # Check docs/raw format
    file="docs/raw/$date.md"
    
    # Also check docs/logs/YYYY/MM-DD/start.md or end.md if raw doesn't exist?
    # User specifically asked for docs/raw/...
    if [ -f "$file" ]; then
        echo "   -> Extracting from $file..."
        $PYTHON $CLI extract file "$file" --provider deepseek
        count_logs=$((count_logs + 1))
    else
        # Try docs/logs alternative location just to be helpful
        # 2026/01-26/end.md
        alt_file="docs/logs/2026/01-$day/end.md"
        if [ -f "$alt_file" ]; then
             echo "   -> Extracting from $alt_file..."
             $PYTHON $CLI extract file "$alt_file" --provider deepseek
             count_logs=$((count_logs + 1))
        else
             echo "   [dim]No log found for $date[/]"
        fi
    fi
done

# 2. Backfill Commits (HEAD~50..HEAD)
echo "---------------------------------------------------"
echo "🔧 Processing Recent Commits (HEAD~50..HEAD)..."
# Using extract diff with a range
$PYTHON $CLI extract diff HEAD~50..HEAD --provider deepseek

# 3. Validation / Stats
echo "---------------------------------------------------"
echo "📊 Validation Stats:"
echo -n "Total Events: "
$PYTHON $CLI timeline | grep -cE "^\d{2}-\d{2}"

echo -n "Rich Events (Decision/Reasoning): "
$PYTHON $CLI timeline | grep -E "decision|reasoning|failed_attempt" | wc -l

echo "✅ Backfill Complete!"
