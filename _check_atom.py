import json

path = r"C:\Users\87465\.codex\.codex-global-state.json"
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

atom = data.get("electron-persisted-atom-state", {})
s = json.dumps(atom)

import re
# Find agents skills paths
paths = set(re.findall(r"agents\\\\skills[^\"'\\s]+", s))
print(f"Unique skill refs found: {len(paths)}")

# Check specific skills
check = ["decision-auditor", "chatgpt-advisor", "claude-advisor", "yuanbao-advisor", "hr-director", "qa-reviewer"]
for name in check:
    found = [p for p in paths if name in p]
    print(f"  {name}: {'FOUND' if found else 'MISSING'}")

# Look for structured skill list
import re
# Try to find a JSON array of skills
arrays = re.findall(r'\[.*?(?:skill|Skill)[^\]]*\]', s)[:5]
for arr in arrays:
    print(f"Array segment: {arr[:200]}")
