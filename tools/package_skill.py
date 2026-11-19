#!/usr/bin/env python3
"""Build a skill-only import ZIP with SKILL.md at its root."""
from pathlib import Path
import zipfile

repo = Path(__file__).resolve().parents[1]
source = repo / "skills" / "product-demo-video"
target = repo / "dist" / "product-demo-video.zip"
files = []
for path in sorted(source.rglob("*")):
    relative = path.relative_to(source)
    if path.is_symlink():
        raise SystemExit(f"Refusing symlink in distribution: {relative}")
    if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
        continue
    if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
        files.append((path, relative.as_posix()))
if "SKILL.md" not in {name for _, name in files}:
    raise SystemExit("Missing root SKILL.md")
target.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path, name in files:
        entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        bundle.writestr(entry, path.read_bytes())
with zipfile.ZipFile(target) as bundle:
    if bundle.testzip() is not None or "SKILL.md" not in bundle.namelist():
        raise SystemExit("Invalid skill archive")
print(f"Built {target.relative_to(repo)} ({len(files)} files)")
