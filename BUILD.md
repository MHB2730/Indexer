# Building Indexer

This produces a polished, offline Windows desktop installer
(`IndexerSetup.exe`) that users can run with a double-click.

## Prerequisites

1. **Python 3.11 or newer** — https://www.python.org/downloads/
   During install, tick "Add Python to PATH".
2. **Inno Setup 6** (only needed for the installer step) —
   https://jrsoftware.org/isinfo.php

That's it. PyInstaller, PySide6 and Pillow are installed automatically by
`build.ps1` into a local virtualenv.

## One-command build

Open PowerShell in the project folder and run:

```powershell
.\build.ps1
```

What this does, in order:

1. Creates `.venv\` and installs dependencies.
2. Generates the brand icons (`icon.png`, `icon.ico`) from
   `scripts/make_icons.py`.
3. Runs PyInstaller using `packaging/Indexer.spec`, producing
   `dist\Indexer\` (the runnable app folder with `Indexer.exe`).
4. Runs Inno Setup against `packaging/Indexer.iss`, producing
   `packaging\Output\IndexerSetup.exe`.

Final artefact: **`packaging\Output\IndexerSetup.exe`** — give this to
end users.

## Variants

* Skip the installer step (useful while iterating):
  ```powershell
  .\build.ps1 -SkipInstaller
  ```
  Run the result directly: `dist\Indexer\Indexer.exe`.

* Custom Inno Setup path:
  ```powershell
  .\build.ps1 -InnoSetup "D:\Tools\Inno\ISCC.exe"
  ```

## Cutting a release (auto-update channel)

The app checks https://github.com/MHB2730/Indexer/releases on launch. To
publish a new version that all installed apps will pick up:

1. Bump `__version__` in [src/indexer/__init__.py](src/indexer/__init__.py) — e.g. `"0.2.0"`.
2. Commit and push:
   ```powershell
   git add src/indexer/__init__.py
   git commit -m "Bump to 0.2.0"
   git push
   ```
3. Tag and push the tag:
   ```powershell
   git tag v0.2.0
   git push --tags
   ```

GitHub Actions ([.github/workflows/release.yml](.github/workflows/release.yml))
runs automatically: builds the installer with version stamping, creates a
GitHub Release, and attaches `IndexerSetup.exe`. Within seconds of the
workflow finishing, every running Indexer will offer the update on its
next launch.

**Important**: the tag must match `__version__` exactly. The workflow
fails fast if they disagree, to prevent shipping a broken update channel.

## Code signing (optional, recommended for distribution)

Unsigned installers trigger a SmartScreen warning. To sign:

1. Obtain an OV/EV code-signing certificate (DigiCert, Sectigo, etc.).
2. After PyInstaller, sign `dist\Indexer\Indexer.exe`:
   ```powershell
   signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 `
       /a dist\Indexer\Indexer.exe
   ```
3. Then build the installer; afterwards sign `IndexerSetup.exe` the same way.

## Running the dev app without building

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyside6 pillow
python scripts\make_icons.py
python -m indexer.app
```

## Sanity-check the engine

```powershell
python tests\make_fixtures.py
python tests\test_end_to_end.py
```

This generates a synthetic affidavit + candidate pool and runs the full
pipeline headless. You should see six annexures matched to their
documents with confidence scores.
