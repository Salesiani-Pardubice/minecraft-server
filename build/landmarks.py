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
from parts import (BUILT, clear_growth, cylinder, deck, disc, follow, gable,
                   gable_end, hull, level, line, mast, perimeter, profile,
                   ring_cells, round_roof, route, shell, trace, tree)
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
    "lod":       dict(at=(990, -1626),  label="Loď",
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


# --- 5. the arena -----------------------------------------------------------

STONE = "sandstone"
STONE_CUT = "cut_sandstone"
STONE_SMOOTH = "smooth_sandstone"
STONE_STAIR = "smooth_sandstone_stairs"


def koloseum(s, grid):
    """A ring of arches round a sanded floor, with the seating stepped up
    between them. Four ways in, on the four winds."""
    outer, inner = 24, 13
    y = base_level(grid, (-outer, -outer, outer, outer))
    clear_growth(s, (-outer, -outer, outer, outer), y, margin=4, up=30)
    level(s, grid, (-outer - 1, -outer - 1, outer + 1, outer + 1), y, blend=6)

    floor = y - 2                                   # the arena is sunk a little
    # Clear the whole inside once rather than ring by ring: the same job in a
    # few hundred commands instead of forty thousand.
    for h in range(floor + 1, y + 15):
        disc(s, 0, 0, h, outer - 2, "air")
    disc(s, 0, 0, floor - 1, inner - 1, "stone_bricks")
    disc(s, 0, 0, floor, inner - 1, "sand")

    # Seating: each ring a course higher than the one inside it.
    for i, r in enumerate(range(inner, outer - 1)):
        h = y + i // 2
        disc(s, 0, 0, h, r, STONE_SMOOTH, hollow=True)
        disc(s, 0, 0, h - 1, r, STONE_CUT, hollow=True)
    # The wall that holds the seating off the floor.
    cylinder(s, 0, 0, floor, y + 1, inner, STONE_CUT)

    # The outer wall, two storeys of arches under a cornice.
    top = y + 13
    cylinder(s, 0, 0, y - 3, top, outer, STONE)
    cylinder(s, 0, 0, y - 3, top, outer - 1, STONE_SMOOTH)
    for h in (y + 5, top):
        disc(s, 0, 0, h, outer, STONE_CUT, hollow=True)
    ring = ring_cells(0, 0, outer)
    inner_ring = ring_cells(0, 0, outer - 1)
    for level_y, height in ((y + 1, 4), (y + 7, 4)):
        for cells in (ring, inner_ring):
            for i, (u, v) in enumerate(cells):
                if i % 6 in (1, 2, 3):
                    s.fill((u, level_y, v), (u, level_y + height - 2, v), "air")
                if i % 6 == 2:
                    s.block((u, level_y + height - 1, v), "air")
    # Merlons round the top.
    for i, (u, v) in enumerate(ring):
        if i % 3 == 0:
            s.block((u, top + 1, v), STONE_CUT)

    # Four tunnels in, and the stairs down to the sand.
    for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for i in range(inner - 1, outer + 2):
            for w in (-1, 0, 1):
                u = du * i + (dv and w)
                v = dv * i + (du and w)
                s.fill((u, y - 2, v), (u, y + 2, v), "air")
                s.block((u, y - 3, v), "stone_bricks")
        for j in range(3):                      # steps down into the arena
            u, v = du * (inner - 1 - j), dv * (inner - 1 - j)
            s.fill((u - abs(dv), y - 1 - j, v - abs(du)),
                   (u + abs(dv), y - 1 - j, v + abs(du)), "stone_brick_slab")
    # Torches on the wall, and banners at the gates.
    for i, (u, v) in enumerate(ring):
        if i % 8 == 0:
            s.block((u, y + 12, v), "lantern")
    for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        u, v = du * (outer - 1), dv * (outer - 1)
        s.fill((u + (dv and 2), y + 3, v + (du and 2)),
               (u + (dv and 2), y + 4, v + (du and 2)), "red_wool")
    route(s, grid, [(0, outer + 2), (2, outer + 12), (0, outer + 24)],
          "dirt_path", width=1)


# --- 6. the castle ----------------------------------------------------------

def hrad(s, grid):
    """A keep and a curtain wall on the highest ground on the map, with the
    rock left standing round it - it is a crag with a castle on it, not a
    castle on a lawn."""
    y = base_level(grid, (-13, -13, 13, 13))
    clear_growth(s, (-16, -16, 16, 16), y, margin=3, up=34)
    level(s, grid, (-14, -14, 14, 14), y, blend=8, top="stone")

    stone, dark = "stone_bricks", "deepslate_bricks"
    roof, roof_stair = "bricks", "brick_stairs"

    # Curtain wall with a tower at each corner.
    wall_top = y + 9
    for u, v in perimeter((-13, -13, 13, 13)):
        s.fill((u, y - 6, v), (u, wall_top, v), stone)
        s.fill((u, y - 6, v), (u, y + 1, v), dark)
    for i, (u, v) in enumerate(sorted(perimeter((-13, -13, 13, 13)))):
        if i % 2 == 0:
            s.block((u, wall_top + 1, v), stone)
    s.fill((-12, y + 1, -12), (12, wall_top + 2, 12), "air")
    s.fill((-12, y, -12), (12, y, 12), "stone_bricks")
    for cu, cv in ((-13, -13), (-13, 13), (13, -13), (13, 13)):
        cylinder(s, cu, cv, y - 6, wall_top + 4, 3, stone)
        cylinder(s, cu, cv, y - 6, wall_top + 4, 2, "air", hollow=False)
        for i, (u, v) in enumerate(ring_cells(cu, cv, 3)):
            if i % 2 == 0:
                s.block((u, wall_top + 5, v), stone)
        s.fill((cu, wall_top + 4, cv), (cu, wall_top + 4, cv), "oak_fence")
        round_roof(s, cu, cv, wall_top + 5, 3, roof)

    # The gatehouse, facing the ramp up the hill.
    s.fill((-1, y + 1, 13), (1, y + 4, 13), "air")
    s.fill((-2, y + 1, 13), (-2, y + 6, 13), dark)
    s.fill((2, y + 1, 13), (2, y + 6, 13), dark)
    s.fill((-1, y + 5, 13), (1, y + 5, 13), "iron_bars")
    s.fill((-1, y + 6, 13), (1, y + 6, 13), stone)

    # The keep: a tall block with a pitched roof and a stair turret.
    keep = dict(x1=-7, x2=3, z1=-7, z2=1)
    shell(s, keep, y + 18, stone, y, floor_y=y + 1, plinth=dark,
          floor="stone_bricks")
    for h in (y + 7, y + 13):
        s.fill((keep["x1"] + 1, h, keep["z1"] + 1),
               (keep["x2"] - 1, h, keep["z2"] - 1), "dark_oak_planks")
    for u in (keep["x1"], keep["x2"]):
        for v in (keep["z1"], keep["z2"]):
            s.fill((u, y, v), (u, y + 19, v), dark)
    for h in (y + 4, y + 10, y + 16):
        for u in range(keep["x1"] + 2, keep["x2"] - 1, 3):
            s.fill((u, h, keep["z1"]), (u, h + 1, keep["z1"]), "glass_pane")
            s.fill((u, h, keep["z2"]), (u, h + 1, keep["z2"]), "glass_pane")
    gable_end(s, keep, y + 19, "x", stone)
    gable(s, keep, y + 18, "x", roof, roof_stair)
    s.fill((0, y + 1, keep["z2"]), (0, y + 3, keep["z2"]), "air")   # the door
    # Stair turret on the keep's south-east corner.
    cylinder(s, 4, 2, y, y + 24, 2, stone)
    cylinder(s, 4, 2, y + 1, y + 24, 1, "air", hollow=False)
    s.fill((4, y + 1, 1), (4, y + 24, 1), "ladder[facing=south]")
    round_roof(s, 4, 2, y + 25, 2, roof)
    s.fill((4, y + 28, 2), (4, y + 30, 2), "oak_fence")
    s.block((4, y + 30, 3), "white_wool")

    # A hall along the west wall, with a red roof of its own.
    hall = dict(x1=-12, x2=-8, z1=-4, z2=6)
    shell(s, hall, y + 6, stone, y, floor_y=y + 1, plinth=dark,
          floor="dark_oak_planks")
    gable_end(s, hall, y + 7, "z", stone)
    gable(s, hall, y + 6, "z", roof, roof_stair)
    for v in (-2, 1, 4):
        s.fill((hall["x2"], y + 3, v), (hall["x2"], y + 4, v), "glass_pane")

    # Lights, and the ramp climbing the crag to the gate.
    for u, v in ((-6, 12), (6, 12), (-12, -10), (12, -10)):
        s.fill((u, y + 1, v), (u, y + 3, v), "oak_fence")
        s.block((u, y + 4, v), "lantern")
    for i, (u, v) in enumerate(ring_cells(0, 0, 13)):
        if i % 7 == 0:
            s.block((u, wall_top, v), "lantern")
    route(s, grid, [(0, 14), (1, 22), (6, 30), (4, 40)], "stone_bricks", width=1)


# --- 7. the ship ------------------------------------------------------------

SEA = 62                      # the water surface out there


def lod(s, grid):
    """A three-master lying at anchor off the beach, drawing four blocks."""
    keel, length, beam = SEA - 4, 31, 11
    deck_y = hull(s, keel, length, beam, 7, "spruce_planks", trim="dark_oak_log")
    deck(s, deck_y, length, beam, "oak_planks", rail="spruce_fence", rail_h=2)
    # Below decks, dry: the hull is a shell, so the hold stays out of the sea.
    for h in range(keel + 1, deck_y):
        s.fill((-12, h, -3), (12, h, 3), "air")
    s.fill((-12, keel + 1, -3), (12, keel + 1, 3), "spruce_planks")
    s.fill((-2, deck_y, 0), (-1, deck_y, 0), "air")          # the hatch
    s.fill((-2, keel + 2, 0), (-2, deck_y - 1, 0), "ladder[facing=east]")

    # Stern cabin, with the wheel in front of it.
    cab = dict(x1=8, x2=13, z1=-3, z2=3)
    shell(s, cab, deck_y + 4, "spruce_planks", deck_y, plinth="spruce_planks")
    gable_end(s, cab, deck_y + 5, "x", "spruce_planks")
    gable(s, cab, deck_y + 4, "x", "dark_oak_planks", "dark_oak_stairs")
    s.fill((cab["x1"], deck_y + 1, 0), (cab["x1"], deck_y + 2, 0), "air")
    for v in (-2, 2):
        s.fill((cab["x2"], deck_y + 2, v), (cab["x2"], deck_y + 3, v), "glass_pane")
    s.block((7, deck_y + 1, 0), "spruce_fence")
    s.block((7, deck_y + 2, 0), "oak_trapdoor[facing=east,open=true]")
    s.block((10, deck_y + 3, 0), "lantern[hanging=true]")

    # Masts, yards and canvas.
    mast(s, -9, 0, deck_y + 1, 17, "spruce_log[axis=y]",
         yard_at=((0.95, 6), (0.6, 5)), sail="white_wool", beam=5)
    mast(s, 0, 0, deck_y + 1, 20, "spruce_log[axis=y]",
         yard_at=((0.95, 7), (0.6, 6)), sail="white_wool", beam=6)
    mast(s, 6, 0, deck_y + 1, 14, "spruce_log[axis=y]",
         yard_at=((0.9, 5),), sail="white_wool", beam=4)
    # Bowsprit and rigging.
    s.fill((-15, deck_y + 1, 0), (-19, deck_y + 3, 0), "spruce_fence")
    for u, h in ((-9, 17), (0, 20), (6, 14)):
        s.fill((u, deck_y + h, 0), (u, deck_y + h, 0), "spruce_fence")
    for i in range(1, 9):
        s.block((-9 - i, deck_y + 17 - 2 * i, 0), "iron_chain")
        s.block((6 + i, deck_y + 14 - i, 0), "iron_chain")
    # Lanterns fore and aft, and the anchor over the bow.
    for u in (-13, 13):
        s.block((u, deck_y + 3, 0), "lantern")
    s.fill((-14, deck_y, 3), (-14, SEA - 3, 3), "iron_chain")
    s.block((-14, SEA - 4, 3), "anvil")
    # Cargo on deck.
    s.fill((2, deck_y + 1, -2), (3, deck_y + 1, -1), "barrel")
    s.block((3, deck_y + 1, 2), "chest[facing=south]")


# --- 8. the flying ship ------------------------------------------------------

def vzducholod(s, grid):
    """A steam packet in the sky over the mountains: a hull, a house on its
    back, chimneys trailing cloud, and wings that hold none of it up."""
    y = 186
    keel, length, beam = y, 35, 13
    deck_y = hull(s, keel, length, beam, 8, "spruce_planks", trim="dark_oak_log")
    deck(s, deck_y, length, beam, "oak_planks", rail="oak_fence", rail_h=1)

    # The house amidships, two storeys of it, with a pitched roof.
    big = dict(x1=-2, x2=8, z1=-4, z2=4)
    shell(s, big, deck_y + 6, "white_terracotta", deck_y, plinth="spruce_planks")
    for u in (big["x1"], big["x2"]):
        for v in (big["z1"], big["z2"]):
            s.fill((u, deck_y + 1, v), (u, deck_y + 6, v), "dark_oak_log[axis=y]")
    for u in range(big["x1"] + 2, big["x2"] - 1, 3):
        for v in (big["z1"], big["z2"]):
            s.fill((u, deck_y + 2, v), (u, deck_y + 4, v), "glass_pane")
    gable_end(s, big, deck_y + 7, "x", "white_terracotta")
    gable(s, big, deck_y + 6, "x", "dark_oak_planks", "dark_oak_stairs")
    small = dict(x1=-9, x2=-3, z1=-3, z2=3)
    shell(s, small, deck_y + 4, "white_terracotta", deck_y, plinth="spruce_planks")
    gable_end(s, small, deck_y + 5, "x", "white_terracotta")
    gable(s, small, deck_y + 4, "x", "dark_oak_planks", "dark_oak_stairs")
    s.fill((small["x2"], deck_y + 1, 0), (small["x2"], deck_y + 2, 0), "air")

    # Chimneys, each trailing a plume of cloud downwind.
    for u, v, h in ((2, -2, 12), (5, 2, 14), (9, 0, 10)):
        s.fill((u, deck_y + 1, v), (u, deck_y + h, v), "copper_block")
        s.block((u, deck_y + h + 1, v), "waxed_copper_block")
        for i in range(1, 9):
            s.fill((u - i, deck_y + h + 1 + i, v - i // 3),
                   (u - i + 1, deck_y + h + 2 + i, v + i // 3), "white_wool")

    # Wings and paddle wheels along the flanks, and a rudder at the stern.
    for side in (-1, 1):
        v = side * (beam // 2)
        for i, u in enumerate(range(-14, 12, 2)):
            s.fill((u, deck_y - 2, v), (u, deck_y - 2, v + side * 4), "white_wool")
            s.fill((u, deck_y - 3, v + side * 4), (u, deck_y - 2, v + side * 6),
                   "spruce_planks")
        for cu in (-8, 4):
            for i, (a, b) in enumerate(ring_cells(0, 0, 4)):
                s.block((cu + a, deck_y - 1 + b, v + side), "stripped_dark_oak_wood")
            s.fill((cu, deck_y - 1, v + side), (cu, deck_y - 1, v + side * 2),
                   "dark_oak_log")
    s.fill((16, deck_y - 2, 0), (20, deck_y + 2, 0), "spruce_planks")
    s.fill((17, deck_y - 4, -3), (19, deck_y - 4, 3), "spruce_planks")
    s.fill((-18, deck_y - 1, 0), (-21, deck_y + 1, 0), "spruce_planks")
    s.fill((-20, deck_y + 2, -2), (-20, deck_y + 2, 2), "white_wool")

    # Lights, and a flag at the bow.
    for u, v in ((-6, -5), (-6, 5), (10, -5), (10, 5), (0, 0)):
        s.block((u, deck_y + 1, v), "lantern")
    for i in (1, 2):
        s.block((-16, deck_y + i, 0), "spruce_fence")
    s.fill((-16, deck_y + 3, 0), (-16, deck_y + 5, 0), "spruce_fence")
    s.fill((-15, deck_y + 4, 0), (-13, deck_y + 5, 0), "red_wool")
    # Lanterns hung under the hull, as the picture has them.
    for u in (-10, -4, 6):
        s.fill((u, keel - 1, 0), (u, keel - 3, 0), "iron_chain")
        s.block((u, keel - 4, 0), "lantern[hanging=true]")


BUILDS = {"mlyn": mlyn, "chata": chata, "strom": strom,
          "carodejnice": carodejnice, "koloseum": koloseum, "hrad": hrad,
          "lod": lod, "vzducholod": vzducholod}


# --- the map -----------------------------------------------------------------

MARKERS = os.path.join(os.path.dirname(HERE), "admin-api", "landmarks.json")


def write_markers():
    """Write the list the map marks the landmarks with.

    squaremap rewrites its own markers.json whenever it updates, so this is
    not that file: admin-api merges this one into what it serves. The
    coordinates are the ones the builds are put up at, so the map and the
    plan cannot drift apart.
    """
    import json
    out = [dict(name=name, x=SITES[name]["at"][0], z=SITES[name]["at"][1],
                label=SITES[name]["label"], note=SITES[name]["note"])
           for name in BUILDS]
    out.append(dict(name="micov", x=50, z=-63, label="Míčov",
                    note="kostel sv. Matouše, hřbitov a fara"))
    with open(MARKERS, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"zapsano {len(out)} znacek do {MARKERS}")


def main():
    # The site labels are Czech and the console here is not UTF-8 by default.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", nargs="*", default=list(BUILDS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--markers", action="store_true",
                    help="write the map marker list and build nothing")
    a = ap.parse_args()
    if a.markers:
        write_markers()
        return
    for name in a.sites:
        if name not in BUILDS:
            sys.exit(f"unknown site {name!r}; known: {', '.join(BUILDS)}")
        print(f"-- {name}  ({SITES[name]['label']}, {SITES[name]['at']})")
        s = Session(origin=SITES[name]["at"])
        BUILDS[name](s, survey(name))
        s.flush(dry_run=a.dry_run)


if __name__ == "__main__":
    main()
