#!/bin/bash
# MAL Daemon launchd Installation Script
# 
# 用途: 将MAL Daemon安装为macOS后台服务
# 要求: macOS 10.10+

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}   MAL Daemon - launchd Installation${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 检测当前用户
CURRENT_USER=$(whoami)
echo -e "Current user: ${GREEN}${CURRENT_USER}${NC}"

# 定义路径
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_TEMPLATE="${PROJECT_DIR}/scripts/com.dimcause.daemon.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.dimcause.daemon.plist"
MAL_DIR="${HOME}/.mal"

echo -e "Project directory: ${GREEN}${PROJECT_DIR}${NC}"
echo ""

# 创建 .mal 目录
echo -e "${YELLOW}[1/6]${NC} Creating MAL directory..."
mkdir -p "${MAL_DIR}"
echo -e "  ✅ ${MAL_DIR}"
echo ""

# 检查plist模板是否存在
if [ ! -f "${PLIST_TEMPLATE}" ]; then
    echo -e "${RED}❌ Error: plist template not found${NC}"
    echo "  Expected: ${PLIST_TEMPLATE}"
    exit 1
fi

# 检测Python路径
echo -e "${YELLOW}[2/6]${NC} Detecting Python interpreter..."
PYTHON_PATH=""

# 尝试1: pyenv
if command -v pyenv &> /dev/null; then
    PYTHON_PATH=$(pyenv which python 2>/dev/null || echo "")
fi

# 尝试2: .venv
if [ -z "${PYTHON_PATH}" ] && [ -f "${PROJECT_DIR}/.venv/bin/python" ]; then
    PYTHON_PATH="${PROJECT_DIR}/.venv/bin/python"
fi

# 尝试3: system python3
if [ -z "${PYTHON_PATH}" ]; then
    PYTHON_PATH=$(which python3 2>/dev/null || echo "")
fi

if [ -z "${PYTHON_PATH}" ]; then
    echo -e "${RED}❌ Error: Python not found${NC}"
    exit 1
fi

echo -e "  ✅ Python: ${GREEN}${PYTHON_PATH}${NC}"
echo ""

# 检测mal命令路径
echo -e "${YELLOW}[3/6]${NC} Detecting dimc command..."
DIMC_PATH=""

# 尝试1: .venv
if [ -f "${PROJECT_DIR}/.venv/bin/mal" ]; then
    DIMC_PATH="${PROJECT_DIR}/.venv/bin/mal"
fi

# 尝试2: global pip install
if [ -z "${DIMC_PATH}" ] && command -v dimc &> /dev/null; then
    DIMC_PATH=$(which mal)
fi

if [ -z "${DIMC_PATH}" ]; then
    echo -e "${RED}❌ Error: dimc command not found${NC}"
    echo "  Please install MAL first: pip install -e ."
    exit 1
fi

echo -e "  ✅ mal: ${GREEN}${DIMC_PATH}${NC}"
echo ""

# 生成plist文件
echo -e "${YELLOW}[4/6]${NC} Generating plist file..."

# 读取模板并替换变量
sed -e "s|/Users/YOUR_USERNAME|${HOME}|g" \
    -e "s|/Users/YOUR_USERNAME/.pyenv/versions/3.13.7/bin/python|${PYTHON_PATH}|g" \
    -e "s|/Users/YOUR_USERNAME/projects/multi-agent-logger/.venv/bin/mal|${DIMC_PATH}|g" \
    -e "s|/Users/YOUR_USERNAME/projects/multi-agent-logger|${PROJECT_DIR}|g" \
    "${PLIST_TEMPLATE}" > "${PLIST_DEST}"

echo -e "  ✅ ${PLIST_DEST}"
echo ""

# 停止已有服务(如果存在)
echo -e "${YELLOW}[5/6]${NC} Stopping existing service (if any)..."
launchctl unload "${PLIST_DEST}" 2>/dev/null || true
echo -e "  ✅ Done"
echo ""

# 加载服务
echo -e "${YELLOW}[6/6]${NC} Loading MAL Daemon service..."
launchctl load "${PLIST_DEST}"

# 等待1秒让服务启动
sleep 1

# 检查服务状态
if launchctl list | grep -q "com.dimcause.daemon"; then
    echo -e "  ${GREEN}✅ MAL Daemon service loaded successfully${NC}"
else
    echo -e "  ${RED}❌ Failed to load service${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}          Installation Complete! 🎉${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "MAL Daemon is now running as a background service."
echo ""
echo "Useful commands:"
echo "  • Check status:   launchctl list | grep mal"
echo "  • View logs:      tail -f ~/.dimcause/daemon.log"
echo "  • View errors:    tail -f ~/.dimcause/daemon.error.log"
echo "  • Restart:        launchctl unload ~/Library/LaunchAgents/com.dimcause.daemon.plist"
echo "                    launchctl load ~/Library/LaunchAgents/com.dimcause.daemon.plist"
echo "  • Uninstall:      ./scripts/uninstall_daemon.sh"
echo ""
echo "The daemon will:"
echo "  ✅ Start automatically on login"
echo "  ✅ Restart automatically if it crashes"
echo ""
