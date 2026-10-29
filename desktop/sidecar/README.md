# Sidecar placeholder

CI (and `scripts/build-sidecar.sh` / `scripts/build-sidecar.ps1`) place the
PyInstaller **music-scribe-helper** onedir contents here before `electron-builder`
runs. Do not commit large binaries.

Optional at package time (`scripts/build-desktop.sh`):

- `bin/ffmpeg` (and `bin/ffprobe` when available) — copied from the build host so
  the packaged Electron helper can decode audio without relying on GUI `PATH`.
  Override source with `MUSICSCRIBE_FFMPEG=/path/to/ffmpeg`.
