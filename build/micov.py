#!/usr/bin/env python3
"""Build Míčov: the church of St Matthew in its graveyard, the parish house
with its workshop and washroom, and the orchard across the lane.

Everything is laid out in village-local coordinates traced off the annotated
map - the church centre is the origin, east is +u and south is +v - and the
Session shifts them into the world. Moving the village means editing ORIGIN.

The ground here rises gently from 67 in the east to 71 in the west, so the
churchyard is levelled at 70: it stands the three blocks the plan asks for
above the lane it faces, and cuts a single block into the slope behind. The
step is held by the graveyard's retaining wall rather than by a skirt of
sloped dirt, which is what made the first hill read as earthworks.

Run with --dry-run to count commands without touching the world.
"""

import argparse
import random
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mc import Session
from terrain_survey import ground_grid

# --- where the village sits --------------------------------------------------
ORIGIN = (50, -63)          # church centre, in world coordinates
Y       = 70                # churchyard platform
HOUSE_Y = 71                # parish house floor   (ground 70 here)
WASH_Y  = 67                # washroom and pergola (ground 66)
SHOP_Y  = 66                # workshop             (ground 65)

# --- palette -----------------------------------------------------------------
RENDER      = "smooth_sandstone"        # ochre walls, church and parish house
DRESSING    = "andesite"                # grey buttresses and quoins
PLINTH      = "cobblestone"
ROOF        = "bricks"                  # the church roof is tiled red
ROOF_STAIR  = "brick_stairs"
SLATE       = "deepslate_tiles"         # the parish roofs are dark slate
SLATE_STAIR = "deepslate_tile_stairs"
SLATE_SLAB  = "deepslate_tile_slab"
SPIRE       = "oxidized_copper"
GLASS       = "black_stained_glass_pane"
FLOOR       = "polished_andesite"
PAVING      = "andesite"                # the swept paving round the parish house
LANE        = "dirt_path"

# Stair facings for a roof course, by which side of the ridge it is on.
# A stair "faces" the direction it descends towards, which is the opposite of
# what reads naturally when writing the loop - the first attempt had every
# pitch inverted, and an inverted pitch leaks rain.
DOWN_N, DOWN_S = "south", "north"
DOWN_W, DOWN_E = "east", "west"

# --- the church --------------------------------------------------------------
# A cruciform plan: the tower stands at the south-west corner with the entrance
# porch on the west gable beside it, a pair of side-altar chapels face each
# other across the nave, and the sacristy adjoins the northern one.
NAVE    = dict(x1=-12, x2=15,  z1=-5,  z2=4)    # 1. hlavní loď
TOWER   = dict(x1=-12, x2=-8,  z1=5,   z2=9)    # 2. věž, jihozápad
PORCH   = dict(x1=-15, x2=-13, z1=-2,  z2=1)    # 3. předsíň se vchodem, západ
ALTAR_S = dict(x1=1,   x2=8,   z1=5,   z2=10)   # 4. boční oltář k jihu
ALTAR_N = dict(x1=1,   x2=8,   z1=-10, z2=-5)   # 5. boční oltář k severu
SACRIST = dict(x1=9,   x2=13,  z1=-10, z2=-5)   # 6. sakristie

WALL_TOP    = Y + 11        # nave eaves
CHAPEL_TOP  = Y + 9         # side altars sit just under the nave
SACRIST_TOP = Y + 7         # sacristy lower again
PORCH_TOP   = Y + 5
TOWER_TOP   = Y + 22
SPIRE_TOP   = TOWER_TOP + 6

# --- the ground plan ---------------------------------------------------------
YARD = (-22, -18, 20, 16)   # churchyard platform: u1, v1, u2, v2
CHAMFER = 28                # its north-east corner is cut back off the lane
GATE_E, GATE_W = (20, -4), (-22, -2)        # the two ways into the graveyard


def yard_cells():
    """The churchyard, with the corner the lane runs past cut off it.

    The map draws that edge as a diagonal, and it has to be one: left square,
    the corner of the platform stands in the middle of the lane.
    """
    u1, v1, u2, v2 = YARD
    return {(u, v) for u in range(u1, u2 + 1) for v in range(v1, v2 + 1)
            if u - v <= CHAMFER}


def edge_of(cells):
    """Cells of a region that have a side facing out of it."""
    return {(u, v) for u, v in cells
            if not all((u + du, v + dv) in cells
                       for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1)))}

# The lane, running north-west to south-east past the churchyard, with the
# graveyard on one side of it and the parish plot on the other.
LANE_RUN = [(-45, -64), (-30, -52), (-8, -38), (12, -24), (24, -10),
            (28, 2), (32, 14), (38, 28)]
# The track along the field side of the graveyard.
TRACK = [(-30, -52), (-28, -32), (-27, -12), (-26, 6), (-24, 14)]
# Orange on the map: out of the parish garden, over the lane, in at the east
# gate, along the north side of the church and round to the west porch.
WALK = [(64, -17), (58, -13), (50, -9), (40, -5), (30, -3), (24, -3),
        GATE_E, (12, -13), (0, -14), (-12, -13), (-18, -9), (-18, -2),
        (-16, -1)]

# --- the parish plot ---------------------------------------------------------
HOUSE  = dict(x1=50, x2=68, z1=-14, z2=-3)      # fara, hlavní budova
WING   = dict(x1=50, x2=57, z1=-3,  z2=3)       # její křídlo
WASH   = dict(x1=66, x2=73, z1=-26, z2=-20)     # umývárna
PERGOLA = dict(x1=58, x2=65, z1=-26, z2=-20)    # pergola, navazuje na zídku
SHOP   = dict(x1=72, x2=80, z1=-40, z2=-32)     # dílna
GARDEN_TREE = (56, -15)
SPAWN = (63, -17)                               # the garden, between the three

# The stone wall along the north-west boundary, broken in places. The pergola
# runs up against the middle stretch, which is why that one is dead straight.
STONE_WALL = [[(43, -3), (50, -13), (55, -19)],
              [(58, -26), (67, -26)],
              [(71, -33), (81, -41)]]
# Between the corner of the house and the wall stands a metal railing.
RAILING = [(50, -3), (44, -3)]

ORCHARD = (0, -60, 40, -40)                     # ovocná zahrada, u1 v1 u2 v2
FIRE = (16, -50)


def survey(radius=95):
    """Ground level over the whole village, in local coordinates."""
    subprocess.run(["docker", "exec", "-i", "minecraft-server", "rcon-cli",
                    "save-all flush"], capture_output=True, text=True)
    grid = ground_grid((ORIGIN[0] + 22, ORIGIN[1] - 18), radius)
    return {(x - ORIGIN[0], z - ORIGIN[1]): h for (x, z), h in grid.items()}


def trace(points, width=0):
    """Rasterise a polyline into a set of cells, optionally thickened."""
    cells = set()
    for (au, av), (bu, bv) in zip(points, points[1:]):
        steps = max(abs(bu - au), abs(bv - av))
        for i in range(steps + 1):
            t = i / steps if steps else 0
            u = round(au + (bu - au) * t)
            v = round(av + (bv - av) * t)
            for du in range(-width, width + 1):
                for dv in range(-width, width + 1):
                    if abs(du) + abs(dv) <= width:
                        cells.add((u + du, v + dv))
    return cells


# --- ground ------------------------------------------------------------------

def _column(s, v, key, ua, ub):
    """Raise or cut one run of columns to its target, then cap it with turf."""
    tgt, nat, top = key
    if tgt > nat:
        s.fill((ua, nat, v), (ub, tgt - 1, v), "dirt")
    elif tgt < nat:
        s.fill((ua, tgt + 1, v), (ub, nat + 24, v), "air")
    s.fill((ua, tgt, v), (ub, tgt, v), top)


def level(s, grid, box, y, top="grass_block", blend=0, cells=None):
    """Flatten a footprint to y, easing out over `blend` blocks if asked.

    Runs of equal (target, natural) are filled in one command; a 43 by 35
    churchyard is a few hundred commands rather than fifteen hundred.
    """
    u1, v1, u2, v2 = box
    for v in range(v1 - blend, v2 + blend + 1):
        run = None
        for u in range(u1 - blend, u2 + blend + 1):
            nat = grid.get((u, v))
            d = max(max(u1 - u, 0, u - u2), max(v1 - v, 0, v - v2))
            if cells is not None and d == 0 and (u, v) not in cells:
                nat = None
            if nat is None:
                tgt = None
            elif d == 0:
                tgt = y
            elif blend:
                t = min(d / blend, 1.0)
                t = t * t * (3 - 2 * t)                  # smoothstep
                tgt = round(y * (1 - t) + nat * t)
            else:
                continue
            if tgt is None:
                if run:
                    _column(s, v, *run)
                run = None
                continue
            key = (tgt, nat, top)
            if run and run[0] == key:
                run = (key, run[1], u)
            else:
                if run:
                    _column(s, v, *run)
                run = (key, u, u)
        if run:
            _column(s, v, *run)


def terrain(s, grid=None):
    """Level the churchyard, and a pad under each building of the parish.

    Only ever run this on bare ground. The survey reports the highest solid
    block, and a roof is a solid block, so levelling a site that is already
    built on reads the church as a hill and cuts it down to the platform -
    which is exactly what happened the first time it was run out of order.
    """
    grid = grid or survey()
    standing = grid.get((NAVE["x1"] + 2, NAVE["z1"]))
    if standing is not None and standing > Y + 3:
        sys.exit("terrain: the church is standing at this site - levelling "
                 "would cut it down. Run terrain before church.")
    keep = yard_cells()
    level(s, grid, YARD, Y, cells=keep)

    # The chamfered corner has to be taken back down to the ground that runs
    # on outside the yard - on a rebuild it is still standing at platform
    # level from before the lane showed the clash.
    u1, v1, u2, v2 = YARD
    for v in range(v1, v2 + 1):
        for u in range(u1, u2 + 1):
            if (u, v) in keep:
                continue
            out = [grid.get((u + d, v)) for d in range(1, 8)] + \
                  [grid.get((u, v - d)) for d in range(1, 8)]
            out = [h for h in out if h is not None]
            here = grid.get((u, v))
            if not out or here is None:
                continue
            tgt = min(out)
            if tgt < here:
                s.fill((u, tgt + 1, v), (u, here + 12, v), "air")
            elif tgt > here:
                s.fill((u, here, v), (u, tgt - 1, v), "dirt")
            s.block((u, tgt, v), "grass_block")

    for box, y in ((HOUSE, HOUSE_Y), (WING, HOUSE_Y), (WASH, WASH_Y),
                   (PERGOLA, WASH_Y), (SHOP, SHOP_Y)):
        pad = (box["x1"] - 1, box["z1"] - 1, box["x2"] + 1, box["z2"] + 1)
        level(s, grid, pad, y - 1, blend=3)


# --- the church --------------------------------------------------------------

def _shell(s, b, top, wall, floor_y=None, base=None):
    """Plinth, walls, hollow interior."""
    base = Y if base is None else base
    s.fill((b["x1"], base, b["z1"]), (b["x2"], base + 1, b["z2"]), PLINTH)
    s.walls((b["x1"], base + 2, b["z1"]), (b["x2"], top, b["z2"]), wall)
    s.fill((b["x1"] + 1, base + 1, b["z1"] + 1),
           (b["x2"] - 1, top, b["z2"] - 1), "air")
    if floor_y is not None:
        s.fill((b["x1"] + 1, floor_y, b["z1"] + 1),
               (b["x2"] - 1, floor_y, b["z2"] - 1), FLOOR)


def _gable(s, b, eaves, along, roof=ROOF, stair=ROOF_STAIR):
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

    def row(w, y, block):
        if along == "x":
            s.fill((f1, y, w), (f2, y, w), block)
        else:
            s.fill((w, y, f1), (w, y, f2), block)

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
            row(a, y, roof)
            if c != a:
                row(c, y, roof)
            break
        row(a, y, f"{stair}[facing={low_face}]")
        row(c, y, f"{stair}[facing={high_face}]")
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


# --- the graveyard -----------------------------------------------------------

GRAVE_STONE = ["polished_andesite", "stone_bricks", "mossy_cobblestone",
               "andesite", "deepslate_tiles", "cobblestone"]
GRAVE_TOP = ["andesite", "gravel", "cobblestone", "stone_bricks"]


def _perimeter(box, inset=0):
    """The ring of cells one block wide round a box."""
    u1, v1, u2, v2 = box
    u1, v1, u2, v2 = u1 + inset, v1 + inset, u2 - inset, v2 - inset
    ring = set()
    for u in range(u1, u2 + 1):
        ring.add((u, v1))
        ring.add((u, v2))
    for v in range(v1, v2 + 1):
        ring.add((u1, v))
        ring.add((u2, v))
    return ring


def _cross(s, u, v, y, stem="cobblestone_wall", high=4):
    """A wayside or memorial cross."""
    s.fill((u, y, v), (u, y + high, v), stem)
    s.fill((u - 1, y + high - 1, v), (u + 1, y + high - 1, v), stem)


def graveyard(s):
    """The retaining wall, the railing round it, the rows, and the trees."""
    u1, v1, u2, v2 = YARD
    cells = yard_cells()
    edge = edge_of(cells)

    # The platform is held by its own edge rather than by a bank of dirt: a
    # face of cobblestone, buried where the ground outside is already higher.
    for u, v in sorted(edge):
        s.fill((u, Y - 9, v), (u, Y - 1, v), PLINTH)

    # Railing on top, in the grey the map draws round the graveyard: stone
    # posts every four blocks with iron between them, open at the two gates.
    gates = {(g[0] + du, g[1] + dv) for g in (GATE_E, GATE_W)
             for du in (-1, 0, 1) for dv in (-1, 0, 1)}
    for u, v in sorted(edge):
        if (u, v) in gates:
            continue
        post = (u - u1) % 4 == 0 and (v - v1) % 4 == 0
        if post or (u in (u1, u2) and v in (v1, v2)):
            s.fill((u, Y + 1, v), (u, Y + 2, v), PLINTH)
        else:
            s.fill((u, Y + 1, v), (u, Y + 2, v), "iron_bars")

    # Rows of graves over what the church, the walk and the railing leave.
    rng = random.Random(1841)                    # the year of the last rebuild
    keep_clear = trace(WALK, width=2)
    for b in (NAVE, TOWER, PORCH, ALTAR_S, ALTAR_N, SACRIST):
        for u in range(b["x1"] - 2, b["x2"] + 3):
            for v in range(b["z1"] - 2, b["z2"] + 3):
                keep_clear.add((u, v))
    for u in range(u1 + 2, u2 - 2, 3):
        for v in range(v1 + 2, v2 - 3, 4):
            plot = [(u + du, v + dv) for du in (0, 1) for dv in (0, 1, 2)]
            if any(c in keep_clear or c not in cells for c in plot):
                continue
            if not all(u1 + 2 <= c[0] <= u2 - 2 and v1 + 2 <= c[1] <= v2 - 2
                       for c in plot):
                continue
            if rng.random() < 0.18:              # a gap, as in any graveyard
                continue
            s.fill((u, Y, v + 1), (u + 1, Y, v + 2), rng.choice(GRAVE_TOP))
            s.fill((u, Y + 1, v), (u + 1, Y + 1, v), rng.choice(GRAVE_STONE))
            if rng.random() < 0.35:              # a taller headstone
                s.block((u, Y + 2, v), rng.choice(GRAVE_STONE))
            if rng.random() < 0.3:
                s.block((u + 1, Y + 1, v + 2),
                        rng.choice(["poppy", "dandelion", "oxeye_daisy"]))
            elif rng.random() < 0.15:
                s.block((u + 1, Y + 1, v + 2), "lantern")

    # The memorial cross stands clear, on the axis of the west porch.
    _cross(s, -19, 6, Y + 1, high=5)
    s.fill((-20, Y, 5), (-18, Y, 7), "andesite")
    s.fill((-19, Y, 6), (-19, Y, 6), "polished_andesite")

    # Limes along the two quiet sides, as in the photograph.
    for patch in ((-21, -17, -17, -13), (-21, 9, -17, 14),
                  (13, -17, 18, -13), (13, 9, 18, 14)):
        s.sel((patch[0], Y, patch[1]), (patch[2], Y + 12, patch[3]))
        s.raw("//forest oak 8")


# --- trees -------------------------------------------------------------------

def _tree(s, u, v, y, h=5, log="oak_log", leaf="oak_leaves"):
    """One specimen tree, placed rather than scattered, so it lands where the
    plan puts it - the map marks single trees, not a wood."""
    top = y + h
    s.fill((u - 2, top - 2, v - 2), (u + 2, top - 1, v + 2), leaf)
    for du, dv in ((-2, -2), (-2, 2), (2, -2), (2, 2)):
        s.fill((u + du, top - 2, v + dv), (u + du, top - 1, v + dv), "air")
    s.fill((u - 1, top, v - 1), (u + 1, top, v + 1), leaf)
    s.fill((u - 1, top + 1, v), (u + 1, top + 1, v), leaf)
    s.fill((u, top + 1, v - 1), (u, top + 1, v + 1), leaf)
    s.fill((u, y, v), (u, top, v), log)


# --- the parish house, its workshop and its washroom -------------------------

def _windows(s, b, y, rows, pane=GLASS, step=4, start=2):
    """Evenly spaced windows down both long walls."""
    for u in range(b["x1"] + start, b["x2"] - 1, step):
        for v in (b["z1"], b["z2"]):
            s.fill((u, y, v), (u, y + rows - 1, v), pane)


def house(s):
    """Fara: two storeys under a slate roof, with a lower wing to the south."""
    b, w = HOUSE, WING
    eaves = HOUSE_Y + 7
    _shell(s, b, eaves, RENDER, floor_y=HOUSE_Y, base=HOUSE_Y - 1)
    _fill_gable_end(s, b, eaves + 1, "x", RENDER)
    _gable(s, b, eaves, "x", roof=SLATE, stair=SLATE_STAIR)
    s.fill((b["x1"] + 1, HOUSE_Y + 4, b["z1"] + 1),
           (b["x2"] - 1, HOUSE_Y + 4, b["z2"] - 1), "spruce_planks")   # upper floor
    _windows(s, b, HOUSE_Y + 2, 2)
    _windows(s, b, HOUSE_Y + 6, 2)

    # The wing, lower, under its own ridge.
    w_eaves = HOUSE_Y + 5
    _shell(s, w, w_eaves, RENDER, floor_y=HOUSE_Y, base=HOUSE_Y - 1)
    _fill_gable_end(s, w, w_eaves + 1, "z", RENDER)
    _gable(s, w, w_eaves, "z", roof=SLATE, stair=SLATE_STAIR)
    s.fill((w["x1"] + 1, HOUSE_Y + 1, w["z1"]), (w["x2"] - 1, HOUSE_Y + 3, w["z1"]),
           "air")                                     # through into the house

    # The front door faces the garden, with a bench either side of it.
    du = (b["x1"] + b["x2"]) // 2
    s.fill((du, HOUSE_Y + 1, b["z1"]), (du, HOUSE_Y + 2, b["z1"]), "air")
    s.block((du, HOUSE_Y + 1, b["z1"]), "oak_door[facing=north,half=lower]")
    s.block((du, HOUSE_Y + 2, b["z1"]), "oak_door[facing=north,half=upper]")
    for dd in (-2, 2):
        s.block((du + dd, HOUSE_Y + 1, b["z1"] - 1),
                "oak_stairs[facing=north]")
    # A chimney out of the ridge.
    s.fill((b["x1"] + 4, eaves, b["z1"] + 5), (b["x1"] + 4, eaves + 9, b["z1"] + 5),
           "bricks")
    s.block((b["x1"] + 4, eaves + 10, b["z1"] + 5), "campfire[lit=false]")


def workshop(s):
    """Dílna: square, cobblestone, and kitted out for work inside."""
    b = SHOP
    eaves = SHOP_Y + 5
    _shell(s, b, eaves, PLINTH, floor_y=SHOP_Y, base=SHOP_Y - 1)
    _fill_gable_end(s, b, eaves + 1, "z", PLINTH)
    _gable(s, b, eaves, "z", roof="spruce_planks", stair="spruce_stairs")
    for x in (b["x1"], b["x2"]):
        for z in (b["z1"], b["z2"]):
            s.fill((x, SHOP_Y, z), (x, eaves, z), "stone_bricks")
    mu = (b["x1"] + b["x2"]) // 2
    s.fill((mu, SHOP_Y + 1, b["z2"]), (mu, SHOP_Y + 2, b["z2"]), "air")
    s.block((mu, SHOP_Y + 1, b["z2"]), "spruce_door[facing=south,half=lower]")
    s.block((mu, SHOP_Y + 2, b["z2"]), "spruce_door[facing=south,half=upper]")
    for z in (b["z1"] + 2, b["z1"] + 5):
        s.fill((b["x1"], SHOP_Y + 2, z), (b["x1"], SHOP_Y + 3, z), "glass_pane")
        s.fill((b["x2"], SHOP_Y + 2, z), (b["x2"], SHOP_Y + 3, z), "glass_pane")
    # Technické vybavení: a bench to craft at and chests along the back wall.
    y, z = SHOP_Y + 1, b["z1"] + 1
    s.block((b["x1"] + 1, y, z), "crafting_table")
    s.block((b["x1"] + 2, y, z), "smithing_table")
    s.block((b["x1"] + 3, y, z), "furnace[facing=south]")
    s.block((b["x1"] + 4, y, z), "blast_furnace[facing=south]")
    s.fill((b["x1"] + 5, y, z), (b["x2"] - 1, y, z), "chest[facing=south]")
    s.fill((b["x1"] + 1, y, b["z2"] - 1), (b["x1"] + 2, y, b["z2"] - 1), "barrel")
    s.block((b["x2"] - 1, y, b["z2"] - 1), "anvil")
    s.block((mu, SHOP_Y + 4, (b["z1"] + b["z2"]) // 2), "lantern[hanging=true]")


def washroom(s):
    """Umývárna: a lean-to whose roof falls away from the pergola."""
    b = WASH
    high = WASH_Y + 5                       # eaves on the pergola side
    s.fill((b["x1"], WASH_Y - 1, b["z1"]), (b["x2"], WASH_Y - 1, b["z2"]), PLINTH)
    s.fill((b["x1"] + 1, WASH_Y, b["z1"] + 1), (b["x2"] - 1, WASH_Y, b["z2"] - 1),
           "smooth_stone")
    for i, u in enumerate(range(b["x1"], b["x2"] + 1)):
        top = high - (i + 1) // 2           # a shallow fall, half a block a bay
        for v in (b["z1"], b["z2"]):
            s.fill((u, WASH_Y, v), (u, top - 1, v), "smooth_quartz")
        if u in (b["x1"], b["x2"]):
            s.fill((u, WASH_Y, b["z1"]), (u, top - 1, b["z2"]), "smooth_quartz")
        s.fill((u, top, b["z1"]), (u, top, b["z2"]),
               SLATE_SLAB if i % 2 else SLATE)
        s.fill((u, top - 1, b["z1"] + 1), (u, top - 1, b["z2"] - 1), "air")
    # Glass-block strip under the eaves, and the door on the pergola side.
    s.fill((b["x1"] + 2, high - 2, b["z1"]), (b["x1"] + 4, high - 2, b["z1"]),
           "glass")
    mv = (b["z1"] + b["z2"]) // 2
    s.fill((b["x1"], WASH_Y + 1, mv), (b["x1"], WASH_Y + 2, mv), "air")
    s.block((b["x1"], WASH_Y + 1, mv), "oak_door[facing=west,half=lower]")
    s.block((b["x1"], WASH_Y + 2, mv), "oak_door[facing=west,half=upper]")
    # Fittings.
    for v in range(b["z1"] + 2, b["z2"] - 1, 2):
        s.block((b["x2"] - 1, WASH_Y + 1, v), "water_cauldron[level=3]")
    s.block((b["x1"] + 2, WASH_Y + 3, mv), "lantern[hanging=true]")


def pergola(s):
    """Open timber frame against the stone wall, with tables under it."""
    b = PERGOLA
    y, top = WASH_Y, WASH_Y + 4
    s.fill((b["x1"], y - 1, b["z1"]), (b["x2"], y - 1, b["z2"]), PLINTH)
    s.fill((b["x1"], y, b["z1"]), (b["x2"], y, b["z2"]), "smooth_stone")
    for u in (b["x1"], (b["x1"] + b["x2"]) // 2, b["x2"]):
        for v in (b["z1"], b["z2"]):
            s.fill((u, y + 1, v), (u, top - 1, v), "spruce_log[axis=y]")
    for v in (b["z1"], b["z2"]):
        s.fill((b["x1"], top, v), (b["x2"], top, v), "spruce_log[axis=x]")
    # A shallow double pitch over the frame.
    for i, v in enumerate(range(b["z1"], b["z2"] + 1)):
        half = (b["z2"] - b["z1"]) // 2
        yy = top + 1 + (half - abs(v - (b["z1"] + half))) // 2
        s.fill((b["x1"], yy, v), (b["x2"], yy, v), SLATE_SLAB)
    # Trestle tables and benches.
    for u in range(b["x1"] + 1, b["x2"] - 1, 3):
        s.fill((u, y + 1, b["z1"] + 2), (u, y + 1, b["z2"] - 2), "spruce_fence")
        s.fill((u, y + 2, b["z1"] + 2), (u, y + 2, b["z2"] - 2), "spruce_slab[type=top]")
    s.block(((b["x1"] + b["x2"]) // 2, top - 1, (b["z1"] + b["z2"]) // 2),
            "lantern[hanging=true]")


def _follow(s, cells, grid, build):
    """Run `build(u, v, y)` over cells, at whatever height the ground is."""
    for u, v in sorted(cells):
        y = grid.get((u, v))
        if y is not None:
            build(u, v, y)


def fara(s, grid=None):
    """The whole parish plot: buildings, the boundary wall and the garden."""
    grid = grid or survey()
    house(s)
    workshop(s)
    washroom(s)
    pergola(s)

    # Kamenná zídka, broken in places, with a brick coping as in the photo.
    for run in STONE_WALL:
        def stone(u, v, y):
            s.fill((u, y, v), (u, y + 1, v), PLINTH)
            s.block((u, y + 2, v), "bricks")
        _follow(s, trace(run), grid, stone)

    # Kovový plot between the corner of the house and the wall.
    def rail(u, v, y):
        s.block((u, y, v), PLINTH)
        s.fill((u, y + 1, v), (u, y + 2, v), "iron_bars")
    _follow(s, trace(RAILING), grid, rail)

    # The tree standing in the middle of the plot, towards the garden.
    gy = grid.get(GARDEN_TREE, HOUSE_Y - 1)
    _tree(s, GARDEN_TREE[0], GARDEN_TREE[1], gy, h=6)


def orchard(s, grid=None):
    """Ovocná zahrada: widely spaced trees behind a fence with no way through."""
    grid = grid or survey()
    u1, v1, u2, v2 = ORCHARD

    def post(u, v, y):
        s.fill((u, y + 1, v), (u, y + 2, v), "oak_fence")
    _follow(s, _perimeter(ORCHARD), grid, post)

    rng = random.Random(7)
    for u in range(u1 + 5, u2 - 3, 9):
        for v in range(v1 + 5, v2 - 3, 8):
            du, dv = u + rng.randint(-2, 2), v + rng.randint(-2, 2)
            if max(abs(du - FIRE[0]), abs(dv - FIRE[1])) < 6:
                continue
            y = grid.get((du, dv))
            if y is None:
                continue
            _tree(s, du, dv, y, h=rng.choice((4, 5, 5, 6)))
            if rng.random() < 0.4:
                s.block((du + 2, y + 1, dv + 2), "sweet_berry_bush[age=3]")

    # Ohniště, with log seats round it.
    fu, fv = FIRE
    fy = grid.get(FIRE, 68)
    s.fill((fu - 2, fy, fv - 2), (fu + 2, fy, fv + 2), "gravel")
    s.fill((fu - 1, fy, fv - 1), (fu + 1, fy, fv + 1), PLINTH)
    s.block((fu, fy, fv), "campfire")
    for du, dv in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        s.block((fu + du, fy + 1, fv + dv), "oak_log[axis=x]")


# --- ways --------------------------------------------------------------------

GARDEN_WALK = [(44, -3), (48, -6), (48, -16), (58, -17), (63, -17)]
DOOR_SPUR   = [(59, -17), (59, -15)]
SHOP_WALK   = [(63, -17), (70, -19), (75, -24), (76, -31)]


def _profile(line, grid):
    """Heights along a line, eased so the walk never steps more than a block.

    The churchyard stands three blocks above the lane, so the path has to
    climb; left at ground level it would run into the face of the retaining
    wall instead of over it.
    """
    ys = []
    last = None
    for c in line:
        h = grid.get(c)
        ys.append(h if h is not None else last)
        last = ys[-1]
    if ys[0] is None:
        return None
    for i in range(1, len(ys)):
        if ys[i] is None:
            ys[i] = ys[i - 1]
    for _ in range(3):
        for i in range(1, len(ys)):
            ys[i] = max(ys[i - 1] - 1, min(ys[i - 1] + 1, ys[i]))
        for i in range(len(ys) - 2, -1, -1):
            ys[i] = max(ys[i + 1] - 1, min(ys[i + 1] + 1, ys[i]))
    return ys


def _line(points):
    """Ordered centre cells of a polyline, without repeats."""
    line = []
    for (au, av), (bu, bv) in zip(points, points[1:]):
        steps = max(abs(bu - au), abs(bv - av))
        for i in range(steps + 1):
            t = i / steps if steps else 0
            c = (round(au + (bu - au) * t), round(av + (bv - av) * t))
            if not line or line[-1] != c:
                line.append(c)
    return line


def route(s, grid, points, surface=LANE, width=1, bed="dirt"):
    """Lay a way along a polyline, cutting and packing it level as it goes."""
    line = _line(points)
    ys = _profile(line, grid)
    if ys is None:
        return
    done = set()
    for (u, v), y in zip(line, ys):
        for du in range(-width, width + 1):
            for dv in range(-width, width + 1):
                if abs(du) + abs(dv) > width:
                    continue
                c = (u + du, v + dv)
                if c in done:
                    continue
                done.add(c)
                g = grid.get(c, y)
                if g < y:
                    s.fill((c[0], g, c[1]), (c[0], y - 1, c[1]), bed)
                elif g > y:
                    s.fill((c[0], y + 1, c[1]), (c[0], g + 3, c[1]), "air")
                s.block((c[0], y, c[1]), surface)
                s.fill((c[0], y + 1, c[1]), (c[0], y + 3, c[1]), "air")


def paths(s, grid=None):
    """The lane, the field track, and the walk from the parish to the porch."""
    grid = grid or survey()
    route(s, grid, LANE_RUN, LANE, width=1)
    route(s, grid, TRACK, "coarse_dirt", width=0)
    # Orange on the map: garden, lane, east gate, north side, west porch.
    u1, v1, u2, v2 = YARD
    inside = [c for c in _line(WALK) if u1 <= c[0] <= u2 and v1 <= c[1] <= v2]
    route(s, grid, WALK, LANE, width=1)
    for u, v in inside:                          # gravel once inside the gates
        for du, dv in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            if u1 <= u + du <= u2 and v1 <= v + dv <= v2:
                s.block((u + du, Y, v + dv), "gravel")
    for pts in (GARDEN_WALK, DOOR_SPUR, SHOP_WALK):
        route(s, grid, pts, PAVING, width=0)
    # A wayside cross where the walk leaves the lane, as the map marks it.
    cy = grid.get((26, -2), Y - 3)
    _cross(s, 26, -2, cy + 1, high=4)


def lights(s, grid=None):
    """Lanterns on posts along the ways, and hung inside the church."""
    grid = grid or survey()
    for pts in (WALK, GARDEN_WALK):
        line = _line(pts)
        ys = _profile(line, grid)
        if ys is None:
            continue
        for i in range(4, len(line), 9):
            u, v = line[i]
            for du, dv in ((2, 0), (0, 2), (-2, 0), (0, -2)):
                c = (u + du, v + dv)
                g = grid.get(c)
                if g is None or abs(g - ys[i]) > 1:
                    continue
                s.fill((c[0], g + 1, c[1]), (c[0], g + 3, c[1]), "oak_fence")
                s.block((c[0], g + 4, c[1]), "lantern")
                break

    n, t = NAVE, TOWER
    for x in range(n["x1"] + 5, n["x2"] - 2, 4):
        s.block((x, WALL_TOP - 2, (n["z1"] + n["z2"]) // 2), "lantern[hanging=true]")
    for b, y in ((ALTAR_S, CHAPEL_TOP - 2), (ALTAR_N, CHAPEL_TOP - 2),
                 (SACRIST, SACRIST_TOP - 2), (PORCH, PORCH_TOP - 1)):
        s.block(((b["x1"] + b["x2"]) // 2, y, (b["z1"] + b["z2"]) // 2),
                "lantern[hanging=true]")
    s.block(((t["x1"] + t["x2"]) // 2, Y + 5, (t["z1"] + t["z2"]) // 2),
            "lantern[hanging=true]")
    for dz in (-1, 1):
        s.block((PORCH["x1"] - 1, Y + 3, (PORCH["z1"] + PORCH["z2"]) // 2 + dz),
                "lantern")
    # Either side of the parish door, and on the garden tree.
    du = (HOUSE["x1"] + HOUSE["x2"]) // 2
    for dd in (-1, 1):
        s.block((du + dd, HOUSE_Y + 3, HOUSE["z1"]), "lantern")


def spawn(s, grid=None):
    """Players arrive on the parish lawn, between house, washroom and workshop."""
    grid = grid or survey()
    su, sv = SPAWN
    y = grid.get(SPAWN, HOUSE_Y - 1)
    s.fill((su - 4, y, sv - 4), (su + 4, y, sv + 4), "grass_block")
    s.fill((su - 4, y + 1, sv - 4), (su + 4, y + 5, sv + 4), "air")
    s.fill((su - 1, y, sv - 1), (su + 1, y, sv + 1), PAVING)
    s.raw(f"setworldspawn {ORIGIN[0] + su} {y + 1} {ORIGIN[1] + sv}")
    s.raw("gamerule spawnRadius 3")


# --- clearing the first attempt ----------------------------------------------

OLD = dict(church=(-41, -1, -7, 23), pad=(-44, -4, -4, 28), spawn=(0, 0), y=89)


def demolish(s, grid=None):
    """Take down the church on the knoll and put the hilltop back to grass.

    Written in world coordinates - it is the one thing here that is not part
    of the village, so it gets its own session rather than the origin shift.
    """
    w = Session(origin=(0, 0))
    ox1, oz1, ox2, oz2 = OLD["church"]
    oy = OLD["y"]
    ours = ("smooth_sandstone,andesite,polished_andesite,cobblestone,bricks,"
            "brick_stairs,oxidized_copper,black_stained_glass_pane,iron_bars,"
            "dirt_path,oak_fence,oak_planks,oak_slab,lantern,water,"
            "cobblestone_slab,glass_pane")
    # Everything of ours above the old churchyard level.
    w.replace((ox1 - 8, oy, oz1 - 6), (ox2 + 8, oy + 40, oz2 + 6), ours, "air")
    px1, pz1, px2, pz2 = OLD["pad"]
    w.fill((px1, oy, pz1), (px2, oy, pz2), "grass_block")
    w.fill((px1, oy + 1, pz1), (px2, oy + 12, pz2), "air")
    # The lamp posts and the track ran down the old skirt, below that level.
    w.replace((px1 - 30, oy - 22, pz1 - 12), (px2 + 14, oy + 2, pz2 + 6),
              "oak_fence,lantern,cobblestone_slab", "air")
    w.replace((px1 - 30, oy - 22, pz1 - 12), (px2 + 14, oy + 2, pz2 + 6),
              "dirt_path,andesite,polished_andesite", "grass_block")
    # And let the hilltop go back to being a hilltop.
    w.sel((px1 + 2, oy, pz1 + 2), (px2 - 2, oy + 14, pz2 - 2))
    w.raw("//forest oak 5")
    w.flush(dry_run=getattr(s, "dry_run", False))


STAGES = {"demolish": demolish, "terrain": terrain, "church": lambda s, g=None: church(s),
          "graveyard": lambda s, g=None: graveyard(s), "fara": fara,
          "orchard": orchard, "paths": paths, "lights": lights, "spawn": spawn}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stages", nargs="*",
                    default=[k for k in STAGES if k != "demolish"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    s = Session(origin=ORIGIN)
    s.dry_run = a.dry_run
    for name in a.stages:
        if name not in STAGES:
            sys.exit(f"unknown stage {name!r}; known: {', '.join(STAGES)}")
        print(f"-- {name}")
        # Each stage is flushed before the next is planned, and the ground is
        # read again in between: the walk has to follow the churchyard that
        # the terrain stage just cut, not the field that was there before.
        STAGES[name](s, None if name == "church" else survey())
        s.flush(dry_run=a.dry_run)


if __name__ == "__main__":
    main()
