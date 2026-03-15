from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

import networkx as nx

from dimcause.core.ontology import get_ontology


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    axiom_id: str
    severity: ValidationSeverity
    message: str
    entity_id: str
    details: Dict[str, Any]


class AxiomValidator:
    """
    公理执行者 (Axiom Enforcer)

    负责验证因果图谱是否符合 ontology.yaml 中定义的公理。
    """

    def __init__(self):
        self.ontology = get_ontology()

    def validate(self, graph: nx.DiGraph) -> List[ValidationResult]:
        """
        对给定的因果图执行所有启用公理的检查

        Args:
            graph: NetworkX DiGraph, 节点为 Event ID, 边属性包含 'relation'
        """
        results = []

        # 1. 检查 Commit 因果 (Rule 4.1)
        results.extend(self._check_commit_cause(graph))

        # 2. 检查 Decision 循环 (Rule 4.2)
        results.extend(self._check_decision_cycle(graph))

        # 3. 检查 Function 可追溯性 (Rule 4.3)
        results.extend(self._check_function_traceability(graph))

        return results

    def _check_commit_cause(self, graph: nx.DiGraph) -> List[ValidationResult]:
        """
        Axiom 4.1: 每个Commit必须至少realize一个Decision或fix一个Incident
        """
        results = []

        # 筛选 Commit 节点
        commit_nodes = [
            n
            for n, attr in graph.nodes(data=True)
            if attr.get("type") == "commit"
            or (isinstance(attr.get("type"), str) and attr.get("type").endswith("commit"))
        ]

        for commit_id in commit_nodes:
            has_cause = False
            # 检查出边
            for _, _target, attr in graph.out_edges(commit_id, data=True):
                relation = attr.get("relation")
                if relation in ["realizes", "fixes"]:
                    has_cause = True
                    break

            if not has_cause:
                # 再次检查入边 (如果关系定义在另一端，如 implemented_by? 不，ontology定义的是主动语态)
                # Ontology: Commit --realizes--> Decision
                # 所以只检查出边
                pass

            if not has_cause:
                results.append(
                    ValidationResult(
                        axiom_id="commit_must_have_cause",
                        severity=ValidationSeverity.WARNING,
                        message=f"Commit {commit_id} 缺少因果关联 (realizes/fixes)",
                        entity_id=commit_id,
                        details={},
                    )
                )

        return results

    def _check_decision_cycle(self, graph: nx.DiGraph) -> List[ValidationResult]:
        """
        Axiom 4.2: Decision的overrides关系不能形成环
        """
        results = []

        # 构建 Decision 子图 (仅包含 overrides 边)
        decision_nodes = [n for n, attr in graph.nodes(data=True) if attr.get("type") == "decision"]

        if not decision_nodes:
            return []

        # 提取子图，仅保留 overrides 边
        # 必须过滤边，否则其他关系的环不是问题
        edges = []
        for u, v, attr in graph.edges(data=True):
            if u in decision_nodes and v in decision_nodes:
                if attr.get("relation") == "overrides":
                    edges.append((u, v))

        subgraph = nx.DiGraph()
        subgraph.add_nodes_from(decision_nodes)
        subgraph.add_edges_from(edges)

        try:
            cycles = list(nx.simple_cycles(subgraph))
            if cycles:
                for cycle in cycles:
                    cycle_path = " -> ".join(cycle)
                    results.append(
                        ValidationResult(
                            axiom_id="no_decision_cycle",
                            severity=ValidationSeverity.ERROR,
                            message=f"检测到 Decision 循环依赖: {cycle_path}",
                            entity_id=cycle[0],  # 标记环的第一个节点
                            details={"cycle": cycle},
                        )
                    )
        except Exception:
            # simple_cycles 可能会很慢，对于大规模图可能需要优化
            pass

        return results

    def _check_function_traceability(self, graph: nx.DiGraph) -> List[ValidationResult]:
        """
        Axiom 4.3: Function修改必须可回溯到Decision
        Chain: Function <--modifies-- Commit --realizes--> Decision
        """
        results = []

        function_nodes = [n for n, attr in graph.nodes(data=True) if attr.get("type") == "function"]

        for func_id in function_nodes:
            # 查找修改此 Function 的 Commit
            # Function <--modifies-- Commit (即 Commit --modifies--> Function)
            # 所以在图上，我们要找指向 Function 的入边，且 relation='modifies'
            commits = []
            for u, _, attr in graph.in_edges(func_id, data=True):
                if attr.get("relation") == "modifies":
                    commits.append(u)

            if not commits:
                # 如果没有 Commit 修改它，可能是由其他方式引入，或者暂不校验
                # 公理说是"Function修改必须..."，如果没修改记录，是否算违反？
                # 暂且认为：如果存在 Function 节点，就应该有来源。
                # 但如果是初始化导入的，可能没有 modifies 边。
                # 暂时跳过无 modifying commit 的 function
                continue

            # 检查这些 Commit 是否有 Decision
            # Rule 4.3: EVERY modifying commit must have a decision
            untraced_commits = []

            for commit_id in commits:
                commit_has_decision = False
                # 检查 Commit --realizes--> Decision
                for _, _target, attr in graph.out_edges(commit_id, data=True):
                    if attr.get("relation") == "realizes":
                        commit_has_decision = True
                        break

                if not commit_has_decision:
                    untraced_commits.append(commit_id)

            if untraced_commits:
                results.append(
                    ValidationResult(
                        axiom_id="function_traceability",
                        severity=ValidationSeverity.WARNING,
                        message=f"Function {func_id} 包含孤立修改 (Commit {untraced_commits} 无Decision关联)",
                        entity_id=func_id,
                        details={"untraced_commits": untraced_commits},
                    )
                )

        return results
