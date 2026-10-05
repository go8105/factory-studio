"""Package only the synthetic POC outputs and their reproducible generator."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent.parent
out = root / 'private/soap-poc'
with ZipFile(out / 'soap-poc-01.zip', 'w', ZIP_DEFLATED) as bundle:
    for file in sorted(out.iterdir()):
        if file.suffix in {'.stl', '.md', '.csv', '.json'}:
            bundle.write(file, file.name)
    bundle.write(root / 'tools/build-soap-poc.mjs', 'tools/build-soap-poc.mjs')
    bundle.write(root / 'package.json', 'package.json')
    bundle.write(root / 'package-lock.json', 'package-lock.json')
print(out / 'soap-poc-01.zip')
