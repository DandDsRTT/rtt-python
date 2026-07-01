from __future__ import annotations

from dataclasses import replace

from rtt.app import spreadsheet_geometry_query as query
from rtt.app.service.text_conventions import ebk_convention
from rtt.app.spreadsheet_constants import VALUE_KINDS


def assign_matrix(cells, resolved, geometry):
    for i, cell_box in enumerate(cells):
        if cell_box.kind not in VALUE_KINDS:
            continue
        rkey, ckey = query.tile_of(
            geometry, cell_box.x + cell_box.width / 2, cell_box.y + cell_box.height / 2
        )
        if rkey is None or ckey is None:
            continue
        upd = {"in_grid": True}
        try:
            convention = ebk_convention(rkey, ckey, superspace=resolved.flags.superspace)
            upd["matrix"] = f"{rkey}:{ckey}"
            upd["matrix_orient"] = "col" if convention.structure == "list" else "row"
        except KeyError:
            pass
        cells[i] = replace(cell_box, **upd)


def _clean_label(text) -> str:
    return " ".join(str(text).split())


def annotate_aria(cells, geometry) -> None:
    for i, cb in enumerate(cells):
        if not cb.in_grid:
            continue
        row_key, column_key = query.tile_of(geometry, cb.x + cb.width / 2, cb.y + cb.height / 2)
        if row_key is None or column_key is None:
            continue
        row_label = _clean_label(geometry.rows[row_key].label)
        column_label = _clean_label(geometry.column_header.get(column_key, column_key))
        value = _clean_label(cb.text)
        parts = [part for part in (row_label, column_label, value) if part]
        cells[i] = replace(cb, aria=", ".join(parts))


def _canon_generator_sizes(resolved):
    generator_map, inverse_form = (
        resolved.tuning.tuning_map.generator_map,
        resolved.canonical.inverse_form_M,
    )
    return tuple(
        sum(generator_map[k] * inverse_form[k][j] for k in range(resolved.dimensions.rank))
        for j in range(resolved.dimensions.canonical_rank)
    )


def _projected(just_map, columns):
    if not columns:
        return ()
    return tuple(sum(just_map[i] * column[i] for i in range(len(just_map))) for column in columns)


def _attr(obj, name):
    return getattr(obj, name) if obj is not None else ()


class _Pitches:
    def __init__(self, resolved, geometry):
        self.superspace = resolved.flags.superspace
        tuning = resolved.tuning
        self.just_map, self.generator_map = (
            tuning.tuning_map.just_map,
            tuning.tuning_map.generator_map,
        )
        self.canon_generator_sizes = _canon_generator_sizes(resolved)
        superspace_tuning = geometry.superspace_tuning_map
        self.superspace_just_map = (
            superspace_tuning.just_map if superspace_tuning is not None else ()
        )
        self.superspace_generator_map = (
            superspace_tuning.generator_map if superspace_tuning is not None else ()
        )
        sized = {
            "targets": tuning.target_sizes,
            "held": tuning.held_sizes,
            "interest": tuning.interest_sizes,
            "commas": tuning.comma_sizes,
            "unchanged": resolved.unchanged.sizes,
            "detempering": resolved.detempering.sizes,
        }
        self.just = {group: _attr(group_sizes, "just") for group, group_sizes in sized.items()}
        self.tempered = {
            group: _attr(group_sizes, "tempered") for group, group_sizes in sized.items()
        }
        rationals = resolved.projection.rationals is not None
        self.projection = {
            group: _projected(self.just_map, getattr(resolved.projection, group))
            if rationals
            else ()
            for group in ("targets", "held", "interest", "detempering")
        }


_INTERVAL_KINDS = frozenset(
    {
        "prime",
        "mapped",
        "vector",
        "ratiocell",
        "commacell",
        "commaratio",
        "unchangedcell",
        "interestcell",
        "heldcell",
        "targetcell",
        "generator_ratio",
        "elementcell",
        "elementratio",
    }
)

_IDENTITY_TILES = frozenset(
    {("mapping", "generators"), ("superspace_mapping", "superspace_generators")}
)

_TILE_PREFIX = {
    "quantities": "quantities",
    "vectors": "vectors",
    "mapping": "mapped",
    "canonical": "canonical",
    "projection": "projection",
    "superspace_vectors": "superspace_vectors",
    "superspace_mapping": "superspace_mapped",
    "superspace_projection": "superspace_projection",
}

_JUST_ROWS = frozenset({"quantities", "vectors", "superspace_vectors"})
_TEMPERED_ROWS = frozenset({"mapping", "canonical", "superspace_mapping"})
_INTERVALS_RUN_DOWN_THE_COLUMN = frozenset({"quantities"})

_BASIS_MAP = {
    "primes": "just_map",
    "superspace_primes": "superspace_just_map",
    "generators": "generator_map",
    "canonical_generators": "canon_generator_sizes",
    "superspace_generators": "superspace_generator_map",
}
_MIRROR_MAP = {
    "vectors": "just_map",
    "projection": "just_map",
    "superspace_vectors": "superspace_just_map",
    "superspace_projection": "superspace_just_map",
    "mapping": "generator_map",
    "canonical": "canon_generator_sizes",
    "superspace_mapping": "superspace_generator_map",
}


def assign_audio(cells, resolved, geometry):
    pitches = _Pitches(resolved, geometry)
    bands = sorted(geometry.rows.items(), key=lambda kv: kv[1].y)
    spans = [
        (column_key, geometry.content_x[column_key], geometry.content_width[column_key])
        for column_key in geometry.content_x
    ]
    groups: dict = {}
    for i, cell_box in enumerate(cells):
        if cell_box.kind not in _INTERVAL_KINDS or cell_box.pending:
            continue
        row_key = _band_of(bands, cell_box.y + cell_box.height / 2)
        column_key = _col_of(spans, cell_box.x + cell_box.width / 2)
        if (
            row_key is None
            or column_key is None
            or not _is_interval_tile(row_key, column_key, pitches.superspace)
        ):
            continue
        groups.setdefault((row_key, column_key), []).append((cell_box.x, cell_box.y, i))
    for (row_key, column_key), items in groups.items():
        axis = 1 if column_key in _INTERVALS_RUN_DOWN_THE_COLUMN else 0
        keys = sorted({round(item[axis], 1) for item in items})
        index = {k: column for column, k in enumerate(keys)}
        for item in items:
            column = index[round(item[axis], 1)]
            cents = _cents(row_key, column_key, column, pitches)
            if cents is not None:
                cells[item[2]] = replace(
                    cells[item[2]], audio=(_tile_name(row_key, column_key), column, float(cents))
                )


def _band_of(bands, y):
    for row_key, band in bands:
        if band.y - 0.5 <= y < band.y + band.height + 0.5:
            return row_key
    return None


def _col_of(spans, x):
    found = None
    for column_key, column_x, column_width in spans:
        if column_x - 0.5 <= x < column_x + column_width + 0.5:
            found = column_key
    return found


def _is_interval_tile(row_key, column_key, superspace):
    if row_key == "prescaling" or (row_key, column_key) in _IDENTITY_TILES:
        return False
    if row_key == "quantities" or column_key == "quantities":
        return True
    try:
        convention = ebk_convention(row_key, column_key, superspace=superspace)
    except KeyError:
        return False
    if convention.structure == "list":
        return convention.inner_close in ("⟩", "}")
    if convention.structure == "stack":
        return convention.outer_close == "⟩"
    return False


def _tile_name(row_key, column_key):
    return f"{_TILE_PREFIX[row_key]}:{'commas' if column_key == 'unchanged' else column_key}"


def _cents(row_key, column_key, column, pitches):
    sizes = _basis_sizes(row_key, column_key, pitches)
    if sizes is None:
        source = (
            pitches.just
            if row_key in _JUST_ROWS
            else pitches.tempered
            if row_key in _TEMPERED_ROWS or column_key == "commas"
            else pitches.projection
        )
        sizes = _interval_sizes(source, column_key)
    return sizes[column] if 0 <= column < len(sizes) else None


def _basis_sizes(row_key, column_key, pitches):
    name = _BASIS_MAP.get(column_key) or (
        _MIRROR_MAP.get(row_key) if column_key == "quantities" else None
    )
    return getattr(pitches, name) if name else None


def _interval_sizes(source, column_key):
    if column_key == "commas":
        return tuple(source.get("commas", ())) + tuple(source.get("unchanged", ()))
    return source.get(column_key, ())
