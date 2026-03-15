#!/usr/bin/env bash
# lock_utils.sh - 并发锁工具函数
# 提供跨平台的文件锁支持

# 锁文件目录
LOCK_DIR="${LOCK_DIR:-/tmp/lindencli-locks}"

# 确保锁目录存在
mkdir -p "$LOCK_DIR"

# 检查 flock 是否可用
has_flock() {
  command -v flock &>/dev/null
}

# 获取锁（使用 flock）
# 用法: acquire_lock_flock <lock_name> <timeout_seconds>
acquire_lock_flock() {
  local lock_name="$1"
  local timeout="${2:-10}"
  local lock_file="$LOCK_DIR/${lock_name}.lock"
  
  # 创建锁文件的文件描述符
  exec 200>"$lock_file"
  
  # 尝试获取锁，带超时
  if flock -w "$timeout" 200; then
    echo "[lock] Acquired lock: $lock_name" >&2
    return 0
  else
    echo "[lock] Failed to acquire lock: $lock_name (timeout: ${timeout}s)" >&2
    return 1
  fi
}

# 释放锁（使用 flock）
release_lock_flock() {
  local lock_name="$1"
  local lock_file="$LOCK_DIR/${lock_name}.lock"
  
  # 关闭文件描述符，自动释放锁
  exec 200>&-
  echo "[lock] Released lock: $lock_name" >&2
}

# 获取锁（使用 mkdir 原子操作，作为 fallback）
# 用法: acquire_lock_mkdir <lock_name> <timeout_seconds>
acquire_lock_mkdir() {
  local lock_name="$1"
  local timeout="${2:-10}"
  local lock_path="$LOCK_DIR/${lock_name}.lockdir"
  local waited=0
  
  while true; do
    # mkdir 是原子操作，成功表示获取锁
    if mkdir "$lock_path" 2>/dev/null; then
      # 写入 PID 和时间戳，便于调试
      echo "$$:$(date +%s)" > "$lock_path/info"
      echo "[lock] Acquired lock: $lock_name (mkdir)" >&2
      return 0
    fi
    
    # 检查是否超时
    if [[ $waited -ge $timeout ]]; then
      echo "[lock] Failed to acquire lock: $lock_name (timeout: ${timeout}s)" >&2
      # 显示当前持有者信息
      if [[ -f "$lock_path/info" ]]; then
        local holder
        holder=$(cat "$lock_path/info" 2>/dev/null)
        echo "[lock] Current holder: $holder" >&2
      fi
      return 1
    fi
    
    # 等待并重试
    sleep 1
    ((waited++))
  done
}

# 释放锁（使用 mkdir）
release_lock_mkdir() {
  local lock_name="$1"
  local lock_path="$LOCK_DIR/${lock_name}.lockdir"
  
  if [[ -d "$lock_path" ]]; then
    rm -rf "$lock_path"
    echo "[lock] Released lock: $lock_name (mkdir)" >&2
  fi
}

# 通用接口：自动选择最佳方案
# 用法: acquire_lock <lock_name> [timeout]
acquire_lock() {
  if has_flock; then
    acquire_lock_flock "$@"
  else
    acquire_lock_mkdir "$@"
  fi
}

# 通用接口：释放锁
release_lock() {
  if has_flock; then
    release_lock_flock "$@"
  else
    release_lock_mkdir "$@"
  fi
}

# 强制清理过期锁（用于恢复）
# 用法: cleanup_stale_locks <max_age_seconds>
cleanup_stale_locks() {
  local max_age="${1:-3600}"  # 默认 1 小时
  local now
  now=$(date +%s)
  
  echo "[lock] Cleaning up stale locks (older than ${max_age}s)..." >&2
  
  for lock_path in "$LOCK_DIR"/*.lockdir; do
    if [[ -d "$lock_path" ]]; then
      local info_file="$lock_path/info"
      if [[ -f "$info_file" ]]; then
        local lock_time
        lock_time=$(cut -d: -f2 "$info_file" 2>/dev/null)
        if [[ -n "$lock_time" ]]; then
          local age=$((now - lock_time))
          if [[ $age -gt $max_age ]]; then
            echo "[lock] Removing stale lock: $(basename "$lock_path") (age: ${age}s)" >&2
            rm -rf "$lock_path"
          fi
        fi
      fi
    fi
  done
}

# 带锁执行命令
# 用法: with_lock <lock_name> <command...>
with_lock() {
  local lock_name="$1"
  shift
  
  if ! acquire_lock "$lock_name" 30; then
    echo "[lock] Cannot execute, lock unavailable" >&2
    return 1
  fi
  
  # 使用 trap 确保锁被释放
  trap 'release_lock "$lock_name"' EXIT
  
  # 执行命令
  "$@"
  local result=$?
  
  release_lock "$lock_name"
  trap - EXIT
  
  return $result
}
