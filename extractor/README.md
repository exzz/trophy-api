# Extracteur Trophy (côté Windows)

Petit service Python qui lit la base **HFSQL de CS Trophy Gestion** en
**lecture seule** et expose les données aux autres applications (l'API
FastAPI de `sterilog`). Il tourne **sous Windows**, sur ou près du serveur.

> Rien n'est jamais écrit dans la base Trophy. Le compte utilisé n'a que le
> droit de lecture : c'est le garde-fou principal.

## Contexte de l'installation observée

- Serveur HFSQL : **SERVEUR1**, service `Hyper File Server : CS Trophy Gestion`
  (`Manta.exe`, WinDev 25).
- Port : **4902** (`AccessPort` dans `HFConf.ini`).
- Racine des bases : `C:\Users\Public\Documents\Carestream\CS Data Trophy Gestion\`.
- Base applicative probable : **`Datas`** (à confirmer avec `discover.py`).

## 1. Créer le compte HFSQL en lecture seule

À faire une fois, avec le **Centre de Contrôle HFSQL version 25** (outil
officiel PC SOFT) :

1. Se connecter au serveur : `SERVEUR1`, port `4902`, avec un compte
   administrateur HFSQL.
2. Créer un utilisateur dédié, p. ex. `api_lecture`, avec un vrai mot de passe
   (plus de 8 caractères, lettres et chiffres).
3. Sur la base `Datas`, ne lui donner que le **droit de lecture**. Retirer
   écriture, suppression et modification de structure.
4. Vérifier, une fois le compte testé, que le compte `admin` par défaut a bien
   un mot de passe (par sécurité ; à faire hors heures d'ouverture, sauvegarde
   prête).

Ne pas réutiliser le compte applicatif de Trophy pour l'API.

## 2. Installer le pilote ODBC HFSQL + pyodbc

- Le **pilote ODBC HFSQL** est fourni par PC SOFT (répertoire `Install ODBC`
  de WINDEV/WEBDEV, ou téléchargement PC SOFT). Prendre la **version 25**, pour
  correspondre au serveur. Installer la variante **64 bits** si le Python est
  en 64 bits.
- Vérifier qu'il apparaît dans *Administrateur de sources de données ODBC
  (64 bits)* → onglet *Pilotes*. Le nom exact du pilote s'y lit (souvent
  `HFSQL` ou `HyperFileSQL`) : c'est la valeur à mettre dans `TROPHY_DRIVER`.
- Côté Python :
  ```bat
  python -m venv .venv
  .venv\Scripts\activate
  pip install pyodbc
  ```

## 3. Configurer et lancer la découverte

La connexion vient de `settings.json` à la racine du projet (voir
`../api/config.py` et `../settings.example.json`). Depuis la racine :

```bash
uv run python extractor/discover.py
```

Le script liste les tables, leurs colonnes et leur nombre de lignes, et écrit
`schema.json`. Aucune donnée patient n'est affichée.

Options :

- `--no-counts` : ne pas compter les lignes (plus rapide, charge nulle).
- `--like RDV` : ne garder que les tables dont le nom contient « RDV ».

Envoyer `schema.json` (qui ne contient que des noms de tables/colonnes et des
totaux) permet d'identifier les tables des patients, praticiens et
rendez-vous, puis d'écrire les requêtes de l'API.

## Dépannage

- **Pilote introuvable / `Data source name not found`** : le nom dans
  `TROPHY_DRIVER` ne correspond pas exactement au pilote installé, ou le Python
  et le pilote n'ont pas le même format (32 vs 64 bits).
- **Connexion refusée sur 4902** : vérifier le pare-feu entre le poste et
  SERVEUR1, et que le compte `api_lecture` existe bien côté serveur.
- **Fichiers protégés par mot de passe** : si une table ne s'ouvre pas en
  ODBC, c'est probablement un mot de passe au niveau fichier `.fic`. Le pilote
  OLE DB de PC SOFT est alors une piste de repli.
