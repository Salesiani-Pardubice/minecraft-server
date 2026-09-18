#!/usr/bin/env python3
"""Read terrain heights straight out of the world's region files.

Probing the live server for heights would mean thousands of RCON round trips;
the region files already hold a WORLD_SURFACE heightmap per chunk, so this
reads them directly. The server keeps recently-changed chunks in memory, so run
`save-all flush` first if you need the very latest state.

Usage:  terrain_survey.py [--centre X Z] [--radius N] [--footprint W D]
"""

import argparse
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


def read_region(rx, rz):
    """Yield (chunk_x, chunk_z, heights[256]) for every chunk present."""
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
        hm = (nbt.get("Heightmaps") or {}).get("WORLD_SURFACE")
        if not hm:
            continue
        cx = rx * 32 + (idx % 32)
        cz = rz * 32 + (idx // 32)
        yield cx, cz, unpack_heightmap(hm)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=int, default=[0, 0], metavar=("X", "Z"))
    ap.add_argument("--radius", type=int, default=64)
    ap.add_argument("--footprint", nargs=2, type=int, metavar=("W", "D"))
    a = ap.parse_args()

    grid = build_grid(tuple(a.centre), a.radius)
    if not grid:
        sys.exit("No chunk data found - is the world generated around there?")

    hs = sorted(grid.values())
    print(f"Probed {len(grid)} columns within {a.radius} blocks of "
          f"({a.centre[0]}, {a.centre[1]})")
    print(f"  height range : {hs[0]} to {hs[-1]}  (median {hs[len(hs)//2]})")

    if a.footprint:
        w, d = a.footprint
        results = flattest(grid, tuple(a.centre), a.radius, w, d)
        print(f"\nFlattest {w}x{d} sites (spread = highest minus lowest):\n")
        print(f"  {'corner':>14}  {'spread':>6}  {'floor':>5}  {'dist':>4}")
        for spread, dist, x, z, lo, hi, med in results[:8]:
            print(f"  {x:>6},{z:>6}  {spread:>6}  {med:>5}  {dist:>4}")


if __name__ == "__main__":
    main()
