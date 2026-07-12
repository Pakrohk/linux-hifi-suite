"""Pipeline — just function composition. No classes.

Usage:
    from .pipeline import run
    from .state import detect_device, enable_nc, set_volume

    result = run(
        {"volume": 75},
        detect_device, enable_nc, set_volume,
        after=record_outcome,
    )
"""
from typing import Callable
from .state import State

Processor = Callable[[State], State]


def run(initial: State, *steps: Processor, after: Processor = None) -> State:
    """Run processors in order. Stop on first error. Run after-hook at end."""
    state = initial
    for step in steps:
        state = step(state)
        if state.get("error"):
            break
    if after:
        state = after(state)
    return state


def compose(*steps: Processor) -> Callable[[State], State]:
    """Create a reusable pipeline from processors."""
    def pipeline(initial: State) -> State:
        return run(initial, *steps)
    return pipeline
