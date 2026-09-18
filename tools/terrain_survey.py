#!/usr/bin/env python3
"""Read terrain heights straight out of the world's region files.

Probing the live server for heights would mean thousands of RCON round trips,
so this reads the saved chunks directly. The server keeps recently-changed
chunks in memory, so run `save-all flush` first if you need the latest state.

The stored heightmaps are no use for *ground* level: all four of them count
leaves and logs, so a column under an oak reads as the top of the tree - which
is how the first terracing pass came to tip dirt into the canopy. Fully
generated chunks no longer keep the OCEAN_FLOOR_WG map that would have
answered it. So `ground_grid` walks the block data itself, top down, and stops
at the first block that is not air, foliage, water or something we built.

Usage:  terrain_survey.py [--centre X Z] [--radius N] [--footprint W D]
"""

import argparse
import statistics
import pathlib
import struct
import zlib
import gzip
import sys

REGION_DIR = pathlib.Path(__file__).resolve().parent.parent / \
    "data/world/dimensions/minecraft/overworld/region"
MIN_Y = -64  # 1.18+ world floor; heightmap values are relative to it


# --- minimal NBT reader -----------------------------------------------------

class NBT:
    SIMPLE = {1: (">b", 1), 2: (">h", 2), 3: (">i", 4),
              4: (">q", 8), 5: (">f", 4), 6: (">d", 8)}

    def __init__(self, data):
        self.d, self.p = data, 0

    def u1(self):
        v = self.d[self.p]; self.p += 1; return v

    def name(self):
        n = struct.unpack_from(">H", self.d, self.p)[0]; self.p += 2
        s = self.d[self.p:self.p + n].decode("utf-8", "replace"); self.p += n
        return s

    def payload(self, t):
        if t in self.SIMPLE:
            f, sz = self.SIMPLE[t]
            v = struct.unpack_from(f, self.d, self.p)[0]; self.p += sz
            return v
        if t == 8:
            n = struct.unpack_from(">H", self.d, self.p)[0]; self.p += 2
            v = self.d[self.p:self.p + n].decode("utf-8", "replace"); self.p += n
            return v
        if t == 7:
            n = struct.unpack_from(">i", self.d, self.p)[0]; self.p += 4
            v = bytes(self.d[self.p:self.p + n]); self.p += n; return v
        if t == 11:
            n = struct.unpack_from(">i", self.d, self.p)[0]; self.p += 4
            v = list(struct.unpack_from(">%di" % n, self.d, self.p)); self.p += 4 * n
            return v
        if t == 12:
            n = struct.unpack_from(">i", self.d, self.p)[0]; self.p += 4
            v = list(struct.unpack_from(">%dq" % n, self.d, self.p)); self.p += 8 * n
            return v
        if t == 9:
            it = self.u1()
            n = struct.unpack_from(">i", self.d, self.p)[0]; self.p += 4
            return [self.payload(it) for _ in range(n)]
        if t == 10:
            out = {}
            while True:
                tt = self.u1()
                if tt == 0:
                    return out
                # Read the key before the value: Python evaluates the
                # right-hand side first, which would consume the payload
                # before the name and desynchronise the stream.
                key = self.name()
                out[key] = self.payload(tt)
        raise ValueError("unknown NBT tag %d" % t)

    def parse(self):
        t = self.u1(); self.name(); return self.payload(t)


def unpack_heightmap(longs):
    """WORLD_SURFACE: 256 nine-bit values, seven per long, never spanning one."""
    out = []
    for word in longs:
        w = word & 0xFFFFFFFFFFFFFFFF
        for i in range(7):
            if len(out) == 256:
                return out
            out.append((w >> (9 * i)) & 0x1FF)
    return out


def read_chunks(rx, rz):
    """Yield (chunk_x, chunk_z, nbt) for every chunk stored in one region."""
    path = REGION_DIR / f"r.{rx}.{rz}.mca"
    if not path.exists():
        return
    raw = path.read_bytes()
    for idx in range(1024):
        # Location entry: three bytes of sector offset, then a sector count.
        off = int.from_bytes(raw[idx * 4:idx * 4 + 3], "big")
        sectors = raw[idx * 4 + 3]
        if off == 0 or sectors == 0:
            continue
        start = off * 4096
        length, comp = struct.unpack_from(">IB", raw, start)
        blob = raw[start + 5:start + 4 + length]
        try:
            data = zlib.decompress(blob) if comp == 2 else gzip.decompress(blob)
            nbt = NBT(data).parse()
        except Exception:
            continue
        yield rx * 32 + (idx % 32), rz * 32 + (idx // 32), nbt


def read_region(rx, rz):
    """Yield (chunk_x, chunk_z, heights[256]) from the WORLD_SURFACE map.

    Tree tops included - see the module docstring. Kept for the flattest and
    prominence searches, which only compare sites with each other.
    """
    for cx, cz, nbt in read_chunks(rx, rz):
        hm = (nbt.get("Heightmaps") or {}).get("WORLD_SURFACE")
        if hm:
            yield cx, cz, unpack_heightmap(hm)


# --- ground level from the block data ---------------------------------------

# Anything that grows on the ground, floats over it, or was put there by us:
# skipped when looking down a column for the surface.
SKIP_EXACT = {
    "air", "cave_air", "void_air", "water", "bubble_column", "snow", "ice",
    "cobweb", "vine", "glow_lichen", "lily_pad", "sugar_cane", "bamboo",
    "cactus", "pumpkin", "melon", "dead_bush", "fern", "large_fern",
    "short_grass", "grass", "tall_grass", "seagrass", "tall_seagrass",
    "kelp", "kelp_plant", "moss_carpet", "hanging_roots", "azalea",
    "flowering_azalea", "torch", "wall_torch", "lantern", "chain",
    "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet",
    "oxeye_daisy", "cornflower", "lily_of_the_valley", "wither_rose",
    "sunflower", "lilac", "rose_bush", "peony", "torchflower",
    "spore_blossom", "pink_petals", "sweet_berry_bush",
}
SKIP_SUFFIX = ("_leaves", "_log", "_wood", "_sapling", "_tulip", "_mushroom",
               "_fungus", "_roots", "_sprouts", "_fence", "_fence_gate",
               "_sign", "_banner", "_carpet", "_button", "_pressure_plate")


def is_cover(name):
    """True for blocks that sit on the ground rather than being the ground."""
    return name in SKIP_EXACT or name.endswith(SKIP_SUFFIX)


def section_lookup(section):
    """(palette, index_of) for one 16^3 section, or None if it is all cover."""
    bs = section.get("block_states") or {}
    palette = [str(e.get("Name", "")).split(":")[-1] for e in bs.get("palette", [])]
    if not palette or all(is_cover(n) for n in palette):
        return None
    data = bs.get("data")
    if data is None:                       # single-block section
        return palette, lambda i: 0
    # 1.16+: entries are packed into longs without ever spanning one.
    bits = max(4, (len(palette) - 1).bit_length())
    per, mask = 64 // bits, (1 << bits) - 1

    def index_of(i):
        return (data[i // per] >> ((i % per) * bits)) & mask

    return palette, index_of


def chunk_ground(nbt):
    """Ground height for all 256 columns of a chunk, or None where unknown."""
    cols = [None] * 256
    left = 256
    for sec in sorted(nbt.get("sections") or [], key=lambda s: -s.get("Y", 0)):
        look = section_lookup(sec)
        if look is None:
            continue
        palette, index_of = look
        base = sec["Y"] * 16
        for y in range(15, -1, -1):
            row = y * 256
            for c in range(256):
                if cols[c] is not None:
                    continue
                if not is_cover(palette[index_of(row + c)]):
                    cols[c] = base + y
                    left -= 1
        if left == 0:
            break
    return cols


def ground_grid(centre, radius):
    """Map every (x, z) in range to the top of the actual ground."""
    cx0, cz0 = centre
    grid = {}
    regions = {(x // 512, z // 512)
               for x in (cx0 - radius, cx0 + radius)
               for z in (cz0 - radius, cz0 + radius)}
    for rx, rz in regions:
        for cx, cz, nbt in read_chunks(rx, rz):
            if (abs(cx * 16 + 8 - cx0) > radius + 16
                    or abs(cz * 16 + 8 - cz0) > radius + 16):
                continue
            for i, h in enumerate(chunk_ground(nbt)):
                if h is None:
                    continue
                x, z = cx * 16 + (i % 16), cz * 16 + (i // 16)
                if abs(x - cx0) <= radius and abs(z - cz0) <= radius:
                    grid[(x, z)] = h
    return grid


def build_grid(centre, radius):
    """Map every (x, z) in range to its surface height."""
    cx0, cz0 = centre
    grid = {}
    regions = {(x // 512, z // 512)
               for x in (cx0 - radius, cx0 + radius)
               for z in (cz0 - radius, cz0 + radius)}
    for rx, rz in regions:
        for cx, cz, heights in read_region(rx, rz):
            for i, h in enumerate(heights):
                x = cx * 16 + (i % 16)
                z = cz * 16 + (i // 16)
                if abs(x - cx0) <= radius and abs(z - cz0) <= radius:
                    grid[(x, z)] = h + MIN_Y
    return grid


def flattest(grid, centre, radius, w, d):
    """Best footprint placement: least height spread, then closest to centre."""
    cx0, cz0 = centre
    best = []
    for x in range(cx0 - radius, cx0 + radius - w):
        for z in range(cz0 - radius, cz0 + radius - d):
            hs = [grid.get((x + i, z + j)) for i in range(w) for j in range(d)]
            if any(h is None for h in hs):
                continue
            spread = max(hs) - min(hs)
            dist = abs(x + w // 2 - cx0) + abs(z + d // 2 - cz0)
            best.append((spread, dist, x, z, min(hs), max(hs),
                         sorted(hs)[len(hs) // 2]))
    best.sort()
    return best


def prominent(grid, centre, radius, w, d, ring=16, step=2):
    """Rank sites by how far they stand above the surrounding terrain.

    `flattest` finds where least earth has to move; this finds where a build
    will be *seen* from. The two rarely agree - a hilltop worth putting a
    cottage on usually needs its top levelling first, which is what the
    `level` column reports.
    """
    cx0, cz0 = centre
    out = []
    for x in range(cx0 - radius, cx0 + radius - w, step):
        for z in range(cz0 - radius, cz0 + radius - d, step):
            foot = [grid.get((x + i, z + j)) for i in range(w) for j in range(d)]
            if any(h is None for h in foot):
                continue
            cx, cz = x + w // 2, z + d // 2
            skirt = [grid.get((cx + dx, cz + dz))
                     for dx in range(-ring, ring + 1)
                     for dz in range(-ring, ring + 1)
                     if max(abs(dx), abs(dz)) > ring - 3]
            skirt = [h for h in skirt if h is not None]
            if len(skirt) < 40:
                continue
            top = statistics.median(foot)
            out.append((top - statistics.median(skirt), top,
                        max(foot) - min(foot), x, z,
                        abs(cx - cx0) + abs(cz - cz0)))
    out.sort(reverse=True)
    return out


def render(grid, centre, half):
    """A quick text relief map, for eyeballing what the numbers describe."""
    cx, cz = centre
    ramp = " .:-=+*#%@"
    hs = [h for (x, z), h in grid.items()
          if abs(x - cx) < half and abs(z - cz) < half]
    lo, hi = min(hs), max(hs)
    print(f"  relief around ({cx}, {cz}) - north up, west left, "
          f"'{ramp[0]}'={lo} to '{ramp[-1]}'={hi}\n")
    for z in range(cz - half, cz + half):
        row = "".join(
            " " if grid.get((x, z)) is None
            else ramp[min(9, (grid[(x, z)] - lo) * 10 // max(1, hi - lo + 1))]
            for x in range(cx - half, cx + half))
        print("   " + row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=int, default=[0, 0], metavar=("X", "Z"))
    ap.add_argument("--radius", type=int, default=64)
    ap.add_argument("--footprint", nargs=2, type=int, metavar=("W", "D"))
    ap.add_argument("--hilltop", action="store_true",
                    help="rank by prominence above surroundings, not flatness")
    ap.add_argument("--map", type=int, metavar="HALF",
                    help="print a text relief map of this half-width")
    a = ap.parse_args()

    grid = build_grid(tuple(a.centre), a.radius)
    if not grid:
        sys.exit("No chunk data found - is the world generated around there?")

    hs = sorted(grid.values())
    print(f"Probed {len(grid)} columns within {a.radius} blocks of "
          f"({a.centre[0]}, {a.centre[1]})")
    print(f"  height range : {hs[0]} to {hs[-1]}  (median {hs[len(hs)//2]})")

    if a.footprint and a.hilltop:
        w, d = a.footprint
        print(f"\nMost prominent {w}x{d} sites:\n")
        print(f"  {'corner':>14}  {'top':>4}  {'above':>6}  {'level':>5}  {'dist':>4}")
        for pro, top, spread, x, z, dist in prominent(
                grid, tuple(a.centre), a.radius, w, d)[:8]:
            print(f"  {x:>6},{z:>6}  {top:>4.0f}  {pro:>6.1f}  {spread:>5}  {dist:>4}")
    elif a.footprint:
        w, d = a.footprint
        results = flattest(grid, tuple(a.centre), a.radius, w, d)
        print(f"\nFlattest {w}x{d} sites (spread = highest minus lowest):\n")
        print(f"  {'corner':>14}  {'spread':>6}  {'floor':>5}  {'dist':>4}")
        for spread, dist, x, z, lo, hi, med in results[:8]:
            print(f"  {x:>6},{z:>6}  {spread:>6}  {med:>5}  {dist:>4}")

    if a.map:
        print()
        render(grid, tuple(a.centre), a.map)


if __name__ == "__main__":
    main()
