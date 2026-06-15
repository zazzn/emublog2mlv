"""Build standalone ``emublog2mlv`` executables with PyInstaller.

    pip install pyinstaller
    python scripts/build_exe.py

Produces (in ``dist/``):
  emublog2mlv.exe      — command-line converter (console)
  emublog2mlv-gui.exe  — double-click GUI (windowed, no console)
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")
WORK = os.path.join(ROOT, "build")


def build_one(name, entry, windowed):
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", name,
        "--paths", SRC,
        "--distpath", DIST,
        "--workpath", WORK,
        "--specpath", WORK,
        "--noconfirm",
    ]
    if windowed:
        args.append("--windowed")
    args.append(entry)
    print("building", name)
    return subprocess.call(args)


def main():
    rc = build_one("emublog2mlv",
                   os.path.join(ROOT, "scripts", "_entry.py"), windowed=False)
    if rc == 0:
        rc = build_one("emublog2mlv-gui",
                       os.path.join(ROOT, "scripts", "_entry_gui.py"), windowed=True)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
