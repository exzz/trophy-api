# API parallèle CS Trophy Gestion (lecture seule)

Accès **lecture seule** aux **patients** et au **planning de rendez-vous par
praticien** de CS Trophy Gestion, sans passer par le logiciel. La base est un
serveur **HFSQL Client/Serveur** (WinDev 25) ; on l'interroge en ODBC/iODBC
via un petit client maison, exposé par une API REST FastAPI.

```
FastAPI (api/app.py)
   └─ api/trophy.py        (couche métier, requêtes SQL lecture seule)
        └─ extractor/hfsql.py   (client ODBC iODBC ANSI en ctypes)
             └─ driver/wd250hfo64.so  →  SERVEUR1:4902 (HFSQL, via Tailscale)
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
3. Réseau : accès à `SERVEUR1:4902` (ici via Tailscale, ACL ouverte).
4. Compte HFSQL **en lecture seule** sur la base `Datas`.
5. Dépendances : `uv sync` (crée `.venv` depuis `pyproject.toml` / `uv.lock`).
   Tests : `uv run pytest`.

## Configuration (variables d'environnement)

`env.sh` règle iODBC et les paramètres de connexion. À fournir en plus :

```bash
source env.sh
export TROPHY_UID=api_lecture
export TROPHY_PWD='********'
export TROPHY_API_KEY='une-cle-longue-et-aleatoire'
```

## Lancer

```bash
./api/run.sh                      # 127.0.0.1:8081 par défaut
# ou : uvicorn api.app:app --host 127.0.0.1 --port 8081
```

Doc interactive : http://127.0.0.1:8081/docs

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
curl -H "X-API-Key: $TROPHY_API_KEY" \
  "http://127.0.0.1:8081/appointments?practitioner=1&from=2026-01-05&to=2026-01-10"
```

## Sécurité (données de santé)

- Écoute sur `127.0.0.1` par défaut. Pour un accès distant, passer par
  **Tailscale**, **jamais** d'exposition publique directe.
- Clé API obligatoire ; la garder hors du dépôt.
- Accès strictement **lecture seule** côté HFSQL (compte dédié sans droit
  d'écriture) : ne jamais écrire dans la base Trophy.
- À traiter en parallèle, côté serveur : les partages Windows
  `CSDataTrophyGestion`, `TW`, `DIS`, `Users` sont ouverts à `Tout le monde`.

## Docker

Image seule (pas de compose). Le pilote natif HFSQL (`driver/`) est embarqué.

```bash
docker build -t trophy-api .
docker run -d --name trophy-api --network host \
  -e TROPHY_UID=api_lecture -e TROPHY_PWD='********' \
  -e TROPHY_API_KEY='une-cle-longue-et-aleatoire' \
  trophy-api            # écoute sur 8081
```

- **`--network host`** : le serveur HFSQL est une IP **Tailscale** (`TROPHY_SERVER`),
  joignable seulement via le réseau de l'hôte. Les secrets passent par `-e`
  (ou `--env-file`), jamais dans l'image.
- **Jamais `--workers > 1`** : une seule connexion HFSQL par process.
- Serveur HS → le process sort (SQLSTATE 08xxx) ; laisser Docker le relancer
  (`--restart unless-stopped`) comme systemd.

### Release (tag git semver → image à cette version)

```bash
deploy/release.sh 1.0.0     # builde trophy-api:1.0.0 (+ :latest), puis crée le tag git v1.0.0
```

Le tag git n'est créé que si le build réussit.

## Exploitation (systemd conseillé)

Vu la contrainte « une seule connexion par process », faire superviser le
service avec redémarrage automatique (voir `deploy/trophy-api.service`).
