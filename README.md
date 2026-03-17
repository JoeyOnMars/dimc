# Dimcause

*Evidence-backed causal investigation across local materials.*

> An evidence-backed causal investigation system for local heterogeneous materials.
> Engineering materials are the current strongest profile, not the only possible domain.

[![CLI](https://img.shields.io/badge/CLI-dimc-blue.svg)](docs/USER_GUIDE.md)
[English](README.md) | [中文](README_zh-CN.md)

## 📦 What is Dimcause?

**Dimcause** is an evidence-backed causal investigation system.

Its goal is to help us:
1. ingest local heterogeneous materials such as code, documents, logs, exports, and reports;
2. elevate those materials into structured objects;
3. build and validate causal relations between those objects;
4. explain conclusions with evidence, coverage, and missing-information boundaries.

Today, the repository is strongest in the engineering profile:
1. code and repository history,
2. project documents and design notes,
3. checks, runs, and investigation artifacts.

It is not positioned as:
1. a generic knowledge base,
2. a generic RAG platform,
3. an AI SRE product,
4. or a generic memory OS.

## 🧭 Architecture Reading

Start here if you want the current architecture rather than historical taglines:

1. [Architecture Index](docs/ARCHITECTURE_INDEX.md)
2. [Project Architecture](docs/PROJECT_ARCHITECTURE.md)
3. [Storage Architecture](docs/STORAGE_ARCHITECTURE.md)

## 🚀 Installation

PyPI release is not available yet. Install from source:

```bash
git clone https://github.com/JoeyOnMars/dimc.git
cd dimc
pip install -e .
```

## 🛠️ Usage

**Dimcause** provides `dimc` as the primary CLI command for efficiency.

```bash
# Initialize in your project
dimc init .

# Inspect the architecture-oriented CLI surface
dimc --help

# Search local materials
dimc search "auth migration"

# Explain a target with current evidence
dimc why src/auth.py
```

## 🔗 Status

This repository currently acts as:
1. the product kernel repository,
2. the default workspace profile for local development,
3. and the internal dogfooding environment for workflow and governance.

Those layers are intentionally separated in the architecture documents linked above.
