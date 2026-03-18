#!/bin/bash
# bootstrap.sh - 一键初始化 v4.0 重构环境
# 
# 使用方式:
#   chmod +x scripts/bootstrap.sh
#   ./scripts/bootstrap.sh

set -euo pipefail

echo "🚀 Dimcause v4.0 重构初始化"
echo "======================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

# === Step 1: 创建目录结构 ===
echo ""
echo "📁 Step 1: 创建目录结构..."

mkdir -p src/dimcause/{core,capture,utils}
mkdir -p tests
mkdir -p .github/workflows

# 创建 __init__.py
touch src/dimcause/__init__.py
touch src/dimcause/core/__init__.py
touch src/dimcause/capture/__init__.py
touch src/dimcause/utils/__init__.py
touch tests/__init__.py

echo "   ✅ 目录结构已创建"

# === Step 2: 创建 pyproject.toml ===
echo ""
echo "📦 Step 2: 创建 pyproject.toml..."

if [[ -f "pyproject.toml" ]]; then
    echo "   ⚠️  pyproject.toml 已存在，跳过"
else
    cat > pyproject.toml << 'PYPROJECT_EOF'
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dimcause"
version = "4.0.0-alpha"
description = "AI Session Context Manager - Own Your AI Conversations"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [
    { name = "JoeyOnMars" }
]
keywords = ["ai", "logging", "context", "llm", "agent"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "typer>=0.9.0",
    "pydantic>=2.0",
    "rich>=13.0",
    "pyperclip>=1.8",
    "pytz>=2023.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
]

[project.scripts]
dimc = "dimcause.cli:app"

[project.urls]
Homepage = "https://github.com/JoeyOnMars/dimc"
Repository = "https://github.com/JoeyOnMars/dimc.git"

[tool.hatch.build.targets.wheel]
packages = ["src/dimcause"]

[tool.ruff]
line-length = 100
target-version = "py310"
select = ["E", "F", "I", "W", "B", "Q"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src/dimcause --cov-report=term-missing"
pythonpath = ["src"]
PYPROJECT_EOF
    echo "   ✅ pyproject.toml 已创建"
fi

# === Step 3: 创建基础模块骨架 ===
echo ""
echo "🐍 Step 3: 创建基础模块骨架..."

# src/dimcause/__init__.py
cat > src/dimcause/__init__.py << 'EOF'
"""
Dimcause - AI Session Context Manager

Usage:
    dimc daily-start    # 开工
    dimc daily-end      # 收工
    dimc job-start      # 开始任务
    dimc job-end        # 结束任务
"""

__version__ = "4.0.0-alpha"
EOF

# 临时 CLI 骨架 (完整版在 REFACTOR_PLAN.md 中)
cat > src/dimcause/cli.py << 'EOF'
"""
Dimcause CLI 入口

完整实现见 docs/REFACTOR_PLAN.md Phase 2
"""
import typer

app = typer.Typer(
    name="dimc",
    help="Dimcause - AI Session Context Manager",
    add_completion=False,
)

@app.command()
def daily_start():
    """开工: 自动恢复上下文，生成开工日志"""
    typer.echo("🚀 daily-start - 待实现 (见 REFACTOR_PLAN.md)")

@app.command()
def daily_end():
    """收工: 导出提醒 → 生成日志 → 更新索引 → Git"""
    typer.echo("🌙 daily-end - 待实现 (见 REFACTOR_PLAN.md)")

@app.command()
def job_start(job_id: str = typer.Argument(..., help="任务 ID")):
    """开始一个子任务"""
    typer.echo(f"🎯 job-start {job_id} - 待实现")

@app.command()
def job_end(job_id: str = typer.Argument(None, help="任务 ID")):
    """结束当前子任务"""
    typer.echo(f"✅ job-end {job_id or '(auto)'} - 待实现")

@app.command()
def version():
    """显示版本信息"""
    from dimcause import __version__
    typer.echo(f"Dimcause v{__version__}")

if __name__ == "__main__":
    app()
EOF

echo "   ✅ 模块骨架已创建"

# === Step 4: 创建 GitHub Actions ===
echo ""
echo "🔧 Step 4: 创建 GitHub Actions..."

cat > .github/workflows/ci.yml << 'EOF'
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      
      - name: Lint
        run: ruff check src/ tests/
      
      - name: Test
        run: pytest --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.11'
EOF

echo "   ✅ GitHub Actions 已创建"

# === Step 5: 创建基础测试 ===
echo ""
echo "🧪 Step 5: 创建基础测试..."

cat > tests/test_cli.py << 'EOF'
"""CLI 基础测试"""
import pytest
from typer.testing import CliRunner
from dimcause.cli import app

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "4.0.0" in result.stdout

def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "daily-start" in result.stdout
    assert "daily-end" in result.stdout
EOF

echo "   ✅ 基础测试已创建"

# === Step 6: 安装开发依赖 ===
echo ""
echo "📥 Step 6: 安装开发依赖..."

pip install -e ".[dev]" --quiet 2>/dev/null || {
    echo "   ⚠️  pip install 失败，请手动运行: pip install -e '.[dev]'"
}

# === Step 7: 验证安装 ===
echo ""
echo "✅ Step 7: 验证安装..."

if command -v dimc &> /dev/null; then
    echo "   ✅ 'dimc' 命令可用"
    dimc version
else
    echo "   ⚠️  'dimc' 命令不可用，请检查 PATH"
    echo "   尝试: python -m dimcause.cli version"
fi

# === 完成 ===
echo ""
echo "======================================="
echo "🎉 重构环境初始化完成!"
echo ""
echo "下一步:"
echo "  1. 阅读 docs/REFACTOR_PLAN.md 了解完整计划"
echo "  2. 运行 'dimc --help' 测试 CLI"
echo "  3. 运行 'pytest' 验证测试"
echo ""
echo "开始 Phase 1:"
echo "  按照 REFACTOR_PLAN.md 实现 src/dimcause/core/schema.py"
echo "======================================="
