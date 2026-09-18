#!/usr/bin/env python3
"""Landmarks scattered over the map: a castle, a flying ship, a jungle cabin,
a tree house, a witch's house, an arena, a ship and a windmill.

Each one is written in its own local coordinates with the site at the origin,
the same way the village is, so a new world can put them up from scratch:
`Session(origin=...)` does the shifting. Sites were chosen by surveying the
generated chunks for biome and relief - the castle wants the highest ground
there is, the cabin wants jungle, the ship wants water - and each build clears
and beds itself into the ground it finds, so it reads as part of the place
rather than dropped on top of it.
"""

import argparse
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mc import Session
from parts import (BUILT, clear_growth, cylinder, disc, follow, gable,
                   gable_end, level, line, perimeter, profile, round_roof,
                   route, shell, trace, tree)
from terrain_survey import ground_grid

# Where each one stands, and what the map should call it. The coordinates come
# from a survey of every generated chunk: biome, median height and relief.
SITES = {
    "mlyn":      dict(at=(480, 144),    label="Větrný mlýn",
                      note="na kopci v květnaté louce"),
    "chata":     dict(at=(768, -1536),  label="Chata v pralese",
                      note="v džungli u pobřeží"),
    "strom":     dict(at=(-320, -256),  label="Dům na stromě",
                      note="v pralesním dubu"),
    "carodejnice": dict(at=(0, -272),   label="Čarodějnická chalupa",
                      note="v temném lese"),
    "koloseum":  dict(at=(690, 75),     label="Koloseum",
                      note="aréna na pláni"),
    "hrad":      dict(at=(976, -192),   label="Hrad",
                      note="na nejvyšším vrcholu"),
    "lod":       dict(at=(950, -1600),  label="Loď",
                      note="u pobřeží"),
    "vzducholod": dict(at=(890, -250),  label="Létající loď",
                      note="nad horami"),
}


def survey(site, radius=40):
    """Ground level round one site, in coordinates local to it."""
    subprocess.run(["docker", "exec", "-i", "minecraft-server", "rcon-cli",
                    "save-all flush"], capture_output=True, text=True)
    ox, oz = SITES[site]["at"]
    grid = ground_grid((ox, oz), radius, extra_cover=BUILT)
    return {(x - ox, z - oz): h for (x, z), h in grid.items()}


def base_level(grid, box):
    """The level to build at: the median of the ground under a footprint."""
    u1, v1, u2, v2 = box
    hs = sorted(h for (u, v), h in grid.items()
                if u1 <= u <= u2 and v1 <= v <= v2)
    return hs[len(hs) // 2] if hs else None


# --- 1. the windmill ---------------------------------------------------------

def mlyn(s, grid):
    """A round stone mill on the brow of the hill, sails to the west wind."""
    pad = (-7, -7, 7, 7)
    y = base_level(grid, pad)
    clear_growth(s, pad, y, margin=6)
    level(s, grid, pad, y, blend=5)

    top = y + 13
    cylinder(s, 0, 0, y + 1, top, 4, "cobblestone")
    cylinder(s, 0, 0, y + 1, top, 3, "air", hollow=False)
    disc(s, 0, 0, y, 4, "stone_bricks")                      # floor
    for h in (y + 5, y + 9):                                 # two more floors
        disc(s, 0, 0, h, 3, "spruce_planks")
        s.block((3, h, 0), "air")
    # A band of stone brick at each floor, so the tower reads as storeys.
    for h in (y + 5, y + 9):
        cylinder(s, 0, 0, h, h, 4, "stone_bricks")
    # Windows and the door, facing the path.
    s.fill((0, y + 1, 4), (0, y + 3, 4), "air")
    s.block((0, y + 1, 4), "spruce_door[facing=south,half=lower]")
    s.block((0, y + 2, 4), "spruce_door[facing=south,half=upper]")
    for h, du, dv in ((y + 3, -4, 0), (y + 7, 0, -4), (y + 7, 4, 0),
                      (y + 11, 0, 4), (y + 11, -4, 0)):
        s.fill((du, h, dv), (du, h + 1, dv), "glass_pane")
    # Ladders up.
    s.fill((-2, y + 1, 0), (-2, top - 1, 0), "ladder[facing=east]")

    # The cap, and the shaft the sails turn on.
    cap = round_roof(s, 0, 0, top + 1, 4, "dark_oak_planks")
    s.fill((0, cap, 0), (0, cap + 1, 0), "dark_oak_fence")
    hub = (0, top - 2, 0)
    s.fill((-5, hub[1], 0), (-4, hub[1], 0), "dark_oak_log[axis=x]")

    # Four sails, an X of lattice, clear of the tower.
    for du, dv in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        for i in range(1, 10):
            u, h = -5, hub[1]
            s.block((u, h + dv * i, du * i), "dark_oak_fence")
            if i > 1:
                s.block((u - 1, h + dv * i, du * i), "oak_trapdoor[facing=west,open=true]")
                s.block((u, h + dv * (i - 1), du * i), "dark_oak_fence")

    # Inside: the millstone, sacks and a lantern.
    s.block((2, y + 1, 1), "smooth_stone")
    s.block((2, y + 2, 1), "smooth_stone_slab")
    s.fill((1, y + 1, -2), (2, y + 1, -2), "hay_block")
    s.block((-1, y + 1, 2), "barrel")
    s.block((0, y + 4, 0), "lantern[hanging=true]")
    s.block((0, y + 8, 0), "lantern[hanging=true]")

    # The yard: a low fence, a stack of hay, and the track up the hill.
    for u, v in perimeter((-7, -7, 7, 7)):
        if abs(u) <= 1 and v == 7:
            continue
        g = grid.get((u, v))
        if g is not None:
            s.fill((u, g + 1, v), (u, g + 2, v), "oak_fence")
    s.fill((5, y + 1, -4), (6, y + 2, -3), "hay_block")
    route(s, grid, [(0, 7), (0, 14), (3, 22), (2, 30)], "dirt_path", width=1)
    for v in (6, 16, 26):
        g = grid.get((3, v))
        if g is not None:
            s.fill((3, g + 1, v), (3, g + 3, v), "oak_fence")
            s.block((3, g + 4, v), "lantern")


BUILDS = {"mlyn": mlyn}


def main():
    # The site labels are Czech and the console here is not UTF-8 by default.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="*", default=list(BUILDS))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for name in a.sites:
        if name not in BUILDS:
            sys.exit(f"unknown site {name!r}; known: {', '.join(BUILDS)}")
        print(f"-- {name}  ({SITES[name]['label']}, {SITES[name]['at']})")
        s = Session(origin=SITES[name]["at"])
        BUILDS[name](s, survey(name))
        s.flush(dry_run=a.dry_run)


if __name__ == "__main__":
    main()
