"""Bundle the private v2 design, excluding earlier friction coupons."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent.parent
assets = root / "private/soap-poc"
with ZipFile(assets / "soap-poc-02.zip", "w", ZIP_DEFLATED) as bundle:
    for name in ["body-v2.stl", "lid-v2.stl", "rotor-v2.stl", "drawer-v2.stl", "hinge-pin-v2.stl", "assembly-v2.json", "DESIGN-v2.md", "dimensions-v2.svg"]:
        bundle.write(assets / name, name)
    bundle.write(root / "tools/build-soap-assembly.mjs", "tools/build-soap-assembly.mjs")
    for name in ["package.json", "package-lock.json"]:
        bundle.write(root / name, name)
