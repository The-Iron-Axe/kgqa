"""检查知识图谱连通分量（孤岛检测）。"""

from __future__ import annotations

import json
from collections import deque, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "ai_knowledge.json"


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    entities = {e["name"] for e in data["entities"]}
    adj: dict[str, set[str]] = defaultdict(set)
    for r in data["relations"]:
        s, t = r["source"], r["target"]
        if s in entities and t in entities:
            adj[s].add(t)
            adj[t].add(s)

    visited: set[str] = set()
    components: list[set[str]] = []
    for name in entities:
        if name in visited:
            continue
        q = deque([name])
        comp: set[str] = set()
        while q:
            n = q.popleft()
            if n in visited:
                continue
            visited.add(n)
            comp.add(n)
            for nb in adj[n]:
                if nb not in visited:
                    q.append(nb)
        components.append(comp)

    components.sort(key=len, reverse=True)
    print(f"entities={len(entities)} relations={len(data['relations'])} components={len(components)}")
    for i, comp in enumerate(components):
        names = sorted(comp)
        preview = ", ".join(names[:15])
        if len(names) > 15:
            preview += f" ... (+{len(names) - 15})"
        print(f"\n[{i + 1}] size={len(comp)}: {preview}")


if __name__ == "__main__":
    main()
