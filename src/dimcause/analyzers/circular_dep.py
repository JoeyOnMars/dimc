"""
Circular Dependency Detection - 循环依赖检测

使用 DFS 检测模块间的循环依赖
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class CircularDep:
    """循环依赖"""

    module_a: str
    module_b: str
    path: List[str]  # 循环路径

    def __str__(self) -> str:
        path_str = " -> ".join(self.path)
        return f"Circular dependency: {path_str}"


def detect_circular_deps(dependencies: Dict[str, Set[str]]) -> List[CircularDep]:
    """
    检测循环依赖

    Args:
        dependencies: {module: {depended_modules}} - 模块依赖关系

    Returns:
        List[CircularDep] - 检测到的循环依赖列表
    """
    circular_deps: List[CircularDep] = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def dfs(node: str, path: List[str]) -> None:
        """DFS 检测循环，检测所有循环而非只检测第一个"""
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in dependencies.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor, path.copy())
            elif neighbor in rec_stack:
                # 发现循环
                try:
                    cycle_start = path.index(neighbor)
                except ValueError:
                    continue
                cycle_path = path[cycle_start:] + [neighbor]

                # 去重：只记录 A->B 的循环，不记录 B->A
                if len(cycle_path) >= 2:
                    circular_deps.append(
                        CircularDep(module_a=path[cycle_start], module_b=neighbor, path=cycle_path)
                    )
            # 注意：不 return，继续检测其他循环

        rec_stack.remove(node)

    for node in dependencies:
        if node not in visited:
            dfs(node, [])

    return circular_deps


def detect_circular_deps_from_graph(graph_data: dict) -> List[CircularDep]:
    """
    从代码依赖图数据检测循环依赖

    Args:
        graph_data: {
            "dependencies": [(source, target, type), ...]
        }

    Returns:
        List[CircularDep]
    """
    # 构建依赖关系字典
    deps: Dict[str, Set[str]] = {}

    for source, target, dep_type in graph_data.get("dependencies", []):
        if dep_type == "imports":
            # 提取模块名（去掉文件路径）
            source_module = _extract_module_name(source)
            target_module = _extract_module_name(target)

            if source_module and target_module:
                if source_module not in deps:
                    deps[source_module] = set()
                deps[source_module].add(target_module)

    return detect_circular_deps(deps)


def _extract_module_name(entity_id: str) -> str:
    """从实体ID提取模块名"""
    # 文件路径 -> 模块名
    if entity_id.endswith(".py"):
        return entity_id.replace("\\", "/").split("/")[-1].replace(".py", "")
    return entity_id


# 便捷函数
def create_circular_dep_detector() -> "CircularDepDetector":
    """创建循环依赖检测器"""
    return CircularDepDetector()


class CircularDepDetector:
    """循环依赖检测器"""

    def __init__(self):
        self.dependencies: Dict[str, Set[str]] = {}

    def add_dependency(self, source: str, target: str) -> None:
        """添加依赖关系"""
        if source not in self.dependencies:
            self.dependencies[source] = set()
        self.dependencies[source].add(target)

    def detect(self) -> List[CircularDep]:
        """检测循环依赖"""
        return detect_circular_deps(self.dependencies)

    def reset(self) -> None:
        """重置"""
        self.dependencies = {}
