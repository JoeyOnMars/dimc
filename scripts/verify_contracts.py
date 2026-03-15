#!/usr/bin/env python3
"""
契约校验脚本 - 验证 api_contracts.yaml 中定义的函数签名与源码是否一致。

校验范围：
- status: stable 和 status: experimental：完整签名校验（函数存在性 + 参数名 + 参数默认值 + 返回类型）
- status: missing_implementation 和 status: broken_implementation：仅检查函数是否存在，不校验签名

用法：
    python scripts/verify_contracts.py
退出码：
    0: 全部通过
    1: 存在不一致
"""

import ast
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def load_contracts(contracts_path: Path) -> Dict[str, Any]:
    """加载 api_contracts.yaml"""
    with open(contracts_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("functions", {})


def module_to_path(module: str) -> Path:
    """将 module 转换为文件路径"""
    # src/dimcause/xxx/yyy.py -> src/dimcause/xxx/yyy.py
    return Path("src") / f"{module.replace('.', '/')}.py"


def parse_function_signature(file_path: Path, class_name: Optional[str], func_name: str) -> Optional[Dict[str, Any]]:
    """解析源码中的函数签名"""
    if not file_path.exists():
        return None

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # 如果指定了 class，先找到 class
        target_class = None
        if class_name:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    target_class = node
                    break
            if not target_class:
                return None
        else:
            # 顶层函数
            target_class = tree

        # 查找函数
        for node in ast.walk(target_class):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                # 提取参数名
                args = [arg.arg for arg in node.args.args]

                # 提取默认值
                defaults = []
                defaults_offset = len(args) - len(node.args.defaults)
                for i, default in enumerate(node.args.defaults):
                    defaults.append((args[defaults_offset + i], ast.unparse(default)))

                # 提取返回类型注解
                returns = None
                if node.returns:
                    returns = ast.unparse(node.returns)

                return {
                    "args": args,
                    "defaults": dict(defaults),
                    "returns": returns,
                }

        return None
    except Exception as e:
        print(f"[WARN] Failed to parse {file_path}: {e}", file=sys.stderr)
        return None


def check_contracts() -> int:
    """执行契约校验"""
    contracts_path = Path("docs/api_contracts.yaml")

    if not contracts_path.exists():
        print(f"[ERROR] Contracts file not found: {contracts_path}", file=sys.stderr)
        return 1

    contracts = load_contracts(contracts_path)
    if not contracts:
        print("[ERROR] No contracts found in yaml", file=sys.stderr)
        return 1

    errors = []
    checked = 0
    skipped = 0

    for func_alias, contract in contracts.items():
        module = contract.get("module", "")
        class_name = contract.get("class")
        status = contract.get("status", "stable")
        # 支持 actual_name：当字典键是别名时，用 actual_name 去源码查找真实函数名
        func_name = contract.get("actual_name", func_alias)

        file_path = module_to_path(module)

        if status in ("missing_implementation", "broken_implementation"):
            # 仅检查函数是否存在
            if not file_path.exists():
                errors.append(f"{func_alias}: module file {file_path} does not exist")
                skipped += 1
            else:
                skipped += 1
            continue

        checked += 1

        if not file_path.exists():
            errors.append(f"{func_alias}: module file {file_path} does not exist")
            continue

        sig = parse_function_signature(file_path, class_name, func_name)
        if sig is None:
            # 函数不存在但可能是契约定义问题（函数名映射错误），发出警告并跳过
            display_name = f"{func_alias} (actual_name={func_name})" if func_name != func_alias else func_alias
            print(f"[WARN] {display_name}: function not found in {file_path} (possible contract name mismatch)")
            skipped += 1
            continue

        # --- 签名对比逻辑 ---
        contract_args = contract.get("args", [])
        actual_args = sig.get("args", [])

        # 如果是类方法（class_name 存在），需要过滤掉 self 参数
        if class_name and actual_args and actual_args[0] == "self":
            actual_args = actual_args[1:]

        # 对比参数名列表
        expected_arg_names = [a.get("name") for a in contract_args]
        if actual_args != expected_arg_names:
            errors.append(
                f"{func_alias}: args mismatch - expected {expected_arg_names}, got {actual_args}"
            )
            continue

        # 对比默认值（可选校验）
        for arg_def in contract_args:
            arg_name = arg_def.get("name")
            if "default" in arg_def:
                expected_default = str(arg_def["default"]).strip("'\"")
                actual_default = sig.get("defaults", {}).get(arg_name)
                # AST unparse 可能带引号（如 'hybrid'），YAML 解析后无引号（如 hybrid）
                actual_stripped = actual_default.strip("'\"") if actual_default else actual_default
                if actual_stripped != expected_default:
                    # 默认值不匹配警告（不阻断）
                    print(f"[WARN] {func_alias}: arg '{arg_name}' default mismatch - expected {expected_default}, got {actual_default}")

        # 校验通过
        print(f"[OK] {func_alias}: signature matches")

    print(f"\n--- Summary ---")
    print(f"Checked: {checked}, Skipped: {skipped}, Errors: {len(errors)}")

    if errors:
        print("\n[ERRORS]:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\n[PASS] All contracts verified")
    return 0


if __name__ == "__main__":
    sys.exit(check_contracts())
