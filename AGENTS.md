# AGENTS.md

Operating guide for AI coding agents working in this repository.
Human-facing overview lives in [`README.md`](./README.md) (Czech).

## What this repo is

A single `docker-compose.yml` that runs a **Paper Minecraft server** for the
Salesian LAN parties in Pardubice, on a Raspberry Pi 5, exposed to the internet
through a **playit.gg** tunnel at `mc.salesianipardubice.cz`.

**The prime directive:** `docker compose up -d` on a clean host (plus a `.env`)
must bring the whole stack up, correctly configured, with no manual follow-up
steps. Any change that requires a human to run something afterwards is a
regression. If you add a step, encode it in the compose file — not in the docs.

## Target hardware — optimise for it

| Component | Spec |
|-----------|------|
| Board | Raspberry Pi 5 (ARM64, 4 cores) |
| RAM | 8 GB total — **4 GB** goes to the JVM (`MEMORY: "4G"`) |
| Storage | 1 TB NVMe SSD (~805 GB free) |
| OS | Debian 12 Bookworm (64-bit) |
| Expected load | ≤ 10 concurrent players (`MAX_PLAYERS: 10`) |

Consequences for every change you propose:

- **RAM is the scarce resource, not disk.** At idle the host sits around
  1.4 GB available. Do not add services, plugins, or heap without accounting
  for what they cost. Never raise `MEMORY` above `4G`.
- **Images must be `linux/arm64`.** Check before suggesting any new image.
- `VIEW_DISTANCE` / `SIMULATION_DISTANCE` are at `6` deliberately — they are
  the main TPS lever on this board. Raising them needs a measured reason.
- `MAX_WORLD_SIZE: 2000` caps world growth (disk *and* chunk-gen cost).
- `USE_AIKAR_FLAGS: "true"` must stay on (GC pause tuning for Paper).
- `MAX_TICK_TIME: "-1"` must stay — the watchdog it disables kills the server
  on long GC pauses, which are normal on a Pi.

## Repository layout

```
docker-compose.yml   # the entire stack + the entire server configuration
README.md            # Czech, for humans running the LAN party
ARCHITECTURE.md      # English, the system as currently deployed
AGENTS.md            # this file
.env                 # gitignored, must exist on the host
data/                # gitignored, bind-mounted server volume (generated)
```

Git history contains two removed documents — an architecture specification
(deleted in `b7244c3`) and a `CLAUDE.md` (deleted in `bfde034`) — that
described an Astro + Cloudflare Pages frontend and a `sync-agent` service.
**Neither was ever built.** Do not resurrect them from history as if they
described reality; `ARCHITECTURE.md` is the current source of truth.

There is no application source code, no build step, and no package manager in
this repo. It is configuration only.

## Services

| Service | Image | Role |
|---------|-------|------|
| `minecraft-server` | `itzg/minecraft-server:2026.5.2-java25` | Paper server, 4 GB heap, port `25565`, network `mcnet` |
| `mc-backup` | `itzg/mc-backup:2026.5.0` | World archives via RCON, network `mcnet` |
| `playit` | `ghcr.io/playit-cloud/playit-agent:0.16` | Outbound tunnel, `network_mode: host` |

`playit` runs on the host network on purpose, so it is not on `mcnet` and
reaches the server via the host's published `25565`.

## Configuration model — read this before editing anything

**All server configuration lives in the `environment:` block of
`docker-compose.yml`.** The `itzg/minecraft-server` image regenerates
`data/server.properties`, `data/bukkit.yml`, `data/spigot.yml` and friends from
those variables on *every* start.

- Editing files under `data/` is pointless — the next start overwrites them.
  To change difficulty, PVP, view distance, ops, MOTD: edit the compose file.
- `data/` is the source of *state* (worlds, plugin data, logs, the Paper jar),
  never of *configuration*.
- `data/ops.json` is generated from `OPS:`. Do not hand-edit it; add the name
  to `OPS:` or use `rcon-cli op <name>` and mirror it into the compose file.

After any edit to `docker-compose.yml`:

```sh
docker compose config --quiet   # must pass before you consider the edit done
```

Beware of YAML block scalars (`|`) in the environment block: `MODRINTH_PROJECTS`
and `OPS` are multi-line strings, and a line commented out at the *wrong*
indentation silently becomes part of the value. Always verify with
`docker compose config | grep -A5 MODRINTH_PROJECTS` after touching them.

## Versions

Container images are pinned to exact tags and bumping one is a deliberate edit
followed by `docker compose pull && docker compose up -d`.

`VERSION` is pinned to an exact Paper release, chosen as the **intersection of
plugin support** rather than the newest available build — see
[`ARCHITECTURE.md` §6](./ARCHITECTURE.md#6-version-policy). `LATEST` is
forbidden: it once moved this server to 26.2 ahead of the plugin ecosystem, and
because Minecraft cannot load a world backwards, that could not be undone
without discarding the world. The resolved build is recorded in
`data/.papermc-manifest.json`.

Before bumping `VERSION`, confirm on Modrinth that **every** plugin in
`MODRINTH_PROJECTS` lists the candidate version. Query the API rather than
reading the project page, and do not trust the first few entries — Modrinth
does not return versions in semver order:

```sh
curl -s 'https://api.modrinth.com/v2/project/<slug>/version?loaders=%5B%22paper%22%5D' \
  | python3 -c 'import json,sys; print([v["version_number"] for v in json.load(sys.stdin) if "<mc-version>" in v["game_versions"]])'
```

## Plugins

Two independent mechanisms, and they interact badly:

- **`MODRINTH_PROJECTS`** — the image downloads these on every start and
  records them in `data/.modrinth-manifest.json`. Deleting the jar by hand does
  nothing; it comes back.
- **Manual jars in `data/plugins/`** — loaded unconditionally, regardless of
  the compose file.

To truly remove a plugin: remove the `MODRINTH_PROJECTS` entry **and** delete
the jar **and** (optionally) its config directory under `data/plugins/`.

Currently active: `worldedit` (7.4.5), `worldguard` (7.0.18), both via
`MODRINTH_PROJECTS`. Note `data/plugins/spark/` is a leftover config directory
from a plugin that is no longer installed.

Every plugin costs RAM and tick time on this hardware. Justify additions.

## Backups

The `mc-backup` sidecar handles backups — **no host cron exists or should be
added**. It connects over RCON (`RCON_HOST: minecraft-server`), runs
`save-off` → `save-all flush` → `sync` → archive → `save-on`, and writes
`world-*.tar.gz` to `/home/pedro/backups` on the host.

- `BACKUP_INTERVAL: 24h`, counted from container start — **not** wall-clock.
  To anchor backups near a given hour, restart the stack at that hour.
- `PRUNE_BACKUPS_DAYS: 14` — older archives are deleted automatically.
- `data` is mounted read-only into this container; `/backups` is the only
  writable path.
- The host directory `/home/pedro/backups` must exist before first start.

Backups are currently ~5 MB (the world is ~14 MB). Disk is not a constraint;
do not add compression complexity to save space.

## Secrets

`.env` is gitignored and must exist on the host:

```
SECRET_KEY=<playit.gg agent secret>
```

Without it only `playit` fails; the server still runs on `localhost:25565`.

`RCON_PASSWORD` is set explicitly in `.env` and shared by `minecraft-server`
and `admin-api`, which needs it to reach the server at all. Treat it as a
secret: never print it into logs, docs, commit messages, or commands you echo
back. Changing it requires recreating `minecraft-server`, since the value is
written into `data/server.properties` at startup.

## Common commands

```sh
# Lifecycle
docker compose up -d
docker compose down
docker compose restart minecraft-server
docker compose pull && docker compose up -d

# Logs
docker compose logs -f minecraft-server
docker compose logs --tail=100 minecraft-server
docker compose logs -f mc-backup
docker compose logs -f playit

# Admin console (RCON)
docker exec -i minecraft-server rcon-cli               # interactive, Ctrl+D to exit
docker exec -i minecraft-server rcon-cli list
docker exec -i minecraft-server rcon-cli "say Restart za 5 minut"

# Diagnostics
docker stats --no-stream
docker inspect -f '{{.State.Health.Status}}' minecraft-server
free -h && df -h /

# Backups
docker exec mc-backup backup now
ls -lh /home/pedro/backups
```

## Rules for agents

1. **Never commit `data/`, `.env`, or backup archives.** All are gitignored;
   keep it that way.
2. **Never hand-edit files under `data/`** as a way of changing configuration.
   Change the compose file.
3. **Validate before finishing:** `docker compose config --quiet`.
4. **Do not restart or `down` the stack without asking**, and never while
   players may be online. Check `rcon-cli list` first. A LAN party is a live
   event; an unannounced restart is a real-world failure.
5. **Do not add host-level state** (cron jobs, systemd units, scripts that must
   be run by hand). If it is needed for the stack to work, it belongs in
   `docker-compose.yml`.
6. **Check ARM64 support** before proposing any new image or plugin.
7. **Read before you overwrite.** The running server holds live world state;
   `docker compose down -v` or deleting `data/` destroys it.
8. Language convention: **Czech** for the README and anything a player or
   organiser reads (server name, MOTD, in-game messages). **English** for code,
   comments, commit messages, and architecture documents.
9. Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
   `chore:`), as in the existing history.

## Known drift (as of 2026-09-13)

Mismatches between the documentation and the running system. Re-check each one
before relying on it — they may already be fixed by the time you read this.

- `README.md` states image `...-java21` and Paper `1.21.11`, and still
  describes the stack as three services. Both are stale — see
  [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the target, which adds
  `cloudflared` and `admin-api`.
- `README.md` lists WorldEdit and WorldGuard as manual jars in `data/plugins/`.
  Both are in fact managed by `MODRINTH_PROJECTS` and re-downloaded on every
  start.
- `data/plugins/spark/` is a leftover configuration directory for a plugin that
  is no longer installed.
- `motd` is still the default `A Minecraft Server`. `SERVER_NAME` sets
  `server-name`, not the MOTD shown in the client's server list — that needs a
  separate `MOTD` env var.
- `whitelist.json` is empty and `white-list=false`: the server is open to
  anyone who finds the tunnel address.
- `mc-backup` uses a bare `depends_on` without `condition: service_healthy`,
  so it starts before the server is ready and relies on `INITIAL_DELAY: 2m`
  to cover the gap.
- Restoring from a backup archive has no documented procedure and has never
  been exercised.
