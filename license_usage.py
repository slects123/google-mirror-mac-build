# -*- coding: utf-8 -*-
"""密钥/密码一次性使用记录（优先联网校验服务器，离线时使用本地记录）。"""

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

import sys

LICENSE_API_BASE = "http://154.8.236.49:8899"


def _usage_file_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "."))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "自助框架教程" / "license_usage.json"


USAGE_FILE = _usage_file_path()


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_local():
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            data.setdefault("used_keys", [])
            data.setdefault("used_passwords", [])
            data.setdefault("key_meta", {})
            return data
        except Exception:
            pass
    return {"used_keys": [], "used_passwords": [], "key_meta": {}}


def _save_local(data):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _api_post(path, payload):
    try:
        req = urllib.request.Request(
            f"{LICENSE_API_BASE}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _local_usage_info(key, unlimited=False):
    data = _load_local()
    meta = data["key_meta"].get(key, {})
    pwd = None
    try:
        from licenses_data import LICENSE_MAP
        pwd = LICENSE_MAP.get(key, "")
    except ImportError:
        pass
    pwd_left = -1 if unlimited else (0 if pwd and pwd in data["used_passwords"] else 1)
    if unlimited:
        return {
            "unlimited": True,
            "first_used": meta.get("first_used", _now_str()),
            "last_used": meta.get("last_used", _now_str()),
            "entry_remaining": -1,
            "entry_total": -1,
            "entry_used": int(meta.get("entry_count", 0)),
            "password_remaining": -1,
            "password_total": -1,
        }
    return {
        "unlimited": False,
        "first_used": meta.get("first_used", ""),
        "last_used": meta.get("last_used", ""),
        "entry_remaining": 0 if key in data["used_keys"] else 1,
        "entry_total": 1,
        "entry_used": 1 if key in data["used_keys"] else 0,
        "password_remaining": pwd_left,
        "password_total": 1,
    }


def _record_local_key_use(key):
    data = _load_local()
    now = _now_str()
    meta = data["key_meta"].setdefault(key, {})
    if not meta.get("first_used"):
        meta["first_used"] = now
    meta["last_used"] = now
    meta["entry_count"] = int(meta.get("entry_count", 0)) + 1
    if key not in data["used_keys"]:
        data["used_keys"].append(key)
    _save_local(data)
    return data


def format_usage_lines(info):
    """将使用信息格式化为展示行。"""
    if not info:
        return ["使用时间：--", "进入剩余：--", "稳定框架剩余：--"]

    def fmt_remain(remaining, total, unlimited):
        if unlimited or remaining == -1:
            return "不限次数"
        return f"{remaining} / {total} 次"

    first_used = info.get("first_used") or info.get("last_used") or _now_str()
    last_used = info.get("last_used") or first_used
    unlimited = bool(info.get("unlimited"))
    lines = [
        f"首次使用：{first_used}",
        f"最近使用：{last_used}",
        f"进入软件：{fmt_remain(info.get('entry_remaining', 0), info.get('entry_total', 1), unlimited)}",
        f"稳定框架：{fmt_remain(info.get('password_remaining', 0), info.get('password_total', 1), unlimited)}",
    ]
    if unlimited:
        used = int(info.get("entry_used", 0))
        if used > 0:
            lines.append(f"累计进入：{used} 次")
    return lines


def get_key_status(key, unlimited=False):
    result = _api_post("/api/key_status", {"key": key})
    if result and result.get("ok"):
        return result
    return _local_usage_info(key, unlimited=unlimited)


def is_key_used(key):
    data = _load_local()
    return key in data["used_keys"]


def is_password_used(password):
    data = _load_local()
    return password in data["used_passwords"]


def try_consume_key(key, unlimited=False):
    ok, msg, _info = try_consume_key_with_info(key, unlimited=unlimited)
    return ok, msg


def try_consume_key_with_info(key, unlimited=False):
    if unlimited:
        result = _api_post("/api/use_key", {"key": key})
        if result is not None:
            if result.get("ok"):
                return True, "", result
            return False, result.get("msg", "密钥不可用"), result
        _record_local_key_use(key)
        info = _local_usage_info(key, unlimited=True)
        info["entry_used"] = info.get("entry_used", 0) + 1
        return True, "", info

    result = _api_post("/api/use_key", {"key": key})
    if result is not None:
        if result.get("ok"):
            return True, "", result
        return False, result.get("msg", "此密钥已使用，无法再次进入。"), result

    data = _load_local()
    if key in data["used_keys"]:
        return False, "此密钥已使用，无法再次进入。", _local_usage_info(key, unlimited=False)
    _record_local_key_use(key)
    return True, "", _local_usage_info(key, unlimited=False)


def try_consume_password(key, password, unlimited=False):
    if unlimited:
        return True, ""
    result = _api_post("/api/use_password", {"key": key, "password": password})
    if result is not None:
        return bool(result.get("ok")), result.get("msg", "此密码已使用，无法再次运行。")
    data = _load_local()
    if password in data["used_passwords"]:
        return False, "此密码已使用，无法再次运行。"
    data["used_passwords"].append(password)
    _save_local(data)
    return True, ""
