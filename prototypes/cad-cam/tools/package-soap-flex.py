from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent.parent
assets = root / "private/soap-poc"
with ZipFile(assets / "soap-poc-03.zip", "w", ZIP_DEFLATED) as bundle:
    for file in sorted(assets.glob("*-v3.stl")):
        bundle.write(file, file.name)
    for name in ["assembly-v3.json", "DESIGN-v3.md"]:
        bundle.write(assets / name, name)
    for name in ["build-soap-flex.mjs", "build-soap-assembly.mjs"]:
        bundle.write(root / "tools" / name, "tools/" + name)
    for name in ["package.json", "package-lock.json"]:
        bundle.write(root / name, name)
