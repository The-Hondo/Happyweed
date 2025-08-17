#!/usr/bin/env python3
import argparse, csv, os
from happyweed.mapgen.generator import generate_grid

def write_csv(mat, path, include_header=False):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        if include_header:
            w.writerow(list(range(len(mat[0]))))
        for r in mat:
            w.writerow(r)

def cmd_emit(args):
    mat = generate_grid(args.set, args.level)
    write_csv(mat, args.out, include_header=args.header)
    print(f"Wrote {args.out}")

def cmd_golden(args):
    base = os.path.join(args.outdir, str(args.set))
    os.makedirs(base, exist_ok=True)
    for lvl in range(1, 26):
        mat = generate_grid(args.set, lvl)
        path = os.path.join(base, f"{lvl:02d}.csv")
        write_csv(mat, path, include_header=False)
    print(f"Wrote golden pack to {base}")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('emit')
    p1.add_argument('--set', type=int, required=True)
    p1.add_argument('--level', type=int, required=True)
    p1.add_argument('--out', type=str, required=True)
    p1.add_argument('--header', action='store_true')
    p1.set_defaults(func=cmd_emit)
    p2 = sub.add_parser('golden')
    p2.add_argument('--set', type=int, required=True)
    p2.add_argument('--outdir', type=str, required=True)
    p2.set_defaults(func=cmd_golden)
    args = p.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
