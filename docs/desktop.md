# Desktop app packaging

Music Scribe ships as a **downloadable desktop app** (macOS + Windows) that embeds the
existing UI and a localhost-only Python helper. Songs never leave the machine.

## Architecture

- **Electron** loads a splash, starts the helper on `127.0.0.1` (auto-picks a free port if
  `8765` is busy), then opens the existing `frontend/` served by that helper.
- **PyInstaller sidecar** (`music-scribe-helper`) packages `bandscribe.server` for production.
- **Dev mode** spawns `.venv/bin/python` (macOS/Linux) or `.venv\Scripts\python.exe` (Windows)
  with `python -m bandscribe`.
- **Models** are downloaded on first run into the OS user-data folder (installer stays lean).
- **ffmpeg** for decode: Electron sets `PATH` + `IMAGEIO_FFMPEG_EXE` for the helper from a
  bundled `Resources/sidecar/bin/ffmpeg` (copied at package time) or common host paths
  (`~/bin`, `/usr/local/bin`, `/opt/homebrew/bin`). macOS GUI apps do not inherit shell PATH.

## Privacy invariants

- Helper bind address is forced to localhost (`127.0.0.1` / `localhost` / `::1` only).
- No cloud song storage; ephemeral jobs remain the default (`BANDSCRIBE_KEEP_JOBS` opt-in).
- Clear local data still wipes ephemeral jobs.

## Build & release

| Target | Where to build | Commands | Artifact |
|---|---|---|---|
| macOS `.dmg` | macOS host (iMac / `macos-latest`) | `./scripts/build-sidecar.sh` then `./scripts/build-desktop.sh` | `desktop/dist/*.dmg` |
| Windows NSIS | Windows host (`windows-latest`) | `.\scripts\build-sidecar.ps1` then `.\scripts\build-desktop.ps1` | `desktop/dist/*.exe` |

Full step-by-step: [`desktop/README.md`](../desktop/README.md).

Tag a release (`v0.1.0`) or run **Desktop release** via `workflow_dispatch` to build on
GitHub-hosted runners (see [`.github/workflows/desktop-release.yml`](../.github/workflows/desktop-release.yml)).

A Linux cloud agent cannot emit a signed (or generally usable) macOS `.dmg`; use a Mac or the
macOS CI job.
