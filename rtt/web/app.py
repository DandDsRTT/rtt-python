"""NiceGUI front end for the RTT monolith.

The layout is the spreadsheet coordinate model (:mod:`rtt.web.spreadsheet`): rows
are the temperament's quantities, columns the sets they're shown over, cells on
shared prime/generator axes. The renderer is persistent and reconciling — one
element per entity id, moved/updated on each state change rather than rebuilt —
so rows/columns animate via CSS transitions. Editing the mapping recomputes
in-process; domain expand/shrink and undo are available. No HTTP layer.
"""

from __future__ import annotations

import math
import sys
from html import escape as _escape
from pathlib import Path

from nicegui import ui

from rtt.web import presets
from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.editor import Editor

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration
_PANEL_W = 330  # px width the settings drawer opens to (the Show + example columns)
_RAIL_W = 40  # px width of the permanent left rail (hamburger + the rotated app title)

# One weight and colour for every EBK bracket, brace and monzo rule. Each mark is
# drawn as an SVG whose viewBox maps 1:1 to the cell's px size (see _svg), so a
# stroke specified as N px is exactly N px tall AND wide at any span — no scaling.
_BR_COLOR = "#1a1a1a"
_PENDING_COLOR = "#e53935"  # red for a pending comma's draft cells, brackets and "?"
# the value cells tile into a shared-border grid (a ruled spreadsheet, per the
# mockup): each cell draws a rule and overlaps its neighbour by exactly the rule
# width, so two abutting borders coincide as ONE line — no doubled inner rules.
_CELL_BORDER_W = 1  # px
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {_BR_COLOR}"
_CELL_FONT = 17  # px for the single-digit values in the square cells (≈0.37 of the cell)
_BR_BAR = 2  # main bar / monzo-rule / square-bracket bar thickness (px)
_BR_SERIF_T = 0.9  # square + top bracket serif thickness — a thin foot, well under the bar
_BR_SERIF_L = 6  # square + top bracket serif length (how far the foot reaches) — also
# the shared footprint width every value bracket (square AND angle) draws within
_BR_INSET = 2.5  # gap from a bracket's open side to the value cells it hugs
# The ⟨ and the brace are filled ribbons of varying width (see _ribbon): a
# calligraphic pen lays a LONG stroke down THICK and a SHORT one THIN. The thin
# ends are kept delicate so the thick/thin taper reads clearly.
_BR_ANGLE_THICK = 1.1  # ⟨ half-width at the vertex (heavier)
_BR_ANGLE_THIN = 0.45  # ⟨ half-width at the open tips (much lighter) — a pronounced taper
_BR_BRACE_THICK = 1.15  # brace arm half-width: the long horizontal stroke is thick
_BR_BRACE_THIN = 0.4  # brace end-serif half-width: the short upturn is thin
_BR_BRACE_CUSP = 0.2  # brace central-cusp half-width: the short dip is a near point
# A per-tile bar chart (damage, retuning) is drawn in the same 1:1 SVG box as the EBK
# marks: a left y-axis with nice-stepped gridlines, a darker zero baseline, and one bar
# per value column aligned to the cells below. Bars rise from the zero line for positive
# values and drop from it for negative, so an all-positive chart (damage) reads from the
# bottom and a signed one (retuning) reads from a centred zero.
_CHART_PAD_T = 9  # top padding (room for the top gridline's label)
_CHART_PAD_B = 2  # bottom padding
_CHART_BAR_FRAC = 0.5  # bar width as a fraction of the column it sits in
_CHART_GRID = "#bbbbbb"  # light gridline / tick colour
# The generator tuning-ranges chart: per-generator vertical I-beam range markers drawn
# in the same 1:1 SVG box as the EBK marks. A ranged generator is a stem with a cap at
# top (max cents) and bottom (min), labelled at the caps; a pinned generator (the period,
# octave held pure, so min == max) collapses to a single flat cap with one value.
_RANGE_TITLE = "tuning ranges"  # the panel title, per the mockup
_RANGE_CAP_W = 14  # I-beam cap width (px); the live-tuning tick is a shorter bar
_RANGE_MARK_W = 1.6  # I-beam stem + cap thickness (px) — constant at any height (1:1 viewBox)
_RANGE_PLOT_T = 25  # plot-area top (below the title + top-cap label; spaced off the title)
_RANGE_PLOT_B = 12  # plot-area bottom margin (room for the bottom-cap label)
_RANGE_FONT = 7  # cents-label / placeholder font size

# Colorization wash colours, keyed by the box-group name the layout tags a wash with
# (spreadsheet.COLORIZE_REGIONS). These are the mockup's saturated box-group tones;
# a wash sits behind the grey tiles so the colour reads through the gaps around them.
_TINTS = {"tuning": "#9acdcd", "temperament": "#cdcd9a"}  # cyan tuning rows, khaki temperament columns

_CSS = f"""
/* the grid's empty top-left corner cell now holds only the undo/redo buttons (the app
   title moved to the left rail). It fills the corner exactly — LABEL_W wide so its right
   edge meets the row-label column, HEADER_H tall so its bottom meets the column-header row
   — i.e. aligned with both the row titles and the column titles. Square (no radius), on the
   same light grey as the rail and pane; the buttons centre within it. */
.rtt-titletile {{ position:absolute; top:0; left:0; z-index:5; box-sizing:border-box;
                 width:{spreadsheet.LABEL_W}px; height:{spreadsheet.HEADER_H}px; background:#e0e0e0;
                 display:flex; align-items:center; justify-content:center; }}
.rtt-tile-btns {{ display:flex; gap:3px; }}
/* square bordered icon buttons (undo/redo), matching the mockup's framed glyphs */
.rtt-iconbtn {{ width:18px !important; min-width:18px !important; height:18px !important;
            min-height:18px !important; padding:0 !important; background:#fff !important;
            border:1px solid #000; border-radius:2px !important; box-shadow:none !important; }}
.rtt-iconbtn .q-icon {{ color:#000 !important; font-size:13px; }}
/* a disabled undo/redo button greys out like the disabled Show toggles. NiceGUI marks a
   set_enabled(False) button with the generic `.disabled` class (NOT Quasar's
   q-btn--disable), so target that: grey the icon AND border to #999/#bbb, well off the
   crisp black of an active button — so against Quasar's own disabled fade the button
   reads unmistakably inactive, matching the #999 of a disabled toggle. */
.rtt-iconbtn.disabled {{ border-color:#bbb !important; }}
.rtt-iconbtn.disabled .q-icon {{ color:#999 !important; }}
/* the left rail: a permanent light-grey column down the screen's left edge holding the
   hamburger (top) and, under it, the app title turned a quarter-turn. It sits to the LEFT of
   the pane and stays #e0e0e0 whether the pane is open or closed, so opening the pane never
   moves the title. It carries no align-self, so the pane group (align-items:stretch) makes it as
   tall as the group: the main app (grid) when the pane is collapsed, and the taller of the grid
   and the settings when the pane is open — so the bar always matches whatever it stands beside. */
.rtt-rail {{ flex:none; width:{_RAIL_W}px; background:#e0e0e0;
            display:flex; flex-direction:column; align-items:center; gap:10px; padding:7px 0 14px; }}
/* the app title, turned a quarter-turn (writing-mode) so it reads top-to-bottom down the
   rail. Noticeably larger than the 13px row/column titles, yet narrow enough to fit the rail. */
.rtt-sidetitle {{ writing-mode:vertical-rl; font-family:'Cambria',Georgia,serif; font-size:22px;
                 font-weight:bold; color:#000; white-space:nowrap; line-height:1; }}
/* the hamburger, parked at the top of the rail */
.rtt-hamburger {{ width:28px !important; min-width:28px !important; height:28px !important;
                 min-height:28px !important; padding:0 !important; background:#fff !important;
                 border:1px solid #999; border-radius:3px !important; box-shadow:none !important; }}
.rtt-hamburger .q-icon {{ color:#333 !important; font-size:19px; }}
/* the shell lays the rail+pane group and the app in a row */
.rtt-shell {{ position:relative; display:flex; flex-wrap:nowrap; gap:0; align-items:flex-start; }}
/* the rail+pane group is always align-self:stretch, so it — and the rail inside it (via
   align-items:stretch) — is as tall as the shell's tallest child. A COLLAPSED drawer is 0fr
   (zero height, below), so it adds nothing and the group matches the grid → the bar matches the
   main app. An OPEN drawer adds the settings' height, so the group grows to the taller of the
   grid and the settings. Opening the pane widens this group, pushing the app right. */
.rtt-panelgroup {{ display:flex; flex-wrap:nowrap; align-self:stretch; }}
/* the drawer animates BOTH its width (the slide-over) and its height (grid-template-rows 0fr->1fr,
   which grows/shrinks the pane to its content height), so opening/closing glides instead of the
   pane popping to full height. align-self:flex-start stops the group stretching the drawer, which
   would defeat the content-based fr sizing; a 0fr drawer contributes no height (see above). */
.rtt-drawer {{ display:grid; grid-template-rows:0fr; align-self:flex-start; width:0; overflow:hidden;
              transition:width {_T}, grid-template-rows {_T}; flex:none; }}
.rtt-drawer.rtt-drawer-open {{ width:{_PANEL_W}px; grid-template-rows:1fr; }}
/* the pane hugs its settings boxes — no min-height (a forced 100vh ran past the foot of the
   screen and added a scrollbar). overflow:hidden + min-height:0 let the drawer's grid-rows
   animation clip and grow it smoothly. */
.rtt-drawer-inner {{ width:{_PANEL_W}px; box-sizing:border-box; background:#e0e0e0; overflow:hidden;
                    min-height:0; font-family:'Cambria',Georgia,serif; color:#000; padding:8px 14px 16px; }}
/* the app fills the space right of the rail+pane group; min-width:0 lets a wide grid scroll
   inside its own .rtt-scroll rather than widening the page */
.rtt-app {{ flex:1 1 0; min-width:0; }}

.rtt-scroll {{ overflow-x:auto; max-width:100%; }}
.rtt-outer {{ background:#c0c0c0; padding:{_PAD}px; width:max-content;
              font-family:'Cambria',Georgia,serif; }}
/* isolate the board so the washes' mix-blend-mode composes only with the board's
   own layers (the white wash bases), not the page behind it */
.rtt-board {{ position:relative; isolation:isolate; transition:width {_T}, height {_T}; }}
@keyframes rtt-in {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.rtt-line, .rtt-block, .rtt-block-boxed, .rtt-cell, .rtt-wash, .rtt-washbase {{ animation:rtt-in {_T} ease; }}

.rtt-line {{ position:absolute; z-index:1; opacity:1; transition:left {_T}, top {_T},
            width {_T}, height {_T}, opacity {_T}; }}
.rtt-line-v {{ border-left:1px solid #e0e0e0; width:0; }}
.rtt-line-h {{ border-top:1px solid #e0e0e0; height:0; }}
/* a colorization wash: a colour band behind the grey tiles (below the gridlines too)
   filling a colorized group's row/column background. Each group's band has a white
   base on a LOWER layer (z-index:-1) than its darken colour layer (z-index:0), so the
   opaque bases can never cover another group's colour — wherever two colour bands
   cross, the darken min's them over white into the mockup's blend (cyan ⊓ yellow =
   green), independent of which group was toggled on first. */
.rtt-washbase, .rtt-wash {{ position:absolute; opacity:1;
            transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
.rtt-washbase {{ z-index:-1; background:#fff; }}
.rtt-wash {{ z-index:0; mix-blend-mode:darken; }}
.rtt-block {{ position:absolute; z-index:2; background:#e0e0e0; opacity:1;
             transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
/* the nested tuning-ranges box: a thin-bordered frame on the generator tuning map tile
   (per the mockup), above the grey tile but below the chart/selector cells */
.rtt-block-boxed {{ position:absolute; z-index:2; background:#e8e8e8; border:1px solid #8a8a8a;
             opacity:1;
             transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
.rtt-cell {{ position:absolute; z-index:3; display:flex; align-items:center; justify-content:center;
            opacity:1; transition:left {_T}, top {_T}, opacity {_T}; }}

.rtt-white {{ position:absolute; top:0; left:0;
             width:calc(100% + {_CELL_BORDER_W}px); height:calc(100% + {_CELL_BORDER_W}px);
             box-sizing:border-box; display:flex; align-items:center; justify-content:center;
             background:#fff; border:{_CELL_BORDER}; color:#000; font-size:{_CELL_FONT}px; }}
/* titles carry explicit "\n" breaks (col_header) so a multi-word header stacks to two
   lines (e.g. "domain" / "primes"); pre-line honors them. Tight line-height keeps them close. */
.rtt-colheader {{ font-size:13px; font-weight:bold; color:#000; white-space:pre-line;
                 width:100%; text-align:center; line-height:1.1; }}
.rtt-rowlabel {{ font-size:13px; font-weight:bold; color:#000; width:100%; text-align:right;
                padding-right:8px; line-height:1.1; }}
.rtt-val {{ font-size:{_CELL_FONT}px; color:#000; }}
/* the in-tile quantity name: small (≈0.2 of the cell, per the mockup) and wrapping
   within its column — the tile is sized tall enough to hold every wrapped line, so
   a long name on a narrow column never spills out of bounds. It top-aligns in its
   band so short names hug the cells when a sibling column's name wraps taller. */
.rtt-caption {{ width:100%; text-align:center; font-size:9px; line-height:10px; color:#333;
               overflow-wrap:break-word; font-family:'Cambria',Georgia,serif; }}
.rtt-caption-cell {{ align-items:flex-start; }}
/* most mnemonic underlines sit snug at the baseline; only a marked descender
   (g/j/p/q/y — e.g. the j of "just tuning map") drops its underline below the tail
   so it reads instead of hiding under the glyph */
.rtt-caption u.rtt-desc {{ text-underline-position:under; }}
.rtt-count {{ font-size:16px; color:#000; white-space:nowrap; }}
/* a read-only plain-text value: serif text on ONE line, no box. Its font-size is set
   inline per box (shrunk to fit its column), so a long value never wraps or spills. */
.rtt-ptext {{ width:100%; text-align:center; color:#000; white-space:nowrap; line-height:1;
             font-family:'Cambria',Georgia,serif; }}
/* the two editable duals (mapping, comma basis): a white bordered input filling its
   cell; an unparseable entry turns the border red (rtt-ptext-error) and is not applied.
   Its font-size is set inline per box too, so the value stays on one line. */
.rtt-ptextedit {{ width:100%; height:100%; }}
.rtt-ptextedit .q-field__control {{ min-height:0 !important; height:100%;
            background:#fff; border:1px solid #888; border-radius:2px; padding:0 3px; }}
.rtt-ptextedit .q-field__control::before, .rtt-ptextedit .q-field__control::after {{ display:none !important; }}
.rtt-ptextedit .q-field__native {{ color:#000; min-height:0 !important; padding:0; text-align:center;
            line-height:{spreadsheet.PTEXT_EDIT_H}px; white-space:nowrap; font-size:inherit !important;
            font-family:'Cambria',Georgia,serif; }}
.rtt-ptextedit .q-field__marginal, .rtt-ptextedit .q-field__bottom {{ display:none !important; }}
.rtt-ptextedit.rtt-ptext-error .q-field__control {{ border-color:#d33; }}
/* the quantity symbol above the caption: _math_html renders the base letter in the
   UI serif with explicit weight/slant (bold-italic for maps, bold-upright for
   vectors/matrices) — not a maths-font glyph, whose styling font fallback dropped */
.rtt-symbol {{ width:100%; text-align:center; font-size:15px; color:#000; line-height:1;
              font-family:'Cambria',Georgia,serif; }}
/* the per-box "units: …" line below the caption, and the domain-units row/col labels:
   small centred serif, the unit glyphs styled by _math_html (bold-upright g/p) */
.rtt-units {{ width:100%; text-align:center; font-size:10px; color:#333; line-height:1;
            white-space:nowrap; font-family:'Cambria',Georgia,serif; }}
/* every EBK mark (⟨ ] [, top bracket, brace, monzo rule) is one SVG that fills
   its cell at a 1:1 viewBox, so its strokes keep a constant px weight at any span */
.rtt-svgfill {{ width:100%; height:100%; line-height:0; }}
/* the symbol + caption (and the units line) hold off their fade-in until the tile has expanded */
.rtt-caption-cell, .rtt-symbol-cell, .rtt-units-cell {{ animation-delay:{_T}; animation-fill-mode:backwards; }}
/* the preselect chooser dropdowns: a compact bordered q-select that fills its
   PRESELECT_H cell, with a thin grey rule and a small caret — like the mockup */
.rtt-preselect {{ width:100%; }}
.rtt-preselect .q-field__control {{ min-height:0 !important; height:20px;
            background:#fff; border:1px solid #999; border-radius:2px; padding:0 2px 0 6px; }}
.rtt-preselect .q-field__control::before, .rtt-preselect .q-field__control::after {{ display:none !important; }}
.rtt-preselect .q-field__native, .rtt-preselect .q-field__input {{ font-size:11px; color:#000;
            min-height:0 !important; padding:0; line-height:20px; font-family:'Cambria',Georgia,serif; }}
.rtt-preselect .q-field__marginal, .rtt-preselect .q-field__append {{ height:20px; min-height:0 !important; }}
.rtt-preselect .q-icon {{ font-size:15px; color:#555; }}
/* each chooser's dropdown popup matches the field's Cambria text, with compact items */
.rtt-select-popup {{ font-family:'Cambria',Georgia,serif; }}
/* compact items; a long name (e.g. a systematic tuning) wraps within the field
   width rather than widening the popup past the field it drops from */
.rtt-select-popup .q-item {{ min-height:22px; padding:1px 8px; font-size:11px; }}
.rtt-select-popup .q-item__label {{ font-size:11px; white-space:normal;
              font-family:'Cambria',Georgia,serif; }}
/* greyscale the selection (no Quasar primary blue): the chosen item keeps a steady
   light-grey wash so it stays visible, lighter than the darker grey hover/keyboard
   highlight (the focus-helper, at Quasar's own hover/focus opacity) */
.rtt-select-popup .q-item--active {{ color:#000 !important; background:#ededed; }}
.rtt-select-popup .q-focus-helper {{ background:#000 !important; }}
/* the target chooser pairs a SQUARE numeric limit override with the TILT/OLD family select */
.rtt-preselect-target {{ width:100%; height:20px; display:flex; gap:3px; align-items:center; }}
.rtt-preselect-target .rtt-preselect-num {{ flex:0 0 20px; }}  /* square: matches the 20px height */
.rtt-preselect-target .rtt-preselect {{ flex:1 1 auto; width:auto; }}
.rtt-preselect-num .q-field__control {{ min-height:0 !important; height:20px;
            background:#fff; border:1px solid #999; border-radius:2px; padding:0 2px; }}
.rtt-preselect-num .q-field__control::before, .rtt-preselect-num .q-field__control::after {{ display:none !important; }}
.rtt-preselect-num .q-field__native {{ font-size:11px; color:#000; min-height:0 !important; padding:0;
            line-height:20px; text-align:center; font-family:'Cambria',Georgia,serif; }}
.rtt-preselect-num .q-field__native::-webkit-inner-spin-button {{ -webkit-appearance:none; margin:0; }}
.rtt-preselect-num .q-field__marginal, .rtt-preselect-num .q-field__append {{ display:none !important; }}
/* the monotone/tradeoff range selector under the ranges chart: two square indicators
   side by side (filled = selected), per the mockup, with small Cambria labels */
.rtt-rangemode {{ width:100%; display:flex; flex-direction:row; align-items:center;
                  justify-content:center; gap:4px; line-height:1; overflow:hidden; }}
.rtt-rangeopt {{ display:flex; align-items:center; gap:2px; cursor:pointer; user-select:none; }}
.rtt-rangebox {{ width:8px; height:8px; flex:none; border:1px solid #555; background:#fff;
                box-sizing:border-box; position:relative; }}
/* selected = a square "radio": the ring stays and a smaller filled square sits centred
   inside it (like a radio dot, but square) — not a solid fill */
.rtt-rangeopt-on .rtt-rangebox::after {{ content:""; position:absolute; inset:1px; background:#000; }}
.rtt-rangelabel {{ font-family:'Cambria',Georgia,serif; font-size:7.5px; color:#000; white-space:nowrap; }}
.rtt-ratio {{ display:flex; align-items:center; justify-content:center; gap:1px;
             font-size:13px; color:#000; }}
.rtt-approx {{ font-size:13px; align-self:center; }}
.rtt-frac {{ display:inline-flex; flex-direction:column; align-items:center; line-height:1.04; }}
.rtt-frac-num {{ border-bottom:1px solid #000; padding:0 3px; }}
.rtt-frac-den {{ padding:0 3px; }}
.rtt-tval {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
            width:100%; color:#000; white-space:nowrap; line-height:1.05; }}
.rtt-cents-int {{ font-size:10px; }}
.rtt-cents-frac {{ font-size:7px; color:#000; }}
/* a just value's closed form, stacked as "1200 · log₂(3/2)" over "= 701.96"; each
   line's font is scaled (inline) to fit the narrow value square, so it never overflows */
.rtt-mathexpr {{ width:100%; height:100%; display:flex; align-items:center; justify-content:center; }}
.rtt-mathexpr-stack {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
                      line-height:1.15; color:#000; white-space:nowrap; }}
.rtt-cellinput {{ width:100% !important; height:100%; min-height:0; overflow:visible; }}
.rtt-cellinput .q-field__inner {{ overflow:visible; }}
.rtt-cellinput .q-field__control {{ position:absolute !important; top:0; left:0;
            width:calc(100% + {_CELL_BORDER_W}px) !important; height:calc(100% + {_CELL_BORDER_W}px) !important;
            max-width:none !important; min-height:0 !important;
            box-sizing:border-box; padding:0 !important; background:#fff; border:{_CELL_BORDER}; }}
.rtt-cellinput .q-field__control::before, .rtt-cellinput .q-field__control::after {{ display:none !important; }}
.rtt-cellinput .q-field__native {{ text-align:center; padding:0 !important; color:#000; font-size:{_CELL_FONT}px;
            min-height:0; font-family:'Cambria',Georgia,serif; }}
.rtt-cellinput .q-field__bottom, .rtt-cellinput .q-field__marginal {{ display:none !important; }}
/* a pending comma's draft cells: red-outlined and empty until the user types a valid
   independent comma, at which point it commits and reverts to a normal black cell. The
   typed entries are red too, matching the brackets, the "?" quantity, and the plain text */
.rtt-cellinput.rtt-pending .q-field__control {{ border-color:{_PENDING_COLOR} !important; }}
.rtt-cellinput.rtt-pending .q-field__native {{ color:{_PENDING_COLOR} !important; }}
/* a pending comma's "?" quantity (and the draft vector in the plain text), in the same
   red as its draft cells/brackets */
.rtt-pending-q {{ color:{_PENDING_COLOR} !important; }}
/* the comma basis plain text while a comma is pending: not an editable input (which is
   one colour) but a static box matching the input's frame, holding the committed commas
   in black and the red draft vector — you edit the draft in the red grid cells */
.rtt-ptextpending {{ width:100%; height:100%; box-sizing:border-box; display:flex;
            align-items:center; justify-content:center; background:#fff; border:1px solid #888;
            border-radius:2px; padding:0 3px; color:#000; white-space:nowrap; overflow:hidden;
            font-family:'Cambria',Georgia,serif; }}
/* the +/− controls are half the square mapping/prime cell, sharing its exact border */
.rtt-btn {{ width:15px !important; min-width:15px !important; height:15px !important;
           min-height:15px !important; background:#fff !important; border:{_CELL_BORDER} !important;
           border-radius:0 !important; padding:0 !important; box-shadow:none !important; }}
/* center the glyph: Quasar's content box defaults to a tall line-height that
   overflowed the small square; pin it to the box so the flex centering can take over */
.rtt-btn .q-btn__content {{ color:#000 !important; font-size:13px; line-height:1; min-height:0;
           font-family:'Cambria',Georgia,serif; }}
/* the domain − is a hover affordance: an invisible zone over the removable prime's
   header reveals the button parked at its top (above the header, clear of inputs). The
   zone sits above the prime cells (z-index) so a column added via + can't paint over it
   and shrink the hover target down to just the button itself. */
.rtt-minus-zone {{ background:transparent; z-index:4; }}
.rtt-minus-btn {{ position:absolute !important; top:0; left:50%; transform:translateX(-50%);
           opacity:0; pointer-events:none; transition:opacity {_T}; }}
.rtt-minus-zone:hover .rtt-minus-btn {{ opacity:1; pointer-events:auto; }}
/* the vertical basis's domain −: reveals to the RIGHT of the highest prime (the
   spine's spare width), since the row above it is the next prime, not free space */
.rtt-minus-btn-v {{ position:absolute !important; right:0; top:50%; transform:translateY(-50%);
           opacity:0; pointer-events:none; transition:opacity {_T}; }}
.rtt-minus-zone:hover .rtt-minus-btn-v {{ opacity:1; pointer-events:auto; }}

.rtt-toggle {{ width:100%; height:100%; display:flex; align-items:center; justify-content:center;
              font-size:12px !important; line-height:1; color:#666; background:#fff;
              border:1px solid #bbb; cursor:pointer; user-select:none; }}
.rtt-toggle:hover {{ background:#ececec; color:#000; }}
/* the panel's two column headers: "show" (the toggles) and "example" (their sample
   renders), aligned over the grid columns the rows below use. Both share one font and
   sit on a common baseline so the two words line up. */
.rtt-show-head {{ display:grid; grid-template-columns:160px 1fr; align-items:baseline;
                 padding:0 9px 2px 9px; }}
.rtt-show-title {{ font-size:14px; font-weight:bold; }}
.rtt-show-examplehdr {{ font-size:14px; font-weight:bold; }}
/* general and specific each sit in their own rounded, lightly-bordered sub-card,
   stacked vertically (general above specific) */
.rtt-show-group {{ border:1px solid #c4c4c4; border-radius:5px; background:#e6e6e6;
                  padding:6px 8px; margin-top:8px; }}
.rtt-show-grouptitle {{ font-size:13px; font-style:italic; text-align:center;
                       color:#000; margin-bottom:4px; }}
/* one toggle row: the checkbox+label in the Show column, its sample in the example column */
.rtt-show-row {{ display:grid; grid-template-columns:160px 1fr; align-items:center; min-height:26px; }}
.rtt-show-item .q-checkbox__label {{ font-family:'Cambria',Georgia,serif; font-size:13px;
                                    color:#000; white-space:nowrap; }}
/* a not-yet-built toggle is disabled — make that unmistakable: render its label AND
   its checkbox box the same light grey (vs the crisp black of an active toggle), a
   far clearer "inactive" cue than Quasar's faint default opacity dim alone */
.rtt-show-item.disabled .q-checkbox__label {{ color:#999; }}
.rtt-show-item.disabled .q-checkbox__inner {{ color:#999 !important; }}
/* a sub-control's checkbox sits indented under its parent toggle; only the Show
   column indents, so the example column stays aligned with the other rows */
.rtt-show-sub .rtt-show-item {{ margin-left:18px; }}
.rtt-ex-cell {{ font-family:'Cambria',Georgia,serif; font-size:14px; color:#000;
               display:flex; align-items:center; min-height:24px; }}
/* a disabled toggle's sample greys to match its label — color for the glyph examples,
   plus the same 0.75 dim Quasar puts on the checkbox so the two read as one shade */
.rtt-ex-cell.rtt-ex-disabled {{ color:#999; opacity:0.75; }}
.rtt-ex {{ white-space:nowrap; }}
"""

_LABEL_KINDS = {"prime", "colheader", "rowlabel", "mapped", "vec",
                "rowtoggle", "coltoggle", "tiletoggle", "alltoggle"}  # "ptext" has its own font-sync branch

# A math-expression cell stacks 1–2 lines ("1200 · log₂(3/2)" over "= 701.96") in a
# narrow value square, so each line's font is scaled down to fit the cell width.
_EXPR_MAX_FONT = 9.0  # px — short lines (a bare prime map) sit at the comfortable size
_EXPR_MIN_FONT = 3.5  # px — the floor for the longest target-ratio expressions
_EXPR_CHAR_W = 0.5  # a glyph's width as a fraction of font size (serif average), for the fit


def _fit_font(line: str, width: float, max_font: float = _EXPR_MAX_FONT,
              min_font: float = _EXPR_MIN_FONT, char_w: float = _EXPR_CHAR_W) -> float:
    """Largest font (capped at ``max_font``, floored at ``min_font``) at which ``line``
    fits ``width`` px on one line. Shared by the math-expression cells and the
    plain-text value boxes (which pass their own bounds)."""
    if not line:
        return max_font
    fit = (width - 2) / (len(line) * char_w)
    return max(min_font, min(max_font, fit))


def _mathexpr_html(text: str, width: float) -> str:
    """The stacked HTML for a math-expression cell: each newline-separated line on
    its own row, its font shrunk to fit the cell so long expressions stay in-bounds."""
    lines = "".join(
        f'<div style="font-size:{_fit_font(line, width):.2f}px">{line}</div>'
        for line in text.split("\n")
    )
    return f'<div class="rtt-mathexpr-stack">{lines}</div>'

# Every EBK mark is drawn by hand as an SVG sized to the cell. The viewBox is the
# cell's own px box (0 0 w h), so one viewBox unit == one px: a stroke we declare
# as N px renders exactly N px wide regardless of how tall/long the mark spans.
# This is the single rule that keeps the brackets and brace a constant weight —
# the rejected font glyph scaled its weight with its height, and a fixed viewBox
# stretched to the cell sheared its serifs. Square/top brackets are crisp filled
# rects; the calligraphic ⟨ and brace are filled variable-width ribbons (_ribbon).
_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar"}


def _svg(w, h, body):
    return (f'<svg width="100%" height="100%" viewBox="0 0 {w:.2f} {h:.2f}" '
            f'preserveAspectRatio="none" style="display:block;overflow:visible">{body}</svg>')


def _rect(x, y, w, h):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{_BR_COLOR}"/>'


def _ribbon(pts):
    """One filled path tracing a variable-width stroke down a centreline. ``pts``
    is a list of ``(x, y, half_width)``; the outline runs up one offset edge and
    back down the other. A long run can be laid thick and a short turn thin, and
    the centreline may double back (the brace cusp, the ⟨ vertex) — the offsets
    meet at a clean point there, and any inner overlap fills solid (nonzero)."""
    edge_a, edge_b = [], []
    n = len(pts)
    for i in range(n):
        x, y, hw = pts[i]
        px, py = pts[i - 1][:2] if i else pts[i][:2]
        nx, ny = pts[i + 1][:2] if i < n - 1 else pts[i][:2]
        tx, ty = nx - px, ny - py
        length = math.hypot(tx, ty) or 1.0
        ox, oy = -ty / length * hw, tx / length * hw  # normal * half-width
        edge_a.append((x + ox, y + oy))
        edge_b.append((x - ox, y - oy))
    outline = edge_a + edge_b[::-1]
    return ('<path fill="' + _BR_COLOR + '" d="M'
            + ' '.join(f'{x:.2f},{y:.2f}' for x, y in outline) + ' Z"/>')


def _qbez(p0, ctrl, p1, w0, w1, n, *, skip_first=False):
    """Sample a quadratic Bézier from ``p0`` to ``p1`` into ``(x, y, half_width)``
    centreline points, the width lerped ``w0``->``w1`` along it."""
    out = []
    for i in range(n + 1):
        if skip_first and i == 0:
            continue
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * ctrl[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * ctrl[1] + t * t * p1[1]
        out.append((x, y, w0 + (w1 - w0) * t))
    return out


def _square_bracket(w, h, side):
    """``[`` or ``]`` as a bar + two perpendicular feet, hugging the value cells
    (open side ``_BR_INSET`` from them). Constant weight at 1 row or many."""
    if side == "left":  # bar on the left, feet reaching right toward the cells
        x_in = w - _BR_INSET
        x_out = x_in - _BR_SERIF_L
        bar_x = x_out
    else:  # "right": bar on the right, feet reaching left toward the cells
        x_out = _BR_INSET
        bar_x = x_out + _BR_SERIF_L - _BR_BAR
    return _svg(w, h,
        _rect(bar_x, 0, _BR_BAR, h)
        + _rect(x_out, 0, _BR_SERIF_L, _BR_SERIF_T)
        + _rect(x_out, h - _BR_SERIF_T, _BR_SERIF_L, _BR_SERIF_T))


def _top_bracket(w, h):
    """The matrix's spanning top bracket: a bar across the top with a down-foot at
    each end. Same weights as the square brackets, so the frame reads as one font."""
    return _svg(w, h,
        _rect(0, 0, w, _BR_BAR)
        + _rect(0, 0, _BR_SERIF_T, _BR_SERIF_L)
        + _rect(w - _BR_SERIF_T, 0, _BR_SERIF_T, _BR_SERIF_L))


def _angle_bracket(w, h):
    """``⟨`` drawn within the SAME oblong footprint as the square brackets — a
    serif-length wide and the full cell height — so every value bracket shares one
    rectangle. A filled ribbon, subtly heavier at the vertex than the open tips.
    The centreline insets (vertex by the thick half-width, tips by the thin one)
    land the ribbon's outer edge on that footprint, vertex hugging the far side."""
    bx1 = w - _BR_INSET  # open tips, nearest the value cells
    bx0 = bx1 - _BR_SERIF_L  # vertex, at the far edge — width matches the square's reach
    cy = h / 2
    vx, tx = bx0 + _BR_ANGLE_THICK, bx1 - 0.4
    top, vertex, bot = (tx, 0.2), (vx, cy), (tx, h - 0.2)
    n = 10
    pts = [(top[0] + (vertex[0] - top[0]) * i / n, top[1] + (vertex[1] - top[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (bot[0] - vertex[0]) * i / n, vertex[1] + (bot[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _brace(w, h):
    """The matrix's bottom curly brace as ONE variable-width ribbon computed from
    the width: long horizontal arms (THICK) sweeping from upturned end-serifs
    (THIN) into a central downward cusp (a THIN near-point). The main (arm) stroke
    runs through the vertical CENTRE of the box, with the end-serifs rising and the
    cusp dipping by the SAME amount, so the brace is balanced about its main stroke
    (not top-heavy). Its depth (the short bounding dimension) matches the value
    brackets' footprint. On a wide span the curls keep a fixed shape and only the
    arm grows; on a narrow span (the per-column braces) the curls shrink together
    so a short arm always survives. One outline, so no seams or overshoot."""
    cx = w / 2
    end_x, serif_dx, cusp_dx = 2.0, 3.2, 5.5
    span = end_x + serif_dx + cusp_dx + 1.0  # the curls plus a reserved minimal arm
    if span > cx:  # too narrow to fit full curls — shrink them together to fit
        s = cx / span
        end_x, serif_dx, cusp_dx = end_x * s, serif_dx * s, cusp_dx * s
    arm_y = h / 2  # the main stroke runs through the box's vertical centre...
    reach = h / 2 - 0.5  # ...with the serifs rising this far above it. The cusp
    # centreline stops a touch short because its pointed tip's fill overshoots
    # downward, so this lands the cusp's fill symmetric to the serif tips — i.e.
    # the arm ends up at the bounding box's exact centre, not above it.
    tip_y, cusp_y = arm_y - reach, arm_y + reach - 0.3
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = 10
    pts = _qbez((end_x, tip_y), (end_x, arm_y), (end_x + serif_dx, arm_y), thin, thick, n)
    pts.append((cx - cusp_dx, arm_y, thick))
    pts += _qbez((cx - cusp_dx, arm_y), (cx, arm_y), (cx, cusp_y), thick, cusp, n, skip_first=True)
    pts += _qbez((cx, cusp_y), (cx, arm_y), (cx + cusp_dx, arm_y), cusp, thick, n, skip_first=True)
    pts.append((w - end_x - serif_dx, arm_y, thick))
    pts += _qbez((w - end_x - serif_dx, arm_y), (w - end_x, arm_y), (w - end_x, tip_y),
                 thick, thin, n, skip_first=True)
    return _svg(w, h, _ribbon(pts))


def _curly_bracket(w, h):
    """A left curly brace ``{`` for the generator tuning map's frame (it reads ``{ … ]`` —
    curly open, square close — per the mockup). The matrix brace (:func:`_brace`) turned a
    quarter-turn: ONE variable-width ribbon with a vertical spine, the two ends curling
    toward the value cells (thin tips) and a central cusp poking to the far edge (a thin
    near-point). Shares the value brackets' oblong footprint, so the cusp sits where a ``⟨``
    vertex would. The curls keep a fixed shape; only the spine grows with the cell height."""
    cy = h / 2
    end_y, serif_dy, cusp_dy = 2.0, 3.2, 5.5
    span = end_y + serif_dy + cusp_dy + 1.0  # the curls plus a reserved minimal spine
    if span > cy:  # too short to fit full curls — shrink them together to fit
        s = cy / span
        end_y, serif_dy, cusp_dy = end_y * s, serif_dy * s, cusp_dy * s
    tip_x = w - _BR_INSET  # the end-tips curl in toward the value cells
    cusp_x = tip_x - _BR_SERIF_L  # the cusp pokes to the far edge (width matches the ⟨ reach)
    arm_x = (tip_x + cusp_x) / 2  # the spine runs midway between
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = 10
    pts = _qbez((tip_x, end_y), (arm_x, end_y), (arm_x, end_y + serif_dy), thin, thick, n)
    pts.append((arm_x, cy - cusp_dy, thick))
    pts += _qbez((arm_x, cy - cusp_dy), (arm_x, cy), (cusp_x, cy), thick, cusp, n, skip_first=True)
    pts += _qbez((cusp_x, cy), (arm_x, cy), (arm_x, cy + cusp_dy), cusp, thick, n, skip_first=True)
    pts.append((arm_x, h - end_y - serif_dy, thick))
    pts += _qbez((arm_x, h - end_y - serif_dy), (arm_x, h - end_y), (tip_x, h - end_y),
                 thick, thin, n, skip_first=True)
    return _svg(w, h, _ribbon(pts))


def _angle_foot(w, h):
    """The ket's ``⟩`` turned a quarter-turn to close a raw (untempered) monzo column:
    a shallow downward chevron from the top corners to a centre vertex, the calligraphic
    weight of the ⟨ angle bracket (heavier at the vertex than the open tips). A monzo
    thus reads ``[ … ⟩`` down its column — square top, angle foot — telling it apart
    from a tempered column, which closes with the curly brace (:func:`_brace`)."""
    cx = w / 2
    # the vertex's outer (thick) edge must land inside the box, not poke past it, so
    # the chevron's footprint matches the other marks' shared short dimension — hence
    # the vertex centreline sits a thick-half-width-plus-margin up from the bottom
    ty, vy = 0.85, h - 0.5 - _BR_ANGLE_THICK
    left, vertex, right = (0.8, ty), (cx, vy), (w - 0.8, ty)
    n = 8
    pts = [(left[0] + (vertex[0] - left[0]) * i / n, left[1] + (vertex[1] - left[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (right[0] - vertex[0]) * i / n, vertex[1] + (right[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _vbar(w, h):
    """A vertical rule between the mapped list's monzo columns, the bar's weight."""
    return _svg(w, h, _rect((w - _BR_BAR) / 2, 0, _BR_BAR, h))


def _ebk_svg(cb):
    """The SVG for one EBK cell, generated from its current px box (cb.w, cb.h). A
    pending comma's marks are recoloured red to match its draft cells."""
    if cb.kind == "bracket":
        if cb.text == "⟨":
            svg = _angle_bracket(cb.w, cb.h)
        elif cb.text == "{":
            svg = _curly_bracket(cb.w, cb.h)
        else:
            svg = _square_bracket(cb.w, cb.h, "left" if cb.text == "[" else "right")
    elif cb.kind == "ebktop":
        svg = _top_bracket(cb.w, cb.h)
    elif cb.kind == "ebkbrace":
        svg = _brace(cb.w, cb.h)
    elif cb.kind == "ebkangle":
        svg = _angle_foot(cb.w, cb.h)
    else:
        svg = _vbar(cb.w, cb.h)  # "vbar"
    return svg.replace(_BR_COLOR, _PENDING_COLOR) if cb.pending else svg


def _chart_ticks(lo, hi):
    """A short list of nice round tick values spanning ``[lo, hi]`` (~4 steps)."""
    span = hi - lo
    if span <= 0:
        return [0.0]
    raw = span / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag)
    ticks, v = [], math.floor(lo / step) * step
    while v <= hi + step * 1e-9:
        if v >= lo - step * 1e-9:
            ticks.append(round(v, 6))
        v += step
    return ticks


def _bar_chart(w, h, values):
    """A bar chart filling its 1:1 px box: one bar per value, aligned to the value
    columns below, rising/falling from a zero baseline; gridlines mark nice ticks."""
    axis_x, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    vals = tuple(values)
    vmax = max(vals + (0.0,))
    vmin = min(vals + (0.0,))
    if vmax == vmin:
        vmax = vmin + 1.0
    plot_top, plot_bot = _CHART_PAD_T, h - _CHART_PAD_B
    span = vmax - vmin

    def y_of(v):
        return plot_top + (vmax - v) / span * (plot_bot - plot_top)

    body = []
    for tv in _chart_ticks(vmin, vmax):
        ty = y_of(tv)
        body.append(f'<line x1="{axis_x:.2f}" y1="{ty:.2f}" x2="{w:.2f}" y2="{ty:.2f}" '
                    f'stroke="{_CHART_GRID}" stroke-width="0.5"/>')
        body.append(f'<text x="{axis_x - 2:.2f}" y="{ty + 2.4:.2f}" text-anchor="end" '
                    f'font-size="7" fill="{_BR_COLOR}">{tv:g}</text>')
    zero_y = y_of(0)
    body.append(f'<line x1="{axis_x:.2f}" y1="{zero_y:.2f}" x2="{w:.2f}" y2="{zero_y:.2f}" '
                f'stroke="{_BR_COLOR}" stroke-width="1"/>')
    body.append(_rect(axis_x, plot_top, 0.8, plot_bot - plot_top))  # vertical y-axis
    bw = col_w * _CHART_BAR_FRAC
    for i, v in enumerate(vals):
        cx = axis_x + i * col_w + col_w / 2
        yv = y_of(v)
        top, bot = min(zero_y, yv), max(zero_y, yv)
        body.append(_rect(cx - bw / 2, top, bw, bot - top))
    return _svg(w, h, "".join(body))


def _range_chart(w, h, ranges, tunings=()):
    """The generator tuning-ranges chart filling its 1:1 px box: a titled panel with one
    vertical I-beam per generator showing its [min, max] tuning in cents (max at the top
    cap, min at the bottom), with a shorter tick marking where the live tuning falls within
    that range. A pinned generator (min == max) draws a single flat cap; empty ``ranges``
    draws a 'no range' placeholder."""
    cx0, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    title = (f'<text x="{w / 2:.2f}" y="9" text-anchor="middle" font-size="8.5" '
             f'font-weight="bold" fill="{_BR_COLOR}">{_RANGE_TITLE}</text>')
    if not ranges:
        return _svg(w, h, title + f'<text x="{w / 2:.2f}" y="{h / 2 + 2:.2f}" text-anchor="middle" '
                    f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">no range</text>')
    plot_top, plot_bot = _RANGE_PLOT_T, h - _RANGE_PLOT_B
    mid, hw = (plot_top + plot_bot) / 2, _RANGE_MARK_W / 2
    cap_half, tick_half = _RANGE_CAP_W / 2, _RANGE_CAP_W / 2 - 3  # the live-tuning tick is shorter

    def bar(cx, y, half):
        return _rect(cx - half, y - hw, 2 * half, _RANGE_MARK_W)

    def label(cx, y, v):
        return (f'<text x="{cx:.2f}" y="{y:.2f}" text-anchor="middle" '
                f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">{v:.3f}</text>')

    body = [title]
    for i, (lo, hi) in enumerate(ranges):
        cx = cx0 + i * col_w + col_w / 2
        if hi - lo < 1e-6:  # pinned (e.g. the period): one value, no range — a single cap
            body.append(bar(cx, mid, cap_half) + label(cx, mid - 4, lo))
            continue
        # a vertical stem capped at the max (top) and min (bottom), labelled at each
        body.append(_rect(cx - hw, plot_top, _RANGE_MARK_W, plot_bot - plot_top))
        body.append(bar(cx, plot_top, cap_half) + bar(cx, plot_bot, cap_half))
        body.append(label(cx, plot_top - 4, hi) + label(cx, plot_bot + 9, lo))
        if i < len(tunings):  # the live tuning, ticked where it falls within [min, max]
            frac = min(1.0, max(0.0, (hi - tunings[i]) / (hi - lo)))
            body.append(bar(cx, plot_top + frac * (plot_bot - plot_top), tick_half))
    return _svg(w, h, "".join(body))


def _parse_int(text):
    """``text`` -> int, or None for blank/partial input (matching the old parseInt)."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _ratio_parts(text):
    """Split a ratio like ``"3/2"`` into ``("3", "2")``; None if it isn't a fraction."""
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text):
    """Split a cents value like ``"1899.260"`` into a big whole part and small fraction."""
    whole, _, frac = str(text).partition(".")
    return whole, frac


def _ptext_font(text, width):
    """The largest font (px, capped at PTEXT_MAX_FONT) at which ``text`` still fits on
    ONE line within a ``width``-px box — so a long value (a tuning row) shrinks rather
    than wrapping or spilling. Shares _fit_font with the math cells, at the plain-text
    bounds (0.58·font is a conservative serif estimate for digit-dense EBK strings)."""
    return round(_fit_font(text, width, max_font=spreadsheet.PTEXT_MAX_FONT, min_font=5.0, char_w=0.58), 1)


_DESCENDERS = "gjpqy"  # letters whose tail dips below the baseline


def _underline_html(text, spans):
    """``text`` with each ``(start, len)`` span wrapped in ``<u>`` — the mnemonic
    underline marking a caption's symbol letter. All text is HTML-escaped. A span
    holding a descender (g/j/p/q/y) is tagged ``rtt-desc`` so only its underline is
    dropped below the tail; the rest keep the normal snug underline."""
    out, i = [], 0
    for start, length in sorted(spans):
        seg = text[start:start + length]
        tag = '<u class="rtt-desc">' if any(c in _DESCENDERS for c in seg) else "<u>"
        out.append(_escape(text[i:start]) + tag + _escape(seg) + "</u>")
        i = start + length
    out.append(_escape(text[i:]))
    return "".join(out)


# The "example" column of the Show panel: one illustrative sample per toggle, read
# from the mockup's Show legend. Most are a glyph or short string (the maps' bold-
# italic letters, the vectors/matrices' bold-upright ones, the plain captions); the
# few graphical samples (the gridded EBK mark, the chart, the preselect chooser) are
# built below from the same primitives the grid uses.
_EXAMPLE_TEXT: dict[str, str] = {
    "names": "tuning map",
    "symbols": "𝒕",
    "equivalences": "𝒕 = 𝒈𝑀",
    "plain_text_values": "[ ⟨12 19 24] }",
    "units": "𝐩",
    "math_expressions": "log₂3",
    "counts": "𝑑",
    "domain_quantities": "2.3.5",
    "domain_units": "p₁/",
    "temperament_boxes": "𝑀",
    "form_controls": "canonical form",
    "tuning_boxes": "T",
    "optimization": "𝑝",
    "weighting": "𝒘",
    "all_interval": "minimax-S",
    "alt_complexity": "E-lp",
    "projection": "𝑃",
    "generator_detempering": "D",
    "nonstandard_domain": "prime-based",
    "identity_objects": "𝑀ⱼ",
}


def _example_grid() -> str:
    """The gridded-values sample: the ⟨12 19 24] EBK mark (angle bracket, three
    boxed components, closing bracket) framed by the matrix top-bracket and brace —
    the same hand-drawn marks the grid uses, shrunk to a legend sample."""
    def box(x, text):
        return (f'<div style="position:absolute;left:{x}px;top:11px;width:22px;height:20px;'
                'border:1px solid #000;background:#fff;display:flex;align-items:center;'
                f'justify-content:center;font-size:11px">{text}</div>')

    def mark(x, y, w, h, svg):
        return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">{svg}</div>'

    return ('<div style="position:relative;width:90px;height:42px">'
            + mark(11, 2, 66, 6, _top_bracket(66, 6))
            + mark(0, 11, 10, 20, _angle_bracket(10, 20))
            + box(12, "12") + box(33, "19") + box(54, "24")
            + mark(78, 11, 10, 20, _square_bracket(10, 20, "right"))
            + mark(11, 34, 66, 6, _brace(66, 6))
            + '</div>')


def _example_chart() -> str:
    """The charts sample: a tiny signed bar sparkline — a 5 / −5 axis with a bar
    dipping below the zero line, as the mockup's legend shows."""
    return ('<div style="position:relative;width:84px;height:34px">'
            '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
            '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
            '<svg width="66" height="34" viewBox="0 0 66 34" '
            'style="position:absolute;left:16px;top:0">'
            '<line x1="2" y1="3" x2="2" y2="31" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="5" x2="6" y2="5" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="29" x2="6" y2="29" stroke="#000" stroke-width="1.4"/>'
            '<line x1="2" y1="17" x2="62" y2="17" stroke="#000" stroke-width="1"/>'
            '<rect x="16" y="17" width="22" height="6" fill="#000"/>'
            '</svg></div>')


def _example_preselect() -> str:
    """The preselects sample: the chooser as a bordered field with a caret box."""
    return ('<span style="display:inline-flex;align-items:stretch;font-size:10px">'
            '<span style="border:1px solid #000;border-right:none;padding:2px 6px;'
            'color:#555">&lt;choose form&gt;</span>'
            '<span style="border:1px solid #000;padding:2px 4px;display:flex;'
            'align-items:center">▼</span></span>')


def _example_html(key: str) -> str:
    """The example-column sample for one Show toggle, as an HTML string."""
    if key == "gridded_values":
        return _example_grid()
    if key == "charts":
        return _example_chart()
    if key == "preselects":
        return _example_preselect()
    if key == "mnemonics":  # the underlined mnemonic letters. Wrap in one element: the
        # example cell is a flex box, which would split the words into separate items and
        # trim the space between them — every branch here must return a single root element.
        return f'<span class="rtt-ex">{_underline_html("canonical mapping", ((0, 1), (10, 1)))}</span>'
    if key == "quantities":  # a generic quantity over its size: 1 above .585
        return ('<span style="display:inline-flex;flex-direction:column;align-items:center;'
                'line-height:1.05"><span>1</span><span style="font-size:9px">.585</span></span>')
    if key in ("temperament_colorization", "tuning_colorization"):  # a swatch of the wash colour
        color = _TINTS[key.split("_")[0]]  # one source of truth: the swatch == the actual wash
        return f'<span style="display:inline-block;width:36px;height:14px;background:{color}"></span>'
    if key == "tuning_ranges":  # the tuning-range I-beam (min/max generator bars)
        return ('<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
                '<rect x="6" y="2" width="2" height="16" fill="#000"/>'
                '<rect x="2" y="2" width="10" height="2" fill="#000"/>'
                '<rect x="2" y="16" width="10" height="2" fill="#000"/></svg>')
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


def _demath(ch):
    """A Mathematical Alphanumeric letter as ``(base_letter, bold, italic)``, or
    None for an ordinary character. Covers the bold, italic and bold-italic blocks
    — the maps (bold-italic), matrices/vectors (bold-upright) and the counts' plain
    italic variables; other characters pass through unstyled."""
    cp = ord(ch)
    if 0x1D400 <= cp <= 0x1D419:  # bold capitals
        return chr(ord("A") + cp - 0x1D400), True, False
    if 0x1D41A <= cp <= 0x1D433:  # bold small
        return chr(ord("a") + cp - 0x1D41A), True, False
    if 0x1D434 <= cp <= 0x1D44D:  # italic capitals
        return chr(ord("A") + cp - 0x1D434), False, True
    if 0x1D44E <= cp <= 0x1D467:  # italic small
        return chr(ord("a") + cp - 0x1D44E), False, True
    if 0x1D468 <= cp <= 0x1D481:  # bold-italic capitals
        return chr(ord("A") + cp - 0x1D468), True, True
    if 0x1D482 <= cp <= 0x1D49B:  # bold-italic small
        return chr(ord("a") + cp - 0x1D482), True, True
    return None


def _math_html(text):
    """``text`` with each Mathematical Alphanumeric letter rendered as its base
    letter in a span carrying explicit CSS weight/slant — so the UI serif draws a
    correctly bold/italic glyph rather than depending on a maths font (which font
    fallback mis-rendered). Ordinary characters pass through, HTML-escaped. Used
    for the quantity symbols and their equivalence tails."""
    out = []
    for ch in text:
        styled = _demath(ch)
        if styled is None:
            out.append(_escape(ch))
            continue
        base, bold, italic = styled
        css = (["font-weight:700"] if bold else []) + (["font-style:italic"] if italic else [])
        out.append(f'<span style="{";".join(css)}">{_escape(base)}</span>')
    return "".join(out)


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    ui.query("body").style("background:#fff")
    # trim NiceGUI's default 16px content padding to a slim margin around the whole app
    ui.query(".nicegui-content").style("padding:6px")

    editor = Editor()
    settings = show_settings.defaults()  # which parts of the grid are visible
    # the commas and "other intervals of interest" columns and the interval-vectors
    # row start folded to strips (the mockup's default view), each expandable on
    # click; interest also starts empty until the user enters intervals
    collapsed: set = {"col:commas", "col:interest", "row:vectors"}  # ids of folded rows/columns/tiles
    els: dict = {}  # entity id -> outer element (persists across renders)
    inputs: dict = {}  # mapping cell id -> q-input
    labels: dict = {}  # cell id -> the label whose text tracks state
    fracs: dict = {}  # ratio cell id -> (numerator label, denominator label)
    cents: dict = {}  # cents cell id -> (whole label, fraction label), aligned on the point
    htmls: dict = {}  # EBK svg cell id -> the ui.html holding its hand-drawn mark
    ebk_sizes: dict = {}  # EBK svg cell id -> last (w, h) it was drawn at, to redraw on resize
    chart_keys: dict = {}  # chart cell id -> last (w, h, values) drawn, to redraw on resize/data change
    range_keys: dict = {}  # range-chart cell id -> last (w, h, ranges) drawn, to redraw on resize/data change
    exprs: dict = {}  # math-expression cell id -> the ui.html holding its stacked lines
    expr_state: dict = {}  # math-expression cell id -> last (text, w) rendered, to redraw on change
    kinds: dict = {}  # entity id -> the kind its element was built for (rebuild when it changes)
    selects: dict = {}  # preselect cell id -> its q-select
    ptext_inputs: dict = {}  # editable plain-text cell id -> its q-input (mapping / comma basis)
    rangeopts: dict = {}  # range-mode cell id -> {mode: its clickable square option} (monotone / tradeoff)
    captions: dict = {}  # caption cell id -> the ui.html holding its (maybe underlined) name
    caption_html: dict = {}  # caption cell id -> last html, to rewrite on a mnemonic toggle
    math_cells: dict = {}  # symbol/count cell id -> the ui.html holding its _math_html glyph(s)
    math_rendered: dict = {}  # ...and its last html, to rewrite on an equivalences toggle / value change
    building = [False]
    last_lay = [None]  # the most recently built layout, so the master toggle can read its foldable bands
    refs: dict = {}

    def drop(eid):
        """Remove an entity's element and forget every per-id handle for it."""
        els[eid].delete()
        for d in (els, inputs, labels, fracs, cents, htmls, ebk_sizes, exprs, expr_state, kinds,
                  selects, ptext_inputs, captions, caption_html, math_cells, math_rendered,
                  chart_keys, range_keys, rangeopts):
            d.pop(eid, None)

    def on_mapping_change():
        if building[0] or not settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        matrix = [[_parse_int(inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
        if any(v is None for row in matrix for v in row):
            return
        editor.edit_mapping(matrix)
        render()

    def on_comma_change():
        # the comma basis (the mapping's dual) is edited in the interval-vectors row,
        # which is present independent of the temperament boxes
        if building[0]:
            return
        d, nc = editor.state.d, len(editor.state.comma_basis)
        if editor.pending_comma is not None:
            # the draft column rides at index nc; hand its cells to the editor, which
            # commits (and re-ranks) once they form a valid independent comma
            if any(f"cell:comma:{p}:{nc}" not in inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_comma([_parse_int(inputs[f"cell:comma:{p}:{nc}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:comma:{p}:{c}" not in inputs for c in range(nc) for p in range(d)):
            return  # the comma cells aren't currently shown (folded away)
        # the comma cells are the basis transposed (prime down the rows, comma across)
        basis = [[_parse_int(inputs[f"cell:comma:{p}:{c}"].value) for p in range(d)] for c in range(nc)]
        if any(v is None for comma in basis for v in comma):
            return
        editor.edit_comma_basis(basis)
        render()

    def on_interest_change():
        # the intervals of interest are edited as monzos in the interval-vectors row,
        # like the comma basis; read the d-tall columns and replace the set
        if building[0]:
            return
        d, mi = editor.state.d, len(editor.interest_monzos)
        if any(f"cell:interest:{p}:{i}" not in inputs for i in range(mi) for p in range(d)):
            return  # the interest cells aren't currently shown (folded away)
        monzos = [[_parse_int(inputs[f"cell:interest:{p}:{i}"].value) for p in range(d)] for i in range(mi)]
        if any(v is None for m in monzos for v in m):
            return
        editor.set_interest_monzos(monzos)
        render()

    def on_ptext_edit(cid, value):
        # the editable plain-text duals: a valid EBK string drives the grid (like
        # typing in a matrix cell); an unparseable one reddens the box and is ignored
        if building[0]:
            return
        if cid == "ptext:mapping:primes":
            ok = editor.try_edit_mapping_text(value)
        elif cid == "ptext:vectors:commas":
            ok = editor.try_edit_comma_basis_text(value)
        else:
            return
        if ok:
            ptext_inputs[cid].classes(remove="rtt-ptext-error")
            render()
        else:
            ptext_inputs[cid].classes(add="rtt-ptext-error")

    def act(action):
        action()
        render()

    def on_show_toggle(key, value):
        settings[key] = value
        render()  # the reconciling renderer animates the affected rows/columns in or out

    def on_preselect(name, value):
        # the temperament chooser loads a mapping (an undoable edit); the tuning chooser
        # sets the view scheme. A re-render echo is ignored via the building guard.
        if building[0]:
            return
        if name == "temperament":
            if value in presets.TEMPERAMENT_COMMAS:
                editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
            render()  # inert divider rows re-render too, snapping back to the live temperament
        elif name == "tuning" and value is not None:
            editor.set_tuning_scheme(value)
            render()

    def on_target_change():
        # the target chooser is a numeric limit + a TILT/OLD family; compose them into
        # a spec ("9-TILT", or just "TILT" when the limit is blank). An incomplete or
        # out-of-range limit (one that resolves to no intervals) is held without
        # disturbing the grid, mirroring how a half-typed mapping cell is ignored.
        if building[0]:
            return
        num, sel = selects["preselect:target"]
        family = sel.value or "TILT"
        spec = f"{int(num.value)}-{family}" if num.value else family
        try:
            valid = bool(service.target_interval_set(spec, service.standard_primes(editor.state.d)))
        except Exception:
            valid = False
        if not valid:
            return
        editor.set_target_spec(spec)
        render()

    def on_prescaler(value):
        # the alt.-complexity prescaler dropdown (box 𝐋): swap the complexity prescaler,
        # which re-weights and retunes. The re-render echo is ignored via the guards.
        if building[0] or value is None:
            return
        editor.set_complexity_prescaler(value)
        render()

    def on_range_mode(value):
        # which generator tuning range the ranges chart shows. A re-render echo (the radio
        # mirroring editor.range_mode) is ignored via the building/None guards, like the preselects.
        if building[0] or value is None:
            return
        editor.set_range_mode(value)
        render()

    def on_toggle(item):  # fold/unfold one row, column, or tile ("row:tuning", "tile:mapping:primes")
        collapsed.discard(item) if item in collapsed else collapsed.add(item)
        render()

    def on_toggle_all():  # the master node-corner toggle: fold the whole grid, or expand it all back
        new = spreadsheet.toggle_all_collapsed(last_lay[0], collapsed)
        collapsed.clear()
        collapsed.update(new)
        render()

    def _ratio(cb, approx):
        """A ratio rendered as a stacked fraction (with a ~ prefix when approximate)."""
        parts = _ratio_parts(cb.text)
        with ui.element("div").classes("rtt-ratio"):
            if approx:
                ui.label("~").classes("rtt-approx")
            if parts:
                with ui.element("div").classes("rtt-frac"):
                    num = ui.label(parts[0]).classes("rtt-frac-num")
                    den = ui.label(parts[1]).classes("rtt-frac-den")
                fracs[cb.id] = (num, den)
            else:
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")

    def _make_cell(cb):
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            if cb.kind == "mapping":
                inputs[cb.id] = ui.input(on_change=lambda e: on_mapping_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "commacell":
                inputs[cb.id] = ui.input(on_change=lambda e: on_comma_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "interestcell":  # an editable interval of interest monzo component
                inputs[cb.id] = ui.input(on_change=lambda e: on_interest_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "prime":  # a read-only bordered cell (the domain-prime label)
                with ui.element("div").classes("rtt-white"):
                    labels[cb.id] = ui.label(cb.text)
            elif cb.kind == "genratio":
                _ratio(cb, approx=True)
            elif cb.kind == "commaratio" and cb.pending:  # the draft comma's "?" quantity, red
                labels[cb.id] = ui.label(cb.text).classes("rtt-val rtt-pending-q")
            elif cb.kind in ("target", "commaratio"):
                _ratio(cb, approx=False)
            elif cb.kind in ("mapped", "vec"):  # plain integer values (mapped lists, monzo components)
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")
            elif cb.kind in ("count", "optimization"):  # a scalar "symbol = value" (𝑑 = 3, 𝑝 = ∞)
                math_cells[cb.id] = ui.html("").classes("rtt-count")  # content set in render()
            elif cb.kind in _EBK_SVG_KINDS:  # ⟨ ] [, top bracket, brace, monzo rule
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # drawn in render() from its px box
            elif cb.kind == "chart":
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # bar chart drawn in render()
            elif cb.kind == "rangechart":
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # I-beam ranges chart drawn in render()
            elif cb.kind == "rangemode":  # the monotone/tradeoff range selector under the ranges chart
                wrap.classes("rtt-rangemode")  # two square indicators side by side (the mockup style)
                opts = {}
                for mode in ("monotone", "tradeoff"):
                    opt = ui.element("div").classes("rtt-rangeopt")
                    with opt:
                        ui.element("span").classes("rtt-rangebox")  # the square (filled when selected)
                        ui.label(mode).classes("rtt-rangelabel")
                    opt.on("click", lambda _=None, m=mode: on_range_mode(m))
                    opts[mode] = opt
                rangeopts[cb.id] = opts
            elif cb.kind == "symbol":
                wrap.classes("rtt-symbol-cell")
                math_cells[cb.id] = ui.html("").classes("rtt-symbol")  # content set in render()
            elif cb.kind == "units":  # the per-box units line and the domain-units row/col labels
                wrap.classes("rtt-units-cell")
                math_cells[cb.id] = ui.html("").classes("rtt-units")  # content set in render()
            elif cb.kind == "caption":
                wrap.classes("rtt-caption-cell")
                captions[cb.id] = ui.html("").classes("rtt-caption")  # content set in render()
            elif cb.kind == "preselect":
                name = cb.id.split(":", 1)[1]  # temperament / tuning / target
                if name == "target":
                    # a numeric limit override beside the TILT/OLD family select, seeded
                    # from the editor's live target family + (optional) manual limit
                    with ui.element("div").classes("rtt-preselect-target"):
                        num = ui.number(value=editor.target_limit, min=2,
                                on_change=lambda e: on_target_change()) \
                            .props("dense borderless hide-bottom-space").classes("rtt-preselect-num")
                        sel = ui.select(list(presets.TARGET_SETS), value=editor.target_family,
                                on_change=lambda e: on_target_change()) \
                            .props("dense options-dense borderless hide-bottom-space popup-content-class=rtt-select-popup "
                                   f"popup-content-style=width:{cb.w - 23}px").classes("rtt-preselect")  # field = cell − square − gap
                    selects[cb.id] = (num, sel)
                elif name == "temperament":
                    # a normal dropdown: the chosen preset shows in the box; the ""
                    # sentinel ("choose temperament") shows only when none matches.
                    # Grouped by prime limit (divider rows) in the open list.
                    options = {"": "choose temperament", **presets.temperament_options()}
                    selects[cb.id] = ui.select(options, value=presets.identify(editor.state) or "",
                            on_change=lambda e: on_preselect("temperament", e.value)) \
                        .props("dense options-dense borderless hide-bottom-space popup-content-class=rtt-select-popup "
                               f"popup-content-style=width:{cb.w}px").classes("rtt-preselect")
                else:  # tuning — systematic scheme names; a control-refined scheme has no name
                    scheme = editor.tuning_scheme if isinstance(editor.tuning_scheme, str) else None
                    selects[cb.id] = ui.select(list(presets.TUNING_SCHEMES), value=scheme,
                            on_change=lambda e: on_preselect("tuning", e.value)) \
                        .props("dense options-dense borderless hide-bottom-space popup-content-class=rtt-select-popup "
                               f"popup-content-style=width:{cb.w}px").classes("rtt-preselect")
            elif cb.kind == "prescaler_select":  # the alt.-complexity prescaler dropdown (box 𝐋)
                selects[cb.id] = ui.select(list(service.PRESCALERS), value=cb.text or None,
                        on_change=lambda e: on_prescaler(e.value)) \
                    .props("dense options-dense borderless hide-bottom-space popup-content-class=rtt-select-popup "
                           f"popup-content-style=width:{cb.w}px").classes("rtt-preselect")
            elif cb.kind == "ptext":  # a read-only value: plain wrapping text, no box
                labels[cb.id] = ui.label(cb.text).classes("rtt-ptext")
            elif cb.kind == "ptextedit":  # an editable dual: typing a valid EBK string drives the grid
                ptext_inputs[cb.id] = ui.input(value=cb.text,
                        on_change=lambda e, cid=cb.id: on_ptext_edit(cid, e.value)) \
                    .props("dense borderless").classes("rtt-ptextedit")
            elif cb.kind == "ptextpending":  # comma basis mid-draft: a static two-tone box (the
                # draft is typed into the red grid cells, not here), content set in render()
                htmls[cb.id] = ui.html("").classes("rtt-ptextpending")
            elif cb.kind == "tval":
                whole, frac = _cents_parts(cb.text)
                with ui.element("div").classes("rtt-tval"):
                    w = ui.label(whole).classes("rtt-cents-int")
                    f = ui.label(f".{frac}" if frac else "").classes("rtt-cents-frac")
                cents[cb.id] = (w, f)
            elif cb.kind == "mathexpr":  # a just value's stacked closed form, fit to the cell
                exprs[cb.id] = ui.html("").classes("rtt-mathexpr")  # content drawn in render()
            elif cb.kind == "colheader":
                labels[cb.id] = ui.label(cb.text).classes("rtt-colheader")
            elif cb.kind == "rowlabel":
                labels[cb.id] = ui.label(cb.text).classes("rtt-rowlabel")
            elif cb.kind in ("rowtoggle", "coltoggle", "tiletoggle"):
                item = cb.id.split("toggle:", 1)[1]  # "row:tuning" / "col:targets" / "tile:mapping:primes"
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None, it=item: on_toggle(it))
            elif cb.kind == "alltoggle":  # the master expand/collapse-all control in the node corner
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None: on_toggle_all())
            elif cb.kind == "minus":
                # the zone spans the removable prime's header (the hover target); the
                # button hides at its top and reveals on hover, above the header so it
                # never covers the editable mapping cell below
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "plus":
                ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "basis_minus":
                # the domain − for the vertical basis: a hover zone over the highest
                # prime revealing the − to its right, so it never covers the box
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn-v")
            elif cb.kind == "comma_minus":
                # the same hover affordance as the domain −, but on the last comma
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.remove_comma), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "comma_plus":
                ui.button("+", on_click=lambda: act(editor.add_comma), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "interest_minus":
                # one per interval (every interval of interest is removable); the hover
                # zone over its header reveals a − that drops just that interval
                i = int(cb.id.split(":", 1)[1])
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda _=None, idx=i: act(lambda: editor.remove_interest(idx)), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "interest_plus":
                ui.button("+", on_click=lambda: act(editor.add_interest), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
        return wrap

    def render():
        building[0] = True
        st = editor.state
        lay = spreadsheet.build(st, settings, collapsed, editor.tuning_scheme, editor.target_spec,
                                interest=editor.interest_monzos, range_mode=editor.range_mode,
                                pending_comma=editor.pending_comma)
        last_lay[0] = lay  # the master toggle reads this layout's foldable bands on click
        board.style(f"width:{lay.width}px; height:{lay.height}px")
        seen = set()

        for ln in lay.lines:
            seen.add(ln.id)
            if ln.id not in els:
                with board:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    els[ln.id] = ui.element("div").classes(cls).props(f'data-eid="{ln.id}"')
            if ln.orientation == "v":
                els[ln.id].style(f"left:{ln.pos}px; top:{ln.start}px; height:{ln.length}px")
            else:
                els[ln.id].style(f"top:{ln.pos}px; left:{ln.start}px; width:{ln.length}px")

        for bl in lay.blocks:
            seen.add(bl.id)
            if bl.id not in els:
                # a block is a thin-bordered box (boxed, the nested tuning-ranges frame), a
                # plain grey tile (tint ""), a colorization wash's white base (tint "base"),
                # or its coloured layer (tint = group name). Fixed for the block's lifetime,
                # so the class is chosen once.
                with board:
                    cls = ("rtt-block-boxed" if bl.boxed
                           else "rtt-washbase" if bl.tint == "base"
                           else "rtt-wash" if bl.tint else "rtt-block")
                    els[bl.id] = ui.element("div").classes(cls).props(f'data-eid="{bl.id}"')
            style = f"left:{bl.x}px; top:{bl.y}px; width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:  # the coloured layer (the base draws white from CSS)
                style += f"; background:{_TINTS[bl.tint]}"
            els[bl.id].style(style)

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id in els and kinds[cb.id] != cb.kind:
                drop(cb.id)  # a cell changed kind (e.g. cents <-> math expression): rebuild it
            if cb.id not in els:
                with board:
                    els[cb.id] = _make_cell(cb)
                kinds[cb.id] = cb.kind
            els[cb.id].style(f"left:{cb.x}px; top:{cb.y}px; width:{cb.w}px; height:{cb.h}px")
            if cb.kind in _EBK_SVG_KINDS:
                # the mark is drawn 1:1 to its px box, so redraw it whenever the box
                # changes size (e.g. the brace/top bracket as the domain grows) or its
                # pending (red) state flips (a draft comma's marks committing to black)
                if ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
                    htmls[cb.id].set_content(_ebk_svg(cb))
                    ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)
            elif cb.kind == "chart":
                # redraw when the box resizes OR the underlying data changes (mapping edit)
                key = (cb.w, cb.h, cb.values)
                if chart_keys.get(cb.id) != key:
                    htmls[cb.id].set_content(_bar_chart(cb.w, cb.h, cb.values))
                    chart_keys[cb.id] = key
            elif cb.kind == "rangechart":
                # redraw when the box resizes OR the ranges/live tuning change (mapping/mode edit)
                key = (cb.w, cb.h, cb.ranges, cb.values)
                if range_keys.get(cb.id) != key:
                    htmls[cb.id].set_content(_range_chart(cb.w, cb.h, cb.ranges, cb.values))
                    range_keys[cb.id] = key
            elif cb.kind == "rangemode":  # fill the live mode's square (the other's is hollow)
                for mode, opt in rangeopts[cb.id].items():
                    (opt.classes(add="rtt-rangeopt-on") if mode == cb.text
                     else opt.classes(remove="rtt-rangeopt-on"))
            elif cb.kind == "mapping":
                inputs[cb.id].value = "" if cb.blank else str(st.mapping[cb.gen][cb.prime])
            elif cb.kind == "commacell":
                if cb.pending:  # the draft column: show the typed component (blank if None), red-outlined
                    v = editor.pending_comma[cb.prime] if editor.pending_comma is not None else None
                    inputs[cb.id].value = "" if v is None else str(v)
                else:
                    inputs[cb.id].value = "" if cb.blank else str(st.comma_basis[cb.comma][cb.prime])
                inputs[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                      remove="" if cb.pending else "rtt-pending")
            elif cb.kind == "interestcell":
                inputs[cb.id].value = cb.text  # the normalized monzo component build computed
            elif cb.kind == "ptext":  # read-only value: keep its text and shrink-to-fit font in sync
                labels[cb.id].set_text(cb.text)
                labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
            elif cb.kind == "ptextedit":  # reflect the canonical string + its shrink-to-fit font
                ptext_inputs[cb.id].value = cb.text
                ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
            elif cb.kind == "ptextpending":  # comma basis with a draft comma: two-tone, the
                # committed commas black and the draft vector red (same red as its grid cells)
                prefix, draft, suffix = service.comma_basis_pending_text(st.comma_basis, editor.pending_comma)
                htmls[cb.id].set_content(
                    f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
                htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            elif cb.kind == "mathexpr":
                # redraw (with refit fonts) whenever the expression text or cell width changes
                if expr_state.get(cb.id) != (cb.text, cb.w):
                    exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
                    expr_state[cb.id] = (cb.text, cb.w)
            elif cb.id in fracs:
                num, den = _ratio_parts(cb.text) or (cb.text, "")
                fracs[cb.id][0].set_text(num)
                fracs[cb.id][1].set_text(den)
            elif cb.id in cents:
                whole, frac = _cents_parts(cb.text)
                cents[cb.id][0].set_text(whole)
                cents[cb.id][1].set_text(f".{frac}" if frac else "")
            elif cb.kind == "preselect":
                # mirror the live selection: the temperament chooser shows the matched
                # preset (or its placeholder), the target chooser splits into limit +
                # family, the tuning chooser shows its scheme. building[0] guards echoes.
                if cb.id == "preselect:temperament":
                    selects[cb.id].value = presets.identify(editor.state) or ""
                elif cb.id == "preselect:target":
                    num, sel = selects[cb.id]
                    family = editor.target_family
                    # always show the number in use: the manual limit, or the domain default
                    limit = editor.target_limit
                    num.value = limit if limit is not None else \
                        service.default_target_limit(family, service.standard_primes(editor.state.d))
                    sel.value = family
                else:  # tuning
                    selects[cb.id].value = cb.text or None
            elif cb.kind == "prescaler_select":  # mirror the live prescaler (alt. complexity)
                selects[cb.id].value = cb.text or None
            elif cb.kind in ("symbol", "count", "optimization", "units"):  # math-styled text: symbols, their
                html = _math_html(cb.text)        # equivalence tails, the counts'/power's italic variables, units
                if math_rendered.get(cb.id) != html:  # rewrite on a toggle / value change
                    math_cells[cb.id].set_content(html)
                    math_rendered[cb.id] = html
            elif cb.kind == "caption":
                html = _underline_html(cb.text, cb.underlines)
                if caption_html.get(cb.id) != html:  # rewrite when a mnemonic toggle adds/removes underlines
                    captions[cb.id].set_content(html)
                    caption_html[cb.id] = html
            elif cb.kind in _LABEL_KINDS:
                labels[cb.id].set_text(cb.text)

        for eid in [e for e in els if e not in seen]:
            drop(eid)

        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        building[0] = False

    # the corner hamburger toggles the settings drawer, which slides the app right
    drawer_open = [False]

    def toggle_drawer():
        drawer_open[0] = not drawer_open[0]
        drawer.classes(add="rtt-drawer-open") if drawer_open[0] else drawer.classes(remove="rtt-drawer-open")

    with ui.element("div").classes("rtt-shell"):
        # the rail and the settings pane share one group so the rail's grey stretches to the
        # pane's height; the app sits to the group's right
        with ui.element("div").classes("rtt-panelgroup"):
            # the left rail: the hamburger on top, the app title rotated a quarter-turn below it.
            # The rail is left of the pane, so opening the pane never moves the title.
            with ui.element("div").classes("rtt-rail"):
                ui.button(icon="menu", on_click=toggle_drawer, color=None).props("flat dense").classes("rtt-hamburger")
                ui.label("D&D's RTT app").classes("rtt-sidetitle")
            drawer = ui.element("div").classes("rtt-drawer")
            with drawer, ui.element("div").classes("rtt-drawer-inner"):
                with ui.element("div").classes("rtt-show-head"):
                    ui.label("show").classes("rtt-show-title")
                    ui.label("example").classes("rtt-show-examplehdr")
                boxes: dict = {}  # toggle key -> checkbox, so a sub-control row can bind to its parent
                for group_name, items in show_settings.SHOW_GROUPS:
                    with ui.element("div").classes("rtt-show-group"):
                        ui.label(group_name).classes("rtt-show-grouptitle")
                        for key, label, _ in items:
                            row = ui.element("div").classes("rtt-show-row")
                            with row:
                                box = ui.checkbox(label, value=settings[key],
                                                  on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                                    .props("dense size=xs color=grey-8").classes("rtt-show-item")
                                example = ui.html(_example_html(key)).classes("rtt-ex-cell")
                                if key not in show_settings.IMPLEMENTED:
                                    box.props("disable")  # not built yet -> greyed and inert
                                    example.classes(add="rtt-ex-disabled")  # ...and its sample greys to match
                            boxes[key] = box
                            parent = show_settings.SUBCONTROLS.get(key)
                            if parent:  # indent the row under its parent and show it only while the parent is on
                                row.classes(add="rtt-show-sub")
                                row.bind_visibility_from(boxes[parent], "value")

        with ui.element("div").classes("rtt-app"):
            with ui.element("div").classes("rtt-scroll"):
                with ui.element("div").classes("rtt-outer"):
                    board = ui.element("div").classes("rtt-board")
                    # the corner cell (top-left of the grid, above the row labels) holds just
                    # the undo/redo buttons now — the app title moved to the left rail
                    with board:
                        with ui.element("div").classes("rtt-titletile"):
                            with ui.element("div").classes("rtt-tile-btns"):
                                refs["undo"] = ui.button(icon="undo", on_click=lambda: act(editor.undo), color=None) \
                                    .props("flat dense").classes("rtt-iconbtn").mark("undo")
                                refs["redo"] = ui.button(icon="redo", on_click=lambda: act(editor.redo), color=None) \
                                    .props("flat dense").classes("rtt-iconbtn").mark("redo")

    def on_key(e):
        if not (e.action.keydown and e.modifiers.ctrl):
            return
        is_z = e.key == "z" or e.key == "Z"
        if e.key == "y" or (is_z and e.modifiers.shift):
            act(editor.redo)
        elif is_z:
            act(editor.undo)

    ui.keyboard(on_key=on_key)
    render()


def _reload_excludes(worktrees: Path) -> str:
    """The uvicorn ``reload_excludes`` string: NiceGUI's default ignore globs plus the
    agent-worktrees subtree, but only when it exists. An existing directory becomes a
    watchfiles ``exclude_dir`` (every change under it is dropped by path-parent
    containment), the only way to ignore a subtree of unknown depth — uvicorn's glob
    matcher has no ``**`` and a relative dir never matches the absolute change paths. The
    path must therefore be absolute AND exist: uvicorn globs any non-dir exclude relative
    to cwd, and on Python 3.14 pathlib rejects an absolute glob pattern
    (NotImplementedError), crashing the server at startup. Absent, there's nothing to skip."""
    excludes = [".*", ".py[cod]", ".sw.*", "~*"]
    if worktrees.is_dir():
        excludes.append(str(worktrees))
    return ", ".join(excludes)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
    ui.run(title="D&D's RTT App", favicon="https://github.com/DandDsRTT.png",
           reload=True, show=False, port=port,
           uvicorn_reload_excludes=_reload_excludes(worktrees))


if __name__ in {"__main__", "__mp_main__"}:
    main()
