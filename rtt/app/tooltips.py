from __future__ import annotations

from dataclasses import dataclass

GUIDE_BASE = "https://en.xen.wiki/w/Dave_Keenan_%26_Douglas_Blumeyer%27s_guide_to_RTT"


def guide_url(chapter: str, section: str) -> str:
    anchor = "#" + section.replace(" ", "_") if section else ""
    return f"{GUIDE_BASE}/{chapter.replace(' ', '_')}{anchor}"


@dataclass(frozen=True)
class GuideHelp:
    text: str
    chapter: str
    section: str

    @property
    def location(self) -> str:
        return f"{self.chapter} › {self.section}" if self.section else self.chapter

    @property
    def url(self) -> str:
        return guide_url(self.chapter, self.section)


GUIDE_HELP: dict[tuple[str, str], GuideHelp] = {
    ("mapping", "primes"): GuideHelp(
        "A mapping captures a temperament: one map per generator, each counting how many "
        "of that generator it takes to reach every prime. It is the central object of RTT — "
        "everything else follows from it.",
        "Mappings", "Mappings"),
    ("vectors", "commas"): GuideHelp(
        "The comma basis collects the commas this temperament tempers out: small JI "
        "intervals it makes vanish, so that moving by one of them changes nothing. Each "
        "column is one vanishing comma.",
        "Mappings", "Making commas vanish"),
    ("tuning", "gens"): GuideHelp(
        "The generator tuning map gives the size, in cents, of each generator. The mapping "
        "says how the generators build the primes; this says how large the generators "
        "actually are, which is what pins down the tuning.",
        "Tuning fundamentals", "Tuning"),
    ("vectors", "targets"): GuideHelp(
        "The target intervals are the ones you want tuned well — usually the consonances "
        "your music leans on. The tuning is chosen to keep their combined damage as low as "
        "possible.",
        "Tuning fundamentals", "Target-intervals"),
    ("damage", "targets"): GuideHelp(
        "Damage measures how badly the tuning serves an interval: how far its tempered size "
        "lands from just intonation, scaled by how much that interval matters.",
        "Tuning fundamentals", "Damage, error, and weight"),
    ("weight", "targets"): GuideHelp(
        "The weights set how much each target's damage counts in the optimization, so the "
        "intervals you care about most pull the tuning hardest toward serving them.",
        "Tuning fundamentals", "Damage, error, and weight"),
    ("vectors", "held"): GuideHelp(
        "The held intervals are the ones the tuning keeps pure — each dealt absolutely zero "
        "damage, most often the octave. Each column is one held interval.",
        "Tuning fundamentals", "Held-intervals"),
    ("tuning", "primes"): GuideHelp(
        "The tuning map gives the tempered size, in cents, of each prime — the generator "
        "sizes pushed through the mapping (𝒕 = 𝒈𝑀).",
        "Tuning fundamentals", "Tuning"),
    ("just", "primes"): GuideHelp(
        "The just tuning map gives each prime's pure size in cents — the just-intonation "
        "values the tempered tuning is measured against.",
        "Tuning fundamentals", "Tuning"),
    ("retune", "primes"): GuideHelp(
        "The retuning map is each prime's error: how far its tempered size lands from just "
        "(𝒓 = 𝒕 − 𝒋). The damage is the size of that error.",
        "Tuning fundamentals", "Damage, error, and weight"),
    ("complexity", "targets"): GuideHelp(
        "Each target interval's complexity — a ranking of how complex the ratio is, with a "
        "larger value meaning more complex. It is what the damage weighting scales with.",
        "Tuning fundamentals", "Complexity"),
    ("mapping", "commas"): GuideHelp(
        "The comma basis sent through the mapping — all zeros, because the temperament makes "
        "exactly these commas vanish.",
        "Mappings", "Making commas vanish"),
}


def tile_guide_help(rkey: str, ckey: str) -> GuideHelp | None:
    return GUIDE_HELP.get((rkey, ckey))


def tile_guide_help_for_cell(cell_id: str) -> GuideHelp | None:
    parts = cell_id.split(":")
    if len(parts) == 3 and parts[0] in ("symbol", "caption"):
        return tile_guide_help(parts[1], parts[2])
    return None


SHOW_HELP: dict[str, str] = {
    "animations": "Animate grid changes — slide and fade rows, columns and cells in and out as they appear, move or leave. Off makes every change snap instantly.",
    "preview_highlighting": "Highlight what a control would do before you click it — hovering a +/− or a chooser option rings the cells it would change (amber), remove (red) or add (green). Off hides the preview.",
    "tooltips": "Show the hover tooltips that explain each control, value and setting (like this one).",
    "drag_to_combine": "Show drag handles for combining basis elements: drag one generator row (or one interval) onto another to add it in.",
    "names": "Show each tile's name caption (e.g. “mapping”, “generators”).",
    "mnemonics": "Underline the letter of each name that its symbol uses — a memory aid. Refines “names”.",
    "symbols": "Show each value's math symbol (𝑀, 𝒈, 𝒕, …).",
    "header_symbols": "Show the row and column header symbols (𝒎₁, 𝐜₁, …) labelling each matrix's rows and columns.",
    "equivalences": "Show each symbol's defining equation (e.g. 𝒕 = 𝒈𝑀) instead of the bare glyph. Refines “symbols”.",
    "gridded_values": "Lay the values out in the grid as matrix and vector cells.",
    "plain_text_values": "Show each value as one plain-text string (e.g. ⟨1 0 -4]) below its tile.",
    "charts": "Draw a bar chart over each charted row's values.",
    "presets": "Show the preset choosers — temperament, tuning scheme, and target set.",
    "quantities": "Show the numeric quantities inside the value cells.",
    "decimals": "Show the decimal fraction of each value (the .955 beneath the 701). Off rounds every value in the app to the nearest integer. Refines “quantities”.",
    "ebk": "Frame every matrix and vector in EBK (Extended Bra-Ket) notation — the angle ⟨…] of a map, the ket […⟩, the curly { of a generator map. Off replaces it everywhere with plain matrix notation: square braces throughout, a superscript ᵀ marking the vector kind.",
    "units": "Show each box's “units: …” line beneath its caption (e.g. ¢/p, g/p).",
    "cell_units": "Show each value's unit beneath its own cell (e.g. ¢/p₁, 𝒈₁).",
    "math_expressions": "Show just values as closed-form expressions (e.g. 1200·log₂(3/2)).",
    "counts": "Show the dimension counts — dimensionality 𝑑, rank 𝑟, nullity 𝑛.",
    "interval_ratios": "Show the interval-ratios row — each interval written as a ratio — and its spine column (the domain basis, e.g. 2.3.5).",
    "interval_vectors": "Show the interval-vectors row — each interval written as a column vector (monzo).",
    "domain_units": "Show the units on the domain-basis row and column labels.",
    "temperament": "Expand the temperament settings — the temperament tiles and their colorization. A grouping toggle; it shows nothing of its own.",
    "temperament_tiles": "Show the temperament tiles — the mapping 𝑀 and the comma basis C.",
    "temperament_colorization": "Tint each cell by what derives it — the mapping 𝑀 or the comma basis C. Refines “temperament tiles”.",
    "form": "Show the form layer — mark the canonical (default) form with a subscript C on the mapping 𝑀, generator tuning map 𝒈, and generator embedding G. Also expands the form sub-controls.",
    "form_controls": "Show the form controls — the <choose form> dropdowns that rewrite the mapping or comma basis into a chosen form. Refines “form”.",
    "form_tiles": "Show the form tiles — the canonical mapping row and the form matrix 𝐹. Refines “form”.",
    "form_colorization": "Tint the cells touched by the form 𝐹. Refines “form”.",
    "tuning": "Expand the tuning settings — the tuning tiles and everything beneath them. A grouping toggle; it shows nothing of its own.",
    "tuning_tiles": "Show the tuning tiles — the generator tuning map, prescaler, damage, and more.",
    "optimization": "Show the optimization box — the mean damage and the power 𝑝.",
    "tuning_ranges": "Chart each generator's tuning range as an I-beam under the generator tuning map.",
    "weighting": "Show the weighting boxes — the prescaler, the complexity 𝒄, and the weight 𝒘.",
    "all_interval": "Show the all-interval control — optimize over every interval rather than a finite target list.",
    "alt_complexity": "Show the alternative-complexity controls — the prescaler box 𝐋 and the wider choice of interval-complexity measures.",
    "custom_weights": "Type your own damage weight per target interval (the editable 𝒘 row), overriding the slope's complexity/simplicity/unity weighting.",
    "projection": "Show the projection box — the rational projection 𝑃 = 𝐺𝑀 holding the just primes.",
    "tuning_colorization": "Tint each cell by what derives it — the generator tuning map 𝒈. Refines “tuning tiles”.",
    "interest": "Show the “other intervals of interest” column.",
    "generator_detempering": "Show the generator-detempering D column — the generator map written as vectors.",
    "nonstandard_domain": "Show the superspace block — the basis change matrix Bₗ, the lifted mapping 𝑀ₗ, and (over a domain with nonprime basis elements) the prime/nonprime-based mode chooser.",
    "identity_objects": "Show the identity-object tiles — trivial self-maps built from the other boxes.",
}

CHROME_HELP: dict[str, str] = {
    "settings": "Show or hide the Show settings panel. (⌘/Ctrl+,)",
    "chapter": "Reveal the Show controls chapter by chapter as they're introduced in D&D's guide — slide left for a simpler view, right to expose more. The ★ notch shows everything.",
    "select_all": "Turn every available Show toggle on, or all off.",
    "dark_mode": "Switch the whole app between the light and dark colour themes.",
    "undo": "Undo the last change. (⌘/Ctrl+Z)",
    "redo": "Redo the change you undid. (⌘/Ctrl+Y, or ⌘/Ctrl+Shift+Z)",
    "reset": "Reset everything — settings, layout, and values — to the defaults.",
    "share": "Copy a shareable link to this exact state — open it to load the app right here (its undo history isn't included).",
    "tour": "Replay the guided tour of the app.",
}

AUDIO_HELP: dict[str, str] = {
    "mute": "Mute all audio — also stops anything still sounding; unmute to play a pitch by clicking its cell.",
    "wave": "Cycle the waveform every pitch sounds — sine, square, triangle, sawtooth.",
    "mode": "Cycle the play mode — note, arpeggio, chord, rolled chord.",
    "hold": "Toggle sustain — hold or loop the notes.",
    "root": "Toggle the 1/1 root drone sounding underneath.",
}

RATIO_REDUCE_HELP = "Reduce this interval into one equave (the octave by default) — fold it by the equave until it lands in [1, equave)."
RATIO_RECIPROCATE_HELP = "Reciprocate this interval — swap its numerator and denominator (3/2 → 2/3)."


READONLY_KINDS: frozenset[str] = frozenset({
    "prime", "colheader", "rowlabel", "mapped", "vec", "tuningvalue", "powerdisplay",
    "genratio", "commaratio", "mathexpr", "ptext", "ptextpending",
    "symbol", "matlabel", "units", "caption", "count", "boxtitle",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "transpose", "vbar", "chart", "rangechart",
})

MEAN_DAMAGE_IDS: frozenset[str] = frozenset({"optimization:mean_damage", "optimization:mean_damage:symbol"})
HELPED_READONLY_IDS: frozenset[str] = MEAN_DAMAGE_IDS | frozenset({"control:dual"})

_KIND_HELP: dict[str, str] = {
    "mapping": "Mapping entry — how many of this generator map to this prime. Type to edit the temperament, or scroll the wheel to step it by 1.",
    "formcell": "Generator form matrix entry — how this stored generator is built from the canonical ones (𝑀 = 𝐹𝑀ᴄ). Type to re-store the mapping in a new generating set (same temperament), or scroll the wheel to step it by 1; the whole 𝐹 must stay unimodular.",
    "commacell": "One prime's exponent in a comma the temperament makes vanish — a small interval that maps to nothing. Type to edit, or scroll the wheel to step it by 1.",
    "unchangedcell": "Unchanged interval entry — this prime's exponent in an interval the tuning holds just. Type a new basis to retune to the projection that holds it.",
    "interestcell": "Interval-of-interest entry — this prime's exponent in an interval you're tracking. Type to edit, or scroll the wheel to step it by 1.",
    "heldcell": "One prime's exponent in a held interval — one the tuning keeps pure, dealt absolutely zero damage. Type to edit, or scroll the wheel to step it by 1.",
    "targetcell": "One prime's exponent in a target interval, whose damage the tuning works to keep low. Type to override the chosen target set, or scroll the wheel to step it by 1.",
    "prescalercell": "Prescaler entry — the weight on this prime applied before optimizing. Type to override the scheme's value, or scroll the wheel to nudge it by 0.001.",
    "weightcell": "Damage weight — this target interval's weight in the optimization. Type your own to override the slope's complexity/simplicity/unity weighting.",
    "gentuningcell": "Generator tuning — this generator's tuned size in cents. Type to override the optimum, click its sign to reverse the generator (its mapping row flips too, so the tuning is unchanged), or scroll the wheel to fine-tune by a thousandth of a cent.",
    "elementcell": "Domain basis element — a prime, or any rational (e.g. 13/5) for a nonstandard domain. Type to relabel this basis element; the ?/? draft adds a new one (held just). Valid if it's a positive rational that keeps the basis independent.",
    "elementratio": "Domain basis element — a prime, or any rational (e.g. 13/5) for a nonstandard domain. Type to relabel this basis element; the ?/? draft adds a new one (held just). Valid if it's a positive rational that keeps the basis independent.",
    "rangemode": "Choose how the generator's tuning range is measured — monotone or tradeoff.",
    "scheme_button": "Back to the scheme — discard a picked or edited projection and return the tuning to the scheme's optimized result, bringing the target list back.",
    "plus": "Add the next prime to the domain.",
    "minus": "Remove the highest prime from the domain.",
    "gen_plus": "Add a generator — raises the rank and dimensionality, mapping a new prime just. (⌥/Alt+M)",
    "gen_minus": "Remove the last generator — lowers the rank and dimensionality.",
    "map_plus": "Add a generator (a mapping row) — un-tempers a comma, raising the rank and holding the dimensionality. (⌥/Alt+M)",
    "map_minus": "Remove this generator (a mapping row) — lowers the rank, tempering one more comma; holds the dimensionality.",
    "map_drag": "Drag this generator (a mapping row) onto another row to add it into that row — a change of generator basis that holds the temperament and its tuning.",
    "int_drag": "Drag this interval onto another in the same column to combine them into their product. For the comma basis this re-expresses the same temperament; for a target / held / interest list it just combines the two intervals.",
    "etpick": "Set this generator row to a curated equal temperament — pick one (in wart notation, with its map) to build the temperament by merging ETs. Only ETs over the current domain basis are offered.",
    "commapick": "Set this comma column to a curated comma — pick one (with its prime-count vector) to build the temperament by merging commas. Only commas within the current domain basis are offered.",
    "basis_minus": "Remove the highest prime from the domain.",
    "element_plus": "Add a domain basis element — opens a blank ?/? draft; type any positive rational (e.g. 13/5) to add it, held just (its own pure generator). (⌥/Alt+E)",
    "element_minus": "Remove this domain basis element — re-expresses the temperament over the remaining basis.",
    "comma_plus": "Add a comma to the basis. (⌥/Alt+C)",
    "comma_minus": "Un-temper this comma — raising the rank; removing the sole comma leaves just intonation.",
    "interest_plus": "Add an interval of interest. (⌥/Alt+I)",
    "interest_minus": "Remove this interval of interest.",
    "held_plus": "Add a held interval. (⌥/Alt+H)",
    "held_minus": "Remove this held interval.",
    "target_plus": "Add a target interval to the list. (⌥/Alt+T)",
    "target_minus": "Remove this target interval from the list.",
    "colgrip": "Drag this interval to another list, or reorder it — drop onto the commas to temper it out.",
    "rowtoggle": "Collapse or expand this row.",
    "coltoggle": "Collapse or expand this column.",
    "tiletoggle": "Collapse or expand this tile.",
    "alltoggle": "Collapse or expand the entire grid.",
}


_ID_HELP: dict[str, str] = {
    "element_minus:pending": "Cancel the pending domain basis element draft.",
    "element_minus:basis:pending": "Cancel the pending domain basis element draft.",
    "optimization:power": "Optimization power 𝑝 — ∞ minimizes the worst damage (minimax), 2 the RMS, 1 the mean. Type ∞, or scroll the wheel to step a finite power by 1.",
    "control:q": "Interval-complexity norm power 𝑞. Type it, or scroll the wheel to step it by 1.",
    "control:dual": "Dual norm power — the dual exponent of 𝑞, used to minimax over every interval.",
    "control:complexity": "Choose the interval-complexity measure used to weight damage.",
    "control:slope": "Choose the damage weight slope — how a target's weight scales with its complexity.",
    "control:diminuator": "Replace the diminuator — the smaller of each ratio's numerator and denominator — in the interval-complexity measure.",
    "control:all_interval": "Optimize over every interval at once (an all-interval scheme) instead of a finite target list.",
    "formchooser:mapping": "Rewrite the mapping into a canonical form (an undoable edit).",
    "formchooser:comma_basis": "Rewrite the comma basis into a canonical form (an undoable edit).",
}

_PRESET_HELP: dict[str, str] = {
    "temperament": "Load a named temperament preset — sets the mapping and comma basis.",
    "tuning": "Choose a named tuning scheme (e.g. minimax-S).",
    "target": "Choose the target interval set and its limit — an integer limit for the triangle (TILT), an odd limit for the diamond (OLD). Scroll the wheel over the limit to step it by 1.",
    "prescaler": "Choose a predefined prescaler — the per-prime weighting applied before optimizing.",
    "projection": "Choose an established projection — a named rational tuning (e.g. 1/4-comma) that sets the generator tuning; its unchanged intervals drive the projection 𝑃 = 𝐺𝑀 and the generator embedding 𝐺. Empty when the temperament has no such tuning.",
}

_RATIO_HELP: dict[str, str] = {
    "comma": "A comma this temperament makes vanish — a small JI interval it tempers out, so moving by it lands you nowhere new. Type a fraction (e.g. 81/80) to set it.",
    "target": "A target interval — one of the consonances you want tuned well, whose damage the tuning works to keep as low as possible. Type a fraction to override the chosen target set.",
    "held": "A held interval — one the tuning keeps pure, dealt absolutely zero damage (most often the octave). Type a fraction to edit it.",
    "interest": "Interval-of-interest ratio — an interval you're tracking. Type a fraction to edit it.",
    "unchanged": "Unchanged interval ratio — an interval the tuning holds just. Type a fraction to retune to the projection that holds it.",
}

_PTEXT_HELP: dict[str, str] = {
    "ptext:mapping:primes": "Type the mapping as a plain-text string (e.g. ⟨⟨1 0 -4]]) to drive the grid.",
    "ptext:vectors:commas": "Type the comma basis as a plain-text string to drive the grid.",
    "ptext:tuning:gens": "Type the generator tuning map as a plain-text string to drive the grid.",
    "ptext:mapping:canongens": "Type the generator form matrix 𝐹 as a plain-text string to re-store the mapping in that generating set (same temperament); rejected unless 𝐹 is square and unimodular.",
    "ptext:vectors:targets": "Type the target interval list as a plain-text string to drive the grid.",
    "ptext:prescaling:primes": "Type the prescaler as a plain-text string to drive the grid.",
    "ptext:projection:primes": "Type the projection 𝑃 as a plain-text string to retune to it; rejected unless it's a valid projection (idempotent, commas in its kernel).",
    "ptext:projection:gens": "Type the generator embedding 𝐺 as a plain-text string to retune to it; rejected unless 𝑀𝐺 = 𝐼.",
}


def target_limit_help(problem: str) -> str:
    return {
        "odd": "The odd-limit diamond (OLD) needs an odd limit.",
        "whole": "The target limit must be a whole number.",
    }[problem]


def mean_damage_help(all_interval: bool) -> str:
    if all_interval:
        return ("Retuning magnitude — the magnitude that the tuning minimizes over every interval "
                "at once: the size of the prescaled retuning map 𝒓 at the dual-norm power dual(𝑞).")
    return ("Mean damage ⟪𝐝⟫ₚ — the power mean of damage that the tuning minimizes over the target "
            "list: the targets' damage combined by the optimization power 𝑝.")


def control_help(kind: str, cid: str) -> str | None:
    if cid in MEAN_DAMAGE_IDS:
        return mean_damage_help(all_interval=False)
    if kind in READONLY_KINDS:
        return _ID_HELP.get(cid) if cid in HELPED_READONLY_IDS else None
    if kind == "preset":
        return _PRESET_HELP.get(cid.split(":")[1])
    if kind == "ptextedit":
        return _PTEXT_HELP.get(cid)
    if kind == "ratiocell":
        return _RATIO_HELP.get(cid.split(":")[0])
    return _ID_HELP.get(cid) or _KIND_HELP.get(kind)
