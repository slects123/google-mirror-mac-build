# -*- coding: utf-8 -*-
import json
import urllib.request
from pathlib import Path

API = "http://154.8.236.49:8899"
data = json.loads(urllib.request.urlopen(f"{API}/api/licenses/sync", timeout=20).read())
lm = data["LICENSE_MAP"]
uk = set(data["UNLIMITED_KEYS"])
lines = [
    "# -*- coding: utf-8 -*-",
    '"""内置卡密数据（由服务器同步生成）"""',
    "",
    "LICENSE_MAP = {",
]
for k, v in sorted(lm.items()):
    lines.append(f'    "{k}": "{v}",')
lines.append("}")
lines.append("")
lines.append("UNLIMITED_KEYS = {")
for k in sorted(uk):
    lines.append(f'    "{k}",')
lines.append("}")
text = "\n".join(lines) + "\n"
targets = [Path(__file__).parent]
for extra in [r"D:\桌面\投屏\client_src", r"D:\桌面\投屏\exe_build"]:
    p = Path(extra)
    if p.exists() and p not in targets:
        targets.append(p)
for p in targets:
    (p / "licenses_data.py").write_text(text, encoding="utf-8")
    print("written", p / "licenses_data.py", "keys", len(lm))
