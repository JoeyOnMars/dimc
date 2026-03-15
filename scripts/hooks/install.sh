#!/usr/bin/env bash
# 安装 DIMCAUSE Git Hooks
# 用法: bash scripts/hooks/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "[DIMC] 安装 Git Hooks..."

# 安装 pre-commit hook
cp "$SCRIPT_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/pre-commit"
echo "[DIMC] ✅ pre-commit hook 已安装"

echo "[DIMC] 安装完成。在 main 上的 commit 将被自动阻断。"
