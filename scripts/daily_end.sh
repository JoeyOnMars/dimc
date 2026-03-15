#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# ⚠️ DEPRECATED: 此脚本已被 v4.0 版本替代
# 请使用: dimc daily-end
#
# daily_end.sh - 一键收工脚本 (Dimcause v3.0)
#
# 功能：
#   1. Antigravity 对话导出提醒
#   2. 生成收工日志骨架 (end.md)
#   3. 更新智能索引 (INDEX.md)
#   4. Git 分支选择与提交
#
# 使用方式：
#   dimc daily-end  # 推荐
#   ./scripts/daily_end.sh  # 旧方式
# ============================================================================

echo "⚠️  警告: 此脚本已废弃，请使用 'dimc daily-end' 命令" >&2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_TZ="${DAILY_PROMPT_TZ:-Asia/Shanghai}"

# 加载环境配置 (如果存在)
if [[ -f "$SCRIPT_DIR/env_utils.sh" ]]; then
    source "$SCRIPT_DIR/env_utils.sh"
fi

LOGS_ROOT="${LOGS_ROOT:-$ROOT_DIR/docs/logs}"

# === 辅助函数 ===

step() {
    local title="$1"
    printf '\n========== %s ==========\n' "$title"
}

get_today_dir() {
    local date_str year_str
    date_str="$(TZ="$DEFAULT_TZ" date '+%m-%d')"
    year_str="$(TZ="$DEFAULT_TZ" date '+%Y')"
    echo "$LOGS_ROOT/$year_str/$date_str"
}

create_end_log() {
    local today_dir end_file date_str
    today_dir="$(get_today_dir)"
    end_file="$today_dir/end.md"
    date_str="$(TZ="$DEFAULT_TZ" date '+%Y-%m-%d')"

    mkdir -p "$today_dir"

    if [[ -f "$end_file" ]]; then
        echo "[daily_end] 收工日志已存在: $end_file"
        echo "如需重新生成，请先删除该文件。"
        return
    fi

    cat <<EOF > "$end_file"
---
type: daily-end
date: "$date_str"
status: done
description: ""
tags: []
---

# 🏁 Daily Wrap-up: $date_str

## ✅ 完成事项
- 

## 🚫 遇到的问题
- 

## ⏭️ 明日切入点
- 

## [待办]
- 

EOF

    echo "[daily_end] ✅ 已生成收工日志: $end_file"
}

# === 主流程 ===

step "1) 🛑 Antigravity 对话导出"
echo "请前往 Antigravity IDE，点击右上角【Export】按钮导出对话。"
echo "建议保存位置: ~/Documents/AG_Exports/"
echo ""
read -p "❓ 是否已完成导出？(y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "⚠️  警告：跳过导出可能导致上下文丢失！"
else
    echo "✅ 确认已导出"
fi

step "2) 📝 生成收工日志"
create_end_log

step "3) 📊 更新智能索引"
if [[ -f "$ROOT_DIR/scripts/log_indexer.py" ]]; then
    (cd "$ROOT_DIR" && python3 scripts/log_indexer.py) || echo "[WARN] log_indexer.py 执行失败"
else
    echo "[SKIP] log_indexer.py 未找到"
fi

step "4) 🔀 Git 提交"
cd "$ROOT_DIR"
current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
today_date=$(TZ="$DEFAULT_TZ" date '+%Y-%m-%d')
daily_branch="daily/$today_date"

echo "当前分支: $current_branch"
git status --short 2>/dev/null || true

echo ""
echo "请选择提交方式："
echo "[1] 直接提交到当前分支 ($current_branch) - 快速模式"
echo "[2] 新建 $daily_branch 分支并提交 - 安全模式"
echo "[3] 跳过 Git 操作"
echo ""
read -p "请输入选项 (1/2/3): " -n 1 -r git_choice
echo ""

case $git_choice in
    1)
        echo "📦 正在提交到 $current_branch..."
        git add .
        git commit -m "chore(daily): end of day wrap-up $today_date" || echo "[INFO] 没有需要提交的更改"
        git push origin "$current_branch" || echo "[WARN] Push 失败，请稍后手动执行"
        echo "✅ 已提交并推送到 $current_branch"
        ;;
    2)
        echo "🔀 正在创建新分支 $daily_branch..."
        git checkout -b "$daily_branch"
        git add .
        git commit -m "chore(daily): end of day wrap-up $today_date" || echo "[INFO] 没有需要提交的更改"
        git push origin "$daily_branch" || echo "[WARN] Push 失败，请稍后手动执行"
        echo "✅ 已提交并推送到 $daily_branch"
        
        echo "🔙 切换回主开发分支 $current_branch..."
        git checkout "$current_branch"
        
        mkdir -p "$ROOT_DIR/.agent"
        echo "$daily_branch" > "$ROOT_DIR/.agent/pending_merge.txt"
        echo "📝 已记录待合并分支，明天开工时会提醒您合并"
        ;;
    3)
        echo "⏭️  跳过 Git 操作"
        ;;
    *)
        echo "⚠️  无效选项，跳过 Git 操作"
        ;;
esac

echo ""
echo "🌙 收工流程完成！明天见！"
