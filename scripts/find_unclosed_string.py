path = "src/mal/cli.py"
with open(path, encoding="utf-8") as f:
    lines = f.readlines()

in_string = False
start_line = -1

for i, line in enumerate(lines):
    idx = 0
    while True:
        try:
            # Find next """
            idx = line.index('"""', idx)
            # Found one. Toggle state.
            if not in_string:
                in_string = True
                start_line = i + 1
                # print(f"Start string at {start_line}")
            else:
                in_string = False
                # print(f"End string at {i + 1}")
            idx += 3
        except ValueError:
            break

if in_string:
    print(f"Unclosed string started at line {start_line}")
else:
    print("All strings closed.")
