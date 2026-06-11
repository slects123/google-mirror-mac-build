# -*- coding: utf-8 -*-
"""生成密钥(10位)与密码(6位)，合并旧数据，并生成不限次数密钥。"""

import csv
import os
import random
import shutil
import string
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent


def get_release_dir():
    candidates = [
        Path(r"D:\桌面\谷歌框架简单远程操作 密钥版本"),
        Path(os.environ.get("USERPROFILE", "")) / "Desktop" / "谷歌框架简单远程操作 密钥版本",
        Path("D:/桌面") / "谷歌框架简单远程操作 密钥版本",
    ]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            continue
    fallback = ROOT / "release"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback

CHARS = string.ascii_uppercase + string.digits
NEW_COUNT = 1000
KEY_LEN = 10
PASS_LEN = 6


def _rand_code(length):
    return "".join(random.choice(CHARS) for _ in range(length))


def load_existing():
    py_file = ROOT / "licenses_data.py"
    if not py_file.exists():
        return {}, set()
    ns = {}
    exec(py_file.read_text(encoding="utf-8"), ns)
    return dict(ns.get("LICENSE_MAP", {})), set(ns.get("UNLIMITED_KEYS", []))


def _rand_unique_key(used_keys):
    while True:
        key = _rand_code(KEY_LEN)
        if key not in used_keys:
            return key


def generate_new_pairs(existing_map, count):
    used_keys = set(existing_map.keys())
    used_passwords = set(existing_map.values())
    pairs = []
    while len(pairs) < count:
        key = _rand_unique_key(used_keys)
        pwd = _rand_code(PASS_LEN)
        if pwd in used_passwords:
            continue
        used_keys.add(key)
        used_passwords.add(pwd)
        pairs.append((key, pwd))
    return pairs


def ensure_unlimited(existing_map, existing_unlimited):
    if existing_unlimited:
        key = next(iter(existing_unlimited))
        return existing_unlimited, {key: existing_map[key]}
    used_keys = set(existing_map.keys())
    used_passwords = set(existing_map.values())
    key = _rand_unique_key(used_keys)
    while True:
        pwd = _rand_code(PASS_LEN)
        if pwd not in used_passwords:
            break
    return {key}, {key: pwd}


def write_py(license_map, unlimited_keys):
    lines = [
        "# -*- coding: utf-8 -*-",
        "# 自动生成，请勿手动修改。",
        "LICENSE_MAP = {",
    ]
    for key, pwd in license_map.items():
        lines.append(f'    "{key}": "{pwd}",')
    lines.append("}")
    lines.append("UNLIMITED_KEYS = {")
    for key in sorted(unlimited_keys):
        lines.append(f'    "{key}",')
    lines.append("}")
    (ROOT / "licenses_data.py").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ordered_pairs(license_map, unlimited_keys):
    items = []
    for key in sorted(unlimited_keys):
        if key in license_map:
            items.append((key, license_map[key]))
    for key, pwd in license_map.items():
        if key not in unlimited_keys:
            items.append((key, pwd))
    return items


def write_csv(license_map, unlimited_keys, release_dir=None):
    release_dir = release_dir or get_release_dir()
    csv_path = release_dir / "自助框架教程_密钥密码表.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["序号", "密钥(10位)", "密码(6位)", "使用限制", "生成时间"])
        for i, (key, pwd) in enumerate(ordered_pairs(license_map, unlimited_keys), 1):
            limit = "不限次数" if key in unlimited_keys else "仅一次"
            writer.writerow([i, key, pwd, limit, now])
    return csv_path


def export_release_files(license_map, unlimited_keys):
    release_dir = get_release_dir()
    csv_path = write_csv(license_map, unlimited_keys, release_dir)
    exe_src = ROOT / "自助框架教程.exe"
    if exe_src.exists():
        shutil.copy2(exe_src, release_dir / "自助框架教程.exe")
    readme = ROOT / "使用说明.txt"
    if readme.exists():
        shutil.copy2(readme, release_dir / "使用说明.txt")
    return release_dir, csv_path


def main():
    existing_map, existing_unlimited = load_existing()
    old_count = len(existing_map)

    if len(sys.argv) > 1 and sys.argv[1] == "--export-only":
        license_map = existing_map
        unlimited_keys = existing_unlimited
    else:
        new_pairs = generate_new_pairs(existing_map, NEW_COUNT)
        unlimited_keys, unlimited_map = ensure_unlimited(existing_map, existing_unlimited)
        license_map = dict(existing_map)
        for key, pwd in new_pairs:
            license_map[key] = pwd
        license_map.update(unlimited_map)
        write_py(license_map, unlimited_keys)
        print(f"原有: {old_count} 组")
        print(f"新增: {len(new_pairs)} 组")

    release_dir, csv_path = export_release_files(license_map, unlimited_keys)

    print(f"不限次数: {len(unlimited_keys)} 组")
    print(f"合计: {len(license_map)} 组")
    if unlimited_keys:
        uk = sorted(unlimited_keys)[0]
        print(f"不限次数密钥(第1行): {uk}  密码: {license_map[uk]}")
    print(f"  {ROOT / 'licenses_data.py'}")
    print(f"  {release_dir}")


if __name__ == "__main__":
    main()
