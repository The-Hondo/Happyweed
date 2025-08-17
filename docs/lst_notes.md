# LST Notes (initial)

- Random bounded helper: sub_56C2 — `_Random` → low16 (signed) → abs → %N → +1.
- Open classification: sub_74C6 — `10..199` counts as open; 241..249 special elsewhere.
- Generator driver: sub_879A — orchestrates carve and placements.
- Random placement: sub_89BC — samples walls w/ open neighbors, 30-wide stride.
- Jail placement: sub_8AAC — validates 2×2 wall block; neighbor-open from BR; writes 250..253.

We will expand with exact operands/branches as we transcribe.
