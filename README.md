# Salesiánský Minecraft Server

Jedním ze salesiánských míst působnosti je i hřiště. Pro mnohé z nás to není
jen venkovní prostor, ale i ten virtuální. Proto jsme se rozhodli připravovat
sérii tzv. LAN přespávaček. Tento repozitář slouží jako podpora pro jednu
z nich — konkrétně Minecraft LAN přespávačku — a obsahuje vše potřebné
pro spuštění herního serveru na pořádnou LAN párty.

Server běží na Raspberry Pi 5 (8 GB RAM, 1 TB NVMe, Debian 12) a je veřejně
dostupný přes playit.gg tunel na adrese **`mc.salesianipardubice.cz`**.

## Komponenty

`docker-compose.yml` spouští tři služby:

| Služba | Image | Účel |
|--------|-------|------|
| `minecraft-server` | `itzg/minecraft-server:2026.5.2-java21` | Paper server 1.21.11, 4 GB RAM, Aikar GC flagy |
| `mc-backup` | `itzg/mc-backup:2026.5.0` | Automatické zálohování světa přes RCON (každých 24 h, retence 14 dní) |
| `playit` | `ghcr.io/playit-cloud/playit-agent:0.16` | Tunel z internetu na `mc.salesianipardubice.cz` |

## Příprava

Před prvním spuštěním vytvořte soubor `.env` v rootu repozitáře:

```
SECRET_KEY=<agent secret z playit.gg dashboardu>
```

Bez `SECRET_KEY` se nespustí jen `playit` — Minecraft server poběží lokálně
na `localhost:25565`.

Adresář pro zálohy na hostiteli:

```sh
mkdir -p /home/pedro/backups
```

## Spuštění

```sh
docker compose up -d                          # spustí všechny služby na pozadí
docker compose down                           # zastaví a odstraní kontejnery
docker compose restart minecraft-server       # restart pouze MC serveru
docker compose pull && docker compose up -d   # aktualizace imagů
```

## Užitečné příkazy

```sh
# Logy
docker compose logs -f minecraft-server       # živé logy serveru
docker compose logs -f mc-backup              # živé logy záloh
docker compose logs -f playit                 # živé logy tunelu

# RCON konzole (CTRL+D pro odchod)
docker exec -i minecraft-server rcon-cli
docker exec -i minecraft-server rcon-cli list
docker exec -i minecraft-server rcon-cli "say Restart za 5 minut"
docker exec -i minecraft-server rcon-cli "op petrkucerak"

# Diagnostika
docker stats minecraft-server                 # živé CPU / RAM
df -h                                         # volné místo na disku

# Zálohy
docker exec mc-backup backup now              # vynutí okamžitou zálohu
ls -lh /home/pedro/backups                    # seznam záloh
```

## Konfigurace

**Veškerá konfigurace serveru je v `docker-compose.yml`**, nikoli v souborech
pod `data/`. Image `itzg/minecraft-server` generuje `server.properties`,
`bukkit.yml` a další z proměnných prostředí při každém startu — ruční úpravy
souborů v `data/` budou přepsány.

Pro změnu obtížnosti, view-distance, operátorů, PVP atd. upravte sekci
`environment:` v compose souboru a restartujte server.

## Zálohování

`mc-backup` sidecar se připojuje k serveru přes RCON, spouští
`save-off` / `save-all flush` / `save-on` a archiv `world-*.tgz` ukládá
do `/home/pedro/backups`. Interval je 24 h od startu kontejneru (ne wall-clock);
pro zálohy okolo 03:00 restartujte stack v tu dobu. Archivy starší než 14 dní
jsou mazány automaticky.

## Pluginy

Aktivní pluginy (jary v `data/plugins/`):

| Plugin | Účel |
|--------|------|
| WorldEdit | In-game editor pro operátory |
| WorldGuard | Ochrana regionů |

Pluginy lze instalovat dvěma způsoby:

- **`MODRINTH_PROJECTS`** v compose — image stáhne plugin automaticky při každém startu.
- **Ruční jar v `data/plugins/`** — načte se vždy, bez ohledu na compose.

Pro úplné odstranění pluginu smažte jak záznam v `MODRINTH_PROJECTS`, tak
příslušný jar v `data/plugins/`.
