"""Drive WorldEdit over RCON.

Vanilla /fill is not usable here: with no player nearby the chunks are not
loaded and the command refuses with "That position is not loaded". WorldEdit
edits the world directly, so it works on untouched terrain - which is the whole
situation when building on virgin ground.

Commands are queued and sent down a single rcon-cli stdin, because one
`docker exec` per command costs about 150 ms while a batch of five costs 90 ms
for the lot.
"""

import subprocess


class Session:
    """A queue of WorldEdit commands, flushed together."""

    BATCH = 400

    def __init__(self, world="world", container="minecraft-server", echo=False):
        self.world, self.container, self.echo = world, container, echo
        self.q = [f"//world {world}"]

    # --- primitives ---------------------------------------------------------

    def raw(self, cmd):
        self.q.append(cmd)

    def sel(self, a, b):
        self.q.append("//pos1 %d,%d,%d" % a)
        self.q.append("//pos2 %d,%d,%d" % b)

    def fill(self, a, b, block):
        self.sel(a, b)
        self.q.append(f"//set {block}")

    def replace(self, a, b, old, new):
        self.sel(a, b)
        self.q.append(f"//replace {old} {new}")

    def walls(self, a, b, block):
        """Only the four vertical sides, no floor or ceiling."""
        self.sel(a, b)
        self.q.append(f"//walls {block}")

    def hollow_box(self, a, b, block):
        self.sel(a, b)
        self.q.append(f"//faces {block}")

    def block(self, p, block):
        self.fill(p, p, block)

    def line(self, a, b, block):
        """A straight run; only sensible for axis-aligned pairs."""
        self.fill(a, b, block)

    # --- composites ---------------------------------------------------------

    def clear(self, a, b):
        self.fill(a, b, "air")

    def platform(self, x1, z1, x2, z2, y, top, under, depth=6):
        """Level a terrace: solid below, clear above.

        Ground gets cut and filled in one go, which is what terracing a slope
        actually is - anything above the platform height goes, anything below
        is packed out to meet it.
        """
        self.fill((x1, y - depth, z1), (x2, y - 1, z2), under)
        self.fill((x1, y, z1), (x2, y, z2), top)
        self.clear((x1, y + 1, z1), (x2, y + 40, z2))

    # --- execution ----------------------------------------------------------

    def flush(self, dry_run=False):
        cmds = self.q + ["//world"]
        self.q = [f"//world {self.world}"]
        if dry_run:
            print(f"[dry run] {len(cmds)} commands")
            for c in cmds[:12]:
                print("   ", c)
            if len(cmds) > 12:
                print(f"    ... and {len(cmds)-12} more")
            return []

        problems = []
        for i in range(0, len(cmds), self.BATCH):
            batch = cmds[i:i + self.BATCH]
            out = subprocess.run(
                ["docker", "exec", "-i", self.container, "rcon-cli"],
                input="\n".join(batch) + "\n",
                capture_output=True, text=True, timeout=600,
            ).stdout
            for line in out.splitlines():
                low = line.lower()
                if any(w in low for w in ("unknown", "error", "invalid",
                                          "not loaded", "exception",
                                          "you need", "please")):
                    problems.append(line.strip())
            if self.echo:
                print(f"  sent {len(batch)} commands")
        print(f"sent {len(cmds)} commands"
              + (f", {len(problems)} problem lines" if problems else ", no errors"))
        for p in problems[:10]:
            print("   !", p)
        return problems
