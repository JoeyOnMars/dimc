import ast


def apply_fix(path):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    lines = source.splitlines()
    insertions = []  # List of (line_idx, text) to insert

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            is_command = False
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and hasattr(dec.func, "attr")
                    and dec.func.attr == "command"
                ):
                    is_command = True
                    break
                # Also check scheduler_app.command, extract_app.command
                if (
                    isinstance(dec, ast.Call)
                    and hasattr(dec.func, "attr")
                    and dec.func.attr == "command"
                ):
                    # Check if it's app.command or something_app.command
                    if isinstance(dec.func, ast.Attribute):
                        is_command = True

            if is_command:
                # Find args with defaults
                args_with_defaults = []
                # defaults match last n args
                # node.args.defaults
                # node.args.args
                diff = len(node.args.args) - len(node.args.defaults)
                for i, default in enumerate(node.args.defaults):
                    arg_name = node.args.args[i + diff].arg
                    # We blindly add fix for ALL args to be safe, or check if default is call to typer?
                    # Safer to check if default is a Call
                    if isinstance(default, ast.Call):
                        # check if it is typer.Option or typer.Argument
                        # Or just assume it might be OptionalInfo
                        args_with_defaults.append(arg_name)

                if args_with_defaults:
                    # Check body for existing fixes
                    existing_logic = []
                    for stmt in node.body:
                        if isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Call):
                            # simplistic check: hasattr(arg, "default")
                            if hasattr(stmt.test.func, "id") and stmt.test.func.id == "hasattr":
                                if len(stmt.test.args) > 0 and isinstance(
                                    stmt.test.args[0], ast.Name
                                ):
                                    existing_logic.append(stmt.test.args[0].id)

                    # Calculate insertion content
                    to_insert = []
                    for arg in args_with_defaults:
                        if arg not in existing_logic:
                            indent = " " * node.body[0].col_offset
                            line = f'{indent}if hasattr({arg}, "default"): {arg} = {arg}.default'
                            to_insert.append(line)

                    if to_insert:
                        # Insert at start of body (before first statement)
                        # We use line number of first statement to insert before
                        insert_line = node.body[0].lineno - 1
                        insertions.append((insert_line, to_insert))

    # Apply insertions in reverse order to keep indices valid
    insertions.sort(key=lambda x: x[0], reverse=True)

    for line_idx, texts in insertions:
        for text in reversed(texts):
            lines.insert(line_idx, text)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Applied fixes to {len(insertions)} functions.")


if __name__ == "__main__":
    apply_fix("src/mal/cli.py")
