"""Synthetic chord accuracy checks (no Demucs / Whisper / Basic Pitch).

Expectations mirror the project calibration summaries under internal/calibration/
(diatonic loops, slash inversions, richer qualities).
"""
from __future__ import annotations

import unittest

import numpy as np

from bandscribe import chords

SR = 22050


def _tone(freq: float, dur: float, amp: float = 0.22) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    env = np.minimum(1.0, t / 0.02) * np.minimum(1.0, (dur - t) / 0.05)
    return amp * np.sin(2 * np.pi * freq * t) * env


def _chord(freqs: list[float], dur: float = 1.0) -> np.ndarray:
    return sum(_tone(f, dur) for f in freqs)


# MIDI-ish frequencies for common tones
F = {
    "C3": 130.81, "E3": 164.81, "G3": 196.00, "B3": 246.94, "D4": 293.66,
    "A2": 110.00, "F2": 87.31, "G2": 98.00, "B2": 123.47, "D3": 146.83,
    "C4": 261.63, "E2": 82.41, "Fs2": 92.50, "G4": 392.00,
    "Fs3": 185.00, "A3": 220.00, "Cs3": 138.59,
}

GMAJ9_FAMILY = {"Gmaj9", "Gmaj7", "Gadd9", "G9"}
BM7_FAMILY = {"Bm7", "Bm"}


def _recognize(harm: np.ndarray, bass: np.ndarray, beats: np.ndarray | None = None) -> dict:
    duration = len(harm) / SR
    if beats is None:
        n = max(1, int(round(duration)))
        beats = np.arange(n, dtype=float)
    return chords.recognize(harm, bass, SR, beats, duration)


def _root_quality(label: str) -> str:
    """Strip slash bass for comparisons that only care about root+quality."""
    return label.split("/", 1)[0]


class ChordAccuracyTests(unittest.TestCase):
    def test_let_it_be_style_c_am_f_g(self):
        # Calibration: let-it-be — C G Am F family; here the classic I–vi–IV–V loop.
        segs = [
            ([F["C3"], F["E3"], F["G3"]], F["C3"], "C"),
            ([F["A2"], F["C3"], F["E3"]], F["A2"], "Am"),
            ([F["F2"], F["A2"], F["C3"]], F["F2"], "F"),
            ([F["G2"], F["B2"], F["D3"]], F["G2"], "G"),
        ]
        harm = np.concatenate([_chord(fs) for fs, _, _ in segs])
        bass = np.concatenate([_chord([b]) for _, b, _ in segs])
        res = _recognize(harm, bass, np.array([0.0, 1.0, 2.0, 3.0]))
        got = [_root_quality(x) for x in res["beat_labels"]]
        self.assertEqual(got, [e for *_, e in segs])
        self.assertEqual(res["key"]["tonic"], "C")

    def test_knockin_style_g_d_am_c(self):
        # Calibration: knockin-on-heavens-door core tones G D Am C.
        segs = [
            ([F["G2"], F["B2"], F["D3"]], F["G2"], "G"),
            ([146.83, 185.00, 220.00], 146.83, "D"),  # D F# A
            ([F["A2"], F["C3"], F["E3"]], F["A2"], "Am"),
            ([F["C3"], F["E3"], F["G3"]], F["C3"], "C"),
        ]
        harm = np.concatenate([_chord(fs) for fs, _, _ in segs])
        bass = np.concatenate([_chord([b]) for _, b, _ in segs])
        res = _recognize(harm, bass, np.array([0.0, 1.0, 2.0, 3.0]))
        got = [_root_quality(x) for x in res["beat_labels"]]
        self.assertEqual(got, ["G", "D", "Am", "C"])

    def test_slash_inversions_c_over_e_and_g(self):
        # Calibration: cant-help-falling-in-love slash targets (C/E, C/G).
        harm = _chord([F["C3"], F["E3"], F["G3"]], 2.0)
        bass_e = _chord([F["E3"]], 2.0)
        res_e = _recognize(harm, bass_e, np.array([0.0, 1.0]))
        self.assertTrue(all(lbl == "C/E" for lbl in res_e["beat_labels"]), res_e["beat_labels"])

        bass_g = _chord([F["G2"]], 2.0)
        res_g = _recognize(harm, bass_g, np.array([0.0, 1.0]))
        self.assertTrue(all(lbl == "C/G" for lbl in res_g["beat_labels"]), res_g["beat_labels"])

    def test_slash_g_over_fs_walkdown(self):
        # Calibration: wonderwall G/F# walk — F# is maj7 below G, not a triad tone.
        harm = _chord([F["G2"], F["B2"], F["D3"]], 2.0)
        bass = _chord([F["Fs2"]], 2.0)
        res = _recognize(harm, bass, np.array([0.0, 1.0]))
        self.assertTrue(all(lbl == "G/F#" for lbl in res["beat_labels"]), res["beat_labels"])

    def test_creep_style_g_b_c_cm(self):
        # Calibration: creep — G B C Cm (chromatic iv).
        segs = [
            ([F["G2"], F["B2"], F["D3"]], F["G2"], "G"),
            ([123.47, 155.56, 185.00], 123.47, "B"),  # B D# F#
            ([F["C3"], F["E3"], F["G3"]], F["C3"], "C"),
            ([F["C3"], 155.56, F["G3"]], F["C3"], "Cm"),  # C Eb G
        ]
        harm = np.concatenate([_chord(fs) for fs, _, _ in segs])
        bass = np.concatenate([_chord([b]) for _, b, _ in segs])
        res = _recognize(harm, bass, np.array([0.0, 1.0, 2.0, 3.0]))
        got = [_root_quality(x) for x in res["beat_labels"]]
        self.assertEqual(got, ["G", "B", "C", "Cm"])

    def test_cmaj9_prefers_maj9_or_add9_family(self):
        # Richer vocabulary: C E G B D should not collapse only to C / wrong key forever.
        harm = _chord([F["C3"], F["E3"], F["G3"], F["B3"], F["D4"]], 2.0)
        bass = _chord([F["C3"]], 2.0)
        res = _recognize(harm, bass, np.array([0.0, 1.0]))
        quals = {_root_quality(x) for x in res["beat_labels"]}
        self.assertTrue(quals <= {"Cmaj9", "Cmaj7", "C9", "Cadd9", "C"}, quals)
        self.assertTrue(any(q in {"Cmaj9", "C9", "Cadd9", "Cmaj7"} for q in quals), quals)
        self.assertFalse(any("sus2" in q for q in quals), quals)

    def test_gmaj9_d_a_bm7_loop(self):
        # Calibration: 4 Guitar / maj9-loop sketch — Gmaj9 → D → A → Bm7.
        # Gmaj9 = G B D F# A; accept maj9/maj7/add9/9 family; Bm7 ≈ Bm.
        segs = [
            ([F["G2"], F["B2"], F["D3"], F["Fs3"], F["A3"]], F["G2"]),
            ([F["D3"], F["Fs3"], F["A3"]], F["D3"]),
            ([F["A2"], F["Cs3"], F["E3"]], F["A2"]),
            ([F["B2"], F["D3"], F["Fs3"], F["A3"]], F["B2"]),
        ]
        harm = np.concatenate([_chord(fs) for fs, _ in segs])
        bass = np.concatenate([_chord([b]) for _, b in segs])
        res = _recognize(harm, bass, np.array([0.0, 1.0, 2.0, 3.0]))
        got = [_root_quality(x) for x in res["beat_labels"]]
        self.assertIn(got[0], GMAJ9_FAMILY, got)
        self.assertEqual(got[1], "D", got)
        self.assertEqual(got[2], "A", got)
        self.assertIn(got[3], BM7_FAMILY, got)
        # Honest posterior confidence — finite, not hard-coded marketing floors.
        self.assertEqual(len(res["beat_confidence"]), 4)
        for c in res["beat_confidence"]:
            self.assertTrue(0.0 <= c <= 1.0, c)

    def test_gmaj9_loop_does_not_over_dwell(self):
        # Repeating 4-chord grid: stay-bias must not glue one triad for ~half the song.
        # Shared D/F#/A tones make plain D tempting; loop transitions keep the cycle.
        cycle = [
            ([F["G2"], F["B2"], F["D3"], F["Fs3"], F["A3"]], F["G2"], "G"),
            ([F["D3"], F["Fs3"], F["A3"]], F["D3"], "D"),
            ([F["A2"], F["Cs3"], F["E3"]], F["A2"], "A"),
            ([F["B2"], F["D3"], F["Fs3"], F["A3"]], F["B2"], "B"),
        ]
        n_reps = 3
        segs = cycle * n_reps
        harm = np.concatenate([_chord(fs) for fs, _, _ in segs])
        bass = np.concatenate([_chord([b]) for _, b, _ in segs])
        beats = np.arange(len(segs), dtype=float)
        res = _recognize(harm, bass, beats)

        def root_pc(label: str) -> str:
            q = _root_quality(label)
            if q.startswith("G"):
                return "G"
            if q.startswith("D"):
                return "D"
            if q.startswith("A"):
                return "A"
            if q.startswith("B"):
                return "B"
            return q

        pcs = [root_pc(x) for x in res["beat_labels"]]
        counts = {k: pcs.count(k) for k in ("G", "D", "A", "B")}
        total = len(pcs)
        self.assertEqual(total, len(segs), pcs)
        for k, n in counts.items():
            self.assertGreaterEqual(n, 2, f"{k} under-represented: {counts} labels={res['beat_labels']}")
            self.assertLessEqual(n / total, 0.5, f"{k} over-dwells: {counts} labels={res['beat_labels']}")
        # Sequence should still prefer the Gmaj9-family / D / A / Bm* cycle shape.
        for i in range(0, total, 4):
            self.assertIn(_root_quality(res["beat_labels"][i]), GMAJ9_FAMILY, res["beat_labels"])
            self.assertEqual(_root_quality(res["beat_labels"][i + 1]), "D", res["beat_labels"])
            self.assertEqual(_root_quality(res["beat_labels"][i + 2]), "A", res["beat_labels"])
            self.assertIn(_root_quality(res["beat_labels"][i + 3]), BM7_FAMILY, res["beat_labels"])
        for c in res["beat_confidence"]:
            self.assertTrue(0.0 <= c <= 1.0, c)

    def test_sus2_without_third_stays_sus2(self):
        # Bare 0+2+7 must still prefer sus2 (not flood maj9/add9).
        harm = _chord([F["G2"], F["A3"], F["D3"]], 2.0)
        bass = _chord([F["G2"]], 2.0)
        res = _recognize(harm, bass, np.array([0.0, 1.0]))
        quals = {_root_quality(x) for x in res["beat_labels"]}
        self.assertEqual(quals, {"Gsus2"}, quals)

    def test_root_position_has_no_slash(self):
        harm = _chord([F["C3"], F["E3"], F["G3"]], 2.0)
        bass = _chord([F["C3"]], 2.0)
        res = _recognize(harm, bass, np.array([0.0, 1.0]))
        self.assertEqual(res["beat_labels"], ["C", "C"])

    def test_transpose_preserves_slash(self):
        self.assertEqual(chords.transpose_name("C/E", 2, False), "D/F#")
        self.assertEqual(chords.transpose_name("G/F#", -2, False), "F/E")


if __name__ == "__main__":
    unittest.main()
