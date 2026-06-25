from __future__ import annotations

from fractions import Fraction

from rtt.app import service
from rtt.app.spreadsheet_text import _log_operand


class _ClosedFormMixin:
    def closed_form_operand(self, key, group, i, value=None):
        _r = self.resolved
        if key == "just":
            ratio = self.group_ratio[group][i]
            return _log_operand(ratio) if ratio is not None else None
        if group == "commas" and key == "retune" and i < _r.dims.nc:
            recip = 1 / Fraction(_r.commas.ratios[i])
            return _log_operand(f"{recip.numerator}/{recip.denominator}")
        if key in ("tuning", "retune") and value is not None:
            if group in ("ssprimes", "ssgens"):
                return self._ss_closed_form_operand(key, group, i, value)
            closed_form = self._closed_form()
            vector = self._tempered_vector(group, i) if closed_form is not None else None
            if vector is not None:
                return (
                    closed_form.tempered_operand(vector, value)
                    if key == "tuning"
                    else closed_form.retune_operand(vector, value)
                )
        return None

    def _ss_closed_form_operand(self, key, group, i, value):
        ss = self._ss_closed_form()
        if ss is None:
            return None
        if group == "ssgens":
            return ss.generator_operand(i, value) if key == "tuning" else None
        vector = tuple(1 if k == i else 0 for k in range(len(ss.primes)))
        return (
            ss.tempered_operand(vector, value)
            if key == "tuning"
            else ss.retune_operand(vector, value)
        )

    def _closed_form(self):
        _r = self.resolved
        if not hasattr(self, "_closed_form_cache"):
            self._closed_form_cache = (
                None
                if not _r.flags.math or _r.tuning.from_generators
                else service.closed_form_tuning(
                    self.state.mapping,
                    self.tuning_scheme,
                    _r.dims.elements,
                    self.nonprime_approach,
                    held=_r.held.ratios,
                    prescaler_override=self.custom_prescaler,
                    targets=_r.tuning.optimum_target_override,
                    weights_override=self.custom_weights,
                )
            )
        return self._closed_form_cache

    def _ss_closed_form(self):
        _r = self.resolved
        if not hasattr(self, "_ss_closed_form_cache"):
            self._ss_closed_form_cache = (
                service.closed_form_superspace_tuning(self.state, self.tuning_scheme)
                if _r.flags.math and _r.flags.superspace
                else None
            )
        return self._ss_closed_form_cache

    def _tempered_vector(self, group, i):
        _r = self.resolved
        if group == "primes":
            return tuple(1 if k == i else 0 for k in range(_r.dims.d))
        if group == "commas":
            return self._comma_tempered_vector(i)
        seqs = {
            "targets": _r.targets.vectors,
            "interest": _r.interest.vectors,
            "held": _r.held.vectors,
            "detempering": _r.detempering.vectors,
        }
        seq = seqs.get(group)
        if seq is None:
            return None
        return seq[i] if i < len(seq) else None

    def _comma_tempered_vector(self, i):
        _r = self.resolved
        if i < _r.dims.nc:
            return self.state.comma_basis[i]
        j = i - _r.dims.nc
        return _r.unchanged.basis[j] if _r.unchanged.basis and j < len(_r.unchanged.basis) else None
