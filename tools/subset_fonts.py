from __future__ import annotations

import sys
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

UPSTREAM_STIX_FONTS = "https://github.com/stipub/stixfonts"

_ASSETS_FONTS = Path(__file__).resolve().parents[1] / "rtt" / "app" / "assets" / "fonts"

TEXT_FACES = (
    "STIXTwoText-Regular",
    "STIXTwoText-Italic",
    "STIXTwoText-Bold",
    "STIXTwoText-BoldItalic",
)

RETAIN_BLOCKS = (
    (0x0020, 0x007F, "Basic Latin"),
    (0x00A0, 0x00FF, "Latin-1 Supplement"),
    (0x0300, 0x036F, "Combining Diacritical Marks"),
    (0x0370, 0x03FF, "Greek and Coptic"),
    (0x02B0, 0x02FF, "Spacing Modifier Letters"),
    (0x1D00, 0x1DBF, "Phonetic Extensions"),
    (0x2000, 0x206F, "General Punctuation"),
    (0x2070, 0x209F, "Superscripts and Subscripts"),
    (0x20A0, 0x20CF, "Currency Symbols"),
    (0x2100, 0x214F, "Letterlike Symbols"),
    (0x2150, 0x218F, "Number Forms"),
    (0x2190, 0x21FF, "Arrows"),
    (0x2200, 0x22FF, "Mathematical Operators"),
    (0x2300, 0x23FF, "Miscellaneous Technical"),
    (0x2500, 0x257F, "Box Drawing"),
    (0x2600, 0x26FF, "Miscellaneous Symbols"),
    (0x2700, 0x27BF, "Dingbats"),
    (0x27C0, 0x27EF, "Miscellaneous Mathematical Symbols-A"),
    (0x2900, 0x297F, "Supplemental Arrows-B"),
    (0x2980, 0x29FF, "Miscellaneous Mathematical Symbols-B"),
    (0x2800, 0x28FF, "Braille Patterns"),
    (0x2C60, 0x2C7F, "Latin Extended-C"),
    (0xFB00, 0xFB4F, "Alphabetic Presentation Forms"),
    (0x1D400, 0x1D7FF, "Mathematical Alphanumeric Symbols"),
    (0xE000, 0xE0FF, "Private Use Area"),
)


def retain_unicodes() -> set[int]:
    keep: set[int] = set()
    for lo, hi, _name in RETAIN_BLOCKS:
        keep.update(range(lo, hi + 1))
    return keep


def subset_face(source: Path, destination: Path) -> None:
    font = TTFont(source)
    keep = sorted(retain_unicodes() & set(font.getBestCmap()))
    options = Options()
    options.flavor = "woff2"
    options.desubroutinize = True
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.notdef_outline = True
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=keep)
    subsetter.subset(font)
    font.save(destination)


def main(argv: list[str]) -> int:
    source_dir = Path(argv[0]) if argv else _ASSETS_FONTS
    for face in TEXT_FACES:
        source = source_dir / f"{face}.woff2"
        if not source.exists():
            source = source_dir / f"{face}-subset.woff2"
        destination = _ASSETS_FONTS / f"{face}-subset.woff2"
        before = source.stat().st_size
        subset_face(source, destination)
        after = destination.stat().st_size
        print(f"{face}: {before // 1024} KB -> {after // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
