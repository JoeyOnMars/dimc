#!/bin/bash
# Dimcause Daemon launchd Uninstallation Script

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}   Dimcause Daemon - launchd Uninstallation${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

PLIST_PATH="${HOME}/Library/LaunchAgents/com.dimcause.daemon.plist"

if [ ! -f "${PLIST_PATH}" ]; then
    echo -e "${GREEN}✅ Dimcause Daemon is not installed${NC}"
    exit 0
fi

# 停止服务
echo -e "${YELLOW}[1/2]${NC} Stopping Dimcause Daemon service..."
launchctl unload "${PLIST_PATH}" 2>/dev/null || true
echo -e "  ✅ Service stopped"
echo ""

# 删除plist
echo -e "${YELLOW}[2/2]${NC} Removing plist file..."
rm -f "${PLIST_PATH}"
echo -e "  ✅ ${PLIST_PATH} removed"
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}       Uninstallation Complete! 👋${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Dimcause Daemon has been removed from launchd."
echo "To reinstall, run: ./scripts/install_daemon.sh"
echo ""
