from __future__ import annotations

from rtt.app.service import outcome
from rtt.app.service.outcome import Outcome, Reason
from rtt.library.domain_basis import (
    filter_target_intervals_for_nonstandard_domain_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.math_utils import quotient_to_pcv
from rtt.library.target_intervals import (
    default_old_limit,
    default_tilt_limit,
    process_old,
    process_tilt,
)


def target_interval_set(spec: str, domain_basis) -> tuple[str, ...]:
    domain = tuple(domain_basis)
    quotients = process_old(spec, domain) if "OLD" in spec else process_tilt(spec, domain)
    if is_standard_prime_limit_domain_basis(domain):
        quotients = tuple(q for q in quotients if len(quotient_to_pcv(q)) <= len(domain))
    else:
        quotients = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain)
    return tuple(f"{q.numerator}/{q.denominator}" for q in quotients)


def default_target_limit(family: str, domain_basis) -> int:
    domain = tuple(domain_basis)
    return default_old_limit(domain) if "OLD" in family else default_tilt_limit(domain)


def target_limit_problem(family: str | None, limit_value) -> str | None:
    no_manual_limit = not limit_value
    if no_manual_limit:
        return None
    try:
        number = float(limit_value)
    except (TypeError, ValueError):
        return "whole"
    if number != int(number):
        return "whole"
    if "OLD" in (family or "") and int(number) % 2 == 0:
        return "odd"
    return None


def target_spec(family: str, limit_value) -> str:
    text = (str(limit_value) if limit_value is not None else "").strip()
    if not text:
        return family
    try:
        return f"{int(float(text))}-{family}"
    except ValueError:
        return family


def resolve_target_limit(family: str | None, limit_value, domain_basis) -> Outcome:
    family = family or "TILT"
    problem = target_limit_problem(family, limit_value)
    if problem == "whole":
        return outcome.reject(reason=Reason.TARGET_WHOLE)
    spec = target_spec(family, limit_value)
    try:
        valid = bool(target_interval_set(spec, domain_basis))
    except Exception:
        valid = False
    if not valid:
        return outcome.IGNORE
    if problem == "odd":
        return outcome.accept(spec, reason=Reason.TARGET_ODD)
    return outcome.accept(spec)
