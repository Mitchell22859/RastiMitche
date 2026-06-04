from pathlib import Path
from datetime import datetime
import shutil

root = Path.cwd()
backup_dir = root / "patch_backups" / ("remove_template_tags_from_py_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_dir.mkdir(parents=True, exist_ok=True)

changed = []

for path in root.rglob("*.py"):
    if any(part in {".venv", "venv", "__pycache__", "site-packages"} for part in path.parts):
        continue

    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines(True)

    new_lines = []
    removed = []

    for line in lines:
        s = line.strip()
        if s.startswith("{%") and s.endswith("%}"):
            removed.append(s)
            continue
        new_lines.append(line)

    if removed:
        rel = path.relative_to(root)
        backup_path = backup_dir / str(rel).replace("\\", "__").replace("/", "__")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)

        path.write_text("".join(new_lines), encoding="utf-8")
        changed.append((str(rel), removed))

print("Fixed python files:", len(changed))
for rel, removed in changed:
    print(rel, "removed:", removed)

print("Backup dir:", backup_dir)
