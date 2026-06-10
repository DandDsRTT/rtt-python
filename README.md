# D&D's RTT App

A [Regular Temperament Theory](https://en.xen.wiki/w/Regular_temperament) engine for
microtonal music, with a live web front end. Define a temperament by its mapping or the
commas it tempers out, and the app derives the rest — canonical form, generators, optimal
tunings under dozens of schemes, and the damage each does to your target intervals — and
lays it all out as an interactive spreadsheet you can edit cell by cell.

**▶ Try it live at [rtt-python.onrender.com](https://rtt-python.onrender.com)** — no
install required. It's hosted on Render's free tier, which spins down after about 15
minutes idle, so the first load after a quiet spell can take up to a minute to wake.

It is the working companion to *[Dave Keenan & Douglas Blumeyer's guide to
RTT](https://en.xen.wiki/w/Dave_Keenan_%26_Douglas_Blumeyer%27s_guide_to_RTT)*; the
[`guide/`](guide/) folder mirrors that text, and the app is built to match its notation and
conventions chapter by chapter.

![The default view the app renders](RTT%20design%20mockup%20-%20default.png)

> The image above is the design mockup the default view targets. A fuller, every-toggle-on
> layout lives in [`RTT design mockup - maximized.png`](RTT%20design%20mockup%20-%20maximized.png).

## What is Regular Temperament Theory?

Just intonation tunes intervals as exact whole-number frequency ratios (a perfect fifth is
3/2, a major third 5/4). A **regular temperament** systematically approximates a whole
lattice of those ratios using a *small* set of tunable **generators**, by deliberately
tempering out chosen **commas** (tiny ratios collapsed to a unison — e.g. meantone tempers
out 81/80, so four fifths land on a major third). RTT is the linear algebra that makes this
precise: a temperament is a matrix, intervals and tunings are vectors and maps over it, and
"best tuning" becomes a well-posed optimization. This project implements that algebra and
puts a visual editor on top of it.

## Quick start

The app is hosted live at **[rtt-python.onrender.com](https://rtt-python.onrender.com)** —
no install needed. To run it locally you'll need **Python 3.10+**:

```bash
git clone git@github.com:DandDsRTT/rtt-python.git
cd rtt-python

python -m venv .venv                  # optional but recommended
source .venv/bin/activate             # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

`python app.py` serves the UI on port **8137** by default; open
<http://localhost:8137>. Pass a port to use another: `python app.py 8200`.

## Using the library directly

The `rtt.library` package is a standalone RTT math library — the web app (`rtt.app`) is just one consumer of it.
Temperaments are read and written in **extended bra–ket notation** (EBK): maps are written
`⟨…]` and vectors `[…⟩`.

```python
from rtt.library.parsing import parse_temperament_data
from rtt.library.canonicalization import canonical_form
from rtt.library.dual import dual
from rtt.library.tuning import optimize_generator_tuning_map

t = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")      # 5-limit meantone, as a mapping

canonical_form(t).matrix        # ((1, 0, -4), (0, 1, 4))  — defactored mapping
dual(t).matrix                  # ((4, -4, 1),)            — the comma it tempers: 81/80
optimize_generator_tuning_map(t, "minimax-S")   # (1201.70, 697.56) ¢ — octave & fifth
```

Tuning schemes are named **systematically** (`minimax-S`, `minimax-copfr-C`, …) rather than
by the historical eponyms; the systematic name encodes the optimization power, the damage
weighting, and the complexity used.

## Project layout

```
app.py            # entry point: python app.py [port]
rtt/library/      # the RTT math library (pure, framework-free)
rtt/app/          # the NiceGUI front end
guide/            # the D&D guide to RTT, mirrored for reference
tests/library/    # library tests (unit/)
tests/app/        # web-app tests (unit/ and integration/)
```

### The math library (`rtt/library/`)

| Module | Responsibility |
| --- | --- |
| `temperament.py` | The core `Temperament` value type — a matrix, its variance (`⟨…]` vs `[…⟩`), and its domain basis |
| `canonicalization.py` | Canonical (defactored, Hermite) form of a mapping or comma basis |
| `dual.py` | Mapping ↔ comma-basis duality |
| `exterior_algebra.py` | Multivectors / wedge products (the wedgie invariant) |
| `tuning.py` | Optimal generator tuning maps for a given scheme |
| `tuning_solvers.py` | The temperament-agnostic Lₚ-norm / linear-program optimum solvers |
| `tuning_scheme_names.py` | Parsing systematic (and historical) scheme names into traits |
| `tuning_ranges.py` | Diamond-monotone and diamond-tradeoff generator tuning *ranges* |
| `target_intervals.py` | Target interval sets the tuning is optimized against |
| `domain_basis.py`, `change_basis.py` | Nonstandard (non-prime-limit) domain bases |
| `merging.py`, `addition.py` | Combining temperaments (map/comma merging; temperament addition) |
| `generator_detempering.py`, `generator_embedding.py` | Generators ↔ tempering projections |
| `parsing.py`, `formatting.py` | EBK input/output |
| `math_utils.py`, `matrix_utils.py`, `dimensions.py`, … | Shared numeric helpers |

### The web front end (`rtt/app/`)

The UI imports the library's public API directly — there is no HTTP layer — and funnels every
library call through a single seam, `service.py`.

| Module | Responsibility |
| --- | --- |
| `app.py` | NiceGUI app; a persistent, *reconciling* renderer so rows/columns animate across edits |
| `service.py` | The sole seam to the library — passes plain tuples/ints/strings, never library types |
| `editor.py` | Framework-free document view-model holding all editable state + undo/redo |
| `spreadsheet.py`, `grid_tables.py`, `layout.py` | The spreadsheet coordinate model (which quantities exist, and where they sit) |
| `marks.py` | The EBK bracket/brace SVG glyphs that frame each value matrix |
| `settings.py` | The "Show" toggles controlling which parts of the grid are visible |
| `presets.py` | Curated preset menus for the few things you actually choose |
| `tooltips.py` | The single home for every hover string in the app |

## Running the tests

```bash
pip install -r requirements.txt   # includes pytest + pytest-asyncio
python -m pytest
```

The suite (~2,000 tests) covers both the math library and the web layer. The web tests —
including the "integration" suite — drive the editor and renderer **entirely in-process**
(no server, no port, no network), so the full run needs nothing beyond `pytest`.

## Credits

By **Dave Keenan & Douglas Blumeyer**. The theory, notation, and conventions come from their
[guide to RTT](https://en.xen.wiki/w/Dave_Keenan_%26_Douglas_Blumeyer%27s_guide_to_RTT) on
the Xenharmonic Wiki; this repository is the Python port of their reference implementation.

## License

[MIT](LICENSE) © Dave Keenan and Douglas Blumeyer.
