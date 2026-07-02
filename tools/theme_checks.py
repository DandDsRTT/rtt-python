from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple


class _DarkCoverage(NamedTuple):
    props_by_selector: dict[str, set[str]]
    tokens: set[str]


_ASSETS = Path("rtt/app/assets")
_LIGHT = "rtt.css"
_DARK = "rtt-dark.css"

_THEMED_PROPS = frozenset(
    {
        "color",
        "background",
        "background-color",
        "background-image",
        "fill",
        "stroke",
        "border",
        "border-color",
        "border-top",
        "border-bottom",
        "border-left",
        "border-right",
        "border-top-color",
        "border-bottom-color",
        "border-left-color",
        "border-right-color",
        "outline",
        "outline-color",
        "box-shadow",
        "caret-color",
        "-webkit-text-fill-color",
        "accent-color",
    }
)

_COLOUR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|"
    r"\b(?:white|black|red|blue|green|gold|silver|gray|grey)\b"
)

_JS_COLOUR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")

INTENTIONALLY_THEME_NEUTRAL = {
    (".rtt-guide-card", "background"): "self-contained dark hover-card, same in both themes",
    (".rtt-guide-card", "color"): "self-contained dark hover-card, same in both themes",
    (".rtt-guide-card", "box-shadow"): "drop shadow, dark in both themes",
    (".rtt-guide-card-link", "color"): "link on the dark hover-card, same in both themes",
    (".rtt-guide-card-link:hover", "color"): "link on the dark hover-card, same in both themes",
    (
        ".rtt-cell.rtt-gridval:not(.rtt-cell-input)",
        "background",
    ): "white highlight, strength rides --hl",
    (".rtt-app .rtt-cell:focus-visible", "outline"): "a11y focus ring, legible on both surfaces",
    (
        ".rtt-plain-text-edit.rtt-plain-text-error .q-field__control",
        "border-color",
    ): "error-red accent, reads on both themes",
    (".q-tooltip.rtt-tip-error", "background"): "self-contained error tooltip bubble",
    (".q-tooltip.rtt-tip-error", "color"): "self-contained error tooltip bubble",
    (".rtt-zoom-help", "background"): "loupe help, documented same-grey-in-both in rtt.css",
    (".rtt-zoom-help", "color"): "loupe help, documented same-grey-in-both in rtt.css",
    (
        ".rtt-pending::selection, .rtt-pending ::selection",
        "background",
    ): "opaque text selection, documented same-in-both in rtt.css",
    (
        ".rtt-pending::selection, .rtt-pending ::selection",
        "color",
    ): "opaque text selection, documented same-in-both in rtt.css",
    (".rtt-speaker-float", "box-shadow"): "drop shadow, dark in both themes",
    (".rtt-busy-card", "box-shadow"): "drop shadow, dark in both themes",
    ("0%,90%", "box-shadow"): "visibility-preview pulse ring, a @keyframes stop with no selector",
    ("0%,90%", "background"): "visibility-preview pulse ring, a @keyframes stop with no selector",
}


def _without_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rules(css: str) -> list[tuple[str, list[tuple[str, str]]]]:
    parsed = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", _without_comments(css)):
        selector = " ".join(match.group(1).split())
        declarations = []
        for declaration in match.group(2).split(";"):
            if ":" in declaration:
                prop, _, value = declaration.partition(":")
                declarations.append((prop.strip(), value.strip()))
        parsed.append((selector, declarations))
    return parsed


def _without_body_qualifier(selector: str) -> str:
    selector = selector.strip()
    if selector.startswith("body"):
        head_and_rest = selector.split(None, 1)
        selector = head_and_rest[1] if len(head_and_rest) > 1 else ""
    return selector.strip()


def _dark_would_cover(prop: str, dark_props: set[str]) -> bool:
    accepted = {prop}
    if prop in ("border", "border-top", "border-bottom", "border-left", "border-right"):
        accepted |= {"border-color", prop + "-color"}
    if prop == "background":
        accepted |= {"background-color"}
    if prop == "outline":
        accepted |= {"outline-color"}
    return bool(accepted & dark_props)


def _declaration_gap(selector: str, prop: str, value: str, dark: _DarkCoverage) -> str | None:
    if not _COLOUR_LITERAL.search(value):
        return None
    if selector == ":root" and prop.startswith("--"):
        if prop not in dark.tokens:
            return f"{selector}  |  {prop}: {value}  (token has no dark redefinition)"
        return None
    if prop not in _THEMED_PROPS or (selector, prop) in INTENTIONALLY_THEME_NEUTRAL:
        return None
    parts = [_without_body_qualifier(part) for part in selector.split(",")]
    if all(_dark_would_cover(prop, dark.props_by_selector.get(part, set())) for part in parts):
        return None
    return f"{selector}  |  {prop}: {value}"


def css_theme_gaps(light: str, dark: str) -> list[str]:
    light_rules = _rules(light)
    dark_rules = _rules(dark) + [rule for rule in light_rules if "body.rtt-dark" in rule[0]]
    plain_rules = [rule for rule in light_rules if "body.rtt-dark" not in rule[0]]

    dark = _DarkCoverage(props_by_selector={}, tokens=set())
    for selector, declarations in dark_rules:
        props = {prop for prop, _ in declarations}
        for part in selector.split(","):
            dark.props_by_selector.setdefault(_without_body_qualifier(part), set()).update(props)
        dark.tokens.update(prop for prop, _ in declarations if prop.startswith("--"))

    gaps = []
    for selector, declarations in plain_rules:
        for prop, value in declarations:
            gap = _declaration_gap(selector, prop, value, dark)
            if gap is not None:
                gaps.append(gap)
    return gaps


def js_colour_literals(js_files: list[Path]) -> list[str]:
    hits = []
    for path in js_files:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        text = re.sub(r"//[^\n]*", "", text)
        for match in _JS_COLOUR_LITERAL.finditer(text):
            hits.append(f"{path.name}: {match.group(0)}")
    return hits


def collect(root: Path) -> list[str]:
    assets = root / _ASSETS
    light = (assets / _LIGHT).read_text()
    dark = (assets / _DARK).read_text()
    violations = [
        f"un-themed colour (no dark disposition): {gap}" for gap in css_theme_gaps(light, dark)
    ]
    violations += [
        f"raw colour literal in client JS (route it through a themed var): {hit}"
        for hit in js_colour_literals(sorted(assets.glob("*.js")))
    ]
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    violations = collect(root)
    for violation in violations:
        print(violation)
    if violations:
        print(f"\n{len(violations)} theme-coverage violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
