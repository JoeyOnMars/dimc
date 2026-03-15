import ast


def scan_file(path):
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if decorated with @app.command or @something.command
            is_command = False
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and hasattr(dec.func, "attr")
                    and dec.func.attr == "command"
                ):
                    is_command = True
                    break

            if is_command:
                for arg in node.args.args:
                    if arg.annotation is None:
                        # Argument without type hint! THIS CAUSES TYPER CRASH with defaults
                        issues.append(
                            {
                                "func": node.name,
                                "arg": arg.arg,
                                "line": node.lineno,
                                "type": "missing_type_hint",
                            }
                        )
                    elif isinstance(arg.annotation, ast.Name) and arg.annotation.id == "bool":
                        pass  # bool is fine usually
                    # TODO: Check deeper logic

    return issues


if __name__ == "__main__":
    issues = scan_file("src/mal/cli.py")
    if not issues:
        print("✅ No missing type hints found!")
    else:
        print(f"❌ Found {len(issues)} issues:")
        for i in issues:
            print(
                f"  Line {i['line']}: Function '{i['func']}' arg '{i['arg']}' is missing type hint."
            )
