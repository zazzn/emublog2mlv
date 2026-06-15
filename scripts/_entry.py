"""PyInstaller entry point (kept separate so --paths src resolves the package)."""
from emublog2mlv.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
