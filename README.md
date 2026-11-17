# API parallèle CS Trophy Gestion (lecture seule)

Accès **lecture seule** aux **patients** et au **planning de rendez-vous par
praticien** de CS Trophy Gestion, sans passer par le logiciel. La base est un
serveur **HFSQL Client/Serveur** (WinDev 25) ; on l'interroge en ODBC/iODBC
via un petit client maison, exposé par une API REST FastAPI.

```
FastAPI (api/app.py)
   └─ api/trophy.py        (couche métier, requêtes SQL lecture seule)
        └─ extractor/hfsql.py   (client ODBC iODBC ANSI en ctypes)
             └─ driver/wd250hfo64.so  →  scm-ac-01.med.lan:4902 (HFSQL, LAN ou Tailscale)
```

## Pourquoi ce montage

- **pyodbc est inutilisable** avec le pilote HFSQL iODBC (SQLWCHAR 4 octets →
  « stack smashing »). D'où un client **100 % ANSI en ctypes** (`extractor/hfsql.py`).
- Le pilote HFSQL n'est stable **que sur le thread principal** → endpoints en
  `async def` (boucle d'événements = thread principal).
- Le pilote **ne supporte qu'une connexion par process** → une connexion
  unique, ouverte au démarrage, réutilisée, accès **sérialisés** par un verrou.
  Si la connexion est perdue : **relancer le service**.

## Prérequis

1. iODBC : `sudo apt install libiodbc2 libiodbc2-dev`
2. Pilote HFSQL v25 Linux 64 bits dans `driver/` (voir `driver/README.md`).
3. Réseau : accès à `scm-ac-01.med.lan:4902` (réseau du cabinet, ou Tailscale).
4. Compte HFSQL **en lecture seule** sur la base `Datas`.
5. Dépendances : `uv sync` (crée `.venv` depuis `pyproject.toml` / `uv.lock`).
   Tests : `uv run pytest`.

## Configuration (`settings.json`)

Toute la config (identifiants HFSQL + clé d'API) est dans **`settings.json`** à
la racine, **hors git** (comme sterilog/medirappel). Copier l'exemple :

```bash
cp settings.example.json settings.json   # puis renseigner password et api_key
chmod 600 settings.json
```

```json
{
  "hfsql": { "server": "100.79.174.114", "port": 4902, "database": "Datas",
             "username": "api_lecture", "password": "********" },
  "api_key": "une-cle-longue-et-aleatoire"
}
```

Le chemin est surchargeable par `TROPHY_SETTINGS` (tests, conteneur). Le pilote
natif est trouvé via `TROPHY_DRIVER` (défaut : `driver/wd250hfo64.so`).

## Lancer

```bash
# dev (rechargement auto) :
mise exec -- uv run uvicorn api.app:app --host 0.0.0.0 --port 8333 --reload
# prod local :
uv run uvicorn api.app:app --host 127.0.0.1 --port 8333
```

Doc interactive : http://127.0.0.1:8333/docs

## Endpoints

| Méthode / route            | Description                                   |
|----------------------------|-----------------------------------------------|
| `GET /health`              | état (sans clé)                               |
| `GET /practitioners`       | praticiens (`?include_inactive=true`). Chaque praticien inclut `horaires` : 7 jours (`jour_semaine` ISO, 1=lundi) avec `matin` et `apres_midi` `{ouvert, debut, fin}`. |
| `GET /holidays`            | jours fériés (`J_Feries`) : `?from=AAAA-MM-JJ`, `?to=AAAA-MM-JJ` **requis**. Renvoie `{date, libelle}`. |
| `GET /appointment-types`   | types de RDV (`TypeRDV`) : `{id, libelle, rdv_event, duree_min}` |
| `GET /patients`            | patients : `?q=`, `?practitioner=`, `?include_archived=`, `?limit=`, `?offset=`. Trié par `DATE_CREATION DESC` (derniers créés d'abord). Chaque fiche inclut `sms_actif` (bool). |
| `GET /patients/{num}`      | une fiche patient (inclut `sms_actif`)        |
| `GET /appointments`        | planning : `?practitioner=` **requis**, `?from=AAAA-MM-JJ`, `?to=AAAA-MM-JJ`, `?with_patient=`. Avec `with_patient=true`, l'objet `patient` inclut `mobile`, `tel` et `sms_actif` (plus besoin d'une requête par patient). Chaque RDV inclut `type_id` (NUM_TYPERDV). |

Toutes les routes (sauf `/health`) exigent l'en-tête `X-API-Key`.

Vérifié sur données réelles (2026-11-04) : `n=1 → lundi` (recoupement volume de
RDV / jours ouverts des praticiens 1 et 2) ; heures `HH*_n` au format
`HH:MM:SS.mmm` ; `DUREE_RDV` est une **heure** (`HH:MM:SS`), exposée convertie
en minutes (`duree_min`). `RDV_EVENT` vaut `1` (RDV patient) ou `2` (événement /
plage bloquée), exposé tel quel + `evenement` (bool, `=2`).

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://127.0.0.1:8333/appointments?practitioner=1&from=2026-01-05&to=2026-01-10"
```

## Sécurité (données de santé)

- Écoute sur `127.0.0.1` par défaut. Pour un accès distant, passer par
  **Tailscale**, **jamais** d'exposition publique directe.
- Clé API obligatoire ; la garder hors du dépôt.
- Accès strictement **lecture seule** côté HFSQL (compte dédié sans droit
  d'écriture) : ne jamais écrire dans la base Trophy.
- **Logs** : le journal d'accès uvicorn est désactivé (`--no-access-log` dans
  le Dockerfile / le service) car les URL portent des données patients (nom via
  `?q=`, identifiant via `/patients/{num}`). Seules les erreurs sont tracées
  (sur stderr). Attention : un message d'erreur HFSQL contient le **SQL** de la
  requête — une recherche en échec peut donc y laisser un nom. En tenir compte
  avant tout export de logs hors de la machine.
- À traiter en parallèle, côté serveur : les partages Windows
  `CSDataTrophyGestion`, `TW`, `DIS`, `Users` sont ouverts à `Tout le monde`.

## Docker

Image seule (pas de compose). Le pilote natif HFSQL (`driver/`) est embarqué.

```bash
docker build -t trophy-api .
docker run -d --name trophy-api --network host \
  -v "$PWD/settings.json:/config/settings.json:ro" \
  trophy-api            # écoute sur 8333
```

- **`settings.json` monté dans `/config`** (lecture seule) : il porte les
  identifiants HFSQL et la clé d'API ; jamais dans l'image. Le chemin interne
  est fixé par `TROPHY_SETTINGS=/config/settings.json`.
- **`--network host`** (image lancée seule) : moyen simple de joindre le serveur
  HFSQL (`settings.json → hfsql.server`). En prod, le stack compose utilise
  plutôt un réseau bridge (voir **Production**) ; `host` n'est pas obligatoire.
- **Jamais `--workers > 1`** : une seule connexion HFSQL par process.
- Connexion perdue (serveur Trophy redémarré / coupure réseau) → le process
  sort ; laisser Docker le relancer (`--restart unless-stopped`) comme systemd.
  La reconnexion en vol est impossible (le pilote segfault), d'où ce « exit +
  relance » qui repart sur une connexion saine.

### Release (tag git semver → image à cette version)

```bash
deploy/release.sh 1.0.0     # builde trophy-api:1.0.0 (+ :latest), puis crée le tag git v1.0.0
```

Le tag git n'est créé que si le build réussit.

## Production (stack compose `/srv/compose/cabinet`)

En prod, l'API tourne dans le stack Docker Compose **cabinet** (avec Sterilog et
MediRappel). Elle est sur le réseau **bridge** `cabinet` (pas `--network host`)
et joint le serveur HFSQL `scm-ac-01.med.lan:4902` par le routage de l'hôte —
réseau du cabinet ou Tailscale, indifféremment.

Arborescence (ce qui n'est pas dans l'image vit ici, sauvegardé d'un bloc) :

```
/srv/compose/cabinet/
├── compose.yaml                  # services trophy / sterilog / medirappel
├── .env                          # versions d'images + ports (hors git, chmod 600)
└── trophy/
    └── config/
        └── settings.json         # identifiants HFSQL + clé d'API
```

Service `trophy` (profil durci `x-hardened` partagé : `read_only`, `tmpfs /tmp`,
`cap_drop ALL`, `no-new-privileges`, `restart: unless-stopped`, réseau `cabinet`) :

```yaml
trophy:
  <<: *hardened
  image: trophy-api:${TROPHY_VERSION}   # version choisie dans .env
  user: 10011:10011                     # app_trophy (uid:gid)
  ports:
    - "127.0.0.1:8333:8333"             # lié à la loopback de l'hôte
  environment:
    TZ: Europe/Paris
  volumes:
    - ./trophy/config:/config:ro        # settings.json monté en lecture seule
```

- **Port** publié sur `127.0.0.1` seulement ; l'accès distant passe par un
  `tailscale serve` posé sur l'hôte, jamais d'exposition publique directe.
- **`settings.json`** appartient à `app_trophy:app_config` (droits `660`) ; le
  conteneur tourne en `10011:10011` = `app_trophy`, il le lit donc comme
  propriétaire.
- Entre conteneurs du stack, l'API répond à `http://trophy:8333`.

### Déployer une nouvelle version

```bash
deploy/release.sh X.Y.Z                      # build l'image + tag git (dans ce dépôt)
# puis sur l'hôte, dans /srv/compose/cabinet :
#   éditer .env → TROPHY_VERSION=X.Y.Z
docker compose up -d trophy
```

## Exploitation sans compose (systemd)

Alternative à Docker, hors du stack cabinet. Vu la contrainte « une seule
connexion par process », faire superviser le service avec redémarrage
automatique (voir `deploy/trophy-api.service`).
