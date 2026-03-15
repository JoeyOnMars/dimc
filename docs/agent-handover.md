**一下是AI时需要了解的核心文档，按优先级排列**

## 1 项目状态与规划
文件	用途

STATUS.md
项目当前整体进度快照，各 Phase 的完成状态

V6.0_ROADMAP.md
V6.0 版本的详细任务路线图和勾选进度

BACKLOG.md
全局 Bug 登记表和技术债清单（P0-P2 分级）
---
## 2 架构设计（L1 只读，不可修改）
文件	用途

PROJECT_ARCHITECTURE.md
系统整体架构定义（模块、层级、职责）

DEV_ONTOLOGY.md
V6.0 本体定义（事件类型、关系类型的设计规范）

STORAGE_ARCHITECTURE.md
存储层架构（SQLite schema、WAL、向量存储）

api_contracts.yaml
函数签名契约（只能在 rfc/* 分支修改）

## 3 规则体系（Agent 必读）
文件	用途

.agent/rules/
全部 Agent 行为规则（启动任何任务前必须全部读取）

dimcause-ai-system.md
核心链路保护规则，定义什么能改什么不能改

agent-git-workflow.md
Git 分支/提交/PR 协作流程

## 4 契约与审计
文件	用途

docs/PROPOSALS/Antigravity/
所有任务契约和审计报告存放处

CONTRACT_TEMPLATE.md
契约物理模板，起草新契约必须用这个

PHASE2_AUDIT_CHECKLIST.md
审计门禁清单（合入前必须逐条通过）

## 5 验证工具
文件	用途

scripts/check.zsh
一键检查脚本（ruff + pytest + 契约校验 + L1 门禁）

scripts/verify_contracts.py
契约签名自动校验（AST 解析源码 vs YAML 定义）

## 6 关键提醒
虚拟环境：所有命令必须 source .venv/bin/activate 后执行
main 禁止直接提交：pre-commit hook 会阻断，必须走分支 + 合并