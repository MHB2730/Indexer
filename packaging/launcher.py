"""PyInstaller entry point. Keeps app.py as a proper package module."""
from indexer.app import main

if __name__ == "__main__":
    raise SystemExit(main())
