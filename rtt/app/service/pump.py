from __future__ import annotations

import json


def comma_pump_moves(comma, just_map) -> tuple[tuple[int, ...], ...]:
    dimensionality = len(comma)
    if dimensionality == 0 or len(just_map) != dimensionality or not any(comma):
        return ()
    equave_cents = float(just_map[0])
    if equave_cents <= 0:
        return ()
    remaining = tuple(-int(x) for x in comma)
    moves: list[tuple[int, ...]] = []
    landing = 0.0
    equaves_spent = 0
    for element in range(1, dimensionality):
        direction = 1 if remaining[element] > 0 else -1
        step_cents = float(just_map[element]) * direction
        for _ in range(abs(remaining[element])):
            recentering = round(-(landing + step_cents) / equave_cents)
            move = [0] * dimensionality
            move[element] = direction
            move[0] = recentering
            moves.append(tuple(move))
            landing += step_cents + recentering * equave_cents
            equaves_spent += recentering
    closure = remaining[0] - equaves_spent
    direction = 1 if closure > 0 else -1
    for _ in range(abs(closure)):
        move = [0] * dimensionality
        move[0] = direction
        moves.append(tuple(move))
    return tuple(moves)


def pump_payload(comma, just_map, tempered_map) -> str:
    if len(tempered_map) != len(comma):
        return ""
    moves = comma_pump_moves(comma, just_map)
    if not moves:
        return ""
    just_roots: list[float] = []
    tempered_roots: list[float] = []
    just_position = 0.0
    tempered_position = 0.0
    for move in moves:
        just_roots.append(just_position)
        tempered_roots.append(tempered_position)
        just_position += sum(m * float(j) for m, j in zip(move, just_map, strict=True))
        tempered_position += sum(m * float(t) for m, t in zip(move, tempered_map, strict=True))
    return json.dumps(
        {
            "ji": just_roots,
            "t": tempered_roots,
            "dji": just_position,
            "dt": tempered_position,
            "eji": float(just_map[0]),
            "et": float(tempered_map[0]),
        },
        separators=(",", ":"),
    )
