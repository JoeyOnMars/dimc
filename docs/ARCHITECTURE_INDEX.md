# Architecture Index

## Purpose

This index is the stable reading entry for DIMCAUSE architecture and governance documents.

It exists to reduce confusion between three different layers that coexist in the current repository:

1. Product architecture
2. Workspace/default profile mapping
3. Current repository workflow and governance

This file does not redefine any of those layers. It only explains where each layer is documented and in what order the documents should be read.

## Canonical Reading Order

Read the documents in this order when you need to rebuild context from scratch.

1. [PROJECT_ARCHITECTURE.md](/Users/mini/projects/GithubRepos/dimc/docs/PROJECT_ARCHITECTURE.md)
   - Canonical product architecture overview
   - Defines product identity, runtime/kernel direction, objectification and causal reasoning direction

2. [STORAGE_ARCHITECTURE.md](/Users/mini/projects/GithubRepos/dimc/docs/STORAGE_ARCHITECTURE.md)
   - Canonical storage architecture overview
   - Defines the four-layer storage model: Evidence / Runtime / Knowledge / Derived Index

3. [STORAGE_ARCHITECTURE_DRAFT_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/STORAGE_ARCHITECTURE_DRAFT_V1.md)
   - Proposal-level rationale and sharper boundary definitions behind the formal storage document

4. [CORE_OBJECT_MODEL_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/CORE_OBJECT_MODEL_V1.md)
   - Canonical proposal for first-class product objects and their boundaries

5. [EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md)
   - Proposal for evidence coverage grades and causal certainty grades
   - Explains how evidence strength and causal confidence should be separated

6. [WORKSPACE_PROFILE_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/WORKSPACE_PROFILE_V1.md)
   - Describes how the current `dimc` repository acts as the default local workspace profile
   - This is a mapping document, not a product-definition document

7. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)
   - Describes what belongs to current repository workflow/governance
   - Explains what must not flow back into product architecture or workspace profile

## Layer Map

## Product Architecture

These documents define the product itself and should be treated as the primary source for stable product semantics.

1. [PROJECT_ARCHITECTURE.md](/Users/mini/projects/GithubRepos/dimc/docs/PROJECT_ARCHITECTURE.md)
2. [STORAGE_ARCHITECTURE.md](/Users/mini/projects/GithubRepos/dimc/docs/STORAGE_ARCHITECTURE.md)

Current product-level anchor points include:

1. DIMCAUSE is an evidence-backed causal investigation system for local heterogeneous materials.
2. The runtime direction is run-centric, not task-centric.
3. The system direction is domain-agnostic objectification plus evidence-backed causal reasoning.
4. Storage is split into Evidence / Runtime / Knowledge / Derived Index.
5. Deterministic Precision Retrieval is part of product architecture, not just an implementation detail.

## Proposal Layer

These documents are the current proposal stack for architecture evolution, boundary clarification, and default mapping. They are more detailed than the formal architecture docs, but they still remain proposals rather than protected formal design docs.

1. [STORAGE_ARCHITECTURE_DRAFT_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/STORAGE_ARCHITECTURE_DRAFT_V1.md)
2. [CORE_OBJECT_MODEL_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/CORE_OBJECT_MODEL_V1.md)
3. [EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md)
4. [WORKSPACE_PROFILE_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/WORKSPACE_PROFILE_V1.md)
5. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)

Use this layer when:

1. Formal architecture is too high-level for a current design question
2. A new formal rewrite needs an upper constraint
3. You need to understand the reasoning behind a boundary before changing code or docs

Not every document in this layer plays the same role:

1. `STORAGE_ARCHITECTURE_DRAFT_V1`, `CORE_OBJECT_MODEL_V1`, and `EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1` act as upper architecture constraints.
2. `WORKSPACE_PROFILE_V1` acts as a default mapping document.
3. `REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1` acts as a repository-governance boundary document and must not be treated as product-definition source.

## Workspace Profile

The workspace profile layer explains how the current `dimc` repository maps product abstractions into a default local working setup.

Current entry:

1. [WORKSPACE_PROFILE_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/WORKSPACE_PROFILE_V1.md)

This layer may discuss:

1. Default local material roots
2. Default evidence/artifact surfaces
3. Default runtime/storage/index mappings in this repository
4. What is a current default choice rather than a universal product requirement

This layer must not:

1. Redefine the product
2. Redefine storage responsibilities
3. Redefine the object model
4. Absorb repository-only workflow rules

## Repository Workflow and Governance

The repository workflow/governance layer explains how this repository is operated and protected.

Current entry:

1. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)

This layer is where branch discipline, protected-doc behavior, preflight/check/review flow, and repository-specific collaboration rules should be interpreted.

Repository governance may constrain how we work in this repository, but it must not be used to redefine product architecture or workspace profile semantics.

## Rules and How To Read Them

The `.agent/rules/` directory remains important, but it should be interpreted carefully.

1. Rules are authoritative for current repository behavior and collaboration constraints.
2. Rules are not automatically authoritative for product definition.
3. If an older rule file conflicts with the latest formal architecture or proposal stack on product semantics, product semantics should be taken from:
   - formal architecture docs
   - upper proposals
4. Current handoff documents can help rebuild thread context, but they do not replace formal architecture docs or upper proposals as stable product truth sources.
5. Older rules may still remain valid as repository behavior constraints even if their product narrative is stale.

## Fast Recovery Path

If you need to recover context quickly after a long pause or a new thread, use this order:

1. [PROJECT_ARCHITECTURE.md](/Users/mini/projects/GithubRepos/dimc/docs/PROJECT_ARCHITECTURE.md)
2. [STORAGE_ARCHITECTURE.md](/Users/mini/projects/GithubRepos/dimc/docs/STORAGE_ARCHITECTURE.md)
3. [CORE_OBJECT_MODEL_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/CORE_OBJECT_MODEL_V1.md)
4. [EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md)
5. [WORKSPACE_PROFILE_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/WORKSPACE_PROFILE_V1.md)
6. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](/Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)

## What This Index Prevents

This index exists to reduce four recurring errors:

1. Treating current repository layout as product architecture
2. Treating repository workflow rules as product capabilities
3. Treating workspace profile defaults as universal requirements
4. Treating older rules or historical narratives as newer product truth

## Maintenance Rule

When adding a new architecture, storage, object, evidence, profile, or governance document, update this index so that the reading order and layer ownership remain explicit.
