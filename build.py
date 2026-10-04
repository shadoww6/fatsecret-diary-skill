"""Build dist/fatsecret-diary.zip — the file users upload to Claude as a skill."""

import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
SKILL = ROOT / "fatsecret-diary"
OUT = ROOT / "dist" / "fatsecret-diary.zip"

OUT.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for path in sorted(SKILL.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            z.write(path, path.relative_to(ROOT).as_posix())
print(f"Built {OUT.relative_to(ROOT)}")
