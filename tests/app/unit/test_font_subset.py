import string
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

from rtt.app.spreadsheet_text import _mathit
from tools.subset_fonts import TEXT_FACES, retain_unicodes

_ROOT = Path(__file__).resolve().parents[3]
_APP = _ROOT / "rtt" / "app"
_FONTS = _APP / "assets" / "fonts"

_SOURCE_FILES = (
    sorted(_APP.rglob("*.py"))
    + sorted(_APP.glob("assets/*.js"))
    + sorted(_APP.glob("assets/*.css"))
)


def _runtime_generated_codepoints() -> set[int]:
    generated: set[int] = set()
    for letter in string.ascii_lowercase:
        generated.update(ord(character) for character in _mathit(letter))
    return generated


def _emitted_codepoints() -> set[int]:
    seen: set[int] = set(_runtime_generated_codepoints())
    for path in _SOURCE_FILES:
        for character in path.read_text(encoding="utf-8"):
            if ord(character) >= 0x20:
                seen.add(ord(character))
    return seen


class TestFontSubsetCoverage:
    def test_every_emittable_codepoint_is_within_the_retain_set(self):
        keep = retain_unicodes()
        missing = sorted(c for c in _emitted_codepoints() if c not in keep)
        assert not missing, (
            "these codepoints appear in app source but fall outside tools/subset_fonts.RETAIN_BLOCKS, "
            "so the subset STIX faces would drop them and the browser would fall back to Georgia: "
            + ", ".join(f"U+{c:04X} {chr(c)!r}" for c in missing)
            + " — widen RETAIN_BLOCKS to cover them, then rerun tools/subset_fonts."
        )

    @pytest.mark.parametrize("face", TEXT_FACES)
    def test_subset_face_exists_and_was_actually_subset(self, face):
        path = _FONTS / f"{face}-subset.woff2"
        assert path.exists(), f"{face}-subset.woff2 is missing; run tools/subset_fonts"
        font = TTFont(path)
        assert font.flavor == "woff2"
        cmap = set(font.getBestCmap())
        stray = cmap - retain_unicodes()
        assert not stray, (
            f"{face}-subset.woff2 carries codepoints outside the retain set — it was not produced by "
            f"tools/subset_fonts against the current RETAIN_BLOCKS: {sorted(hex(c) for c in stray)[:8]}"
        )
        ascii_letters_and_digits = (
            set(range(0x30, 0x3A)) | set(range(0x41, 0x5B)) | set(range(0x61, 0x7B))
        )
        assert ascii_letters_and_digits <= cmap, (
            f"{face}-subset.woff2 dropped ASCII letters/digits — the subset is over-aggressive"
        )

    def test_full_unsubset_text_faces_are_no_longer_shipped(self):
        for face in TEXT_FACES:
            assert not (_FONTS / f"{face}.woff2").exists(), (
                f"{face}.woff2 (full, ~120 KB) is still shipped alongside its subset — remove it"
            )
