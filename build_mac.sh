#!/bin/bash
# macOS 打包脚本：生成 谷歌投屏.app 并封装为 谷歌投屏.dmg
# 必须在苹果电脑（macOS）上运行，Windows 无法直接打出 DMG。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

APP_NAME="谷歌投屏"
SCRCPY_VER="v2.7"
SCRCPY_URL="https://github.com/Genymobile/scrcpy/releases/download/${SCRCPY_VER}/scrcpy-macos-${SCRCPY_VER}.zip"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=== 1. 检查 Python 环境 ==="
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    echo "未找到 python3，请先安装：brew install python@3.12"
    exit 1
fi
"$PYTHON_BIN" --version

echo "=== 2. 安装依赖 ==="
VENV="$ROOT/.venv_mac"
"$PYTHON_BIN" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip -q
python -m pip install pyqt6 pyinstaller -q
PYTHON_BIN="$VENV/bin/python"

echo "=== 3. 下载 macOS 版 adb/scrcpy ==="
if [ ! -f "$ROOT/adb" ] || [ ! -f "$ROOT/scrcpy" ]; then
    TMP_ZIP="$ROOT/runtime/scrcpy-macos.zip"
    TMP_DIR="$ROOT/runtime/scrcpy_mac_tmp"
    mkdir -p "$ROOT/runtime"
    curl -L "$SCRCPY_URL" -o "$TMP_ZIP"
    rm -rf "$TMP_DIR"
    unzip -q "$TMP_ZIP" -d "$TMP_DIR"
    find "$TMP_DIR" -maxdepth 3 -type f \( -name adb -o -name scrcpy -o -name scrcpy-server -o -name '*.dylib' \) -exec cp {} "$ROOT/" \;
    chmod +x "$ROOT/adb" "$ROOT/scrcpy" 2>/dev/null || true
    rm -rf "$TMP_ZIP" "$TMP_DIR"
fi
for f in adb scrcpy scrcpy-server; do
    if [ ! -f "$ROOT/$f" ]; then
        echo "缺少文件: $f"
        exit 1
    fi
done

echo "=== 3b. 下载 Software 资源包 ==="
if [ ! -d "$ROOT/Software" ]; then
    SW_URL="${SOFTWARE_ZIP_URL:-http://154.8.236.49/download/software.zip}"
    TMP_SW="$ROOT/runtime/software.zip"
    mkdir -p "$ROOT/runtime"
    curl -fsSL "$SW_URL" -o "$TMP_SW"
    unzip -q "$TMP_SW" -d "$ROOT"
    rm -f "$TMP_SW"
fi
if [ ! -d "$ROOT/Software" ]; then
    echo "Software 下载失败"
    exit 1
fi

echo "=== 4. 检查授权数据 ==="
if [ ! -f "$ROOT/licenses_data.py" ]; then
    echo "licenses_data.py 缺失"
    exit 1
fi

echo "=== 5. 收集打包资源 ==="
ADD_DATA=()
BUNDLE_FILES=(adb scrcpy scrcpy-server)
for f in "${BUNDLE_FILES[@]}"; do
    ADD_DATA+=(--add-data "$ROOT/$f:.")
done
for f in "$ROOT"/*.dylib; do
    [ -f "$f" ] || continue
    ADD_DATA+=(--add-data "$f:.")
done
if [ -d "$ROOT/Software" ]; then
    ADD_DATA+=(--add-data "$ROOT/Software:Software")
else
    echo "警告: 未找到 Software 目录，安装教程相关 APK 将无法使用"
fi

BUILD_TMP="$ROOT/build_tmp_mac"
rm -rf "$BUILD_TMP"

echo "=== 6. PyInstaller 打包 .app ==="
ICON_ARG=()
if [ -f "$ROOT/app_icon.icns" ]; then
    ICON_ARG=(--icon "$ROOT/app_icon.icns")
elif [ -f "$ROOT/app_icon.ico" ]; then
    ICON_ARG=(--icon "$ROOT/app_icon.ico")
fi

"$PYTHON_BIN" -m PyInstaller \
    -y -w \
    --name "$APP_NAME" \
    "${ICON_ARG[@]}" \
    --distpath "$ROOT/dist_mac" \
    --workpath "$BUILD_TMP" \
    --specpath "$BUILD_TMP" \
    --clean \
    --hidden-import licenses_data \
    --hidden-import license_usage \
    "${ADD_DATA[@]}" \
    "$ROOT/main.py"

APP_PATH="$ROOT/dist_mac/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "打包失败，未找到 $APP_PATH"
    exit 1
fi

echo "=== 7. 制作 DMG 安装包 ==="
DMG_STAGING="$ROOT/dmg_staging"
DMG_OUT="$ROOT/${APP_NAME}.dmg"
rm -rf "$DMG_STAGING" "$DMG_OUT"
mkdir -p "$DMG_STAGING"
cp -R "$APP_PATH" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_OUT"
rm -rf "$DMG_STAGING"

SIZE_MB=$(du -m "$DMG_OUT" | awk '{print $1}')
echo ""
echo "SUCCESS: $DMG_OUT (${SIZE_MB} MB)"
echo "将 DMG 发给 Mac 用户，拖入「应用程序」即可安装。"
echo "首次打开若提示「无法验证开发者」，请右键 -> 打开。"
