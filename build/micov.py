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
Y     = 89                              # churchyard level
PAD   = (-36, -4, -8, 30)               # flat ground: x1, z1, x2, z2
BLEND = 14                              # blocks over which the cut eases out

# Nave running east-west, centred on the knoll.
NAVE  = dict(x1=-32, x2=-12, z1=4, z2=18)
# Tower stands against the south wall near the east end, over the entrance -
# not on the nave axis.
TOWER = dict(x1=-18, x2=-12, z1=18, z2=24)
PORCH = dict(x1=-17, x2=-13, z1=24, z2=26)
# Sacristy: a lower annexe on the north side, deliberately well below the nave.
ANNEX = dict(x1=-20, x2=-12, z1=0, z2=4)

WALL_TOP  = Y + 8
RIDGE     = Y + 15
ANNEX_TOP = Y + 5
TOWER_TOP = Y + 18
SPIRE_TOP = TOWER_TOP + 11


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


def church(s):
    n, t, p, a = NAVE, TOWER, PORCH, ANNEX
    cz = (n["z1"] + n["z2"]) // 2

    _shell(s, n, WALL_TOP, RENDER, floor_y=Y)

    # Buttresses punctuating both long walls.
    for x in range(n["x1"] + 2, n["x2"] - 1, 4):
        for z, dz in ((n["z1"], -1), (n["z2"], 1)):
            s.fill((x, Y, z + dz), (x, WALL_TOP - 1, z + dz), DRESSING)

    # Pointed lights between them.
    for x in range(n["x1"] + 4, n["x2"] - 2, 4):
        for z in (n["z1"], n["z2"]):
            s.fill((x, Y + 4, z), (x + 1, Y + 7, z), GLASS)
            s.fill((x, Y + 8, z), (x + 1, Y + 8, z), DRESSING)

    # West gable and its rose window.
    gx = n["x1"]
    for i in range(8):
        zi, zo = n["z1"] + i, n["z2"] - i
        if zi > zo:
            break
        s.fill((gx, WALL_TOP + i, zi), (gx, WALL_TOP + i, zo), RENDER)
    s.fill((gx, WALL_TOP + 2, cz - 1), (gx, WALL_TOP + 4, cz + 1), GLASS)
    s.block((gx, WALL_TOP + 3, cz), DRESSING)

    # Nave roof.
    for i in range(8):
        y = WALL_TOP + 1 + i
        zn, zs = n["z1"] + i, n["z2"] - i
        if zn > zs:
            break
        s.fill((n["x1"], y, zn), (n["x2"], y, zn), f"{ROOF_STAIR}[facing={DOWN_N}]")
        s.fill((n["x1"], y, zs), (n["x2"], y, zs), f"{ROOF_STAIR}[facing={DOWN_S}]")
        if zn + 1 <= zs - 1:
            s.fill((n["x1"], y, zn + 1), (n["x2"], y, zs - 1), "air")
    s.fill((n["x1"], RIDGE, cz), (n["x2"], RIDGE, cz), ROOF)

    # Sacristy: low annexe on the north side, its ridge well under the nave eaves.
    _shell(s, a, ANNEX_TOP, RENDER, floor_y=Y)
    acz = (a["x1"] + a["x2"]) // 2
    for i in range(3):
        y = ANNEX_TOP + 1 + i
        zn, zs = a["z1"] + i, a["z2"] - i
        if zn > zs:
            break
        s.fill((a["x1"], y, zn), (a["x2"], y, zn), f"{ROOF_STAIR}[facing={DOWN_N}]")
        s.fill((a["x1"], y, zs), (a["x2"], y, zs), f"{ROOF_STAIR}[facing={DOWN_S}]")
    s.fill((a["x1"] + 2, Y + 2, a["z1"]), (a["x1"] + 3, Y + 4, a["z1"]), GLASS)
    s.fill((a["x1"] + 3, Y + 1, n["z1"]), (a["x1"] + 4, Y + 3, n["z1"]), "air")

    # Tower against the south wall, over the entrance.
    _shell(s, t, TOWER_TOP, RENDER, floor_y=Y)
    for x in (t["x1"], t["x2"]):
        for z in (t["z1"], t["z2"]):
            s.fill((x, Y, z), (x, TOWER_TOP, z), DRESSING)
    tmx, tmz = (t["x1"] + t["x2"]) // 2, (t["z1"] + t["z2"]) // 2
    b1, b2 = TOWER_TOP - 5, TOWER_TOP - 2
    s.fill((tmx - 1, b1, t["z2"]), (tmx + 1, b2, t["z2"]), GLASS)
    s.fill((t["x1"], b1, tmz - 1), (t["x1"], b2, tmz + 1), GLASS)
    s.fill((t["x2"], b1, tmz - 1), (t["x2"], b2, tmz + 1), GLASS)
    # Open the tower into the nave.
    s.fill((tmx - 1, Y + 1, n["z2"]), (tmx + 1, Y + 4, n["z2"]), "air")

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

    # Entrance porch at the tower foot.
    s.walls((p["x1"], Y, p["z1"]), (p["x2"], Y + 4, p["z2"]), RENDER)
    s.fill((p["x1"] + 1, Y, p["z1"]), (p["x2"] - 1, Y + 3, p["z2"] - 1), "air")
    s.fill((p["x1"], Y + 5, p["z1"]), (p["x2"], Y + 5, p["z2"]), ROOF)
    s.fill((p["x1"] + 1, Y + 1, p["z2"]), (p["x2"] - 1, Y + 3, p["z2"]), "air")
    s.fill((p["x1"] + 1, Y + 1, t["z2"]), (p["x2"] - 1, Y + 3, t["z2"]), "air")


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
