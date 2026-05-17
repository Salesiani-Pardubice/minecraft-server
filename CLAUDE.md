# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

A docker-compose setup that runs a Paper Minecraft server (via `itzg/minecraft-server`) for Salesian LAN parties, exposed to the internet through a `playit-cloud/playit-agent` tunnel. There is no application code in this repo — the "source" is the compose file and the env-driven configuration it passes to the image.

## Common commands

```sh
docker compose up -d                          # start server (detached)
docker compose down                           # stop and remove containers
docker compose logs -f minecraft-server       # tail server logs
docker container ls                           # find the container ID
docker exec -i <CONTAINER ID> rcon-cli        # open admin console (CTRL+D to exit)
```

The playit tunnel requires `SECRET_KEY` in `.env` (gitignored) — without it the `playit` service will fail to start but the Minecraft server itself still runs on `localhost:25565`.

## Architecture notes

- **Configuration lives in `docker-compose.yml`, not in `data/`.** The `itzg/minecraft-server` image generates `data/server.properties`, `data/bukkit.yml`, `data/spigot.yml`, etc. from environment variables on each startup. To change server behavior (difficulty, view distance, ops, PVP, etc.), edit the `environment:` block in `docker-compose.yml` — edits to files under `data/` will be overwritten.

- **`data/` is the bind-mounted server volume.** Worlds (`world/`, `world_nether/`, `world_the_end/`), plugin data, logs, and the Paper jar all live here and persist across restarts. The directory is currently untracked (see `.gitignore`).

- **Two ways to install plugins, and they behave differently:**
  - `MODRINTH_PROJECTS` env var (currently commented out) — image auto-downloads plugins on each start. Recent commits intentionally disabled this for `luckperms`, `worldguard`, `worldedit`, and `coreprotect`.
  - Manual jars dropped into `data/plugins/` — currently `WorldEdit` and `WorldGuard` jars are present from earlier auto-installs and will load even though they're commented out in compose. If removing a plugin, delete both the env var entry and the jar in `data/plugins/`.

- **Paper version is pinned by `VERSION: "LATEST"`** in compose, which resolves at container start. The exact resolved jar lives at `data/paper-*.jar` and is recorded in `data/.papermc-manifest.json`.

## Conventions

- The README is in Czech; user-facing strings (server name, etc.) are also Czech. Keep them that way.
- Operator list is managed via the `OPS:` env var in compose, not by editing `data/ops.json`.
