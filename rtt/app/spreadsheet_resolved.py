from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dims:
    d: int
    dL: int
    r: int
    rL: int
    rc: int
    k: int
    nc: int
    nh: int
    mi: int
    nu: int
    k_shown: int
    nh_shown: int
    mi_shown: int
    nc_shown: int
    nv_shown: int
    d_shown: int
    r_shown: int
    elements: tuple
    superspace_primes: tuple


@dataclass(frozen=True)
class IntervalSet:
    ratios: object
    sizes: object
    mapped: object
    vectors: object
    pending: object


@dataclass(frozen=True)
class Tuning:
    tun: object
    ss_tun: object
    from_generators: bool
    target_weights: object
    target_sizes: object
    held_sizes: object
    held_mapped: object
    comma_sizes: object
    interest_sizes: object
    optimum_target_override: object


@dataclass(frozen=True)
class Canon:
    mapping: object
    gens: object
    form_M: object
    inverse_form_M: object
    mapping_form_key: object
    comma_basis_form_key: object
    form_is_canonical: bool
    embedding_matrix: object
    mapped: object
    held_mapped: object
    interest_mapped: object
    mapped_commas: object
    mapped_detempering: object
    unchanged_mapped: object


@dataclass(frozen=True)
class Projection:
    matrix: object
    rationals: object
    superspace: object
    embedding_matrix: object
    embedding_superspace: object
    detempering: object
    targets: object
    held: object
    interest: object
    ss_matrix: object
    ss_rationals: object
    ss_embedding_matrix: object
    ss_basis: object
    ss_detempering: object
    ss_targets: object
    ss_held: object
    ss_interest: object
    ss_unchanged: object
    ss_unchanged_mapped: object


@dataclass(frozen=True)
class Ghosts:
    row: bool
    comma: bool
    new: object
    row_map: object
    row_ratio: object
    row_mapped: object
    comma_vec: object
    comma_ratio: object
    comma_mapped: object
    comma_just: float
    comma_complexity: float


@dataclass(frozen=True)
class Unchanged:
    shown: bool
    basis: object
    ratios: object
    mapped: object
    sizes: object
    complexities: object
    born: bool
    empty_comma_w: float


@dataclass(frozen=True)
class Resolved:
    dims: Dims
    targets: IntervalSet
    held: IntervalSet
    commas: IntervalSet
    interest: IntervalSet
    detempering: IntervalSet
    tuning: Tuning
    canon: Canon
    projection: Projection
    ghosts: Ghosts
    unchanged: Unchanged
    complexities: object
    col_ids: object


def _interval_set(b, ratios, sizes, mapped, vectors, pending) -> IntervalSet:
    return IntervalSet(
        ratios=getattr(b, ratios, None), sizes=getattr(b, sizes, None),
        mapped=getattr(b, mapped, None), vectors=getattr(b, vectors, None),
        pending=getattr(b, pending, None))


def from_builder(b) -> Resolved:
    return Resolved(
        dims=Dims(d=b.d, dL=b.dL, r=b.r, rL=b.rL, rc=b.rc, k=b.k, nc=b.nc, nh=b.nh,
                  mi=b.mi, nu=b.nu, k_shown=b.k_shown, nh_shown=b.nh_shown, mi_shown=b.mi_shown,
                  nc_shown=b.nc_shown, nv_shown=b.nv_shown, d_shown=b.d_shown, r_shown=b.r_shown,
                  elements=b.elements, superspace_primes=b.superspace_primes),
        targets=_interval_set(b, "targets", "target_sizes", "mapped", "target_vectors", "pending_target"),
        held=_interval_set(b, "held_ratios", "held_sizes", "held_mapped", "held", "pending_held"),
        commas=_interval_set(b, "comma_ratios", "comma_sizes", "mapped_commas", "comma_vectors", "pending"),
        interest=_interval_set(b, "interest_ratios", "interest_sizes", "interest_mapped", "interest", "pending_interest"),
        detempering=_interval_set(b, "detempering_ratios", "detempering_sizes", "detempering_mapped",
                                  "detempering_vectors", "detempering_pending"),
        tuning=Tuning(tun=b.tun, ss_tun=b._ss_tun, from_generators=b._tun_from_generators,
                      target_weights=b.target_weights, target_sizes=b.target_sizes, held_sizes=b.held_sizes,
                      held_mapped=b.held_mapped, comma_sizes=b.comma_sizes, interest_sizes=b.interest_sizes,
                      optimum_target_override=b._optimum_target_override),
        canon=Canon(mapping=b.canon_mapping, gens=b.canon_gens, form_M=b.form_M,
                    inverse_form_M=b.inverse_form_M, mapping_form_key=b.mapping_form_key,
                    comma_basis_form_key=b.comma_basis_form_key, form_is_canonical=b.form_is_canonical,
                    embedding_matrix=b.canon_embedding_matrix, mapped=b.canon_mapped,
                    held_mapped=b.canon_held_mapped, interest_mapped=b.canon_interest_mapped,
                    mapped_commas=b.canon_mapped_commas, mapped_detempering=b.canon_mapped_detempering,
                    unchanged_mapped=b.canon_unchanged_mapped),
        projection=Projection(matrix=b.projection_matrix, rationals=b.projection_rationals,
                              superspace=b.projection_superspace, embedding_matrix=b.embedding_matrix,
                              embedding_superspace=b.embedding_superspace, detempering=b.proj_detempering,
                              targets=b.proj_targets, held=b.proj_held, interest=b.proj_interest,
                              ss_matrix=b.ss_projection_matrix, ss_rationals=b.ss_projection_rationals,
                              ss_embedding_matrix=b.ss_embedding_matrix, ss_basis=b.ss_proj_basis,
                              ss_detempering=b.ss_proj_detempering, ss_targets=b.ss_proj_targets,
                              ss_held=b.ss_proj_held, ss_interest=b.ss_proj_interest,
                              ss_unchanged=b.ss_unchanged, ss_unchanged_mapped=b.ss_unchanged_mapped),
        ghosts=Ghosts(row=b.ghost_row, comma=b.ghost_comma, new=b.ghost_new, row_map=b.ghost_row_map,
                      row_ratio=b.ghost_row_ratio, row_mapped=b.ghost_row_mapped, comma_vec=b.ghost_comma_vec,
                      comma_ratio=b.ghost_comma_ratio, comma_mapped=b.ghost_comma_mapped,
                      comma_just=b.ghost_comma_just, comma_complexity=b.ghost_comma_complexity),
        unchanged=Unchanged(shown=b.show_unchanged, basis=b.unchanged_basis, ratios=b.unchanged_ratios,
                            mapped=b.unchanged_mapped, sizes=b.unchanged_sizes,
                            complexities=b.unchanged_complexities, born=b.born_u, empty_comma_w=b.empty_comma_w),
        complexities=b.complexities, col_ids=b._col_ids)
