import json
path = r"C:\Users\87465\.codex\vendor_imports\skills-curated-cache.json"
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
skills = data.get("skills", [])
print(f"Cache last fetched: {data.get('fetchedAt', 'N/A')}")
print(f"Total cached skills: {len(skills)}")
names = [s["name"] for s in skills]
print(f"Sample names: {names[:10]}")
# Check if any of our skills are in cache
for target in ["decision-auditor", "军师", "chatgpt-advisor", "claude-advisor", "yuanbao-advisor", "hr-director", "qa-reviewer"]:
    found = [s["name"] for s in skills if target in s["name"] or target in s.get("id", "")]
    print(f"  {target}: {'FOUND' if found else 'MISSING'} -> {found}")
