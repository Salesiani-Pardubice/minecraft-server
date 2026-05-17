# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Purpose

A `docker-compose` setup that runs a **Paper Minecraft server** (`itzg/minecraft-server`)
for Salesian LAN parties, exposed to the internet through a `playit-cloud/playit-agent`
tunnel on `mc.salesianipardubice.cz`. There is no application code — the "source" is
the compose file and the env-driven configuration it passes to the image.

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

# Backups (manual)
docker exec minecraft-server rcon-cli save-off
tar -czf ~/backups/world-$(date +%Y%m%d-%H%M).tar.gz \
  ~/Documents/minecraft-server/data/world \
  ~/Documents/minecraft-server/data/world_nether \
  ~/Documents/minecraft-server/data/world_the_end
docker exec minecraft-server rcon-cli save-on
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

- **Paper version** is controlled by `VERSION: "LATEST"`, resolved at container start.
  The exact resolved jar lives at `data/paper-*.jar` and is recorded in
  `data/.papermc-manifest.json`.

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

Worlds live in `data/` which is not committed to git. Schedule automatic backups
with cron on the host:

```sh
# Edit with: crontab -e
# Daily backup at 03:00, keep 14 days
0 3 * * * /home/pedro/Documents/minecraft-server/scripts/backup.sh >> /home/pedro/backups/backup.log 2>&1
```

`scripts/backup.sh` should:
1. Run `rcon-cli save-off` and `rcon-cli save-all` to flush chunks.
2. `tar` the world directories.
3. Run `rcon-cli save-on`.
4. Delete archives older than 14 days (`find ~/backups -mtime +14 -delete`).

---

## Secrets

The `.env` file is **gitignored** and must exist on the host. Required keys:

```
SECRET_KEY=<playit.gg agent secret — from playit.gg dashboard>
```

Without `SECRET_KEY` the `playit` service fails but the Minecraft server still runs
on `localhost:25565`.

---

## Conventions

- The README and user-facing strings (server name, etc.) are in Czech. Keep them that way.
- Operator list is managed via `OPS:` env var in compose, not by editing `data/ops.json`.
- Never commit `data/`, `.env`, or `backups/` to git (all covered by `.gitignore`).
- When updating `docker-compose.yml`, run `docker compose config` first to validate syntax.
