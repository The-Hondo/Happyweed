from dataclasses import dataclass

@dataclass(frozen=True)
class ModeFlags:
    # Original mode must mirror the 1993 binary exactly.
    original: bool = True
    extended: bool = False

# Global flags (can be swapped by launcher)
FLAGS = ModeFlags()
