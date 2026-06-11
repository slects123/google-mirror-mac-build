# -*- coding: utf-8 -*-
"""密钥/密码校验：联网自动同步卡密，离线使用本地缓存。"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

LICENSE_API_BASE = os.environ.get("LICENSE_API_BASE", "http://154.8.236.49:8899")


def _usage_file_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "."))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "自助框架教程" / "license_usage.json"


def _sync_cache_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "."))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "自助框架教程" / "license_sync.json"


USAGE_FILE = _usage_file_path()
SYNC_CACHE = _sync_cache_path()


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _api_post(path, payload, timeout=12):
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{LICENSE_API_BASE}{path}",
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "mirror-app"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _api_get(path, timeout=12):
    try:
        req = urllib.request.Request(
            f"{LICENSE_API_BASE}{path}",
            headers={"User-Agent": "mirror-app"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _load_sync_cache():
    if not SYNC_CACHE.exists():
        return {}, set(), ""
    try:
        cached = json.loads(SYNC_CACHE.read_text(encoding="utf-8"))
        return (
            dict(cached.get("LICENSE_MAP") or {}),
            set(cached.get("UNLIMITED_KEYS") or []),
            cached.get("version") or "",
        )
    except Exception:
        return {}, set(), ""


def _save_sync_cache(license_map, unlimited, version=""):
    SYNC_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_CACHE.write_text(
        json.dumps(
            {
                "LICENSE_MAP": license_map,
                "UNLIMITED_KEYS": sorted(unlimited),
                "version": version or _now_str(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _merge_license_maps(base_map, base_unlimited, extra_map, extra_unlimited):
    merged = dict(base_map)
    merged.update(extra_map or {})
    merged_unlimited = set(base_unlimited or set())
    merged_unlimited.update(extra_unlimited or set())
    return merged, merged_unlimited


def sync_license_map_from_server(fallback_map=None, fallback_unlimited=None):
    """兼容旧调用：刷新卡密（联网优先，离线读缓存，最后回退内置数据）。"""
    return refresh_license_maps(fallback_map, fallback_unlimited)


def refresh_license_maps(fallback_map=None, fallback_unlimited=None):
    fallback_map = dict(fallback_map or {})
    fallback_unlimited = set(fallback_unlimited or [])
    cache_map, cache_unlimited, _cache_ver = _load_sync_cache()

    license_map, unlimited = _merge_license_maps(
        fallback_map, fallback_unlimited, cache_map, cache_unlimited
    )

    data = _api_get("/api/licenses/sync", timeout=15)
    if data and data.get("ok"):
        online_map = data.get("LICENSE_MAP") or {}
        online_unlimited = set(data.get("UNLIMITED_KEYS") or [])
        if online_map:
            license_map, unlimited = _merge_license_maps(
                license_map, unlimited, online_map, online_unlimited
            )
            _save_sync_cache(license_map, unlimited, data.get("version") or "")
            return license_map, unlimited

    if cache_map:
        license_map, unlimited = _merge_license_maps(
            fallback_map, fallback_unlimited, cache_map, cache_unlimited
        )
        return license_map, unlimited

    return fallback_map, fallback_unlimited


def bind_key_from_server(key):
    """联网查询单个新卡密并写入本地缓存，便于后续离线使用。"""
    key = key.strip().upper()
    data = _api_post("/api/license/lookup", {"key": key})
    if not data or not data.get("ok"):
        return None
    row = data.get("data") or {}
    password = (row.get("password") or "").strip().upper()
    if not password:
        return None
    unlimited = bool(row.get("unlimited"))
    cache_map, cache_unlimited, cache_ver = _load_sync_cache()
    cache_map[key] = password
    if unlimited:
        cache_unlimited.add(key)
    _save_sync_cache(cache_map, cache_unlimited, cache_ver)
    return {"password": password, "unlimited": unlimited}


def ensure_key_bound(key, license_map, unlimited_keys):
    """确保密钥已绑定到本地授权表（联网/离线均可）。"""
    key = key.strip().upper()
    if key in license_map:
        return license_map, unlimited_keys

    license_map, unlimited_keys = refresh_license_maps(license_map, unlimited_keys)
    if key in license_map:
        return license_map, unlimited_keys

    bound = bind_key_from_server(key)
    if bound:
        license_map = dict(license_map)
        unlimited_keys = set(unlimited_keys)
        license_map[key] = bound["password"]
        if bound["unlimited"]:
            unlimited_keys.add(key)
    return license_map, unlimited_keys


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


def _normalize_server_info(info):
    if not info:
        return info
    unlimited = bool(info.get("unlimited"))
    max_u = int(info.get("max_uses", 1) or 1)
    key_left = int(info.get("key_left", 0) or 0)
    pwd_left = int(info.get("pwd_left", 0) or 0)
    key_used = int(info.get("key_used", 0) or 0)
    created = info.get("created_at") or _now_str()
    return {
        "unlimited": unlimited,
        "first_used": created,
        "last_used": _now_str(),
        "entry_remaining": -1 if unlimited else key_left,
        "entry_total": -1 if unlimited else max_u,
        "entry_used": key_used,
        "password_remaining": -1 if unlimited else pwd_left,
        "password_total": -1 if unlimited else max_u,
        "expires_at": info.get("expires_at"),
        "created_at": info.get("created_at"),
    }


def _local_usage_info(key, unlimited=False, license_map=None):
    data = _load_local()
    meta = data["key_meta"].get(key, {})
    pwd = (license_map or {}).get(key, "")
    pwd_token = f"{key}:{pwd}" if pwd else ""
    pwd_left = -1 if unlimited else (0 if pwd_token and pwd_token in data["used_passwords"] else 1)
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


def format_usage_lines(info):
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


def try_consume_key(key, unlimited=False):
    ok, msg, _info = try_consume_key_with_info(key, unlimited=unlimited)
    return ok, msg


def try_consume_key_with_info(key, unlimited=False):
    key = key.strip().upper()
    data = _api_post("/api/license/consume_key", {"key": key})
    if data is not None:
        info = _normalize_server_info(data.get("info")) if data.get("info") else None
        return data.get("ok", False), data.get("message", ""), info

    cache_map, _, _ = _load_sync_cache()
    if unlimited:
        _record_local_key_use(key)
        info = _local_usage_info(key, unlimited=True, license_map=cache_map)
        info["entry_used"] = info.get("entry_used", 0) + 1
        return True, "验证成功（不限次数，离线）", info

    local = _load_local()
    if key in local["used_keys"]:
        return False, "此密钥已使用（离线记录）", _local_usage_info(
            key, unlimited=False, license_map=cache_map
        )
    if key not in cache_map:
        return False, "此密钥未同步到本地，请先联网验证一次。", None
    _record_local_key_use(key)
    return True, "验证成功（离线）", _local_usage_info(
        key, unlimited=False, license_map=cache_map
    )


def try_consume_password(key, password, unlimited=False):
    key = key.strip().upper()
    password = password.strip().upper()
    if unlimited:
        return True, ""
    data = _api_post("/api/license/consume_password", {"key": key, "password": password})
    if data is not None:
        return bool(data.get("ok")), data.get("message", "此密码已使用，无法再次运行。")

    local = _load_local()
    token = f"{key}:{password}"
    if token in local["used_passwords"]:
        return False, "此密码已使用（离线记录）"
    local["used_passwords"].append(token)
    _save_local(local)
    return True, "密码验证成功（离线）"
