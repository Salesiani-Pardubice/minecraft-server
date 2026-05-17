# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Purpose

A `docker-compose` setup that runs a **Paper Minecraft server** (`itzg/minecraft-server`)
for Salesian LAN parties, exposed to the internet through a `playit-cloud/playit-agent`
tunnel on `mc.salesianipardubice.cz`. The compose file plus its env-driven configuration
is the core "source" for the Pi-side stack.

A companion **web frontend** lives in [`web/`](./web/) (Astro + Tailwind + shadcn/ui,
hosted on Cloudflare Pages, API in `web/functions/`). It is reconciled into the running
MC server by the [`sync-agent/`](./sync-agent/) service. See "Web frontend & sync-agent"
below for the boundary.

## Hardware

| Component | Spec |
|-----------|------|
| Board | Raspberry Pi 5 |
| RAM | 8 GB |
| Storage | 1 TB NVMe SSD (≈ 811 GB free) |
| OS | Debian 12 Bookworm (Raspbian) |
| Tunnel | playit.gg → `mc.salesianipardubice.cz` |

Memory allocation: **4 GB** is given to the JVM (`MEMORY: "4G"`), leaving ≈ 4 GB
for the OS, Docker overhead, and the playit agent.

---

## Common commands

```sh
# Lifecycle
docker compose up -d                          # start all services (detached)
docker compose down                           # stop and remove containers
docker compose restart minecraft-server       # restart only the MC server
docker compose pull && docker compose up -d   # update images and restart

# Logs
docker compose logs -f minecraft-server       # tail server logs
docker compose logs -f playit                 # tail tunnel logs
docker compose logs --tail=100 minecraft-server  # last 100 lines

# Admin console (RCON)
docker exec -i minecraft-server rcon-cli      # interactive console (Ctrl+D to exit)
docker exec -i minecraft-server rcon-cli list           # who is online
docker exec -i minecraft-server rcon-cli "say Restart in 5 min"
docker exec -i minecraft-server rcon-cli "op petrkucerak"

# Diagnostics
docker stats minecraft-server                 # live CPU / RAM usage
docker inspect minecraft-server | grep Status # quick health check
df -h                                         # disk space

# Backups (handled by the mc-backup sidecar — see "Backup strategy" below)
docker compose logs -f mc-backup              # tail backup activity
docker exec mc-backup backup now              # force an immediate backup
```

---

## Architecture notes

- **Configuration lives in `docker-compose.yml`, not in `data/`.** The `itzg/minecraft-server`
  image generates `data/server.properties`, `data/bukkit.yml`, `data/spigot.yml`, etc.
  from environment variables on each startup. To change server behaviour (difficulty,
  view distance, ops, PVP, etc.), edit the `environment:` block in `docker-compose.yml` —
  edits to files under `data/` will be overwritten on the next start.

- **`data/` is the bind-mounted server volume.** Worlds (`world/`, `world_nether/`,
  `world_the_end/`), plugin data, logs, and the Paper jar all live here and persist
  across restarts. The directory is untracked (see `.gitignore`).

- **Two ways to install plugins, and they behave differently:**
  - `MODRINTH_PROJECTS` env var — image auto-downloads plugins on each start. If a
    plugin is listed here it will be (re)downloaded even if you delete the jar manually.
  - Manual jars in `data/plugins/` — load unconditionally at server start, regardless
    of what is in `MODRINTH_PROJECTS`. To fully remove a plugin, delete **both** the
    env var entry and the jar.

- **Versions are pinned.** Container images use exact tags
  (`itzg/minecraft-server:2026.5.2-java21`, `itzg/mc-backup:2026.5.0`,
  `playit-agent:0.16`) and `VERSION: "1.21.11"` pins the Paper build. Bumping
  any of these is a deliberate edit in `docker-compose.yml` followed by
  `docker compose pull && docker compose up -d`. The resolved Paper jar lives at
  `data/paper-*.jar` and is recorded in `data/.papermc-manifest.json`.

- **JVM tuning:** `USE_AIKAR_FLAGS: "true"` enables the community-standard GC flags for
  Paper servers. These significantly reduce garbage-collection pauses and should always
  be on. Do not set `MAX_TICK_TIME` to anything other than `-1` — the watchdog kill it
  enables is harmful on RPi where GC pauses can exceed the default threshold.

- **Timezone:** `TZ: "Europe/Prague"` ensures log timestamps match local time.

- **`SPAWN_PROTECTION`** must be `"0"` (a radius in blocks). The string `"TRUE"` is
  silently ignored by the image and leaves the default 16-block protection active.
  Use `"0"` to disable, or a number like `"4"` for a small protected radius.

---

## Plugin management

Currently active plugins (jars present in `data/plugins/`):

| Plugin | Source | Purpose |
|--------|--------|---------|
| WorldEdit | Manual jar | In-world editing tool for operators |
| WorldGuard | Manual jar | Region protection |

Plugins commented out in `MODRINTH_PROJECTS` but **with jars still present** will still
load. After commenting out a plugin, always check `data/plugins/` and remove the jar if
you want it gone.

Recommended plugins to add (uncomment in compose):

| Plugin | Why |
|--------|-----|
| `spark` | Server profiler — essential for diagnosing TPS drops |
| `chunky` | Pre-generates chunks, eliminates lag on first exploration |
| `coreprotect` | Block-change audit log + rollback for grief recovery |
| `luckperms` | Fine-grained permission management |
| `tab` | Nicer player tab list with ping / role display |

---

## Backup strategy

Worlds live in `data/` which is not committed to git. Backups are handled by the
`mc-backup` sidecar (`itzg/mc-backup`) defined in `docker-compose.yml`, so they
start automatically with `docker compose up -d` — **no host cron is required**.

Behaviour:
- Connects to the server over RCON (`RCON_HOST: minecraft-server`) to run
  `save-off` / `save-all flush` / `save-on` around each archive.
- Writes `world-*.tgz` archives to `/home/pedro/backups` on the host
  (bind-mounted into the sidecar at `/backups`).
- `BACKUP_INTERVAL: 24h` — one archive every 24 hours from container start
  (after a `2m` `INITIAL_DELAY`). The schedule is interval-based, not
  wall-clock; to anchor backups near 03:00, restart the stack at the desired
  time of day.
- `PRUNE_BACKUPS_DAYS: 14` — archives older than 14 days are removed
  automatically.

Useful commands:

```sh
docker compose logs -f mc-backup              # tail backup activity
docker exec mc-backup backup now              # force an immediate backup
ls -lh /home/pedro/backups                    # list archives
```

---

## Secrets

The `.env` file is **gitignored** and must exist on the host. Required keys:

```
SECRET_KEY=<playit.gg agent secret — from playit.gg dashboard>
```

Without `SECRET_KEY` the `playit` service fails but the Minecraft server still runs
on `localhost:25565`.

---

## Web frontend & sync-agent

This repo contains two independently-deployed components beyond the Pi stack:

- **[`web/`](./web/)** — Astro + Tailwind + shadcn/ui frontend deployed to
  **Cloudflare Pages**. The API lives in `web/functions/` as Cloudflare Pages
  Functions, backed by Cloudflare **D1**. Provides a public landing page,
  email-magic-link auth, self-service whitelist requests (with admin approval),
  operator management, player profiles/stats, and LAN-event registration.
  Czech UI, English code.
- **[`sync-agent/`](./sync-agent/)** — small Docker service that runs on the Pi
  alongside `minecraft-server`. Polls the cloud's `/api/sync/desired-state`
  every ~5 minutes, diffs against live MC state, and applies changes via RCON.

**Design invariant — the web is purely additive.** The MC server must keep
running normally if Cloudflare, D1, or the sync-agent fail. Control flow is
**pull-based**: Cloudflare never connects to the Pi; the sync-agent only makes
outbound HTTPS. Whitelist/op changes made through the web propagate to the
server within one poll interval. Manual RCON / env-var changes on the Pi remain
fully supported.

Full design lives in [`web/ARCHITECTURE.md`](./web/ARCHITECTURE.md). API surface
in [`web/functions/README.md`](./web/functions/README.md). Sync-agent details in
[`sync-agent/README.md`](./sync-agent/README.md). All three are **templates**
with `<!-- PASTE: ... -->` markers — extend them as the design firms up rather
than starting from scratch.

When making changes touching this feature, remember:
- The `OPS:` env-var list in `docker-compose.yml` is the bootstrap; once the
  sync-agent is running, ops are managed via the web and reconciled via RCON.
  Both paths must stay compatible.
- Add `SYNC_SECRET` and `RCON_PASSWORD` to the existing `.env` (gitignored)
  when the sync-agent ships. The MC server needs `RCON_PASSWORD` set too.
- `web/` has its own `package.json` and Node toolchain; the Pi side has none.
  Don't pull web dependencies into the Pi services.

---

## Conventions

- The README and user-facing strings (server name, web UI copy, etc.) are in
  **Czech**. Code, comments, commit messages, and architecture docs are in
  **English**. Keep them that way.
- Operator list is managed via `OPS:` env var in compose for bootstrap; ongoing
  changes flow through the web → sync-agent → RCON. Avoid editing
  `data/ops.json` by hand.
- Never commit `data/`, `.env`, or `backups/` to git (all covered by `.gitignore`).
- When updating `docker-compose.yml`, run `docker compose config` first to validate syntax.
