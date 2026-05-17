# functions/

Cloudflare Pages Functions — the API layer for the web. Each `.ts` file under
`functions/api/…` becomes an HTTP endpoint of the same path.

See [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the high-level design and
data model. This file documents the endpoint surface only.

> **Template status.** The listing below reflects the planned API from the
> architecture doc. Refine paths, status codes, and payloads as endpoints are
> implemented.

---

## Conventions

- **Languages** — TypeScript only. No JavaScript files in this tree.
- **Errors** — JSON `{ "error": "<code>", "message": "<human>" }` with the
  appropriate HTTP status.
- **Auth** — three tiers, checked by `_middleware.ts`:
  - `public` — no auth.
  - `session` — requires a valid session cookie (`sid=…`).
  - `admin` — `session` plus `users.role = 'admin'`.
  - `signed` — requires `Authorization: Bearer <SYNC_SECRET>` (only `/api/sync/*`).
- **Time** — all timestamps are Unix seconds (UTC).
- **Validation** — request bodies validated with `zod` (or similar) before
  touching D1.
- **Rate limits** — applied per-IP for `auth/request-magic-link` and
  `whitelist/request`; values TBD.

---

## Bindings (set in `wrangler.toml` / Pages dashboard)

| Binding name      | Type        | Purpose                                  |
|-------------------|-------------|------------------------------------------|
| `DB`              | D1          | Main database                            |
| `SYNC_SECRET`     | Env / secret| Shared secret for sync-agent auth        |
| `MAGIC_FROM`      | Env         | "From" email address for magic links     |
| `MAIL_API_KEY`    | Secret      | Email provider API key                   |
| `SITE_URL`        | Env         | Canonical site origin (for magic links)  |

<!-- PASTE: confirm exact binding names once decided -->

---

## Endpoint inventory

### Auth

| Method | Path                              | Auth     | Notes                                   |
|--------|-----------------------------------|----------|-----------------------------------------|
| POST   | `/api/auth/request-magic-link`    | public   | Body: `{ email }`. Always returns 200.  |
| GET    | `/api/auth/verify`                | public   | Query: `token`. Sets `sid` cookie.      |
| POST   | `/api/auth/logout`                | session  | Clears `sid` cookie, deletes session row. |
| GET    | `/api/auth/me`                    | session  | Returns current user + role.            |

### Whitelist (user-facing)

| Method | Path                          | Auth    | Notes                                          |
|--------|-------------------------------|---------|------------------------------------------------|
| POST   | `/api/whitelist/request`      | session | Body: `{ mc_username, note? }`. One pending per user. |
| GET    | `/api/whitelist/me`           | session | Returns user's current request status.         |

### Admin

| Method | Path                                       | Auth  | Notes                                |
|--------|--------------------------------------------|-------|--------------------------------------|
| GET    | `/api/admin/requests`                      | admin | Query: `status=pending&limit=…`      |
| POST   | `/api/admin/requests/:id/approve`          | admin | Body: `{ note? }`                    |
| POST   | `/api/admin/requests/:id/reject`           | admin | Body: `{ note? }`                    |
| POST   | `/api/admin/requests/:id/revoke`           | admin | Reverses an approval                 |
| GET    | `/api/admin/ops`                           | admin | Lists current ops                    |
| POST   | `/api/admin/ops`                           | admin | Body: `{ mc_username, level }`       |
| DELETE | `/api/admin/ops/:username`                 | admin | Removes op                           |
| POST   | `/api/admin/users/:id/role`                | admin | Body: `{ role }`. Promote/demote.    |

### Events

| Method | Path                              | Auth    | Notes                              |
|--------|-----------------------------------|---------|------------------------------------|
| GET    | `/api/events`                     | public  | Upcoming events, paginated.        |
| POST   | `/api/admin/events`               | admin   | Create event.                      |
| PATCH  | `/api/admin/events/:id`           | admin   | Update.                            |
| DELETE | `/api/admin/events/:id`           | admin   | Delete.                            |
| POST   | `/api/events/:id/rsvp`            | session | Body: `{ status }`                 |

### Stats

| Method | Path                       | Auth   | Notes                                  |
|--------|----------------------------|--------|----------------------------------------|
| GET    | `/api/stats/:username`     | public | Public-facing player profile data.     |
| POST   | `/api/stats/ingest`        | signed | Bulk push from the sync-agent.         |

### Sync (sync-agent only)

| Method | Path                          | Auth   | Notes                                                  |
|--------|-------------------------------|--------|--------------------------------------------------------|
| GET    | `/api/sync/desired-state`     | signed | Returns the current desired whitelist + ops + version. |

<!-- PASTE: add/remove endpoints as the design firms up -->

---

## Folder layout

```text
functions/
├── README.md             # this file
├── _middleware.ts        # auth + CORS + logging
├── _lib/                 # shared helpers (db, auth, errors, mail)
└── api/
    ├── auth/
    ├── whitelist/
    ├── admin/
    ├── events/
    ├── stats/
    └── sync/
```

<!-- PASTE: any deviations from the default Pages Functions layout -->
