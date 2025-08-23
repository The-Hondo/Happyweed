# src/happyweed/engine/timing.py
# Centralized timing model so parity is adjustable without touching the runner.
# This lets us mirror the original Mac timing feel while staying platform-neutral.

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimingModel:
    # Durations in engine ticks (runner drives ~60 ticks/sec)
    prestart_ticks: int = 120   # ≈2.0s @60Hz — update from LST once confirmed
    death_pause_ticks: int = 60 # ≈1.0s @60Hz — update from LST once confirmed
    sprite_blink_period: int = 8  # player 60↔61 while paused; update from LST

    # Movement periods (ticks per tile)
    player_period: int = 8
    cop_period: int = 10
    # Overridden while super is active (if the original speeds differ)
    player_period_super: int = 8   # placeholder: same unless LST shows otherwise
    cop_period_super: int = 10     # placeholder: cops are frozen by rules, not speed

    # Global scalar to stretch/shrink time uniformly (menu speed slider)
    time_scalar_num: int = 1
    time_scalar_den: int = 1

    def scaled(self) -> "TimingModel":
        """Return a copy with all durations/periods scaled by time_scalar."""
        s = TimingModel(
            prestart_ticks=max(1, (self.prestart_ticks * self.time_scalar_num) // self.time_scalar_den),
            death_pause_ticks=max(1, (self.death_pause_ticks * self.time_scalar_num) // self.time_scalar_den),
            sprite_blink_period=max(1, (self.sprite_blink_period * self.time_scalar_num) // self.time_scalar_den),
            player_period=max(1, (self.player_period * self.time_scalar_num) // self.time_scalar_den),
            cop_period=max(1, (self.cop_period * self.time_scalar_num) // self.time_scalar_den),
            player_period_super=max(1, (self.player_period_super * self.time_scalar_num) // self.time_scalar_den),
            cop_period_super=max(1, (self.cop_period_super * self.time_scalar_num) // self.time_scalar_den),
            time_scalar_num=1,
            time_scalar_den=1,
        )
        return s


# Menu speed helpers (placeholder mapping; replace with exact LST mapping later)
# Index 0..4 where 2 is "normal"; chosen so scalar is rational and deterministic.
MENU_SPEED_TO_SCALAR = {
    0: (6, 5),   # 1.2x slower
    1: (11, 10), # 1.1x slower
    2: (1, 1),   # normal
    3: (9, 10),  # 1.1x faster
    4: (4, 5),   # 1.25x faster
}


def timing_for(menu_speed_index: int = 2) -> TimingModel:
    num, den = MENU_SPEED_TO_SCALAR.get(menu_speed_index, (1, 1))
    base = TimingModel()
    base.time_scalar_num = den  # NOTE: smaller periods when speed increases -> invert scalar for periods
    base.time_scalar_den = num
    return base.scaled()
