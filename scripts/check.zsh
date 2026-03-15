#!/usr/bin/env zsh
set -euo pipefail

REPORT_MODE=0
REPORT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report)
      REPORT_MODE=1
      ;;
    --report-file)
      REPORT_MODE=1
      shift
      REPORT_PATH="${1:-}"
      if [[ -z "$REPORT_PATH" ]]; then
        echo "[DIMC] ERROR: --report-file requires a path" >&2
        exit 2
      fi
      ;;
    *)
      echo "[DIMC] ERROR: Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

# 获取脚本所在目录（兼容 bash/zsh）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

CHECK_STATUS="pass"
FAIL_STEP=""
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
BRANCH_NAME="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo "unknown")"
typeset -a STEP_NAMES STEP_COMMANDS STEP_STATUSES STEP_DETAILS L1_VIOLATIONS

log() {
  if [[ "$REPORT_MODE" -eq 1 ]]; then
    print -u2 -- "$@"
  else
    print -- "$@"
  fi
}

json_escape() {
  local s="$1"
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  print -r -- "$s"
}

record_step() {
  local name="$1"
  local command="$2"
  local step_status="$3"
  local detail="$4"

  STEP_NAMES+=("$name")
  STEP_COMMANDS+=("$command")
  STEP_STATUSES+=("$step_status")
  STEP_DETAILS+=("$detail")
}

emit_report() {
  local json
  json="{"
  json+="\"version\":1,"
  json+="\"generated_at\":\"$(json_escape "$TIMESTAMP")\","
  json+="\"branch\":\"$(json_escape "$BRANCH_NAME")\","
  json+="\"head\":\"$(json_escape "$HEAD_SHA")\","
  json+="\"status\":\"$(json_escape "$CHECK_STATUS")\","
  json+="\"failed_step\":\"$(json_escape "$FAIL_STEP")\","
  json+="\"steps\":["

  local i
  for (( i = 1; i <= ${#STEP_NAMES[@]}; i++ )); do
    if (( i > 1 )); then
      json+=","
    fi
    json+="{"
    json+="\"name\":\"$(json_escape "${STEP_NAMES[i]}")\","
    json+="\"command\":\"$(json_escape "${STEP_COMMANDS[i]}")\","
    json+="\"status\":\"$(json_escape "${STEP_STATUSES[i]}")\","
    json+="\"detail\":\"$(json_escape "${STEP_DETAILS[i]}")\""
    json+="}"
  done
  json+="],"
  json+="\"l1_violations\":["
  for (( i = 1; i <= ${#L1_VIOLATIONS[@]}; i++ )); do
    if (( i > 1 )); then
      json+=","
    fi
    json+="\"$(json_escape "${L1_VIOLATIONS[i]}")\""
  done
  json+="]"
  json+="}"

  if [[ -n "$REPORT_PATH" ]]; then
    mkdir -p "$(dirname "$REPORT_PATH")"
    print -r -- "$json" > "$REPORT_PATH"
  fi

  if [[ "$REPORT_MODE" -eq 1 ]]; then
    print -r -- "$json"
  fi
}

run_step() {
  local name="$1"
  shift
  local command_display="${(j: :)@}"
  local output=""

  log "[DIMC] ${name}..."
  if output="$("$@" 2>&1)"; then
    [[ -n "$output" ]] && log "$output"
    record_step "$name" "$command_display" "pass" "ok"
    return 0
  fi

  CHECK_STATUS="fail"
  FAIL_STEP="$name"
  [[ -n "$output" ]] && log "$output"
  record_step "$name" "$command_display" "fail" "$(print -r -- "$output" | head -n 20)"
  emit_report
  return 1
}

run_l1_immutability_check() {
  local changed_files=""
  changed_files=$(git diff --name-only main...HEAD 2>/dev/null || git diff --name-only HEAD~1..HEAD 2>/dev/null || echo "")
  L1_VIOLATIONS=()

  local is_rfc_branch=0
  if [[ "$BRANCH_NAME" == rfc/* || "$BRANCH_NAME" == codex/rfc-* || "$BRANCH_NAME" == codex/rfc/* ]]; then
    is_rfc_branch=1
  fi

  local l1_file
  for l1_file in "${L1_FILES[@]}"; do
    if echo "$changed_files" | grep -q "^$l1_file"; then
      if [[ "$is_rfc_branch" -eq 0 ]]; then
        L1_VIOLATIONS+=("$l1_file")
      fi
    fi
  done

  if [[ ${#L1_VIOLATIONS[@]} -gt 0 ]]; then
    CHECK_STATUS="fail"
    FAIL_STEP="L1 immutability check"
    log "[DIMC] L1 VIOLATION: Non-RFC branch modified L1 files:"
    local f
    for f in "${L1_VIOLATIONS[@]}"; do
      log "  - $f"
    done
    log "[DIMC] Protected design docs can only be modified in approved RFC branches (rfc/* or codex/rfc-*)."
    record_step "L1 immutability check" "git diff --name-only main...HEAD" "fail" "modified protected L1 files on non-rfc branch"
    emit_report
    return 1
  fi

  record_step "L1 immutability check" "git diff --name-only main...HEAD" "pass" "ok"
  return 0
}

# Ensure the repo-local virtualenv is active before any checks.
if [[ -z "${VIRTUAL_ENV:-}" ]] || [[ "${VIRTUAL_ENV}" != *".venv"* ]]; then
  if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
    log "[DIMC] Force activating local .venv..."
    source "$REPO_ROOT/.venv/bin/activate" || {
      log "[DIMC] ERROR: Failed to activate .venv"
      exit 1
    }
  else
    log "[DIMC] ERROR: No .venv found in expected path. Aborting check."
    exit 1
  fi
fi

# DIMCAUSE Check Script (updated 2026-02-12)
# Covers: core utils, extractors, brain, CLI, history, and related tests

run_step "Ruff check" ruff check src/

run_step "Ruff format check" ruff format --check src/

run_step "Pytest" pytest \
  tests/search/test_engine.py \
  tests/scheduler/test_orchestrator.py \
  tests/scheduler/test_orchestrator_status_file.py \
  tests/scheduler/test_loop.py \
  tests/scheduler/test_system_jobs.py \
  tests/scheduler/test_cli_scheduler.py \
  tests/scheduler/test_lint_paths.py \
  tests/scheduler/test_runner.py \
  tests/scheduler/test_task_event_sync.py \
  tests/test_cost_tracker.py \
  tests/test_continue_watcher.py \
  tests/test_daemon_manager.py \
  tests/test_deepseek_client.py \
  tests/test_llm_linker.py \
  tests/test_analyzer.py \
  tests/test_cli_brain.py \
  tests/test_cli_detect.py \
  tests/test_cli_search_helpers.py \
  tests/test_cli_timeline.py \
  tests/test_cli_history.py \
  tests/test_code_indexer.py \
  tests/test_config.py \
  tests/test_event_index.py \
  tests/test_event_index_link_roundtrip.py \
  tests/test_event_index_query_cache.py \
  tests/test_event_index_wal_bridge.py \
  tests/test_models.py \
  tests/test_preflight_guard.py \
  tests/test_pr_ready.py \
  tests/test_state_job_markers.py \
  tests/test_pipeline_runtime.py \
  tests/test_semantic_linker.py \
  tests/test_extraction_pipeline_relations.py \
  tests/test_state_watcher.py \
  tests/test_core_history.py \
  tests/test_trace_engine.py \
  tests/test_timeline_service.py \
  tests/test_brain_decision.py \
  tests/core/test_schema_validator.py \
  tests/unit/core/test_semantic_event.py \
  tests/unit/core/test_event_index_links.py

# ============================================================
# Task: 契约验证自动化 - 物理闸门
# ============================================================

run_step "Contract signature verification" python scripts/verify_contracts.py

log "[DIMC] L1 immutability check..."
# L1 受保护文件清单
L1_FILES=(
  "docs/PROJECT_ARCHITECTURE.md"
  "docs/V6.0/DEV_ONTOLOGY.md"
  "docs/api_contracts.yaml"
  "docs/STORAGE_ARCHITECTURE.md"
)

run_l1_immutability_check

log "[DIMC] All checks passed"
emit_report
