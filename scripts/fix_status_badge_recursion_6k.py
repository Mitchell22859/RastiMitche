from pathlib import Path
from datetime import datetime
import shutil

root = Path.cwd()
backup_dir = root / "patch_backups" / ("fix_status_badge_recursion_6k_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_dir.mkdir(parents=True, exist_ok=True)

files = [
    root / "templates" / "includes" / "components" / "badge.html",
    root / "templates" / "includes" / "components" / "status_badge.html",
]

for path in files:
    if path.exists():
        backup_path = backup_dir / str(path.relative_to(root)).replace("\\", "__").replace("/", "__")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)

component = """{% load fa_labels %}
{# Central status badge component - no include to avoid recursion #}
<span class="{{ status|status_badge_classes }}">
    {% if label %}
        {{ label|status_fa }}
    {% else %}
        {{ status|status_fa }}
    {% endif %}
</span>
"""

for path in files:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(component, encoding="utf-8")

print("Rewritten badge components without nested include:")
for path in files:
    print(" -", path.relative_to(root))
print("Backup dir:", backup_dir)
