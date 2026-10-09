import pathlib
import subprocess
import sys

RAW = pathlib.Path("data/raw")
PAIRS = [
    ("2025-07-21", "2025-08-02", "y25_0721"), ("2025-08-02", "2025-08-14", "y25_0802"),
    ("2025-08-14", "2025-08-26", "y25_0814"), ("2025-08-26", "2025-09-07", "y25_0826"),
    ("2024-07-14", "2024-07-26", "y24_0714"), ("2024-07-26", "2024-08-07", "y24_0726"),
    ("2024-08-07", "2024-08-19", "y24_0807"), ("2024-08-19", "2024-08-31", "y24_0819"),
    ("2024-08-31", "2024-09-12", "y24_0831"),
    ("2025-06-27", "2025-07-09", "pos2025"),
]
failed = []
for pre, post, tag in PAIRS:
    if (RAW / f"diff_terrain_{tag}.tif").exists():
        print("skip", tag)
        continue
    r = subprocess.run([sys.executable, "scripts/run_pair.py", pre, post, tag],
                       capture_output=True, text=True)
    lines = (r.stdout or "").strip().splitlines()
    print(tag, "rc", r.returncode)
    for ln in lines:
        if ln.startswith(("coregistration", "gcps used", "SUMMARY", "duplicate")):
            print("  ", ln[:220])
    if r.returncode != 0:
        failed.append(tag)
        print((r.stderr or "")[-600:])
print("failed:", failed)