#!/bin/bash
set -euo pipefail

# 依赖检查
echo "[CHECK] Verifying dependencies..."

which git > /dev/null || { echo "[FATAL] git not found"; exit 1; }
which python > /dev/null || { echo "[FATAL] python not found"; exit 1; }
which sqlite3 > /dev/null || { echo "[FATAL] sqlite3 not found"; exit 1; }

python -c "import sys; assert sys.version_info >= (3, 8)" || {
    echo "[FATAL] Python 3.8+ required"
    exit 1
}

if [ ! -d ".venv" ]; then
    echo "[FATAL] Virtual environment .venv not found"
    exit 1
fi

echo "[OK] All dependencies verified."

# 检查快照 ID
if [ ! -f .audit_snapshot ]; then
    echo "No snapshot ID found. Cannot rollback safely."
    exit 1
fi

SNAPSHOT_ID=$(cat .audit_snapshot)
BACKUP_DIR=".dimcause.backup.$SNAPSHOT_ID"

echo "[CRITICAL] Initiating Rollback to Snapshot: $SNAPSHOT_ID"

# 0. 验证备份完整性 (A1.5)
if [ -d "$BACKUP_DIR" ]; then
    if [ -f "$BACKUP_DIR/checksum.sha256" ]; then
        echo "[CHECK] Verifying Backup Checksum..."
        # 使用 shasum -c 验证校验和，忽略缺失文件警告（如果只备份了部分文件）
        if (cd "$BACKUP_DIR" && shasum -c checksum.sha256 > /dev/null); then
            echo "[OK] Backup checksum verified"
        else
            echo "[FATAL] Backup checksum verification failed!"
            exit 1
        fi
    else
        echo "[WARN] No checksum file found in backup. Skipping checksum verification."
    fi
else
    echo "[FATAL] Backup directory $BACKUP_DIR not found!"
    exit 1
fi

# 1. 停止所有服务
echo "[ACTION] Stopping services..."
pkill -f dimc || true

# 2. 恢复代码 (Git)
echo "[ACTION] Restoring code..."
# 保存任何未提交的更改用于取证分析，然后丢弃
git stash push -m "Failed attempt before rollback $SNAPSHOT_ID" || true
# 硬重置到已知良好的提交 (假设我们已打标签或记录)
# 目前，我们回退到 Phase 分支的起点
git reset --hard origin/main 

# 3. 恢复数据 (最关键部分)
echo "[ACTION] Restoring data..."
# 回滚熔断器
ROLLBACK_FAILED=0

if [ -d "$BACKUP_DIR" ]; then
    rm -rf .dimcause
    if cp -r "$BACKUP_DIR" .dimcause; then
        echo "[OK] Data restored from $BACKUP_DIR"
    else
        echo "[FATAL] Failed to copy backup directory"
        ROLLBACK_FAILED=1
    fi
else
    echo "[FATAL] Backup directory $BACKUP_DIR not found!"
    ROLLBACK_FAILED=1
fi

# 4. 清理状态
if [ $ROLLBACK_FAILED -eq 0 ]; then
    echo "[ACTION] Cleaning up..."
    rm -rf build/ dist/ *.egg-info
    find . -name "__pycache__" -exec rm -rf {} +
fi

# 5. 验证与检查
source .venv/bin/activate

if [ $ROLLBACK_FAILED -eq 0 ]; then
    # 5.1 数据完整性验证 (E3.3)
    echo "[CHECK] Verifying Data Integrity..."
    BACKUP_DB="$BACKUP_DIR/graph.db"
    RESTORED_DB=".dimcause/graph.db"

    if [ -f "$BACKUP_DB" ] && [ -f "$RESTORED_DB" ]; then
        # 验证实体数量一致性
        COUNT_BACKUP=$(sqlite3 "$BACKUP_DB" "SELECT count(*) FROM entities;")
        COUNT_RESTORED=$(sqlite3 "$RESTORED_DB" "SELECT count(*) FROM entities;")
        if [ "$COUNT_BACKUP" -eq "$COUNT_RESTORED" ]; then
            echo "[OK] Data count matches: $COUNT_RESTORED entities"
        else
            echo "[FATAL] Data count mismatch! Backup: $COUNT_BACKUP, Restored: $COUNT_RESTORED"
            ROLLBACK_FAILED=1
        fi
    else
        echo "[WARN] Could not verify data count (DB missing in backup or restore)"
    fi

    # 5.2 验证 GraphStore 读取功能
    if [ $ROLLBACK_FAILED -eq 0 ]; then
        if python -c "from dimcause.storage.graph_store import GraphStore; g = GraphStore(); entities = g.get_all_entities(limit=1); print(f'[OK] GraphStore functional - {len(entities)} entities accessible')"; then
            :
        else
            echo "[FATAL] GraphStore validation failed"
            ROLLBACK_FAILED=1
        fi
    fi

    # 5.3 验证 VectorStore 功能
    if [ $ROLLBACK_FAILED -eq 0 ]; then
        if python -c "
from dimcause.storage.vector_store import VectorStore
try:
    v = VectorStore()
    results = v.search('test', top_k=1)
    print(f'[OK] VectorStore functional - search returns {len(results)} results')
except Exception as e:
    print(f'[FATAL] VectorStore error: {e}')
    exit(1)
"; then
            :
        else
            echo "[FATAL] VectorStore validation failed"
            ROLLBACK_FAILED=1
        fi
    fi
fi

if [ $ROLLBACK_FAILED -eq 0 ]; then
    echo "[SUCCESS] Rollback verified (GraphStore + VectorStore functional)."
else
    echo "=========================================="
    echo "ROLLBACK CIRCUIT BREAKER TRIGGERED"
    echo "=========================================="
    echo "System is in INCONSISTENT state."
    echo "DO NOT PROCEED. Manual intervention required."
    echo ""
    echo "Next steps:"
    echo "1. Review logs: logs/rollback_*.log"
    echo "2. Check backup integrity: .dimcause.backup.*"
    echo "3. Contact: [your-email]"
    echo "=========================================="
    exit 99  # 特殊退出码：回滚失败
fi
