import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

_COMMON_FFMPEG_DIRS = (
    Path.home() / "bin",
    Path("/usr/local/bin"),
    Path("/opt/homebrew/bin"),
    Path("/usr/bin"),
)


def _env_ffmpeg() -> str | None:
    for key in ("IMAGEIO_FFMPEG_EXE", "FFMPEG_BINARY", "FFMPEG_PATH"):
        value = (os.environ.get(key) or "").strip()
        if value and Path(value).is_file():
            return value
    return None


def _which_on_path(name: str) -> str | None:
    found = shutil.which(name)
    return found if found else None


def _scan_common(name: str) -> str | None:
    for directory in _COMMON_FFMPEG_DIRS:
        candidate = directory / name
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        except OSError:
            continue
    return None


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """Resolve ffmpeg for decode/encode. Prefer Electron-injected env, then PATH, then common dirs."""
    return _env_ffmpeg() or _which_on_path("ffmpeg") or _scan_common("ffmpeg") or "ffmpeg"


@lru_cache(maxsize=1)
def ffprobe_exe() -> str:
    env = (os.environ.get("FFPROBE_BINARY") or "").strip()
    if env and Path(env).is_file():
        return env
    ffmpeg = ffmpeg_exe()
    if ffmpeg not in ("", "ffmpeg"):
        sibling = Path(ffmpeg).with_name("ffprobe")
        if sibling.is_file():
            return str(sibling)
    return _which_on_path("ffprobe") or _scan_common("ffprobe") or "ffprobe"


# Back-compat for imports that still read the module-level names.
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def _ffmpeg(*args: str) -> None:
    subprocess.run(
        [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", *args],
        check=True,
        capture_output=True,
    )


def to_wav(src: Path, dst: Path, sr: int = 44100) -> None:
    _ffmpeg("-i", str(src), "-vn", "-ac", "2", "-ar", str(sr), str(dst))


def to_mp3(src: Path, dst: Path) -> None:
    _ffmpeg("-i", str(src), "-vn", "-codec:a", "libmp3lame", "-b:a", "192k", str(dst))


def read_tags(src: Path) -> dict:
    """Return {'title': ..., 'artist': ...} from file metadata, if present."""
    try:
        out = subprocess.run(
            [ffprobe_exe(), "-v", "error", "-show_entries", "format_tags=title,artist",
             "-of", "json", str(src)],
            check=True, capture_output=True, text=True,
        ).stdout
        tags = json.loads(out).get("format", {}).get("tags", {})
        return {k.lower(): v for k, v in tags.items()}
    except Exception:
        return {}
