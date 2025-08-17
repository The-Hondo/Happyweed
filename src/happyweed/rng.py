from dataclasses import dataclass

A = 16807
M = 0x7FFFFFFF  # 2^31-1

def pm_next(state: int) -> int:
    """Advance Park–Miller state once, returning the new 31-bit state."""
    return (state * A) % M

def low16_signed_abs(x32: int) -> int:
    """Take low 16 bits, interpret as signed, return abs(value)."""
    w = x32 & 0xFFFF
    if w & 0x8000:
        w = -((~w + 1) & 0xFFFF)  # two's complement → negative
    return abs(w)

@dataclass
class PMRandom:
    state: int

    def next32(self) -> int:
        self.state = pm_next(self.state)
        return self.state

    def bounded(self, n: int) -> int:
        """Game helper: (abs(low16(signed)) % n) + 1, for n>0."""
        assert n > 0
        w = low16_signed_abs(self.next32())
        return (w % n) + 1

def seed_from_E(base_seed: int, E: int) -> int:
    """Derive the state after E advances from base_seed (exclusive).""" 
    s = base_seed
    for _ in range(E):
        s = pm_next(s)
    return s

def E_from_set_level(level_set: int, level: int) -> int:
    # Linear reuse index:
    # E = (set-1) + 8*(level-1)
    return (level_set - 1) + 8*(level - 1)
