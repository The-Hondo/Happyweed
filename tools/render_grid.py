#!/usr/bin/env python3
# Render 20x12 TSV grids to PNGs using Pillow.
# Works with tile filenames like "255.png" or "tile_255.png".

import argparse, os, csv
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = os.path.join("assets", "original", "images")

def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            rows.append([int(x) for x in line.split("\t")])
    if len(rows) != 12 or any(len(r) != 20 for r in rows):
        raise SystemExit(f"{path}: expected 12 rows of 20 columns.")
    return rows

def tile_image(tile_id, tile_size):
    # Accept multiple filename patterns/locations
    candidates = [
        os.path.join(ASSET_DIR, "tiles", f"{tile_id}.png"),
        os.path.join(ASSET_DIR, "tiles", f"tile_{tile_id}.png"),
        os.path.join(ASSET_DIR, f"{tile_id}.png"),
        os.path.join(ASSET_DIR, f"tile_{tile_id}.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            img = Image.open(p).convert("RGBA")
            if img.size != (tile_size, tile_size):
                img = img.resize((tile_size, tile_size), Image.NEAREST)
            return img
    # Fallback: colored tile with the ID text
    img = Image.new("RGBA", (tile_size, tile_size), color=_fallback_color(tile_id))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
        text = str(tile_id)
        # center text approximately
        tw, th = draw.textlength(text, font=font), 8
        draw.text(((tile_size - tw) / 2, (tile_size - th) / 2), text, fill=(0,0,0,255), font=font)
    except Exception:
        pass
    return img

def _fallback_color(tile_id):
    if tile_id >= 250:   # jail 250..253
        return (200, 200, 255, 255)
    if tile_id >= 241:   # exit 241
        return (255, 220, 0, 255)
    if tile_id >= 200:   # walls (incl. 255)
        return (80, 80, 80, 255)
    if tile_id >= 100:
        return (160, 255, 160, 255)
    if tile_id >= 80:    # leaves/super
        return (0, 220, 0, 255)
    return (220, 220, 220, 255)

def render_grid(tsv_path, out_png, tile_size=16, margin=0):
    grid = read_tsv(tsv_path)
    w, h = 20 * tile_size + 2*margin, 12 * tile_size + 2*margin
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(12):
        for x in range(20):
            tid = grid[y][x]
            img = tile_image(tid, tile_size)  # RGBA, exact size
            x0 = margin + x * tile_size
            y0 = margin + y * tile_size
            # Use a 4-item box so Pillow never complains about region size
            canvas.paste(img, (x0, y0, x0 + tile_size, y0 + tile_size), img)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    canvas.save(out_png)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, required=True, help="Level set number (e.g., 41)")
    ap.add_argument("--indir", type=str, default="data/golden_levels", help="Directory containing TSVs")
    ap.add_argument("--outdir", type=str, default="out/png", help="Where to write PNGs")
    ap.add_argument("--tile", type=int, default=16, help="Tile size in pixels")
    args = ap.parse_args()

    set_dir = os.path.join(args.indir, str(args.set))
    for lvl in range(1, 26):
        tsv = os.path.join(set_dir, f"{lvl:02d}.tsv")
        png = os.path.join(args.outdir, str(args.set), f"{lvl:02d}.png")
        render_grid(tsv, png, tile_size=args.tile)
    print(f"Wrote PNGs to {os.path.join(args.outdir, str(args.set))}")

if __name__ == "__main__":
    main()
