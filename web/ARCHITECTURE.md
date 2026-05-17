# Architecture — Salesian LAN Minecraft Web

> **Template status.** Sections below contain a starter design derived from the
> initial conversation. Replace or extend each section as the design firms up.
> Paste-points are marked with `<!-- PASTE: ... -->`.

---

## 1. Overview

A public website that describes the Salesian LAN-party Minecraft server, shows
players how to join, and provides a self-service flow for getting whitelisted.
Authenticated users can manage their profile and see stats; administrators have
a separate UI for approving whitelist requests, granting operator status, and
running LAN-party event sign-ups.

The site is hosted on Cloudflare Pages; its API lives in
[`functions/`](./functions/README.md) as Cloudflare Pages Functions. The
Minecraft server on the Raspberry Pi remains the source of truth for the live
game world, and it operates **independently** of the web — the web only
influences server state through a pull-based sync handled by the
[`sync-agent`](../sync-agent/README.md).

<!-- PASTE: any additional context, history, or motivation for this feature -->

---

## 2. Goals & Non-goals

### Goals

- **Public landing page** with server description and join instructions
  (anonymous access).
- **Self-service whitelist** flow gated by email-magic-link login and
  admin approval.
- **Admin console** for managing whitelist requests, operators, and LAN events.
- **Player profiles & stats** surfaced from data the Pi pushes to the cloud.
- **Event registration** for upcoming LAN parties.
- **Strict modularity** — the MC server must keep working if any part of the
  web stack fails.

### Non-goals

- Real-time player chat or in-game commands from the web.
- Replacing RCON / in-game `/op` / `/whitelist` commands — the web is a
  convenience layer on top of these primitives.
- A general-purpose Minecraft hosting panel — this serves *this* server only.

<!-- PASTE: refine the goals / add explicit non-goals you want recorded -->

---

## 3. High-level architecture

```text
                                ┌────────────────────────┐
   Players / Admins  ──HTTPS──▶ │  Cloudflare Pages      │
                                │  (Astro static + SSR)  │
                                │  + Pages Functions API │
                                │  + D1 (SQLite at edge) │
                                └──────────┬─────────────┘
                                           │  /api/sync/desired-state
                                           │  (signed, pull-only)
                                           ▼
                                ┌────────────────────────┐
                                │  sync-agent (on the Pi)│
                                │  polls every ~5 min    │
                                │  diffs desired ↔ live  │
                                │  applies via RCON      │
                                └──────────┬─────────────┘
                                           │ RCON
                                           ▼
                                ┌────────────────────────┐
                                │  minecraft-server      │
                                │  (Paper, itzg image)   │
                                └────────────────────────┘
```

Key property: **the arrow from the cloud to the Pi is dashed** in the sense
that the Pi *pulls* — Cloudflare never initiates a connection to the Pi. This
means no inbound holes in the home network and no playit dependency for the
control plane.

<!-- PASTE: alternative diagrams, sequence diagrams for specific flows, etc. -->

---

## 4. Components

### 4.1 Astro site (`web/src/`)

- Static pages for the landing / how-to-join / events list (anonymous).
- React islands (shadcn/ui) for interactive bits: login form, whitelist request
  form, admin tables.
- Server-rendered pages for authenticated views (`/profil`, `/admin/*`).
- All user-facing copy in Czech; `lang="cs"` on the document.

### 4.2 Pages Functions (`web/functions/`)

The API. See [`functions/README.md`](./functions/README.md) for the endpoint
inventory. Functions handle:

- Magic-link issuance and verification.
- Whitelist request lifecycle (`pending` → `approved` / `rejected`).
- Operator grant/revoke (admin only).
- Event CRUD + RSVP.
- Stats ingestion endpoint (called by the sync-agent, write-only).
- **`/api/sync/desired-state`** — the single endpoint the sync-agent reads.

### 4.3 Cloudflare D1

SQLite database holding users, requests, ops, events, RSVPs, and stat snapshots.
Schema lives in [`db/schema.sql`](./db/schema.sql) (TODO).

### 4.4 sync-agent (on the Pi)

A small Docker service alongside `minecraft-server`. Polls
`/api/sync/desired-state` every ~5 min, computes a diff against the live MC
server (via RCON / reading `whitelist.json`, `ops.json`), and applies changes.
Pushes stats back to the cloud. See [`../sync-agent/README.md`](../sync-agent/README.md).

<!-- PASTE: any additional components (caching layer, image CDN, etc.) -->

---

## 5. Primary data flows

### 5.1 Whitelist self-service

```text
1. Visitor opens /pridat-se, fills in MC username + email.
2. Web sends magic link to email (Cloudflare Email Workers or Resend).
3. Visitor clicks link → session cookie issued → row inserted in
   `whitelist_requests` with status='pending'.
4. Admin sees it in /admin/zadosti, clicks Approve.
5. Status flips to 'approved'. No live MC call happens yet.
6. Within ≤5 min, sync-agent polls /api/sync/desired-state, sees the
   approved username is not in the live whitelist, runs
   `rcon whitelist add <user>`.
7. Player joins the server.
```

### 5.2 Operator management

<!-- PASTE: describe the op flow once you've decided whether grants are
     immediate-on-approve or also gated by a separate admin action -->

### 5.3 Event registration

<!-- PASTE: how events are created, who can RSVP, capacity rules, etc. -->

### 5.4 Stats ingestion

<!-- PASTE: which stats are surfaced (playtime / deaths / blocks placed?),
     how often the sync-agent pushes them, retention -->

---

## 6. Pull-based sync — the core principle

The cloud holds **desired state**; the Pi holds **actual state**; the sync-agent
reconciles. This pattern is borrowed from Kubernetes controllers and is chosen
deliberately for these properties:

| Property                            | Why it matters here                              |
|-------------------------------------|--------------------------------------------------|
| No inbound connections to the Pi    | Home network stays closed; no playit for control |
| Cloud outage ⇒ stale, not broken    | MC server keeps running on its last applied state|
| Pi outage ⇒ web still functional    | Requests queue up and apply when Pi returns      |
| Idempotent application              | Re-polling is safe; sync = `desired - actual`    |
| Single source of truth per layer    | Cloud = intent, Pi = reality, agent = bridge     |

### Polling cadence

- Default: **every 5 minutes**.
- Acceptable latency for whitelist approvals: a few minutes.
- Tunable via env var on the sync-agent.

### Desired-state payload (sketch)

```jsonc
{
  "version": 1,
  "generated_at": "2026-05-17T12:34:56Z",
  "whitelist": ["petrkucerak", "..."],
  "ops": [{"name": "petrkucerak", "level": 4}],
  "etag": "<hash for If-None-Match optimization>"
}
```

<!-- PASTE: finalize the payload schema, decide on ETag vs version cursor,
     decide whether to include rejected/banned lists -->

---

## 7. Authentication & authorization

### Login

- **Email magic links.** No passwords. Tokens are single-use, time-limited
  (e.g. 15 min), and tied to the requesting IP/UA fingerprint loosely.
- Sessions: HTTP-only secure cookies, ≈30-day rolling expiry.

### Authorization tiers

| Role        | Granted how                                | Can do                                   |
|-------------|--------------------------------------------|------------------------------------------|
| Anonymous   | (default)                                  | Read public pages, request a magic link  |
| `user`      | Logged in via magic link                   | Submit whitelist request, view own status, RSVP to events |
| `approved`  | Admin approved their whitelist request     | Same as `user`, plus access to MC server (via sync) |
| `admin`     | Bootstrapped in DB; promotable by admins   | Approve/reject requests, manage ops, manage events |

### Admin approval gate

A user being logged in is **not** sufficient to join the MC server. Admin
approval of a `whitelist_requests` row is the gate. This is the explicit design
choice — the web is open to everyone to browse, but server access is curated.

<!-- PASTE: bootstrap process for the first admin, rate-limiting policy for
     magic-link requests, what happens to abandoned pending requests -->

---

## 8. Data model (D1 schema sketch)

```sql
-- users: anyone who has ever logged in
CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  mc_username   TEXT UNIQUE,           -- nullable until they submit a request
  display_name  TEXT,
  role          TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'admin'
  created_at    INTEGER NOT NULL,
  last_login_at INTEGER
);

-- whitelist_requests: drives desired-state for `whitelist`
CREATE TABLE whitelist_requests (
  id           INTEGER PRIMARY KEY,
  user_id      INTEGER NOT NULL REFERENCES users(id),
  mc_username  TEXT NOT NULL,
  status       TEXT NOT NULL,          -- 'pending' | 'approved' | 'rejected' | 'revoked'
  note         TEXT,
  reviewed_by  INTEGER REFERENCES users(id),
  created_at   INTEGER NOT NULL,
  reviewed_at  INTEGER
);

-- ops: drives desired-state for `ops`
CREATE TABLE ops (
  user_id   INTEGER PRIMARY KEY REFERENCES users(id),
  level     INTEGER NOT NULL DEFAULT 4,
  granted_by INTEGER REFERENCES users(id),
  granted_at INTEGER NOT NULL
);

-- events: LAN parties
CREATE TABLE events (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,
  starts_at   INTEGER NOT NULL,
  ends_at     INTEGER,
  capacity    INTEGER,
  description TEXT
);

CREATE TABLE event_rsvps (
  event_id INTEGER NOT NULL REFERENCES events(id),
  user_id  INTEGER NOT NULL REFERENCES users(id),
  status   TEXT NOT NULL,              -- 'going' | 'maybe' | 'declined'
  PRIMARY KEY (event_id, user_id)
);

-- stats: latest snapshot per player, pushed by sync-agent
CREATE TABLE player_stats (
  mc_username  TEXT PRIMARY KEY,
  playtime_min INTEGER,
  deaths       INTEGER,
  -- ...
  updated_at   INTEGER NOT NULL
);

-- auth: magic-link tokens (short-lived)
CREATE TABLE magic_tokens (
  token       TEXT PRIMARY KEY,
  email       TEXT NOT NULL,
  expires_at  INTEGER NOT NULL,
  used_at     INTEGER
);

-- auth: sessions
CREATE TABLE sessions (
  id          TEXT PRIMARY KEY,        -- random opaque token
  user_id     INTEGER NOT NULL REFERENCES users(id),
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL
);
```

<!-- PASTE: refine column types, add indexes, decide retention policy for
     `magic_tokens` and `sessions`, expand `player_stats` -->

---

## 9. API surface

Detailed endpoint listing lives in
[`functions/README.md`](./functions/README.md). The architectural shape:

- `POST /api/auth/request-magic-link` — public
- `GET  /api/auth/verify?token=…`     — public
- `POST /api/auth/logout`             — session
- `POST /api/whitelist/request`       — session
- `GET  /api/whitelist/me`            — session
- `GET  /api/admin/requests`          — admin
- `POST /api/admin/requests/:id/approve` — admin
- `POST /api/admin/requests/:id/reject`  — admin
- `POST /api/admin/ops`               — admin
- `DELETE /api/admin/ops/:username`   — admin
- `GET  /api/events`                  — public
- `POST /api/events/:id/rsvp`         — session
- `GET  /api/stats/:username`         — public (or session — TBD)
- `POST /api/stats/ingest`            — sync-agent (signed)
- `GET  /api/sync/desired-state`      — sync-agent (signed)

<!-- PASTE: any additional endpoints, or move auth model into per-endpoint table -->

---

## 10. Failure modes & graceful degradation

| Failure                          | Effect                                            |
|----------------------------------|---------------------------------------------------|
| Cloudflare Pages down            | Web inaccessible; MC server unaffected; whitelist additions deferred until back |
| D1 down                          | Same as above (Pages depends on it for most API)  |
| sync-agent crashed on the Pi     | Web still accepts requests; MC state freezes at last sync; restart fixes |
| MC server down                   | Web fully functional; sync-agent retries; queued changes apply on restart |
| Email provider outage            | New users can't log in; existing sessions continue |
| Token table grew unbounded       | Login latency rises; mitigated by TTL cleanup     |

<!-- PASTE: add monitoring/alerting notes once you decide where to send alerts -->

---

## 11. Security model

- **No inbound to the Pi.** Sync agent only makes outbound HTTPS to Cloudflare.
- **Signed sync endpoints.** `/api/sync/*` requires a shared secret in an
  `Authorization: Bearer …` header; secret is set in the Pages dashboard and
  in the sync-agent `.env`. Rotatable.
- **Magic-link tokens** are random 32-byte URL-safe strings, single-use,
  15-minute TTL.
- **Sessions** are opaque random IDs in HTTP-only cookies; CSRF protection via
  same-site=Lax + explicit CSRF tokens on state-changing forms.
- **Admin actions** are logged to an `audit_log` table (TODO).
- **Email enumeration** mitigated by returning the same response whether or not
  the email is known.

<!-- PASTE: threat model specifics, rate-limit thresholds, secret rotation cadence -->

---

## 12. Local development

<!-- PASTE: full local setup. At minimum: Node version, wrangler version,
     how to create a local D1 instance, how to seed an admin user, how to fake
     the magic-link email locally (log to console? mailhog?), how to point
     a local sync-agent at the local API. -->

---

## 13. Deployment

<!-- PASTE: Cloudflare account/project layout, branch → environment mapping
     (e.g. main → production, PRs → preview), required env vars and bindings,
     custom domain config, D1 migration workflow, secret management. -->

---

## 14. Open questions / decisions to make

- [ ] Email provider — Cloudflare Email Workers vs. Resend vs. Postmark?
- [ ] Hosting domain — subdomain of `salesianipardubice.cz`?
- [ ] Should `mc_username` be verifiable (e.g. by checking Mojang API for a
      valid UUID) or trusted at face value?
- [ ] Should we surface live online-player count? (would need an additional
      Pi → cloud push or a server-list query from a Worker).
- [ ] Audit log retention — how long, and surface to admin UI?
- [ ] Bootstrap mechanism for the first admin user.

<!-- PASTE: add/cross off as decisions land -->
