from __future__ import annotations

import enum
from dataclasses import dataclass


class Effect(enum.Enum):
    IGNORE = enum.auto()
    RERENDER = enum.auto()
    REJECT = enum.auto()
    ACCEPT = enum.auto()


class Reason(enum.Enum):
    INVALID_PRESCALER = enum.auto()
    INVALID_WEIGHT = enum.auto()
    TARGET_WHOLE = enum.auto()
    TARGET_ODD = enum.auto()


@dataclass(frozen=True)
class Outcome:
    effect: Effect
    value: object = None
    message: str | None = None
    reason: Reason | None = None


IGNORE = Outcome(Effect.IGNORE)
RERENDER = Outcome(Effect.RERENDER)


def reject(message: str | None = None, reason: Reason | None = None) -> Outcome:
    return Outcome(Effect.REJECT, message=message, reason=reason)


def accept(value=None, message: str | None = None, reason: Reason | None = None) -> Outcome:
    return Outcome(Effect.ACCEPT, value=value, message=message, reason=reason)
