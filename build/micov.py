#!/usr/bin/env python3
"""Build Míčov - the church of St Matthew, its graveyard, and the parish house.

Sited on the knoll ~25 blocks north-west of spawn, whose top stands 17 blocks
above the surrounding ground (tools/terrain_survey.py). The real church and
parish house sit on comparable ground; here the church takes the high point and
the parish house the slope below it, because levelling 30 blocks of hill would
cost more than the accuracy is worth - and a village church on a rise is hardly
unfaithful.

Distances and orientation follow the map: nave running east-west with the tower
at its east end, graveyard wrapped around it, parish house about sixty blocks
east across the road, with the workshop and washroom north of it.

Run with --dry-run to count commands without touching the world.
"""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from mc import Session

# --- palette ----------------------------------------------------------------
# Chosen off the photographs: ochre render, grey stone dressings, red sheet
# roof, and a spire of verdigris copper - which Minecraft happens to have
# exactly, as oxidized_copper.
RENDER      = "smooth_sandstone"        # ochre walls
DRESSING    = "andesite"                # grey buttresses and quoins
PLINTH      = "cobblestone"             # stone base course
ROOF        = "bricks"                  # red sheet roof
ROOF_STAIR  = "brick_stairs"
SPIRE       = "oxidized_copper"
SPIRE_STAIR = "oxidized_cut_copper_stairs"
GLASS       = "black_stained_glass_pane"
FLOOR       = "polished_andesite"

# Which way a roof stair points when the surface descends towards -z (north).
# If the roof comes out inverted, flip these two and rebuild.
DOWN_N, DOWN_S = "north", "south"

# --- geometry ---------------------------------------------------------------
Y = 90                     # churchyard platform level

NAVE = dict(x1=-36, x2=-14, z1=4, z2=18)   # 23 x 15 outer
TOWER = dict(x1=-13, x2=-7, z1=8, z2=14)   # 7 x 7, east end
PORCH = dict(x1=-21, x2=-17, z1=18, z2=21)

WALL_TOP   = Y + 8         # eaves
RIDGE      = Y + 15
TOWER_TOP  = Y + 18
SPIRE_TOP  = TOWER_TOP + 11


def terrain(s):
    """Cut and fill the knoll into a churchyard terrace."""
    s.platform(-44, -2, -1, 26, Y, "grass_block", "dirt", depth=8)
    # A retaining edge so the terrace reads as built, not as a floating slab.
    s.walls((-44, Y - 6, -2), (-1, Y, 26), PLINTH)


def church(s):
    n, t, p = NAVE, TOWER, PORCH

    # Nave: plinth, walls, then hollow it out.
    s.fill((n["x1"], Y, n["z1"]), (n["x2"], Y + 1, n["z2"]), PLINTH)
    s.walls((n["x1"], Y + 2, n["z1"]), (n["x2"], WALL_TOP, n["z2"]), RENDER)
    s.fill((n["x1"] + 1, Y + 1, n["z1"] + 1),
           (n["x2"] - 1, WALL_TOP, n["z2"] - 1), "air")
    s.fill((n["x1"] + 1, Y, n["z1"] + 1), (n["x2"] - 1, Y, n["z2"] - 1), FLOOR)

    # Buttresses: the grey pilasters that punctuate both long walls.
    for x in range(n["x1"] + 2, n["x2"] - 1, 4):
        for z in (n["z1"], n["z2"]):
            dz = -1 if z == n["z1"] else 1
            s.fill((x, Y, z + dz), (x, WALL_TOP - 1, z + dz), DRESSING)

    # Windows: tall pointed lights between the buttresses.
    for x in range(n["x1"] + 4, n["x2"] - 2, 4):
        for z in (n["z1"], n["z2"]):
            s.fill((x, Y + 4, z), (x + 1, Y + 7, z), GLASS)
            s.fill((x, Y + 8, z), (x + 1, Y + 8, z), DRESSING)

    # West gable with its rose window.
    gx = n["x1"]
    for i in range(0, 8):
        z_in = n["z1"] + i
        z_out = n["z2"] - i
        if z_in > z_out:
            break
        s.fill((gx, WALL_TOP + i, z_in), (gx, WALL_TOP + i, z_out), RENDER)
    cz = (n["z1"] + n["z2"]) // 2
    s.fill((gx, WALL_TOP + 2, cz - 1), (gx, WALL_TOP + 4, cz + 1), GLASS)
    s.block((gx, WALL_TOP + 3, cz), DRESSING)

    # Gable roof: eaves at the wall head, ridge down the middle.
    for i in range(0, 8):
        y = WALL_TOP + 1 + i
        zn, zs = n["z1"] + i, n["z2"] - i
        if zn > zs:
            break
        s.fill((n["x1"], y, zn), (n["x2"], y, zn),
               f"{ROOF_STAIR}[facing={DOWN_N}]")
        s.fill((n["x1"], y, zs), (n["x2"], y, zs),
               f"{ROOF_STAIR}[facing={DOWN_S}]")
        if zn + 1 <= zs - 1:
            s.fill((n["x1"], y, zn + 1), (n["x2"], y, zs - 1), "air")
    s.fill((n["x1"], RIDGE, cz), (n["x2"], RIDGE, cz), ROOF)

    # Tower at the east end.
    s.fill((t["x1"], Y, t["z1"]), (t["x2"], Y + 1, t["z2"]), PLINTH)
    s.walls((t["x1"], Y + 2, t["z1"]), (t["x2"], TOWER_TOP, t["z2"]), RENDER)
    s.fill((t["x1"] + 1, Y + 1, t["z1"] + 1),
           (t["x2"] - 1, TOWER_TOP, t["z2"] - 1), "air")
    for x in (t["x1"], t["x2"]):
        for z in (t["z1"], t["z2"]):
            s.fill((x, Y, z), (x, TOWER_TOP, z), DRESSING)      # quoins
    # Belfry openings, one to each face.
    b1, b2 = TOWER_TOP - 5, TOWER_TOP - 2
    mid_x, mid_z = (t["x1"] + t["x2"]) // 2, (t["z1"] + t["z2"]) // 2
    s.fill((mid_x - 1, b1, t["z1"]), (mid_x + 1, b2, t["z1"]), GLASS)
    s.fill((mid_x - 1, b1, t["z2"]), (mid_x + 1, b2, t["z2"]), GLASS)
    s.fill((t["x2"], b1, mid_z - 1), (t["x2"], b2, mid_z + 1), GLASS)
    s.fill((t["x1"], b1, mid_z - 1), (t["x1"], b2, mid_z + 1), GLASS)

    # Spire: a copper pyramid drawn in from all four sides.
    x1, x2, z1, z2 = t["x1"], t["x2"], t["z1"], t["z2"]
    s.fill((x1, TOWER_TOP + 1, z1), (x2, TOWER_TOP + 1, z2), SPIRE)
    y = TOWER_TOP + 2
    while x1 <= x2 and z1 <= z2 and y <= SPIRE_TOP:
        s.walls((x1, y, z1), (x2, y, z2), SPIRE)
        x1, x2, z1, z2 = x1 + 1, x2 - 1, z1 + 1, z2 - 1
        y += 1
    s.fill((mid_x, y, mid_z), (mid_x, SPIRE_TOP + 1, mid_z), SPIRE)
    # Cross.
    s.block((mid_x, SPIRE_TOP + 2, mid_z), "iron_bars")
    s.block((mid_x, SPIRE_TOP + 3, mid_z), "iron_bars")
    s.fill((mid_x, SPIRE_TOP + 3, mid_z - 1), (mid_x, SPIRE_TOP + 3, mid_z + 1),
           "iron_bars")

    # South porch with its own little roof.
    s.walls((p["x1"], Y, p["z1"]), (p["x2"], Y + 4, p["z2"]), RENDER)
    s.fill((p["x1"] + 1, Y, p["z1"]), (p["x2"] - 1, Y + 3, p["z2"] - 1), "air")
    s.fill((p["x1"], Y + 5, p["z1"]), (p["x2"], Y + 5, p["z2"]), ROOF)
    s.fill((p["x1"] + 1, Y, p["z2"]), (p["x2"] - 1, Y + 2, p["z2"]), "air")
    # And a doorway through the nave wall behind it.
    s.fill((p["x1"] + 1, Y + 1, n["z2"]), (p["x2"] - 1, Y + 3, n["z2"]), "air")


STAGES = {"terrain": terrain, "church": church}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stages", nargs="*", default=list(STAGES),
                    help="which stages to build (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    s = Session()
    for name in a.stages:
        if name not in STAGES:
            sys.exit(f"unknown stage {name!r}; known: {', '.join(STAGES)}")
        print(f"-- {name}")
        STAGES[name](s)
    s.flush(dry_run=a.dry_run)


if __name__ == "__main__":
    main()
