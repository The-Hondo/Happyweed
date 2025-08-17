# Architecture

- `rng.py`: Park–Miller RNG, low16 signed rule, E mapping for level reuse.
- `grid.py`: 30-wide backing buffer; 20×12 visible extraction.
- `mapgen/generator.py`: Carve + placement driver (to be refined to exact .lst).
- `tiles.py`: Tile IDs + level-dependent wall/superdrug.
- `tools/hwtool.py`: CLI for grids/goldens.
