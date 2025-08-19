# src/happyweed/timing.py
"""
Tick/timer helpers mirroring classic MacOS TickCount (unsigned 16-bit rollover
with signed 16-bit comparisons).
"""

from typing import Callable

def s16(v: int) -> int:
    """Interpret v as signed 16-bit."""
    v &= 0xFFFF
    return v - 0x10000 if (v & 0x8000) else v

def tick_over(start_tick: int, cur_tick: int, delta: int) -> bool:
    """
    Return True if cur_tick > start_tick + delta using signed-16 comparison,
    matching the carve loop condition in the listing.
    """
    # Comparison is done in signed 16-bit space:
    return s16(cur_tick) > s16(start_tick) + delta

def make_linear_provider(start: int = 0) -> Callable[[int], int]:
    """
    Deterministic tick provider for tests:
      returns (start + steps) & 0xFFFF
    i.e., +1 tick per loop iteration.
    """
    def provider(steps: int) -> int:
        return (start + steps) & 0xFFFF
    return provider
