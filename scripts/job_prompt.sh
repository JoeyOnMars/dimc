#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 引入环境配置工具 (提供 PROJECT_ROOT, LOGS_ROOT)
source "$SCRIPT_DIR/env_utils.sh"

DEFAULT_TZ="${DAILY_PROMPT_TZ:-Asia/Shanghai}"

# 引入锁工具
source "$SCRIPT_DIR/lock_utils.sh"

JOB_NAME=""
COPY=false
USE_LOCK=true  # 是否使用并发锁
CURRENT_LOCK=""  # 全局变量存储当前锁名

# 清理函数
cleanup() {
  if [[ -n "$CURRENT_LOCK" && "$USE_LOCK" == "true" ]]; then
    release_lock "$CURRENT_LOCK"
  fi
}

usage() {
  cat <<'EOF'
Usage: job_prompt.sh <start|end> [options]

Manage sub-task (Job/Sub-agent) log generation.

Options:
  --job=<NAME>     Job name, format: number-semantic, e.g. "1-i18n", "2-data"
  --copy, -c       Copy the prompt to clipboard (macOS pbcopy)
  --tz=<TZ>        Override timezone (default Asia/Shanghai)
  -h, --help       Show this help

Examples:
  job_prompt.sh start --job=1-i18n    # Start job 1-i18n
  job_prompt.sh end                   # End current job (auto-detect)
  job_prompt.sh end --job=1-i18n      # End specified job
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

ACTION="$1"
shift

if [[ "$ACTION" == "-h" || "$ACTION" == "--help" || "$ACTION" == "help" ]]; then
  usage
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --job=*)
      JOB_NAME="${1#--job=}"
      ;;
    --copy|-c|copy)
      COPY=true
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

# Find unfinished job (has start.md but no end.md)
find_unfinished_job() {
  local today_dir
  today_dir="$(get_today_dir)"
  local jobs_dir="$today_dir/jobs"
  
  if [[ ! -d "$jobs_dir" ]]; then
    return
  fi
  
  local latest=""
  shopt -s nullglob
  for job_dir in "$jobs_dir"/*; do
    if [[ -d "$job_dir" ]]; then
      if [[ -f "$job_dir/start.md" && ! -f "$job_dir/end.md" ]]; then
        if [[ -z "$latest" ]] || [[ "$job_dir" > "$latest" ]]; then
          latest="$job_dir"
        fi
      fi
    fi
  done
  shopt -u nullglob
  
  if [[ -n "$latest" ]]; then
    basename "$latest"
  fi
}

# Handle job start
handle_job_start() {
  if [[ -z "$JOB_NAME" ]]; then
    echo "[job_prompt] Error: Please specify job name, e.g. --job=1-i18n" >&2
    exit 1
  fi
  
  # 获取锁（防止并发创建同一个 job）
  CURRENT_LOCK="job-${JOB_NAME}"
  if [[ "$USE_LOCK" == "true" ]]; then
    if ! acquire_lock "$CURRENT_LOCK" 10; then
      echo "[job_prompt] Error: Another process is working on job $JOB_NAME" >&2
      exit 1
    fi
    trap cleanup EXIT
  fi
  
  local today_dir
  today_dir="$(get_today_dir)"
 # === Scaffolding Functions ===

# Create start.md scaffold
create_scaffold() {
  local job_dir="$1"
  local job_name="$2"
  local date_str="$3"
  
  cat <<EOF > "$job_dir/start.md"
---
type: job-start
job_id: "$job_name"
status: active
description: "One-sentence task summary for index"
date: "$date_str"
tags: []
---

# 🚀 Job Start: $job_name

## 🎯 Goal
> One sentence description of what we are trying to achieve.

## 📋 Context
- **Why**: 
- **Reference**: 

## 🛠️ Plan
1. [ ] Step 1
2. [ ] Step 2
EOF
  echo "Created $job_dir/start.md"
}

# Create end.md scaffold
create_end_scaffold() {
  local job_dir="$1"
  local job_name="$2"
  
  cat <<EOF > "$job_dir/end.md"
---
type: job-end
job_id: "$job_name"
status: done
description: "Key outcome summary for index (< 20 words)"
date: "$(date +%Y-%m-%d)"
tags: []
files_modified: []
---

# ✅ Job End: $job_name

## 📝 Summary
> What did we accomplish?

## 🔍 Key Output
- [ ] 

## 🚫 Barriers / Leftovers
- [ ] 

## 🧠 Learnings (Optional)
> Any new insights?
EOF
  echo "Created $job_dir/end.md"
}

# === Start Action ===
handle_job_start() {
  # 如果未指定 Job Name，则尝试启动交互式选择器的逻辑
  if [[ -z "$JOB_NAME" ]]; then
    if [[ -f "$SCRIPT_DIR/task_manager.py" && -t 1 ]]; then
      # 仅在交互式 TTY 下运行 Dashboard
      # 捕获 Python 脚本的标准输出作为 Job Name
      SELECTED_JOB=$(python3 "$SCRIPT_DIR/task_manager.py")
      EXIT_CODE=$?
      
      if [[ $EXIT_CODE -eq 0 && -n "$SELECTED_JOB" ]]; then
        JOB_NAME="$SELECTED_JOB"
      else
        echo "[job_prompt] Operation cancelled." >&2
        exit 1
      fi
    else
      # 非交互模式或脚本不存在，报错
      echo "[job_prompt] Error: Please specify job name: --job=1-i18n" >&2
      exit 1
    fi
  fi

  # 获取锁 (以下逻辑不变)
  CURRENT_LOCK="job-${JOB_NAME}"
  if [[ "$USE_LOCK" == "true" ]]; then
    if ! acquire_lock "$CURRENT_LOCK" 10; then
      echo "[job_prompt] Error: Job $JOB_NAME is currently being started by another process" >&2
      exit 1
    fi
    trap cleanup EXIT
  fi

  local today_dir
  today_dir="$(get_today_dir)"
  local job_dir="$today_dir/jobs/$JOB_NAME"
  local start_file="$job_dir/start.md"
  
  # Ensure daily log exists (redundancy check)
  if [[ ! -d "$today_dir" ]]; then
    echo "[job_prompt] Info: Daily log dir not found, creating it: $today_dir"
    mkdir -p "$today_dir"
    touch "$today_dir/start.md"
  fi

  if [[ -f "$start_file" ]]; then
    echo "[job_prompt] Job $JOB_NAME already exists: $start_file" >&2
    echo "[job_prompt] To restart, please delete the directory first" >&2
    exit 1
  fi
  
  # Create directory
  mkdir -p "$job_dir"
  
  # Generate content using scaffold
  local date_str="$(date +%Y-%m-%d)"
  create_scaffold "$job_dir" "$JOB_NAME" "$date_str"
  
  echo "[job_prompt] Created job log: $job_dir/start.md" >&2
  echo "[job_prompt] When done, run: make job-end or make job-end JOB=$JOB_NAME" >&2
}

# === End Action ===
handle_job_end() {
  local target_job="$JOB_NAME"
  
  # Auto-detect if not specified
  if [[ -z "$target_job" ]]; then
    target_job="$(find_unfinished_job)"
    if [[ -z "$target_job" ]]; then
      echo "[job_prompt] No unfinished job found" >&2
      echo "[job_prompt] Please specify job name: --job=1-i18n" >&2
      exit 1
    fi
    echo "[job_prompt] Auto-detected unfinished job: $target_job" >&2
  fi
  
  # 获取锁
  CURRENT_LOCK="job-${target_job}"
  if [[ "$USE_LOCK" == "true" ]]; then
    if ! acquire_lock "$CURRENT_LOCK" 10; then
      echo "[job_prompt] Error: Another process is working on job $target_job" >&2
      exit 1
    fi
    trap cleanup EXIT
  fi
  
  local today_dir
  today_dir="$(get_today_dir)"
  local job_dir="$today_dir/jobs/$target_job"
  local start_file="$job_dir/start.md"
  local end_file="$job_dir/end.md"
  
  # Check if start exists
  if [[ ! -f "$start_file" ]]; then
    echo "[job_prompt] Job $target_job start.md not found" >&2
    exit 1
  fi
  
  # Check if already ended
  if [[ -f "$end_file" ]]; then
    echo "[job_prompt] Job $target_job already completed: $end_file" >&2
    exit 1
  fi
  
  # Generate end content
  create_end_scaffold "$job_dir" "$target_job"
  
  echo "[job_prompt] Created completion log: $end_file" >&2
}

case "$ACTION" in
  start|s)
    handle_job_start
    ;;
  end|e)
    handle_job_end
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    usage
    exit 1
    ;;
esac
