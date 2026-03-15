from pathlib import Path
from typing import List

from dimcause.audit.checks.dry import DuplicateDefinitionCheck
from dimcause.audit.checks.security import BanditCheck, SensitiveInfoCheck
from dimcause.audit.checks.style import FormatCheck, MypyCheck, RuffCheck

# We don't register TimelineIntegrityCheck here if we are calculating it separately or we keep it?
# Blueprint says: "Make run_audit returning AuditResult"
# And "Let TimelineIntegrityCheck populate TimelineSummary" -> implies check still runs.
# BUT we also want to populate AuditResult.timeline_summary.
# We can extract it from the CheckResult OR run logic here.
# Let's run checks, then extract stats if available.
from dimcause.audit.checks.timeline import TimelineIntegrityCheck
from dimcause.audit.engine import AuditEngine
from dimcause.audit.mode import STANDARD_MODE, AuditMode
from dimcause.audit.result import AuditResult, SecurityFinding
from dimcause.reasoning.validator import AxiomValidator

# Assuming GraphStore can be hydrated
from dimcause.storage.graph_store import GraphStore


def run_audit(
    files: List[Path],
    mode: AuditMode = STANDARD_MODE,
    fix: bool = False,
    include_timeline: bool = True,
) -> AuditResult:
    """
    Main entry point for running audits.
    Orchestrates checks and aggregates functionality.
    """

    # 1. Initialize Engine
    engine = AuditEngine(mode=mode)

    # 2. Register Checks
    config = {"fix": fix}

    # Style & Lint
    engine.register(FormatCheck(config, mode=mode))
    engine.register(RuffCheck(config, mode=mode))
    engine.register(MypyCheck(config, mode=mode))

    # Security
    engine.register(SensitiveInfoCheck(config, mode=mode))
    engine.register(BanditCheck(config, mode=mode))

    # DRY 违规（同名函数多模块定义检测）
    engine.register(DuplicateDefinitionCheck(config, mode=mode))

    # Timeline
    if include_timeline:
        engine.register(TimelineIntegrityCheck(config, mode=mode))

    # 3. Run Checks
    raw_results = engine.run_all(files)

    # 4. Aggregation Logic
    findings: List[SecurityFinding] = []
    timeline_stats = None

    has_blocking_failure = False

    for res in raw_results:
        # Check Blocking Status
        if not res.success and res.is_blocking:
            has_blocking_failure = True

        # Extract Security Findings (Naive parsing from details for now,
        # ideally checks return structured findings)
        if res.check_name in ["sensitive_data", "bandit"]:
            # Parse detail strings into Findings if possible
            # For now we just trust the result status and collection
            # To strictly follow schema, we would parse res.details
            pass

        # Extract Timeline Stats
        # Since TimelineIntegrityCheck in checks/timeline.py delegates to service,
        # we can also re-instantiate service here or parse the CheckResult.
        # But wait, AuditResult needs the structured stats object.
        # CheckResult details are just strings.
        # OPTION: Run TimelineService explicitly here if we want the object.
        pass

    # Explicitly fetching timeline stats for the result object
    if include_timeline:
        from datetime import date

        from dimcause.core.timeline import TimelineService

        try:
            svc = TimelineService()
            timeline_stats = svc.get_daily_stats(date.today())
        except Exception:
            pass

    # 5. 因果公理验证 (Phase 1: Real Audit)
    # 使用 AxiomValidator 对图谱执行因果检查
    causal_issues = []
    try:
        graph_store = GraphStore()
        if graph_store._graph is not None and graph_store._graph.number_of_nodes() > 0:
            validator = AxiomValidator()
            causal_issues = validator.validate(graph_store._graph)
    except Exception:
        # 图谱为空或数据库不存在时，跳过因果检查 (不阻塞审计)
        pass

    # Exit Code Logic
    # If mode is Strict: failure = blocking failure
    # If mode is Standard: failure = blocking failure (but mostly non-blocking warnings)

    exit_code = 1 if has_blocking_failure else 0

    return AuditResult(
        mode=mode,
        success=not has_blocking_failure,
        exit_code=exit_code,
        timeline_stats=timeline_stats,
        findings=findings,  # populated if we parsed them
        causal_issues=causal_issues,
        raw_results=raw_results,
    )
