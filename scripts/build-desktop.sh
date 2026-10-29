#!/usr/bin/env bash
# Package the Electron app for the current host OS.
# On Linux CI/dev VMs this can produce an AppImage smoke build; macOS .dmg and
# Windows NSIS must be built on macos-latest / windows-latest (see GitHub Actions).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/desktop"

if [[ ! -d node_modules ]]; then
  npm install
fi

# Sidecar must already exist under desktop/sidecar/ (from build-sidecar.sh/.ps1).
if [[ ! -e sidecar/music-scribe-helper && ! -e sidecar/music-scribe-helper.exe ]]; then
  echo "Missing desktop/sidecar helper binary. Run scripts/build-sidecar.sh first." >&2
  exit 1
fi

# Bundle a host ffmpeg into sidecar/bin so packaged Electron apps can decode
# without relying on GUI PATH (macOS GUI apps often omit ~/bin and Homebrew).
bundle_ffmpeg() {
  local dest="$ROOT/desktop/sidecar/bin"
  mkdir -p "$dest"
  local src=""
  if [[ -n "${MUSICSCRIBE_FFMPEG:-}" && -x "${MUSICSCRIBE_FFMPEG}" ]]; then
    src="$MUSICSCRIBE_FFMPEG"
  else
    for candidate in \
      "$HOME/bin/ffmpeg" \
      /usr/local/bin/ffmpeg \
      /opt/homebrew/bin/ffmpeg \
      "$(command -v ffmpeg 2>/dev/null || true)"; do
      if [[ -n "$candidate" && -x "$candidate" ]]; then
        src="$candidate"
        break
      fi
    done
  fi
  if [[ -z "$src" ]]; then
    echo "WARNING: no ffmpeg found to bundle; decode needs ffmpeg on the target machine." >&2
    return 0
  fi
  cp -f "$src" "$dest/ffmpeg"
  chmod +x "$dest/ffmpeg"
  # Prefer a sibling ffprobe when present (same directory as the resolved binary).
  local probe_src
  probe_src="$(dirname "$src")/ffprobe"
  if [[ -x "$probe_src" ]]; then
    cp -f "$probe_src" "$dest/ffprobe"
    chmod +x "$dest/ffprobe"
  fi
  echo "Bundled ffmpeg from $src -> sidecar/bin/ffmpeg"
}

bundle_ffmpeg

case "$(uname -s)" in
  Darwin) npm run dist:mac ;;
  Linux)  npx electron-builder --linux ;;
  MINGL*|MSYS*|CYGWIN*|Windows_NT) npm run dist:win ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

echo "Artifacts under desktop/dist/"
ls -la dist || true
if [[ -x sidecar/bin/ffmpeg ]]; then
  echo "Packaged ffmpeg present at desktop/sidecar/bin/ffmpeg"
fi
