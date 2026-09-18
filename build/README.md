# Stavění na serveru

Skripty v `build/` staví do živého světa přes WorldEdit po RCON. Nic se nestaví
ručně: každá stavba je kód, takže ji jde na novém světě vygenerovat znovu.

```
build/mc.py         fronta WorldEdit příkazů, posun počátku, hlídání chyb
build/micov.py      Míčov: kostel sv. Matouše, hřbitov, fara, sad, cesty
tools/terrain_survey.py   čtení terénu přímo z region souborů
```

## Jak to pustit

```bash
python3 build/micov.py --dry-run              # jen spočítá příkazy
python3 build/micov.py terrain church          # vybrané etapy
python3 build/micov.py                         # všechny krom demolish a tidy
python3 build/micov.py --force terrain         # srovná i tam, kde už něco stojí
```

Etapy: `demolish`, `tidy`, `terrain`, `church`, `graveyard`, `fara`, `orchard`,
`paths`, `lights`, `spawn`. **Pořadí není libovolné** — viz pasti níže.

## Míčov

Předloha je skutečná rekreační fara Míčov (49.9046282N, 15.6042375E) a kostel
sv. Matouše vedle ní; půdorys je obkreslený z mapy, kterou Petr zakreslil
barvami: oranžově cesty, šedě plot kolem hřbitova, modře neprůchozí plot sadu,
fialově kamenná zídka (na několika místech přerušená), zeleně hranice fary,
žlutě ohniště. Měřítko vyšlo 1 blok = 1 metr.

Všechno se počítá v místních souřadnicích se středem kostela v počátku (`u`
na východ, `v` na jih); `Session(origin=ORIGIN)` je posouvá do světa. Celý
areál se přestěhuje změnou `ORIGIN`, což už jednou bylo potřeba.

| co | kde (místně) | výška |
|---|---|---|
| kostel sv. Matouše | u −15..15, v −10..10 | podlaha 70 |
| hřbitov (plato) | u −22..20, v −18..16, useknutý roh u silnice | 70 |
| fara | u 50..68, v −14..−3 | 71 |
| umývárna + pergola | u 58..73, v −26..−19 | 67 |
| dílna | u 72..80, v −40..−32 | 66 |
| sad s ohništěm | u 0..40, v −60..−40 | podle terénu |
| spawn | u 63, v −17 (zahrada fary) | world 113, 71, −80 |

`ORIGIN = (50, −63)`, tedy kostel stojí na world (50, −63). Plato hřbitova je
**tři bloky** nad cestou, jak si Petr přál — ne na kopci; první pokus stál na
přirozeném kopci o 17 bloků vyšším a nešel do krajiny zasadit.

## Pasti, které to stály nejvíc času

1. **Výškové mapy v chunku počítají listí a kmeny.** Sloupec pod dubem se čte
   jako vrcholek dubu, takže terénní úpravy sypaly hlínu do korun. `OCEAN_FLOOR_WG`
   by odpověděla, ale plně vygenerované chunky ji neukládají. Proto
   `ground_grid()` čte bloky samotné a zastaví se na prvním, co není vzduch,
   zeleň, voda nebo naše zdivo.
2. **Stavbu čte průzkum jako terén.** Střecha je pevný blok, takže druhý běh
   `terrain` srovnal kostel se zemí. Etapa to teď kontroluje a odmítne se
   spustit (`--force` to obejde a stavbu skutečně zbourá).
3. **Zeď postavená na zemi se příště čte jako zem.** Každý běh `fara` přidal
   zídce další řadu — došla do pěti a kříž visel dvacet bloků ve vzduchu.
   Průzkum proto dostává `extra_cover=BUILT`, seznam našich materiálů.
4. **Do toho seznamu nepatří andesit.** Je to naše dlažba, ale roste i v zemi;
   když se bere jako zdivo, průzkum propadne přírodní vrstvou o dvanáct bloků
   níž a čistící průchod tam vyhloubí jámu. Dlažba **je** zem — do `BUILT`
   patří jen to, co na zemi *stojí*.
5. **Před srovnáním terénu je nutné plochu odlesnit** (`clear_growth`), jinak
   zůstanou stromy uvnitř budov.
6. **WorldEdit nebere seznam tagů.** `//replace ##logs,##leaves air` čte jako
   jediný tag jménem `logs,##leaves` a odmítne to — jedna maska na příkaz.
7. **Odmítnutý příkaz neřekne vždycky „error".** Tenhle se vrátil jako
   „Too many arguments." a řádek s usage, takže se tvářil jako úspěch.
   `Session.flush()` teď hlídá i tyhle formulace.
8. **Cesty se kladou až po budovách a prosekávají si průchod**, takže trasa,
   která vede přes půdorys, prostřelí barák. Kolize kontroluje test níže.

## Kontrola po zásahu

```python
# kolize cest s budovami
import sys; sys.path.insert(0, "build")
import micov as m
cells = m.trace(m.WALK, width=1)
[c for c in cells if m.HOUSE["x1"] <= c[0] <= m.HOUSE["x2"]
                  and m.HOUSE["z1"] <= c[1] <= m.HOUSE["z2"]]
```

`python3 build/micov.py tidy` uklidí zdivo a dlažbu, které plán už nikam
neklade, a zasype jámy vyhloubené dřívějším omylem. Po každé změně geometrie
je dobré ho pustit.

## Stavby po mapě

`build/landmarks.py` staví osm samostatných staveb roztroušených po světě.
Místa nejsou vybraná od oka: skript prošel všech 8 456 vygenerovaných chunků
a hledal podle biomu, střední výšky a převýšení nad okolím.

```bash
python3 build/landmarks.py                 # všechny
python3 build/landmarks.py hrad koloseum   # vybrané
python3 build/landmarks.py --markers       # přepíše seznam značek pro mapu
```

| stavba | kde | proč tam |
|---|---|---|
| Hrad | 976, −192 | nejvyšší terén na mapě (y ≈ 137) |
| Létající loď | 890, −250 | ve vzduchu na y 186 nad horami |
| Chata v pralese | 768, −1536 | džungle u pobřeží |
| Dům na stromě | −320, −256 | starý les; strom je postavený, žádný tam není dost silný |
| Čarodějnická chalupa | 136, −328 | temný les, nejnižší sloupec nad hladinou |
| Koloseum | 690, 75 | souvislá pláň |
| Loď | 990, −1626 | 12 bloků hloubky, 8 bloků od břehu |
| Větrný mlýn | 480, 144 | kopec v louce, převyšuje okolí o 33 bloků |

Společné díly (terén, střechy, cesty, trupy, stromy) jsou v `build/parts.py`;
oba stavební skripty je sdílejí.

### Značky v mapě

squaremap si svůj `markers.json` průběžně přepisuje, takže se do něj nepíše.
Seznam staveb vygeneruje `landmarks.py --markers` do `admin-api/landmarks.json`,
ten je zakompilovaný v binárce admin-api a ta ho **přimíchá do odpovědi**
na `/mapa/tiles/{svět}/markers.json`. Ikonu servíruje taky admin-api, na cestě,
kterou si frontend složí z klíče `squaremap-landmark`.

Po změně souřadnic tedy: `--markers`, `docker compose build admin-api`,
`docker compose up -d admin-api`.

### Prohlížení bez hry

```bash
python3 tools/look.py --centre 976 -192 --radius 17 --section -192
```

Vypíše půdorys (nejvyšší blok každého sloupce) a svislý řez. Rychlejší než
tam doběhnout.

## Co zbývá

- Staré místo na kopci (world ≈ −44..−4, 89) je po demolici rovná travnatá
  plošina; zaslouží si zvlnit, aby zase vypadalo jako kopec.
- Hřbitovní lípy sází `//forest`, takže každý běh `graveyard` přidá další.
- Pozor na `pathlib.write_text()` v jednorázových patch skriptech: soubor
  otevře a teprve pak selže na kódování, takže po pádu zůstane prázdný.
  Vždycky `encoding="utf-8"` (nebo `PYTHONUTF8=1`).
