"""Pieces every build here needs: ground work, roofs, ways, trees.

Nothing in this module knows about a particular place. It takes a Session
already shifted to wherever it is building, a grid of ground heights in the
same local coordinates, and explicit block names - so the same gable serves a
village church and a windmill.
"""

# Stair facings for a roof course, by which side of the ridge it is on.
# A stair "faces" the direction it descends towards, which is the opposite of
# what reads naturally when writing the loop - the first attempt had every
# pitch inverted, and an inverted pitch leaks rain.
DOWN_N, DOWN_S = "south", "north"
DOWN_W, DOWN_E = "east", "west"

# What a build puts up itself. The ground survey has to look past it: a wall
# is built on the ground and is then read as the ground, so every rebuild
# would raise it another course. Paving is deliberately absent - it *is* the
# ground - and so is andesite, which also occurs in natural bands underground.
BUILT = frozenset((
    "smooth_sandstone", "polished_andesite", "cobblestone", "cobblestone_wall",
    "cobblestone_slab", "mossy_cobblestone", "mossy_stone_bricks", "bricks",
    "brick_stairs", "stone_bricks", "stone_brick_wall", "stone_brick_stairs",
    "stone_brick_slab", "chiseled_stone_bricks", "smooth_stone", "quartz_block",
    "smooth_quartz", "deepslate_tiles", "deepslate_tile_stairs",
    "deepslate_tile_slab", "polished_deepslate", "polished_deepslate_stairs",
    "spruce_planks", "spruce_stairs", "spruce_slab", "spruce_fence",
    "oak_planks", "oak_slab", "oak_stairs", "oak_fence", "dark_oak_planks",
    "dark_oak_stairs", "dark_oak_slab", "jungle_planks", "jungle_stairs",
    "jungle_slab", "stripped_oak_wood", "stripped_spruce_wood",
    "stripped_dark_oak_wood", "stripped_jungle_wood", "iron_bars", "glass",
    "glass_pane", "white_stained_glass", "black_stained_glass_pane",
    "oxidized_copper", "copper_block", "white_wool", "light_gray_wool",
    "campfire", "water_cauldron", "cauldron", "crafting_table",
    "smithing_table", "furnace", "blast_furnace", "chest", "barrel", "anvil",
    "brewing_stand", "oak_door", "spruce_door", "jungle_door", "dark_oak_door",
    "bookshelf", "lectern", "ladder", "scaffolding", "hay_block",
))

# One mask per command: WorldEdit reads "##logs,##leaves" as a single tag
# named "logs,##leaves" and rejects the lot.
GROWTH = ("##logs", "##leaves", "##saplings", "##flowers", "vine",
          "dead_bush", "sweet_berry_bush", "moss_carpet")


# --- ground ------------------------------------------------------------------

def clear_growth(s, box, y, margin=3, up=26, down=4):
    """Fell whatever is growing over a site before anything is built on it.

    The ground survey looks past foliage on purpose, so a levelled pad can
    come out with a full-grown oak standing in the middle of it and the
    building disappears into the wood.
    """
    u1, v1, u2, v2 = box
    s.sel((u1 - margin, y - down, v1 - margin),
          (u2 + margin, y + up, v2 + margin))
    for mask in GROWTH:
        s.raw(f"//replace {mask} air")


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

    Runs of equal (target, natural) are filled in one command, so a 43 by 35
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


def perimeter(box, inset=0):
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


def follow(s, cells, grid, build, clear=12):
    """Run `build(u, v, y)` over cells, at whatever height the ground is.

    Whatever stood there is taken down first, so running a stage twice
    rebuilds it rather than adding a course to it.
    """
    for u, v in sorted(cells):
        y = grid.get((u, v))
        if y is None:
            continue
        if clear:
            s.fill((u, y + 1, v), (u, y + clear, v), "air")
        build(u, v, y)


# --- walls and roofs ---------------------------------------------------------

def shell(s, b, top, wall, base, floor_y=None, plinth="cobblestone",
          floor="polished_andesite"):
    """Plinth, walls, hollow interior."""
    s.fill((b["x1"], base, b["z1"]), (b["x2"], base + 1, b["z2"]), plinth)
    s.walls((b["x1"], base + 2, b["z1"]), (b["x2"], top, b["z2"]), wall)
    s.fill((b["x1"] + 1, base + 1, b["z1"] + 1),
           (b["x2"] - 1, top, b["z2"] - 1), "air")
    if floor_y is not None:
        s.fill((b["x1"] + 1, floor_y, b["z1"] + 1),
               (b["x2"] - 1, floor_y, b["z2"] - 1), floor)


def gable(s, b, eaves, along, roof, stair):
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


def gable_end(s, b, eaves, along, wall):
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


def cone(s, u, v, y, radius, block, step=1):
    """A conical or pyramidal spire, one ring a course."""
    r = radius
    while r >= 0:
        s.walls((u - r, y, v - r), (u + r, y, v + r), block)
        y += step
        r -= 1
    s.block((u, y, v), block)
    return y


# --- trees -------------------------------------------------------------------

def tree(s, u, v, y, h=5, log="oak_log", leaf="oak_leaves", spread=2):
    """One specimen tree, placed rather than scattered, so it lands where the
    plan puts it - a plan marks single trees, not a wood."""
    top = y + h
    r = spread
    s.fill((u - r, top - 2, v - r), (u + r, top - 1, v + r), leaf)
    for du, dv in ((-r, -r), (-r, r), (r, -r), (r, r)):
        s.fill((u + du, top - 2, v + dv), (u + du, top - 1, v + dv), "air")
    s.fill((u - 1, top, v - 1), (u + 1, top, v + 1), leaf)
    s.fill((u - 1, top + 1, v), (u + 1, top + 1, v), leaf)
    s.fill((u, top + 1, v - 1), (u, top + 1, v + 1), leaf)
    s.fill((u, y, v), (u, top, v), log)


# --- ways --------------------------------------------------------------------

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


def line(points):
    """Ordered centre cells of a polyline, without repeats."""
    out = []
    for (au, av), (bu, bv) in zip(points, points[1:]):
        steps = max(abs(bu - au), abs(bv - av))
        for i in range(steps + 1):
            t = i / steps if steps else 0
            c = (round(au + (bu - au) * t), round(av + (bv - av) * t))
            if not out or out[-1] != c:
                out.append(c)
    return out


def profile(cells, grid):
    """Heights along a line, eased so a way never steps more than a block."""
    ys, last = [], None
    for c in cells:
        h = grid.get(c)
        ys.append(h if h is not None else last)
        last = ys[-1]
    if not ys or ys[0] is None:
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


def route(s, grid, points, surface="dirt_path", width=1, bed="dirt"):
    """Lay a way along a polyline, cutting and packing it level as it goes."""
    cells = line(points)
    ys = profile(cells, grid)
    if ys is None:
        return
    done = set()
    for (u, v), y in zip(cells, ys):
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


# --- round work --------------------------------------------------------------

def disc(s, u, v, y, r, block, hollow=False):
    """A filled or hollow circle of blocks, laid a row at a time."""
    for dv in range(-r, r + 1):
        w = int(round((r * r - dv * dv) ** 0.5))
        if not hollow:
            s.fill((u - w, y, v + dv), (u + w, y, v + dv), block)
            continue
        inner = r - 1
        wi = int(round((inner * inner - dv * dv) ** 0.5)) if abs(dv) <= inner else -1
        if wi < 0:
            s.fill((u - w, y, v + dv), (u + w, y, v + dv), block)
        else:
            s.fill((u - w, y, v + dv), (u - wi - 1, y, v + dv), block)
            s.fill((u + wi + 1, y, v + dv), (u + w, y, v + dv), block)


def cylinder(s, u, v, y1, y2, r, block, hollow=True):
    for y in range(y1, y2 + 1):
        disc(s, u, v, y, r, block, hollow=hollow)


def round_roof(s, u, v, y, r, block, step=1):
    """A cone over a round tower."""
    while r >= 0:
        disc(s, u, v, y, r, block, hollow=(r > 1))
        y += step
        r -= 1
    return y
