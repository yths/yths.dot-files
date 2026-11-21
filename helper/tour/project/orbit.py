"""Trace a body around a star, one step at a time."""

import math
from typing import NamedTuple

GRAVITY = 39.478  # AU^3 / (solar mass * year^2)


class State(NamedTuple):
    x: float
    y: float
    vx: float
    vy: float


def step(state: State, dt: float) -> State:
    """Advance one leapfrog step: kick, drift, kick."""
    ax, ay = acceleration(state.x, state.y)
    vx, vy = state.vx + ax * dt / 2, state.vy + ay * dt / 2
    x, y = state.x + vx * dt, state.y + vy * dt
    ax, ay = acceleration(x, y)
    return State(x, y, vx + ax * dt / 2, vy + ay * dt / 2)


def acceleration(x: float, y: float) -> tuple[float, float]:
    radius = math.hypot(x, y)
    return -GRAVITY * x / radius**3, -GRAVITY * y / radius**3


def energy(state: State) -> float:
    """Specific orbital energy; constant along an orbit, so a drift is an error."""
    kinetic = (state.vx**2 + state.vy**2) / 2
    return kinetic - GRAVITY / math.hypot(state.x, state.y)


def trace(state: State, years: float, steps: int) -> list[State]:
    path = [state]
    for _ in range(steps):
        path.append(step(path[-1], years / steps))
    return path


if __name__ == "__main__":
    start = State(1.0, 0.0, 0.0, 2 * math.pi)
    path = trace(start, years=1.0, steps=365)
    print(f"closed to {math.hypot(path[-1].x - 1, path[-1].y):.2e} AU")
    print(f"energy drift {energy(path[-1]) - energy(start):+.2e}")
