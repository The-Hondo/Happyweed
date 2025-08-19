# Happyweed! — Project Roadmap

## Purpose
Pixel-perfect, 1:1 reimplementation of **Happyweed!** in Python. Tests + goldens lock behavior.

## Current state (✅ = done)
- ✅ RNG: Park–Miller + low16 *signed* abs; bounded helper.
- ✅ Seeding: closed-form `seed_from_set_level` using `pm_prev` + `INV_A`.
- ✅ Carve: LST-accurate; 135-step cap; optional tick guard.
- ✅ Placement: super, cops×3, exit, player (wall+open-neighbor).
- ✅ Jail: 2×2 (250–253), BR neighbor-open, exact write order.
- ✅ Goldens: `data/golden_levels/41/*.tsv` (HUD baked; tests mask).
- ✅ Tools: `tools/run_viewer.py` (TSV/OURS/TW, HUD toggle, status bar).
- ✅ CI: Windows/Linux, Python 3.11–3.13.

## Invariants
- 30-wide memory → 20×12 visible.
- Open tiles: 10..199 (strict).
- Wall: 200+L (1..20), 255 (21..25). Super: 80+L (1..14), 255 (15..25).
- Generator stays HUD-free; HUD is render overlay.

## Next milestones
1) Status bar module (viewer-only first).  
2) 60 Hz runtime loop (signed-16 tick semantics).  
3) Centralized tileset loader/cache.  
4) Movement/collisions, super timer, exit; CP AI/jail behavior.  
5) Expand `docs/lst_crossref.csv`.

## Testing
- Parity vs `TheWinner2.py` and TSV goldens (mask HUD).  
- CI must be green on Win+Linux before merging.

## Handoff prompt (paste in a new chat to resume)
Project: Happyweed! reimplementation (Python)  
Repo: https://github.com/The-Hondo/happyweed  
Status: RNG+seed, carve, placements, jail, goldens, viewer, CI; tests green.  
Next: status bar or 60 Hz loop.  
Constraints: 30→20×12, open=10..199, Park–Miller, closed-form seed, reproduce original bugs.
