from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from rtt.app import service
from rtt.app.grid_tables import (
    CAPTIONS,
    COL_LABEL_LETTERS,
    PRESCALER_LETTER,
    ROW_LABEL_LETTERS,
    SUBSCRIPT_L,
    SYMBOLS,
)
from rtt.app.spreadsheet_text import _prescaler_col_labels, _pretransform_label


@dataclass(frozen=True)
class _ShowFlags:
    captions: bool
    mnemonics: bool
    equiv: bool
    presets: bool
    counts: bool
    ptext: bool
    charts: bool
    ranges: bool
    symbols: bool
    header_symbols: bool
    units: bool
    cell_units: bool
    domain_units: bool
    temp: bool
    form: bool
    form_controls: bool
    form_tiles: bool
    tuning: bool
    optimization: bool
    weighting: bool
    alt_complexity: bool
    lbox: bool
    cbox: bool
    detempering: bool
    interest: bool
    gridded: bool
    quantities: bool
    decimals: bool
    ebk: bool
    interval_ratios: bool
    interval_vectors: bool
    math: bool


def _resolve_show_flags(settings, collapsed) -> _ShowFlags:
    captions = settings["names"]
    temp = settings["temperament_tiles"]
    tuning = settings["tuning_tiles"]
    optimization = tuning and settings["optimization"]
    weighting = tuning and settings["weighting"]
    alt_complexity = weighting and settings["alt_complexity"]
    return _ShowFlags(
        captions=captions,
        mnemonics=captions and settings["mnemonics"],
        equiv=settings["equivalences"],
        presets=settings["presets"],
        counts=settings["counts"],
        ptext=settings["plain_text_values"],
        charts=settings["charts"],
        ranges=settings["tuning_ranges"],
        symbols=settings["symbols"],
        header_symbols=settings["header_symbols"],
        units=settings["units"],
        cell_units=settings["cell_units"],
        domain_units=settings["domain_units"],
        temp=temp,
        form=settings["form"],
        form_controls=settings["form_controls"],
        form_tiles=settings["form_tiles"],
        tuning=tuning,
        optimization=optimization,
        weighting=weighting,
        alt_complexity=alt_complexity,
        lbox=(alt_complexity and settings["temperament_tiles"]
              and "col:primes" not in collapsed and "row:prescaling" not in collapsed
              and "tile:prescaling:primes" not in collapsed),
        cbox=(weighting
              and "col:targets" not in collapsed and "row:complexity" not in collapsed
              and "tile:complexity:targets" not in collapsed),
        detempering=settings["generator_detempering"],
        interest=settings["interest"],
        gridded=settings["gridded_values"],
        quantities=settings["quantities"],
        decimals=settings.get("decimals", True),
        ebk=settings.get("ebk", True),
        interval_ratios=settings["interval_ratios"],
        interval_vectors=settings["interval_vectors"],
        math=settings["math_expressions"],
    )


@dataclass(frozen=True)
class _PrescalerLabels:
    scheme_prescaler: object
    realized: object
    symbol: str
    equivalence: str
    prescaling_symbols: dict
    col_labels: dict
    row_labels: dict
    effective_captions: dict


def _resolve_prescaler_labels(state, tuning_scheme, custom_prescaler, show_equiv, show_superspace=False) -> _PrescalerLabels:
    all_interval = service.is_all_interval(tuning_scheme)
    scheme_prescaler = service.prescaler_of(tuning_scheme)
    realized = service.displayed_prescaler_name(state.mapping, tuning_scheme, custom_prescaler)
    size_factor = service.complexity_size_factor(tuning_scheme)
    prescaler_is_matrix = isinstance(
        service.complexity_prescaler(state.mapping, tuning_scheme, override=custom_prescaler)[0], (tuple, list))
    non_scaling = bool(size_factor) or prescaler_is_matrix
    is_log_prime = realized == "log-prime"
    symbol = "𝐿" if is_log_prime else "𝑋"
    if size_factor and realized:
        base = "" if realized == "identity" else PRESCALER_LETTER[realized]
        sep = "·" if base.startswith("diag") else ""
        equivalence = f" = 𝑍{sep}{base}"
    elif realized:
        equivalence = f" = {PRESCALER_LETTER[realized]}"
    else:
        equivalence = ""
    prescaling_symbols = {(r, c): symbol + s[1:] for (r, c), s in SYMBOLS.items()
                          if r == "prescaling" and s.startswith("L")}
    effective_captions = dict(CAPTIONS)
    bare_col = "ssprimes" if show_superspace else "primes"
    row_labels = dict(ROW_LABEL_LETTERS)
    row_labels.pop(("prescaling", "primes"), None)
    row_labels.pop(("prescaling", "ssprimes"), None)
    row_labels[("prescaling", bare_col)] = "𝒍" if is_log_prime else "𝒙"
    if show_superspace:
        prescaling_symbols[("prescaling", "primes")] = f"{symbol}B{SUBSCRIPT_L}ₛ"
        effective_captions[("prescaling", "primes")] = "complexity prescaled subspace basis elements"
        effective_captions[("complexity", "primes")] = "subspace basis element complexity map"
    _BASE_MATRIX_NAME = {"log-prime": "log-prime matrix", "prime": "diagonal matrix of primes", "identity": "identity matrix"}
    if show_equiv and realized:
        if size_factor:
            base = _BASE_MATRIX_NAME[realized]
            effective_captions[("prescaling", bare_col)] += (
                " = size-sensitizing matrix" + ("" if realized == "identity" else f" × {base}"))
        elif is_log_prime:
            effective_captions[("prescaling", bare_col)] += f" = {_BASE_MATRIX_NAME['log-prime']}"
    if non_scaling:
        effective_captions = {k: _pretransform_label(v) for k, v in effective_captions.items()}
    return _PrescalerLabels(
        scheme_prescaler=scheme_prescaler, realized=realized, symbol=symbol, equivalence=equivalence,
        prescaling_symbols=prescaling_symbols,
        col_labels={**COL_LABEL_LETTERS, **_prescaler_col_labels(symbol, show_equiv, all_interval, show_superspace)},
        row_labels=row_labels, effective_captions=effective_captions,
    )


class _VecGrid(NamedTuple):
    group: str
    count: int
    id_fn: Callable[[str, int], str]
    left_fn: Callable[[int], float]
    committed_kind: str
    pending_kind: str
    data: object
    pending: object
    sizes: object


class _QtyList(NamedTuple):
    group: str
    singular: str
    count: int
    left_fn: Callable[[int], float]
    ratios: object
    sizes: object
    pending: object
    kind: str
    minus_gate: bool


class _MappedTile(NamedTuple):
    prefix: str
    group: str
    count: int
    left_fn: Callable[[int], float]
    data: object
    pending: object
    sizes: object = None


@dataclass
class RowBand:
    y: float
    h: float
    label: str
    collapsible: bool
    tile_h: float
    tile_top: float
    frame: float
    sym: float
    cap: float
    units: float
    ptext: float
    pre: float
    schemebtn: float
    nsub: int
    chart_top: float | None = None
    int_handle_top: float | None = None
    matlabel_top: float | None = None
