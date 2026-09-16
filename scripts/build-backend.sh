#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="${PYTHON_BIN:-.venv/bin/python}"
mkdir -p .build
package_dir=$(mktemp -d "$PWD/.build/lambda-package-XXXXXX")
"$python_bin" -m pip install --index-url "${PACKAGE_INDEX_URL:-https://pypi.org/simple}" --target "$package_dir" \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: -r backend/requirements.txt
"$python_bin" - "$package_dir" <<'PY'
import pathlib,shutil,sys,zipfile
folder=pathlib.Path(sys.argv[1])
shutil.copytree('backend/src',folder/'src',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
with zipfile.ZipFile('.build/backend.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(folder.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
            item=zipfile.ZipInfo(str(path.relative_to(folder)),date_time=(2026,1,1,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(item,path.read_bytes())
shutil.rmtree(folder)
print('Built .build/backend.zip')
PY
