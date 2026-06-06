"""Hover text (tooltips) for the Show settings and the interactive grid controls.

THIS MODULE IS THE SINGLE HOME for every hover string in the app — to refine any wording,
edit it here and nowhere else. The settings panel, the layout (:mod:`rtt.web.spreadsheet`)
and the renderer (:mod:`rtt.web.app`) only *reference* these tables; they hold no hover
text of their own.

  - :data:`SHOW_HELP`   — one entry per Show-toggle key (see :mod:`rtt.web.settings`).
  - :data:`CHROME_HELP` — the app-chrome buttons (undo / redo / reset / settings / select-all).
  - :data:`AUDIO_HELP`  — the dummy tile's audio bank controls (mute / waveform / play-mode / hold / 1-1).
  - :func:`control_help` — a grid cell's ``(kind, id)`` → its hover text, or ``None`` for
    the read-only output kinds listed in :data:`READONLY_KINDS`.
  - :func:`objective_help` — the optimization objective's hover text, which names a different
    quantity per mode (see :data:`OBJECTIVE_IDS`); the renderer swaps it live as all-interval flips.

Coverage is test-enforced (``tests/test_web_tooltips.py``): ``SHOW_HELP`` must match
``settings.DEFAULTS``, every editable dual must match ``spreadsheet.EDITABLE_PTEXT``, and
every kind a full-feature build renders must be either in ``READONLY_KINDS`` or carry help
(the lone read-only exceptions are the :data:`OBJECTIVE_IDS` cells) — so a new setting or
control can't ship without its hover text.
"""

from __future__ import annotations

# Hover text per Show toggle (settings.SHOW_GROUPS key). Every toggle is covered,
# greyed-out ones included — the text explains what the toggle would reveal.
SHOW_HELP: dict[str, str] = {
    # interaction
    "drag_to_combine": "Show drag handles for combining basis elements: drag one generator row (or one interval) onto another to add it in.",
    # general
    "names": "Show each tile's name caption (e.g. “mapping”, “generators”).",
    "mnemonics": "Underline the letter of each name that its symbol uses — a memory aid. Refines “names”.",
    "symbols": "Show each value's math symbol (𝑀, 𝒈, 𝒕, …).",
    "equivalences": "Show each symbol's defining equation (e.g. 𝒕 = 𝒈𝑀) instead of the bare glyph. Refines “symbols”.",
    "gridded_values": "Lay the values out in the grid as matrix and vector cells.",
    "plain_text_values": "Show each value as one plain-text string (e.g. ⟨1 0 -4]) below its tile.",
    "charts": "Draw a bar chart over each charted row's values.",
    "presets": "Show the preset choosers — temperament, tuning scheme, and target set.",
    "quantities": "Show the numeric quantities inside the value cells.",
    "units": "Show each value's units (e.g. ¢, g/p) beneath its cells.",
    "math_expressions": "Show just values as closed-form expressions (e.g. 1200·log₂(3/2)).",
    # specific boxes & controls
    "counts": "Show the dimension counts — dimensionality 𝑑, rank 𝑟, nullity 𝑛.",
    "domain_quantities": "Show the numeric quantities in the domain basis (the prime column).",
    "domain_units": "Show the units on the domain-basis row and column labels.",
    "temperament_boxes": "Show the temperament boxes — the mapping 𝑀 and the comma basis C.",
    "temperament_colorization": "Tint each cell by what derives it — the mapping 𝑀 or the comma basis C. Refines “temperament boxes”.",
    "form_controls": "Show the form controls — rewrite the mapping or comma basis into a chosen form.",
    "form_colorization": "Tint the cells touched by the form 𝐹. Refines “form controls”.",
    "tuning_boxes": "Show the tuning boxes — the generator tuning map, prescaler, damage, and more.",
    "optimization": "Show the optimization box — the objective, the optimize button, and the power 𝑝.",
    "tuning_ranges": "Chart each generator's tuning range as an I-beam under the generator tuning map.",
    "weighting": "Show the weighting boxes — the prescaler, the complexity 𝒄, and the weight 𝒘.",
    "all_interval": "Show the all-interval control — optimize over every interval rather than a finite target list.",
    "alt_complexity": "Show the alternate-complexity controls — the prescaler box 𝐋 and the wider choice of interval-complexity measures.",
    "projection": "Show the projection box — the rational projection 𝑃 = 𝐺𝑀 holding the just primes.",
    "tuning_colorization": "Tint each cell by what derives it — the generator tuning map 𝒈. Refines “tuning boxes”.",
    "interest": "Show the “other intervals of interest” column.",
    "generator_detempering": "Show the generator-detempering D column — the generator map written as vectors.",
    "nonstandard_domain": "Show the superspace block — the basis-embedding matrix Bₗ, the lifted mapping 𝑀ₗ, and (over a domain with nonprime basis elements) the prime/nonprime-based mode chooser.",
    "identity_objects": "Show the identity-object tiles — trivial self-maps built from the other boxes.",
}

# Hover text for the always-present app chrome (the rail + the title tile).
CHROME_HELP: dict[str, str] = {
    "settings": "Show or hide the Show settings panel.",
    "select_all": "Turn every available Show toggle on, or all off.",
    "dark_mode": "Switch the whole app between the light and dark colour themes.",
    "undo": "Undo the last change.",
    "redo": "Redo the change you undid.",
    "reset": "Reset everything — settings, layout, and values — to the defaults.",
}

# Hover text for the audio control bank (see :func:`rtt.web.app._audio_bank`). The bank is no
# longer per-tile: one bank on the settings panel's dummy tile drives every speaker from a single
# global config, so the wording speaks of "every pitch", not "this tile". Keyed by the control name.
AUDIO_HELP: dict[str, str] = {
    "mute": "Mute all audio — also stops anything still sounding; unmute to play a pitch by clicking its cell.",
    "wave": "Cycle the waveform every pitch sounds — sine, square, triangle, sawtooth.",
    "mode": "Cycle the play mode — note, arpeggio, chord, rolled chord.",
    "hold": "Toggle sustain — hold or loop the notes.",
    "root": "Toggle the 1/1 root drone sounding underneath.",
}


# The read-only OUTPUT kinds — value cells, labels, symbols, captions, brackets, charts.
# They are not controls, so control_help returns None for them. Declared here (not only in
# the test) so the whole tooltip taxonomy lives in one place; the completeness test asserts
# every kind a full build renders is either listed here or carries help.
READONLY_KINDS: frozenset[str] = frozenset({
    "prime", "formcell", "colheader", "rowlabel", "mapped", "vec", "tval", "powerdisplay",
    "genratio", "commaratio", "mathexpr", "ptext", "ptextpending",
    "symbol", "matlabel", "units", "caption", "count", "boxtitle",
    "bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "chart", "rangechart",
})

# Read-only OUTPUT values that nonetheless carry hover help — exempt from the no-tooltip rule.
# Two kinds qualify:
#   - the optimization objective's value cell (a ``tval``) and symbol cell (a ``symbol``). Like the
#     power 𝑝, the objective carries a label caption ("power mean" / "retuning magnitude"), but that
#     two-word label only names the quantity — the hover text explains it, and flips with all-interval
#     mode (the damage ⟪𝐝⟫ₚ vs the retuning magnitude). Both ids hang the tooltip so the whole
#     displayed value is hoverable; the renderer swaps the wording live (see :func:`objective_help`).
#   - the dual norm power dual(𝑞), a value DERIVED from 𝑞 (never editable, so a read-only
#     ``powerdisplay``) but advanced enough to warrant a word; its help lives in :data:`_ID_HELP`.
# :func:`control_help` returns help for all of these ahead of / through the READONLY_KINDS check,
# and the completeness sweep exempts them from the no-tooltip rule.
OBJECTIVE_IDS: frozenset[str] = frozenset({"optimization:objective", "optimization:objective:symbol"})
HELPED_READONLY_IDS: frozenset[str] = OBJECTIVE_IDS | frozenset({"control:dual"})

# Hover text per interactive cell kind whose meaning is fixed by the kind alone.
# (Kinds backing several controls are disambiguated by id in _ID_HELP below.)
_KIND_HELP: dict[str, str] = {
    # editable matrix / vector entries. Each is a single integer, so it also steps by 1 on a mouse-
    # wheel notch once the cell is focused (the coarse-integer analogue of the generator-tuning
    # cell's thousandth-cent wheel fine-adjust).
    "mapping": "Mapping entry — how many of this generator map to this prime. Type to edit the temperament, or scroll the wheel to step it by 1.",
    "commacell": "Comma-vector entry — this prime's exponent in a comma the temperament tempers out. Type to edit, or scroll the wheel to step it by 1.",
    "interestcell": "Interval-of-interest entry — this prime's exponent in an interval you're tracking. Type to edit, or scroll the wheel to step it by 1.",
    "heldcell": "Held-interval entry — this prime's exponent in an interval held unchanged (pure) by the tuning. Type to edit, or scroll the wheel to step it by 1.",
    "targetcell": "Target-interval entry — this prime's exponent in a target the tuning optimizes over. Type to override the chosen target set, or scroll the wheel to step it by 1.",
    "prescalercell": "Prescaler entry — the weight on this prime applied before optimizing. Type to override the scheme's value, or scroll the wheel to nudge it by 0.001.",
    "gentuningcell": "Generator tuning — this generator's tuned size in cents. Type to override the optimum, click its sign to reverse the generator (its mapping row flips too, so the tuning is unchanged), or scroll the wheel to fine-tune by a thousandth of a cent.",
    # other grid controls
    "rangemode": "Choose how the generator's tuning range is measured — monotone or tradeoff.",
    "optimize": "Optimize the tuning to minimize damage now. Double-click to lock auto-optimize on.",
    # add / remove buttons
    "plus": "Add the next prime to the domain.",
    "minus": "Remove the highest prime from the domain.",
    "gen_plus": "Add a generator — raises the rank and dimensionality, mapping a new prime just.",
    "gen_minus": "Remove the last generator — lowers the rank and dimensionality.",
    "map_plus": "Add a generator (a mapping row) — un-tempers a comma, raising the rank and holding the dimensionality.",
    "map_minus": "Remove this generator (a mapping row) — lowers the rank, tempering one more comma; holds the dimensionality.",
    "map_drag": "Drag this generator (a mapping row) onto another row to add it into that row — a change of generator basis that holds the temperament and its tuning.",
    "int_drag": "Drag this interval onto another in the same column to combine them into their product. For the comma basis this re-expresses the same temperament; for a target / held / interest list it just combines the two intervals.",
    "basis_minus": "Remove the highest prime from the domain.",
    "comma_plus": "Add a comma to the basis.",
    "comma_minus": "Remove the last comma — un-tempers it, raising the rank; removing the sole comma leaves just intonation.",
    "interest_plus": "Add an interval of interest.",
    "interest_minus": "Remove this interval of interest.",
    "held_plus": "Add a held interval.",
    "held_minus": "Remove this held interval.",
    "target_plus": "Add a target interval to the list.",
    "target_minus": "Remove this target interval from the list.",
    # drag-and-drop
    "colgrip": "Drag this interval to another list, or reorder it — drop onto the commas to temper it out.",
    # fold / unfold toggles
    "rowtoggle": "Collapse or expand this row.",
    "coltoggle": "Collapse or expand this column.",
    "tiletoggle": "Collapse or expand this tile.",
    "alltoggle": "Collapse or expand the entire grid.",
}


# Controls whose kind backs several roles, told apart by the cell's exact id.
_ID_HELP: dict[str, str] = {
    # powerinput: the optimization power vs the complexity norm power and its dual
    "optimization:power": "Optimization power 𝑝 — ∞ minimizes the worst damage (minimax), 2 the RMS, 1 the mean. Type ∞, or scroll the wheel to step a finite power by 1.",
    "control:q": "Interval-complexity norm power 𝑞. Type it, or scroll the wheel to step it by 1.",
    "control:dual": "Dual norm power — the dual exponent of 𝑞, used to minimax over every interval.",
    # control_select: the complexity and weight-slope choosers (the prescaler is a preset now)
    "control:complexity": "Choose the interval-complexity measure used to weight damage.",
    "control:slope": "Choose the damage weight slope — how a target's weight scales with its complexity.",
    # control_check
    "control:diminuator": "Replace the diminuator — the smaller of each ratio's numerator and denominator — in the interval-complexity measure.",
    "control:all_interval": "Optimize over every interval at once (an all-interval scheme) instead of a finite target list.",
    # formchooser
    "formchooser:mapping": "Rewrite the mapping into a canonical form (an undoable edit).",
    "formchooser:comma_basis": "Rewrite the comma basis into a canonical form (an undoable edit).",
}

# preset choosers, keyed by name (the id is ``preset:<name>`` plus, for a copy
# of the chooser in a second tile, a trailing ``:<column>`` — so the name is segment 1).
_PRESET_HELP: dict[str, str] = {
    "temperament": "Load a named temperament preset — sets the mapping and comma basis.",
    "tuning": "Choose a named tuning scheme (e.g. minimax-S).",
    "target": "Choose the target-interval set and its limit — an integer limit for the triangle (TILT), an odd limit for the diamond (OLD). Scroll the wheel over the limit to step it by 1.",
    "prescaler": "Choose a predefined prescaler — the per-prime weighting applied before optimizing.",
}

# the editable quantities-row ratios (kind ``ratiocell``), keyed by the cell-id prefix (the
# column group: ``comma:0`` → "comma"). The scalar twin of the interval-vectors row cells, so
# each reads like its vector-cell tooltip but edits the whole interval as one fraction.
_RATIO_HELP: dict[str, str] = {
    "comma": "Comma ratio — an interval this temperament tempers out. Type a fraction (e.g. 81/80) to edit the comma.",
    "target": "Target ratio — an interval the tuning optimizes over. Type a fraction to override the chosen target set.",
    "held": "Held-interval ratio — an interval held unchanged (pure) by the tuning. Type a fraction to edit it.",
    "interest": "Interval-of-interest ratio — an interval you're tracking. Type a fraction to edit it.",
}

# the editable plain-text duals (kind ``ptextedit``), each naming its own value. These
# ids are exactly spreadsheet.EDITABLE_PTEXT, so every ptextedit cell is covered here.
_PTEXT_HELP: dict[str, str] = {
    "ptext:mapping:primes": "Type the mapping as a plain-text string (e.g. ⟨⟨1 0 -4]]) to drive the grid.",
    "ptext:vectors:commas": "Type the comma basis as a plain-text string to drive the grid.",
    "ptext:tuning:gens": "Type the generator tuning map as a plain-text string to drive the grid.",
    "ptext:vectors:targets": "Type the target-interval list as a plain-text string to drive the grid.",
    "ptext:prescaling:primes": "Type the prescaler as a plain-text string to drive the grid.",
}


def target_limit_help(problem: str) -> str:
    """Hover (and toast) text for an invalid target-limit entry, keyed by the problem
    :func:`rtt.web.service.target_limit_problem` reports: an even limit for the odd-limit
    diamond (``"odd"``), or a value that isn't a whole number (``"whole"``)."""
    return {
        "odd": "The odd-limit diamond (OLD) needs an odd limit.",
        "whole": "The target limit must be a whole number.",
    }[problem]


def objective_help(all_interval: bool) -> str:
    """Hover text for the optimization objective, which names a DIFFERENT quantity per mode.

    Target-based, the objective is the minimized damage ⟪𝐝⟫ₚ over the target list (the
    targets' damage combined by the optimization power 𝑝). All-interval, that quantity IS the
    retuning magnitude — the size of the prescaled retuning map 𝒓 at the dual-norm power
    dual(𝑞), minimized over every interval at once — matching the symbol's live relabel (see
    :mod:`rtt.web.spreadsheet`). The prescaler is named in words, never glyphed (it is 𝐿 or 𝑋
    depending on the scheme). :func:`control_help` returns the target-based wording as the static
    default for the objective cells; the renderer swaps in the all-interval wording in place."""
    if all_interval:
        return ("Optimization objective — the retuning magnitude that the tuning minimizes over "
                "every interval at once: the size of the prescaled retuning map 𝒓 at the "
                "dual-norm power dual(𝑞).")
    return ("Optimization objective ⟪𝐝⟫ₚ — the damage that the tuning minimizes over the target "
            "list: the targets' damage combined by the optimization power 𝑝.")


def control_help(kind: str, cid: str) -> str | None:
    """Hover text for an interactive grid control, or ``None`` for a read-only cell.

    Keyed on the cell's ``kind`` (see :mod:`rtt.web.spreadsheet`), with a few kinds
    disambiguated by their ``id`` where one kind backs several controls (e.g. a
    ``powerinput`` is the optimization power 𝑝, the norm power 𝑞, or its dual)."""
    if cid in OBJECTIVE_IDS:  # a read-only value that still carries help (text swapped live by the renderer)
        return objective_help(all_interval=False)
    if kind in READONLY_KINDS:
        # most read-only kinds carry no tooltip; a few derived values (e.g. the dual norm power
        # dual(𝑞), a powerdisplay) still do — their ids are listed in HELPED_READONLY_IDS
        return _ID_HELP.get(cid) if cid in HELPED_READONLY_IDS else None
    if kind == "preset":
        return _PRESET_HELP.get(cid.split(":")[1])
    if kind == "ptextedit":
        return _PTEXT_HELP.get(cid)
    if kind == "ratiocell":  # comma / target / held / interest, told apart by the id prefix
        return _RATIO_HELP.get(cid.split(":")[0])
    return _ID_HELP.get(cid) or _KIND_HELP.get(kind)
