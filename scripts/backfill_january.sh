#!/bin/bash
# scripts/backfill_january.sh
# 批量回填 2026-01-01 到 2026-01-25 的工程事件
# 支持断点续传，容错处理

# Configuration
STATE_FILE="backfill_processed.txt"
PYTHON=".venv/bin/python"
CLI="src/dimcause/cli.py"
LOG_FILE="backfill_internal.log" # Internal debug log if needed, but user redirects output

# 只允许从环境变量注入密钥，禁止在仓库中硬编码
: "${DEEPSEEK_API_KEY:?请先通过环境变量或 .env 提供 DEEPSEEK_API_KEY}"
export DEEPSEEK_BASE_URL="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
export PYTHONPATH=src

# Ensure state file exists
touch "$STATE_FILE"

echo "🚀 Starting January Backfill (2026-01-01 to 2026-01-25)..."
echo "RESUME_FILE: $STATE_FILE"

processed_count=0

# Iterate dates
for day in {01..25}; do
    date="2026-01-$day"
    
    # 1. Identify Target Files
    # Candidate paths
    candidates=(
        "docs/raw/$date.md"
        "docs/logs/2026/01-$day/end.md"
        "docs/logs/2026/01-$day/start.md"
    )
    
    target=""
    for cand in "${candidates[@]}"; do
        if [ -f "$cand" ]; then
            target="$cand"
            break
        fi
    done
    
    if [ -z "$target" ]; then
        # echo "   [dim]No log found for $date (Skipping)[/]"
        continue
    fi
    
    # 2. Check if already processed
    if grep -Fxq "$target" "$STATE_FILE"; then
        echo "⏭️  Skipping already processed: $target"
        continue
    fi
    
    # 3. Process
    echo "Processing $target..."
    if $PYTHON $CLI extract file "$target" --provider deepseek >> backfill_january_detail.log 2>&1; then
        echo "✅ Extracted: $target"
        echo "$target" >> "$STATE_FILE"
    else
        echo "❌ Failed: $target (Continuing... check detail log)"
        # Note: We do NOT add to state file so it can be retried
    fi
    
    # 4. Progress Update
    processed_count=$((processed_count + 1))
    if (( processed_count % 5 == 0 )); then
        echo "---------------------------------------------------"
        echo "📊 Progress: Processed $processed_count files so far..."
        echo "---------------------------------------------------"
    fi
    
    # Gentle rate limiting
    sleep 1
done

echo "🎉 January Backfill Loop Complete!"
