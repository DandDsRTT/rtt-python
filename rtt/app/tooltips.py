from __future__ import annotations

from dataclasses import dataclass, replace

from rtt.app import terminology
from rtt.app.spreadsheet_text import _pretransform_label

GUIDE_BASE = "https://en.xen.wiki/w/Dave_Keenan_%26_Douglas_Blumeyer%27s_guide_to_RTT"


def guide_url(chapter: str, section: str) -> str:
    anchor = "#" + section.replace(" ", "_") if section else ""
    return f"{GUIDE_BASE}/{chapter.replace(' ', '_')}{anchor}"


@dataclass(frozen=True)
class GuideHelp:
    text: str
    chapter: str = ""
    section: str = ""
    page: str = ""
    anchor: str = ""

    @property
    def location(self) -> str:
        if self.page:
            return self.anchor or self.page
        if self.chapter:
            tail = f"{self.chapter} › {self.section}" if self.section else self.chapter
            return f"D&D's Guide > {tail}"
        return ""

    @property
    def url(self) -> str:
        if self.page:
            anchor = "#" + self.anchor.replace(" ", "_") if self.anchor else ""
            return f"https://en.xen.wiki/w/{self.page.replace(' ', '_')}{anchor}"
        if self.chapter:
            return guide_url(self.chapter, self.section)
        return ""


GUIDE_HELP: dict[tuple[str, str], GuideHelp] = {
    ("mapping", "primes"): GuideHelp(
        "A mapping represents a temperament: one map per generator, each counting how many "
        "of that generator are used to approximate each prime. It is the central object of "
        "RTT.",
        "Mappings",
        "Mappings",
    ),
    ("vectors", "commas"): GuideHelp(
        "The commas this temperament tempers out — or in other words, (usually) small JI "
        "intervals it makes vanish — form an endless set; the comma basis is a minimal "
        "selection of them that generates all the rest by combination. Intervals differing "
        "by any such combination are thereby tempered together.",
        "Exploring temperaments",
        "Mapping-row-bases and comma bases",
    ),
    ("tuning", "generators"): GuideHelp(
        "The generator tuning map gives the size in cents of each generator. So while the mapping shows how the generators approximate the primes, this shows how large the generators actually are, thus pinning down the tuning.",
        "Tuning fundamentals",
        "Tuning",
    ),
    ("vectors", "targets"): GuideHelp(
        "The target intervals are the ones you want tuned well — usually the consonances "
        "your music leans on. The tuning is chosen to keep the damage across them as low as "
        "possible.",
        "Tuning fundamentals",
        "Target-intervals",
    ),
    ("damage", "targets"): GuideHelp(
        "Damage measures how badly the tuning serves an interval: how far its tempered size lands from just intonation, weighted by how much the accuracy of that interval matters.",
        "Tuning fundamentals",
        "Damage, error, and weight",
    ),
    ("weight", "targets"): GuideHelp(
        "The weights set how much each target's damage counts in the optimization, so the "
        "intervals you care about most pull the tuning hardest toward serving them.",
        "Tuning fundamentals",
        "Damage, error, and weight",
    ),
    ("vectors", "held"): GuideHelp(
        "The held intervals are the ones the tuning keeps pure: each dealt absolutely zero damage. The most common held interval is the octave.",
        "Tuning fundamentals",
        "Held-intervals",
    ),
    ("tuning", "primes"): GuideHelp(
        "The tuning map gives the tempered size in cents of each prime.",
        "Tuning fundamentals",
        "Temperament",
    ),
    ("just", "primes"): GuideHelp(
        "The just tuning map gives each prime's justly-intoned size in cents.",
        "Tuning fundamentals",
        "Primes",
    ),
    ("retune", "primes"): GuideHelp(
        "The retuning map gives each prime's retuning — the change the temperament makes to "
        "its tuning, from just to tempered.",
        "Tuning fundamentals",
        "Retuning map",
    ),
    ("complexity", "targets"): GuideHelp(
        "Each target interval's complexity — a measure of how complex the ratio is, with a "
        "larger value meaning more complex. It is what the damage weighting scales with.",
        "Tuning fundamentals",
        "Complexity",
    ),
    ("mapping", "commas"): GuideHelp(
        "The comma basis is mapped to all zeros, demonstrating how the temperament's mapping tempers out each of these commas.",
        "Mappings",
        "Making commas vanish",
    ),
    ("vectors", "primes"): GuideHelp(
        "The trivial JI mapping — each prime maps to itself. It is the identity every "
        "temperament departs from.",
        "Exploring temperaments",
        "JI as a temperament",
    ),
    ("mapping", "targets"): GuideHelp(
        "Each target interval mapped through the mapping, giving how many of each generator it takes to reach the temperament's version of that interval.",
        "Mappings",
        "Mappings",
    ),
    ("canonical", "primes"): GuideHelp(
        "The mapping rewritten into its canonical form, serving as a standard identifier "
        "for the temperament.",
        "Mappings",
        "Standard forms",
    ),
    ("tuning", "targets"): GuideHelp(
        "Each target interval's size in cents under this tempered tuning.",
        "Tuning fundamentals",
        "Temperament",
    ),
    ("retune", "targets"): GuideHelp(
        "Each target interval's error: the difference between its tempered and just tunings.",
        "Tuning fundamentals",
        "Errors",
    ),
    ("tuning", "commas"): GuideHelp(
        "The comma basis sized under the tempered tuning — all zero cents, because the "
        "temperament makes all of these commas vanish.",
        "Mappings",
        "Making commas vanish",
    ),
    ("counts", "primes"): GuideHelp(
        "The dimensionality is the count of domain basis elements, typically primes up to a prime limit.",
        "Mappings",
        "Matrices",
    ),
    ("counts", "generators"): GuideHelp(
        "The rank is how many generators the temperament has, or equivalently, its number of different step sizes. A rank-1 temperament (also known as an equal temperament) has exactly one generator / step size; a rank-2 temperament has two, and so on.",
        "Mappings",
        "Rank",
    ),
    ("counts", "commas"): GuideHelp(
        "Nullity counts the minimal number of commas necessary to describe every comma that the temperament tempers out. Said another way, it is the count of commas in the comma basis.",
        "Exploring temperaments",
        "Rank and nullity",
    ),
    ("counts", "targets"): GuideHelp(
        "The number of target intervals the tuning is optimizing for."
    ),
    ("mapping", "canonical_generators"): GuideHelp(
        "The form matrix maps the canonical form of the mapping to the form you're using.",
        page="Projection",
        anchor="Form matrix",
    ),
    ("vectors", "detempering"): GuideHelp(
        "Another way to think of your generators, as a corresponding list of simple example JI intervals, where each maps to a different one of the generators.",
        page="Generator preimage",
    ),
    ("vectors", "interest"): GuideHelp(
        "Other intervals you'd like to keep an eye on — neither targeted nor held, simply tracked so that you can watch how the temperament and tuning treat them."
    ),
    ("mapping", "detempering"): GuideHelp(
        "When the generator detempering is mapped, we get an identity matrix, because (by definition) each of the detempering's intervals maps to exactly its own generator.",
        page="Generator preimage",
    ),
    ("tuning", "detempering"): GuideHelp(
        "Detempering generators and then retempering them with the tuning map naturally "
        "yields a map identical to the generator tuning map.",
        page="Generator preimage",
    ),
    ("just", "detempering"): GuideHelp(
        "The justly-intoned size of the intervals chosen for this generator detempering.",
        page="Generator preimage",
    ),
    ("mapping", "generators"): GuideHelp(
        "The generators mapped through the mapping — the identity, since each generator "
        "maps to exactly itself.",
        "Mappings",
        "Mappings",
    ),
    ("canonical", "generators"): GuideHelp(
        "The inverse of the form matrix — it converts your mapping's generators back to the "
        "canonical ones.",
        page="Projection",
        anchor="Form matrix",
    ),
    ("canonical", "canonical_generators"): GuideHelp(
        "The form matrix times its inverse — the identity, since changing to your form and "
        "back leaves things unchanged.",
        page="Projection",
        anchor="Form matrix",
    ),
    ("tuning", "canonical_generators"): GuideHelp(
        "The generator tuning map for the canonical form's generators.",
        "Tuning fundamentals",
        "Generators",
    ),
    ("tuning", "held"): GuideHelp(
        "Each held interval's tempered size — equal to its just size, since the tuning holds "
        "it pure.",
        "Tuning fundamentals",
        "Held-intervals",
    ),
    ("just", "held"): GuideHelp(
        "Each held interval's just size in cents.", "Tuning fundamentals", "Held-intervals"
    ),
    ("retune", "held"): GuideHelp(
        "Each held interval's retuning — zero, because the tuning holds these intervals pure.",
        "Tuning fundamentals",
        "Held-intervals",
    ),
    ("just", "commas"): GuideHelp(
        "Each comma's just size in cents.", "Mappings", "Making commas vanish"
    ),
    ("retune", "commas"): GuideHelp(
        "Each comma's retuning — the negative of its just size, since the tuning shrinks it "
        "away to nothing.",
        "Mappings",
        "Making commas vanish",
    ),
    ("just", "targets"): GuideHelp(
        "Each target interval's just size in cents.", "Tuning fundamentals", "Primes"
    ),
    ("prescaling", "primes"): GuideHelp(
        "The complexity prescaler — the per-prime weighting applied before the optimization "
        "measures damage.",
        page="All-interval tuning schemes",
        anchor="Dual-norm prescalers",
    ),
    ("scaling_factors", "commas"): GuideHelp(
        "The scaling factors for the unrotated intervals of the projection — one for an "
        "unchanged interval, and zero for a comma.",
        page="Projection",
        anchor="Unrotated vectors and scaling factors",
    ),
    ("superspace_vectors", "primes"): GuideHelp(
        "The basis change matrix — it expresses your domain basis in a prime-only superspace, "
        "and thus can be used to map intervals from your domain to that superspace.",
        page="Domain basis",
        anchor="Basis matrix conversion",
    ),
    ("superspace_vectors", "superspace_primes"): GuideHelp(
        "The trivial JI mapping over the superspace's primes — the identity, since each "
        "superspace prime maps to itself."
    ),
    ("tuning", "superspace_primes"): GuideHelp(
        "The superspace tuning map gives the tempered size in cents of each superspace prime.",
        "Tuning fundamentals",
        "Temperament",
    ),
    ("tuning", "superspace_generators"): GuideHelp(
        "The size in cents of each superspace generator.", "Tuning fundamentals", "Tuning"
    ),
    ("just", "superspace_primes"): GuideHelp(
        "Each superspace prime's justly-intoned size in cents.",
        "Tuning fundamentals",
        "Primes",
    ),
    ("retune", "superspace_primes"): GuideHelp(
        "Each superspace prime's retuning — the change the temperament makes to its tuning, "
        "from just to tempered.",
        "Tuning fundamentals",
        "Retuning map",
    ),
    ("projection", "primes"): GuideHelp(
        "Uniquely identifies a specific tuning of a specific temperament — an idempotent (maps any interval it outputs to itself) rational (its entries are all ratios or integers, no irrationals) matrix which not only tempers out the temperament's commas, but also maps 𝑟 intervals to themselves (leaves them unchanged), where 𝑟 is the rank.",
        page="Projection matrix",
    ),
    ("projection", "generators"): GuideHelp(
        "The interval each generator is tuned to. These vectors entries are rational, but not necessarily integers, and thus the intervals are not necessarily JI.",
        page="Generator embedding matrix",
    ),
    ("projection", "canonical_generators"): GuideHelp(
        "The generator embedding for the canonical form's generators.",
        page="Generator embedding matrix",
    ),
    ("counts", "superspace_primes"): GuideHelp("The count of superspace primes."),
    ("counts", "superspace_generators"): GuideHelp("The number of superspace generators."),
}


def tile_guide_help(row_key: str, column_key: str) -> GuideHelp | None:
    return GUIDE_HELP.get((row_key, column_key))


def _relabeled(guide_help: GuideHelp | None, pretransform: bool) -> GuideHelp | None:
    if guide_help is not None and pretransform:
        relabeled = _pretransform_label(guide_help.text)
        if relabeled != guide_help.text:
            return replace(guide_help, text=relabeled)
    return guide_help


def tile_guide_help_for_cell(cell_id: str, *, pretransform: bool = False) -> GuideHelp | None:
    parts = cell_id.split(":")
    if len(parts) == 3 and parts[0] in ("symbol", "name", "label"):
        return _relabeled(tile_guide_help(parts[1], parts[2]), pretransform)
    return None


_HEADER_QUANTITIES = GuideHelp(
    "Each generator, prime, or interval in the grid shown as a ratio — the plain fraction naming it."
)
_HEADER_UNITS = GuideHelp(
    "Each value's unit — what the quantity is measured in (e.g. cents per prime, ¢/p)."
)

COLUMN_HEADER_HELP: dict[str, GuideHelp] = {
    "quantities": _HEADER_QUANTITIES,
    "units": _HEADER_UNITS,
    "canonical_generators": GuideHelp(
        "The generators of the mapping's canonical form — the standard generating set that "
        "identifies the temperament.",
        "Mappings",
        "Standard forms",
    ),
    "generators": GuideHelp(
        "The temperament's generators — the intervals every note is built by stacking. How many "
        "there are is the rank.",
        "Mappings",
        "Rank",
    ),
    "superspace_generators": GuideHelp(
        "The generators of the temperament lifted into the prime-only superspace.",
        page="Domain basis",
    ),
    "superspace_primes": GuideHelp(
        "The primes of the prime-only superspace the domain basis is lifted into.",
        page="Domain basis",
    ),
    "primes": GuideHelp(
        "The domain basis — the primes (or, for a nonstandard domain, the rationals) the "
        "temperament and its intervals are expressed over.",
        page="Domain basis",
    ),
    "detempering": GUIDE_HELP[("vectors", "detempering")],
    "commas": GUIDE_HELP[("vectors", "commas")],
    "held": GUIDE_HELP[("vectors", "held")],
    "targets": GUIDE_HELP[("vectors", "targets")],
    "interest": GUIDE_HELP[("vectors", "interest")],
}

ROW_HEADER_HELP: dict[str, GuideHelp] = {
    "counts": GuideHelp(
        "The dimension counts — dimensionality 𝑑 (the number of primes), rank 𝑟 (generators), "
        "and nullity 𝑛 (commas).",
        "Mappings",
        "Matrices",
    ),
    "quantities": _HEADER_QUANTITIES,
    "units": _HEADER_UNITS,
    "scaling_factors": GUIDE_HELP[("scaling_factors", "commas")],
    "vectors": GuideHelp(
        "Each interval written as a prime-count vector — the exponents giving how many of each "
        "prime it is built from."
    ),
    "canonical": GUIDE_HELP[("canonical", "primes")],
    "mapping": GUIDE_HELP[("mapping", "primes")],
    "superspace_vectors": GUIDE_HELP[("superspace_vectors", "primes")],
    "superspace_mapping": GuideHelp(
        "The temperament's mapping lifted into the prime-only superspace.",
        page="Domain basis",
    ),
    "superspace_projection": GuideHelp(
        "The temperament's projection lifted into the prime-only superspace.",
        page="Domain basis",
    ),
    "projection": GUIDE_HELP[("projection", "primes")],
    "tuning": GUIDE_HELP[("tuning", "primes")],
    "just": GUIDE_HELP[("just", "primes")],
    "retune": GUIDE_HELP[("retune", "primes")],
    "prescaling": GUIDE_HELP[("prescaling", "primes")],
    "complexity": GUIDE_HELP[("complexity", "targets")],
    "weight": GUIDE_HELP[("weight", "targets")],
    "damage": GUIDE_HELP[("damage", "targets")],
}


def header_guide_help(cell_id: str, *, pretransform: bool = False) -> GuideHelp | None:
    parts = cell_id.split(":")
    if len(parts) == 2 and parts[0] == "header":
        return _relabeled(COLUMN_HEADER_HELP.get(parts[1]), pretransform)
    if len(parts) == 2 and parts[0] == "label":
        return _relabeled(ROW_HEADER_HELP.get(parts[1]), pretransform)
    return None


_TOOLBAR_HELP = {
    "undo": "Undo the last change. (⌘/Ctrl+Z)",
    "redo": "Redo the change you undid. (⌘/Ctrl+Y, or ⌘/Ctrl+Shift+Z)",
    "reset": "Reset everything — settings, layout, and values — to the defaults.",
    "share": "Copy a shareable link to this exact state (undo history not included).",
    "tour": "Replay the guided tour of the app.",
}


_SETTINGS_TOGGLE_HELP = {
    "settings": "Show or hide the Show settings panel. (⌘/Ctrl+,)",
}


_VISUAL_FEATURE_HELP = {
    "dark_mode": "Light/dark mode.",
    "animations": "Animate grid changes — slide and fade rows, columns and cells in and out as they appear, move or leave. Off makes every change snap instantly.",
    "preview_highlighting": "Highlight what a control would do before you click it — hovering a +/− or a chooser option rings the cells it would change (amber), remove (red) or add (green). Off hides the preview.",
    "tooltips": "Show the hover tooltips that explain each control, value and setting (like this one).",
}


_GUIDE_SETTING_HELP = {
    "chapter": "Reveal the Show controls chapter by chapter as they're introduced in D&D's guide — slide left for a simpler view, right to expose more. The ★ notch shows everything.",
    "terminology": "Choose how terms are shown: Dave & Douglas's systematic terminology, the more common xenharmonic-wiki names, or both — D&D's with the wiki name in parentheses.",
    "ebk": "Frame every matrix and vector in EBK (Extended Bra-Ket) notation — the angle ⟨…] of a map, the ket […⟩, the curved angle ⧼ of a generator map. Choose plain matrices to replace it everywhere: square braces throughout, a superscript ᵀ marking the vector kind.",
}


_TILE_FEATURE_HELP = {
    "names": "Show each tile's name (e.g. “mapping”, “generators”).",
    "mnemonics": "Underline the letter of each name that its symbol uses — a memory aid. Refines “names”.",
    "symbols": "Show each value's math symbol (𝑀, 𝒈, 𝒕, …).",
    "header_symbols": "Show the row and column header symbols (𝒎₁, 𝐜₁, …) labelling each matrix's rows and columns.",
    "equivalences": "Show each symbol's defining equation (e.g. 𝒕 = 𝒈𝑀) instead of the bare glyph. Refines “symbols”.",
    "gridded_values": "Lay the values out in the grid as matrix and vector cells.",
    "brackets": "Draw the enclosing brackets around every gridded matrix and vector. Off removes them entirely — the values stay, just unenclosed (plain text is unaffected). Whether the brackets that DO show are EBK or plain matrices is the separate “EBK” toggle.",
    "plain_text_values": "Show each value as one plain-text string (e.g. ⟨1 0 -4]) below its tile.",
    "charts": "Draw a bar chart over each charted row's values.",
    "tile_controls": "Show the additional tile controls — the radio pickers (weight slope, domain approach, monotone/tradeoff, all-interval, replace diminuator) and the power inputs (norm power, minimized power mean, optimization power).",
    "tile_collapse": "Show the fold control on each tile — the button that collapses a tile down to its name and expands it again. Hide it to keep every tile open with no fold controls.",
    "presets": "Show the preset choosers — temperament, tuning scheme, and target set.",
    "quantities": "Show the numeric quantities inside the value cells.",
    "decimals": "Show the decimal fraction of each value (the .955 beneath the 701). Off rounds every value in the app to the nearest integer. Refines “quantities”.",
    "tile_units": "Show each tile's “units: …” line (e.g. ¢/p, g/p).",
    "cell_units": "Show each value's unit beneath its own cell (e.g. ¢/p₁, 𝒈₁).",
    "math_expressions": "Show just values as closed-form expressions (e.g. 1200·log₂(3/2)).",
    "drag_to_combine": "Show drag handles for combining basis elements: drag one generator row (or one interval) onto another to add it in.",
}


_APP_FEATURE_HELP = {
    "select_all": "Turn every available Show toggle on, or all off.",
    "controls": "Show or hide the grid's interaction controls as a group — the reorder grips, the row and column collapse chevrons, and the add/remove buttons.",
    "rowcol_collapse": "Show the fold chevrons on the row labels and column headers (and the corner all-fold) that collapse whole rows and columns.",
    "add_remove_buttons": "Show the − and + buttons that remove or add mapping rows, primes, commas, targets, held, and interest intervals.",
    "reorder_grips": "Show the drag-to-reorder grips riding each gridline — drag one to reorder the commas, targets, held, or interest intervals, or drag a trunk grip to reorder a whole row or column.",
    "basic": "Expand the basic settings — counts, interval ratios and vectors, EBK, units, and other intervals of interest. A grouping toggle; it shows nothing of its own.",
    "counts": "Show the dimension counts — dimensionality 𝑑, rank 𝑟, nullity 𝑛.",
    "interval_ratios": "Show the interval ratios row and column.",
    "interval_vectors": "Show the interval vectors row.",
    "app_units": "Show the units row and column.",
    "interest": "Show the “other intervals of interest” column.",
    "temperament": "Expand the temperament settings — the temperament tiles, their colorization, and the nonstandard-domain superspace block. A grouping toggle; it shows nothing of its own.",
    "temperament_tiles": "Show the temperament tiles — the mapping 𝑀 and the comma basis C.",
    "temperament_colorization": "Tint each cell by what derives it — the mapping 𝑀 or the comma basis C. Refines “temperament tiles”.",
    "mapping_demos": "Hover an interval to overlay how the mapping 𝑀 sends it to its generator counts — yellow lines trace each prime count down its mapping column, multiply it into each cell, sum each row, and carry the row’s total over to the mapped interval’s generator count. Refines “temperament”.",
    "tuning": "Expand the tuning settings — the tuning tiles and everything beneath them. A grouping toggle; it shows nothing of its own.",
    "tuning_tiles": "Show the tuning tiles — the generator tuning map, prescaler, damage, and more.",
    "optimization": "Show the optimization tile — the mean damage and the power 𝑝.",
    "tuning_ranges": "Chart each generator's tuning range as an I-beam under the generator tuning map.",
    "weighting": "Show the weighting tiles — the prescaler, the complexity 𝒄, and the weight 𝒘.",
    "all_interval": "Show the all-interval control — optimize over every interval rather than a finite target list.",
    "alt_complexity": "Show the alternative-complexity controls — the prescaler tile 𝐋 and the wider choice of interval-complexity measures.",
    "custom_weights": "Make the 𝒘 row editable so you can set your own damage weight per target interval. It starts seeded from the current slope, so the damage weight slope stays selected until you edit a weight away from it — at which point the slope deselects, just like a matrix cell moving off its preset. Picking a slope, complexity, or prescaler re-seeds the weights; all-interval mode suspends editing until you leave it.",
    "nonstandard_domain": "Show the superspace block — the basis change matrix Bₗ, the lifted mapping 𝑀ₗ, and (over a domain with nonprime basis elements) the prime/nonprime-based mode chooser.",
    "projection": "Show the projection tile — the rational projection 𝑃 = 𝐺𝑀 holding the just primes.",
    "tuning_colorization": "Tint each cell by what derives it — the generator tuning map 𝒈. Refines “tuning tiles”.",
    "other": "Expand the other settings — projection, generator detempering, and identity objects. A grouping toggle; it shows nothing of its own.",
    "form": "Expand the form settings — the form tiles and their colorization. A grouping toggle; it shows nothing of its own.",
    "form_tiles": "Show the canonical (default) form — off canonical, as its own row plus the form matrix 𝐹; on canonical, as a subscript C on the mapping 𝑀, generator tuning map 𝒈, and generator embedding G. Adds the <choose form> dropdowns that rewrite the mapping or comma basis into a chosen form.",
    "form_colorization": "Tint the cells touched by the form 𝐹. Refines “form”.",
    "generator_detempering": "Show the generator-detempering D column — the generator map written as vectors.",
    "identity_objects": "Show the identity-object tiles — trivial self-maps built from the other tiles.",
}


_DRAWER_CHROME = frozenset({"dark_mode", "select_all"})


SHOW_HELP: dict[str, str] = {
    key: text
    for group in (_VISUAL_FEATURE_HELP, _TILE_FEATURE_HELP, _APP_FEATURE_HELP)
    for key, text in group.items()
    if key not in _DRAWER_CHROME
}


def show_help(key: str, mode: str = terminology.DD) -> str:
    return terminology.substitute(SHOW_HELP[key], mode)


_CHROME_HELP: dict[str, str] = {
    **_TOOLBAR_HELP,
    **_SETTINGS_TOGGLE_HELP,
    "dark_mode": _VISUAL_FEATURE_HELP["dark_mode"],
    **_GUIDE_SETTING_HELP,
    "select_all": _APP_FEATURE_HELP["select_all"],
}


def chrome_help(key: str) -> str:
    return _CHROME_HELP[key]


TEXT_FORM_HELP = (
    "Show or hide the tile's features as a checklist — the same show/example rows as the app "
    "features below — for settings that are fiddly to click on the tile itself."
)

_AUDIO_HELP: dict[str, str] = {
    "mute": (
        "Mute or unmute all audio. When on, ratios, interval vectors, and cents values can be sounded. Can be flipped off and back on to kill anything sounding."
    ),
    "wave": "Cycle the waveform that every pitch sounds — sine, square, triangle, sawtooth.",
    "mode": "Cycle the play mode — single note, arpeggio, chord, rolled chord. When anything other than single note, uses all the intervals in the given set.",
    "hold": "Toggle whether the given play mode occurs just once, or repeats/persists.",
    "root": "Toggle the 1/1 root drone sounding underneath.",
    "pump_size": (
        "How many notes sound per comma-pump chord — 1 is the bare root, 2 adds the third (so you "
        "hear major or minor), 3 the full triad, 4 adds an octave. Hover a comma's column to start a pump."
    ),
    "pump_tempo": "Comma-pump tempo — whole-note chords per minute.",
    "pump_type": (
        "The chord built on each comma-pump root. 'mixed' follows the pump's own major/minor "
        "quality per chord; the others stack one fixed shape, tuned to the temperament. The "
        "available types depend on the chord size."
    ),
}


def audio_help(control: str) -> str:
    return _AUDIO_HELP[control]


RATIO_REDUCE_HELP = "Octave-reduce this interval, i.e. divide or multiply it by 2 until it is between 1 and 2. When the first element of the domain basis is not 2, it is taken as the equave, and this button equave-reduces instead."
RATIO_RECIPROCATE_HELP = (
    "Reciprocate this interval — swap its numerator and denominator (e.g. 3/2 → 2/3)."
)


READONLY_KINDS: frozenset[str] = frozenset(
    {
        "prime",
        "column_header",
        "row_label",
        "mapped",
        "vector",
        "tuning_value",
        "power_display",
        "generator_ratio",
        "comma_ratio",
        "math_expression",
        "plain_text",
        "plain_text_pending",
        "symbol",
        "matrix_label",
        "units",
        "name",
        "label",
        "count",
        "panel_title",
        "bracket",
        "ebktop",
        "ebkcurve",
        "ebkangle",
        "vbar",
        "chart",
        "rangechart",
        "colgap",
        "rowgap",
    }
)

MEAN_DAMAGE_IDS: frozenset[str] = frozenset(
    {"optimization:mean_damage", ("optimization:mean_damage:symbol")}
)
HELPED_READONLY_IDS: frozenset[str] = MEAN_DAMAGE_IDS | frozenset({"control:dual"})

_CELL_EDIT_HELP = {
    "mapping": "How many of this generator are used to approximate this prime. Type to edit the temperament, or scroll the wheel to step it by 1.",
    "form_cell": "Type to re-store the mapping in a new generating set (same temperament), or scroll the wheel to step it by 1; the whole form matrix must stay unimodular.",
    "comma_cell": "One prime's exponent in a comma the temperament makes vanish — a small interval that maps to nothing. Type to edit, or scroll the wheel to step it by 1.",
    "projection_cell": "Projection matrix entry — type a rational to drive the grid; the whole matrix must stay a valid projection (idempotent, tempers out the temperament's commas).",
    "embed_cell": "Generator embedding entry — type a rational to drive the grid; the whole matrix must keep 𝑀𝐺 = 𝐼.",
    "unchanged_cell": "Unchanged interval entry — this prime's exponent in an interval the tuning holds just. Type a new basis to retune to the projection that holds it.",
    "interest_cell": "Interval-of-interest entry — this prime's exponent in an interval you're tracking. Type to edit, or scroll the wheel to step it by 1.",
    "held_cell": "One prime's exponent in a held interval — one the tuning keeps pure, dealt absolutely zero damage. Type to edit, or scroll the wheel to step it by 1.",
    "target_cell": "One prime's exponent in a target interval, whose damage the tuning works to keep low. Type to override the chosen target set, or scroll the wheel to step it by 1.",
    "prescaler_cell": "Type to override the scheme's value, or scroll the wheel to nudge it by 0.001.",
    "weight_cell": "How much this target interval's damage counts relative to the others — editable because “custom weights” is on. Type your own to override the slope's complexity/simplicity/unity weighting, or scroll the wheel to nudge it by 0.001.",
    "generator_tuning_cell": "This generator's tuned size in cents. Type to set it by hand, click its sign to reverse the generator (its mapping row flips too, so the tuning is unchanged), or scroll the wheel to fine-tune by a thousandth of a cent.",
    "element_cell": "Domain basis element — a prime, or any rational (e.g. 13/5) for a nonstandard domain. Type to relabel this basis element; the ?/? draft adds a new one (held just). Valid if it's a positive rational that keeps the basis independent.",
    "element_ratio": "Domain basis element — a prime, or any rational (e.g. 13/5) for a nonstandard domain. Type to relabel this basis element; the ?/? draft adds a new one (held just). Valid if it's a positive rational that keeps the basis independent.",
}


_ADD_REMOVE_HELP = {
    "plus": "Add the next prime to the domain.",
    "minus": "Remove the highest prime from the domain.",
    "basis_minus": "Remove the highest prime from the domain.",
    "generator_plus": "Add a generator — opens a blank ?/? draft; type any positive rational (e.g. 7, or 13/5) to add it to the domain as a generator of its own, mapped just. Raises the rank and the dimensionality.",
    "generator_minus": "Remove the last generator (a mapping row) — lowers the rank, tempering one more comma; holds the dimensionality.",
    "map_plus": "Add a generator (a mapping row) — un-tempers a comma, raising the rank and holding the dimensionality. (⌥/Alt+M)",
    "map_minus": "Remove this generator (a mapping row) — lowers the rank, tempering one more comma; holds the dimensionality.",
    "comma_plus": "Add a comma to the basis. (⌥/Alt+C)",
    "comma_minus": "Un-temper this comma — raising the rank; removing the sole comma leaves just intonation.",
    "element_plus": "Add a domain basis element — opens a blank ?/? draft; type any positive rational (e.g. 13/5) to add it, held just (its own pure generator). (⌥/Alt+E)",
    "element_minus": "Remove this domain basis element — re-expresses the temperament over the remaining basis.",
    "interest_plus": "Add an interval of interest. (⌥/Alt+I)",
    "interest_minus": "Remove this interval of interest.",
    "held_plus": "Add a held interval. (⌥/Alt+H)",
    "held_minus": "Remove this held interval.",
    "unchanged_minus": "Stop holding this interval unchanged — the remaining filled slots stay held and the tuning re-optimizes around them.",
    "target_plus": "Add a target interval to the list. (⌥/Alt+T)",
    "target_minus": "Remove this target interval from the list.",
    "element_minus:pending": "Cancel the pending domain basis element draft.",
    "element_minus:basis:pending": "Cancel the pending domain basis element draft.",
    "element_minus:generator:pending": "Cancel the pending domain basis element draft.",
}


_DRAG_HELP = {
    "map_drag": "Drag this generator (a mapping row) onto another row to add it into that row — a change of generator basis that holds the temperament and its tuning.",
    "int_drag": "Drag this interval onto any other interval to multiply that one by this. Dropping onto a target, held, or other interval just combines the two; dropping onto a comma re-expresses the temperament.",
    "int_derived": "This column is derived from the temperament rather than an editable interval list, so its intervals can't be combined — there's nowhere to store the result.",
    "subcolumngrip": "Drag this interval to another list, or reorder it — drop onto the commas to temper it out.",
    "columngrip": "Drag this whole column into a gap between columns to reorder the grid's columns.",
    "rowgrip": "Drag this whole row into a gap between rows to reorder the grid's rows.",
    "element_reorder": "Drag to reorder this domain basis element among the others — the temperament and every interval are re-expressed over the reordered basis.",
    "canonicalize_button": "Put the domain basis into canonical form — re-expressing the whole grid over it, the same temperament and intervals in their canonical basis.",
}

_GENERATOR_GRIP_HELP = "Drag this generator to reorder it — the mapping rows follow the new generator order. The temperament and its optimum tuning are unchanged."


_COLLAPSE_HELP = {
    "rowtoggle": "Collapse or expand this row.",
    "columntoggle": "Collapse or expand this column.",
    "tiletoggle": "Collapse or expand this tile.",
    "alltoggle": "Collapse or expand the entire grid.",
}


_TUNING_CONTROL_HELP = {
    "rangemode": "Choose how the generator's tuning range is measured — monotone or tradeoff.",
    "scheme_button": "Back to the scheme — discard a picked or edited projection and return the tuning to the scheme's optimized result, bringing the target list back.",
    "optimization:power": "Optimization power 𝑝 — ∞ minimizes the worst damage (minimax), 2 the RMS, 1 the mean. Type ∞, or scroll the wheel to step a finite power by 1.",
    "control:q": "Interval-complexity norm power 𝑞. Type it, or scroll the wheel to step it by 1.",
    "control:dual": "Dual norm power — the dual exponent of 𝑞, used to minimax over every interval.",
    "control:complexity": "Choose the interval complexity measure used to weight damage.",
    "control:slope": "Choose how a target's weight scales with its complexity.",
    "control:diminuator": "In the interval-complexity measure, replace the diminuator — the smaller of each ratio's numerator and denominator — with the larger of the two.",
    "control:all_interval": "Optimize over theoretically every interval at once (an all-interval scheme) instead of a finite target list. Requires the scheme to be simplicity-weighted and minimax.",
}


_FORM_CONTROL_HELP = {
    "formchooser:mapping": "Rewrite the mapping 𝑀 into a chosen form. This says nothing about the comma basis: the two carry their own forms, chosen separately, so the mapping can sit off canonical while the comma basis is already on it.",
    "formchooser:comma_basis": "Rewrite the comma basis C into a chosen form. This says nothing about the mapping: the two carry their own forms, chosen separately, so the comma basis can sit on canonical while the mapping is off it.",
}


_PICKER_HELP = {
    "etpick": "Set this generator row to a curated equal temperament — pick one (in wart notation, with its map) to build the temperament by merging ETs. Only ETs over the current domain basis are offered.",
    "commapick": "Set this comma column to a curated comma — pick one (with its prime-count vector) to build the temperament by merging commas. Only commas within the current domain basis are offered.",
}


_CONTROL_HELP = {
    **_CELL_EDIT_HELP,
    **_ADD_REMOVE_HELP,
    **_DRAG_HELP,
    **_COLLAPSE_HELP,
    **_TUNING_CONTROL_HELP,
    **_FORM_CONTROL_HELP,
    **_PICKER_HELP,
}

_PRESET_HELP: dict[str, str] = {
    "temperament": "Load a temperament from a list of established temperaments.",
    "tuning": "Load a tuning scheme from a list of established tuning schemes.",
    "target": (
        "Choose the target interval set and its limit — an integer limit for the triangle (TILT), "
        "an odd limit for the diamond (OLD). Scroll the wheel over the limit to step it by 1."
    ),
    "prescaler": ("Load a complexity prescaler from a list of established complexity prescalers."),
    "projection": (
        "Load a projection from a list of established projections for this temperament (if any)."
    ),
}

_PRESET_HELP_DISABLED: dict[str, str] = {
    "projection": (
        "Load a projection from a list of established projections for this temperament "
        "(this temperament does not have any, which is why this is disabled)."
    ),
    "tuning": (
        "Choose the tuning scheme. Only one scheme fits the current settings, so there is "
        "nothing to choose — enable weighting (and its options) under optimization to unlock more schemes."
    ),
    "prescaler": (
        "Choose the complexity prescaler. Only one prescaler fits the current settings, so there is "
        "nothing to choose — enable alternative complexities under weighting to unlock more."
    ),
}

_RATIO_HELP: dict[str, str] = {
    "comma": (
        "A comma this temperament makes vanish, or in other words, a small JI interval that it tempers out, such that moving by it lands you nowhere new. Type a ratio (e.g. 81/80) to set it."
    ),
    "target": (
        "A target interval — one of the consonances you want tuned well, whose damage the tuning works to keep as low as possible. Type a ratio to override the chosen target set."
    ),
    "held": (
        "A held interval — one the tuning keeps pure, dealt absolutely zero damage (most often the octave). Type a ratio to edit it."
    ),
    "interest": ("Any other interval you're tracking. Type a ratio to edit it."),
    "unchanged": (
        "Unchanged interval ratio — an interval the tuning holds just. Type a ratio to retune to the projection that holds it."
    ),
}

_PLAIN_TEXT_HELP: dict[str, str] = {
    "plain_text:mapping:primes": (
        "Type the mapping as a plain-text string (e.g. ⟨⟨1 0 -4]]) to drive the grid."
    ),
    "plain_text:vectors:commas": "Type the comma basis as a plain-text string to drive the grid.",
    "plain_text:tuning:generators": "Type the generator tuning map as a plain-text string to drive the grid.",
    "plain_text:mapping:canonical_generators": (
        "Type the generator form matrix as a plain-text string to drive the grid; rejected unless square and unimodular."
    ),
    "plain_text:vectors:targets": (
        "Type the target interval list as a plain-text string to drive the grid."
    ),
    "plain_text:prescaling:primes": "Type the complexity prescaler as a plain-text string to drive the grid.",
    "plain_text:projection:primes": (
        "Type the projection as a plain-text string to drive the grid; rejected unless it's a valid projection (idempotent, tempers out the temperament's commas)."
    ),
    "plain_text:projection:generators": (
        "Type the generator embedding as a plain-text string to drive the grid; rejected unless 𝑀𝐺 = 𝐼."
    ),
}


def target_limit_help(problem: str) -> str:
    return {
        "odd": "The odd-limit diamond (OLD) needs an odd limit.",
        "whole": "The target limit must be a whole number.",
    }[problem]


def scheme_help(active: bool) -> str:
    if active:
        return _TUNING_CONTROL_HELP["scheme_button"]
    return "Disabled — the scheme's optimum already produces this tuning, so there's nothing to hand back."


def mean_damage_help(all_interval: bool) -> str:
    if all_interval:
        return (
            "Retuning magnitude — the magnitude that the tuning minimizes over every interval "
            "at once: the size of the prescaled retuning map 𝒓 at the dual-norm power dual(𝑞)."
        )
    return (
        "Mean damage ⟪𝐝⟫ₚ — the power mean of damage that the tuning minimizes over the target "
        "list: the targets' damage combined by the optimization power 𝑝."
    )


def control_help(
    kind: str, cell_id: str, *, pretransform: bool = False, disabled: bool = False
) -> str | None:
    text = _control_help(kind, cell_id, disabled)
    return _pretransform_label(text) if (pretransform and text) else text


def _control_help(kind: str, cell_id: str, disabled: bool = False) -> str | None:
    if cell_id in MEAN_DAMAGE_IDS:
        return mean_damage_help(all_interval=False)
    if kind in READONLY_KINDS:
        return _CONTROL_HELP.get(cell_id) if cell_id in HELPED_READONLY_IDS else None
    if kind == "preset":
        name = cell_id.split(":")[1]
        return (
            _PRESET_HELP_DISABLED[name]
            if disabled and name in _PRESET_HELP_DISABLED
            else _PRESET_HELP.get(name)
        )
    if kind == "plain_text_edit":
        return _PLAIN_TEXT_HELP.get(cell_id)
    if kind == "ratio_cell":
        return _RATIO_HELP.get(cell_id.split(":", maxsplit=1)[0])
    generator_grip = (kind == "subcolumngrip" and cell_id.startswith("grip:generators:")) or (
        kind == "subrowgrip" and cell_id.startswith("subrowgrip:generators:")
    )
    return _GENERATOR_GRIP_HELP if generator_grip else (
        _CONTROL_HELP.get(cell_id) or _CONTROL_HELP.get(kind))
