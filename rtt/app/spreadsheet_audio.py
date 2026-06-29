from __future__ import annotations

from dataclasses import replace

from rtt.app.service.text_conventions import ebk_convention


def _canon_gen_sizes(r):
    gm, inv = r.tuning.tuning_map.generator_map, r.canon.inverse_form_M
    return tuple(
        sum(gm[k] * inv[k][j] for k in range(r.dims.rank)) for j in range(r.dims.canonical_rank)
    )


def _projected(jm, columns):
    if not columns:
        return ()
    return tuple(sum(jm[i] * col[i] for i in range(len(jm))) for col in columns)


def _attr(obj, name):
    return getattr(obj, name) if obj is not None else ()


class _Pitches:
    def __init__(self, r, geometry):
        self.ss = r.flags.superspace
        t = r.tuning
        self.jm, self.gm = t.tuning_map.just_map, t.tuning_map.generator_map
        self.cangen = _canon_gen_sizes(r)
        sst = geometry.superspace_tuning_map
        self.ss_jm = sst.just_map if sst is not None else ()
        self.ss_gm = sst.generator_map if sst is not None else ()
        sized = {
            "targets": t.target_sizes,
            "held": t.held_sizes,
            "interest": t.interest_sizes,
            "commas": t.comma_sizes,
            "unchanged": r.unchanged.sizes,
            "detempering": r.detempering.sizes,
        }
        self.just = {g: _attr(s, "just") for g, s in sized.items()}
        self.temp = {g: _attr(s, "tempered") for g, s in sized.items()}
        rationals = r.projection.rationals is not None
        self.proj = {
            g: _projected(self.jm, getattr(r.projection, g)) if rationals else ()
            for g in ("targets", "held", "interest", "detempering")
        }


_INTERVAL_KINDS = frozenset(
    {
        "prime",
        "mapped",
        "vec",
        "ratiocell",
        "commacell",
        "commaratio",
        "unchangedcell",
        "interestcell",
        "heldcell",
        "targetcell",
        "genratio",
        "elementcell",
        "elementratio",
    }
)

_IDENTITY_TILES = frozenset({("mapping", "gens"), ("superspace_mapping", "superspace_generators")})

_TILE_PREFIX = {
    "quantities": "quantities",
    "vectors": "vectors",
    "mapping": "mapped",
    "canon": "canon",
    "projection": "projection",
    "superspace_vectors": "superspace_vectors",
    "superspace_mapping": "superspace_mapped",
    "superspace_projection": "superspace_projection",
}

_JUST_ROWS = frozenset({"quantities", "vectors", "superspace_vectors"})
_TEMPERED_ROWS = frozenset({"mapping", "canon", "superspace_mapping"})
_INTERVALS_RUN_DOWN_THE_COLUMN = frozenset({"quantities"})

_BASIS_MAP = {
    "primes": "jm",
    "superspace_primes": "ss_jm",
    "gens": "gm",
    "canongens": "cangen",
    "superspace_generators": "ss_gm",
}
_MIRROR_MAP = {
    "vectors": "jm",
    "projection": "jm",
    "superspace_vectors": "ss_jm",
    "superspace_projection": "ss_jm",
    "mapping": "gm",
    "canon": "cangen",
    "superspace_mapping": "ss_gm",
}


def assign_audio(cells, r, geometry):
    p = _Pitches(r, geometry)
    bands = sorted(geometry.rows.items(), key=lambda kv: kv[1].y)
    spans = [(ck, geometry.content_x[ck], geometry.content_w[ck]) for ck in geometry.content_x]
    groups: dict = {}
    for i, cb in enumerate(cells):
        if cb.kind not in _INTERVAL_KINDS or cb.pending:
            continue
        rkey = _band_of(bands, cb.y + cb.height / 2)
        ckey = _col_of(spans, cb.x + cb.width / 2)
        if rkey is None or ckey is None or not _is_interval_tile(rkey, ckey, p.ss):
            continue
        groups.setdefault((rkey, ckey), []).append((cb.x, cb.y, i))
    for (rkey, ckey), items in groups.items():
        axis = 1 if ckey in _INTERVALS_RUN_DOWN_THE_COLUMN else 0
        keys = sorted({round(it[axis], 1) for it in items})
        index = {k: col for col, k in enumerate(keys)}
        for it in items:
            col = index[round(it[axis], 1)]
            cents = _cents(rkey, ckey, col, p)
            if cents is not None:
                cells[it[2]] = replace(
                    cells[it[2]], audio=(_tile_name(rkey, ckey), col, float(cents))
                )


def _band_of(bands, y):
    for rkey, band in bands:
        if band.y - 0.5 <= y < band.y + band.height + 0.5:
            return rkey
    return None


def _col_of(spans, x):
    found = None
    for ckey, column_x, cw in spans:
        if column_x - 0.5 <= x < column_x + cw + 0.5:
            found = ckey
    return found


def _is_interval_tile(rkey, ckey, superspace):
    if rkey == "prescaling" or (rkey, ckey) in _IDENTITY_TILES:
        return False
    if rkey == "quantities" or ckey == "quantities":
        return True
    try:
        conv = ebk_convention(rkey, ckey, superspace=superspace)
    except KeyError:
        return False
    if conv.structure == "list":
        return conv.inner_close in ("⟩", "}")
    if conv.structure == "stack":
        return conv.outer_close == "⟩"
    return False


def _tile_name(rkey, ckey):
    return f"{_TILE_PREFIX[rkey]}:{'commas' if ckey == 'unchanged' else ckey}"


def _cents(rkey, ckey, col, p):
    sizes = _basis_sizes(rkey, ckey, p)
    if sizes is None:
        source = (
            p.just
            if rkey in _JUST_ROWS
            else p.temp
            if rkey in _TEMPERED_ROWS or ckey == "commas"
            else p.proj
        )
        sizes = _interval_sizes(source, ckey)
    return sizes[col] if 0 <= col < len(sizes) else None


def _basis_sizes(rkey, ckey, p):
    name = _BASIS_MAP.get(ckey) or (_MIRROR_MAP.get(rkey) if ckey == "quantities" else None)
    return getattr(p, name) if name else None


def _interval_sizes(source, ckey):
    if ckey == "commas":
        return tuple(source.get("commas", ())) + tuple(source.get("unchanged", ()))
    return source.get(ckey, ())
