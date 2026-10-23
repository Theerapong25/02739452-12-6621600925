from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).parent
out = root.parent / "Notebook_Price_Exam_6621600925.zip"
skip_dirs = {".git", "research", "data", "tmp", "__pycache__", ".pytest_cache"}
skip_files = {".env", out.name}
with ZipFile(out, "w", ZIP_DEFLATED) as archive:
    for item in root.rglob("*"):
        if not item.is_file() or any(part in skip_dirs for part in item.relative_to(root).parts):
            continue
        if item.name in skip_files or item.suffix == ".pyc":
            continue
        archive.write(item, Path("notebook-price-comparison") / item.relative_to(root))
print(out)
