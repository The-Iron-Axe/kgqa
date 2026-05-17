import json
from collections import defaultdict
from pathlib import Path

data = json.loads(Path("data/raw/ai_knowledge.json").read_text(encoding="utf-8"))
deg = defaultdict(int)
for r in data["relations"]:
    deg[r["source"]] += 1
    deg[r["target"]] += 1

rows = sorted((deg.get(e["name"], 0), e["name"], e["type"]) for e in data["entities"])
Path("data/evaluation/low_degree.txt").write_text(
    "\n".join(f"{d}\t{n}\t{t}" for d, n, t in rows), encoding="utf-8"
)
print("written", len(rows), "lines")
