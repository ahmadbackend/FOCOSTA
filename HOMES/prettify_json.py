import json
from pathlib import Path

INPUT_ROOT = Path("private_by_location")
OUTPUT_ROOT = Path("private_pretty_final")

for path in INPUT_ROOT.rglob("*.json"):
    out_path = OUTPUT_ROOT / path.relative_to(INPUT_ROOT)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Prettified:", out_path)
