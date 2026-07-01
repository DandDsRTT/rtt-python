from __future__ import annotations

from typing import TYPE_CHECKING

from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app.editor_state import (
    INITIAL_COLLAPSED,
    _Doc,
    prescaler_is_solvable,
    weights_are_solvable,
)

if TYPE_CHECKING:
    from rtt.app.editor_document import Document


def _prescaler_to_json(p):
    if p is None:
        return None
    return [list(row) for row in p] if isinstance(p[0], (tuple, list)) else list(p)


def _prescaler_from_json(p):
    if p is None:
        return None
    if p and isinstance(p[0], (list, tuple)):
        prescaler = tuple(tuple(float(x) for x in row) for row in p)
    else:
        prescaler = tuple(float(x) for x in p)
    return prescaler if prescaler_is_solvable(prescaler) else None


def _weights_to_json(w):
    return list(w) if w is not None else None


def _weights_from_json(w):
    if w is None:
        return None
    weights = tuple(float(x) for x in w)
    return weights if weights_are_solvable(weights) else None


def serialize(document: Document) -> dict:
    return {
        "mapping_ebk": service.mapping_ebk(document.state),
        "tuning_scheme": service.scheme_to_json(document.tuning_scheme),
        "target_family": document.target_family,
        "target_limit": document.target_limit,
        "interest_vectors": [list(m) for m in document.interest_vectors],
        "held_vectors": [list(m) for m in document.held_vectors],
        "range_mode": document.range_mode,
        "generator_tuning": list(document.generator_tuning)
        if document.generator_tuning is not None
        else None,
        "manual_tuning": document.manual_tuning,
        "custom_prescaler": _prescaler_to_json(document.custom_prescaler),
        "custom_weights": _weights_to_json(document.custom_weights),
        "target_override": list(document.target_override)
        if document.target_override is not None
        else None,
        "projection_basis": list(document.projection_basis),
        "settings": dict(document.settings),
        "collapsed": sorted(document.collapsed),
    }


_MAX_RANK = 128
_MAX_DIMENSIONALITY = 128
_MAX_COLLECTION = 512


def _within_limits(state, data: dict) -> bool:
    if state.rank > _MAX_RANK or state.dimensionality > _MAX_DIMENSIONALITY:
        return False
    for key in ("interest_vectors", "held_vectors"):
        vectors = data.get(key) or ()
        if len(vectors) > _MAX_COLLECTION or any(
            len(vector) > _MAX_DIMENSIONALITY for vector in vectors
        ):
            return False
    for key in ("target_override", "projection_basis"):
        if len(data.get(key) or ()) > _MAX_COLLECTION:
            return False
    return True


def load(data: dict) -> _Doc | None:
    state = service.parse_mapping_state(data.get("mapping_ebk", ""))
    if state is None:
        return None
    if not _within_limits(state, data):
        return None
    return _Doc(
        state=state,
        tuning_scheme=service.scheme_from_json(
            data.get("tuning_scheme", service.DEFAULT_DOCUMENT_SCHEME)
        ),
        target_family=data.get("target_family", service.DEFAULT_TARGET_SPEC),
        target_limit=data.get("target_limit"),
        interest_vectors=tuple(tuple(int(x) for x in m) for m in data.get("interest_vectors", ())),
        held_vectors=tuple(tuple(int(x) for x in m) for m in data.get("held_vectors", ())),
        range_mode=data.get("range_mode", "monotone"),
        generator_tuning=tuple(data["generator_tuning"])
        if data.get("generator_tuning") is not None and data.get("manual_tuning")
        else None,
        manual_tuning=bool(data.get("manual_tuning") and data.get("generator_tuning") is not None),
        custom_prescaler=_prescaler_from_json(data.get("custom_prescaler")),
        custom_weights=_weights_from_json(data.get("custom_weights")),
        target_override=tuple(data["target_override"])
        if data.get("target_override") is not None
        else None,
        projection_basis=tuple(data.get("projection_basis", ()) or ()),
        settings=tuple(sorted(show_settings.from_persisted(data.get("settings", {})).items())),
        collapsed=frozenset(data.get("collapsed", INITIAL_COLLAPSED)),
        preferred_form=(),
    )
