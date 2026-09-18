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
    "carodejnice": dict(at=(136, -328), label="Čarodějnická chalupa",
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


# --- 2. the cabin in the jungle ---------------------------------------------

def chata(s, grid):
    """Two storeys of timber over a stone undercroft, deep in the jungle."""
    b = dict(x1=-5, x2=5, z1=-4, z2=4)
    pad = (b["x1"] - 2, b["z1"] - 2, b["x2"] + 2, b["z2"] + 2)
    y = base_level(grid, pad)
    clear_growth(s, pad, y, margin=5)
    level(s, grid, pad, y, blend=4)

    # Undercroft: mossy stone, with a cart arch on the west end.
    ground = y + 1
    shell(s, b, ground + 3, "cobblestone", y, floor_y=ground,
          plinth="mossy_cobblestone", floor="stone_bricks")
    s.fill((b["x1"], ground, -2), (b["x1"], ground + 2, 2), "air")   # the arch
    s.fill((b["x1"] - 1, ground + 3, -2), (b["x1"], ground + 3, 2),
           "jungle_slab[type=top]")
    s.fill((0, ground, b["z2"]), (0, ground + 1, b["z2"]), "air")    # the door
    s.block((0, ground, b["z2"]), "jungle_door[facing=south,half=lower]")
    s.block((0, ground + 1, b["z2"]), "jungle_door[facing=south,half=upper]")

    # Upper storey: planks between log posts, and a balcony over the arch.
    upper = ground + 4
    top = upper + 4
    shell(s, b, top, "jungle_planks", upper - 1, floor_y=upper,
          plinth="jungle_planks", floor="jungle_planks")
    for u in (b["x1"], b["x2"], -2, 2):
        for v in (b["z1"], b["z2"]):
            s.fill((u, upper, v), (u, top, v), "jungle_log[axis=y]")
    for u in (-3, -1, 1, 3):
        s.fill((u, upper + 1, b["z2"]), (u, upper + 2, b["z2"]), "glass_pane")
        s.fill((u, upper + 1, b["z1"]), (u, upper + 2, b["z1"]), "glass_pane")
    gable_end(s, b, top + 1, "x", "jungle_planks")
    gable(s, b, top, "x", "spruce_planks", "spruce_stairs")

    # The balcony, reached by an outside stair on the east end.
    s.fill((b["x1"] - 2, upper - 1, -3), (b["x1"] - 1, upper - 1, 3),
           "jungle_planks")
    for u, v in ((b["x1"] - 2, -3), (b["x1"] - 2, 3)):
        s.fill((u, ground, v), (u, upper - 2, v), "jungle_fence")
    for u, v in trace([(b["x1"] - 2, -3), (b["x1"] - 2, 3), (b["x1"], 3)]):
        s.block((u, upper, v), "jungle_fence")
    s.fill((b["x1"] - 1, upper, 0), (b["x1"] - 1, upper, 0), "air")
    for i in range(4):
        s.block((b["x2"] + 1, ground + i, 3 - i),
                f"jungle_stairs[facing=north]")
    s.fill((b["x2"], upper, 1), (b["x2"], upper + 1, 1), "air")      # the way in

    # Chimney, lights and pots, as in the picture.
    s.fill((b["x2"] - 1, ground, b["z1"] - 1), (b["x2"] - 1, top + 6, b["z1"] - 1),
           "cobblestone")
    s.block((b["x2"] - 1, top + 7, b["z1"] - 1), "campfire[lit=true]")
    for u, v in ((-4, b["z2"]), (2, b["z2"]), (b["x1"] - 1, 0)):
        s.block((u, ground + 3, v), "lantern")
    for u in (-2, 2):
        s.block((u, ground, b["z2"] + 1), "flower_pot")
    route(s, grid, [(0, b["z2"] + 1), (0, 9), (4, 16)], "stone_bricks", width=1)
    s.block((b["x1"] - 3, ground, 0), "barrel")
    tree(s, b["x2"] + 5, b["z2"] + 4, y, h=7, log="jungle_log",
         leaf="jungle_leaves", spread=3)


# --- 3. the tree house -------------------------------------------------------

def strom(s, grid):
    """A house up a tree that had to be grown first: no oak here is big
    enough to carry one, so the trunk, the boughs and the crown are built."""
    y = base_level(grid, (-9, -9, 9, 9))
    clear_growth(s, (-8, -8, 8, 8), y, margin=4)
    level(s, grid, (-4, -4, 4, 4), y, blend=6)

    trunk_top = y + 22
    s.fill((-1, y, -1), (1, trunk_top, 1), "oak_log[axis=y]")
    s.fill((-2, y, -2), (2, y + 2, 2), "oak_log[axis=y]")            # root flare
    s.fill((-2, y, -2), (-2, y + 1, -2), "air")
    s.fill((2, y, 2), (2, y + 1, 2), "air")
    # A door into the foot of the trunk, and a ladder inside it.
    s.fill((0, y + 1, 2), (0, y + 2, 2), "air")
    s.block((0, y + 1, 2), "oak_door[facing=south,half=lower]")
    s.block((0, y + 2, 2), "oak_door[facing=south,half=upper]")
    s.fill((0, y + 1, 1), (0, trunk_top - 4, 1), "ladder[facing=south]")
    s.fill((0, y + 1, 0), (0, trunk_top - 4, 0), "air")

    # The platform and the house on it.
    deck = y + 13
    s.fill((-5, deck, -5), (5, deck, 5), "oak_planks")
    for u, v in perimeter((-5, -5, 5, 5)):
        s.block((u, deck + 1, v), "oak_fence")
    s.fill((-1, deck, -1), (1, deck, 1), "oak_log[axis=y]")
    s.fill((0, deck, 0), (0, deck, 0), "air")                        # the hatch
    house = dict(x1=-4, x2=2, z1=-4, z2=2)
    shell(s, house, deck + 4, "oak_planks", deck, plinth="oak_planks",
          floor="oak_planks")
    for u in (house["x1"], house["x2"]):
        for v in (house["z1"], house["z2"]):
            s.fill((u, deck + 1, v), (u, deck + 4, v), "stripped_oak_wood")
    gable_end(s, house, deck + 5, "x", "oak_planks")
    gable(s, house, deck + 4, "x", "oak_planks", "oak_stairs")
    s.fill((house["x2"], deck + 1, 0), (house["x2"], deck + 2, 0), "air")
    s.block((house["x2"], deck + 1, 0), "oak_door[facing=east,half=lower]")
    s.block((house["x2"], deck + 2, 0), "oak_door[facing=east,half=upper]")
    for v in (-3, -1):
        s.fill((house["x1"], deck + 2, v), (house["x1"], deck + 3, v), "glass_pane")
    s.fill((-2, deck + 2, house["z1"]), (0, deck + 3, house["z1"]), "glass_pane")
    s.block((-1, deck + 3, -1), "lantern[hanging=true]")

    # Boughs and crown, so the house sits in a tree rather than on a pole.
    for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        for i in range(2, 7):
            s.block((du * i, trunk_top - 6 + i // 2, dv * i), "oak_log")
    for h, r in ((trunk_top - 3, 6), (trunk_top - 1, 7), (trunk_top + 1, 6),
                 (trunk_top + 3, 4)):
        disc(s, 0, 0, h, r, "oak_leaves")
    s.fill((-1, trunk_top - 3, -1), (1, trunk_top + 2, 1), "oak_log[axis=y]")
    for u, v in ((-6, 0), (6, 0), (0, -6), (0, 6), (4, 4), (-4, -4)):
        s.fill((u, deck + 2, v), (u, deck + 4, v), "hanging_roots")
    for u, v in ((-4, 4), (4, -4)):
        s.fill((u, deck + 2, v), (u, deck + 3, v), "iron_chain")
        s.block((u, deck + 4, v), "lantern[hanging=true]")
    route(s, grid, [(0, 3), (2, 10), (1, 18)], "dirt_path", width=0)


# --- 4. the witch's house ----------------------------------------------------

def carodejnice(s, grid):
    """Mossy stone below, crooked timber above, a roof going back to moss."""
    b = dict(x1=-4, x2=4, z1=-4, z2=3)
    pad = (b["x1"] - 2, b["z1"] - 2, b["x2"] + 2, b["z2"] + 2)
    y = base_level(grid, pad)
    clear_growth(s, pad, y, margin=5)
    level(s, grid, pad, y, blend=5)

    ground = y + 1
    shell(s, b, ground + 3, "mossy_stone_bricks", y, floor_y=ground,
          plinth="mossy_cobblestone", floor="cobblestone")
    s.fill((0, ground, b["z2"]), (0, ground + 2, b["z2"]), "air")
    s.block((0, ground, b["z2"]), "dark_oak_door[facing=south,half=lower]")
    s.block((0, ground + 1, b["z2"]), "dark_oak_door[facing=south,half=upper]")
    for u in (-3, 3):
        s.fill((u, ground + 1, b["z2"]), (u, ground + 2, b["z2"]), "glass_pane")

    # The upper floor overhangs, and leans out further at the gable.
    upper = dict(x1=b["x1"] - 1, x2=b["x2"] + 1, z1=b["z1"] - 1, z2=b["z2"] + 1)
    lo = ground + 4
    s.fill((upper["x1"], lo, upper["z1"]), (upper["x2"], lo, upper["z2"]),
           "dark_oak_planks")
    shell(s, upper, lo + 4, "spruce_planks", lo, floor_y=None,
          plinth="dark_oak_planks")
    for u in (upper["x1"], upper["x2"]):
        for v in (upper["z1"], upper["z2"]):
            s.fill((u, lo + 1, v), (u, lo + 4, v), "dark_oak_log[axis=y]")
    for u in (-2, 0, 2):
        s.fill((u, lo + 2, upper["z2"]), (u, lo + 3, upper["z2"]), "glass_pane")
    s.fill((upper["x1"], lo + 2, -1), (upper["x1"], lo + 3, 1), "glass_pane")
    gable_end(s, upper, lo + 5, "x", "spruce_planks")
    # A roof of moss and grass over dark timber, as in the picture.
    ridge = gable(s, upper, lo + 4, "x", "moss_block", "dark_oak_stairs")
    for v in range(upper["z1"] + 1, upper["z2"]):
        s.fill((upper["x1"], lo + 5 + abs(v) // 2, v),
               (upper["x2"], lo + 5 + abs(v) // 2, v), "moss_block")
    s.fill((upper["x1"], ridge, -1), (upper["x2"], ridge, 0), "moss_block")

    # Chimney, cauldron, and the things a witch keeps.
    s.fill((b["x1"] + 1, ground, b["z1"]), (b["x1"] + 1, ridge + 3, b["z1"]),
           "cobblestone")
    s.block((b["x1"] + 1, ridge + 4, b["z1"]), "campfire[lit=true]")
    s.block((2, ground, b["z2"] + 2), "cauldron")
    s.block((3, ground, b["z2"] + 2), "campfire[lit=true]")
    s.block((-2, ground, b["z2"] + 2), "brewing_stand")
    s.fill((b["x1"] + 1, ground, b["z1"] + 1), (b["x1"] + 1, ground + 1, b["z1"] + 1),
           "bookshelf")
    s.block((0, ground + 2, 0), "lantern[hanging=true]")
    for u, v in ((b["x1"] - 1, b["z2"] + 1), (b["x2"] + 1, b["z2"] + 1)):
        s.fill((u, ground, v), (u, ground + 2, v), "oak_fence")
        s.block((u, ground + 3, v), "lantern")
    # Left to the wood: vines down the stonework and a ring of mushrooms.
    for v in (b["z1"], b["z2"]):
        s.fill((b["x1"] + 2, ground + 1, v), (b["x1"] + 2, ground + 2, v), "vine")
    for u, v in ((-6, 5), (-5, 6), (6, -5), (5, 5), (-6, -4)):
        g = grid.get((u, v))
        if g is not None:
            s.block((u, g + 1, v), "red_mushroom")
    route(s, grid, [(0, b["z2"] + 1), (1, 9), (-2, 16)], "dirt_path", width=0)


BUILDS = {"mlyn": mlyn, "chata": chata, "strom": strom,
          "carodejnice": carodejnice}


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
