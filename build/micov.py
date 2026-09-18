#!/usr/bin/env python3
"""Build Míčov - the church of St Matthew, its graveyard, and the parish house.

Sited on the knoll ~25 blocks north-west of spawn, whose top stands 17 blocks
above the surrounding ground (tools/terrain_survey.py).

The churchyard is cut into the hill rather than raised on a retaining wall: the
target ground level is flat over the pad and eases out to the real hillside
over a dozen blocks, so the place sits in the slope instead of on it.

Run with --dry-run to count commands without touching the world.
"""

import argparse
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mc import Session
from terrain_survey import build_grid

# --- palette ----------------------------------------------------------------
RENDER      = "smooth_sandstone"        # ochre walls
DRESSING    = "andesite"                # grey buttresses and quoins
PLINTH      = "cobblestone"
ROOF        = "bricks"
ROOF_STAIR  = "brick_stairs"
SPIRE       = "oxidized_copper"
GLASS       = "black_stained_glass_pane"
FLOOR       = "polished_andesite"

# Stair facings for a roof course, by which side of the ridge it is on.
# A stair "faces" the direction it descends towards, which is the opposite of
# what reads naturally when writing the loop - the first attempt had every
# pitch inverted, and an inverted pitch leaks rain.
DOWN_N, DOWN_S = "south", "north"
DOWN_W, DOWN_E = "east", "west"

# --- geometry ---------------------------------------------------------------
# Footprint traced from the annotated map: a cruciform plan, not a plain nave.
# The tower stands at the south-west corner with the entrance porch on the west
# gable beside it; a pair of side-altar chapels face each other across the nave
# and the sacristy adjoins the northern one on its east side.
Y     = 89                              # churchyard level
PAD   = (-44, -4, -4, 28)               # flat ground: x1, z1, x2, z2
BLEND = 26                              # blocks over which the cut eases out

NAVE    = dict(x1=-36, x2=-9,  z1=6,  z2=15)   # 1. hlavní loď
TOWER   = dict(x1=-36, x2=-32, z1=16, z2=20)   # 2. věž, jihozápad
PORCH   = dict(x1=-39, x2=-37, z1=9,  z2=12)   # 3. předsíň se vchodem, západ
ALTAR_S = dict(x1=-23, x2=-16, z1=16, z2=21)   # 4. boční oltář k jihu
ALTAR_N = dict(x1=-23, x2=-16, z1=1,  z2=6)    # 5. boční oltář k severu
SACRIST = dict(x1=-15, x2=-11, z1=1,  z2=6)    # 6. sakristie

WALL_TOP    = Y + 11        # nave eaves
CHAPEL_TOP  = Y + 9         # side altars sit just under the nave
SACRIST_TOP = Y + 7         # sacristy lower again
PORCH_TOP   = Y + 5
TOWER_TOP   = Y + 22
SPIRE_TOP   = TOWER_TOP + 6


def load_heights():
    """Surface heights around the site, read from the region files."""
    subprocess.run(["docker", "exec", "-i", "minecraft-server", "rcon-cli",
                    "save-all flush"], capture_output=True, text=True)
    # Wide enough to cover spawn, the church, and the route between them.
    return build_grid((-24, 8), 60)


def target_height(x, z, grid):
    """Flat on the pad, easing to the real hillside outside it."""
    x1, z1, x2, z2 = PAD
    d = max(max(x1 - x, 0, x - x2), max(z1 - z, 0, z - z2))
    if d == 0:
        return Y
    nat = grid.get((x, z))
    if nat is None:
        return None
    t = min(d / BLEND, 1.0)
    t = t * t * (3 - 2 * t)                      # smoothstep
    return round(Y * (1 - t) + nat * t)


def terrain(s):
    grid = load_heights()
    x1, z1, x2, z2 = PAD
    for z in range(z1 - BLEND, z2 + BLEND + 1):
        run = None                               # ((target, natural), xa, xb)
        for x in range(x1 - BLEND, x2 + BLEND + 1):
            nat = grid.get((x, z))
            key = (target_height(x, z, grid), nat)
            if key[0] is None or nat is None:
                if run:
                    _column(s, z, *run)
                run = None
                continue
            if run and run[0] == key:
                run = (key, run[1], x)
            else:
                if run:
                    _column(s, z, *run)
                run = (key, x, x)
        if run:
            _column(s, z, *run)


def _column(s, z, key, xa, xb):
    """Raise or cut one run of columns to its target, then cap it with turf."""
    tgt, nat = key
    if tgt > nat:
        s.fill((xa, nat, z), (xb, tgt - 1, z), "dirt")
    elif tgt < nat:
        s.fill((xa, tgt + 1, z), (xb, nat + 26, z), "air")
    s.fill((xa, tgt, z), (xb, tgt, z), "grass_block")


def _shell(s, b, top, wall, floor_y=None):
    """Plinth, walls, hollow interior."""
    s.fill((b["x1"], Y, b["z1"]), (b["x2"], Y + 1, b["z2"]), PLINTH)
    s.walls((b["x1"], Y + 2, b["z1"]), (b["x2"], top, b["z2"]), wall)
    s.fill((b["x1"] + 1, Y + 1, b["z1"] + 1), (b["x2"] - 1, top, b["z2"] - 1), "air")
    if floor_y is not None:
        s.fill((b["x1"] + 1, floor_y, b["z1"] + 1),
               (b["x2"] - 1, floor_y, b["z2"] - 1), FLOOR)


def _gable(s, b, eaves, along):
    """A pitched roof over b, ridge running along 'x' or 'z'.

    Courses are laid inward from both eaves. The last one or two courses are
    solid blocks rather than stairs: a pair of opposing stairs meeting at the
    apex leaves a hole, which is how rain gets in.
    """
    if along == "x":
        lo, hi, f1, f2 = b["z1"], b["z2"], b["x1"], b["x2"]
        low_face, high_face = DOWN_N, DOWN_S
    else:
        lo, hi, f1, f2 = b["x1"], b["x2"], b["z1"], b["z2"]
        low_face, high_face = DOWN_W, DOWN_E

    def row(v, y, block):
        if along == "x":
            s.fill((f1, y, v), (f2, y, v), block)
        else:
            s.fill((v, y, f1), (v, y, f2), block)

    def clear(a, c, y):
        if a + 1 > c - 1:
            return
        if along == "x":
            s.fill((f1, y, a + 1), (f2, y, c - 1), "air")
        else:
            s.fill((a + 1, y, f1), (c - 1, y, f2), "air")

    i = 0
    while True:
        y, a, c = eaves + 1 + i, lo + i, hi - i
        if a > c:
            break
        if c - a <= 1:                       # ridge course, solid
            row(a, y, ROOF)
            if c != a:
                row(c, y, ROOF)
            break
        row(a, y, f"{ROOF_STAIR}[facing={low_face}]")
        row(c, y, f"{ROOF_STAIR}[facing={high_face}]")
        clear(a, c, y)
        i += 1
    return eaves + 1 + i


def _fill_gable_end(s, b, eaves, along, wall):
    """Close the triangular ends under a pitched roof."""
    if along == "x":
        lo, hi = b["z1"], b["z2"]
        for i in range((hi - lo) // 2 + 2):
            a, c = lo + i, hi - i
            if a > c:
                break
            for x in (b["x1"], b["x2"]):
                s.fill((x, eaves + i, a), (x, eaves + i, c), wall)
    else:
        lo, hi = b["x1"], b["x2"]
        for i in range((hi - lo) // 2 + 2):
            a, c = lo + i, hi - i
            if a > c:
                break
            for z in (b["z1"], b["z2"]):
                s.fill((a, eaves + i, z), (c, eaves + i, z), wall)


def church(s):
    n, t, p = NAVE, TOWER, PORCH
    aS, aN, sac = ALTAR_S, ALTAR_N, SACRIST
    cz = (n["z1"] + n["z2"]) // 2

    # 1. Nave.
    _shell(s, n, WALL_TOP, RENDER, floor_y=Y)
    _fill_gable_end(s, n, WALL_TOP + 1, "x", RENDER)
    _gable(s, n, WALL_TOP, "x")

    # Buttresses and pointed lights along both long walls.
    for x in range(n["x1"] + 3, n["x2"] - 1, 4):
        for z, dz in ((n["z1"], -1), (n["z2"], 1)):
            s.fill((x, Y, z + dz), (x, WALL_TOP - 1, z + dz), DRESSING)
    for x in range(n["x1"] + 5, n["x2"] - 2, 4):
        for z in (n["z1"], n["z2"]):
            s.fill((x, Y + 4, z), (x, Y + 7, z), GLASS)
            s.block((x, Y + 8, z), DRESSING)

    # Rose window in the east gable, opposite the entrance.
    s.fill((n["x2"], WALL_TOP + 2, cz - 1), (n["x2"], WALL_TOP + 4, cz + 1), GLASS)
    s.block((n["x2"], WALL_TOP + 3, cz), DRESSING)

    # 4. + 5. Side altars, facing each other; ridges run north-south.
    for chapel, open_z in ((aS, n["z2"]), (aN, n["z1"])):
        _shell(s, chapel, CHAPEL_TOP, RENDER, floor_y=Y)
        _fill_gable_end(s, chapel, CHAPEL_TOP + 1, "z", RENDER)
        _gable(s, chapel, CHAPEL_TOP, "z")
        far = chapel["z2"] if open_z == n["z1"] else chapel["z1"]
        s.fill((chapel["x1"] + 2, Y + 3, far), (chapel["x2"] - 2, Y + 6, far), GLASS)
        # Open the chapel into the nave.
        s.fill((chapel["x1"] + 2, Y + 1, open_z), (chapel["x2"] - 2, Y + 5, open_z), "air")

    # 6. Sacristy, lower again.
    _shell(s, sac, SACRIST_TOP, RENDER, floor_y=Y)
    _fill_gable_end(s, sac, SACRIST_TOP + 1, "z", RENDER)
    _gable(s, sac, SACRIST_TOP, "z")
    s.fill((sac["x1"] + 1, Y + 2, sac["z1"]), (sac["x2"] - 1, Y + 4, sac["z1"]), GLASS)
    s.fill((sac["x1"] + 1, Y + 1, n["z1"]), (sac["x2"] - 1, Y + 3, n["z1"]), "air")

    # 2. Tower at the south-west corner.
    _shell(s, t, TOWER_TOP, RENDER, floor_y=Y)
    for x in (t["x1"], t["x2"]):
        for z in (t["z1"], t["z2"]):
            s.fill((x, Y, z), (x, TOWER_TOP, z), DRESSING)
    tmx, tmz = (t["x1"] + t["x2"]) // 2, (t["z1"] + t["z2"]) // 2
    b1, b2 = TOWER_TOP - 5, TOWER_TOP - 2
    s.fill((tmx, b1, t["z2"]), (tmx, b2, t["z2"]), GLASS)
    s.fill((t["x1"], b1, tmz), (t["x1"], b2, tmz), GLASS)
    s.fill((t["x2"], b1, tmz), (t["x2"], b2, tmz), GLASS)
    s.fill((tmx, Y + 1, t["z1"]), (tmx, Y + 4, t["z1"]), "air")   # into the nave

    # Spire.
    x1, x2, z1, z2 = t["x1"], t["x2"], t["z1"], t["z2"]
    s.fill((x1, TOWER_TOP + 1, z1), (x2, TOWER_TOP + 1, z2), SPIRE)
    y = TOWER_TOP + 2
    while x1 <= x2 and z1 <= z2 and y <= SPIRE_TOP:
        s.walls((x1, y, z1), (x2, y, z2), SPIRE)
        x1, x2, z1, z2, y = x1 + 1, x2 - 1, z1 + 1, z2 - 1, y + 1
    s.fill((tmx, y, tmz), (tmx, SPIRE_TOP + 1, tmz), SPIRE)
    s.fill((tmx, SPIRE_TOP + 2, tmz), (tmx, SPIRE_TOP + 3, tmz), "iron_bars")
    s.fill((tmx, SPIRE_TOP + 3, tmz - 1), (tmx, SPIRE_TOP + 3, tmz + 1), "iron_bars")

    # 3. Entrance porch on the west gable.
    _shell(s, p, PORCH_TOP, RENDER)
    _fill_gable_end(s, p, PORCH_TOP + 1, "z", RENDER)
    _gable(s, p, PORCH_TOP, "z")
    s.fill((p["x1"], Y + 1, p["z1"] + 1), (p["x1"], Y + 3, p["z2"] - 1), "air")
    s.fill((n["x1"], Y + 1, p["z1"] + 1), (n["x1"], Y + 3, p["z2"] - 1), "air")



# --- the rest of the scene ---------------------------------------------------

SPAWN = (0, 0)                  # world spawn, where the path starts
# Round the churchyard, then along the south side to the west porch.
ROUTE = [SPAWN, (-4, 6), (-10, 14), (-18, 24), (-30, 25), (-40, 20), (-41, 11)]


def _surface(x, z, grid):
    """Ground level after the terrace has been cut - the path follows this."""
    return target_height(x, z, grid)


def trees(s):
    """Scatter oaks over the slope, leaving the churchyard itself clear."""
    x1, z1, x2, z2 = PAD
    o = 6                                    # keep this much clear round the pad
    lo_y, hi_y = Y - 34, Y + 8
    bands = [
        (x1 - BLEND, z1 - BLEND, x2 + BLEND, z1 - o),      # north
        (x1 - BLEND, z2 + o,     x2 + BLEND, z2 + BLEND),  # south
        (x1 - BLEND, z1 - o,     x1 - o,     z2 + o),      # west
        (x2 + o,     z1 - o,     x2 + BLEND, z2 + o),      # east
    ]
    for bx1, bz1, bx2, bz2 in bands:
        s.sel((bx1, lo_y, bz1), (bx2, hi_y, bz2))
        s.raw("//forest oak 6")


def path(s):
    """A worn track from spawn up to the church door."""
    grid = load_heights()
    seen = set()
    for (ax, az), (bx, bz) in zip(ROUTE, ROUTE[1:]):
        steps = max(abs(bx - ax), abs(bz - az))
        for i in range(steps + 1):
            cx = round(ax + (bx - ax) * i / steps)
            cz = round(az + (bz - az) * i / steps)
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if abs(dx) + abs(dz) > 1:
                        continue
                    x, z = cx + dx, cz + dz
                    if (x, z) in seen:
                        continue
                    seen.add((x, z))
                    y = _surface(x, z, grid)
                    if y is None:
                        continue
                    s.fill((x, y, z), (x, y, z), "dirt_path")
                    s.fill((x, y + 1, z), (x, y + 3, z), "air")


def spawn(s):
    """A little well where players arrive, so spawn is somewhere, not nowhere."""
    grid = load_heights()
    sx, sz = SPAWN
    y = _surface(sx, sz, grid)

    # A swept apron of stone, and level ground under it.
    s.fill((sx - 6, y, sz - 6), (sx + 6, y, sz + 6), "grass_block")
    s.fill((sx - 6, y + 1, sz - 6), (sx + 6, y + 6, sz + 6), "air")
    s.fill((sx - 4, y, sz - 4), (sx + 4, y, sz + 4), "andesite")
    s.fill((sx - 3, y, sz - 3), (sx + 3, y, sz + 3), "polished_andesite")

    # The well itself: a cobble ring round a column of water.
    s.walls((sx - 1, y + 1, sz - 1), (sx + 1, y + 2, sz + 1), "cobblestone")
    s.fill((sx, y - 3, sz), (sx, y + 1, sz), "water")
    for dx, dz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        s.fill((sx + dx, y + 3, sz + dz), (sx + dx, y + 4, sz + dz), "oak_fence")
    s.fill((sx - 1, y + 5, sz - 1), (sx + 1, y + 5, sz + 1), "oak_planks")
    s.fill((sx - 2, y + 5, sz - 2), (sx + 2, y + 5, sz + 2), "oak_slab")
    s.block((sx, y + 6, sz), "lantern")

    # A bench of steps to sit on, facing the church.
    s.fill((sx - 3, y + 1, sz + 3), (sx + 3, y + 1, sz + 3), "cobblestone_slab")


def lights(s):
    """Lanterns on posts along the route, and inside the church."""
    grid = load_heights()

    placed = 0
    for (ax, az), (bx, bz) in zip(ROUTE, ROUTE[1:]):
        steps = max(abs(bx - ax), abs(bz - az))
        for i in range(0, steps + 1, 9):
            cx = round(ax + (bx - ax) * i / steps)
            cz = round(az + (bz - az) * i / steps)
            x, z = cx + 2, cz + 2            # just off the path edge
            y = _surface(x, z, grid)
            if y is None:
                continue
            s.fill((x, y + 1, z), (x, y + 3, z), "oak_fence")
            s.block((x, y + 4, z), "lantern")
            placed += 1

    n, t = NAVE, TOWER
    # Nave: a lantern hung between each pair of buttresses.
    for x in range(n["x1"] + 5, n["x2"] - 2, 4):
        s.block((x, WALL_TOP - 2, (n["z1"] + n["z2"]) // 2), "lantern[hanging=true]")
    # Chapels, sacristy, porch and the tower stair.
    for b, y in ((ALTAR_S, CHAPEL_TOP - 2), (ALTAR_N, CHAPEL_TOP - 2),
                 (SACRIST, SACRIST_TOP - 2), (PORCH, PORCH_TOP - 1)):
        s.block(((b["x1"] + b["x2"]) // 2, y, (b["z1"] + b["z2"]) // 2),
                "lantern[hanging=true]")
    s.block(((t["x1"] + t["x2"]) // 2, Y + 5, (t["z1"] + t["z2"]) // 2),
            "lantern[hanging=true]")
    # Two lanterns flanking the porch door outside.
    for dz in (-1, 1):
        s.block((PORCH["x1"] - 1, Y + 3, (PORCH["z1"] + PORCH["z2"]) // 2 + dz),
                "lantern")


STAGES = {"terrain": terrain, "trees": trees, "church": church,
          "path": path, "spawn": spawn, "lights": lights}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stages", nargs="*", default=list(STAGES))
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
