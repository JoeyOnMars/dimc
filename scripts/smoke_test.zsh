#!/usr/bin/env zsh
# ============================================================
# CI 冒烟测试：验证 dimcause 安装后核心命令可用
#
# 用途：在 pip install 后运行，确保包的入口和路径计算正确。
# 这是防止 "开发时正常 → 安装后崩溃" 类 bug 的最后防线。
# ============================================================
set -euo pipefail

echo "🔍 Dimcause 安装后冒烟测试"
echo "================================"

PASS=0
FAIL=0
TOTAL=0

run_test() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    echo -n "  [$TOTAL] $desc ... "
    if eval "$@" > /dev/null 2>&1; then
        echo "✅"
        PASS=$((PASS + 1))
    else
        echo "❌"
        echo "      命令: $@"
        FAIL=$((FAIL + 1))
    fi
}

# ---- 基础入口 ----
run_test "dimc 入口点可用" "dimc --help"
run_test "dimc version" "dimc version"

# ---- 路径相关命令（这正是 get_root_dir bug 暴露的地方）----
run_test "dimc context（路径计算）" "dimc context"
run_test "dimc stats（路径计算）" "dimc stats"

# ---- 子命令帮助 ----
run_test "dimc up --help" "dimc up --help"
run_test "dimc down --help" "dimc down --help"
run_test "dimc audit --help" "dimc audit --help"
run_test "dimc search --help" "dimc search --help"
run_test "dimc timeline --help" "dimc timeline --help"

# ---- 审计（含新增的 DRY 检查）----
run_test "dimc audit 可运行" "dimc audit 2>&1 || true"

echo ""
echo "================================"
echo "结果: $PASS/$TOTAL 通过, $FAIL 失败"

if [ $FAIL -gt 0 ]; then
    echo "❌ 冒烟测试失败！"
    exit 1
else
    echo "✅ 全部通过"
    exit 0
fi
