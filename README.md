# Salesiánský Minecraft Server

Jedním ze salesiánských míst působnosti je i hřiště. Pro mnohé z nás to není jen venkovní prostor ale i ten virtuální. Proto jsme se rozhodli připravovat sérii tzv. LAN přespávaček. Tento repositář slouží jako podpora pro jezdnu z nich, konkrétně Minecraft LAN přespávačku. Reposiář obsahuje skripty a materiály nutné pro spuštěné serveru na pořádnou LAN párty.

## Spuštění serveru
```
docker compose up -d # run in background
```

## Snippety
```sh
docker container ls # list docker containers
docker stop <CONTAINER ID> # stop container
docker exec -i <CONTAINER ID> rcon-cli # open command terminal
```
