path = r"C:\Users\87465\.agents\skills\decision-auditor\SKILL.md"
with open(path, "rb") as f:
    content = f.read()

# Check line endings
crlf = b"\r\n" in content
lf_only = b"\n" in content
print(f"CRLF: {crlf}, LF: {lf_only}")

# Split by lines
lines = content.split(b"\n")
print(f"Total lines: {len(lines)}")
for i in range(5, 11):
    if i < len(lines):
        print(f"Line {i+1}: {repr(lines[i][:100])}")
