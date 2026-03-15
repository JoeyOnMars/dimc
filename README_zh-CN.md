# Dimcause

*Evidence-backed causal investigation across local materials.*（面向本地材料的证据驱动因果调查）

> 一套面向本地异构材料的证据驱动因果调查系统。
> 当前最强的 profile 是工程材料，而不是唯一领域。

[![PyPI](https://img.shields.io/pypi/v/dimcause)](https://pypi.org/project/dimcause/)
[![CLI](https://img.shields.io/badge/CLI-dimc-blue.svg)](https://pypi.org/project/dimcause/)
[English](README.md) | [中文](README_zh-CN.md)

## 📦 什么是 Dimcause?

**Dimcause** 是一套面向本地异构材料的证据驱动因果调查系统。

它的目标是：
1. 接收代码、文档、日志、导出记录、报告等本地材料；
2. 将这些材料提升为结构化对象；
3. 在对象之间构建和验证因果关系；
4. 输出带证据、覆盖范围和缺失信息说明的调查结论。

当前仓库最成熟的是工程材料 profile，包括：
1. 代码与仓库历史；
2. 项目文档与设计记录；
3. checks、runs 和调查工件。

它不是：
1. 通用知识库，
2. 通用 RAG 平台，
3. AI SRE 产品，
4. 通用 memory OS。

## 🧭 架构阅读入口

如果你想了解当前正式架构，而不是历史口号，请优先阅读：

1. [Architecture Index](docs/ARCHITECTURE_INDEX.md)
2. [Project Architecture](docs/PROJECT_ARCHITECTURE.md)
3. [Storage Architecture](docs/STORAGE_ARCHITECTURE.md)

## 🚀 安装

```bash
pip install dimcause
```

## 🛠️ 使用方法

**Dimcause** 提供 `dimc` 作为主 CLI 命令，以提高效率。

```bash
# 在项目中初始化
dimc init .

# 查看 CLI 能力
dimc --help

# 搜索本地材料
dimc search "auth migration"

# 对目标做当前证据解释
dimc why src/auth.py
```

## 🔗 当前仓库角色

当前仓库同时承载：
1. 产品内核实现；
2. 默认 workspace profile；
3. 当前内部 dogfooding 与治理环境。

这三层在架构文档中被明确区分，不应混读。
