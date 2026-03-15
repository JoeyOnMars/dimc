# ============================================================================
# Dimcause v4.0 - Makefile
# 
# 这是兼容层，调用新的 `mal` CLI 命令
# 推荐直接使用: mal <command>
# ============================================================================

.PHONY: daily-start daily-end job-start job-end index capture test lint install

# === 每日开工 ===
daily-start:
	@dimc daily-start

# === 每日收工 ===
# 一键完成所有收工操作: Export 提醒 → 生成日志 → 更新索引 → Git 提交
daily-end:
	@dimc daily-end

# === 快速收工 (跳过确认) ===
daily-end-quick:
	@dimc daily-end --quick

# === Job 管理 ===
# 开始一个子任务
# 使用方式: make job-start JOB=ui-polish
job-start:
ifndef JOB
	@echo "❌ 错误：请指定任务名称"
	@echo "   使用方式: make job-start JOB=ui-polish"
	@echo "   或直接: mal job-start ui-polish"
	@exit 1
else
	@dimc job-start $(JOB)
endif

# 结束一个子任务
# 使用方式: make job-end 或 make job-end JOB=ui-polish
job-end:
ifdef JOB
	@dimc job-end $(JOB)
else
	@dimc job-end
endif

# === 索引管理 ===
index:
	@dimc index

index-rebuild:
	@dimc index --rebuild

# === 上下文 ===
context:
	@dimc context

# === 剪贴板监控 ===
capture:
	@dimc capture

# === 开发命令 ===
install:
	pip install -e ".[dev]"

test:
	pytest -v

test-cov:
	pytest --cov=src/dimcause --cov-report=html
	@echo "覆盖率报告: htmlcov/index.html"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

# === 帮助 ===
help:
	@echo "Dimcause v4.0"
	@echo ""
	@echo "工作流命令:"
	@echo "  make daily-start       开工"
	@echo "  make daily-end         收工"
	@echo "  make job-start JOB=x   开始任务"
	@echo "  make job-end           结束任务"
	@echo ""
	@echo "工具命令:"
	@echo "  make index             更新索引"
	@echo "  make context           查看上下文"
	@echo "  make capture           剪贴板监控"
	@echo ""
	@echo "开发命令:"
	@echo "  make install           安装依赖"
	@echo "  make test              运行测试"
	@echo "  make lint              代码检查"
	@echo ""
	@echo "推荐直接使用: dimc --help"
