from dataclasses import dataclass

A = 16807
M = 0x7FFFFFFF  # 2^31-1
# NEW: modular inverse of A (so we can step backward exactly)
INV_A = 1407677000  # because (A * INV_A) % M == 1

def pm_next(state: int) -> int:
    return (state * A) % M

# NEW: step backward one state
def pm_prev(state: int) -> int:
    return (state * INV_A) % M

def low16_signed_abs(x32: int) -> int:
    w = x32 & 0xFFFF
    if w & 0x8000:
        w = -((~w + 1) & 0xFFFF)
    return abs(w)

@dataclass
class PMRandom:
    state: int
    def next32(self) -> int:
        self.state = pm_next(self.state)
        return self.state
    def bounded(self, n: int) -> int:
        assert n > 0
        w = low16_signed_abs(self.next32())
        return (w % n) + 1

# (Keep this older helper if you like — it’s not used after we switch)
def seed_from_E(base_seed: int, E: int) -> int:
    s = base_seed
    for _ in range(E):
        s = pm_next(s)
    return s

# NEW: exact closed-form seed used by TheWinner2 / the original binary
def seed_from_set_level(level_set: int, level: int) -> int:
    """
    Return the pre-call Park–Miller seed for (set, level).
    K = set + 8*(level-1)
    pre-call seed0 = pm_prev( (A*K + 0x0FCDD36) % M )
    """
    K = level_set + 8 * (level - 1)
    s1 = (A * K + 0x0FCDD36) % M
    return pm_prev(s1)

def E_from_set_level(level_set: int, level: int) -> int:
    # You can keep this invariant helper if it’s useful elsewhere
    return (level_set - 1) + 8*(level - 1)
