# sync-agent/

The bridge between the cloud-hosted [`web/`](../web/README.md) and the
on-Pi Minecraft server. Runs as a Docker service alongside `minecraft-server`,
polls the cloud API every ~5 minutes, diffs the **desired state** against the
**live state**, and applies the delta via RCON.

> **Why a separate component?** So that the Minecraft server stays usable when
> the cloud is unreachable. If `sync-agent` crashes or Cloudflare is down,
> `minecraft-server` keeps running on its last-applied configuration; queued
> changes apply as soon as the agent returns. See [§6 of the architecture
> doc](../web/ARCHITECTURE.md#6-pull-based-sync--the-core-principle).

---

## Responsibilities

1. **Pull desired state.** GET `/api/sync/desired-state` from Cloudflare every
   `POLL_INTERVAL` (default 5 min).
2. **Read live state.** Either via RCON (`whitelist list`, `ops list`) or by
   reading `data/whitelist.json` / `data/ops.json` directly from the bind mount.
3. **Compute diff.** Set-difference between desired and live for each managed
   resource (whitelist, ops).
4. **Apply diff.** Emit RCON commands: `whitelist add <user>`,
   `whitelist remove <user>`, `op <user>`, `deop <user>`. Each command is
   idempotent.
5. **Push stats** *(later)*. POST aggregated player stats to
   `/api/stats/ingest`.
6. **Log + report health.** Structured logs to stdout; surface last-sync
   timestamp via a tiny HTTP `/healthz` endpoint for `docker compose ps` checks.

<!-- PASTE: any additional responsibilities (announcements, scheduled
     restarts, MotD updates, etc.) -->

---

## Non-responsibilities

- Does **not** modify the Minecraft server JAR or plugin configs.
- Does **not** accept inbound connections from the cloud.
- Does **not** hold any state of its own — re-derives everything from cloud +
  live state on each tick. Stateless restart is safe.

---

## Configuration (env vars)

| Var                   | Default                            | Purpose                                  |
|-----------------------|------------------------------------|------------------------------------------|
| `SYNC_API_URL`        | `https://<site>/api/sync/desired-state` | Endpoint to poll                    |
| `SYNC_SECRET`         | *(required)*                       | Shared bearer token                      |
| `POLL_INTERVAL`       | `300s`                             | How often to pull                        |
| `RCON_HOST`           | `minecraft-server`                 | Compose service name                     |
| `RCON_PORT`           | `25575`                            |                                          |
| `RCON_PASSWORD`       | *(required)*                       | Set on the MC server too                 |
| `DRY_RUN`             | `false`                            | Log diffs without executing RCON         |
| `LOG_LEVEL`           | `info`                             |                                          |

<!-- PASTE: confirm final var names and add any others (stats push toggle,
     rate-limit knobs, etc.) -->

---

## Algorithm (sketch)

```text
loop forever:
    desired = GET /api/sync/desired-state            # may 304 via If-None-Match
    if no change since last tick:
        sleep POLL_INTERVAL; continue

    live_whitelist = rcon("whitelist list")
    live_ops       = rcon("ops list")

    for user in desired.whitelist - live_whitelist:
        rcon("whitelist add " + user)
    for user in live_whitelist - desired.whitelist:
        rcon("whitelist remove " + user)

    for op in desired.ops - live_ops:
        rcon("op " + op.name)
    for op in live_ops - desired.ops:
        rcon("deop " + op.name)

    report_health(success, applied_count)
    sleep POLL_INTERVAL
```

Properties:

- **Idempotent**: re-running with no change is a no-op.
- **Bounded delta**: diff is at most O(|desired| + |live|) per tick.
- **Crash-safe**: state is re-derived from sources on next start.

<!-- PASTE: refine — e.g. clarify ordering when a player is both op'd and
     whitelisted in the same tick, decide on backoff/retry policy -->

---

## Failure handling

| Failure                                      | Behaviour                                   |
|----------------------------------------------|---------------------------------------------|
| Cloud unreachable                            | Log + skip tick. Live state untouched.      |
| Cloud returns 5xx                            | Exponential backoff up to `POLL_INTERVAL`.  |
| RCON unreachable                             | Log + skip tick. Retry next tick.           |
| Malformed desired-state payload              | Log + alert + skip. Refuse to apply partial state. |
| Diff would remove the bootstrap admin        | Refuse + log. Hard-coded safety check.      |

<!-- PASTE: any additional safety rails you want enforced -->

---

## Deployment

Adds a service to the existing [`../docker-compose.yml`](../docker-compose.yml):

```yaml
  sync-agent:
    build: ./sync-agent
    container_name: mc-sync-agent
    depends_on:
      - minecraft-server
    environment:
      TZ: "Europe/Prague"
      SYNC_API_URL: "https://<site>/api/sync/desired-state"
      SYNC_SECRET: "${SYNC_SECRET}"
      POLL_INTERVAL: "300s"
      RCON_HOST: minecraft-server
      RCON_PASSWORD: "${RCON_PASSWORD}"
    restart: unless-stopped
    networks:
      - mcnet
```

`SYNC_SECRET` and `RCON_PASSWORD` go into the existing `.env` file (also used
by `playit`).

<!-- PASTE: confirm Dockerfile base image (alpine + python? distroless? go?)
     and language choice for the agent -->

---

## Folder layout

```text
sync-agent/
├── README.md         # this file
├── Dockerfile
├── src/              # agent source (language TBD)
├── tests/
└── .env.example
```

<!-- PASTE: finalize once language is chosen -->

---

## Open questions

- [ ] Implementation language — Python (simple, fits Pi well) vs. Go
      (single static binary)?
- [ ] Read live state via RCON or by reading `whitelist.json` / `ops.json`
      from the bind mount? RCON is the source of truth but adds an RTT;
      file-read is cheaper but races with the MC server's writes.
- [ ] Should the agent also manage the `OPS:` env-var list in compose? (No —
      env vars are applied at container start; managing them at runtime via
      RCON is correct.)
- [ ] Where to surface health: just logs, or a Prometheus `/metrics` endpoint?
