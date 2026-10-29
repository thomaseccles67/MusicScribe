# Music Scribe desktop (Electron)

Electron shell around the existing `frontend/` + localhost Python helper.

## Dev (macOS / Windows)

1. From the repo root, create the Python venv (`./setup.sh` or `.\setup.ps1`).
2. Install Electron deps:

```bash
cd desktop && npm install
```

3. Start the desktop shell (spawns `.venv` helper on `127.0.0.1`, splash while it boots):

```bash
npm run dev
```

On Windows PowerShell:

```powershell
cd desktop
npm install
npm run dev
```

The helper never binds `0.0.0.0`. Jobs stay ephemeral by default.

## Production layout

- `electron-builder` packs this app and copies `frontend/` + `desktop/sidecar/` into `resources/`.
- Production spawn uses the OS-native PyInstaller binary (`music-scribe-helper` / `.exe`).
- First-run model download UI writes weights under:
  - macOS: `~/Library/Application Support/MusicScribe/models`
  - Windows: `%LOCALAPPDATA%\MusicScribe\models`

## Build a macOS `.dmg` (run on a Mac)

Linux/cloud VMs **cannot** produce a usable macOS `.dmg`. Build on macOS (iMac / MacBook / `macos-latest` CI).

### Prerequisites

```bash
brew install git python@3.12 node@20 ffmpeg
# Node 20+ on PATH (brew link node@20 if needed)
# Packaged builds copy host ffmpeg into Resources/sidecar/bin (override: MUSICSCRIBE_FFMPEG=…)
```

### One-shot build

```bash
cd ~/MusicScribe   # or your clone
git pull origin main
./setup.sh
cd desktop && npm ci && cd ..
./scripts/build-sidecar.sh    # PyInstaller → desktop/sidecar/
./scripts/build-desktop.sh    # electron-builder --mac → desktop/dist/*.dmg
```

### Artifacts

| Output | Path |
|---|---|
| Sidecar onedir | `desktop/sidecar/` (`music-scribe-helper` + `_internal/`) |
| Installers | `desktop/dist/Music Scribe-*.dmg` (arm64 + x64 when built on Apple Silicon with default config) |

Open the `.dmg`, drag **Music Scribe** to Applications. First launch downloads models into
`~/Library/Application Support/MusicScribe/models`.

**Signing:** `desktop/package.json` sets `"identity": null` (ad-hoc / unsigned). On a pilot Mac,
right-click → **Open** the first time if Gatekeeper blocks it. Apple notarization is a follow-up
once a Developer ID cert exists.

### Windows (for reference)

```powershell
.\setup.ps1
cd desktop; npm ci; cd ..
.\scripts\build-sidecar.ps1
.\scripts\build-desktop.ps1   # → desktop/dist/*.exe
```

### CI release

GitHub Actions (`.github/workflows/desktop-release.yml`) builds **macos-latest** and
**windows-latest** on version tags (`v*`) or `workflow_dispatch`, and uploads the artifacts.
