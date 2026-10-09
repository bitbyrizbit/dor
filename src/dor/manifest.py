import hashlib
import json
import pathlib
import platform
import subprocess
import time


def _run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return "unknown"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(path, config, outputs, extra=None):
    m = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "git_commit": _run(["git", "rev-parse", "--short", "HEAD"]),
         "git_dirty": bool(_run(["git", "status", "--porcelain"])),
         "python": platform.python_version(), "config": config,
         "outputs": {str(p): sha256(p) for p in map(pathlib.Path, outputs) if p.exists()}}
    if extra:
        m.update(extra)
    pathlib.Path(path).write_text(json.dumps(m, indent=1), encoding="utf-8")
