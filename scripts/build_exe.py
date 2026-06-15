"""Build a standalone ``emublog2mlv`` executable with PyInstaller.

    pip install pyinstaller
    python scripts/build_exe.py

Produces ``dist/emublog2mlv.exe`` (Windows) or ``dist/emublog2mlv`` (Linux/macOS):
a single self-contained binary that needs no Python install.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ROOT, "scripts", "_entry.py")
SRC = os.path.join(ROOT, "src")


def main():
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "emublog2mlv",
        "--paths", SRC,
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", os.path.join(ROOT, "build"),
        "--noconfirm",
        ENTRY,
    ]
    print("running:", " ".join(args))
    raise SystemExit(subprocess.call(args))


if __name__ == "__main__":
    main()
