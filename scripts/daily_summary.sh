#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 引入环境配置工具
source "$SCRIPT_DIR/env_utils.sh"

DEFAULT_TZ="${DAILY_PROMPT_TZ:-Asia/Shanghai}"

# 引入锁工具
source "$SCRIPT_DIR/lock_utils.sh"

FORCE=false
USE_LOCK=true
CURRENT_LOCK=""

# 清理函数
cleanup() {
  if [[ -n "$CURRENT_LOCK" && "$USE_LOCK" == "true" ]]; then
    release_lock "$CURRENT_LOCK"
  fi
}

usage() {
  cat <<'EOF'
Usage: daily_summary.sh [options]

Generate daily summary by scanning all jobs.

Options:
  --force, -f    Continue even if some jobs are not completed
  --tz=<TZ>      Override timezone (default Asia/Shanghai)
  -h, --help     Show this help

Description:
  This script scans all jobs in today's directory and generates a summary.
  If any job is not completed (missing end.md), it will warn you.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|-f)
      FORCE=true
      ;;
    --tz=*)
      DEFAULT_TZ="${1#--tz=}"
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

# Get today's directory
get_today_dir() {
  local tz="$DEFAULT_TZ"
  local date_str
  local year_str
  date_str="$(TZ="$tz" date '+%m-%d')"
  year_str="$(TZ="$tz" date '+%Y')"
  echo "$LOGS_ROOT/$year_str/$date_str"
}

# Main logic
main() {
  local tz="$DEFAULT_TZ"
  local today_dir
  local full_date
  local ts
  
  today_dir="$(get_today_dir)"
  full_date="$(TZ="$tz" date '+%Y-%m-%d')"
  ts="$(TZ="$tz" date '+%Y-%m-%d %H:%M (%Z%z)')"
  
  # 获取锁（防止并发生成 daily summary）
  CURRENT_LOCK="daily-summary-${full_date}"
  if [[ "$USE_LOCK" == "true" ]]; then
    if ! acquire_lock "$CURRENT_LOCK" 10; then
      echo "[daily_summary] Error: Another process is generating daily summary" >&2
      exit 1
    fi
    trap cleanup EXIT
  fi
  
  local daily_start="$today_dir/start.md"
  local daily_end="$today_dir/end.md"
  local jobs_dir="$today_dir/jobs"
  
  # Check if today's directory exists
  if [[ ! -d "$today_dir" ]]; then
    echo "[daily_summary] Error: Today's directory not found: $today_dir" >&2
    echo "[daily_summary] Please run 'make daily-start' or 'make job-start JOB=...' first" >&2
    exit 1
  fi
  
  # Check if daily end already exists
  if [[ -f "$daily_end" ]]; then
    echo "[daily_summary] Warning: Daily end already exists: $daily_end" >&2
    echo "[daily_summary] To regenerate, please delete it first" >&2
    exit 1
  fi
  
  # Scan jobs
  echo "[daily_summary] Scanning jobs in $jobs_dir..." >&2
  
  declare -a completed_jobs=()
  declare -a incomplete_jobs=()
  declare -a job_summaries=()
  
  if [[ -d "$jobs_dir" ]]; then
    shopt -s nullglob
    for job_dir in "$jobs_dir"/*; do
      if [[ -d "$job_dir" ]]; then
        local job_name
        job_name="$(basename "$job_dir")"
        local start_file="$job_dir/start.md"
        local end_file="$job_dir/end.md"
        
        if [[ -f "$start_file" ]]; then
          if [[ -f "$end_file" ]]; then
            echo "[daily_summary] ✅ $job_name: completed" >&2
            completed_jobs+=("$job_name")
            # Extract summary from end.md if possible
            job_summaries+=("$job_name")
          else
            echo "[daily_summary] ⚠️  $job_name: NOT completed (missing end.md)" >&2
            incomplete_jobs+=("$job_name")
          fi
        fi
      fi
    done
    shopt -u nullglob
  fi
  
  local completed_count=${#completed_jobs[@]}
  local incomplete_count=${#incomplete_jobs[@]}
  local total_jobs=$((completed_count + incomplete_count))
  
  if [[ $total_jobs -eq 0 ]]; then
    echo "[daily_summary] No jobs found for today" >&2
    echo "[daily_summary] Creating minimal daily summary..." >&2
  fi
  
  # Check for incomplete jobs
  if [[ $incomplete_count -gt 0 ]]; then
    echo "" >&2
    echo "[daily_summary] ⚠️  WARNING: $incomplete_count job(s) not completed!" >&2
    for job in "${incomplete_jobs[@]}"; do
      echo "[daily_summary]    - $job" >&2
    done
    echo "" >&2
    
    if [[ "$FORCE" != "true" ]]; then
      echo "[daily_summary] To continue anyway, use: make daily-end-summary FORCE=1" >&2
      echo "[daily_summary] Or complete the jobs first: make job-end JOB=<name>" >&2
      exit 1
    else
      echo "[daily_summary] --force specified, continuing anyway..." >&2
    fi
  fi
  
  # Generate summary file
  {
    echo "# $full_date - Daily Summary"
    echo ""
    echo "> Generated: $ts"
    echo ""
    
    # Jobs table
    echo "### Jobs Summary"
    echo ""
    if [[ $total_jobs -gt 0 ]]; then
      echo "| Job | Status |"
      echo "|-----|--------|"
      if [[ $completed_count -gt 0 ]]; then
        for job in "${completed_jobs[@]}"; do
          echo "| $job | ✅ Done |"
        done
      fi
      if [[ $incomplete_count -gt 0 ]]; then
        for job in "${incomplete_jobs[@]}"; do
          echo "| $job | ⚠️ Incomplete |"
        done
      fi
    else
      echo "_No jobs recorded for today_"
    fi
    echo ""
    
    # Overall summary
    echo "### Overall Summary"
    echo "- **[Completed]** $completed_count job(s) completed"
    if [[ $incomplete_count -gt 0 ]]; then
      echo "- **[Incomplete]** $incomplete_count job(s) not finished"
    fi
    echo "- **[Tomorrow]** TBD"
    echo ""
    
    # Job details
    if [[ $completed_count -gt 0 ]]; then
      echo "### Job Details"
      echo ""
      for job in "${completed_jobs[@]}"; do
        echo "#### $job"
        local end_file="$jobs_dir/$job/end.md"
        if [[ -f "$end_file" ]]; then
          # Include content from end.md (skip the header)
          echo ""
          echo "<details>"
          echo "<summary>View details</summary>"
          echo ""
          tail -n +2 "$end_file"
          echo "</details>"
          echo ""
        fi
      done
    fi
    
  } > "$daily_end"
  
  echo "" >&2
  echo "[daily_summary] ✅ Created daily summary: $daily_end" >&2
  echo "[daily_summary] Total: ${#completed_jobs[@]} completed, ${#incomplete_jobs[@]} incomplete" >&2
  
  # === Auto-Update Index ===
  if [[ -f "$SCRIPT_DIR/log_indexer.py" ]]; then
    echo "🔄 Updating Knowledge Index..." >&2
    python3 "$SCRIPT_DIR/log_indexer.py" || echo "Warning: Index update failed" >&2
  fi
}

main
