#!/usr/bin/env python3
"""Look at what is actually standing somewhere, without opening the game.

Prints a plan (the top block of each column) and, with --section, a vertical
slice. Blocks are grouped into a handful of symbols, which is enough to tell a
tower from a hole and a roof from a floor.

Usage:  look.py --centre X Z [--radius 24] [--section Z] [--legend]
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_survey import read_chunks, section_lookup

GROUPS = [
    (" ", ("air", "cave_air", "void_air")),
    ("~", ("water", "bubble_column", "ice")),
    ("&", ("lava",)),
    ("T", ("leaves", "log", "wood", "bamboo", "vine", "sapling", "moss")),
    ("\"", ("grass", "fern", "flower", "petals", "bush", "wildflowers",
            "leaf_litter", "seagrass", "kelp", "lily", "dead_bush", "sprouts")),
    (".", ("grass_block", "dirt", "podzol", "mud", "rooted", "farmland",
           "dirt_path", "coarse", "mycelium")),
    (",", ("sand", "gravel", "clay", "sandstone")),
    ("#", ("stone", "cobble", "andesite", "granite", "diorite", "deepslate",
           "tuff", "basalt", "blackstone", "calcite", "brick", "quartz",
           "concrete", "terracotta", "prismarine", "purpur")),
    ("=", ("planks", "stairs", "slab", "fence", "door", "trapdoor", "sign",
           "barrel", "chest", "ladder", "scaffold", "bookshelf", "loom",
           "table", "furnace", "anvil", "campfire", "hay", "wool", "carpet")),
    ("o", ("lantern", "torch", "glowstone", "sea_lantern", "candle", "fire",
           "shroomlight", "froglight", "beacon")),
    ("+", ("glass", "iron_bars", "chain", "copper", "iron_block", "amethyst")),
]


def symbol(name):
    for ch, keys in GROUPS:
        if name in keys or any(k in name for k in keys):
            return ch
    return "?"


def read_area(cx, cz, radius, lo, hi):
    """{(x, z): {y: block}} over the box, from the saved chunks."""
    out = {}
    for rx, rz in {(x // 512, z // 512)
                   for x in (cx - radius, cx + radius)
                   for z in (cz - radius, cz + radius)}:
        for chx, chz, nbt in read_chunks(rx, rz):
            if (abs(chx * 16 + 8 - cx) > radius + 16
                    or abs(chz * 16 + 8 - cz) > radius + 16):
                continue
            secs = {s["Y"]: s for s in (nbt.get("sections") or [])}
            for sy, sec in secs.items():
                if not (lo - 16 <= sy * 16 <= hi):
                    continue
                look = section_lookup(sec)
                if not look:
                    continue
                pal, idx = look
                for y in range(16):
                    yy = sy * 16 + y
                    if not lo <= yy <= hi:
                        continue
                    for i in range(256):
                        x, z = chx * 16 + i % 16, chz * 16 + i // 16
                        if abs(x - cx) > radius or abs(z - cz) > radius:
                            continue
                        n = pal[idx(y * 256 + (i // 16) * 16 + (i % 16))]
                        if n != "air":
                            out.setdefault((x, z), {})[yy] = n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=int, required=True, metavar=("X", "Z"))
    ap.add_argument("--radius", type=int, default=24)
    ap.add_argument("--range", nargs=2, type=int, default=(40, 200), metavar=("LO", "HI"))
    ap.add_argument("--section", type=int, help="print a vertical slice at this z")
    ap.add_argument("--legend", action="store_true")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    cx, cz = a.centre
    lo, hi = a.range
    cols = read_area(cx, cz, a.radius, lo, hi)
    if a.legend:
        for ch, keys in GROUPS:
            print(f"  {ch}  {', '.join(keys[:5])}")

    print(f"\nplan ({cx}, {cz}) +-{a.radius}, north up, west left"
          f"   [cislo = vyska nejvyssiho bloku - {lo}]")
    header = "     " + "".join(str(abs(x) // 10 % 10) if x % 5 == 0 else " "
                               for x in range(cx - a.radius, cx + a.radius + 1))
    print(header)
    for z in range(cz - a.radius, cz + a.radius + 1):
        row = ""
        for x in range(cx - a.radius, cx + a.radius + 1):
            col = cols.get((x, z))
            row += " " if not col else symbol(col[max(col)])
        print(f"{z:>5} {row}")

    if a.section is not None:
        z = a.section
        top = max((max(c) for (x, zz), c in cols.items() if zz == z), default=hi)
        bot = min((min(c) for (x, zz), c in cols.items() if zz == z), default=lo)
        print(f"\nrez z={z}, y {top} dolu na {max(bot, top - 45)}")
        for y in range(top, max(bot, top - 45) - 1, -1):
            row = "".join(symbol(cols.get((x, z), {}).get(y, "air"))
                          for x in range(cx - a.radius, cx + a.radius + 1))
            print(f"{y:>5} {row}")


if __name__ == "__main__":
    main()
