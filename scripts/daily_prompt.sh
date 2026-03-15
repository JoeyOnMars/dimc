#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 引入环境配置工具
source "$SCRIPT_DIR/env_utils.sh"

DEFAULT_TZ="${DAILY_PROMPT_TZ:-Asia/Shanghai}"
COPY=false

usage() {
  cat <<'EOF'
Usage: daily_prompt.sh <start|end> [options]

Manage daily supervisor log generation (v3.0).

Options:
  --copy, -c       Copy the prompt to clipboard (macOS pbcopy)
  --tz=<TZ>        Override timezone (default Asia/Shanghai)
  --session=<N>    (Ignored in v3.0, kept for compatibility)
  -h, --help       Show this help
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

ACTION="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy|-c|copy)
      COPY=true
      ;;
    --tz=*)
      DEFAULT_TZ="${1#--tz=}"
      ;;
    --session=*)
      # v3.0 simplified session management, ignoring explicit session ID for now
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      # Ignore unknown options for flexibility or error out
      ;;
  esac
  shift
done

get_today_dir() {
  local tz="$DEFAULT_TZ"
  local date_str
  local year_str
  date_str="$(TZ="$tz" date '+%m-%d')"
  year_str="$(TZ="$tz" date '+%Y')"
  echo "$LOGS_ROOT/$year_str/$date_str"
}

create_daily_start() {
  local today_dir
  today_dir="$(get_today_dir)"
  local start_file="$today_dir/start.md"
  local date_str
  date_str="$(TZ="$DEFAULT_TZ" date '+%Y-%m-%d')"

  if [[ -f "$start_file" ]]; then
    echo "[daily_prompt] Daily log already exists: $start_file" >&2
    return
  fi

  mkdir -p "$today_dir"

  # Template for Daily Start
  cat <<EOF > "$start_file"
---
type: daily-start
date: "$date_str"
status: active
supervisor_status: "Planning"
---

# 📅 Daily Supervisor Log: $date_str

## 🔗 Context
- **Previous Log**: (Auto-link or manually add previous day)
- **DDD Reference**: (Link to relevant DDD sections)

## 📝 Today's Goal
> High-level summary of what we want to achieve today.

## ### Task Breakdown (Planned Jobs)
- [ ] 1-xxx (See jobs/1-xxx)
- [ ] 2-xxx (See jobs/2-xxx)

## 🧠 Supervisor Notes
- 
EOF

  echo "[daily_prompt] Created supervisor log: $start_file" >&2
}

create_daily_end() {
  local today_dir
  today_dir="$(get_today_dir)"
  local start_file="$today_dir/start.md"
  local end_file="$today_dir/end.md"
  local date_str
  date_str="$(TZ="$DEFAULT_TZ" date '+%Y-%m-%d')"

  if [[ ! -f "$start_file" ]]; then
    echo "[daily_prompt] Warning: No start.md found for today. Creating one..." >&2
    create_daily_start
  fi

  if [[ -f "$end_file" ]]; then
    echo "[daily_prompt] Daily end log already exists: $end_file" >&2
    return
  fi

  # Template for Daily End
  cat <<EOF > "$end_file"
---
type: daily-end
date: "$date_str"
status: done
summary: "Daily summary content"
---

# 🏁 Daily Wrap-up: $date_str

## ✅ Achievements
- 

## 🚫 Blockers / Issues
- 

## ⏭️ Next Steps (For Tomorrow)
- 
EOF

  echo "[daily_prompt] Created supervisor wrap-up: $end_file" >&2
}

case "$ACTION" in
  start|s)
    create_daily_start
    # If using copy, we could output prompt text here, but v3.0 relies more on reading the file
    if [[ "$COPY" == "true" ]]; then
       echo "Daily log created. Please check $LOGS_ROOT."
    fi
    ;;
  end|e)
    create_daily_end
    ;;
  *)
    usage
    exit 1
    ;;
esac
