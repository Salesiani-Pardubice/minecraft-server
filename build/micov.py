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

# Facing for a roof stair where the surface descends towards -z / +z.
# Flip these two if the pitch comes out inverted.
DOWN_N, DOWN_S = "north", "south"

# --- geometry ---------------------------------------------------------------
# Footprint traced from the annotated map: a cruciform plan, not a plain nave.
# The tower stands at the south-west corner with the entrance porch on the west
# gable beside it; a pair of side-altar chapels face each other across the nave
# and the sacristy adjoins the northern one on its east side.
Y     = 89                              # churchyard level
PAD   = (-42, -2, -6, 26)               # flat ground: x1, z1, x2, z2
BLEND = 14                              # blocks over which the cut eases out

NAVE    = dict(x1=-36, x2=-9,  z1=6,  z2=15)   # 1. hlavní loď
TOWER   = dict(x1=-36, x2=-32, z1=16, z2=20)   # 2. věž, jihozápad
PORCH   = dict(x1=-39, x2=-37, z1=9,  z2=12)   # 3. předsíň se vchodem, západ
ALTAR_S = dict(x1=-23, x2=-16, z1=16, z2=21)   # 4. boční oltář k jihu
ALTAR_N = dict(x1=-23, x2=-16, z1=1,  z2=6)    # 5. boční oltář k severu
SACRIST = dict(x1=-15, x2=-11, z1=1,  z2=6)    # 6. sakristie

WALL_TOP   = Y + 8          # nave eaves
CHAPEL_TOP = Y + 7          # side altars sit just under the nave
SACRIST_TOP = Y + 5         # sacristy lower again
TOWER_TOP  = Y + 18
SPIRE_TOP  = TOWER_TOP + 11


def load_heights():
    """Surface heights around the site, read from the region files."""
    subprocess.run(["docker", "exec", "-i", "minecraft-server", "rcon-cli",
                    "save-all flush"], capture_output=True, text=True)
    cx = (PAD[0] + PAD[2]) // 2
    cz = (PAD[1] + PAD[3]) // 2
    radius = max(PAD[2] - PAD[0], PAD[3] - PAD[1]) // 2 + BLEND + 6
    return build_grid((cx, cz), radius)


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

    Courses are laid from both eaves inwards until they meet, so the pitch is
    45 degrees and the ridge lands wherever the span puts it.
    """
    if along == "x":
        lo, hi, fixed = b["z1"], b["z2"], (b["x1"], b["x2"])
    else:
        lo, hi, fixed = b["x1"], b["x2"], (b["z1"], b["z2"])
    for i in range((hi - lo) // 2 + 2):
        y = eaves + 1 + i
        a, c = lo + i, hi - i
        if a > c:
            break
        if along == "x":
            s.fill((fixed[0], y, a), (fixed[1], y, a), f"{ROOF_STAIR}[facing={DOWN_N}]")
            s.fill((fixed[0], y, c), (fixed[1], y, c), f"{ROOF_STAIR}[facing={DOWN_S}]")
            if a + 1 <= c - 1:
                s.fill((fixed[0], y, a + 1), (fixed[1], y, c - 1), "air")
        else:
            s.fill((a, y, fixed[0]), (a, y, fixed[1]), f"{ROOF_STAIR}[facing=west]")
            s.fill((c, y, fixed[0]), (c, y, fixed[1]), f"{ROOF_STAIR}[facing=east]")
            if a + 1 <= c - 1:
                s.fill((a + 1, y, fixed[0]), (c - 1, y, fixed[1]), "air")
    return y


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
    _shell(s, p, Y + 4, RENDER)
    _fill_gable_end(s, p, Y + 5, "z", RENDER)
    _gable(s, p, Y + 4, "z")
    s.fill((p["x1"], Y + 1, p["z1"] + 1), (p["x1"], Y + 3, p["z2"] - 1), "air")
    s.fill((n["x1"], Y + 1, p["z1"] + 1), (n["x1"], Y + 3, p["z2"] - 1), "air")


STAGES = {"terrain": terrain, "church": church}


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
