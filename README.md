# Happyweed! — Exact Reimplementation (Python)

This repo aims to reproduce the 1993 **Happyweed!** game *exactly* — logic, RNG, timing, tiles, and original bugs — and then layer an **Extended** mode for optional enhancements.

[![CI](https://github.com/The-Hondo/Happyweed/actions/workflows/ci.yml/badge.svg)](https://github.com/The-Hondo/Happyweed/actions)

## Quick start
```bash
pip install -e .
pytest -q
# viewer (optional extras)
pip install -e .[viewer]
python tools/run_viewer.py --set 41 --source tsv --tile 16