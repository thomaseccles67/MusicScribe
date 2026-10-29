"""ffmpeg resolution for packaged desktop (GUI PATH is often empty of Homebrew/~/bin)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bandscribe import audio


class FfmpegResolveTests(unittest.TestCase):
    def tearDown(self):
        audio.ffmpeg_exe.cache_clear()
        audio.ffprobe_exe.cache_clear()

    def test_prefers_imageio_ffmpeg_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "ffmpeg"
            fake.write_text("#!/bin/sh\n", encoding="utf-8")
            fake.chmod(0o755)
            with mock.patch.dict(
                os.environ,
                {"IMAGEIO_FFMPEG_EXE": str(fake), "PATH": "/usr/bin:/bin"},
                clear=False,
            ):
                audio.ffmpeg_exe.cache_clear()
                self.assertEqual(audio.ffmpeg_exe(), str(fake))

    def test_scans_home_bin_when_path_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "ffmpeg"
            fake.write_text("#!/bin/sh\n", encoding="utf-8")
            fake.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=False):
                for key in ("IMAGEIO_FFMPEG_EXE", "FFMPEG_BINARY", "FFMPEG_PATH"):
                    os.environ.pop(key, None)
                with mock.patch.object(audio, "_COMMON_FFMPEG_DIRS", (bin_dir,)):
                    with mock.patch.object(audio, "_which_on_path", return_value=None):
                        audio.ffmpeg_exe.cache_clear()
                        self.assertEqual(audio.ffmpeg_exe(), str(fake))


if __name__ == "__main__":
    unittest.main()
