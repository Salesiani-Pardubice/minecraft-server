# web/

Companion web frontend for the Salesian LAN-party Minecraft server, deployed to
**Cloudflare Pages** with the API in `functions/` (Cloudflare Pages Functions).

> **Design principle.** The web is purely additive. If Cloudflare Pages, the
> database, or the [`sync-agent`](../sync-agent/README.md) go down, the
> Minecraft server continues to operate normally — players just can't sign up
> for new whitelist access until the web is back. See
> [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design.

---

## Stack

| Layer       | Tech                                                  |
|-------------|-------------------------------------------------------|
| Framework   | [Astro](https://astro.build) (static + islands)       |
| Styling     | [Tailwind CSS](https://tailwindcss.com)               |
| Components  | [shadcn/ui](https://ui.shadcn.com) (React islands)    |
| Hosting     | [Cloudflare Pages](https://pages.cloudflare.com)      |
| API         | Cloudflare Pages Functions (`functions/`)             |
| Database    | Cloudflare D1 (SQLite at the edge)                    |
| Auth        | Email magic links + admin approval                    |
| MC sync     | Pull-based — see [`../sync-agent/`](../sync-agent/)   |

---

## Folder layout

```text
web/
├── README.md              # this file
├── ARCHITECTURE.md        # full design — start here when picking up the project
├── functions/             # Cloudflare Pages Functions (the API)
│   └── README.md          # API surface reference
├── src/
│   ├── pages/             # Astro file-routed pages (Czech UI)
│   ├── components/        # Astro + shadcn components
│   ├── layouts/
│   ├── lib/               # client/server helpers (auth, db, fetch)
│   └── styles/
├── db/
│   ├── schema.sql         # D1 schema
│   └── migrations/
├── public/                # static assets
├── astro.config.mjs
├── tailwind.config.mjs
├── wrangler.toml          # Pages + D1 + bindings config
├── package.json
└── .env.example
```

> **Conventions** — user-facing copy is in **Czech** (matches the project README);
> code, comments, commit messages, and architecture docs are in **English**.

---

## Quickstart (local dev)

<!-- PASTE: detailed setup instructions, prerequisites (Node version, wrangler login, etc.) -->

```sh
# install
npm install

# run dev server (Astro + Pages Functions via wrangler)
npm run dev

# apply D1 schema locally
npx wrangler d1 execute <db-name> --local --file=db/schema.sql
```

---

## Deployment

<!-- PASTE: Cloudflare Pages project name, build command, env vars to set in Pages dashboard,
     custom domain, branch → environment mapping, etc. -->

---

## Related components

- [`../sync-agent/`](../sync-agent/) — the puller that runs on the Pi alongside
  the MC server and reconciles cloud state into RCON commands.
- [`../docker-compose.yml`](../docker-compose.yml) — Pi-side services; the
  sync-agent will be added here as a new service.
- [`../CLAUDE.md`](../CLAUDE.md) — repo-wide instructions.
