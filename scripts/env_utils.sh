#!/usr/bin/env bash
# env_utils.sh: 环境探测、配置初始化与全局注册

# 1. 定义全局注册表位置
GLOBAL_CONFIG_DIR="$HOME/.multi-agent-logger"
GLOBAL_REGISTRY="$GLOBAL_CONFIG_DIR/projects.registry"

# 2. 查找项目根目录的辅助函数
find_project_root() {
  local dir="$1"
  while [[ "$dir" != "/" ]]; do
    if [[ -e "$dir/.logger-config" || -d "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  echo "$(pwd)" # 如果找不到，回退到当前目录
  return 1
}

# 3. 初始化或读取项目配置
init_project_env() {
  # 探测当前项目的根目录
  local current_dir="$(pwd)"
  PROJECT_ROOT="$(find_project_root "$current_dir")"
  CONFIG_FILE="$PROJECT_ROOT/.logger-config"

  # 配置变量
  LOGS_REL_DIR="docs/logs"
  
  # A) 如果配置文件存在，直接读取
  if [[ -f "$CONFIG_FILE" ]]; then
    # 读取 LOGS_DIR 配置 (兼容 key=value 格式)
    local cfg_logs_dir
    cfg_logs_dir=$(grep "^LOGS_DIR=" "$CONFIG_FILE" | cut -d'=' -f2)
    if [[ -n "$cfg_logs_dir" ]]; then
      LOGS_REL_DIR="$cfg_logs_dir"
    fi
    
  # B) 如果不存在，说明是新项目 -> 交互式初始化
  else
    # 仅在交互式终端下询问，否则使用默认值
    if [ -t 1 ]; then
      echo "🤖 Dimcause Initialization"
      echo "--------------------------------------"
      echo "Looks like this is the first time running logger in: $PROJECT_ROOT"
      read -p "Where should logs be stored? [Default: docs/logs] > " user_input
      if [[ -n "$user_input" ]]; then
        LOGS_REL_DIR="$user_input"
      fi
      
      # 写入配置文件
      echo "LOGS_DIR=$LOGS_REL_DIR" > "$CONFIG_FILE"
      echo "✅ Created config: $CONFIG_FILE"
      
      # 创建目录
      mkdir -p "$PROJECT_ROOT/$LOGS_REL_DIR"
      
      # --- 全局注册 ---
      register_project "$PROJECT_ROOT" "$LOGS_REL_DIR"
    else
      # 非交互模式（如CI），使用默认值但不写入文件，避免污染环境
      : 
    fi
  fi

  # 导出最终的绝对路径供主脚本使用
  export PROJECT_ROOT
  export LOGS_ROOT="$PROJECT_ROOT/$LOGS_REL_DIR"
}

# 4. 全局注册函数
register_project() {
  local p_root="$1"
  local p_logs="$2"
  local p_name="$(basename "$p_root")"
  local timestamp="$(date +%Y-%m-%d)"
  
  mkdir -p "$GLOBAL_CONFIG_DIR"
  touch "$GLOBAL_REGISTRY"
  
  # 检查是否已注册，如果已存在则更新时间
  # 简单 CSV 格式: NAME|ROOT|LOGS_REL|LAST_ACTIVE
  
  # 移除旧记录 (如果有)
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "\|^$p_name|$d" "$GLOBAL_REGISTRY"
  else
    sed -i "\|^$p_name|$d" "$GLOBAL_REGISTRY"
  fi
  
  # 追加新记录
  echo "$p_name|$p_root|$p_logs|$timestamp" >> "$GLOBAL_REGISTRY"
  
  # echo "🌐 Project registered globally in $GLOBAL_REGISTRY"
}

# 自动执行初始化
init_project_env
