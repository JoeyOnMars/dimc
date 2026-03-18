from pathlib import Path

target = Path("src/dimcause/cli.py")
content = target.read_bytes()

# Decode as utf-8, ignore errors if any (though we expect valid utf-8 with invisible chars?)
text = content.decode("utf-8", errors="ignore")

# Strip non-ascii
clean_lines = []
for line in text.splitlines():
    # Keep only ascii
    new_line = "".join(c for c in line if ord(c) < 128)
    clean_lines.append(new_line)

# Write back
target.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
print(f"Sanitized {len(clean_lines)} lines.")
