#!/bin/bash
# macOS cloud build script
set -eo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

APP_NAME="谷歌投屏"
SCRCPY_VER="v4.0"
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    SCRCPY_URL="https://github.com/Genymobile/scrcpy/releases/download/${SCRCPY_VER}/scrcpy-macos-aarch64-${SCRCPY_VER}.tar.gz"
else
    SCRCPY_URL="https://github.com/Genymobile/scrcpy/releases/download/${SCRCPY_VER}/scrcpy-macos-x86_64-${SCRCPY_VER}.tar.gz"
fi

echo "=== 1. Python ==="
python3 --version
VENV="$ROOT/.venv_mac"
python3 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install --upgrade pip -q
python -m pip install pyqt6 pyinstaller -q
PY="$VENV/bin/python"

echo "=== 2. adb/scrcpy ==="
if [ ! -f "$ROOT/adb" ] || [ ! -f "$ROOT/scrcpy" ]; then
    mkdir -p "$ROOT/runtime/scrcpy_dl"
    curl -fsSL "$SCRCPY_URL" -o "$ROOT/runtime/scrcpy.tar.gz"
    tar -xzf "$ROOT/runtime/scrcpy.tar.gz" -C "$ROOT/runtime/scrcpy_dl"
    find "$ROOT/runtime/scrcpy_dl" -type f \( -name adb -o -name scrcpy -o -name scrcpy-server -o -name '*.dylib' \) -exec cp {} "$ROOT/" \;
    chmod +x "$ROOT/adb" "$ROOT/scrcpy" 2>/dev/null || true
fi
for f in adb scrcpy scrcpy-server; do
    [ -f "$ROOT/$f" ] || { echo "missing $f"; exit 1; }
done

echo "=== 3. Software ==="
if [ ! -d "$ROOT/Software" ]; then
    curl -fsSL "${SOFTWARE_ZIP_URL:-http://154.8.236.49/download/software.zip}" -o "$ROOT/runtime/software.zip"
    unzip -q "$ROOT/runtime/software.zip" -d "$ROOT"
fi
[ -d "$ROOT/Software" ] || { echo "Software missing"; exit 1; }

echo "=== 4. licenses ==="
[ -f "$ROOT/licenses_data.py" ] || { echo "licenses_data.py missing"; exit 1; }

echo "=== 5. PyInstaller ==="
ADD_DATA=()
for f in adb scrcpy scrcpy-server; do
    ADD_DATA+=(--add-data "$ROOT/$f:.")
done
for f in "$ROOT"/*.dylib; do
    [ -f "$f" ] && ADD_DATA+=(--add-data "$f:.")
done
ADD_DATA+=(--add-data "$ROOT/Software:Software")
ADD_DATA+=(--add-data "$ROOT/app_icon.ico:.")
ADD_DATA+=(--add-data "$ROOT/app_icon.png:.")

ICON_ARG=()
[ -f "$ROOT/app_icon.icns" ] && ICON_ARG=(--icon "$ROOT/app_icon.icns")
[ -f "$ROOT/app_icon.ico" ] && ICON_ARG=(--icon "$ROOT/app_icon.ico")

rm -rf "$ROOT/build_tmp_mac"
"$PY" -m PyInstaller -y -w --name "$APP_NAME" "${ICON_ARG[@]}" \
    --distpath "$ROOT/dist_mac" --workpath "$ROOT/build_tmp_mac" --specpath "$ROOT/build_tmp_mac" \
    --clean --hidden-import licenses_data --hidden-import license_usage \
    "${ADD_DATA[@]}" "$ROOT/main.py"

APP_PATH="$ROOT/dist_mac/${APP_NAME}.app"
[ -d "$APP_PATH" ] || { echo "app bundle missing"; exit 1; }

echo "=== 6. DMG ==="
rm -rf "$ROOT/dmg_staging" "$ROOT/${APP_NAME}.dmg"
mkdir -p "$ROOT/dmg_staging"
cp -R "$APP_PATH" "$ROOT/dmg_staging/"
ln -s /Applications "$ROOT/dmg_staging/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$ROOT/dmg_staging" -ov -format UDZO "$ROOT/${APP_NAME}.dmg"
ls -lh "$ROOT/${APP_NAME}.dmg"
